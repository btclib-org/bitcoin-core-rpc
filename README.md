# bitcoin-core-rpc

A standalone JSON-RPC client against Bitcoin Core.
As used by the btclib library.

<!-- The badges are what the reader decides with, in three groups: what the
software is and whether it can be used, whether it works, and what the
OpenSSF makes of it.

Inside the second group the gates come first, in the order a commit meets
them, and the sentinels follow in the order section 10 of the organization
standard schedules them -- the badge order *is* the calendar order over
that subset, which is why the two move together or not at all. The day and
hour each sentinel owns live in that section and are not copied here: a
reader wanting the schedule reads it there, where it is still true.

One badge per line keeps a change to one line and every line inside MD013,
whose 80 columns bind only where a space follows them.

A badge that reports no state -- "we use ruff", "we use uv" -- reports a
choice instead, and those are in CONTRIBUTING.md, beside the prose that
says how the choice is enforced.
-->
[![PyPI version](https://img.shields.io/pypi/v/bitcoin-core-rpc.svg?logo=pypi)](https://pypi.org/project/bitcoin-core-rpc/)
[![GitHub release](https://img.shields.io/github/v/release/btclib-org/bitcoin-core-rpc.svg)](https://github.com/btclib-org/bitcoin-core-rpc/releases)
[![development status](https://img.shields.io/pypi/status/bitcoin-core-rpc.svg)](https://pypi.org/project/bitcoin-core-rpc/)
[![license](https://img.shields.io/github/license/btclib-org/bitcoin-core-rpc.svg)](https://github.com/btclib-org/bitcoin-core-rpc/blob/main/LICENSE)
[![downloads](https://static.pepy.tech/badge/bitcoin-core-rpc)](https://pepy.tech/projects/bitcoin-core-rpc)
[![supported Python versions](https://img.shields.io/pypi/pyversions/bitcoin-core-rpc.svg?logo=python)](https://pypi.org/project/bitcoin-core-rpc/)
[![implementation](https://img.shields.io/pypi/implementation/bitcoin-core-rpc.svg)](https://pypi.org/project/bitcoin-core-rpc/)
[![wheel](https://img.shields.io/pypi/wheel/bitcoin-core-rpc.svg)](https://pypi.org/project/bitcoin-core-rpc/)

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/btclib-org/bitcoin-core-rpc/main.svg)](https://results.pre-commit.ci/latest/github/btclib-org/bitcoin-core-rpc/main)
[![lint workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/lint.yml)
[![test workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/test.yml)
[![docs workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/docs.yml)
[![documentation build](https://app.readthedocs.org/projects/bitcoin-core-rpc/badge/?version=latest)](https://bitcoin-core-rpc.readthedocs.io)
[![mutation workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/mutation.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/mutation.yml)
[![integration-bitcoind workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/integration-bitcoind.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/integration-bitcoind.yml)
[![deps-latest workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/deps-latest.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/deps-latest.yml)
[![pypi-install workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/pypi-install.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/pypi-install.yml)
[![os-macos workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/os-macos.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/os-macos.yml)
[![os-ubuntu workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/os-ubuntu.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/os-ubuntu.yml)
[![os-windows workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/os-windows.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/os-windows.yml)
[![links workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/links.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/links.yml)
[![codeql workflow status](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/btclib-org/bitcoin-core-rpc/actions/workflows/codeql.yml)

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/btclib-org/bitcoin-core-rpc/badge)](https://scorecard.dev/viewer/?uri=github.com/btclib-org/bitcoin-core-rpc)

Nothing but the standard library behind it, fully annotated and shipping
`py.typed`. `BitcoinCoreRpcClient` invokes any one rpc method a node has,
with positional or named parameters: one HTTP POST per call, basic
authentication, the result or an exception.

```shell
pip install bitcoin-core-rpc
```

## Talking to a node

`from_chain` is the local node of one of Core's chains: the loopback url,
the port and the cookie file all come from Core's own defaults, so a node
started with none of them overridden needs no arguments at all.

```python
from bitcoin_core_rpc import BitcoinCoreRpcClient

client = BitcoinCoreRpcClient.from_chain("main")
print(client.call("getblockcount"))
print(client.call("getblockchaininfo")["chain"])
```

The credential is the cookie file bitcoind rewrites at every start, read at
each call rather than held: a client built when the node was up still works
an hour and a restart later. The datadir it is looked for under is Core's
own for the platform running — `%APPDATA%\Bitcoin` on Windows,
`~/Library/Application Support/Bitcoin` on macOS, `~/.bitcoin` elsewhere —
so `from_chain` needs no help on any of the three. A node started with
`-datadir=` somewhere else is what nothing can derive, and there the path
is an argument:

```python
from pathlib import Path

client = BitcoinCoreRpcClient(
    "http://127.0.0.1:8332",
    cookie_path=Path("/srv/bitcoin/.cookie"),
)
```

`rpcuser` and `rpcpassword` are the other way. They are arguments and never
part of the url: a url with `user:password@` in it is refused, because that
string ends up in configuration files, tracebacks and logs.

```python
client = BitcoinCoreRpcClient(
    "http://127.0.0.1:8332", user="rpcuser", password="rpcpassword"
)
```

A cookie or a datadir only authenticates the node that wrote it, not the
chain it is running: `-chain=test` and a `main` cookie both exist. `main`
is `from_chain`'s own default, so a caller who names it and gets `test`
back either passed the wrong name or reused a cookie carried over from
elsewhere — `verify_chain` asks `getblockchaininfo` once and raises
`BtcRpcValueError` if the two disagree, rather than trusting the port and
the datadir name to have agreed with the node underneath them.

```python
client = BitcoinCoreRpcClient.from_chain("main", verify_chain=True)
```

Signet is the case a name cannot settle: Core answers `signet` for the
default signet and for every custom one alike, so the challenge is what
tells two of them apart. Pass the one you mean, hex or bytes, as
`-signetchallenge` takes it; the comparison is of the p2p magic it derives,
which is what makes the same challenge in upper case the same challenge.

```python
client = BitcoinCoreRpcClient.from_chain(
    "signet", verify_chain=True, signet_challenge="512102...ae"
)
```

`assert_chain` is that check on its own, for a client built at a url of your
own — a node on another host, or behind a proxy — where there is no
`from_chain` to ask for it.

```python
client = BitcoinCoreRpcClient("https://node.example/", user="u", password="p")
client.assert_chain("signet", signet_challenge="512102...ae")
```

## Calling

`params` is one value, shaped as JSON-RPC shapes it: a sequence for the
positional form, a mapping for the named one. Core takes both, and which
one a method wants is the method's business.

```python
block_id = client.call("getblockhash", [700_000])
block = client.call("getblock", {"blockhash": block_id, "verbosity": 2})
```

Amounts do not travel as binary floating point in either direction: a
number in the reply decodes as a `Decimal`, and a `Decimal` parameter is
refused rather than rounded through `float`.

```python
balance = client.for_wallet("hot").call("getbalance")  # Decimal, exact
```

`for_wallet` is the `/wallet/<name>` endpoint of a node with several
wallets loaded, with the name percent-encoded — a wallet is a directory and
may be called anything a filesystem accepts. Every wallet's client is
derived from the client built for the node: calling it on a client that is
already a wallet endpoint is refused rather than composing
`/wallet/hot/wallet/cold`, which is no path Core serves.

`call_raw` is `call` with the envelope handed back instead of read: the
same request, the same params validation, with the protocol marker an
argument rather than always `"2.0"` — a string is sent verbatim, `None`
sends no marker at all. The answer is the HTTP status and whatever the
body parses to, with neither `id`, `error` nor shape interpreted — an
array or a bare scalar comes back exactly as parsed rather than being
refused the way `call`'s own reply is, which is what a harness testing
a server's own conformance wants in place of a result already extracted.

```python
status, reply = client.call_raw("getblockcount", jsonrpc=None)
```

## Batching

`call_batch` sends several `(method, params)` pairs in one HTTP POST,
each built and each member's reply read the way `call` builds and reads
its own. The result is a list aligned with the input: a member's
`RpcError` sits at its own position rather than raising and discarding
every answer beside it.

```python
results = client.call_batch([("getblockhash", [700_000]), ("getblockcount", None)])
```

Only a failure of the whole exchange raises — a non-2xx status, a reply
that is not an array — exactly as `call` raises for its own request.
[COMPARISON.md](./COMPARISON.md#batching) has where this is worth
reaching for over a loop of `call`, and where it is not.

## Attribute-style calls

`RpcChannel` wraps a client for a caller who wants `rpc.getblockcount()`
over `client.call("getblockcount")` and has weighed the trade in
[COMPARISON.md](./COMPARISON.md#dynamic-dispatch): an unknown method is a
request to the node rather than an `AttributeError` here.

```python
from bitcoin_core_rpc import BitcoinCoreRpcClient, RpcChannel

rpc = RpcChannel(BitcoinCoreRpcClient.from_chain("main"))
print(rpc.getblockcount())
print(rpc.getblock(blockhash=block_id, verbosity=2))
```

Positional arguments become the sequence form of `params`, named ones the
mapping form — never both at once, json-rpc having one shape per call.
`request_timeout` and `max_body_size`, `call`'s own keyword-only controls,
reach `call` rather than travelling to the node as a named parameter; every
other name starting with `_`, dunders included, is an `AttributeError`
instead of a request, which is what keeps `copy.deepcopy` and an
interactive shell's attribute probing from becoming one.

## Keeping a connection alive

The default transport opens one connection per call and lets the node
close it — [COMPARISON.md](./COMPARISON.md#one-connection-per-call) has
why. `SessionTransport` is this module's own alternative: one connection
kept per node, reused across calls, passed the way any other `transport`
is.

```python
from bitcoin_core_rpc import BitcoinCoreRpcClient, SessionTransport

with SessionTransport() as session:
    client = BitcoinCoreRpcClient.from_chain("main", transport=session)
    client.call("getblockcount")
    client.call("getblockchaininfo")  # the same connection, reused
```

One instance is safe to share between threads: the whole exchange —
connect or reuse, send, read — is serialized under one lock, at the cost
of never running two calls through it at once. A caller wanting
concurrency across several nodes keeps one instance per node instead.

## Reading Core's `-rest` interface

`-rest` is Core's other interface, read-only, off by default, and — unlike
JSON-RPC — authenticating nobody who reaches it. `BitcoinCoreRestClient`
speaks it: `get_bin` for a `.bin` path, returning the body unread, and
`get_json` for a `.json` one, returning what it parses to. It shares the
transport and the chain vocabulary with `BitcoinCoreRpcClient` and nothing
else — no credentials, `-rest` taking none.

```python
from bitcoin_core_rpc import BitcoinCoreRestClient

rest = BitcoinCoreRestClient.from_chain("main")
info = rest.get_json("/chaininfo.json")
raw_tx = rest.get_bin(f"/tx/{tx_id}.bin")
```

There is no `get_tx`, no `get_block`, no `get_utxos`: `path` is built from
Core's own documentation of `-rest` and appended after `/rest` unread.
`/getutxos` is why a per-resource method is refused rather than merely
undone here — it reads the UTXO set, so an output already spent and one
never created answer the same way, and a wrapper turning that answer into
`None` would read as telling more than `/getutxos` does.

## When it goes wrong

Each exception below is a different thing to do about a failure. Every
one of them is a `FetchError`, so one `except FetchError` covers the lot.

| exception | what happened | what it carries |
| --- | --- | --- |
| `RpcError` | the node computed an error | `code`, `data` |
| `HttpError` | the exchange failed | `status` |
| `FetchError` | there was no answer to read | — |

```python
from bitcoin_core_rpc import FetchError, HttpError, RpcError

try:
    raw = client.call("getrawtransaction", [tx_id])
except RpcError as e:
    if e.code == -5:  # no such transaction; a node without -txindex
        ...  # answers this for anything outside its wallet
except HttpError as e:
    if e.status == 503:  # the rpc work queue is full: try again later
        ...  # a 401 never works again, so tell the two apart
except FetchError:
    ...  # refused connection, expired timeout, no answer
```

There is no retry, and it is deliberate: `call` carries any method, so this
client cannot know whether re-sending one is safe, and a timeout is not a
deadline — a node that stopped answering may still be executing the call.
`HttpError.status` is what makes a caller's own policy three lines rather
than a match on the text of a message.

## What it does not do

- **notifications**, a request sent with no `id`, which a node does not
  answer.
- **retries**, per above.
- **redirects.** A 30x arrives as an `HttpError` rather than as a second
  request: the first one already carries the `Authorization` for the host
  it names, and following the redirect would send that credential wherever
  the `Location` points.
- **proxies from the environment.** `HTTP_PROXY` is set for a browser or a
  package manager and inherited by everything in the shell, which is the
  wrong source for the decision of where a wallet command is sent. A caller
  who does want one passes a `transport`.

## Migrating from `AuthServiceProxy`

It is **not** python-bitcoinrpc's `AuthServiceProxy` and not a port of it.
That class, and the copy of it Core's test framework maintains, carry the
LGPL-2.1 of their python-jsonrpc ancestry, where this is MIT: this is an
implementation of the protocol and shares no line with either.

```python
# AuthServiceProxy
rpc = AuthServiceProxy(f"http://{user}:{password}@127.0.0.1:8332")

# this client
client = BitcoinCoreRpcClient("http://127.0.0.1:8332", user=user, password=password)
```

[docs/source/migrating.md](./docs/source/migrating.md) has the rest, an
`AuthServiceProxy` line at a time with the line that replaces it, for a
caller carrying either Core's copy or python-bitcoinrpc's own.
[COMPARISON.md](./COMPARISON.md) has the case for the switch beyond any
one rewrite, and why the features this client does not have — and the
one, dynamic dispatch, offered differently instead — are decisions rather
than omissions.

## Testing code that calls a node

`transport` is the seam, and it is public for this: a callable taking the
request and a timeout, answering with the HTTP status and the body. The
suite of this project opens no socket, and neither has yours to.

```python
import json


def transport(request, timeout):
    request_id = json.loads(request.data)["id"]
    body = {"jsonrpc": "2.0", "id": request_id, "result": 481824}
    return 200, json.dumps(body).encode()


client = BitcoinCoreRpcClient(
    "http://127.0.0.1:8332", user="u", password="p", transport=transport
)
assert client.call("getblockcount") == 481824
```

What a transport of your own owes, none of which this module can check for
it: its own bound on what it holds in memory while reading, its own bound
on how long it holds the call — most client libraries spend `timeout` per
socket operation, which a peer dripping a body resets forever — no
redirect followed, and its own thread safety.

## Type checking

The source is annotated throughout, `mypy --strict` runs over it here, and
the distribution ships `py.typed` — so your own checker reads those
annotations with no configuration of any kind:

```console
$ mypy --strict your_code.py
your_code.py:4: error: Argument 1 to "call" of "BitcoinCoreRpcClient" has
incompatible type "int"; expected "str"
```

That marker is why `py.typed` sits inside `src/bitcoin_core_rpc/`: PEP 561
puts it inside a package directory and nowhere else. `pyproject.toml`
records what the alternatives were measured to do.

## Security

Basic authentication is cleartext over plain HTTP, that being what Core's
rpc speaks. On loopback that cleartext is between one process and the node
beside it; for a node anywhere else it is on the wire, and rpc credentials
authorise every wallet command that node has. [SECURITY.md](./SECURITY.md)
carries the rest, and how to report a vulnerability.

## Contributing

[CONTRIBUTING.md](./CONTRIBUTING.md) has the commands each CI job runs,
verbatim. `uv sync` creates the environment; uv is the only tool that has
to be installed. [REVIEWING.md](./REVIEWING.md) is what a pull request is
answered against.

## Links

- Documentation: <https://bitcoin-core-rpc.readthedocs.io/>
- Source: <https://github.com/btclib-org/bitcoin-core-rpc>
- Releases: <https://github.com/btclib-org/bitcoin-core-rpc/releases>
- [CHANGELOG.md](./CHANGELOG.md), and [RELEASE_NOTES.md](./RELEASE_NOTES.md)
  for what a release asks a user to act on

---

The btclib organization and its projects are actively supported by
[DGI](https://dgi.io) and [CheckSig](https://checksig.com).
