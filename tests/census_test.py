# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The package's census: the public surface, the documentation, the imports.

Everything else in the suite runs with the package installed, which is
exactly the arrangement that cannot tell these three properties from ones
that merely happen to hold today. `errors.py`, `chains.py`, `transport.py`
and `client.py` are what defines the public surface; `__init__.py` is the
facade that only re-exports it, so it is read for `__all__` and not
walked for definitions of its own.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

import bitcoin_core_rpc

# errors < chains < transport < client, the order stated in each module's
# own docstring and in CLAUDE.md's architecture section: a module may
# import any of the ones before it and none of the ones after
_MODULE_ORDER = ("errors", "chains", "transport", "client")


def _source_paths() -> tuple[Path, ...]:
    """Return the path of every module that defines the public surface."""
    init_path = bitcoin_core_rpc.__file__
    assert init_path is not None
    package = Path(init_path).parent
    return tuple(package / f"{name}.py" for name in _MODULE_ORDER)


def _documented_names(source: str) -> set[str]:
    body = ast.parse(source).body
    documented = set()
    for position, statement in enumerate(body):
        if isinstance(statement, (ast.FunctionDef, ast.ClassDef)):
            if ast.get_docstring(statement):
                documented.add(statement.name)
            continue
        following = body[position + 1] if position + 1 < len(body) else None
        # PEP 258's attribute docstring: the string literal *after* the
        # assignment, which is what sphinx reads and what `ast` gives no
        # accessor for
        target = (
            statement.targets[0]
            if isinstance(statement, ast.Assign)
            else statement.target
            if isinstance(statement, ast.AnnAssign)
            else None
        )
        name = getattr(target, "id", None)
        if (
            name is not None
            and isinstance(following, ast.Expr)
            and isinstance(following.value, ast.Constant)
            and isinstance(following.value.value, str)
        ):
            documented.add(name)
    return documented


def test_the_docstring_scan_reads_what_automodule_would() -> None:
    """The scan below reports nothing on this tree, so it is read here.

    Every module-level definition of the package carries a docstring and
    every name of `__all__` is documented, which is the property the next
    test states -- and it leaves that test unable to distinguish a scan
    that works from one that returns everything it is asked about. This
    source has one of each kind: a definition with a docstring and one
    without, an assignment followed by a string literal and one followed
    by nothing.
    """
    source = (
        'class Documented:\n    """Yes."""\n\n'
        "class Bare:\n    x = 1\n\n"
        'def documented() -> None:\n    """Yes."""\n\n'
        "def bare() -> None:\n    return None\n\n"
        'DOCUMENTED = 1\n"""Yes."""\n\n'
        "BARE = 2\n"
    )
    assert _documented_names(source) == {"Documented", "documented", "DOCUMENTED"}


def test_every_public_name_carries_a_docstring() -> None:
    """`docs/source/api.rst` says the page lists the whole public surface.

    `automodule` with `:members:` documents a class or a function by its
    docstring and a module-level assignment by the string literal that
    follows it -- a `#` comment is neither, so a constant carrying one is
    absent from the built page rather than undescribed on it. That is the
    way this promise goes false without anything looking wrong: the
    comment is right there in the source, and the page it never reaches
    is the interface a consumer reads at readthedocs.
    """
    documented: set[str] = set()
    for path in _source_paths():
        documented |= _documented_names(path.read_text(encoding="utf-8"))
    undocumented = sorted(set(bitcoin_core_rpc.__all__) - documented)
    # named, because pytest elides the difference of two sets this size and
    # what the next reader needs is which name arrived without one
    assert not undocumented, f"public names with no docstring: {undocumented}"


def _public_names(source: str) -> set[str]:
    """Return the module-level names a bare `import *` would offer.

    Definitions and assignments, less whatever a leading underscore keeps
    out. Imports are not read: a name a module imported from another one
    of this package, or from the standard library, is not part of what it
    publishes, so counting them would report the standard library -- or a
    sibling module -- as an unexported surface of its own. Reading the
    source rather than the imported module is what lets a constant and a
    type alias be seen at all -- neither carries a `__module__` to be
    filtered on.
    """
    names: set[str] = set()
    for statement in ast.parse(source).body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(statement.name)
            continue
        target = (
            statement.targets[0]
            if isinstance(statement, ast.Assign)
            else statement.target
            if isinstance(statement, ast.AnnAssign)
            else None
        )
        name = getattr(target, "id", None)
        if name is not None:
            names.add(name)
    return {name for name in names if not name.startswith("_")}


