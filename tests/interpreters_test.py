# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The interpreters this package claims are the ones it runs on.

One fact, declared three times: `requires-python` is the floor,
`Programming Language :: Python :: X.Y` is what PyPI shows whoever is
choosing the package, and the platform sweeps' own list is what actually
runs.
Nothing compared them, and the three drift in the direction that is
hardest to notice -- a classifier left behind when a floor moves is a
package advertising an interpreter its suite never touches, and the
person it misleads is not reading this repository.

The organization standard's rule is that a library covers every Python
that is not out of support, so all three move together twice around each
October: one version leaves support as another is released. This module
does not know that calendar and does not try to -- python.org keeps it,
and a test that hard-coded a date would be one more thing to move. What
it holds is the weaker and checkable claim: whatever the three say, they
say the same thing.

Read with a regex rather than parsed. `tomllib` arrives in 3.11 and the
floor here is 3.10, so a test that imported it would fail on the oldest
interpreter this package claims -- which is one of the things this module
is about. The workflow is yaml and no group here carries a parser for
that either.
"""

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[1]
_PYPROJECT = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
_WORKFLOWS = sorted((_ROOT / ".github/workflows").glob("*.yml"))
# the three platform sweeps between which the interpreters below are
# supposed to agree, named explicitly so that a sweep whose `python:`
# block stops matching `_PYTHONS` is a workflow the check below can miss,
# rather than one that quietly stops being compared
_SWEEPS = ("os-macos.yml", "os-ubuntu.yml", "os-windows.yml")

# "3.10" out of `requires-python = ">=3.10"`, the floor and nothing else:
# an upper bound is not declared here and would be a different claim
_FLOOR = re.compile(r'^requires-python = ">=(?P<version>3\.\d+)"', re.MULTILINE)
# the per-version classifiers, not `:: 3` or `:: 3 :: Only`, which say
# something about the major version rather than about an interpreter
_CLASSIFIER = re.compile(
    r'^    "Programming Language :: Python :: (?P<version>3\.\d+)",$', re.MULTILINE
)
_PYPY_CLASSIFIER = "Programming Language :: Python :: Implementation :: PyPy"
# PyPI's free-threading classifiers, the bare one and its maturity levels
# alike: each is a claim about the code under a free-threaded build, and
# which is claimed is not this module's question
_FREE_THREADING_CLASSIFIER = re.compile(
    r'^    "Programming Language :: Python :: Free Threading(?: :: .+)?",$',
    re.MULTILINE,
)
# the matrix list a suite workflow builds its cells from. The gate runs
# one interpreter, so the list lives in the weekly platform sweeps now --
# in each of them, which is why they are read together below rather than
# one of them being named here as the one that counts
_PYTHONS = re.compile(
    r"^        python:\n(?P<block>(?:^          - \"\S+\"\n)+)", re.MULTILINE
)
# the merge gate, and inside it the jobs a landing waits on. Section 3 of
# the organization standard declares a free-threading classifier where
# the gate exercises that build, a gate being what refuses the landing
# that breaks it, so the second side is the aggregate's `needs:` closure
# rather than the workflow file: a job of this workflow outside that
# closure reports what a sweep reports, which is the ground that section
# declines, and reading the file is the alternative it names as
# rejected. The aggregate is located by the name main's required contexts
# hold -- a job's `name:` and not its key, REPOSITORY.md's *Required
# checks on main* being where that name is read back from the endpoint
_GATE = _ROOT / ".github/workflows/test.yml"
_AGGREGATE = "test: every job passed"
# `jobs:` and everything under it: the trigger keys of `on:` sit at the
# same indent as a job key, so a pattern that did not cut here would
# offer `pull_request` to the closure below as though it were a job
_JOBS = re.compile(r"^jobs:\n(?P<block>.*)\Z", re.MULTILINE | re.DOTALL)
# a job key at the one indent `jobs:` gives them, and the block that
# follows it, which ends at the next line indented less than three
# spaces -- a comment between two jobs, this file writing those at two
_JOB = re.compile(
    r"^  (?P<key>[a-z0-9_-]+):\n(?P<block>(?:^ {3,}.*\n|^\n)*)", re.MULTILINE
)
# `needs:` in each of the three shapes GitHub takes -- one job after the
# key, a flow list there, and a block list under it -- read as whatever
# follows the key on its own line plus the items below it. A reader blind
# to the block shape answers a closure short of whatever sits behind an
# edge written that way, and the biconditional below then passes on a gate
# it has not read (btclib-org/.github#1031).
#
# The run of items takes a comment line and a blank one as well, and an
# item's own trailing comment with it: a whole-line comment among the
# items, a blank line between two of them and a `#` after an item are one
# thing to a yaml reader, and a run of adjacent item lines ends at each of
# them and drops every item below. A tree that strips comments before the
# job blocks are read meets whitespace where this one meets the comment,
# so both arrive here and one spelling answers for the organization's
# copies of this module rather than for this tree
# (btclib-org/.github#1038).
#
# What the run must not take is a step: `steps:` entries sit at the item
# indent, and `      - name: Setup uv` is kept out by an item being the
# whole line up to its comment
_NEEDS = re.compile(
    r"^    needs:(?P<inline>[^#\n]*)(?:#[^\n]*)?\n"
    r"(?P<items>(?:^      - \S+[ \t]*(?:#[^\n]*)?\n|^[ \t]*(?:#[^\n]*)?\n)*)",
    re.MULTILINE,
)
# one item of the block list above, the key picked off a line the run has
# already read as an item
_ITEM = re.compile(r"^      - (?P<key>\S+)", re.MULTILINE)
_NAME = re.compile(r'^    name: "?(?P<name>[^"\n]*?)"?$', re.MULTILINE)
_KEY = re.compile(r"[\w-]+")
# each gating job writes the interpreter it runs into itself, as
# `python-version: "3.14"` or `--python 3.14`, and a free-threaded build
# is a "3.14t" of the same shape, so they are read as tokens off the job
# block rather than out of a matrix. Comments go first, so that a
# sentence about a sweep's free-threaded cell does not read as the gate
# running one. What this does not read is .python-version: a job pointed
# at it through `python-version-file:` names its interpreter nowhere in
# this file, so a `t` in that pin would be missed here -- no job of the
# gate is written that way
_COMMENT = re.compile(r"(?:^|\s)#.*$", re.MULTILINE)
_INTERPRETER = re.compile(r"\b3\.\d+t?\b")


def _versions(pattern: re.Pattern[str], text: str) -> tuple[str, ...]:
    """Return every `version` group `pattern` finds, in order."""
    return tuple(m["version"] for m in pattern.finditer(text))


def _declared() -> dict[str, tuple[str, ...]]:
    """Return each workflow's interpreter list, those that declare one."""
    found: dict[str, tuple[str, ...]] = {}
    for workflow in _WORKFLOWS:
        listed: set[str] = set()
        text = workflow.read_text(encoding="utf-8")
        for match in _PYTHONS.finditer(text):
            listed.update(
                line.strip().removeprefix('- "').removesuffix('"')
                for line in match["block"].splitlines()
            )
        if listed:
            found[workflow.name] = tuple(sorted(listed))
    return found


