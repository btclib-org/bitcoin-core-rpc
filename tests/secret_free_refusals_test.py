# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Every refusal a secret can reach, fed one and read by `assert_secret_free`.

The rule is section 7 of the btclib-org standard, *A refusal carries no
secret*. `ASSURANCE_CASE.md`'s CWE-209 entry lists the refusals and what is
left out. Each test feeds a secret where the refusal reads it, and
`assert_secret_free` looks for every piece of it, in each spelling, in the
exception and in every exception it chains.

What no test here asks is what a node says: `ASSURANCE_CASE.md`'s CWE-209
entry lists it. `chains_test.py`, `client_test.py` and `transport_test.py`
hold the tests of what a refusal does say.
"""

from __future__ import annotations

import json
import os
import sys
from base64 import b64encode
from collections.abc import Callable
from decimal import Decimal, InvalidOperation, localcontext
from functools import partial
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest
from typing_extensions import override

from bitcoin_core_rpc import (
    BitcoinCoreRestClient,
    BitcoinCoreRpcClient,
    BtcRpcTypeError,
    BtcRpcValueError,
    FetchError,
    RpcChannel,
    RpcError,
    SessionTransport,
    chain_from_network,
    cookie_auth,
    cookie_path_from_chain,
    datadir_subdir_from_chain,
    http_request,
    magic_from_chain,
    magic_from_signet_challenge,
    network_from_chain,
    rpc_port_from_chain,
    urlopen_transport,
)
from tests import Recorded
from tests.secret_free import assert_secret_free

# Fixed values that look random: a run such as all zeros is a piece of a
# clean message, and a literal hex string is what the secret scanners read as
# a leaked key. The key is the one a caller must not see echoed; the user and
# the password are the credentials every client below holds, which no
# refusal may repeat either.
KEY = sha256(b"secret_free_refusals_test: key").hexdigest()
KEY_BYTES = bytes.fromhex(KEY)
KEY_INT = int(KEY, 16)
USER = sha256(b"secret_free_refusals_test: user").hexdigest()[:12]
PASSWORD = sha256(b"secret_free_refusals_test: password").hexdigest()[:24]

URL = "http://127.0.0.1:8332"

#: What a refusal may be: the library's three families, and not whatever the
#: standard library raises from underneath it.
REFUSALS = (BtcRpcTypeError, BtcRpcValueError, FetchError)

#: The key in each spelling a refusal could print, and the credentials.
SECRETS: list[str | bytes] = [KEY, KEY_BYTES, str(KEY_INT), USER, PASSWORD]


class _ShowsKey:
    """An object whose `repr` is the key, as a key object's can be."""

    @override
    def __repr__(self) -> str:
        return KEY


def _type_name(value: object) -> str:
    """Name a case by the type of what it feeds, never by the secret."""
    return type(value).__name__


def _url_id(url: str) -> str:
    """Name a case by the url with the key left out."""
    return url.replace(KEY, "KEY").replace(USER, "USER").replace(str(KEY_INT), "INT")


def refused(
    call: Callable[[], object], secrets: list[str | bytes] | None = None
) -> None:
    """Assert the call is refused, and that no secret is in the refusal."""
    with pytest.raises(REFUSALS) as exc:
        call()
    assert_secret_free(exc.value, SECRETS if secrets is None else secrets)


def client(*answers: tuple[int, bytes] | Exception, **kwargs: Any) -> Any:
    """Return a client holding the user and password above, over a recording."""
    return BitcoinCoreRpcClient(
        URL,
        user=USER,
        password=PASSWORD,
        transport=Recorded(*answers or ((200, b"{}"),)),
        **kwargs,
    )


