# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the chain and network vocabulary, and the cookie it derives.

`chains.py` is what this file judges: the port and datadir tables, the
chain and network translation, the magic bytes and the signet derivation,
and `cookie_auth`'s own reading of a cookie file. `client_test.py` judges
`BitcoinCoreRpcClient.from_chain` and `assert_chain`, which call into this
module rather than being part of it.
"""

from __future__ import annotations

import re
import sys
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any, get_args

import pytest
from typing_extensions import override

from bitcoin_core_rpc.chains import (
    _CHAIN_FROM_NETWORK,
    _DATADIR_SUBDIR_FROM_CHAIN,
    _MAGIC_FROM_CHAIN,
    _NETWORK_FROM_CHAIN,
    _RPC_PORT_FROM_CHAIN,
    COOKIE_USER,
    DEFAULT_SIGNET_CHALLENGE,
    Chain,
    Network,
    chain_from_network,
    cookie_auth,
    cookie_path_from_chain,
    datadir_subdir_from_chain,
    default_datadir,
    magic_from_chain,
    magic_from_signet_challenge,
    network_from_chain,
    rpc_port_from_chain,
)
from bitcoin_core_rpc.errors import (
    BtcRpcTypeError,
    BtcRpcValueError,
    CookieNotFoundError,
    FetchError,
)

# the shape bitcoind writes: the fixed user, a colon, and 32 random bytes
# in hex. This one is not random and is the credential of nothing -- the
# point is the parsing, and a real cookie would be a secret in a
# repository
COOKIE_LINE = f"{COOKIE_USER}:" + "ab" * 32


def test_the_cookie_path_is_the_datadir_the_subdir_and_the_filename(
    tmp_path: Path,
) -> None:
    """A node's datadir composes with Core's table into the cookie path.

    The three facts of the path, and the reason the function exists: two
    are published tables and the third is the name Core gives the file.
    `main` keeps it in the datadir itself, the rest a subdirectory down.
    """
    assert cookie_path_from_chain("main", tmp_path) == tmp_path / ".cookie"
    assert cookie_path_from_chain("test", tmp_path) == tmp_path / "testnet3" / ".cookie"
    assert (
        cookie_path_from_chain("regtest", tmp_path) == tmp_path / "regtest" / ".cookie"
    )
    # a datadir as a string, which is how one arrives from a config file
    assert cookie_path_from_chain("signet", str(tmp_path)) == (
        tmp_path / "signet" / ".cookie"
    )


def test_the_cookie_path_defaults_to_the_datadir_of_this_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No datadir given is `default_datadir`, asked now and not at import.

    The same property `from_chain` has, and for the same reason: a module
    imported transitively is imported at a moment the caller did not
    choose, so the environment of the call is the one that counts.

    The platform is pinned to the branch the home is the base of, as it is
    for `from_chain`'s own test in `client_test.py`: on Windows the base
    is `APPDATA`, and moving the home there would move nothing.
    """
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home-after")

    expected = tmp_path / "home-after" / ".bitcoin" / "regtest" / ".cookie"
    assert cookie_path_from_chain("regtest") == expected


