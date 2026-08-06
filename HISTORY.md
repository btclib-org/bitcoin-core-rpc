# Release notes

Notable changes are documented here.
[CHANGELOG.md](./CHANGELOG.md) is the record behind them: this file says
what a user has to act on, that one says what changed and why.

Versions follow *[semantic versioning](https://semver.org/)*, pre-1.0: a
breaking change moves the minor.

## v0.1.0 (work in progress, not released yet)

The first release. There is nothing to act on and nothing to migrate.

`pip install btclib-bitcoin-core-rpc`, or copy `bitcoin_core_rpc.py` — one
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
