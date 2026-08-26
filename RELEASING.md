# Releasing bitcoin-core-rpc

Releases are published by GitHub Actions
([release.yml](./.github/workflows/release.yml)), not from a developer
machine. Pushing a `v<version>` tag runs the full test matrix, builds and
checks the distribution files, publishes them to PyPI, and creates the
GitHub release. There is no PyPI token anywhere: both indices are
configured to trust the workflow itself
([Trusted Publishing](https://docs.pypi.org/trusted-publishers/)).

The same workflow, started by hand instead of by a tag, is a full rehearsal
against TestPyPI. A rehearsal is never tagged.

**A workflow GitHub has not registered cannot be dispatched, and it
registers one only once its file has reached the default branch.** Any new
workflow therefore answers `gh: Not Found (HTTP 404)` to `gh workflow run`
until the pull request adding it is merged. What makes that more than a
nuisance is the set no commit and no pull request fires either, which is
otherwise never exercised before the merge at all: `release.yml`, whose
`push:` names tags and nothing else, and the workflows below.

```shell
grep -L -E '^  (push|pull_request):' .github/workflows/*.yml
```

It bites once, on the first release after any of them is written, and it
inverts the order below: the TestPyPI rehearsal that this file asks for
*before* the merge can only happen after it, still before the tag. It also
means such a workflow reaches `main` having never run.

## Which version string is which

Telling these apart is most of what can go wrong when cutting a release.

- **`pyproject.toml`'s own `version`** shifts shape over one cycle,
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
- **`2026.8.6.dev701`** is a rehearsal, and nobody types it either half
  at a time: `.dev<run*100+attempt>` is the template `release.yml`
  appends to what `pyproject.toml` declares when `workflow_dispatch`
  starts it, `github.run_number` counted for that workflow alone and
  `github.run_attempt` counted for one dispatch of it, so the seventh
  such run's first attempt, rehearsing `2026.8.6`, produces exactly
  that. The multiplier is what makes a re-run a version of its own
  rather than a collision: a re-run keeps the run's own number and only
  raises the attempt, so the run number alone was identical across every
  re-run of one dispatch and PEP 440 could not tell them apart. Placing
  the attempt below the run number's own place value keeps a run's later
  attempts sorting after its earlier ones and before the next run's, the
  attempt therefore capped at two digits and the workflow refusing a
  hundredth rather than silently wrapping into the next run's range.
  Nothing writes it down, and no commit ever carries it
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
   index is uploaded to without a human approving that run; `publish-pypi`
   and `publish-testpypi` are the only holders of `id-token: write` that
   carry one of these two environments, and this is the gate in front of
   them. `attest` holds `id-token: write` too, for its own Sigstore
   exchange, but no environment of its own — what gates it instead is
   `needs: [publish-pypi, publish-testpypi]`, so it never runs before one
   of the two reviewed jobs already has. `pypi` is additionally restricted
   to `v*` tags, which is the only ref its job runs on anyway — the
   restriction is what makes that true of the environment and not just
   of an `if:` in a file a pull request could change.

   Self-review stays allowed on purpose: the maintainer who pushes the
   tag is the reviewer, and forbidding it would deadlock a
   one-maintainer release. The approval is a confirmation step, not a
   second pair of eyes; it becomes one as soon as there is a second
   reviewer to add.

## Rehearse on TestPyPI

A rehearsal runs the identical pipeline — lint gate, test matrix, the
`dist` job's build, its packaging checks (twine, check-wheel-contents,
pyroma) and its wheel smoke test — and publishes the very files those
checks passed to
[TestPyPI](https://test.pypi.org/project/bitcoin-core-rpc/) instead of
PyPI (issue btclib-org/btclib#1166: the `dist` job used to build its own
copy while a separate `build` job in `release.yml` built a second one
and ran the same three checks on it again (issue #155); that job no
longer exists, so what release.yml publishes and what test.yml checked
are now the same files).

**What it answers is whether the publish path still works**, so it earns
its run when that path or what travels it has moved: `release.yml` or a
workflow it calls, `pyproject.toml`'s packaging metadata — the build
backend and the patterns of `[tool.uv.build-backend]` above all —
`normalize_sdist.py`, the trusted publisher registration, or the addition
of a file the distribution has to carry. A cycle that changed the module
and the prose and nothing else is one the tag's own run judges as well,
every job up to `publish-pypi` being the same job — and skipping it is
the maintainer's call to make and to say out loud in the release pull
request, not a step to leave silently undone. What is given up either way
is the token exchange and the upload, which no rehearsal on `main` proves
for PyPI anyway: `pypi` and `testpypi` are two registrations, and only
the tag exercises the first.

1. On GitHub, Actions → release → Run workflow, and pick the branch to
   rehearse (usually `main`).

1. The workflow appends `.dev<run*100+attempt>` to whatever
   `pyproject.toml` declares on the branch dispatched — the outgoing
   cycle's placeholder if the version about to ship has not landed yet,
   which publishes something like `2026.9.dev401` and still tests the
   identical pipeline the tag will run; the number is not what is being
   asked about.
   Every rehearsal is unique on TestPyPI this way, re-runs included: a
   re-run raises only `github.run_attempt`, which the run number is
   multiplied by 100 to make room for, so re-running a failed or finished
   rehearsal mints its own version instead of colliding with the one it
   repeats. It sorts before the release it rehearses once that release's
   own version is the one declared, which is what the rehearsal after
   the merge below runs on; a placeholder naming a later month sorts
   after the day it rehearses instead, which costs nothing — `.dev` is a
   pre-release no plain install resolves, and the release itself never
   reaches TestPyPI.

1. Check the upload, and optionally install it — it has no dependency to
   resolve from anywhere:

   ```shell
   uv run --isolated --no-project \
     --index https://test.pypi.org/simple/ \
     --with bitcoin-core-rpc \
     python -c "import bitcoin_core_rpc;
     print(bitcoin_core_rpc.DEFAULT_TIMEOUT)"
   ```

1. Check that the `attest` job is green. It signs a rehearsal's files too,
   which is what it is here for: the release path attests after PyPI has
   the distribution files and the tag can no longer be moved, so a
   permission or an API that only works on release day is one this job
   would find there. What it produces here goes no further than an
   artifact of the run — no release is cut from a dispatch, so nothing is
   attached anywhere — and the attestation it records names a `.dev`
   version nothing resolves.

## A live node has already been asked

The recorded replies say what Core sent when they were recorded, and whether
Core still sends that is checked on every pull request:
`integration-bitcoind.yml` is a required check, and `release.yml` calls it again
on the tag. Nothing to dispatch here, and nothing to remember -- the step this
section used to be is what the required check replaced.

Dispatch it by hand only to ask about a Core version the matrix does not
carry, or when a run needs repeating without a push: Actions → bitcoind →
Run workflow. CONTRIBUTING.md has the same command for a node of your own.

## Release to PyPI

**A release is a tag on `main`, and everything below that edits a file
does so on a branch of its own.** Nothing is pushed to `main` directly,
this release included: the steps that retitle the notes and set the
version are one pull request, the one that opens the next cycle is
another, and the tag names the commit the first of them left behind.

`deps-latest` is worth dispatching before the tag rather than waiting for
its cron, because what it answers is cheaper to know before a version is
consumed than after. It gates nothing, so it will not stop you: reading it
is the point.

**Read it per job, not as a verdict**, and open the failure rather than
inferring it from a sibling. A release ships what `uv.lock` pins, so drift
against a newer version of some dependency does not make the release
wrong — it says the next bump is going to be work.

Whether to close that drift now — `uv lock --upgrade`, gated by nothing
here — or leave it for Dependabot's own pull requests is a decision
worth stating rather than defaulting by omission: silence at the tag
reads as "nobody looked", not as "looked and chose to leave it". State
the choice in the release pull request, next to `deps-latest`'s own
result.

1. Read what is open, and land first anything that fixes the release path
   itself:

   ```shell
   gh pr list --state open
   gh pr list --state open --search "release.yml OR pypi-install.yml"
   ```

   A pull request touching `release.yml`, anything under
   `.github/scripts/`, or any workflow `release.yml` calls is one the tag
   is about to run, so leaving it in review means running the defect it
   fixes on the release. What it calls is a list this file would only let
   rot, so read it from the file itself:

   ```shell
   grep -n 'uses: \./\.github/workflows/' .github/workflows/release.yml
   ```

   It is not caught anywhere else: every one of those workflows is
   green on the pull request that fixes it, which is what makes it look
   like something that can wait. `pypi-install.yml` is the case to watch,
   its own failures arriving after PyPI has already accepted the files.

   The reverse question is worth the same minute: a pull request that is
   *not* ready is one this release ships without, so what the notes claim
   is what landed rather than what is nearly landed.

1. Read the public API against the previous release, before the notes that
   describe it are declared final. [RELEASE_NOTES.md](./RELEASE_NOTES.md)
   promises that a breaking change is announced there, the calendar version
   promising nothing, and nothing else reads that promise: the suite judges the
   code, and a reviewer weighs what the prose says rather than what it leaves
   out. griffe reads both revisions and answers that second question — not
   whether the list is right, but whether it is complete:

   ```shell
   uv run --locked --with griffe griffe check bitcoin_core_rpc \
       -a v<previous version>
   ```

   It reports breakage only: a public object removed, a parameter that
   changed kind or default, an attribute whose value moved. An addition is
   silent, so the output is short and every line of it wants an entry —
   what the step asks is that nothing it names is missing from RELEASE_NOTES.md.
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

1. Retitle the work-in-progress sections of
   [RELEASE_NOTES.md](./RELEASE_NOTES.md) and [CHANGELOG.md](./CHANGELOG.md) to
   `## v<version>` — the heading must be the version alone, and the section
   must not be empty. `release.yml` checks both before anything is built,
   because a version cannot be unpublished once an index has accepted it.

1. Set the version in `pyproject.toml`, which is the one place it is
   declared, and re-lock so `uv.lock` agrees:

   ```shell
   uv lock
   ```

   **If `main` moves while the gates run, throw the branch away and redo
   these edits on top of it — never rebase it, and never merge `main` into
   it.** CHANGELOG.md and RELEASE_NOTES.md are `merge=union`, so a change that
   opened a `### Repository` group where this release opens its own is
   fused into one section carrying that heading twice, and the union driver
   reports no conflict for a reader to catch:

   ```shell
   git fetch origin
   git reset --hard origin/main       # then retitle, set the version,
                                      # uv lock, and gate again
   ```

   The retitle and the version are three lines; what is expensive to
   reconstruct is the entries, and those are already on `main` in the
   pull requests that landed them. `git diff --cached` at the landing step
   below is the second reading of the same hazard, not a substitute for
   this one: by then the fused headings are what is being committed.

1. Give the release pull request its title and its body, before merging it
   and not after. The title is the version; the body says what the release
   is — what moved, what did not, and which of the two a user would
   notice. A squash leaves one commit whose message is that title, so the
   pull request is where the rest stays, and where a reader arriving from
   that commit lands. A template left unfilled, or a bot's summary of the
   diff, is not a substitute — the summary can stay, but what the diff
   cannot say has to be written, and what a reader should not have to
   discover at the button belongs there too.

   The work-in-progress section of RELEASE_NOTES.md is what that body is written
   from, and the reason it is filled in one landed change at a time rather
   than reconstructed from the diff on release day. Check it against
   `git log v<previous version>..main --oneline` regardless of how current
   it looks, rather than trust that every line landed when it should have.
   Griffe's result and the integration run belong in the body too, each a
   line rather than a screenshot — both are steps nothing else enforces,
   and a pull request that never mentions them reads exactly like one that
   skipped them.

1. Run `uv run pre-commit run --all-files` and `uv run pytest --cov`
   before pressing anything, then verify the
   [read the docs](https://readthedocs.org/projects/bitcoin-core-rpc/builds/)
   build renders. Read the *builds* page and not only the rendered one: a
   site that answers 200 may be serving the last build that succeeded,
   the webhook having quietly refused every delivery since.

1. Merge it, with the button, the way every other pull request here
   lands.

   "Squash and merge" is the only method either the repository setting
   or the ruleset accepts, and auto-merge presses it once the review and
   the checks are in. Branch protection requires an approving review
   and GitHub does not let an author approve their own, which on a
   solo-maintainer repository would stop every merge — the
   `main-self-merge` bypass in `pull_request` mode is what answers that,
   and only that. There is no second landing to choose between: a direct
   push to `main` is refused for everyone.

   `gh pr merge <n> --squash` alone can still refuse this pull request —
   `the base branch policy prohibits the merge` — the way it did on
   btclib-secp256k1's own v0.8.0.4 (btclib-secp256k1#288): a
   solo-maintainer repository never clears `REVIEW_REQUIRED`, so gh's
   client-side mergeable check declines before it asks the server at
   all, and `--auto` only waits longer for the same review that will not
   arrive. `--admin` is the flag that clears it — the pair
   REPOSITORY.md's "Branch protection" describes, `enforce_admins`
   `false` together with holding `admin` — and it is the one to reach
   for first: measured directly on a sibling organization repository
   across four pull requests, each landing from `BLOCKED` and
   `REVIEW_REQUIRED` with a verified signature. Name the release
   commit's title and body explicitly when using it — `gh pr merge <n>
   --squash --admin --subject "<title>" --body-file <path>` — rather
   than leave them to `squash_merge_commit_message`'s repository
   default, `COMMIT_MESSAGES` here: this repository's own release pull
   requests have so far landed as a single commit each (#143, #108), so
   that default and the commit's own message have been the same string,
   but naming them explicitly costs nothing and stops depending on that
   staying true — btclib-secp256k1's release branch is a version bump
   and two retitles, never one commit, and its own RELEASING.md needed
   this the first time a release carried more than a single change.

   `gh api -X PUT repos/{owner}/{repo}/pulls/<n>/merge -f
   merge_method=squash` is the fallback for when `--admin` is
   unavailable, and needs `commit_title` and `commit_message` passed the
   same way for the same reason. It is what landed btclib-secp256k1's
   0.8.0.4 clean — but only because that branch carried a single commit,
   so `COMMIT_MESSAGES`'s concatenation and that commit's own message
   were the same string there too; a multi-commit release branch without
   the two parameters would not be so lucky.

   That the commit is composed by GitHub and signed with its web-flow
   key rather than yours costs nothing. What `main-integrity` requires
   is a signature, not a signer, and it enforces that with no bypass
   actor at all: a verified signature, linear history, no force push and
   no branch deletion, for administrators too.

   ```shell
   gh pr view <pull request number> --json state,mergeCommit \
     --jq '{state, merged_as: .mergeCommit.oid}'
   ```

   `MERGED` is what it reads, its `Closes #N` closes the issue, and
   GitHub deletes the release branch itself.

   Then read `lint` and `test` on the commit `main` ends up at before
   tagging, rather than trust the pull request's own green run:

   ```shell
   gh run list --commit "$(git rev-parse origin/main)"
   ```

   a squash creates a commit that is not the one the pull request tested,
   and the merge fires both workflows again from their own `push`
   trigger — a run of its own, not the `pull_request` run already green a
   moment earlier. That trigger is the whole reason `main` keeps one, and
   the run to read is the `push` run on `main`.

1. Rehearse on TestPyPI (see above) from `main`, if this cycle touched the
   publish path — that section says which changes make it worth the run,
   and asks that a skip be stated in the release pull request rather than
   left to be inferred.

1. Tag the release commit on `main` and push the tag. **Name the
   commit**, and read the tag back before pushing it:

   ```shell
   git tag -s v2026.8.6 -m "release v2026.8.6" <sha of the release commit>
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
   the upload tries. Sibling repository btclib-secp256k1 hit exactly
   this on a real tag rather than a rehearsal: the matrix had already
   built everything and only the token exchange failed, so retagging
   would have rebuilt it for nothing. Fixing the registration and running
   `gh run rerun <run id> --failed` republished from the artifacts
   already there in minutes instead. Retagging is the right answer only
   when the failure happened before those artifacts existed — see "If
   something goes wrong" below.

   A job that sits `queued` with no runner assigned for tens of minutes,
   on an ordinary `ubuntu-latest` label, past the point where the
   environment approval has already gone through, is not this repository's
   problem to fix: the org's GitHub Actions concurrency is shared across
   every `btclib-org` repository, and a burst of CI elsewhere in the
   organization is enough to queue this one behind it. Confirm
   there is nothing to fix rather than assume it — githubstatus.com green,
   no `pending_deployments` left on the run, no concurrency group of this
   repository's own blocking it — then wait; cancelling or re-dispatching
   a job that is merely queued, not failed, risks a second attempt racing
   the first one into `publish-pypi`.

1. Install what was just published, in an environment of its own rather
   than one that may already hold it, and run something with it:

   ```shell
   uv run --isolated --no-project --with bitcoin-core-rpc \
     python -c "import bitcoin_core_rpc; \
       print(bitcoin_core_rpc.DEFAULT_TIMEOUT)"
   ```

   then check the attestations — the JSON API answers `null` for
   `provenance` even where they exist; the
   [simple API](https://pypi.org/simple/bitcoin-core-rpc/) (`Accept:
   application/vnd.pypi.simple.v1+json`) carries the real link, under
   `/integrity/<project>/<version>/<filename>/provenance`, and
   `pypi-attestations verify pypi <file> --repository
   https://github.com/btclib-org/bitcoin-core-rpc` checks the
   signature rather than merely its presence.

1. Read the `published` job of the release run, which needs no dispatch:
   `release.yml` calls that workflow once PyPI has accepted the files, with
   the tag's version, and it waits for the index to serve that version
   before installing anything — so it cannot pass by testing the release
   before this one. It installs from PyPI on every image `os-ubuntu.yml`,
   `os-macos.yml` and `os-windows.yml` run between them, at both ends of
   the supported interpreter range and on the free-threaded build, and
   round-trips a JSON-RPC call against it. From then on it runs weekly on
   its own, and a failure means the outside world moved, not this
   repository — a new
   runner image, an interpreter release, PyPI serving a file that does not
   match its own hash — which is why it is a workflow of its own rather
   than a job of this one.

1. Check the GitHub release the previous step's workflow run created —
   **ask for the release itself, not for the run's conclusion**, a
   skipped job being what a green run looks like from the Actions page:

   ```shell
   gh release view v<version> --json name,assets,author
   ```

   `release not found` is the failure "If something goes wrong" ends with.
   `author` is the cheap second question: `github-actions` is the workflow
   having cut it, any other login a release recreated by hand. Its notes
   are the tag's section of RELEASE_NOTES.md, and the distribution files are
   attached, `<tag>.attestation.jsonl` beside them. A run that logs
   `RELEASE_NOTES.md has no v<version> section` generated the notes from the
   merged pull requests instead — the fallback `version-check` exists to make
   unreachable, not a second way to write release notes — and they are worth
   replacing by hand if it ever fires.

   **No CycloneDX bill of materials is among them, on purpose.** This
   repository declares `dependencies = []` in `pyproject.toml`, and
   `pypi-install.yml` already asserts that against the installed package
   on every run, so a bill of materials would list nothing beyond what
   those already prove empty. A real runtime dependency arriving here is
   the most direct way to change the answer, and that trigger is this
   repository's own. If the generator ever learns
   to describe a component `Requires-Dist` cannot express, the question
   reopens for this repository and its siblings at once, and
   [btclib-org/.github#24](https://github.com/btclib-org/.github/issues/24)
   is the open issue that carries it.

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
   progress" section in RELEASE_NOTES.md and CHANGELOG.md. That shape is
   the one nothing tagged can have, so a checkout of `main` between releases
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

test.yml's `dist` job exports `SOURCE_DATE_EPOCH` from the commit date
and normalizes the sdist, so a rebuild of a released tag is the same
bytes as what was published — that job's own upload is what
`publish-pypi` publishes, unchanged, so "what was published" and "what
that job built" are the same files (issue btclib-org/btclib#1166).
Anyone can check that, and the check is one command short of the
provenance one above: verify the *rebuilt* file rather than a downloaded
one, and it can only pass if the digests agree.

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

Three things bound that guarantee, and each is worth knowing before
reading a mismatch as tampering:

- **the build reads the working directory, not git.** `uv_build` walks
  the tree through the glob patterns of `[tool.uv.build-backend]`, so an
  *untracked* file matching one of them is packed like any other and
  changes the digest. `tests/**` and `docs/**` are the patterns wide
  enough for that to happen by accident, and `source-exclude` beside them
  names what a linter or a type checker is known to leave there — but the
  rule is the directory, not the list. Rebuild in a clean export, which
  is what the checkout above is only if nothing was ever built in it:

  ```shell
  d=$(mktemp -d) && git archive v2026.8.8 | tar -x -C "$d" && cd "$d"
  ```

- **the build backend is bounded, not pinned.** `[build-system] requires`
  asks for `uv_build>=0.12.5,<0.13` and an isolated build takes whatever
  in that range is current, so a rebuild months later runs a backend the
  release never saw. What the ceiling bounds is the *content* of the
  archive; its member metadata is `normalize_sdist.py`'s answer and not
  the backend's, which is the whole reason that script runs over an sdist
  already deterministic without it.
- **the rehearsal is a different version, by construction.** A TestPyPI
  dispatch appends `.dev<run*100+attempt>` to the version, so its files are not
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
  worktree leaves it in every other, and the `git tag -s` that follows
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
  re-run the failed job, or recover by hand from the run's `dist` **and**
  `attestation` artifacts, not `dist` alone — the job downloads both
  before it writes the release, and a release built from `dist` only
  would carry the wheel and the sdist with no signed statement beside
  them, leaving "Verify the provenance of an asset" above nothing to
  `--bundle` against. The by-hand recovery is the same script the
  `skipped` case spells out next; the difference between the two is
  only that `gh run rerun --failed` reaches a job the run marks
  *failed*, so it is worth trying first here and is not an option
  there at all.

- `github-release` shows **`skipped`** rather than failed, though both of
  its needs — `publish-pypi` and `attest` — report `success`. The run's own
  conclusion is `success` and no release exists, which is why the step
  above asks `gh release view` rather than reading the run. What produces
  it is a job the release path does not depend on and cannot see:
  `publish-testpypi` is skipped on a tag, `attest` needs it, and a job
  standing behind a skipped ancestor is skipped in turn unless its own
  condition opts out with `always()` — which `attest` does for itself and
  cannot do on behalf of what needs `attest`. Every job that crosses a
  skip has to say `always()`, so the answer is an explicit `if` on the job
  that shows the symptom, not on the one that caused it. Recovery is by
  hand: `gh run rerun --job` refuses a skipped job outright (`cannot be
  rerun`), unlike a failed one. Re-running the whole workflow is not the
  fix either: `publish-pypi` would attempt the upload a second time, and
  while PyPI would refuse the existing file names rather than accept a
  duplicate, the attempt itself asks for a fresh approval of the `pypi`
  environment and gates the run on nothing this repository controls. Skip
  the workflow entirely and do by hand exactly what the job's own script
  does, from the artifacts already sitting on the run:

  ```shell
  gh run download <run id> -n dist -D dist
  gh run download <run id> -n attestation -D attestation
  shasum -a 256 dist/*                     # compare against PyPI's own
  curl -s https://pypi.org/pypi/bitcoin-core-rpc/<version>/json \
    | python3 -c 'import json,sys; d=json.load(sys.stdin)
  [print(u["filename"], u["digests"]["sha256"]) for u in d["urls"]]'

  git show v<version>:RELEASE_NOTES.md | awk -v tag="v<version>" '
    $0 ~ "^## " tag "( |$)" {found=1; next}
    /^## / && found {exit}
    found {print}
  ' > notes.md
  cp attestation/attestation.jsonl v<version>.attestation.jsonl
  gh release create v<version> dist/* v<version>.attestation.jsonl \
    --title v<version> --notes-file notes.md
  ```

  The digest comparison is not optional: it is what stands in for the
  provenance a second, unwanted publish attempt would otherwise have to
  establish, confirming the files a human is about to attach are the
  exact bytes the token exchange already accepted rather than a fresh
  local build that merely claims to be.