def test_the_cookie_path_refuses_a_datadir_it_cannot_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No base for a datadir is a refusal naming `datadir`, not a relative path.

    `from_chain` refuses the same case naming `cookie_path`, which is what
    a caller of *that* passes instead; the remedy is what differs, and it
    is why the constructor resolves the datadir itself rather than leaving
    it to this default.

    The platform is pinned for the same reason as above: the home is the
    base on every row but Windows, where `APPDATA` is, so patching one of
    the two makes the answer None only on the row it is the base of.
    """

    def no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", no_home)
    with pytest.raises(BtcRpcValueError, match="pass datadir"):
        cookie_path_from_chain("main")


def test_the_cookie_path_of_an_unknown_chain_is_no_path(tmp_path: Path) -> None:
    """A chain Core has no directory for is the table's refusal, unchanged.

    `mainnet` is the BIP name of `main` and the mistake this catches;
    `chain_from_network` is the translation.
    """
    with pytest.raises(BtcRpcValueError, match="unknown Core chain"):
        cookie_path_from_chain("mainnet", tmp_path)


def test_the_datadir_is_cores_own_on_each_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    r"""The three directories `GetDefaultDataDir` writes, from one run.

    Core's src/common/args.cpp: ``%APPDATA%\Bitcoin`` on Windows,
    ``~/Library/Application Support/Bitcoin`` on macOS, ``~/.bitcoin`` on
    everything else -- the `#else` branch, which is what a platform absent
    from the table takes here and why one that is not among the three is
    asserted too rather than left to the reader.

    `sys.platform` is patched, which is what lets one row of the matrix
    state all three: `default_datadir` reads it at the call, so the branch
    a run cannot take natively is still a branch this reaches. The paths
    hang off `tmp_path`, absolute on whichever platform is running, since
    a Windows literal is a relative path to a POSIX `Path` and would be
    refused rather than compared.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))

    monkeypatch.setattr(sys, "platform", "win32")
    assert default_datadir() == tmp_path / "AppData" / "Roaming" / "Bitcoin"

    monkeypatch.setattr(sys, "platform", "darwin")
    expected = tmp_path / "Library" / "Application Support" / "Bitcoin"
    assert default_datadir() == expected

    monkeypatch.setattr(sys, "platform", "linux")
    assert default_datadir() == tmp_path / ".bitcoin"

    monkeypatch.setattr(sys, "platform", "freebsd14")
    assert default_datadir() == tmp_path / ".bitcoin"


def test_no_absolute_home_is_no_default_datadir_and_no_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both ways a home is not a datadir answer with None, and neither raises.

    `DEFAULT_DATADIR` is computed at import, so an exception here would fail
    the import itself on a host that was never going to reach a node: a
    container run under an arbitrary uid, where `HOME` is unset and the
    passwd file has no entry to fall back to, is where `Path.home()` raises.
    A `HOME` that holds a relative path is the other way, and it raises
    nothing at all.

    `Path.home` is patched, and not the `os.path.expanduser` under it. Some
    interpreters of the matrix call that function while resolving the home;
    others bound it to a pathlib accessor when the class was created, and
    there patching the module attribute is invisible -- written that way,
    this passed on 3.14 and did not raise at all on 3.10. What
    `default_datadir` reads is `Path.home`, so that is what this arranges.

    The platform is one whose base is the home, `Path.home` being what
    there is to make fail: `APPDATA` is the Windows base and has its own
    test below.
    """

    def no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", no_home)
    assert default_datadir() is None

    monkeypatch.setattr(Path, "home", lambda: Path("relative/home"))
    assert Path.home().is_absolute() is False
    assert default_datadir() is None


def test_no_absolute_appdata_is_no_default_datadir_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r"""The Windows base answers None the two ways the home does, and one more.

    `APPDATA` is an environment variable and can simply be unset, where a
    home directory is resolved from the passwd database when `HOME` is not
    there. Relative is the other way, and the reason is the one that makes
    a relative home None: the path would be read against the working
    directory of the moment, and a `Bitcoin\\.cookie` under whatever
    directory a caller happens to be in is not a credential to present to a
    node.

    The home is made to fail the test if it is consulted, since on this
    platform it is not the base and reading it would mean the table was
    not what answered.
    """
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(Path, "home", lambda: pytest.fail("home consulted"))

    monkeypatch.delenv("APPDATA", raising=False)
    assert default_datadir() is None

    monkeypatch.setenv("APPDATA", "AppData/Roaming")
    assert default_datadir() is None


def test_an_absent_cookie_file_says_which_file_and_that_none_was_written(
    tmp_path: Path,
) -> None:
    """A missing cookie names the file, and says a node writes it.

    Naming it is what tells a caller looking in the wrong place -- a node
    started with `-datadir=` elsewhere, a `cookie_path` carried over from
    another host -- which place was looked in.

    `CookieNotFoundError` and not the FetchError the other four cookie
    failures are: nothing is at the path, so there is no file to go and
    look at, and the node starting is what fixes it. A FetchError all the
    same, so a caller catching that alone still catches this.
    """
    absent = tmp_path / "no-such-datadir" / ".cookie"
    # escaped because `match` is a regex and a path is not: the windows
    # separator is a backslash, so a tmp_path under C:\Users carries an
    # incomplete \U escape and the pattern does not even compile
    expected = re.escape(f"no rpc cookie file {absent}")
    with pytest.raises(CookieNotFoundError, match=expected):
        cookie_auth(absent)
    with pytest.raises(FetchError, match="bitcoind writes one while it runs"):
        cookie_auth(absent)


def test_a_cookie_path_that_cannot_be_opened_is_not_a_missing_one(
    tmp_path: Path,
) -> None:
    """Something at the path that will not open is the unreadable failure.

    A directory is the case every platform has: POSIX refuses the open
    with EISDIR and Windows with EACCES, and both are a file to go and
    look at rather than a node to start -- which is the line
    `CookieNotFoundError` draws.
    """
    expected = re.escape(f"unreadable rpc cookie file {tmp_path}")
    with pytest.raises(FetchError, match=expected) as raised:
        cookie_auth(tmp_path)
    assert not isinstance(raised.value, CookieNotFoundError)


def test_a_cookie_file_without_a_colon_is_not_one(tmp_path: Path) -> None:
    """Refuse a cookie file carrying no colon as malformed."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("nonsense\n")
    with pytest.raises(FetchError, match="no ':' in it"):
        cookie_auth(cookie)


