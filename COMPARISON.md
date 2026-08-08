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

Since each candidate improvement is already addressed by a documented
decision with an extension point, no upstream issue was filed:
re-litigating documented choices without new evidence would add noise,
not value.

## Verification performed during the migration

- byte-identical parse→serialize roundtrips between btclib's `Psbt`
  and HWI's `PSBT` on real custody psbts (2-input P2WSH multisig with
  `hd_key_paths`), unsigned and signed, including cross-parsing of
  `partial_sigs`;
- the full test suite (73 tests, bitcoind 29.4) against the new
  client, including the broadcast fallback and fee-estimation error
  paths.
