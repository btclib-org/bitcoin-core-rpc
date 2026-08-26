# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The one property the rest of the suite cannot state: one file, no imports.

Everything else here runs with the package installed, which is exactly the
arrangement that cannot tell a standalone source from one whose
dependencies happen to be present. These two tests read the file's imports
and then run a copy of it where nothing else is importable at all.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

import bitcoin_core_rpc


def _source_path() -> Path:
    path = bitcoin_core_rpc.__file__
    assert path is not None
    return Path(path)


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

    Every module-level definition of the client carries a docstring and
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
    documented = _documented_names(_source_path().read_text(encoding="utf-8"))
    undocumented = sorted(set(bitcoin_core_rpc.__all__) - documented)
    # named, because pytest elides the difference of two sets this size and
    # what the next reader needs is which name arrived without one
    assert not undocumented, f"public names with no docstring: {undocumented}"


def _public_names(source: str) -> set[str]:
    """Return the module-level names a bare `import *` would offer.

    Definitions and assignments, less whatever a leading underscore keeps
    out. Imports are not read: a name this file imported is not part of
    what it publishes, so counting them would report the standard library
    as an unexported surface. Reading the source rather than the imported
    module is what lets a constant and a type alias be seen at all --
    neither carries a `__module__` to be filtered on.
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
    sentence true rather than aspirational: a name added to the module
    without being exported fails here, which is the census section 7 of
    the organization standard asks a publishing package for. `py.typed`
    ships, so which names are supported is half of what the distribution
    promises.
    """
    source = _source_path().read_text(encoding="utf-8")
    exported = set(bitcoin_core_rpc.__all__)
    # named rather than counted: what the next reader needs is which name
    # arrived without an export, and a set difference pytest elides
    unexported = sorted(_public_names(source) - exported)
    assert not unexported, f"public names missing from __all__: {unexported}"
    # the other direction, which fails at import time for a caller writing
    # `from bitcoin_core_rpc import *` and nowhere else in this suite
    missing = sorted(exported - _public_names(source))
    assert not missing, f"__all__ names nothing defines: {missing}"


def test_the_client_source_imports_only_the_standard_library() -> None:
    """A copied file has no package or third-party import left behind."""
    tree = ast.parse(_source_path().read_text(encoding="utf-8"))
    # a relative import is the one this would otherwise not see: were the
    # file to sit inside a package, `from . import helper` is how a
    # dependency would come back, and `node.module` is None for the `from
    # . import x` spelling -- an empty set of roots, and an assertion that
    # passes. The level is what says an import is relative at all
    relative = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level
    ]
    assert not relative
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
    assert imported_roots <= {*sys.stdlib_module_names, "__future__"}


def test_the_single_copied_file_imports_and_calls_on_its_own(
    tmp_path: Path,
) -> None:
    """Exercise results and structured errors with site packages disabled."""
    vendored = tmp_path / "bitcoin_core_rpc.py"
    shutil.copy2(_source_path(), vendored)
    smoke = """
import copy
import importlib.util
import json
import pickle
import sys
from decimal import Decimal

for module_name in ("a_vendored_bitcoin_core_rpc", "z_vendored_bitcoin_core_rpc"):
    spec = importlib.util.spec_from_file_location(module_name, sys.argv[1])
    assert spec is not None and spec.loader is not None
    rpc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rpc)
    assert rpc.FetchError.__module__ == module_name
    # a copy's exceptions cross a process boundary the way the package's
    # do, and pickle looks a class up by the module it names: registering
    # what importlib loaded is what makes that name resolve, here and in
    # any application loading the copy the same way
    sys.modules[module_name] = rpc
    error = rpc.RpcError("getrawtransaction: not found", -5, {"tx": 1})
    said = "getrawtransaction: not found (rpc error code -5)"
    assert str(error) == said
    for back in (pickle.loads(pickle.dumps(error)), copy.deepcopy(error)):
        assert type(back) is rpc.RpcError
        assert str(back) == said
        assert back.code == -5 and back.data == {"tx": 1}

# what -I -S bought, asserted rather than assumed: no site packages, no
# PYTHONPATH and no script directory on sys.path, so the installed package
# is not here to have been reached. Without these two, an isolation that
# stopped working would leave a test that passes and proves nothing
assert "bitcoin_core_rpc" not in sys.modules
try:
    import bitcoin_core_rpc
except ImportError:
    pass
else:
    raise AssertionError("the package is importable here, so this proves nothing")

calls = []
def transport(request, timeout):
    calls.append((request, timeout))
    request_id = json.loads(request.data)["id"]
    body = json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "result": 1.25}
    ).encode()
    return 200, body

client = rpc.BitcoinCoreRpcClient(
    "http://127.0.0.1:8332",
    user="rpcuser",
    password="rpcpassword",  # pragma: allowlist secret
    transport=transport,
)
assert client.call("getbalance") == Decimal("1.25")
assert len(calls) == 1

def rpc_error(request, timeout):
    request_id = json.loads(request.data)["id"]
    body = json.dumps(
        {"jsonrpc": "2.0", "id": request_id,
         "error": {"code": -5, "message": "not found", "data": {"tx": 1}}}
    ).encode()
    return 200, body

client.transport = rpc_error
try:
    client.call("getrawtransaction")
except rpc.RpcError as error:
    assert error.code == -5 and error.data == {"tx": 1}
else:
    raise AssertionError("RpcError not raised")

client.transport = lambda request, timeout: (503, b"not json")
try:
    client.call("getblockcount")
except rpc.HttpError as error:
    assert error.status == 503
else:
    raise AssertionError("HttpError not raised")
"""
    subprocess.run(  # ruff: ignore[S603]
        [sys.executable, "-I", "-S", "-c", smoke, str(vendored)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
