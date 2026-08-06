# Release notes

Notable changes are documented here.
[CHANGELOG.md](./CHANGELOG.md) is the record behind them: this file says
what a user has to act on, that one says what changed and why.

Versions are *[calendar versions](https://calver.org/)*, `YYYY.M.D`: the
number says when a release was cut, which is the useful thing to know about
a client whose recorded replies come from the Core versions of that month.
It promises nothing about compatibility, so a breaking change is announced
in this file — read it before upgrading, rather than a digit.

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
