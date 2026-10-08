# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""What the tests share: a transport that opens no socket.

Not one test here reaches the network. A client a test calls passes
`transport=` pointing at `Recorded` below, which answers from bytes
committed under `_data` and remembers the `urllib.request.Request` it was
handed.

The argument is not on every construction, and the difference is worth
knowing before copying a call site. A test that only reads a property off
a client -- `for_wallet(name).url`, say -- leaves the default
`urlopen_transport` in place and never calls it, so nothing resolves and
nothing is opened. So two things keep this suite hermetic rather than
one: `transport=` wherever a call is made, and no call at all on the
clients built without it. The second is the weaker of the two, because
nothing states it at the call site. Add a `.call()` to one of those
constructions and it reaches 127.0.0.1 -- passing on a machine that runs
bitcoind, failing where none listens, which is a property of the machine
and not of this suite.

That is a claim about the clients and not about the package: sockets are
opened here, by `rpc_smoke_test.py`, which binds and listens on a loopback
port of its own in order to test the port probe `.github/scripts/rpc_smoke.py`
uses, and by `transport_test.py`, which tests the transports and their
reuse probe against loopback peers of its own. Nothing leaves the machine
and nothing needs a node, which is what the sentence above is for.
Section 7's convention is the stricter "the suite opens no socket", and
tests/README.md's declaration is where this suite says it does not keep
that one, and why.

The recorded bodies are what bitcoind sends, byte for byte, newline
included; `_data/README.md` says where each came from.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from urllib.request import Request

from typing_extensions import override

_DATA = Path(__file__).parent / "_data"

# transaction 1 of block 170, the recorded answer throughout: the first
# bitcoin payment between two people, 275 bytes of it
TX_ID = "f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16"
# the tip the recorded answers report, block 481824 -- the first block with
# a segwit transaction in it
TIP_HEIGHT = 481824
TIP_ID = "0000000000000000001c8018d9cb3b742ef25114f27563e3fc4a1902167f9893"


# the rpc credentials every test here passes. Named once rather than
# written at each call, which is what keeps the string out of a
# `password=` argument: the two secret scanners read a literal there as a
# credential, and they are right to -- a real one belongs in neither
RPC_USER = "rpcuser"
RPC_PASSWORD = "rpcpassword"  # ruff: ignore[S105]  # pragma: allowlist secret

# urls written with credentials in a form that does not parse as
# credentials: each refusal must not repeat them, in its message or in the
# traceback the exception would be printed with. The last is no typo: an
# internationalized host, refused like any non-ASCII url
LOGIN = f"{RPC_USER}:{RPC_PASSWORD}"
URLS_WITH_A_LOGIN_TYPO = [
    f"http:{LOGIN}@h:1",
    f"http:/{LOGIN}@h",
    f"http:///{LOGIN}@h",
    f"http:\\\\{LOGIN}@h",
    f"{LOGIN}@h:1",
    f"http://h/?x={LOGIN}@",
    f"http://h/#{LOGIN}@",
    f"http://[{LOGIN}@h/",
    f"http://h:{RPC_PASSWORD}",
    f"http://h/a b/{LOGIN}@",
    f"http://h/\u00e9/{LOGIN}@",
    "http://b\u00fccher.example/",
]


def refusal_text(exc: BaseException) -> str:
    """Everything printing the exception would print, and every `args`."""
    text = "".join(traceback.format_exception(exc))
    link: BaseException | None = exc
    while link is not None:
        text += repr(link.args)
        link = link.__cause__ or link.__context__
    return text


def assert_no_login(exc: BaseException) -> None:
    """Assert the login is in no printed traceback and no chained exception."""
    assert RPC_PASSWORD not in refusal_text(exc)
    assert RPC_USER not in refusal_text(exc)
    assert exc.__cause__ is None
    assert exc.__context__ is None


# a value a caller must not see echoed: a passphrase, a key, a cookie
SECRET = "s3cr3t-passphrase"  # ruff: ignore[S105]  # pragma: allowlist secret


class Shows:
    """An object whose repr is `SECRET`, as a key object's can be."""

    @override
    def __repr__(self) -> str:
        return SECRET


def assert_no_secret(exc: BaseException) -> None:
    """Assert `SECRET` is in no printed traceback and no chained exception."""
    assert SECRET not in refusal_text(exc)


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
