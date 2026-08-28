# AuthServiceProxy and bitcoin-core-rpc

What differs between the two clients, row by row, and why three cases —
dynamic dispatch, batching, a kept connection — are each a decision
`BitcoinCoreRpcClient` took rather than left to a caller's own code. The
README's ["Migrating from
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

`__all__` is the public surface this package publishes, and a name added
to it is a name kept forever — the cost weighed against each of the three
cases below before it was offered rather than left to a caller's own
code: dynamic dispatch as `RpcChannel`, batching as `call_batch`, a kept
connection as `SessionTransport`. Each subsection argues what a caller's
own version of it would have gotten wrong that this package gets right
once. [README.md's *What it does not
do*](./README.md#what-it-does-not-do) is where this project's actual
non-goals are: notifications, retries, redirects, and a proxy read from
the environment.

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

`call_batch` sends several `(method, params)` pairs in one HTTP POST and
reads each member's reply the way `call` reads its own: JSON-RPC 2.0 §6's
own rule — an array of requests answered by an array of responses in any
order, matched by `id`, an error object in the slot of the member that
failed — is what this module already had the pieces for, a unique id per
request and one function reading one reply object.

That last part is what had stood against it: reusing `_reply_object` and
the version discrimination behind it, per member, is what makes a batch
member's reply no different a thing to parse than a lone call's, so
there is no third parsing branch, legacy-1.1-shaped or otherwise, to
establish against a live node first. The other two costs a batch weighs
were real and stay real — they do not disappear, they move to the
caller reaching for `call_batch` over a loop of `call`, and its own
docstring is where they are named for that caller:

- one timeout now covers several node operations. A timeout is not a
  deadline, the node may still be executing, so `request_timeout` on a
  batch turns "this call may have run" into an unknown number of
  executed wallet commands, of unknown identity;
- `max_body_size` no longer maps onto one answer: the bound is the sum
  of every member's reply, and a refusal is no longer attributable to
  one of them.

A batch amortises the round trip, and the deployment this client targets
is a loopback node, where the round trip is already close to free — a
loop over `call` costs the same there. It is over a WAN or a TLS link,
where a round trip costs something, that `call_batch` is the one worth
reaching for.

### One connection per call

`Connection: close` is not this module's choice for its default
transport. CPython's `urllib.request.AbstractHTTPHandler.do_open` sets it
unconditionally, its comment recording that `addinfourl` cannot hold a
persistent connection.

`SessionTransport` is what this module ships instead of leaving the gap
to a caller: one connection kept per `(scheme, host, port)`, built on
`http.client` rather than urllib, passed as `transport=` with nothing
else about the client changing. A caller wanting a full session —
cookies, a retry policy, HTTP/2 — still reaches for a `requests` or
`httpx` session of their own; what `SessionTransport` buys over that is
the one thing a caller polling a single node needs, with none of the
zero-dependency promise spent on it.

Per call a loopback connect is negligible. In aggregate it is socket
churn, and the default transport's request asks the node to be the side
that closes, so the sockets accumulate in TIME_WAIT there — which is why
a caller polling at a high rate wants `SessionTransport`, or a transport
of their own, on loopback too, and not only over TLS.
