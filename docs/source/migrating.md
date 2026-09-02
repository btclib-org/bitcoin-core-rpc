# Migrating from `AuthServiceProxy`

Two files answer to that name, and they no longer agree with each other:
Bitcoin Core's own copy, `test/functional/test_framework/authproxy.py`,
and python-bitcoinrpc's `bitcoinrpc/authproxy.py`, which most PyPI
packages carrying a vendored client mean by it. Every claim below about
one of the two is checked against it directly — Core's copy at
`05e49b342f`, python-bitcoinrpc's at
`c5527bcdd0b1d98dd9d785729f52337f5bb44a16` — and labelled by file where
the two no longer behave alike.

[COMPARISON.md](./comparison_link.md) makes the case for the switch and
is not repeated here: this page is the mechanics of it, an
`AuthServiceProxy` line at a time with the line that replaces it, for a
caller carrying either file.

## Construction

Both variants take one url, and the credential — where there is one —
sits inside it. That string is also what ends up in a configuration
file, a traceback and a log, which is why a url shaped that way is
refused here; the credential is an argument instead.

```python
# AuthServiceProxy
rpc = AuthServiceProxy(f"http://{user}:{password}@127.0.0.1:8332")

# this client
client = BitcoinCoreRpcClient("http://127.0.0.1:8332", user=user, password=password)
```

**The cookie file.** Neither variant's constructor reads one: a caller
does, by hand, and builds the credential into the url before
constructing it — Core's own test framework is such a caller,
`get_auth_cookie` reading `.cookie` and `create_new_rpc_connection`
building `f"http://{rpc_u}:{rpc_p}@{host}:{port}"` from what it returns.
`from_chain` is that same read, made once inside the constructor rather
than in the caller's own code, and made again at every call rather than
held: a client built while the node is up still works after a restart
rewrites the file.

```python
# AuthServiceProxy (a caller's own glue, e.g. test_framework/test_node.py)
rpc_u, rpc_p = get_auth_cookie(datadir, chain)
rpc = AuthServiceProxy(f"http://{rpc_u}:{rpc_p}@127.0.0.1:{port}")

# this client
client = BitcoinCoreRpcClient.from_chain("main")
```

