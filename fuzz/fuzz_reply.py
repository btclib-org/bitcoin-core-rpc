# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness fuzzing how the package reads a node's reply.

A reply is what an endpoint sends back, and the endpoint is the caller's to
choose: it can be a host on the internet, or a proxy in front of the node.
`data` is read as the body of a reply, at several HTTP statuses, through the
paths that decode one: the body readers of `client.py`, the two clients end
to end, `assert_chain`, and `transport.py`'s `http_request` and bounded
read. No node runs. The clients are built on a `transport=` that answers
from `data`, which is the lowest seam the package gives a caller, and the
bounded read is handed a response object that serves `data` in chunks.

A body that holds `%ID0%` or `%ID1%` has the id of the first or second
member of the request it answers written in its place, so that a mutated
reply can reach the id check and what follows it.

A crash here on hostile input is a defect in the package, never in this
harness. `FetchError` is what each path answers a reply it cannot read with,
`RpcError` and `HttpError` included, so that family is caught as the
expected outcome, and so is the `BtcRpcValueError` of `assert_chain` for a
node that serves another chain than the one asked for. Any other exception
propagates to atheris as the finding it is. So does an `AssertionError`,
which is how this harness reports that the body a bounded read returned is
not the prefix of `data` the limit allows.

The seed corpus is `fuzz/corpus/fuzz_reply/`.
"""

from __future__ import annotations

import contextlib
import json
import sys
from time import monotonic
from typing import TYPE_CHECKING

import atheris

from bitcoin_core_rpc import client, transport
from bitcoin_core_rpc.errors import BtcRpcValueError, FetchError

if TYPE_CHECKING:
    from collections.abc import Callable
    from urllib.request import Request

# tests/fuzz_corpus_test.py reads this by ast.literal_eval, never by
# importing the module -- atheris above is CI-only and undeclared in
# pyproject.toml, so the test must not execute this file. Each takes
# `(where, status, payload)`
ENTRY_POINTS = (
    "bitcoin_core_rpc.client:_parsed_json_body",
    "bitcoin_core_rpc.client:_reply_object",
    "bitcoin_core_rpc.client:_batch_reply_array",
)

_URL = "http://127.0.0.1:1"
_USER = "fuzz"
_PASSWORD = "fuzz"  # ruff: ignore[S105]  # pragma: allowlist secret

# 200 is the answer, 401 and 404 are statuses a node sends and Core's 1.1
# error is an HTTP 500, 503 is what a proxy in front of it sends
_STATUSES = (200, 401, 404, 500, 503)

# where a status stops being an answer: the body of a failure is cut to
# `MAX_ERROR_BODY_SIZE`, not held to the limit of an answer
_FAILURE = 400

# how much one `read1` of the fake response answers: small enough that the
# bounded read loops, which `_READ_CHUNK` alone would not make it do for a
# body this size
_CHUNK = 7


class _Peer:
    """An `HttpTransport` that answers `status` and `body` to any request.

    The id of each member of the request is written over `%ID<n>%` in the
    body, which is what a node does with the id it was sent.
    """

    def __init__(self) -> None:
        self.status = 200
        self.body = b""

    def __call__(self, request: Request, timeout: float) -> tuple[int, bytes]:
        """Answer the scripted reply, with the request's ids in it."""
        body = self.body
        if isinstance(request.data, bytes):
            sent = json.loads(request.data)
            for index, member in enumerate(sent if isinstance(sent, list) else [sent]):
                body = body.replace(f"%ID{index}%".encode(), member["id"].encode())
        return self.status, body


class _Response:
    """What `_read_bounded` reads: `read1` in small chunks, and `headers`."""

    def __init__(self, body: bytes, announced: str | None) -> None:
        self._body = body
        self.headers = {} if announced is None else {"Content-Length": announced}

    def read1(self, size: int) -> bytes:
        """Return at most `size` and `_CHUNK` octets of what is left."""
        chunk = self._body[: min(size, _CHUNK)]
        self._body = self._body[len(chunk) :]
        return chunk


_PEER = _Peer()
_RPC = client.BitcoinCoreRpcClient(
    _URL, user=_USER, password=_PASSWORD, transport=_PEER
)
_REST = client.BitcoinCoreRestClient(_URL, transport=_PEER)

