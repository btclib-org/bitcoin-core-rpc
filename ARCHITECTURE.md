# Architecture

bitcoin-core-rpc is a JSON-RPC client library that runs inside its
caller's process. This page is its high-level design: the modules, how
they depend on one another, and the properties those dependencies keep.
What a user can expect of it in terms of security is
[SECURITY](./SECURITY.md), and why those expectations hold is the
[assurance case](./ASSURANCE_CASE.md).

## Four modules, one direction

A package of four modules under `src/bitcoin_core_rpc/`, `__init__.py`
itself a facade re-exporting `__all__` rather than defining any of it:
`errors.py` the exception hierarchy every other module raises out of,
`chains.py` the chain and network vocabulary, `transport.py` the urllib
layer, `client.py` the two clients built on the three beneath it. A
module may import any of the ones before it in that order and none of
the ones after — `errors < chains < transport < client` — and none of
the four takes a dependency outside the standard library.
`tests/census_test.py` reads the imports of every source file with
`ast` and holds both the order and the closure, rather than trusting
what ran; CONTRIBUTING.md's *The one constraint* is the rule a
contributor is bound by.

## The transport layer

`transport.py`'s `http_request` and `urlopen_transport` are the only
functions here that open a socket, and they map everything below an
HTTP status onto `FetchError`: what a status *means* is `client.py`'s
question, never the transport's. `HttpTransport` — a callable taking the
built request and a timeout, answering with the status and the body —
is the public seam a caller's own transport implements, and
`urlopen_transport` is the default. `_read_bounded` is what every
transport built here reads a reply through: a deadline taken once,
before the exchange starts, and a loop of bounded chunks rather than one
blocking read, so a body larger than `max_body_size` or slower than
`timeout` is refused instead of held in memory or waited out
indefinitely.

`SessionTransport` is the alternative transport, one connection kept per
`(scheme, host, port)` and reused across calls rather than one socket
per call: a probe before every reuse, and one reconnect where the probe
cannot see the drop, are what let it do that without ever re-sending a
request the node may already be executing — its own docstring is the
argument in full.

Three things a caller cannot get from `HttpTransport`'s own two
arguments, and what `http_request` and `urlopen_transport` each do about
them: only `http` and `https` reach a `Request` (`_SCHEMES`), no proxy is
taken from the environment (`ProxyHandler({})` in the one `_OPENER` this
module builds its I/O with), and no redirect is followed (`_NoRedirect`).
The `Authorization` header is built for one host, so following a 30x
elsewhere, or letting `HTTP_PROXY` redirect the exchange, would send that
credential somewhere the caller never named.

## Two JSON-RPC versions, one client

Core answers JSON-RPC 1.1 by default and 2.0 to a request carrying the
`"jsonrpc": "2.0"` marker; a node older than v28 does not recognize the
marker and answers 1.1 regardless. Under 1.1 an rpc error arrives as the
body of an HTTP 500, so the error is read before the status is judged.
`client.py`'s `_discriminate` picks the shape from the reply's own
`jsonrpc` member, and `_legacy_result` and `_v2_result` are two
functions rather than one with a flag, each reading its own version's
rule for where an error can be found. `BitcoinCoreRpcClient.call` always
sends the 2.0 marker; `call_raw` is the one place a caller controls it,
for a harness testing a server's own conformance.

Every reply is also read against the request that asked for it:
`_reply_object` refuses a body that does not parse as a json object, and
`_id_error` refuses one whose `id` does not match — a caching proxy, or
another call's own answer arriving out of turn, is not read as this
call's result.

## Credentials

`BitcoinCoreRpcClient` takes either a cookie path or a `user`/`password`
pair, never both and never neither — each names who is calling, so a
client given both would have to rank them. `auth_header` builds the
Basic credential at every call rather than once: a cookie path is
re-read through `chains.cookie_auth`, since bitcoind rewrites the file
at every restart, and a client built while the node was up still works
an hour and a restart later. `BitcoinCoreRpcClient` defines no
`__repr__`, because a generated one prints every field, and the
credential would then appear in any traceback or log line that renders
the client. `BitcoinCoreRestClient`, over Core's `-rest` interface,
takes no credential at all — `-rest` authenticates nobody who reaches
it — and shares only the transport and the chain vocabulary with the
JSON-RPC client.

`chains.cookie_auth` reads the cookie file ascii, one line, bounded to
`_MAX_COOKIE_SIZE`: a path that is not a cookie file is the ordinary
mistake, and every failure to read one as such is a `FetchError` naming
the file rather than a raw exception carrying its contents.

## The two clients and `RpcChannel`

`BitcoinCoreRpcClient.call` invokes one rpc method; `call_batch` sends
several in one HTTP exchange and correlates each reply by `id`, a
member's own `RpcError` sitting at its position rather than discarding
every other member's answer; `call_raw` hands back the envelope
unread, for a caller who wants what arrived rather than what `call`
makes of it. `for_wallet` derives a client for a node's `/wallet/<name>`
endpoint, always from the client the wallet client set was built from,
never composing a second wallet segment onto an existing one.
`BitcoinCoreRestClient` is `-rest`'s two shapes, `get_bin` and
`get_json`, over a path the caller builds from Core's own documentation
of the interface: there is no per-resource method, because `-rest`
itself cannot always tell two answers apart — `README.md`'s *Reading
Core's `-rest` interface* has why. `RpcChannel` is attribute-style
sugar over a client's `call`, with a hand-written guard in front of
every name starting with `_` so that `copy.deepcopy` or an interactive
shell probing for a dunder does not turn into an rpc call of that name.

## What proves it, and what a live node adds

`tests/__init__.py`'s `Recorded` is the transport a test passes wherever
a client's call has to answer with something: it answers from bytes
committed under `tests/_data`, recorded from Core itself, and opens no
socket. That is what keeps the suite hermetic and fast, and it is also a
boundary: a recording proves the client reads the shape Core is *known*
to have sent, not that a live node still sends it.

`.github/scripts/rpc_smoke.py` is the other half. Its `--protocol` mode
starts a real bitcoind on a regtest chain it generates itself, and asks
it every question the client answers — the protocol version read off
the wire before the client classifies it, the cookie file at the path
Core's own layout puts it, the `/wallet/<name>` endpoint of a node with
two wallets loaded, and `-rest` against the same chain. Its `--chain`
mode starts a node of any of Core's five chains with no peer reachable
at all and checks only that Core still accepts `-chain=<name>` and
echoes it back. Neither mode lets the node reach the network:
`-listen=0` throughout, and `-connect=0 -dnsseed=0` besides for
`--chain`, regtest alone shipping no seed to connect to or look up.
`.github/workflows/integration-bitcoind.yml` runs it against as many
Core majors as the trigger calls for; what it trusts in bitcoind is
stated where that workflow downloads it: an immutable, versioned
archive fetched over `https` and checked against a `SHA256SUMS` digest
pinned in the workflow itself before anything in the archive is
extracted or run, with a negative control proving the check would fail
a tampered digest.

## The public surface

`__all__` is declared in every module, and it is the union
`__init__.py` re-exports — a name is public because that list says so.
There is no version constant anywhere in the package: the release tag
is the version, which `pyproject.toml`'s own comment on the point
states for the one place the number is written down.