class _Echoing(Recorded):
    """A recording answering `getblockchaininfo` with the id it was asked."""

    def __init__(self, result: dict[str, str]) -> None:
        super().__init__((200, b""))
        self.result = result

    @override
    def __call__(self, request: Request, timeout: float) -> tuple[int, bytes]:
        """Answer the request with its own id and the result given."""
        super().__call__(request, timeout)
        assert isinstance(request.data, bytes)
        reply = {"id": json.loads(request.data)["id"], "result": self.result}
        return 200, json.dumps(reply).encode()


def echoing(result: dict[str, str]) -> Any:
    """Return a client whose node answers every call with this result."""
    return BitcoinCoreRpcClient(
        URL, user=USER, password=PASSWORD, transport=_Echoing(result)
    )


def rest(*answers: tuple[int, bytes] | Exception) -> BitcoinCoreRestClient:
    """Return a rest client over a recording."""
    return BitcoinCoreRestClient(URL, transport=Recorded(*answers or ((200, b"{}"),)))


def test_the_helper_reads_what_this_package_raises() -> None:
    """The control: a refusal quoting the key fails the tests below."""
    with pytest.raises(AssertionError):
        assert_secret_free(RpcError(f"x: {KEY}", -1), SECRETS)
    with pytest.raises(AssertionError):
        assert_secret_free(BtcRpcValueError(f"x: {KEY_BYTES!r}"), SECRETS)
    assert_secret_free(BtcRpcValueError("x"), SECRETS)
    assert repr(_ShowsKey()) == KEY


# a rejected credential


@pytest.mark.parametrize("field", ["user", "password"])
@pytest.mark.parametrize(
    "fed",
    [KEY_BYTES, bytearray(KEY_BYTES), KEY_INT, [KEY], _ShowsKey()],
    ids=["bytes", "bytearray", "int", "list", "object"],
)
def test_a_credential_that_is_no_string(field: str, fed: Any) -> None:
    """A rejected `user` or `password` is reported by its type."""
    kwargs: dict[str, Any] = {"user": USER, "password": PASSWORD, field: fed}
    refused(lambda: BitcoinCoreRpcClient(URL, **kwargs))


@pytest.mark.parametrize(
    "user",
    [f"{USER}:{KEY}", f"{KEY}:{PASSWORD}", f":{KEY}"],
    ids=["user-colon-key", "key-colon-password", "colon-key"],
)
def test_a_user_with_a_colon_is_not_quoted(user: str) -> None:
    """The likeliest content of such a user is `user:password`."""
    refused(lambda: BitcoinCoreRpcClient(URL, user=user, password=KEY))


def test_a_credential_given_by_halves_is_not_quoted() -> None:
    """A lone `user` or `password` is a key passed to the wrong argument."""
    refused(lambda: BitcoinCoreRpcClient(URL, user=KEY))
    refused(lambda: BitcoinCoreRpcClient(URL, password=KEY))
    refused(lambda: BitcoinCoreRpcClient.from_chain("main", password=KEY))


def test_credentials_and_a_cookie_path_together_are_not_quoted(tmp_path: Path) -> None:
    """Both are refused, whichever the key was meant for."""
    cookie = tmp_path / ".cookie"
    refused(
        lambda: BitcoinCoreRpcClient(URL, user=USER, password=KEY, cookie_path=cookie)
    )
    refused(lambda: BitcoinCoreRpcClient(URL))


@pytest.mark.parametrize("fed", [KEY_BYTES, KEY_INT, _ShowsKey()], ids=_type_name)
def test_a_cookie_path_that_is_no_path_is_not_quoted(fed: Any) -> None:
    """A path is `str` or `PathLike`; a key may be passed in its place."""
    refused(lambda: BitcoinCoreRpcClient(URL, cookie_path=fed))


@pytest.mark.parametrize("fed", [KEY, KEY_BYTES, _ShowsKey()], ids=_type_name)
def test_a_transport_that_is_not_callable_is_not_quoted(fed: Any) -> None:
    """The transport is a callable; a key may be passed in its place."""
    refused(lambda: BitcoinCoreRpcClient(URL, user=USER, password=KEY, transport=fed))
    refused(lambda: BitcoinCoreRestClient(URL, transport=fed))


