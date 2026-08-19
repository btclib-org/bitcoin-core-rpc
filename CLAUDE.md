# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

Repository configuration — branch protection, required checks, token
permissions, publishing environments, secret scanning — is in
`REPOSITORY.md`. Read that file before changing a workflow, a branch rule
or a repository setting. Writing code does not need it.

## Commands

uv is the only tool that must be installed; it fetches interpreters,
linters and packaging tools itself. `uv sync` creates the environment.

```shell
uv run pytest                                   # the suite
uv run pytest tests/transport_test.py           # one file
uv run pytest -k test_a_wallet_name             # one test
uv run pre-commit run --all-files               # every gate, see below
uv run pre-commit run mypy --files bitcoin_core_rpc/__init__.py  # one hook
uv run --python 3.10 pytest                     # another interpreter
```

`CONTRIBUTING.md` has the command for each CI job, verbatim; keep it true
if a workflow changes.

## Architecture

One source file, `bitcoin_core_rpc/__init__.py`, with nothing but the standard
library behind it, and that constraint is the single most important thing
to know before touching it:

- **no dependency, and no second module.** A dependency here is one a
  vendored copy silently does not have, and a second module is a second
  file to copy. `tests/standalone_test.py` is what fails when either
  happens: it walks the imports of the source with `ast`, and it runs a
  copy of the file under `python -I -S`, where no site package is reachable
- the file is installed as a top-level module *and* meant to be copied, so
  it carries the MIT notice embedded rather than referenced — a copy has no
  `LICENSE` beside it. There is deliberately no version constant in it: the
  release tag is the version
- layers, such as they are: `http_request` and `urlopen_transport` open the
  socket and map everything below an HTTP status onto `FetchError`;
  `BitcoinCoreRpcClient.call` builds the request, and `_reply_object`,
  `_legacy_result` and `_v2_result` decide what came back. What a status
  *means* is the client's question and never the transport's
- **JSON-RPC 2.0, and 1.1 read back.** Core answers 1.1 by default and 2.0
  to a request carrying the marker; a node older than v28 does not know the
  marker and replies 1.1 to it. Under 1.1 an rpc error arrives as the body
  of an HTTP 500, so the error is read before the status is judged — which
  is why `_legacy_result` and `_v2_result` are two functions and not one
  with a flag

The tests: `tests/bitcoin_core_rpc_test.py` judges the client,
`tests/transport_test.py` the urllib layer under it,
`tests/standalone_test.py` the one-file property. `tests/__init__.py` holds
`Recorded`, the transport that answers from `tests/_data` and opens no
socket — which is what keeps the suite hermetic, not the absence of a node.

## Non-obvious facts that will otherwise waste a session

- **`main` is the only branch**, and nothing is pushed to it directly:
  every change lands through a pull request, Dependabot's and
  pre-commit.ci's included, and a release is a tag on it. Branch
  protection, and why it is what it is, is `REPOSITORY.md`.
- **How a pull request lands**: squash-and-merge from the web UI, or
  auto-merge once review and checks are in, is the default — one commit
  regardless of how many the branch carried. The exception is a
  single-commit pull request that is the base of a stacked one: that one
  is fast-forwarded from the command line instead, so `main` gets that
  exact sha rather than a new commit — which is what leaves the stacked
  pull request its base, and its diff honest. A signature lands either
  way — the maintainer's on a CLI fast-forward, the forge's own on a
  button-driven merge — and the ruleset refuses a commit without one.
  `CONTRIBUTING.md` states the rule, `REPOSITORY.md` the settings and the
  pushes under it.
- **A branch's CI run can be `cancelled` rather than green.** `test.yml`'s
  concurrency group is `test-${{ github.ref }}` with cancel-in-progress, so
  the next push kills the run for the previous commit. The local gates
  below are the evidence; `cancelled` is not `failure`.
- **A draft pull request runs no CI at all**, every workflow carrying
  `if: ${{ !github.event.pull_request.draft }}`. Mark it ready to be
  checked; `test: every job passed` is required, and a required check that
  never
  reports blocks the merge rather than passing it.
- **`.pre-commit-config.yaml` is the lint gate**, and `lint.yml`'s first
  job runs exactly it. Never add a second list of the same tools to a
  workflow. mypy is a *local* hook shelling out to uv on purpose: the
  mirrors-mypy hook injects `--ignore-missing-imports`, and it type checks
  in an isolated environment where the project is not installed — so
  `import bitcoin_core_rpc` in a test would be `Any` and every assertion
  about it would pass vacuously.