def test_a_cookie_file_of_several_lines_is_not_one(tmp_path: Path) -> None:
    """One line is what bitcoind writes, so more than one is another file."""
    cookie = tmp_path / ".cookie"
    cookie.write_text(f"{COOKIE_LINE}\nand a second line\n")
    with pytest.raises(FetchError, match="several lines"):
        cookie_auth(cookie)


def test_a_cookie_file_that_is_not_ascii_is_not_one(tmp_path: Path) -> None:
    """A binary file at the cookie path is a FetchError, not a decode error.

    The wrong path is the ordinary mistake here, and everything it can
    point at has to arrive through the same contract: naming the file,
    and never rendering what was in it.
    """
    cookie = tmp_path / ".cookie"
    cookie.write_bytes(b"\x80\x81:not ascii")
    with pytest.raises(FetchError, match="non-ascii rpc cookie file"):
        cookie_auth(cookie)


@pytest.mark.parametrize("size", [4096, 4097])
def test_the_cookie_size_boundary_is_4096_bytes(tmp_path: Path, size: int) -> None:
    """The largest permitted cookie is accepted and the next byte is not."""
    line = "u:" + "x" * (size - 2)
    cookie = tmp_path / ".cookie"
    cookie.write_text(line, encoding="ascii")

    if size == 4096:
        assert cookie_auth(cookie) == line
    else:
        with pytest.raises(FetchError, match="oversized rpc cookie file"):
            cookie_auth(cookie)