def test_a_credential_utf_8_cannot_encode_is_not_chained() -> None:
    """A `UnicodeEncodeError` holds the whole `user:password`."""
    for user, password in (("\ud800" + KEY, PASSWORD), (USER, "\ud800" + KEY)):
        endpoint = client()
        endpoint.user = user
        endpoint._password = password
        refused(endpoint.auth_header)
        refused(partial(endpoint.call, "getblockcount"))
        refused(partial(endpoint.call_raw, "getblockcount"))
        refused(partial(endpoint.call_batch, [("getblockcount", None)]))


def test_a_client_repr_holds_no_credential() -> None:
    """Nothing renders the password: client, wallet client or channel."""
    endpoint = BitcoinCoreRpcClient(URL, user=USER, password=KEY)
    for shown in (endpoint, endpoint.for_wallet("hot"), RpcChannel(endpoint)):
        assert KEY not in repr(shown)
        assert KEY not in str(shown)


# a refused url


def _urls(login: str) -> list[str]:
    return [
        f"http:{login}@h:1",
        f"http:/{login}@h",
        f"http:///{login}@h",
        f"http:\\\\{login}@h",
        f"{login}@h:1",
        f"http://{login}@h:1",
        f"http://h/?x={login}@",
        f"http://h/#{login}@",
        f"http://[{login}@h/",
        f"http://h:{KEY}",
        f"http://h:{KEY_INT}",
        f"ftp://h/{KEY}",
        f"http://h/a b/{login}@",
        f"http://h/é/{login}@",
        f"http://{KEY}ü.example/",
        f"http://\ud800{KEY}/",
        f"http:{KEY}",
        KEY,
    ]


@pytest.mark.parametrize("url", _urls(f"{USER}:{KEY}"), ids=_url_id)
def test_a_refused_url_is_not_quoted(url: str) -> None:
    """A url with a login, or a typo that parses as one, is not repeated."""
    refused(lambda: BitcoinCoreRpcClient(url, user=USER, password=KEY))
    refused(lambda: BitcoinCoreRpcClient(url, cookie_path="c"))
    refused(lambda: BitcoinCoreRestClient(url))
    refused(lambda: http_request(url))


@pytest.mark.parametrize(
    "url", [f"http://{USER}:{KEY}@h/", f"http://h:{KEY}"], ids=["login", "port"]
)
def test_a_request_with_a_refused_url_is_not_quoted(url: str) -> None:
    """The transports are public: a caller's `Request` reaches them."""
    request = Request(url)  # noqa: S310
    refused(lambda: urlopen_transport(request, 1))
    refused(lambda: SessionTransport()(request, 1))


# a refused rpc parameter

_Call = Callable[[Any], object]

_SURFACES: list[tuple[str, _Call]] = [
    ("call", lambda p: client().call("walletpassphrase", p)),
    ("call_raw", lambda p: client().call_raw("walletpassphrase", p)),
    ("call_batch", lambda p: client().call_batch([("walletpassphrase", p)])),
    ("call_batch_later", lambda p: client().call_batch([("a", None), ("b", p)])),
]


def _cycle() -> list[Any]:
    cyclic: list[Any] = []
    cyclic.append(cyclic)
    return cyclic


def _deep() -> list[Any]:
    deep: list[Any] = [1]
    for _ in range(200):
        deep = [deep]
    return deep