**A non-default `-rpcport` or `-datadir`.** Neither is a keyword either
constructor takes: a caller builds it into the url, and into whatever
reads the cookie, by hand. `from_chain` carries the chain's own default
port; a node moved off it is an explicit url, and a node started with
`-datadir=` elsewhere is `cookie_path`, per
[Talking to a node](../../README.md#talking-to-a-node).

```python
client = BitcoinCoreRpcClient.from_chain(
    "main", cookie_path=Path("/srv/bitcoin/.cookie")
)
```

**`https`.** Both variants dispatch on the url's scheme —
`http.client.HTTPSConnection` where it reads `https`, exactly as this
client's own transports do — so an `https://` url is the same story on
either side, with the same standard-library certificate trust and no
extra knob on any of the three.

## Invoking a method

**Attribute style.** `AuthServiceProxy.__getattr__` returns a new proxy
bound to the name, sharing the connection; `RpcChannel` wraps a client
for the same syntax one to one, with no second object underneath it.

```python
# AuthServiceProxy
block = rpc.getblock(block_id, 2)

# this client
rpc = RpcChannel(client)
block = rpc.getblock(block_id, 2)
```

**The explicit form.** `call` is the equivalent with no attribute lookup
at all, and it is what `RpcChannel` calls underneath: an unknown method
is a value the node answers for, not an `AttributeError` here.

```python
block = client.call("getblock", [block_id, 2])
block = client.call("getblock", {"blockhash": block_id, "verbosity": 2})
```

**Positional and named together.** Core's copy accepts both in one
call, folding the positional ones under `args` —
`params = dict(args=args, **argsn)` — the same convenience
`src/rpc/server.cpp` reads back out of a named call on the node's own
side. `RpcChannel` refuses the combination outright, json-rpc having one
params shape per call and not both; `call` still reaches it, written out
as the mapping Core's own `args` convenience already is.

```python
# AuthServiceProxy (Core's copy)
block = rpc.getblock(block_id, verbosity=2)

# this client
block = client.call("getblock", {"args": [block_id], "verbosity": 2})
```

## Wallet endpoints

Core's copy overloads `/`: `rpc / "wallet/hot"` builds a second proxy at
the concatenated path, sharing the connection. python-bitcoinrpc's copy
has no such operator, so a caller there starts from a second url built
by hand instead. Either way the wallet name reaches the url exactly as
written; `for_wallet` percent-encodes it, a wallet being a directory and
free to be called anything a filesystem accepts.

```python
# AuthServiceProxy (Core's copy)
hot = rpc / "wallet/hot"
balance = hot.getbalance()

# AuthServiceProxy (python-bitcoinrpc)
hot = AuthServiceProxy(f"http://{user}:{password}@127.0.0.1:8332/wallet/hot")
balance = hot.getbalance()

# this client
balance = client.for_wallet("hot").call("getbalance")
```

## Batching

Core's copy names it `batch`, python-bitcoinrpc's `batch_`; `call_batch`
replaces either name. The shape of the answer differs more than the
name: Core's `batch` hands back the raw reply objects unread, and
python-bitcoinrpc's `batch_` raises the first error it finds and
discards every answer beside it, where `call_batch` reads each member
the way `call` reads its own and keeps going — position i holds member
i's `result`, or its `RpcError` as a value.

```python
# AuthServiceProxy (python-bitcoinrpc)
hashes = rpc.batch_([["getblockhash", height] for height in heights])

# AuthServiceProxy (Core's copy)
calls = [rpc.getblockhash.get_request(height) for height in heights]
hashes = rpc.batch(calls)

# this client
hashes = client.call_batch([("getblockhash", [height]) for height in heights])
```

## Errors

| AuthServiceProxy | this client |
| --- | --- |
| `JSONRPCException.error["code"]` | `RpcError.code` |
| `JSONRPCException.error.get("data")` | `RpcError.data` |
| `JSONRPCException.http_status` (Core's copy only) | `HttpError.status` |
| any other `JSONRPCException` | `FetchError` |

python-bitcoinrpc's own `JSONRPCException` carries no HTTP status at
all — its constructor takes only the error object, and `_get_response`
reads `http_response.status` solely to word the message of the one
error it raises for a non-json content type, never to distinguish a
routine rpc error from a backend that failed outright. Core's copy added
`http_status` for exactly that reason, and it is the field
`HttpError.status` answers.

```python
# AuthServiceProxy
try:
    raw = rpc.getrawtransaction(tx_id)
except JSONRPCException as e:
    if e.error["code"] == -5:
        ...

# this client
try:
    raw = client.call("getrawtransaction", [tx_id])
except RpcError as e:
    if e.code == -5:
        ...
```

[COMPARISON.md](../../COMPARISON.md#comparison) has the `except OSError`
trap beside this: a refused connection is a plain `OSError` on both
`AuthServiceProxy` variants and a `FetchError`, derived from
`RuntimeError`, here.

## Amounts

A reply's numbers decode as `Decimal` on every side alike — `parse_float`
reads the same way in `authproxy.py` and in this client. Requests are
where the two variants part ways from each other as well as from this
one: python-bitcoinrpc's `EncodeDecimal` rounds a `Decimal` parameter
through `float` before sending it (`float(round(o, 8))`); Core's copy
stringifies it instead (`serialization_fallback`'s `str(o)`), which
survives the round trip but silently turns the parameter from a number
into a string. Both are silent either way; this client refuses a
`Decimal` parameter outright, naming what to send instead — an int of
satoshis, or the string the method itself documents.

## Timeouts

Both variants hand `timeout` to `http.client`'s own connection, which
spends it per socket operation: a peer dripping a reply one byte at a
time resets the clock on every read and can hold the call open past
what was asked for. `timeout` and `request_timeout` are a deadline over
the whole exchange instead, taken once before the connect, so the same
dripped reply cannot hold this client open past it either.
`request_timeout` is the one to widen for a method that legitimately
runs long — `rescanblockchain`, `scantxoutset` — rather than building a
second client for it.

## Connections

Both `AuthServiceProxy` variants keep one `http.client` connection open
for the object's life, and `__getattr__` hands it on to every proxy
derived from the first one. This client opens a fresh connection per
`call` by default, per
[Keeping a connection alive](../../README.md#keeping-a-connection-alive);
`SessionTransport` is the equivalent, one connection kept per node and
passed as `transport=`.

```python
from bitcoin_core_rpc import BitcoinCoreRpcClient, SessionTransport

with SessionTransport() as session:
    client = BitcoinCoreRpcClient.from_chain("main", transport=session)
```

## The envelope

Core's copy exposes `_request` and `_get_response` for a caller who
wants to send a request `__call__` would not build and read the reply
before anything is asked of its shape — both reached by poking at
attributes (`rpc._AuthServiceProxy__url`, name-mangled) the class does
not otherwise publish. `call_raw` is the same seam, public: the same
authenticated POST `call` builds, the protocol marker itself an
argument, and the answer handed back exactly as parsed — no id check,
no `result` extracted, no shape assumed.

```python
status, reply = client.call_raw("getblockcount", jsonrpc=None)
```

## Testing

Neither `AuthServiceProxy` variant takes a seam: a caller wanting to
test code that calls a node monkeypatches `http.client` itself, or the
connection object each constructor builds by hand. `transport` is that
seam here, a callable in place of the constructor's default, taking the
request and the timeout and answering the status and the body — the
suite of this project opens no socket, and neither has yours to, per
[Testing code that calls a
node](../../README.md#testing-code-that-calls-a-node).

## What has no equivalent

**Notifications.** A request sent with no `id`, which a node does not
answer, is not a documented feature of either `AuthServiceProxy` file —
but nothing in `__call__` refuses building one by hand, where `call`
always sends an `id`. No `AuthServiceProxy` consumer is giving anything
up.

**A request this client refuses to build.** Neither `AuthServiceProxy`
file validates a method name or its params before sending them —
`__call__` sends whatever `json.dumps` accepts, method, params and all —
where this client refuses a non-string method, or params that are
neither a sequence nor a mapping, before opening a connection. A caller
building a request that is deliberately invalid — a conformance harness
testing a server's own handling of a malformed one — has `http_request`
for it, the public seam beneath `call` and `call_raw` alike, rather than
a version of `AuthServiceProxy`'s own permissiveness inside this class.
