# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The HTTP layer: `HttpTransport`, `http_request`, and the bounded read.

Everything below an HTTP status is mapped onto `FetchError` here, and
nothing above it is: what a status *means* is `client.py`'s question, not
this module's. `urlopen_transport` and `SessionTransport` are the two
things here that open a socket, both through `_connect`; nothing else in
this module does.
"""

from __future__ import annotations

import select
from collections.abc import Callable, Mapping
from contextlib import suppress
from http.client import (
    HTTPConnection,
    HTTPException,
    HTTPMessage,
    HTTPSConnection,
)
from io import BufferedReader, RawIOBase
from math import isfinite
from socket import AI_NUMERICHOST, SOCK_STREAM, gaierror, getaddrinfo, socket
from threading import Lock, Thread
from time import monotonic
from typing import IO, Any, Protocol, Self
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPHandler,
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from bitcoin_core_rpc.errors import BtcRpcTypeError, BtcRpcValueError, FetchError

# Every name this module defines, none of it imported: `__init__.py`'s own
# `__all__` is their union across the four modules of the package, and
# section 7 of the organization standard asks each of them for its own
# besides.
__all__ = [
    "DEFAULT_MAX_BODY_SIZE",
    "DEFAULT_TIMEOUT",
    "MAX_ERROR_BODY_SIZE",
    "HttpTransport",
    "SessionTransport",
    "http_request",
    "urlopen_transport",
]


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

For both transports of this module it bounds the whole exchange rather
than each socket operation -- name resolution, connect, send, status line,
headers and body -- so a peer that keeps sending cannot outlast it. A reply
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

# how much one send of a request offers the socket, `_DeadlineSocket.sendall`
# saying why there is a bound at all
_SEND_CHUNK = 64 * 1024

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
    # No @override: typing has it from 3.12, the floor here is 3.11, and
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


# The deadline below the response, where `_read_bounded` cannot reach.
# `http.client` spends a socket timeout per operation: every recv of the
# status line and of each header waits up to the full timeout again, so a
# peer dripping headers holds the call as long as it keeps dripping --
# and `http.client` accepts a hundred header lines of 64 KiB each before
# it refuses any. The connections both transports here open hold every
# step to one deadline instead: the lookup, each connect attempt, the TLS
# handshake, every send and every recv, each given what is left of it.


def _seconds_left(deadline: float) -> float:
    """Return what is left of `deadline` for one socket operation.

    Raising the `TimeoutError` a socket raises when its own timeout
    expires, so a deadline passing between two operations and one passing
    during an operation reach the caller as the same exception. Never a
    timeout of zero or less for the socket: zero would make it
    non-blocking, and a negative one is a `ValueError`.
    """
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError("timed out")
    return remaining


def _resolve(host: str, port: int, deadline: float) -> list[tuple[Any, ...]]:
    """Return `getaddrinfo`'s answer for `host`, waited for until `deadline`.

    No socket timeout reaches name resolution: `getaddrinfo` is the
    system resolver's call, and it takes as long as that resolver's own
    configuration allows, whatever the caller asked for. So the lookup
    runs in a daemon thread, and the call waits for it only until the
    deadline. A resolver that has not answered by then leaves that thread
    blocked in it until the resolver's own timeout ends the lookup, the
    call having raised already; the thread holds nothing but the lookup,
    and being a daemon it does not keep the process from exiting.

    An address is asked for with `AI_NUMERICHOST` first, which consults
    no resolver, so an endpoint written as an address starts no thread.
    """
    with suppress(gaierror):
        return getaddrinfo(host, port, type=SOCK_STREAM, flags=AI_NUMERICHOST)

    answer: list[list[tuple[Any, ...]] | Exception] = []

    def look_up() -> None:
        # whatever the lookup raises is handed to the waiting thread and
        # raised there, as it would have been without this thread: a
        # `gaierror`, or the `UnicodeError` an unencodable host name is
        try:
            answer.append(getaddrinfo(host, port, type=SOCK_STREAM))
        except Exception as e:  # noqa: BLE001
            answer.append(e)

    lookup = Thread(target=look_up, name=f"getaddrinfo {host}", daemon=True)
    lookup.start()
    # `_seconds_left` itself would raise a bare "timed out" here if the
    # deadline is already gone by this line -- reached before `.join()`
    # ever runs on a slow enough thread start -- masking the message
    # below with one naming no host. `join` takes zero or a negative
    # timeout as "don't wait", so clamping keeps that message the one
    # answer given the deadline, however it was already spent.
    lookup.join(max(0.0, deadline - monotonic()))
    if not answer:
        raise TimeoutError(f"timed out resolving {host}")
    if isinstance(answer[0], Exception):
        raise answer[0]
    return answer[0]


def _connect(host: str, port: int, deadline: float) -> socket:
    """Return a socket connected to `host`, every step held to `deadline`.

    `socket.create_connection`, which `http.client` calls otherwise,
    gives each address the resolver answers the whole timeout, so a host
    with two addresses that both drop the SYN is waited for twice. Each
    attempt here is given what is left instead. The socket comes back
    with its timeout set to what is left once connected, and that is the
    bound on a TLS handshake over it: CPython's `ssl` reads a socket's
    timeout as one deadline over the whole handshake, not one per read.
    """
    error: OSError = OSError(f"no address for {host}")
    for family, kind, protocol, _, address in _resolve(host, port, deadline):
        sock = socket(family, kind, protocol)
        try:
            sock.settimeout(_seconds_left(deadline))
            sock.connect(address)
            sock.settimeout(_seconds_left(deadline))
        except OSError as e:
            sock.close()
            error = e
        else:
            return sock
    raise error


class _DeadlineReader(RawIOBase):
    """The raw stream a response reads through, one recv per deadline check.

    Over the socket's own unbuffered `makefile`, so the socket counts this
    stream as open exactly as it counts the one `http.client` would have
    made: urllib closes the socket once the status and headers are in,
    and the descriptor stays open for as long as the response reads.
    """

    def __init__(
        self, sock: socket, raw: RawIOBase, seconds_left: Callable[[], float]
    ) -> None:
        super().__init__()
        self._sock = sock
        self._raw = raw
        self._seconds_left = seconds_left

    def readable(self) -> bool:  # type: ignore[explicit-override]
        """Answer True: this stream is the reading half of a socket."""
        return True

    # `Any` and not the buffer protocol: typeshed's name for it is private,
    # and `collections.abc.Buffer` is 3.12's
    def readinto(self, buffer: Any) -> int | None:  # type: ignore[explicit-override]
        """Read one recv into `buffer`, having given it what is left."""
        self._sock.settimeout(self._seconds_left())
        return self._raw.readinto(buffer)

    def close(self) -> None:  # type: ignore[explicit-override]
        """Close the socket's stream beneath, and this one."""
        self._raw.close()
        super().close()


