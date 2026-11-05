# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for `JsonStream` and `BitcoinCoreRpcClient.call_stream`.

`JsonStream` is read from bytes in memory, in chunks of every size that
matters: one octet at a time, which puts a chunk boundary inside every
token, and all at once. `call_stream` is read over a caller's transport,
over a stand-in for `_post_stream`, and over the default transport
against a loopback peer of the test's own, which is where a reply larger
than `max_body_size` is read.
"""

from __future__ import annotations

import json
import socket
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from decimal import Decimal
from threading import Thread
from typing import Any
from urllib.request import Request

import pytest
from typing_extensions import override

from bitcoin_core_rpc import (
    MAX_ERROR_BODY_SIZE,
    BitcoinCoreRpcClient,
    BtcRpcTypeError,
    BtcRpcValueError,
    FetchError,
    HttpError,
    JsonStream,
    RpcError,
    SessionTransport,
)
from bitcoin_core_rpc import client as client_module
from bitcoin_core_rpc import transport as transport_module
from tests import RPC_PASSWORD, RPC_USER, Recorded

URL = "http://127.0.0.1:8332"


def reader(data: bytes, size: int) -> Callable[[int], bytes]:
    """Return a `read` answering `data` at most `size` octets at a time."""
    position = 0

    def read(n: int) -> bytes:
        nonlocal position
        piece = data[position : position + min(n, size)]
        position += len(piece)
        return piece

    return read


@pytest.fixture(params=[1, 1 << 20], ids=["octet", "whole"])
def chunk(request: pytest.FixtureRequest) -> int:
    """Return the most one read answers."""
    size = request.param
    assert isinstance(size, int)
    return size


def stream(data: bytes | str, size: int) -> JsonStream:
    """Return a stream over `data`, read `size` octets at a time."""
    raw = data.encode() if isinstance(data, str) else data
    return JsonStream(reader(raw, size), where="test")


# --- JsonStream: what it reads ---


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            '  {"a": [1, -2.50, "x\\n\\u00e9"], "b": {}}  ',
            {"a": [1, Decimal("-2.50"), "x\né"], "b": {}},
        ),
        ("true", True),
        ("false", False),
        ("null", None),
        ("0", 0),
        ("-1.5e3", Decimal("-1.5e3")),
        ('"\\"\\\\\\/\\b\\f\\n\\r\\t"', '"\\/\b\f\n\r\t'),
        ("[]", []),
    ],
)
def test_a_value_is_read_as_call_reads_one(
    chunk: int, text: str, expected: object
) -> None:
    """`value` decodes as `json.loads` does under `call`'s number rules."""
    read = stream(text, chunk)
    assert read.value(1000) == expected
    read.end()


def test_a_walk_reads_members_and_items_in_order(chunk: int) -> None:
    """`members` and `items` yield ahead of each value, `skip` consumes one."""
    text = '{"skip": {"deep": [[{}], "s", 1]}, "keep": [1, 2], "e": []}'
    walked = stream(text, chunk)
    seen: list[object] = []
    for name in walked.members():
        if name == "keep":
            seen.extend((index, walked.value(10)) for index in walked.items())
        elif name == "e":
            seen.extend(walked.items())
        else:
            walked.skip()
    walked.end()
    assert seen == [(0, 1), (1, 2)]


def test_an_empty_object_has_no_members(chunk: int) -> None:
    """`members` of `{}` yields nothing, and consumes the object."""
    walked = stream("{ }", chunk)
    assert list(walked.members()) == []
    walked.end()


def names_of(walked: JsonStream) -> list[str | None]:
    """Return the member names of an object, each value skipped."""
    names = []
    for name in walked.members():
        names.append(name)
        walked.skip()
    return names


def test_a_long_member_name_is_answered_as_none(chunk: int) -> None:
    """A name past the bound is consumed, and nobody can ask for it."""
    text = '{"' + "n" * 100 + '": 1, "short": 2}'
    assert names_of(stream(text, chunk)) == [None, "short"]


def test_a_member_name_given_twice_is_yielded_twice(chunk: int) -> None:
    """The walk decides what a repeated name means."""
    assert names_of(stream('{"a": 1, "a": 2}', chunk)) == ["a", "a"]


