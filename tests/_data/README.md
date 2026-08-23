# The recorded replies

What is in this directory, where each file came from, and how to check a
copy. Nothing here is fetched at test time and nothing here is generated:
these are the bytes a test is handed instead of a socket.

The distinction between the envelope and what it carries is the whole of
the entry.

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

Nothing here was invented; nothing here was captured either, and a node's
answer is what settles a disagreement.
`.github/workflows/integration-bitcoind.yml` is where that question is
asked of two live bitcoind versions.

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

Every file carries `"id": "btclib"`, which is no id `call` ever sends —
that one is random per request. The tests echo the request's own id into
the reply the way a node does, so a test about the *reply* is not also a
test about the id; a test about the id builds its own body.