def _jobs() -> dict[str, str]:
    """Return the merge gate's job blocks, keyed by the job's own key."""
    found: dict[str, str] = {}
    for under in _JOBS.findall(_GATE.read_text(encoding="utf-8")):
        found.update({m["key"]: m["block"] for m in _JOB.finditer(under)})
    return found


def _named(block: str) -> str:
    """Return the `name:` a job block declares, empty where it declares none."""
    name = _NAME.search(block)
    return name["name"] if name else ""


def _needed(block: str) -> set[str]:
    """Return the job keys a job block's `needs:` names."""
    return {
        key
        for match in _NEEDS.finditer(block)
        for key in _KEY.findall(match["inline"]) + _ITEM.findall(match["items"])
    }


def _gating() -> dict[str, str]:
    """Return the blocks of the jobs the required check waits on."""
    jobs = _jobs()
    closure: set[str] = set()
    pending = [key for key, block in jobs.items() if _named(block) == _AGGREGATE]
    while pending:
        key = pending.pop()
        closure.add(key)
        pending.extend((_needed(jobs[key]) & set(jobs)) - closure)
    return {key: jobs[key] for key in closure}


def _gate_interpreters() -> tuple[str, ...]:
    """Return every interpreter a gating job names outside its comments."""
    found: set[str] = set()
    for block in _gating().values():
        found.update(_INTERPRETER.findall(_COMMENT.sub("", block)))
    return tuple(sorted(found))


def _matrix() -> tuple[str, ...]:
    """Return the interpreters the platform sweeps name."""
    found: set[str] = set()
    for listed in _declared().values():
        found.update(listed)
    return tuple(sorted(found))


