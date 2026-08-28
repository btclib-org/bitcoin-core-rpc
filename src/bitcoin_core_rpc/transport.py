# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The HTTP layer: `HttpTransport`, `http_request`, and the bounded read.

Everything below an HTTP status is mapped onto `FetchError` here, and
nothing above it is: what a status *means* is `client.py`'s question, not
this module's. `urlopen_transport` is the only function in this package
that opens a socket.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from http.client import HTTPException, HTTPMessage
from math import isfinite
from time import monotonic
from typing import IO, Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from bitcoin_core_rpc.errors import BtcRpcTypeError, BtcRpcValueError, FetchError


def _is_integer(value: Any) -> bool:
    """Return whether value is an integer, with a bool not being one.

    `bool` is a subclass of `int`, so every field whose contract is an
    integer quantity takes `True` for the number one unless something says
    otherwise. The json boundary is what makes that worth refusing: `true`
    is what a configuration file decodes to, and an rpc error code of
    `True` is not the code 1.

    Shared with `client.py`'s own reading of a reply's `code`, and living
    here rather than there: this module and that one are the two that
    check an integer boundary, and this is the lower of the two.
    """
    return isinstance(value, int) and not isinstance(value, bool)


HttpTransport = Callable[[Request, float], tuple[int, bytes]]
"""What this module does its I/O with, and what `transport=` takes.

A callable given the built `Request` -- url, method, body and headers all
set -- and a timeout in seconds, answering with the HTTP status and the
response body. A status rather than an exception, because a JSON-RPC error
can arrive with a 500 and its body is the error object.

Two arguments and no more, so a transport of a caller's own owes four
things this module cannot check for it. `urlopen_transport` is the default
and does all four:

- *its own* bound on what it holds in memory while reading. There is
  nowhere in two arguments to pass `max_body_size`, and the limit applied
  to the bytes it hands back is a refusal after the allocation rather than
  instead of it;
- a bound on how long it holds the call. `timeout` is one number, and most
  client libraries spend it per socket operation, which a peer dripping a
  body resets forever; `urlopen_transport` reads it as a deadline for the
  whole exchange;
- no redirect followed. The request already carries the `Authorization`
  for the host it names, and a client library that follows a 30x sends
  that credential to whatever the `Location` says;
- its own thread-safety. `BitcoinCoreRpcClient` promises that concurrent
  calls are safe while its configuration is not mutated, and the transport
  is part of that configuration: a session object that is not thread-safe
  makes the client not thread-safe, and only its author knows which it is.
"""

# Long enough for `getrawtransaction` against a node reading from a cold
# transaction index, short enough that a caller notices a host that is not
# answering: urllib's own default is no timeout at all, i.e. whatever the
# socket does, which on a silently dropped connection is minutes
DEFAULT_TIMEOUT = 30.0
"""The seconds a call may take, unless `timeout` or `request_timeout` says.

For the default transport it bounds the whole exchange rather than each
socket operation, so a peer that keeps sending cannot outlast it. A reply
large enough to take longer than this to arrive is one of the cases for
`request_timeout`, along with the methods that legitimately run long.
"""

# An endpoint is allowed to be a host on the internet rather than the node
# beside the process, and `response.read()` with nothing in front of it
# lets that host hand over as much as it likes before any parser gets to
# refuse it. The deadline in `_read_bounded` bounds the time and not the
# memory: a fast peer sends a great deal well inside it.
#
# Twice Core's 4,000,000-byte buffer bound on a serialized block, plus room
# for the newline a proxy may add. A buffer bound and not a consensus rule,
# consensus capping the weight of a block rather than its size, which is
# why it is written out here rather than named as a limit of the protocol.
_MAX_BLOCK_SERIALIZED_SIZE = 4_000_000
DEFAULT_MAX_BODY_SIZE = 2 * _MAX_BLOCK_SERIALIZED_SIZE + 1024
"""How much of a reply this module will hold in memory, by default.

Twice Core's buffer bound on a serialized block, so a block as hex fits.
A default and not a ceiling on what a node can answer: `getblock` at
verbosity 2 renders every transaction as json and is larger, and so is
`listunspent` or `listtransactions` on a large wallet, which no block size
bounds at all. Those are ordinary calls, so the refusal names
`max_body_size` -- the one thing the caller has to change.
"""

