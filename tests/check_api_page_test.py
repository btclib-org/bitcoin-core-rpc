# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the built-page census of `.github/scripts`.

`missing_names` is what is asserted here, against a page built by hand
rather than a real one: proving it catches a name docs.yml would find
missing is the point, and a real `sphinx-build` needs the `docs` group
this suite does not carry. `docs.yml` is where the real page is read, and
`.github/scripts/check_api_page.py`'s own docstring says why the check
lives there and not here.

The script is loaded by path, `.github/scripts` being no package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).parents[1] / ".github" / "scripts" / "check_api_page.py"


@pytest.fixture(scope="module")
def checker() -> ModuleType:
    """Return the script, imported by path."""
    spec = importlib.util.spec_from_file_location("check_api_page", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _page(*ids: str) -> str:
    """Return a page carrying one anchor per id, and nothing else read."""
    anchors = "".join(f'<dt id="{i}"></dt>' for i in ids)
    return f"<html><body>{anchors}</body></html>"


def test_every_name_present_is_not_missing(checker: ModuleType) -> None:
    """The page this asserts against is what a complete build would write."""
    page = _page(
        "bitcoin_core_rpc.chains.Chain",
        "bitcoin_core_rpc.chains.chain_from_network",
        "bitcoin_core_rpc.chains.network_from_chain",
    )
    names = ("Chain", "chain_from_network", "network_from_chain")
    assert checker.missing_names(names, page) == []


def test_a_name_the_page_drops_is_caught(checker: ModuleType) -> None:
    """The exact regression: a data member with no docstring where read.

    `Chain` is a class and carries its own `__doc__`, so it survives
    `automodule` even where a constant would not; here the page simply
    never wrote it, which is the shape the built page had before
    `docs/source/api.rst` moved to one `automodule` block per submodule.
    """
    page = _page("bitcoin_core_rpc.chains.chain_from_network")
    assert checker.missing_names(("Chain", "chain_from_network"), page) == ["Chain"]


def test_a_suffix_is_not_mistaken_for_the_name_it_ends_with(
    checker: ModuleType,
) -> None:
    """`chain_from_network` on the page does not stand in for `network`.

    A bare substring search would have `"network" in id` pass on
    `chain_from_network`'s own id; the dot before the name is what this
    checks for instead, and there is none before `network` inside it.
    """
    page = _page("bitcoin_core_rpc.chains.chain_from_network")
    assert checker.missing_names(("network",), page) == ["network"]


def test_an_empty_page_is_missing_every_name(checker: ModuleType) -> None:
    """No anchor at all is the page a failed build or a wrong path gives."""
    names = ("Chain", "chain_from_network")
    assert checker.missing_names(names, "<html><body></body></html>") == list(names)
