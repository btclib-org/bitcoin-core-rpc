# A test certificate authority

`ca.pem` is a certificate authority made for the suite and nothing else.
`server.pem` is a certificate it issued for `127.0.0.1` and `localhost`,
and `server.key` is that certificate's key. No trust store holds the
authority, so a loopback server presenting `server.pem` is refused by the
default TLS context and reached by a context that trusts `ca.pem`.
`tests/transport_test.py` runs such a server.

The key is a test fixture, public on purpose. `generate.py` wrote the
three files and never wrote the authority's own key, so no other
certificate chains to `ca.pem`. Both certificates are valid from 2026 to
the end of 9999.

This command, run from the repository root, replaces them with a new
set:

```shell
uv run python tests/_tls/generate.py tests/_tls
```

`tests/tls_generate_test.py` checks that a context with
`VERIFY_X509_STRICT`, which `_tls_context` sets, accepts a set the
script writes.