def test_peek_names_the_next_value_without_consuming_it(chunk: int) -> None:
    """`peek` answers the first character of the value, which stays unread."""
    peeked = stream(' [ "x" ]', chunk)
    assert peeked.peek() == "["
    assert peeked.value(10) == ["x"]


def test_the_end_can_be_asked_twice() -> None:
    """A stream already at its end reads nothing more."""
    ended = stream("1", 1)
    ended.skip()
    ended.end()
    ended.end()


def test_the_readme_example_reads_a_block() -> None:
    """The walk README.md shows reads the ids of a block's transactions."""

    def tx_ids(walked: JsonStream) -> list[Any]:
        ids: list[Any] = []
        for name in walked.members():
            if name != "tx":
                walked.skip()
                continue
            ids.extend(walked.value(100) for _ in walked.items())
        return ids

    block = {"hash": "00" * 32, "tx": ["11" * 32, "22" * 32], "height": 1}
    assert tx_ids(stream(json.dumps(block), 7)) == ["11" * 32, "22" * 32]


# --- JsonStream: what it refuses ---


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        ("", "cut short"),
        ("[1,", "cut short"),
        ('"abc', "cut short"),
        ('"a\\', "cut short"),
        ('"\\u12', "cut short"),
        ('"a\x01"', "a control character in a string"),
        ('"\\x"', "an invalid escape"),
        ('"\\u12g4"', "an invalid \\\\u escape"),
        ("x", "no json value"),
        ("NaN", "no json value"),
        ("[1 2]", "not ','"),
        ("[1}", "not ','"),
        ('{"a" 1}', "not ':'"),
        ("1" * 1025, "a number longer than 1024 octets"),
        ("[" * 65 + "]" * 65, "nesting deeper than 64"),
        ("1 2", "more than one json value"),
        (b'"\xff"', "not utf-8"),
        (b'"\xc3', "not utf-8"),
    ],
)
def test_a_document_that_is_not_json_is_refused(
    chunk: int, text: str | bytes, refusal: str
) -> None:
    """Each refusal is a `FetchError` starting with `where`, chaining none."""
    refused = stream(text, chunk)
    with pytest.raises(FetchError, match=f"^test: .*{refusal}") as caught:
        refused.skip()
        refused.end()
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def skip_each_member(walked: JsonStream) -> None:
    """Skip every member of an object."""
    for _ in walked.members():
        walked.skip()


def skip_each_item(walked: JsonStream) -> None:
    """Skip every element of an array."""
    for _ in walked.items():
        walked.skip()


def test_skipping_each_member_or_item_consumes_the_document(chunk: int) -> None:
    """The two helpers below, on a document they walk to its end."""
    members = stream('{"a": [1], "b": 2}', chunk)
    skip_each_member(members)
    members.end()
    items = stream("[1, {}]", chunk)
    skip_each_item(items)
    items.end()


@pytest.mark.parametrize(
    ("walk", "text"),
    [
        (lambda walked: list(walked.members()), "[]"),
        (lambda walked: list(walked.items()), "{}"),
        (skip_each_member, '{"a": 1 "b": 2}'),
        (skip_each_item, "[1 2]"),
        (lambda walked: list(walked.members()), '{"a": 1}'),
    ],
    ids=["members-of-array", "items-of-object", "members", "items", "unconsumed"],
)
def test_a_walk_out_of_place_is_refused(
    walk: Callable[[JsonStream], object], text: str
) -> None:
    """A step that does not match the document is refused, not guessed at."""
    with pytest.raises(FetchError, match="^test: not "):
        walk(stream(text, 1))


def test_a_value_past_its_limit_is_refused(chunk: int) -> None:
    """The limit counts the value as it arrives, quotes included."""
    assert stream('"abc"', chunk).value(5) == "abc"
    with pytest.raises(FetchError, match="longer than the 4 octets asked for"):
        stream('"abc"', chunk).value(4)


def test_a_limit_that_is_no_size_is_refused() -> None:
    """A limit is a non-negative integer, `True` not being one."""
    with pytest.raises(BtcRpcTypeError, match="non-integer json value limit"):
        stream("1", 1).value(True)
    with pytest.raises(BtcRpcValueError, match="negative json value limit"):
        stream("1", 1).value(-1)


