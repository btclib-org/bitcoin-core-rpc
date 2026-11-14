# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for `tests/_tls/generate.py`, which writes the TLS fixtures.

A set it writes completes a handshake with a context that trusts its
authority and sets `VERIFY_X509_STRICT`, and carries what the committed
set carries. The handshake runs over memory buffers, so no socket opens.

`main` is called in this interpreter, and the `__main__` guard is run with
`runpy.run_path`, for the coverage floor. The script is loaded by path,
`tests/_tls` being no package.
"""

from __future__ import annotations

import importlib.util
import runpy
import ssl
import sys
from pathlib import Path
from types import ModuleType

import pytest
from cryptography import x509

_TLS = Path(__file__).parent / "_tls"
_SCRIPT = _TLS / "generate.py"
_FILES = ["ca.pem", "server.key", "server.pem"]
# the extensions whose value is a key's identifier, which a new key changes
_KEY_IDS = {x509.SubjectKeyIdentifier.oid, x509.AuthorityKeyIdentifier.oid}


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    """Return the script, imported by path."""
    spec = importlib.util.spec_from_file_location("generate", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _done(tls: ssl.SSLObject) -> bool:
    """Advance the handshake of `tls`, and say whether it is complete."""
    try:
        tls.do_handshake()
    except ssl.SSLWantReadError:
        return False
    return True


def _handshake(directory: Path, client: ssl.SSLContext, server_hostname: str) -> None:
    """Complete a handshake with a server presenting the set in `directory`."""
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # for CodeQL, as `_tls_serve` in transport_test.py says
    server.minimum_version = ssl.TLSVersion.TLSv1_2
    server.load_cert_chain(directory / "server.pem", directory / "server.key")
    to_server, to_client = ssl.MemoryBIO(), ssl.MemoryBIO()
    client_side = client.wrap_bio(to_client, to_server, server_hostname=server_hostname)
    server_side = server.wrap_bio(to_server, to_client, server_side=True)
    # each side is advanced on every round, whatever the other answered;
    # a handshake takes a few rounds, and the bound turns a stall into a
    # failure rather than a hang
    rounds = 0
    while not all([_done(client_side), _done(server_side)]):
        rounds += 1
        assert rounds < 10


def _strict(directory: Path) -> ssl.SSLContext:
    """Return a client context trusting the authority in `directory`."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(directory / "ca.pem")
    context.verify_flags |= ssl.VERIFY_X509_STRICT
    return context


@pytest.mark.parametrize("server_hostname", ["127.0.0.1", "localhost"])
def test_a_generated_set_passes_a_strict_handshake(
    generator: ModuleType, tmp_path: Path, server_hostname: str
) -> None:
    """Both names the server certificate carries are verified."""
    assert generator.main(["generate.py", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == _FILES
    _handshake(tmp_path, _strict(tmp_path), server_hostname)


def test_a_context_not_trusting_the_authority_refuses_it(
    generator: ModuleType, tmp_path: Path
) -> None:
    """The handshake above verifies: one trusting another authority fails."""
    generator.generate(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    generator.generate(other)
    with pytest.raises(ssl.SSLCertVerificationError):
        _handshake(tmp_path, _strict(other), "127.0.0.1")


def _shape(certificate: x509.Certificate) -> object:
    """Return what does not depend on the keys, nor on a random serial."""
    extensions = [
        (e.oid, e.critical, None if e.oid in _KEY_IDS else e.value)
        for e in certificate.extensions
    ]
    return (
        certificate.subject,
        certificate.issuer,
        certificate.not_valid_before_utc,
        certificate.not_valid_after_utc,
        certificate.signature_algorithm_oid,
        extensions,
    )


@pytest.mark.parametrize("name", ["ca.pem", "server.pem"])
def test_a_generated_set_carries_what_the_committed_one_does(
    generator: ModuleType, tmp_path: Path, name: str
) -> None:
    """Names, validity, signature algorithm and extensions agree."""
    generator.generate(tmp_path)
    generated = x509.load_pem_x509_certificate((tmp_path / name).read_bytes())
    committed = x509.load_pem_x509_certificate((_TLS / name).read_bytes())
    assert _shape(generated) == _shape(committed)


def test_the_server_serial_and_the_key_identifiers_chain(
    generator: ModuleType, tmp_path: Path
) -> None:
    """The server certificate is serial 2, naming the authority's key."""
    generator.generate(tmp_path)
    ca = x509.load_pem_x509_certificate((tmp_path / "ca.pem").read_bytes())
    server = x509.load_pem_x509_certificate((tmp_path / "server.pem").read_bytes())
    authority_id = ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
    named = server.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier)
    assert server.serial_number == 2
    assert named.value.key_identifier == authority_id.value.digest


def test_main_refuses_a_missing_directory_argument(
    generator: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without exactly one argument it prints the usage and exits 2."""
    assert generator.main(["generate.py"]) == 2
    assert capsys.readouterr().err == "usage: generate.py <directory>\n"


def test_the_main_guard_writes_a_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run as a script, it exits 0 having written the three files."""
    monkeypatch.setattr(sys, "argv", [str(_SCRIPT), str(tmp_path)])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(_SCRIPT), run_name="__main__")
    assert exited.value.code == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == _FILES
