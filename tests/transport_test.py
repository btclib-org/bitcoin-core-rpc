# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the bounded urllib transport under the rpc client.

`http_request` and `urlopen_transport` are the layer that opens the socket
and maps everything below an HTTP status onto `FetchError`; what a status
*means* is the client's question, and `client_test.py` is where that is
asked.
"""

from __future__ import annotations

import select
import socket
from array import array
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from http.client import (
    BadStatusLine,
    HTTPConnection,
    HTTPException,
    HTTPMessage,
    HTTPSConnection,
    IncompleteRead,
    LineTooLong,
    RemoteDisconnected,
)
from io import BytesIO
from threading import Event, Thread
from time import monotonic
from types import SimpleNamespace, TracebackType
from typing import Any, ClassVar, Self, cast
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPHandler,
    HTTPRedirectHandler,
    OpenerDirector,
    ProxyHandler,
    Request,
    build_opener,
    getproxies_environment,
)
from urllib.response import addinfourl

import pytest
from typing_extensions import override

from bitcoin_core_rpc import transport as transport_module
from bitcoin_core_rpc.errors import BtcRpcTypeError, BtcRpcValueError, FetchError
from bitcoin_core_rpc.transport import (
    _READ_CHUNK,
    DEFAULT_MAX_BODY_SIZE,
    DEFAULT_TIMEOUT,
    MAX_ERROR_BODY_SIZE,
    SessionTransport,
    _read_bounded,
    http_request,
    urlopen_transport,
)
from tests import Recorded

URL = "http://127.0.0.1:8332"
# where a 30x would send the request, and the host that must receive
# nothing: `.invalid` is reserved by RFC 2606, so a test that started
# following redirects would fail on a resolution error rather than reach
# somebody
REDIRECT_URL = "http://elsewhere.invalid/"
# the credential of the reproduction this test was written from, which
# is what the redirected request carried verbatim: `alice:secret`
CREDENTIAL = "Basic YWxpY2U6c2VjcmV0"


def _opener(open_: Callable[..., Any]) -> SimpleNamespace:
    """Return something with an `open`, which is all the transport uses.

    `urlopen_transport` does its I/O through the module's own opener --
    urllib's default one without the redirect handler -- so that is what a
    test replaces, and `.open(request, timeout=...)` is the whole of the
    interface it needs to offer.
    """
    return SimpleNamespace(open=open_)


class FakeResponse:
    """What the real urlopen answers with, reduced to what is read of it.

    `content_length` is what the response *claims*, which is a header and
    so is the sender's claim about the sender: a test sets it apart from
    the body on purpose. `chunk_size` is how much one recv answers with,
    and it caps `read1` alone -- `read` fills what it was asked for, the
    two differing exactly as they do on a `BufferedReader`. That
    difference is the reason the transport reads with `read1`, so a fake
    whose `read` behaved like `read1` would be a fake that cannot tell the
    bounded read from an unbounded wait.
    """

    def __init__(
        self,
        status: int,
        body: bytes,
        *,
        content_length: str | None = None,
        chunk_size: int | None = None,
        will_close: bool = False,
    ) -> None:
        self.status = status
        self._body = body
        self.closed = False
        self._offset = 0
        self._chunk_size = chunk_size
        self._returned_eof = False
        self.reads: list[int | None] = []
        self.headers: dict[str, str] = (
            {} if content_length is None else {"Content-Length": content_length}
        )
        # what `http.client.HTTPResponse.will_close` answers from the
        # `Connection` header and the HTTP version: `SessionTransport`
        # reads this to decide whether the connection it just used is
        # still one to keep, which is the only thing here that cares
        self.will_close = will_close

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def read(self, amt: int | None = None) -> bytes:
        """Return amt octets, or the rest of the body when it is shorter.

        What a `BufferedReader` does: it blocks until it has the whole of
        what was asked for, which is why one `read` cannot be interrupted
        by a deadline and the transport does not use it.
        """
        return self._take(amt, one_recv=False)

    def read1(self, amt: int | None = None) -> bytes:
        """Return what one recv answered with, capped by `chunk_size`.

        Every read is remembered, which is how a test checks that a
        caller's limit reached the read rather than the check after it.
        """
        return self._take(amt, one_recv=True)

    def _take(self, amt: int | None, *, one_recv: bool) -> bytes:
        if self._returned_eof:
            raise AssertionError("the response was read again after EOF")
        self.reads.append(amt)
        size = len(self._body) - self._offset if amt is None else amt
        if one_recv and self._chunk_size is not None:
            size = min(size, self._chunk_size)
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        self._returned_eof = not chunk
        return chunk

    def isclosed(self) -> bool:
        """Return whether a read has reached the end of the body.

        What `http.client.HTTPResponse.isclosed` answers for a body its
        `Content-Length` delimits: it closes the response once a read takes
        the last octet the header announced.
        """
        return self._offset >= len(self._body)


def test_urlopen_transport_reads_status_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one function here that opens a socket, with none opened.

    urlopen is replaced rather than called: what is under test is that
    the status and the body come back untouched and that the timeout is
    handed on, none of which needs a server -- and a test that needed one
    would be a test this suite cannot have.
    """
    seen: dict[str, object] = {}
    response = FakeResponse(200, b"body")

    def fake_open(request: Request, timeout: float) -> FakeResponse:
        seen["request"] = request
        seen["timeout"] = timeout
        return response

    monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))

    request = Request(URL, method="GET")
    assert urlopen_transport(request, 12.5) == (200, b"body")
    assert seen["request"] is request
    assert seen["timeout"] == 12.5
    # the `with` closed it, which is what keeps the connection from
    # being held until the garbage collector notices
    assert response.closed


@contextmanager
def http_error(
    status: int,
    body: bytes = b"",
    *,
    chunk_size: int | None = None,
    content_length: str | None = None,
    no_headers: bool = False,
) -> Iterator[HTTPError]:
    """Yield an HTTPError carrying a body, closed when the test is done.

    Built with no file object, urllib gives it a temporary file of its
    own; nobody closing it is a ResourceWarning raised from a deallocator
    at some later collection, which `filterwarnings = ["error"]` then
    fails an unrelated test with.

    An HTTPError is a response as well as an exception, and the bounded
    read reads it as one: the body is served through `read1` off a
    `FakeResponse`, so `chunk_size` is a drip here as it is there.

    `no_headers` passes `None` for the `hdrs` argument, which is what
    `HTTPError.headers` then answers: the shape a caller writing a test
    double of their own produces, and the one every other helper here
    hides by always building an `HTTPMessage`.
    """
    headers = HTTPMessage()
    if content_length is not None:
        headers["Content-Length"] = content_length
    # typeshed declares `hdrs` as a Message and not an optional one, where
    # `HTTPError.__init__` stores whatever it was handed and `headers`
    # answers it -- so the None this passes is the runtime shape the
    # annotation does not admit, which is why the module under test cannot
    # rely on that annotation either
    error = HTTPError(
        URL,
        status,
        "Internal Server Error",
        None if no_headers else headers,  # type: ignore[arg-type]
        None,
    )
    # `read1` is what an HTTPError forwards to the response it wraps, so
    # typeshed declares no such attribute to assign over
    error.read1 = FakeResponse(status, body, chunk_size=chunk_size).read1  # type: ignore[attr-defined]
    try:
        yield error
    finally:
        error.close()


def test_urlopen_transport_does_not_swallow_an_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-2xx is urlopen's exception, and it goes up to http_request."""
    with http_error(500) as error:

        def fake_open(request: Request, timeout: float) -> FakeResponse:
            raise error

        monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))

        with pytest.raises(HTTPError):
            urlopen_transport(Request(URL, method="GET"), DEFAULT_TIMEOUT)


def test_the_body_of_a_response_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bound is the point of the transport, not a courtesy of the peer.

    An explorer is a host on the internet, and an unbounded `read()` lets
    it decide how much memory this process spends before any parser gets
    to refuse the answer. One octet over the limit is what tells a body at
    the limit from one past it.
    """
    limit = 32

    def serve(body: bytes) -> FakeResponse:
        response = FakeResponse(200, body)

        def fake_open(request: Request, timeout: float) -> FakeResponse:
            return response

        monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))
        return response

    serve(b"a" * limit)
    request = Request(URL, method="GET")
    assert urlopen_transport(request, DEFAULT_TIMEOUT, max_body_size=limit) == (
        200,
        b"a" * limit,
    )

    serve(b"a" * (limit + 1))
    with pytest.raises(FetchError, match=f"larger than the max_body_size of {limit}"):
        urlopen_transport(request, DEFAULT_TIMEOUT, max_body_size=limit)


def test_a_chunked_body_is_read_to_the_limit_and_no_further(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read1(n) answers with one recv, so the bounded read loops.

    A single `read1(limit + 1)` would take a chunked response for a short
    one and hand back a truncated body as if the peer were done with it.
    """
    limit = 100
    body = b"z" * limit
    response = FakeResponse(200, body, chunk_size=7)

    def fake_open(request: Request, timeout: float) -> FakeResponse:
        return response

    monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))

    request = Request(URL, method="GET")
    assert urlopen_transport(request, DEFAULT_TIMEOUT, max_body_size=limit) == (
        200,
        body,
    )


def test_eof_ends_the_incremental_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty chunk is EOF, so the transport does not read it again."""
    response = FakeResponse(200, b"")

    def fake_open(request: Request, timeout: float) -> FakeResponse:
        return response

    monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))

    request = Request(URL, method="GET")
    assert urlopen_transport(request, DEFAULT_TIMEOUT, max_body_size=64) == (
        200,
        b"",
    )
    assert response.reads == [65]
    with pytest.raises(AssertionError, match="read again after EOF"):
        response.read(1)


def test_a_read_asks_for_no_more_than_a_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`read1` allocates what it was asked for, so it is asked for little.

    `HTTPResponse.read1` caps n at the remaining `Content-Length` or at the
    rest of the current chunk, and does neither for a body the close of the
    connection delimits -- where asking for the limit allocates the limit,
    whatever the reply weighs. Both directions are checked: a body of one
    octet under a wide limit, and one that spans several chunks.
    """
    limit = 4 * _READ_CHUNK
    for body in (b"a", b"b" * (limit - 1)):
        response = FakeResponse(200, body)

        def fake_open(
            request: Request, timeout: float, _r: FakeResponse = response
        ) -> FakeResponse:
            return _r

        monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))
        request = Request(URL, method="GET")
        assert urlopen_transport(request, DEFAULT_TIMEOUT, max_body_size=limit) == (
            200,
            body,
        )
        assert max(read for read in response.reads if read is not None) <= _READ_CHUNK