def test_a_number_json_will_not_decode_is_refused() -> None:
    """An integer past the digit limit, an exponent past the decimal one.

    The second is the decimal module's refusal on CPython, and on PyPy,
    whose decimal builds the number, `_json_number`'s.
    """
    digits = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(640)
    try:
        with pytest.raises(FetchError, match="^test: a reply the json parser refused"):
            stream("1" * 700, 1 << 20).value(1000)
    finally:
        sys.set_int_max_str_digits(digits)
    with pytest.raises(FetchError, match="parser refused|exponent is beyond"):
        stream("1e999999999999999999999999999", 1 << 20).value(100)


# --- call_stream over a caller's transport ---


class Echoing(Recorded):
    """A Recorded writing each request's id where its answer says `ID`."""

    @override
    def __call__(self, request: Request, timeout: float) -> tuple[int, bytes]:
        """Answer the next scripted reply, with this request's id in it."""
        status, body = super().__call__(request, timeout)
        data = request.data
        assert isinstance(data, bytes)
        request_id = json.dumps(json.loads(data)["id"]).encode()
        return status, body.replace(b"ID", request_id)


def answering(status: int, body: bytes) -> BitcoinCoreRpcClient:
    """Return a client whose transport answers `body` under `status`."""
    transport = Echoing((status, body))
    return BitcoinCoreRpcClient(
        URL, user=RPC_USER, password=RPC_PASSWORD, transport=transport
    )


def recording(endpoint: BitcoinCoreRpcClient) -> Recorded:
    """Return the recording a client was built with."""
    transport = endpoint.transport
    assert isinstance(transport, Recorded)
    return transport


def keep(limit: int) -> Callable[[JsonStream], Any]:
    """Return a walk keeping the whole result under `limit` octets."""
    return lambda walked: walked.value(limit)


def walk_never_called(  # pragma: no cover -- never called is the point of the test
    walked: JsonStream,
) -> object:
    """Fail: the walk of a reply whose `result` must not be read."""
    raise AssertionError(walked)


V2 = b'{"jsonrpc": "2.0", "result": [1, 2.5], "id": ID}'
LEGACY = b'{"result": [1, 2.5], "error": null, "id": ID}'


@pytest.mark.parametrize("body", [V2, LEGACY], ids=["2.0", "legacy"])
def test_the_result_is_what_the_walk_returns(body: bytes) -> None:
    """Both dialects, the request being the one `call` sends."""
    endpoint = answering(200, body)
    result = endpoint.call_stream("getblock", ["ab", 2], keep(100))
    assert result == [1, Decimal("2.5")]
    sent = json.loads(recording(endpoint).body)
    assert sent["method"] == "getblock"
    assert sent["params"] == ["ab", 2]
    assert sent["jsonrpc"] == "2.0"
    authorization = recording(endpoint).request.get_header("Authorization")
    assert authorization == endpoint.auth_header()


def test_a_member_beside_the_envelope_is_skipped() -> None:
    """A member the reply does not need is read and dropped."""
    body = b'{"x": {"y": [1]}, "result": 7, "error": null, "id": ID}'
    assert answering(200, body).call_stream("m", None, keep(10)) == 7


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (500, b'{"result": null, "error": {"code": -5, "message": "no"}, "id": ID}'),
        (200, b'{"jsonrpc": "2.0", "error": {"code": -5, "message": "no"}, "id": ID}'),
    ],
    ids=["legacy-500", "2.0"],
)
def test_an_rpc_error_is_raised_and_no_result_is_walked(
    status: int, body: bytes
) -> None:
    """A legacy error under its 500, and a 2.0 error with no `result`."""
    with pytest.raises(RpcError, match="^m at http://127.0.0.1:8332: no ") as caught:
        answering(status, body).call_stream("m", None, walk_never_called)
    assert caught.value.code == -5


def test_a_legacy_error_under_200_walks_the_null_result() -> None:
    """The `null` arrives before the error, and the error is still raised."""
    walked: list[object] = []
    body = b'{"result": null, "error": {"code": -1, "message": "no"}, "id": ID}'
    endpoint = answering(200, body)
    with pytest.raises(RpcError):
        endpoint.call_stream("m", None, lambda s: walked.append(s.value(4)))
    assert walked == [None]


