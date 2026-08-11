# Release notes

Notable changes are documented here.
[CHANGELOG.md](./CHANGELOG.md) is the record behind them: this file says
what a user has to act on, that one says what changed and why.

Versions are *[calendar versions](https://calver.org/)*, `YYYY.M.D`: the
number says when a release was cut, which is the useful thing to know about
a client whose recorded replies come from the Core versions of that month.
It promises nothing about compatibility, so a breaking change is announced
in this file — read it before upgrading, rather than a digit.

## v2026.9 (work in progress, not released yet)

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
