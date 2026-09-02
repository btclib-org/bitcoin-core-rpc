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

A package of four modules under `src/bitcoin_core_rpc/`, `__init__.py`
itself a facade re-exporting `__all__` rather than defining any of it:
`errors.py` the exception hierarchy every other module raises out of,
`chains.py` the chain and network vocabulary, `transport.py` the urllib
layer, `client.py` the RPC client built on the three beneath it. A
module may import any of the ones before it in that order and none of
the ones after — `errors < chains < transport < client` — and none of
the four takes a dependency outside the standard library. That the
package stays that way is a rule a contributor is bound by rather than
a fact about the code, so it is `CONTRIBUTING.md`'s *The one
constraint*; what follows is what the package is made of.

- every module opens with `COPYRIGHT`'s three lines like every other
  source file of the organization — the pointer form, whose third line
  names the URL of the license text — checked by
  `[tool.ruff.lint.flake8-copyright]` in `pyproject.toml`. There is
  deliberately no version constant anywhere in the package: the release
  tag is the version
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

The tests: `tests/client_test.py` judges the client,
`tests/chains_test.py` the chain and network vocabulary,
`tests/transport_test.py` the urllib layer under it, `tests/census_test.py`
the package's public surface, documentation and import graph.
`tests/__init__.py` holds `Recorded`, the transport that answers from
`tests/_data` and opens no socket — which is what keeps the suite
hermetic, not the absence of a node.

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

**Every session works in a worktree**, its own, from the first edit,
named `wt-<tracker>-<issue>-<repo>-<role>` rather than after the issue
alone. `tracker` is the repository whose issue tracker holds the issue:
an issue number is unique only within one tracker, so
`btclib-org/.github#45` and `btclib-org/btclib#45` are different issues
that would otherwise name the same worktree. `issue` is what prevents
the collision that has actually happened — two worktrees of different
work sharing a generic basename in one repository's own `.git`, keyed on
its path's basename. `repo` prevents a different collision, a *path*
one rather than a `.git` one: two repositories each keep their own
`.git/worktrees/<basename>` and cannot collide there, but the workers of
one session share one scratchpad directory, so a session carrying one
issue into several repositories computes the same target path for each
of them, and `git worktree add` refuses a directory that already
exists — or worse, a second worker reads the first one's tree; naming it
this way also sorts every worktree of one issue together. `role` covers
the narrower case of a coder and its reviewer holding a worktree at
once, which the ordinary sequence avoids by each removing its own.

```shell
WT=<scratchpad>/wt-<tracker>-<issue>-<repo>-<role>  # wt-github-255-btclib-coder
git worktree add -b <branch> "$WT" origin/main
cd "$WT" && uv sync --locked
# edit, gate and commit here, then
git push origin HEAD:refs/heads/<branch>
```

Removing the worktree is part of finishing, and it stands in a block of
its own: the block above ends in a placeholder, and a shell that
discards that line as a parse error reads the next as a fresh command —
which, in one block, is this line against whatever `$WT` already held.

```shell
git worktree remove --force "$WT"
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
- **A `###` in `CHANGELOG.md`'s open section names one entry, never a
  theme several entries share** (issue btclib-org/.github#586). Section
  9's `CHANGELOG.md and RELEASE_NOTES.md` makes grouping by theme the
  rejected alternative and settles the transitional case for a tree,
  like this one, whose open section already carries a heading of that
  shape: it is landed text and stays, and the next entry takes its own
  `###` at the end of the section rather than joining it. Which of this
  tree's own headings are themes is a reading of what sits under them,
  not a list to keep here — several citations under one heading are no
  evidence either way, section 9's own bullets citing separately.

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
