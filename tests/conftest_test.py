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


def test_a_whole_run_is_gated_at_what_pyproject_configured() -> None:
    """No selection: the ratchet applies, and it is not restated here.

    The number comes back as it was handed in, which is the property
    worth pinning: pyproject.toml is where 100 is decided, and a copy of
    it in this file would be a second place to change it.
    """
    assert coverage_fail_under(None, 100.0, [], "", "") == 100.0
    assert coverage_fail_under(None, 42.0, [], "", "") == 42.0


def test_a_selected_subset_is_gated_at_nothing() -> None:
    """Any of paths, `-k` or `-m` drops the threshold to zero.

    Zero and not None: None is what pytest-cov reads the configured
    threshold into, so it would restore the very gate this removes.
    """
    assert coverage_fail_under(None, 100.0, ["tests/transport_test.py"], "", "") == 0
    assert coverage_fail_under(None, 100.0, ["tests"], "", "") == 0
    assert coverage_fail_under(None, 100.0, [], "getbalance", "") == 0
    assert coverage_fail_under(None, 100.0, [], "", "integration") == 0
    assert (
        coverage_fail_under(
            None, 100.0, ["tests/transport_test.py"], "getbalance", "integration"
        )
        == 0
    )


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
    assert coverage_fail_under(90.0, 100.0, ["tests"], "", "") == 90.0
    assert coverage_fail_under(90.0, 100.0, [], "", "") == 90.0
    # zero is a threshold somebody asked for, not a missing answer: it
    # has to survive the `is not None` test rather than be falsy
    assert coverage_fail_under(0, 100.0, [], "", "") == 0
