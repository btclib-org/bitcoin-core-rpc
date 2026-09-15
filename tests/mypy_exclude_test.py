# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`[tool.mypy] exclude` is a regex, not a glob, and reaches every source file.

`mypy.modulefinder.matches_exclude` (uv.lock's pinned mypy) is
`re.search(pattern, subpath)`, unanchored unless the pattern itself
anchors -- so `"build"` drops any path merely containing that substring,
not only the top-level `build/` directory a packaging tool writes.
`.github/scripts/wait_for_readthedocs_build.py` and
`tests/wait_for_readthedocs_build_test.py` left the type gate this way:
neither is reached by a static `import` the gate's own crawl does follow
-- the test loads the script at run time, through
`importlib.util.spec_from_file_location`, which mypy does not trace, and
nothing statically imports a test -- so both were silently unchecked
while `uv run --locked --no-default-groups --group lint --group test
mypy src/bitcoin_core_rpc tests .github/scripts` exited 0 throughout
(issue btclib-org/.github#1102).

This tree carries no standalone `uv run mypy ...` line in
`CONTRIBUTING.md` the way a sibling repository's does: here the type
gate runs only inside `.pre-commit-config.yaml`'s `mypy` hook, so this
module reads that hook's own `entry:` for the roots and `pyproject.toml`
for the `exclude` list, rather than importing mypy or invoking
`pre-commit`, which `test`'s own environment does not carry.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).parents[1]
_PYPROJECT = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
_HOOKS = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

# the section alone, so a `[tool.ruff.format]` or `[tool.typos.files]`
# `exclude` sitting elsewhere in the file is never read as this one
_MYPY_SECTION = re.compile(r"(?ms)^\[tool\.mypy\]\n(.*?)(?=\n\[|\Z)")
_EXCLUDE_LIST = re.compile(r"(?ms)^exclude = \[\n(.*?)^\]")
_LIST_ITEM = re.compile(r'^\s*"((?:[^"\\]|\\.)*)",?\s*$', re.MULTILINE)


def _mypy_exclude_patterns() -> tuple[str, ...]:
    section = _MYPY_SECTION.search(_PYPROJECT)
    assert section is not None, "[tool.mypy] is not in pyproject.toml"
    exclude_list = _EXCLUDE_LIST.search(section.group(1))
    assert exclude_list is not None, "[tool.mypy] carries no exclude list"
    return tuple(_LIST_ITEM.findall(exclude_list.group(1)))


def _fold_block_scalar(text: str, after: str) -> str:
    """Fold the block scalar that starts on the line right after `after`.

    `>` is YAML's fold indicator, one line break becomes one space, so
    unwrapping a wrapped `entry:` by hand is what turns its physical
    lines back into the one command a shell runs. Ends at a line whose
    indentation is no deeper than `after`'s own, or at the text's end
    where none dedents first -- `.pre-commit-config.yaml` always dedents
    into `language:` before the file ends, so a case reaching the text's
    end is exercised by a test written for the shape rather than by that
    file.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == after), None)
    assert start is not None, f"no line reading {after!r} in the text handed to this"
    indent = len(lines[start]) - len(lines[start].lstrip(" "))
    block: list[str] = []
    for line in lines[start + 1 :]:
        this_indent = len(line) - len(line.lstrip(" "))
        if line.strip() and this_indent <= indent:
            break
        block.append(line.strip())
    return " ".join(block)


def _mypy_hook_command() -> str:
    """Return the `mypy` hook's `entry:`, folded the way YAML `>` folds it.

    A parser bought nothing further here: `entry: >` names one hook in
    the whole file, so finding it by its own text is exact.
    """
    return _fold_block_scalar(_HOOKS, "entry: >")


def _gate_roots() -> tuple[str, ...]:
    command = _mypy_hook_command()
    tokens = command.split()
    assert "mypy" in tokens, f"the mypy hook's entry does not invoke mypy: {command!r}"
    return tuple(tokens[tokens.index("mypy") + 1 :])


def _excluded(relative_posix_path: str, patterns: tuple[str, ...]) -> bool:
    """Whether mypy's own crawl would drop this path, its own way of asking.

    `re.search`, unanchored, over every pattern -- `matches_exclude`'s own
    logic, without importing the package that carries it.
    """
    return any(re.search(pattern, relative_posix_path) for pattern in patterns)


def _census(roots: tuple[str, ...]) -> tuple[str, ...]:
    """Every `.py` file under the gate's own roots, relative to the root."""
    files: list[str] = []
    for root in roots:
        files.extend(
            str(path.relative_to(_ROOT).as_posix())
            for path in sorted((_ROOT / root).rglob("*.py"))
        )
    return tuple(files)


def test_the_exclude_reaches_the_directory_it_names() -> None:
    """A real `build/` output stays out, proving the control has teeth."""
    patterns = _mypy_exclude_patterns()
    assert _excluded("build/lib/bitcoin_core_rpc/version.py", patterns)


def test_fold_block_scalar_runs_to_the_texts_end_with_no_dedent() -> None:
    """A block scalar the text ends inside of is folded to its last line too.

    Nothing in `.pre-commit-config.yaml` exercises the loop finishing
    without a `break`, since its own `entry:` always dedents into
    `language:` before the file ends; this constructs that shape
    directly rather than leaving it unmeasured.
    """
    text = "  entry: >\n    one\n    two\n"
    assert _fold_block_scalar(text, "entry: >") == "one two"


def test_the_gate_roots_are_read_from_the_hook_that_runs_them() -> None:
    """The roots this module walks are the ones the type gate actually walks.

    Fixed against a hard-coded triple: a root added to the hook and not
    here would otherwise leave this test silently narrower than the gate
    it stands in for.
    """
    assert _gate_roots() == ("src/bitcoin_core_rpc", "tests", ".github/scripts")


def test_the_exclude_drops_nothing_the_gate_command_names() -> None:
    """Every source the documented command walks is one mypy still checks.

    An exclude entry unanchored the way `"build"` was drops any path
    carrying that substring, silently -- the census below is what makes
    that regression visible again the next time an entry is loosened.
    """
    patterns = _mypy_exclude_patterns()
    census = _census(_gate_roots())
    excluded = [path for path in census if _excluded(path, patterns)]
    assert not excluded, f"the exclude drops {excluded} from the type gate"
