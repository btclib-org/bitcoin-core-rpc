#!/usr/bin/env python3

# Copyright (C) The btclib developers
#
# This file is part of bitcoin-core-rpc. It is subject to the license
# terms in the LICENSE file found in the top-level directory of this
# distribution.
#
# No part of bitcoin-core-rpc including this file, may be copied,
# modified, propagated, or distributed except according to the terms contained
# in the LICENSE file.
"""What the tests share: a transport that opens no socket.

Not one test here reaches the network, and none can: every client is built
with `transport=` pointing at `Recorded` below, which answers from bytes
committed under `_data` and remembers the `urllib.request.Request` it was
handed. A test that forgot the argument would fall back to
`urlopen_transport` and try to reach 127.0.0.1, so the absence of a
listening node is not what keeps the suite hermetic -- the argument is, and
it is on every construction.

The recorded bodies are what bitcoind sends, byte for byte, newline
included; `_data/README.md` says where each came from.
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import Request

_DATA = Path(__file__).parent / "_data"

# transaction 1 of block 170, the recorded answer throughout: the first
# bitcoin payment between two people, 275 bytes of it
TX_ID = "f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16"
# the tip the recorded answers report, block 481824 -- the first block with
# a segwit transaction in it
TIP_HEIGHT = 481824
TIP_ID = "0000000000000000001c8018d9cb3b742ef25114f27563e3fc4a1902167f9893"


def recorded_body(name: str) -> bytes:
    """Return a recorded response body, as it arrived."""
    return (_DATA / name).read_bytes()


class Recorded:
    """An HttpTransport answering from a script, remembering the requests.

    Each answer is either a `(status, body)` pair to return or an
    exception to raise, consumed in order; the last one repeats, so a
    test that makes two calls with one answer gets it twice. Everything
    it was asked is kept, which is how the tests check the url, the
    method, the headers and the timeout without a server to observe them
    from.
    """

    def __init__(self, *answers: tuple[int, bytes] | Exception) -> None:
        self.answers = list(answers)
        self.requests: list[Request] = []
        self.timeouts: list[float] = []

    def __call__(self, request: Request, timeout: float) -> tuple[int, bytes]:
        """Record the request and answer with the next scripted response."""
        self.requests.append(request)
        self.timeouts.append(timeout)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    @property
    def request(self) -> Request:
        """The only request made, when a test made exactly one."""
        assert len(self.requests) == 1
        return self.requests[0]

    @property
    def body(self) -> bytes:
        """The body of the only request made."""
        data = self.request.data
        assert isinstance(data, bytes)
        return data