@pytest.mark.parametrize(
    ("body", "refusal"),
    [
        (b'{"jsonrpc": "2.0", "result": 1, "id": "other"}', "is not the"),
        (b'{"jsonrpc": "1.0", "result": 1, "id": ID}', "json-rpc version"),
        (b'{"jsonrpc": "2.0", "result": 1, "result": 2, "id": ID}', "given twice"),
        (b'{"jsonrpc": "2.0", "result": 1, "id": ID} 1', "more than one json"),
        (b"[1]", "not '{'"),
    ],
    ids=["id", "version", "twice", "trailing", "array"],
)
def test_a_reply_call_would_refuse_is_refused(body: bytes, refusal: str) -> None:
    """The envelope is checked as `call` checks it, after the walk."""
    with pytest.raises(FetchError, match=refusal):
        answering(200, body).call_stream("m", None, keep(10))


def test_a_status_without_a_reply_is_the_status() -> None:
    """A 503 whose body is no reply is an `HttpError`, as for `call`."""
    with pytest.raises(HttpError) as caught:
        answering(503, b"busy").call_stream("m", None, walk_never_called)
    assert caught.value.status == 503


def test_the_body_of_a_failure_is_read_no_further_than_its_bound() -> None:
    """A failure body past `MAX_ERROR_BODY_SIZE` is cut, and is no reply."""
    message = b"x" * MAX_ERROR_BODY_SIZE
    body = b'{"error": {"code": -5, "message": "' + message + b'"}, "id": ID}'
    with pytest.raises(HttpError) as caught:
        answering(500, body).call_stream("m", None, walk_never_called)
    assert caught.value.status == 500


def test_a_body_over_the_limit_from_a_caller_transport_is_refused() -> None:
    """Read whole, the body is held to `max_body_size`, as for `call`."""
    endpoint = answering(200, V2)
    with pytest.raises(FetchError, match="more than the max_body_size of 10"):
        endpoint.call_stream("m", None, keep(100), max_body_size=10)


def test_what_the_walk_raises_is_raised() -> None:
    """The walk's own exception reaches the caller unchanged."""

    def refuse(walked: JsonStream) -> object:
        raise LookupError(walked)

    with pytest.raises(LookupError):
        answering(200, V2).call_stream("m", None, refuse)


def test_the_controls_are_checked_before_anything_is_sent() -> None:
    """A bad limit, timeout or method costs no request."""
    endpoint = answering(200, V2)
    with pytest.raises(BtcRpcTypeError, match="max_body_size"):
        endpoint.call_stream("m", None, keep(10), max_body_size=1.5)  # type: ignore[arg-type]
    with pytest.raises(BtcRpcValueError, match="request_timeout"):
        endpoint.call_stream("m", None, keep(10), request_timeout=0)
    with pytest.raises(BtcRpcTypeError, match="method"):
        endpoint.call_stream(7, None, keep(10))  # type: ignore[arg-type]
    assert recording(endpoint).requests == []


# --- call_stream over a stand-in for `_post_stream` ---


def streamed(
    monkeypatch: pytest.MonkeyPatch, status: int, body: bytes
) -> BitcoinCoreRpcClient:
    """Return a client whose default transport streams `body`, an octet a read.

    `_post_stream` is replaced, so the reply is read as from the socket
    without one, and `ID` in `body` becomes the id of the request.
    """

    @contextmanager
    def post_stream(
        url: str, *, data: bytes, headers: object, timeout: float
    ) -> Iterator[tuple[int, Callable[[int], bytes]]]:
        assert url == URL
        request_id = json.dumps(json.loads(data)["id"]).encode()
        yield status, reader(body.replace(b"ID", request_id), 1)

    monkeypatch.setattr(client_module, "_post_stream", post_stream)
    return BitcoinCoreRpcClient(URL, user=RPC_USER, password=RPC_PASSWORD)


