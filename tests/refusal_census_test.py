# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""No refusal of the package holds a value it did not trace.

Section 7 of the organization's standard, *A refusal carries no secret*,
says an argument in the wrong place may be a key, and a key passed in the
wrong place can come back in what a node answers. The census reads the
sources and finds every exception the package builds: each call of a name
ending in `Error` or `Exception`, and the exception of each `raise` that is
not what a function of the package returns. Every argument of each has to
be traced to values a refusal may hold, and the census fails closed: what
it cannot trace is a finding. It traces

- a literal, a comparison, a name bound by an import, a `def` or a
  `class`, and an attribute named in capitals;
- what `_quoted`, `_kept_name`, `_endpoint`, `_split_url`, `len`, `type`
  and `bool` answer, what the methods `bit_length`, `count`, `find`, `index`,
  `start` and `end` answer, and a `__name__` or a `__qualname__`;
- the index `enumerate` counts from a start it traces, and the one a
  `range` counts from zero or from a start it traces;
- a call, an attribute or an item of what it traces; each element a loop
  or a comprehension takes from it, or `zip` pairs; and in a loop over
  rows written out, the column the name takes;
- a local or module name, where it traces every value the name is bound
  to, what a `with` binds traced as the call it makes, and every value
  put into it anywhere in the scope, by a method such as `append` or by
  an assignment to an item or an attribute;
- an attribute of a method's `self`, where it traces every value a method
  of that class assigns to it;
- the exception an `except` binds, where every class it catches is one
  the package defines: its own refusal, whose arguments the census reads
  where it is built;
- a parameter of a private function, where it traces what every call in
  the package passes there;
- what a function of the package answers, where it traces every value
  the function returns or yields, or the item at the position a tuple is
  unpacked from.

A name called is the `def` of the scope that binds it, or the one of the
module of the package it is imported from; an attribute called is every
method of that name in the package. So the census does not trace a
parameter of a public function or of a lambda, a method's `self` itself,
a function read as a value rather than called, any other exception an
`except` binds, or the environment and the arguments of the process.
Each holds what a caller, a node or another program handed over.

What a refusal still shows of those is in two tables, each entry with its
reason: `CALLER_VALUES`, a parameter whose value the caller passed, and
`KEPT`, an argument of the refusals of one function that the census does
not trace, nor any name that function binds to it. Of what a node sends,
they hold the rpc error code and the HTTP status alone. An entry no
refusal uses fails the census too.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest

import bitcoin_core_rpc

_LIBRARY = Path(bitcoin_core_rpc.__file__).parent

# a call whose answer describes what it is handed and holds no byte of it,
# or holds a name short enough to quote, or the scheme, the host and the port
# of a url
_DESCRIBING = frozenset(
    {"_quoted", "_kept_name", "_endpoint", "_split_url", "len", "type", "bool"}
)
_DESCRIBING_METHODS = frozenset(
    {"bit_length", "count", "find", "index", "start", "end"}
)
_DESCRIBING_ATTRIBUTES = frozenset({"__name__", "__qualname__"})
# what a module holds that the process was handed
_PROCESS_INPUT = frozenset({"environ", "argv", "stdin"})
# the methods that put values into a list, a set, a dict or a deque
_MUTATORS = frozenset(
    {
        "add",
        "append",
        "appendleft",
        "extend",
        "extendleft",
        "insert",
        "setdefault",
        "update",
    }
)
_CONSTANT = re.compile(r"_*[A-Z][A-Z0-9_]*")
_FUNCTION = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_COMPREHENSION = (ast.ListComp, ast.SetComp, ast.GeneratorExp)
_BINDING = (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)
_LOOP = (ast.For, ast.AsyncFor, ast.comprehension)
_DECLARED = (ast.Import, ast.ImportFrom, *_FUNCTION, ast.ClassDef)


def _private(name: str) -> bool:
    return name.startswith("_") and not name.endswith("__")


def _called_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _arguments(func: ast.AST) -> list[ast.arg]:
    args: ast.arguments = func.args  # type: ignore[attr-defined]
    found = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    found.extend(arg for arg in (args.vararg, args.kwarg) if arg is not None)
    return found


def _own_nodes(scope: ast.AST) -> list[ast.AST]:
    """Return the nodes of a scope, not entering a nested function or class."""
    found: list[ast.AST] = []
    todo = list(ast.iter_child_nodes(scope))
    while todo:
        node = todo.pop()
        found.append(node)
        if isinstance(node, (*_FUNCTION, ast.ClassDef)):
            # its decorators are read in this scope, its body is not
            todo.extend(getattr(node, "decorator_list", []))
            continue
        todo.extend(ast.iter_child_nodes(node))
    return found


def _names(target: ast.AST) -> list[str]:
    return [node.id for node in ast.walk(target) if isinstance(node, ast.Name)]


