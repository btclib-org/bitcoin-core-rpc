# AuthServiceProxy, corepc and bitcoin-core-rpc

What differs between AuthServiceProxy and this client, row by row, and
why three cases — dynamic dispatch, batching, a kept connection — are
each a decision `BitcoinCoreRpcClient` took rather than left to a
caller's own code. [corepc](#corepc) compares this client with
rust-bitcoin's. [docs/source/migrating.md](./docs/source/migrating.md)
is the line-by-line rewrite; this is the case for doing it.

## The two clients

**AuthServiceProxy** is python-bitcoinrpc's client, along with the copy
Bitcoin Core's test framework maintains. Both carry the LGPL-2.1 of their
python-jsonrpc ancestry, and both are normally vendored — copied into the
caller's own tree, which makes the copy the caller's to maintain.

**bitcoin-core-rpc** is a standalone JSON-RPC client for Bitcoin Core,
MIT licensed, with no dependencies, released in lockstep with the
library downstream of it. It is an implementation of the protocol
rather than a translation of that one, and shares no line with either.

## Comparison

<!-- markdownlint-disable MD013 -->

| | AuthServiceProxy (vendored) | bitcoin-core-rpc |
| --- | --- | --- |
| Maintenance | in-repo copy, the caller's to patch | maintained package, zero dependencies |
| Amounts | `Decimal` on replies; a `Decimal` request parameter rounded through `float` by python-bitcoinrpc, sent as a string by Core's copy, a type an amount argument accepts and an integer one refuses | `Decimal` on replies **and** on requests, a `Decimal` parameter written as the JSON number it is; `NaN`/`Infinity` refused both ways |
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

## corepc

**corepc** is rust-bitcoin's client for Bitcoin Core. Its `corepc-client`
crate calls its `jsonrpc` crate, which sends over its `bitreq` HTTP
client. The corepc column reads the async `Client`, which
`client/src/lib.rs` calls the production client, at commit
[`eca58560`](https://github.com/rust-bitcoin/corepc/commit/eca585605f6fbf79a1c8ce81ce86e2e4205cdf31),
and each of its cells cites a file and line there. Each bitcoin-core-rpc
cell names the code that does it. Bitcoin Core's `src/httprpc.cpp` is
read at commit `7efbdb6437`.

<!-- markdownlint-disable MD013 -->

| | bitcoin-core-rpc | corepc | Why this client differs |
| --- | --- | --- | --- |
| Version sent | `"2.0"`, from `call` and `call_batch` | `"2.0"`, `jsonrpc/src/client_async.rs:22` and `:64` | alike |
| A reply's version and id | no `jsonrpc` member is a 1.1 reply, any other value than `"2.0"` is refused (`_discriminate`), and so is an id other than the one sent (`_legacy_result`, `_v2_result`) | neither is checked: `Client::call` reads the reply with `result()`, `client/src/client_async/mod.rs:140-142`; the `jsonrpc` crate's own `Client::call` checks both, `jsonrpc/src/client_async.rs:136-141` | intended: `_discriminate`'s comment and `_legacy_result`'s docstring say why |
| Batch | refused: an empty batch (`call_batch`), and a reply count other than the requests', an unknown id or a duplicate id (`_correlated_batch_replies`) | `corepc-client` has no batch call; `jsonrpc`'s `send_batch` refuses an empty batch, more replies than requests, an unknown id and a duplicate id, and answers `None` for a request with no reply, `jsonrpc/src/client_async.rs:89-120` | intended: a request with no reply is refused, as `_correlated_batch_replies`'s docstring says; Core answers every request that has an id, `src/httprpc.cpp:168-170` |
| Timeout | `DEFAULT_TIMEOUT` per client, `request_timeout` per call, a deadline over the whole exchange | 60 s, set by the constructor, `client/src/client_async/mod.rs:89`; a deadline, `bitreq/src/request.rs:409` | intended: the comment above `DEFAULT_TIMEOUT` gives the reason for its value, and `call`'s docstring the case for a per-call one |
| Body limit | `DEFAULT_MAX_BODY_SIZE` by default, `max_body_size` per call | 1 GiB, `bitreq`'s default, `bitreq/src/request.rs:126`, which `jsonrpc`'s transport leaves as it is, `jsonrpc/src/http/bitreq_http_async.rs:58-66` | intended: the comment above `DEFAULT_MAX_BODY_SIZE` gives the reason |
| Non-200 status | under 2.0 always `HttpError` (`_v2_result`); under 1.1 a readable error object first, then the status (`_legacy_result`) | `HttpError` only when the body is not json; a json body is read as the reply, `jsonrpc/src/http/bitreq_http_async.rs:72-83` | intended: under 2.0 Core answers an rpc error with HTTP 200, `src/httprpc.cpp:43-46` and `:122-126`, and `_v2_result`'s docstring says what that buys |
| Error codes | `RpcError.code` and `.data`; `RPCErrorCode` names Core's codes | code, message and data, `jsonrpc/src/error.rs:120-127`; one code tested by name, `-5` for `is_not_found_error`, `client/src/client_async/error.rs:82-84` | alike in what reaches the caller; `RPCErrorCode` is a lookup on top, as its docstring says |
| Amounts | `Decimal` both ways (`_json_number`, `_decimal_json`) | `f64` in the reply type, `types/src/v17/blockchain/mod.rs:631`, then `Amount::from_btc`, `types/src/v17/blockchain/into.rs:522` | intended: `call`'s docstring |
| Cookie | a path, or one `from_chain` derives from the chain and the datadir; read at every call (`cookie_auth`) | a path only, read once by the constructor, `client/src/client_async/mod.rs:60-66` and `:111-112` | intended: `cookie_auth`'s docstring |

<!-- markdownlint-enable MD013 -->

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
