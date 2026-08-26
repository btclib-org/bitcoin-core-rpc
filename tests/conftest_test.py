# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the coverage gate of conftest.

`coverage_fail_under` is one a passing suite cannot exercise on its own:
the run that reaches it with a subset selected is, by construction, not
the run that measures this file. The position of `--cov` in addopts is
here for the same reason -- it is a property of the command line no run
of that command line can report on.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import coverage_fail_under

_ROOT = Path(__file__).parents[1]
# what `[tool.pytest.ini_options]` testpaths names, joined onto the
# rootdir the way tests/conftest.py's pytest_configure joins it
_TESTPATHS = [_ROOT / "tests"]


def _threshold(
    file_or_dir: list[str] | None,
    keyword: str = "",
    markexpr: str = "",
    *,
    asked: float | None = None,
    configured: float | None = 100.0,
    testpaths: list[Path] | None = None,
    invocation_dir: Path | None = None,
) -> float | None:
    """Ask `coverage_fail_under` from the rootdir, unless told otherwise.

    Most cases below are run from the rootdir, and naming that in each
    assertion would bury what the case is about. Two are not: a tree
    that configures no `testpaths`, and a run started from a
    subdirectory, which is the only case that tells `invocation_dir`
    from the rootdir.
    """
    return coverage_fail_under(
        asked,
        configured,
        file_or_dir,
        keyword,
        markexpr,
        invocation_dir=_ROOT if invocation_dir is None else invocation_dir,
        testpaths=_TESTPATHS if testpaths is None else testpaths,
    )


def test_a_whole_run_is_gated_at_what_pyproject_configured() -> None:
    """No selection: the ratchet applies, and it is not restated here.

    The number comes back as it was handed in, which is the property
    worth pinning: pyproject.toml is where 100 is decided, and a copy of
    it in this file would be a second place to change it.
    """
    assert _threshold([]) == 100.0
    assert _threshold([], configured=42.0) == 42.0


def test_naming_the_suite_is_not_selecting_from_it() -> None:
    """A path that takes `testpaths` in is gated at the full ratchet.

    `pytest tests` collects what a bare run collects, `testpaths` being
    `tests`, so the spelling that says out loud which suite is meant is
    the one that must not drop the floor. The trailing slash, the `./`
    and the absolute path are that same directory; the rootdir is above
    it, and a path above `testpaths` collects it whole too.
    """
    for path in ("tests", "./tests", "tests/", str(_ROOT / "tests"), str(_ROOT)):
        assert _threshold([path]) == 100.0, path


def test_a_path_is_read_against_where_pytest_was_started() -> None:
    """`tests` means one directory from the rootdir and another from `tests/`.

    pytest reads a positional argument against the directory it was
    invoked from and `testpaths` against the rootdir, so the two bases
    are what `invocation_dir` exists to keep apart. Without this case
    nothing here would fail if the rootdir were substituted back for it:
    every other assertion starts from the rootdir, where the two
    coincide, so the suite would stay green at a 100% floor while the
    parameter had stopped meaning anything.

    From `tests/`, `pytest tests` names `tests/tests`, which collects
    none of the suite and is therefore a selection.
    """
    assert _threshold(["tests"], invocation_dir=_ROOT / "tests") == 0
    assert _threshold(["tests"]) == 100.0


def test_the_help_path_is_no_selection_either() -> None:
    """`--help` leaves `file_or_dir` at `None` rather than at `[]`.

    pytest abandons the parse before the positional is consumed, and
    `pytest_configure` fires anyway, so this is what reaches the hook on
    a command line that named no path at all.
    """
    assert _threshold(None) == 100.0


def test_a_tree_naming_no_testpaths_treats_every_path_as_a_subset() -> None:
    """With `testpaths` empty, nothing on the command line is the suite.

    A bare run collects the rootdir, which no named path can be more
    than -- and `all` over an empty `testpaths` would answer the
    opposite, calling every path the whole suite.
    """
    assert _threshold(["tests"], testpaths=[]) == 0


def test_a_selected_subset_is_gated_at_nothing() -> None:
    """Any of a partial path, `-k` or `-m` drops the threshold to zero.

    Zero and not None: None is what pytest-cov reads the configured
    threshold into, so it would restore the very gate this removes. The
    last case is the suite named beside a `-k`: a run that also asked
    for less is a selection whatever its paths say.
    """
    one_file = ["tests/transport_test.py"]
    for file_or_dir, keyword, markexpr in (
        (one_file, "", ""),
        ([], "getbalance", ""),
        ([], "", "integration"),
        (one_file, "getbalance", "integration"),
        (["tests"], "getbalance", ""),
    ):
        selection = (file_or_dir, keyword, markexpr)
        assert _threshold(file_or_dir, keyword, markexpr) == 0, selection


def test_cov_is_not_the_last_token_of_addopts() -> None:
    """`--cov` last in addopts eats the first argument of the command.

    It takes an optional value, so as the final token it is handed
    whatever the command line goes on to say: `pytest
    tests/transport_test.py` would become `--cov=tests/transport_test.py`,
    leaving no path to select on. The whole suite would then run,
    measure a directory `omit` excludes, and report against a
    `fail_under` of 100 having measured the wrong thing.

    `pytest -q tests/...` hides it, a token starting with `-` not being
    consumed, so the habitual spelling is green and the documented one is
    not. Nothing about a run reports its own addopts, which is why this
    reads the file: anywhere but last is safe, and the assertion is that
    weak on purpose -- the order of the rest is nobody's business here.
    """
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^addopts = "(.*)"$', text, re.MULTILINE)
    assert match, "pyproject.toml has no single-line 'addopts = \"...\"'"

    addopts = match.group(1).split()
    assert "--cov" in addopts, "the local coverage gate is --cov in addopts"
    assert addopts[-1] != "--cov", (
        "--cov is the last token of addopts, so it will swallow the first "
        "positional argument of any command line that has one"
    )


def test_an_explicit_threshold_survives_either_kind_of_run() -> None:
    """`--cov-fail-under` is the caller's, and outranks both branches."""
    assert _threshold(["tests/transport_test.py"], asked=90.0) == 90.0
    assert _threshold([], asked=90.0) == 90.0
    # zero is a threshold somebody asked for, not a missing answer: it
    # has to survive the `is not None` test rather than be falsy
    assert _threshold([], asked=0) == 0
