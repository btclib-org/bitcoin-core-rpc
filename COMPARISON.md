# RPC client review: AuthServiceProxy vs bitcoin-core-rpc

This document compares a vendored `AuthServiceProxy` — the client a
Bitcoin custody service used until 2026 — with this package, which
replaced it, and records why the replacement is the more robust and
reliable choice for custody operations.

## The candidates

**AuthServiceProxy** was a ~240-line copy of the classic
python-bitcoinrpc client (2011 lineage), vendored into the caller's own
tree. Being vendored, it was maintained there: the caller had to patch
it over the years (e.g. the `socket.timeout` → `TimeoutError`
transition).

**bitcoin-core-rpc** is a standalone JSON-RPC client for Bitcoin Core
by btclib-org, with no dependencies, released in lockstep with btclib.
The caller wraps it in a 15-line attribute-style façade purely for
call-site ergonomics.

## Comparison

<!-- markdownlint-disable MD013 -->

| | AuthServiceProxy (vendored) | bitcoin-core-rpc |
| --- | --- | --- |
| Maintenance | in-repo copy, patched by the caller itself | maintained package, zero dependencies |
| Amounts | `Decimal` on replies; requests serialized through a generic fallback, so a `Decimal` could silently round through `float` | `Decimal` on replies **and** refusal of `Decimal` request parameters rather than rounding them through `float`; `NaN`/`Infinity` refused both ways |
| Credentials | embedded in the URL (`http://user:pass@...`), so they can leak into logs, reprs and exception messages | separate `user`/`password` fields, or first-class cookie authentication (`cookie_path`, `from_chain` with datadir discovery) |
| Errors | `JSONRPCException` wrapping raw error dicts | typed hierarchy: `RpcError` (with `.code` and `.data`, message in `str()`), `HttpError` (with `.status`), `FetchError` for transport failures |
| Timeouts | per-connection only | per-client and **per-call** (`request_timeout`), plus a bounded response size (`max_body_size`) |
| Concurrency | shared mutable request-id counter | `call` writes nothing on the client: one client serves any number of threads |
| Wallet endpoints | URL string concatenation | `for_wallet()` |
| Testability | none | pluggable `HttpTransport` |

<!-- markdownlint-enable MD013 -->

For custody software the decisive rows are the **amount handling**
(exactness enforced by construction, never by discipline), the
**credential hygiene**, and the **typed errors**: branching on
`RpcError.code` (e.g. `-26 non-BIP68-final`) beats parsing an error
dict, and transport failures are cleanly separated from node answers
(`FetchError` vs `RpcError` — note that a refused connection is *not*
an `OSError`: the blockstream broadcast fallback catches both).

## Deliberate non-goals of bitcoin-core-rpc

Reviewing the library for possible upstream improvement requests, the
apparent gaps all turned out to be documented, reasoned design
decisions rather than omissions:

- **no attribute-style dynamic dispatch** (`client.getblockcount()`):
  `call(method, params)` is explicit so that the client's own controls
  (e.g. `request_timeout`) can never collide with an RPC method's
  parameter names. A caller keeps such ergonomics via its own façade,
  which is where that sugar belongs;
- **no JSON-RPC batching**: a named non-goal — a batch API must decide
  how answers are correlated and how partial failures surface; a loop
  over `call` is the documented replacement;
- **one connection per call** (`Connection: close`): keeping
  connections alive would mean a pool, its thread-safety and its
  eviction policy; callers that need it can supply their own
  `HttpTransport`.

Each was then re-examined against the source rather than against its
stated reason. All three hold, on a criterion none of them names: the
file is meant to be copied, so its public API is permanent and its size
is the vendoring caller's audit burden. What is cheap to add downstream
belongs downstream — the façade, the session, the array. Two of the
three stated reasons, however, do not carry what is placed on them, and
three of the supporting statements are narrower than their wording.

### Dynamic dispatch

The collision is a consequence of offering per-call controls, not an
argument against dispatch: `AuthServiceProxy` offers no such controls
and so has no collision. Two other consequences do decide it.

`__getattr__` absorbs typos of the client's own surface, not only of
method names: `client.for_walet("hot")` becomes a request to the node
instead of an `AttributeError`. It also puts the dunder protocol behind
a hand-written guard, without which `copy.copy`, pickling and an
interactive shell's attribute probing each become an rpc request.

And the package ships `py.typed` so that a consumer's type checker
reads its annotations. `__getattr__` returns `Any`, which is what that
marker exists to prevent, in a module that checks at run time that
`method` is a `str`.

The module docstring adds that the named parameter form is one "no
attribute lookup can express". A `**kwargs` façade does express it;
what cannot be expressed is both parameter forms *together with* the
client's controls, which is the collision argument again.

### Batching

Correlation and partial failure are answered normatively by JSON-RPC
2.0 §6 — an array of requests, responses in any order matched by `id`,
an error object in the slot of the member that failed — and the module
already assigns unique ids and already parses one member. The reasons
that decide it are elsewhere.

A batch buys amortisation of the round trip, and the deployment this
client targets is a loopback node, where the round trip is already
close to free. Against that:

- one timeout would cover several node operations. The no-retry rule
  rests on a timeout not being a deadline — the node may still be
  executing — and a batch turns that into an unknown number of executed
  wallet commands, of unknown identity;
- `max_body_size` stops mapping onto an answer: the bound becomes the
  sum of the replies, and a refusal is no longer attributable to a
  member;
- the legacy 1.1 reply shape for a batch is a third parsing branch, to
  be established against Core rather than deduced from the 2.0
  specification, in a module whose parsing is deliberately two
  functions and not one with a flag.

The documented replacement, a loop over `call`, is an equivalent on
loopback and not over a WAN or a TLS link, which is where a batch pays.
Nor is batching reachable through `HttpTransport`, the way keep-alive
is: the transport receives a `Request` whose body is already a single
object. It is reachable through public API all the same —
`http_request` is exported and `auth_header()` is public, so a caller
can POST the array to `client.url` through `client.transport` and match
the replies by `id` — and that route is documented nowhere.

### One connection per call

The header is not this module's choice: CPython's
`urllib.request.AbstractHTTPHandler.do_open` sets `Connection: close`
unconditionally, its comment recording that `addinfourl` cannot hold a
persistent connection. The decision taken was urllib, and a pool with
its thread-safety and its eviction is the cost of leaving urllib for
`http.client` — which is what makes the conclusion right.

Alone among the three, the extension point closes the gap in full. A
caller's transport receives the `Request` before urllib's handler chain
runs, so a `requests` or `httpx` session keeps connections alive with
nothing else changed.

The cost is stated per call, where a loopback connect is negligible. In
aggregate it is socket churn, and the request asks the node to be the
side that closes, so the sockets accumulate in TIME_WAIT there. A
caller polling at a high rate wants a transport of its own on loopback
too, not only over TLS.

### What the re-examination leaves

No upstream issue was filed against the decisions, which stand. Three
statements about them are corrections rather than re-litigation: the
named form that "no attribute lookup can express", the unqualified
"loop over `call` is the replacement", and a per-call cost stated as
costing nothing.

## Verification performed during the migration

- byte-identical parse→serialize roundtrips between btclib's `Psbt`
  and HWI's `PSBT` on real custody psbts (2-input P2WSH multisig with
  `hd_key_paths`), unsigned and signed, including cross-parsing of
  `partial_sigs`;
- the full test suite (73 tests, bitcoind 29.4) against the new
  client, including the broadcast fallback and fee-estimation error
  paths.
