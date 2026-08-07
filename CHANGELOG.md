# Changelog

Every change of a release, in full: what changed, why, and what it cost.
[HISTORY.md](./HISTORY.md) has the release notes, which say what a user has
to act on; this file is the record behind them, and is where a claim in
those notes can be checked.

Neither file counts its entries: `grep -c '^- '` does that, whereas a
stated number is a line every open branch has to edit, and the two files
carry a union merge driver that would keep both sides' numbers.

## v2026.8.6.1 (work in progress, not released yet)

### Added

- **`rpc_port_from_chain` and `datadir_subdir_from_chain`**, the port and
  the subdirectory Core gives a chain, which `from_chain` reads and a
  caller could not derive: `main` keeps its cookie in the datadir itself
  and `test` lives under `testnet3`, neither of them a name the chain name
  gives away. A node on another host, or one started with `-datadir=`
  elsewhere, is a url and a `cookie_path` the caller assembles, and these
  two are what it assembles them out of instead of a table copied from
  here. Functions rather than the dicts behind them, for the reason the
  vocabulary pair are functions: an unknown chain is refused where it is
  named, and a published dict is a table a caller can write to.

- **`Chain` and `Network`**, a `Literal` each for the five names of each
  vocabulary, and what `chain_from_network` and `network_from_chain` are
  now annotated as returning. Not what they take: an argument arrives from
  a config file or from `getblockchaininfo`, as a `str` no annotation
  narrows, so a parameter of that type would only mean a cast at the call
  site — the runtime refusal is what checks a name either way. Not an
  `Enum` either: both vocabularies are `str` in every place they are
  spoken, `-chain=` and a json body included, so an enum would be an
  island every caller converts at, and this file has to import on 3.10,
  where `StrEnum` does not exist and the `str, Enum` that stands in for it
  formats as `Chain.MAIN` inside an f-string.

- **`USER_AGENT`**, what `call` now sends as the `User-Agent` header:
  `bitcoin-core-rpc`, where urllib's default named the interpreter and
  identified neither this client nor the program running it. What a node's
  access log and any proxy in front of it record, the request `id` already
  marking the same call in the node's debug log. No version in it, for the
  reason there is none anywhere here -- the release tag is the version,
  and a copied file would carry whichever one it was copied from forever.
  Published so that a caller writing a transport of their own can send the
  same thing.

### Changed

- **three arguments are checked where they are written**, which is
  `_checked_url`'s rule and the three that escaped it. A `transport` that
  is not callable built a client and failed at the first `call`, from
  inside urllib; a `cookie_path` that is no path left through pathlib's
  TypeError about `__fspath__`; a `wallet_name` that is not a string left
  through urllib's about `quote_from_bytes` -- and `for_wallet(b"hot")`
  did not fail at all, `quote` taking bytes, so it built an endpoint from
  a name nobody spelled. Each is a `BtcRpcTypeError` naming the argument
  now.

  `cookie_path` is annotated `str | PathLike[str] | None` with that, where
  it said `Path | str | None`. The runtime check is what `Path()` on the
  next line accepts, and an annotation narrower than the check is the
  disagreement that matters: a `PurePosixPath` worked and a type checker
  said it would not. Widening a parameter breaks no caller -- `Path` is a
  `PathLike[str]` -- and what the attribute holds is a `Path` either way.
- **`for_wallet` builds `type(self)`**, where it named this class. A
  subclass kept its type through `from_chain`, which builds with `cls`,
  and lost it at the one call whose whole subject is carrying this
  client's configuration over.