- **`pre-commit` passing is not the lint gate passing: run sphinx too.**
  `docs.yml` runs it with `-W`, so a docstring docutils cannot
  parse fails the workflow while every hook passes — a name ending in an
  underscore is a reference to a link target (``mult_``, and the fix is
  those very backticks). Reproduce it before claiming the gate is green:

  ```shell
  uv run --locked --no-default-groups --group docs \
      sphinx-build -W --keep-going -b html docs/source docs/build/html
  ```

- **`uv run pytest` is not the coverage gate.** `fail_under = 100.0` is
  enforced only when coverage is measured, which the plain command does
  not do:

  ```shell
  uv run pytest --cov=bitcoin_core_rpc --cov=tests
  ```

- **Prefix any `--python <version>` command with
  `UV_PROJECT_ENVIRONMENT=.venv-3.10`.** Without it, `uv run --python
  <version>` rebuilds `.venv`, and a group-restricted command then leaves
  pre-commit out of it — and pre-commit's git hook `exec`s
  `.venv/bin/python -mpre_commit` by absolute path, which exists and lacks
  the module, so the next `git commit` dies with `No module named
  pre_commit`. `uv sync` restores it.
- **The version is declared once**, in `pyproject.toml`.
  `docs/source/conf.py` parses that file (not the metadata, which would
  need the package installed), and the module carries no version at all.

## The primary checkout is the maintainer's

**Never work in it.** No edit, no `git add`, no commit, no branch switch,
no rebase, no `git stash`, no `pre-commit run` — the hooks fix files in
place. Reading it is fine — `git log`, `git show`, `git diff`, `gh`, and a
`git fetch`, which writes refs and leaves the work tree alone.

**Every session works in a worktree**, its own, from the first edit:

```shell
WT=<scratchpad>/wt<issue>
git worktree add -b <branch> "$WT" origin/main
cd "$WT" && uv sync --locked
# edit, gate and commit here, then
git push origin HEAD:refs/heads/<branch>
git worktree remove --force "$WT"     # removing it is part of finishing
```

**Never `git stash` in a worktree either: `refs/stash` is shared.** A
worktree isolates files, not refs, so `git stash push` pushes onto the same
stack every other session pops from. Commit to your own branch instead.

**Do not rewrite `refs/heads/main`, or advance it with work that is not
yours.** Your own branch is what you push, and the pull request is what
moves `main`.

## Conventions to match

- **Workflows**: every action pinned to a commit SHA with the tag in a
  trailing comment; every workflow declares `permissions: contents: read`
  and `timeout-minutes`; concurrency groups are named literally
  (`test-${{ github.ref }}`), never through `github.workflow`, which in a
  called workflow is the caller's name; `checkout` passes
  `persist-credentials: false`; uv commands pass `--locked`, never
  `--frozen`. `actionlint` and `zizmor` are hooks, and both must stay at
  zero findings.
- **The prose style — tone, comments, docstrings, no history — is
  CONTRIBUTING.md's "Documentation and comments" section**, stated once
  there because contributors read that file and not this one. It governs
  the workflows and the pre-commit config too.
- **Markdown wraps at 80 columns**, tables included (MD013 is on), so long
  commands go in fenced blocks split with `\`.
- pytest is strict: a warning is an error, an unregistered marker is an
  error, an xfail that passes is a failure. Coverage has a `fail_under`
  ratchet in `pyproject.toml`.
- **CHANGELOG.md gets an entry for anything a user would notice**, in the
  group it belongs to; HISTORY.md is the release notes on top of it and
  only moves for a change a user has to *act* on.
- **Never state how many of anything a file holds** — measure it when a
  release wants it, and do not estimate. A wall clock and a linter's
  findings are counts too, and nothing fails on those: what a comment
  carries instead is the reason, with the command that re-derives the
  number beside it.
- **CHANGELOG.md and HISTORY.md are `merge=union`**, which is what
  `.gitattributes` is for. Its price is that these two files never conflict
  at all, so two branches editing *the same* entry merge in silence.

## Verifying

Check exit codes, not filtered output: `pre-commit run ... | grep -v
Passed` hides a failure. Run the command as documented before claiming it
works, and prefer measuring to asserting — every claim in this file was
checked against the tree, and the tree changes.
