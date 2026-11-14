# The data the suite reads

What is in this directory, where each file came from, and how to check a
copy. Nothing here is fetched at test time.

The `.json` files are the recorded replies, and nothing generated them:
they are the bytes a test is handed instead of a socket. The distinction
between the envelope and what it carries is the whole of their entry.
`tls/` holds a test certificate authority and the script that wrote it,
and the last section describes them.

## The envelopes are not recorded

They are what bitcoind sends, written here from the source that writes them
rather than captured from a node: `JSONRPCReplyObj` in Core's
`src/rpc/request.cpp` puts `jsonrpc`, `result` and `id` in that order,
compact, and `WriteReply` appends the newline — which is why these files
are one line each, and why `pretty-format-json` is configured to leave this
directory alone. Reformatting one would void the claim this file makes
about it.

The error object of `getrawtransaction_error.json` is Core's too: code `-5`
with the message `src/rpc/rawtransaction.cpp` builds for a node running
without `-txindex`, verbatim, including the trailing sentence
`JSONRPCError` appends.

No reply here was invented; none was captured either, and a node's answer
is what settles a disagreement.
`.github/workflows/integration-bitcoind.yml` is where that question is
asked of live bitcoind versions, its `versions` job choosing which.

## What they carry is chain data, and it verifies itself

`getrawtransaction.json` holds transaction 1 of block 170 —

```text
txid  f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16
      1 input, 2 outputs of 10 and 40 BTC
```

— the first bitcoin payment between two people. It is a transaction id
recomputed from the serialization, so any copy can be checked against any
node or explorer that has the index:

```shell
bitcoin-cli getrawtransaction \
    f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16
```

`getblockcount.json` and `getbestblockhash.json` carry block 481824, the
first block with a segwit transaction in it, as a height and as a hash. The
two agree, and either answers for the other:

```shell
bitcoin-cli getblockhash 481824
```

## The id

Every reply carries `"id": "btclib"`, which is no id `call` ever sends —
that one is random per request. The tests echo the request's own id into
the reply the way a node does, so a test about the *reply* is not also a
test about the id; a test about the id builds its own body.

## `tls/` is a test certificate authority

`ca.pem` is a certificate authority made for the suite and nothing else.
`server.pem` is a certificate it issued for `127.0.0.1` and `localhost`,
and `server.key` is that certificate's key. No trust store holds the
authority, so a loopback server presenting `server.pem` is refused by the
default TLS context and reached by a context that trusts `ca.pem`.
`tests/transport_test.py` runs such a server.

The key is a test fixture, public on purpose. `generate.py` wrote the
three files and never wrote the authority's own key, so no other
certificate chains to `ca.pem`. Both certificates are valid from
`NOT_BEFORE` to `NOT_AFTER`, which `generate.py` sets.

This command, run from the repository root, replaces them with a new
set:

```shell
uv run python tests/_data/tls/generate.py tests/_data/tls
```

`tests/tls_generate_test.py` checks that a context with
`VERIFY_X509_STRICT`, which `_tls_context` sets, accepts a set the
script writes.