def _mutates(node: ast.AST, name: str) -> bool:
    """Return whether a node is a call putting values into a named container."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _MUTATORS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == name
    )


def _mutated(node: ast.AST) -> list[str]:
    """Return the names a node puts values into, by a call or an assignment.

    `x.append(v)` puts `v` into `x`, and so do `x[k] = v` and `x.k = v`.
    """
    if isinstance(node, ast.Call):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in _MUTATORS
            and isinstance(func.value, ast.Name)
        ):
            return [func.value.id]
        return []
    if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return []
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    found: list[str] = []
    for target in targets:
        for part in ast.walk(target):
            if isinstance(part, (ast.Subscript, ast.Attribute)):
                root = part.value
                while isinstance(root, (ast.Subscript, ast.Attribute)):
                    root = root.value
                if isinstance(root, ast.Name):
                    found.append(root.id)
    return found


def _binds(node: ast.AST, name: str) -> bool:  # noqa: PLR0911
    """Return whether a node binds a name in the scope it belongs to."""
    if _mutates(node, name):
        return True
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return any(name in _names(target) for target in targets)
    if isinstance(node, (*_LOOP, ast.NamedExpr)):
        return name in _names(node.target)
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return any(
            item.optional_vars is not None and name in _names(item.optional_vars)
            for item in node.items
        )
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return any((a.asname or a.name).split(".")[0] == name for a in node.names)
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return name in node.names
    if isinstance(
        node,
        (ast.ExceptHandler, ast.MatchAs, ast.MatchStar, *_FUNCTION, ast.ClassDef),
    ):
        return getattr(node, "name", None) == name
    return False


@dataclass
class _Module:
    name: str
    tree: ast.Module
    parents: dict[ast.AST, ast.AST] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parents[child] = node

    def scopes(self, node: ast.AST) -> list[ast.AST]:
        """Return the enclosing functions, innermost first, then the module."""
        found: list[ast.AST] = []
        current = self.parents.get(node)
        while current is not None:
            if isinstance(current, _FUNCTION):
                found.append(current)
            current = self.parents.get(current)
        found.append(self.tree)
        return found

    def where(self, node: ast.AST) -> str:
        return f"{self.name}:{getattr(node, 'lineno', 0)}"


# what a value is traced through: a name in the scope that binds it, a
# parameter of a function, what a private function returns, or an attribute
_Key = tuple[str, int, str]


def _function_name(module: _Module, node: ast.AST) -> str:
    """Return the name of the `def` a node is in, or `<module>`."""
    for scope in module.scopes(node):
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return scope.name
    return "<module>"


def _origin(leaf: str) -> str:
    """Return an untraced value with no line number, as the tables name it."""
    return re.sub(r"(\.py):[0-9]+", r"\1", leaf)


@dataclass
class _Census:
    modules: list[_Module]
    # the calls of each function of the package, and where it is read as a
    # value, keyed by the id of its `def`
    calls: dict[int, list[tuple[_Module, ast.Call]]] = field(default_factory=dict)
    reads: dict[int, list[tuple[_Module, ast.AST]]] = field(default_factory=dict)
    functions: dict[int, tuple[_Module, ast.AST]] = field(default_factory=dict)
    methods: dict[str, list[ast.AST]] = field(default_factory=dict)
    scopes: dict[int, tuple[_Module, ast.AST]] = field(default_factory=dict)
    nodes: dict[int, list[ast.AST]] = field(default_factory=dict)
    mutations: dict[int, dict[str, list[ast.AST]]] = field(default_factory=dict)
    edges: dict[_Key, tuple[list[str], set[_Key]]] = field(default_factory=dict)
    reached: dict[_Key, frozenset[str]] = field(default_factory=dict)
    classes: set[str] = field(default_factory=set)
    used: set[object] = field(default_factory=set)
    kept_scopes: dict[int, frozenset[str]] = field(default_factory=dict)
    kept_now: frozenset[str] = frozenset()

    def __post_init__(self) -> None:  # noqa: C901
        for module in self.modules:
            for node in ast.walk(module.tree):
                if isinstance(node, ast.ClassDef):
                    self.classes.add(node.name)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.functions[id(node)] = (module, node)
                    if isinstance(module.parents.get(node), ast.ClassDef):
                        self.methods.setdefault(node.name, []).append(node)
        for module in self.modules:
            for node in ast.walk(module.tree):
                if isinstance(node, ast.Call):
                    for func in self._resolve(node.func, module) or []:
                        self.calls.setdefault(id(func), []).append((module, node))
                elif isinstance(node, (ast.Name, ast.Attribute)) and isinstance(
                    node.ctx, ast.Load
                ):
                    parent = module.parents.get(node)
                    if not (isinstance(parent, ast.Call) and parent.func is node):
                        for func in self._resolve(node, module) or []:
                            self.reads.setdefault(id(func), []).append((module, node))

    def _resolve(self, func: ast.expr, module: _Module) -> list[ast.AST] | None:
        """Return the `def`s of the package a callee may be, None where unknown.

        A name is the `def` of the scope that binds it, or the one of the
        module it is imported from. An attribute is every method of that
        name.
        """
        if isinstance(func, ast.Attribute):
            return self.methods.get(func.attr)
        if not isinstance(func, ast.Name):
            return None
        for scope in module.scopes(func):
            bindings = [n for n in self._scope_nodes(scope) if _binds(n, func.id)]
            if isinstance(scope, _FUNCTION) and any(
                arg.arg == func.id for arg in _arguments(scope)
            ):
                return None
            if not bindings:
                continue
            found: list[ast.AST] = []
            for binding in bindings:
                if isinstance(binding, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found.append(binding)
                elif isinstance(binding, ast.ImportFrom):
                    found.extend(self._imported(binding, func.id))
                else:
                    return None
            return found or None
        return None

    def _imported(self, node: ast.ImportFrom, name: str) -> list[ast.AST]:
        """Return the `def`s an import of the package binds to a name."""
        source = next(a.name for a in node.names if (a.asname or a.name) == name)
        path = f"{(node.module or '').replace('.', '/')}.py"
        package = path.removesuffix(".py") + "/__init__.py"
        return [
            func
            for module in self.modules
            if module.name in {path, package}
            for func in module.tree.body
            if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef))
            and func.name == source
        ]

    def sites(self) -> list[tuple[_Module, ast.Call]]:
        """Return each exception the package builds, as the call that builds it.

        A `raise` of what a function of the package returns is not one: the
        exception that function builds is.
        """
        found: dict[int, tuple[_Module, ast.Call]] = {}
        for module in self.modules:
            for node in ast.walk(module.tree):
                if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                    if self._resolve(node.exc.func, module) is None:
                        found[id(node.exc)] = (module, node.exc)
                elif isinstance(node, ast.Call):
                    name = _called_name(node.func) or ""
                    if name.endswith(("Error", "Exception")):
                        found[id(node)] = (module, node)
        return sorted(found.values(), key=lambda site: (site[0].name, site[1].lineno))

    def findings(
        self,
        callers: Mapping[str, str] | None = None,
        kept: Mapping[tuple[str, str, str], str] | None = None,
    ) -> list[str]:
        """Return each exception built from a value the census cannot trace.

        `callers` and `kept` are what `CALLER_VALUES` and `KEPT` hold. The
        entries a refusal used are left in `used`.
        """
        callers, kept = callers or {}, kept or {}
        for module in self.modules:
            for node in ast.walk(module.tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    exprs = {
                        e for m, f, e in kept if (m, f) == (module.name, node.name)
                    }
                    if exprs:
                        self.kept_scopes[id(node)] = frozenset(exprs)
        found: list[str] = []
        for module, call in self.sites():
            function = _function_name(module, call)
            shown = frozenset(
                e for m, f, e in kept if (m, f) == (module.name, function)
            )
            values = [*call.args, *(keyword.value for keyword in call.keywords)]
            leaves = self.untraced(values, module, shown)
            untraced = []
            for leaf in sorted(leaves):
                origin = _origin(leaf)
                if origin in callers:
                    self.used.add(origin)
                else:
                    untraced.append(leaf)
            if untraced:
                found.append(f"{module.where(call)}: " + "; ".join(untraced))
        return found

    def untraced(
        self, exprs: list[ast.expr], module: _Module, kept: frozenset[str] = frozenset()
    ) -> set[str]:
        """Return each value the expressions hold that cannot be traced."""
        leaves: list[str] = []
        keys: set[_Key] = set()
        for expr in exprs:
            self._visit(expr, module, leaves, keys, kept)
        found = set(leaves)
        for key in keys:
            found |= self._reach(key)
        return found

    def _visit(  # noqa: C901, PLR0911, PLR0912
        self,
        expr: ast.AST | None,
        module: _Module,
        leaves: list[str],
        keys: set[_Key],
        kept: frozenset[str] = frozenset(),
    ) -> None:
        """Sort what an expression holds into untraced values and keys.

        `kept` holds the source of each expression of a refusal that `KEPT`
        lets it show, which is not traced.
        """
        if expr is None or isinstance(expr, (ast.Constant, ast.Compare)):
            # nothing, a literal, or a bool whatever it compares
            return
        kept = kept or self.kept_now
        if kept and (text := ast.unparse(expr)) in kept:
            self.used.add((module.name, _function_name(module, expr), text))
            return
        if isinstance(expr, ast.Name):
            key = self._name_key(expr, module)
            if key is not None:
                keys.add(key)
            return
        if isinstance(expr, ast.Call):
            func = expr.func
            name = _called_name(func) or ""
            if isinstance(func, ast.Name) and name in _DESCRIBING:
                return
            if isinstance(func, ast.Attribute) and name in _DESCRIBING_METHODS:
                return
            functions = self._resolve(func, module)
            if functions is not None:
                # what a function of the package answers: each value it
                # returns or yields, whichever `def` the call reaches
                keys.update(("returns", id(function), "") for function in functions)
                return
            for child in [func, *expr.args, *(k.value for k in expr.keywords)]:
                self._visit(child, module, leaves, keys)
            return
        if isinstance(expr, ast.Attribute):
            if expr.attr in _DESCRIBING_ATTRIBUTES or _CONSTANT.fullmatch(expr.attr):
                return
            if expr.attr in _PROCESS_INPUT:
                leaves.append(f"{module.where(expr)} {ast.unparse(expr)}")
                return
            if self._is_self(expr.value, module):
                # an attribute of `self`: every value the package assigns to
                # an attribute of that name, whatever object it is on
                keys.add(("attribute", 0, expr.attr))
                return
            self._visit(expr.value, module, leaves, keys)
            return
        if isinstance(expr, (ast.Subscript, ast.NamedExpr, ast.Starred)):
            # an item of what is traced, whichever item
            self._visit(expr.value, module, leaves, keys)
            return
        if isinstance(expr, ast.DictComp):
            self._visit(expr.key, module, leaves, keys)
            self._visit(expr.value, module, leaves, keys)
            return
        if isinstance(expr, _COMPREHENSION):
            # its targets are bound in the enclosing scope, as a loop's are
            self._visit(expr.elt, module, leaves, keys)
            return
        if isinstance(expr, ast.IfExp):
            # the test only chooses
            self._visit(expr.body, module, leaves, keys, kept)
            self._visit(expr.orelse, module, leaves, keys, kept)
            return
        if isinstance(
            expr,
            (
                ast.JoinedStr,
                ast.FormattedValue,
                ast.BinOp,
                ast.UnaryOp,
                ast.BoolOp,
                ast.Tuple,
                ast.List,
                ast.Set,
                ast.Dict,
                ast.Slice,
            ),
        ):
            for node in ast.iter_child_nodes(expr):
                if isinstance(node, ast.expr):
                    self._visit(node, module, leaves, keys, kept)
            return
        leaves.append(f"{module.where(expr)} {ast.unparse(expr)}")

    def _is_self(self, expr: ast.expr, module: _Module) -> bool:
        """Return whether an expression is the first parameter of a method."""
        if not isinstance(expr, ast.Name):
            return False
        for scope in module.scopes(expr):
            if isinstance(scope, _FUNCTION) and any(
                arg.arg == expr.id for arg in _arguments(scope)
            ):
                positional = [*scope.args.posonlyargs, *scope.args.args]
                return (
                    isinstance(module.parents.get(scope), ast.ClassDef)
                    and bool(positional)
                    and positional[0].arg == expr.id
                    and not any(
                        _called_name(d) == "staticmethod"
                        for d in getattr(scope, "decorator_list", [])
                    )
                )
        return False

    def _attribute(self, attr: str, leaves: list[str], keys: set[_Key]) -> None:
        """Sort every value the package assigns to an attribute of this name.

        An attribute that is a method or a property of a class of the
        package is what that `def` returns. One the package neither assigns
        nor defines comes from outside it, and is untraced.
        """
        found = False
        for module in self.modules:
            for node in ast.walk(module.tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    node.name == attr
                    and isinstance(module.parents.get(node), ast.ClassDef)
                ):
                    found = True
                    keys.add(("returns", id(node), ""))
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = (
                        node.targets if isinstance(node, ast.Assign) else [node.target]
                    )
                    for target in targets:
                        found |= self._assigned(
                            target, node.value, attr, module, leaves, keys
                        )
                elif (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in _MUTATORS
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == attr
                ):
                    found = True
                    for value in [*node.args, *(k.value for k in node.keywords)]:
                        self._visit(value, module, leaves, keys)
        if not found:
            leaves.append(f"attribute {attr}, which the package does not assign")

    def _assigned(  # noqa: PLR0917
        self,
        target: ast.AST,
        value: ast.expr | None,
        attr: str,
        module: _Module,
        leaves: list[str],
        keys: set[_Key],
    ) -> bool:
        """Sort what a target assigns to an attribute; say whether it does."""
        if (
            isinstance(target, ast.Tuple)
            and isinstance(value, ast.Tuple)
            and len(target.elts) == len(value.elts)
        ):
            found = False
            for part, item in zip(target.elts, value.elts, strict=True):
                found |= self._assigned(part, item, attr, module, leaves, keys)
            return found
        hit = False
        for node in ast.walk(target):
            # `x.attr = v`, and `x.attr[k] = v` puts `v` into it
            root = node.value if isinstance(node, ast.Subscript) else node
            if isinstance(root, ast.Attribute) and root.attr == attr:
                hit = True
        if hit:
            self._visit(value, module, leaves, keys)
        return hit

    def _mutations(self, scope: ast.AST) -> dict[str, list[ast.AST]]:
        """Return, by name, the nodes in a scope that put values into it."""
        if id(scope) not in self.mutations:
            found: dict[str, list[ast.AST]] = {}
            for node in ast.walk(scope):
                for name in _mutated(node):
                    found.setdefault(name, []).append(node)
            self.mutations[id(scope)] = found
        return self.mutations[id(scope)]

    def _scope_nodes(self, scope: ast.AST) -> list[ast.AST]:
        if id(scope) not in self.nodes:
            self.nodes[id(scope)] = _own_nodes(scope)
        return self.nodes[id(scope)]

    def _name_key(self, node: ast.Name, module: _Module) -> _Key | None:
        """Return the key of the innermost scope binding a name, or None."""
        for scope in module.scopes(node):
            params = isinstance(scope, _FUNCTION) and any(
                arg.arg == node.id for arg in _arguments(scope)
            )
            if params or any(_binds(n, node.id) for n in self._scope_nodes(scope)):
                self.scopes[id(scope)] = (module, scope)
                return ("name", id(scope), node.id)
        return None

    def _reach(self, start: _Key) -> frozenset[str]:  # noqa: C901, PLR0912
        """Return each untraced value a key reaches, through every key it reads.

        Tarjan's strongly connected components, iterative: a key on a cycle
        reaches what every key of the cycle reaches.
        """
        if start in self.reached:
            return self.reached[start]
        index: dict[_Key, int] = {}
        low: dict[_Key, int] = {}
        stack: list[_Key] = []
        on_stack: set[_Key] = set()
        work: list[tuple[_Key, list[_Key]]] = []

        def enter(key: _Key) -> None:
            index[key] = low[key] = len(index)
            stack.append(key)
            on_stack.add(key)
            work.append((key, sorted(self._edges(key)[1])))

        enter(start)
        while work:
            key, todo = work[-1]
            if todo:
                child = todo.pop()
                if child in self.reached:
                    continue
                if child not in index:
                    enter(child)
                else:
                    # a key whose component is complete is in `reached`, so
                    # one indexed and not there is on the stack
                    low[key] = min(low[key], index[child])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[key])
            if low[key] == index[key]:
                component: list[_Key] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == key:
                        break
                found: set[str] = set()
                for member in component:
                    leaves, children = self._edges(member)
                    found.update(leaves)
                    for child in children:
                        if child not in component:
                            found |= self.reached[child]
                for member in component:
                    self.reached[member] = frozenset(found)
        return self.reached[start]

    def _edges(self, key: _Key) -> tuple[list[str], set[_Key]]:  # noqa: C901, PLR0912
        """Return the untraced values a key holds and the keys it reads."""
        if key not in self.edges:
            leaves: list[str] = []
            keys: set[_Key] = set()
            kind, scope_id, name = key
            if kind == "attribute":
                self._attribute(name, leaves, keys)
            elif kind == "returns":
                module, func = self.functions[scope_id]
                for node in self._scope_nodes(func):
                    if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
                        self._visit(node.value, module, leaves, keys)
            elif kind == "item":
                module, func = self.functions[scope_id]
                position, size = map(int, name.split("/"))
                for node in self._scope_nodes(func):
                    if isinstance(node, ast.Return):
                        value = node.value
                        if isinstance(value, ast.Tuple) and len(value.elts) == size:
                            value = value.elts[position]
                        elif isinstance(value, ast.Call) and (
                            callees := self._resolve(value.func, module)
                        ):
                            # that item of what the function it calls returns
                            keys.update(("item", id(c), name) for c in callees)
                            continue
                        self._visit(value, module, leaves, keys)
                    elif isinstance(node, (ast.Yield, ast.YieldFrom)):
                        self._visit(node.value, module, leaves, keys)
            elif kind == "parameter":
                module, func = self.scopes[scope_id]
                self._parameter(func, name, module, leaves, keys)
            else:
                module, scope = self.scopes[scope_id]
                if isinstance(scope, _FUNCTION) and any(
                    arg.arg == name for arg in _arguments(scope)
                ):
                    keys.add(("parameter", scope_id, name))
                bindings = [n for n in self._scope_nodes(scope) if _binds(n, name)]
                # and what any function the scope holds puts into it
                bindings.extend(
                    node
                    for node in self._mutations(scope).get(name, [])
                    if node not in bindings
                )
                # what `KEPT` lets the function's refusals show is not traced
                # where the function binds a name to it either
                self.kept_now = self.kept_scopes.get(scope_id, frozenset())
                for node in bindings:
                    self._binding(node, name, module, leaves, keys)
                self.kept_now = frozenset()
            self.edges[key] = (leaves, keys)
        return self.edges[key]

    def _binding(  # noqa: C901
        self,
        node: ast.AST,
        name: str,
        module: _Module,
        leaves: list[str],
        keys: set[_Key],
    ) -> None:
        if _mutates(node, name):
            call = cast("ast.Call", node)
            for value in [*call.args, *(k.value for k in call.keywords)]:
                self._visit(value, module, leaves, keys)
        elif isinstance(node, _BINDING):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if name in _names(target):
                    self._element(target, node.value, name, module, leaves, keys)
        elif isinstance(node, _LOOP):
            self._element(node.target, node.iter, name, module, leaves, keys, loop=True)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            # what the context manager answers, traced as what makes it
            for item in node.items:
                if item.optional_vars is not None and name in _names(
                    item.optional_vars
                ):
                    self._visit(item.context_expr, module, leaves, keys)
        elif isinstance(node, ast.ExceptHandler) and self._own_exception(node):
            # the package's own refusal, whose arguments are read where it
            # is built
            return
        elif not isinstance(node, _DECLARED):
            leaves.append(
                f"{module.where(node)} {name}, bound by {type(node).__name__}"
            )

    def _own_exception(self, handler: ast.ExceptHandler) -> bool:
        """Return whether a handler catches only classes the package defines."""
        # a handler that binds a name names what it catches
        caught = cast("ast.expr", handler.type)
        names = caught.elts if isinstance(caught, ast.Tuple) else [caught]
        return all(_called_name(name) in self.classes for name in names)

    def _element(  # noqa: C901, PLR0911, PLR0912, PLR0917
        self,
        target: ast.AST,
        value: ast.expr | None,
        name: str,
        module: _Module,
        leaves: list[str],
        keys: set[_Key],
        *,
        loop: bool = False,
    ) -> None:
        """Sort what the value a target takes the name from holds.

        Where `loop` is set the target takes each element of `value` in turn.
        """
        if loop and isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            counter, args = value.func.id, value.args
            if counter == "range":
                if len(args) > 1:
                    self._visit(args[0], module, leaves, keys)
                return
            if counter == "enumerate" and args and isinstance(target, ast.Tuple):
                index, element = target.elts
                if name in _names(index):
                    # the index, counted from a start that has to be traced
                    for start in [*args[1:], *(k.value for k in value.keywords)]:
                        self._visit(start, module, leaves, keys)
                    return
                self._element(element, args[0], name, module, leaves, keys, loop=True)
                return
            if counter == "zip" and isinstance(target, ast.Tuple):
                for part, iterable in zip(target.elts, args, strict=False):
                    if name in _names(part):
                        self._element(
                            part, iterable, name, module, leaves, keys, loop=True
                        )
                        return
        if (
            loop
            and isinstance(target, ast.Tuple)
            and isinstance(value, (ast.Tuple, ast.List))
            and all(
                isinstance(row, ast.Tuple) and len(row.elts) == len(target.elts)
                for row in value.elts
            )
        ):
            # a loop over rows written out: the name takes its column
            position = next(
                i for i, part in enumerate(target.elts) if name in _names(part)
            )
            for row in value.elts:
                row_items = cast("ast.Tuple", row).elts
                self._element(
                    target.elts[position],
                    row_items[position],
                    name,
                    module,
                    leaves,
                    keys,
                )
            return
        if (
            not loop
            and isinstance(target, ast.Tuple)
            and isinstance(value, ast.Tuple)
            and len(target.elts) == len(value.elts)
        ):
            # the name is in the target, so in one of its parts
            part, item = next(
                (part, item)
                for part, item in zip(target.elts, value.elts, strict=True)
                if name in _names(part)
            )
            self._element(part, item, name, module, leaves, keys)
            return
        if not loop and isinstance(target, ast.Tuple) and isinstance(value, ast.Call):
            if _called_name(value.func) in _DESCRIBING:
                # every item of what a describing call answers
                return
            functions = self._resolve(value.func, module)
            position = next(
                (i for i, part in enumerate(target.elts) if name in _names(part)), 0
            )
            if functions is not None and isinstance(target.elts[position], ast.Name):
                # the item of each tuple a function returns, at that position
                keys.update(
                    ("item", id(function), f"{position}/{len(target.elts)}")
                    for function in functions
                )
                return
        self._visit(value, module, leaves, keys)

    def _parameter(  # noqa: C901
        self,
        func: ast.AST,
        name: str,
        module: _Module,
        leaves: list[str],
        keys: set[_Key],
    ) -> None:
        """Sort what every call of the package passes to a parameter."""
        arg = next(arg for arg in _arguments(func) if arg.arg == name)
        func_name = getattr(func, "name", "a lambda")
        origin = f"{module.where(arg)} parameter {name} of {func_name}"
        func_args: ast.arguments = func.args  # type: ignore[attr-defined]
        positional = [*func_args.posonlyargs, *func_args.args]
        bound = bool(positional) and positional[0].arg in {"self", "cls"}
        if not _private(func_name) or arg in {func_args.vararg, func_args.kwarg}:
            leaves.append(origin)
            return
        if bound and arg is positional[0]:
            # the object a method is called on, which no call passes
            leaves.append(origin)
            return
        if id(func) in self.reads:
            # read as a value, it is called where the census cannot see
            reader, read = self.reads[id(func)][0]
            leaves.append(f"{origin}, read at {reader.where(read)}")
            return
        calls = self.calls.get(id(func), [])
        if not calls:
            leaves.append(f"{origin}, never called")
        for caller, call in calls:
            if any(isinstance(a, ast.Starred) for a in call.args) or any(
                k.arg is None for k in call.keywords
            ):
                leaves.append(f"{origin}, unpacked at {caller.where(call)}")
                continue
            passed = [k.value for k in call.keywords if k.arg == name]
            if arg in positional:
                position = positional.index(arg)
                if bound and isinstance(call.func, ast.Attribute):
                    position -= 1
                if 0 <= position < len(call.args):
                    passed.append(call.args[position])
            for value in passed:
                self._visit(value, caller, leaves, keys)


_PACKAGE = "bitcoin_core_rpc"

#: A parameter whose value the caller passed, which a refusal shows on
#: purpose, keyed as the census names it.
CALLER_VALUES = {
    f"{_PACKAGE}/__init__.py parameter name of __getattr__": (
        "the attribute asked for, as `AttributeError` names it"
    ),
    f"{_PACKAGE}/client.py parameter method of __getattr__": (
        "the rpc method an `RpcChannel` call names"
    ),
    f"{_PACKAGE}/client.py parameter method of call": "the rpc method",
    f"{_PACKAGE}/client.py parameter method of call_stream": "the rpc method",
    f"{_PACKAGE}/client.py parameter method of call_raw": "the rpc method",
    f"{_PACKAGE}/client.py parameter where of __init__": (
        "what a `JsonStream`'s caller names the document"
    ),
    f"{_PACKAGE}/client.py parameter limit of value": (
        "the limit a `JsonStream`'s caller passes, shown once a value read has"
        " gone past it"
    ),
    f"{_PACKAGE}/chains.py parameter cookie_path of cookie_auth": (
        "the cookie file, which an operator has to find"
    ),
    f"{_PACKAGE}/transport.py parameter host of _connect, unpacked at "
    f"{_PACKAGE}/transport.py": "the host of the caller's url",
}

#: An argument of the refusals of one function that the census does not
#: trace, keyed by module, function and source.
KEPT = {
    ("chains.py", "cookie_auth", "e"): (
        "the OSError of opening the caller's cookie file, which names its path"
    ),
    ("client.py", "_rpc_error", "code"): (
        "the rpc error code the node sent, an integer of at most 32 bits"
    ),
    ("client.py", "_http_error", "status"): (
        "the HTTP status: three digits from `http.client`, or what a transport"
        " of the caller's own answers"
    ),
    ("client.py", "_json_scalar", "value"): (
        "a float that is not finite: nan, inf or -inf"
    ),
    ("client.py", "_request", "e"): (
        "the encoder's error for the caller's params, which names a limit"
    ),
    ("client.py", "call_batch", "e"): (
        "the encoder's error for the caller's params, which names a limit"
    ),
    ("client.py", "call_raw", "e"): (
        "the encoder's error for the caller's params, which names a limit"
    ),
    ("transport.py", "_assert_valid_timeout", "shown"): (
        "a refused timeout: a float, or the size in bits of a larger integer"
    ),
    ("transport.py", "_read_bounded", "max_body_size"): (
        "the caller's limit, shown once a body read has gone past it"
    ),
    ("transport.py", "http_request", "max_body_size"): (
        "the caller's limit, shown once a body read has gone past it"
    ),
    ("transport.py", "http_request", "e"): (
        "an OSError: the system's text about the connection. An HTTPException,"
        " which can hold what the node sent, is named by its type"
    ),
    ("transport.py", "_post_stream", "e"): "an OSError, as for http_request",
    ("transport.py", "read", "e"): "an OSError, as for http_request",
}


def _census(sources: dict[str, str]) -> _Census:
    return _Census([_Module(name, ast.parse(text)) for name, text in sources.items()])


def _library() -> dict[str, str]:
    return {
        path.relative_to(_LIBRARY.parent).as_posix(): path.read_text()
        for path in sorted(_LIBRARY.rglob("*.py"))
    }


def _kept() -> dict[tuple[str, str, str], str]:
    """Return `KEPT` keyed by the module's name as the census names it."""
    return {(f"{_PACKAGE}/{m}", f, e): why for (m, f, e), why in KEPT.items()}


