# Copyright (c) The btclib developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""A standalone JSON-RPC client against Bitcoin Core.

One source file with nothing but the standard library behind it, so that a
project can install it as a package or copy it whole -- **Vendoring and
updates** below is how.

`BitcoinCoreRpcClient` invokes any one rpc method a node has, with
positional or named parameters: one HTTP POST per call, basic
authentication, the result or an exception. Any method, because a caller
with a node has every reason to ask it anything, and a client that knew a
list of methods would only mean they write this class again.

**Not python-bitcoinrpc's `AuthServiceProxy`, and not a port of it.**
That class, and the copy of it Core's test framework maintains, carry the
LGPL-2.1 of their python-jsonrpc ancestry, where this is MIT: this is
an implementation of the protocol rather than a translation of theirs,
and shares no line with either. It is not API-compatible with them
either, and does not try to be -- `call("getblockcount")` against an
attribute lookup that builds a method name is a different interface, and
the explicit one is what makes an unknown method a value rather than a
typo that becomes a request.

**Migrating from `AuthServiceProxy`.** Four things change, and each of
them is the difference deliberately.

.. code-block:: python

    # a method is an argument, not an attribute: an unknown one is a
    # value that arrives at the node, not an AttributeError here
    rpc.getblock(block_id, 2)
    client.call("getblock", [block_id, 2])

    # and the named form is the other structure Core takes
    client.call("getblock", {"blockhash": block_id, "verbosity": 2})

    # credentials leave the url, which is what gets written into a
    # config file and printed in a traceback
    AuthServiceProxy(f"http://{user}:{password}@127.0.0.1:8332")
    BitcoinCoreRpcClient("http://127.0.0.1:8332", user=user, password=password)
    BitcoinCoreRpcClient.from_chain("main")  # or the node's cookie file

    # one wallet of a multi-wallet node, percent-encoded
    client.for_wallet("hot").call("getbalance")

`JSONRPCException` becomes three exceptions, because it covered three
things a caller acts on differently: `RpcError` when the node computed an
error, with its `code`; `HttpError` when the exchange failed, with its
`status`; `FetchError` when there was no answer to read at all. All three
are `FetchError`, so one `except FetchError` is the equivalent of the one
`except JSONRPCException`; what catching them apart buys is the status a
retry policy reads.

``batch_`` is what a consumer loses -- Core's maintained fork spells it
`batch`. Several calls in one request is a named non-goal: a batch needs
an api for correlating the answers and for partly failing. A loop over
`call` is the replacement, at one HTTP request each -- an equivalent
beside the node, where the round trip is close to free, and not over a
link where it costs something, which is where a batch pays.

Notifications -- a request sent with no `id`, which a node does not answer
-- are a non-goal too, and no `AuthServiceProxy` consumer is giving one
up: both implementations count an `id` into every request they build, so
sending one at all means building the request body instead of calling
`call`.

**One call, one HTTP request, and no retry.** A 503 from bitcoind means
its rpc work queue is full and the same request works once the queue
drains, so a retry is the obvious convenience -- and it is the caller's
to write, for two reasons. `call` carries any method, so this class
cannot know whether re-sending one is safe. And the timeout bounds this
client's wait rather than the node's work: a node that stopped answering
may still be executing the call, so a client re-sending a wallet command
of its own accord can execute it twice. `HttpError.status` is what makes
that policy three lines rather than a match on the text of a message; it
is no ruling on which failures are transient, a refused connection and an
expired timeout arriving as a plain `FetchError` and both able to clear on
their own.

**JSON-RPC 2.0, and 1.1 read back.** Core answers 1.1 by default and 2.0
to a request carrying the `"jsonrpc": "2.0"` marker, and the difference
is which layer reports a bitcoin error: under 1.1 an unknown transaction
comes back as HTTP 500 with the error object in the body, so a genuine
server fault and a routine "no such transaction" are the same status.
Under 2.0 an rpc error is HTTP 200 with an `error` member, and a non-2xx
means the HTTP exchange itself failed. Both are read here -- a node older
than v28 does not know the marker and replies 1.1 to it -- but only one
of them can be told apart from a proxy in the way.

**No credentials in the url.** A url with the userinfo part filled in --
the `<user>:<password>@` before the host -- puts a password in a string
that ends up in configuration files, tracebacks and logs. Such a url is
refused here; the password arrives as an argument, or, better, is never
seen at all -- `.cookie` is what bitcoind writes for exactly this,
rotated at every restart, readable by the user running the node and by
nobody else.

**Vendoring and updates.** `pip install bitcoin-core-rpc` is the
supported way to get this file; copying it is for a project that ships one
artifact and takes no dependency for it. Copy it whole from a release
tag, **rename it to `bitcoin_core_rpc.py`**, keep the license notice
above, and record the tag beside the copy. It is named `__init__.py` here
so that `py.typed` can sit beside it and a consumer's type checker reads
these annotations -- PEP 561 puts that marker inside a package directory
and nowhere else -- and the rename is what that costs.
The upstream source is
`https://github.com/btclib-org/bitcoin-core-rpc/blob/main/bitcoin_core_rpc/__init__.py`,
and the raw source of a release is
`https://raw.githubusercontent.com/btclib-org/bitcoin-core-rpc/<tag>/bitcoin_core_rpc/__init__.py`
-- the whole path, so that it can be fetched as it stands. An update is a
replacement of the whole file; this shows every behavioral change first:

.. code-block:: console

    git diff OLD..NEW -- bitcoin_core_rpc/__init__.py

A vendored copy receives no fix automatically, where an installed one is a
version an ordinary dependency bump moves, so the recorded tag is what
tells a maintainer whether it needs replacing. There is deliberately no
version constant in the file: the release tag is the version, and a number
inside a copied source is a second one that can drift from it.
"""

from __future__ import annotations

import json
import sys
from base64 import b64encode
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from decimal import Decimal, DecimalException
from http.client import HTTPException, HTTPMessage
from math import isfinite
from os import PathLike, environ
from pathlib import Path
from secrets import token_hex
from time import monotonic
from typing import IO, Any, Literal
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

__all__ = [
    "COOKIE_USER",
    "DEFAULT_DATADIR",
    "DEFAULT_MAX_BODY_SIZE",
    "DEFAULT_TIMEOUT",
    "MAX_ERROR_BODY_SIZE",
    "USER_AGENT",
    "BitcoinCoreRpcClient",
    "BtcRpcRuntimeError",
    "BtcRpcTypeError",
    "BtcRpcValueError",
    "Chain",
    "CookieNotFoundError",
    "FetchError",
    "HttpError",
    "HttpTransport",
    "Network",
    "RpcChannel",
    "RpcError",
    "chain_from_network",
    "cookie_auth",
    "cookie_path_from_chain",
    "datadir_subdir_from_chain",
    "default_datadir",
    "http_request",
    "network_from_chain",
    "rpc_port_from_chain",
    "urlopen_transport",
]

# Every exception this module raises is declared here, in the file that
# raises it: a module holding them elsewhere would be a second import for a
# vendored copy to satisfy. Their identity does not survive that copy, and no
# arrangement here could manage it -- these definitions execute again in the
# copy, whose `FetchError` is its own class, so a project that both vendors
# this file and installs the package has two, and one `except` does not catch
# the other.
#
# The three bases below the standard exceptions keep the TypeError,
# ValueError and RuntimeError hierarchies exact: a caller who wants none of
# the names here catches those three and still separates a caller error from
# a failure of the exchange.
#
# `BtcRpc` and not `BTClib`: btclib declares `BTClibValueError` and two more
# of its own, and two classes of one name from two packages is an `except`
# that reads correct at every call site and catches the wrong one at half of
# them -- which btclib hit while taking this dependency. Distinct names put
# the mistake in the source rather than in a test.
#
# The two carrying a field hand every constructor argument to
# `BaseException.__init__` and compose their message in `__str__`, which is
# what `subprocess.CalledProcessError` and `UnicodeDecodeError` do, and what
# makes them picklable: `BaseException.__reduce__` returns `(cls, self.args)`,
# so a class whose `args` is the composed message alone is rebuilt by calling
# it with one argument, and one argument is not what it takes. That is a
# TypeError out of `pickle`, out of `copy.copy` and out of `copy.deepcopy` --
# and out of a `ProcessPoolExecutor`, which cannot send the exception back and
# reports a broken pool instead of the status the worker died of. Composing in
# `__str__` keeps the round trip faithful rather than merely possible: a
# message composed in `__init__` from an argument that is itself a composed
# message gains a second `(rpc error code -5)` every time. The price is
# `args`, a tuple of the arguments rather than a one-tuple of the message,
# and the `repr` that names the fields with it; `str` is unchanged.


class BtcRpcValueError(ValueError):
    """A value no valid input could carry; the library's usual refusal."""


