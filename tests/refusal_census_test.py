# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""No refusal of the package holds a value the census does not trace.

Section 7 of the organization's standard, *A refusal carries no secret*,
says an argument in the wrong place may be a key, and a key passed in the
wrong place can come back in what a node answers. The census reads the
sources and finds every exception the package builds: each call of a name
ending in `Error` or `Exception`, and the exception of each `raise` that is
not what a function of the package returns. Every argument of each has to
be traced to values a refusal may hold by the rules below, and one they do
not trace is a finding. It traces

- a literal, a comparison, a name bound by a `def`, a `class` or an
  import but one of `_PROCESS_INPUT`, a builtin of `_PURE_BUILTINS` or
  one whose name ends in `Error`, `Exception` or `Warning`, and an
  attribute named in capitals;
- what `_quoted`, `_kept_name`, `_endpoint`, `_split_url`,
  `_failure_name`, `len`, `type` and `bool` answer, what the methods
  `bit_length`, `count`, `find`, `index`, `start` and `end` answer, and a
  `__name__` or a `__qualname__`;
- the index `enumerate` counts from a start it traces, and each number a
  `range` counts, where it traces every argument of it;
- a call, an attribute or an item of what it traces, but an attribute of
  `_PROCESS_INPUT`; each element a loop or a comprehension takes from it,
  or `zip` pairs; and in a loop over rows written out, the column the
  name takes;
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
  the package passes there, and its default;
- what a function of the package answers, where it traces every value
  the function returns or yields, or the item at the position a tuple is
  unpacked from.

A name called is the `def` of the scope that binds it, or the one of the
module of the package it is imported from; an attribute called is every
method of that name in the package. So the census does not trace a
parameter of a public function or of a lambda, a method's `self` itself,
a function read as a value rather than called, any other exception an
`except` binds, or what `_PROCESS_INPUT` names. Each holds what a caller,
a node or another program handed over.

What a refusal still shows of those is in two tables, each entry with its
reason: `CALLER_VALUES`, a parameter whose value the caller passed, and
`KEPT`, an argument of the refusals of one function that the census does
not trace, nor any name that function binds to it. Of what a node sends,
they hold the rpc error code and the HTTP status alone. An entry no
refusal uses fails the census too.

Two things it takes on trust. A call outside the package answers only
what it is handed, the reads of `_PROCESS_INPUT` and a builtin outside
`_PURE_BUILTINS` aside. And a value reaches an object only through the
name the census reads it under. Of a container a name is bound to in its
own scope, a list, a dict, a set or what a call of `_CONTAINER_TYPES`
builds, these places it is handed to are each a finding: another name, an
item of another container, and an argument of a call other than a
refusal, one of `_READERS`, or a function of the package whose parameter
neither has a value put into it nor is handed on in turn. A container
reached any other way, through an attribute or what a call answers, is
not followed past the name the census reads.

