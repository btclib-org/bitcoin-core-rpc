# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""A standalone JSON-RPC client against Bitcoin Core.

Nothing but the standard library behind it. `BitcoinCoreRpcClient` invokes
any one rpc method a node has, with positional or named parameters: one
HTTP POST per call, basic authentication, the result or an exception. Any
method, because a caller with a node has every reason to ask it anything,
and a client that knew a list of methods would only mean they write this
class again.

**Not python-bitcoinrpc's `AuthServiceProxy`, and not a port of it.**
That class, and the copy of it Core's test framework maintains, carry the
LGPL-2.1 of their python-jsonrpc ancestry, where this is MIT: this is
an implementation of the protocol rather than a translation of theirs,
and shares no line with either. It is not API-compatible with them
either, and does not try to be -- `call("getblockcount")` against an
attribute lookup that builds a method name is a different interface, and
the explicit one is what makes an unknown method a value rather than a
typo that becomes a request.

**Migrating from `AuthServiceProxy`.** Four things change, and each of
them is the difference deliberately.

.. code-block:: python

    # a method is an argument, not an attribute: an unknown one is a
    # value that arrives at the node, not an AttributeError here
    rpc.getblock(block_id, 2)
    client.call("getblock", [block_id, 2])

    # and the named form is the other structure Core takes
    client.call("getblock", {"blockhash": block_id, "verbosity": 2})

    # credentials leave the url, which is what gets written into a
    # config file and printed in a traceback
    AuthServiceProxy(f"http://{user}:{password}@127.0.0.1:8332")
    BitcoinCoreRpcClient("http://127.0.0.1:8332", user=user, password=password)
    BitcoinCoreRpcClient.from_chain("main")  # or the node's cookie file

    # one wallet of a multi-wallet node, percent-encoded
    client.for_wallet("hot").call("getbalance")

`JSONRPCException` becomes three exceptions, because it covered three
things a caller acts on differently: `RpcError` when the node computed an
error, with its `code`; `HttpError` when the exchange failed, with its
`status`; `FetchError` when there was no answer to read at all. All three
are `FetchError`, so one `except FetchError` is the equivalent of the one
`except JSONRPCException`; what catching them apart buys is the status a
retry policy reads.

``batch_`` is what a consumer loses under that name -- Core's maintained
fork spells it `batch` -- and `call_batch` is what replaces it. Several
`(method, params)` pairs travel in one HTTP POST, each built the way
`call` builds its own single request, and the answer is a list aligned
with the input: position i holds member i's `result`, or its `RpcError`
as a value, matched to its request by `id` rather than by array
position. Only a failure of the whole exchange -- a non-2xx status, a
reply that is not an array, a reply no member's id claims -- raises,
exactly as `call` raises. `COMPARISON.md`'s *Batching* has the case for
reaching for it over a loop of `call`, and where a loop remains the
better choice.

Notifications -- a request sent with no `id`, which a node does not answer
-- are a non-goal too, and no `AuthServiceProxy` consumer is giving one
up: both implementations count an `id` into every request they build, so
sending one at all means building the request body instead of calling
`call`.

**One call, one HTTP request, and no retry.** A 503 from bitcoind means
its rpc work queue is full and the same request works once the queue
drains, so a retry is the obvious convenience -- and it is the caller's
to write, for two reasons. `call` carries any method, so this class
cannot know whether re-sending one is safe. And the timeout bounds this
client's wait rather than the node's work: a node that stopped answering
may still be executing the call, so a client re-sending a wallet command
of its own accord can execute it twice. `HttpError.status` is what makes
that policy three lines rather than a match on the text of a message; it
is no ruling on which failures are transient, a refused connection and an
expired timeout arriving as a plain `FetchError` and both able to clear on
their own.

**JSON-RPC 2.0, and 1.1 read back.** Core answers 1.1 by default and 2.0
to a request carrying the `"jsonrpc": "2.0"` marker, and the difference
is which layer reports a bitcoin error: under 1.1 an unknown transaction
comes back as HTTP 500 with the error object in the body, so a genuine
server fault and a routine "no such transaction" are the same status.
Under 2.0 an rpc error is HTTP 200 with an `error` member, and a non-2xx
means the HTTP exchange itself failed. Both are read here -- a node older
than v28 does not know the marker and replies 1.1 to it -- but only one
of them can be told apart from a proxy in the way.

**No credentials in the url.** A url with the userinfo part filled in --
the `<user>:<password>@` before the host -- puts a password in a string
that ends up in configuration files, tracebacks and logs. Such a url is
refused here; the password arrives as an argument, or, better, is never
seen at all -- `.cookie` is what bitcoind writes for exactly this,
rotated at every restart, readable by the user running the node and by
nobody else.