@pytest.mark.parametrize("body", [V2, LEGACY], ids=["2.0", "legacy"])
def test_a_streamed_reply_is_read_an_octet_at_a_time(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    """Every chunk boundary of the envelope is crossed, in both dialects."""
    endpoint = streamed(monkeypatch, 200, body)
    assert endpoint.call_stream("m", None, keep(100)) == [1, Decimal("2.5")]


def test_an_envelope_member_is_kept_under_max_body_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What `call_stream` keeps itself is held to `max_body_size`."""
    body = b'{"jsonrpc": "2.0", "error": "' + b"e" * 100 + b'", "id": ID}'
    endpoint = streamed(monkeypatch, 200, body)
    with pytest.raises(FetchError, match="longer than the 64 octets"):
        endpoint.call_stream("m", None, walk_never_called, max_body_size=64)


def test_a_streamed_failure_is_read_as_call_reads_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A legacy error under its 500, its body streamed."""
    body = b'{"result": null, "error": {"code": -5, "message": "no"}, "id": ID}'
    endpoint = streamed(monkeypatch, 500, body)
    with pytest.raises(RpcError, match="no"):
        endpoint.call_stream("m", None, walk_never_called)


# --- call_stream over the default transport, against a loopback peer ---


def _request_of(connection: socket.socket) -> bytes:
    """Read one request: its headers and the body they announce."""
    data = b""
    while b"\r\n\r\n" not in data:
        data += connection.recv(65536)
    head, _, body = data.partition(b"\r\n\r\n")
    length = next(
        int(line.split(b":")[1])
        for line in head.split(b"\r\n")
        if line.lower().startswith(b"content-length:")
    )
    while len(body) < length:
        body += connection.recv(65536)
    return head + b"\r\n\r\n" + body


@contextmanager
def _peer(
    answer: Callable[[str], bytes], requests: list[bytes] | None = None
) -> Iterator[str]:
    """Yield the url of a loopback peer answering one request, then closing.

    `answer` is given the request's id and returns what to send. A peer
    of the test's own on 127.0.0.1, reaching no network.
    """
    server = socket.create_server(("127.0.0.1", 0))
    seen = [] if requests is None else requests

    def serve() -> None:
        with suppress(OSError):
            connection, _ = server.accept()
            with connection:
                request = _request_of(connection)
                seen.append(request)
                body = request.partition(b"\r\n\r\n")[2]
                connection.sendall(answer(json.loads(body)["id"]))

    peer = Thread(target=serve, daemon=True)
    peer.start()
    try:
        yield f"http://127.0.0.1:{server.getsockname()[1]}/"
    finally:
        server.close()
        peer.join()


def _response(status: str, body: bytes, *, length: int | None = None) -> bytes:
    """Return a response announcing `length` octets, `len(body)` by default."""
    announced = len(body) if length is None else length
    head = f"HTTP/1.1 {status}\r\nContent-Length: {announced}\r\n"
    return head.encode() + b"Connection: close\r\n\r\n" + body


def _reply(request_id: str, *, dialect: str = "2.0") -> bytes:
    """Return a reply of about 2 MB to `request_id`, each element small."""
    reply: dict[str, Any] = {"result": ["ab" * 32] * 30_000, "id": request_id}
    if dialect == "2.0":
        reply["jsonrpc"] = "2.0"
    else:
        reply["error"] = None
    return json.dumps(reply).encode()


def count(walked: JsonStream) -> int:
    """Return how many elements an array has, each skipped."""
    elements = 0
    for _ in walked.items():
        walked.skip()
        elements += 1
    return elements


def node(url: str) -> BitcoinCoreRpcClient:
    """Return a client of `url` over the default transport."""
    return BitcoinCoreRpcClient(url, user=RPC_USER, password=RPC_PASSWORD)


@pytest.mark.parametrize("dialect", ["2.0", "legacy"])
def test_a_reply_larger_than_the_limit_is_read_as_a_stream(dialect: str) -> None:
    """The issue's *Done when*: a reply past `max_body_size`, both dialects."""

    def answer(request_id: str) -> bytes:
        body = _reply(request_id, dialect=dialect)
        assert len(body) > 1_000_000
        return _response("200 OK", body)

    requests: list[bytes] = []
    with _peer(answer, requests) as url:
        result = node(url).call_stream("getblock", ["ab", 3], count, max_body_size=1000)
    assert result == 30_000
    lines = requests[0].partition(b"\r\n\r\n")[0].lower().split(b"\r\n")
    assert lines[0] == b"post / http/1.1"
    assert b"connection: close" in lines
    assert any(line.startswith(b"authorization: basic ") for line in lines)


def test_call_refuses_the_reply_call_stream_reads() -> None:
    """The control: the same reply through `call` is past its limit."""

    def answer(request_id: str) -> bytes:
        return _response("200 OK", _reply(request_id))

    with _peer(answer) as url, pytest.raises(FetchError, match="of 1000"):
        node(url).call("getblock", max_body_size=1000)


def test_a_status_from_the_peer_is_answered_as_call_answers_it() -> None:
    """A legacy error under its 500, over the default transport."""

    def answer(request_id: str) -> bytes:
        error = {"code": -8, "message": "bad"}
        reply = {"result": None, "error": error, "id": request_id}
        return _response("500 Internal Server Error", json.dumps(reply).encode())

    with _peer(answer) as url, pytest.raises(RpcError, match="bad"):
        node(url).call_stream("m", None, walk_never_called)


# a chunked body whose first chunk size is no number, which `http.client`
# refuses as an `IncompleteRead` at the first read of the body
_BAD_CHUNK = b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\nzz\r\n"


def test_a_failure_body_that_cannot_be_read_keeps_its_status() -> None:
    """A 500 whose body fails is its status, as `http_request` has it."""

    def answer(request_id: str) -> bytes:
        return b"HTTP/1.1 500 Internal Server Error\r\n" + _BAD_CHUNK

    with _peer(answer) as url, pytest.raises(HttpError) as caught:
        node(url).call_stream("m", None, walk_never_called)
    assert caught.value.status == 500


def test_a_body_that_cannot_be_read_is_no_answer() -> None:
    """A 200 whose body fails is a `FetchError`, as for `call`."""

    def answer(request_id: str) -> bytes:
        return b"HTTP/1.1 200 OK\r\n" + _BAD_CHUNK

    with _peer(answer) as url, pytest.raises(FetchError, match="^no answer from"):
        node(url).call_stream("m", None, keep(100))


def test_a_body_cut_short_is_refused() -> None:
    """A 200 whose peer closes before its length is a reply cut short."""

    def answer(request_id: str) -> bytes:
        body = b'{"jsonrpc": "2.0", "result": [1'
        return _response("200 OK", body, length=1000)

    with _peer(answer) as url, pytest.raises(FetchError, match="cut short"):
        node(url).call_stream("m", None, keep(100))


class _Clock:
    """A `monotonic` the test moves forward by hand."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        """Return the reading the test set."""
        return self.now


def test_the_time_the_walk_spends_counts_against_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A walk past the deadline is refused at the read that follows."""
    clock = _Clock()
    monkeypatch.setattr(transport_module, "monotonic", clock)

    def answer(request_id: str) -> bytes:
        return _response("200 OK", _reply(request_id))

    def slow(walked: JsonStream) -> int:
        clock.now = 100.0
        return count(walked)

    expired = "still arriving when the timeout expired"
    with _peer(answer) as url, pytest.raises(FetchError, match=expired):
        BitcoinCoreRpcClient(
            url, user=RPC_USER, password=RPC_PASSWORD, timeout=50.0
        ).call_stream("m", None, slow)


def test_a_peer_that_is_not_there_is_no_answer() -> None:
    """A refused connection is a `FetchError`, as for `call`."""
    with socket.create_server(("127.0.0.1", 0)) as closed:
        port = closed.getsockname()[1]
    with pytest.raises(FetchError, match="^no answer from http://127.0.0.1"):
        node(f"http://127.0.0.1:{port}").call_stream("m", None, keep(10))


def test_a_session_transport_reads_the_body_whole() -> None:
    """Over `SessionTransport` the reply is read whole, then walked."""

    def answer(request_id: str) -> bytes:
        reply = {"jsonrpc": "2.0", "result": [1, 2], "id": request_id}
        return _response("200 OK", json.dumps(reply).encode())

    with _peer(answer) as url, SessionTransport() as session:
        endpoint = BitcoinCoreRpcClient(
            url, user=RPC_USER, password=RPC_PASSWORD, transport=session
        )
        assert endpoint.call_stream("m", None, count) == 2
