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
file that is about its single module.

So which of them this repository tests is **declared here**, and
`conventions_test.py` asserts the declaration is true: every convention
named below is one of section 7's, every module named exists and holds at
least one test, and the two halves together account for the whole list.

| convention | tested in |
| --- | --- |
| the documentation | `standalone_test.py` |
| the import graph | `standalone_test.py` |

Not tested here: the public surface; the copyright header; the changelog;
the build system; the calling convention; input validation.

One module answers two bullets, which is the shape section 7 has in mind
where it says what must not be aligned is *where* these live. This
package is one file, so the properties that elsewhere need a walk over a
tree are here properties of that file, and they are stronger for it:
**the documentation** is not "every module appears in the sphinx pages"
but every name of `__all__` carrying a docstring `automodule` will
render, against `docs/source/api.rst`'s claim to list the whole public
surface; **the import graph** is not "every module imports first" but the
source importing nothing outside the standard library, and a copy of it
running under `python -I -S` where nothing else is importable at all.

Among those not tested, two are near misses worth naming so that
"absent" is not read as "overlooked":

- **The public surface.** `__all__` is declared, and
  `standalone_test.py` reads it — but to ask whether each name is
  documented, not whether the module's public names are all in it.
  Section 7 asks for a census that fails when a new public name appears;
  nothing here fails.
- **The calling convention.** Two tests assert a keyword-only signature
  — `test_connection_controls_are_keyword_only` and
  `test_the_incremental_limit_is_keyword_only` — each about one function.
  Section 7 asks for it as a rule over the package: keyword-only stays
  keyword-only, a private signature carries no default, a name's prefix
  promises what the call answers.

The copyright header, the changelog, the build system and input
validation have nothing standing in for them. `normalize_sdist_test.py`
tests the sdist normalizer of `.github/scripts` rather than what runs
while a distribution is built.

[std]: https://github.com/btclib-org/.github/blob/main/README.md