class BtcRpcTypeError(TypeError):
    """An input of a type no conversion accepts: a caller error."""


class BtcRpcRuntimeError(RuntimeError):
    """A check that failed on valid inputs, e.g. a failed verification."""


class FetchError(BtcRpcRuntimeError):
    """A backend did not answer, or did not answer this.

    A RuntimeError and not a ValueError: nothing the caller passed is
    wrong. The node is down, the credentials are stale, the explorer sent
    html, the transaction is not in the index -- retrying later can work,
    and correcting the argument cannot.

    It covers the conversion of an answer too: a backend replying with
    something that is not a transaction has failed, and reporting that as
    the BtcRpcValueError the parser raised would name the parser rather
    than the host that has to be fixed.

    `HttpError`, `RpcError` and `CookieNotFoundError` derive from it, so
    one `except FetchError` catches every failure of an exchange.
    """


class HttpError(FetchError):
    """A backend failed at the HTTP layer, and `status` is what it said.

    A field rather than something to be parsed back out of a message: the
    retry policy that reads it is the caller's, for the reasons this
    module's docstring gives.

    Not every FetchError carries one. A refused connection and an expired
    timeout never produced a status; neither did a body that is no answer
    -- not json, not utf-8, not a reply object -- arriving with an HTTP
    200, where the shape of the body is the whole diagnosis. The same body
    under a non-200 is this exception instead: it cannot be an answer the
    backend computed, so the status is what is left to report. The message
    states it too -- an exception is a diagnostic before it is a value.
    """

    def __init__(self, message: str, status: int) -> None:
        self.status = status
        super().__init__(message, status)

    def __str__(self) -> str:
        # the message alone, which is what BaseException returns for a
        # single argument and not for the two this now carries
        return str(self.args[0])


class RpcError(FetchError):
    """bitcoind answered with a JSON-RPC error object, and this is it.

    `code` is the node's, from `src/rpc/protocol.h`: -5 is
    RPC_INVALID_ADDRESS_OR_KEY, which is what `getrawtransaction` returns
    for a transaction it cannot find -- including every non-wallet
    transaction on a node running without `-txindex`. A caller telling "no
    such transaction" from "the node is unreachable" needs the number.

    `data` is JSON-RPC's optional third member of an error object, kept
    as it arrived. Core leaves it out today, so it is None for every
    error a node sends; a method that starts sending one, or a proxy
    adding its own, would otherwise have it dropped here, which is the
    one place it cannot be recovered from.
    """

    def __init__(self, message: str, code: int, data: Any = None) -> None:
        self.code = code
        self.data = data
        super().__init__(message, code, data)

    def __str__(self) -> str:
        return f"{self.args[0]} (rpc error code {self.code})"


class CookieNotFoundError(FetchError):
    """There is no cookie file where one was looked for.

    A FetchError like the others, and for the same reason: nothing the
    caller passed is wrong, and the node starting is what fixes it. A
    class of its own because it is the one cookie failure that is
    ordinarily no fault at all -- bitcoind writes the file while it runs
    and removes it when it stops, so an absent one is a node that is not
    running, or one whose rpc server is off, which is `bitcoin-qt` without
    `server=1`. Every other cookie failure is a file to go and look at.

    A caller that reports the two the same way tells an operator to
    inspect a file that was never written; one holding them apart says
    "start the node" for this and names the file for the rest.
    """


def _is_integer(value: Any) -> bool:
    """Return whether value is an integer, with a bool not being one.

    `bool` is a subclass of `int`, so every field whose contract is an
    integer quantity takes `True` for the number one unless something says
    otherwise. The json boundary is what makes that worth refusing: `true`
    is what a configuration file decodes to, and an rpc error code of
    `True` is not the code 1.
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
# the local disk and report the bytes as a node's answer. Refusing the
# scheme here is what makes the suppression in `urlopen_transport` true
# rather than hopeful
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
    # matches the base method's signature rather than shortening it
    def redirect_request(  # noqa: PLR0917
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
    over it.

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

    announced = response.headers.get("Content-Length")
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
    """
    deadline = monotonic() + timeout
    # what reaches the opener is http or https: `http_request` is the only
    # thing that builds a Request, it checks the scheme first, and a
    # redirect cannot introduce a second url
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


# the rpc port and the datadir subdirectory of each chain, from Core's
# `CreateBaseChainParams` in src/chainparamsbase.cpp. Main's cookie is in
# the datadir itself, which is the empty subdirectory below. Keyed by
# Core's chain names -- `ChainTypeToString` in src/util/chaintype.cpp,
# which is what `-chain=` reads and what `getblockchaininfo` reports --
# because what they index here is a port and a directory: a chain Core has
# no default port for is an explicit url, which is the constructor. `test`
# indexes `testnet3`, a third vocabulary for that one chain and the reason
# both columns are Core's: a directory name is no more this module's to
# choose than a port number is
_RPC_PORT_FROM_CHAIN = {
    "main": 8332,
    "test": 18332,
    "testnet4": 48332,
    "signet": 38332,
    "regtest": 18443,
}
_DATADIR_SUBDIR_FROM_CHAIN = {
    "main": "",
    "test": "testnet3",
    "testnet4": "testnet4",
    "signet": "signet",
    "regtest": "regtest",
}


def rpc_port_from_chain(chain: str) -> int:
    """Return the default rpc port of one of Core's chains.

    What `from_chain` builds its loopback url out of, and what reaching
    the same node any other way -- through a tunnel, an `https` proxy, or
    from another host -- otherwise means copying this table to know.
    """
    if chain not in _RPC_PORT_FROM_CHAIN:
        known = ", ".join(_RPC_PORT_FROM_CHAIN)
        raise BtcRpcValueError(f"unknown Core chain: {chain} not in ({known})")
    return _RPC_PORT_FROM_CHAIN[chain]


def datadir_subdir_from_chain(chain: str) -> str:
    """Return the datadir subdirectory of one of Core's chains.

    Empty for `main`, which keeps its cookie in the datadir itself, and
    `testnet3` for `test`: the two the chain name does not give away.
    `cookie_path_from_chain` composes it with a datadir and the name of
    the cookie file; what is left for this is a caller naming something
    else under the same directory -- a wallet, a `debug.log`.
    """
    if chain not in _DATADIR_SUBDIR_FROM_CHAIN:
        known = ", ".join(_DATADIR_SUBDIR_FROM_CHAIN)
        raise BtcRpcValueError(f"unknown Core chain: {chain} not in ({known})")
    return _DATADIR_SUBDIR_FROM_CHAIN[chain]


