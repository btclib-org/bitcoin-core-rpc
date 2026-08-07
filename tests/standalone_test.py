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


def test_every_public_name_carries_a_docstring() -> None:
    """`docs/source/api.rst` says the page lists the whole public surface.

    `automodule` with `:members:` documents a class or a function by its
    docstring and a module-level assignment by the string literal that
    follows it -- a `#` comment is neither, so a constant carrying one is
    absent from the built page rather than undescribed on it. Nine of the
    names in `__all__` were, the type aliases and every constant among
    them, which is the promise above being false about the interface a
    consumer reads at readthedocs.
    """
    body = ast.parse(_source_path().read_text(encoding="utf-8")).body
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
    undocumented = sorted(set(bitcoin_core_rpc.__all__) - documented)
    # named, because pytest elides the difference of two sets this size and
    # what the next reader needs is which name arrived without one
    assert not undocumented, f"public names with no docstring: {undocumented}"


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
        text=True,
    )
