# A test certificate authority

`ca.pem` is a certificate authority made for the suite and nothing else.
`server.pem` is a certificate it issued for `127.0.0.1` and `localhost`,
and `server.key` is that certificate's key. No trust store holds the
authority, so a loopback server presenting `server.pem` is refused by the
default TLS context and reached by a context that trusts `ca.pem`.
`tests/transport_test.py` runs such a server.

The key is a test fixture, public on purpose. The authority's own key was
deleted once the server certificate was issued, so no other certificate
chains to `ca.pem`. Both certificates are valid from 2026 to the end of
9999.

These commands, run in an empty directory, make a new set. A context with
`VERIFY_X509_STRICT`, which `_tls_context` sets, accepts it. They need an
OpenSSL whose `req` and `x509` take `-not_before` and `-not_after`:

```shell
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
  -keyout ca.key -out ca.pem -subj "/CN=bitcoin-core-rpc test authority" \
  -not_before 20260101000000Z -not_after 99991231235959Z \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash"
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
  -keyout server.key -out server.csr -subj "/CN=127.0.0.1"
printf '%s\n' \
  "basicConstraints=critical,CA:FALSE" \
  "keyUsage=critical,digitalSignature" \
  "extendedKeyUsage=serverAuth" \
  "subjectAltName=IP:127.0.0.1,DNS:localhost" \
  "subjectKeyIdentifier=hash" \
  "authorityKeyIdentifier=keyid:always" > server.ext
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key \
  -set_serial 2 -not_before 20260101000000Z -not_after 99991231235959Z \
  -extfile server.ext -out server.pem
rm ca.key server.csr server.ext
```
