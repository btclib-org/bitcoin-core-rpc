# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

How to work here — what the issue tracker takes, the prose style, and how
a pull request is opened and landed — is `CONTRIBUTING.md`, which is the
same file in every repository of the organization up to its last section,
which is this tree's and holds the commands and the gates. Repository
configuration is `REPOSITORY.md`: read it before changing a workflow, a
branch rule or a setting. Reviewing is `REVIEWING.md`, and `/review` is
that file as a command; read it before reviewing a pull request and
before opening one, since it is what the pull request will be answered
against.

## Architecture

One source file, `bitcoin_core_rpc/__init__.py`, with nothing but the
standard library behind it. That it stays one file with no dependency is
a rule a contributor is bound by rather than a fact about the code, so it
is `CONTRIBUTING.md`'s *The one constraint*; what follows is what the
file is made of.

- the file is installed as a top-level module *and* meant to be copied,
  and it opens with `COPYRIGHT`'s three lines like every other source
  file of the organization — the pointer form, whose third line names
  the URL of the license text a copy has no `LICENSE` beside it for;
  `[tool.ruff.lint.flake8-copyright]` in `pyproject.toml` is where the
  self-contained notice it used to carry was weighed and lost. There is
  deliberately no version constant in it: the release tag is the version
- layers, such as they are: `http_request` and `urlopen_transport` open
  the socket and map everything below an HTTP status onto `FetchError`;
  `BitcoinCoreRpcClient.call` builds the request, and `_reply_object`,
  `_legacy_result` and `_v2_result` decide what came back. What a status
  *means* is the client's question and never the transport's
- **JSON-RPC 2.0, and 1.1 read back.** Core answers 1.1 by default and
  2.0 to a request carrying the marker; a node older than v28 does not
  know the marker and replies 1.1 to it. Under 1.1 an rpc error arrives
  as the body of an HTTP 500, so the error is read before the status is
  judged — which is why `_legacy_result` and `_v2_result` are two
  functions and not one with a flag

The tests: `tests/bitcoin_core_rpc_test.py` judges the client,
`tests/transport_test.py` the urllib layer under it,
`tests/standalone_test.py` the one-file property. `tests/__init__.py`
holds `Recorded`, the transport that answers from `tests/_data` and opens
no socket — which is what keeps the suite hermetic, not the absence of a
node.

## The primary checkout is the maintainer's

**Never work in it.** No edit, no `git add`, no commit, no branch switch,
no rebase, no `git stash`, no `pre-commit run` — the hooks fix files in
place. Reading it is fine — `git log`, `git show`, `git diff`, `gh`, and a
`git fetch`, which writes refs and leaves the work tree alone.

**But `git fetch` moves `refs/remotes/origin/main` without moving the work
tree**, so a `grep` or a `Read` against the checkout's files answers for
whenever it was last brought forward, not for now. The read that cannot go
stale is `git show origin/main:<path>`: it answers from the ref `git
fetch` just moved, never from the tree. Where the checkout has to be
current rather than merely readable, a fast-forward of a clean `main`
brings it up:

```shell
git fetch origin && git merge --ff-only origin/main   # clean main only
```

That writes no commit, switches no branch and runs no hook, so it is on
the permitted side of *never work in it*, not an exception to it. Stop if
the checkout is not on `main` or is not clean: that is no longer bringing
it forward.

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

## Model

The default model for this repository is Sonnet. Switch to Opus only
for architectural decisions with conflicting constraints -- design
choices with non-obvious trade-offs, refactors with unclear
dependencies, diagnosis where the symptom does not point to the
cause. Use `/model opus` for the session, then switch back to Sonnet.

Do not use Fable unless explicitly instructed.

## Non-obvious facts that will otherwise waste a session

- **A branch's CI run can be `cancelled` rather than green.** `test.yml`'s
  concurrency group is
  `test-${{ github.event.pull_request.number || github.ref }}` (plus a
  release-only suffix) with cancel-in-progress, so the next push kills
  the run for the previous commit. The local gates are the evidence;
  `cancelled` is not `failure`.
- **A draft pull request runs no CI at all**, every workflow carrying
  `if: ${{ !github.event.pull_request.draft }}`. Mark it ready to be
  checked: a required check that never reports blocks the merge rather
  than passing it.
- **mypy is a *local* hook shelling out to uv on purpose.** The
  mirrors-mypy hook injects `--ignore-missing-imports`, and it type
  checks in an isolated environment where the project is not installed —
  so `import bitcoin_core_rpc` in a test would be `Any` and every
  assertion about it would pass vacuously.
- **The version is declared once**, in `pyproject.toml`.
  `docs/source/conf.py` parses that file (not the metadata, which would
  need the package installed), and the module carries no version at all.

## Conventions to match

Section 9 of `btclib-org/.github` is the prose style and section 10 its
workflow conventions, and neither is re-listed here, that section's own
*One fact in one place* being the reason. They govern the workflows and
the pre-commit config as much as the docstrings. `actionlint` and
`zizmor` read the workflows as hooks of the lint gate, so a finding from
either fails a commit rather than reporting one.

What is left to this file is what those cannot say, because it is about a
session rather than about the tree: the worktree rule, the model, the
failure modes in the section that names them, and what this tree is.

## Verifying

Run the command as documented before claiming it works, and read its exit
code rather than its filtered output, for the reason `CONTRIBUTING.md`'s
*This repository in particular* gives. Every claim in this file was
checked against the tree, and the tree changes.
