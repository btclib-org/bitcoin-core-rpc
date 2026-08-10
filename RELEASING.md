# Releasing bitcoin-core-rpc

Releases are published by GitHub Actions
([release.yml](.github/workflows/release.yml)), not from a developer
machine. Pushing a `v<version>` tag runs the full test matrix, builds and
checks the distribution files, publishes them to PyPI, and creates the
GitHub release. There is no PyPI token anywhere: both indices are
configured to trust the workflow itself
([Trusted Publishing](https://docs.pypi.org/trusted-publishers/)).

The same workflow, started by hand instead of by a tag, is a full rehearsal
against TestPyPI. A rehearsal is never tagged.

**A workflow GitHub has not registered cannot be dispatched, and it
registers one only once its file has reached the default branch.** That
makes `release.yml`, `latest.yml` and `published.yml` — `schedule` and
`workflow_dispatch` only, so nothing else ever triggers them — answer
`gh: Not Found (HTTP 404)` until the pull request adding it is merged. It
bites once, on the first release after any of them is written, and it
inverts the order below: the TestPyPI rehearsal that this file asks for
*before* the merge can only happen after it, still before the tag. It also
means such a workflow reaches `main` having never run.

## Which version string is which

Telling these apart is most of what can go wrong when cutting a release.

- **`pyproject.toml`'s own `version`** takes three shapes over one cycle,
  never two at once: `2026.9`, month only, between releases — the
  placeholder "Open the next cycle" sets, so a checkout of `main` reports
  itself as work in progress rather than as a release it is not;
  `2026.8.6`, with the day added on release day — calendar versioning,
  `YYYY.M.D` — which is what gets published; and `2026.8.6.1`, a fourth
  number added only if `2026.8.6` shipped broken and cannot be reuploaded
  (see "If something goes wrong"). All three are typed by hand. Three
  components is always the release day; four is always a patch on it. The
  day is never dropped in favour of a fourth digit standing in for it,
  which is what would make the two indistinguishable — and `version-check`
  refuses a tag on the placeholder shape for exactly that reason: two
  components reach the check and nothing past it, whichever one is
  declared. It does not tell three apart from four, both being a release
  it accepts
- **`v2026.8.6`**, the tag, carries no version of its own: it picks the
  index, PyPI rather than TestPyPI, and `version-check` exists to
  confirm it says what `pyproject.toml` says
- **`2026.8.6.dev7`** is a rehearsal, and nobody types it either half at
  a time: `.dev<run number>` is the template `release.yml` appends to
  what `pyproject.toml` declares when `workflow_dispatch` starts it, the
  number being `github.run_number` counted for that workflow alone, so
  the seventh such run rehearsing `2026.8.6` produces exactly that. The
  count is what makes a rehearsal's version unique, and what makes
  re-running a finished one collide with itself rather than mint a new
  one. Nothing writes it down, and no commit ever carries it
- **`2026.8.6rc1`**, and a `v2026.8.6rc1` tag, have no place in this
  scheme: there are no release candidates here, only a version not yet
  tagged. `version-check` refuses anything that is not digits and dots,
  which is what stops `2026.8.6rc1` before a tag is even pushed — and
  what a `v2026.8.6rc1` tag would otherwise pass, burning a pre-release
  on PyPI itself, where `--pre` installs would find it from then on

PEP 440 sorts `2026.8.6.dev7` before `2026.8.6`, so a rehearsal never
shadows the release it rehearses. `git tag` on its own does not read the
numbers the same way: measured, `v2026.10` lists before `v2026.7`,
alphabetically rather than chronologically. `git tag --sort=v:refname`
reads them as PEP 440 does.

## One-time setup

Neither index holds the project until an upload creates it, so both entries
below are added as *pending* publishers, on that same page: a publisher
attached to a project can only be added to a project that exists, and a
first upload has nothing else to authenticate with, there being no token
anywhere. The upload PyPI accepts turns its pending entry into an ordinary
one, and TestPyPI's rehearsal does the same there.

1. On [PyPI](https://pypi.org/manage/account/publishing/), add a trusted
   publisher: PyPI project name `bitcoin-core-rpc`, owner `btclib-org`,
   repository `bitcoin-core-rpc`, workflow `release.yml`,
   environment `pypi`.

1. On [TestPyPI](https://test.pypi.org/), add the same trusted publisher,
   with environment `testpypi`.

1. In the GitHub repository settings, create the `pypi` and `testpypi`
   environments. Both require a review from `fametrano`, so neither
   index is uploaded to without a human approving that run; the two
   `publish-*` jobs are the only holders of `id-token: write`, and this
   is the gate in front of them. `pypi` is additionally restricted to
   `v*` tags, which is the only ref its job runs on anyway — the
   restriction is what makes that true of the environment and not just
   of an `if:` in a file a pull request could change.

   Self-review stays allowed on purpose: the maintainer who pushes the
   tag is the reviewer, and forbidding it would deadlock a
   one-maintainer release. The approval is a confirmation step, not a
   second pair of eyes; it becomes one as soon as there is a second
   reviewer to add.

## Rehearse on TestPyPI

A rehearsal runs the identical pipeline — lint gate, test matrix, the
packaging checks of the `dist-py` job (twine, check-wheel-contents,
pyroma), build, wheel smoke test — and publishes to
[TestPyPI](https://test.pypi.org/project/bitcoin-core-rpc/) instead of
PyPI.

1. On GitHub, Actions → release → Run workflow, and pick the branch to
   rehearse (usually `main`).

1. The workflow appends `.dev<run number>` to whatever `pyproject.toml`
   declares on the branch dispatched — the outgoing cycle's placeholder if
   the version about to ship has not landed yet, which publishes something
   like `2026.9.dev4` and still tests the identical pipeline the tag will
   run; the number is not what is being asked about.
   Every rehearsal is unique on TestPyPI this way. It sorts before the
   release it rehearses once that release's own version is the one
   declared, which is what the rehearsal after the merge below runs on; a
   placeholder naming a later month sorts after the day it rehearses
   instead, which costs nothing — `.dev` is a pre-release no plain install
   resolves, and the release itself never reaches TestPyPI. Re-running a
   finished rehearsal would reuse its run number and be refused by
   TestPyPI: dispatch a fresh run instead.

1. Check the upload, and optionally install it — it has no dependency to
   resolve from anywhere:

   ```shell
   uv run --isolated --no-project \
     --index https://test.pypi.org/simple/ \
     --with bitcoin-core-rpc \
     python -c "import bitcoin_core_rpc; print(bitcoin_core_rpc.DEFAULT_TIMEOUT)"
   ```

1. Check that the `attest` job is green. It signs a rehearsal's files too,
   which is what it is here for: the release path attests after PyPI has
   the distribution files and the tag can no longer be moved, so a
   permission or an API that only works on release day is one this job
   would find there. What it produces here goes no further than an
   artifact of the run — no release is cut from a dispatch, so nothing is
   attached anywhere — and the attestation it records names a `.dev`
   version nothing resolves.

## Ask a live node first

The recorded replies say what Core sent when they were recorded. Before a
release, ask two live nodes whether it still sends that: Actions →
rpc-smoke → Run workflow, which downloads a pinned bitcoind of each version
in its matrix, verifies the archive against a digest written in the
workflow, and runs `.github/scripts/rpc_smoke.py` against a regtest chain
it generates. CONTRIBUTING.md has the same command for a node of your own.

It gates nothing automatically, which is why it is a step here.

## Release to PyPI

**A release is a tag on `main`, and everything below that edits a file
does so on a branch of its own.** Nothing is pushed to `main` directly,
this release included: the steps that retitle the notes and set the
version are one pull request, the one that opens the next cycle is
another, and the tag names the commit the first of them left behind.

`latest` is worth dispatching before the tag rather than waiting for its
cron, because what it answers is cheaper to know before a version is
consumed than after. It gates nothing, so it will not stop you: reading it
is the point.

**Read it per job, not as a verdict**, and open the failure rather than
inferring it from a sibling. A release ships what `uv.lock` pins, so drift
against a newer version of some dependency does not make the release
wrong — it says the next bump is going to be work.

1. Read the public API against the previous release, before the notes that
   describe it are declared final. [HISTORY.md](./HISTORY.md) promises that
   a breaking change is announced there, the calendar version promising
   nothing, and nothing else reads that promise: the suite judges the code,
   and a reviewer weighs what the prose says rather than what it leaves
   out. griffe reads both revisions and answers that second question — not
   whether the list is right, but whether it is complete:

   ```shell
   uv run --locked --with griffe griffe check bitcoin_core_rpc \
       -a v<previous version>
   ```

   It reports breakage only: a public object removed, a parameter that
   changed kind or default, an attribute whose value moved. An addition is
   silent, so the output is short and every line of it wants an entry —
   what the step asks is that nothing it names is missing from HISTORY.md.
   The converse is not its to answer: an entry describing a break it did
   not find is a claim about the prose, which review still has to read.
   That it catches a real one is measured rather than assumed: run it with
   `-a 379ae2d -b 873ae03` instead, spanning the exception rename the
   `### Changed` group of v2026.8.6 records, and it names each removed
   spelling.

   Not a hook and not a job of `lint.yml`, deliberately: the comparison is
   against the previous *release*, so a break lands on `main` on purpose and
   remains a finding until the release that announces it, leaving every
   pull request in between red for something no branch introduced. It exits
   1 on a finding, so the day that reasoning stops holding — a cycle that
   means to break nothing — making it a gate is one line.

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

1. Give the release pull request its title and its body, before merging it
   and not after. The title is the version; the body says what the release
   is — what moved, what did not, and which of the two a user would
   notice. A squash leaves one commit whose message is that title, so the
   pull request is where the rest stays, and where a reader arriving from
   that commit lands. A template left unfilled, or a bot's summary of the
   diff, is not a substitute — the summary can stay, but what the diff
   cannot say has to be written, and what a reader should not have to
   discover at the button belongs there too.

   The work-in-progress section of HISTORY.md is what that body is written
   from, and the reason it is filled in one landed change at a time rather
   than reconstructed from the diff on release day. Check it against
   `git log v<previous version>..main --oneline` regardless of how current
   it looks, rather than trust that every line landed when it should have.
   Griffe's result and the rpc-smoke run belong in the body too, each a
   line rather than a screenshot — both are steps nothing else enforces,
   and a pull request that never mentions them reads exactly like one that
   skipped them.

1. Run `uv run pre-commit run --all-files` and `uv run pytest --cov`
   before pressing anything, then verify the
   [read the docs](https://readthedocs.org/projects/bitcoin-core-rpc/builds/)
   build renders. Read the *builds* page and not only the rendered one: a
   site that answers 200 may be serving the last build that succeeded,
   the webhook having quietly refused every delivery since.

1. Merge it with **"Squash and merge"**, as every other pull request here
   — read the button, GitHub offers whichever method was used last.

   Then read `lint` and `test` on the commit `main` ends up at before
   tagging, rather than trust the pull request's own green run:

   ```shell
   gh run list --commit "$(git rev-parse origin/main)"
   ```

   a squash creates a commit that is not the one the pull request tested,
   and the push to `main` fires both workflows again from their own `push`
   trigger — a run of its own, not the `pull_request` run already green a
   moment earlier. That trigger is the whole reason `main` keeps one.

1. Rehearse on TestPyPI (see above) from `main`.

1. Tag the release commit on `main` and push the tag. **Name the
   commit**, and read the tag back before pushing it:

   ```shell
   git tag -a v2026.8.6 -m "release v2026.8.6" <sha of the release commit>
   git show v2026.8.6:pyproject.toml | grep '^version'
   git push origin v2026.8.6
   ```

   `git tag` with no commit tags whatever HEAD the shell is in, and every
   step above ran in a worktree while the primary checkout sits on another
   branch — so the argumentless form is one `cd` away from tagging the
   commit before the version bump. `version-check` would refuse it,
   comparing the declared version against the tag's and failing the run
   with nothing uploaded, which is the guard doing its job; the `git show`
   above is the same check one step earlier, where it costs nothing.

1. Approve the `pypi` environment when the workflow asks. Up to here
   nothing is public and the tag can still be deleted; the upload that
   follows is the point of no return — the upload, and not the approval,
   the token exchange happening after it. A registration that does not
   match the claims fails there having uploaded nothing, and a version
   survives a failed exchange: delete the tag, fix the registration, tag
   again.

   A registration that matched once can still go stale on its own — a
   repository rename is enough — without anything here flagging it before
   the upload tries. Sibling repository btclib-libsecp256k1 hit exactly
   this on a real tag rather than a rehearsal: the matrix had already
   built everything and only the token exchange failed, so retagging
   would have rebuilt it for nothing. Fixing the registration and running
   `gh run rerun <run id> --failed` republished from the artifacts
   already there in minutes instead. Retagging is the right answer only
   when the failure happened before those artifacts existed — see "If
   something goes wrong" below.

1. Install what was just published, in an environment of its own rather
   than one that may already hold it, and run something with it:

   ```shell
   uv run --isolated --no-project --with bitcoin-core-rpc \
     python -c "import bitcoin_core_rpc; print(bitcoin_core_rpc.DEFAULT_TIMEOUT)"
   ```

   then check the attestations — the JSON API answers `null` for
   `provenance` even where they exist; the
   [simple API](https://pypi.org/simple/bitcoin-core-rpc/) (`Accept:
   application/vnd.pypi.simple.v1+json`) carries the real link, under
   `/integrity/<project>/<version>/<filename>/provenance`, and
   `pypi-attestations verify pypi <file> --repository
   https://github.com/btclib-org/bitcoin-core-rpc` checks the
   signature rather than merely its presence.

1. Dispatch the `published` workflow (Actions → published → Run workflow)
   and expect it green: it installs what was just uploaded from PyPI, on
   every platform test.yml builds for and at both ends of the supported
   interpreter range, and round-trips a JSON-RPC call against it. From
   then on it runs weekly on its own, and a failure means the outside
   world moved, not this repository — a new runner image, an interpreter
   release, PyPI serving a file that does not match its own hash — which
   is why it is a workflow of its own rather than a job of this one.

1. Check the GitHub release the previous step's workflow run created: its
   notes are the tag's section of HISTORY.md, and the distribution files
   are attached, `<tag>.attestation.jsonl` beside them. A run that logs
   `HISTORY.md has no v<version> section` generated the notes from the
   merged pull requests instead — the fallback `version-check` exists to
   make unreachable, not a second way to write release notes — and they
   are worth replacing by hand if it ever fires.

1. Verify the provenance of an asset, which is the release's own and not
   the PEP 740 attestations checked two steps up: those cover the copies
   on the index, these the copies attached here. Both forms, the same
   signature read two ways:

   ```shell
   gh release download v2026.8.8 --repo btclib-org/bitcoin-core-rpc
   wheel=bitcoin_core_rpc-2026.8.8-py3-none-any.whl
   repo=btclib-org/bitcoin-core-rpc
   gh attestation verify "$wheel" --repo "$repo" \
     --signer-workflow "$repo/.github/workflows/release.yml"
   gh attestation verify "$wheel" --repo "$repo" \
     --bundle v2026.8.8.attestation.jsonl
   ```

   the first asks the attestations API for the signed statement, the
   second reads it from the asset and asks nothing — which is what the
   bundle is attached for, mirroring the releases page being the case it
   answers. One attestation covers both files, so the sdist verifies
   against the same bundle.

   `--signer-workflow` is the flag that makes the check say *which*
   workflow signed: without it a valid attestation from any workflow in
   the repository passes. Neither form is offline on its own — the
   Sigstore trusted root comes over the network unless
   `gh attestation trusted-root > trusted_root.jsonl` fetched it earlier
   and `--custom-trusted-root` points at it.

1. Open the next cycle, in a pull request of its own and before anything
   else lands: set a generic next version without the day (e.g. after
   2026.8.6, use 2026.9) in `pyproject.toml`, and start a new "work in
   progress" section in HISTORY.md and CHANGELOG.md. Two components is the
   shape nothing tagged can have, so a checkout of `main` between releases
   reports itself as work in progress rather than as a release it is not,
   and `version-check` refuses it should it ever reach a tag — which is a
   second guard behind the heading check, not a replacement for it.
   Re-lock so `uv.lock` agrees:

   ```shell
   uv lock
   ```

   That empty section is what the next release's notes are written into,
   one landed change at a time, and opening it now is what keeps the next
   cycle's body from being reconstructed from the diff on release day.

## Rebuild a release from its tag

The release job exports `SOURCE_DATE_EPOCH` from the commit date and
normalizes the sdist, so a rebuild of a released tag is the same bytes as
what was published. Anyone can check that, and the check is one command
short of the provenance one above: verify the *rebuilt* file rather than a
downloaded one, and it can only pass if the digests agree.

```shell
git checkout v2026.8.8
SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) uv build
uv run --no-project --python 3.14 .github/scripts/normalize_sdist.py dist/
repo=btclib-org/bitcoin-core-rpc
gh attestation verify dist/bitcoin_core_rpc-2026.8.8-py3-none-any.whl \
  --repo "$repo" --signer-workflow "$repo/.github/workflows/release.yml"
gh attestation verify dist/bitcoin_core_rpc-2026.8.8.tar.gz \
  --repo "$repo" --signer-workflow "$repo/.github/workflows/release.yml"
```

Two things bound that guarantee, and both are worth knowing before
reading a mismatch as tampering:

- **the build backend is resolved, not pinned.** `[build-system] requires`
  asks for `setuptools>=77` and an isolated build takes whatever is
  current, so a rebuild months later runs a setuptools the release never
  saw. A mismatch dates the rebuild before it accuses anyone; pinning the
  backend to a version is the fix, and the cost is a floor that ages.
- **the rehearsal is a different version, by construction.** A TestPyPI
  dispatch appends `.dev<run number>` to the version, so its files are not
  a second build of the release's — they are their own artifact, published
  where they say they are. The attestation the rehearsal writes covers
  those, and no digest is shared with the release.

## If something goes wrong

- The workflow failed before the `publish-pypi` job: nothing was
  uploaded. Delete the tag, fix, and tag again:

  ```shell
  git tag -d v<version>
  git push origin :refs/tags/v<version>
  ```

  Both lines, and the local one is the half that is easy to skip: a tag is
  per-repository where a branch is per-worktree, so deleting it in one
  worktree leaves it in every other, and the `git tag -a` that follows
  answers `fatal: tag 'v<version>' already exists` — from a checkout that
  looks uninvolved. Delete locally wherever it is, then re-create.

- `publish-pypi` itself ran and failed at the token exchange
  (`invalid-publisher`), after the matrix had already built everything:
  nothing was uploaded, but retagging would rebuild what was never at
  fault. Fix the registration and re-run the publish job alone against
  what is already built:

  ```shell
  gh run rerun <run id> --failed
  ```

  a fresh approval of the `pypi` environment is still required, the
  protection applying per deployment attempt rather than once per run.
  This is a different case from the one above: there, the workflow never
  reached `publish-pypi`, so there is nothing to re-run and no artifact to
  re-run it against.

- The upload succeeded but the release is broken: PyPI never accepts a
  file name twice, even after deletion. Yank the bad release on PyPI and
  publish a new patch version, a fourth number on the day
  (`2026.8.6` → `2026.8.6.1`).

- Only the `github-release` job failed: the PyPI upload is already done;
  re-run the failed job, or create the release by hand from the `dist`
  artifact of the run.