_CALLS: tuple[Callable[[], object], ...] = (
    lambda: _RPC.call("getblockcount"),
    lambda: _RPC.call_batch([("getblockcount", None), ("getblockhash", [0])]),
    lambda: _RPC.call_raw("getblockcount"),
    lambda: _RPC.call_raw("getblockcount", jsonrpc=None),
    lambda: _REST.get_json("/chaininfo.json"),
    lambda: _REST.get_bin("/chaininfo.json"),
)

# `assert_chain` reads `getblockchaininfo`, and answers a node that serves
# another chain with `BtcRpcValueError`, which is the caller's configuration
# and no reply to refuse
_CHAIN_CHECKS: tuple[Callable[[], object], ...] = (
    lambda: _RPC.assert_chain("main"),
    lambda: _RPC.assert_chain("signet"),
    lambda: _RPC.assert_chain("signet", signet_challenge="51"),
)


def _disagreement_allowed(check: Callable[[], object]) -> None:
    """Run `check`, letting through every `BtcRpcValueError` but a mismatch.

    The harness fixes the arguments, so the one `BtcRpcValueError` that
    `assert_chain` raises of a reply is its disagreement with the node, and
    that message opens "node at". Another one is a refusal of an argument
    the reply cannot have caused, which is a finding.
    """
    try:
        check()
    except BtcRpcValueError as e:
        if not str(e).startswith("node at "):
            raise


def _limits(size: int) -> tuple[int, ...]:
    """Return the limits one below, at and one above `size`, none negative."""
    return tuple(max(size + offset, 0) for offset in (-1, 0, 1))


def _check_http_request(status: int, data: bytes) -> None:
    """Refuse an answer that is not the prefix of `data` its limit allows."""
    for limit in _limits(len(data)):
        try:
            got_status, body = transport.http_request(
                _URL, data=b"[]", max_body_size=limit, transport=_PEER
            )
        except FetchError:
            continue
        if got_status != status:
            msg = f"http_request answered {got_status} for a transport's {status}"
            raise AssertionError(msg)
        if status >= _FAILURE:
            expected = data[: transport.MAX_ERROR_BODY_SIZE]
        elif len(data) <= limit:
            expected = data
        else:
            msg = f"http_request answered {len(data)} octets at limit {limit}"
            raise AssertionError(msg)
        if body != expected:
            msg = f"http_request returned {len(body)} octets at limit {limit}"
            raise AssertionError(msg)


def _check_read_bounded(data: bytes) -> None:
    """Refuse a bounded read that returns too much, or what is not a prefix."""
    first_line = data.split(b"\n", 1)[0].decode("latin-1")
    for limit in _limits(len(data)):
        for announced in (None, first_line):
            for truncate in (False, True):
                with contextlib.suppress(FetchError):
                    body = transport._read_bounded(
                        _Response(data, announced),
                        limit,
                        "fuzz",
                        monotonic() + 3600,
                        truncate=truncate,
                    )
                    if len(body) > limit or not data.startswith(body):
                        msg = f"_read_bounded returned {len(body)} octets at {limit}"
                        raise AssertionError(msg)
                    if not truncate and body != data:
                        msg = "_read_bounded answered less than the body untruncated"
                        raise AssertionError(msg)


def fuzz_target(data: bytes) -> None:
    """Read `data` as a reply, at each status, by the paths that read one.

    What is swallowed and what propagates is the module docstring's.
    """
    _check_read_bounded(data)
    for status in _STATUSES:
        _PEER.status = status
        _PEER.body = data
        for call in _CALLS:
            with contextlib.suppress(FetchError):
                call()
        for check in _CHAIN_CHECKS:
            with contextlib.suppress(FetchError):
                _disagreement_allowed(check)
        _check_http_request(status, data)
        with contextlib.suppress(FetchError):
            client._parsed_json_body("fuzz", status, data)
        with contextlib.suppress(FetchError):
            client._reply_object("fuzz", status, data)
        with contextlib.suppress(FetchError):
            client._batch_reply_array("fuzz", status, data)


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
