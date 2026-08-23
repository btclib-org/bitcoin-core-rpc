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

The script is loaded by path, `.github/scripts` being no package.
"""

from __future__ import annotations

import importlib.util
import io
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
