# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The exception hierarchy this package raises.

`BtcRpcValueError` to `CookieNotFoundError`: every other module raises out
of this one, so it is the layer beneath all of them and the one place a
caller wanting the whole hierarchy imports from.
"""

from __future__ import annotations

import enum
from typing import Any

# Every name this module defines, none of it imported: `__init__.py`'s own
# `__all__` is their union across the four modules of the package, and
# section 7 of the organization standard asks each of them for its own
# besides.
__all__ = [
    "BtcRpcRuntimeError",
    "BtcRpcTypeError",
    "BtcRpcValueError",
    "CookieNotFoundError",
    "FetchError",
    "HttpError",
    "RPCErrorCode",
    "RpcError",
]

# The three bases below the standard exceptions keep the TypeError,
# ValueError and RuntimeError hierarchies exact: a caller who wants none of
# the names here catches those three and still separates a caller error from
# a failure of the exchange.
#
# `BtcRpc`: a distinct prefix, so that a consumer already carrying an
# error hierarchy of its own does not have to tell two `ValueError`
# subclasses apart. Two classes of one name from two packages is an
# `except` that reads correct at every call site and catches the wrong
# one at half of them; distinct names put the mistake in the source
# rather than in a test.
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

    # no @override: typing has it from 3.12, the floor here is 3.10, and
    # this file takes nothing outside the standard library
    def __str__(self) -> str:  # type: ignore[explicit-override]
        # the message alone, which is what BaseException returns for a
        # single argument and not for the two this now carries
        return str(self.args[0])


class RPCErrorCode(enum.IntEnum):
    """Core's own `RPCErrorCode`, `src/rpc/protocol.h`, transcribed whole.

    Every member of Core's enum at `bitcoin/bitcoin@9be056a8a7`, `RPC_`
    dropped from each name, values included -- a code Core reserved or
    deprecated stays a member here rather than being trimmed, because
    `RpcError.code` can still carry it. `FORBIDDEN_BY_SAFE_MODE` (-2) is
    that case: Core's own comment marks the block it is in "unused
    reserved codes, kept around for backwards compatibility. Do not
    reuse," and it is transcribed rather than dropped for the same
    reason the rest are. -21 names no member because Core's own enum
    does not either -- the gap is Core's, not a value cut here.
    `TRANSACTION_ERROR`, `TRANSACTION_REJECTED` and
    `WALLET_INVALID_ACCOUNT_NAME` alias another member rather than naming
    a new value, through `enum`'s own mechanism for it -- a repeated
    value binds to the member that already claims it -- which reproduces
    Core's own `RPC_X = RPC_Y` aliases rather than approximating them.

    This is a lookup, not a constraint: `RpcError.code` stays a plain
    `int`, because a code absent here is an answer a node gave and not a
    defect of this type -- a future Core release, or a JSON-RPC server
    that is not Core, is free to send a code this class does not name.
    `RPCErrorCode(exc.code)` is the caller's own one line when it wants
    the name, and it raises `ValueError` -- Core's own answer, not a
    silent guess -- only for a code truly absent from Core's table.
    """

    # standard JSON-RPC 2.0 errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # general application defined errors
    MISC_ERROR = -1
    TYPE_ERROR = -3
    INVALID_ADDRESS_OR_KEY = -5
    OUT_OF_MEMORY = -7
    INVALID_PARAMETER = -8
    DATABASE_ERROR = -20
    DESERIALIZATION_ERROR = -22
    VERIFY_ERROR = -25
    VERIFY_REJECTED = -26
    VERIFY_ALREADY_IN_UTXO_SET = -27
    IN_WARMUP = -28
    METHOD_DEPRECATED = -32

    # aliases for backward compatibility
    TRANSACTION_ERROR = VERIFY_ERROR
    TRANSACTION_REJECTED = VERIFY_REJECTED

    # P2P client errors
    CLIENT_NOT_CONNECTED = -9
    CLIENT_IN_INITIAL_DOWNLOAD = -10
    CLIENT_NODE_ALREADY_ADDED = -23
    CLIENT_NODE_NOT_ADDED = -24
    CLIENT_NODE_NOT_CONNECTED = -29
    CLIENT_INVALID_IP_OR_SUBNET = -30
    CLIENT_P2P_DISABLED = -31
    CLIENT_NODE_CAPACITY_REACHED = -34

    # chain errors
    CLIENT_MEMPOOL_DISABLED = -33

    # wallet errors
    WALLET_ERROR = -4
    WALLET_INSUFFICIENT_FUNDS = -6
    WALLET_INVALID_LABEL_NAME = -11
    WALLET_KEYPOOL_RAN_OUT = -12
    WALLET_UNLOCK_NEEDED = -13
    WALLET_PASSPHRASE_INCORRECT = -14
    WALLET_WRONG_ENC_STATE = -15
    WALLET_ENCRYPTION_FAILED = -16
    WALLET_ALREADY_UNLOCKED = -17
    WALLET_NOT_FOUND = -18
    WALLET_NOT_SPECIFIED = -19
    WALLET_ALREADY_LOADED = -35
    WALLET_ALREADY_EXISTS = -36

    # backwards compatible aliases
    WALLET_INVALID_ACCOUNT_NAME = WALLET_INVALID_LABEL_NAME

    # unused reserved codes, kept around for backwards compatibility, do
    # not reuse
    FORBIDDEN_BY_SAFE_MODE = -2


class RpcError(FetchError):
    """bitcoind answered with a JSON-RPC error object, and this is it.

    `code` is the node's, from `src/rpc/protocol.h`: -5 is
    RPC_INVALID_ADDRESS_OR_KEY, which is what `getrawtransaction` returns
    for a transaction it cannot find -- including every non-wallet
    transaction on a node running without `-txindex`. A caller telling "no
    such transaction" from "the node is unreachable" needs the number, and
    it stays a plain `int` here rather than `RPCErrorCode` -- a code
    Core's own header does not (yet) name is still a code Core sent, and
    typing this field to the enumeration would make that answer a
    `ValueError` instead. `RPCErrorCode(exc.code)` is the caller's own
    line when it wants the name.

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

    # no @override: typing has it from 3.12, the floor here is 3.10, and
    # this file takes nothing outside the standard library
    def __str__(self) -> str:  # type: ignore[explicit-override]
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
