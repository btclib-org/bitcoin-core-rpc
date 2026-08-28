# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The exception hierarchy this package raises.

`BtcRpcValueError` to `CookieNotFoundError`: every other module raises out
of this one, so it is the layer beneath all of them and the one place a
caller wanting the whole hierarchy imports from.
"""

from __future__ import annotations

from typing import Any

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


class RpcError(FetchError):
    """bitcoind answered with a JSON-RPC error object, and this is it.

    `code` is the node's, from `src/rpc/protocol.h`: -5 is
    RPC_INVALID_ADDRESS_OR_KEY, which is what `getrawtransaction` returns
    for a transaction it cannot find -- including every non-wallet
    transaction on a node running without `-txindex`. A caller telling "no
    such transaction" from "the node is unreachable" needs the number.

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