- **the timeout bounds the whole exchange**, where it bounded each socket
  operation. A socket timeout is reset by every packet, so a peer sending
  one octet just inside it held a call open until `max_body_size` octets
  had arrived -- with the default that is eight megabytes at a byte a
  time, and no number of seconds a caller could write said otherwise.
  `urlopen_transport` takes a `monotonic()` deadline before the connect
  and `_read_bounded` stops at it, so the wait is the timeout plus the one
  recv in flight when it passes. Refused as
  `still arriving when the timeout expired`, a FetchError like the other
  ways an exchange does not produce an answer. What it costs is a reply
  that legitimately takes longer than the timeout to arrive -- a large
  `getblock` over a slow link -- and `request_timeout` is what that call
  passes.

  The read is `read1` and not `read`, which is the half without which the
  deadline is decoration: the response reads through a `BufferedReader`,
  whose `read(n)` blocks until it holds *n* octets, so the whole drip
  happened inside one call and no check ran between packets. Measured
  against a server sending an octet every 0.3s under a one-second timeout:
  the `read` spelling returned only when that server stopped, the `read1`
  one at the deadline. `FakeResponse` in the tests answers the two calls
  differently for the same reason -- a fake whose `read` returned early
  cannot tell a bounded read from an unbounded wait.

  Two bounds are unchanged, and deliberately. A caller's own transport
  gets no deadline: two positional arguments have nowhere to carry one,
  and `HttpTransport`'s comment lists this with the rest of what such a
  transport owes. And the body of a *failure*, which `http_request` reads
  off the `HTTPError`, is still bounded by `MAX_ERROR_BODY_SIZE` and by
  the socket timeout alone -- a drip there is 64 KiB of diagnostic rather
  than eight megabytes of answer, and threading the deadline into that
  path is a change to the exception handling rather than to the read.
- **a refusal on size names `max_body_size`**, in all three places one is
  raised, where they said `more than the 8001024 allowed` and left the
  reader to find which knob carried that number.
- **`core_chain_from_network` and `network_from_core_chain` are
  `chain_from_network` and `network_from_chain`.** In this module `chain`
  is Core's vocabulary and `network` the BIP one -- `from_chain` is named
  for it, and so are the parameters of both functions -- so `core_` was
  spelling a distinction the names around it already carry. What it costs
  is a rename in a caller: the old names are gone rather than aliased, one
  release being a short enough life for a name that a second spelling of
  it is the worse thing to publish.
- **an unknown chain is refused as `unknown Core chain`** wherever it is
  refused, `from_chain` included, where that one said `unknown chain: ...
  These are Core's names, not the BIP ones`. The check there is now
  `rpc_port_from_chain`'s, so the three functions a chain name reaches say
  the same thing, and the three words say what the sentence did.
- **the class docstring says that a call opens its own connection.**
  urllib holds none, so every `call` sends `Connection: close` and
  connects again. Beside the node that is loopback and costs nothing; to a
  node over `https` it is a TLS handshake each time, which is a caller
  polling one in a loop wanting a `transport` of their own. Documented and
  not fixed: keeping a connection alive means a pool, its own
  thread-safety and its own eviction, none of which one bounded request
  needs, and `HttpTransport` is the seam a caller who wants all three
  already has.

### Tests

- **the five chains are checked against every table that takes one.** They
  are written down four times -- a port, a datadir subdirectory, a network
  name and a `Literal` each way -- and only the `Literal`s failed anything
  when one was forgotten, at a type check rather than here. A port with no
  subdirectory beside it derives a cookie path under a directory that is
  not the node's.

### Repository

- **RELEASING.md asks griffe whether the breaking-change list is
  complete**, as a release step carrying the command. HISTORY.md promises
  that a break is announced there, the calendar version promising nothing,
  and until now nothing read that promise back: the suite judges the code,
  and review weighs what the notes say rather than what they leave out.
  griffe reads the public API at the previous release and at the tree and
  reports the breakage between them -- against v2026.8.6 it names
  `core_chain_from_network` and `network_from_core_chain`, which this cycle
  removed and HISTORY.md announces, so the first cycle the step applies to
  is one it passes. A step and not a hook, for the reason RELEASING.md
  gives: the comparison is against the previous *release*, so a deliberate
  break stays a finding until the release that announces it, leaving every
  pull request in between red for something no branch introduced.

