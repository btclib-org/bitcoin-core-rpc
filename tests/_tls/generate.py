# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Write a new test authority, its server certificate and that key.

`README.md` beside this file says what the three files are for, and the
command that replaces them with a set this writes.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

# the first and the last instant both certificates are valid, the last
# being RFC 5280's value for a certificate with no expiry
NOT_BEFORE = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
NOT_AFTER = dt.datetime(9999, 12, 31, 23, 59, 59, tzinfo=dt.UTC)


def _name(common_name: str) -> x509.Name:
    """Return a name holding only `common_name`."""
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _key_usage(*, cert_sign: bool) -> x509.KeyUsage:
    """Return an authority's key usage, or a TLS server's."""
    return x509.KeyUsage(
        digital_signature=not cert_sign,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=cert_sign,
        crl_sign=cert_sign,
        encipher_only=False,
        decipher_only=False,
    )


def _pem(certificate: x509.Certificate) -> bytes:
    """Return `certificate` as PEM."""
    return certificate.public_bytes(serialization.Encoding.PEM)


def generate(directory: Path) -> None:
    """Write `ca.pem`, `server.pem` and `server.key` into `directory`."""
    authority_key = ec.generate_private_key(ec.SECP256R1())
    authority = _name("bitcoin-core-rpc test authority")
    authority_id = x509.SubjectKeyIdentifier.from_public_key(authority_key.public_key())
    ca = (
        x509.CertificateBuilder()
        .subject_name(authority)
        .issuer_name(authority)
        .public_key(authority_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOT_BEFORE)
        .not_valid_after(NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(_key_usage(cert_sign=True), critical=True)
        .add_extension(authority_id, critical=False)
        .sign(authority_key, hashes.SHA256())
    )

    server_key = ec.generate_private_key(ec.SECP256R1())
    names = [
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.DNSName("localhost"),
    ]
    server = (
        x509.CertificateBuilder()
        .subject_name(_name("127.0.0.1"))
        .issuer_name(authority)
        .public_key(server_key.public_key())
        .serial_number(2)
        .not_valid_before(NOT_BEFORE)
        .not_valid_after(NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(_key_usage(cert_sign=False), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                authority_id
            ),
            critical=False,
        )
        .sign(authority_key, hashes.SHA256())
    )

    (directory / "ca.pem").write_bytes(_pem(ca))
    (directory / "server.pem").write_bytes(_pem(server))
    (directory / "server.key").write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


def main(argv: list[str]) -> int:
    """Write a new set into the directory named on the command line."""
    if len(argv) != 2:
        print(f"usage: {argv[0]} <directory>", file=sys.stderr)  # noqa: T201
        return 2
    generate(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