_CLASSIFIED = _versions(_CLASSIFIER, _PYPROJECT)
_MATRIX = _matrix()
# the free-threaded build and PyPy are the same interpreter version as
# far as a classifier is concerned: "3.14t" is CPython 3.14, and
# "pypy-3.11" is what the PyPy classifier covers rather than a version
# of its own
_CPYTHON = tuple(sorted({v.rstrip("t") for v in _MATRIX if not v.startswith("pypy")}))


def test_the_three_declarations_were_read() -> None:
    """Each pattern found something, so the checks below quantify over it.

    A key renamed, a classifier reindented, the workflow's block moved:
    each would leave one of these empty and every comparison below
    trivially true.
    """
    assert _FLOOR.search(_PYPROJECT), "pyproject.toml declares no requires-python"
    assert _CLASSIFIED, "pyproject.toml declares no per-version Python classifier"
    assert _MATRIX, "no workflow declares a python matrix block"


def test_the_floor_is_the_lowest_classifier() -> None:
    """`requires-python` and the classifiers name the same oldest Python."""
    floor = _FLOOR.search(_PYPROJECT)
    assert floor, "pyproject.toml declares no requires-python"
    lowest = min(_CLASSIFIED, key=lambda v: tuple(int(p) for p in v.split(".")))
    assert floor["version"] == lowest, (
        f"requires-python is >={floor['version']} and the lowest classifier"
        f" is {lowest}: one of the two was moved and the other was not"
    )


def test_every_classified_interpreter_is_in_the_matrix() -> None:
    """A version PyPI advertises is a version the suite runs."""
    unrun = [v for v in _CLASSIFIED if v not in _CPYTHON]
    assert not unrun, (
        f"classified and no workflow runs it: {', '.join(unrun)}."
        " PyPI shows a classifier to whoever is choosing this package"
    )


def test_every_matrix_interpreter_is_classified() -> None:
    """A version the suite runs is a version PyPI advertises."""
    unclassified = [v for v in _CPYTHON if v not in _CLASSIFIED]
    assert not unclassified, (
        f"run by a workflow and not classified: {', '.join(unclassified)}"
    )


def test_pypy_is_classified_exactly_when_it_is_run() -> None:
    """The PyPy classifier is a claim about the matrix, not a decoration."""
    classified = _PYPY_CLASSIFIER in _PYPROJECT
    run = any(v.startswith("pypy") for v in _MATRIX)
    assert classified == run, (
        f"the PyPy classifier is {'present' if classified else 'absent'} and"
        f" the matrix {'runs' if run else 'does not run'} a PyPy interpreter"
    )


def test_free_threading_is_classified_exactly_when_the_gate_runs_it() -> None:
    """The free-threading classifier is a claim about the merge gate.

    The organization standard declares one where the gate exercises the
    free-threaded build: a gate refuses the landing that breaks that
    build, where a sweep runs beside a landing and blocks nothing. So the
    second side here is the jobs `test: every job passed` waits on and
    not `_MATRIX` -- the sweeps name "3.14t" as readily as the gate
    would, and a sweep passing is the ground the standard declines.

    The closure is read from a job key pattern and a `needs:` one, and
    either could stop matching: an empty closure names no free-threaded
    interpreter for a reason that has nothing to do with the gate, so
    the aggregate is asserted to be in it before anything is compared.
    """
    gating = _gating()
    assert _AGGREGATE in {_named(block) for block in gating.values()}, (
        f'no job of test.yml is named "{_AGGREGATE}", so the jobs a landing'
        " waits on were read from nothing"
    )
    gate = _gate_interpreters()
    assert gate, "no job the merge gate waits on names an interpreter"
    classified = bool(_FREE_THREADING_CLASSIFIER.search(_PYPROJECT))
    run = [v for v in gate if v.endswith("t")]
    assert classified == bool(run), (
        f"the free-threading classifier is {'present' if classified else 'absent'}"
        " and the jobs the gate waits on name"
        f" {', '.join(run) or 'no free-threaded interpreter'}"
    )


