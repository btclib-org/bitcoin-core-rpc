# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The source guard of conftest stops a real run, in a checkout.

The case needs `.github/scripts` beside `pyproject.toml`, which is what
the guard refuses to leave unmeasured. The sdist ships no `.github`, so
there the guard has nothing to refuse, and `pyproject.toml`'s
`source-exclude` keeps this module out of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .conftest_test import _ROOT, _run_from_tests

if TYPE_CHECKING:
    from pathlib import Path


def test_a_run_from_tests_with_its_rootdir_there_is_refused(tmp_path: Path) -> None:
    """The guard stops a real run whose rootdir is `tests/`.

    `--cov-config` points coverage at `pyproject.toml`, `--rootdir=.` makes
    `tests/` the rootdir, and `.` names the suite, which keeps pytest from
    failing first on a `testpaths` it finds nothing under. Let through,
    that run passes the floor without measuring `.github/scripts`.

    The `-k` matches no test, so that a guard that lets the run through
    collects the suite and stops there, rather than running it inside this
    one. The guard does not read `-k`.
    """
    completed = _run_from_tests(
        tmp_path,
        "--rootdir=.",
        "--cov-config=../pyproject.toml",
        "-k",
        "no_test_is_named_this",
        ".",
    )

    assert completed.returncode == pytest.ExitCode.USAGE_ERROR, completed.stderr
    assert "coverage would not measure .github/scripts:" in completed.stderr
    assert f"Run from {_ROOT}." in completed.stderr