def test_the_cookie_read_stops_after_the_sentinel_octet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checking the bound reads 4096 bytes and only one byte beyond it."""

    class MeasuredCookie(BytesIO):
        def __init__(self) -> None:
            super().__init__(COOKIE_LINE.encode("ascii"))
            self.reads: list[int | None] = []

        @override
        def read(self, size: int | None = -1, /) -> bytes:
            self.reads.append(size)
            return super().read(size)

    measured = MeasuredCookie()

    def open_cookie(path: Path, mode: str) -> MeasuredCookie:
        assert path == Path("measured.cookie")
        assert mode == "rb"
        return measured

    monkeypatch.setattr(Path, "open", open_cookie)
    assert cookie_auth(Path("measured.cookie")) == COOKIE_LINE
    assert measured.reads == [4097]


def test_an_enormous_cookie_file_is_refused_rather_than_held(
    tmp_path: Path,
) -> None:
    """The read is bounded, so a wrong path costs no memory.

    A cookie is seventy octets; anything three orders of magnitude larger
    is another file, and finding that out should not mean holding it.
    """
    cookie = tmp_path / ".cookie"
    cookie.write_text(f"{COOKIE_LINE}\n" + "x" * 8192)
    with pytest.raises(FetchError, match="oversized rpc cookie file"):
        cookie_auth(cookie)


def test_every_chain_is_in_every_table_that_takes_one() -> None:
    """The five chains are written down four times, and must agree.

    A chain Core adds is a port, a datadir subdirectory, a network name
    and a `Literal` -- four edits, of which only the two `Literal`s fail
    anything when one is forgotten, and they fail a type check rather than
    this suite. A port with no subdirectory beside it derives a cookie
    path under a directory that is not the node's.
    """
    chains = set(get_args(Chain))
    assert chains == set(_RPC_PORT_FROM_CHAIN)
    assert chains == set(_DATADIR_SUBDIR_FROM_CHAIN)
    assert chains == set(_NETWORK_FROM_CHAIN)
    assert set(get_args(Network)) == set(_CHAIN_FROM_NETWORK)
    # and the pairing is a bijection, not merely two tables of one size
    assert set(_NETWORK_FROM_CHAIN.values()) == set(_CHAIN_FROM_NETWORK)


def test_the_two_vocabularies_translate_both_ways() -> None:
    """Core's chain names against the BIP network names, and back.

    Two differ and the rest agree, which is what makes the pairing both
    necessary and easy to leave out: `"main" != "mainnet"` is the mismatch
    a correct comparison produces.
    """
    assert chain_from_network("mainnet") == "main"
    assert chain_from_network("testnet") == "test"
    for shared in ("testnet4", "signet", "regtest"):
        assert chain_from_network(shared) == shared
    for network in _CHAIN_FROM_NETWORK:
        assert network_from_chain(chain_from_network(network)) == network


def test_neither_direction_falls_back_on_a_name_it_does_not_know() -> None:
    """A chain Core adds later fails here, rather than being passed through.

    And the two vocabularies are not interchangeable in either direction:
    Core's `main` is no BIP network name, `mainnet` no chain of Core's, and
    each is refused by the function that does not own it.
    """
    with pytest.raises(BtcRpcValueError, match="unknown network: main"):
        chain_from_network("main")
    with pytest.raises(BtcRpcValueError, match="unknown Core chain: mainnet"):
        network_from_chain("mainnet")


def test_a_caller_can_ask_for_the_port_and_the_subdirectory() -> None:
    """What `from_chain` reads, for a caller `from_chain` cannot serve.

    A node on another host, or one started with `-datadir=` elsewhere, is
    a url and a cookie path the caller assembles: these two are the halves
    of it that Core names and a chain name does not give away -- `main`
    keeping its cookie in the datadir itself, and `test` living under
    `testnet3`.
    """
    assert rpc_port_from_chain("main") == 8332
    assert rpc_port_from_chain("regtest") == 18443
    assert datadir_subdir_from_chain("main") == ""
    assert datadir_subdir_from_chain("test") == "testnet3"


def test_the_port_and_the_subdirectory_are_refused_a_bip_name() -> None:
    """Core's vocabulary, in the two functions keyed by it as in the third.

    `mainnet` is the network name of the chain Core calls `main`, and a
    lookup that fell back on it would answer a port and a directory for a
    name this module holds to meaning nothing here.
    """
    with pytest.raises(BtcRpcValueError, match="unknown Core chain: mainnet"):
        rpc_port_from_chain("mainnet")
    with pytest.raises(BtcRpcValueError, match="unknown Core chain: mainnet"):
        datadir_subdir_from_chain("mainnet")


def test_the_magic_of_each_chain_is_the_one_core_writes() -> None:
    """`pchMessageStart` per chain, from Core's src/kernel/chainparams.cpp.

    Four copied constants and, for signet, the default challenge's -- in
    Core's own byte order, the one a p2p message begins with, so that a
    caller comparing against a packet or against another implementation's
    table is comparing the same four bytes the other way round.
    """
    assert magic_from_chain("main").hex() == "f9beb4d9"
    assert magic_from_chain("test").hex() == "0b110907"
    assert magic_from_chain("testnet4").hex() == "1c163f28"
    assert magic_from_chain("signet").hex() == "0a03cf40"
    assert magic_from_chain("regtest").hex() == "fabfb5da"

    # keyed by Core's vocabulary, like the port and the subdirectory: a BIP
    # name is refused rather than answered for the chain it names
    assert set(_MAGIC_FROM_CHAIN) == set(get_args(Chain))
    with pytest.raises(BtcRpcValueError, match="unknown Core chain: mainnet"):
        magic_from_chain("mainnet")


def test_the_default_signet_magic_is_derived_and_not_only_copied() -> None:
    """The table's signet entry against the rule that produced it.

    Core: "message start is defined as the first 4 bytes of the sha256d of
    the block script", the script serialized with its CompactSize length.
    The entry is a constant so that a reader can compare it with
    chainparams.cpp; this is what says the constant and the derivation
    agree, which is what makes the derivation usable for every other
    signet.
    """
    assert len(bytes.fromhex(DEFAULT_SIGNET_CHALLENGE)) == 71
    assert magic_from_signet_challenge(DEFAULT_SIGNET_CHALLENGE) == magic_from_chain(
        "signet"
    )


def test_a_challenge_is_hex_or_the_bytes_it_spells() -> None:
    """Both spellings of the same script, and nothing else.

    Hex is how a challenge is written in a config file and reported by
    `getblockchaininfo`; bytes is what anything that has parsed one holds.
    A number is neither, and `bytes(71)` would have hashed 71 zero bytes as
    if they were the script.
    """
    script = bytes.fromhex(DEFAULT_SIGNET_CHALLENGE)
    expected = magic_from_chain("signet")
    assert magic_from_signet_challenge(script) == expected
    assert magic_from_signet_challenge(bytearray(script)) == expected
    assert magic_from_signet_challenge(DEFAULT_SIGNET_CHALLENGE.upper()) == expected

    untyped: Any = magic_from_signet_challenge
    with pytest.raises(BtcRpcTypeError, match="signet challenge that is no script: 71"):
        untyped(71)


def test_a_challenge_past_the_one_byte_length_carries_a_two_byte_one() -> None:
    """The second CompactSize form, which no real challenge has reached.

    A script of 253 bytes and over is serialized `fd` and the length in two
    little-endian bytes, and the digest is taken over that -- so the prefix
    is not something the length alone can be substituted for. Computed here
    rather than recorded: what is being pinned is the serialization, and
    writing it out is what a recorded digest would hide.
    """
    script = bytes(range(1, 254))
    assert len(script) == 253
    serialized = b"\xfd" + len(script).to_bytes(2, "little") + script
    expected = sha256(sha256(serialized).digest()).digest()[:4]
    assert magic_from_signet_challenge(script) == expected

    # and the one-byte form stops one byte earlier, which is the boundary
    # a `<=` instead of a `<` would move
    shorter = script[:252]
    serialized = bytes([252]) + shorter
    assert (
        magic_from_signet_challenge(shorter)
        == (sha256(sha256(serialized).digest()).digest()[:4])
    )


def test_a_challenge_no_node_would_take_is_refused() -> None:
    """Empty, not hex, or longer than a script can be.

    Core takes at least one byte for `-signetchallenge`, and consensus caps
    a script at 10000 bytes -- so the CompactSize forms above two bytes
    cannot arise, and this refuses them rather than writing an encoding no
    challenge will be serialized with.
    """
    with pytest.raises(BtcRpcValueError, match="empty signet challenge"):
        magic_from_signet_challenge("")
    with pytest.raises(BtcRpcValueError, match="empty signet challenge"):
        magic_from_signet_challenge(b"")
    with pytest.raises(BtcRpcValueError, match="signet challenge that is no hex"):
        magic_from_signet_challenge("not hex")
    with pytest.raises(BtcRpcValueError, match="more than the 65535 this serializes"):
        magic_from_signet_challenge(bytes(0x10000))


def test_every_chain_with_a_port_has_a_datadir_and_a_name() -> None:
    """The three tables index the same chains, so no lookup can miss.

    `from_chain` reads a port out of one and a subdirectory out of the
    other for the same key, so a chain added to one alone is a KeyError at
    the call rather than a refusal at the check above it. The vocabulary is
    the third: a name Core has a port for and this module cannot translate
    would leave a caller holding a BIP name with no way in.
    """
    assert _RPC_PORT_FROM_CHAIN.keys() == _DATADIR_SUBDIR_FROM_CHAIN.keys()
    assert _RPC_PORT_FROM_CHAIN.keys() == set(_CHAIN_FROM_NETWORK.values())


def test_the_two_literals_name_what_the_two_tables_hold() -> None:
    """A name added to a table and not to its Literal is a false signature.

    `Chain` and `Network` are what these functions are annotated as
    returning, and a type checker believes the annotation: a sixth chain
    reaching the tables alone would have every caller matching on the
    five told it cannot happen.
    """
    assert set(get_args(Chain)) == _RPC_PORT_FROM_CHAIN.keys()
    assert set(get_args(Network)) == _CHAIN_FROM_NETWORK.keys()
