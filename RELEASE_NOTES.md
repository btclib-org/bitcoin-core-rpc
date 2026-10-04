# Release notes

Notable changes are documented here.
[CHANGELOG.md](./CHANGELOG.md) is the record behind them: this file says
what a user has to act on, that one says what changed and why.

Versions are *[calendar versions](https://calver.org/)*, `YYYY.M.D`: the
number says when a release was cut, which is the useful thing to know about
a client whose recorded replies come from the Core versions of that month.
It promises nothing about compatibility, so a breaking change is announced
in this file — read it before upgrading, rather than a digit.

## v2026.10 (work in progress, not released yet)

- **Verifying a release's attestation names a new signer and the tag.**
  `gh attestation verify` takes
  `--signer-workflow btclib-org/.github/.github/workflows/reusable-build.yml@refs/heads/main`
  and `--source-ref refs/tags/v<version>`; SECURITY.md has the command.
  SECURITY.md names the signer of an earlier release.
- **A url the client refuses is no longer repeated in the message
  (issue #575).** Upgrade; a caller matching on the refusal text sees no
  url, and `expected http(s)` where the scheme was named.
- **A reply number with an exponent past `sys.get_int_max_str_digits` is a
  `FetchError` (issue #576).** Raise the limit with
  `sys.set_int_max_str_digits` if a node legitimately sends one; 0 lifts it.
- **`str()` of an `RpcError` writes non-printable characters of the node's
  message as escapes (issue #577).** Read `args[0]` for the text as it
  arrived.
- **A `cookie_path` that is not a regular file is a `FetchError`**, a
  pipe that would deliver a cookie included (issue #579): point it at a
  file.
- **The TLS key log is never written (issue #580).** `SSLKEYLOGFILE` is
  ignored by both transports. `SSL_CERT_FILE` and `SSL_CERT_DIR` still
  choose the trust store. A program that replaces
  `ssl._create_default_https_context` to turn verification off finds it
  ignored: verification stays on, and such a caller passes a `transport`
  of its own, as does one that must not honour the two variables. On
  Python 3.11 and 3.12 a server certificate OpenSSL judges malformed
  (`VERIFY_X509_STRICT`) is refused, as on 3.13 and later; a node behind
  such a certificate needs the certificate replaced.
- **A malformed header or url is a `BtcRpcValueError` (issue #578).**
  `http_request` refuses a header name that is not a token and a value
  with a CR, LF, NUL or a character latin-1 cannot encode; the client
  refuses a url with whitespace, control characters or a malformed IPv6
  host when it is built. Both are `BtcRpcValueError`, a `ValueError`, so a
  caller catching the `ValueError` `http.client` raised for a header needs
  no change.
- **The transports do not repeat a malformed url (issue #616).**
  `http_request`, `urlopen_transport` and `SessionTransport` refuse a url
  with whitespace or a control character, no host, a port that is no
  number, or a login, as `BtcRpcValueError`, and an error names
  `scheme://host[:port]` and not the path or query. A caller that read the
  full url from a `FetchError` reads the host there and keeps its own copy
  of the rest. A credential goes in an `Authorization` header.
- **A url with a non-ASCII character is a `BtcRpcValueError` (issue
  #619).** The client, `http_request` and the two transports refuse it, a host
  included: write an internationalized host in its ASCII form, for
  example `xn--bcher-kva.example` for `bücher.example`.

## v2026.9.29

Python 3.10 is no longer supported: `requires-python` is `>=3.11`. On 3.10
an installer resolves to v2026.9.24, the last release that runs there;
staying current means moving to 3.11 or later.

`SessionTransport` no longer sends a request a second time when a kept
connection closes after the request was written: that is a `FetchError`
like any other failure of the exchange, and a caller that wants an
idempotent call retried on it writes that retry.

`SessionTransport(max_body_size=...)` is a `TypeError`: the limit is each
call's own `max_body_size`, which now reaches the session's read as it
reaches the default transport's.

## v2026.9.24

Nothing to act on: the module is the one v2026.9.3 shipped, and its
public surface did not move.

The GitHub release now carries a CycloneDX bill of materials,
`bitcoin_core_rpc-2026.9.24.cdx.json`, attested with the distribution
files. Its `components` list is empty, this distribution declaring no
dependency.

## v2026.9.3

Nothing to act on: both additions to the public surface are opt-in.

`BitcoinCoreRestClient` reads Core's `-rest` interface — `get_bin` for a
`.bin` path, `get_json` for a `.json` one, no credentials, sharing only
the transport and the chain vocabulary with `BitcoinCoreRpcClient`.
`errors.py` gains `RPCErrorCode`, an `IntEnum` naming Core's own error
codes; `RpcError.code` stays a plain `int`, so nothing that already
reads it changes.

## v2026.8.29

`bitcoin_core_rpc` is now a package of four modules —
`errors.py`, `chains.py`, `transport.py`, `client.py` — behind an
`__init__.py` that still answers every name `import bitcoin_core_rpc` did
before. Nothing in the public surface moved, so `pip install` or a
dependency bump is the whole of what this asks of you. If you took a copy
of the old single file rather than installing it, that copy is now the
only channel it will keep working through: this release is not a file to
replace it with.

Every public exception's qualified name gained `.errors` in it — a
traceback now reads `bitcoin_core_rpc.errors.RpcError`, not
`bitcoin_core_rpc.RpcError`. `except RpcError`, `isinstance` and
unpickling all match on the class itself and do not see the difference;
a log line or a test asserting the name as text does.

## v2026.8.20

Nothing to act on. Every change this cycle is repository tooling —
workflows and CI configuration, recorded in
[CHANGELOG.md](./CHANGELOG.md) — and the library itself is unchanged
since v2026.8.13.

## v2026.8.13

`from_chain("signet", verify_chain=True)` now holds the node to the
*default* signet, where it accepted any node answering `signet`. Core
reports that one string for every signet there is, so the old check passed
for a node on somebody else's chain. If that is your case, pass the
challenge you mean: `from_chain("signet", verify_chain=True,
signet_challenge=...)`, hex or bytes, as `-signetchallenge` takes it. The
comparison is of the p2p magic the challenge derives, so upper case and
lower case are the same challenge.

Two things are refused that were previously accepted, both of them a check
that would not be made: a `signet_challenge` with `verify_chain` off, and
one for a chain that is no signet. Both are `BtcRpcValueError` at the call,
before a client is built or a node is reached.

`assert_chain(chain, signet_challenge=...)` is that check as a method, for
a client built against an explicit url — a node on another host, or behind
a proxy — where `from_chain` was the only way to get it. Nothing to do if
you already call `from_chain(verify_chain=True)`: that is now this method.

## v2026.8.12

`from_chain` works on macOS and Windows. `default_datadir` answers Core's
own datadir for the platform it runs on — `%APPDATA%\Bitcoin` on Windows,
`~/Library/Application Support/Bitcoin` on macOS, `~/.bitcoin` on
everything else — where it answered the last of those everywhere, so on the
first two the derived cookie path was one no node writes and every bare
`from_chain()` failed with a "no such file" that reads as a node that is
down. Nothing to do to get the fix, and a caller passing `cookie_path` or
`user`/`password` is untouched: that path is derived only when neither was
given. What to check is a macOS or Windows setup that was made to agree
with the old answer — a node started with `-datadir=~/.bitcoin` there, or a
symlink standing in for one. It is still reachable, by the `cookie_path`
that setup no longer needs to be a workaround for.

`from_chain`'s refusal when there is no directory to derive from names
`APPDATA` now, that being the Windows base and one an environment can
simply not have. Only its wording changed; it is the same
`BtcRpcValueError`, for the same reason, and still names `cookie_path` as
the answer.

A cookie file that is not there raises `CookieNotFoundError` now, with the
message `no rpc cookie file <path>: bitcoind writes one while it runs with
its rpc server enabled`. It is a `FetchError`, so `except FetchError`
catches it as before; code matching on the text has one to update, the case
previously arriving as `unreadable rpc cookie file <path>: [Errno 2] No
such file or directory`. Everything else at that path — a directory, a mode
that excludes this user, a file that is no cookie — keeps the
`unreadable` message and the plain `FetchError`, that being a file to go and
look at where an absent cookie is a node to start.

`cookie_path_from_chain(chain, datadir)` is what derives such a path: the
datadir, the chain's subdirectory and `.cookie`, which `from_chain` builds
its own with. Use it instead of assembling the path by hand wherever
`from_chain` does not do it for you — a node started with `-datadir=`
somewhere else, or one reached at a url of your own, which is the
constructor and derives nothing.

`for_wallet` on a client that is already a wallet endpoint raises
`BtcRpcValueError` now, where it appended a second one and built
`/wallet/hot/wallet/cold` — a path no node serves, so the call that used it
failed at the node. Derive every wallet's client from the client built for
the node: `node.for_wallet("hot")` and `node.for_wallet("cold")`, not
`node.for_wallet("hot").for_wallet("cold")`. A url passed to the constructor
ending in `/wallet/<name>` is refused by the same check — pass the node's
endpoint and let `for_wallet` add the wallet. A wallet named `wallet` is
unaffected: that is a name to add, not one already added.

The repository's default branch is `main`, and it is the only one: `master`
was renamed to it and `dev` is gone. GitHub redirects the old links and
retargets open pull requests, so nothing breaks on its own; a clone follows
with `git fetch origin && git remote set-head origin -a`, and a branch
still based on `dev` is rebased onto `main`. The upstream url in the module
docstring — the one a vendored copy is asked to record beside itself —
names `main`, and the repository name this one was renamed from is
corrected with it.

## v2026.8.8

The body of a failure is bounded by `timeout` now, not only by
`MAX_ERROR_BODY_SIZE` and the socket's own per-`recv` timeout. A peer
answering with an error page that keeps sending, one octet inside that
per-packet limit at a time, no longer holds the call for as long as the
page takes to trickle in; it fails at the deadline instead, the way an
answer already did.

`http_request`'s own `timeout` is refused now where it used to reach the
socket layer unexamined: a `0`, a negative number, `True` or a `NaN`
raises `BtcRpcTypeError` or `BtcRpcValueError` here, the same refusal
`BitcoinCoreRpcClient` already gave its own `timeout` and
`request_timeout`. Only a caller passing a `transport` of their own
straight to `http_request` reaches this — `BitcoinCoreRpcClient` never
forwarded a bad one to begin with.

## v2026.8.7

The timeout now bounds the whole exchange rather than each socket
operation, so a call cannot outlive it by waiting on a peer that keeps
sending. If you fetch replies large enough to take longer than the timeout
to arrive — a big `getblock` over a slow link — raise `request_timeout`
for those calls; they would previously have succeeded under a timeout that
did not cover them.

Requests carry `User-Agent: bitcoin-core-rpc`, where they carried urllib's
`Python-urllib/3.x`. Anything filtering or logging by user agent in front
of a node — a reverse proxy, a WAF rule — sees the new string.

Three arguments are refused now where they used to fail later or not at
all: a `transport` that is not callable, a `cookie_path` that is no path,
and a `wallet_name` that is not a string. Each raises `BtcRpcTypeError` at
the call that supplied it. The one to check for is
`for_wallet(b"hot")` — bytes built an endpoint before, from a name that
was never spelled that way, and is refused now.

Code matching on the text of a size refusal has three to update: they name
`max_body_size` now, as `more than the max_body_size of 8001024` rather
than `more than the 8001024 allowed`.

Two exported functions are renamed, with no alias left behind:
`core_chain_from_network` is `chain_from_network` and
`network_from_core_chain` is `network_from_chain`. They take and return
what they always did.

Code matching on the text of an error has one more to check: an unknown
chain is now refused as `unknown Core chain: ...` everywhere, including
`BitcoinCoreRpcClient.from_chain`, which said `unknown chain: ...`.

## v2026.8.6

The first release. There is nothing to act on and nothing to migrate.

`pip install bitcoin-core-rpc`, or copy `bitcoin_core_rpc/__init__.py` — one
source file with nothing but the standard library behind it, which is what
makes the second option a supported one rather than a fallback.

If you are coming from python-bitcoinrpc's `AuthServiceProxy`, or from the
copy of it Bitcoin Core's test framework maintains, this is not a drop-in
replacement and does not try to be. Four things change, and the module
docstring spells each of them out with the reason:

- a method is an argument, not an attribute
- credentials leave the url
- `JSONRPCException` becomes three exceptions
- `batch_` has no equivalent; a loop over `call` is the replacement
