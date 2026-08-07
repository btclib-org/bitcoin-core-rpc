# Release notes

Notable changes are documented here.
[CHANGELOG.md](./CHANGELOG.md) is the record behind them: this file says
what a user has to act on, that one says what changed and why.

Versions are *[calendar versions](https://calver.org/)*, `YYYY.M.D`: the
number says when a release was cut, which is the useful thing to know about
a client whose recorded replies come from the Core versions of that month.
It promises nothing about compatibility, so a breaking change is announced
in this file — read it before upgrading, rather than a digit.

## v2026.8.6.1 (work in progress, not released yet)

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