def test_needed_reads_needs_in_every_shape_the_gate_may_take(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job after the key, a flow list there, a block list under it.

    GitHub takes all three and they name the same jobs, so a reader of
    two of them answers a closure short of whatever sits behind an edge
    written in the third -- short in silence, the `no job ... names an
    interpreter` assertion above firing only where the aggregate's own
    `needs:` is the unread one (btclib-org/.github#1031). No job of
    `test.yml` writes a block list, so the text read here is its own.

    A whole-line comment among the items, a blank line between two of
    them and a trailing comment on one each end a run of adjacent item
    lines, and each is one thing to a yaml reader
    (btclib-org/.github#1038). A comment reaches this module as it was
    written, where a tree stripping comments ahead of the job blocks
    meets whitespace in its place, so both forms stand below and one
    spelling answers for the organization's copies of this module.
    """
    tail = "    runs-on: ubuntu-latest\n"
    both = {"changes", "coverage"}
    flow = f"    needs: [changes, coverage]\n{tail}"
    scalar = f"    needs: changes\n{tail}"
    under_the_key = {
        "a block list": f"    needs:\n      - changes\n      - coverage\n{tail}",
        "a comment among the items": (
            "    needs:\n"
            "      - changes\n"
            "      # the cell the coverage floor is measured on\n"
            f"      - coverage\n{tail}"
        ),
        "that comment stripped": (
            f"    needs:\n      - changes\n     \n      - coverage\n{tail}"
        ),
        "a comment on an item": (
            f"    needs:\n      - changes  # the gate\n      - coverage\n{tail}"
        ),
        "that one stripped": (
            f"    needs:\n      - changes \n      - coverage\n{tail}"
        ),
        "a blank line between two items": (
            f"    needs:\n      - changes\n\n      - coverage\n{tail}"
        ),
    }
    assert _needed(flow) == both
    assert _needed(scalar) == {"changes"}
    for shape, block in under_the_key.items():
        assert _needed(block) == both, shape
    # the control: a reader of the key's own line and nothing under it --
    # which is what this module read before -- answers the same for the
    # two shapes that write the list there and nothing at all for the
    # shapes that write it below, so what the assertions above turn on is
    # the items being read rather than the text merely being job text
    monkeypatch.setattr(
        sys.modules[__name__],
        "_NEEDS",
        re.compile(
            r"^    needs:(?P<inline>[^#\n]*)(?:#[^\n]*)?\n(?P<items>)", re.MULTILINE
        ),
    )
    assert _needed(flow) == both
    assert _needed(scalar) == {"changes"}
    for shape, block in under_the_key.items():
        assert _needed(block) == set(), shape


def test_needed_reads_no_step_of_a_job_as_a_job_it_waits_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `steps:` entry sits at the item indent and is not an item.

    `      - name: Setup uv` differs from an item in what follows the
    dash and in nothing else, so a run widened to take the rest of the
    line reads its first token as a job and goes on reading below it.
    What ends the run ahead of a real job's steps is the `steps:` key,
    written at the indent a job's keys take, so the text that separates
    the two readings is a step line where an item goes; the widened
    reader below is what says so, both readings answering alike on the
    job whose steps follow its `needs:`.
    """
    steps = (
        "    needs:\n"
        "      - changes\n"
        "      - coverage\n"
        "    steps:\n"
        "      - name: Setup uv\n"
        "        uses: astral-sh/setup-uv@v7\n"
    )
    misplaced = (
        "    needs:\n      - changes\n      - name: Setup uv\n      - coverage\n"
    )
    assert _needed(steps) == {"changes", "coverage"}
    assert _needed(misplaced) == {"changes"}
    monkeypatch.setattr(
        sys.modules[__name__],
        "_NEEDS",
        re.compile(
            r"^    needs:(?P<inline>[^#\n]*)(?:#[^\n]*)?\n"
            r"(?P<items>(?:^      - \S+[^\n]*\n|^[ \t]*(?:#[^\n]*)?\n)*)",
            re.MULTILINE,
        ),
    )
    assert _needed(steps) == {"changes", "coverage"}
    assert _needed(misplaced) == {"changes", "name:", "coverage"}


def test_every_sweep_runs_the_same_interpreters() -> None:
    """One interpreter set, however many platforms sweep it.

    The gate runs one, so the list is declared once per platform sweep
    and nowhere else. Three copies of a list is three chances for one of
    them to be left behind, and a platform quietly running a narrower set
    than another reads, from the outside, as that platform passing.

    Agreement among the lists found only means something once every sweep
    was actually found: `_declared()` keeps a workflow only where its
    `python:` block matched, so a sweep that stopped matching drops out of
    the comparison instead of disagreeing with it, and the fewer sweeps
    survive the weaker -- and, at one, vacuous -- the claim below becomes.
    """
    declared = _declared()
    assert tuple(sorted(declared)) == _SWEEPS, (
        f"the platform sweeps are {', '.join(_SWEEPS)} and the interpreter"
        f" block was read from {', '.join(sorted(declared)) or 'none of them'}"
    )
    lists = set(declared.values())
    assert len(lists) <= 1, (
        f"the workflows do not name the same interpreters: {declared}"
    )