# how much one read of the bounded read asks for. `read1` answers with one
# recv but *allocates* what it was asked for, and `HTTPResponse.read1`
# narrows that request only where it knows how: to the remaining
# `Content-Length`, or to the rest of the current chunk, and to neither for
# a body the close of the connection delimits. There `read1(max_body_size +
# 1)` would allocate the whole limit to hold a tip height, so widening the
# limit for one large answer would cost that on every small one. A fixed
# piece costs one more loop per piece and holds what it is about to read;
# `test_a_read_asks_for_no_more_than_a_chunk` keeps it fixed
_READ_CHUNK = 64 * 1024

# where a status stops being an answer and becomes a diagnosis: urlopen
# raises HTTPError from 400 up, so this is the same line drawn for a
# transport of a caller's own that catches its own errors and returns them
_CLIENT_ERROR = 400

MAX_ERROR_BODY_SIZE = 64 * 1024
"""How much of the body of a *failure* is kept, `max_body_size` not applying.

Enough to carry whatever the backend said with its status, and not the
megabytes an error page from something in the way can be. Truncated rather
than refused: an error page one octet over a caller's limit for a tip
height is still the diagnosis of why there is no height.
"""

# http and https, and nothing else. `urlopen` also speaks `file:` and
# `data:`, so a url taken from configuration could make this client read
# the local disk and report the bytes as a node's answer. Every entry
# point refuses against this, each on the url it is handed -- `http_request`
# on the string, `urlopen_transport` on the one inside a `Request` a caller
# built, `client.py`'s `_checked_url` on the one a caller wrote by hand
# before a client even exists -- which is what makes the S310 suppression
# true rather than hopeful
_SCHEMES = ("http", "https")


