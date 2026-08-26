# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""What the whole suite shares: the coverage gate a selective run drops.

`coverage_fail_under` below takes btclib's reasoning from its
tests/conftest.py rather than deriving a second one: the two answer the
same question about the same pytest hooks. The two docstrings are not the
same text and cannot be -- each names an example path out of the suite it
sits in -- so a difference between them is not a drift to close, and
neither file is the other's copy of record. This file has no hypothesis
profile and no golden-file fixture to carry, `--cov` in addopts being the
one thing bitcoin-core-rpc's suite and btclib's share.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def asks_for_everything(
    file_or_dir: list[str] | None,
    *,
    invocation_dir: Path,
    testpaths: list[Path],
) -> bool:
    """Return whether the paths named on the command line take the suite in.

    No path at all is `testpaths`, which is the suite. A path at or
    above one of those entries collects it whole, so what decides is
    containment and not equality: read as equality, `pytest tests` is a
    subset -- and it is what somebody types who means the whole suite
    and says so.

    The two bases are different directories, which `pytest .` run from
    `tests/` shows: pytest reads a positional argument against the
    directory it was invoked from, and `testpaths` against the rootdir.

    `file_or_dir` is `None` rather than `[]` on the `--help` path, the
    positional never having been parsed, and that names no path either
    -- folding it in is what keeps `--help` from ending in a traceback
    whose last frame is this file.
    """
    given = [(invocation_dir / path).resolve() for path in file_or_dir or []]
    if not given:
        return True
    wanted = [path.resolve() for path in testpaths]
    if not wanted:
        # `all` over nothing is true, which would make every path named
        # here the whole suite. Nothing names the suite, so a bare run
        # collects the rootdir and anything asked for is less than it
        return False
    return all(
        any(target == path or path in target.parents for path in given)
        for target in wanted
    )


def coverage_fail_under(
    asked: float | None,
    configured: float | None,
    file_or_dir: list[str] | None,
    keyword: str,
    markexpr: str,
    *,
    invocation_dir: Path,
    testpaths: list[Path],
) -> float | None:
    """Return the coverage threshold this run's selection has to meet.

    `--cov` is in addopts, so the 100% ratchet is what a bare `uv run
    pytest` measures rather than something only the coverage job reaches:
    a gate that CI alone runs is one a change meets after it is pushed.
    What that costs is this function. `fail_under` applies to every
    report coverage writes, a partial one included, so `pytest
    tests/transport_test.py` would end in `Required test coverage of
    100.0% not reached` -- true of that run and saying nothing about the
    tree. Running one file and one test are documented commands, and a
    gate that fails them is a gate read as noise.

    So a run that asked for a subset is gated at zero rather than having
    coverage switched off: the report still prints, which is what makes
    it worth measuring while iterating on one module. A whole run is
    handed back `configured`, the threshold pytest-cov has already read
    out of the coverage configuration, so pyproject.toml stays the one
    place the number lives.

    The two thresholds are two arguments because by the time any of this
    runs they no longer agree. pytest-cov fills `cov_fail_under` from the
    coverage configuration in `pytest_load_initial_conftests`, before
    `pytest_configure`, so "the option is set" has stopped meaning
    "somebody asked for it": what still means that is `config.option`,
    which carries only what the command line and addopts put there. An
    explicit `--cov-fail-under` is therefore `asked`, and is handed back
    untouched whichever kind of run it is -- the caller naming the
    threshold is the one thing this must not overrule.

    A subset is what pytest was *asked* for: `-k`, `-m`, or paths that
    leave part of the suite out, which is `asks_for_everything`'s
    question and not whether a path was named at all. Not every way a
    run can be short -- `--lf`, `--deselect` and an `-x` that stops early
    are not read -- so those still meet the full threshold and report a
    shortfall the tree does not have. They are the flags of an iteration
    whose next run is the whole suite, and reading intent off all of
    them would make this a second definition of what a real run is.
    """
    if asked is not None:
        return asked
    whole_suite = asks_for_everything(
        file_or_dir, invocation_dir=invocation_dir, testpaths=testpaths
    )
    if not whole_suite or keyword or markexpr:
        return 0
    return configured


def pytest_configure(config: pytest.Config) -> None:
    """Gate a whole run at `fail_under`, and a partial one at nothing.

    The threshold is written to `known_args_namespace` and not to
    `config.option`: pytest builds the first by parsing the known
    arguments into a *copy* of the second, and pytest-cov holds on to
    that copy. Writing to `config.option` instead runs without error and
    changes nothing -- the plugin never reads it back, and the run still
    fails on the whole tree's coverage.
    """
    testpaths: list[str] = config.getini("testpaths")
    namespace = config.known_args_namespace
    namespace.cov_fail_under = coverage_fail_under(
        config.option.cov_fail_under,
        namespace.cov_fail_under,
        config.option.file_or_dir,
        config.option.keyword,
        config.option.markexpr,
        invocation_dir=config.invocation_params.dir,
        testpaths=[config.rootpath / path for path in testpaths],
    )