_PARAMS = [
    pytest.param(KEY_BYTES, id="bytes"),
    pytest.param(bytearray(KEY_BYTES), id="bytearray"),
    pytest.param([[KEY_BYTES]], id="nested-bytes"),
    pytest.param(_ShowsKey(), id="object"),
    pytest.param([1, [2, _ShowsKey()]], id="nested-object"),
    pytest.param({KEY_BYTES: 1}, id="bytes-key"),
    pytest.param({_ShowsKey(): 1}, id="object-key"),
    pytest.param({KEY_INT: 1}, id="int-key"),
    pytest.param({KEY: _ShowsKey()}, id="long-name"),
    pytest.param({"a": {KEY: [_ShowsKey()]}}, id="nested-long-name"),
    pytest.param({USER + KEY: {KEY[::-1]: b"x"}}, id="two-long-names"),
    pytest.param({KEY: _cycle()}, id="cycle-under-a-name"),
    pytest.param({KEY: _deep()}, id="deep-under-a-name"),
    pytest.param([float("nan"), KEY_BYTES], id="after-a-non-number"),
    pytest.param(KEY, id="str-params"),
    pytest.param(KEY_BYTES.hex().encode(), id="bytes-params"),
    pytest.param(KEY_INT, id="int-params"),
]


@pytest.mark.parametrize("params", _PARAMS)
@pytest.mark.parametrize(("surface", "call"), _SURFACES, ids=[s for s, _ in _SURFACES])
def test_a_refused_parameter_is_not_quoted(
    surface: str, call: _Call, params: Any
) -> None:
    """A refusal names the type of a value and where it is, never the value."""
    del surface
    refused(lambda: call(params))


@pytest.mark.skipif(
    sys.get_int_max_str_digits() == 0, reason="no digit limit to refuse a number at"
)
def test_a_number_the_encoder_cannot_write_is_not_quoted() -> None:
    """The refusal chains the encoder's error, which names the digit limit."""
    big = KEY_INT * 10 ** sys.get_int_max_str_digits()
    refused(lambda: client().call("send", [big]))
    refused(lambda: client().call_raw("send", {"a": [big]}))
    refused(lambda: client().call_batch([("send", [big])]))


@pytest.mark.skipif(
    sys.get_int_max_str_digits() == 0, reason="no digit limit to refuse a number at"
)
def test_a_decimal_exponent_over_the_digit_limit_is_not_quoted() -> None:
    """An exponent in range, and past the limit, can carry digits of a key."""
    exponent = Decimal("1E" + str(KEY_INT)[:18])
    refused(lambda: client().call("send", [exponent]))
    refused(lambda: client().call_raw("send", {"a": exponent}))
    refused(lambda: client().call_batch([("send", [exponent])]))


def test_an_rpc_channel_mixing_its_arguments_is_not_quoted() -> None:
    """Positional and named arguments together are refused by shape."""
    refused(lambda: RpcChannel(client()).walletpassphrase(KEY, passphrase=KEY))
    refused(lambda: RpcChannel(client()).walletpassphrase(KEY_BYTES))


@pytest.mark.parametrize(
    "fed", [KEY_BYTES, KEY_INT, _ShowsKey(), [KEY]], ids=_type_name
)
def test_a_method_that_is_no_string_is_not_quoted(fed: Any) -> None:
    """The method is a string; what is passed instead may be a key."""
    refused(lambda: client().call(fed))
    refused(lambda: client().call_raw(fed))
    refused(lambda: client().call_batch([(fed, None)]))
    refused(lambda: client().call_raw("getblockcount", jsonrpc=fed))


@pytest.mark.parametrize(
    "fed", [KEY, KEY_BYTES, KEY_INT, _ShowsKey(), [KEY]], ids=_type_name
)
def test_a_batch_that_is_no_batch_is_not_quoted(fed: Any) -> None:
    """The calls are pairs; any other shape is refused by type."""
    refused(lambda: client().call_batch(fed))
    refused(lambda: client().call_batch([fed]))
    refused(lambda: client().call_batch([(fed, fed, fed)]))
    refused(lambda: client().call_batch([("getblockcount", fed)]))


