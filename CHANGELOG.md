# Changelog

<!-- markdownlint-configure-file
  {
    // MD024/no-duplicate-heading - every release repeats the same few
    // headings ("Added", "Changed", "Repository"), which is what keeps
    // the page readable scrolling down it; only a duplicate under the
    // same release heading would be the accident this rule looks for
    "MD024": { "siblings_only": true }
  }
-->

An entry for anything a reader would notice, in the group it belongs to:
what changed, why, and what it cost. That is section 9 of
[the organization standard][std] and `CONTRIBUTING.md`'s own sentence,
and it is narrower than "every change" — a comment reworded inside a
workflow changes nothing a reader of this repository meets, and lands
without an entry. Where the two readings differ, what decides is whether
somebody who did not write the change would see it.
[RELEASE_NOTES.md](./RELEASE_NOTES.md) has the release notes, which say
what a user has to act on; this file is the record behind them, and is
where a claim in those notes can be checked.

[std]: https://github.com/btclib-org/.github

Neither file counts its entries: `grep -c '^- '` does that, whereas a
stated number is a line every open branch has to edit, and the two files
carry a union merge driver that would keep both sides' numbers.

## v2026.9 (work in progress, not released yet)

### Changed

- **The documentation is built with `furo` and with `-n` beside `-W`**
  (issue #256). Section 3 of the organization standard picks the theme
  for the shape a reference generated from docstrings has, and section 5
  asks for nitpick mode: `-W` never sees a cross-reference that resolves
  to nothing, so a renamed class in a `:class:` role is a green build and
  a dead link. `sphinx.ext.intersphinx` lands with it and comes first,
  without which every annotation naming `pathlib.Path` or
  `collections.abc.Callable` would be reported as this tree's own broken
  link. `nitpick_ignore` is empty, which is what the build answering
  clean means.

- **`Chain`'s docstring no longer opens with a phrase napoleon reads as a
  type** (issue #256). `Core's five chain names: what -chain= takes` has
  the shape napoleon parses as `type: description`, so the built page
  carried a `Type: Core's five chain names` field naming a class nothing
  declares — invisible while `-W` alone ran, and the first thing `-n`
  reports. The docstring says the same in a sentence that is not that
  shape.

- **The sdist ships no test module it cannot run** (closes #220).
  `tests/rpc_smoke_test.py` and `tests/normalize_sdist_test.py` load a
  script out of `.github/scripts` by path and `tests/interpreters_test.py`
  reads the workflow matrices, and `.github` is not in the archive — it is
  on `check-sdist`'s own default ignore list. Unpacked and run, those
  three were a `FileNotFoundError` and a failed assertion rather than a
  test, so a packager building from the sdist read a red suite that said
  nothing about this package. `[tool.uv.build-backend]` `source-exclude`
  now names them.

- **A run narrowed by `--deselect`, `--ignore`, `--ignore-glob` or `--lf`
  is reported and not gated** (closes #268). `tests/conftest.py`'s
  `coverage_fail_under` read `-k`, `-m` and the paths alone, so
  `uv run pytest --ignore=tests/transport_test.py` was handed the whole
  suite's floor with part of the suite left out and ended in `Required
  test coverage of 100.0% not reached` — the shortfall being the tests
  that did not run, printed the way one of the tree's own would be.
  Section 8 of the organization standard names the set, and it is the
  set the hook now reads. `--lf` counts wherever it appears rather than
  only where the cache holds a failure to rerun: what decides is what
  the invocation asked for, and the price is the `--lf` that finds
  nothing to rerun and so is the whole suite ungated. The hook takes
  `config.option` rather than one parameter per flag, so what a run
  asked for is read in one place.

- **The convention declaration names section 7's socket bullet** (issue
  btclib-org/.github#458). `tests/conventions_test.py`'s `_CONVENTIONS`
  is the vocabulary `tests/README.md`'s declaration is written in, and
  **the suite opens no socket** was missing from it — a name outside the
  tuple fails the check, so that convention could be put in neither half
  of the declaration, neither the table nor *Not tested here*. It is
  declared not tested, with the reason: `rpc_smoke_test.py` binds a
  loopback port of its own and listens on it to test the port probe
  `.github/scripts/rpc_smoke.py` uses, so a walk over `socket()` call
  sites — which is how section 7 asks for the convention to be driven —
  finds those constructions, and a test of it here would carry that file
  written into it as the exemption the bullet refuses. The sentences
  that asserted the opposite in passing, in `CONTRIBUTING.md`'s
  environment section and in `pyproject.toml`'s `-n auto` comment, say
  instead what holds: no test here reaches the network.

### Repository

- **`claude-review.yml`'s header points at the ceiling's home** (closes
  #269). Section 10 of the organization standard gives the ceiling on
  concurrent jobs one home per tree, `REPOSITORY.md`'s *Plan-gated
  settings*, beside the command that re-derives it and GitHub's own
  table. This header named `CONTRIBUTING.md`, which states the ceiling
  unnumbered and points on to that section: a pointer to a pointer, where
  the other workflow comments that need the same reasoning name the
  section themselves.

  ```shell
  git grep -n 'Plan-gated' -- '*.yml'
  ```

  One word: `'concurrent jobs'` and `'Plan-gated settings'` each answer
  five, and a different five. It answers six — `claude-review`,
  `codeql`, `mutation`, `os-macos`, `os-ubuntu`, `os-windows` — which is
  every workflow comment here that states the ceiling. The command is
  what finds them the next time the figure's home moves; this entry is
  what one such move left behind.

- **The badge row is a function of the tree and its order is section 2's**
  (closes #262, issue #256). The licence badge was
  `img.shields.io/badge/license-MIT-blue`, which renders `MIT` because the
  URL says so rather than because `LICENSE` does; the derived form
  replaces it. Read the Docs is named at `app.readthedocs.org`, the other
  spelling answering `307` to it. What the property rule adds is `wheel`,
  `implementation`, `github/v/release` and a badge per sentinel, in the
  order section 10's calendar gives them. The rows are grouped by a blank
  line as `btclib` and `btclib-secp256k1` group theirs, which is what makes
  the block's own comment true of what renders: two hard line breaks split
  it into a row the comment did not describe. `trailing-whitespace` keeps
  no markdown derogation now, nothing here spelling a line break that way.

- **ruff selects every family it ships** (issue #256). `select = ["ALL"]`
  rather than a hand-picked list, which is a thing that rots: nothing
  forces a second edit the day ruff ships a family nobody has looked at.
  What each newly reached family costs is in `ignore`, one entry per rule
  and the reason beside it — the formatter's own conflict list cited from
  ruff's `docs/formatter.md`, the declines this tree argues for itself,
  and the families whose construct this tree does not contain. `PYI034` is
  answered where it fires instead, with a `# noqa` that `RUF100` retires
  the day the interpreter floor reaches `Self`.

- **`codeql.yml` runs on a pull request** (closes #233, issue #256). The
  OpenSSF Scorecard's `SAST` check walks a merged pull request's own
  commits and scored the analysis as run on none of them, the workflow
  producing no run there. The same trigger is what makes
  `codeql: every job passed` a name a branch rule could require, which is
  what an aggregate job is for: without it the job produced a context no
  rule could ask for. Whether the rule asks is `REPOSITORY.md`'s, which
  reads the endpoint.

- **`scorecard.yml`, and `griffe check` in the release path** (issue
  #256). `gh api repos/btclib-org/bitcoin-core-rpc --jq '.fork, .private'`
  answers `false` and `false`, which is the property section 10 keys the
  sentinel on; its calendar row already exists and its minute is this
  repository's. The `public-api` job compares the tag being cut against
  the tag before it and the publish jobs wait on it: the public-surface
  census asserts that `__all__` is declared and that what it names exists,
  which never asks whether this release took something the last one gave.

- **The public surface is a census** (closes #235). Section 7 stops its
  escape clause short of a repository publishing an importable package,
  and this one publishes. `standalone_test.py` walks the module's own body
  and fails when a name it defines and does not underscore is missing from
  `__all__`, or when `__all__` names something nothing defines — the
  second being a failure a caller writing `from bitcoin_core_rpc import *`
  would otherwise be the first to see. `tests/README.md` moves the bullet
  from *Not tested here* to the table.

- **The ceiling on concurrent jobs has one home** (issue
  btclib-org/.github#412). The figure was stated in four workflow headers,
  in `CONTRIBUTING.md` and twice in `REPOSITORY.md`, none of them beside a
  command. It now lives in `REPOSITORY.md`'s *Plan-gated settings*, with
  `gh api orgs/btclib-org --jq .plan.name` and GitHub's own table beside
  it; every other statement gives the reasoning with the ceiling unnumbered
  and points there. A date beside the number was the rejected
  alternative: it says when the figure was true and never that it still is.

- **`pypi-install.yml`'s index-wait step runs on every trigger** (issue
  btclib-org/.github#49). Guarded by `if: inputs.version != ''` a tag was
  the script's only execution path, and a step a release is the first to
  run is a step whose defect ships with that release — which this script
  has already done, in more than one repository of the organization. The
  empty case is a condition around the loop rather than an early `exit 0`,
  and that is the whole point of the change: bash parses a script as it
  runs, so an exit at the top leaves what follows unparsed and the weekly
  runs would go on not reading it. Measured — a syntax error below an
  early `exit 0` prints and exits `0`, the same error inside a branch the
  run does not take exits `2`.

- **The queue measurements that nothing re-derives are gone** (closes
  #213, #216, #217). `os-windows.yml`'s header weighed "the fourteen
  Windows cells" against "ubuntu's twenty-eight", where the second
  contained the first, and named a job pair `42e600e` had already
  superseded; `os-macos.yml` offered a command reading `test.yml`'s latest
  run, which carries no macOS cell, for a figure taken from a matrix the
  gate no longer has. Both headers now say why those rows are off the
  gate, which is the ceiling above, and state no count of their own.
  `REPOSITORY.md`'s code-quality figure keeps its number and gains the
  command that answers it — the check runs of a commit of that era, since
  the run-list name it pointed at is gone, and `per_page` is load-bearing
  there.

- **`CHANGELOG.md` says what section 9 says it holds** (closes #218). The
  head claimed "every change of a release, in full", which a
  workflow-comment change refutes by landing without an entry. The rule is
  the standard's and `CONTRIBUTING.md`'s: an entry for anything a reader
  would notice.

- **`CONTRIBUTING.md` and `REVIEWING.md` take the standard's shared half
  byte for byte** (closes #246). Everything above
  *This repository in particular* is now identical to
  `btclib-org/.github`'s copy, which is what section 14 compares. What
  arrives with it: *The landing queue*, the two citation spellings named
  rather than pointed at, the `sha` pin on the merge call, and
  `REVIEWING.md`'s verdict section, whose ack of record is a review rather
  than a comment — which `claude-review.yml` already does, `e57f9a6`
  having converged it on `gh pr review --comment` before this branch
  existed, so the shared half arrives describing a workflow this tree
  already runs rather than one it owes.

- **`tests/conftest.py` no longer claims to keep btclib's docstring in
  full** (closes #265). It does not, and cannot: each docstring names an
  example path out of the suite it sits in. What is true is that this tree
  took the reasoning rather than deriving a second one, which is what the
  sentence says now.

- **`tests/__init__.py`'s claim is about the clients** (closes #248). No
  test builds a client that could reach a node, which is the property
  `transport=` on every construction buys. Sockets are opened here:
  `rpc_smoke_test.py` binds and listens on a loopback port to test the
  port probe, so section 7's stricter "the suite opens no socket" is not
  what this suite answers, and the docstring says so rather than leaving a
  walk over `socket()` call sites to find it.

- **hypothesis stays out, and `_read_bounded` is why that was measured**
  (closes #253). Its arithmetic is over indices, which is the space a
  generator searches and a case list does not — but a chunk boundary
  cannot split a character here, the body being accumulated in one
  bytearray and decoded once after the loop, and both places a body is
  cut — `_read_bounded`'s `truncate=True`, and the `MAX_ERROR_BODY_SIZE`
  slice on a caller's own transport, which `_read_bounded` never sees —
  are reached only under a non-200, where every parse failure is answered
  with the status. What is left is two indices, `max_body_size`
  and one past it, which `tests/transport_test.py` already asserts in each
  direction. The exemption's comment carries that measurement.

- **The coverage floor holds for `uv run pytest tests`, the spelling
  that names the whole suite** (closes btclib-org/.github#430).
  `testpaths` is `tests`, so that path collects exactly what a bare run
  collects, and `tests/conftest.py` read it as a selection from the
  suite and handed the run a threshold of zero: the same command passed
  with the path named and failed without it, over the same tests and the
  same total. `asks_for_everything` decides it by containment against
  `testpaths` now — a path at or above an entry takes the suite in,
  `./tests` and the absolute path being that same directory — and a file
  under it is still the subset the floor comes off for. The hook is
  handed two directories because pytest reads a positional argument
  against the one it was invoked from and `testpaths` against the
  rootdir. `--help`, where `config.option.file_or_dir` is `None` rather
  than `[]`, names no path either and is folded into the same answer.
  `btclib-node`'s `tests/conftest.py` is where that function comes from.
  Whether `--lf`, `--deselect` and `--ignore` should relax the floor too
  is a separate question, btclib-org/.github#424; `-k` and `-m` are
  unchanged.

- **`claude-review.yml`'s `mention` job refuses a missing credential in
  the words of the job it guards** (issue btclib-org/.github#402). That
  job answers an `@claude` comment and reviews nothing, so its step is
  `Refuse to answer without a credential` and its message ends `without
  it this workflow answers nothing`. The comment above the step gives
  the reason by pointing at the review job's own rather than restating a
  measurement made there (issue btclib-org/.github#410).

- **`claude-review.yml`'s `claude_args` comment names the `gh pr`
  subcommands this file uses** (issue btclib-org/.github#398): `diff`,
  `review` and `view`, which
  `grep -n 'gh pr ' .github/workflows/claude-review.yml` reads back.
  Spelling the three out in `--allowedTools`, in place of
  `Bash(gh pr:*)`, is what would put that line past the 100 columns
  `yamllint` holds the file to.

- **`claude-review.yml` converges to `btclib-org/.github`'s current
  mechanism** (issue btclib-org/.github#340) (issue
  btclib-org/.github#385). The job carries a job-level
  `CLAUDE_REVIEW_ENABLED` switch, so a review left disabled
  organization-wide skips cleanly instead of a step failing loudly; the
  guard step reads `api_error_status` and `stop_reason` from the SDK's
  own execution file, which the action's log otherwise drops; and the
  verdict is posted as a pull request review of type `COMMENT` — one of
  `ACK <sha>`, `CHANGES REQUESTED <sha>` or `NACK <sha>` — with the
  verification step reading `pulls/<n>/reviews` in place of
  `issues/<n>/comments`. The header keeps this tree's own reasoning
  about `REPOSITORY.md`'s required-checks rule and its own accounting
  of the concurrent-job ceiling.

- **`claude-review.yml`'s `allowed_bots` comment cites the organization
  standard by name for what account produces the ack of record**
  (closes #234), landing with the convergence above: it named
  `REVIEWING.md`, which does not state which account produces one.

- **`CONTRIBUTING.md` no longer says `claude-review` runs beside the
  other gates.** The `CLAUDE_REVIEW_ENABLED` switch the convergence
  above adds is an organization variable that is currently unset, so
  neither of the workflow's jobs runs in this tree at all while it
  stays that way; the sentence claiming otherwise is the same one
  `btclib-org/.github`'s own copy of `CONTRIBUTING.md` corrected in the
  commit that introduced the switch.

- **Every fixable hook now fixes, and this file's lint derogation is
  gone**, closing issue #249. `codespell` gains `--write-changes`, next
  to `markdownlint-cli2` and `typos`, which already fixed in place.
  With `markdownlint-cli2` repairing a joined file rather than only
  reporting it, `CHANGELOG.md`'s two-comment directive disabling MD022
  and MD032 has nothing left to guard: a rebase that drops the blank
  line between two joined `###` sections is now the hook's own repair
  on its next run, so the directive is gone and both rules apply to
  this file again. `codespell --write-changes` over the whole tree
  rewrote nothing, which is the measurement behind turning the flag on.

- **`ignore` names no half of a pair `convention = "pep257"` settles**
  (btclib-org/.github#178). Under a declared convention ruff disables
  `incorrect-blank-line-before-class` (D203) and
  `multi-line-summary-second-line` (D213) whether or not `ignore` names
  them, so an entry for either reads as an enforced choice and decides
  nothing. Measured with the ruff `uv.lock` pins, over a tree carrying a
  module written to violate both: `ruff check --no-cache .` answers
  `All checks passed!` with the entries and without them, and ruff's
  incompatible-pair warning appears only where the convention itself is
  taken out. Section 5 of the standard is the rule, and it now sits at
  the key that decides it.

- **`[tool.mypy]` sets no `show_error_codes`** (btclib-org/.github#191).
  mypy has no such option: `Options` carries `hide_error_codes`, `False`
  before any config file is read, and `config_parser.py`'s generic
  `show_`/`hide_` inversion is the whole of why the key parses.
  `mypy --help` under the locked mypy writes `--hide-error-codes` as the
  flag that changes the default and gives `--show-error-codes` as its
  inverse, which is what section 6 of the standard reads as a setting
  mypy has already; the same erroring file reports the same message,
  error code included, with the line and without it.
  `show_column_numbers` stays -- its default is `False`, and section 6's
  sample carries it.

- **`check-sdist` and `pyroma` build with the backend `[build-system]`
  admits** (btclib-org/.github#197). check-sdist's default installer is
  `uv build`, and that is not PEP 517 for this backend: given
  `build-backend = "uv_build"` and a `requires` the running uv satisfies,
  it builds with the copy bundled in whichever uv is importable or on
  `PATH`, so the backend that packed the archive the gate compares against
  git was not one this file declares -- measured with a `requires` whose
  ceiling excludes the running uv, where `uv build` warns that the
  declaration does not contain its own version and builds the sdist
  anyway. `args: [--inject-junk, --installer=pip]` puts check-sdist on
  `python -m build --no-isolation`, which does read the hook environment,
  and `additional_dependencies` names `[build-system]`'s own specifier;
  the hook then fails with `ERROR Missing dependencies` where the two
  disagree, which with the manifest's args it passed. What that does not
  keep is the two specifiers equal: a `requires` widened past the hook's
  line leaves it satisfied and green, the half btclib-org/.github#145
  leaves open. `pyroma` reads the metadata through `build` as well,
  without isolation where the environment satisfies `requires` and falling
  back to an isolated build otherwise -- the environment pre-commit.ci
  cannot create -- and here it was the fallback that ran: in the
  environment that hook had, `build.util.project_wheel_metadata('.',
  isolated=False)` raises `BuildBackendException: Backend 'uv_build' is
  not available.`

- **The question form names the Slack link beside it rather than
  `CONTRIBUTING.md`.** The sentence pointed at `CONTRIBUTING.md`, which
  carries no such link: the channel is a contact link in
  `.github/ISSUE_TEMPLATE/config.yml`, shown to the reader as *Chat with
  the developers* on the page that offers the form
  (btclib-org/.github#101).

- **`REVIEWING.md` says the reviewer runs the whole suite, every time.**
  The organization's copy, shared half byte for byte (section 14): the
  test suite is run whole on the sha under review, never a subset and
  never relied on from the author's run.
- **mypy's optional error codes are the organization's list**, section 6
  of the standard, the same in every repository that runs mypy
  (btclib-org/.github#165). `explicit-override`, `possibly-undefined`,
  `redundant-expr` and `unused-awaitable` join;
  `narrowed-type-not-subtype` goes, the locked mypy enabling it by
  default. What `explicit-override` asked for: `@override` on the test
  doubles, from `typing_extensions`, declared in the `test` group -- and
  a named ignore on the client's own overriding methods, `typing` having
  the decorator from 3.12 while the one-file module holds to a 3.10
  floor and the standard library alone.
- **`REVIEWING.md`'s *The gates are the evidence* excepts no gate from
  the run a reviewer may rely on, the test suite included.** The
  organization's copy, shared half byte for byte (section 14): a run is
  whole whoever makes it — never a module on its own, a `-k`, a `--lf`,
  a deselect or a marker in its place — and one that was narrowed or cut
  short is reported as no run (btclib-org/.github#168).

- **`REVIEWING.md` is the organization's copy.** A review reads the prose
  that stays in the tree, treats a commit message or a pull request's
  body as a finding only where it decides something, and asks a stated
  count, a measurement nothing re-derives, or the history of the code
  told in a comment to go — section 14 of the standard, the shared half
  byte for byte.

- **Every source file opens with `COPYRIGHT`'s three lines, and
  `notice-rgx` is that file transcribed** (btclib-org/.github#119). The
  headers carried the MIT permission notice in full, on the argument
  that the copied-out module has no `LICENSE` beside it; that issue
  decided section 5 states one notice for every tree, the pointer form,
  and that a self-contained one in one tree is a second notice -- the
  third line of `COPYRIGHT` names the URL of the license text, and a
  copy loses `AUTHORS.md` and `pyproject.toml` with the `LICENSE`
  anyway. `git ls-files '*.py'` names every file rewritten, and
  `uvx ruff check --select CPY .` passes on them; `notice-rgx` is byte
  for byte what `tests/copyright_test.py` of `btclib-org/.github`
  derives from `COPYRIGHT`, where before it was the long notice that
  test refused. `CLAUDE.md`, the README's *Vendoring*, the module
  docstring's own vendoring paragraph and `docs/source/conf.py`'s year
  comment each argued the embedded notice and now describe the pointer;
  the entry further down this section saying the headers "still carry
  the MIT permission notice in full" describes the tree between that
  landing and this one.

- **The lint gate runs `pretty-format-json`, `toml-comment-width` and
  `decoded-subprocess-encoding`** (btclib-org/.github#130 and
  btclib-org/.github#134). `pretty-format-json` was left out on the
  claim that every `.json` here was under `tests/_data`, so that an
  exclude would leave it matching nothing; `git ls-files '*.json'` on
  the tree before this answers `.claude/settings.json` as well, and the
  hook now reads that file, with `.vscode/` and `tests/_data/` excluded
  for the two reasons beside it -- `tests/_data/README.md` already said
  the hook was configured to leave that directory alone, and is true
  now. The two local pygrep hooks are section 4's, in the text btclib
  carries: the first holds a toml comment to the 80 columns
  `[tool.ruff.lint.pycodestyle]` already names for every other comment
  in the tree, and every comment in `pyproject.toml` was under it by
  hand; the second refuses `text=True` on a subprocess, and
  `tests/standalone_test.py` passed it once, now `encoding="utf-8"`,
  the same text mode with the decoding named.

- **`[project.urls]` carries the seven links section 3 of
  `btclib-org/.github` names, keyed as the other two published packages
  key them** (btclib-org/.github#133). v2026.8.20 is on the index with
  six -- `Homepage`, `Download`, `Documentation`, `GitHub`, `Issues` and
  `Pull Requests`, as `pypi.org/pypi/bitcoin-core-rpc/json` reports them
  -- and no changelog, which is the one link from a version already
  published back to what changed in it. `GitHub` is `repository`,
  `changelog` points at `RELEASE_NOTES.md` for the reason
  `btclib-secp256k1` gives beside its own, and every key is lowercase
  with an underscore, so that a check reading the set back across the
  three packages keys on one spelling. `docs/source/conf.py` read the
  `GitHub` key for the base of its links to the root files and now reads
  `repository`; the documentation build with `-W` is what would have
  caught the rename without it.

- **`links.yml` accepts every status lychee would accept unasked, and
  stops passing a cache no step keeps** (btclib-org/.github#110 and
  btclib-org/.github#111). `--accept 200,206,429` replaced lychee's
  default range rather than adding to it -- `lychee --help` gives that
  default as `100..=103,200..=299` -- so a host answering `201` or `204`
  was a dead link, to name a `206` the default already covered; the
  argument is now that range with `429` added, a rate limit being an
  answer from a host that is alive. `--cache --max-cache-age 1d` is gone
  with the clause that credited it: on the tree before this,
  `grep -c 'actions/cache\|lycheecache' .github/workflows/links.yml`
  answered `0`, so the file lychee wrote at the end of a run was read by
  no later one, and the comment's "the retries, the timeout and the
  cache are what keep a slow or throttling host from being reported as a
  dead one" named a mechanism that was not there. Dropped rather than made
  true with an `actions/cache` pair, because the issue's own measurement
  is that lychee collapses repeated URLs without it.

- **This file stops asking for the blank line a union merge drops.**
  MD022 and MD032 are off for `CHANGELOG.md` alone, by a comment at its
  head and not by an edit to `.markdownlint.jsonc`, which is section 14's
  verbatim copy: a rebase of two branches that each appended a section
  joins them without the blank line between, and the rule would then fail
  the gate on a file that never conflicted. btclib-org/.github#138 is the
  record, and the comment says when it goes back on.

- **`claude-review.yml` reports red on anything but an ack of this
  head.** The job ended at a step testing whether the action had run at
  all, so a `CHANGES REQUESTED`, a run that posted no comment, and an ack
  naming a sha the branch had moved past each left the check green --
  btclib-org/.github#146 measured that guard and nothing past it in every
  copy of the workflow. The step btclib-org/.github carries at `18e6c64`
  is here now, with its comment: it reads the last verdict `claude[bot]`
  posted on the pull request and fails unless it is an `ACK` whose sha is
  a prefix of the head. Run outside the workflow against this
  repository's own pull requests, with `REPO`, `NUMBER` and `HEAD_SHA` in
  the environment: on PR 222 at its head it prints `the review acked
  18affcac...` and exits 0; with any other head it exits 1 naming both
  shas; on PR 219 and PR 215, where no `claude[bot]` verdict was posted,
  it exits 1 saying so. Still not a required check, and red there gates
  nothing. The two copies differ beyond this step -- the header, the
  checkout comment, `allowed_bots` and the prompt are each this
  repository's -- and those stay as they were.

- **`CODE_OF_CONDUCT.md` is gone, and the inherited copy is what GitHub
  shows.** Section 14 of `btclib-org/.github` no longer lists it and
  section 2 no longer asks for one: the file was a pointer to the PSF
  code of conduct, and the copy in `btclib-org/.github` is displayed for
  a public repository carrying none (btclib-org/.github#123). The entry
  further down this section that calls it one of three verbatim files
  describes the tree between that landing and this one. `test.yml`'s
  `prose` pattern stops naming it, a name nothing matches being a rule
  that has quietly stopped applying. Nothing else linked it: on the tree
  before this, `git grep -n CODE_OF_CONDUCT` answered with that pattern,
  the file itself and this file's earlier entries.

- **`.gitattributes` is the organization's file** (btclib-org/.github#102).
  Section 14 of the standard names it as the same file in every
  repository, and `tests/verbatim_test.py` there compares the copies it
  finds; the difference here was in the comment and never in the two
  `merge=union` lines. It is byte for byte the copy in
  `btclib-org/.github`, on the digest of the raw file the contents
  endpoint serves. This tree has no attribute of its own to keep under
  `## This repository in particular`, so it carries no such heading.
  `git check-attr merge` still answers `union` for both files.

- **`COPYRIGHT` leaves the sdist.** `license-files` here was already
  `["LICENSE", "AUTHORS.md"]`, so the wheel never carried it, and
  `source-include` named it by hand. btclib-org/.github#135 decides that
  every package of the organization ships the same set and the file is
  not in it -- the holder a consumer needs is in `LICENSE`, and
  `COPYRIGHT` is the source of a header rather than a statement to a
  consumer. Measured on `uv build` before and after: the sdist's root
  loses `COPYRIGHT` (and `CODE_OF_CONDUCT.md`, above) and nothing else,
  and the wheel's `dist-info/licenses/` is `AUTHORS.md` and `LICENSE`
  both times. `[tool.check-sdist]` `git-only` gains the name, that hook
  otherwise reporting a tracked file the archive does not carry.

- **The build backend is `uv_build`, and `MANIFEST.in` is gone with the
  include list it was.** btclib-org/.github#118 settles that a
  pure-Python project uses that backend, and `btclib` is where the pin
  comes from: `uv_build>=0.12.5,<0.13`. What the floor has to clear is
  **0.12.0**, where the sdist's own `pyproject.toml` became a normalized
  copy with the verbatim one kept beside it as `pyproject.toml.orig` --
  which this tree's sdist now carries, matching the file in the checkout
  byte for byte. Measured by replacing the specifier with `==<version>`
  and reading the member list, `0.11.31` answers with no `.orig` and
  every `0.12.x` with one, so a floor below `0.12.0` would be a
  different archive rather than an older one and `0.12.5` is not that
  boundary. It sits there because `0.12.5` is the rev
  `.pre-commit-config.yaml` pins for `uv-pre-commit`, which keeps the
  backend no older than the uv whose lock format that hook writes, and
  because it is `btclib`'s floor -- two reasons to hold it rather than
  constraints, which is what makes it the number to lower first. The
  ceiling is the next minor, where uv's versioning policy puts a
  breaking change.

  What `MANIFEST.in` said in include and exclude lines is now the glob
  patterns of `[tool.uv.build-backend]`, beside the rest of the
  configuration. Built both ways and the archives compared:

  ```shell
  uv build --sdist -o dist-before   # on origin/main
  uv build --sdist -o dist-after    # here
  diff <(tar tzf dist-before/*.tar.gz | sed 's|^[^/]*/||' | sort) \
       <(tar tzf dist-after/*.tar.gz  | sed 's|^[^/]*/||' | sort)
  ```

  The only tracked file that leaves is `MANIFEST.in`, which this diff
  deletes. Everything else the command prints is backend metadata or the
  spelling of a directory member: `setup.cfg` and the four files of
  `bitcoin_core_rpc.egg-info/` go, `pyproject.toml.orig` arrives, and
  where setuptools wrote seven directory members, every one with a
  trailing slash in the name, `uv_build` writes six: the root keeps its
  slash, the five nested ones lose it, and `bitcoin_core_rpc.egg-info/`
  is the seventh, gone with the backend that made it. So the listing
  compares `docs/` against `docs`. It does not count them; this does:

  ```shell
  python3 -c 'import sys, tarfile
  print(sum(m.isdir() for m in tarfile.open(sys.argv[1]).getmembers()))' \
      dist/*.tar.gz
  ```

  The wheel answers the same question the other way round: it loses
  `dist-info/top_level.txt`, which is the only file entry the two builds
  differ on, and it gains three directory entries where setuptools wrote
  none — `bitcoin_core_rpc/`, `dist-info/` and `dist-info/licenses/`.
  `py.typed` is among the members it keeps, with no `package-data` entry
  left to name it.

  What the backend reads is the **working directory**, walked through
  those globs, and not git: an untracked file matching one of them is
  packed like any other and moves the digest of the archive built from a
  given commit. `check-sdist` turns that into a red gate rather than a
  shipped archive, `source-exclude` names the caches a linter or a type
  checker is known to leave under `tests/` or `docs/` — btclib shipped a
  nested one whole (btclib-org/btclib#985) — and RELEASING.md's rebuild
  section now carries it as the first of three bounds on what a digest
  comparison proves, with the clean-export command beside it.

- **`check-sdist` replaces `check-manifest` in the lint gate**, asking
  the same question -- what is tracked and not in the sdist, and what is
  in the sdist and not tracked -- against the patterns of
  `[tool.uv.build-backend]` rather than against an include list no
  backend reads any more. It registers a plugin for that backend, so it
  builds with the uv it installs and needs neither `--no-build-isolation`
  nor a `setuptools` additional dependency. `[tool.check-sdist]`
  `git-only` holds what no include pattern adds in the first place, and
  it was read off the tool rather than carried over: with the list
  emptied the hook reports `.gitattributes`, `.gitignore` and the tracked
  files under `.claude/` and `.vscode/`, and nothing else — `.github` is
  on check-sdist's own default ignore list, and `.lycheeignore`, which
  `[tool.check-manifest]` ignored, is not tracked here at all.

- **The sdist normalizer stays, and its reason changes.** It existed
  because setuptools tarred a staging directory whose sub-second `mtime`
  `SOURCE_DATE_EPOCH` did not reach. That backend is gone and the
  nondeterminism with it: `uv_build` ignores `SOURCE_DATE_EPOCH` and
  writes every sdist member at epoch 0, mode 0644 or 0755, owner root
  with no names and no PAX records, the gzip header at 0 and the wheel's
  zip entries at 1980-01-01 -- a build with the variable exported and one
  without give one sha256 per artefact. So the script now runs over an
  sdist already deterministic without it, and it runs for the reason
  btclib's copy of it states: epoch 0 is uv's choice and uv may revisit
  it, while a release rebuilt from its tag has to give the bytes
  `release.yml`'s `attest` job vouched for however many backends later
  that is.

  What it does there is a rewrite and not a check, and the difference is
  the digest this repository publishes: every member's `mtime` goes from
  uv's 0 to `SOURCE_DATE_EPOCH`, which moves the archive.

  ```shell
  uv build --sdist -o dist && shasum -a 256 dist/*.tar.gz
  SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) uv run --no-project \
      --python 3.14 .github/scripts/normalize_sdist.py dist/
  shasum -a 256 dist/*.tar.gz
  ```

  So the step in `test.yml` is what decides the bytes `attest` signs, and
  dropping it would publish others. Its docstring carries that argument
  and the measurement under it, `SOURCE_DATE_EPOCH` stays because the
  script is what reads it, and the mode is rewritten on the same footing
  as the timestamp -- there the line really is a no-op, 0644 and 0755
  being what `uv_build` already writes -- rather than against a umask no
  backend now consults.

- **`claude-review.yml` points at the file that states the ceiling,
  instead of at a measurement taken of something else.** Its header
  promised that "`REPOSITORY.md` measures what a commit at that ceiling
  costs in wall clock". `REPOSITORY.md` does measure a wall clock
  against that ceiling, but one job's and not one commit's -- the
  seconds of a slot a single `Analyze (python)` held -- while what it
  says a *commit* asks for is a count of jobs, which `42e600e`
  superseded. Following it does land on a measurement, which is what
  makes the wrong generality worse than a dangling reference: the reader
  arrives at a number and takes it for the one that was named. The
  ceiling is `CONTRIBUTING.md`'s to state, and `CONTRIBUTING.md` is also
  where what the platform sweeps ask of it is accounted for, so the
  sentence names that file. Restating the number here would be one more
  copy of what the tree already repeats:

  ```shell
  git grep -n 'concurrent jobs' -- '*.yml' '*.md'
  ```

  That form rather than `'twenty concurrent'`, which misses two of them:
  `CONTRIBUTING.md`, where the sentence wraps between the two words, and
  this very workflow, whose header stops repeating the number here. The
  narrower pattern answers with neither the file the ceiling belongs to
  nor the file this entry is about.

- **A bare `uv run pytest` is the coverage gate, and the prose that said
  otherwise is gone.** `CLAUDE.md` carried "`uv run pytest` is not the
  coverage gate" and a longer command to use instead; `--cov` has been
  in `addopts` since it moved there so that the ratchet is what a bare
  run measures, and `pyproject.toml` says as much beside the flag. The
  run answers with `Required test coverage of 100.0% reached`, which is
  the gate. What is true, and is what the moved prose now says, is that
  a *selective* run is reported and not gated:
  `uv run pytest tests/transport_test.py` prints the whole tree's
  coverage and passes, `tests/conftest.py`'s `pytest_configure` being
  what makes the difference.

- **`CLAUDE.md` holds only what no document written for a human can.**
  The commands, the gates and how they lie are `CONTRIBUTING.md`'s last
  section, and the review rules are `REVIEWING.md`: a human had to open
  an agent's file to learn how to run a gate, and an agent's file was
  the second place a review rule was written. What is left is what those
  two cannot say because it is about a session rather than about the
  tree -- what the module is made of, the worktree rule, the model, and
  the failure modes that otherwise cost a session, `cancelled` not being
  `failure` and a draft pull request running nothing among them.

- **`REVIEWING.md` is the organization's file down to the same heading,
  and `.claude/commands/review.md` is its copy of the invocation.** A
  review that means one thing here and another in a sibling is no
  standard, which is section 14's reason for comparing the two halves
  that are meant to agree. What the shared half says is gone from the
  tail: what is under review, what to look for, what a finding contains,
  what becomes of a collateral finding, the gates as evidence, the
  verdict and the re-review. The tail keeps what a review of *this* tree
  checks and a generic one does not -- a dependency or a second module,
  both JSON-RPC dialects, the boundary the layers draw, and whether the
  suite is still hermetic.

  `.claude/commands/review.md` had drifted into naming this tree's
  facts, which is not what a verbatim file can carry: those facts are in
  the tail above, and the command is the invocation again.

- **`CONTRIBUTING.md` is the organization's file down to `## This
  repository in particular`.** Section 14 of `btclib-org/.github` has it
  verbatim to that heading and this tree's below it, and
  `tests/verbatim_test.py` there compares the halves that are meant to
  agree. What the shared half already says is gone from here rather than
  said twice in this repository's words: where an issue is filed, the
  prose style, what a pull request is and answers, one subject per pull
  request, how a review is exchanged and how a change lands. Each of
  those now points at the section of the standard that decides it.

  What stayed is what only this tree can say: the constraint that this
  is one source file with nothing but the standard library behind it,
  the commands that build the environment and run the gates, the editor
  files, the command each CI job runs verbatim, the cadence table, the
  mutation session, the live node and the secrets baseline. The gates
  moved here from `CLAUDE.md`, a human having no reason to open an
  agent's file to learn how to run one, and `REVIEWING.md` reads which
  checks are required from this file's last section.

  The toolchain badges move under that heading with them, the shared
  half being byte-compared and a badge line being this repository's.
  `.gitattributes` pointed here for the union-merge reasoning and now
  points at section 9, which is where it went; `docs/source/conf.py`
  named `CONTRIBUTING.md`'s links to `CODE_OF_CONDUCT.md` and
  `RELEASING.md` as the reason the root files are not copied into the
  documentation tree, and names `README.md`'s link to `LICENSE`
  instead, that being the one such link left.

- **`.yamllint.yaml` is the organization's copy, byte for byte.** It is
  one of the files section 14 of `btclib-org/.github` calls verbatim,
  and the copy there has moved: `document-start` is raised from the
  default set's warning to `error`, the pre-commit hook running plain
  `yamllint` with no `--strict`, where a warning exits 0 -- so at the
  inherited level the rule reported the convention and gated nothing. It
  costs this tree nothing today:

  ```shell
  git ls-files '*.yml' '*.yaml' \
      | xargs -I{} sh -c 'head -1 {} | grep -q "^---" || echo {}'
  ```

  answers with nothing here. The hook's own comment no longer lists what
  the file departs from the default set in, that list being one more
  thing to keep in step with the file itself.

- **`AUTHORS.md` names this repository's authors.** It pointed at this
  repository's contributor graph while calling them btclib's, which is
  the shape section 14 of `btclib-org/.github` gives for why the file
  cannot be verbatim: a shared pointer is accurate only while one graph
  stays a superset of the others, and the first person to contribute
  somewhere else goes uncredited in silence.

- **`LICENSE`, `COPYRIGHT` and `CODE_OF_CONDUCT.md` are the
  organization's copies, byte for byte.** Section 14 of
  `btclib-org/.github` calls the three verbatim, and
  `tests/verbatim_test.py` there compares them across the repositories,
  so a copy that reads better here is a copy that fails everywhere.
  `LICENSE` gains the `MIT License` title and loses the `2017-2026`
  range -- a range is a line nobody updates, and `COPYRIGHT` states the
  holder without one, so the two disagree the first January nobody
  remembers. `CODE_OF_CONDUCT.md` is the file GitHub falls back to for a
  repository of the organization carrying none, which is why a
  repository that carries one carries that one.

  `COPYRIGHT` is now the three-line notice the other trees point at, and
  the headers here still carry the MIT permission notice in full: what
  the ruff `CPY` rule requires of a source file is `notice-rgx` in
  `pyproject.toml` and never this file, and the argument for the long
  form -- a vendored copy has no `LICENSE` beside it to point at -- is
  about `bitcoin_core_rpc.py`, which is copied, and not about
  `COPYRIGHT`, which is not. That comment says so where the rule is, and
  names the section it departs from.

- **A workflow's file name says its own subject, and a shared prefix
  groups a family.** `ubuntu.yml`, `macos.yml` and `windows.yml` are now
  `os-ubuntu.yml`, `os-macos.yml` and `os-windows.yml`: the platform
  sweep is a family, and the prefix is what says so in a directory
  listing that is read alphabetically. `latest.yml` is
  `deps-latest.yml`, `latest` having named an adjective without the noun
  it qualified -- what that workflow moves is the dependency resolution,
  the `os-*` sweep being the one that holds it at the lock.
  `published.yml` is `pypi-install.yml`, which says what it asks of the
  published package rather than that there is one: it installs it from
  the index and round-trips a call through it. `integration.yml` is
  `integration-bitcoind.yml`, integration naming neither of the two sides it
  joins, where the other side is a live node the workflow downloads and starts.

  **No job name moved**, and that is the constraint the renames were
  written under: a job name is the context a required status check
  carries, and `integration: every job passed` is one of them, so
  renaming it would drop a check and add another under a rule that
  blocks every open pull request in between -- REPOSITORY.md's *Required
  checks on main* has the cost in full. Each workflow's `name:` key
  and its concurrency group follow its file, the group being a literal
  this repository writes for itself rather than a name anything else
  reads.

  **What the rename leaves owed is a row apiece in section 10's
  calendar.** That table gives a workflow a day and an hour under its
  file stem, `tests/grid_test.py` of `btclib-org/.github` reads it
  against the trees, and a stem it does not name is reported as a cron
  on no calendar. No cron moved -- this repository's minute is `12` and
  each still lands on the slot its old name held -- so what is owed is
  the table, in the repository that holds it:

  ```shell
  grep -l 'cron:' .github/workflows/*.yml
  ```

  against section 10's workflow table. The rows this repository leaves
  behind stay answered by btclib, whose `.github/workflows` still
  schedules every one of the old names, so none of them is left dangling
  by this.

- **A `TODO` that opens a comment no longer passes lint**
  (btclib-org/.github#87). Ruff's `FIX` family joins
  `[tool.ruff.lint] select`, so a comment beginning `TODO`, `FIXME`,
  `XXX` or `HACK` is a finding, on its own line or after code.
  Unfinished work belongs in an issue, where whoever might do it can see
  it and where it can be closed; a marker in the tree is visible only to
  somebody already reading that file, and it outlives the branch that put
  it there without anyone noticing.

  What the rule does not reach is worth knowing before trusting it: a
  marker further into a comment, one inside a docstring or a string
  literal, and any file that is not Python. It cost nothing to adopt --
  the tree measures zero findings under it, so this is a ratchet on
  something already true rather than a cleanup, and no code changed.

- **The gate runs one image and one interpreter, and the sweeps moved to
  the calendar** (btclib-org/.github#85). `test.yml`'s `suite` job is
  gone: three images by seven interpreters, minus one cell, asked before
  every review on an organization whose plan gives it twenty concurrent
  jobs across every repository. Measured on one run of the workflow
  carrying it, 24 jobs did 5.8 minutes of work and spent 36.5 minutes
  queueing. What waits for a review is `ubuntu-latest` on the version
  `.python-version` names, and the images that left are `ubuntu.yml`,
  `macos.yml` and `windows.yml` — the last renamed from
  `windows-arm.yml`, which had stopped naming what it runs the day
  `windows-latest` joined it.

  Each of those runs its matrix whole, the cell the gate already covers
  included. A sweep that subtracted the gate would be a matrix with a
  hole in it, and whoever asked what ran would have to re-derive the hole
  from another file.

  `integration.yml` gains the same shape and a `versions` job to give it
  one: the compatibility boundary — the last Core major that has never
  heard of the `"jsonrpc": "2.0"` marker, and the newest — before a
  merge, every supported major on the schedule. Its chain cells go from
  four to five, `regtest` having been left out on the grounds that the
  protocol cells start one in passing; a matrix row that reads as itself
  outlives the comment explaining where the fifth went.

  Every schedule here is on the organization's grid, which gives a
  workflow its day and its hour and this repository its minute. Seven
  crons moved; `published.yml` goes from monthly to weekly with the rest.
  The grid is section 10 of `btclib-org/.github`, which is why the
  cadence table in CONTRIBUTING.md no longer names a day: one calendar
  covering six repositories is one thing to remember, and six copies of
  it are six things to keep true.

- **The interpreters this package claims are the ones it runs on**
  (btclib-org/.github#83). `requires-python`, the per-version
  `Programming Language :: Python ::` classifiers and the interpreter
  list the workflows run are one fact written three times, and nothing
  compared them. `tests/interpreters_test.py` does: the floor is the
  lowest classifier, the classified set and that list's CPython set are
  each other, and the PyPy classifier is present exactly when a PyPy
  interpreter runs.

  The drift it catches misleads somebody who is not reading this
  repository — PyPI shows a classifier to whoever is choosing the
  package, so a version left behind when a floor moves is an interpreter
  advertised and never touched.

  It does not encode the calendar. The organization standard's rule is
  that a library covers every Python still in support, which moves twice
  around each October; python.org keeps that schedule, and a date written
  here would be one more thing to move. The claim held is the weaker and
  checkable one: whatever the three say, they say the same thing.

- **Which of section 7's conventions this suite tests is declared, and a
  test says the declaration is true** (btclib-org/.github#32). A new
  `tests/README.md` names each convention the organization standard lists
  that this repository tests and the module that tests it, then names the
  ones it does not.

  Both of the ones it does test are answered by `standalone_test.py`,
  which is the shape section 7 has in mind where it says what must not be
  aligned is
  *where* these live. This package is one file, so what elsewhere needs a
  walk over a tree is here a property of that file, and stronger for it:
  the documentation is every name of `__all__` carrying a docstring
  `automodule` will render, against `docs/source/api.rst`'s claim to list
  the whole public surface; the import graph is the source importing
  nothing outside the standard library, and a copy of it running under
  `python -I -S`.

  Among those it does not, two are near misses the file names so that
  "absent" is not read as "overlooked". `__all__` is declared and read,
  but to ask whether each name is documented rather than whether the
  module's public names are all in it — section 7 asks for a census that
  fails when a new public name appears, and nothing here fails. Two tests
  assert a keyword-only signature, each about one function, where section
  7 asks for it as a rule over the package.

  `tests/conventions_test.py` is what keeps the declaration from being
  prose, and its assertions were checked by making the declaration wrong
  and watching the suite go red.

- **A Dependabot pull request can be reviewed** (btclib-org/.github#77).
  `claude-review.yml`'s review job failed on #207, the first Dependabot
  pull request opened since the credential guard landed, and it failed
  twice for two different reasons. The first was the credential: a
  `pull_request` run whose actor is `dependabot[bot]` reads from GitHub's
  Dependabot secret store rather than from Actions secrets, and that
  store was empty, so the guard fired exactly as designed. The second is
  this change: the action refuses a run a bot initiated unless the bot is
  named — "Workflow initiated by non-human actor".

  `allowed_bots: "dependabot[bot]"`, named rather than `*`: the input's
  own description warns that on a public repository `*` lets an external
  App invoke the action with a prompt it controls. The mention job takes
  no such input, what triggers it being somebody writing `@claude`.

  Without this a Dependabot pull request is the one class that can never
  carry the ack of record `REVIEWING.md` requires, which is the class
  whose whole value is landing promptly.

- **The sibling repository is named `btclib-secp256k1`** in the seven
  places here that named it otherwise, under either spelling.
  Hyphenated, in `.markdownlint.jsonc`, `.github/dependabot.yml` and
  `RELEASING.md` twice; with an underscore, in `README.md`,
  `CONTRIBUTING.md` and `CHANGELOG.md`, where what is named is the
  sibling that "carries the same three lines" of badges and "the same
  CONTRIBUTING.md run" — which a repository does and a distribution does
  not. `grep -rn libsecp256k1` over the tree is what says whether any is
  left.

  `.markdownlint.jsonc` is the one that reaches past this repository:
  §14 of the organization standard holds that file identical in every
  repository, and `shasum` over the five copies is what says whether it
  does. With this one it is four of five, `btclib-node` being the last.

- **A markdown line does not end inside a word**
  (btclib-org/.github#71). Markdown joins two source lines with a space,
  so a word wrapped at its own hyphen renders with the hyphen and then a
  space inside it -- "read-any-" and "number-of-times" on consecutive
  lines come out as "read-any- number-of-times". The source looks
  correct, which is why reading a diff does not find one, and nothing
  here read the output: markdownlint has no rule for it, the width rules
  read a line rather than what two lines become, and `sphinx-build -W`
  is not asked whether a token means anything.

  A `pygrep` hook, for the reason `local-link-prefix` beside it is one:
  nothing off the shelf does it and the pattern is one line. The rule
  and what the hook cannot see -- a code span whose content breaks at a
  `/` or a `.` renders the same way and has no hyphen to match -- are in
  section 4 of the organization standard, which the comment points at
  rather than restates. This tree was already clean under it, so the
  hook costs nothing today and exists to keep the next one from being
  written.

- **`claude-review.yml` stops counting the required checks**
  (btclib-org/.github#22). "The four required checks stay what they are"
  is a count, and a count in a workflow comment is checked by nothing:
  `actionlint` reads the workflow, `zizmor` reads it for injection, and
  prose beside them reads as authoritative for sitting there. It happens
  to be right here and is wrong in two sibling repositories, which is
  the same sentence in the same file -- the shape that made it worth
  removing rather than confirming.

  What the paragraph is for survives without the number: this job is not
  a required check and must not become one, a model's judgement not
  being a branch rule. Which contexts are required is `REPOSITORY.md`'s
  to record and the endpoint's to answer, and the comment now says so.
  Found by the workflow-comment sweep that issue asks for.

- **`release.yml`'s `concurrency:` comment stops counting the workflows
  it calls** (issue #175). "this one calls three" was true when it was
  written -- `git log -S 'this one calls three'` finds the one commit,
  and `release.yml` called `test`, `lint` and `docs` at that point. Four
  more were added under it since, `macos`, `windows-arm`, `integration`
  and `published`, none of them revisiting a comment far enough above to
  be off the screen -- the nearest of those four `uses:` lines is
  hundreds of lines below it, which is the distance that made the
  sentence safe to leave alone.

  The count carried nothing the reader needed. What the comment is for
  is why the group is named literally -- `github.workflow` inside a
  called workflow is the *caller's* name, so every one of those calls
  would otherwise share this workflow's group -- and that argument is
  the same whether the number is three or seven. It now says "several"
  and gives the `grep` that answers it in the tree that is asking, which
  is what stays true the next time one is added.

- **The yamllint hook's comment says what the hook reads**
  (btclib-org/.github#68). The change that turned the default rule set
  back on renamed the hook and left the paragraph above it describing a
  width check -- "the two rules enabled and the two left off", which was
  true of the `.yamllint.yaml` that change replaced. That is the same
  defect the change existed to fix, one file over: a comment naming a
  narrower scope than what runs, with nothing to notice. Caught by the
  review of the sibling change in `btclib-benchmarks#148`, after this
  repository's had already landed. The paragraph now says what nothing
  else here reads -- width being the half a sibling gate could in
  principle have covered, where a key written twice or a block indented
  under nothing is read by no other hook at all.

- **`.yamllint.yaml` turns the default rule set back on**
  (btclib-org/.github#68). The file listed `line-length` and
  `document-start` under `rules:` and extended nothing, and yamllint
  enables no rule a configuration does not name -- so those two were the
  only rules that had ever run here. Indentation, trailing whitespace,
  duplicate keys, colon spacing and the rest of the default set were
  off, while the file's own comment named `comments` and `truthy` as the
  exceptions and read as though the rest were on.

  Three things kept it out of sight, and each generalizes past this
  file: the comment said otherwise; the gate stayed green, because
  removing a check cannot make a conformant tree fail; and the file is
  shared byte-for-byte, so the defect travelled by being copied rather
  than by being written twice. `extends: default` is back, and the two
  exceptions are named under `rules:` as explicit `disable`s where a
  reader sees them instead of inferring them from what is missing.

  The hook's own name follows it: "yamllint (line width and document
  start)" was an accurate description of a defect, and is now "yamllint
  (the default rule set, less two)".

  It costs this tree nothing: `git ls-files '*.yml' '*.yaml' | xargs
  uvx yamllint` reports the same nothing before and after. That is a
  fact about how the yaml here is written, not an argument for having
  left the set off -- what a rule is worth is what it catches the day
  somebody writes the line.

- **`.taplo.toml` stops carrying one tree's furniture**
  (btclib-org/.github#40). The file is shared byte-for-byte across the
  organization's repositories, deliberately, and this copy justified its
  two settings by naming things that are one tree's: `reorder_keys`
  because "`[project]` reads top to bottom, and the ruff rule sets are
  grouped by what they cover", the indent because "the arrays in
  `pyproject.toml` already use" it. Both readings are true here and
  neither is the reason -- the reason is that a table's order is an
  argument rather than an accident, and that one indent across every
  toml in the organization is the point of having a formatter. A shared
  file arguing from local furniture is a file the next repository
  inherits an untrue sentence with.

  It is now byte-identical to the copy `btclib` and `btclib-benchmarks`
  already carry, which argues from the rule and says outright that it is
  shared and that nothing in it may be true of one tree only. Neither
  setting moves: `indent_string` is the same four spaces and
  `array_auto_collapse` the same `false`, which the formatter leaving
  every toml here untouched is what shows.

- **`docs/source/conf.py`'s reason for not copying the root files names
  the links this `CONTRIBUTING.md` has** (issue #188). The paragraph
  rejecting a build-time copy said the file "links to CODE_OF_CONDUCT.md
  and tests/\_data/README.md". It does not link the second and never
  did: `git log -S 'tests/_data/README.md' -- docs/source/conf.py`
  returns the commit that opened this repository, and `CONTRIBUTING.md`
  at that commit named `CODE_OF_CONDUCT.md` and nothing else outside the
  documentation. The sentence is `btclib`'s, where it is true — that
  tree's `CONTRIBUTING.md` does link `./tests/README.md` — carried over
  with the path bent to a file this tree happens to have. It is the
  shape `.yamllint.yaml`'s survey had: a claim that reads as measured
  because it was, somewhere else.

  The conclusion never depended on it. One destination outside the
  documentation is enough to reject copying, and there are two here as
  the sentence always said: `CODE_OF_CONDUCT.md`, and `RELEASING.md`,
  which `CONTRIBUTING.md` links and no shim in `docs/source/` includes.
  The comment now names that second one, and says what decides the
  question — whether a shim includes the file — so the next reader
  checks the thing that settles it rather than a list. What the wrong
  name cost was never a build: it was a reader running the check the
  comment invites, watching it fail, and having no way to tell whether
  the decision rested on a misreading or the tree had moved under a
  decision that was right.

- **CONTRIBUTING.md sends a contributor to the organization standard**
  (btclib-org/.github#52). `README.md` in `btclib-org/.github` states
  the toolchain, the lint gate, the workflow set and the branch rules
  once for this repository and its siblings, and it claims to be linked
  from each repository's CONTRIBUTING.md. Nothing here named it. Every
  mention of that repository in this tree cited an issue filed there,
  to justify the rule that issue records; not one of them told a reader
  the document itself exists. A sibling repository has one mention that
  is a link rather than a citation, into a subsection of the standard to
  justify a setting, and it makes no difference to this: a destination
  reached only by somebody already reading the paragraph that carries it
  is not a signpost either.
  `git grep -n 'btclib-org/\.github'` is what re-derives them, a list
  here going stale the next time one is written. So a contributor
  following CONTRIBUTING.md to REPOSITORY.md to CLAUDE.md was never
  told a document above them existed — and a rule stated only there was
  one they could not find. The pointer is in the opening rather than in
  REPOSITORY.md or CLAUDE.md: the audit and the normalizing checklist
  that standard carries are performed *holding* it, so the reader who
  arrives without it is the contributor, and this is the file that
  reader is already in — and the one of the three the documentation
  build renders, `docs/source/contributing_link.md` including it. Hence
  the absolute github.com url, the shape a sibling repository is linked
  with elsewhere here: a relative destination resolves against the
  rendered site.
- **RELEASING.md records why no SBOM is attached to this
  repository's releases.** This repository declares
  `dependencies = []` (`pyproject.toml:62`), and `published.yml`
  already asserts that against the installed package on every run
  (`assert not requires(name)`, monthly and on dispatch). btclib's
  RELEASING.md carries the reasoning for why that makes a bill of
  materials here redundant with what CI already checks directly,
  in its "Read the bill of materials attached to the release"
  step; see that and btclib-org/btclib#1159 for the evaluation.

- **That step names the trigger it shares with its siblings**
  (btclib-org/.github#24). `dependencies = []` is this repository's own
  premise, and the sentence already said what would unseat it; what it
  did not say is that the decision rests on a second premise it holds in
  common with the siblings — btclib's generator builds its `components`
  from `Requires-Dist`, so a generator that learned to describe a
  component that metadata cannot express would reopen the question
  everywhere the decision is recorded, here included. The step now names
  that second trigger and the open issue watching it, where
  btclib-org/btclib#1159, cited beside it for the evaluation, watches
  nothing.

- **The Slack badge is gone from README.md and CONTRIBUTING.md.** The
  badge block's own comment states the criterion — a badge reports state,
  which is why "we use ruff" is not one — and this badge reported a
  route, to a channel of the course workspace the sibling library was
  first taught in. What answers a question here is the issue tracker and
  a pull request, which leave the answer where the next reader of these
  files can find it. This repository carried the badge alone, with no
  bullet sending a contributor there, so the block loses a line and
  nothing else changes. btclib does the same in its own pull request,
  and the organization profile no longer names Slack either.

- **`check-wheel-contents` gains a `package` configuration**, closing
  btclib-org/btclib#1160's divergence for this repository: the two other
  publishing repositories in this organization each carry a form of a
  wheel-contents check the third lacked. `btclib` has a hand-written
  script comparing the built wheel and sdist member for member against
  an allowlist; `btclib-secp256k1` configures `check-wheel-contents`
  with `ignore` entries for the members its compiled wheels carry that
  a pure-Python one does not. This repository ran `check-wheel-contents`
  with no configuration at all. The comment above
  `[tool.check-wheel-contents]` in `pyproject.toml` has what changed,
  the measurement behind it, and why no script was ported from either
  sibling — one place for that reasoning, pointed at rather than
  repeated here.
- **`test.yml`'s and `lint.yml`'s concurrency groups take a
  `concurrency-suffix` input, and `release.yml` passes `-release` at both
  call sites**, part of btclib-org/btclib#1158 (the issue lives in
  `btclib`; this repository was already right about the other half of
  it). `release.yml` calls both workflows, and inside a called workflow
  `github.ref` is the ref of the release run itself: a `workflow_dispatch`
  rehearsal from `main`
  computes `refs/heads/main`, the same group a push to `main` holds,
  with `cancel-in-progress: true`, so one cancelled the other. Not
  exercised directly here — reproducing it costs an actual rehearsal
  race — but `btclib-secp256k1` had already fixed it with the same
  mechanism this copies, and this repository's own concurrency key
  (`github.event.pull_request.number || github.ref`) already carried the
  other half of the issue's fix, so this pull request changes only the
  suffix. `CLAUDE.md` is corrected in the same pull request: it still
  named the pre-#1152 `test-${{ github.ref }}` form; the actual group
  had already moved on.

- **`release.yml`'s `github-release` job gains an explicit `if`**,
  closing issue #149: `always() && needs.publish-pypi.result ==
  'success' && needs.attest.result == 'success'`. Without it the job was
  skipped on every tag since `attest` entered its `needs` — v2026.8.12,
  v2026.8.13 and v2026.8.20 each published to PyPI and cut no release,
  and each was recreated by hand from the run's own `dist` and
  `attestation` artifacts. The cause is not a failure anywhere in the
  run, which is what it looked like: `attest` needs `publish-testpypi`,
  a tag push skips that job, and a job standing behind a skipped
  ancestor is skipped whatever its own needs report, unless its own
  condition begins with `always()` — an opt-out that holds for the job
  saying it and not for whoever needs that job. The two `.result` checks
  without `always()` are the fix that is not one, measured on
  btclib-secp256k1's v0.8.0.2 (btclib-secp256k1#141, then #151); the
  condition here is that repository's, which cut v0.8.0.3 and v0.8.0.4
  from the workflow. It keeps the property the absent `if` was relied on
  for: a `workflow_dispatch` rehearsal skips `publish-pypi`, so the
  condition is false and no release is cut. RELEASING.md's
  troubleshooting entry for the symptom names the cause instead of
  owing a report to GitHub support, and its post-release check now asks
  `gh release view` for the release's `author` — `github-actions` is the
  workflow having cut it.
- **`RELEASING.md` gains an explicit decision point for a dependency's
  drift, and the actual command that lands a release pull request
  here**, both findings from cutting btclib-secp256k1's 0.8.0.4
  (btclib-secp256k1#288, #289, #290): whether to act on `uv lock
  --upgrade`'s drift or leave it belongs in the release pull request
  rather than defaulting by omission, and `gh pr merge --squash` alone
  refuses that same pull request client-side on a solo-maintainer
  repository — `--admin` clears it, measured on btclib's #1111, #1113,
  #1114 and #1133, naming the release commit's title and body
  explicitly rather than leaving them to this repository's
  `COMMIT_MESSAGES` squash default.
- **RELEASING.md, REPOSITORY.md, CONTRIBUTING.md and README.md stop
  stating counts nothing checks** (#150), the prose rule CONTRIBUTING.md
  already carried but 22 places in these four files hadn't caught up
  with: an unguarded number restating a job count, a
  permission count or a structural claim, removed or replaced by naming
  the things directly, so two files describing the same fact can't say
  it two different ways. One of the 22 was already wrong rather than
  merely fragile: CONTRIBUTING.md's workflow table read `integration`'s
  matrix as "2 Core versions, 4 chains", which next to the `N platforms
  × M interpreters` rows around it reads as a cross product, 8;
  `integration.yml`'s actual matrix is 6 — two `protocol` cells plus
  four `chain` cells, additive — matching what REPOSITORY.md's own "six
  matrix cells" already said correctly. `N platforms × M interpreters`
  table rows are otherwise left untouched, and GitHub's platform-limit
  numbers stay as the dated historical constants they already were.
- **RELEASING.md's environment step named the wrong holders of
  `id-token: write`** (#161): "`publish-pypi` and `publish-testpypi` are
  the only holders" was false, `attest` declaring it too for its own
  Sigstore exchange, which REPOSITORY.md's "Token permissions" section
  already got right. Fixed to name `attest` and explain why the gate
  still covers it: `attest` only runs via `needs: [publish-pypi,
  publish-testpypi]`, after one of the two reviewed jobs has already
  succeeded, so nothing bypasses the environment review the sentence
  was arguing for.
- **A `tag-integrity` ruleset now enforces the other half of issue
  #139**, requiring `required_signatures` on `refs/tags/v*`, with no
  bypass actor. RELEASING.md's tagging step already produces a signed
  tag by default (v2026.8.20's `git tag -s` change), so nothing about
  the release procedure changes; what the ruleset adds is that an
  unsigned `v*` tag is now refused outright rather than merely
  undocumented. It carries no `deletion` or `non_fast_forward` rule on
  purpose: RELEASING.md's own recovery path deletes and re-tags a
  release that failed before `publish-pypi`, and either rule would
  block that. Existing tags are unaffected — the ruleset applies to
  pushes going forward, not retroactively — closing the issue now that
  both options it named are done. REPOSITORY.md records it under a new
  "Tag protection" section.
- **`test.yml` gains a `changes` job**, the cheapest one in the workflow
  and the one that decides whether the rest of it runs at all: a pull
  request that edits only prose — `CHANGELOG.md`, `RELEASING.md`, the
  rest of the root's own documentation, `.github`'s markdown, the
  mutation configuration, the detect-secrets baseline — changes nothing
  the matrix reads, and was spending the whole matrix to prove it.
  `suite`, `coverage` and `dist` each skip when it answers nothing to
  check, and `test-passed` still fails if it answers wrong: a failure in
  `changes` shows up in `test-passed`'s own results directly rather than
  being read as everything downstream correctly declining nothing to do.
  `README.md` is deliberately not on the prose list — the `dist` job's
  `twine` and `pyroma` steps check it, so an edit to it is a change the
  matrix can fail on. Mirrors btclib-secp256k1's own `changes` job
  (#189), closing issue #145: `release.yml`'s `test:` job — the one
  calling `test.yml` with `uses:` — now grants `pull-requests: read`
  alongside `contents: read` explicitly, a called workflow's jobs being
  capped at what the caller grants rather than at what the callee's own
  top-level `permissions:` declares. Left ungranted, the `changes` job's
  static declaration alone would refuse the whole release run before a
  single job started, the way it did in btclib-secp256k1's
  `v0.8.0.3` (btclib-secp256k1#281) — even though `changes` never
  actually reads a file list on that path, answering `code=true`
  unconditionally off anything that is not a `pull_request` event, the
  check GitHub runs at startup being against what the job *declares*
  rather than against what it goes on to do.
- **`version-check` now asks where the tag is**, closing issue #153:
  `release.yml`'s `Checkout code` step in that job gains `fetch-depth:
  0`, and a new step reads `git merge-base --is-ancestor` against
  `origin/<default branch>` before anything is built. The three checks
  already there ask whether the version is right; none of them asked
  whether the commit carrying it is reachable from the branch a release
  is supposed to ship — a tag pushed from a stale worktree, a branch
  whose pull request is still open, or a commit squashed away on its
  way into `main` would otherwise publish a tree no review approved,
  and PyPI accepts no file name twice, even after a yank. Ported from
  btclib's own form of the check rather than btclib-secp256k1's: btclib
  verifies `origin/<default branch>` is present first and fails with
  the reason — `origin/<default branch> is not in this checkout` —
  where btclib-secp256k1's bare `git merge-base --is-ancestor` would
  fail with `Not a valid object name`, correct but silent about why.
  The placeholder-tag guard btclib carries beside this check is not
  ported: this repository's `Check that the tag matches the declared
  version` step already refuses a two-component tag.
- **The `build` dependency-group is renamed `check`** (issue #156):
  it held `check-manifest`, `check-wheel-contents`, `pyroma` and
  `twine`, the tools that inspect a distribution, not the ones that
  build it, and `--only-group build` installed the opposite set of
  packages in btclib-secp256k1, which already has both a `build` group
  for building wheels and a `check` group for inspecting them. A step
  copied between these trees — repository btclib's issue #1154 is
  about to do more of that copying — installed the wrong four packages
  under the old name. `pyproject.toml`, its `dev` group's reference,
  `uv.lock`, `CONTRIBUTING.md` and every `--only-group build` call
  site in `test.yml`, `latest.yml` and `release.yml` move to `check`;
  nothing in btclib-secp256k1 changes, and the analogous rename in
  btclib is tracked separately, as repository btclib's issue #1155.
  The rename's actual return: `--only-group build` here now fails —
  `` Group `build` is not defined in the project's `dependency-groups`
  table `` — instead of quietly installing the wrong four packages, so
  a step copied in by mistake stops rather than runs.
- **`[tool.uv]`'s `required-version` floor was above what Dependabot's
  own updater can satisfy** (#159), and not merely a wrong comment: the
  updater in `dependabot/dependabot-core` runs `uv lock` with the uv it
  bundles (`uv/Dockerfile`'s `FROM ghcr.io/astral-sh/uv:...`, `0.12.1`
  at the time of writing) and refuses instead of upgrading itself when
  this key asks for more, turning every uv-ecosystem update it
  attempted, security ones included, into a silent no-op rather than a
  pull request — this repository's `.github/dependabot.yml` has run the
  `uv` ecosystem weekly since its first commit and produced none, while
  `ruff` and `mypy` sat one point release behind both sibling
  repositories on packages all three share. `>=0.12.3` was the floor
  doing this; `>=0.11.31` replaces it, matching repository btclib's
  issue #485, the same failure caught there first, and its own
  `required-version`. Read, not assumed: `uv lock --check` under uv
  0.11.31 resolves this repository's existing lock (schema revision 3)
  without complaint, so the floor drops with no re-lock needed. The
  comment above the key is rewritten to name the actual ceiling — a
  number nobody in this repository controls, that moves only when a
  human bumps that Dockerfile — in place of the uv-lock pre-commit
  hook's `rev`, which was never it: that rev moves on pre-commit.ci's
  own schedule and happened to read close to the old floor by
  coincidence.
- **`release.yml` gains a `documented` job**, closing issue #154: on a
  tag push it polls `https://bitcoin-core-rpc.readthedocs.io/en/<tag>/`
  at a fixed interval, and fails the run if that URL is never
  served. Read the Docs activates and builds a release tag from an
  automation rule of its own, and a build that never starts fails
  nothing else in the pipeline — a site answering 200 keeps serving the
  last build that succeeded for as long as it takes somebody to notice,
  which is the failure mode btclib's own RELEASING.md records in its
  aggravated form: a webhook refusing every delivery with a 400 for
  three years while the site kept answering 200. The job asks the
  rendered URL rather than the v3 API: Read the Docs throttles an
  unauthenticated caller and blocks cloud-provider addresses without a
  token, so asking the API from a runner would mean storing a
  credential for a check that gates nothing, where `/en/<tag>/` is
  CDN-served, 404s for a version with no successful build, and is the
  URL a reader follows anyway. It runs after `version-check` and
  nothing depends on it: a late documentation build is not a reason to
  withhold a wheel, and the fix for a red run here is a build on Read
  the Docs' side, never a moved tag. Landed after issue #149's
  `github-release` fix, deliberately, so that a job able to fail the
  run could not import a new way to lose the GitHub release before that
  fix existed. Ported from btclib's own `documented` job in
  `release.yml`; `release.yml` cannot run on a pull request, so the
  polling loop was run verbatim from the shell against a tag Read the
  Docs did build (v2026.8.20, served) and one it did not (v2026.8.12,
  404) before landing, rather than trusted on the strength of the diff
  alone.
- **A re-run of a finished TestPyPI rehearsal now gets a version of its
  own**, closing issue #157: the suffix was `.dev<run number>`, and a
  re-run keeps `github.run_number` and only raises `github.run_attempt`,
  so re-running a rehearsal rebuilt the same version and TestPyPI
  refused the upload. RELEASING.md's answer had been a warning to
  dispatch a fresh run instead of re-running one — a rule to remember at
  the moment a failed rehearsal is least likely to leave room for it.
  Fixed the way btclib-secp256k1's `release.yml` already was
  (repository btclib-secp256k1's issue #32, PR #58): the suffix is
  `.dev<run*100+attempt>`, the multiplier keeping every attempt of every
  run both unique and ordered — attempt 2 of run 7 still sorts after
  every attempt of run 6 — and the step refuses outright past the two
  digits it reserves for the attempt rather than wrapping into another
  run's range. RELEASING.md's warning goes with it, the rule it stated
  no longer being true.
- **`release.yml`'s `build` job now runs `twine check --strict`,
  `check-wheel-contents` and `pyroma --min 10` on the files it is about
  to publish** (issue #155). Those three already gated every pull
  request, in `test.yml`'s `dist` job, but `build` rebuilds the
  distribution files from the same tree rather than reusing `dist`'s
  artifact, and ran none of the three on its own copy — so a tag that
  passed every check still published files nobody had checked,
  "usually" identical to the checked ones being the whole of the
  guarantee. The three new steps run after `Upload the distribution
  files` rather than before it: each check installs a dependency of its
  own, and the existing comment on that upload step already establishes
  that nothing gets installed before `dist/` is frozen for the publish
  jobs to download, a boundary these steps keep rather than move.
  `publish-testpypi` and `publish-pypi` already had `build` in `needs`,
  so a failing check now stops both. Left undone, and deliberately, the
  same way repository btclib's issue #1154, PR #1164 left it:
  `release.yml` still builds the distribution files twice, once in the
  `test` job it calls and once in `build` — reaching the shape with no
  second build, as `btclib-secp256k1`'s `release.yml` already has, needs
  `test.yml`'s artifact published instead of rebuilt, a larger change
  than this one. `test.yml`'s comment on the `dist` job and
  RELEASING.md's rehearsal description, both of which read as though
  `dist` were the only place checking a distribution, are corrected
  alongside the workflow.
- **Coverage is now measured on a bare `uv run pytest`, and names its
  `source`**, closing issue #6 of the organization's `.github` repository
  (the issue lives in another repository, so no keyword here closes it).
  `--cov` moves into `addopts`, right after `-ra` and not last: it takes
  an optional value, so as the final token it would be handed whatever
  the command line goes on to say — `pytest tests/transport_test.py`
  becomes `--cov=tests/transport_test.py`, the whole suite runs
  regardless, and the run reports against `fail_under` having measured a
  directory `omit` excludes rather than the one path asked for. Moving it
  needs the suite to stop failing on the tree's coverage when it is asked
  for less than the tree: `tests/conftest.py` gains a `pytest_configure`
  hook, ported from btclib's own `coverage_fail_under`, that drops the
  threshold to zero for a run selecting paths, `-k` or `-m`, and leaves
  `--lf`, `--deselect` and an early `-x` at the full gate, those being an
  iteration's flags and not a selection. The threshold is written to
  `config.known_args_namespace` rather than `config.option`: pytest-cov
  reads only the former, filling it before `pytest_configure` runs, so
  the latter changes nothing and fails silently. The hook is itself code
  the 100% gate now covers, so `tests/conftest_test.py` carries the tests
  btclib has for it that apply here — this tree has no hypothesis profile
  and no golden-file fixture to port alongside it.
  `[tool.coverage.run]` gains `source = ["bitcoin_core_rpc", "tests"]`:
  unnamed, `--cov` measures whatever the run imports, which on a
  pristine checkout can differ from what the `coverage` job in `test.yml`
  measures, and a local gate stricter than the one it reproduces is the
  worse of the two directions. That job's own `--cov=bitcoin_core_rpc
  --cov=tests` is now the redundant copy — `addopts` and `source` already
  say what and how — so the step drops back to `pytest
  --cov-report term-missing:skip-covered`, the same measurement as the
  bare command above it in CONTRIBUTING.md. `[tool.mypy]` gains
  `warn_unreachable = true`, which the three siblings already set; unlike
  the other optional error codes this one is not a ratchet with nothing
  to catch — the survey found six sites, each a runtime `isinstance` or
  `callable` guard against a caller that skips type checking, on a value
  whose annotation already promises what the guard re-checks. Each site
  keeps its guard and takes its own `# type: ignore[unreachable]`, naming
  the code, rather than a blanket exemption that would silence the check
  everywhere the finding is legitimate too.
  `addopts` carrying `--cov` also instruments every cell of `test.yml`'s
  `suite` matrix, `macos.yml`, `windows-arm.yml` and `latest.yml` unless
  told otherwise, which broke pypy3.11 outright rather than merely
  costing wall clock: coverage.py has no C extension built for pypy, so
  it falls back to a pure-Python tracer there, and that tracer does not
  survive `rpc_smoke_test.py` exercising `main()`'s several `sys.exit()`
  paths in-process — it warns "Trace function changed" partway through
  the run and stops recording, so a suite that passed every test
  reported 71% against the 100% gate. Each of those four workflows'
  `Run pytest` step now passes `--no-cov`, restoring the invariant
  `test.yml`'s own `coverage` job comment already stated: coverage is
  measured once, on one interpreter, in that job alone.
  A fifth bare-`pytest` call site missed that pass:
  `.github/mutation/bitcoin_core_rpc.toml`'s `test-command`, which shells
  out to `python -m pytest` once per mutant rather than through a
  workflow file, and whose own comment already argued coverage does not
  belong there — a mutant that removes a statement fails the ratchet for
  a reason unrelated to whether the suite noticed the mutation. It now
  carries `--no-cov` too.
  `branch = true` and `exclude_also` are deliberately not part of this
  change — issue #7 of the same repository is that, across every
  repository in the organization, and the two are meant to be read
  together.
- **Coverage measures branches and not statements alone**, `branch =
  true` in `[tool.coverage.run]`, which the organization standard asks
  of every repository under it (btclib-org/.github#7). Statement
  coverage calls a half-tested `if` fully covered: the line ran, one of
  its two ways out never did, and in a module whose bodies are guard
  clauses — the credential already supplied, the cookie file already
  read, the reply that is not an error — the way nobody took is the
  refusal nobody exercised. What the sweep found is that the client
  itself was already whole under the stricter measure, and that the one
  partial branch was in the suite: `tests/standalone_test.py`'s scan for
  the docstrings `automodule` renders never met a module-level
  definition without one, every definition of the client carrying a
  docstring. Closed by a test rather than by a `pragma: no cover`, since
  the branch is reachable and a scan nothing has ever made report is a
  check whose passing says nothing — the scan is now `_documented_names`
  and is read against a source written for it that holds a definition of
  each kind, documented and bare, assignment with a string literal after
  it and assignment without. No pragma was added anywhere.
- **`pydoclint` joins the lint gate**, over `bitcoin_core_rpc/` and
  configured in `[tool.pydoclint]` (btclib-org/.github#7): ruff's `D`
  rules ask that a docstring exists, and this asks that the arguments
  and the return it documents are the ones the signature declares — the
  half that goes wrong in silence when a signature changes and the prose
  above it does not. It reports nothing today, and one of its options is
  why: `skip-checking-short-docstrings` stays at its default, where
  btclib-secp256k1 turns it off, so a docstring carrying no section at
  all is skipped whole. Turning it off here would ask for an `Args:`
  section in every docstring of a file whose paragraphs already name
  their parameters in sentences, which is the same fact written twice in
  the one file a consumer vendors and reads end to end. Issue #172 holds
  that question open, with the output the stricter setting produces and
  the command that reproduces it; the hook meanwhile gates the case the
  sections exist for, a docstring that does list arguments and lists
  them wrong.
- **`published.yml` carried a comment for an `if:` it never had, and
  `setup-uv` was two minor versions behind both siblings** (issue #160,
  divergences 19 and 21 of
  [btclib#1152](https://github.com/btclib-org/btclib/issues/1152)).
  "The second half filters the `workflow_run` trigger" sat above `if:
  ${{ !github.event.pull_request.draft }}`, a single condition with no
  second half and no `workflow_run` trigger anywhere in the file — only
  `workflow_call`. `git log -S` on the phrase finds one commit, #76,
  which introduced both the `workflow_call` trigger and this sentence
  together: the sentence never matched the `if:` it sat above, and the
  scenario it described — a `workflow_dispatch` rehearsal of
  `release.yml` reaching this workflow — cannot happen either, `published`
  being called only via `needs: publish-pypi`, which a rehearsal always
  skips. Aspirational from the moment it was written, not a leftover from
  a removed trigger. Deleted rather than corrected: there is no accurate
  version of "the second half" to write, there being only one half.
  `setup-uv` was pinned to `v10.0.0` (`ae62891f`) throughout, where
  `btclib` and `btclib-secp256k1` are on `v10.0.1` (`20cfd1bf`, read from
  a sibling and verified against the tag rather than re-resolved); brought
  level across all 14 pins.
- **RELEASING.md's "only `github-release` failed" bullet names both of
  a release's artifacts, not one** (btclib#1150). "create the release
  by hand from the `dist` artifact of the run" left out `attestation`,
  which the job downloads beside `dist` before it writes the release;
  a release built from `dist` alone would carry the wheel and the
  sdist with no signed statement beside them, and "Verify the
  provenance of an asset", earlier in the same file, already assumes
  one is there to `--bundle` against. This repository attaches no
  bill of materials — RELEASING.md's own "No CycloneDX bill of
  materials is among them, on purpose" paragraph has the reasoning —
  so the fix is two artifacts, `dist` and `attestation`, and a
  pointer at the `skipped` case's own script below rather than a
  second copy of it, the two bullets already differing only in
  whether `gh run rerun --failed` is worth trying first.
- **`docs.yml`'s unresolved-link grep now carries both known shapes**,
  one of two companion fixes for btclib-org/btclib#1157, which
  btclib-org/btclib's own PR closes. MyST renders a link its
  `RootFileLinks` transform cannot resolve as `href="#<target>"`
  verbatim, so what the grep matches depends on how the target was
  written — `href="#\./` for `./CONTRIBUTING.md`, which every internal
  link in this repository's own root files uses, with no exception, and
  `href="#[A-Za-z0-9_.-]*\.md"` for a bare `SECURITY.md` with no `./`,
  the shape `btclib-secp256k1`'s root files currently carry alongside
  its own `./` links — not a settled convention there, its present
  drift. This repository ran only the first grep, which is blind to a
  bare-shape link breaking here the way one already can there. Built
  the documentation with a
  deliberately unresolved link of each shape and confirmed the added
  grep reports it before removing it; `sphinx-build -W --keep-going`
  passes on both unchanged, since neither is the broken *reference* `-W`
  already catches — a link myst resolves happily and is dead anyway is
  the whole reason this second check exists.

- **REPOSITORY.md records that this repository pins its own
  `default_workflow_permissions` rather than inheriting the
  organization default** (issue #165). The REST API has no field
  distinguishing an override from an inheritance and no value that
  clears one — checked against the current documentation rather than
  assumed — so a future move of the organization default will not
  reach this repository unless whoever moves it also moves this one by
  hand, with the command the new section gives. `btclib` and
  `btclib-secp256k1` are recorded as untested rather than known good:
  both were already at the target value before the organization
  default moved, so neither could have been observed following it.
- **Every `run:` step that can land on a Windows runner declares
  `shell: bash`** (btclib-org/btclib#1148). `suite-latest` in
  `latest.yml`, `suite-windows-arm` in `windows-arm.yml`, and `suite` in
  `test.yml` each carry a `windows-latest` or `windows-11-arm` matrix
  cell, where the default shell is PowerShell and `"$GITHUB_ENV"` and
  the rest of the POSIX spelling are literals rather than variables — the
  same defect btclib-org/btclib#1141 shipped in btclib's own
  `published.yml`, and here in the two remaining scheduled workflows and
  in `test.yml`'s own merge-gate job. All four
  affected steps are one plain command each and run identically under
  either shell today, so nothing shipped broken. `latest.yml` and
  `windows-arm.yml` run on neither a pull request nor a push to `main`,
  so the hazard is the next conditional, substitution or loop landing on
  one of them, first executed on a schedule or a tag; `test.yml`'s
  `suite` job runs its Windows cell on every pull request, where a
  shell-less step still executes PowerShell rather than the intended
  bash, going green on the wrong interpreter's syntax rather than red on
  the right one.

  Enumerated by parsing every workflow file's `jobs.*.strategy.matrix`
  (`os` and `include`) and `runs-on` with PyYAML, and flagging a `run:`
  step whose job's runner set contains `windows` and which declares no
  `shell:` of its own and inherits none from a job-level `defaults.run`
  — `actionlint`, the pinned linter in the pre-commit gate, reports
  nothing for this shape, measured on a minimal workflow with a POSIX
  `for` loop and no `shell:`. `btclib` and `btclib-secp256k1` had the
  same `latest.yml`/`windows.yml` defect in their own copies, fixed in a
  pull request of their own; `btclib-secp256k1`'s `test.yml` carried two
  further instances of its own.
- **`release.yml` no longer has a `build` job, and `test.yml`'s `dist`
  job is now the one build a release publishes** (issue btclib-org/
  btclib#1166, filed from btclib's own copy of the same seam). The
  entry above (issue #155) closed the correctness hole — both builds
  checked — and left the seam standing, in the terms it used itself:
  `dist` still built a copy that was checked and thrown away, `build`
  still built a second, separate copy — with no `SOURCE_DATE_EPOCH` and
  no sdist normalization — checked a second time and published. `dist`
  now pins `SOURCE_DATE_EPOCH` from the commit, normalizes the sdist,
  uploads the `dist` artifact before installing anything, and only then
  runs the three checks and the wheel smoke test; `release.yml`'s
  `publish-testpypi` and `publish-pypi` jobs download that artifact
  unchanged, and `attest` signs the digests the upload already fixed. A
  rehearsal's version suffix moves too, from an inline step in `build` to
  a `.github/actions/dev-version` composite action `dist` runs before its
  own `uv build`, computed once in `version-check` and passed down as a
  `workflow_call` input so every job the release dispatches during one
  run agrees on it — carrying over the `run*100+attempt` scheme issue
  #157 above already fixed here. No `check-newest-bindings`-style second
  smoke test, unlike btclib's own fix: this package declares no runtime
  dependency to ask that question about. `btclib-secp256k1` has had the
  one-build shape from the start.
  `dist`'s own `Setup uv` step carries `build`'s caching-off forward the
  same way, through a new `disable-dist-cache` input rather than a flat
  `enable-cache: false`: a cache entry written by one run is read by
  another through GitHub's branch/PR scoping, so the build whose output
  actually reaches an index must fetch its dependencies afresh, where an
  ordinary pull request's build is thrown away and caching it costs
  nothing. Found and fixed the same way as btclib#1180 (`dd198d83`),
  the twin of this pull request, whose first review round caught the
  same regression.
- **A `local-link-prefix` hook refuses a local markdown link destination
  that does not begin with `./`, and `docs.yml`'s unresolved-link check
  is one grep again** (btclib-org/.github#20). What that grep can match
  is decided by how the link was written, myst rendering the destination
  of a link `docs/source/conf.py`'s `RootFileLinks` transform cannot
  resolve verbatim: `./SECURITY.md` breaking gives
  `href="#./SECURITY.md"`, a bare `SECURITY.md` breaking gives
  `href="#SECURITY.md"`. The links here were already written the first
  way, and nothing said they had to be — the hook is what says so, and
  with it the second grep, added for the bare shape `btclib-secp256k1`
  was writing rather than for anything this tree carried, has nothing
  left it can catch. That grep was no superset of the first even so: a
  character class of name characters stops at the `#` of an anchor, so
  `href="#README.md#build"` is a shape both patterns pass over, which is
  the argument for moving the rule upstream rather than writing a third
  pattern.

  The rule is the prefix and not the extension, and the table in
  btclib-org/btclib#1175 is what decides that: `DOES_NOT_EXIST.txt`,
  `sub/DOES_NOT_EXIST.md`, `DOES_NOT_EXIST` and `../DOES_NOT_EXIST.md`
  each reach MyST's fallback and each is missed by the union of both
  greps, so an `.md`-scoped rule would leave all four writable. `../`
  is the row with nothing downstream behind it at all: the transform
  *declines* a target normalizing above the repository root, so that
  shape reaches the fallback by design and renders `href="#../X.md"`,
  which the surviving grep does not match and should not be widened to
  reach — the hook is the only place it can be caught. A link reference
  definition, `[label]: page.md`, renders the same fallback and carries
  no `(`, so the pattern has a second branch for it, anchored at the
  start of a line so that a reference *use* followed by a colon is not
  mistaken for one.

  Measured here as well, by building this documentation with an
  unresolvable link written each way:
  `./page.md`, `./page.md#anchor`, `./page.txt`, `./sub/page.md` and an
  extensionless `./page` each render `#./` followed by the destination,
  so the one grep sees every one; the same destinations without the `./`
  render the destination alone, which nothing catches without also
  matching the autodoc anchors these pages carry.

  **README.md's licence badge was cited here as the live case for that,
  and the citation was wrong** — recorded rather than swapped out,
  because the rule this entry lands was argued from a destination the
  rule did not reach. `[![license: MIT](…)](./LICENSE)` is a *badge*:
  its destination sits behind a nested image, and a link text written
  `[^]]*` stops at the `]` that closes the alt text, so the first
  version of the pattern checked the image `src` and never the badge's
  own href. Every badge destination in this repository was unchecked,
  and neither `docs.yml` grep, the removed one or the surviving one,
  would have seen one lose its `./` either. The link text is now
  `(?:[^]]|\]\([^)]*\))*` — a character that is not `]`, or a whole
  `](…)` group — which steps over the image and reaches what is behind
  it, and by backtracking still checks the `src` on the way. Measured
  on the built html: a badge href renders exactly what a plain href
  renders, `#./NOPE.md` with the prefix and `#NOPE.md`, `#NOPE.txt`,
  `#sub/NOPE.md`, `#NOPE`, `#../NOPE.md` without it. The corrected hook
  reports nothing against this tree, badges included.

  `RELEASING.md`'s link to `release.yml` was the one destination in
  this repository's markdown that did not begin `./`, and now does.
  `uv run --locked --only-group lint pre-commit run local-link-prefix
  --all-files` re-derives the whole of it.

- **`docs/source/conf.py`'s `RootFileLinks` comment lists every root
  markdown file the toctree pulls a page from, in place of a count**
  (issue #189). The sentence introducing the shims said how many pages
  carried them and named some of the pages but not all of them, so the
  number and the list disagreed with each other as well as with the
  toctree in `docs/source/index.rst`: COMPARISON and REVIEWING were
  missing from both. btclib's own `conf.py` carries the same paragraph
  with no count at all, naming its files instead, and that is the
  shape adopted here too — a page missing from the list is visible on
  the next read, where a stale number was not.

- **`REVIEWING.md` asks a review to run what a diff decides with.** A
  regex, a grep, a pattern in a hook, a script or a query decides an
  outcome by matching or computing, and a review of one executes it
  rather than reading it — against the shapes the diff's own prose
  claims to cover, and against the shapes the tree actually holds. A
  claim the prose makes about the tree takes the same treatment, "every
  link here is already `./`-prefixed" being one `git grep`'s worth of
  evidence and the reason a change is offered as safe.

  What earned the rule is this repository's own review of the
  `local-link-prefix` pygrep hook, pull request #192, the same pattern
  having been proposed across the organization byte for byte. The
  leading clause `\[[^]]*\]\(` cannot cross the `]` that closes an
  image's alt text, so on the badge shape `[![alt](./src)](./href)` it
  examines the image source and never the destination the link itself
  carries — which is the destination that hook's own comment cites as
  its motivating case, left free to lose its `./` unreported. That
  review ran the clause against `README.md`'s licence badge and quoted
  what it printed; the sibling reviews reasoned about the same pattern
  and reported it correct. The rule generalizes what the run did rather
  than leaving it to whoever thinks of it.

  The section says what it is not, `claude-review.yml`'s prompt telling
  a review here not to re-run the gates: those run what the rest of the
  tree already exercises, where a pattern a diff adds has been run
  against nothing until a review runs it. The prompt is unchanged — it
  names `REVIEWING.md` rather than restating it, so the standard moves
  without the workflow being edited.

- **`REVIEWING.md` says when a gate already run is relied on rather than
  repeated, and `CLAUDE.md` says which checks a pull request is gated
  on.** The condition is the sha and the record: where the gates have
  been run on this very commit — the required checks running beside a
  review, or an author handing over a branch they gated and stated the
  result of — the review relies on that run and names whose it is, and
  where there is no such run it runs them itself. A run on another tree
  is not a run on this one, so a rebase voids it, the branch having been
  gated before the tree moved under the gate.

  What earned it is `claude-review.yml`'s prompt, whose reason for not
  running the gates was that a second run of them would cost a runner
  slot. That is an argument about price, and a reviewer reading it
  generalizes it into "running costs, so do not run" — which is the
  disposition that acked the `local-link-prefix` pattern of the entry
  above without running it. The prompt now carries the instruction and
  points at `CLAUDE.md` for why the reliance is sound, which is also
  what keeps its hunk small: a pull request editing that file cannot be
  reviewed at all, the action refusing to run under a workflow differing
  from the default branch's copy (btclib-org/.github#58).

  It leaves the entry above where it was. The gates exercise what the
  tree already held, so what a diff decides with has been run by nothing
  whether they ran or not, and a review runs that either way.
- **`latest.yml`'s pre-commit cache is keyed on the runner image and the
  interpreter rather than on the config hash alone**
  (btclib-org/.github#25). What that cache holds is virtualenvs, so the
  config hash alone survives an `ubuntu-latest` rotation and restores
  environments built on the previous image — not a graceful miss but a
  hit, surfacing as whichever hook touches the broken environment first.
  `lint-latest` is the job with the most to lose from that: it runs to
  report what a new release of a dependency breaks, so a failure the
  cache caused arrives looking exactly like the one the workflow exists
  to find, and is chased in the tree. The `Identify the runner image`
  step reading `ImageOS` from a shell, the key over `runner.os`, that
  output and `hashFiles` of `.pre-commit-config.yaml` and
  `.python-version`, and `restore-keys` still naming the image so a
  partial restore cannot cross an image boundary, are all `lint.yml`'s,
  which has carried them since before this was noticed. The comment
  above the bare key claimed it was keyed "as in `lint.yml`", which was
  false where it stood and offered that file as the justification; what
  replaces it is this job's own reason for the key, with
  `git grep -n 'pre-commit-\${{' -- .github/workflows/` beside it as the
  command that re-reads both keys together.

- **`REPOSITORY.md` stops naming which sibling repositories are untested
  against the organization workflow-permissions default**
  (btclib-org/.github#23). That paragraph was a roster of other
  repositories' settings kept in this one, and it had already gone
  incomplete — `btclib-benchmarks` was missing from it. Each sibling now
  records its own status in its own `REPOSITORY.md`, which is where a
  reader of that repository meets the question; what stays here is the
  reason they share, that each already held `read` when the organization
  default moved on 21 August 2026 and so could not be observed following
  it. This repository's own entry is unchanged: it is pinned, and the
  read-back beside it still answers `read`.
- **`.readthedocs.yaml`'s header stops describing a sibling's tree, and
  starts saying what the file does not decide**
  (btclib-org/.github#26). The line about `readthedocs.yml` being
  honored but deprecated arrived with a clause about `include *.yml`
  dragging the file into the sdist beside the Jekyll configuration.
  Nothing serves a site from this root, there is no such configuration
  to sit beside, and `MANIFEST.in` names `include *.yaml` with its own
  reason written beside it — so the clause was true of btclib and of
  nothing here. It is now attributed to btclib rather than deleted, a
  clause named as another repository's being harder to copy back than a
  gap.

  What is added is the fact this tree cannot answer anywhere: *which*
  versions run this file. `latest`, `stable` and each release tag are
  versions on read the docs' side, and an automation rule is what
  activates a new tag there — so a release that keeps a permanent URL of
  its own and one that does not differ in a setting rather than in the
  tree. btclib's `REPOSITORY.md` carries a "Read the Docs" section
  recording exactly those settings; this repository's has none, and the
  comment says so and names btclib-org/.github#26, which carries the
  commands that read the state back. Writing that section here is a
  change to `REPOSITORY.md` and left to one.
- **`documented`'s wait can no longer spend the whole job timeout, and
  names what it last saw when it gives up** (btclib-org/.github#18). The
  loop's worst case and `timeout-minutes` were the same budget — an
  attempt costs its `curl --max-time` plus the `sleep`, and that sum
  taken over every attempt reached the job's own limit exactly — so a
  response slow enough to spend its `--max-time` without ever answering
  ran the loop into that wall, and the runner killed the job before the
  `::error::` line, the one line the job exists to print. A red run then
  said only that it had exceeded its maximum execution time, which is a
  fact about this workflow rather than about the documentation. The
  ordinary case never came near it, Read the Docs answering a 404 in
  well under a second while a build has not started; it is the slow or
  unreachable case that lost the pointer, and that is the case a reader
  most needs it in. The loop now leaves a margin it cannot spend into,
  and the last attempt no longer sleeps before giving up.

- **The same wait stops discarding what it already knows.** `curl -sf`
  threw the response away, so every attempt printed "is not served yet"
  and the final `::error::` named only the URL and the builds page. A
  status code and a transport failure are now told apart, each attempt
  names which of the two it got, and the verdict reads `last seen: HTTP
  404` or `last seen: curl exit 28 (no response within 10s)` before
  pointing at the builds page — named as where the reason is written,
  this job saying only that there is one. What the wait still cannot do
  is tell a build that has not started from one that never will:
  `/en/<tag>/` answers 404 for both, and the v3 API that separates them
  stays ruled out for the reason the job's own comment already gives.
  Dropping `-f` needed a second fix the diff does not show: under the
  shell's default `set -e` a bare `status=$(curl ...)` aborts the step
  on curl's own non-zero exit, so a hung server would have ended the run
  on the first slow response — precisely the case the margin exists for
  — and the assignment is the condition of an `if` instead.
  `release.yml` cannot run on a pull request, so the step's literal
  script was extracted and driven against a mocked `curl` and `sleep`:
  immediate success, success on a later attempt, a fast failure every
  attempt, and every attempt hanging to `--max-time` each reach the
  intended verdict, and the last attempt is observed not to sleep.
  Ported from btclib's own fix, which found the `set -e` defect the same
  way.

- **`.yamllint.yaml` says what is true of every repository carrying it,
  and re-derives the rest** (btclib-org/.github#40). The file is copied
  byte-for-byte across the organization, and its comment carried a
  survey run once, in `btclib`: how many findings each disabled rule
  produced, what share of the action pins sat at or past 80 columns,
  what a limit of 80 would report and how much of that was pins, the
  width of the longest pin, how many yaml files the tree held, and two
  over-length shell lines in a `release.yml`. Re-measured with the
  pinned yamllint against this tree and against the others sharing the
  file, not one of those figures still held anywhere — `btclib`
  included, where the survey was taken — and the `release.yml` claim
  names a file two of the repositories carrying the comment have never
  had. The survey is replaced by the commands that answer for whichever
  tree is asking, the default set at the configured width and what a
  limit of 80 would cost, beside the reasons that do not vary between
  repositories: dependabot writes one space before a pin's trailing tag,
  `on:` is the boolean true in yaml 1.1, and a 40-character SHA with its
  tag has spent most of an 80-column line before the action is named.
  This repository's `.taplo.toml` already differs from the shared one
  and carries none of this, so it is untouched.

- **`CLAUDE.md`'s primary-checkout paragraph names the read that cannot
  go stale** (btclib-org/.github#255). It said reading the checkout was
  fine and so was `git fetch`, without saying `git fetch` moves
  `refs/remotes/origin/main` and leaves the work tree where it was, so a
  `grep` or a `Read` against the checkout answered for whenever it was
  last brought forward. The paragraph now names `git show
  origin/main:<path>` as the read that does not go stale, and gives the
  fast-forward that brings a clean checkout forward without working in
  it.

- **The shipped module's exception-naming comment no longer names
  `btclib`** (btclib-org/.github#81). This package is zero-dependency
  and vendorable, so `bitcoin_core_rpc/__init__.py` is read by people who
  copied only that file and have never heard of `btclib`; the comment
  explaining the `BtcRpc` prefix stated a collision with `btclib`'s own
  `BTClibValueError` that is not that reader's. It now gives the reason a
  distinct prefix is worth having without naming the dependent: a
  consumer already carrying an error hierarchy of its own should not have
  to tell two `ValueError` subclasses apart. A
  `no-downstream-name-in-package` pygrep hook holds the shipped module to
  it, the organization spelling and the copyright line's "The btclib
  developers" excepted.
- **`CLAUDE.md`'s worktree recipe named the worktree after the issue
  alone, `wt<issue>`** (btclib-org/.github#292). A worktree's
  administrative directory lives in the `.git` of the repository
  `git worktree add` was run from, one per repository, so two
  repositories cannot collide there; what the recipe left uncovered was
  a same-repository collision, between two worktrees of different work
  sharing a generic basename, and a *path* collision across
  repositories, since the workers of one session share one scratchpad
  directory and a session carrying one issue into several repositories
  computed the same target path for each. The recipe now names the
  worktree `wt-<tracker>-<issue>-<repo>-<role>`, most general part
  first: `tracker` because an issue number is unique only within one
  tracker, `issue` against the same-repository collision, `repo` against
  the cross-repository path collision, and `role` against a coder and
  its reviewer holding a worktree at once.

- **`README.md` ends with the line naming who supports the work.** The
  organization standard states the line as tier 1's, for the reason
  `SECURITY.md` is: the archive leaves github.com, and a reader who has
  it and not the repository meets the project with no organization
  beside it (btclib-org/.github#98).

- **`no-downstream-name-in-package` matches `Btclib` and `BtclibError`,
  not only `btclib`** (btclib-org/.github#299). The hook took no `args`,
  so it matched case-sensitively and let a downstream name that opens a
  sentence or sits in a class-name-style compound through where the same
  name mid-sentence would not; `btclib-secp256k1`'s copy of the same
  hook already carries `args: ["-i"]`, so the two enforced different
  rules under one name. `args: ["-i"]` here now closes that gap.

- **`REPOSITORY.md` and `RELEASING.md` stop citing `btclib`'s own state
  to justify this repository's choices** (btclib-org/.github#81). A
  required-check name, a GitHub Actions concurrency count, an `--admin`
  merge precedent and a CycloneDX bill-of-materials decision each
  reasoned from what `btclib` does or measures, standing in for
  reasoning that holds on its own; the bill-of-materials paragraph also
  sent its reader to `btclib`'s own `RELEASING.md` for "the full
  reasoning" instead of stating it. Each now reasons from this
  repository's own configuration alone. The `no-downstream-name-in-package`
  hook does not reach either file, only the package directory that
  ships, which is why this half needed a reading rather than a red hook;
  with it, this repository carries the last box `btclib-org/.github#81`
  had open.

- **`bitcoin_core_rpc/` moves under `src/bitcoin_core_rpc/`** (issue
  btclib-org/.github#313): section 2 of the organization's standard
  puts every repository's package under `src/`, and this repository
  had not yet converged. `[tool.uv.build-backend] module-root = ""` is
  deleted rather than changed: that key existed only to override the
  backend's own default, which is `src/`. Every path this repository's
  own configuration and prose named the package by moves with it --
  `.pre-commit-config.yaml`'s two `files:` patterns and one `exclude:`
  pattern, the mypy invocation's arguments,
  `.github/mutation/bitcoin_core_rpc.toml`'s `module-path`,
  `[tool.check-wheel-contents] package`, and the citations in
  `CLAUDE.md`, `CONTRIBUTING.md`, `README.md` and
  `.vscode/settings.json`. `[tool.coverage.run] source` and every
  `import bitcoin_core_rpc` keep naming the package unchanged, since an
  import name is not a path.

- **`.pre-commit-config.yaml`'s `typos` hook converges to
  `btclib-org/.github`'s `repo: local` shape** (issue
  btclib-org/.github#399). `autoupdate` walks every `repo:` entry except
  `local` and `meta`, so the `crate-ci/typos` mirror kept receiving the
  moving `v1` alias that `pinned-rev` then refused on every run;
  `additional_dependencies: [typos==1.49.0]` now carries the pin in
  place of `rev:`, and the comment explaining why is `btclib-org/.github`'s
  own, taken across unchanged. Two comments this repository carries on
  its own claimed every pre-commit hook's revision is kept current
  either by pre-commit.ci or, for `mypy` alone, by `deps-latest.yml`'s
  own upgrade -- neither reaches `typos` any longer, and
  `.github/dependabot.yml` and `deps-latest.yml` are corrected in the
  same diff.

- **`.gitignore` no longer names `docs/_build/`** (issue
  btclib-org/.github#411). `build/`, already present above it, ignores
  `docs/build/html`, the directory `docs.yml`'s `sphinx-build` step
  writes to; `docs/_build/` matched no path in this tree and decided
  nothing.

- **`README.md`'s badge row drops the link to the repository** (issue
  btclib-org/.github#381). Section 2 of the organization standard
  refuses it now: the badge renders the repository's name because the
  URL says so, and the row is an audit, so the item that measures
  nothing is the one that does not belong in it. `[project.urls]`'s
  `repository` key already carries the same link for the reader who
  meets this file as an index's long description or as an unpacked
  sdist's README.

- **`pyproject.toml`'s comments are corrected against measurement**
  (closes #226) (closes #242) (closes #230) (closes #239) (closes #247).
  The `license-files` comment quotes the notice `LICENSE` carries, "The
  btclib developers", rather than a holder no notice in the tree names.
  The `warn_unreachable` comment drops a count of sibling repositories
  that no longer describes the organization. The
  `skip-checking-short-docstrings` comment states btclib-secp256k1's
  current reason for turning the option off, an Args/Returns form on
  almost every docstring there, rather than its retired one. The
  docstring-`ignore` comment adds the fact that the `pep257` convention
  leaves `undocumented-magic-method` and `undocumented-public-init`
  enabled, so naming neither entry is what asks a docstring at every
  such site.

- **`[tool.check-sdist] source-exclude` gains `.coverage`, `.coverage.*`
  and `coverage.xml`** (closes #264). coverage.py writes its data file
  beside the tree it measured rather than under a cache directory, so
  `cd tests && uv run pytest .` left `tests/.coverage` behind, gitignored
  and swept into the sdist by the `tests/**` include; the three new
  entries are unanchored, the same shape as the three cache entries
  already there.

- **`[tool.uv] required-version` rises to the ceiling Dependabot's own
  uv-ecosystem updater allows** (closes #250), and the comment beside it
  points at the organization standard's own argument and its command to
  re-derive the ceiling rather than restating either.

- **Ruff's `unspecified-encoding` (`PLW1514`) is now selected**
  (closes #225). It is a preview rule, unreached by the `PL` family
  already selected, and asks that `open`, `read_text` and `write_text`
  name an encoding rather than take the locale's -- the defect
  `decoded-subprocess-encoding` already refuses one layer out, at a
  subprocess call. No source in the tree fails it, which makes the
  change a ratchet rather than a cleanup.

- **`CONTRIBUTING.md` and `RELEASING.md` qualify a bare `#1166` as
  `btclib-org/btclib#1166`** (closes #221), the three sites citing
  btclib's own issue rather than one of this repository's.

- **This release's `check-sdist`/`pyroma` entry overstates what
  `pyroma`'s non-isolated build call checks** (closes #238). `pyroma`'s
  `wheel_metadata()` calls the backend's PEP 517 hook directly through
  `build.util.project_wheel_metadata(..., isolated=False)`, which never
  reads `[build-system]`'s `requires`, and falls back to an isolated
  build only when that call raises a `BuildException` or
  `BuildBackendException` -- in this tree's own hook environment the
  backend-import failure that entry's own next sentence already quotes,
  not a `requires` check. That entry is not rewritten, being already
  landed; this corrects the record beside it.

- **Every `cron:` here fires at the instant section 10's calendar gives
  that workflow and this repository** (issue btclib-org/.github#480). The
  calendar's rows sit in the order of what they ask about -- the depth a
  tree's suite is tested to, what it does against software it does not
  ship, what it depends on and what it publishes, its platforms, its own
  health and its security -- so a workflow's day and hour follow its
  family. The minute is this repository's row in that section's second
  table, and it does not move. `dependabot.yml` is untouched, section 10
  keeping `deps-latest` on the day before Dependabot's own.

- **`README.md`'s badge block is section 2's three groups** (issue
  btclib-org/.github#480). What the software is opens with the release
  identity as a pair, the PyPI version beside `github/v/release`, which is
  how section 2 says those two are read: where they disagree, a release
  reached the forge and not the index. The licence and `wheel` sit in that
  group, this tree having a `LICENSE` and publishing a wheel, and section
  2 derives the row from such properties rather than curating it. The CI
  group is the gates in the order a commit meets them, Read the Docs among
  them because it answers `passing`, `failing` or `unknown` as the
  workflow badges around it do, and then the sentinels in the calendar's
  order -- so the badge order is the calendar order over that subset, and
  the two move together or not at all. The Scorecard badge is the OpenSSF
  group, and section 2 reads it as the last of the sentinels without being
  among them, `scorecard` being the calendar's last row.

- **The calendar sentence points at section 10 and states no number**
  (closes #276). It gave the calendar six repositories, where section
  10's second table names more. Section 9 of the organization standard
  asks prose never to state how many of anything a file holds: a total is
  exact on the day it is written and stays grammatical after it stops
  being true. The clause beside it already says the calendar is not this
  file's to restate, and a count of what it covers restates that table.
  The phrase is now the one `btclib-secp256k1`'s copy carries.

- **`pypi-install.yml` says why its `pull_request` types leave out
  `closed`** (closes #273). Section 10 of the organization standard names
  `closed` among the types, and its reason is the merge landing in the
  pull request's own concurrency group to cancel the run still holding
  it. This workflow's group carries `cancel-in-progress: false`, so a
  closed event cancels nothing whichever group it lands in; and the job's
  condition declines a draft and says nothing about a close, so the run
  such an event added would install from the index on every cell of the
  matrix, for a pull request nobody is on. The types are unchanged and
  the divergence states its reason where it is, which is what section 9
  asks of a deviation.

- **The downloads badge's link target is the plural
  `pepy.tech/projects/bitcoin-core-rpc`** (closes #281). The singular
  answers `308`, matching the reason section 2 of the organization
  standard already gives for the Read the Docs spelling it fixed the
  same way: a link that works only because a third party keeps
  forwarding it is a dependency nobody here recorded. The badge's image,
  `static.pepy.tech/badge/bitcoin-core-rpc`, is section 2's own spelling
  and is unchanged; only the href moves.

- **`claude-review.yml` takes `closed` among its `pull_request` types, and
  declines it at step level rather than on the job** (closes #278).
  Section 10 of the organization standard gives `closed` the reason of
  landing a merge in the pull request's own concurrency group to cancel a
  run still holding it, and this job's group is job-level rather than
  workflow-level: the job itself, not only the workflow run, has to be
  scheduled on a closed event to enter that group, so its `if:` stays open
  to the event rather than declining it the way `lint.yml`'s
  workflow-level group lets its job do. `github.event.action != 'closed'`
  sits on the review step and on each step that reports a verdict
  instead, so closing or merging a pull request cancels the run still
  holding `claude-review-<number>` and concludes green, without starting a
  review of a pull request nobody is looking at any more.

- **`claude-review.yml`'s credential check declines a closed event**
  (closes #283). The review job is scheduled on a close so that it
  enters `claude-review-<number>` and cancels the run still holding it,
  and the review step -- the only other step of that job reading
  `CLAUDE_CODE_OAUTH_TOKEN` -- declines that event, as does each step
  that reports a verdict. So on a close the check asserted its invariant
  over a credential the run never reaches, where the empty secret that
  fails it is a red check on a pull request already merged or closed. It
  carries the same `github.event.action != 'closed'` its neighbours do,
  and no `!cancelled()` beside it: an `if:` naming no status check
  function is evaluated as `success() && ...`, which is what a
  precondition wants, where the step reporting a review that never ran
  has to fire after a failure and says so where it sits.

## v2026.8.20

### Repository

- **RELEASING.md's tagging step signs the tag it creates.** `git tag -a`
  is annotated and unsigned; `git tag -s` is the same object with a
  signature on it, and nothing else about the procedure or about
  `version-check` changes. Every commit reaching `main` already carries
  a verified signature, `main-integrity` requiring it with no bypass
  actor, but the tag that turns one of those commits into a PyPI
  release — `release.yml` triggers on `push: tags: ["v*"]`, and the
  `pypi` environment is restricted to that pattern — carried none. The
  `pypi` environment's required review before the publish job runs is
  already a real compensating control. A tag cannot be signed
  retroactively without moving it, and moving a released tag is worse
  than leaving it unsigned, so existing tags stay as they are — this
  applies from the next release onward. A `tag` ruleset requiring
  signatures on `v*`, enforcing the same thing at the
  repository-settings level rather than documenting it, is a further
  step left for a separate, maintainer-authorized change (sibling
  repository btclib landed both halves as issue #1022).
- **`claude-review.yml` reads a pull request against `REVIEWING.md`.**
  Two jobs: one on every non-draft pull request, whose prompt names that
  file rather than restating it, so the standard moves without the
  workflow being edited; one answering `@claude` in a comment, carrying
  no prompt of ours on purpose — the action reads the comment that
  triggered it. It gates nothing and must not: `main`'s required
  contexts are named outside the repository. The gates are not re-run,
  `test.yml`, `lint.yml`, `docs.yml` and `integration.yml` running them
  beside it on the same sha.

  Three things it refuses to do silently, each measured in btclib before
  being asked not to: without `CLAUDE_CODE_OAUTH_TOKEN` the action
  reviews nothing and reports **success**; without `id-token: write` it
  dies before authentication, minting a GitHub OIDC token at startup
  whatever the Anthropic credential is; and it refuses to run at all
  when the workflow file differs from the copy on the default branch,
  reporting that refusal by skipping, green. It fails on an empty secret
  and on an empty `execution_file`, which is exactly when no review was
  written — so on a pull request that adds or edits this file the job is
  red until the change is on `main`.

  It is the one workflow in `CONTRIBUTING.md`'s table taking no
  `workflow_dispatch`, both jobs reading the pull request or the comment
  that triggered them; the `grep` that paragraph cites says so.
- **The landing convention says what is in force, and it is the button.**
  `CONTRIBUTING.md` described two landings, both pushes, with the merge
  button "pressed for neither" and one signer down the whole of `main`;
  `REPOSITORY.md` carried the pushes; `RELEASING.md` said the button
  "stays permanently disabled"; `CLAUDE.md` kept a fast-forward
  exception for a stacked pull request. The `main-self-merge` bypass is
  in `pull_request` mode across the organization, so it excuses the
  approving review a solo-maintainer repository cannot produce and
  excuses nothing else: `main` is reachable through a pull request and
  through nothing else, a direct push refused for everyone. The ruleset
  names `squash` as the only merge method it accepts. What the
  fast-forward bought — a stacked child keeping its base — is paid for
  with a rebase, a button recreating rather than moving whatever the
  count of commits, GitHub's documentation having rebase-and-merge
  "always updates the committer information and creates new commit
  SHAs". That the commit carries GitHub's web-flow signature rather than
  the maintainer's costs nothing: `main-integrity` asks for a valid
  signature and not for a particular signer, with no bypass actor for
  anyone.

- **`REVIEWING.md` is the standard a review is written against**, the
  reviewer's half of `CONTRIBUTING.md`: what a review establishes before
  it gives an ack, what a finding must contain and how it labels its
  severity, and what becomes of everything a reviewer notices that the
  diff is not about — every collateral finding is filed as an issue
  rather than asked for in a comment. It states no new rule. Registered
  the way `CONTRIBUTING.md` is: a page of the sphinx toctree through a
  `reviewing_link.md` shim, named from the README and from `CLAUDE.md`,
  which is the file a repository-aware reviewer reads, with
  `.claude/commands/review.md` as the `/review` command. The body is
  deliberately the text btclib carries, one section excepted: the
  questions a review of *this* tree asks — the single-module and
  no-dependency property `tests/standalone_test.py` enforces, and the
  two JSON-RPC dialects `_legacy_result` and `_v2_result` keep apart.

- **A pull request of one commit is fast-forwarded onto `main`**, where
  every pull request was squashed. A squash writes a new commit: the sha
  the branch was written on is gone, so a pull request stacked on that
  head is asked for a rebase and for a re-review of a diff nobody edited,
  and the commit that lands is not the commit the checks ran on. Two
  commits or more are still squashed into one, the steps of a review being
  the pull request's record rather than `main`'s. A verified signature
  lands either way -- the branch's own where the head is pushed as it
  stands, the maintainer's where a squash is composed in a worktree, the
  merge button being pressed for neither and GitHub's web-flow key
  therefore signing nothing here -- and the ruleset
  takes no unsigned commit, so an unsigned single commit is squashed and
  signed rather than fast-forwarded. The subject `main` reads is the
  branch's own where nothing composes one at the button, so a one-commit
  pull request names its own number, which is an amend and a force-push on
  work no reviewer has read yet. CONTRIBUTING.md states the rule,
  REPOSITORY.md the pushes that do what the merge button does not, and
  RELEASING.md lands a one-commit release branch this way. The push is the
  whole landing: GitHub reads the head as reachable from `main`, marks the
  pull request merged, closes what it says it closes and deletes the head
  branch, which is `delete_branch_on_merge` treating the merge it detects
  as the merge it performs.
- **The generated Code Quality analysis is off.** `Analyze (python)` ran
  on every pull request and every push to `main` from a
  `dynamic/github-code-scanning/codeql` workflow no file in this tree
  declares -- some 44 seconds of a slot each time, out of twenty shared
  with every other repository in the organization, where the same setting
  was on. What it produced cannot be read from outside a browser: there is
  no `code-quality/alerts` endpoint and no `code-quality/analyses`, both
  404, the alert list is empty and every analysis carries `codeql.yml`'s
  own category. REPOSITORY.md gains the section and the endpoint that
  reports and sets it, `code-quality/setup`: not
  `code-scanning/default-setup`, and not the Actions API, which answers
  422 for a workflow this repository does not own.

- **A pull request asks for thirty-three jobs instead of forty-four**, and
  the number that decided it is a ceiling rather than a wall clock: GitHub
  Free gives an organization twenty concurrent jobs, shared across every
  repository in it, so a commit here and a commit in btclib compete for the
  same twenty. Measured on one pull request run, this workflow set asked
  for forty-four jobs and 16.9 runner-minutes for work that finishes in 212
  seconds. Three changes, and each moves an answer off the review path
  rather than dropping it:
    - the seven `windows-11-arm` cells become `windows-arm.yml`, weekly on
    Saturday and called by `release.yml`, exactly as `macos.yml` already
    holds the macOS ones. The fourteen Windows cells were 9.4 of the 16.9
    runner-minutes, and that image is the slower half of them, 40 to 77
    seconds a cell against 29 to 34 on `windows-latest`. **`windows-latest`
    stays**: the datadir table in `default_datadir` is the one
    platform-conditional branch here, the suite drives every row of it but
    the running one by patching `sys.platform`, and a real Windows runner
    is where `%APPDATA%` and the `Path.home()` under it are asked for real.
    - `codeql.yml` loses its `pull_request` trigger and keeps `main` and its
    Tuesday schedule, so `codeql: every job passed` is no longer one of
    main's required checks -- four now, and REPOSITORY.md carries the rule
    and the `gh api` patch that dropped the context. `zizmor` is a
    pre-commit hook, so `lint.yml` still audits these workflows for an
    injected expression on every pull request.
    - the `(3.14, ubuntu-latest)` cell of `test.yml`'s matrix is excluded,
    because the `coverage` job beside it is that cell: same image, same
    interpreter, the same suite, and the only difference is the
    instrumentation.

- **RELEASING.md reads what is open before it tags.** A pull request
  touching `release.yml` or a workflow it calls is one the tag is about to
  run, so leaving it in review runs the defect it fixes on the release
  itself -- and nothing catches that, every such workflow being green on
  the pull request that fixes it. `published.yml` is the case named, its
  failures arriving after PyPI has accepted the files.
- **A release branch is thrown away and redone when `main` moves under
  it**, never rebased and never merged into. CHANGELOG.md and HISTORY.md
  are `merge=union`, so a change that opened a `### Repository` group where
  the release opens its own is fused into one section carrying that heading
  twice, with no conflict reported. The `git diff --cached` at the landing
  step reads the same hazard one step too late, the fused headings being
  what is committed by then.
- **The GitHub release is checked by asking for the release**, `gh release
  view v<version>`, rather than by reading the run's conclusion: the two
  have disagreed on the last two tags, `github-release` reporting `skipped`
  while its needs and the run itself report `success`. "If something goes
  wrong" records that as the expected outcome until it is fixed, and names
  the report to GitHub support as owed.
- **The TestPyPI rehearsal says when it is worth its run**: when the
  publish path or what travels it has moved -- `release.yml` or a workflow
  it calls, the packaging metadata, `MANIFEST.in`, `normalize_sdist.py`,
  the trusted publisher registration, a new file the distribution has to
  carry. A cycle that touched the module and the prose is one the tag's own
  run judges as well, since every job up to `publish-pypi` is the same job;
  what the file asks is that skipping it be stated in the release pull
  request rather than left to be inferred.
- **`test-passed` and `integration-passed` skip a cancelled run instead
  of failing it.** Both carried `always()`, so a run the next push's
  concurrency group already superseded -- every dependency reporting
  `cancelled` -- still reached the "Fail unless every job above
  succeeded" step and turned that into a required check with no defect
  behind it, red beside the newer run's green on the same head sha.
  `always()` becomes `!cancelled()` in both jobs' condition; a skipped
  required check satisfies branch protection the same as a passing one,
  `integration.yml` already recording that for its own `paths`
  filter. The step-level condition inside each job, which fails the
  gate on a dependency cancelled on its own without the run itself being
  cancelled, is unchanged.
- **A closed pull request's run no longer lands in its merge's own push
  run's concurrency group.** `test.yml`, `lint.yml`, `docs.yml` and
  `integration.yml` group by `github.ref` alone, and every one carries
  a comment saying a `pull_request` run lands in a different group from
  a `push` run and so cannot cancel it -- true for `opened`,
  `synchronize` and `ready_for_review`, not for `closed` on a merged
  pull request, where `github.ref` resolves to the base branch's ref
  instead of `refs/pull/N/merge`. The two events fire within about a
  second of each other on every merge, and after #136 landed, its own
  `docs` push run for the merge commit was cancelled two seconds after
  being created, before any job started -- required checks reading
  `cancelled` for a commit the run that got to run never tested. The
  group is now `github.event.pull_request.number || github.ref`: a
  pull_request run of any action, closed included, groups by the pull
  request's own number instead, which cancels that same pull request's
  earlier run exactly as `closed` was added for, and cannot equal any
  push's `github.ref`. `links.yml` gets the same fix though it has no
  push trigger to collide with, its `schedule` and `workflow_dispatch`
  triggers resolving to the same ref a closed run does.
- **`HISTORY.md` is `RELEASE_NOTES.md` now**, mirroring sibling
  repository btclib's issue #1011 (PR #1039). Its own H1 always read
  `# Release notes`; the filename did not, and in common usage the two
  words that were split here name the same file, where a project that
  does split them puts it the other way round — [Keep a
  Changelog](https://keepachangelog.com/) defines CHANGELOG.md as the
  curated, human-facing list, which is what this file already is.
  `CHANGELOG.md` is unchanged: it is the file whose name and contents
  already agree, and every entry it has ever made about the old name
  stays written as it was true then.

  The load-bearing references moved with it: `release.yml` lifts the
  GitHub release notes out of the tag's own section by filename, and
  `version-check` refuses a tag whose heading is not retitled, in both
  files it reads by name. `.gitattributes` keeps `merge=union` under the
  new name, so a parallel release-note bullet still resolves without a
  conflict. `docs/source/history_link.md` moves to
  `docs/source/release_notes_link.md`, its toctree entry relabelled
  `RELEASE NOTES` to match the other entries' pattern. This repository
  has no website config of its own to redirect through, so the old
  `HISTORY.md` path 404s rather than forwarding anywhere; git history is
  where the old name stays reachable.

## v2026.8.13

### Added

- **`assert_chain`**, the check `verify_chain` makes, as a method a caller
  can invoke at a moment of its own: a client built against an explicit url
  -- a node on another host, one behind a proxy -- gets what `from_chain`
  would have asked for it. `from_chain(verify_chain=True)` is now this
  method, so there is one implementation and not a second copy in whatever
  library wraps this one.
- **signet is identified by its challenge**, which is the half of that
  check a chain name cannot make. Core reports `signet` for the default
  signet and for every custom one alike, so two nodes sharing nothing but
  the shape of a challenge answer the same string; `assert_chain` compares
  the p2p magic the challenge derives, taking the node's from the
  `signet_challenge` member of `getblockchaininfo` and the caller's from
  the new `signet_challenge` keyword, or from the default signet when none
  is given. A challenge off signet is refused before the round trip, there
  being nothing a reply could settle; one passed with `verify_chain` off is
  refused as well, being the one argument that would otherwise quietly do
  nothing -- every signet answers on 38332 and keeps its cookie in the same
  subdirectory, so the challenge changes nothing but the check. A node too
  old to report the member, or reporting one that is not hex, is a
  `FetchError`: the check could not be made, which is not the same as
  making it and passing.
- **`magic_from_chain`** and **`magic_from_signet_challenge`**, the two
  facts that check rests on, published for a caller with a use of their
  own -- a p2p handshake, a comparison against another implementation's
  table. `_MAGIC_FROM_CHAIN` is `pchMessageStart` per chain from Core's
  `src/kernel/chainparams.cpp`, in the byte order Core writes it there, and
  keyed by Core's chain names like the port and the datadir subdirectory
  beside it. `magic_from_signet_challenge` is `SigNetParams`' own rule --
  the first four bytes of the sha256d of the challenge script serialized
  with its CompactSize length -- and takes hex or the bytes it spells,
  refusing anything else: `bytes(71)` is 71 zero bytes rather than an
  error, so a challenge that arrived as a number would have been hashed as
  a script of that length. The table's signet entry is a copy of the
  constant Core states, with a test deriving it from
  `DEFAULT_SIGNET_CHALLENGE` -- so the constant and the rule are held to
  agreeing, rather than the entry being a computation nothing would catch
  being wrong. A challenge above 65535 bytes is refused rather than
  serialized: consensus caps a script at 10000, so the longer CompactSize
  forms cannot arise for one, and refusing keeps the two forms written here
  the whole of the encoding.
- **`DEFAULT_SIGNET_CHALLENGE`**, the block challenge of the signet
  everyone means by "signet" -- the `bin` a node started without
  `-signetchallenge` uses, from `SigNetParams`. What makes it worth
  publishing is that it is the one signet a caller can name rather than
  describe.

### Repository

- **The README says who uses this client**: btclib, which declares it a
  dependency in its own `pyproject.toml`. A reader deciding on a package
  that depends on nothing has its tests and its badges to judge it by, and
  neither of those says whether anything runs it.
- **The index-wait step of `published.yml` names its shell**, `bash`, where
  it named none and a Windows runner picked pwsh: `for attempt in $(seq
  20); do` is a `ParserError` there, before a single curl runs, so all five
  Windows cells of the install-check matrix failed the same step on
  v2026.8.12's release run while every Linux and macOS cell passed. The two
  steps after it already carried `shell: bash`; this was the one the
  pattern had not reached.
- **CONTRIBUTING.md states what a merge requires**: an open issue the pull
  request closes with `Closes #N`, and an approving review from somebody
  other than the author, GitHub allowing no self-approval. It also states
  the four commit-level guarantees the `main-integrity` ruleset enforces on
  every push with no bypass actor -- a verified signature, linear history,
  no force push, no branch deletion -- so a contributor learns that an
  unsigned commit is rejected before it is something to review, rather than
  from the push that bounces.
- **RELEASING.md lands the release by a signed local squash**, where it
  said "Squash and merge" as if the button were available. It is not: the
  review branch protection requires cannot come from the author, there is
  no second maintainer, and a bypass would still have GitHub compose the
  commit and sign it with the web-flow key rather than the maintainer's.
  The steps are the ones every maintainer-only commit here already takes --
  squash in a worktree, sign, push to `main`, then close the pull request
  and delete its branch by hand, which is what the button would otherwise
  have done.
- **Two release-day failures RELEASING.md had no answer for** are written
  down with theirs: a job left `queued` for tens of minutes on
  `ubuntu-latest` is the org's shared Actions concurrency, not this
  repository's to fix, and is waited out rather than cancelled into a race
  with itself; a `github-release` job reporting `skipped` while both of its
  needs succeeded is rebuilt by hand from the run's own artifacts, digests
  compared against PyPI's, since `gh run rerun --job` refuses a skipped job
  and re-running the workflow would ask PyPI for a second upload.

## v2026.8.12

### Added

- **`RpcChannel`**, an opt-in attribute-style façade over a client's
  `call`: `channel.getblockcount()` for `client.call("getblockcount")`,
  positional arguments the sequence form of `params` and named ones the
  mapping form, never both at once. `request_timeout` and `max_body_size`,
  `call`'s own keyword-only controls, are reserved and forwarded to `call`
  rather than reaching the node as a named parameter, and every name
  starting with `_` -- dunders included -- is an `AttributeError` instead
  of a request: without that guard `copy.copy` and `copy.deepcopy` turn
  into a bound call for `__setstate__` or `__deepcopy__`, verified against
  a transport that raises on any request rather than assumed.
  `BitcoinCoreRpcClient` itself keeps its explicit `call(method, params)`
  surface unchanged; see COMPARISON.md's "Dynamic dispatch" for why the
  façade lives here rather than in a vendoring caller's own copy.
- **`verify_chain`**, an opt-in keyword on `from_chain`: after building
  the client, calls `getblockchaininfo` and compares its `chain` field to
  the one `from_chain` was given, raising `BtcRpcValueError` on a
  mismatch. Off by default, since `from_chain` otherwise asks the node
  nothing; a cookie or a datadir authenticates the node it names, not the
  chain it is running, and `-chain=test` under a cookie or a datadir
  carried over from a `main` setup is what this catches instead of a
  wrong-network call succeeding silently.
- **`cookie_path_from_chain`**, the path of the cookie file a chain's node
  writes: a datadir, the subdirectory `datadir_subdir_from_chain` names,
  and `.cookie`, which is `COOKIEAUTH_FILE` in Core's
  `src/rpc/request.cpp`. The datadir defaults to `default_datadir`, asked
  at the call as `from_chain` asks it, and where there is no absolute base
  to answer with, `BtcRpcValueError` naming `datadir` rather than a path
  resolved against the working directory. `from_chain` derives its own
  `cookie_path` with it; what it is for is the caller `from_chain` cannot
  serve -- a node started with `-datadir=` somewhere else, or one reached
  at a url of the caller's, which is the constructor and derives nothing
  -- who had the two tables published and the name of the file to write
  out, that being the one of the three facts no function here stated.
- **`CookieNotFoundError`**, a `FetchError` for a cookie file that is not
  there. bitcoind writes one while it runs with its rpc server enabled, so
  an absent cookie is a node that is not running -- or `bitcoin-qt`
  without `server=1` -- where the four other cookie failures (unreadable,
  oversized, non-ascii, malformed) are a file to go and look at. Since it
  derives from `FetchError`, an `except FetchError` catches it as before;
  what the class buys is the caller that says "start the node" for this one
  and names the file for the rest, instead of reporting both as a file to
  inspect. `cookie_auth` raises it for `FileNotFoundError` alone: ENOTDIR
  stays the unreadable failure, a datadir that is no directory being
  configuration the node starting does not fix.

### Changed

- **An `HTTPError` with no headers is a status and a body**, where
  `http_request` left it as `AttributeError: 'NoneType' object has no
  attribute 'get'` -- from reading the announced `Content-Length` off
  headers that are not there. `HTTPError.headers` answers the `hdrs` it was
  built with, so the shape comes from a transport of a caller's own, which
  the module docstring invites onto that path: a test double standing in for
  a busy node is the ordinary way to write one, and `None` is what gets
  passed for a field the double has no opinion about. The announced size is
  now read only where there is something to read it from, the bounded read
  being unchanged and absent `Content-Length` already the ordinary case for
  a chunked reply. So the promise that everything below the HTTP status is a
  `FetchError` holds for that exception too -- the same one carrying an
  `HTTPMessage` was always read as intended, which is why nothing in the
  suite reached it.
- **`urlopen_transport` checks the scheme, the timeout and the limit before
  it opens anything.** It is public and it takes a `Request` a caller
  built, where `http_request` checks the url it is handed and then builds
  one -- so a caller reaching the transport directly had no scheme boundary
  at all: `urlopen_transport(Request(Path("LICENSE").resolve().as_uri()),
  ...)` read the local file and answered with its bytes, `urlopen` speaking
  `file:` and `data:` as well as http(s). A url that reaches configuration
  or untrusted input could therefore turn this transport into a local-file
  reader, and a `timeout` of zero or a negative `max_body_size` was refused
  after the resource had been opened rather than instead of opening it. The
  refusals are `http_request`'s own, in the same words; nothing about
  `http_request` changes.
- **`verify_chain` reads the `getblockchaininfo` reply rather than indexing
  it**, so a result that is no mapping, or one whose `chain` is not a
  string, is a `FetchError` naming the unreadable reply: `result["chain"]`
  on an array is `TypeError: list indices must be integers or slices, not
  str` and on a mapping without the member a `KeyError`, both arriving from
  underneath a library whose every other unreadable answer from a backend is
  a `FetchError`, and neither inside `except FetchError`. The mismatch of a
  well-formed reply is still the `BtcRpcValueError` naming both chains: that
  one is the caller's configuration, where this is what the node sent.
- **`for_wallet` refuses a client that is already a wallet endpoint**, where
  it appended a second one: `client.for_wallet("hot").for_wallet("cold")`
  built `http://127.0.0.1:8332/wallet/hot/wallet/cold`, a path Core does not
  serve, so the mistake surfaced as an `HttpError` from the node about a
  path rather than as a refusal at the line that made it. The message names
  the client to call it on -- "call for_wallet on the client it was derived
  from" -- that arrangement, one client per wallet derived from the one
  built for the node, being what `for_wallet` recommends and what deriving
  from a wallet client is the mistaken form of. A url a caller wrote by hand
  ending in `/wallet/hot` is refused by the same check, the constructor
  taking the endpoint of a node; a wallet *named* `wallet` is still a name
  to add, `/wallet/wallet` being the endpoint of a wallet a filesystem
  allows. Replacing the trailing segment instead of refusing is rejected on
  the grounds the rest of this class refuses on: it would make
  `for_wallet("hot")` and `for_wallet("hot").for_wallet("cold")` two
  spellings of one endpoint, and nothing tells a caller who meant that from
  one who lost track of which client they were holding.
- **`default_datadir` answers Core's datadir for the platform it runs on**,
  not Linux's on all of them: `%APPDATA%\Bitcoin` on Windows,
  `~/Library/Application Support/Bitcoin` on macOS, `~/.bitcoin` on
  everything else, which is `GetDefaultDataDir` in Core's
  src/common/args.cpp -- the `#else` branch there being what a platform
  absent from the table takes here. So `from_chain` derives a cookie path
  Core actually writes on the three, where on two of them it derived one no
  node was ever going to have written and failed with a "no such file" that
  reads as a node that is down. `None` is still the answer where there is no
  absolute directory to hang the datadir off, and Windows has one more way
  to be in that state than a home directory does: `APPDATA` unset, which
  `Path.home()`'s fall back to the passwd database has no equivalent of.
  `from_chain`'s refusal names it.
  The argument the old docstring made against this -- "guessing per platform
  would put two branches here that no test on a third can reach" -- is
  answered by the shape rather than waved away: the three directories are a
  table keyed on `sys.platform`, read at the call, so one run of the suite
  patches its way through all three rows and the coverage gate stays at 100
  on a single operating system. A chain of `sys.platform ==` comparisons
  would not have done: mypy narrows those to the platform it is aimed at and
  stops type checking the rest, and a table is what keeps every row in front
  of the checker as well as the runner.
- **An absent cookie file is reported as absent**: `no rpc cookie file
  <path>: bitcoind writes one while it runs with its rpc server enabled`,
  where it was `unreadable rpc cookie file <path>: [Errno 2] No such file
  or directory` -- a message that says the file was found and would not
  open, for the case where nothing is at the path at all, and that leaves
  the reader to work out from an errno what a node writing the file would
  have meant. `CookieNotFoundError` above is the class it now carries; a
  caller matching on the text of the old message is what this breaks.
- **`default_datadir` is public**, no longer `_default_datadir`. `from_chain`
  already called it to find the live `HOME` at the moment of the call rather
  than the one `DEFAULT_DATADIR` froze at import; a caller deriving its own
  datadir-relative path -- a wallet directory, a second cookie under
  `datadir_subdir_from_chain` -- needed that same answer and had no way to
  ask for it short of importing the underscored name or copying the
  function. No behavior changes; the name in `__all__` is the only diff.
- **COMPARISON.md's "Dynamic dispatch"** no longer calls the façade a
  vendoring caller's own to write: `RpcChannel` above is the reason, and
  the section now says why it is offered here instead.
- **The module's docstrings and comments are shorter**, and no reason is
  stated twice: each now sits in one place and is pointed at from the
  others -- the retry policy in the module docstring, which `HttpError` and
  `call` refer to; the four obligations of a caller's transport in
  `HttpTransport`, where the comment above it repeated them; the
  truncation of a failure's body in `MAX_ERROR_BODY_SIZE`; the datadir and
  the platforms it is right on in `default_datadir`, which
  `DEFAULT_DATADIR` and `from_chain` refer to. `FetchError` names its two
  subclasses once, rather than each of them repeating that it is one. Two
  statements were also wrong: the notifications paragraph named a
  `_request` function this module does not have, and the client's class
  docstring said nothing here asks the node which chain it is on, where
  `verify_chain` above does exactly that on request.
- **The upstream url in the module docstring is right again**: it named
  the repository `btclib-bitcoin-core-rpc`, which this one was renamed
  from, and the `master` branch, which is now `main`. Both spellings still
  redirect, so nothing was broken by them -- but that url is what a
  vendored copy is asked to record beside itself, and a copy is not a
  thing to leave depending on a redirect. The raw url for a release, on
  the same line, carried the same stale repository name.

### Repository

- **`normalize_sdist.py` normalizes the member modes too**, 0644 for a file
  and 0755 for a directory, beside the timestamp and the ownership it
  already rewrote. The mode came from the working tree, so the umask of the
  checkout reached the published archive: a verifier following RELEASING.md's
  "Rebuild a release from its tag" from a checkout whose files carry group
  write got a digest mismatch on an archive whose content matches byte for
  byte, and is told to read a mismatch as a rebuild that ran a newer
  setuptools, or as tampering. It is digest-preserving for what CI
  publishes, a runner's checkout carrying those two modes already, so the
  digests already attested stay the digests a rebuild produces. Nothing in
  the sdist needs the executable bit -- no source file here opens with a
  shebang, which `.pre-commit-config.yaml` records as a decision -- so one
  mode for files and one for directories is the whole of it.
  `tests/normalize_sdist_test.py` asserts the property the script exists
  for, on archives staged by hand: two whose members differ only in a mode
  normalize to the same bytes, which no build of this tree can check on its
  own, carrying the modes of the checkout it ran in.
- **`pyproject.toml` says where the version is declared and stops there.**
  The comment above `version` also restated the convention for the
  placeholder between releases -- "the version just released, with its
  trailing component bumped by one, or `.1` appended if it had none", which
  would be `2026.8.9` where the declared value is `2026.9`, the month -- and
  went on to say the placeholder is shaped like a release on purpose, where
  `release.yml`'s version-check job says the opposite in the job itself and
  refuses a tag of that shape. RELEASING.md's "Which version string is
  which" states the convention correctly and is now the one place that
  answers it. The calendar-versioning note and the no-leading-zero note are
  true of this file and stay.
- **Three stated counts are gone from `pyproject.toml`**, the command that
  re-derives each of them staying: the parallelism note's test count, which
  moves with every merge and said 298 against 306, and the site counts of
  the `PLR2004` and `TRY003` ignore entries, which said 47 and 37 against 48
  and 38. `PLR0913`'s said 4 and still measures 4, and goes with them for
  the same reason: what argues for those three waivers is the shape of the
  finding, and a number nothing checks is a claim waiting to be false.
- **The gate that talks to a live node is `integration`**, the name btclib
  gives its own, where it was `rpc-smoke`: `integration.yml`, an
  `integration` job, an `integration: every job passed` aggregate and a
  required context of that name. `rpc-smoke` described two of the six cells
  -- the two that grow a regtest chain and read the replies off the wire --
  while the other four start Core on the chains regtest is not and check
  only that `-chain=<name>` is accepted, so a reader holding the two
  repositories side by side had two names for one question. What the
  workflow runs keeps its own name, `.github/scripts/rpc_smoke.py` being a
  smoke script and not what the rule names. Renaming a required check is
  the change a pull request cannot make alone: REPOSITORY.md has the order,
  and the rule moved first
- **The weekly sentinels run on btclib's days.** `latest.yml` and
  `macos.yml` move from Thursday to Wednesday and dependabot from Friday to
  Thursday, keeping the day between them that made the pairing worth
  having: the sentinel reports, and the pull requests open the morning
  after, so each is a diff whose result is already known. What changes is
  which weekday that is, and only so that the same question is asked on the
  same day across the three repositories instead of on two calendars
- **REPOSITORY.md's branch protection is read back from the rule** rather
  than remembered. It said `enforce_admins` was on -- "the rule holds for
  an administrator too, which is what makes it a rule" -- and that no
  approving review was required, calling that omission the deliberate half
  of the setup. `gh api
  repos/btclib-org/bitcoin-core-rpc/branches/main/protection` answers
  `enforce_admins: false` and one approving review with
  `dismiss_stale_reviews`: the opposite arrangement, where the review is
  required and the administrator bypass is what lets the maintainer's own
  pull request merge past a review nobody can give it, GitHub not allowing
  self-approval. The paragraphs that argued from the old shape argue from
  this one, and the two that reasoned "with `enforce_admins` on there is
  nothing to override" -- the deadlock warning and the rename procedure --
  say what the bypass costs instead. The rest of the file was checked the
  same way and holds: the five contexts with their app bindings,
  `delete_branch_on_merge`, the `pypi` environment's `v*` tag policy,
  release.yml's one elevation per job, and the six security settings
- **The suite runs serially again.** `-n auto --dist worksteal` cost more than
  it saved here: nine interleaved runs each put the medians at 0.50s serial
  against 0.90s parallel, and 0.65s against 1.23s under coverage, with CI
  agreeing on ubuntu and on the coverage job. 298 tests that open no socket
  finish before ten workers have started, which is the opposite of the
  condition the flag exists for -- checksig's suite starts a node per test
  and gains about 4.5x from the same setting. pytest-xdist stays installed
  because the mutation session passes `-n0`, and without the plugin pytest
  rejects the flag rather than ignoring it
- **Code scanning is a workflow in the tree**, `.github/workflows/codeql.yml`,
  rather than GitHub's default setup. It was the only required check whose
  definition a diff could not review: the setting generates a workflow it
  does not show, where every other check on `main` is a file here with its
  actions pinned to commit SHAs. What the setting held is reproduced rather
  than re-chosen -- `gh api
  repos/btclib-org/bitcoin-core-rpc/code-scanning/default-setup` answers
  `languages: [actions, python]`, `query_suite: default` and `schedule:
  weekly`, and those are the matrix, the unset `queries` input and the
  Tuesday cron. One job per language, so a failure names the language, and
  `codeql: every job passed` aggregates them for a rule that has to name an
  outcome rather than a matrix cell. The two are exclusive at the upload and
  not at the start -- `init` succeeds and `analyze` is refused, "CodeQL
  analyses from advanced configurations cannot be processed when the default
  setup is enabled" -- so this cost a five-step switch a person performed,
  the analysis red until step 2 of it. That switch is done: default setup
  answers `not-configured`, the rule ends in `codeql: every job passed` at
  `app_id` 15368 where it named the `github-advanced-security` context
  `CodeQL`, and both analyses report green. REPOSITORY.md's "Turning default
  setup off without deadlocking" is the order it went in and the order to
  repeat if the setting comes back; dropping the `CodeQL` context before
  disabling the setting is what keeps the rule from waiting on a check whose
  result is not the tree's to produce, that context being the
  `github-advanced-security` app's. It does not stop with the setting: it
  still reports on a pull request's head, `neutral` and summarised
  `1 configuration not found`. A generated
  `dynamic/github-code-scanning/codeql` workflow outlives it too, uploading
  code quality results rather than security ones -- a separate setting the
  `code-scanning` endpoint does not report
- **CONTRIBUTING.md's workflow table names what `release` calls** instead of
  counting it. The count said six where `grep -n 'uses: ./.github/workflows'
  .github/workflows/release.yml` finds five, and a row added above it would
  have made "the six above it" wrong a second way. The `workflow_dispatch`
  sentence beside it went the same way: it excepted the gates, and
  `grep -c workflow_dispatch: .github/workflows/*.yml` reports every
  workflow taking it
- **The `PATCH` REPOSITORY.md documents for the required-check list runs**,
  where the spelling it carried could not: `gh api -f` sends every value as
  a string and that endpoint types `app_id` as an integer, so
  `-f 'checks[][app_id]=15368'` earns `422 Invalid request. For
  'properties/app_id', "15368" is not a null or integer`. The body is JSON
  on stdin instead, `--input -`. Where that command is used is what makes an
  unrun one expensive: renaming a required check cannot be done in a pull
  request, so the rule moves first and by hand, and a 422 at that moment
  invites the whole-object `PUT` the same file warns drops the signatures.
  The list in it is the rule's own, read back by the `gh api` now beside the
  table -- `rpc-smoke: every job passed` was in that table and missing from
  the command, so the command as written would have dropped a required check
  rather than moved one
- **A pre-commit rev that is not a released version fails the gate.** The
  weekly autoupdate pull request has twice offered the same two moves this
  configuration must not take -- typos onto `v1`, a floating major tag its
  repository keeps beside the versioned one, and pyroma onto `5.1b1`, 5.1
  having no released tag -- and twice they were caught by hand, the second
  time after the merge, which is why the commit is reverted here. A local
  pygrep hook now names them by line instead. pre-commit itself warns that a
  mutable reference "is not supported" and exits zero anyway, which is the
  difference between the warning and this hook. A commit SHA stays
  acceptable: the pattern requires a prerelease marker to end the value
- **A merge no longer depends on bitcoincore.org answering.** The bitcoind
  archive `rpc-smoke.yml` downloads is cached across runs, keyed by the
  sha256 the matrix already pins rather than by the version, so a key can
  only ever hold the bytes it names. What it saves is nine seconds a cell,
  measured; what it removes is five fetches of Core per pull request from a
  server nobody here runs, which arrived with that workflow becoming a
  required check. The digest check and its negative control still run on a
  restored archive exactly as on a downloaded one -- verified rather than
  trusted is the property, and a cache is a mutable store
- **A pull request waits about three minutes instead of eighteen, and the
  wait was never work.** One run of the full matrix is 45 jobs, 17 minutes
  of compute and 212 minutes of queueing: no cell runs longer than a minute,
  while the two macOS images wait 15.7 and 13.1 minutes on average for a
  runner against 0.1 to 0.3 for ubuntu and windows. So `test.yml` keeps all
  seven interpreters and drops to four platforms, and the new `macos.yml`
  runs the two macOS images against the same lock weekly, on demand, and
  from a release -- which is what keeps a macOS regression from being
  published while nobody waits for one. It is scheduled the same morning as
  `latest.yml`, half an hour before, so the two read as a difference: red in
  both is the platform, red in `latest` alone is the upgrade
- **`rpc-smoke.yml` gates a merge**, where it gated only a release: the
  reason it did not was a cost the run log does not support, 12 to 24 seconds
  a cell and about 90 seconds for the workflow, live bitcoind downloads
  included. Its `paths` filter had to go with the promotion -- a required
  check that never runs blocks a merge where a skipped one satisfies it --
  so every pull request now pays those 90 seconds, and gets the one claim a
  recorded reply cannot make. The rule names its aggregate,
  `rpc-smoke: every job passed`, and not six cells
- **`published.yml` is called by `release.yml`** once PyPI has accepted the
  files, with the tag's version, and waits for the index to serve that
  version before installing -- so it can no longer pass by testing the
  release before this one, which is what the dispatch RELEASING.md asked for
  by hand could do. Not a `workflow_run` trigger, which zizmor rates
  dangerous and rightly: that runs the default branch's copy on a push
  nobody reviewed, where a call runs inside the release that gated it. Its
  schedule goes from weekly to monthly, the release path now answering the
  question the weekly was standing in for
- **Every CI job has a name, and the names say what the job answers.** The
  ids lose a suffix that distinguished nothing -- `test-py`,
  `coverage-py` and `dist-py` become `suite`, `coverage` and `dist`, there
  being one language and one package here -- while the suffix that does name
  a variant stays, `suite-latest` and `install-published` among them. Every
  job of `test.yml` and `release.yml` now declares a display name, where
  eleven of them showed their id in the checks list beside the sentences the
  other workflows wrote. The aggregate gate is `test: every job passed`,
  which carries its workflow because branch protection keys a context by
  name alone and two workflows with a job named the same thing produce one
  ambiguous check; REPOSITORY.md has the `PATCH` that moves the rule and the
  reason a rename cannot be done in a pull request
- **`release.yml` has a concurrency group**, the last workflow without one
  and the only one whose runs have side effects: two runs at once are two
  attempts at the same publication. `cancel-in-progress: false`, against
  every other workflow here, and the rule behind both is now written down --
  a superseded run is cancelled where its subject is the commit, and kept
  where its subject is a version on an index, an attestation or a release
- **The distribution files are reproducible**: a rebuild of a released tag
  is the same bytes as what was published, so the provenance attestation
  can be verified against a file the verifier built rather than one they
  downloaded. `release.yml` exports `SOURCE_DATE_EPOCH` from the commit
  date, which is the whole of it for the wheel, and runs
  `.github/scripts/normalize_sdist.py` for the sdist -- setuptools stages
  that archive in a directory it creates at build time and tars it as the
  first member, whose sub-second timestamp `SOURCE_DATE_EPOCH` does not
  reach and whose PAX record therefore changes length between two builds
  of one commit. The script rewrites member metadata and no content.
  RELEASING.md has the rebuild command, and the two bounds on the
  guarantee: the build backend is resolved rather than pinned, and a
  TestPyPI rehearsal is a different version by construction
- **The documentation build is a workflow of its own**, `docs.yml`, where it
  was the second job of `lint.yml`: a failed sphinx build and a failed hook
  are two different verdicts, and a workflow each is what gives them a badge
  each and a line each in the checks list. The job keeps its name, `Build the
  documentation`, so the required check on `main` did not have to move -- a
  context is matched by name and not by the workflow that reported it, which
  is what makes moving a job free where renaming one is not. `release.yml`
  calls the new workflow alongside `test.yml` and `lint.yml`, so a tag still
  cannot publish docstrings that read the docs would fail to render
- **The distribution files attached to a GitHub release carry
  provenance**, where until now only the copies on PyPI did: the publish
  action generates PEP 740 attestations for what it uploads to the index,
  and the byte-identical wheel and sdist on the releases page carried
  nothing, so whoever pinned to a release asset url or mirrored the page
  had no way to check where the files came from. `release.yml` gains an
  `attest` job -- `actions/attest`, one SLSA build provenance statement
  covering both files, signed with a short-lived Sigstore certificate --
  and `gh attestation verify <file> --repo btclib-org/bitcoin-core-rpc`
  is what checks it. The signed bundle is attached to the release too, so
  `--bundle <tag>.attestation.jsonl` verifies the same signature without
  asking the attestations API for it. The digests are the index's own,
  the job downloading the `dist` artifact rather than rebuilding it.
  A job of its own and not two more permissions on `github-release`:
  `id-token: write` and `attestations: write` stay off the job that
  writes releases, and further off the job that runs the build backend.
  It runs after whichever publish job ran, so a dispatch from an
  arbitrary branch signs nothing the `testpypi` environment approval did
  not already let through -- and the TestPyPI rehearsal exercises it,
  which on the release path would otherwise happen for the first time
  after PyPI has the files and the tag can no longer be moved.
- **`main` is the only branch**, renamed from `master` and now the whole
  of the model: `dev` is gone, every change reaches the trunk through a
  pull request -- a contributor's, a maintainer's, Dependabot's and
  pre-commit.ci's alike -- and a release is a tag on `main` rather than a
  branch merged into it. What two branches bought was somewhere bot
  commits could land with no required check in front of them; what they
  cost was a permanently draft release pull request, a rebase merge whose
  new SHAs left the two branches equal in content and unequal in identity,
  and the realign that then had to force-update `dev` behind a rule
  blocking force pushes that an administrator is not exempt from. One
  branch pays none of that, and gates every commit on the same four
  checks. Dependabot declares no `target-branch` and pre-commit.ci no
  `autoupdate_branch`, both taking the default branch; the draft exemption
  the release pull request needed (`|| github.base_ref == 'master'`, in
  five workflows) goes with it, so a draft runs no CI at all and nothing
  is exempt; `test.yml` and `lint.yml` push-trigger on `main`.
  `REPOSITORY.md` holds what the branch rule requires and why,
  `CONTRIBUTING.md` how a change lands, `RELEASING.md` how a release is
  cut from one branch.
- **`main`'s branch rule requires no approving review, and applies to
  administrators.** The four checks are unchanged and `strict` with them,
  as are required signatures, linear history, blocked force pushes and
  blocked deletions; what goes is the one approving review, which GitHub
  does not let an author give themselves -- on a solo-maintainer
  repository it either stops every merge or is waved through on every
  merge, and a rule whose normal operation is its own bypass gates nothing
  while reading as though it does. `enforce_admins` is on in its place, so
  what is left holds for everyone.
- **Squash is the only merge method the repository enables.** The merge
  commit was refused by `main`'s required linear history already, so
  turning it off takes away a button that could not have worked; the
  rebase merge could have, and what it would have done is replay a
  branch's commits onto a trunk whose rule is one commit per landed
  change. What a single method takes away is not the choice on a pull
  request in front of somebody: GitHub preselects whichever was used last
  and offers the same dropdown in the dialog that switches auto-merge on,
  hours before anything merges and with nothing asking again -- so "read
  the button before pressing it" was advice three files gave and none
  could enforce. REPOSITORY.md gains the section, with the two fields that
  shape the commit a squash writes; CONTRIBUTING.md and RELEASING.md said
  all three methods were enabled and say what holds instead.

## v2026.8.8

### Added

- **COMPARISON.md**, the case for this client against `AuthServiceProxy`:
  the comparison table row by row, the three rows that carry the weight --
  amounts, credentials and errors, enforced by construction rather than left to
  discipline -- and the consequence of the typed errors that nothing announces,
  a refused connection arriving as a `FetchError` and no longer as the `OSError`
  an `except` clause was written for. Then the three features this client does
  not have and what decides each: dynamic dispatch, which absorbs typos of the
  client's own surface and returns `Any` where the package ships `py.typed`;
  batching, whose correlation and partial failure JSON-RPC 2.0 section 6
  settles, and whose cost is a timeout covering several node operations, a
  `max_body_size` that stops mapping onto an answer, and a third parsing branch
  -- reachable through `http_request` and `auth_header` for the WAN link a batch
  pays on; and one connection per call, which is CPython's `do_open` setting
  `Connection: close` rather than a choice made here, negligible per call on
  loopback and socket churn in aggregate. The README's ["Migrating from
  `AuthServiceProxy`"](./README.md#migrating-from-authserviceproxy) is the
  line-by-line rewrite; this is why the rewrite is worth doing. Linked from the
  README, and from `docs/source/index.rst` alongside the other root documents.

### Changed

- **The timeout bounds the body of a failure too**, where
  `MAX_ERROR_BODY_SIZE` and the socket timeout bounded it alone -- and a
  socket timeout is per recv, so a peer sending an octet just inside it
  holds the call for as many packets as 64 KiB takes. `http_request` takes
  a `monotonic()` deadline before the transport call and reads the
  `HTTPError` through `_read_bounded`: an `HTTPError` forwards `read1` to
  the response it wraps and answers `headers` with the ones it carries, so
  it is read as the response it is. A page still arriving at the deadline
  goes back as its status with an empty body, which is what a page that
  cannot be read at all already did -- the status is the part a caller has
  a policy for. A transport of a caller's own is held to that deadline for
  the error body alone, that being the only part of such an exchange this
  module does the reading of.

  `_read_bounded` grows a `truncate` keyword, the two bounds differing in
  what they do at the limit: an answer over `max_body_size` is refused, a
  diagnostic over `MAX_ERROR_BODY_SIZE` is cut to it and answered, and an
  announced `Content-Length` over the limit is not grounds for refusal
  under `truncate` either.
- **`_read_bounded` accumulates into one `bytearray` now, not a `list` of
  chunks joined at the end.** A `list` keeps every chunk alive as its own
  object until the join, so a response near `max_body_size` sat in memory
  twice over -- once as the pieces, once as the joined result -- for as
  long as both stayed in scope; a single growing buffer replaces the
  pieces instead of standing beside a second copy of them. The one copy
  this function cannot avoid is `bytes(buffer)` at the end, since a
  `bytearray` is not the immutable value it promises: the docstring now
  says so directly, `max_body_size` bounding what is read and not the
  memory reading it costs, which is that bound plus the one copy the
  return type is worth.
- **`http_request`'s `timeout` is validated at the boundary now, and not
  only `max_body_size`.** `BitcoinCoreRpcClient` already refused a `0`, a
  negative number, `True` or a `NaN` for its own `timeout` and
  `request_timeout`, but `http_request` is public on its own, so a direct
  caller with a transport of its own reached the socket layer with
  whichever of those it passed. `_assert_valid_timeout` runs alongside
  `_assert_valid_max_body_size` now, before the request is built, so every
  public timeout argument is refused the same way and the transport is
  never reached with one that cannot work.
- **Three documented claims narrowed to what the code does.** The named
  parameter form was one "no attribute lookup can express", which a
  `**kwargs` façade expresses; what no attribute lookup can carry is both
  parameter forms together with the client's own per-call controls, and
  that belongs to [COMPARISON.md](./COMPARISON.md)'s account of the
  non-goal rather than to a migration example, so the claim is gone and
  the example stands on its own. A loop over `call` was the replacement
  for a batch without qualification, and it is an equivalent beside the
  node and not over a link where the round trip costs something, which is
  where a batch pays -- the README and the module docstring both say so
  now, the second because a vendored copy has no README beside it. And a
  connection per call "costs nothing" beside the node per call, while a
  great many of them are socket churn: RFC 9112 section 9.6 has the server
  initiating the close on `Connection: close`, so the node is what holds
  the sockets in TIME_WAIT, and the docstring now sends a caller polling
  in a loop to its own `transport` on loopback too and not only over
  `https`.
- **The between-releases placeholder is the month, `2026.9`, and no longer
  the last release with its trailing component bumped.** The old
  placeholder was shaped exactly like a release on purpose, which left one
  guard in front of it: `version-check`'s heading check against HISTORY.md
  and CHANGELOG.md. A version with no day cannot be published at all --
  the same `version-check` requires three components of anything tagged,
  and always did -- so the month-only shape puts a second, independent
  guard behind the first, and a checkout of `dev` stops reporting itself
  as a release it is not. `pyproject.toml`, `uv.lock` and the two
  work-in-progress headings move with it, and `release.yml`'s comment on
  the three-component check says which guard it now is.
- **RELEASING.md takes back eight steps from btclib's copy of it.** The
  rehearsal from `master` after the version bump, and the annotated tag
  that names the release commit and is read back with `git show` before
  the push, the argumentless `git tag` being one `cd` away from tagging
  the commit before the bump; the local gates as the evidence they are
  here, `test.yml` and `lint.yml` triggering on `pull_request` and a push
  to `master` alone, so a commit pushed straight to `dev` runs neither;
  the read-the-docs *builds* page, which a rendered page answering 200
  does not stand in for; the 100-commit ceiling on "Rebase and merge",
  past which the button reads `This branch can't be rebased` and the
  command line it wraps is what is left; the fast-forward that ceiling's
  `git merge-base --is-ancestor` also detects, which makes the realign
  step below it moot and is now the question that step opens with; the
  404 a `workflow_dispatch`-only workflow answers until its file reaches
  the default branch; `git tag --sort=v:refname`, without which `v2026.10`
  lists before `v2026.7`; and deleting a botched tag locally in every
  worktree, a tag being per-repository where a branch is per-worktree.
  `latest` gets the short form of btclib's paragraph, there being no
  sibling pin here for the long one.
- **`keywords` and the GitHub repository topics name the same things.**
  The keyword list had neither `zero-dependency` nor `vendorable`, which
  the topics already carried and which are two of the three things the
  README leads with; `bitcoin-rpc` is new to both, and is what somebody
  looking for this searches for. The order is by relevance rather than
  alphabetical, PyPI showing keywords as the metadata gives them; GitHub
  sorts its own, so there the order decides only which topic goes when the
  twenty it allows are full, which nine is well short of. Three candidates
  are left out, and the comment beside the list says why: `python`, which
  names no feature and repeats the `Programming Language ::` classifiers,
  `type-hints`, which repeats `Typing :: Typed`, and a chain name,
  `from_chain` carrying Core's defaults for all five. The `python` topic
  goes for the first of those reasons, leaving the two lists identical.

### Repository

- **The README's migration section pairs each `AuthServiceProxy` command
  with the one that replaces it, where it listed lines and left the reader
  to pair them.** One block held three changes, each of them a comment
  followed by two or three lines in no marked order: the `AuthServiceProxy`
  spelling and the one here were told apart only by the class name where a
  line happened to carry one, so the two `client.call` lines under
  `rpc.getblock` read as a sequence to run rather than as the same call
  twice, and the `for_wallet` change had no "before" line at all. It is now
  one block per change, each opening `# AuthServiceProxy` and continuing
  `# this client`, under a sentence of prose saying what moved and why --
  connecting, invoking a method, a wallet command, a batch and an error,
  the last two of which were prose with no command in them. `batch_`
  gains the loop that replaces it, spelled out. The claim that an unknown
  method "arrives at the node, not an AttributeError here" is gone with
  it: `AuthServiceProxy.__getattr__` builds a proxy for any name too, so
  the sentence named a difference that is not one, where what does differ
  is that a method name is data here and cannot collide with the client's
  own attributes. No count of the changes either, the old "four changes"
  having counted three blocks and a paragraph. Every `# this client` line
  was run against a stub transport before the section was rewritten around
  them, which is what the section had never been.

- **The README gained the badges it was missing -- `status`, `downloads`,
  `docs` and `pre-commit.ci` among them -- and now carries only the ones
  that can turn red.** None of the additions claimed something new:
  `pre-commit.ci` is the check already configured in
  `.pre-commit-config.yaml`'s `ci:` block and already running against
  `dev`; what was missing was the badge saying so. They read on three
  lines, in the order the reader asks for them: version, downloads,
  development status, license and supported interpreters first; test,
  lint, pre-commit.ci and the documentation build second; the repository
  and the `slack` channel third, "where is the code" and "where do I ask"
  being the two questions a reader has once the first two lines have
  answered theirs. Version and downloads are adjacent, both being PyPI
  reading back the same project, and `test` precedes `lint`, a red suite
  and a red linter not weighing the same. The badges that report no state
  -- `cal_ver`, `uv`, ruff, mypy, markdownlint-cli2 and `pre-commit
  enabled` -- name a choice rather than measure anything, so they open
  CONTRIBUTING.md, which is the file that says how each choice is enforced
  and what the command for it is; ruff is three of them, its formatter,
  its linter and its docstring rules being three gates with three
  documentation pages and three ways to fail, where one badge announced
  them as one. `pre-commit` closes that run because it is what runs the
  others, and the repository and `slack` badges close the line, a
  contributor wanting both. No `twitter` badge, which the sibling projects
  dropped too. The alternative text says what a badge means -- "PyPI
  version", "supported Python versions", "test workflow status" -- rather
  than naming the site that serves the image: it is the accessible name of
  the link, and a flat list has nothing else to carry the meaning. One
  badge per source line, which puts a badge change in one line of a diff
  and needs no `markdownlint-disable MD013`: the rule's 80 columns bind
  only where a space follows them, and in a bare URL none does. btclib and
  btclib-secp256k1 carry the same three lines and the same
  CONTRIBUTING.md run, which is what makes the three comparable; the badge
  sets differ only where the projects do.

- **The GitHub repository is `btclib-org/bitcoin-core-rpc`**, where it was
  `btclib-org/btclib-bitcoin-core-rpc`: the distribution took the shorter
  name in v0.1.0 already, and the repository read as the wrong thing to
  clone for a client that is not part of btclib for exactly as long as it
  kept the old one. GitHub redirects `git clone`, the web UI and most of
  the REST API from the old path, so nothing with it cached breaks
  outright; every URL this tree spells out regardless -- `release.yml`'s
  `github.repository` guard on the publish jobs, `pyproject.toml`'s
  `[project.urls]`, RELEASING.md's and REPOSITORY.md's `gh api` runbook
  commands, the README's badges and Links section, CONTRIBUTING.md,
  SECURITY.md, AUTHORS.md and both issue templates -- now names the new
  one, so none of it depends on the redirect staying up. PyPI's Trusted
  Publisher entry lives outside this tree and does not follow a GitHub
  rename automatically; RELEASING.md's setup step now records the new
  repository name, and the entry on pypi.org needs updating to match
  before the next release, or that release's OIDC handshake fails.

## v2026.8.7

### Added

- **`rpc_port_from_chain` and `datadir_subdir_from_chain`**, the port and
  the subdirectory Core gives a chain, which `from_chain` reads and a
  caller could not derive: `main` keeps its cookie in the datadir itself
  and `test` lives under `testnet3`, neither of them a name the chain name
  gives away. A node on another host, or one started with `-datadir=`
  elsewhere, is a url and a `cookie_path` the caller assembles, and these
  two are what it assembles them out of instead of a table copied from
  here. Functions rather than the dicts behind them, for the reason the
  vocabulary pair are functions: an unknown chain is refused where it is
  named, and a published dict is a table a caller can write to.

- **`Chain` and `Network`**, a `Literal` each for the five names of each
  vocabulary, and what `chain_from_network` and `network_from_chain` are
  now annotated as returning. Not what they take: an argument arrives from
  a config file or from `getblockchaininfo`, as a `str` no annotation
  narrows, so a parameter of that type would only mean a cast at the call
  site — the runtime refusal is what checks a name either way. Not an
  `Enum` either: both vocabularies are `str` in every place they are
  spoken, `-chain=` and a json body included, so an enum would be an
  island every caller converts at, and this file has to import on 3.10,
  where `StrEnum` does not exist and the `str, Enum` that stands in for it
  formats as `Chain.MAIN` inside an f-string.

- **`USER_AGENT`**, what `call` now sends as the `User-Agent` header:
  `bitcoin-core-rpc`, where urllib's default named the interpreter and
  identified neither this client nor the program running it. What a node's
  access log and any proxy in front of it record, the request `id` already
  marking the same call in the node's debug log. No version in it, for the
  reason there is none anywhere here -- the release tag is the version,
  and a copied file would carry whichever one it was copied from forever.
  Published so that a caller writing a transport of their own can send the
  same thing.

### Changed

- **every public name reaches the documentation.** `docs/source/api.rst`
  says the page lists the whole public interface, and it listed fourteen
  of the twenty-three names in `__all__`. `automodule` with `:members:`
  documents a class or a function by its docstring and a module-level
  assignment by the string literal that *follows* it; a `#` comment is
  neither, so a name carrying one is absent from the built page rather
  than undescribed on it. The nine were `COOKIE_USER`, `DEFAULT_DATADIR`,
  `DEFAULT_MAX_BODY_SIZE`, `DEFAULT_TIMEOUT`, `MAX_ERROR_BODY_SIZE`,
  `USER_AGENT`, `Chain`, `Network` and `HttpTransport` -- the last of
  which is the type a caller has to implement to pass a transport of their
  own, so the interface the module tells them to use was the one they
  could not look up.

  Each has a docstring now, and the `#` comment above it keeps the
  reasoning that is not a caller's business: the docstring states the
  contract, the comment says why not the alternative, which is the split
  CONTRIBUTING.md already draws between the two.
  `test_every_public_name_carries_a_docstring` fails on the next name that
  arrives without one.
- **a read asks for a chunk, not for the whole limit.** `read1` allocates
  what it was asked for, and the response narrows that request only where
  it knows how -- `HTTPResponse.read1` caps n at the remaining
  `Content-Length`, or at the rest of the current chunk, and does neither
  for a body the close of the connection delimits. Against a peer like
  that, `max_body_size` was paid in full on every reply however small,
  which is the limit behaving backwards: widening it to allow one large
  answer cost that much on each little one. Measured with `tracemalloc`
  against a local HTTP/1.0 server sending a fifty-octet reply with no
  announced length, peak allocation for one `call`:

  | `max_body_size` | before | after |
  | --- | --- | --- |
  | 8001024 (the default) | 8.27 MB | 0.34 MB |
  | 1024 | 0.14 MB | 0.20 MB |

  Core announces a length, so a call to a node was never the case that
  paid it; something in the way that does not is. Not a regression from
  the `read1` of the deadline change either -- the `read(max_body_size +
  1)` before it allocated the same, measured at the same 8.27 MB on the
  commit before. `test_a_read_asks_for_no_more_than_a_chunk` is what keeps
  the request bounded.
- **three arguments are checked where they are written**, which is
  `_checked_url`'s rule and the three that escaped it. A `transport` that
  is not callable built a client and failed at the first `call`, from
  inside urllib; a `cookie_path` that is no path left through pathlib's
  TypeError about `__fspath__`; a `wallet_name` that is not a string left
  through urllib's about `quote_from_bytes` -- and `for_wallet(b"hot")`
  did not fail at all, `quote` taking bytes, so it built an endpoint from
  a name nobody spelled. Each is a `BtcRpcTypeError` naming the argument
  now.

  `cookie_path` is annotated `str | PathLike[str] | None` with that, where
  it said `Path | str | None`. The runtime check is what `Path()` on the
  next line accepts, and an annotation narrower than the check is the
  disagreement that matters: a `PurePosixPath` worked and a type checker
  said it would not. Widening a parameter breaks no caller -- `Path` is a
  `PathLike[str]` -- and what the attribute holds is a `Path` either way.
- **`for_wallet` builds `type(self)`**, where it named this class. A
  subclass kept its type through `from_chain`, which builds with `cls`,
  and lost it at the one call whose whole subject is carrying this
  client's configuration over.
- **the timeout bounds the whole exchange**, where it bounded each socket
  operation. A socket timeout is reset by every packet, so a peer sending
  one octet just inside it held a call open until `max_body_size` octets
  had arrived -- with the default that is eight megabytes at a byte a
  time, and no number of seconds a caller could write said otherwise.
  `urlopen_transport` takes a `monotonic()` deadline before the connect
  and `_read_bounded` stops at it, so the wait is the timeout plus the one
  recv in flight when it passes. Refused as
  `still arriving when the timeout expired`, a FetchError like the other
  ways an exchange does not produce an answer. What it costs is a reply
  that legitimately takes longer than the timeout to arrive -- a large
  `getblock` over a slow link -- and `request_timeout` is what that call
  passes.

  The read is `read1` and not `read`, which is the half without which the
  deadline is decoration: the response reads through a `BufferedReader`,
  whose `read(n)` blocks until it holds *n* octets, so the whole drip
  happened inside one call and no check ran between packets. Measured
  against a server sending an octet every 0.3s under a one-second timeout:
  the `read` spelling returned only when that server stopped, the `read1`
  one at the deadline. `FakeResponse` in the tests answers the two calls
  differently for the same reason -- a fake whose `read` returned early
  cannot tell a bounded read from an unbounded wait.

  Two bounds are unchanged, and deliberately. A caller's own transport
  gets no deadline: two positional arguments have nowhere to carry one,
  and `HttpTransport`'s comment lists this with the rest of what such a
  transport owes. And the body of a *failure*, which `http_request` reads
  off the `HTTPError`, is still bounded by `MAX_ERROR_BODY_SIZE` and by
  the socket timeout alone -- a drip there is 64 KiB of diagnostic rather
  than eight megabytes of answer, and threading the deadline into that
  path is a change to the exception handling rather than to the read.
- **a refusal on size names `max_body_size`**, in all three places one is
  raised, where they said `more than the 8001024 allowed` and left the
  reader to find which knob carried that number.
- **`core_chain_from_network` and `network_from_core_chain` are
  `chain_from_network` and `network_from_chain`.** In this module `chain`
  is Core's vocabulary and `network` the BIP one -- `from_chain` is named
  for it, and so are the parameters of both functions -- so `core_` was
  spelling a distinction the names around it already carry. What it costs
  is a rename in a caller: the old names are gone rather than aliased, one
  release being a short enough life for a name that a second spelling of
  it is the worse thing to publish.
- **an unknown chain is refused as `unknown Core chain`** wherever it is
  refused, `from_chain` included, where that one said `unknown chain: ...
  These are Core's names, not the BIP ones`. The check there is now
  `rpc_port_from_chain`'s, so the three functions a chain name reaches say
  the same thing, and the three words say what the sentence did.
- **the class docstring says that a call opens its own connection.**
  urllib holds none, so every `call` sends `Connection: close` and
  connects again. Beside the node that is loopback and costs nothing; to a
  node over `https` it is a TLS handshake each time, which is a caller
  polling one in a loop wanting a `transport` of their own. Documented and
  not fixed: keeping a connection alive means a pool, its own
  thread-safety and its own eviction, none of which one bounded request
  needs, and `HttpTransport` is the seam a caller who wants all three
  already has.

### Tests

- **the five chains are checked against every table that takes one.** They
  are written down four times -- a port, a datadir subdirectory, a network
  name and a `Literal` each way -- and only the `Literal`s failed anything
  when one was forgotten, at a type check rather than here. A port with no
  subdirectory beside it derives a cookie path under a directory that is
  not the node's.

### Repository

- **the smoke script stops waiting on a credential the node refused.**
  `wait_for_rpc` retried every `FetchError` until `STARTUP_TIMEOUT`, and a
  401 is a `FetchError` -- so a wrong cookie was two minutes of polling
  followed by `no rpc answer in 120.0 s`, which names the symptom. It is
  the case `HttpError.status` exists for, and the script already asserted
  the property from the other side in `check_credentials_refused`. Every
  other status is still retried: a 503 from a full work queue is the one
  that does clear on its own, and the rpc error -28 of a node reading its
  index arrives as an `RpcError`.
- **`except (FetchError, RpcError)` is `except FetchError`**, there and in
  `stop`. `RpcError` and `HttpError` are both a `FetchError`, so the pair
  read as two families where there is one.
- **RELEASING.md asks griffe whether the breaking-change list is
  complete**, as a release step carrying the command. HISTORY.md promises
  that a break is announced there, the calendar version promising nothing,
  and until now nothing read that promise back: the suite judges the code,
  and review weighs what the notes say rather than what they leave out.
  griffe reads the public API at the previous release and at the tree and
  reports the breakage between them -- against v2026.8.6 it names
  `core_chain_from_network` and `network_from_core_chain`, which this cycle
  removed and HISTORY.md announces, so the first cycle the step applies to
  is one it passes. A step and not a hook, for the reason RELEASING.md
  gives: the comparison is against the previous *release*, so a deliberate
  break stays a finding until the release that announces it, leaving every
  pull request in between red for something no branch introduced.

## v2026.8.6

The first release.

### Added

- **the distribution ships `py.typed`**, so a consumer's type checker reads
  these annotations with no configuration at all. That marker has to sit
  inside a package directory, which is why the source is
  `bitcoin_core_rpc/__init__.py`: measured against a built wheel of each
  layout, a top-level module leaves `mypy --strict` reporting "missing
  library stubs or py.typed marker" and treating every name as `Any` --
  and a `py.typed` or a `.pyi` placed beside such a module changes
  nothing, mypy looking for the marker under `<module>/`. What it costs is
  that vendoring is now a copy *and a rename*, which the module docstring
  and the README both say.

### Changed

- **`BTClibValueError`, `BTClibTypeError` and `BTClibRuntimeError` are
  `BtcRpcValueError`, `BtcRpcTypeError` and `BtcRpcRuntimeError`.** The old
  names were this file's while it lived inside btclib, and btclib declares
  three of its own spelled exactly that way -- so a consumer holding both
  had two same-named classes and an `except BTClibValueError` that reads
  correct at every call site while being the wrong one at some of them.
  btclib hit that taking the dependency, in an `except` around a function
  of this module. Nothing catches these names inside this package, so the
  change is a rename; nothing has shipped, so no caller has to act.
- **a request id is prefixed `btcrpc-`**, where it said `btclib-`. The
  prefix reaches a node's `debug.log`, and naming a library the caller may
  not be using was a claim this package had no business making.

- `BitcoinCoreRpcClient`, one Bitcoin Core JSON-RPC endpoint and the
  credentials to reach it. `call` invokes any one method with positional or
  named parameters, `from_chain` builds a client for the local node of one
  of Core's chains from Core's own port and datadir tables, and
  `for_wallet` derives the `/wallet/<name>` endpoint with the name
  percent-encoded.
- JSON-RPC 2.0 with 1.1 read back, so a node older than v28 — which does
  not know the `"jsonrpc": "2.0"` marker and replies 1.1 to it — is
  answered correctly, an rpc error under an HTTP 500 included.
- `FetchError`, `HttpError` and `RpcError`: one exception for a backend
  that did not answer, one for an exchange that failed with a status, one
  for an error the node computed with its code and its `data`. All three
  are `FetchError`, so one `except` catches the lot, and the fields are
  what a caller's own retry policy reads. `HttpError` and `RpcError` hand
  every constructor argument to `BaseException.__init__` and compose their
  message in `__str__`, which is what makes them picklable —
  `BaseException.__reduce__` rebuilds an exception from `self.args`, and a
  class carrying two or three fields is not rebuilt by calling it with the
  one composed string those two used to leave in `args` — and what a
  `ProcessPoolExecutor` needs to send one back from a worker rather than
  report the pool broken.
- Amounts as `Decimal` in both directions: a number in a reply is parsed
  exactly, a `Decimal` parameter is refused rather than rounded through
  `float`, and `NaN` and `Infinity` are refused either way.
- `cookie_auth` and `DEFAULT_DATADIR`, for the credential bitcoind writes
  and rotates at every restart — read at each call rather than held.
- `core_chain_from_network` and `network_from_core_chain`, the two
  vocabularies written down once: `main` where BIP32 and BIP173 say
  `mainnet`.
- `HttpTransport`, `urlopen_transport` and `http_request`: the seam that
  lets code calling a node be tested without one, and the bounded urllib
  implementation behind it.

### Security

- No credential in the url: a url carrying `user:password@` is refused,
  that string being what ends up in configuration files and tracebacks.
  The class has no generated `__repr__` for the same reason.
- No redirect followed, and no proxy taken from the environment: a request
  already carries the `Authorization` for the host it names, and both
  would send it somewhere else.
- `http` and `https` only, so a url from configuration cannot make this
  read the local disk through `file:`.
- Every response body is read under a bound, `Content-Length` checked
  first and then not believed.

### Repository

- The project standards of btclib-org: the lint gate is
  `.pre-commit-config.yaml` and `lint.yml` runs that very file; every
  action is pinned to a commit SHA; coverage is a 100% ratchet rather than
  a report; `mutation.yml` asks weekly whether a line the suite executes is
  a line the suite checks; `rpc-smoke.yml` asks two live bitcoind versions
  whether the recorded replies are still what Core sends.
- Calendar versioning, `YYYY.M.D`: a release is named by the day it was
  cut, and what it breaks is read in HISTORY.md rather than inferred from
  the number. The month carries no leading zero, PEP 440 normalizing
  `2026.08` to `2026.8` and `release.yml` comparing the tag to the declared
  string as written. `release.yml`'s version-check job also refuses a tag
  with fewer than three components: without it a tag naming only the
  month, `v2026.8`, would pass every other check and publish a version
  indistinguishable from the placeholder `pyproject.toml` declares between
  releases, which names the same month and is never tagged.
- `.github/scripts/rpc_smoke.py` restructured for `tests/rpc_smoke_test.py`
  to cover: every function with no live node behind it —
  `check`, `port_is_free`, `check_legacy_reply`, `check_v2_reply`,
  `check_cookie`, `print_log_tail`, and `main`'s own argument parsing —
  now has a test with no `bitcoind` in the loop, and every function that
  does talk to one carries `# pragma: no cover`, that half staying
  `rpc-smoke.yml`'s to monitor against Core itself.
- `mutation.yml`'s session runs under `timeout --signal=INT` rather than
  the default SIGTERM, with a `git diff --quiet` check afterwards that
  restores the tracked source if anything is left changed. The local
  distributor applies a mutant and restores it from a `finally` block that
  only runs if the process can unwind; SIGTERM kills it outright,
  mid-mutant, before that block runs, where SIGINT is what Python turns
  into a catchable `KeyboardInterrupt`. A session cut at its budget could
  otherwise leave `bitcoin_core_rpc.py` mutated for whatever ran next.
- The MIT permission notice in full at the head of every source file, and
  `COPYRIGHT` — the text a hook requires them all to carry — is that notice
  rather than a pointer to `LICENSE`: `bitcoin_core_rpc.py` is meant to be
  copied out, and a copy has no `LICENSE` beside it to point at. No year in
  it, so a vendored copy nobody has touched does not look out of date every
  January.
