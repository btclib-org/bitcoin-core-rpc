# Copyright (c) The btclib developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Rewrite an sdist so that two builds of one commit are the same bytes.

`SOURCE_DATE_EPOCH` is enough for the wheel: with it exported, two
builds of this tree from two checkouts produce a byte-identical
`.whl`. The `.tar.gz` still differs, and the difference is one field.
setuptools stages an sdist in a directory it creates at build time and
tars that directory as the archive's first member, whose timestamp
`SOURCE_DATE_EPOCH` does not reach -- so the member carries a PAX
`mtime` record with sub-second precision, the header length changes
with the number of digits in it, and the checksum changes with the
length:

    28 mtime=1786392620.4787617
    28 mtime=1786392621.1946435

What is *in* the archive is already deterministic; what is not is the
metadata of the members. This rewrites that metadata and nothing else:
every timestamp becomes `SOURCE_DATE_EPOCH`, ownership becomes root
with no names, every mode becomes 0644 or 0755, and the gzip header
carries the same timestamp instead of the moment it was compressed. The
order of the members and every byte of their content are the archive's
own.

The mode is normalized because it otherwise comes from the working
tree, which puts the umask of the checkout in the published archive: a
verifier whose files carry group write rebuilds a tag and reads a
digest mismatch as a newer setuptools or as tampering, where the
content matches byte for byte. Nothing in the sdist needs the
executable bit -- no source file here opens with a shebang, which
`.pre-commit-config.yaml` records as a decision rather than an accident
-- so one mode for files and one for directories is the whole of it.

`PAX_FORMAT` with the extended headers cleared, rather than
`USTAR_FORMAT`: an integral timestamp needs no PAX record, so the two
formats write the same bytes today -- and the day a path in the sdist
outgrows ustar's 100 characters, pax records it and ustar would have
refused it.

Run it after `uv build` and before anything reads dist/:

    uv run --no-project --python 3.14 \
        .github/scripts/normalize_sdist.py dist/

RELEASING.md has the command that verifies a published release against
a rebuild of its tag.
"""

from __future__ import annotations

import gzip
import io
import os
import sys
import tarfile
from pathlib import Path


def normalize(archive: Path, epoch: int) -> None:
    """Rewrite one archive in place, member metadata at `epoch`."""
    members: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            # extractfile returns None for anything that is not a regular
            # file, and a directory member is exactly the case this script
            # exists for, so the two are told apart rather than asserted
            stream = source.extractfile(member) if member.isfile() else None
            members.append((member, stream.read() if stream is not None else None))

    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode="w", format=tarfile.PAX_FORMAT) as target:
        for member, content in members:
            member.mtime = epoch
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            # beside the ownership, and for the same reason: what the
            # archive found here came from the working tree, so the umask of
            # the checkout reached the published bytes. Digest-preserving
            # for what CI publishes, a runner's checkout carrying these two
            member.mode = 0o755 if member.isdir() else 0o644
            # the records this exists to remove: tarfile writes one per
            # field it cannot express in the ustar header, and the
            # sub-second mtime above was such a field. Replaced rather than
            # cleared, the attribute being a Mapping to a type checker
            member.pax_headers = {}
            target.addfile(member, io.BytesIO(content) if content is not None else None)

    compressed = io.BytesIO()
    # mtime, not the clock, and filename empty: gzip stores both in its
    # header, and the name of a temporary file is not the archive's
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=compressed, mtime=epoch, compresslevel=9
    ) as compressor:
        compressor.write(tar.getvalue())
    archive.write_bytes(compressed.getvalue())


def main(argv: list[str]) -> int:
    """Normalize every sdist in the directory named on the command line."""
    if len(argv) != 2:
        print(f"usage: {argv[0]} <dist directory>", file=sys.stderr)  # noqa: T201
        return 2

    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is None:
        # not a default of "now": a default would make the failure a
        # reproducibility bug found by whoever tried to verify a release,
        # which is the one person who cannot fix it
        print("SOURCE_DATE_EPOCH is not set", file=sys.stderr)  # noqa: T201
        return 1

    archives = sorted(Path(argv[1]).glob("*.tar.gz"))
    if not archives:
        print(f"no sdist in {argv[1]}", file=sys.stderr)  # noqa: T201
        return 1

    for archive in archives:
        normalize(archive, int(epoch))
        print(f"normalized {archive}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
