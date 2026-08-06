# Changelog

Every change of a release, in full: what changed, why, and what it cost.
[HISTORY.md](./HISTORY.md) has the release notes, which say what a user has
to act on; this file is the record behind them, and is where a claim in
those notes can be checked.

Neither file counts its entries: `grep -c '^- '` does that, whereas a
stated number is a line every open branch has to edit, and the two files
carry a union merge driver that would keep both sides' numbers.

## v2026.8 (work in progress, not released yet)

The first release.

### Added

- `BitcoinCoreRpcClient`, one Bitcoin Core JSON-RPC endpoint and the
  credentials to reach it. `call` invokes any one method with positional or
  named parameters, `from_chain` builds a client for the local node of one
  of Core's chains from Core's own port and datadir tables, and
  `for_wallet` derives the `/wallet/<name>` endpoint with the name
  percent-encoded.
- JSON-RPC 2.0 with 1.1 read back, so a node older than v28 — which does
  not know the `"jsonrpc": "2.0"` marker and replies 1.1 to it — is
  answered correctly, an rpc error under an HTTP 500 included.
- `FetchError`, `HttpError` and `RpcError`: one exception for a backend
  that did not answer, one for an exchange that failed with a status, one
  for an error the node computed with its code and its `data`. All three
  are `FetchError`, so one `except` catches the lot, and the fields are
  what a caller's own retry policy reads.
- Amounts as `Decimal` in both directions: a number in a reply is parsed
  exactly, a `Decimal` parameter is refused rather than rounded through
  `float`, and `NaN` and `Infinity` are refused either way.
- `cookie_auth` and `DEFAULT_DATADIR`, for the credential bitcoind writes
  and rotates at every restart — read at each call rather than held.
- `core_chain_from_network` and `network_from_core_chain`, the two
  vocabularies written down once: `main` where BIP32 and BIP173 say
  `mainnet`.
- `HttpTransport`, `urlopen_transport` and `http_request`: the seam that
  lets code calling a node be tested without one, and the bounded urllib
  implementation behind it.

### Security

- No credential in the url: a url carrying `user:password@` is refused,
  that string being what ends up in configuration files and tracebacks.
  The class has no generated `__repr__` for the same reason.
- No redirect followed, and no proxy taken from the environment: a request
  already carries the `Authorization` for the host it names, and both
  would send it somewhere else.
- `http` and `https` only, so a url from configuration cannot make this
  read the local disk through `file:`.
- Every response body is read under a bound, `Content-Length` checked
  first and then not believed.

### Repository

- The project standards of btclib-org: the lint gate is
  `.pre-commit-config.yaml` and `lint.yml` runs that very file; every
  action is pinned to a commit SHA; coverage is a 100% ratchet rather than
  a report; `mutation.yml` asks weekly whether a line the suite executes is
  a line the suite checks; `rpc-smoke.yml` asks two live bitcoind versions
  whether the recorded replies are still what Core sends.
- Calendar versioning, `YYYY.M`: a release is named by the month it was
  cut, and what it breaks is read in HISTORY.md rather than inferred from
  the number. The month carries no leading zero, PEP 440 normalizing
  `2026.08` to `2026.8` and `release.yml` comparing the tag to the declared
  string as written.
