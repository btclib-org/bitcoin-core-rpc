# AuthServiceProxy and bitcoin-core-rpc

What differs between the two clients, row by row, and why the two features
`BitcoinCoreRpcClient` does not have are decisions rather than omissions --
plus a third case, dynamic dispatch, decided the other way from
`AuthServiceProxy`'s. The README's ["Migrating from
`AuthServiceProxy`"](./README.md#migrating-from-authserviceproxy) is the
line-by-line rewrite; this is the case for doing it.

## The two clients

**AuthServiceProxy** is python-bitcoinrpc's client, along with the copy
Bitcoin Core's test framework maintains. Both carry the LGPL-2.1 of their
python-jsonrpc ancestry, and both are normally vendored — copied into the
caller's own tree, which makes the copy the caller's to maintain.

**bitcoin-core-rpc** is a standalone JSON-RPC client for Bitcoin Core,
MIT licensed, with no dependencies, released in lockstep with btclib. It
is an implementation of the protocol rather than a translation of that
one, and shares no line with either.

## Comparison

<!-- markdownlint-disable MD013 -->

| | AuthServiceProxy (vendored) | bitcoin-core-rpc |
| --- | --- | --- |
| Maintenance | in-repo copy, the caller's to patch | maintained package, zero dependencies |
| Amounts | `Decimal` on replies; requests serialized through a generic fallback, so a `Decimal` could silently round through `float` | `Decimal` on replies **and** refusal of `Decimal` request parameters rather than rounding them through `float`; `NaN`/`Infinity` refused both ways |
| Credentials | embedded in the URL (`http://user:pass@...`), so they can leak into logs, reprs and exception messages | separate `user`/`password` fields, or first-class cookie authentication (`cookie_path`, `from_chain` with datadir discovery) |
| Errors | `JSONRPCException` wrapping raw error dicts | typed hierarchy: `RpcError` (with `.code` and `.data`, message in `str()`), `HttpError` (with `.status`), `FetchError` for transport failures |
| Timeouts | per-connection only, and spent per socket operation, which a peer dripping a body resets forever | per-client and **per-call** (`request_timeout`), bounding the whole exchange — answer and error page alike — plus a bounded response size (`max_body_size`) |
| Concurrency | shared mutable request-id counter | `call` writes nothing on the client: one client serves any number of threads |
| Wallet endpoints | URL string concatenation | `for_wallet()` |
| Testability | none | pluggable `HttpTransport` |

<!-- markdownlint-enable MD013 -->

Three rows carry the weight — amounts, credentials and errors — because
they are the ones where the difference is enforced by construction rather
than left to discipline. Branching on `RpcError.code` (`-26` for a policy
rejection, `-5` for a transaction the node cannot find) is a test on a
field rather than a match on the text of a message, and a backend that
did not answer is a different exception from an error the node computed.

That taxonomy has one consequence nothing announces. A refused connection
reaches `AuthServiceProxy`'s caller as `ConnectionRefusedError`, an
`OSError`; here `http_request` converts it, and `FetchError` derives from
`RuntimeError`. An `except OSError` written for a node that is down
therefore stops matching, and stops matching silently: the original is
kept as `__cause__`, so the diagnosis survives and it is only the
`except` clause that is wrong. A path that falls back to some other
service when the node does not answer needs both names — `FetchError`
for this client, `OSError` for whatever in that path does its own I/O.
The same conversion is what stops the standard library reaching the
caller at all: `socket.timeout` becoming an alias of `TimeoutError` is a
change a vendored `AuthServiceProxy` hands to whoever holds the copy, and
one this client absorbs.

## Non-goals

Two features are absent by decision, on a criterion common to both:
`__all__` is the public surface this package publishes, and a name added
to it is a name kept forever. What is cheap to add downstream belongs
downstream — the session, the array. A third, dynamic dispatch, looks like
the same case and is not: see below for why it is offered rather than left
to a caller's own code.

### Dynamic dispatch

`BitcoinCoreRpcClient.call(method, params)` stays explicit: an unknown
attribute is an `AttributeError` on the client itself, not a request —
`client.for_walet("hot")` a typo caught at the call rather than one more
method name sent to the node. That does not change.

What changes is that the sugar, `client.getblockcount()`, is now offered
as `RpcChannel`, wrapping a client rather than replacing its surface. Not
downstream, and not because a caller could not write `__getattr__`
themselves: two things about it are this package's to get right, not a
caller's own code to rediscover.

`call`'s own keyword-only controls — `request_timeout` and
`max_body_size` today — have to be excluded from `params` rather than
sent to the node as a named argument, and that list belongs to `call`,
not to whoever wraps it: a façade written against one release is silently
wrong against a later one that adds a third control, forwarding it to
Core instead of catching it, and neither mypy nor a test says so. Kept
here, the exclusion list and the method it excludes from are one change
instead of two.

The dunder protocol needs the guard `__getattr__` always needs, and needs
it exactly, not approximately: without it, `copy.copy` and `copy.deepcopy`
each turn into a bound call for `__setstate__` or `__deepcopy__` — verified
by calling both against a transport that raises on any request, not
assumed — and an interactive shell probing for `_repr_html_` becomes one
more name `RpcChannel` would otherwise treat as a method. `RpcChannel`
still returns `Any` for the same reason `call` does: no attribute lookup
carries a per-method parameter type, so a caller who wants one keeps
`call` and its explicit `params`.

### Batching

One call is one HTTP request. Correlation and partial failure are not
what makes a batch a non-goal: JSON-RPC 2.0 §6 settles both — an array of
requests, responses in any order matched by `id`, an error object in the
slot of the member that failed — and this module already assigns unique
ids and already parses one member.

What a batch buys is amortisation of the round trip, and the deployment
this client targets is a loopback node, where the round trip is already
close to free. Against that:

- one timeout would cover several node operations. A timeout is not a
  deadline, the node may still be executing, so a batch turns "this call
  may have run" into an unknown number of executed wallet commands, of
  unknown identity;
- `max_body_size` stops mapping onto an answer: the bound becomes the sum
  of the replies, and a refusal is no longer attributable to a member;
- the legacy 1.1 reply shape for a batch is a third parsing branch, to be
  established against Core rather than deduced from the 2.0
  specification, in a module whose parsing is deliberately two functions
  and not one with a flag.

A loop over `call` is the equivalent on loopback. Over a WAN or a TLS
link, where a round trip costs something, it is not — and batching is not
reachable through `HttpTransport` the way keep-alive is, that transport
receiving a `Request` whose body is already a single object. It is
reachable through public API all the same: `http_request` is exported and
`auth_header()` is public, so a caller can POST the array to `client.url`
through `client.transport` and match the replies by `id`.

### One connection per call

`Connection: close` is not this module's choice. CPython's
`urllib.request.AbstractHTTPHandler.do_open` sets it unconditionally, its
comment recording that `addinfourl` cannot hold a persistent connection.
The decision taken was urllib, and a pool with its thread-safety and its
eviction is the cost of leaving urllib for `http.client`.

Alone among the three, the extension point closes this gap in full: a
caller's transport receives the `Request` before urllib's handler chain
runs, so a `requests` or `httpx` session keeps connections alive with
nothing else changed.

Per call a loopback connect is negligible. In aggregate it is socket
churn, and the request asks the node to be the side that closes, so the
sockets accumulate in TIME_WAIT there — which is why a caller polling at
a high rate wants a transport of its own on loopback too, and not only
over TLS.