# The BIP network names against Core's chain names: `mainnet`/`main` and
# `testnet`/`test` differ, the rest agree. A library encoding keys and
# addresses spells what BIP32 and BIP173 spell, Core what `-chain=` takes,
# and neither vocabulary is going to adopt the other -- a `network` there
# names the encoding table to encode *with*, and is `testnet` for a signet
# address, where Core's `chain` is an identity. So the pair is written down
# once, in the file that speaks Core's protocol and is therefore the
# boundary between the two: a caller holding one name and needing the other
# has these two functions instead of a dict of their own.
#
# A translation of vocabulary and not a promise of availability: v31.1
# warns that support for testnet3 is deprecated and will be removed, so
# `test` is a name Core still reads rather than a chain every node still
# serves.
#
# A Literal each, and not an Enum: both vocabularies are `str` wherever
# they are spoken -- `-chain=` takes one, `getblockchaininfo` answers one,
# a json body carries them -- so an enum would be an island every caller
# converts at, where a Literal still catches the typo at every call site
# that spells the name out. They annotate what these functions return and
# not what they take: an argument arrives from a config file or from a node
# as a `str` no annotation narrows, and a parameter of this type would buy
# a cast at every such call site to say what the refusal below already says
# at runtime.
Chain = Literal["main", "test", "testnet4", "signet", "regtest"]
"""Core's five chain names: what `-chain=` takes and `getblockchaininfo`
reports, and what `from_chain` and the two lookups are spelled in.

What `chain_from_network` returns, and not what `network_from_chain` is
annotated as taking.
"""

Network = Literal["mainnet", "testnet", "testnet4", "signet", "regtest"]
"""The five BIP network names, which BIP32 and BIP173 spell.

`mainnet` and `testnet` are where this vocabulary differs from `Chain`;
the rest agree. `chain_from_network` translates.
"""

_NETWORK_CHAIN_PAIRS: tuple[tuple[Network, Chain], ...] = (
    ("mainnet", "main"),
    ("testnet", "test"),
    ("testnet4", "testnet4"),
    ("signet", "signet"),
    ("regtest", "regtest"),
)
_CHAIN_FROM_NETWORK: dict[str, Chain] = dict(_NETWORK_CHAIN_PAIRS)
_NETWORK_FROM_CHAIN: dict[str, Network] = {
    chain: network for network, chain in _NETWORK_CHAIN_PAIRS
}


def chain_from_network(network: str) -> Chain:
    """Return Core's chain name for one of the BIP network names.

    Raises rather than passing an unrecognized name through, in both
    directions: a chain Core adds later is then a failure here, naming
    what it knows, instead of a string that reaches a node as a port
    lookup or a directory name.
    """
    if network not in _CHAIN_FROM_NETWORK:
        known = ", ".join(_CHAIN_FROM_NETWORK)
        raise BtcRpcValueError(f"unknown network: {network} not in ({known})")
    return _CHAIN_FROM_NETWORK[network]


def network_from_chain(chain: str) -> Network:
    """Return the BIP network name for one of Core's chain names.

    The inverse of `chain_from_network`, and raising for the same reason.
    """
    if chain not in _NETWORK_FROM_CHAIN:
        known = ", ".join(_NETWORK_FROM_CHAIN)
        raise BtcRpcValueError(f"unknown Core chain: {chain} not in ({known})")
    return _NETWORK_FROM_CHAIN[chain]


COOKIE_USER = "__cookie__"
"""The username bitcoind writes into its cookie file.

`COOKIEAUTH_USER` in Core's `src/rpc/request.cpp`. The node ignores it --
cookie authentication compares the whole `user:password` line -- so it is
documentation, and a cookie file whose first field is something else is
still a valid one.
"""


# Core's default datadir per platform, from `GetDefaultDataDir` in
# src/common/args.cpp: the directory below hanging off a base, which is the
# home directory except on Windows, where Core asks the shell for
# CSIDL_APPDATA -- the folder `%APPDATA%` names, and the environment
# variable is how a Python process asks for it. Keyed by `sys.platform`,
# with everything not in the table taking Core's `#else`, the Unix branch:
# a table rather than a chain of comparisons because mypy narrows
# `sys.platform ==` to the platform it is aimed at and stops checking the
# rest, so the two branches a Linux run of the checker would not look at
# are the two this table keeps in front of it.
_DATADIR_FROM_PLATFORM: dict[str, tuple[str | None, tuple[str, ...]]] = {
    "darwin": (None, ("Library", "Application Support", "Bitcoin")),
    "win32": ("APPDATA", ("Bitcoin",)),
}
_DATADIR_ELSEWHERE: tuple[str | None, tuple[str, ...]] = (None, (".bitcoin",))


def default_datadir() -> Path | None:
    r"""Return Core's datadir for this platform, or None where it has no base.

    What Core's own `GetDefaultDataDir` answers: ``%APPDATA%\Bitcoin`` on
    Windows, ``~/Library/Application Support/Bitcoin`` on macOS,
    ``~/.bitcoin`` on everything else. The three are a table here, so the
    branch a checker or a coverage run on one platform does not take is
    still a line both of them read; `sys.platform` and the environment are
    read at the call, which is what a test drives to reach the other two.

    Three ways there is no base to hang that off, and none may raise, since
    `DEFAULT_DATADIR` below calls this at import: `Path.home()` raises
    RuntimeError when nothing resolves `~` -- no `HOME` in the environment
    and no passwd entry for the uid, which is a container run under an
    arbitrary one -- and it answers with whatever `HOME` holds, so a
    relative `HOME` gives a relative home and raises nothing. On Windows
    `APPDATA` is the base, and it can be unset or relative in the same way.

    None for all of them, rather than a path that is no datadir. A relative
    one would be resolved against the working directory at the moment of
    the read, so `~/.bitcoin/.cookie` would make a file a caller's cwd
    happens to contain the credential this client presents. `from_chain`
    refuses instead, naming `cookie_path` as what to pass.

    A default and not a discovery: a node started with `-datadir=` is
    somewhere this cannot know, and `cookie_path` is the answer for one.

    `from_chain` calls this at every call rather than reading
    `DEFAULT_DATADIR`, so that the `HOME` of the call is the one that
    counts and not the one that stood when something first imported this
    module. Public for the same reason: a caller building its own
    datadir-derived path -- a wallet directory, or the cookie
    `cookie_path_from_chain` derives -- needs that live answer too, and had
    no way to ask for it short of copying this function.
    """
    base_var, subdirs = _DATADIR_FROM_PLATFORM.get(sys.platform, _DATADIR_ELSEWHERE)
    if base_var is None:
        try:
            base = Path.home()
        except RuntimeError:
            return None
    else:
        named = environ.get(base_var)
        if named is None:
            return None
        base = Path(named)
    return base.joinpath(*subdirs) if base.is_absolute() else None


# the answer as it stood at import, kept for a caller who wants to name the
# location or build a path under it. `Path | None` is a deliberate
# declaration rather than an oversight: the alternatives are a `Path` that
# lies -- an invented absolute path -- or the relative `~/.bitcoin` that
# made a cwd file a credential, so a caller whose strict type checking asks
# for the None case is being asked the question the value always had
DEFAULT_DATADIR: Path | None = default_datadir()
"""Core's datadir for this platform as it stood at import, or None.

`default_datadir` computes it, and says which directory each platform
gets. `from_chain` calls that rather than reading this, so that a `HOME`
set after this module was imported is the one that counts.
"""


