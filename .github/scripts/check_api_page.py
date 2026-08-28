# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Refuse a built api page that drops a name of `bitcoin_core_rpc.__all__`.

`automodule` skips a data member silently when its attribute docstring is
not in the source of the module being documented -- the exact shape
`docs/source/api.rst` moved to one automodule block per submodule to
avoid, and the one `sphinx-build -n -W` does not warn about either way,
since nothing is malformed and nothing fails to resolve. This is the
check that reads the artifact instead of the configuration: `docs.yml`
runs it against the page its own build just wrote, so this script pays
for no second build and no second install of the `docs` group.

`tests/check_api_page_test.py` is where `missing_names` is proven, against
a page invented for the purpose rather than a real build -- the test
suite does not carry the `docs` group, and a real build is not what this
function's own correctness needs.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path

import bitcoin_core_rpc

# the reviewer's own command against the branch that found the gap:
# every id sphinx writes for a member of this package, whichever
# submodule the automodule block that rendered it names
_ID = re.compile(r'id="bitcoin_core_rpc[A-Za-z_0-9.]*"')


def missing_names(all_names: Sequence[str], page: str) -> list[str]:
    """Return every name of `all_names` no id of `page` carries.

    An id matches a name when it ends `.<name>"` -- the dot is what a bare
    substring match would miss: `"network" in` the id
    `bitcoin_core_rpc.chains.chain_from_network` is true, `network` never
    having been on the page at all.
    """
    found = _ID.findall(page)
    return [
        name for name in all_names if not any(f.endswith(f'.{name}"') for f in found)
    ]


def main(argv: list[str]) -> int:
    """Print every name missing from the page named by `argv[1]`."""
    if len(argv) != 2:
        print("usage: check_api_page.py <built api.html>", file=sys.stderr)
        return 2
    page = Path(argv[1]).read_text(encoding="utf-8")
    missing = missing_names(bitcoin_core_rpc.__all__, page)
    for name in missing:
        print(f"::error::{name!r} is in __all__ and not on the built api page")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