def _clock(*readings: float) -> Callable[[], float]:
    """Return a `monotonic` answering each reading, then repeating the last."""
    remaining = list(readings)

    def now() -> float:
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return now


def test_a_body_that_drips_past_the_deadline_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The socket timeout is per read, so a slow drip never expires it.

    A peer sending one octet just inside the timeout resets it with every
    packet, and the bounded read on its own would wait for `max_body_size`
    of them. The deadline is what ends the loop instead.
    """
    response = FakeResponse(200, b"z" * 100, chunk_size=1)

    def fake_open(request: Request, timeout: float) -> FakeResponse:
        return response

    monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))
    # 0.0 sets a deadline of 1.0, 0.5 is inside it and 9.0 is past it
    monkeypatch.setattr(transport_module, "monotonic", _clock(0.0, 0.5, 9.0))

    request = Request(URL, method="GET")
    with pytest.raises(FetchError, match="still arriving when the timeout expired"):
        urlopen_transport(request, 1.0, max_body_size=100)
    # one read, and the ninety-nine octets still to come are not waited for
    assert response.reads == [101]


def test_a_failure_body_that_drips_past_the_deadline_keeps_its_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The deadline covers the error page too, the status outliving it.

    A drip is a drip whichever status precedes it, and the socket timeout
    is no more of a bound here than it is on an answer: without the
    deadline this call waits for `MAX_ERROR_BODY_SIZE` packets. The page
    is what is lost at the deadline, the status being already in hand and
    the part a caller has a policy for.
    """
    with http_error(503, b"z" * 100, chunk_size=1) as error:

        def fake_open(request: Request, timeout: float) -> FakeResponse:
            raise error

        monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))
        # `http_request` reads 0.0 and sets a deadline of 1.0, the transport
        # reads 0.5 for one of its own, 0.6 is inside both and 9.0 is past
        monkeypatch.setattr(transport_module, "monotonic", _clock(0.0, 0.5, 0.6, 9.0))

        # the ninety-nine octets still to come are not waited for
        assert http_request(URL, timeout=1.0) == (503, b"")


def test_the_deadline_covers_the_connect_and_not_only_the_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Taken before the open, so a slow connect spends the same budget.

    Otherwise a connect just inside the timeout and a body just inside it
    again are two timeouts spent on one exchange.
    """
    response = FakeResponse(200, b"body")

    def fake_open(request: Request, timeout: float) -> FakeResponse:
        return response

    monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))
    monkeypatch.setattr(transport_module, "monotonic", _clock(0.0, 9.0))

    request = Request(URL, method="GET")
    with pytest.raises(FetchError, match="still arriving when the timeout expired"):
        urlopen_transport(request, 1.0, max_body_size=64)
    assert response.reads == []


def test_an_announced_size_over_the_limit_is_refused_before_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Content-Length fails the request early, and is never believed.

    Early because a server that says it is about to send a gigabyte can be
    refused without reading one, and never believed because the header is
    the sender's claim about the sender: the third case below announces a
    single octet and sends more, and the bounded read is what catches it.
    """
    limit = 16
    request = Request(URL, method="GET")

    def serve(response: FakeResponse) -> None:
        def fake_open(req: Request, timeout: float) -> FakeResponse:
            return response

        monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))

    serve(FakeResponse(200, b"a" * 4, content_length=str(limit + 1)))
    with pytest.raises(FetchError, match=f"announced {limit + 1} bytes"):
        urlopen_transport(request, DEFAULT_TIMEOUT, max_body_size=limit)

    # equal is still within the limit: changing `>` to `>=` must not turn
    # the largest permitted response into an early refusal
    serve(FakeResponse(200, b"a" * limit, content_length=str(limit)))
    assert urlopen_transport(request, DEFAULT_TIMEOUT, max_body_size=limit) == (
        200,
        b"a" * limit,
    )

    # not a number: no claim about the size, so the read decides
    serve(FakeResponse(200, b"a" * 4, content_length="banana"))
    assert urlopen_transport(request, DEFAULT_TIMEOUT, max_body_size=limit) == (
        200,
        b"a" * 4,
    )

    serve(FakeResponse(200, b"a" * (limit + 1), content_length="1"))
    with pytest.raises(FetchError, match=f"larger than the max_body_size of {limit}"):
        urlopen_transport(request, DEFAULT_TIMEOUT, max_body_size=limit)


def test_an_oversized_body_from_a_caller_transport_goes_no_further() -> None:
    """What is left to promise for a transport this module did not write.

    A caller's transport hands over bytes it has already read, so nothing
    here can keep it from having read them; refusing to pass the body on
    is the whole of what remains, and it is what keeps a caller's own
    limit meaningful whichever transport is underneath it.
    """
    transport = Recorded((200, b"a" * 40))
    assert http_request(URL, max_body_size=40, transport=transport) == (200, b"a" * 40)

    with pytest.raises(
        FetchError, match="response of 40 bytes, more than the max_body_size of 39"
    ):
        http_request(URL, max_body_size=39, transport=Recorded((200, b"a" * 40)))


def test_the_limit_reaches_the_read_of_the_default_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller's limit is incremental where it can be, i.e. here.

    `HttpTransport` is two positional arguments, so a limit cannot be
    handed to a transport this module did not write; the one it did write
    takes it as a keyword, and `http_request` passes it -- otherwise a
    request for a tip height would buffer megabytes before refusing them.
    """
    response = FakeResponse(200, b"a" * 100)

    def fake_open(request: Request, timeout: float) -> FakeResponse:
        return response

    monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))

    with pytest.raises(FetchError, match="larger than the max_body_size of 64"):
        http_request(URL, max_body_size=64)

    # what the read asked for, and the whole of what it asked for: the
    # limit and the one octet that tells a body at it from one over it
    assert response.reads == [65]


def test_an_odd_limit_still_reads_the_octet_that_proves_it_was_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sentinel octet is read after a chunk exactly fills the limit.

    An odd limit distinguishes `limit + 1` from the bitwise expressions a
    mutation can replace it with. The first chunk leaves that one octet to
    read; stopping with one remaining would silently accept a truncated body.
    """
    response = FakeResponse(200, b"a" * 64, chunk_size=63)

    def fake_open(request: Request, timeout: float) -> FakeResponse:
        return response

    monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))

    with pytest.raises(FetchError, match="larger than the max_body_size of 63"):
        http_request(URL, max_body_size=63)
    assert response.reads == [64, 1]


def test_the_body_of_a_failure_is_truncated_not_refused() -> None:
    """An error page is bounded separately, and by truncation.

    A backend's explanation of why there is no answer is worth having
    even when it arrives longer than the answer would have been allowed to
    be: a 404 page is not a 404-byte page. What it may not be is
    unbounded, an error page being written by whatever is in the way. The
    announcement is not grounds for refusal either, for the same reason:
    the second case below says it is sending more than the bound, and the
    bound is what it is cut to rather than what it is refused by.
    """
    oversized = b"x" * (MAX_ERROR_BODY_SIZE + 10)
    with http_error(404, oversized) as error:
        status, body = http_request(URL, max_body_size=64, transport=Recorded(error))
    assert status == 404
    assert len(body) == MAX_ERROR_BODY_SIZE

    announced = str(MAX_ERROR_BODY_SIZE + 10)
    with http_error(404, oversized, content_length=announced) as error:
        status, body = http_request(URL, max_body_size=64, transport=Recorded(error))
    assert status == 404
    assert len(body) == MAX_ERROR_BODY_SIZE


def test_truncate_is_keyword_only() -> None:
    """`_read_bounded`'s `deadline` is positional, `truncate` cannot join it."""
    read_bounded: Any = _read_bounded
    with pytest.raises(TypeError):
        read_bounded(None, 0, "", 0.0, True)


def test_the_failure_body_limit_is_64_kib() -> None:
    """The public diagnostic bound has a stable value, not only a name."""
    assert MAX_ERROR_BODY_SIZE == 64 * 1024


def test_the_response_of_a_failure_is_closed() -> None:
    """A bounded read leaves octets in it, and nobody else will close it.

    An HTTPError is a response as well as an exception, so releasing the
    connection is this function's now that it stops reading early. Left
    open, it is a ResourceWarning out of a deallocator at whatever later
    moment the collector picks -- which under `filterwarnings = ["error"]`
    fails whichever unrelated test is running then.
    """
    with http_error(500, b"x" * (MAX_ERROR_BODY_SIZE + 1)) as error:
        closed: list[bool] = []
        already = error.close

        def close() -> None:
            closed.append(True)
            already()

        error.close = close  # type: ignore[method-assign]
        status, body = http_request(URL, transport=Recorded(error))

        assert status == 500
        assert len(body) == MAX_ERROR_BODY_SIZE
        assert closed == [True]


@pytest.mark.parametrize("max_body_size", [1.5, "64", None, 64.0, True, False])
def test_a_limit_that_is_no_size_is_refused_as_such(max_body_size: object) -> None:
    """And refused before it is read as one.

    A float reaches `read` and leaves through a bare `TypeError` about the
    argument of a read: outside this module's exception contract, and out
    of a function whose whole subject is what it refuses to read. A bool
    goes with it, through `_is_integer`: `True` would be a limit of one
    octet, and `true` is what a json configuration decodes to.
    """
    transport = Recorded((200, b"7"))
    with pytest.raises(BtcRpcTypeError, match="non-integer max_body_size"):
        http_request(URL, max_body_size=max_body_size, transport=transport)  # type: ignore[arg-type]
    assert transport.requests == []