def cookie_path_from_chain(
    chain: str, datadir: str | PathLike[str] | None = None
) -> Path:
    """Return the path of the cookie file bitcoind writes for one chain.

    Under `datadir`, the directory the node was started with, defaulting
    to `default_datadir` -- asked at this call, so that the environment of
    the call is what counts, and where it has no base to answer with this
    refuses with `BtcRpcValueError` naming `datadir` rather than deriving
    a path against the working directory. Then the subdirectory
    `datadir_subdir_from_chain` names, and `.cookie`, which is
    `COOKIEAUTH_FILE` in Core's `src/rpc/request.cpp`.

    What `from_chain` builds its `cookie_path` out of, and what the caller
    it cannot serve otherwise assembles by hand: a node started with
    `-datadir=` somewhere else, or one reached at a url of the caller's,
    which is the constructor and derives nothing. Two of the three facts
    were published as tables and the name of the file was not, so
    assembling it meant writing that name out.

    A node started with `-rpccookiefile` writes the file somewhere else
    again: that is a path the caller already holds, and nothing derives
    it.

    A path and no read, `cookie_auth` being what reads one -- and a client
    re-reads it at every call, the node rotating the credential at every
    restart.
    """
    if datadir is None:
        datadir = default_datadir()
        if datadir is None:
            err_msg = "no absolute home directory (APPDATA on Windows), so"
            err_msg += " no default datadir to find the cookie file in:"
            err_msg += " pass datadir"
            raise BtcRpcValueError(err_msg)
    # `Path` refuses a type that is no path itself, with a TypeError of
    # pathlib's naming what it takes; the constructor checks `cookie_path`
    # by hand because `quote` accepts `bytes` and built an endpoint out of
    # one, which is a wrong value passing rather than a refusal
    return Path(datadir) / datadir_subdir_from_chain(chain) / ".cookie"


# what a cookie file may weigh. bitcoind writes one line of some seventy
# octets, so a bound three orders of magnitude above that refuses nothing
# a node wrote; what it refuses is holding a log, a core dump or a disk
# image in memory whole because `cookie_path` pointed at one, only to
# report a missing colon afterwards
_MAX_COOKIE_SIZE = 4096

# how many random bytes make the `id` of a request this call's. Distinct
# per call: the echo check exists to catch a reply that answers another
# request -- a caching proxy in the way -- and a value reused across calls
# cannot tell that reply from the right one. Random rather than counted
# because a counter is shared mutable state, which is the one thing that
# would make a client unsafe to call from two threads. Prefixed on the way
# out, so a node's debug log says whose call it was
_RPC_ID_BYTES = 8

# how deep a parameter structure may nest. Both the encoder and the walk
# that checks a structure before it recurse, so a bound is what turns
# something too deep for either into a refusal that names the parameters
# rather than a RecursionError out of the standard library. Core's own
# methods nest a few levels -- the inputs of a psbt, the tree of a
# descriptor -- so this is not a limit a call arrives at
_MAX_PARAMS_DEPTH = 100


USER_AGENT = "bitcoin-core-rpc"
"""What `call` sends as `User-Agent`, and a transport of a caller's own can.

urllib's default names the interpreter -- `Python-urllib/3.14` -- which
identifies neither this client nor the program running it, where a node's
access log and any proxy in front of it record this. No version in it: the
release tag is the version, and a copied file would carry whichever one it
was copied from.
"""


def _rpc_id() -> str:
    """Return the `id` of one request, distinct from every other."""
    return f"btcrpc-{token_hex(_RPC_ID_BYTES)}"