class _DeadlineSocket:
    """A connected socket whose every send and recv is given what is left.

    What `http.client` holds as the connection's `sock`: it sends through
    `sendall` and reads a response through `makefile`, and those two are
    the ones answered here. Everything else it or `SessionTransport` asks
    of a socket -- `close`, `settimeout`, the `fileno` a readability probe
    registers -- goes to the socket itself.
    """

    def __init__(self, sock: socket, seconds_left: Callable[[], float]) -> None:
        self._sock = sock
        self._seconds_left = seconds_left

    def __getattr__(self, name: str) -> Any:
        return getattr(self._sock, name)

    def sendall(self, data: Any) -> None:
        """Send all of `data`, each send given what is left of the deadline.

        One `send` at a time rather than `socket.sendall` under one
        timeout: `SSLSocket.sendall` is a loop of sends each given the
        whole timeout, and so is PyPy's plain `socket.sendall`, so a peer
        reading slowly would reset it with every piece it takes.

        Each send is offered `_SEND_CHUNK` at most. A `send` on PyPy costs
        time in proportion to the buffer it is handed, not to what the
        socket takes of it, so offering the rest of a large body every
        time makes the whole send quadratic in its size. For the same
        reason a view is cast to octets only where its items are not
        octets already: slicing a cast view is what costs, on PyPy, and
        the request `http.client` sends is `bytes`.
        """
        view = memoryview(data)
        if view.nbytes != len(view):
            view = view.cast("B")
        while view:
            self._sock.settimeout(self._seconds_left())
            view = view[self._sock.send(view[:_SEND_CHUNK]) :]

    def makefile(self, _mode: str) -> BufferedReader:
        """Return the stream a response reads, `http.client` asking for "rb"."""
        raw = self._sock.makefile("rb", buffering=0)
        return BufferedReader(_DeadlineReader(self._sock, raw, self._seconds_left))