def test_a_negative_limit_is_no_limit_at_all() -> None:
    """Where zero is a limit: only an empty body answers it."""
    with pytest.raises(BtcRpcValueError, match="negative max_body_size: -1"):
        http_request(URL, max_body_size=-1, transport=Recorded((200, b"")))

    assert http_request(URL, max_body_size=0, transport=Recorded((200, b""))) == (
        200,
        b"",
    )
    with pytest.raises(FetchError, match="more than the max_body_size of 0"):
        http_request(URL, max_body_size=0, transport=Recorded((200, b"7")))


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_a_timeout_that_is_no_duration_is_refused(timeout: float) -> None:
    """A zero, a negative, an infinity and a nan are not seconds to wait.

    `BitcoinCoreRpcClient` already refuses these before `http_request` is
    reached, but `http_request` is public on its own, so a direct caller
    with a transport of their own gets the same refusal rather than
    forwarding the value unexamined.
    """
    transport = Recorded((200, b"7"))
    with pytest.raises(BtcRpcValueError, match="http timeout is not a positive"):
        http_request(URL, timeout=timeout, transport=transport)
    assert transport.requests == []


@pytest.mark.parametrize("timeout", [True, "30", None])
def test_a_non_numeric_timeout_is_refused(timeout: object) -> None:
    """A bool is not a duration: `timeout=True` would be one second."""
    transport = Recorded((200, b"7"))
    with pytest.raises(BtcRpcTypeError, match="non-numeric http timeout"):
        http_request(URL, timeout=timeout, transport=transport)  # type: ignore[arg-type]
    assert transport.requests == []


def test_the_default_limit_is_a_block_in_hex() -> None:
    """Twice Core's buffer bound on a block, plus room for a newline.

    A default and not a ceiling: `getblock` at verbosity 2 answers with
    more than this, and says so by naming `max_body_size`.
    """
    assert DEFAULT_MAX_BODY_SIZE == 2 * 4_000_000 + 1024
    defaults = http_request.__kwdefaults__
    assert defaults is not None
    assert defaults["max_body_size"] == DEFAULT_MAX_BODY_SIZE


def test_the_default_transport_is_the_urllib_one() -> None:
    """Nothing else can be, and no test in this directory relies on it.

    Read off the signature rather than by calling `http_request` without
    a transport, which is the one thing the suite must never do.
    """
    defaults = http_request.__kwdefaults__
    assert defaults is not None
    assert defaults["transport"] is urlopen_transport
    assert defaults["timeout"] == DEFAULT_TIMEOUT
    assert DEFAULT_TIMEOUT == 30.0


def test_the_incremental_limit_is_keyword_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two-argument transport protocol stays valid for custom transports."""
    monkeypatch.setattr(
        transport_module,
        "_OPENER",
        _opener(lambda _request, **_kwargs: FakeResponse(200, b"body")),
    )
    untyped_transport: Any = urlopen_transport
    with pytest.raises(TypeError):
        untyped_transport(Request(URL), DEFAULT_TIMEOUT, 64)


def test_a_transport_equal_to_the_default_is_still_the_callers_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The special incremental path is selected by identity, not equality."""
    monkeypatch.setattr(
        transport_module,
        "_OPENER",
        _opener(
            lambda _request, **_kwargs: FakeResponse(200, b"the module's transport")
        ),
    )

    # PLW1641: an __eq__ that answers True to one object and nothing else
    # has no hash to define, and defining one would be defining the very
    # thing this class exists to lie about
    class EqualTransport:  # ruff: ignore[PLW1641]
        def __init__(self) -> None:
            self.requests: list[Request] = []

        @override
        def __eq__(self, other: object) -> bool:
            return other is urlopen_transport

        def __call__(self, request: Request, timeout: float) -> tuple[int, bytes]:
            self.requests.append(request)
            return 200, b"the caller's transport"

    transport = EqualTransport()
    assert transport == urlopen_transport
    assert http_request(URL, transport=transport) == (200, b"the caller's transport")
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    ("status", "is_error"),
    [(int("399"), False), (int("400"), True), (int("401"), True)],
)
def test_a_caller_transport_uses_400_as_the_error_boundary(
    status: int, is_error: bool
) -> None:
    """A 400 starts diagnostics; a 399 remains a size-limited answer."""
    transport = Recorded((status, b"too long"))
    if not is_error:
        with pytest.raises(FetchError, match="more than the max_body_size of 1"):
            http_request(URL, max_body_size=1, transport=transport)
        return

    assert http_request(URL, max_body_size=1, transport=transport) == (
        status,
        b"too long",
    )


def test_a_get_carries_no_body() -> None:
    """Verify a GET sends no body and uses the default timeout."""
    transport = Recorded((200, b"7"))
    assert http_request(f"{URL}/x", transport=transport) == (200, b"7")
    assert transport.request.get_method() == "GET"
    assert transport.request.data is None
    assert transport.request.full_url == f"{URL}/x"
    assert transport.timeouts == [DEFAULT_TIMEOUT]


def test_data_makes_it_a_post_with_the_headers_given() -> None:
    """Verify data makes the request a POST carrying the headers given."""
    transport = Recorded((200, b"{}"))
    http_request(
        URL,
        data=b'{"method":"getblockcount"}',
        headers={"Content-Type": "application/json"},
        timeout=1.5,
        transport=transport,
    )
    assert transport.request.get_method() == "POST"
    assert transport.body == b'{"method":"getblockcount"}'
    # urllib capitalizes what it is given, so this is the header as sent
    assert transport.request.get_header("Content-type") == "application/json"
    assert transport.timeouts == [1.5]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "data:text/plain,0100000001",
        "ftp://example.com/tx",
        "127.0.0.1:8332",
        "",
    ],
)
def test_only_http_and_https_are_opened(url: str) -> None:
    """The scheme check, which is what makes the S310 waiver true.

    `file:` and `data:` are the two urlopen would otherwise accept, and
    both turn a base url read from configuration into a way of reading
    the local disk. The last two have no scheme at all.
    """
    transport = Recorded((200, b"never reached"))
    with pytest.raises(BtcRpcValueError, match="invalid url scheme"):
        http_request(url, transport=transport)
    assert transport.requests == []