def test_the_census_scan_reads_what_import_star_would() -> None:
    """The scan below reports nothing on this tree, so it is read here.

    Same reason as the docstring scan two tests up: a walk that finds no
    unexported name is indistinguishable from one that finds nothing at
    all. This source carries every shape the walk decides differently
    about -- each kind of definition, a plain and an annotated
    assignment, a target that is not a name, an import, and one of each
    behind a leading underscore.
    """
    source = (
        "import json\n"
        "from decimal import Decimal\n"
        "class Klass: pass\n"
        "class _Private: pass\n"
        "def function() -> None: pass\n"
        "def _helper() -> None: pass\n"
        "async def coroutine() -> None: pass\n"
        "CONSTANT = 1\n"
        "_PRIVATE = 2\n"
        "ANNOTATED: int = 3\n"
        "_ANNOTATED: int = 4\n"
        "CONSTANT[0] = 5\n"
    )
    assert _public_names(source) == {
        "Klass",
        "function",
        "coroutine",
        "CONSTANT",
        "ANNOTATED",
    }


def test_every_public_name_is_exported() -> None:
    """`__all__` is the public surface, so nothing may be public beside it.

    `CONTRIBUTING.md` says a name is public because that list says so and
    not because it lacks an underscore, and this is what makes the
    sentence true rather than aspirational: a name added to a module of
    the package without being exported fails here, which is the census
    section 7 of the organization standard asks a publishing package for.
    `py.typed` ships, so which names are supported is half of what the
    distribution promises.
    """
    names: set[str] = set()
    for path in _source_paths():
        names |= _public_names(path.read_text(encoding="utf-8"))
    exported = set(bitcoin_core_rpc.__all__)
    # named rather than counted: what the next reader needs is which name
    # arrived without an export, and a set difference pytest elides
    unexported = sorted(names - exported)
    assert not unexported, f"public names missing from __all__: {unexported}"
    # the other direction, which fails at import time for a caller writing
    # `from bitcoin_core_rpc import *` and nowhere else in this suite
    missing = sorted(exported - names)
    assert not missing, f"__all__ names nothing defines: {missing}"


