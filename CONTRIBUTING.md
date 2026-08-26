# Contributing

What this repository holds in common with the others of the organization
— the toolchain, the lint gate, the tool tables behind it, the workflow
set and the branch rules — is stated once in the
[btclib-org repository standard](https://github.com/btclib-org/.github),
each rule with the alternative it was decided against. It binds this
repository, so a change departing from it is a divergence, and one filed
as an issue in that repository rather than here: a difference between two
repositories belongs to neither of them.

**This file is the same in every repository of the organization up to
its last section.** What is true of one tree only — the commands that
build its environment, the gates it runs, which of its workflows decide
a merge — is under that heading, and the comparison stops there.

## The issue tracker

Where an issue is filed, and what an alignment finding has to name, is
[the standard's *What this repository is*][s-what]: an issue spanning
repositories, or whose subject is the standard, goes to
[btclib-org/.github](https://github.com/btclib-org/.github/issues), and
one about this tree alone stays here.

A finding noticed while doing something else is filed, not carried.
`REVIEWING.md`'s *Every collateral finding becomes an issue* is the whole
of what to do with one, and it applies to an author as much as to a
reviewer: a pull request answering two questions cannot be accepted for
either.

## Documentation and comments

[Section 9 of the standard][s9] is the prose style, and it governs the
prose this tree ships — comments, docstrings and markdown. It is not
restated here: a second wording is the one that goes stale, which is
that section's own *One fact in one place*.

A commit message is prose this tree ships too, though section 9 does not
say so: squash is the only merge method and the landing commit carries
the messages, so what is written in one is read on `main` long after the
branch is gone.

## Pull requests

What `main` accepts, and what it refuses to everyone, is [section 11 of
the standard][s11]. Run the gates locally before opening anything —
the last section of this file says which they are — because CI runs
exactly them, so a red run there is a local run that was not done.

What a pull request's title and description have to say about the issues
it closes, and why a manual link in the Development panel is a trap
neither of them shows, is [the standard's *What a pull request says it
is*][s-title]. Read it before opening one; it is the rule most often
found broken after the fact.

`REVIEWING.md` is the standard a review is written against, and is this
file's other half. Read before opening a pull request, it is what the
pull request will be answered against.

`CHANGELOG.md` gets an entry for anything a reader would notice, and the
release notes move only for something a user has to *act* on, in the
repositories that publish.

### One subject, opened as soon as it is written

A pull request answers one question. Issues that share a subject are one
pull request, closing each of them; issues that do not are one pull
request each, however small either of them is.

It is opened the moment it is written and verified — not held for the
previous one to be reviewed or to land, and not batched with the next. A
batch arrives as one reviewing job with several subjects, which is the
shape that costs the most to read; a finished pull request held back is
review that could have started and did not.

Working this way stacks branches, which is fine and costs one rule: a
child whose base was amended is moved with the old base named,

```shell
git rebase --onto <new-base> <old-base-sha> <child>
```

because a plain rebase replays the base's old commit inside the child,
and the forge then shows the base's old text as additions with nothing
red anywhere. Read the child's diff afterwards rather than trusting the
rebase, and retarget each child onto `main` as its parent lands.

### The review

A review is given promptly and on local evidence. It does not wait for
CI, does not report a check as a finding, and does not discuss a run at
all: whether CI is green is the author's business, once, at landing time.

The exchange is anchored to a sha rather than to a branch, a branch being
free to move under a review:

- the author hands off by naming the sha pushed and the evidence run
  against it, then leaves that head alone;
- the reviewer answers with findings — where, what is wrong, how they
  know it, and whether each is blocking;
- the author accepts what is reasonable, declines the rest with a reason
  in the thread, and pushes the answer without waiting for CI;
- the reviewer resolves the threads they opened, that being what says a
  finding is closed, and re-reviews the delta rather than the branch.

**What ends the loop is the ack of record**, and the author does not
supply their own. A reading that says what it found and delivers no
verdict is a review too and ends nothing; [the standard's *Review*][s-rev]
has which is which, and `REVIEWING.md` has how each is written. A
disagreement that survives a second exchange goes to the maintainer
instead of into a third round.

### Landing it

CI is read once, and this is where. Rebase onto `main`'s tip, push that
head so the checks run on the tree that will land, and only then wait for
them: checks read before a rebase describe a tree nobody is landing. A
rebase that moved nothing but the base leaves the ack standing; one that
resolved a conflict does not, that resolution being a change no reviewer
has seen.

Then squash, [the only method the rule accepts][s11].

**The maintainer's bypass is not automatic — it has to be invoked, and
`gh pr merge` cannot invoke it**, refusing client-side before it asks
GitHub anything:

```text
Pull request is not mergeable: the base branch policy prohibits the merge
```

The merge endpoint applies it server-side, and it is the same endpoint
the merge button asks:

```shell
gh api -X PUT repos/{owner}/{repo}/pulls/<n>/merge \
  -f merge_method=squash
```

**Verify what landed rather than trusting the answer**, the signature
[the standard asks for][s-sigs] being a valid one rather than a
particular signer's:

```shell
gh api repos/{owner}/{repo}/commits/main \
  --jq '.commit.verification | {verified, reason}'
```

The forge deletes the head branch itself, per the setting section 11
names. What is still yours is bringing every checkout sitting on `main`
up to date,
that being where the next session starts from and a stale one being where
a branch gets built on a base that has moved. `REPOSITORY.md` carries the
settings and why they are what they are.

[s-what]: https://github.com/btclib-org/.github#what-this-repository-is
[s11]: https://github.com/btclib-org/.github#11-github-settings
[s9]: https://github.com/btclib-org/.github#9-prose-comments-and-docstrings
[s-title]: https://github.com/btclib-org/.github#what-a-pull-request-says-it-is
[s-rev]: https://github.com/btclib-org/.github#review
[s-sigs]: https://github.com/btclib-org/.github#signatures

## This repository in particular

Everything above is the same file in every repository of the
organization; everything below is this one's, and the comparison stops at
this heading.

<!-- The toolchain badges are here rather than in the README because they report
no state: each names a choice, and this is the file that says how the choice is
enforced and what the command for it is. The README keeps the badges that can
turn red. btclib and btclib-secp256k1 do the same. --> [![calendar versioning:
yyyy.m.d](<https://img.shields.io/badge/cal_ver-yyyy.m.d-1674b1.svg?logo=calver>)](<https://calver.org/>)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![format:
ruff](https://img.shields.io/badge/format-ruff-yellowgreen.svg?logo=ruff)](https://docs.astral.sh/ruff/formatter/)
[![lint:
ruff](https://img.shields.io/badge/lint-ruff-yellowgreen.svg?logo=ruff)](https://docs.astral.sh/ruff/)
[![docstrings:
ruff](https://img.shields.io/badge/docstrings-ruff-yellowgreen.svg?logo=ruff)](https://docs.astral.sh/ruff/rules/#pydocstyle-d)
[![type check:
mypy](https://img.shields.io/badge/type_check-mypy-yellowgreen.svg?logo=mypy)](https://mypy-lang.org/)
[![lint:
markdownlint-cli2](https://img.shields.io/badge/lint-markdownlint--cli2-yellowgreen.svg?logo=markdown)](https://github.com/DavidAnson/markdownlint-cli2)
[![pre-commit
enabled](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![GitHub repository:
btclib-org/bitcoin-core-rpc](https://img.shields.io/badge/GitHub-btclib--org%2Fbitcoin--core--rpc-181717?logo=github)](https://github.com/btclib-org/bitcoin-core-rpc/)

To get an overview of the project, read the [README](./README.md) and the
docstring at the top of `src/bitcoin_core_rpc/__init__.py`, which is where the
design and the reason behind every refusal are written down.

What a *method* does is Bitcoin Core's, not this client's: an `RpcError`
carrying a code is usually a question for the method's documentation
rather than an issue here.

### The one constraint

**This is one source file with nothing but the standard library behind
it**, and it stays that way. A dependency here is a dependency a vendored
copy silently does not have, and a second module is a second file to copy;
`tests/standalone_test.py` is what fails when either happens — it reads the
imports of the source, and it runs a copy of it under `python -I -S`, where
no site package is reachable.

`__all__` is the public surface. A name is public because that list says
so, not because it happens to lack a leading underscore.

### The environment and the gates

uv is the only tool that must be installed; it fetches interpreters,
linters and packaging tools itself.

```shell
uv sync                       # create the environment
uv run pre-commit install     # so a commit runs the lint gate
```

The suite opens no socket and needs no node: every client in it is built with a
`transport=` that answers from bytes committed under `tests/_data`. What a
*live* node answers is a separate question, asked by `integration-bitcoind.yml`
and by the command under [A live node](#a-live-node) below.

The gate is the suite, the hooks and the documentation build:

```shell
uv run pytest
uv run pre-commit run --all-files
uv run --locked --no-default-groups --group docs \
    sphinx-build -W --keep-going -b html docs/source docs/build/html
```

`--cov` is in `addopts`, so the bare `pytest` above is the coverage gate
and `fail_under = 100.0` is what it answers against; `pyproject.toml`
says why the flag sits there rather than in the workflow that used to
carry it. A selective run is reported and not gated —
`uv run pytest tests/transport_test.py` prints a coverage of the whole
tree and passes — and `tests/conftest.py`'s `pytest_configure` is what
makes that difference.

The documentation build is the one to remember, because no hook reads
reStructuredText: a docstring docutils cannot parse fails it with every
hook green — a name ending in an underscore is a reference to a link
target (``mult_``, and the fix is those very backticks).

**Check exit codes, not filtered output.** `pre-commit run ... | grep -v
Passed` hides a failure, and `grep` finding nothing exits 1, which is not
the gate's answer to anything.

**Prefix any `--python <version>` command with
`UV_PROJECT_ENVIRONMENT=.venv-3.10`.** Without it, `uv run --python
<version>` rebuilds `.venv`, and a group-restricted command then leaves
pre-commit out of it — and pre-commit's git hook `exec`s
`.venv/bin/python -mpre_commit` by absolute path, which exists and lacks
the module, so the next `git commit` dies with `No module named
pre_commit`. `uv sync` restores it.

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

### Reproducing what CI runs

Each command below is the one a CI job runs, verbatim. Keep this section
true when a workflow changes.

`os-ubuntu.yml`, `os-macos.yml` and `os-windows.yml`, the suite job of
each — the suite, on one cell of a platform matrix. `--no-cov` undoes the
`--cov` addopts carries: a cell asks whether one (image, interpreter)
pair passes, and the `coverage` job below is where coverage is measured
once, gated, and reported instead:

```shell
uv run --locked --no-default-groups --group test pytest --no-cov
```

`test.yml`, the `coverage` job — `--cov` is in addopts, so this and the
bare `pytest` above are the same measurement; what this job adds is the
report:

```shell
uv run --locked --no-default-groups --group test \
    pytest --cov-report term-missing:skip-covered
```

`test.yml`, the `dist` job — build the distribution files, check them
and install one. This is the one build there is (issue #1166):
`release.yml`'s `test` job calls this workflow, so a tag runs the very
same job, and its own `publish-testpypi` and `publish-pypi` jobs download
the `dist` artifact this job uploads rather than building a second copy
— so what the checks below judge is what an index ends up serving, byte
for byte. The first two commands are what make the sdist's determinism
this tree's rather than the backend's — `uv_build` already writes a fixed
timestamp into both archives and ignores `SOURCE_DATE_EPOCH`, and
`normalize_sdist.py`'s docstring is where that measurement and the reason
to run it anyway are. `sha256sum` after them is the digest a rebuild from
the tag is compared against, per RELEASING.md's "Rebuild a release from
its tag". The distribution files are uploaded before anything below
installs a package: installing a dependency executes its code, and a
compromised one must not reach a `dist/` that still has to be handed on:

```shell
export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
uv build
uv run --no-project --python 3.14 .github/scripts/normalize_sdist.py dist/
sha256sum dist/*
uv run --locked --only-group check twine check --strict dist/*
uv run --locked --only-group check check-wheel-contents dist/*.whl
uv run --locked --only-group check pyroma --min 10 dist/*.tar.gz
```

A rehearsal (`workflow_dispatch`) runs one command ahead of the block
above, which the tag path skips: `.github/actions/dev-version` rewrites
`pyproject.toml`'s version with the suffix `release.yml`'s
`version-check` job computed and re-locks, so that `uv build` above
ships a version TestPyPI has not already seen. None of the three checks
mind — what they judge is metadata syntax, README rendering and metadata
quality, none of which the suffix changes.

The job then installs the wheel it just built and checked, alone, from
an empty directory, and uses it:

```shell
tmp=$(mktemp -d)
cd "$tmp"
uv venv
uv pip install "$OLDPWD"/dist/*.whl
.venv/bin/python -c "
from decimal import Decimal
from importlib.metadata import requires, version
import json
import bitcoin_core_rpc as rpc

name = 'bitcoin-core-rpc'
print(version(name))
assert not requires(name), requires(name)
replies = []
def transport(request, timeout):
    request_id = json.loads(request.data)['id']
    replies.append(request_id)
    body = {'jsonrpc': '2.0', 'id': request_id, 'result': 1.25}
    return 200, json.dumps(body).encode()
client = rpc.BitcoinCoreRpcClient.from_chain(
    'regtest', user='u', password='p', transport=transport
)
assert client.call('getbalance') == Decimal('1.25')
assert len(replies) == 1
"
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
    --group test --python 3.10 pytest --no-cov
```

### What gates a merge, and what only reports

`lint.yml`, `test.yml`, `docs.yml` and `integration-bitcoind.yml` produce the
required checks, and `REPOSITORY.md` reads the rule back from the
endpoint rather than restating it. So a diff does not reach a review
without having passed them or passing them beside it on the same sha,
which is the reliance `REVIEWING.md` provides for.

| workflow | when | what it varies |
| --- | --- | --- |
| `test` | pull request, push | — |
| `lint`, `docs` | pull request, push | — |
| `claude-review` | pull request, and `@claude` in a comment | — |
| `bitcoind` | pull request, push | Core's two ends, then 5 chains |
| `codeql` | push to main, and weekly | 2 languages |
| `os-ubuntu` | weekly, a release | 2 ubuntu images × 7 interpreters |
| `os-macos` | weekly, a release | 2 macOS images × 7 interpreters |
| `os-windows` | weekly, a release | 2 Windows images × 7 interpreters |
| `deps-latest` | weekly | 3 images × the floor and the ceiling, upgraded |
| `bitcoind` | weekly | every Core major, then 5 chains on the newest |
| `links` | weekly | — |
| `mutation` | weekly | — |
| `pypi-install` | weekly, a release | what PyPI serves |
| `release` | a tag | the workflows it calls |

Which workflows that last row covers is
`grep -n 'uses: \./\.github/workflows/' .github/workflows/release.yml`,
not a list here: a list restated is one more thing to keep true.

Those gates run one image on one interpreter: `ubuntu-latest`, and the
version `.python-version` names. `claude-review` gates nothing: its own
header says it must not become a required check, a review that gates a
merge making a model's judgement a branch rule.

Which day each of the rest runs is section 10 of the organization
standard, in `btclib-org/.github`, and not this file's to restate — one
calendar covering six repositories is one thing to remember.

Why so little gates is one number: GitHub Free gives an organization twenty
concurrent jobs, shared across every repository in it. The platform sweeps
on every commit ask for twice that between them, so a pull request spends
its wall clock waiting for a slot rather than running anything.
At that ceiling a second image before a review buys a rarer answer at the
price of every review: macOS queues 15.7 and 13.1 minutes on average against
0.1 to 0.3 elsewhere, on cells that each run in under a minute, and the
fourteen Windows cells were 9.4 of the run's 16.9 runner-minutes.

**What the sentinels vary, they vary whole.** `os-ubuntu` runs the images
and the interpreters the gate does not sweep *and* the cell it does, and
`bitcoind` runs every Core major including the two it gates on. A matrix
with the gate's cells cut out of it is one nobody can read the shape of, and
whoever asked what ran would have to re-derive the hole from the gate.

`windows-latest` is in `os-windows` rather than on the gate, and the
platform-conditional branch it answers for is the datadir table in
`default_datadir`, whose rows the suite drives by patching `sys.platform` —
every row but the running one, so `%APPDATA%` and the `Path.home()` under it
are asked for real only on a Windows runner. That question does not vary
with the architecture the interpreter targets, which is why one row of that
matrix answers it and the rest are there for the standard library beneath.

`os-ubuntu`, `os-macos` and `os-windows` hold the dependencies at the lock
and move the platform; `deps-latest` moves both, and one variable each is
what lets the pair be read as a difference — `os-macos.yml`'s header states
that reading for its own column, and it is the same on the other two. Every
workflow here also takes `workflow_dispatch`, gates included, `claude-review`
excepted — `grep -c workflow_dispatch: .github/workflows/*.yml` is what says
so, and for `codeql` and the three image workflows it is the only way to ask
about a branch at all. `claude-review` takes none because both its jobs read
the pull request or the comment that triggered them, so a manual run would
start with nothing to read.

`codeql` runs on `main` and on its weekly schedule and not on a pull
request, which is the same arithmetic as the rows above: it holds slots
while a review waits. What still reads a branch before it merges is
`zizmor`, a `pre-commit` hook and therefore part of `lint`, which audits
these workflows for an injected expression. `REPOSITORY.md` has the trade in
full. It is also the one gate `release` does not call, a tag publishing the
tree those checks already passed.

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

`integration-bitcoind.yml` is the one claim the recorded replies cannot make.
Against a `bitcoind` of your own — it runs on a regtest chain in a temporary
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