**The client and the transport are published without being imported.**
`chains.py` is the chain and network vocabulary and opens no socket, and
`errors.py` is the exception hierarchy every module raises out of; both
import only the standard library beneath them, and neither pulls in
`urllib.request`. `client.py` and `transport.py` do -- `ssl` and `socket`
under it -- so a caller reaching for `magic_from_chain` or `cookie_auth`
alone pays for none of that. The names those two modules hold are
answered by `__getattr__` below, imported the first time one of them is
asked for; the `TYPE_CHECKING`
import beside it is what keeps a checker reading `BitcoinCoreRpcClient`
as that class and not as the `Any` an unresolved `__getattr__` answers
with, since it never runs and costs nothing at import time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bitcoin_core_rpc.chains import (
    COOKIE_USER,
    DEFAULT_DATADIR,
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
    BtcRpcRuntimeError,
    BtcRpcTypeError,
    BtcRpcValueError,
    CookieNotFoundError,
    FetchError,
    HttpError,
    RpcError,
)

if TYPE_CHECKING:
    # never executed -- `TYPE_CHECKING` is False at runtime -- so a
    # checker sees these at their own type and nothing here pays for
    # `transport.py` or `client.py` at import time. `__getattr__` below is
    # what answers them for real, and it answers a checker too: mypy
    # reads a module's own `__getattr__` return type only for a name
    # neither this import nor anything else in this module has already
    # bound, which is why this block covers every one of them
    from bitcoin_core_rpc.client import USER_AGENT, BitcoinCoreRpcClient, RpcChannel
    from bitcoin_core_rpc.transport import (
        DEFAULT_MAX_BODY_SIZE,
        DEFAULT_TIMEOUT,
        MAX_ERROR_BODY_SIZE,
        HttpTransport,
        SessionTransport,
        http_request,
        urlopen_transport,
    )

__all__ = [
    "COOKIE_USER",
    "DEFAULT_DATADIR",
    "DEFAULT_MAX_BODY_SIZE",
    "DEFAULT_SIGNET_CHALLENGE",
    "DEFAULT_TIMEOUT",
    "MAX_ERROR_BODY_SIZE",
    "USER_AGENT",
    "BitcoinCoreRpcClient",
    "BtcRpcRuntimeError",
    "BtcRpcTypeError",
    "BtcRpcValueError",
    "Chain",
    "CookieNotFoundError",
    "FetchError",
    "HttpError",
    "HttpTransport",
    "Network",
    "RpcChannel",
    "RpcError",
    "SessionTransport",
    "chain_from_network",
    "cookie_auth",
    "cookie_path_from_chain",
    "datadir_subdir_from_chain",
    "default_datadir",
    "http_request",
    "magic_from_chain",
    "magic_from_signet_challenge",
    "network_from_chain",
    "rpc_port_from_chain",
    "urlopen_transport",
]

# `transport.py`'s, answered from that module the first time one is asked
# for. `client.py`'s three are `_ON_DEMAND_CLIENT` below, not folded into
# this tuple: the two modules are imported separately, and each name says
# which
_ON_DEMAND_TRANSPORT = (
    "DEFAULT_MAX_BODY_SIZE",
    "DEFAULT_TIMEOUT",
    "MAX_ERROR_BODY_SIZE",
    "HttpTransport",
    "SessionTransport",
    "http_request",
    "urlopen_transport",
)
_ON_DEMAND_CLIENT = (
    "BitcoinCoreRpcClient",
    "RpcChannel",
    "USER_AGENT",
)


def __getattr__(name: str) -> Any:
    """Return a transport- or client-backed name, importing it on first use.

    PEP 562: this is what keeps `import bitcoin_core_rpc.chains` -- or
    `.errors` -- from also running `transport.py` and `client.py`, which
    is where `urllib.request` and, under it, `ssl` and `socket` come
    from. Reached through `bitcoin_core_rpc.<name>` and through
    `from bitcoin_core_rpc import <name>` alike, which is how a walker
    reading `__all__` descends and how the second spelling resolves a name
    this module has not bound directly.
    """
    if name in _ON_DEMAND_TRANSPORT:
        from bitcoin_core_rpc import transport  # noqa: PLC0415

        return getattr(transport, name)
    if name in _ON_DEMAND_CLIENT:
        from bitcoin_core_rpc import client  # noqa: PLC0415

        return getattr(client, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Answer with the published names beside what is already here.

    The PEP 562 asymmetry: `dir()` reads the namespace, so a name
    `__getattr__` has not been asked for yet is missing from it, and
    interactive completion would hide every name this answers on demand.
    """
    return sorted({*__all__, *globals()})