@pytest.mark.parametrize("fed", [KEY, KEY_BYTES, _ShowsKey()], ids=_type_name)
def test_a_timeout_or_limit_that_is_wrong_is_not_quoted(fed: Any) -> None:
    """A key passed as a timeout or a body limit is refused by its type."""
    refused(lambda: client(timeout=fed))
    refused(lambda: client().call("getblockcount", request_timeout=fed))
    refused(lambda: client().call("getblockcount", max_body_size=fed))
    refused(lambda: client().call_raw("getblockcount", max_body_size=fed))
    refused(lambda: client().call_batch([("a", None)], max_body_size=fed))
    refused(lambda: rest().get_bin("/x", max_body_size=fed))
    refused(lambda: rest().get_json("/x", request_timeout=fed))
    refused(lambda: http_request(URL, max_body_size=fed))
    refused(lambda: http_request(URL, timeout=fed))
    refused(lambda: BitcoinCoreRestClient(URL, timeout=fed))


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": KEY + "\n"},
        {"Authorization": KEY + "Ā"},
        {"Authorization": KEY + "\0"},
        {"Authorization": KEY_INT},
        {"Authorization": KEY_BYTES},
        {KEY + " ": "x"},
        {KEY_BYTES: KEY},
    ],
    ids=_type_name,
)
def test_a_refused_header_is_not_quoted(headers: Any) -> None:
    """A header value may be a credential, so it is never echoed."""
    refused(lambda: http_request(URL, headers=headers))


# a rest path and a wallet name


@pytest.mark.parametrize(
    "path",
    [KEY, KEY_BYTES, KEY_INT, _ShowsKey(), "/" + KEY + "\u00e9", "/ " + KEY],
    ids=["no-slash", "bytes", "int", "object", "non-ascii", "space"],
)
def test_a_refused_rest_path_is_not_quoted(path: Any) -> None:
    """A path that is no path may be a key passed to the wrong argument."""
    refused(lambda: rest().get_bin(path))
    refused(lambda: rest().get_json(path))


@pytest.mark.parametrize(
    "name",
    [KEY_BYTES, KEY_INT, _ShowsKey(), "\ud800" + KEY],
    ids=["bytes", "int", "object", "surrogate"],
)
def test_a_refused_wallet_name_is_not_quoted(name: Any) -> None:
    """A `UnicodeEncodeError` holds the name, so it is not chained."""
    refused(lambda: client().for_wallet(name))


def test_a_wallet_client_is_not_extended_by_name() -> None:
    """The refusal names the client to call it on, and no wallet."""
    refused(lambda: client().for_wallet(KEY).for_wallet(KEY))


# a chain, a network and a signet challenge


@pytest.mark.parametrize(
    "call",
    [
        rpc_port_from_chain,
        datadir_subdir_from_chain,
        chain_from_network,
        network_from_chain,
        magic_from_chain,
        cookie_path_from_chain,
        BitcoinCoreRpcClient.from_chain,
        BitcoinCoreRestClient.from_chain,
    ],
    ids=lambda call: call.__qualname__,
)
@pytest.mark.parametrize(
    "fed", [KEY, KEY_BYTES, KEY_INT, _ShowsKey(), KEY.upper()], ids=_type_name
)
def test_a_name_that_is_not_one_of_cores_is_not_quoted(
    call: Callable[[Any], object], fed: Any
) -> None:
    """A name over `_MAX_NAME_SHOWN` characters, or a non-string, is hidden."""
    refused(lambda: call(fed))


def test_a_chain_checked_against_a_node_is_not_quoted() -> None:
    """`assert_chain` and `from_chain(verify_chain=True)` name a chain."""
    info = {"chain": "main"}
    refused(lambda: echoing(info).assert_chain(KEY))
    refused(lambda: echoing(info).assert_chain("signet", signet_challenge=KEY))
    refused(lambda: echoing(info).assert_chain(KEY, signet_challenge="00"))
    refused(lambda: echoing(info).assert_chain("main", signet_challenge="00"))
    signet = {"chain": "signet", "signet_challenge": KEY + "zz"}
    refused(lambda: echoing(signet).assert_chain("signet"))
    refused(
        lambda: BitcoinCoreRpcClient.from_chain(
            "main", user=USER, password=PASSWORD, signet_challenge=KEY
        )
    )