def _assert_valid_timeout(timeout: float, what: str) -> None:
    """Refuse a timeout that is not a number of seconds to wait.

    A bool is not a duration and `timeout=True` would be one second; a
    zero or a negative one makes the socket give up before it connects;
    an infinity or a nan is what `Infinity` in a json configuration
    decodes to. All four reach the socket layer and fail there, out of
    the standard library rather than through this module's exceptions.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise BtcRpcTypeError(f"non-numeric {what}: {timeout!r}")
    if not isfinite(timeout) or timeout <= 0:
        raise BtcRpcValueError(f"{what} is not a positive number of seconds: {timeout}")


def _checked_url(url: str) -> str:
    """Return the endpoint url, having refused what is not one.

    Checked when the client is built and not at the first call, which is
    where `urlopen` would refuse most of it: a url is configuration, and
    configuration that cannot work is worth refusing while the caller who
    supplied it is still looking at the line.
    """
    split = urlsplit(url)
    if split.scheme not in _SCHEMES:
        err_msg = f"invalid rpc url scheme: '{split.scheme}' instead of http(s)"
        raise BtcRpcValueError(err_msg)
    if split.username is not None or split.password is not None:
        err_msg = "credentials in the rpc url:"
        err_msg += " pass user and password, or use the cookie file"
        raise BtcRpcValueError(err_msg)
    if not split.hostname:
        raise BtcRpcValueError(f"no host in the rpc url: {url}")
    if split.query or split.fragment:
        err_msg = f"query or fragment in the rpc url: {url}"
        err_msg += " -- an rpc endpoint is a path, and the call is the body"
        raise BtcRpcValueError(err_msg)
    try:
        # the port is parsed on access and not before, so this is what
        # refuses `http://node:https` here rather than at the first call
        _ = split.port
    except ValueError as e:
        raise BtcRpcValueError(f"invalid port in the rpc url: {url}") from e
    return url


def cookie_auth(cookie_path: Path) -> str:
    """Return the `user:password` bitcoind wrote in its cookie file.

    One line, `__cookie__:` and 32 random bytes in hex, rewritten at
    every start of the node. Read at each call rather than once at
    construction: a client built when the node was up and used an hour
    later would otherwise answer 401 for the rest of the process, the
    node having been restarted in between, and the cost is one small
    local read against an HTTP round trip.

    Ascii, one line and a bounded read, because a path that is not a
    cookie file is the ordinary mistake here and a credential is the one
    value that must not appear in the error reporting it: what the three
    checks buy is that a binary file, a log or something enormous arrives
    as a FetchError naming the file, rather than as a UnicodeDecodeError
    or as memory nobody agreed to.

    A file that is not there is `CookieNotFoundError`, which is a
    FetchError too: it says the node wrote no cookie, where the rest say
    something is at the path and it is not a cookie.
    """
    try:
        with cookie_path.open("rb") as file:
            raw = file.read(_MAX_COOKIE_SIZE + 1)
    except FileNotFoundError as e:
        err_msg = f"no rpc cookie file {cookie_path}: bitcoind writes one"
        err_msg += " while it runs with its rpc server enabled"
        raise CookieNotFoundError(err_msg) from e
    except OSError as e:
        # every other way the open fails is a file to look at: a directory
        # at the path, a mode that excludes this user, a datadir that is no
        # directory. `FileNotFoundError` alone above, and not `ENOTDIR`
        # with it -- a path component that is a file is a datadir the
        # caller configured wrong, which the node starting does not fix
        raise FetchError(f"unreadable rpc cookie file {cookie_path}: {e}") from e
    if len(raw) > _MAX_COOKIE_SIZE:
        err_msg = f"oversized rpc cookie file {cookie_path}:"
        err_msg += f" more than the {_MAX_COOKIE_SIZE} bytes one can be"
        raise FetchError(err_msg)
    try:
        line = raw.decode("ascii").strip()
    except UnicodeDecodeError as e:
        raise FetchError(f"non-ascii rpc cookie file {cookie_path}: {e}") from e
    if "\n" in line or "\r" in line:
        raise FetchError(f"malformed rpc cookie file {cookie_path}: several lines")
    if ":" not in line:
        raise FetchError(f"malformed rpc cookie file {cookie_path}: no ':' in it")
    return line


def _params_member(params: Sequence[Any] | Mapping[str, Any] | None) -> Any:
    """Return what goes in the request as `params`, refusing what cannot.

    JSON-RPC has two parameter structures and Core takes both: an array,
    read positionally, and an object, read by name. Which of them a
    method wants is the method's business, so both go through unchanged
    -- Core's `args` convenience included, a named call carrying an array
    of leading positional values, which is one key of a caller's mapping
    and needs nothing here.

    A str, bytes or bytearray is a Sequence and is never a list of
    parameters: `call("getblock", block_id)` means one parameter, where
    json would have sent sixty-four of them. Refused rather than wrapped,
    since a caller who meant a sequence of one has `[block_id]` to say so
    and nothing tells the two intentions apart from here.
    """
    if params is None:
        return []
    if isinstance(params, Mapping):
        return dict(params)
    if isinstance(params, (str, bytes, bytearray)):
        err_msg = f"rpc params is a {type(params).__name__} and not a sequence"
        err_msg += " of parameters: pass [params] for a single positional one"
        raise BtcRpcTypeError(err_msg)
    if isinstance(params, Sequence):
        return list(params)
    err_msg = "rpc params is neither a sequence nor a mapping, but a"
    err_msg += f" {type(params).__name__}"
    raise BtcRpcTypeError(err_msg)


def _assert_json_params(
    value: Any, depth: int = 0, enclosing: tuple[int, ...] = ()
) -> None:
    """Refuse a parameter structure json cannot carry, before it is encoded.

    Walked rather than left to the encoder, because most of what goes
    wrong here is silent or unhelpful in it. A mapping keyed by anything
    but a string is *rewritten*: `{1: "a"}` encodes as `{"1": "a"}`, so a
    caller's value reaches the node changed rather than refused, and only
    the outermost mapping is a name a caller wrote by hand. A structure
    containing itself raises ValueError("Circular reference detected"),
    which is the same type a non-finite number raises and means something
    else entirely. One nested past the interpreter's stack raises
    RecursionError from inside the encoder. And a Decimal or a `bytes`
    reaches `default`, which cannot say where in the structure it was.

    `enclosing` carries the ids of the containers this value sits inside,
    which is what a cycle is: a container reached from within itself. No
    depth bound tells that from a structure that is merely deep, and no
    bound on a *reply* helps -- these are the caller's own objects.
    """
    if depth > _MAX_PARAMS_DEPTH:
        err_msg = f"rpc params nested deeper than the {_MAX_PARAMS_DEPTH} allowed"
        raise BtcRpcValueError(err_msg)
    if _json_scalar(value):
        return
    if isinstance(value, Mapping):
        _assert_no_cycle(value, enclosing)
        for name, item in value.items():
            if not isinstance(name, str):
                raise BtcRpcTypeError(f"non-string rpc parameter name: {name!r}")
            _assert_json_params(item, depth + 1, (*enclosing, id(value)))
        return
    if isinstance(value, Sequence):
        _assert_no_cycle(value, enclosing)
        for item in value:
            _assert_json_params(item, depth + 1, (*enclosing, id(value)))
        return
    raise BtcRpcTypeError(f"rpc parameter that is not a json value: {value!r}")


def _json_scalar(value: Any) -> bool:
    """Say whether a value is a json scalar, refusing three that look like one.

    A Decimal, a non-finite float and a `bytes` are each a value a caller
    has a reason to pass and json has no rendering for, so each is refused
    where what to pass instead can be named -- rather than reported as
    "not a json value" from the end of the walk, or, for the `bytes`,
    walked as the list of the ints of its octets.
    """
    if isinstance(value, Decimal):
        err_msg = "Decimal rpc parameter: json carries no exact decimal, so"
        err_msg += " pass what the method documents -- an int of satoshis,"
        err_msg += " or the string it accepts -- rather than a rounded float"
        raise BtcRpcTypeError(err_msg)
    if isinstance(value, float) and not isfinite(value):
        raise BtcRpcValueError(f"not a json number in the rpc params: {value}")
    if isinstance(value, (bytes, bytearray)):
        raise BtcRpcTypeError(f"rpc parameter that is not a json value: {value!r}")
    return value is None or isinstance(value, (bool, int, float, str))


def _assert_no_cycle(value: Any, enclosing: tuple[int, ...]) -> None:
    """Refuse a container reached from inside itself, by the ids it is in."""
    if id(value) in enclosing:
        raise BtcRpcValueError("rpc params contains itself, so it has no json")


def _refuse_param(value: Any) -> Any:
    """Refuse a parameter the walk before the encoder did not anticipate.

    The backstop, and every type it can be reached with today is one
    `_assert_json_params` refuses first. What keeps it here is that
    `json.dumps` calling this is the alternative to a TypeError from
    inside the encoder: an object that is a `Sequence` of json values and
    still has no json -- `range(3)` is one -- passes the walk and arrives
    here.
    """
    raise BtcRpcTypeError(f"rpc parameter that is not a json value: {value!r}")


def _json_number(token: str) -> Decimal:
    """Return the Decimal a json number is, having refused a non-finite one.

    `Decimal(token)` is built in whatever decimal context the *caller* is
    running under, and that context decides whether an exponent the
    implementation cannot represent raises or is answered quietly: with
    `InvalidOperation` untrapped -- `ctx.traps[InvalidOperation] = False`,
    which a program doing its own arithmetic has reason to want --
    `1e999999999999999999999999999` comes back as `Decimal("NaN")`, an
    amount that compares false against itself for the rest of its life,
    arriving past the refusal of NaN this module states and raising nothing
    for the `DecimalException` normalization to catch. So the value is
    checked rather than the exception waited for.

    Size is deliberately not the question: a finite number is an answer
    however large, which is what lets pypy's decimal build exponents
    libmpdec declines to.
    """
    number = Decimal(token)
    if not number.is_finite():
        raise FetchError(f"not a json number in the reply: {token}")
    return number


def _refuse_constant(name: str) -> Any:
    """Refuse the three non-numbers Python's json decodes by default.

    `NaN`, `Infinity` and `-Infinity` are what Python writes and reads
    for floats json has no numbers for. A node does not send them; a
    proxy or a stub in the way can, and a nan arriving as an amount
    compares false against itself for the rest of its life.
    """
    raise FetchError(f"not a json number in the reply: {name}")


def _http_error(where: str, status: int) -> HttpError:
    """Turn a status that is itself the failure into the exception for it."""
    if status == 401:
        message = f"{where}: HTTP 401, the node refused the credentials"
        return HttpError(message, status)
    return HttpError(f"{where}: HTTP {status}", status)


def _id_error(where: str, request_id: str, reply: Mapping[str, Any]) -> FetchError:
    """Say that a reply answers some request other than this one."""
    err_msg = f"{where}: reply id {reply.get('id')!r}"
    err_msg += f" is not the {request_id!r} asked for"
    return FetchError(err_msg)


def _rpc_error(where: str, error: Any) -> FetchError:
    """Turn what the node put in `error` into the exception for it.

    An error object is a code that is an integer and a message that is a
    string; a caller acts on the first and reads the second, so neither is
    something to render whatever arrived. A missing message would become
    an empty one and a list would be formatted into the exception, both of
    which report the node as having said something it did not.
    """
    if not isinstance(error, Mapping):
        return FetchError(f"{where}: unreadable rpc error {error!r}")
    # Any, both of them: every value of a reply is whatever the backend
    # put there, which is what the two checks below are for
    code: Any = error.get("code")
    message: Any = error.get("message")
    if not _is_integer(code) or not isinstance(message, str):
        return FetchError(f"{where}: unreadable rpc error {error!r}")
    return RpcError(f"{where}: {message}", code, error.get("data"))


def _unreadable(where: str, cause: Exception) -> FetchError:
    """Say what shape a body was, for the 200 where the status says nothing.

    Each shape gets its own sentence, being a different thing to go and
    look at: not utf-8, nested past the interpreter's stack, not json.
    Anything else -- a json integer longer than
    `sys.get_int_max_str_digits` allows, a number whose exponent the
    decimal module refuses to build, and whatever a later Python adds --
    is the parser refusing the reply, which is what happened.

    Only for a 200. Under any other status the shape is not the answer:
    see `_reply_object`, which reaches this only after ruling that out.
    """
    if isinstance(cause, UnicodeDecodeError):
        return FetchError(f"{where}: a reply that is not utf-8 ({cause})")
    if isinstance(cause, RecursionError):
        return FetchError(f"{where}: a reply nested too deeply to parse")
    if isinstance(cause, json.JSONDecodeError):
        return FetchError(f"{where}: not json ({cause})")
    return FetchError(f"{where}: a reply the json parser refused ({cause})")


def _reply_object(where: str, status: int, payload: bytes) -> Mapping[str, Any]:
    """Return the json object a reply is, or say what arrived instead.

    One rule for every body that is not a json-rpc reply, whichever way it
    is not one: none of them can be a *correlated* answer, so none can be
    this call's rpc error, and on a non-200 what is left to report is the
    status -- the 401 with the empty body Core sends, or a 503 whose body
    is whatever stands in front of the node. Reporting the encoding of an
    error page would name the symptom and hide the cause.

    The status cannot be consulted before this, which is why the rule
    lives here and not at the top of `_result`: a 1.1 error object
    arriving with an HTTP 500 *is* a reply -- `_legacy_result` says what
    giving up on the status first would cost.
    """
    try:
        reply = json.loads(
            payload, parse_float=_json_number, parse_constant=_refuse_constant
        )
    except FetchError as e:
        # one of this module's own two refusals of a number: the three
        # non-numbers Python decodes by default, through `_refuse_constant`,
        # or a `Decimal` that came back non-finite because the caller's
        # context does not trap that, through `_json_number`. Each names
        # what it saw, so under a 200 it is re-raised as it stands -- `raise
        # _unreadable(...) from e` would hand back this very object and make
        # the exception its own `__cause__`, which anything walking that
        # chain follows in a loop
        if status == 200:
            raise
        raise _http_error(where, status) from e
    except (ValueError, RecursionError, DecimalException) as e:
        # the rest of the ways a parse fails: JSONDecodeError and
        # UnicodeDecodeError are both ValueError, the bare ValueError of
        # the integer digit limit is a third, and json recurses.
        # `DecimalException` is none of those and is the price of
        # `parse_float=Decimal`: `1e999999999999999999999999999` is a json
        # number this parser will not build, an `InvalidOperation` out of
        # the decimal module, and an ArithmeticError rather than a
        # ValueError -- so it escaped a promise this module makes about
        # every unreadable reply
        if status != 200:
            raise _http_error(where, status) from e
        raise _unreadable(where, e) from e
    if not isinstance(reply, dict):
        # read, and still not a reply: an array, a string or a number is
        # no more a json-rpc answer than a page of html is, so a 503 whose
        # body is `[1, 2, 3]` is a 503
        if status != 200:
            raise _http_error(where, status)
        raise FetchError(f"{where}: not a json-rpc reply, but a {type(reply).__name__}")
    return reply


def _legacy_result(
    where: str, request_id: str, status: int, reply: Mapping[str, Any]
) -> Any:
    """Return the `result` of a reply carrying no version marker.

    Core's legacy JSON-RPC 1.1: what a node answers to a request without
    the 2.0 marker, and what v27 and older answer to every request.
    `result` and `error` are both present, one of them null, and an rpc
    error arrives with an HTTP 500 -- so the error is read before the
    status, or every "no such transaction" from an old node would be
    reported as a server fault.

    Before the status, but not before the id. A 500 from something in the
    way, carrying an error object of its own or another call's, is a
    failure of the HTTP exchange and not this call's rpc error.

    And not before the status either when the `error` member is no error
    object: `{"id": ours, "error": "bad"}` under a 503 is a correlated
    something, but nothing the node computed -- so what is left to report is
    the status, which is the thing a caller has a policy for. Only a
    readable error object outranks it.
    """
    ours = reply.get("id") == request_id
    error = reply.get("error")
    if ours and error is not None:
        rpc_error = _rpc_error(where, error)
        if isinstance(rpc_error, RpcError) or status == 200:
            raise rpc_error
        raise _http_error(where, status) from rpc_error
    if status != 200:
        raise _http_error(where, status)
    if not ours:
        raise _id_error(where, request_id, reply)
    if "result" not in reply:
        raise FetchError(f"{where}: a reply with neither result nor error")
    return reply["result"]


def _v2_result(
    where: str, request_id: str, status: int, reply: Mapping[str, Any]
) -> Any:
    """Return the `result` of a JSON-RPC 2.0 reply.

    The status is read first, and that is the whole gain of asking for
    2.0: a non-200 is a failure of the HTTP exchange and never an rpc
    error, Core answering 200 with an `error` member for those. So a 401
    from the node, a 403 from something in front of it and a 503 from a
    full work queue cannot be reported as anything the node computed,
    however json-shaped the body beside them is.

    Then exactly one of `result` and `error`, which is 2.0's own rule and
    what tells a 2.0 reply from a 1.1 one wearing the marker. Which member
    is *present*, and not which is non-null: `"error": null` beside a
    result is the 1.1 shape, and a reply that is 1.1 under a 2.0 marker is
    one whose errors this function would look for in the wrong place.
    """
    if status != 200:
        raise _http_error(where, status)
    if reply.get("id") != request_id:
        raise _id_error(where, request_id, reply)
    has_result = "result" in reply
    has_error = "error" in reply
    if has_result == has_error:
        both = "both result and error" if has_result else "neither result nor error"
        raise FetchError(f"{where}: a 2.0 reply with {both}")
    if has_error:
        raise _rpc_error(where, reply["error"])
    return reply["result"]


class BitcoinCoreRpcClient:
    """One Bitcoin Core JSON-RPC endpoint, and the credentials to reach it.

    Not a dataclass, and that is about the password: a generated
    `__repr__` prints every field, so the credential would appear in any
    traceback or log line that renders the client.

    Credentials or a cookie path, and not both: each of the two says who
    is calling, so a client given both would have to rank them, and a
    caller who passed both has a mistaken idea of which one is in use.
    `from_chain` is the constructor that fills in a cookie path, along
    with the port, from Core's own defaults.

    **Concurrent calls are supported while the configuration is not
    mutated.** `call` writes nothing on the client, opens its own
    connection and takes its request id from no shared counter, so one
    client serves any number of threads. What is not promised is a client
    whose url, credentials or transport are reassigned while a call is in
    flight, or a caller's transport that is not itself thread-safe --
    that one is the transport's own contract.

    **Basic authentication is cleartext over plain HTTP**, that being
    what Core's rpc speaks. On loopback, which is what `from_chain`
    builds, the cleartext is between one process and the node beside it.
    For a node anywhere else it is on the wire, and rpc credentials
    authorise every wallet command that node has: an `https` url, or a
    tunnel, is what keeps them off it.

    **One connection per call**, urllib holding none open: every `call`
    sends `Connection: close` and opens a socket of its own. Beside the
    node that is a loopback connect, which costs nothing for one call and
    is socket churn for a great many -- RFC 9112 section 9.6 has the server
    initiating the close on that option, so it is the node that holds the
    sockets in TIME_WAIT -- and to a node reached over `https` it is a TLS
    handshake each time. Either way a caller polling one in a loop wants a
    `transport` of their own, a `requests` session or an `httpx` client.
    Keeping a connection alive here would mean a pool, its own
    thread-safety and its own eviction, none of which one bounded request
    needs.

    No call asks the node which chain it is on: the url and the cookie path
    say where to ask, and what the answers mean is the caller's to hold.
    `getblockchaininfo` is the question, its `chain` member the answer, and
    `network_from_chain` the vocabulary to read it in -- worth the one
    round trip, because a client built for a testnet node under code that
    believes it is on mainnet fails silently. `from_chain`'s `verify_chain`
    makes exactly that call once, at construction.
    """

    def __init__(
        self,
        url: str,
        *,
        user: str | None = None,
        password: str | None = None,
        cookie_path: str | PathLike[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport: HttpTransport = urlopen_transport,
    ) -> None:
        self.url = _checked_url(url)
        if (user is None) != (password is None):
            raise BtcRpcValueError("rpc user and password go together, or neither")
        if user is not None and cookie_path is not None:
            err_msg = "both rpc credentials and a cookie path:"
            err_msg += " either of them says who is calling, so pass one"
            raise BtcRpcValueError(err_msg)
        if user is None and cookie_path is None:
            err_msg = "no rpc credentials: pass user and password, or the"
            err_msg += " path of the cookie file the node writes"
            raise BtcRpcValueError(err_msg)
        for name, value in (("user", user), ("password", password)):
            if value is not None and not isinstance(value, str):
                # the annotation is not a check, and neither half of the
                # credential survives being something else: a `bytes` or an
                # `int` user made the colon test below raise a bare TypeError
                # from underneath the library, and a list passed it and was
                # formatted into the credential -- `['alice']:secret` reaching
                # the node as a username nobody wrote.
                #
                # The type and not the value: a rejected `password` is a
                # credential, and putting it in an exception writes it into
                # every traceback that renders one -- the same reason this
                # class has no generated `__repr__`. The type is what a
                # caller needs to see, `bytes` being the mistake this
                # catches most often
                err_msg = f"non-string rpc {name}: {type(value).__name__}"
                raise BtcRpcTypeError(err_msg)
        if user is not None and ":" in user:
            # the Basic credential is `user:password`, and Core splits it at
            # the *first* colon -- `RPCAuthorized` in src/httprpc.cpp. So a
            # user of `alice:admin` reaches the node as the user `alice`,
            # whose credential begins `admin:`: a different rpc user, a
            # different `-rpcwhitelist` and no error anywhere, the two
            # spellings encoding to the same header so that nothing
            # downstream can tell them apart. A colon on the other side is
            # unambiguous and stays valid, everything after the first one
            # belonging to the second field by definition.
            #
            # The user is not quoted back: the string being refused has a
            # colon in it, so the likeliest thing it holds is `user:password`
            # written into the first argument -- a credential, and one that
            # would go into the traceback with it. `_checked_url` refuses a
            # url with userinfo in it without echoing the url either
            err_msg = "colon in the rpc user. The credential is user:password"
            err_msg += " and the node splits it at the first colon, so a user"
            err_msg += " containing one names a different user than intended"
            raise BtcRpcValueError(err_msg)
        _assert_valid_timeout(timeout, "rpc timeout")
        if cookie_path is not None and not isinstance(cookie_path, (str, PathLike)):
            # what `Path()` on the next line takes, asked before it is asked
            # there: an int reaches it and leaves through a bare TypeError
            # about `__fspath__`, which names pathlib rather than the
            # argument this class was given
            err_msg = f"rpc cookie_path that is no path: {type(cookie_path).__name__}"
            raise BtcRpcTypeError(err_msg)
        if not callable(transport):
            # configuration checked while the caller is still looking at the
            # line that supplied it -- `_checked_url` says why -- and a
            # transport is the one argument where not doing so is a failure
            # at the first `call` instead, out of urllib rather than here
            err_msg = f"rpc transport that is not callable: {type(transport).__name__}"
            raise BtcRpcTypeError(err_msg)
        self.user = user
        self._password = password
        self.cookie_path = None if cookie_path is None else Path(cookie_path)
        self.timeout = timeout
        self.transport = transport

    @classmethod
    def from_chain(
        cls,
        chain: str = "main",
        *,
        user: str | None = None,
        password: str | None = None,
        cookie_path: str | PathLike[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport: HttpTransport = urlopen_transport,
        verify_chain: bool = False,
    ) -> BitcoinCoreRpcClient:
        """Return a client for the local node of one of Core's chains.

        The convenience of not writing out a loopback url, a port and a
        datadir: all three come from Core's own tables, and everything
        else is the constructor's. `chain` is spelled as Core spells it, so
        `main` where BIP32 and BIP173 say `mainnet`; `chain_from_network`
        translates for a caller holding a BIP name, and a chain Core has no
        default port for is an explicit url with a `cookie_path`, which is
        the constructor.

        It asks the node nothing, so it is no claim that one is listening
        on that port, nor that it serves this chain if it is. The first
        `call` is what finds out -- unless `verify_chain` says to make
        that call now, with `getblockchaininfo`, and compare its `chain`
        field to this one.

        Off by default, because a cookie authenticates only that the node
        is the one this call was told about -- a file only that node could
        have written -- and says nothing about which chain it is running:
        `-chain=test` and a `main` cookie both exist. A caller for whom
        that gap matters -- a cookie path or a datadir carried over from a
        differently-configured host, an environment variable naming the
        wrong chain -- opts in and gets `BtcRpcValueError` naming both
        chains instead of a wrong-network call succeeding silently, at the
        cost of one round trip here rather than trust in every call after.
        A reply with no chain to read -- a result that is not a mapping, or
        one whose `chain` is not a string -- is a `FetchError`, this being
        an interpretation of an untrusted reply like any other.

        The datadir comes from `default_datadir` at this call, which is
        Core's own for the platform underneath; where there is no absolute
        directory to hang it off, deriving a cookie path is what this
        refuses -- naming `cookie_path` as the answer.

        Nothing is derived when the caller said who is calling: a `user` or
        a `password`, either of them, is an answer to that question, and
        the constructor is where the two are held to going together. A
        cookie derived before that check would report a missing home
        directory to a caller who passed a password and forgot the user.
        """
        port = rpc_port_from_chain(chain)
        if user is None and password is None and cookie_path is None:
            # the datadir is resolved here, rather than left to
            # `cookie_path_from_chain`'s own default, because the remedy
            # differs: that function names `datadir`, which this
            # constructor does not take, where what a caller of this one
            # passes instead is a `cookie_path`, or credentials
            datadir = default_datadir()
            if datadir is None:
                err_msg = "no absolute home directory (APPDATA on Windows),"
                err_msg += " so no default datadir to find the cookie file"
                err_msg += " in: pass cookie_path, or user and password"
                raise BtcRpcValueError(err_msg)
            cookie_path = cookie_path_from_chain(chain, datadir)
        client = cls(
            f"http://127.0.0.1:{port}",
            user=user,
            password=password,
            cookie_path=cookie_path,
            timeout=timeout,
            transport=transport,
        )
        if verify_chain:
            result = client.call("getblockchaininfo")
            # the shape of the result is the node's and not a given, so it
            # is read rather than indexed: `result["chain"]` on an array is
            # a TypeError about list indices and on a mapping without the
            # member a KeyError, both from underneath a library that
            # reports every other unreadable answer as a FetchError. A
            # mismatch stays a BtcRpcValueError below: that one is a node
            # this client was built for the wrong chain of, which is the
            # caller's configuration, where this is the backend's reply
            reported = result.get("chain") if isinstance(result, Mapping) else None
            if not isinstance(reported, str):
                err_msg = f"getblockchaininfo at {client.url}: no string"
                err_msg += f" chain in the {type(result).__name__} result"
                raise FetchError(err_msg)
            if reported != chain:
                err_msg = f"node at {client.url} reports chain {reported!r},"
                err_msg += f" not the {chain!r} this client was built for"
                raise BtcRpcValueError(err_msg)
        return client

    def for_wallet(self, wallet_name: str) -> BitcoinCoreRpcClient:
        """Return a client for this node's `/wallet/<name>` endpoint.

        Which is how a node with several wallets loaded is told which one
        a wallet command is about. The name is percent-encoded, a wallet
        being a directory and free to be called anything a filesystem
        accepts: a space, a `#` or a `/` written into the path unencoded
        addresses a different endpoint, or none.

        The credentials, the timeout and the transport are this client's,
        the endpoint being the only difference -- so a caller working on
        several wallets builds one client and derives the rest.

        `type(self)` and not this class by name, as `from_chain` builds
        with `cls`: a subclass that derives a wallet client keeps whatever
        it added.
        """
        if not isinstance(wallet_name, str):
            # `quote` takes `bytes` as well, so this is a refusal and not a
            # convenience: `for_wallet(b"hot")` built an endpoint rather
            # than failing, and anything else left through a TypeError of
            # urllib's about `quote_from_bytes`
            err_msg = f"rpc wallet name that is not a string: {wallet_name!r}"
            raise BtcRpcTypeError(err_msg)
        url = f"{self.url.rstrip('/')}/wallet/{quote(wallet_name, safe='')}"
        return type(self)(
            url,
            user=self.user,
            password=self._password,
            cookie_path=self.cookie_path,
            timeout=self.timeout,
            transport=self.transport,
        )

    def auth_header(self) -> str:
        """Return the Basic credential, from the arguments or the cookie.

        RFC 7617 leaves the charset of the credential unspecified and
        Core compares the decoded bytes, so utf-8 is a choice that only
        matters for a password with a non-ascii character in it -- where
        it is the choice that matches what a shell and a config file
        would have written.
        """
        if self.cookie_path is not None:
            credential = cookie_auth(self.cookie_path)
        else:
            credential = f"{self.user}:{self._password}"
        return "Basic " + b64encode(credential.encode()).decode("ascii")

    def call(
        self,
        method: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
        *,
        request_timeout: float | None = None,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    ) -> Any:
        """Invoke one rpc method, returning its `result`.

        `params` is one value, shaped as json-rpc shapes it: a sequence
        for the positional form, a mapping for the named one. The
        client's own controls are keyword-only for that reason --
        `timeout` is a parameter of several Core methods, and a signature
        mixing the two would have to decide which of them owns the name.

        Amounts do not travel as binary floating point in either
        direction: a number in the reply decodes as a Decimal, and a
        Decimal parameter is refused rather than rounded through `float`.
        `NaN` and `Infinity` are refused both ways, being what Python
        writes for floats json has no numbers for.

        `request_timeout` is this call's, defaulting to the client's, and
        for the default transport it bounds the whole exchange -- the
        node's thinking and the reply's arrival together. What it is for
        is the methods that legitimately run long
        -- `rescanblockchain`, `scantxoutset`, `dumptxoutset` -- and the
        replies large enough to take a while on the wire; the alternative
        is a second client whose wider timeout applies to everything.

        `max_body_size` is what the reply may weigh: widen it for the
        answers larger than the default, which `DEFAULT_MAX_BODY_SIZE`
        names, and tighten it where the reply is a number, this being the
        caller's node and the caller's memory.

        There is no retry: one call is one HTTP request, whatever comes
        back. `HttpError.status` is what a caller's own policy reads, and
        this module's docstring says why the policy is theirs.
        """
        request_id = _rpc_id()
        if not isinstance(method, str):
            # json-rpc's `method` is a string, and the annotation is not a
            # check: `call(7)` otherwise built `"method": 7` and sent it,
            # which is this client constructing an invalid request while it
            # walks the caller's params for exactly that reason. An unknown
            # method is a value the node answers for -- that is the point of
            # taking it as an argument -- and a number is not one
            raise BtcRpcTypeError(f"rpc method that is not a string: {method!r}")
        timeout = self.timeout if request_timeout is None else request_timeout
        _assert_valid_timeout(timeout, "rpc request_timeout")
        params_member = _params_member(params)
        _assert_json_params(params_member)
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params_member,
        }
        try:
            body = json.dumps(request, allow_nan=False, default=_refuse_param).encode()
        except ValueError as e:
            # an int of more digits than `sys.get_int_max_str_digits`
            # allows, which is the mirror of the limit a *reply* holding
            # one runs into: json has the number and this interpreter will
            # not write it. The walk above refuses the types json has no
            # rendering for, and this is a value of a type it does, so the
            # encoder is where it surfaces
            raise BtcRpcValueError(f"rpc params json cannot carry: {e}") from e
        status, payload = http_request(
            self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": self.auth_header(),
                # the request `id` marks this client in the node's debug
                # log, and `USER_AGENT` is the half a proxy and an access
                # log see
                "User-Agent": USER_AGENT,
            },
            timeout=timeout,
            max_body_size=max_body_size,
            transport=self.transport,
        )
        return self._result(method, request_id, status, payload)

    def _result(self, method: str, request_id: str, status: int, payload: bytes) -> Any:
        where = f"{method} at {self.url}"
        reply = _reply_object(where, status, payload)
        if "jsonrpc" not in reply:
            # the member and not its value: `"jsonrpc": null` is a reply
            # that names no protocol, which is not the same thing as a
            # 1.1 reply, and it is the member's absence that means 1.1
            return _legacy_result(where, request_id, status, reply)
        marker = reply["jsonrpc"]
        if marker != "2.0":
            # a version this module does not read, so the object is no
            # answer -- and under a non-200 the status is what is left to
            # report, as it is for a body that would not parse at all. A
            # `"jsonrpc": "1.0"` beside a 503 is a 503, and losing that
            # would cost the caller the policy `HttpError.status` is for
            if status != 200:
                raise _http_error(where, status)
            err_msg = f"{where}: json-rpc version {marker!r}, neither 2.0"
            err_msg += " nor the legacy reply that carries no version at all"
            raise FetchError(err_msg)
        return _v2_result(where, request_id, status, reply)


class RpcChannel:
    """Attribute-style convenience over a client's `call`.

    `channel.getblockcount()` is `client.call("getblockcount")`.
    `channel.getblock(block_hash, 2)` passes the positional form,
    `channel.getblock(blockhash=block_hash, verbosity=2)` the named one
    -- whichever the caller wrote, since json-rpc has one params shape
    per call and not both at once.

    `request_timeout` and `max_body_size`, `call`'s own keyword-only
    controls, are caught by the wrapper and passed to `call` rather than
    travelling to the node as named rpc parameters. That reservation is why
    this class lives here rather than in a caller's own script: it has to
    know which names are `call`'s own, that list is this module's to grow,
    and a copy written against one release is silently wrong against a
    later one that adds a third control -- neither mypy nor a test catches
    a keyword that now reaches Core instead of this class.

    A hand-written guard sits in front of every name starting with `_`,
    dunders included. Without it, `copy.deepcopy`, a pickling path this
    object does not otherwise reach, and an interactive shell probing
    for `_repr_html_` or `_ipython_canary_method_should_not_exist_`
    would each turn into a bound method for an rpc call of that name --
    and calling one is not the same failure as an `AttributeError` a
    caller can catch by name.

    `client`, the one public attribute, is reserved for the same reason:
    it is how a caller reaches the `BitcoinCoreRpcClient` this channel
    wraps, and an rpc method named `client` -- Core has none -- would
    otherwise shadow it.

    Not `BitcoinCoreRpcClient.__getattr__`: that class stays the explicit
    surface `call(method, params)` is, where an unknown attribute is an
    `AttributeError` and `for_walet("hot")` a typo caught at the call
    rather than one more method name sent to the node. This is the
    opt-in beside it, for a caller who has weighed that trade the other
    way for a given script.
    """

    __slots__ = ("client",)

    def __init__(self, client: BitcoinCoreRpcClient) -> None:
        self.client = client

    def __getattr__(self, method: str) -> Callable[..., Any]:
        """Return a bound call to `method`, unless its name starts with `_`."""
        if method.startswith("_"):
            raise AttributeError(method)

        def bound_call(
            *args: Any,
            request_timeout: float | None = None,
            max_body_size: int = DEFAULT_MAX_BODY_SIZE,
            **kwargs: Any,
        ) -> Any:
            if args and kwargs:
                err_msg = f"{method}: positional and named arguments together,"
                err_msg += " json-rpc params being one shape or the other"
                raise BtcRpcValueError(err_msg)
            params: Sequence[Any] | Mapping[str, Any] | None
            params = kwargs or (list(args) if args else None)
            return self.client.call(
                method,
                params,
                request_timeout=request_timeout,
                max_body_size=max_body_size,
            )

        return bound_call
