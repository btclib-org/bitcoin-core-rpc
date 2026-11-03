# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the sdist normalizer of `.github/scripts`.

`normalize` exists for one property -- two archives whose content agrees
normalize to the same bytes, whatever the metadata of their members said --
and that is what is asserted here, on archives staged by hand rather than
on a build of this tree. A build cannot show it: `uv_build` writes one
fixed timestamp and one pair of modes into every member, so two of its
archives differ in no metadata for the property to bite on. What
`normalize` does over one of them is rewrite it -- every member's mtime
moves from uv's 0 to `SOURCE_DATE_EPOCH`, and the digest with it, which
is what `test.yml`'s step is for. The metadata a member can otherwise
carry is what the archives below are staged with, and the script's own
docstring is why that case has to keep being answered by this tree
rather than by the backend.

RELEASING.md's "Rebuild a release from its tag" is what the property is
for, a verifier's digest having to agree with the published one.

`main` is called in this interpreter, by each of its refusals and on a
directory holding one sdist, and the `__main__` guard is run with
`runpy.run_path`: `.github/scripts` is under the coverage floor, and a
subprocess would report nothing to it.

The script is loaded by path, `.github/scripts` being no package.
"""

from __future__ import annotations

import importlib.util
import io
import runpy
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).parents[1] / ".github" / "scripts" / "normalize_sdist.py"
# what the release job exports, and what a normalized member's mtime is:
# any fixed reading does, this one being the epoch of a commit
_EPOCH = 1786392620
_CONTENT = b"# a member of the archive\n"


@pytest.fixture(scope="module")
def normalizer() -> ModuleType:
    """Return the script, imported by path."""
    spec = importlib.util.spec_from_file_location("normalize_sdist", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _staged_sdist(archive: Path, *, mode: int, mtime: float) -> None:
    """Write an sdist of one directory and one file, with these member bits.

    Two members because the mode a directory takes is not the one a file
    takes, and an sdist carries both. `mtime` is a float on purpose: a
    sub-second timestamp is what writes the PAX record whose length moves
    the checksum, and clearing those records is half of what the script
    does.
    """
    with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        directory = tarfile.TarInfo("pkg-1.0")
        directory.type = tarfile.DIRTYPE
        directory.mode = mode | 0o111
        directory.mtime = mtime
        tar.addfile(directory)
        member = tarfile.TarInfo("pkg-1.0/README.md")
        member.size = len(_CONTENT)
        member.mode = mode
        member.mtime = mtime
        member.uid = member.gid = 501
        member.uname = member.gname = "somebody"
        tar.addfile(member, io.BytesIO(_CONTENT))


def _members(archive: Path) -> list[tuple[str, int, float, int, str]]:
    """Return the metadata this script rewrites, member by member."""
    with tarfile.open(archive, "r:gz") as tar:
        return [(m.name, m.mode, m.mtime, m.uid, m.uname) for m in tar.getmembers()]


def test_two_archives_differing_only_in_a_mode_normalize_alike(
    normalizer: ModuleType, tmp_path: Path
) -> None:
    """The property the script exists for, across two member modes.

    One archive carries group write where the other does not, and the
    content of every file agrees: the archives are the same source tree, so
    the digests a verifier compares have to agree too. Which backend wrote
    which mode is the question this makes not matter.
    """
    theirs = tmp_path / "umask-022.tar.gz"
    ours = tmp_path / "umask-002.tar.gz"
    _staged_sdist(theirs, mode=0o644, mtime=_EPOCH + 0.4787617)
    _staged_sdist(ours, mode=0o664, mtime=_EPOCH + 1.1946435)
    assert theirs.read_bytes() != ours.read_bytes()

    normalizer.normalize(theirs, _EPOCH)
    normalizer.normalize(ours, _EPOCH)

    assert theirs.read_bytes() == ours.read_bytes()


def test_normalizing_rewrites_the_metadata_and_keeps_the_content(
    normalizer: ModuleType, tmp_path: Path
) -> None:
    """One mode for files, one for directories, and root with no names.

    The mode says what a rebuild no longer depends on; the rest is what the
    script already promised, asserted beside it because a member is rewritten
    as a whole and a check on one field alone would not notice the others
    being dropped.
    """
    archive = tmp_path / "sdist.tar.gz"
    _staged_sdist(archive, mode=0o664, mtime=_EPOCH + 0.5)

    normalizer.normalize(archive, _EPOCH)

    assert _members(archive) == [
        ("pkg-1.0", 0o755, _EPOCH, 0, ""),
        ("pkg-1.0/README.md", 0o644, _EPOCH, 0, ""),
    ]
    with tarfile.open(archive, "r:gz") as tar:
        extracted = tar.extractfile("pkg-1.0/README.md")
        assert extracted is not None
        assert extracted.read() == _CONTENT
    # the gzip header carries the epoch as well, and not the moment of the
    # compression: four octets at offset 4, little-endian, which is RFC 1952
    # section 2.3's MTIME field
    assert int.from_bytes(archive.read_bytes()[4:8], "little") == _EPOCH


def test_main_says_how_to_be_called_when_it_is_not(
    normalizer: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """No dist directory, or two of them, is the usage and exit 2."""
    assert normalizer.main(["prog"]) == 2
    assert capsys.readouterr().err == "usage: prog <dist directory>\n"


def test_main_refuses_to_default_source_date_epoch_to_now(
    normalizer: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset is a failure, not "now": the script's comment there says why."""
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert normalizer.main(["prog", str(tmp_path)]) == 1
    assert capsys.readouterr().err == "SOURCE_DATE_EPOCH is not set\n"


def test_main_names_a_dist_directory_with_no_sdist(
    normalizer: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A directory with a wheel and no sdist is named, not skipped."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    (tmp_path / "bitcoin_core_rpc-1.0-py3-none-any.whl").write_bytes(b"")
    assert normalizer.main(["prog", str(tmp_path)]) == 1
    assert capsys.readouterr().err == f"no sdist in {tmp_path}\n"


def test_main_normalizes_every_sdist_and_reports_it(
    normalizer: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The success path: each `*.tar.gz` is rewritten and named."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    archive = tmp_path / "pkg-1.0.tar.gz"
    _staged_sdist(archive, mode=0o664, mtime=_EPOCH + 0.5)
    assert normalizer.main(["prog", str(tmp_path)]) == 0
    assert capsys.readouterr().out == f"normalized {archive}\n"
    assert [mtime for _, _, mtime, _, _ in _members(archive)] == [_EPOCH, _EPOCH]


def test_the_main_guard_runs_the_script_as___main__(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`runpy.run_path` runs the file with `__name__` set to `"__main__"`."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    _staged_sdist(tmp_path / "pkg-1.0.tar.gz", mode=0o644, mtime=_EPOCH)
    monkeypatch.setattr(sys, "argv", ["prog", str(tmp_path)])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT), run_name="__main__")
    assert excinfo.value.code == 0