class _DeadlineHTTPConnection(HTTPConnection):
    """An `HTTPConnection` holding every socket operation to `deadline`.

    `deadline` is taken from `timeout` when the connection is built, which
    urllib does for every request and `SessionTransport` for every new
    connection, and `SessionTransport` then sets it to each call's own
    before sending, over a new connection and a kept one alike.
    """

    def __init__(
        self,
        host: str,
        port: int | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> None:
        super().__init__(host, port, timeout=timeout, **kwargs)
        self.deadline = monotonic() + timeout
        # `http.client`'s own seam for how a connection's socket is made,
        # the one attribute `connect()` calls for it, here and in
        # `HTTPSConnection`, which wraps the answer in TLS
        self._create_connection = self._connect

    def _connect(
        self, address: tuple[str, int], _timeout: object, _source: object = None
    ) -> socket:
        # the timeout is replaced by the deadline, and a source address is
        # something nothing here sets: neither urllib nor `_new_connection`
        # passes one
        return _connect(*address, self.deadline)

    def _seconds_left(self) -> float:
        return _seconds_left(self.deadline)

    def connect(self) -> None:  # type: ignore[explicit-override]
        """Connect, then hold every later send and recv to the deadline."""
        super().connect()
        self.sock = _DeadlineSocket(self.sock, self._seconds_left)


class _DeadlineHTTPSConnection(_DeadlineHTTPConnection, HTTPSConnection):
    """The same, over TLS: the handshake is `_connect`'s, the rest is ours."""


class _DeadlineHTTPHandler(HTTPHandler):
    """urllib's `http` handler, opening a `_DeadlineHTTPConnection`."""

    def do_open(  # type: ignore[explicit-override]
        self, http_class: Any, req: Request, **http_conn_args: Any
    ) -> Any:
        """Open `req` over a connection held to its deadline."""
        return super().do_open(_DeadlineHTTPConnection, req, **http_conn_args)


class _DeadlineHTTPSHandler(HTTPSHandler):
    """urllib's `https` handler, opening a `_DeadlineHTTPSConnection`."""

    def do_open(  # type: ignore[explicit-override]
        self, http_class: Any, req: Request, **http_conn_args: Any
    ) -> Any:
        """Open `req` over a connection held to its deadline."""
        return super().do_open(_DeadlineHTTPSConnection, req, **http_conn_args)


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
#
# The two handlers after those are urllib's own for `http` and `https`,
# replacing the defaults of their classes the same way, and opening the
# connections above that hold the exchange to its deadline
_OPENER = build_opener(
    _NoRedirect, ProxyHandler({}), _DeadlineHTTPHandler, _DeadlineHTTPSHandler
)


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
    flight when it passes -- a recv that, over a connection either
    transport here opened, is itself given only what is left of the
    deadline.

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

    The default `HttpTransport`, and one of the two things here that open
    a socket. It maps nothing and interprets nothing: the status and the
    bytes go back as they arrived, and `http_request` is where the
    failures become the exceptions above.

    Bounded while reading, the limit being a keyword with a default, so
    this function still *is* an `HttpTransport` -- `SessionTransport` takes
    it the same way. A transport of someone else's returns bytes it has
    already read, so all `http_request` can do for those is refuse to pass
    an oversized body on.

    No redirect is followed: `_OPENER` above says why, and what a 30x
    arrives as is the `HTTPError` any other non-2xx status does.

    `timeout` bounds the exchange and not each socket operation: the
    connection urllib builds for the request takes its deadline from it
    before it connects, and gives every step of the exchange what is left
    of that -- so a peer that drips headers or a body one octet at a time
    cannot hold this call open past it.

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
        # the limit reaches the read itself for the two transports of this
        # module, each taking it as a keyword beside the two arguments of an
        # `HttpTransport`: a caller's own has nowhere in those two to be told
        # one. `urlopen_transport` by identity, there being one such
        # function, and `SessionTransport` by type, it being a class a
        # caller builds instances of
        if transport is urlopen_transport:
            status, body = urlopen_transport(
                request, timeout, max_body_size=max_body_size
            )
        elif isinstance(transport, SessionTransport):
            status, body = transport(request, timeout, max_body_size=max_body_size)
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

    # the transports of this module have already stopped reading at the
    # limit; a caller's own has not, and cannot be made to, so this is
    # what is left to promise for one: an oversized answer goes no further
    if len(body) > max_body_size:
        err_msg = f"{url}: response of {len(body)} bytes,"
        err_msg += f" more than the max_body_size of {max_body_size}"
        raise FetchError(err_msg)
    return status, body


# What a *write* into a connection the peer already closed raises: the
# request did not reach the wire in full, because the local send is what
# failed. This set is for `request()` alone -- a malformed but present
# response is a `BadStatusLine` or a `LineTooLong` neither derives from,
# which is what keeps a garbled reply from a live node out of it.
# `RemoteDisconnected` is a `ConnectionResetError` and has no entry of its
# own: `http.client` raises it reading a status line, which `request()`
# does only through a proxy tunnel's `CONNECT`, and this transport sets no
# tunnel.
#
# `getresponse()` is not read against this set, nor against any other: by
# then `request()` has returned, the whole request has been handed to the
# socket, and a failing read is no evidence that the node did not execute
# it -- one that did and closed before answering raises `RemoteDisconnected`
# there.
_STALE_CONNECTION_ERRORS = (
    BrokenPipeError,
    ConnectionAbortedError,
    ConnectionResetError,
)


class _Connection(Protocol):
    """The subset of `http.client.HTTPConnection` `SessionTransport` drives.

    A `Protocol` and not that class itself, so a test's fake stands in
    without inheriting anything of it: a fake answers for this whole
    interface without ever opening a real socket.
    """

    sock: Any
    # the `monotonic()` reading every socket operation is held to, set by
    # `SessionTransport` before each call it makes over the connection
    deadline: float
    # `float | None`, matching `HTTPConnection.timeout`'s own stub: it
    # takes `_GLOBAL_DEFAULT_TIMEOUT`, typed as `None`, for "the socket
    # module's default" -- a value this transport never assigns, always
    # passing a checked `float`, but the attribute's declared type has to
    # agree with the real class's for a fake to satisfy this Protocol
    # *and* `_new_connection` below to satisfy it by returning one
    timeout: float | None

    def request(
        self,
        method: str,
        url: str,
        # `Any` on both: `HTTPConnection.request`'s own stub takes a wider
        # union for a body this transport never constructs -- it only
        # ever forwards `Request.data`, already `bytes | None` -- and a
        # `headers` value type wider than the `str` this transport ever
        # puts there, with no `None` default. Matching either narrower
        # would make the real class fail to satisfy the Protocol it is
        # the default implementation of
        body: Any = None,
        headers: Any = None,
    ) -> None:
        """Send a request over this connection, connecting first if idle."""

    def getresponse(self) -> Any:
        """Return the response to the request just sent.

        `Any`, and so no contract a type checker holds a fake to: what
        `SessionTransport` reads of it is `http.client.HTTPResponse`'s,
        `isclosed()` included, asked after an error status to learn whether
        the body was read to its end.
        """

    def close(self) -> None:
        """Close the socket, discarding whatever this connection held."""


def _new_connection(
    scheme: str, host: str, port: int, timeout: float
) -> _DeadlineHTTPConnection:
    """Build the `http.client` connection `SessionTransport` defaults to.

    `_DeadlineHTTPSConnection` for `https`, `_DeadlineHTTPConnection`
    otherwise -- the same connections, split the same way by scheme, that
    urllib's handlers open for `urlopen_transport`. `timeout` is what the
    connection's first deadline is taken from; `SessionTransport` sets the
    call's own over it before anything is sent.
    """
    connection_class = (
        _DeadlineHTTPSConnection if scheme == "https" else _DeadlineHTTPConnection
    )
    return connection_class(host, port, timeout=timeout)


def _is_reused_connection_dead(connection: _Connection) -> bool:
    """Return whether a pooled connection's socket already saw the peer gone.

    A zero-timeout readability probe, asked of the kept socket before
    anything is sent on it again: HTTP/1.1 answers one request at a time,
    so a kept connection with no request in flight has nothing pending to
    make its socket readable except the peer's own close or reset -- an
    idle timeout on the other end, unrelated to anything this transport
    does. A live, still-open connection reports nothing, and this returns
    `False` for it without reading anything from the socket or blocking
    on it.

    `select.poll` where the platform has it, and `select.select` only
    where it does not -- Windows. Outside Windows `select.select` refuses
    a descriptor at or above `FD_SETSIZE` with a `ValueError`, so a
    process holding that many open files could not reuse a connection at
    all; on Windows it bounds how many descriptors one call holds rather
    than their value, and this asks about one. `urllib3`'s
    `wait_for_read` makes the same choice for the same reason. Any event
    `poll` reports counts: `POLLHUP` and `POLLERR` arrive unasked beside
    `POLLIN`, and each is a peer that is gone.
    """
    if hasattr(select, "poll"):
        poller = select.poll()
        poller.register(connection.sock, select.POLLIN)
        return bool(poller.poll(0))
    readable, _, _ = select.select([connection.sock], [], [], 0)
    return bool(readable)


def _time_left(deadline: float, where: str) -> float:
    """Return the seconds left before `deadline`, refusing none or fewer.

    What a connect, a reconnect and a reused connection's refreshed socket
    timeout are all given, in place of the `timeout` argument `__call__`
    was handed: the deadline is over the whole exchange, so a reconnect
    reached after a slow first attempt gets what is left of the budget and
    not a second full one. Raising here rather than handing a socket a
    zero or negative timeout is what keeps this transport out of the
    `ValueError` a real socket answers that with, this being the one place
    the deadline can already be spent before any connect is attempted.
    """
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise FetchError(f"{where}: timeout expired before the exchange completed")
    return remaining


class SessionTransport:
    """An `HttpTransport` that keeps one connection per `(scheme, host, port)`.

    `urlopen_transport` opens a socket, sends `Connection: close` -- not
    its own choice but urllib's `AbstractHTTPHandler.do_open`, which sets
    the header unconditionally -- and lets the node close it. This one
    does not: it keeps the connection `http.client` gives it and hands the
    same one to the next call addressed to the same scheme, host and port,
    so a caller making many calls against one node pays the connect cost,
    and on `https` the TLS handshake, once rather than every time.

    `max_body_size` and the timeout mean what they mean for
    `urlopen_transport`: `max_body_size` bounds what one answer holds in
    memory, and `timeout` is a deadline over the whole exchange -- connect
    or reuse, send, and read -- taken as one `monotonic()` reading before
    any of the three. The connection is given it as its `deadline`, which
    every lookup, connect, send and recv over the connection `_new_connection`
    builds is held to, and it is what `_read_bounded` reads the response
    against, the same bounded, chunked read `urlopen_transport` uses. No
    redirect is followed: `http.client` does not follow one on its own,
    so a 30x already arrives as the status and body of any other
    response, with nothing here needing to refuse it.

    **Thread safety.** One instance is safe to share between threads, and
    the contract is one lock guarding the whole exchange rather than one
    per connection: a socket can carry one request at a time, so two
    threads sharing a connection have to be serialized somewhere, and
    guarding only the dict of connections would still let both drive the
    same socket's `request()` and `getresponse()` at once, which is
    corruption on the wire rather than a data race Python's own GIL
    prevents. Serializing the whole call is what rules that out, at the
    cost of one instance never running two calls concurrently even
    across different hosts; a caller wanting that keeps one instance per
    host, the same shape `BitcoinCoreRpcClient` already asks a caller's
    own transport for.

    **A kept connection is probed before it is reused.** A connection
    this transport kept open is one the node may since have closed on its
    own -- an idle timeout on the other end, unrelated to anything this
    transport does -- and whether a `send()` into that socket fails
    outright, succeeds and only the read afterwards fails, or fails as a
    plain `ConnectionResetError` at either step, is a detail of what the
    peer did (a graceful `close()` versus a `shutdown()`) and of timing
    that this transport does not control and cannot tell apart from a
    healthy connection's own silence by guessing. Before every reuse, a
    zero-timeout probe asks the kept socket whether it is already
    readable with no request in flight -- `_is_reused_connection_dead`
    above -- which is unambiguous under HTTP/1.1's one-request-at-a-time
    shape: a live connection with nothing asked of it reports
    not-readable. A readable probe evicts the kept connection and opens a
    fresh one before anything at all is sent, which is not the reconnect
    below -- nothing has been written yet, so there is nothing to have
    sent twice -- and the fresh connection's own first failure, if the
    node itself is also unreachable, is the ordinary fresh-connection
    case: a node not answering, which no reconnect fixes either.

    **The one reconnect is on the write.** What the probe above does not
    catch is a drop landing after it: between the probe and the write,
    or after the write. Where the write is what notices -- one of
    `_STALE_CONNECTION_ERRORS` out of `request()` -- the request never
    reached the wire in full, so no node can have executed it, and it is
    sent once more on a fresh connection. Where the read is what
    notices, nothing is sent again, whatever it raises: `request()` has
    returned, so the whole request was written, and
    `http.client.RemoteDisconnected` -- the end of the stream where a
    status line belongs -- is what a node that executed the call and
    closed before answering produces. That failure propagates,
    `http_request` reports it as a `FetchError`, and whether to send the
    request again is the caller's decision, for the reason the package
    docstring's *One call, one HTTP request, and no retry* gives: the
    node may have executed it. The reconnect is offered only where the
    connection was already open before this call, and once: a fresh
    connection failing the same way is a node not answering, which no
    reconnect fixes, and a failure of the reconnect's own attempt is not
    caught again. The end of the write is the line the reconnect must
    not cross, and a status line that did arrive is further past it
    still: a response that began and then broke -- a truncated body, a
    malformed header -- is not re-sent.

    **Nothing failed is left pooled.** Any exception `request()` or
    `getresponse()` raises that the paragraph above does not resolve into
    a successful reconnect closes the connection and drops it from the
    pool before propagating, whether the connection was fresh or reused:
    a `(scheme, host, port)` a first attempt could not reach stays usable
    for the next attempt once the node answers, rather than failing
    forever on a dead connection object no later call has any way to
    replace. Only a connection an exchange actually completed over is
    kept.

    Not a pool of several connections per key, and not eviction under
    memory pressure: one caller talks to one node, sometimes a second for
    a second wallet, which is one or two keys for the life of the
    process -- the pool a caller polling many nodes would want is closer
    to what `requests` or `httpx` already build.

    No connection is opened by the constructor: one is asked for on the
    first call addressed to a given `(scheme, host, port)`.
    `connection_factory` is the seam a test replaces it with, taking the
    scheme, the host, the port and the timeout and answering something
    with `_Connection`'s interface -- a fake never opening a real socket,
    `_new_connection` above doing exactly that for everything else.
    """

    def __init__(
        self,
        *,
        connection_factory: Callable[
            [str, str, int, float], _Connection
        ] = _new_connection,
    ) -> None:
        self._connection_factory = connection_factory
        self._connections: dict[tuple[str, str, int], _Connection] = {}
        self._lock = Lock()

    def _send_and_receive(
        self,
        key: tuple[str, str, int],
        *,
        method: str,
        path: str,
        body: Any,
        headers: Any,
        deadline: float,
        url: str,
    ) -> Any:
        """Send over the connection pooled for `key`, and read the status line.

        Called with `self._lock` already held, so this is not a public
        entry point of its own: the pool it reads and writes is not
        otherwise guarded. On return, `self._connections[key]` holds
        whichever connection the response came over -- reused, freshly
        made, or the write-side reconnect's own -- so a caller reads it
        back from there rather than being handed it directly.

        Where the reconnect below does not apply, this closes and drops
        whatever connection was in play before re-raising: the class
        docstring's *Nothing failed is left pooled* is what that pays
        for, and its two paragraphs above are the pre-write probe and
        the write-side reconnect this catches instead.
        """
        connection = self._connections.get(key)
        reused = connection is not None
        if connection is not None and _is_reused_connection_dead(connection):
            # Caught before anything is sent, so this is not the one
            # reconnect below spending its budget: a connection that was
            # never written to has nothing to have sent twice, and what
            # replaces it is asked for exactly like a key never seen
            # before -- `reused` becomes `False` for it too. Popping the
            # key here, not only closing the connection, is what keeps a
            # `_time_left` raise on the very next line -- outside the
            # `try` below -- from leaving this closed connection pooled
            # for a later call's probe to register a socket that is
            # `None`: closing alone does not remove the entry, only a
            # successful exchange overwrites it.
            connection.close()
            self._connections.pop(key, None)
            connection = None
            reused = False
        if connection is None:
            connection = self._connection_factory(*key, _time_left(deadline, url))
        else:
            # what a connection that reads no `deadline` is held to instead,
            # one socket operation at a time
            remaining = _time_left(deadline, url)
            connection.timeout = remaining
            connection.sock.settimeout(remaining)
        connection.deadline = deadline

        try:
            try:
                connection.request(method, path, body=body, headers=headers)
            except _STALE_CONNECTION_ERRORS:
                if not reused:
                    raise
                connection.close()
                connection = self._connection_factory(*key, _time_left(deadline, url))
                connection.deadline = deadline
                connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
        except BaseException:
            connection.close()
            self._connections.pop(key, None)
            raise

        self._connections[key] = connection
        return response

    def __call__(
        self,
        request: Request,
        timeout: float,
        *,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    ) -> tuple[int, bytes]:
        """Send `request` over the connection kept for its host and port.

        Opens one where none is kept yet, reconnects once where writing
        to the kept one fails, and answers the status and the bounded
        body -- an `HttpTransport`, like `urlopen_transport`.

        `max_body_size` bounds this one answer. A keyword with a default,
        as `urlopen_transport`'s is, so this is still an `HttpTransport`;
        `http_request` passes each call's own. Checked before anything is
        sent, so an invalid limit costs no request.
        """
        _assert_valid_timeout(timeout, "http timeout")
        _assert_valid_max_body_size(max_body_size)
        parts = urlsplit(request.full_url)
        if parts.scheme not in _SCHEMES:
            err_msg = f"invalid url scheme: '{parts.scheme}' instead of http(s)"
            raise BtcRpcValueError(err_msg)
        if parts.hostname is None:
            raise BtcRpcValueError(f"no host in url: {request.full_url!r}")
        try:
            # `.port` is a property, not a stored field: unlike the scheme
            # and the host, an unparsable one -- "http://host:abc/" --
            # raises a bare `ValueError` out of `urlsplit` itself only
            # once asked for, which is here and not before
            port = parts.port or (443 if parts.scheme == "https" else 80)
        except ValueError as e:
            err_msg = f"invalid port in url: {request.full_url!r}"
            raise BtcRpcValueError(err_msg) from e
        key = (parts.scheme, parts.hostname, port)
        method = request.get_method()
        path = request.selector
        headers = dict(request.unredirected_hdrs)
        headers.update(request.headers)
        body = request.data
        deadline = monotonic() + timeout

        with self._lock:
            response = self._send_and_receive(
                key,
                method=method,
                path=path,
                body=body,
                headers=headers,
                deadline=deadline,
                url=request.full_url,
            )

            try:
                # A body under a status from 400 up is the node's
                # diagnosis, not the answer the caller sized
                # `max_body_size` for. The same bound `http_request` reads
                # `urlopen_transport`'s HTTPError against applies here so a
                # legacy 1.1 rpc error under HTTP 500 still surfaces as
                # that error rather than a FetchError about the page being
                # larger than the success-body limit.
                if response.status >= _CLIENT_ERROR:
                    body_bytes = _read_bounded(
                        response,
                        MAX_ERROR_BODY_SIZE,
                        request.full_url,
                        deadline,
                        truncate=True,
                    )
                    # a cut body leaves the rest of it on the wire, which
                    # the next call's probe cannot see before it arrives:
                    # that call's request would go out whole and its
                    # `getresponse()` would read this one's leftovers.
                    # `http.client` closes a response once a read reaches
                    # the end of its body, so an open one is a cut one
                    read_to_the_end = response.isclosed()
                else:
                    # a success read stops only at the end of the body or
                    # by raising, so reaching here is reaching the end
                    body_bytes = _read_bounded(
                        response, max_body_size, request.full_url, deadline
                    )
                    read_to_the_end = True
            except BaseException:
                # A status line did arrive -- the class docstring's line
                # the reconnect must not cross -- so this is never
                # re-sent; the connection is left mid-response, so it is
                # not offered to a later call either.
                self._connections.pop(key).close()
                raise

            if response.will_close:
                # The node said so in this very response -- `Connection:
                # close`, or no keep-alive at all under HTTP/1.0 -- so
                # holding it for a next call would hold a socket the
                # other end has already given up on.
                self._connections.pop(key).close()
            elif not read_to_the_end:
                # the exchange did not complete: the rest of a cut error
                # body is still to come over this connection
                self._connections.pop(key).close()

            return response.status, body_bytes

    def close(self) -> None:
        """Close every connection this transport is holding open.

        Nothing else in this module owns a socket across calls, so this
        is the one thing here with anything to close between them.
        """
        with self._lock:
            for connection in self._connections.values():
                connection.close()
            self._connections.clear()

    def __enter__(self) -> Self:
        """Return self, so `with SessionTransport() as transport:` works."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close every connection on the way out of the `with` block."""
        self.close()
