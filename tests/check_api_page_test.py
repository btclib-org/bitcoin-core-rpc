# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the built-page census of `.github/scripts`.

`missing_names` is what is asserted here, against a page built by hand
rather than a real one: proving it catches a name the reusable docs
workflow would find missing is the point, and a real `sphinx-build`
needs the `docs` group this suite does not carry. That workflow is
where the real page is read, and `.github/scripts/check_api_page.py`'s
own docstring says why the check lives there and not here.

`page_path` is asserted too, against a bare directory name rather than
one an actual build wrote: `main`'s single argument is the directory
holding the built `api.html`, not the page itself.

`main` is called in this interpreter, on an `api.html` written into a
temporary directory, and the `__main__` guard is run with
`runpy.run_path`: `.github/scripts` is under the coverage floor, and a
subprocess would report nothing to it.

The script is loaded by path, `.github/scripts` being no package.
"""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path
from types import ModuleType

import pytest

import bitcoin_core_rpc

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


def test_page_path_joins_api_html_onto_the_build_directory(
    checker: ModuleType,
) -> None:
    """The reusable workflow passes the build directory, not the page."""
    assert checker.page_path("docs/build/html") == Path("docs/build/html/api.html")


def _built(directory: Path, *names: str) -> None:
    """Write an `api.html` under `directory` carrying one id per name."""
    ids = (f"bitcoin_core_rpc.module.{name}" for name in names)
    (directory / "api.html").write_text(_page(*ids), encoding="utf-8")


def test_main_says_how_to_be_called_when_it_is_not(
    checker: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """No build directory, or two of them, is the usage and exit 2."""
    assert checker.main(["check_api_page.py"]) == 2
    assert capsys.readouterr().err == "usage: check_api_page.py <build directory>\n"


def test_main_passes_a_page_carrying_every_name(
    checker: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every name of `__all__` on the page is exit 0 and prints nothing."""
    _built(tmp_path, *bitcoin_core_rpc.__all__)
    assert checker.main(["check_api_page.py", str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""


def test_main_names_each_name_the_page_drops(
    checker: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dropped name is exit 1 and one annotation naming it."""
    dropped, *kept = bitcoin_core_rpc.__all__
    _built(tmp_path, *kept)
    assert checker.main(["check_api_page.py", str(tmp_path)]) == 1
    assert capsys.readouterr().out == (
        f"::error::{dropped!r} is in __all__ and not on the built api page\n"
    )


def test_the_main_guard_runs_the_script_as___main__(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`runpy.run_path` runs the file with `__name__` set to `"__main__"`."""
    _built(tmp_path, *bitcoin_core_rpc.__all__)
    monkeypatch.setattr(sys, "argv", ["check_api_page.py", str(tmp_path)])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT), run_name="__main__")
    assert excinfo.value.code == 0