@pytest.mark.parametrize(
    "challenge",
    [KEY + "zz", KEY_INT, b"", "", KEY_BYTES * 3000, KEY * 3000, _ShowsKey()],
    ids=lambda c: type(c).__name__,
)
def test_a_signet_challenge_that_is_refused_is_not_quoted(challenge: Any) -> None:
    """A challenge is public, and a key may be passed where it belongs."""
    refused(lambda: magic_from_signet_challenge(challenge))


# an unreadable reply

_UNREADABLE = {
    "not-json": b'{"result": "' + KEY.encode() + b'" x',
    "not-utf-8": b'{"result": "' + KEY.encode() + b'\xff"}',
    "truncated": b'{"result": "' + KEY.encode(),
    "exponent": b'{"result": 1e' + str(KEY_INT).encode() * 2 + b"}",
    "nan": b'{"result": NaN, "x": "' + KEY.encode() + b'"}',
    "infinity": b'{"result": [-Infinity, "' + KEY.encode() + b'"]}',
}

_READERS: list[tuple[str, Callable[[int, bytes], object]]] = [
    ("call", lambda status, body: client((status, body)).call("dumpprivkey")),
    ("call_raw", lambda status, body: client((status, body)).call_raw("dumpprivkey")),
    (
        "call_batch",
        lambda status, body: client((status, body)).call_batch([("dumpprivkey", None)]),
    ),
    ("get_json", lambda status, body: rest((status, body)).get_json("/x.json")),
]


@pytest.mark.parametrize("status", [200, 500, 503])
@pytest.mark.parametrize("name", _UNREADABLE)
@pytest.mark.parametrize(("kind", "read"), _READERS, ids=[k for k, _ in _READERS])
def test_an_unreadable_reply_is_not_quoted(
    kind: str, read: Callable[[int, bytes], object], name: str, status: int
) -> None:
    """A parse or decode error holds the reply, which can be a `dumpprivkey`."""
    del kind
    refused(lambda: read(status, _UNREADABLE[name]))


@pytest.mark.parametrize("status", [200, 500])
def test_a_reply_nested_too_deeply_is_not_quoted(status: int) -> None:
    """The `RecursionError`, chained, names nothing of the reply it parsed."""
    body = b"[" * 200_000 + b'"' + KEY.encode() + b'"' + b"]" * 200_000
    refused(lambda: client((status, body)).call("dumpprivkey"))


@pytest.mark.skipif(
    sys.get_int_max_str_digits() == 0, reason="no digit limit to refuse a number at"
)
@pytest.mark.parametrize("status", [200, 500])
def test_an_integer_over_the_digit_limit_is_not_quoted(status: int) -> None:
    """The parser's `ValueError`, chained, names the limit and no digit."""
    digits = str(KEY_INT) + "0" * sys.get_int_max_str_digits()
    body = b'{"result": ' + digits.encode() + b"}"
    refused(lambda: client((status, body)).call("dumpprivkey"))
    refused(lambda: client((status, body)).call_raw("dumpprivkey"))


def test_a_number_the_context_does_not_trap_is_not_quoted() -> None:
    """With `InvalidOperation` untrapped, a huge exponent parses as a NaN."""
    body = b'{"result": 1e' + str(KEY_INT).encode() + b"}"
    with localcontext() as context:
        context.traps[InvalidOperation] = False
        refused(lambda: client((200, body)).call("dumpprivkey"))
        refused(lambda: client((200, body)).call_raw("dumpprivkey"))


@pytest.mark.skipif(
    sys.get_int_max_str_digits() == 0, reason="no digit limit to refuse a number at"
)
@pytest.mark.parametrize("status", [200, 500])
def test_an_exponent_over_the_digit_limit_is_not_quoted(status: int) -> None:
    """An exponent in range, and past the limit, can carry digits of a key."""
    body = b'{"result": 1e' + str(KEY_INT)[:18].encode() + b"}"
    refused(lambda: client((status, body)).call("dumpprivkey"))
    refused(lambda: client((status, body)).call_raw("dumpprivkey"))