class _NoRedirect(HTTPRedirectHandler):
    """The handler that does not follow a 30x, and answers None to say so.

    `redirect_request` returning None means "not handled" to
    `OpenerDirector.error`, which then reaches `HTTPDefaultErrorHandler`
    and raises the `HTTPError` -- so a redirect arrives at `http_request`
    as the status and the bounded body of any other non-2xx.
    """

    # the seven positional parameters are urllib's own, not chosen here:
    # this overrides HTTPRedirectHandler.redirect_request, and a subclass
    # matches the base method's signature rather than shortening it.
    # No @override: typing has it from 3.12, the floor here is 3.10, and
    # this file takes nothing outside the standard library
    def redirect_request(  # type: ignore[explicit-override]  # noqa: PLR0917
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        """Answer None: no redirect is followed, whatever it points at."""
        return None


# The one opener this module does its I/O with, and what it is missing is
# the point: urllib's default `HTTPRedirectHandler`, which follows a 30x
# before any of this module sees a response. Three things it does that no
# caller asked for, read off CPython's urllib/request.py:
#
# - `redirect_request` copies every request header except `content-length`
#   and `content-type`, so an `Authorization` built for a node reaches
#   whatever host the redirect names -- a JSON-RPC POST also arriving there
#   as a GET;
# - `http_error_302` admits `http`, `https`, `ftp` and the empty scheme, so
#   an https request can be answered with an http target and the scheme
#   check of `http_request` covers only the first url;
# - it calls `fp.read()` with no argument before following, so the whole
#   intermediate body is read whatever `max_body_size` says.
#
# Refused rather than policed: a policy worth the name strips credentials
# across origins, refuses a downgrade, bounds every intermediate body and
# counts hops, which is a redirect implementation inside a module whose
# subject is one bounded request. What a same-origin redirect would buy --
# an endpoint that moved path -- is a url the caller fixes once, and the
# FetchError naming the status and the url is what tells them to. A caller
# passing a transport of their own does its own I/O, so what `requests` or
# `httpx` does with a 30x is theirs.
#
# `ProxyHandler({})` is the second thing missing, for the same reason.
# `build_opener` otherwise installs a `ProxyHandler` built from
# `getproxies()`, i.e. from `HTTP_PROXY`, `HTTPS_PROXY` and the system's
# proxy configuration -- so an rpc call to a node would be sent to whatever
# host an environment variable named, carrying the `Basic` credential this
# client puts on every request before being asked for it. Those variables
# are set for a browser or a package manager and inherited by everything in
# the shell, where the endpoint here is a node the caller named. A caller
# who does want a proxy has `HttpTransport`.
#
# An empty map does not install an inert handler, it installs none:
# `ProxyHandler.__init__` sets one `<scheme>_open` method per entry,
# `add_handler` keeps a handler only when it registered something, and
# `build_opener` drops the default of a class it was handed an instance
# of. So this argument is how the handler is *removed*.
#
# `build_opener` and not `install_opener`: the default opener is process
# wide, and a library that replaced it would decide this for every other
# user of `urlopen` in the program
_OPENER = build_opener(_NoRedirect, ProxyHandler({}))


def _assert_valid_timeout(timeout: float, what: str) -> None:
    """Refuse a timeout that is not a number of seconds to wait.

    A bool is not a duration and `timeout=True` would be one second; a
    zero or a negative one makes the socket give up before it connects;
    an infinity or a nan is what `Infinity` in a json configuration
    decodes to. All four reach the socket layer and fail there, out of
    the standard library rather than through this module's exceptions.

    Shared with `client.py`, which checks its own `timeout` and
    `request_timeout` the same way before either reaches this module.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise BtcRpcTypeError(f"non-numeric {what}: {timeout!r}")
    if not isfinite(timeout) or timeout <= 0:
        raise BtcRpcValueError(f"{what} is not a positive number of seconds: {timeout}")


def _assert_valid_max_body_size(max_body_size: int) -> None:
    """Refuse a limit that is no size, before it is read as one.

    A float reaches `read` and leaves through a bare `TypeError` about the
    argument of a read, from underneath the library rather than through its
    exception contract; a negative limit makes the bounded read ask for
    nothing and then report every body as too large. Zero is a size and is
    left alone: it says that only an empty body is an answer. `True` is not
    one -- `_is_integer` says why -- a limit of one octet being nobody's
    intention.
    """
    if not _is_integer(max_body_size):
        err_msg = f"non-integer max_body_size: {max_body_size}"
        raise BtcRpcTypeError(err_msg)
    if max_body_size < 0:
        raise BtcRpcValueError(f"negative max_body_size: {max_body_size}")


def _read_bounded(
    response: Any,
    max_body_size: int,
    where: str,
    deadline: float,
    *,
    truncate: bool = False,
) -> bytes:
    """Return the body, having never held more than the limit of it.

    `Content-Length` first, when the response carries one: a server
    announcing more than the limit is refused before a byte of it is
    read. It is not believed, though -- it is the sender's claim about
    the sender -- so the read is bounded as well, and by one octet more
    than the limit, which is what tells a body *at* the limit from one
    over it. A response with no headers at all carries none: `HTTPError`
    answers `headers` with the `hdrs` it was built from, and a caller's
    transport raising one has no opinion to put there.

    `truncate` is how the body of a *failure* is read: cut to the limit and
    answered rather than refused, an announced `Content-Length` over it
    included. `MAX_ERROR_BODY_SIZE` says why.

    `read1` and not `read`, and that is what makes `deadline` mean
    anything. The response reads through a `BufferedReader`, whose
    `read(n)` blocks until it has *n* octets or reaches EOF -- so
    `read(limit + 1)` is one call that returns when the whole body has
    arrived, and no check around it runs in the meantime. `read1(n)`
    returns after one underlying read, which is what puts the loop, and
    the deadline in it, between one packet and the next. Each read asks
    for `_READ_CHUNK` at most, that being what such a read allocates.

    `deadline` is a `monotonic()` reading, and is what a socket timeout
    cannot be: that one is per recv, so a peer sending an octet just inside
    it resets it with every packet and the limit is never reached. Checked
    before each read, so the wait is the deadline plus the one recv in
    flight when it passes.

    The accumulator is one `bytearray` grown with `extend`, not a `list` of
    chunks joined at the end: a list holds every chunk as its own object
    until the join, so a response near the limit sits in memory twice over
    for as long as both are in scope. What a single buffer cannot avoid is
    the one copy `bytes(buffer)` makes at the end, this function promising
    an immutable value -- so `max_body_size` bounds what is read and not
    the memory a call needs to read it, which is this bound plus that copy.
    """
    _assert_valid_max_body_size(max_body_size)

    # the announced size where there is something to read it from. urllib's
    # own responses always carry headers; an `HTTPError` a caller's
    # transport raised carries whatever it was built with, and `None` is
    # what a test double standing in for a busy node passes for a field it
    # has no opinion about -- which reached `.get` and left through an
    # AttributeError, outside the FetchError `http_request` promises
    headers = getattr(response, "headers", None)
    announced = None if headers is None else headers.get("Content-Length")
    if announced is not None and not truncate:
        # a header, so it can be anything: a value that is not a number
        # says nothing about the size and is left to the bounded read
        with suppress(ValueError):
            if int(announced) > max_body_size:
                err_msg = f"{where}: announced {int(announced)} bytes,"
                err_msg += f" more than the max_body_size of {max_body_size}"
                raise FetchError(err_msg)

    buffer = bytearray()
    remaining = max_body_size + 1
    while remaining > 0:
        if monotonic() > deadline:
            err_msg = f"{where}: still arriving when the timeout expired"
            raise FetchError(err_msg)
        chunk = response.read1(min(remaining, _READ_CHUNK))
        if not chunk:
            break
        buffer.extend(chunk)
        remaining -= len(chunk)

    if len(buffer) > max_body_size:
        if truncate:
            return bytes(buffer[:max_body_size])
        err_msg = f"{where}: response larger than the max_body_size of {max_body_size}"
        raise FetchError(err_msg)
    return bytes(buffer)


def urlopen_transport(
    request: Request,
    timeout: float,
    *,
    max_body_size: int = DEFAULT_MAX_BODY_SIZE,
) -> tuple[int, bytes]:
    """Perform the request with urllib, reading a bounded response.

    The default `HttpTransport`, and the only function here that opens a
    socket. It maps nothing and interprets nothing: the status and the
    bytes go back as they arrived, and `http_request` is where the
    failures become the exceptions above.

    Bounded, and this is the only place a bound can be incremental: the
    limit is a keyword with a default, so this function still *is* an
    `HttpTransport`. A transport of someone else's returns bytes it has
    already read, so all `http_request` can do for those is refuse to pass
    an oversized body on.

    No redirect is followed: `_OPENER` above says why, and what a 30x
    arrives as is the `HTTPError` any other non-2xx status does.

    `timeout` bounds the exchange and not each socket operation: the
    deadline is taken before the connect, so a peer that drips a body one
    octet at a time cannot hold this call open past it.

    The scheme, the timeout and the limit are checked here and not only
    where `http_request` already checks them, for the reason that function
    gives for its own copy: this one is public too, and it takes a
    `Request` a caller built. `urlopen` speaks `file:` and `data:` as well,
    so a request whose url came from configuration would otherwise make
    this transport read the local disk and report the bytes as a node's
    answer -- and an invalid control would be refused after the resource
    was opened rather than instead of opening it.
    """
    _assert_valid_timeout(timeout, "http timeout")
    _assert_valid_max_body_size(max_body_size)
    scheme = urlsplit(request.full_url).scheme
    if scheme not in _SCHEMES:
        raise BtcRpcValueError(f"invalid url scheme: '{scheme}' instead of http(s)")

    deadline = monotonic() + timeout
    # so what reaches the opener is http or https, whoever built the
    # request: the three lines above are what says so here, and a redirect
    # cannot introduce a second url
    with _OPENER.open(request, timeout=timeout) as response:
        body = _read_bounded(response, max_body_size, request.full_url, deadline)
        return response.status, body


def http_request(
    url: str,
    *,
    data: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    transport: HttpTransport = urlopen_transport,
) -> tuple[int, bytes]:
    """Return the status and body of a GET, or of a POST when data is given.

    Everything below the HTTP status is a FetchError: a refused
    connection, an unresolvable host and an expired timeout are one
    answer to the caller -- the backend did not answer -- and none of
    them is a bitcoin error worth a type of its own.

    A non-2xx status is *not* a failure here. It comes back like any
    other, because the body of a 500 is where bitcoind's legacy JSON-RPC
    1.1 reply puts its error object, and the body of a 404 is where an
    explorer says what it could not find. Deciding what a status means is
    the backend's job, that being the layer that knows. A 30x is one of
    those statuses now rather than a second request: `urlopen_transport`
    follows no redirect, and `_OPENER` says why.

    `max_body_size` is what an *answer* may weigh, and the caller sets it
    from what it asked for: a tip height is a few octets and a raw
    transaction is megabytes, so one number for both would be the larger.
    The body of a failure is bounded by `MAX_ERROR_BODY_SIZE` instead, and
    in time by `timeout`, the same deadline the answer is read against: a
    drip is a drip whichever status precedes it.

    `timeout` is checked here and not only where `BitcoinCoreRpcClient`
    already does, because this function is public on its own: a caller
    reaching it directly with a transport of their own would otherwise
    forward a zero, a negative number, `True` or a `NaN` straight to that
    transport unexamined.
    """
    _assert_valid_max_body_size(max_body_size)
    _assert_valid_timeout(timeout, "http timeout")

    scheme = urlsplit(url).scheme
    if scheme not in _SCHEMES:
        raise BtcRpcValueError(f"invalid url scheme: '{scheme}' instead of http(s)")

    # S310 asks what scheme this url can carry, and the answer is the three
    # lines above: nothing but http and https reaches a Request.
    #
    # `data is not None` and not the truth of it: `data=b""` is a body a
    # caller passed, so the request is the POST they asked for. urllib draws
    # the same line -- an absent body is what makes a request a GET there --
    # and Core answers a GET with "JSON-RPC: method not allowed", which is
    # not the diagnosis an empty body deserves
    request = Request(  # ruff: ignore[S310]
        url,
        data=data,
        headers=dict(headers or {}),
        method="POST" if data is not None else "GET",
    )
    # what the body of a failure is read against, taken here and not in the
    # `except` below, which runs once the exchange has already spent its
    # time. It is the reading `urlopen_transport` takes for itself, and a
    # transport of a caller's own that raises `HTTPError` is held to it for
    # the error body -- the only part of such an exchange this module reads
    deadline = monotonic() + timeout
    try:
        # the limit reaches the read itself for the transport of this
        # module, which is the only one it can reach: a caller's has
        # nowhere in two arguments to be told one. Identity and not a
        # subclass check because there is one such function, and it is the
        # default this module passes on
        if transport is urlopen_transport:
            status, body = urlopen_transport(
                request, timeout, max_body_size=max_body_size
            )
        else:
            status, body = transport(request, timeout)
    except HTTPError as e:
        # a subclass of URLError, so it has to be caught before the OSError
        # below. It is also a response, and one `_read_bounded` can read:
        # `HTTPError` forwards `read1` to the response it wraps and answers
        # `headers` with the ones it was built from. Discarding that body
        # would turn whatever diagnosis the backend offered into a bare
        # number; the bound is because an error page is neither a size nor a
        # wait this library agreed to
        try:
            try:
                return e.code, _read_bounded(
                    e, MAX_ERROR_BODY_SIZE, url, deadline, truncate=True
                )
            except (OSError, HTTPException, FetchError):
                # the body of the failure failed too -- a connection dropped
                # mid-error-page is `IncompleteRead` here, and one still
                # arriving at the deadline is the `FetchError` the bounded
                # read raises. The status is the part worth keeping and it
                # is already in hand, so it goes back with no body rather
                # than replacing a 503 a caller has a policy for with a
                # report about reading it
                return e.code, b""
        finally:
            # an HTTPError is a response, and a bounded read leaves it with
            # octets still in it. An unclosed one is a ResourceWarning out
            # of a deallocator at whatever later moment the collector picks
            # -- which under `filterwarnings = ["error"]` fails an
            # unrelated test. The `with` in `urlopen_transport` does this
            # for the responses that are not errors
            e.close()
    except (OSError, HTTPException) as e:
        # URLError and TimeoutError derive from OSError, which is every way
        # urllib reports that the exchange did not happen. `HTTPException` is
        # the other family and no relation of it: `IncompleteRead` from a
        # chunked body that stopped early, `BadStatusLine` and `LineTooLong`
        # from a peer that is not speaking HTTP. Those arrive from inside the
        # read rather than from the connect, so nothing above catches them,
        # and this function promises that everything below the status is a
        # FetchError
        raise FetchError(f"no answer from {url}: {e}") from e

    # a failure, whether it arrived as an exception above or as a status
    # from a transport that catches its own: the body is a diagnostic and
    # not the answer, so it is truncated rather than held to the caller's
    # limit for an answer -- `MAX_ERROR_BODY_SIZE` says why
    if status >= _CLIENT_ERROR:
        return status, body[:MAX_ERROR_BODY_SIZE]

    # the transport of this module has already stopped reading at the
    # limit; a caller's own has not, and cannot be made to, so this is
    # what is left to promise for one: an oversized answer goes no further
    if len(body) > max_body_size:
        err_msg = f"{url}: response of {len(body)} bytes,"
        err_msg += f" more than the max_body_size of {max_body_size}"
        raise FetchError(err_msg)
    return status, body
