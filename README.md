# bitcoin-core-rpc

A standalone JSON-RPC client against Bitcoin Core.

[![Lint](https://github.com/btclib-org/btclib-bitcoin-core-rpc/actions/workflows/lint.yml/badge.svg)](https://github.com/btclib-org/btclib-bitcoin-core-rpc/actions/workflows/lint.yml)
[![Test](https://github.com/btclib-org/btclib-bitcoin-core-rpc/actions/workflows/test.yml/badge.svg)](https://github.com/btclib-org/btclib-bitcoin-core-rpc/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/bitcoin-core-rpc.svg)](https://pypi.org/project/bitcoin-core-rpc/)
[![Python](https://img.shields.io/pypi/pyversions/bitcoin-core-rpc.svg)](https://pypi.org/project/bitcoin-core-rpc/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

One source file with nothing but the standard library behind it, fully
annotated and shipping `py.typed`. `BitcoinCoreRpcClient` invokes any one
rpc method a node has, with positional or named parameters: one HTTP POST
per call, basic authentication, the result or an exception.

Install it, or copy the file — [Vendoring](#vendoring) below is how, and it
is a supported way to use this rather than a fallback.

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
an hour and a restart later. Where the datadir is somewhere else — macOS
and Windows put it outside `~/.bitcoin` — say so:

```python
from pathlib import Path

client = BitcoinCoreRpcClient(
    "http://127.0.0.1:8332",
    cookie_path=Path.home() / "Library/Application Support/Bitcoin/.cookie",
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
balance = client.for_wallet("hot").call("getbalance")   # Decimal, exact
```

`for_wallet` is the `/wallet/<name>` endpoint of a node with several
wallets loaded, with the name percent-encoded — a wallet is a directory and
may be called anything a filesystem accepts.

## When it goes wrong

Three exceptions, because there are three different things to do about
them. All three are `FetchError`, so one `except FetchError` covers the
lot.

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
    if e.code == -5:        # no such transaction; a node without -txindex
        ...                 # answers this for anything outside its wallet
except HttpError as e:
    if e.status == 503:     # the rpc work queue is full: try again later
        ...                 # a 401 never works again, so tell the two apart
except FetchError:
    ...                     # refused connection, expired timeout, no answer
```

There is no retry, and it is deliberate: `call` carries any method, so this
client cannot know whether re-sending one is safe, and a timeout is not a
deadline — a node that stopped answering may still be executing the call.
`HttpError.status` is what makes a caller's own policy three lines rather
than a match on the text of a message.

## What it does not do

- **batches.** One call is one HTTP request. A batch needs an api for
  correlating the answers and for partly failing, which is a question of
  its own; a loop over `call` is the replacement.
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
implementation of the protocol and shares no line with either. Migrating
from it is four changes, and the module docstring spells each of them out.

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
it: its own bound on what it holds in memory while reading, no redirect
followed, and its own thread safety.

## Type checking

The source is annotated throughout, `mypy --strict` runs over it here, and
the distribution ships `py.typed` — so your own checker reads those
annotations with no configuration of any kind:

```console
$ mypy --strict your_code.py
your_code.py:4: error: Argument 1 to "call" of "BitcoinCoreRpcClient" has
incompatible type "int"; expected "str"
```

That marker is why the source is `bitcoin_core_rpc/__init__.py` and not a
top-level module: PEP 561 puts it inside a package directory and nowhere
else. `pyproject.toml` records what the alternatives were measured to do.

## Vendoring

Copy `bitcoin_core_rpc/__init__.py` whole from a release tag, **rename it
to `bitcoin_core_rpc.py`**, keep the license notice at the top of it — MIT,
embedded rather than referenced, because a copy has no `LICENSE` beside it
— and record the tag next to the copy. An update is a replacement of the
whole file, and this shows every behavioral change first:

```shell
git diff OLD..NEW -- bitcoin_core_rpc/__init__.py
```

A vendored copy receives no security or compatibility fix automatically, so
its recorded tag is what says whether it needs replacing. An installed one
is a version an ordinary dependency bump moves, which is why installing is
the default advice.

## Security

Basic authentication is cleartext over plain HTTP, that being what Core's
rpc speaks. On loopback that cleartext is between one process and the node
beside it; for a node anywhere else it is on the wire, and rpc credentials
authorise every wallet command that node has. [SECURITY.md](./SECURITY.md)
carries the rest, and how to report a vulnerability.

## Contributing

[CONTRIBUTING.md](./CONTRIBUTING.md) has the commands each CI job runs,
verbatim. `uv sync` creates the environment; uv is the only tool that has
to be installed.

## Links

- Documentation: <https://bitcoin-core-rpc.readthedocs.io/>
- Source: <https://github.com/btclib-org/btclib-bitcoin-core-rpc>
- Releases: <https://github.com/btclib-org/btclib-bitcoin-core-rpc/releases>
- [CHANGELOG.md](./CHANGELOG.md), and [HISTORY.md](./HISTORY.md) for what a
  release asks a user to act on
