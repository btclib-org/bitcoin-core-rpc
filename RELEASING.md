# Releasing

Releases are published by GitHub Actions
([release.yml](.github/workflows/release.yml)), not from a developer
machine. Pushing a `v<version>` tag runs the full test matrix, builds and
checks the distribution files, publishes them to PyPI, and creates the
GitHub release. There is no PyPI token anywhere: both indices are
configured to trust the workflow itself
([Trusted Publishing](https://docs.pypi.org/trusted-publishers/)).

The same workflow, started by hand instead of by a tag, is a full rehearsal
against TestPyPI. A rehearsal is never tagged.

## One-time setup

Neither index holds the project until an upload creates it, so both entries
below are added as *pending* publishers, on that same page: a publisher
attached to a project can only be added to a project that exists, and a
first upload has nothing else to authenticate with, there being no token
anywhere. The upload PyPI accepts turns its pending entry into an ordinary
one, and TestPyPI's rehearsal does the same there.

1. On [PyPI](https://pypi.org/manage/account/publishing/), add a trusted
   publisher: PyPI project name `bitcoin-core-rpc`, owner `btclib-org`,
   repository `btclib-bitcoin-core-rpc`, workflow `release.yml`,
   environment `pypi`.

1. On [TestPyPI](https://test.pypi.org/), add the same trusted publisher,
   with environment `testpypi`.

1. In the GitHub repository settings, create the `pypi` and `testpypi`
   environments. Both require a review, so neither index is uploaded to
   without a human approving that run; the two `publish-*` jobs are the
   only holders of `id-token: write`, and this is the gate in front of
   them. `pypi` is additionally restricted to `v*` tags, which is the only
   ref its job runs on anyway — the restriction is what makes that true of
   the environment and not just of an `if:` in a file a pull request could
   change.

## Rehearse on TestPyPI

A rehearsal runs the identical pipeline — lint gate, test matrix, the
packaging checks of the `dist-py` job, build, wheel smoke test — and
publishes to TestPyPI instead of PyPI.

1. On GitHub, Actions → release → Run workflow, and pick the branch to
   rehearse (usually `dev`).

1. The workflow appends `.dev<run number>` to the version, so every
   rehearsal is unique on TestPyPI and sorts before the release it
   rehearses. Re-running a finished rehearsal would reuse its run number
   and be refused by TestPyPI: dispatch a fresh run instead.

1. Check the upload, and optionally install it — it has no dependency to
   resolve from anywhere:

   ```shell
   uv run --isolated --no-project \
     --index https://test.pypi.org/simple/ \
     --with bitcoin-core-rpc \
     python -c "import bitcoin_core_rpc; print(bitcoin_core_rpc.DEFAULT_TIMEOUT)"
   ```

## Ask a live node first

The recorded replies say what Core sent when they were recorded. Before a
release, ask two live nodes whether it still sends that: Actions →
rpc-smoke → Run workflow, which downloads a pinned bitcoind of each version
in its matrix, verifies the archive against a digest written in the
workflow, and runs `.github/scripts/rpc_smoke.py` against a regtest chain
it generates. CONTRIBUTING.md has the same command for a node of your own.

It gates nothing automatically, which is why it is a step here.

## Release

1. Retitle the work-in-progress sections of [HISTORY.md](./HISTORY.md) and
   [CHANGELOG.md](./CHANGELOG.md) to `## v<version>` — the heading must be
   the version alone, and the section must not be empty. `release.yml`
   checks both before anything is built, because a version cannot be
   unpublished once an index has accepted it.

1. Set the version in `pyproject.toml`, which is the one place it is
   declared, and re-lock so `uv.lock` agrees:

   ```shell
   uv lock
   ```

1. Merge `dev` into `master` with **"Rebase and merge"** — read the button,
   GitHub offers whichever method was used last, and a squash there would
   fold every landed change into one commit.

1. Tag `master` and push the tag:

   ```shell
   git tag v<version>
   git push origin v<version>
   ```

1. Approve the `pypi` environment when the workflow asks. The GitHub
   release is created afterwards, from HISTORY.md's section for the tag: a
   release announces what users can already install.

1. Add the new work-in-progress headings back to HISTORY.md and
   CHANGELOG.md on `dev`.