An exception that is not one of the package's classes may hold the same
values, as a `JSONDecodeError` holds the document it failed on, so no
refusal chains one or has it as context. A `raise` inside an `except` of
another class, or in a `finally`, is a finding, `from None` included,
which keeps the context, and the exception handled raised again alone
excepted; so is a `raise ... from` anything but `None`, the exception of
an `except` of the package's own classes, or what a function of the
package builds of them. So is a call, inside such an `except`, that may
reach a `raise` of the package: of a function of the package that holds
one, or calls one that does, however far down, or of a callee the census
cannot name, a parameter, a local or what is no name, there or in any
function it reaches. A method is every method of that name in the
package, whatever object it is called on; a class of the package called
is its `__init__`, `__new__` and `__post_init__`; a builtin, or a name
imported from outside the package, runs none of it. What a call outside
the package raises is not one of its refusals, and is not read.
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
    {
        "_quoted",
        "_kept_name",
        "_endpoint",
        "_split_url",
        "_failure_name",
        "len",
        "type",
        "bool",
    }
)
_DESCRIBING_METHODS = frozenset(
    {"bit_length", "count", "find", "index", "start", "end"}
)
_DESCRIBING_ATTRIBUTES = frozenset({"__name__", "__qualname__"})
# what a module holds that the process was handed
_PROCESS_INPUT = frozenset(
    {
        "argv",
        "cwd",
        "environ",
        "environb",
        "expanduser",
        "getcwd",
        "getenv",
        "getenvb",
        "home",
        "input",
        "orig_argv",
        "stdin",
    }
)
# the builtins a refusal may be built of: each answers only what it is
# handed, and a module's `__name__` is its own
_PURE_BUILTINS = frozenset(
    {
        "__name__",
        "abs",
        "all",
        "any",
        "bool",
        "bytes",
        "chr",
        "divmod",
        "dict",
        "enumerate",
        "float",
        "frozenset",
        "hex",
        "int",
        "isinstance",
        "issubclass",
        "len",
        "list",
        "max",
        "min",
        "ord",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "zip",
    }
)
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
# what builds a container a value can be put into
_CONTAINERS = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)
_CONTAINER_TYPES = frozenset(
    {"list", "dict", "set", "bytearray", "deque", "defaultdict", "OrderedDict"}
)
# what reads a container handed to it, and puts nothing into it
_READERS = frozenset(
    {
        *_DESCRIBING,
        "all",
        "any",
        "enumerate",
        "frozenset",
        "isinstance",
        "iter",
        "join",
        "list",
        "max",
        "min",
        "reversed",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    }
)
_CONSTANT = re.compile(r"_*[A-Z][A-Z0-9_]*")
_FUNCTION = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_COMPREHENSION = (ast.ListComp, ast.SetComp, ast.GeneratorExp)
_BINDING = (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)
_LOOP = (ast.For, ast.AsyncFor, ast.comprehension)
_DECLARED = (ast.Import, ast.ImportFrom, *_FUNCTION, ast.ClassDef)
_BOUND = frozenset({"self", "cls"})


def _private(name: str) -> bool:
    return name.startswith("_") and not name.endswith("__")


def _called_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _positional(func: ast.AST) -> list[ast.arg]:
    args: ast.arguments = func.args  # type: ignore[attr-defined]
    return [*args.posonlyargs, *args.args]


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