@pytest.mark.parametrize("status", [200, 404, 503])
def test_a_rest_reply_that_is_refused_is_not_quoted(status: int) -> None:
    """`get_bin` refuses a status; `get_json` also a body that is no json."""
    refused(lambda: rest((status, KEY_BYTES)).get_bin("/x.bin", max_body_size=3))
    if status != 200:
        refused(lambda: rest((status, KEY_BYTES)).get_bin("/x.bin"))
        refused(lambda: rest((status, KEY.encode())).get_json("/x.json"))


_SHAPES = {
    "array": b'["' + KEY.encode() + b'"]',
    "string": b'"' + KEY.encode() + b'"',
    "number": KEY_INT.to_bytes(32, "big").hex().encode(),
    "two-point-oh-with-both": b'{"jsonrpc": "2.0", "result": "%b", "error": 1}',
    "neither": b'{"jsonrpc": "2.0", "x": "%b"}',
    "legacy-neither": b'{"x": "%b"}',
    "another-id": b'{"id": "other", "result": "%b"}',
    "another-id-2.0": b'{"jsonrpc": "2.0", "id": "other", "result": "%b"}',
    "no-id": b'{"jsonrpc": "2.0", "result": "%b"}',
    "batch-reply-object": b'{"result": "%b"}',
}


@pytest.mark.parametrize("name", _SHAPES)
def test_a_reply_of_the_wrong_shape_is_not_quoted(name: str) -> None:
    """A reply that answers nothing asked is refused by what it lacks."""
    body = _SHAPES[name]
    body = body.replace(b"%b", KEY.encode()) if b"%b" in body else body
    refused(lambda: client((200, body)).call("dumpprivkey"))
    refused(lambda: client((200, body)).call_batch([("dumpprivkey", None)]))


def test_a_batch_reply_that_answers_nothing_asked_is_not_quoted() -> None:
    """The members of the reply array are refused by position and type."""
    key = KEY.encode()
    bodies = [
        b"[]",
        b'["' + key + b'"]',
        b'[{"id": "other", "result": "' + key + b'"}]',
        b'[{"id": "other", "result": "' + key + b'"}, ' + b"1]",
        b'[{"result": "' + key + b'"}, {"result": "' + key + b'"}]',
    ]
    for body in bodies:
        batch = client((200, body)).call_batch
        refused(partial(batch, [("a", None), ("b", None)]))


def test_a_reply_over_the_limit_is_not_quoted() -> None:
    """The limit and the size are shown, and no octet of the body."""
    body = KEY.encode() * 4
    refused(lambda: client((200, body)).call("dumpprivkey", max_body_size=8))
    refused(lambda: client((200, body)).call_raw("dumpprivkey", max_body_size=8))
    refused(lambda: http_request(URL, transport=Recorded((200, body)), max_body_size=8))


# an unreadable cookie file


def _cookie(directory: Path, content: bytes) -> Path:
    path = directory / ".cookie"
    path.write_bytes(content)
    return path


_COOKIES = {
    "non-ascii": b"__cookie__:" + KEY.encode() + b"\xff",
    "several-lines": b"__cookie__:" + KEY.encode() + b"\nsecond:line",
    "no-colon": KEY.encode(),
    "no-colon-padded": b"\n  " + KEY.encode() + b"  \n",
    "oversized": b"__cookie__:" + KEY.encode() * 200,
    "oversized-binary": KEY_BYTES * 400,
}