def test_no_refusal_holds_a_value_it_did_not_trace() -> None:
    """Each exception the package builds holds only what the census traces."""
    census = _census(_library())
    findings = census.findings(CALLER_VALUES, _kept())
    assert not findings, "\n".join(findings)
    # an entry no refusal uses is one a change made stale
    assert set(CALLER_VALUES) <= census.used, set(CALLER_VALUES) - census.used
    assert set(_kept()) <= census.used, set(_kept()) - census.used


# one module per shape the docstring claims, each refusing `key`, a public
# function's parameter, or a value made from it: the census traces the
# first of each pair and flags the second
_SHAPES = {
    "literal": (
        "def f(key):\n    raise ValueError('a literal')",
        "def f(key):\n    raise ValueError(key)",
    ),
    "comparison": (
        "def f(key):\n    raise ValueError(f'{key == 1}')",
        "def f(key):\n    raise ValueError(f'{key + 1}')",
    ),
    "capitals": (
        "import m\ndef f(key):\n    raise ValueError(m.LIMIT)",
        "def f(key):\n    raise ValueError(key.limit)",
    ),
    "describing call": (
        "def f(key):\n    raise ValueError(_quoted(key), len(key), _endpoint(key))",
        "def f(key):\n    raise ValueError(str(key))",
    ),
    "describing method": (
        "def f(key):\n    raise ValueError(key.count(';'), key.bit_length())",
        "def f(key):\n    raise ValueError(key.hex())",
    ),
    "name attribute": (
        "def f(key):\n    raise ValueError(type(key).__name__, key.__qualname__)",
        "def f(key):\n    raise ValueError(key.__doc__)",
    ),
    "enumerate": (
        "def f(keys):\n    for i, key in enumerate(keys):\n        raise ValueError(i)",
        (
            "def f(keys):\n    for i, key in enumerate(keys):\n"
            "        raise ValueError(key)"
        ),
    ),
    "enumerate start": (
        (
            "def f(keys):\n    for i, key in enumerate(keys, 1):\n"
            "        raise ValueError(i)"
        ),
        (
            "def f(keys, start):\n    for i, key in enumerate(keys, start):\n"
            "        raise ValueError(i)"
        ),
    ),
    "range": (
        "def f(n):\n    for i in range(n):\n        raise ValueError(i)",
        "def f(n, start):\n    for i in range(start, n):\n        raise ValueError(i)",
    ),
    "zip": (
        (
            "def f(keys):\n    for name, key in zip(('a',), keys):\n"
            "        raise ValueError(name)"
        ),
        (
            "def f(keys):\n    for name, key in zip(('a',), keys):\n"
            "        raise ValueError(key)"
        ),
    ),
    "rows": (
        (
            "def f(key):\n    for value, name in ((key, 'a'),):\n"
            "        raise ValueError(name)"
        ),
        (
            "def f(key):\n    for value, name in ((key, 'a'),):\n"
            "        raise ValueError(value)"
        ),
    ),
    "comprehension": (
        "def f(keys):\n    raise ValueError([len(key) for key in keys])",
        "def f(keys):\n    raise ValueError([key for key in keys])",
    ),
    "local name": (
        "def f(key):\n    text = 'a'\n    raise ValueError(text)",
        "def f(key):\n    text = 'a'\n    text = key\n    raise ValueError(text)",
    ),
    "with": (
        (
            "def _open():\n    return 'a'\n"
            "def f(key):\n    with _open() as text:\n        raise ValueError(text)"
        ),
        "def f(key):\n    with open(key) as text:\n        raise ValueError(text)",
    ),
    "mutator": (
        (
            "def f(key):\n    names = []\n    names.append('a')\n"
            "    raise ValueError(names)"
        ),
        (
            "def f(key):\n    names = []\n    names.append(key)\n"
            "    raise ValueError(names)"
        ),
    ),
    "item assignment": (
        (
            "def f(key):\n    names = {}\n    names['a'] = 'b'\n"
            "    raise ValueError(names)"
        ),
        (
            "def f(key):\n    names = {}\n    def g():\n        names['a'] = key\n"
            "    raise ValueError(names)"
        ),
    ),
    "private parameter": (
        "def _g(text):\n    raise ValueError(text)\ndef f(key):\n    _g('a')",
        "def _g(text):\n    raise ValueError(text)\ndef f(key):\n    _g(key)",
    ),
    "never called": (
        "def _g(text):\n    raise ValueError(len(text))",
        "def _g(text):\n    raise ValueError(text)",
    ),
    "read as a value": (
        "def _g(text):\n    raise ValueError(len(text))\nTABLE = {'a': _g}",
        "def _g(text):\n    raise ValueError(text)\nTABLE = {'a': _g}",
    ),
    "lambda": (
        "def f(key):\n    g = lambda text: ValueError(len(text))",
        "def f(key):\n    g = lambda text: ValueError(text)",
    ),
    "self": (
        "class C:\n    def _m(self):\n        raise ValueError(type(self))",
        "class C:\n    def _m(self):\n        raise ValueError(self)",
    ),
    "except": (
        (
            "def f(key):\n    try:\n        pass\n    except OSError as e:\n"
            "        raise ValueError(type(e).__name__) from e"
        ),
        (
            "def f(key):\n    try:\n        pass\n    except OSError as e:\n"
            "        raise ValueError(str(e)) from e"
        ),
    ),
    "environment": (
        "import os\ndef f(key):\n    raise ValueError(len(os.environ))",
        "import os\ndef f(key):\n    raise ValueError(os.environ['HOME'])",
    ),
    "arguments": (
        "import sys\ndef f(key):\n    raise ValueError(len(sys.argv))",
        "import sys\ndef f(key):\n    raise ValueError(sys.argv[0])",
    ),
    "returns": (
        "def _g(key):\n    return 'a'\ndef f(key):\n    raise ValueError(_g(key))",
        "def _g(key):\n    return key\ndef f(key):\n    raise ValueError(_g(key))",
    ),
    "item": (
        (
            "def _g(key):\n    return 'a', key\ndef f(key):\n"
            "    name, value = _g(key)\n    raise ValueError(name)"
        ),
        (
            "def _g(key):\n    return 'a', key\ndef f(key):\n"
            "    name, value = _g(key)\n    raise ValueError(value)"
        ),
    ),
    "item forwarded": (
        (
            "def _g(key):\n    return 'a', key\ndef _h(key):\n    return _g(key)\n"
            "def f(key):\n    name, value = _h(key)\n    raise ValueError(name)"
        ),
        (
            "def _g(key):\n    return 'a', key\ndef _h(key):\n    return _g(key)\n"
            "def f(key):\n    name, value = _h(key)\n    raise ValueError(value)"
        ),
    ),
    "method": (
        (
            "class C:\n    def _m(self, text):\n        raise ValueError(text)\n"
            "def f(key, c):\n    c._m('a')"
        ),
        (
            "class C:\n    def _m(self, text):\n        raise ValueError(text)\n"
            "def f(key, c):\n    c._m(key)"
        ),
    ),
    "raise of a call": (
        (
            "def _error(key):\n    return ValueError(len(key))\n"
            "def f(key):\n    raise _error(key)"
        ),
        (
            "def _error(key):\n    return ValueError(key)\n"
            "def f(key):\n    raise _error(key)"
        ),
    ),
    "error name": (
        "def f(key):\n    return KeyError('a')",
        "def f(key):\n    return KeyError(key)",
    ),
    "dict comprehension": (
        "def f(keys):\n    raise ValueError({len(k): len(k) for k in keys})",
        "def f(keys):\n    raise ValueError({k: 1 for k in keys})",
    ),
    "expression the census does not read": (
        "def f(key):\n    raise ValueError('a literal')",
        "def f(key):\n    raise ValueError(lambda: 1)",
    ),
    "chained assignment": (
        "def f(key):\n    a = b = len(key)\n    raise ValueError(a, b)",
        "def f(key):\n    a = b = key\n    raise ValueError(a, b)",
    ),
    "with of several items": (
        "def f(key):\n    with open('a') as h, lock():\n        raise ValueError(h)",
        "def f(key):\n    with open(key) as h, lock():\n        raise ValueError(h)",
    ),
    "zip of fewer iterables than names": (
        (
            "def f(key):\n    for a, b, c in zip((1,), (2,)):\n"
            "        raise ValueError(c)"
        ),
        (
            "def f(key):\n    for a, b, c in zip((1,), (key,)):\n"
            "        raise ValueError(c)"
        ),
    ),
    "tuple from a tuple": (
        "def f(key):\n    a, b = 1, len(key)\n    raise ValueError(b)",
        "def f(key):\n    a, b = 1, key\n    raise ValueError(b)",
    ),
    "tuple from a call outside the package": (
        "def f(key):\n    a, b = divmod(1, 2)\n    raise ValueError(a)",
        "def f(key):\n    a, b = divmod(key, 2)\n    raise ValueError(a)",
    ),
    "tuple from a generator": (
        (
            "def _g():\n    yield 1\n    yield 2\n"
            "def f(key):\n    a, b = _g()\n    raise ValueError(a)"
        ),
        (
            "def _g(key):\n    yield key\n    yield 2\n"
            "def f(key):\n    a, b = _g(key)\n    raise ValueError(a)"
        ),
    ),
    "attribute of self": (
        (
            "class C:\n    def __init__(self, key):\n        self.n = 1\n"
            "    def _m(self):\n        raise ValueError(self.n)"
        ),
        (
            "class C:\n    def __init__(self, key):\n        self.n = key\n"
            "    def _m(self):\n        raise ValueError(self.n)"
        ),
    ),
    "attribute of self in a tuple": (
        (
            "class C:\n    def __init__(self, key):\n        self.a, self.n = key, 1\n"
            "    def _m(self):\n        raise ValueError(self.n)"
        ),
        (
            "class C:\n    def __init__(self, key):\n        self.n, self.a = key, 1\n"
            "    def _m(self):\n        raise ValueError(self.n)"
        ),
    ),
    "attribute of self put into": (
        (
            "class C:\n    def __init__(self, key):\n        self.n = []\n"
            "        self.n.append(1)\n"
            "    def _m(self):\n        raise ValueError(self.n)"
        ),
        (
            "class C:\n    def __init__(self, key):\n        self.n = []\n"
            "        self.n.append(key)\n"
            "    def _m(self):\n        raise ValueError(self.n)"
        ),
    ),
    "attribute of self assigned elsewhere": (
        (
            "class C:\n    def _m(self):\n        raise ValueError(self.n)\n"
            "def f(key, c):\n    c.n = 1"
        ),
        (
            "class C:\n    def _m(self):\n        raise ValueError(self.n)\n"
            "def f(key, c):\n    c.n = key"
        ),
    ),
    "property of self": (
        (
            "class C:\n    def n(self):\n        return 1\n"
            "    def _m(self):\n        raise ValueError(self.n)"
        ),
        "class C:\n    def _m(self):\n        raise ValueError(self.n)",
    ),
    "exception of the package": (
        (
            "class E(Exception):\n    pass\ndef f(key):\n    try:\n        pass\n"
            "    except E as e:\n        raise ValueError(e) from e"
        ),
        (
            "class E(Exception):\n    pass\ndef f(key):\n    try:\n        pass\n"
            "    except (E, OSError) as e:\n        raise ValueError(e) from e"
        ),
    ),
    "items of a describing call": (
        "def f(key):\n    a, b = _split_url(key)\n    raise ValueError(b)",
        "def f(key):\n    a, b = urlsplit(key)\n    raise ValueError(b)",
    ),
    "item of a call outside the package": (
        (
            "def _g(key):\n    return divmod(1, 2)\n"
            "def f(key):\n    a, b = _g(key)\n    raise ValueError(a)"
        ),
        (
            "def _g(key):\n    return divmod(key, 2)\n"
            "def f(key):\n    a, b = _g(key)\n    raise ValueError(a)"
        ),
    ),
    "zip taken whole": (
        "def f(key):\n    for p in zip((1,), (2,)):\n        raise ValueError(p)",
        "def f(key):\n    for p in zip((1,), (key,)):\n        raise ValueError(p)",
    ),
    "put into what a call answers": (
        "def f(key):\n    a = [1]\n    _g()[0] = key\n    raise ValueError(a)",
        "def f(key):\n    a = [1]\n    a[0] = key\n    raise ValueError(a)",
    ),
    "global": (
        "a = 1\ndef f(key):\n    raise ValueError(a)",
        "a = 1\ndef f(key):\n    global a\n    raise ValueError(a)",
    ),
    "refusal of the module": (
        "raise ValueError('a')",
        "import sys\nraise ValueError(sys.argv[0])",
    ),
    "arguments unpacked": (
        "def _g(x):\n    raise ValueError(x)\ndef f(keys):\n    _g(1)",
        "def _g(x):\n    raise ValueError(x)\ndef f(keys):\n    _g(*keys)",
    ),
}


@pytest.mark.parametrize(("traced", "flagged"), _SHAPES.values(), ids=_SHAPES)
def test_census_controls(traced: str, flagged: str) -> None:
    """The census traces one module of a shape and flags the other."""
    assert not _census({"m.py": traced}).findings()
    assert _census({"m.py": flagged}).findings()


def test_the_tables_hide_their_own_entries_alone() -> None:
    """A caller's parameter is hidden by name, a kept argument by function."""
    module = "def f(key, other):\n    raise ValueError(key)\ndef g(key):\n"
    module += "    raise ValueError(key)"
    census = _census({"m.py": module})
    assert len(census.findings()) == 2
    callers = {"m.py parameter key of f": "", "m.py parameter key of g": ""}
    assert not census.findings(callers)
    assert census.used == set(callers)
    census = _census({"m.py": module})
    assert len(census.findings(kept={("m.py", "f", "key"): ""})) == 1
    assert census.used == {("m.py", "f", "key")}
    # a name the function binds to the kept argument is not traced either
    local = "def f(key):\n    text = key\n    raise ValueError(text)"
    assert not _census({"m.py": local}).findings(kept={("m.py", "f", "key"): ""})
