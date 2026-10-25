# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""A fuzz/corpus/ seed is still a reply one of its entry points reads.

`fuzz/fuzz_<name>.py` and `fuzz/corpus/fuzz_<name>/` are read from disk;
neither is imported. Every harness imports atheris at module level,
which is CI-only and undeclared in `[dependency-groups]`, so this module
never runs `import fuzz.fuzz_<name>` and never executes a harness's own
code -- it parses the source with `ast` and resolves what a harness
*names* against the installed package instead.

`ENTRY_POINTS`, a module-level tuple of `"module:name"` string literals,
is what each harness names, and `fuzz_target`'s own body has to call
each of them and each decoder `tests/fuzz_test.py` lists. Each takes
`(where, status, payload)`. Every seed is then tried against every entry
point as a reply with status 200, and passes if at least one reads it
without raising `FetchError`.

What this gate is for is keeping the fuzzer's own starting point honest
as the decoders move under it. A crash the fuzzer finds is a test of the
ordinary suite, naming the input and what the decoder now does with it,
and never a seed: a seed is a valid reply. This gate reads each seed with
the entry points alone, so it does not drive the clients as the harness
does and cannot tell a seed that crashes them.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any

import pytest

from bitcoin_core_rpc.errors import FetchError
from tests.fuzz_test import DECODERS

# the arguments a seed is read with besides its bytes: where it came from,
# for the message of a refusal, and the status of an answer
_WHERE = "fuzz"
_OK = 200

_FUZZ = Path(__file__).parent.parent / "fuzz"
_CORPUS = _FUZZ / "corpus"


def _harness_paths() -> tuple[Path, ...]:
    """Every fuzz/fuzz_*.py, sorted for a stable parametrize order."""
    return tuple(sorted(_FUZZ.glob("fuzz_*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _entry_points(tree: ast.Module) -> tuple[str, ...]:
    """Return the one module-level ENTRY_POINTS tuple of strings."""
    (value,) = (
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "ENTRY_POINTS"
    )
    assert isinstance(value, tuple)
    assert all(isinstance(v, str) for v in value)
    return value


def _called(tree: ast.Module) -> set[str]:
    """Every `module.function(...)` call `fuzz_target`'s body makes.

    As "package.module:function", the module resolved through the
    `from package import module` that binds its name, so a call is
    compared with a declared entry point in the one spelling both share.
    """
    bindings = {
        alias.asname or alias.name: f"{node.module}.{alias.name}"
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
        for alias in node.names
    }
    (target,) = (
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "fuzz_target"
    )
    return {
        f"{bindings[node.func.value.id]}:{node.func.attr}"
        for node in ast.walk(target)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in bindings
    }


def _resolve(spec: str) -> Any:
    """Import the callable a "module:name" spec names."""
    module_name, _, name = spec.partition(":")
    return getattr(importlib.import_module(module_name), name)


def _seed_paths(name: str) -> tuple[Path, ...]:
    return tuple(sorted((_CORPUS / name).glob("*.bin")))


_HARNESSES = _harness_paths()
_SEEDS = tuple((path, seed) for path in _HARNESSES for seed in _seed_paths(path.stem))


def test_the_corpus_is_not_empty() -> None:
    """Every assertion below quantifies over _HARNESSES and _SEEDS."""
    assert _HARNESSES, f"{_FUZZ} holds no fuzz_*.py"
    assert _SEEDS, f"{_CORPUS} holds no seed"


def test_every_corpus_directory_has_a_harness_and_back() -> None:
    """A harness with no seeds, or seeds with no harness, is unchecked."""
    harnesses = {path.stem for path in _HARNESSES}
    directories = {d.name for d in _CORPUS.iterdir() if d.is_dir()}
    assert harnesses == directories


@pytest.mark.parametrize("path", _HARNESSES, ids=lambda p: p.stem)
def test_entry_points_are_what_the_target_calls(path: Path) -> None:
    """ENTRY_POINTS is declared, resolves, and is what fuzz_target calls."""
    tree = _tree(path)
    declared = _entry_points(tree)
    assert declared, f"{path.name} declares no non-empty ENTRY_POINTS"
    for spec in declared:
        assert callable(_resolve(spec)), spec
    called = _called(tree)
    assert set(declared) <= called, sorted(set(declared) - called)


@pytest.mark.parametrize(
    ("path", "seed"), _SEEDS, ids=[f"{p.stem}/{s.name}" for p, s in _SEEDS]
)
def test_every_seed_is_read(path: Path, seed: Path) -> None:
    """At least one entry point reads the seed without refusing it."""
    payload = seed.read_bytes()
    read = []
    for spec in _entry_points(_tree(path)):
        try:
            _resolve(spec)(_WHERE, _OK, payload)
        except FetchError:
            continue
        read.append(spec)
    assert read, f"no entry point of {path.name} reads {seed.name}"


def test_every_decoder_the_mutation_tests_drive_is_fuzzed() -> None:
    """Each decoder of fuzz_test.DECODERS is called by a harness's target."""
    called = set().union(*(_called(_tree(path)) for path in _HARNESSES))
    missing = {name for name in DECODERS if name not in called}
    assert not missing, sorted(missing)