def _builds_container(node: ast.AST) -> bool:
    """Return whether a binding assigns a container a value can be put into."""
    value = getattr(node, "value", None)
    if isinstance(node, ast.AugAssign) or value is None:
        return False
    if isinstance(value, _CONTAINERS):
        return True
    return isinstance(value, ast.Call) and _called_name(value.func) in _CONTAINER_TYPES


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
    raising: set[int] | None = None
    class_defs: dict[str, list[ast.ClassDef]] = field(default_factory=dict)

    def __post_init__(self) -> None:  # noqa: C901
        for module in self.modules:
            for node in ast.walk(module.tree):
                if isinstance(node, ast.ClassDef):
                    self.classes.add(node.name)
                    self.class_defs.setdefault(node.name, []).append(node)
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
        return found + self.chains()

    def chains(self) -> list[str]:
        """Return each `raise` that chains, or leaves as context, another error.

        And each call of a function of the package that raises, made while
        handling one.
        """
        found: list[str] = []
        for module in self.modules:
            for node in ast.walk(module.tree):
                if isinstance(node, ast.Raise) and node.exc is not None:
                    found.extend(self._chained(node, module))
                elif isinstance(node, ast.ExceptHandler) and not self._own(node.type):
                    found.extend(self._raising_calls(node, module))
        return found

    def _raising_calls(self, handler: ast.ExceptHandler, module: _Module) -> list[str]:
        """Return each call in an `except` body that may raise from the package.

        What a function of the package raises, itself or through any
        function of the package it calls, has the exception handled as
        context. A call whose callee the census cannot name is one too.
        """
        found: list[str] = []
        caught = "everything" if handler.type is None else ast.unparse(handler.type)
        for statement in handler.body:
            for node in [statement, *_own_nodes(statement)]:
                if not isinstance(node, ast.Call):
                    continue
                callee = ast.unparse(node.func)
                callees = self._callees(node.func, module)
                if callees is None:
                    found.append(
                        f"{module.where(node)}: calls {callee}, which the census"
                        f" cannot name, while handling {caught}"
                    )
                elif any(id(function) in self._raising() for function in callees):
                    found.append(
                        f"{module.where(node)}: calls {callee}, which raises,"
                        f" while handling {caught}"
                    )
        return found

    def _callees(self, func: ast.expr, module: _Module) -> list[ast.AST] | None:
        """Return the `def`s of the package a call may run, None where unknown.

        An attribute called is every method of that name in the package,
        whatever it is called on. A name is the `def` of the scope binding
        it, the one of the package it is imported from, or the constructor
        of a class of the package; a name nothing binds is a builtin, and
        one imported by name from outside the package runs none of it. A
        name bound any other way, a parameter or a local, is unknown, and so
        is a callee that is no name.
        """
        if isinstance(func, ast.Attribute):
            return self.methods.get(func.attr, [])
        if not isinstance(func, ast.Name):
            return None
        for scope in module.scopes(func):
            if isinstance(scope, _FUNCTION) and any(
                arg.arg == func.id for arg in _arguments(scope)
            ):
                return None
            bindings = [n for n in self._scope_nodes(scope) if _binds(n, func.id)]
            if not bindings:
                continue
            found: list[ast.AST] = []
            for binding in bindings:
                runs = self._runs(binding, func.id)
                if runs is None:
                    return None
                found.extend(runs)
            return found
        return []

    def _runs(self, binding: ast.AST, name: str) -> list[ast.AST] | None:
        """Return what calling a name a node binds runs, None where unknown."""
        if isinstance(binding, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return [binding]
        if isinstance(binding, ast.ImportFrom):
            return [
                *self._imported(binding, name),
                *self._constructors(binding.names, name),
            ]
        if isinstance(binding, ast.ClassDef):
            return self._constructors([], binding.name)
        return None

    def _constructors(self, names: list[ast.alias], name: str) -> list[ast.AST]:
        """Return what building a class of the package of a name runs."""
        source = next((a.name for a in names if (a.asname or a.name) == name), name)
        return [
            method
            for class_def in self.class_defs.get(source, [])
            for method in class_def.body
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
            and method.name in {"__init__", "__new__", "__post_init__"}
        ]

    def _raising(self) -> set[int]:
        """Return the ids of the `def`s of the package that may raise.

        A `def` holding a `raise` of an exception, or a call the census
        cannot name, and then, until nothing changes, one calling any of
        them.
        """
        if self.raising is None:
            calls: dict[int, list[list[ast.AST]]] = {}
            raising: set[int] = set()
            for function_id, (module, function) in self.functions.items():
                calls[function_id] = []
                for node in self._scope_nodes(function):
                    if isinstance(node, ast.Raise) and node.exc is not None:
                        raising.add(function_id)
                    elif isinstance(node, ast.Call):
                        callees = self._callees(node.func, module)
                        if callees is None:
                            raising.add(function_id)
                        else:
                            calls[function_id].append(callees)
            changed = True
            while changed:
                changed = False
                for function_id, callee_lists in calls.items():
                    if function_id not in raising and any(
                        id(callee) in raising
                        for callees in callee_lists
                        for callee in callees
                    ):
                        raising.add(function_id)
                        changed = True
            self.raising = raising
        return self.raising

    def _chained(self, node: ast.Raise, module: _Module) -> list[str]:
        """Return what a `raise` chains that can hold what it was handed.

        An exception is handled, and becomes the context of what is raised,
        in the body of each `except` around the `raise` and in a `finally`.
        One of the package's own classes holds what the census checks; any
        other may hold what a caller or a node handed over, as a
        `JSONDecodeError` holds the document it failed on.
        """
        found: list[str] = []
        handlers: list[ast.ExceptHandler] = []
        child: ast.AST = node
        parent = module.parents.get(node)
        while parent is not None and not isinstance(parent, (*_FUNCTION, ast.ClassDef)):
            if isinstance(parent, ast.ExceptHandler):
                handlers.append(parent)
            elif (
                isinstance(parent, (ast.Try, ast.TryStar)) and child in parent.finalbody
            ):
                found.append(f"{module.where(node)}: raised in a finally block")
            child, parent = parent, module.parents.get(parent)
        names = {handler.name for handler in handlers if handler.name}
        if isinstance(node.exc, ast.Name) and node.exc.id in names:
            # the exception handled, raised again: no refusal of the package
            return found
        for handler in handlers:
            if not self._own(handler.type):
                caught = (
                    "everything" if handler.type is None else ast.unparse(handler.type)
                )
                found.append(f"{module.where(node)}: raised while handling {caught}")
        cause = node.cause
        if not (
            cause is None
            or (isinstance(cause, ast.Constant) and cause.value is None)
            or (isinstance(cause, ast.Name) and cause.id in names)
            or self._own_kept(cause, module)
        ):
            found.append(f"{module.where(node)}: chains {ast.unparse(cause)}")
        return found

    def _own_kept(self, cause: ast.expr, module: _Module) -> bool:
        """Return whether a name, or an item of it, holds own exceptions alone.

        Each value put into it is an empty literal, None, the exception an
        `except` of the package's own classes binds, or what a function of
        the package returns where each of its `return`s builds one of them.
        """
        while isinstance(cause, ast.Subscript):
            cause = cause.value
        if not isinstance(cause, ast.Name):
            return False
        scope = module.scopes(cause)[0]
        own = {
            handler.name
            for handler in self._scope_nodes(scope)
            if isinstance(handler, ast.ExceptHandler)
            and handler.name
            and self._own(handler.type)
        }
        values: list[ast.expr | None] = []
        # and what any function the scope holds puts into it
        nested = self._mutations(scope).get(cause.id, [])
        for node in [*self._scope_nodes(scope), *nested]:
            if _mutates(node, cause.id):
                call = cast("ast.Call", node)
                values.extend([*call.args, *(k.value for k in call.keywords)])
            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and _binds(
                node, cause.id
            ):
                values.append(node.value)
            elif _binds(node, cause.id):
                return False
        return bool(values) and all(
            (isinstance(value, (ast.List, ast.Tuple)) and not value.elts)
            or (isinstance(value, ast.Constant) and value.value is None)
            or (isinstance(value, ast.Name) and value.id in own)
            or self._builds_own(value, module)
            for value in values
        )

    def _builds_own(self, value: ast.expr | None, module: _Module) -> bool:
        """Return whether a call is of functions building own classes alone."""
        if not isinstance(value, ast.Call):
            return False
        functions = self._resolve(value.func, module) or []
        returns = [
            node
            for function in functions
            for node in self._scope_nodes(function)
            if isinstance(node, ast.Return)
        ]
        return bool(returns) and all(
            isinstance(node.value, ast.Call)
            and _called_name(node.value.func) in self.classes
            for node in returns
        )

    def _own(self, caught: ast.expr | None) -> bool:
        """Return whether an `except` catches the package's classes alone."""
        if isinstance(caught, ast.Tuple):
            return all(self._own(each) for each in caught.elts)
        return _called_name(caught) in self.classes if caught is not None else False

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
            elif expr.id not in _PURE_BUILTINS and not expr.id.endswith(
                ("Error", "Exception", "Warning")
            ):
                # a builtin that reads what the process holds or was handed
                leaves.append(f"{module.where(expr)} {expr.id}, a builtin")
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
                    and all(
                        _called_name(d) != "staticmethod"
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
                if any(_builds_container(node) for node in bindings):
                    leaves.extend(self._escapes(scope, name, module))
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
        elif isinstance(node, (ast.Import, ast.ImportFrom)) and any(
            alias.name.rsplit(".", 1)[-1] in _PROCESS_INPUT
            and (alias.asname or alias.name).split(".")[0] == name
            for alias in node.names
        ):
            # what the process was handed, imported by name
            leaves.append(f"{module.where(node)} {name}, imported")
        elif isinstance(node, ast.ExceptHandler) and self._own_exception(node):
            # the package's own refusal, whose arguments are read where it
            # is built
            return
        elif not isinstance(node, _DECLARED):
            leaves.append(
                f"{module.where(node)} {name}, bound by {type(node).__name__}"
            )

    def _escapes(
        self, scope: ast.AST, name: str, module: _Module, depth: int = 0
    ) -> list[str]:
        """Return where a container a name is bound to is handed elsewhere.

        What is put into it through another name, or by what it is handed
        to, is not read: a name it is bound to, a container it is put
        into, and a call it is passed to are each a finding, but a refusal,
        a call that only reads it, and a function of the package whose
        parameter neither puts a value into it nor hands it on.
        """
        found: list[str] = []
        reads = [
            node
            for node in ast.walk(scope)
            if isinstance(node, ast.Name)
            and node.id == name
            and isinstance(node.ctx, ast.Load)
        ]
        for node in reads:
            parent = module.parents.get(node)
            if isinstance(parent, ast.Call) and node is not parent.func:
                callee = _called_name(parent.func) or ""
                if callee in _READERS or callee.endswith(("Error", "Exception")):
                    continue
                if self._only_read(parent, node, module, depth):
                    continue
            elif not isinstance(
                parent,
                (
                    ast.Assign,
                    ast.AnnAssign,
                    ast.AugAssign,
                    ast.NamedExpr,
                    ast.Call,
                    ast.keyword,
                    ast.Starred,
                    *_CONTAINERS,
                    ast.Tuple,
                    ast.Lambda,
                    ast.arguments,
                ),
            ) or (isinstance(parent, ast.AugAssign) and parent.target is node):
                continue
            found.append(
                f"{module.where(node)} {name}, handed to {type(parent).__name__}"
            )
        return found

    def _only_read(
        self, call: ast.Call, node: ast.Name, module: _Module, depth: int
    ) -> bool:
        """Return whether every package `def` a call runs only reads `node`.

        Where the parameter it is passed as has no value put into it in
        that `def`, and is handed nowhere else.
        """
        functions = self._resolve(call.func, module)
        if not functions or node not in call.args or depth > len(self.functions):
            return False
        for function in functions:
            function_module = self.functions[id(function)][0]
            positional = _positional(function)
            # a method called on its object is handed that object first
            position = call.args.index(node) + (
                bool(positional)
                and positional[0].arg in _BOUND
                and isinstance(call.func, ast.Attribute)
            )
            if position >= len(positional):
                return False
            parameter = positional[position].arg
            if self._mutations(function).get(parameter) or self._escapes(
                function, parameter, function_module, depth + 1
            ):
                return False
        return True

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
                # each number it counts is made of its start, its stop and
                # its step
                for bound in [*args, *(k.value for k in value.keywords)]:
                    self._visit(bound, module, leaves, keys)
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
        # the default, which a call that passes nothing there takes
        defaults: dict[ast.arg, ast.expr | None] = dict(
            zip(
                positional[len(positional) - len(func_args.defaults) :],
                func_args.defaults,
                strict=True,
            )
        )
        defaults.update(zip(func_args.kwonlyargs, func_args.kw_defaults, strict=True))
        default = defaults.get(arg)
        if default is not None:
            self._visit(default, module, leaves, keys)
        calls = self.calls.get(id(func), [])
        if not calls and default is None:
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
    ("client.py", "_rpc_error", "code"): (
        "the rpc error code the node sent, an integer of at most 32 bits"
    ),
    ("client.py", "_http_error", "status"): (
        "the HTTP status, shown where `_is_http_status` finds it three digits"
    ),
    ("client.py", "_json_scalar", "value"): (
        "a float that is not finite: nan, inf or -inf"
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
        "def f(n):\n    for i in range(3):\n        raise ValueError(i)",
        "def f(n):\n    for i in range(n):\n        raise ValueError(i)",
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
            "def f(key):\n    failure = ''\n    try:\n        pass\n"
            "    except OSError as e:\n        failure = type(e).__name__\n"
            "    raise ValueError(failure)"
        ),
        (
            "def f(key):\n    failure = ''\n    try:\n        pass\n"
            "    except OSError as e:\n        failure = str(e)\n"
            "    raise ValueError(failure)"
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
        (
            "def _make(x):\n    return x\n"
            "def f(key):\n    with _make('a') as h, lock():\n        raise ValueError(h)"
        ),
        (
            "def _make(x):\n    return x\n"
            "def f(key):\n    with _make(key) as h, lock():\n        raise ValueError(h)"
        ),
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
    "chained": (
        (
            "class _OwnError(Exception):\n    pass\ndef f(key):\n    try:\n"
            "        pass\n    except _OwnError as e:\n"
            "        raise ValueError('a') from e"
        ),
        (
            "def f(key):\n    try:\n        pass\n    except ValueError as e:\n"
            "        raise ValueError('a') from e"
        ),
    ),
    "context": (
        (
            "def f(key):\n    failed = False\n    try:\n        pass\n"
            "    except ValueError:\n        failed = True\n"
            "    if failed:\n        raise ValueError('a')"
        ),
        (
            "def f(key):\n    try:\n        pass\n    except ValueError:\n"
            "        raise ValueError('a') from None"
        ),
    ),
    "context of a bare except": (
        "def f(key):\n    try:\n        pass\n    except:\n        raise",
        "def f(key):\n    try:\n        pass\n    except:\n        raise ValueError('a')",
    ),
    "finally": (
        "def f(key):\n    try:\n        raise ValueError('a')\n    finally:\n        pass",
        "def f(key):\n    try:\n        pass\n    finally:\n        raise ValueError('a')",
    ),
    "cause kept": (
        (
            "class _OwnError(Exception):\n    pass\ndef f(key):\n    seen = []\n"
            "    try:\n        pass\n    except _OwnError as e:\n"
            "        seen.append(e)\n    raise ValueError('a') from seen[-1]"
        ),
        (
            "def f(key):\n    seen = []\n    try:\n        pass\n"
            "    except ValueError as e:\n        seen.append(e)\n"
            "    raise ValueError('a') from seen[-1]"
        ),
    ),
    "cause of a call": (
        "def f(key):\n    raise ValueError('a') from None",
        "def f(key):\n    raise ValueError('a') from g()",
    ),
    "cause bound by a loop": (
        (
            "class _OwnError(Exception):\n    pass\ndef f(key):\n    last = None\n"
            "    try:\n        pass\n    except _OwnError as e:\n        last = e\n"
            "    raise ValueError('a') from last"
        ),
        (
            "def f(errors):\n    for last in errors:\n        pass\n"
            "    raise ValueError('a') from last"
        ),
    ),
    "cause built by the package": (
        (
            "class _OwnError(Exception):\n    pass\ndef _g():\n"
            "    return _OwnError('a')\ndef f(key):\n    cause = _g()\n"
            "    raise ValueError('a') from cause"
        ),
        (
            "class _OwnError(Exception):\n    pass\ndef _g(key):\n"
            "    return key\ndef f(key):\n    cause = _g(key)\n"
            "    raise ValueError('a') from cause"
        ),
    ),
    "cause built by no function of the package": (
        (
            "class _OwnError(Exception):\n    pass\ndef f(key):\n"
            "    cause = None\n    raise ValueError('a') from cause"
        ),
        "def f(key):\n    cause = g()\n    raise ValueError('a') from cause",
    ),
    "raising call in an except": (
        (
            "class _OwnError(Exception):\n    pass\ndef _g():\n"
            "    raise ValueError('a')\ndef f(key):\n    try:\n        pass\n"
            "    except _OwnError:\n        _g()"
        ),
        (
            "def _g():\n    raise ValueError('a')\ndef f(key):\n    try:\n"
            "        pass\n    except ValueError:\n        _g()"
        ),
    ),
    "method called in an except": (
        (
            "class C:\n    def _g(self):\n        raise ValueError('a')\n"
            "    def _f(self, other):\n        try:\n            pass\n"
            "        except ValueError:\n            other.close()"
        ),
        (
            "class C:\n    def _g(self):\n        raise ValueError('a')\n"
            "    def _f(self):\n        try:\n            pass\n"
            "        except ValueError:\n            self._g()"
        ),
    ),
    "method of another object called in an except": (
        (
            "class C:\n    def _g(self):\n        return 1\n"
            "    def _f(self, other):\n        try:\n            pass\n"
            "        except ValueError:\n            other._g()"
        ),
        (
            "class C:\n    def _g(self):\n        raise ValueError('a')\n"
            "    def _f(self, other):\n        try:\n            pass\n"
            "        except ValueError:\n            other._g()"
        ),
    ),
    "method of super called in an except": (
        (
            "class C:\n    def _g(self):\n        raise ValueError('a')\n"
            "    def _f(self):\n        try:\n            pass\n"
            "        except ValueError:\n            make().close()"
        ),
        (
            "class C:\n    def _g(self):\n        raise ValueError('a')\n"
            "    def _f(self):\n        try:\n            pass\n"
            "        except ValueError:\n            super()._g()"
        ),
    ),
    "handled exception raised again": (
        "def f(key):\n    try:\n        pass\n    except ValueError as e:\n        raise e",
        (
            "def f(key):\n    try:\n        pass\n    except ValueError as e:\n"
            "        raise ValueError(e)"
        ),
    ),
    "default of a parameter": (
        (
            "def f(key):\n    def _g(text='a'):\n        raise ValueError(text)\n"
            "    _g()"
        ),
        (
            "def f(key):\n    def _g(text=key):\n        raise ValueError(text)\n"
            "    _g()"
        ),
    ),
    "default of a keyword": (
        (
            "def f(key):\n    def _g(*, text='a'):\n        raise ValueError(text)\n"
            "    _g()"
        ),
        (
            "def f(key):\n    def _g(*, text=key):\n        raise ValueError(text)\n"
            "    _g()"
        ),
    ),
    "step of a range": (
        "def f(key):\n    for i in range(0, 6, 2):\n        raise ValueError(i)",
        "def f(key):\n    for i in range(0, key * 2, key):\n        raise ValueError(i)",
    ),
    "container aliased": (
        (
            "def f(key):\n    values = []\n    size = len(values)\n"
            "    raise ValueError(values, size)"
        ),
        (
            "def f(key):\n    values = []\n    alias = values\n"
            "    alias.append(key)\n    raise ValueError(values)"
        ),
    ),
    "container handed to a function of the package": (
        (
            "def _read(items):\n    return len(items)\n"
            "def f(key):\n    values = []\n    _read(values)\n"
            "    raise ValueError(values)"
        ),
        (
            "def _fill(items, key):\n    items.append(key)\n"
            "def f(key):\n    values = []\n    _fill(values, key)\n"
            "    raise ValueError(values)"
        ),
    ),
    "container handed on by a function of the package": (
        (
            "class C:\n    def _read(self, items):\n        return len(items)\n"
            "    def _m(self):\n        values = list()\n        self._read(values)\n"
            "        raise ValueError(values)"
        ),
        (
            "def _fill(items):\n    other = items\n"
            "def f(key):\n    values = []\n    _fill(values)\n"
            "    raise ValueError(values)"
        ),
    ),
    "container handed past the parameters": (
        (
            "def _read(items):\n    return len(items)\n"
            "def f(key):\n    values = {}\n    _read(values)\n"
            "    raise ValueError(values)"
        ),
        (
            "def _read():\n    return 1\n"
            "def f(key):\n    values = {}\n    _read(values)\n"
            "    raise ValueError(values)"
        ),
    ),
    "container handed to a call outside the package": (
        (
            "def f(key):\n    values = []\n    total = sum(values)\n"
            "    raise ValueError(values, total)"
        ),
        (
            "from heapq import heappush\ndef f(key):\n    values = []\n"
            "    heappush(values, key)\n    raise ValueError(values)"
        ),
    ),
    "environment imported": (
        "from os import sep\ndef f(key):\n    raise ValueError(sep)",
        "from os import environ\ndef f(key):\n    raise ValueError(environ['A'])",
    ),
    "builtin": (
        "def f(key):\n    raise ValueError(len('a'))",
        "def f(key):\n    raise ValueError(input())",
    ),
    "raising call reached in an except": (
        (
            "def _inner():\n    return 1\ndef _outer():\n    _inner()\n"
            "def f(action):\n    try:\n        action()\n    except OSError:\n"
            "        _outer()"
        ),
        (
            "def _inner():\n    raise ValueError('safe')\ndef _outer():\n"
            "    _inner()\ndef f(action):\n    try:\n        action()\n"
            "    except OSError:\n        _outer()"
        ),
    ),
    "call of an unknown callee in an except": (
        (
            "import os\ndef f(fd):\n    try:\n        pass\n    except OSError:\n"
            "        os.close(fd)\n        raise"
        ),
        (
            "def f(action):\n    try:\n        pass\n    except OSError:\n"
            "        action()"
        ),
    ),
    "call of an unknown callee reached in an except": (
        (
            "def _g(x):\n    return x\ndef f(action):\n    try:\n        pass\n"
            "    except OSError:\n        _g(1)"
        ),
        (
            "def _g(action):\n    action()\ndef f(action):\n    try:\n"
            "        pass\n    except OSError:\n        _g(action)"
        ),
    ),
    "callee that is no name in an except": (
        (
            "def f(key):\n    try:\n        pass\n    except OSError:\n"
            "        print('a')"
        ),
        (
            "def f(handlers):\n    try:\n        pass\n    except OSError:\n"
            "        handlers[0]()"
        ),
    ),
    "class built in an except": (
        (
            "class _C:\n    def __init__(self):\n        self.a = 1\n"
            "def f(key):\n    try:\n        pass\n    except OSError:\n        _C()"
        ),
        (
            "class _C:\n    def __init__(self):\n        raise ValueError('a')\n"
            "def f(key):\n    try:\n        pass\n    except OSError:\n        _C()"
        ),
    ),
    "local callee in an except": (
        (
            "from os import close\ndef f(key):\n    try:\n        pass\n"
            "    except OSError:\n        close(1)"
        ),
        (
            "def f(key):\n    handler = make()\n    try:\n        pass\n"
            "    except OSError:\n        handler()"
        ),
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
    module = (
        "def f(key, other):\n    raise ValueError(key)\ndef g(key):\n"
        "    raise ValueError(key)"
    )
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


# the library with one refusal put back as it was before issue 808, or as a
# change could write it: each is a finding
_SEEDS = {
    "a JSONDecodeError chained": (
        "client.py",
        'refusal = FetchError(f"{where}: not json")',
        'raise FetchError(f"{where}: not json") from e',
    ),
    "an HTTPException written into the text": (
        "transport.py",
        "failure = _failure_name(e)",
        "failure = str(e)",
    ),
    "an OSError written and chained": (
        "transport.py",
        "failure = _failure_name(e)",
        'raise FetchError(f"no answer from {where}: {e}") from e',
    ),
    "raised from None while handling a FileNotFoundError": (
        "chains.py",
        "missing = True",
        'raise FetchError("no cookie") from None',
    ),
}


@pytest.mark.parametrize(("module", "old", "new"), _SEEDS.values(), ids=_SEEDS)
def test_the_census_finds_a_refusal_put_back(module: str, old: str, new: str) -> None:
    """Each seed is a finding of the census, and the library is not."""
    sources = _library()
    name = f"{_PACKAGE}/{module}"
    assert old in sources[name]
    sources[name] = sources[name].replace(old, new, 1)
    assert _census(sources).findings(CALLER_VALUES, _kept())