## v2026.8.6

The first release.

### Added

- **the distribution ships `py.typed`**, so a consumer's type checker reads
  these annotations with no configuration at all. That marker has to sit
  inside a package directory, which is why the source is
  `bitcoin_core_rpc/__init__.py`: measured against a built wheel of each
  layout, a top-level module leaves `mypy --strict` reporting "missing
  library stubs or py.typed marker" and treating every name as `Any` --
  and a `py.typed` or a `.pyi` placed beside such a module changes
  nothing, mypy looking for the marker under `<module>/`. What it costs is
  that vendoring is now a copy *and a rename*, which the module docstring
  and the README both say.

### Changed

- **`BTClibValueError`, `BTClibTypeError` and `BTClibRuntimeError` are
  `BtcRpcValueError`, `BtcRpcTypeError` and `BtcRpcRuntimeError`.** The old
  names were this file's while it lived inside btclib, and btclib declares
  three of its own spelled exactly that way -- so a consumer holding both
  had two same-named classes and an `except BTClibValueError` that reads
  correct at every call site while being the wrong one at some of them.
  btclib hit that taking the dependency, in an `except` around a function
  of this module. Nothing catches these names inside this package, so the
  change is a rename; nothing has shipped, so no caller has to act.
- **a request id is prefixed `btcrpc-`**, where it said `btclib-`. The
  prefix reaches a node's `debug.log`, and naming a library the caller may
  not be using was a claim this package had no business making.

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
  what a caller's own retry policy reads. `HttpError` and `RpcError` hand
  every constructor argument to `BaseException.__init__` and compose their
  message in `__str__`, which is what makes them picklable —
  `BaseException.__reduce__` rebuilds an exception from `self.args`, and a
  class carrying two or three fields is not rebuilt by calling it with the
  one composed string those two used to leave in `args` — and what a
  `ProcessPoolExecutor` needs to send one back from a worker rather than
  report the pool broken.
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
- Calendar versioning, `YYYY.M.D`: a release is named by the day it was
  cut, and what it breaks is read in HISTORY.md rather than inferred from
  the number. The month carries no leading zero, PEP 440 normalizing
  `2026.08` to `2026.8` and `release.yml` comparing the tag to the declared
  string as written. `release.yml`'s version-check job also refuses a tag
  with fewer than three components: without it a tag naming only the
  month, `v2026.8`, would pass every other check and publish a version
  indistinguishable from the placeholder `pyproject.toml` declares between
  releases, which names the same month and is never tagged.
- `.github/scripts/rpc_smoke.py` restructured for `tests/rpc_smoke_test.py`
  to cover: every function with no live node behind it —
  `check`, `port_is_free`, `check_legacy_reply`, `check_v2_reply`,
  `check_cookie`, `print_log_tail`, and `main`'s own argument parsing —
  now has a test with no `bitcoind` in the loop, and every function that
  does talk to one carries `# pragma: no cover`, that half staying
  `rpc-smoke.yml`'s to monitor against Core itself.
- `mutation.yml`'s session runs under `timeout --signal=INT` rather than
  the default SIGTERM, with a `git diff --quiet` check afterwards that
  restores the tracked source if anything is left changed. The local
  distributor applies a mutant and restores it from a `finally` block that
  only runs if the process can unwind; SIGTERM kills it outright,
  mid-mutant, before that block runs, where SIGINT is what Python turns
  into a catchable `KeyboardInterrupt`. A session cut at its budget could
  otherwise leave `bitcoin_core_rpc.py` mutated for whatever ran next.
- The MIT permission notice in full at the head of every source file, and
  `COPYRIGHT` — the text a hook requires them all to carry — is that notice
  rather than a pointer to `LICENSE`: `bitcoin_core_rpc.py` is meant to be
  copied out, and a copy has no `LICENSE` beside it to point at. No year in
  it, so a vendored copy nobody has touched does not look out of date every
  January.