def test_the_package_imports_only_the_standard_library() -> None:
    """No module of the package takes a dependency outside itself.

    A module importing another module of this same package is not a
    dependency -- `_MODULE_ORDER` is the order that makes such an import
    acyclic -- so a root of `bitcoin_core_rpc` is excluded here and
    checked on its own below, against the order rather than against the
    standard library.
    """
    for path in _source_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_roots = {
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imported_roots.update(
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        imported_roots.discard("bitcoin_core_rpc")
        outside = imported_roots - {*sys.stdlib_module_names, "__future__"}
        assert not outside, (
            f"{path.name} imports {outside}, outside the standard library"
        )


def _bitcoin_core_rpc_imports(tree: ast.Module) -> set[str]:
    """Return every sibling module a tree of this package imports, by name.

    Three spellings reach one: `from bitcoin_core_rpc.chains import X`,
    `from bitcoin_core_rpc import chains` -- the one `__init__.py`'s own
    `__getattr__` uses -- and `import bitcoin_core_rpc.chains`.
    """
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.startswith("bitcoin_core_rpc."):
                imported.add(node.module.rsplit(".", 1)[-1])
            elif node.module == "bitcoin_core_rpc":
                imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("bitcoin_core_rpc."):
                    imported.add(alias.name.rsplit(".", 1)[-1])
    return imported


def test_no_module_imports_a_later_one() -> None:
    """errors, chains, transport, client: the order a module may look behind.

    `client.py` is free to import `chains.py` and `transport.py`; neither
    of those may import it back, which is what keeps the four acyclic and
    is the property a fifth module joining the package will be held to.
    """
    for index, name in enumerate(_MODULE_ORDER):
        path = _source_paths()[index]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        later = _bitcoin_core_rpc_imports(tree) & set(_MODULE_ORDER[index + 1 :])
        assert not later, f"{name}.py imports {later}, later in the order"


def test_every_spelling_of_a_sibling_import_is_read() -> None:
    """The two spellings no source file of this package currently uses.

    `from bitcoin_core_rpc.chains import X` is exercised by the test
    above, against the real tree; these two are not, so they are
    exercised here, against a tree built for the purpose.
    """
    from_package = ast.parse("from bitcoin_core_rpc import chains\n")
    assert _bitcoin_core_rpc_imports(from_package) == {"chains"}
    plain_import = ast.parse("import bitcoin_core_rpc.chains\n")
    assert _bitcoin_core_rpc_imports(plain_import) == {"chains"}


def test_the_facade_answers_every_on_demand_name_and_refuses_the_rest() -> None:
    """`__getattr__` answers a name from `transport.py` or `client.py`.

    And refuses one neither module defines, `AttributeError` being what
    `from bitcoin_core_rpc import <typo>` needs to fail with rather than
    a bare exception out of `__getattr__`'s own body.
    """
    for name in bitcoin_core_rpc.__all__:
        assert hasattr(bitcoin_core_rpc, name)
    with pytest.raises(AttributeError, match="no attribute 'not_a_public_name'"):
        _ = bitcoin_core_rpc.not_a_public_name


def test_dir_answers_every_published_name() -> None:
    """`dir()` is what interactive completion reads, `__all__` included.

    `__getattr__` above answers a name `dir()` would otherwise miss, since
    nothing has bound it in the module's own namespace until it is asked
    for at least once -- `__dir__` is what keeps completion from hiding a
    name for that reason alone.
    """
    named = dir(bitcoin_core_rpc)
    for name in bitcoin_core_rpc.__all__:
        assert name in named


def test_importing_chains_or_errors_adds_no_socket_layer() -> None:
    """`chains.py` and `errors.py` reach for no networking module of their own.

    `transport.py` is where `urllib.request` comes from, `ssl` and
    `socket` under it, and `__init__.py`'s facade answers `chains.py`'s
    and `client.py`'s names alike through one `__getattr__` -- so what
    proves a caller reaching for `magic_from_chain` or `cookie_auth` pays
    for none of that is a fresh interpreter, `sys.modules` being the read
    nothing already imported in this process can spoof.

    The measurement is relative to a baseline taken in that same
    subprocess, after `hashlib` -- `chains.py`'s own dependency, for
    `sha256` -- and before either module import, rather than an absolute
    read of `sys.modules` afterwards. `hashlib` is where `socket` actually
    enters on PyPy: its cffi hash backend loads an OpenSSL binding that
    pulls `_socket` in as an implementation detail of hashing, on an
    interpreter never asked to open a connection. An absolute read, or one
    baselined before `hashlib`, attributes that to the package; what the
    guarantee is actually about is a networking module the package's own
    code reaches for, which is what the import adds over that baseline.
    The pull request gate checks one interpreter; a sweep or a release run
    is what reaches PyPy.
    """
    watched = ("urllib.request", "ssl", "socket")
    for module in ("bitcoin_core_rpc.chains", "bitcoin_core_rpc.errors"):
        probe = (
            "import sys\n"
            "import hashlib\n"
            "baseline = sorted(sys.modules)\n"
            f"import {module}\n"
            "print(baseline)\n"
            "print(sorted(sys.modules))\n"
        )
        output = subprocess.run(  # ruff: ignore[S603]
            [sys.executable, "-c", probe],
            check=True,
            capture_output=True,
            encoding="utf-8",
        ).stdout
        baseline_line, after_line = output.splitlines()
        added = set(ast.literal_eval(after_line)) - set(ast.literal_eval(baseline_line))
        newly_watched = added & set(watched)
        assert not newly_watched, (module, newly_watched)


_NETWORK_ROOTS = ("socket", "ssl", "urllib")


def _imported_roots(tree: ast.Module) -> set[str]:
    """Return the root of every module a tree imports, by name.

    Root rather than full dotted path -- `urllib.request` and a bare
    `urllib` reach the same layer -- which is what lets the check below
    compare against a fixed, short list rather than every spelling of
    every submodule underneath it.
    """
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    return roots


def test_chains_or_errors_imports_no_network_module_directly() -> None:
    """A static backstop the baseline above cannot be, on every interpreter.

    That test's baseline is taken after `hashlib`, which already holds
    `socket` on PyPy -- so a future `chains.py` or `errors.py` importing
    `socket` (or `ssl`, or `urllib`) *directly* would still pass it
    there, `socket` no longer being something the import adds. This
    reads the source instead of a subprocess's `sys.modules`: the two
    modules either name one of the three or they do not, which is true
    the same way on every interpreter and needs none run.
    """
    by_name = dict(zip(_MODULE_ORDER, _source_paths(), strict=True))
    for name in ("chains", "errors"):
        path = by_name[name]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found = _imported_roots(tree) & set(_NETWORK_ROOTS)
        assert not found, (name, found)


def test_the_network_import_check_is_not_vacuous() -> None:
    """The scan above reports nothing on this tree, so it is read here.

    Same reason as the docstring and census scans further up: a check
    that never trips is indistinguishable from one that cannot. A
    scratch copy of `errors.py`'s own source with `import socket`
    spliced in is what a regression of the shape the test above guards
    against looks like, and it is what that scan is asked to catch.
    """
    source = _source_paths()[0].read_text(encoding="utf-8") + "\nimport socket\n"
    assert _imported_roots(ast.parse(source)) & set(_NETWORK_ROOTS) == {"socket"}


def _declared_all(source: str) -> list[str] | None:
    """Return the module's own `__all__`, in the order it is written.

    None where the module declares none. `__init__.py`'s is read off
    `bitcoin_core_rpc.__all__` directly instead, so this is only ever
    asked of the four modules beneath the facade.
    """
    for statement in ast.parse(source).body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in statement.targets
        ):
            continue
        value = ast.literal_eval(statement.value)
        assert isinstance(value, list)
        return [str(item) for item in value]
    return None


def test_declared_all_reads_none_off_a_module_that_declares_none() -> None:
    """The scan above reports nothing on this tree, so it is read here.

    Same reason as the docstring and census scans further up: `None` is
    what a module with no `__all__` answers, and no module of this
    package is one, so a source built for the purpose is what exercises
    that return rather than a real module the next refactor might touch.
    """
    assert _declared_all("CONSTANT = 1\n") is None


def test_every_module_declares_its_own_public_surface() -> None:
    """Section 7 asks each module for its own surface, not only the facade.

    `chains.py`, `client.py`, `errors.py` and `transport.py` are public
    modules of a published package -- `btclib-org/.github`'s own census,
    `test_every_published_module_declares_its_public_surface`, reads
    them that way -- and each names its own `__all__` here, exactly the
    names it defines: `_public_names` already excludes an import, so a
    name a module merely re-exports from a sibling does not sneak into
    its own declared list the way it would into `dir()`. The order is
    ruff's `RUF022` to keep, not this test's to check -- a constant
    before a class before a function, each group alphabetical -- so the
    comparison is of sets, and of the count against the set to catch a
    name declared twice.
    """
    for path in _source_paths():
        source = path.read_text(encoding="utf-8")
        declared = _declared_all(source)
        assert declared is not None, f"{path.name} declares no __all__"
        assert len(declared) == len(set(declared)), (path.name, declared)
        assert set(declared) == _public_names(source), (path.name, declared)


def test_the_facades_surface_is_the_union_of_the_modules_own() -> None:
    """`__init__.py`'s `__all__` is the four modules' own, put together.

    `test_every_public_name_is_exported` already answers section 7 for
    the facade, against every name the four modules define, and the test
    above answers it once more per module; this is what ties the two
    answers to each other rather than leaving them merely both true by
    coincidence.
    """
    union: set[str] = set()
    for path in _source_paths():
        declared = _declared_all(path.read_text(encoding="utf-8"))
        assert declared is not None
        union |= set(declared)
    assert union == set(bitcoin_core_rpc.__all__)