@pytest.mark.parametrize("name", _COOKIES)
def test_an_unreadable_cookie_file_is_not_quoted(name: str, tmp_path: Path) -> None:
    """The refusal names the file and the defect, not its content."""
    cookie = _cookie(tmp_path, _COOKIES[name])
    refused(lambda: cookie_auth(cookie))
    refused(lambda: BitcoinCoreRpcClient(URL, cookie_path=cookie).auth_header())
    refused(lambda: BitcoinCoreRpcClient(URL, cookie_path=cookie).call("getblockcount"))
    refused(lambda: BitcoinCoreRpcClient(URL, cookie_path=cookie).call_raw("x"))
    refused(
        lambda: BitcoinCoreRpcClient(URL, cookie_path=cookie).call_batch([("x", None)])
    )
    refused(lambda: BitcoinCoreRpcClient(URL, cookie_path=cookie).assert_chain("main"))


def test_a_cookie_path_that_is_not_a_file_is_not_quoted(tmp_path: Path) -> None:
    """A directory and an absent file are named by their path alone."""
    refused(lambda: cookie_auth(tmp_path))
    refused(lambda: cookie_auth(tmp_path / "absent"))
    _cookie(tmp_path, KEY.encode())
    refused(lambda: cookie_auth(tmp_path / ".cookie" / "below-a-file"))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no FIFOs on this platform")
def test_a_fifo_for_a_cookie_is_not_quoted(tmp_path: Path) -> None:
    """A file that is not regular is refused before it is read."""
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    refused(lambda: cookie_auth(fifo))


def test_a_cookie_path_with_a_nul_is_a_fetch_error() -> None:
    """`os.open` raises a bare `ValueError` for it; the path may be a key."""
    refused(lambda: cookie_auth(Path("a\0" + KEY)))
    refused(lambda: BitcoinCoreRpcClient(URL, cookie_path="\0" + KEY).auth_header())


@pytest.mark.skipif(sys.platform == "win32", reason="a lone surrogate names a file")
def test_a_cookie_path_utf_8_cannot_encode_is_not_chained(tmp_path: Path) -> None:
    """A `UnicodeEncodeError` holds the path, which may be a key."""
    refused(lambda: cookie_auth(tmp_path / ("\ud800" + KEY)))
    refused(lambda: BitcoinCoreRpcClient(URL, cookie_path="\ud800" + KEY).auth_header())


@pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="a mode excludes no user on Windows, or from root",
)
def test_a_cookie_file_nobody_may_read_is_not_quoted(tmp_path: Path) -> None:
    """The refusal chains the `OSError`, which names the path only."""
    cookie = _cookie(tmp_path, b"__cookie__:" + KEY.encode())
    cookie.chmod(0)
    refused(lambda: cookie_auth(cookie))


def test_the_header_is_not_in_a_refusal() -> None:
    """A refusal holds neither the credential nor its header."""
    token = b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    assert client().auth_header() == f"Basic {token}"
    refused(lambda: client().call("getblockcount", [KEY_BYTES]), [token, *SECRETS])
    refused(lambda: client((200, b"x")).call("getblockcount"), [token, *SECRETS])


# a refusal's path


@pytest.mark.parametrize("size", [1, 16])
def test_a_name_of_at_most_sixteen_characters_is_in_the_path(size: int) -> None:
    """A name is quoted only where it is short enough to be a name."""
    name = KEY[:size]
    with pytest.raises(BtcRpcTypeError) as exc:
        client().call("send", {name: KEY_BYTES})
    assert f'at params["{name}"]' in str(exc.value)


@pytest.mark.parametrize("size", [17, 18, 64])
def test_a_longer_name_is_not_in_the_path(size: int) -> None:
    """A name that could be a key, or hold one, is not shown at all."""
    with pytest.raises(BtcRpcTypeError) as exc:
        client().call("send", {"a": {KEY[:size]: KEY_BYTES}})
    assert str(exc.value).endswith('a bytes at params["a"][...]')
    refused(lambda: client().call("send", {"a": {KEY[:size]: KEY_BYTES}}))
    refused(lambda: client().call_batch([("send", {KEY[:size]: KEY_BYTES})]))
