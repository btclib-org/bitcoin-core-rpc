# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Core's chains: the port and datadir tables, the magic bytes, the cookie.

The chain and network vocabularies and their translations, the rpc port
and datadir subdirectory of each chain, the magic bytes and the signet
derivation, and the cookie path and `cookie_auth` that reads it. Nothing
here opens a socket: `client.py` is where a chain's own defaults become a
connection.
"""

from __future__ import annotations

import sys
from hashlib import sha256
from os import PathLike, environ
from pathlib import Path
from typing import Literal

from bitcoin_core_rpc.errors import (
    BtcRpcTypeError,
    BtcRpcValueError,
    CookieNotFoundError,
    FetchError,
)

# Every name this module defines, none of it imported: `__init__.py`'s own
# `__all__` is their union across the four modules of the package, and
# section 7 of the organization standard asks each of them for its own
# besides.
__all__ = [
    "COOKIE_USER",
    "DEFAULT_DATADIR",
    "DEFAULT_SIGNET_CHALLENGE",
    "Chain",
    "Network",
    "chain_from_network",
    "cookie_auth",
    "cookie_path_from_chain",
    "datadir_subdir_from_chain",
    "default_datadir",
    "magic_from_chain",
    "magic_from_signet_challenge",
    "network_from_chain",
    "rpc_port_from_chain",
]

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
# once, in the module that speaks Core's protocol and is therefore the
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
# no `phrase: rest` opening below, here or on any other attribute docstring:
# napoleon reads that shape as `type: description` and renders the phrase as
# the attribute's Type, which `-n` then reports as a class nothing declares
"""Core's chain names, which `-chain=` takes and `getblockchaininfo`
reports, and which `from_chain` and the two lookups are spelled in.

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


DEFAULT_SIGNET_CHALLENGE = (
    # split at a push boundary: OP_1 and the first key, then the second key
    # with OP_2 and OP_CHECKMULTISIG after it -- a 1-of-2 multisig. The
    # allowlist comments are for the secret scanner, which reads a long hex
    # string as a credential: this one is two public keys and is published
    # in every copy of Core
    "512103ad5e0edad18cb1f0fc0d28a3d4f1f3e445640337489abb10404f2d1e086be430"  # pragma: allowlist secret
    "210359ef5021964fe22d6f8e05b2463c9540ce96883fe3b278760f048f5189f2e6c452ae"  # pragma: allowlist secret
)
"""The block challenge of the signet everyone means by "signet".

`SigNetParams` in Core's src/kernel/chainparams.cpp, the `bin` a node
started without `-signetchallenge` uses. What makes it worth publishing is
that it is the one signet a caller can name rather than describe:
`magic_from_signet_challenge(DEFAULT_SIGNET_CHALLENGE)` is
`magic_from_chain("signet")`, and any other challenge is a chain this table
has no entry for.
"""


# Core's `pchMessageStart` per chain, from src/kernel/chainparams.cpp: the
# four bytes every p2p message on that chain begins with, in the order Core
# writes them there. Not needed to make an rpc call, and here for the one
# question rpc cannot otherwise answer -- `assert_chain` in `client.py`: two
# signets report the same `chain` string and are different networks, and
# the magic is what tells them apart.
#
# Signet's entry is the *default* signet's, and it is a copy of the derived
# value rather than the derivation: a table of constants is what a reader
# compares against Core, and `magic_from_signet_challenge` reproducing this
# entry from `DEFAULT_SIGNET_CHALLENGE` is a test rather than an import-time
# computation nothing would catch being wrong.
_MAGIC_FROM_CHAIN: dict[str, bytes] = {
    "main": bytes.fromhex("f9beb4d9"),
    "test": bytes.fromhex("0b110907"),
    "testnet4": bytes.fromhex("1c163f28"),
    "signet": bytes.fromhex("0a03cf40"),
    "regtest": bytes.fromhex("fabfb5da"),
}

# above which a script's CompactSize length would take five bytes, which
# `magic_from_signet_challenge` refuses rather than serializes: consensus
# caps a script at 10000 bytes, so the form cannot arise for a challenge,
# and refusing is what keeps the two forms below the whole of the encoding
_MAX_CHALLENGE_LENGTH = 0xFFFF


def magic_from_chain(chain: str) -> bytes:
    """Return the p2p message start of one of Core's chains.

    Signet's is the default signet's -- `magic_from_signet_challenge` is
    what answers for any other, the challenge being what a signet is
    identified by.
    """
    if chain not in _MAGIC_FROM_CHAIN:
        known = ", ".join(_MAGIC_FROM_CHAIN)
        raise BtcRpcValueError(f"unknown Core chain: {chain} not in ({known})")
    return _MAGIC_FROM_CHAIN[chain]


def magic_from_signet_challenge(challenge: str | bytes | bytearray) -> bytes:
    """Return the p2p message start a signet's block challenge determines.

    Core: "message start is defined as the first 4 bytes of the sha256d of
    the block script", the script serialized with its CompactSize length,
    and the four bytes in the order the digest produces them. BIP325 is
    the challenge itself; this is what `SigNetParams` does with it.

    Hex or the bytes it spells, because a challenge is written in a config
    file and reported by `getblockchaininfo` as hex, and held as bytes by
    anything that has parsed it. Nothing else, `bytes(7)` being seven zero
    bytes rather than an error: a challenge that arrived as a number would
    otherwise be hashed as a script of that length.

    A challenge no node would accept is refused: Core takes at least one
    byte, and above two bytes of length prefix the serialization is one
    this does not write.
    """
    if isinstance(challenge, str):
        try:
            script = bytes.fromhex(challenge)
        except ValueError as e:
            raise BtcRpcValueError(f"signet challenge that is no hex: {e}") from e
    elif isinstance(challenge, (bytes, bytearray)):
        script = bytes(challenge)
    else:
        # unreachable under the annotation above, which is not a promise
        # a caller that skips type checking keeps
        err_msg = f"signet challenge that is no script: {challenge!r}"  # type: ignore[unreachable]
        raise BtcRpcTypeError(err_msg)
    if not script:
        raise BtcRpcValueError("empty signet challenge")
    if len(script) > _MAX_CHALLENGE_LENGTH:
        err_msg = f"signet challenge of {len(script)} bytes,"
        err_msg += f" more than the {_MAX_CHALLENGE_LENGTH} this serializes"
        raise BtcRpcValueError(err_msg)
    length = (
        bytes([len(script)])
        if len(script) < 0xFD
        else b"\xfd" + len(script).to_bytes(2, "little")
    )
    return sha256(sha256(length + script).digest()).digest()[:4]


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