def _recording_opener(monkeypatch: pytest.MonkeyPatch) -> Recorded:
    """Install an opener that records what it was asked, and return it.

    What the refusals below are worth is that they come before anything is
    opened, and the exception alone does not say that -- it is the same
    either side of `_OPENER.open`. So the requests this recorded are the
    assertion, as they are for `http_request`'s own scheme test. It answers
    with a `(status, body)` pair, which is no response at all: a refusal
    that stopped refusing would reach the `with` and fail on the tuple
    rather than pass quietly.
    """
    opener = Recorded((200, b"never reached"))
    monkeypatch.setattr(transport_module, "_OPENER", _opener(opener))
    return opener


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "data:text/plain,0100000001",
        "ftp://example.com/tx",
        "127.0.0.1:8332",
    ],
)
def test_the_transport_opens_nothing_but_http_and_https(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scheme check of the transport, on a `Request` a caller built.

    `urlopen_transport` is public and takes the request rather than the
    url, so `http_request`'s check above is not the boundary for a caller
    who reaches this function directly: without one here, a `file:` request
    read the local file and answered with its bytes, the status coming back
    as None because a file response has none.
    """
    opener = _recording_opener(monkeypatch)
    with pytest.raises(BtcRpcValueError, match="invalid url scheme"):
        # the scheme this builds a request for is the subject of the test,
        # which is what S310 asks about and what the refusal answers
        urlopen_transport(Request(url), DEFAULT_TIMEOUT)  # noqa: S310
    assert opener.requests == []


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_the_transport_refuses_a_timeout_that_is_no_duration(
    timeout: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """And before the connect, the deadline being taken from this number."""
    opener = _recording_opener(monkeypatch)
    with pytest.raises(BtcRpcValueError, match="http timeout is not a positive"):
        urlopen_transport(Request(URL), timeout)
    assert opener.requests == []


@pytest.mark.parametrize("timeout", [True, "30", None])
def test_the_transport_refuses_a_non_numeric_timeout(
    timeout: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`timeout=True` is not one second here either."""
    opener = _recording_opener(monkeypatch)
    with pytest.raises(BtcRpcTypeError, match="non-numeric http timeout"):
        urlopen_transport(Request(URL), timeout)  # type: ignore[arg-type]
    assert opener.requests == []


def test_the_transport_refuses_a_limit_that_is_no_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Instead of refusing it once the response is open.

    `_read_bounded` checks the limit too, and that check is where a
    non-integer one was caught: after `_OPENER.open`, so the request had
    been sent and the response had to be closed to report an argument the
    caller could have been refused for.
    """
    opener = _recording_opener(monkeypatch)
    with pytest.raises(BtcRpcTypeError, match="non-integer max_body_size"):
        urlopen_transport(
            Request(URL),
            DEFAULT_TIMEOUT,
            max_body_size=64.0,  # type: ignore[arg-type]
        )
    with pytest.raises(BtcRpcValueError, match="negative max_body_size: -1"):
        urlopen_transport(Request(URL), DEFAULT_TIMEOUT, max_body_size=-1)
    assert opener.requests == []


def test_an_http_error_is_a_status_and_a_body_not_an_exception() -> None:
    """Where bitcoind's 1.1 error object under an HTTP 500 comes from."""
    with http_error(500, b'{"result":null,"error":{"code":-5}}') as error:
        assert http_request(URL, transport=Recorded(error)) == (
            500,
            b'{"result":null,"error":{"code":-5}}',
        )


def test_the_opener_does_not_follow_a_redirect() -> None:
    """One redirect handler is installed, and it is the one that refuses.

    The direct claim behind the exchange the next test measures, and worth
    a test of its own for what it says when it fails: an opener carrying
    urllib's own handler follows a 30x before this module sees a response,
    and that is a fact about which object is in the chain.
    """
    # getattr with a default because typeshed does not declare `handlers`
    # on OpenerDirector: the attribute is what add_handler appends to, and
    # a plain access would be an attr-defined error rather than a test
    handlers = getattr(transport_module._OPENER, "handlers", [])
    redirect_handlers = [
        handler for handler in handlers if isinstance(handler, HTTPRedirectHandler)
    ]
    assert len(redirect_handlers) == 1
    assert isinstance(redirect_handlers[0], transport_module._NoRedirect)


@pytest.mark.parametrize("variable", ["http_proxy", "HTTPS_PROXY"])
def test_no_proxy_is_taken_from_the_environment(
    variable: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A variable set for a browser does not get the rpc credential.

    `build_opener` installs a `ProxyHandler` built from `getproxies()` by
    default, so without the empty one this module passes it, a call to a
    node on loopback would be sent to whatever host `HTTP_PROXY` names --
    with the `Basic` header this client puts on every request before
    being asked for one. The environment is inherited by everything in a shell
    and is nobody's statement about which host holds the node.

    There is no proxy handler in the chain at all, which is what passing
    an empty map achieves: `ProxyHandler.__init__` sets one `<scheme>_open`
    method per entry, `add_handler` appends a handler only when it
    registered something, and `build_opener` skips the default of a class
    it was handed an instance of. So the empty one takes the place of
    urllib's and then declines to be in the chain.

    Measured against what the default opener does with the same
    environment, which is the other half of the claim: a handler that
    would have proxied is there, and in this module's opener it is not.

    These two variables and not `ALL_PROXY`, which is the case that looks
    like a wildcard and is not one: `getproxies_environment` maps it to
    the key `all`, `ProxyHandler` registers `all_open` from that, and
    `OpenerDirector` dispatches an http request through the `http` chain
    alone. So an `ALL_PROXY` handler is installed and never proxies
    either scheme, which would make this a test that a handler exists
    rather than one about where a credential goes.
    """
    monkeypatch.setenv(variable, "http://proxy.invalid:3128")
    assert getproxies_environment()  # the environment does name one

    default = getattr(build_opener(), "handlers", [])
    assert [h for h in default if isinstance(h, ProxyHandler)]

    handlers = getattr(transport_module._OPENER, "handlers", [])
    assert [h for h in handlers if isinstance(h, ProxyHandler)] == []


@pytest.mark.parametrize(
    "target",
    [
        REDIRECT_URL,  # another origin, which is where the credential leaked
        f"{URL}/moved",  # the same one, i.e. an endpoint that changed path
        "https://elsewhere.invalid/",  # an upgrade
        "ftp://elsewhere.invalid/tx",  # not http at all, and urllib admits it
    ],
)
def test_no_redirect_target_is_followed(target: str) -> None:
    """Cross-origin, same-origin, an upgrade and an ftp target alike.

    urllib's own handler follows all four -- `http_error_302` admits http,
    https, ftp and the empty scheme -- and a redirect policy would have had
    to tell them apart: strip the credential across origins, refuse a
    downgrade, bound the intermediate body, keep the rest. Answering None
    before the target is read is what makes the four one case, and it is
    why a downgrade needs no rule of its own: the scheme of the request is
    not consulted either.
    """
    handlers = getattr(transport_module._OPENER, "handlers", [])
    redirect = next(h for h in handlers if isinstance(h, HTTPRedirectHandler))
    headers = HTTPMessage()
    headers["Location"] = target

    request = Request(URL, data=b"{}", headers={"Authorization": CREDENTIAL})
    assert (
        redirect.redirect_request(
            request, BytesIO(b"moved"), 302, "Found", headers, target
        )
        is None
    )


class RecordedBody(BytesIO):
    """A response body that remembers what the bounded read asked for.

    Which is the half a status cannot show: the read is `read1`, and the
    sizes in `reads` are the bound at work. A handler that followed the
    redirect would take the whole body with `fp.read()` first, leaving
    these sizes to add up to nothing.
    """

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.reads: list[int] = []

    @override
    def read1(self, size: int | None = -1, /) -> bytes:
        """Record the size asked for, and answer as a BytesIO does."""
        self.reads.append(-1 if size is None else size)
        return super().read1(size)


class RecordedHTTP(HTTPHandler):
    """The opener's socket, replaced by a scripted response in memory.

    A handler and not a whole opener: what the redirect exchange runs
    through is urllib's own chain -- the redirect handler, the error
    processor, the default error handler -- and the only part of it that
    would reach the network is this one. `Location` is set on every
    response, so a handler that follows redirects has somewhere to go and
    the test can tell that it went.
    """

    def __init__(self, code: int, body: bytes) -> None:
        super().__init__()
        self.code = code
        self.body = RecordedBody(body)
        self.requests: list[Request] = []

    # typeshed types `http_open` by what urllib's own answers with, an
    # `HTTPResponse` read off a socket; the chain downstream only takes a
    # status, headers and bytes off it, which is what an `addinfourl` is --
    # and what `FileHandler.file_open` beside it answers with
    @override
    def http_open(self, req: Request) -> addinfourl:  # type: ignore[override]
        """Record the request and answer the scripted response."""
        self.requests.append(req)
        headers = HTTPMessage()
        headers["Location"] = REDIRECT_URL
        response = addinfourl(self.body, headers, req.full_url, self.code)
        # what `do_open` sets from the reason line and `HTTPErrorProcessor`
        # reads off a response beside the status; addinfourl has no such
        # attribute of its own, and typeshed says so
        response.msg = "Found"  # type: ignore[attr-defined]
        return response


def _opener_over(handler: HTTPHandler) -> OpenerDirector:
    """Return the module's own opener with `handler` in place of the socket.

    The redirect handler is taken from `_OPENER` rather than named here,
    and that is what makes a test built on this fail if urllib's own comes
    back: the exchange would then be two requests instead of one, which is
    the property under test rather than a spelling of it.
    """
    handlers = getattr(transport_module._OPENER, "handlers", [])
    redirect = next(h for h in handlers if isinstance(h, HTTPRedirectHandler))
    return build_opener(type(redirect), handler)


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_a_redirect_is_a_status_and_not_a_second_request(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    """The credential goes nowhere, and the 30x body is bounded.

    urllib's default handler copies every header but the content ones onto
    the redirected request, so an `Authorization` built for a node reached
    whatever host the `Location` named -- and it read the whole 30x body
    before following, whatever `max_body_size` said.

    The whole chain runs here, socket excepted: `http_request` builds the
    request, `urlopen_transport` hands it to the module's opener, and the
    30x travels `OpenerDirector.error` -> the redirect handler ->
    `HTTPDefaultErrorHandler` -> the `HTTPError` that `http_request`
    answers with a status. What a caller gets is one request and one
    response, which for a caller is a `FetchError` naming the status.
    """
    handler = RecordedHTTP(code, b"x" * (MAX_ERROR_BODY_SIZE + 10))
    monkeypatch.setattr(transport_module, "_OPENER", _opener_over(handler))

    status, body = http_request(
        URL,
        data=b'{"method":"getblockcount"}',
        headers={"Authorization": CREDENTIAL},
        max_body_size=64,
    )

    assert status == code
    # bounded as any failure body is, by truncation rather than refusal
    assert len(body) == MAX_ERROR_BODY_SIZE
    # one request, to the url the caller asked for, carrying the credential
    # exactly once and nowhere else
    assert len(handler.requests) == 1
    assert handler.requests[0].full_url == URL
    assert handler.requests[0].get_header("Authorization") == CREDENTIAL
    # and the body of the 30x was read to the bound and no further, in
    # pieces no larger than one recv allocates -- where the `fp.read()` of
    # a following handler would have taken the whole of it first
    assert sum(handler.body.reads) == MAX_ERROR_BODY_SIZE + 1
    assert max(handler.body.reads) <= _READ_CHUNK
    assert handler.body.closed


@pytest.mark.parametrize(
    "error",
    [
        URLError("Connection refused"),
        TimeoutError("timed out"),
        ConnectionResetError("peer went away"),
        OSError("no route to host"),
        IncompleteRead(b"ab", 10),
        BadStatusLine("not a status line"),
        LineTooLong("header line"),
    ],
)
def test_an_exchange_that_did_not_happen_is_a_fetch_error(error: Exception) -> None:
    """One answer for every way of not getting one.

    A timeout is the one worth naming among the first four: `socket.timeout`
    has been `TimeoutError` since 3.10, so it arrives here as an OSError like
    the rest, and there is nothing left for a caller to tell apart.

    The last three are the other family, and no relation of `OSError`:
    `HTTPException` is a plain Exception, so an `except OSError` never saw
    them. They come from inside the read rather than from the connect -- a
    chunked body that stopped early, a peer answering something that is not
    a status line -- which is exactly where this function's promise that
    everything below the status is a FetchError used to end.
    """
    assert not issubclass(HTTPException, OSError)
    with pytest.raises(FetchError, match="no answer from"):
        http_request(URL, transport=Recorded(error))


def test_a_failure_body_that_cannot_be_read_keeps_its_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The status outlives the error page, which is the part with a policy.

    An `HTTPError` is a response and its body is the backend's diagnosis, so
    it is read -- and that read is over the same connection that just
    failed, so it can fail the same way. What a caller does about a 503 does
    not depend on the page, so the status goes back with an empty body
    rather than being replaced by a report about reading one.
    """

    class UnreadableError(HTTPError):
        def read1(self, amt: int | None = None) -> bytes:
            raise IncompleteRead(b"", 42)

    error = UnreadableError(URL, 503, "busy", HTTPMessage(), None)

    def fake_open(request: Request, timeout: float) -> FakeResponse:
        raise error

    monkeypatch.setattr(transport_module, "_OPENER", _opener(fake_open))

    assert http_request(URL) == (503, b"")


def test_an_http_error_with_no_headers_keeps_its_status_and_body() -> None:
    """`HTTPError.headers` can be None, and the announced size is a courtesy.

    `HTTPError` answers `headers` with the `hdrs` it was built from, so an
    exception a caller's transport raised has `None` there wherever the
    author had no opinion about the field -- and the `Content-Length` read
    off it is the sender's claim, checked before the first octet and absent
    from every chunked reply already. So the status and the bounded body
    come back as they do for the same exception carrying an `HTTPMessage`,
    rather than through the AttributeError that is outside the FetchError
    `http_request` promises for everything below the status.
    """
    page = b"the work queue is full"
    with http_error(503, page, no_headers=True) as error:

        def transport(request: Request, timeout: float) -> tuple[int, bytes]:
            raise error

        assert http_request(URL, data=b"{}", transport=transport) == (503, page)


def test_an_explicitly_empty_body_is_still_a_post() -> None:
    """`data=b""` is a body a caller passed, and a POST is what they asked.

    The public contract is a POST "when data is given", and the truth of the
    bytes is not what gives them: an empty body used to build a GET, which
    Core answers with "JSON-RPC: method not allowed" -- a diagnosis about
    the method for a request whose body was the problem. `urllib.request`
    draws the line at `data is None` too.
    """
    methods = []

    def spy(request: Request, timeout: float) -> tuple[int, bytes]:
        methods.append(request.get_method())
        return 200, b"{}"

    http_request(URL, data=b"", transport=spy)
    http_request(URL, data=b"{}", transport=spy)
    http_request(URL, transport=spy)
    assert methods == ["POST", "POST", "GET"]


# --- SessionTransport: the connection this module keeps between calls ---
#
# `FakeConnection` below is the `_Connection` seam `connection_factory`
# replaces -- no `http.client` object, no socket, so this suite stays as
# hermetic over `SessionTransport` as it already is over `urlopen_transport`.


class _RequestFails:
    """A scripted turn where `request()` itself raises, nothing sent."""

    def __init__(self, error: Exception) -> None:
        self.error = error


class _ResponseFails:
    """A scripted turn where `request()` succeeds and `getresponse()` raises.

    What a write into a connection the peer already closed usually does,
    per the class docstring: the local write succeeds and the failure
    surfaces reading a response that never comes.
    """

    def __init__(self, error: Exception) -> None:
        self.error = error


class _FakeSocket:
    """The one attribute of a connection's socket `SessionTransport` reads.

    `settimeout` is called on a reused connection to refresh its deadline
    for this call, real `HTTPConnection` sockets answering to it the same
    way; every call is remembered, which is what proves a reused
    connection's budget was actually replaced and not left over from the
    call that opened it.
    """

    def __init__(self) -> None:
        self.timeouts: list[float] = []

    def settimeout(self, timeout: float) -> None:
        """Record the timeout `SessionTransport` just refreshed it to."""
        self.timeouts.append(timeout)


class FakeConnection:
    """A `_Connection` double, answering one scripted turn per `request()`.

    Each of `turns` is a `FakeResponse` for an ordinary exchange, or one
    of the two markers above for a failure at one step or the other --
    the distinction `SessionTransport`'s reconnect is written against.
    """

    def __init__(
        self,
        *turns: FakeResponse | _RequestFails | _ResponseFails,
        on_request: Callable[[], None] | None = None,
    ) -> None:
        self._turns = list(turns)
        self._current: FakeResponse | _ResponseFails | None = None
        self._on_request = on_request
        self.sock: _FakeSocket | None = None
        self.timeout: float | None = None
        # what `SessionTransport` sets before a request, and what each
        # request found set, in order
        self.deadline = 0.0
        self.deadlines: list[float] = []
        self.closed = False
        self.requests: list[tuple[str, str, Any, Any]] = []

    def request(
        self, method: str, url: str, body: Any = None, headers: Any = None
    ) -> None:
        """Record the call, then act out the next scripted turn."""
        if self._on_request is not None:
            self._on_request()
        self.requests.append((method, url, body, headers))
        self.deadlines.append(self.deadline)
        turn = self._turns.pop(0)
        if isinstance(turn, _RequestFails):
            raise turn.error
        self.sock = _FakeSocket()
        self._current = turn

    def getresponse(self) -> Any:
        """Return this turn's response, or raise what it scripted instead."""
        current = self._current
        if isinstance(current, _ResponseFails):
            raise current.error
        assert current is not None
        return current

    def close(self) -> None:
        """Drop the socket, the way a real connection's `close()` does."""
        self.closed = True
        self.sock = None


def _connection_factory(
    *connections: FakeConnection,
) -> Callable[[str, str, int, float], FakeConnection]:
    """Return a `connection_factory` answering each of `connections` once.

    One call for a key never seen before asks for one; a stale-connection
    reconnect asks for a second. Asking for a third is the test's own
    mistake and not `SessionTransport`'s, so this raises `IndexError`
    rather than repeating the last the way `tests.Recorded` does for a
    client retry, which is not this file's question.
    """
    remaining = list(connections)

    def factory(scheme: str, host: str, port: int, timeout: float) -> FakeConnection:
        connection = remaining.pop(0)
        connection.timeout = timeout
        return connection

    return factory


def _patch_reuse_probe(monkeypatch: pytest.MonkeyPatch, *, dead: bool) -> None:
    """Make every reused-connection probe answer `dead`, no real socket asked.

    The probe needs a real file descriptor, which `FakeConnection`'s
    socket does not have; this replaces `_is_reused_connection_dead`
    itself instead, the same seam-by-monkeypatch `monotonic` already is
    elsewhere in this file. `test_is_reused_connection_dead_reads_a_real_
    socket` is where the probe's own `poll` and `select` calls are
    exercised instead of assumed.
    """
    monkeypatch.setattr(
        transport_module, "_is_reused_connection_dead", lambda connection: dead
    )


def test_two_calls_to_the_same_host_reuse_one_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The point of the transport: one connection answers both calls."""
    _patch_reuse_probe(monkeypatch, dead=False)
    connection = FakeConnection(FakeResponse(200, b"one"), FakeResponse(200, b"two"))
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    request = Request(URL, method="GET")

    assert transport(request, DEFAULT_TIMEOUT) == (200, b"one")
    assert transport(request, DEFAULT_TIMEOUT) == (200, b"two")

    assert len(connection.requests) == 2
    assert connection.closed is False


@pytest.mark.parametrize("without_poll", [False, True])
def test_is_reused_connection_dead_reads_a_real_socket(
    monkeypatch: pytest.MonkeyPatch, *, without_poll: bool
) -> None:
    """The probe itself, against a real socket pair rather than a fake.

    A live, idle socket reports not dead; the same socket after its peer
    closes its own end reports dead -- the read end of a closed
    connection is read-ready with nothing sent to it, which is the one
    thing this probe is asked to tell apart from a live connection's own
    silence. Asked twice: through `select.poll`, and with `poll` taken
    away, through the `select.select` a platform without it -- Windows --
    falls back to.
    """
    if without_poll:
        # `raising=False`: on Windows there is no `poll` to take away
        monkeypatch.delattr(select, "poll", raising=False)
    readable_end, peer = socket.socketpair()
    try:
        connection = SimpleNamespace(sock=readable_end)
        assert transport_module._is_reused_connection_dead(connection) is False
        peer.close()
        assert transport_module._is_reused_connection_dead(connection) is True
    finally:
        readable_end.close()


def test_the_probe_reads_a_descriptor_select_refuses() -> None:
    """A descriptor at `FD_SETSIZE` or above is probed like any other.

    `select.select` answers such a descriptor with a `ValueError` outside
    Windows -- the control below, taken on the very socket the probe is
    then asked about -- so a process holding that many open files could
    not reuse a connection at all. `fcntl` and `resource` are POSIX
    modules, and Windows' `select` does not bound a descriptor's value.
    """
    fcntl = pytest.importorskip("fcntl")
    resource = pytest.importorskip("resource")
    # 1024 is `FD_SETSIZE` on Linux and on macOS alike; `F_DUPFD` answers
    # the lowest free descriptor at or above it rather than replacing one
    # the process already holds, and the soft limit is raised only where
    # it would refuse that descriptor
    fd_setsize = 1024
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (max(soft, fd_setsize + 1), hard))
    readable_end, peer = socket.socketpair()
    try:
        high = socket.socket(
            fileno=fcntl.fcntl(readable_end.fileno(), fcntl.F_DUPFD, fd_setsize)
        )
        try:
            assert high.fileno() >= fd_setsize
            with pytest.raises(ValueError, match="out of range"):
                select.select([high], [], [], 0)
            connection = SimpleNamespace(sock=high)
            assert transport_module._is_reused_connection_dead(connection) is False
            peer.close()
            assert transport_module._is_reused_connection_dead(connection) is True
        finally:
            high.close()
    finally:
        readable_end.close()
        peer.close()
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def test_a_dead_socket_found_at_reuse_is_evicted_before_any_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A probe that finds the kept socket already readable evicts it first.

    Nothing is sent on the evicted connection at all -- unlike the
    reconnect elsewhere in this file, which sends again knowing the first
    attempt never reached the wire in full -- so the second connection
    answering is the ordinary fresh-connection case, not a retried one.
    """
    monkeypatch.setattr(
        transport_module, "_is_reused_connection_dead", lambda connection: True
    )
    stale = FakeConnection(FakeResponse(200, b"first"))
    fresh = FakeConnection(FakeResponse(200, b"second"))
    transport = SessionTransport(connection_factory=_connection_factory(stale, fresh))
    request = Request(URL, method="GET")

    assert transport(request, DEFAULT_TIMEOUT) == (200, b"first")
    assert transport(request, DEFAULT_TIMEOUT) == (200, b"second")

    assert stale.closed is True
    assert len(stale.requests) == 1
    assert len(fresh.requests) == 1


def test_an_evicted_connection_is_popped_and_not_left_pooled_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closing the connection the probe evicts is not enough on its own.

    `_time_left` for whatever replaces it can itself raise -- a deadline
    already spent -- from a line outside the `try` below that would
    otherwise have popped the key on any other failure; a probed-dead
    connection is popped right where it is closed instead, so this exit
    does not leave `self._connections[key]` holding a connection whose
    `sock` the close already set to `None`, for a later call's own probe
    to run `select` against.
    """
    stale = FakeConnection(FakeResponse(200, b"first"))
    transport = SessionTransport(connection_factory=_connection_factory(stale))
    request = Request(URL, method="GET")

    assert transport(request, DEFAULT_TIMEOUT) == (200, b"first")
    assert transport._connections != {}

    monkeypatch.setattr(
        transport_module, "_is_reused_connection_dead", lambda connection: True
    )
    monkeypatch.setattr(transport_module, "monotonic", _increasing_clock(1000.0))

    with pytest.raises(FetchError, match="timeout expired"):
        transport(request, DEFAULT_TIMEOUT)

    assert stale.closed is True
    assert transport._connections == {}


def test_a_different_host_gets_a_connection_of_its_own() -> None:
    """The key is `(scheme, host, port)`, not one connection for everything."""
    first = FakeConnection(FakeResponse(200, b"a"))
    second = FakeConnection(FakeResponse(200, b"b"))
    transport = SessionTransport(connection_factory=_connection_factory(first, second))

    assert transport(Request(URL, method="GET"), DEFAULT_TIMEOUT) == (200, b"a")
    other = Request("http://127.0.0.1:18443/", method="GET")
    assert transport(other, DEFAULT_TIMEOUT) == (200, b"b")

    assert len(first.requests) == 1
    assert len(second.requests) == 1


def _increasing_clock(step: float = 1.0) -> Callable[[], float]:
    """Return a `monotonic` whose reading grows by `step` every call.

    Unlike `_clock` above, a scenario using this does not need its own
    `monotonic()` calls counted in advance -- only that a later one sees
    a larger reading than an earlier one, which is what a real clock
    gives too and what a deadline-over-several-calls test needs.
    """
    value = -step

    def now() -> float:
        nonlocal value
        value += step
        return value

    return now


def test_the_reconnect_is_given_what_is_left_of_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One deadline over the whole exchange, not a fresh one per attempt.

    The reconnect's own connection is asked for with less time than the
    call started with: some of the second call's own budget is already
    spent finding the kept connection stale by the time the reconnect's
    `connection_factory` call is reached.
    """
    _patch_reuse_probe(monkeypatch, dead=False)
    stale = FakeConnection(
        FakeResponse(200, b"first"),
        _RequestFails(BrokenPipeError("gone")),
    )
    fresh = FakeConnection(FakeResponse(200, b"second"))
    connections = iter((stale, fresh))
    seen_timeouts: list[float] = []

    def factory(scheme: str, host: str, port: int, timeout: float) -> FakeConnection:
        seen_timeouts.append(timeout)
        return next(connections)

    transport = SessionTransport(connection_factory=factory)
    monkeypatch.setattr(transport_module, "monotonic", _increasing_clock())
    request = Request(URL, method="GET")

    assert transport(request, 10.0) == (200, b"first")
    assert transport(request, 10.0) == (200, b"second")

    # one factory call for the first, fresh connect, and one for the
    # reconnect -- the second call's own reused connection never asks the
    # factory for anything
    assert len(seen_timeouts) == 2
    assert seen_timeouts[1] < seen_timeouts[0]


def test_a_deadline_already_spent_refuses_the_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_time_left` refuses to hand a socket a timeout of zero or less.

    A real socket answers a non-positive timeout with its own
    `ValueError`; this is the one place the whole exchange's deadline can
    already be spent before any connect is attempted, and it is refused
    here instead, as a `FetchError` like every other exchange failure.
    """
    clock = iter((0.0, 100.0))
    monkeypatch.setattr(transport_module, "monotonic", lambda: next(clock))
    connection = FakeConnection(FakeResponse(200, b"{}"))
    transport = SessionTransport(connection_factory=_connection_factory(connection))

    with pytest.raises(FetchError, match="timeout expired"):
        transport(Request(URL, method="GET"), 1.0)

    assert connection.requests == []


@pytest.mark.parametrize(
    "error",
    [
        RemoteDisconnected("Remote end closed connection without response"),
        ConnectionResetError("reset while reading the response"),
    ],
)
def test_a_drop_after_the_write_is_not_re_sent(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """The probe passes, the write goes through, and the read fails.

    The whole request has been written by then, and a node that executed
    it and closed before answering produces the `RemoteDisconnected`
    scripted here -- a wallet command sent again could run twice. So
    whatever the read
    raises reaches the caller, from a reused connection as from a fresh
    one, and `http_request` reports it as a `FetchError`. The factory
    has this one connection to give, so a re-send would be this test's
    own `IndexError` rather than the `FetchError` asserted.
    """
    _patch_reuse_probe(monkeypatch, dead=False)
    stale = FakeConnection(FakeResponse(200, b"first"), _ResponseFails(error))
    transport = SessionTransport(connection_factory=_connection_factory(stale))

    assert http_request(URL, data=b"{}", transport=transport) == (200, b"first")
    with pytest.raises(FetchError, match="no answer from") as excinfo:
        http_request(URL, data=b"{}", transport=transport)

    assert excinfo.value.__cause__ is error
    assert len(stale.requests) == 2
    assert stale.closed is True
    assert transport._connections == {}


def test_a_stale_write_is_retried_once_on_a_reused_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The probe passes, and the drop surfaces at the write instead.

    The probe is answered `False` here too: `request()` itself raising is
    the one shape of a drop the probe missed that is retried, the request
    not having reached the wire in full, so no node can have executed it.
    """
    _patch_reuse_probe(monkeypatch, dead=False)
    stale = FakeConnection(
        FakeResponse(200, b"first"),
        _RequestFails(BrokenPipeError("write failed")),
    )
    fresh = FakeConnection(FakeResponse(200, b"second"))
    transport = SessionTransport(connection_factory=_connection_factory(stale, fresh))
    request = Request(URL, method="GET")

    assert transport(request, DEFAULT_TIMEOUT) == (200, b"first")
    assert transport(request, DEFAULT_TIMEOUT) == (200, b"second")

    assert len(stale.requests) == 2
    assert stale.closed is True
    assert len(fresh.requests) == 1


def test_a_fresh_connections_getresponse_failure_is_not_retried() -> None:
    """The fresh connection's twin of the reused one's test above.

    `RemoteDisconnected` out of a connection's very first `getresponse()`
    is not retried either, and the connection is not left pooled.
    """
    connection = FakeConnection(_ResponseFails(RemoteDisconnected("gone")))
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    request = Request(URL, method="GET")

    with pytest.raises(RemoteDisconnected):
        transport(request, DEFAULT_TIMEOUT)

    assert len(connection.requests) == 1
    assert connection.closed is True
    assert transport._connections == {}


def test_a_fresh_connections_first_failure_is_not_retried() -> None:
    """A node not answering is not a stale kept-alive connection.

    The reconnect above is only offered where a connection was already
    open before the call; the same failure on one just created here is a
    node this transport has never reached, which no reconnect fixes. The
    connection is still closed and never pooled -- `test_a_fresh_connect_
    failure_does_not_poison_the_pool` is where that is what the next call
    depends on.
    """
    connection = FakeConnection(_RequestFails(ConnectionResetError("refused")))
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    request = Request(URL, method="GET")

    with pytest.raises(ConnectionResetError):
        transport(request, DEFAULT_TIMEOUT)

    assert len(connection.requests) == 1
    assert connection.closed is True
    assert transport._connections == {}


def test_a_fresh_connect_failure_does_not_poison_the_pool() -> None:
    """A dead connection left pooled would fail this key forever.

    Two calls while the node is down, then one after it answers: the
    third succeeds, which it could not if the first failure's connection
    were still sitting in the pool for every later call to inherit --
    `connection.sock.settimeout` on the `None` a failed connect leaves
    behind, an `AttributeError` escaping the module's
    every-failure-is-`FetchError` contract, forever, is the shape this
    refuses.
    """
    node_is_up = False

    def factory(scheme: str, host: str, port: int, timeout: float) -> FakeConnection:
        if not node_is_up:
            return FakeConnection(_RequestFails(ConnectionRefusedError("refused")))
        return FakeConnection(FakeResponse(200, b"{}"))

    transport = SessionTransport(connection_factory=factory)

    with pytest.raises(FetchError):
        http_request(URL, transport=transport)
    with pytest.raises(FetchError):
        http_request(URL, transport=transport)

    node_is_up = True
    assert http_request(URL, transport=transport) == (200, b"{}")


def test_a_failure_once_the_request_is_on_the_wire_is_not_re_sent() -> None:
    """A status line did arrive, so the write was long done: nothing is re-sent.

    An oversized body is what is used to make the read fail here, the
    same bound `urlopen_transport` enforces -- what matters for this test
    is that it happens after `getresponse()` already succeeded, and that
    it is answered by closing the connection rather than by sending the
    request again.
    """
    connection = FakeConnection(FakeResponse(200, b"z" * 10))
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    request = Request(URL, method="GET")

    with pytest.raises(FetchError, match="larger than the max_body_size of 5"):
        transport(request, DEFAULT_TIMEOUT, max_body_size=5)

    assert len(connection.requests) == 1
    assert connection.closed is True


def test_the_max_body_size_bounds_what_the_session_transport_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One octet over the limit is refused; the limit itself is not."""
    _patch_reuse_probe(monkeypatch, dead=False)
    limit = 32
    connection = FakeConnection(
        FakeResponse(200, b"a" * limit), FakeResponse(200, b"a" * (limit + 1))
    )
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    request = Request(URL, method="GET")

    assert transport(request, DEFAULT_TIMEOUT, max_body_size=limit) == (
        200,
        b"a" * limit,
    )
    with pytest.raises(FetchError, match=f"larger than the max_body_size of {limit}"):
        transport(request, DEFAULT_TIMEOUT, max_body_size=limit)


def test_http_request_hands_a_tighter_limit_to_the_session_transport_read() -> None:
    """The read stops at the call's limit, not after a whole default's worth.

    "larger than" is `_read_bounded`'s refusal and "response of" is the one
    `http_request` makes of bytes already held, so the message says which
    of the two refused; the one read asked for no more than the limit and
    the octet past it.
    """
    response = FakeResponse(200, b"a" * 40)
    transport = SessionTransport(
        connection_factory=_connection_factory(FakeConnection(response))
    )

    with pytest.raises(FetchError, match="larger than the max_body_size of 39"):
        http_request(URL, max_body_size=39, transport=transport)

    assert response.reads == [40]


def test_http_request_hands_a_wider_limit_to_the_session_transport_read() -> None:
    """An answer over the default is read whole when the call allows it."""
    body = b"a" * (DEFAULT_MAX_BODY_SIZE + 1)
    response = FakeResponse(200, body, content_length=str(len(body)))
    transport = SessionTransport(
        connection_factory=_connection_factory(FakeConnection(response))
    )

    assert http_request(URL, max_body_size=len(body), transport=transport) == (
        200,
        body,
    )


def test_the_session_transport_refuses_a_limit_that_is_no_size() -> None:
    """Checked before anything is sent, as `urlopen_transport` checks it."""
    connection = FakeConnection(FakeResponse(200, b""))
    transport = SessionTransport(connection_factory=_connection_factory(connection))

    with pytest.raises(BtcRpcValueError, match="negative max_body_size: -1"):
        transport(Request(URL, method="GET"), DEFAULT_TIMEOUT, max_body_size=-1)

    assert connection.requests == []


def test_session_transport_truncates_an_oversized_error_body() -> None:
    """A 4xx/5xx body is cut to MAX_ERROR_BODY_SIZE, not refused.

    A legacy 1.1 rpc error under HTTP 500, larger than the call's
    max_body_size, still comes back with its status and its body, bounded
    the way http_request bounds the body of urlopen_transport's HTTPError.
    """
    payload = b"e" * (MAX_ERROR_BODY_SIZE + 50)
    connection = FakeConnection(
        FakeResponse(500, payload, content_length=str(len(payload)))
    )
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    request = Request(URL, method="POST", data=b"{}")

    status, body = transport(request, DEFAULT_TIMEOUT, max_body_size=100)

    assert status == 500
    assert body == payload[:MAX_ERROR_BODY_SIZE]


def test_a_connection_left_inside_a_cut_error_body_is_not_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rest of a cut body is still due, so the next call opens its own.

    The probe answers alive, as it does while that rest is still in
    flight: kept, the connection would carry the next request in full and
    hand its `getresponse()` the leftovers of this one.
    """
    _patch_reuse_probe(monkeypatch, dead=False)
    payload = b"e" * (MAX_ERROR_BODY_SIZE + 50)
    first = FakeConnection(FakeResponse(500, payload, content_length=str(len(payload))))
    second = FakeConnection(FakeResponse(200, b"b"))
    transport = SessionTransport(connection_factory=_connection_factory(first, second))
    request = Request(URL, method="POST", data=b"{}")

    assert transport(request, DEFAULT_TIMEOUT)[0] == 500
    assert first.closed is True

    assert transport(request, DEFAULT_TIMEOUT) == (200, b"b")
    assert len(first.requests) == 1
    assert len(second.requests) == 1


def test_an_error_body_read_to_its_end_keeps_the_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An rpc error under HTTP 500 costs no reconnect when it was read whole."""
    _patch_reuse_probe(monkeypatch, dead=False)
    error = b'{"result": null, "error": {"code": -5}, "id": 1}'
    connection = FakeConnection(FakeResponse(500, error), FakeResponse(200, b"b"))
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    request = Request(URL, method="POST", data=b"{}")

    assert transport(request, DEFAULT_TIMEOUT) == (500, error)
    assert transport(request, DEFAULT_TIMEOUT) == (200, b"b")
    assert len(connection.requests) == 2
    assert connection.closed is False


def test_the_session_transport_deadline_bounds_a_dripping_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same deadline `_read_bounded` reads for `urlopen_transport`.

    A peer sending one octet just inside a per-read timeout would reset
    it with every packet; the deadline taken once, before the connect or
    reuse, is what ends the wait instead.
    """
    response = FakeResponse(200, b"z" * 100, chunk_size=1)
    connection = FakeConnection(response)
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    # one extra reading over `_read_bounded`'s own three (0.0 for the
    # deadline, 0.5 inside it, 9.0 past it): `_time_left` reads the clock
    # once more, connecting the fresh connection before any of that
    monkeypatch.setattr(transport_module, "monotonic", _clock(0.0, 0.1, 0.5, 9.0))
    request = Request(URL, method="GET")

    with pytest.raises(FetchError, match="still arriving when the timeout expired"):
        transport(request, 1.0, max_body_size=100)

    assert response.reads == [101]
    assert connection.closed is True


def test_no_redirect_is_followed() -> None:
    """`http.client` follows none on its own: a 30x is just a status."""
    connection = FakeConnection(FakeResponse(301, b"", content_length="0"))
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    request = Request(URL, method="GET")

    assert transport(request, DEFAULT_TIMEOUT) == (301, b"")
    assert len(connection.requests) == 1


def test_a_connection_the_node_says_to_close_is_not_kept() -> None:
    """`will_close` is read off the response, not assumed either way."""
    first = FakeConnection(FakeResponse(200, b"a", will_close=True))
    second = FakeConnection(FakeResponse(200, b"b"))
    transport = SessionTransport(connection_factory=_connection_factory(first, second))
    request = Request(URL, method="GET")

    assert transport(request, DEFAULT_TIMEOUT) == (200, b"a")
    assert first.closed is True

    assert transport(request, DEFAULT_TIMEOUT) == (200, b"b")
    assert len(first.requests) == 1
    assert len(second.requests) == 1


def test_the_method_path_body_and_headers_reach_the_connection() -> None:
    """What `SessionTransport` hands `http.client` is what the request built."""
    connection = FakeConnection(FakeResponse(200, b"{}"))
    transport = SessionTransport(connection_factory=_connection_factory(connection))
    request = Request(
        "http://127.0.0.1:8332/wallet/hot",
        data=b'{"id": 1}',
        headers={"Authorization": "Basic xx", "Content-Type": "application/json"},
        method="POST",
    )

    transport(request, DEFAULT_TIMEOUT)

    method, path, body, headers = connection.requests[0]
    assert method == "POST"
    assert path == "/wallet/hot"
    assert body == b'{"id": 1}'
    assert headers["Authorization"] == "Basic xx"


def test_the_session_transport_refuses_a_non_http_scheme() -> None:
    """Checked here too, and not only where a caller reaches `http_request`."""
    transport = SessionTransport()
    # the scheme this builds on purpose, to prove `SessionTransport` itself
    # refuses it, is what S310 is written to flag -- the same waiver
    # `http_request`'s own `Request(...)` carries, for the same reason
    request = Request("file:///etc/passwd")  # ruff: ignore[S310]
    with pytest.raises(BtcRpcValueError, match="invalid url scheme"):
        transport(request, DEFAULT_TIMEOUT)


def test_the_session_transport_refuses_a_url_with_no_host() -> None:
    """`urlsplit("http:///path").hostname` is `None`, which is not a key."""
    transport = SessionTransport()
    with pytest.raises(BtcRpcValueError, match="no host in url"):
        transport(Request("http:///path"), DEFAULT_TIMEOUT)


def test_the_session_transport_refuses_an_unparsable_port() -> None:
    """`urlsplit(...).port` raises a bare `ValueError` on its own, unasked.

    Unlike the scheme and the host, the port is a property rather than a
    stored field, so this is checked separately -- and reachable through
    `http_request(url, transport=SessionTransport())` with a url built by
    hand, where every other refusal here is checked directly against the
    transport for the same reason.
    """
    transport = SessionTransport()
    with pytest.raises(BtcRpcValueError, match="invalid port in url"):
        transport(Request("http://127.0.0.1:abc/"), DEFAULT_TIMEOUT)


def test_the_default_connection_factory_picks_the_class_by_scheme() -> None:
    """`_new_connection`, never exercised by a test naming its own fake.

    Constructing an `HTTPConnection` opens no socket -- `connect()` runs
    lazily, on the first `request()`, which this never calls -- so this
    stays as hermetic as the rest of the suite.
    """
    plain = transport_module._new_connection("http", "127.0.0.1", 8332, 5.0)
    assert type(plain) is transport_module._DeadlineHTTPConnection
    assert isinstance(plain, HTTPConnection)

    secure = transport_module._new_connection("https", "127.0.0.1", 443, 5.0)
    assert type(secure) is transport_module._DeadlineHTTPSConnection
    assert isinstance(secure, HTTPSConnection)


def test_the_session_transport_refuses_a_timeout_that_is_no_duration() -> None:
    """Checked before a connection is even asked for."""
    transport = SessionTransport(
        connection_factory=_connection_factory(FakeConnection())
    )
    with pytest.raises(BtcRpcValueError, match="not a positive number of seconds"):
        transport(Request(URL, method="GET"), 0)


def test_close_closes_every_pooled_connection() -> None:
    """`close()` is the one thing here with a socket to give up between calls.

    Both keys of a transport that talked to two hosts, in one call.
    """
    first = FakeConnection(FakeResponse(200, b"a"))
    second = FakeConnection(FakeResponse(200, b"b"))
    transport = SessionTransport(connection_factory=_connection_factory(first, second))
    transport(Request(URL, method="GET"), DEFAULT_TIMEOUT)
    transport(Request("http://127.0.0.1:18443/", method="GET"), DEFAULT_TIMEOUT)

    transport.close()

    assert first.closed is True
    assert second.closed is True


def test_the_context_manager_closes_on_the_way_out() -> None:
    """`with SessionTransport() as transport:` closes what it opened."""
    connection = FakeConnection(FakeResponse(200, b"a"))
    with SessionTransport(connection_factory=_connection_factory(connection)) as t:
        t(Request(URL, method="GET"), DEFAULT_TIMEOUT)

    assert connection.closed is True


def test_the_whole_exchange_is_serialized_under_one_lock() -> None:
    """One lock guards connect-or-reuse, send and read together.

    The class docstring's reason: guarding only the pool would still let
    two threads drive one connection's `request()` and `getresponse()` at
    once. Checked without a second thread -- `Lock.locked()` answers the
    same regardless of which thread asks -- by reading it from inside the
    one call in flight.
    """
    seen: dict[str, bool] = {}

    def check() -> None:
        seen["locked"] = transport._lock.locked()

    connection = FakeConnection(FakeResponse(200, b"a"), on_request=check)
    transport = SessionTransport(connection_factory=_connection_factory(connection))

    transport(Request(URL, method="GET"), DEFAULT_TIMEOUT)

    assert seen["locked"] is True
    assert transport._lock.locked() is False


# --- The deadline below the response: lookup, connect, send, headers ---


@contextmanager
def _peer(serve: Callable[[socket.socket, Event], None]) -> Iterator[str]:
    """Yield the url of a loopback peer answering one connection with `serve`.

    A peer of the test's own on 127.0.0.1, reaching no network: `serve` is
    handed the accepted connection and an `Event` set when the test is
    done with it, and runs on a thread of its own until then.
    """
    server = socket.create_server(("127.0.0.1", 0))
    done = Event()

    def accept() -> None:
        with suppress(OSError):
            connection, _ = server.accept()
            with connection:
                serve(connection, done)

    peer = Thread(target=accept, daemon=True)
    peer.start()
    try:
        yield f"http://127.0.0.1:{server.getsockname()[1]}/"
    finally:
        done.set()
        server.close()
        peer.join()


def _drip_headers(connection: socket.socket, done: Event) -> None:
    """Answer a status line, then one octet of a header every millisecond.

    For ten seconds at least, and then close: `http.client` reads an
    unfinished header line up to 64 KiB long, so without a deadline the
    call waits out the drip and, once the peer closes, answers a 200.
    """
    connection.recv(65536)
    connection.sendall(b"HTTP/1.1 200 OK\r\nX-Drip: ")
    drips = iter(range(10_000))
    with suppress(OSError):
        while not done.wait(0.001) and next(drips, None) is not None:
            connection.sendall(b"a")


@pytest.mark.parametrize("session", [False, True])
def test_a_peer_dripping_headers_is_held_to_the_deadline(
    monkeypatch: pytest.MonkeyPatch, *, session: bool
) -> None:
    """Every recv of the headers is given what is left, and none resets it.

    A socket timeout spent per recv is what a peer sending an octet just
    inside it keeps renewing, and the headers arrive before `_read_bounded`
    has anything to check. The clock advances once per reading instead of
    with time, so what ends the call is how many operations it made -- a
    few dozen, the drip being endless for as long as they take.
    """
    monkeypatch.setattr(transport_module, "monotonic", _increasing_clock())
    with (
        _peer(_drip_headers) as url,
        SessionTransport() as session_transport,
        pytest.raises(FetchError, match="timed out"),
    ):
        transport = session_transport if session else urlopen_transport
        http_request(url, timeout=50.0, transport=transport)


def test_a_tls_handshake_is_held_to_the_deadline() -> None:
    """The `https` connection urllib opens hands the handshake what is left.

    A listening socket that never accepts still completes the TCP connect,
    from the backlog, and then answers no ClientHello: the handshake is
    what waits, and the timeout is what ends it.
    """
    with socket.create_server(("127.0.0.1", 0)) as silent:
        url = f"https://127.0.0.1:{silent.getsockname()[1]}/"
        with pytest.raises(FetchError, match="timed out"):
            http_request(url, timeout=0.2)


class _TrickleSocket:
    """A socket taking `take` octets per `send` at most, remembering each.

    What each send was offered and each timeout it was given are kept, as
    are the octets taken.
    """

    def __init__(self, take: int) -> None:
        self.take = take
        self.timeouts: list[float] = []
        self.offered: list[int] = []
        self.sent = bytearray()

    def settimeout(self, timeout: float) -> None:
        """Record the timeout this send is given."""
        self.timeouts.append(timeout)

    def send(self, data: memoryview) -> int:
        """Take the first `take` octets of `data` and nothing more."""
        self.offered.append(data.nbytes)
        taken = data[: self.take]
        self.sent += taken
        return taken.nbytes


def _trickle_sendall(
    monkeypatch: pytest.MonkeyPatch, data: Any, deadline: float, take: int = 1
) -> _TrickleSocket:
    """Send `data` through a `_DeadlineSocket` over a `_TrickleSocket`.

    The clock reads 0.0, 1.0, 2.0 and on, one reading per send.
    """
    monkeypatch.setattr(transport_module, "monotonic", _increasing_clock())
    trickle = _TrickleSocket(take)
    sock = transport_module._DeadlineSocket(
        cast("socket.socket", trickle),
        lambda: transport_module._seconds_left(deadline),
    )
    sock.sendall(data)
    return trickle


def test_each_send_is_given_what_is_left(monkeypatch: pytest.MonkeyPatch) -> None:
    """A peer taking a request one octet at a time renews nothing."""
    trickle = _trickle_sendall(monkeypatch, b"abc", deadline=10.0)
    assert trickle.sent == b"abc"
    assert trickle.timeouts == [10.0, 9.0, 8.0]


def test_a_send_past_the_deadline_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """What is left of the request once the deadline passes is not sent."""
    with pytest.raises(TimeoutError, match="timed out"):
        _trickle_sendall(monkeypatch, b"abcdef", deadline=3.0)


def test_each_send_is_offered_a_chunk_at_most(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never the rest of a large body, which PyPy's `send` pays for whole."""
    chunk = transport_module._SEND_CHUNK
    data = bytes(2 * chunk + 1)
    trickle = _trickle_sendall(monkeypatch, data, deadline=10.0, take=chunk)
    assert trickle.offered == [chunk, chunk, 1]
    assert trickle.sent == data


def test_a_body_of_wider_items_is_sent_as_its_octets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A buffer whose items are not octets is counted in octets, not items.

    `send` answers octets, so slicing the view it was given by that answer
    has to slice octets too.
    """
    body = array("i", [1, 2])
    trickle = _trickle_sendall(monkeypatch, body, deadline=100.0)
    assert trickle.sent == body.tobytes()


class _AttemptSocket:
    """A socket whose `connect` raises what the test scripted, or succeeds."""

    attempts: ClassVar[list[_AttemptSocket]] = []
    errors: ClassVar[list[OSError | None]] = []

    def __init__(self, *args: object) -> None:
        self.timeouts: list[float] = []
        self.closed = False
        self.error = _AttemptSocket.errors.pop(0)
        _AttemptSocket.attempts.append(self)

    def settimeout(self, timeout: float) -> None:
        """Record the timeout this attempt is given."""
        self.timeouts.append(timeout)

    def connect(self, address: object) -> None:
        """Raise the scripted error, if there is one."""
        if self.error is not None:
            raise self.error

    def close(self) -> None:
        """Record that the failed attempt's socket was not left open."""
        self.closed = True


def test_each_connect_attempt_is_given_what_is_left(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not the whole timeout per address, as `socket.create_connection` does.

    Two addresses, the first refusing: the second is given what the first
    left, and the socket it connects is given what is left after that, for
    the TLS handshake that may follow.
    """
    info = (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 8332))
    monkeypatch.setattr(transport_module, "_resolve", lambda *args: [info, info])
    monkeypatch.setattr(transport_module, "socket", _AttemptSocket)
    monkeypatch.setattr(_AttemptSocket, "attempts", [])
    monkeypatch.setattr(_AttemptSocket, "errors", [ConnectionRefusedError(), None])
    monkeypatch.setattr(transport_module, "monotonic", _increasing_clock())

    connected = transport_module._connect("node", 8332, 10.0)

    first, second = _AttemptSocket.attempts
    assert first.timeouts == [10.0]
    assert first.closed is True
    assert cast("object", connected) is second
    assert second.timeouts == [9.0, 8.0]
    assert second.closed is False


def test_a_connect_with_no_time_left_is_not_attempted() -> None:
    """The deadline already past, each address raises before connecting."""
    with pytest.raises(TimeoutError, match="timed out"):
        transport_module._connect("127.0.0.1", 8332, 0.0)


def _fake_getaddrinfo(
    look_up: Callable[[], list[tuple[Any, ...]]],
) -> Callable[..., list[tuple[Any, ...]]]:
    """Return a `getaddrinfo` finding no address, then answering `look_up`."""

    def fake(host: str, port: int, **kwargs: int) -> list[tuple[Any, ...]]:
        if kwargs.get("flags", 0) & socket.AI_NUMERICHOST:
            raise socket.gaierror(socket.EAI_NONAME, "not an address")
        return look_up()

    return fake


def test_a_name_is_looked_up_on_a_thread_of_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host name is not an address, so the resolver is asked for it."""
    info = (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.0.2.1", 8332))
    monkeypatch.setattr(
        transport_module, "getaddrinfo", _fake_getaddrinfo(lambda: [info])
    )

    deadline = monotonic() + DEFAULT_TIMEOUT
    assert transport_module._resolve("node", 8332, deadline) == [info]


def test_a_failed_lookup_raises_what_the_resolver_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The thread hands its exception over, and the caller raises it."""

    def no_such_host() -> list[tuple[Any, ...]]:
        raise socket.gaierror(socket.EAI_NONAME, "no such host")

    monkeypatch.setattr(
        transport_module, "getaddrinfo", _fake_getaddrinfo(no_such_host)
    )

    deadline = monotonic() + DEFAULT_TIMEOUT
    with pytest.raises(socket.gaierror, match="no such host"):
        transport_module._resolve("node", 8332, deadline)


def test_a_lookup_is_waited_for_no_longer_than_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resolver that does not answer is left answering, and the call raises.

    The lookup here answers only once the test has its result, so nothing
    but the deadline can end the wait.
    """
    released = Event()

    def unanswered() -> list[tuple[Any, ...]]:
        released.wait()
        return []

    monkeypatch.setattr(transport_module, "getaddrinfo", _fake_getaddrinfo(unanswered))
    try:
        with pytest.raises(TimeoutError, match="timed out resolving node"):
            transport_module._resolve("node", 8332, monotonic() + 0.05)
    finally:
        released.set()


def test_the_session_transport_hands_each_call_its_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Set on the connection before each request, fresh, kept or reconnected.

    A kept connection would otherwise hold the deadline of the call that
    opened it, which passed with that call.
    """
    _patch_reuse_probe(monkeypatch, dead=False)
    kept = FakeConnection(
        FakeResponse(200, b"first"),
        FakeResponse(200, b"second"),
        _RequestFails(BrokenPipeError("gone")),
    )
    reconnected = FakeConnection(FakeResponse(200, b"third"))
    transport = SessionTransport(
        connection_factory=_connection_factory(kept, reconnected)
    )
    now = [100.0]
    monkeypatch.setattr(transport_module, "monotonic", lambda: now[0])
    request = Request(URL, method="GET")

    for reading in (100.0, 200.0, 300.0):
        now[0] = reading
        transport(request, 10.0)

    assert kept.deadlines == [110.0, 210.0, 310.0]
    assert reconnected.deadlines == [310.0]


def _answer_every_request(connection: socket.socket, done: Event) -> None:
    """Answer each request with a 200 whose body is more than one read."""
    pending = b""
    with suppress(OSError):
        while chunk := connection.recv(65536):
            pending += chunk
            while b"\r\n\r\n" in pending:
                _, pending = pending.split(b"\r\n\r\n", 1)
                body = b"z" * (2 * _READ_CHUNK)
                head = f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n\r\n"
                connection.sendall(head.encode() + body)


@pytest.mark.parametrize("session", [False, True])
def test_a_whole_exchange_runs_over_the_deadline_connections(*, session: bool) -> None:
    """The answer arrives through them, and a kept one is used again.

    urllib closes its handle on the socket once the headers are in, and
    the body is read afterwards: the stream the response reads keeps the
    descriptor open, as `http.client`'s own does. The peer accepts one
    connection, so a session's second call is answered only over the
    connection its first one kept.
    """
    with _peer(_answer_every_request) as url, SessionTransport() as kept:
        transport = kept if session else urlopen_transport
        for _ in range(2 if session else 1):
            status, body = http_request(url, timeout=5.0, transport=transport)
            assert (status, len(body)) == (200, 2 * _READ_CHUNK)
