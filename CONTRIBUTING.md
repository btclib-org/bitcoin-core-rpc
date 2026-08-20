# Contributing to bitcoin-core-rpc

<!-- The toolchain badges are here rather than in the README because they
report no state: each names a choice, and this is the file that says how
the choice is enforced and what the command for it is. The README keeps the
badges that can turn red. btclib and btclib_libsecp256k1 do the same. -->
[![calendar versioning: yyyy.m.d](https://img.shields.io/badge/cal_ver-yyyy.m.d-1674b1.svg?logo=calver)](https://calver.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![format: ruff](https://img.shields.io/badge/format-ruff-yellowgreen.svg?logo=ruff)](https://docs.astral.sh/ruff/formatter/)
[![lint: ruff](https://img.shields.io/badge/lint-ruff-yellowgreen.svg?logo=ruff)](https://docs.astral.sh/ruff/)
[![docstrings: ruff](https://img.shields.io/badge/docstrings-ruff-yellowgreen.svg?logo=ruff)](https://docs.astral.sh/ruff/rules/#pydocstyle-d)
[![type check: mypy](https://img.shields.io/badge/type_check-mypy-yellowgreen.svg?logo=mypy)](https://mypy-lang.org/)
[![lint: markdownlint-cli2](https://img.shields.io/badge/lint-markdownlint--cli2-yellowgreen.svg?logo=markdown)](https://github.com/DavidAnson/markdownlint-cli2)
[![pre-commit enabled](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![GitHub repository: btclib-org/bitcoin-core-rpc](https://img.shields.io/badge/GitHub-btclib--org%2Fbitcoin--core--rpc-181717?logo=github)](https://github.com/btclib-org/bitcoin-core-rpc/)
[![slack: btclib_dev](https://img.shields.io/badge/slack-btclib_dev-white.svg?logo=slack)](https://bbt-training.slack.com/messages/C01CCJ85AES)

Thank you for investing your time in contributing to this project.

Read our [Code of Conduct](./CODE_OF_CONDUCT.md) to keep our community
approachable and respectable.

In this guide you will get an overview of the contribution workflow from
opening an issue and creating a PR, to reviewing and merging it.

## New contributor guide

To get an overview of the project, read the [README](./README.md) and the
docstring at the top of `bitcoin_core_rpc/__init__.py`, which is where the design
and the reason behind every refusal are written down.

Here are some resources to help you get started with open source
contributions:

- [Finding ways to contribute to open source on GitHub](https://docs.github.com/en/get-started/exploring-projects-on-github/finding-ways-to-contribute-to-open-source-on-github)
- [Set up Git](https://docs.github.com/en/get-started/quickstart/set-up-git)
- [GitHub flow](https://docs.github.com/en/get-started/quickstart/github-flow)
- [Collaborating with pull requests](https://docs.github.com/en/github/collaborating-with-pull-requests)

## Getting started

uv is the only tool that must be installed; it fetches interpreters,
linters and packaging tools itself.

```shell
uv sync                       # create the environment
uv run pytest                 # the suite
uv run pre-commit install     # so a commit runs the lint gate
```

The suite opens no socket and needs no node: every client in it is built
with a `transport=` that answers from bytes committed under `tests/_data`.
What a *live* node answers is a separate question, asked by the integration
workflow and by the command under [A live node](#a-live-node) below.

### The editor

`.vscode/settings.json` and `.vscode/extensions.json` are tracked, and they
hold no preference: the recommended extensions are the tools
`.pre-commit-config.yaml` already runs, and the settings put the fixing ones
on save. Installing them is optional and changes nothing about what a commit
enforces — what they buy is learning of a finding while typing rather than
at the commit that trips over it.

Anything machine-local — an interpreter path, a telemetry answer, a theme —
belongs in the editor's own user settings instead, those two files being
read by every checkout of this repository.

### What runs when

| workflow | when | what it varies |
| --- | --- | --- |
| `test` | pull request, push | 3 platforms × 7 interpreters |
| `lint`, `docs` | pull request, push | — |
| `claude-review` | pull request, and `@claude` in a comment | — |
| `integration` | pull request, push | 2 Core versions, 4 chains |
| `codeql` | push to main, Tuesday | 2 languages |
| `macos` | Wednesday, a release | 2 macOS images × 7 interpreters |
| `windows-arm` | Saturday, a release | `windows-11-arm` × 7 interpreters |
| `latest` | Wednesday | 6 platforms × 7, deps upgraded |
| `links` | Monday | — |
| `mutation` | Sunday | — |
| `published` | monthly, a release | what PyPI serves |
| `release` | a tag | calls the six workflows above it, and `published` |

The first four rows are what a merge waits for, about three minutes between
them.

What the rows below them have in common is one number: GitHub Free gives an
organization twenty concurrent jobs, shared across every repository in it.
A commit here asked for forty-four and one in btclib for thirty-nine, so a
pull request in either spent its wall clock waiting for a slot rather than
running anything. An image therefore earns a place before a review only if
it is cheap to wait for, and two are not: macOS queues 15.7 and 13.1 minutes
on average against 0.1 to 0.3 elsewhere, on cells that each run in under a
minute; and the fourteen Windows cells were 9.4 of the run's 16.9
runner-minutes, `windows-11-arm` the slower half of them at 40 to 77 seconds
a cell against 29 to 34 on `windows-latest`.

`windows-latest` stays in `test`, and that is not an oversight. The one
platform-conditional branch in this client is the datadir table in
`default_datadir`, whose rows the suite drives by patching `sys.platform` —
every row but the running one, so `%APPDATA%` and the `Path.home()` under it
are asked for real only on a Windows runner. One row asks that completely,
and the question does not vary with the architecture the interpreter targets.

`macos` and `latest` share a morning half an hour apart, which is what makes
the pair readable: red in both is the platform, red in `latest` alone is the
upgrade. `windows-arm` takes a morning of its own, Saturday being the day
nothing else here asks for. Every workflow here also takes
`workflow_dispatch`, gates included, `claude-review` excepted —
`grep -c workflow_dispatch: .github/workflows/*.yml` is what says so, and
for `codeql` and the two image workflows it is the only way to ask about a
branch at all. `claude-review` takes none because both its jobs read the
pull request or the comment that triggered them, so a manual run would
start with nothing to read.

`codeql` runs on `main` and on its Tuesday schedule and not on a pull
request, which is the same arithmetic as the rows above: three slots held
while a review waits. What still reads a branch before it merges is
`zizmor`, a `pre-commit` hook and therefore part of `lint`, which audits
these workflows for an injected expression. `REPOSITORY.md` has the trade in
full. It is also the one gate `release` does not call, a tag publishing the
tree those checks already passed.

### Reproducing what CI runs

Each command below is the one a CI job runs, verbatim. Keep this section
true when a workflow changes.

`test.yml`, the `suite` job — the suite, on one cell of the matrix:

```shell
uv run --locked --no-default-groups --group test pytest
```

`test.yml`, the `coverage` job — the same suite under the 100% ratchet,
which a bare `pytest` does not enforce:

```shell
uv run --locked --no-default-groups --group test \
    pytest --cov-report term-missing:skip-covered \
    --cov=bitcoin_core_rpc --cov=tests
```

`test.yml`, the `dist` job — build the distribution files and check
them:

```shell
uv build
uv run --locked --only-group build twine check --strict dist/*
uv run --locked --only-group build check-wheel-contents dist/*.whl
uv run --locked --only-group build pyroma --min 10 dist/*.tar.gz
```

`lint.yml`, the `lint` job — this file *is* the lint gate, so there is no
second list of tools anywhere:

```shell
uv run --locked --only-group lint pre-commit run --all-files
```

`docs.yml`, the `docs` job — and this one is worth running even when every
hook passes, because no hook reads reStructuredText: a docstring docutils
cannot parse fails the workflow while pre-commit is green.

```shell
uv run --locked --no-default-groups --group docs \
    sphinx-build -W --keep-going -b html docs/source docs/build/html
```

`codeql.yml` has no line here, and it is the one gate that cannot: its jobs
run `github/codeql-action` and no command of this project's, so reproducing
it locally means the CodeQL CLI and a database rather than a `uv run`. What
a branch can do instead is ask for the analysis it would get —
`gh workflow run codeql.yml --ref <branch>`.

Another interpreter, which is what the matrix varies. Prefix it with
`UV_PROJECT_ENVIRONMENT`, or `uv run --python <version>` rebuilds `.venv`
with the restricted group set and leaves pre-commit out of the environment
its own git hook execs by absolute path:

```shell
UV_PROJECT_ENVIRONMENT=.venv-3.10 uv run --locked --no-default-groups \
    --group test --python 3.10 pytest
```

### Mutation testing

`mutation.yml` asks the question coverage cannot: a line the suite executes
is not a line the suite checks. It gates nothing and runs weekly; the
configuration is the single source of the scope and the test command.

```shell
uv run --locked --no-default-groups --group test --group mutation \
    cosmic-ray baseline .github/mutation/bitcoin_core_rpc.toml
uv run --locked --no-default-groups --group test --group mutation \
    cosmic-ray init .github/mutation/bitcoin_core_rpc.toml rpc.sqlite
uv run --locked --no-default-groups --group test --group mutation \
    cr-filter-operators rpc.sqlite .github/mutation/bitcoin_core_rpc.toml
uv run --locked --no-default-groups --group test --group mutation \
    cosmic-ray exec .github/mutation/bitcoin_core_rpc.toml rpc.sqlite
uv run --locked --no-default-groups --group test --group mutation \
    cr-report --surviving-only --show-diff rpc.sqlite
```

The session writes each mutation into the client source and restores it
afterwards, so nothing else may read the file while it runs.

### A live node

`integration.yml` is the one claim the recorded replies cannot make. Against
a `bitcoind` of your own — it runs on a regtest chain in a temporary
datadir, on Core's own rpc port, and leaves nothing behind:

```shell
uv run --locked --no-default-groups \
    python .github/scripts/rpc_smoke.py \
    --bitcoind /path/to/bitcoind --core-version 31.1 --protocol 2.0
```

`--protocol` is asserted rather than derived: what the workflow's matrix
pins is that Core v27 answers JSON-RPC 1.1 and the current release answers
2.0, and a node that stopped doing so has to fail this rather than be
accommodated by it.

`--chain` is the other mode, one node at a time and no chain generated on
it: it starts a node of `main`, `test`, `testnet4` or `signet` with no peer
reachable at all, and checks only that Core still accepts `-chain=<name>`
and reports it back:

```shell
uv run --locked --no-default-groups \
    python .github/scripts/rpc_smoke.py \
    --bitcoind /path/to/bitcoind --core-version 31.1 --chain testnet4
```

### The secrets baseline

`detect-secrets` reads `.secrets.baseline` to decide which findings have
already been reviewed, and which plugins run at all. Adding a credential
shaped literal to the tests means regenerating it:

```shell
uv run --locked --only-group lint pre-commit run detect-secrets --all-files
uvx detect-secrets scan --baseline .secrets.baseline
```

Read the diff before committing it: a new entry is a finding somebody has
to have looked at, which is the whole point of a baseline over an
exclusion.

## Issues

### Create a new issue

If you spot a problem, [search if an issue already
exists](https://docs.github.com/en/github/searching-for-information-on-github/searching-on-github/searching-issues-and-pull-requests#search-by-the-title-body-or-comments).
If a related issue does not exist, open a new one using the relevant form.

What a *method* does is Bitcoin Core's, not this client's: an `RpcError`
carrying a code is usually a question for the method's documentation.

### Solve an issue

Scan through our [existing
issues](https://github.com/btclib-org/bitcoin-core-rpc/issues) to
find one that interests you.

## Make Changes

Work locally on your fork until you are satisfied. Ensure that pre-commit
and pytest have no issue with your modified codebase.

### The one constraint

**This is one source file with nothing but the standard library behind
it**, and it stays that way. A dependency here is a dependency a vendored
copy silently does not have, and a second module is a second file to copy;
`tests/standalone_test.py` is what fails when either happens — it reads the
imports of the source, and it runs a copy of it under `python -I -S`, where
no site package is reachable.

`__all__` is the public surface. A name is public because that list says
so, not because it happens to lack a leading underscore.

### Documentation and comments

What "satisfied" means for the prose — docstrings, comments, the sphinx
pages, a pull request reply — is written down here, because a hook can
check that a docstring exists but not what it says.

**Tone of voice: neutral, factual, dry.** The same register everywhere: no
wit, no salesmanship, no emphasis where the fact is enough. Explanatory
detail is wanted; decoration is not.

**Length is a cost, and the reason is what buys it.** One sentence where
one will carry it, and a paragraph only where a shorter one would leave
the reader wrong. Three habits lengthen prose here without adding to it,
and each is worth deleting on sight:

- the same reason in a second wording — not emphasis, but a second copy
  to keep true, and the one that drifts;
- the sentence that only introduces the next one;
- the tour of alternatives, where the rejected one and the thing that
  rejects it are the whole of the negative result.

Nothing checks prose the way the suite checks code, so every line of it
is one a later change can falsify in silence. That is what its length is
weighed against.

**A docstring states the contract.** What the function takes, what it
returns or raises, and the rule the behaviour comes from — not a
restatement of the name. Most readers of a docstring here are new to the
project: write for them.

**A comment carries the reasoning, including the negative result.** Say why
the code is as it is and why *not* the obvious alternative — the second
half is what stops the next reader from "fixing" a deliberate choice, and
it is what makes a file reviewable rather than merely readable.

**Cite the authority.** Where behaviour comes from an RFC, the JSON-RPC
specification or a Bitcoin Core function, name it, rather than asserting
the behaviour as if this project had decided it. Where this project
deviates, say so and say why.

**Measure, don't assert.** A number in prose comes from a command, and the
command belongs beside it, so the next reader can re-measure instead of
trusting a figure whose date they cannot see. Never state a count that
nothing checks — an unchecked number drifts into a false claim — and never
state how many of anything a file holds: a stated total is a line every
open branch has to edit, and two branches moving it to the same wrong
number merge without a conflict.

**One fact in one place.** Two files stating the same thing become two
files disagreeing about it; the second one points at the first.

**No history in the prose.** Comments and docstrings say why the code is as
it is, in the present tense; they do not tell the story of what it used to
be. "This is here rather than X because X breaks Y" stays, whatever
prompted it; "this used to be X, until Z" goes — unless the old spelling is
something a caller can still encounter (a deprecated alias, a wire format),
in which case it is not history but the present. History has two files of
its own, [CHANGELOG.md](./CHANGELOG.md) and
[RELEASE_NOTES.md](./RELEASE_NOTES.md), and it is complete there.

**Markdown wraps at 80 columns**, tables included, so long commands go in
fenced blocks split with `\`.

## Commit your update

Commit the changes to your fork once you are happy with them.

Every commit that reaches `main` needs a [verified
signature](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification)
— GPG, SSH or S/MIME — together with linear history, no force push and no
branch deletion. A GitHub ruleset enforces the four on every push that
reaches `main`, regardless of who makes it and with no bypass actor: a
commit that is unsigned or that rewrites history is rejected before it is
something to review. REPOSITORY.md has the branch protection
configuration.

## Pull Request

When you're finished with the changes, create a pull request (PR).

Every change starts with an open issue: file one before opening the pull
request that closes it, not after.

- Don't forget to
  [link PR to issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue)
  if you are solving one — `Closes #N` in the description is what closes
  the issue once a reviewed pull request merges.
- A pull request merges only after an approving review from somebody
  other than its author: GitHub does not allow self-approval.
  [REVIEWING.md](./REVIEWING.md) is the standard that review is written
  against, and is this file's other half — what a review establishes
  before it gives an ack, how a finding states its severity, and why
  everything it notices that the pull request is not about becomes an
  issue rather than a comment. Read before opening a pull request, it is
  what the pull request will be answered against.
- Enable the checkbox to
  [allow maintainer edits](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/allowing-changes-to-a-pull-request-branch-created-from-a-fork)
  so the branch can be updated for a merge.
- We may ask for changes to be made before a PR can be merged, either using
  [suggested changes](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/incorporating-feedback-in-your-pull-request)
  or pull request comments.
- As you update your PR and apply changes, mark each conversation as
  [resolved](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/commenting-on-a-pull-request#resolving-conversations).

**A correction is a commit of its own, never an amend.** Once a branch is
pushed and under review, `git commit --amend` and a force-push replace the
commits the review is attached to: the reviewer loses the diff they read,
"changes since your last review" has nothing to compare against, and every
check starts again from a commit nobody has seen. Add the fix on top, with
a message saying what it fixes, and reply to the comment with the sha.

Nothing is lost in `main`'s history by doing so, because **a pull request
lands as one commit**: the branch is squashed at the button, so the
review's commits are the record of the review and `main` keeps one
commit per landed change. Squash is the only method either the
repository setting or the ruleset will accept, so there is no other
button to read; REPOSITORY.md has both, and what the other two would
have cost.

**Auto-merge is what presses it**, once the review and the checks are
in, and that is the whole of how a change reaches `main`: a direct push
is refused for everyone, the maintainer included. The commit GitHub
composes is signed with its own web-flow key — `Verified`, and by GitHub
— which is what the rule asks for, a valid signature rather than a
particular signer's. What is enforced rather than remembered is that
there is a signature at all: the ruleset takes no unsigned commit onto
`main`, with no bypass actor for anyone.

A branch opened on top of another one's head is the case that costs
something here. When the parent lands, the squash replaces the head the
child was written on, so the child is rebased and pays a fresh run of
the gates for a diff nobody edited. That is the price of having no way
to write to `main` by hand, and it is not avoidable by keeping the child
to a single commit: a button recreates rather than moves, GitHub's
documentation saying rebase-and-merge "always updates the committer
information and creates new commit SHAs".

The one force-push that stays right is the one that carries no new work: a
`git rebase origin/main` on a branch whose base has moved, which is how a
stale pull request is refreshed. Re-run the gates after it, never only
before it, and say in the pull request that the head moved and why.

**`main` is the only branch**, and every change reaches it through a pull
request — a contributor's, a maintainer's, Dependabot's and
pre-commit.ci's alike. A release is a tag on it rather than a branch of
its own; [RELEASING.md](./RELEASING.md) is what happens after that.

## Your PR is merged

Congratulations :tada::tada:

Once your PR is merged, your contributions will be publicly visible on the
[contributors page](https://github.com/btclib-org/bitcoin-core-rpc/graphs/contributors).
