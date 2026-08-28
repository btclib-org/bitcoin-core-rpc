# Tests

This file exists for section 7 of the [organization standard][std],
which asks each repository to declare which of its conventions the suite
turns into a red test rather than leave it to be read off a directory
listing. `tests/_data/README.md` is the other file here, and it is about
the recorded replies rather than about the suite.

## Convention tests

Section 7 lists the conventions, and says a repository needs the ones
its own prose states rather than all of them. That escape clause is right
and it costs something: an absent convention test reads exactly like a
convention this repository does not have, and a `grep` over `tests/`
cannot tell the two apart — the suites of the organization name the same
idea three different ways, and this one folds several checks into the
file that is about the package's own census.

So which of them this repository tests is **declared here**, and
`conventions_test.py` asserts the declaration is true: every convention
named below is one of section 7's, every module named exists and holds at
least one test, and the two halves together account for the whole list.

| convention | tested in |
| --- | --- |
| the public surface | `census_test.py` |
| the documentation | `census_test.py` |
| the import graph | `census_test.py` |

Not tested here: the copyright header; the changelog; the build system;
the calling convention; input validation; the suite opens no socket.

One module answers several bullets, which is the shape section 7 has in
mind where it says what must not be aligned is *where* these live. This
package is `errors.py`, `chains.py`, `transport.py` and `client.py` behind
an `__init__.py` facade, and the three properties below read the four,
`__init__.py` re-exporting rather than defining: **the public surface**
walks every one of the four for a name it defines and does not
underscore, and every such name has to be in `__all__` and every name in
`__all__` has to be defined by one of the four; **the documentation** is
not "every module appears in the sphinx pages" but every name of
`__all__` carrying a docstring `automodule` will render, against
`docs/source/api.rst`'s claim to list the whole public surface; **the
import graph** is not "every module imports first" but the four
importing nothing outside the standard library and each other, in the
order `errors < chains < transport < client`, and `chains.py` and
`errors.py` each leaving `urllib.request`, `ssl` and `socket` out of a
fresh interpreter's `sys.modules`.

The public surface is not one this repository could have declined.
Section 7's escape clause — a repository needs the conventions its own
prose states — stops short of it wherever an importable package is
published, and this one publishes: `py.typed` ships, so which names are
supported is the other half of a promise the distribution already makes.

Among those not tested, one is a near miss worth naming so that
"absent" is not read as "overlooked":

- **The calling convention.** Two tests assert a keyword-only signature
  — `test_connection_controls_are_keyword_only` and
  `test_the_incremental_limit_is_keyword_only` — each about one function.
  Section 7 asks for it as a rule over the package: keyword-only stays
  keyword-only, a private signature carries no default, a name's prefix
  promises what the call answers.

**The suite opens no socket** is not a near miss but the one bullet this
suite does not keep rather than merely leave untested.
`rpc_smoke_test.py` binds a loopback port of its own and listens on it,
to test the port probe `.github/scripts/rpc_smoke.py` uses against a port
that is held and against one that is free. Nothing leaves the machine and
no node is needed, but section 7 asks for this convention to be driven by
a walk over the call sites, and a walk over `socket()` finds exactly
those: a test of it here would carry that file written into it as an
exception, which is the fixed list the bullet refuses. What keeps the
clients hermetic is `transport=`, and `tests/__init__.py` is where that
is written down.

The copyright header, the changelog, the build system and input
validation have nothing standing in for them. `normalize_sdist_test.py`
tests the sdist normalizer of `.github/scripts` rather than what runs
while a distribution is built.

[std]: https://github.com/btclib-org/.github/blob/main/README.md
