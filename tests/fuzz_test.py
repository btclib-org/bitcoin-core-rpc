# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The reply decoders, on input nobody wrote down.

The rest of the suite is recorded replies and the malformed ones somebody
thought of. This file is the converse. It does not assert what a decoder
reads, the rest does that, but that it *fails the way the package says it
fails*, whatever it is handed: a reply is what an endpoint chooses to send,
and a caller who catches `FetchError` to treat an endpoint's answer as a
failure has no reason to expect a `KeyError`, an `IndexError` or an
`ArithmeticError` out of it.

`fuzz/`'s atheris harness asks the same question of these decoders
for an hour a week, and of the clients and the bounded read as well. This
asks it on every run, and exhaustively rather than by sampling: each valid
reply below is cut at every length, and has each octet taken out and each
of a few structural octets put in at every position. Nothing here is
random; `pyproject.toml` says why the `test` group has no `hypothesis`.

The inputs after the mutations are the ones a mutation cannot reach: a
number of more digits than the interpreter converts, an exponent the
decimal module refuses to build, nesting past the recursion limit, and
octets that are not utf-8.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import pytest

from bitcoin_core_rpc import client
from bitcoin_core_rpc.errors import FetchError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# what a decoder of this package is allowed to raise of a reply: the
# exception `http_request` and the readers of a reply promise
CONTRACT = (FetchError,)

# each is called with `(where, status, payload)`; the key is what
# `fuzz/fuzz_reply.py`'s ENTRY_POINTS spells, which is how
# tests/fuzz_corpus_test.py knows the harness fuzzes each of them
DECODERS: dict[str, Callable[[str, int, bytes], Any]] = {
    "bitcoin_core_rpc.client:_parsed_json_body": client._parsed_json_body,
    "bitcoin_core_rpc.client:_reply_object": client._reply_object,
    "bitcoin_core_rpc.client:_batch_reply_array": client._batch_reply_array,
}

# a 200 is an answer; the others are what a node and what a proxy in front
# of it send, 500 being the HTTP status of Core's 1.1 error
_STATUSES = (200, 401, 500)

# one reply of each shape a node sends
_VALID = [
    b'{"jsonrpc":"2.0","result":481824,"id":"btcrpc-0"}',
    b'{"result":481824,"error":null,"id":"btcrpc-0"}',
    (
        b'{"result":null,"error":{"code":-5,"message":"No such transaction",'
        b'"data":null},"id":"btcrpc-0"}'
    ),
    (
        b'[{"jsonrpc":"2.0","result":0.00000001,"id":"btcrpc-0"},'
        b'{"jsonrpc":"2.0","error":{"code":-8,"message":"range"},"id":"btcrpc-1"}]'
    ),
    b'{"chain":"main","blocks":481824,"difficulty":1.5e-3,"flag":true,"x":[]}',
]

# the octets a JSON document is built of -- its structure, the escape, a
# digit, a sign, a point and an exponent -- a NUL, and one that no utf-8
# text holds
_INSERTED = b'"{}[],:\\0-.e\x00\xff'


def _mutants(valid: bytes) -> Iterator[bytes]:
    """Yield `valid` cut at every length, and with an octet removed or added."""
    for i in range(len(valid) + 1):
        yield valid[:i]
    for i in range(len(valid)):
        yield valid[:i] + valid[i + 1 :]
    for i in range(len(valid) + 1):
        for octet in _INSERTED:
            yield valid[:i] + bytes([octet]) + valid[i:]


# what a mutation cannot reach, and what each is for
_HOSTILE = [
    b"",
    b"null",
    b"NaN",
    b"-Infinity",
    b'{"result":Infinity}',
    b"[" * 100_000,
    b'{"a":' * 100_000,
    b'{"result":' + b"9" * 100_000 + b"}",
    b'{"result":1e999999999999999999999999999}',
    b'{"result":1E-999999999999999999999999999}',
    b'{"result":-0.0e0}',
    b'{"error":{"code":1e5,"message":"x"},"id":"a"}',
    b'{"error":{"code":true,"message":"x"},"id":"a"}',
    b'{"error":{"code":-1,"message":["x"]},"id":"a"}',
    b'{"id":[],"result":1}',
    b'[{"id":[]}]',
    b'["a"]',
    b'"\\ud800"',
    b"\xef\xbb\xbf{}",
    b"\xff\xfe{\x00}\x00",
    b'{"result":"\xc3("}',
]


def _read(decoder: Callable[[str, int, bytes], Any], status: int, body: bytes) -> None:
    with contextlib.suppress(*CONTRACT):
        decoder("fuzz", status, body)


@pytest.mark.parametrize("name", DECODERS)
@pytest.mark.parametrize("valid", _VALID, ids=range(len(_VALID)))
def test_a_mutated_reply_is_refused_within_the_contract(
    name: str, valid: bytes
) -> None:
    """A valid reply cut, with an octet removed or one inserted."""
    decoder = DECODERS[name]
    for body in _mutants(valid):
        for status in _STATUSES:
            _read(decoder, status, body)


@pytest.mark.parametrize("name", DECODERS)
def test_a_hostile_reply_is_refused_within_the_contract(name: str) -> None:
    """The inputs the mutations above do not reach, at every status."""
    decoder = DECODERS[name]
    for body in _HOSTILE:
        for status in _STATUSES:
            _read(decoder, status, body)
