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

## Which version string is which

Five strings here look like versions, and two of them are written by
hand. Telling them apart is most of what can go wrong:

- **`2026.8.6`**, in `pyproject.toml`, is *the* version. It is what gets
  published, on either index, and the only one typed in by number
- **`2026.8.6.1`**, a fourth number on an already-final version, plays
  two roles: right after `2026.8.6` ships, the last step of a release
  opens `dev` on it as a placeholder, nothing having moved since to
  warrant a real bump; and if `2026.8.6` itself shipped broken, "If
  something goes wrong" ships the very same string as the fix, tagged.
  Both are typed by hand, and both read the same way — "the same
  release, one change since" — whichever of the two prompted it. The
  placeholder is shaped exactly like a release on purpose: what keeps it
  from being tagged as one is `version-check`'s heading check against
  HISTORY.md's and CHANGELOG.md's section for it, not the shape of the
  number, which no longer tells the two apart
- **`v2026.8.6`**, the tag, carries no version of its own: it picks the
  index, PyPI rather than TestPyPI, and `version-check` exists to
  confirm it says what `pyproject.toml` says
- **`.dev<run number>`** is not a version but the template in
  `release.yml`, appended to what `pyproject.toml` declares by a
  `workflow_dispatch` run alone. Nothing writes it down, and no commit
  ever carries it
- **`2026.8.6rc1`**, and a `v2026.8.6rc1` tag, have no place in this
  scheme: there are no release candidates here, only a version not yet
  tagged. `version-check` refuses anything that is not digits and dots,
  which is what stops `2026.8.6rc1` before a tag is even pushed — and
  what a `v2026.8.6rc1` tag would otherwise pass, burning a pre-release
  on PyPI itself, where `--pre` installs would find it from then on

PEP 440 sorts a `.dev<run number>` rehearsal before the release it
rehearses, so a rehearsal never shadows it.

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

1. Give the pull request that merges `dev` into `master` its title and its
   body, before merging it and not after. The title is the version; the
   body says what the release is — what moved, what did not, and which of
   the two a user would notice. A rebase leaves no merge commit, so none
   of that reaches `master`'s history: the pull request is where it stays,
   and where a reader of any commit in it arrives. A template left
   unfilled, or a bot's summary of the diff, is not a substitute — the
   summary can stay, but what the diff cannot say has to be written.

1. Merge `dev` into `master` with **"Rebase and merge"**, never *"Squash
   and merge"* — read the button, GitHub offers whichever method was used
   last, and a squash there would fold every landed change into one
   commit, leaving `master` with one line where `dev` carried the
   reasoning one decision at a time. That cannot be undone afterwards: a
   tag on the squashed commit, and the attestations bound to it, outlive
   any attempt to rewrite the history back.

1. Tag `master` and push the tag:

   ```shell
   git tag v<version>
   git push origin v<version>
   ```

1. Approve the `pypi` environment when the workflow asks. Up to here
   nothing is public and the tag can still be deleted; the upload that
   follows is the point of no return — the upload, and not the approval,
   the token exchange happening after it. A registration that does not
   match the claims fails there having uploaded nothing, and a version
   survives a failed exchange: delete the tag, fix the registration, tag
   again.

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
   https://github.com/btclib-org/btclib-bitcoin-core-rpc` checks the
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
   are attached. A run that logs `HISTORY.md has no v<version> section`
   generated the notes from the merged pull requests instead — the
   fallback `version-check` exists to make unreachable, not a second way
   to write release notes — and they are worth replacing by hand if it
   ever fires.

1. Realign `dev` onto `master`. "Rebase and merge" replayed `dev`'s
   commits onto `master` with new SHAs, so `dev`'s old ones and
   `master`'s are equal in content and unequal in identity — the two
   branches hold the same tree through different histories, and their
   merge base stops advancing right here. Left alone this is not the
   cosmetic issue it looks like: a two-commit `dev`/`master` set up
   exactly this way, tested by hand, made GitHub itself report the
   *next* dev-to-master pull request as `CONFLICTING`, and
   `gh pr merge --rebase` on it as `the merge commit cannot be cleanly
   created`. GitHub's rebase-merge does not drop a commit whose patch is
   already upstream the way a local `git rebase` does — it tries to
   reapply it, and reapplying "add this file" or "add this line" where
   it already exists is a conflict, not a no-op. Archive what is about
   to become unreachable, then move the branch:

   ```shell
   git fetch origin
   git tag -a history/dev-<version> dev -m "dev's own commits for <version>"
   git push origin history/dev-<version>
   git switch dev && git reset --hard origin/master
   git push --force-with-lease origin dev
   ```

   the tag must not start with `v`, `release.yml` triggering on
   `tags: ["v*"]`. Nothing in the working tree changes, the two trees
   already being identical, and `git diff origin/master origin/dev` is
   how to say so rather than assume it.

   That last push can fail on its own: `dev`'s branch protection blocking
   force pushes is not one of the rules "Include administrators" being
   off exempts an administrator from — that toggle covers required
   reviews, required status checks, required signatures and required
   linear history, and blocking force pushes is a rule of its own that
   GitHub applies to every push over the git protocol regardless of who
   is pushing. This repository's own v2026.8.6 is where it was learned:
   the maintainer's own push, run by hand as an administrator, came back
   `remote: - Cannot force-push to this branch`. What worked was flipping
   the setting itself, immediately before the push and immediately
   after, reading its other fields back first so the PUT does not
   silently drop them:

   ```shell
   branch=repos/btclib-org/btclib-bitcoin-core-rpc/branches/dev/protection
   gh api "$branch" --jq \
     '{required_status_checks, enforce_admins: .enforce_admins.enabled,
       required_pull_request_reviews, restrictions,
       required_linear_history: .required_linear_history.enabled,
       allow_force_pushes: true, allow_deletions: .allow_deletions.enabled,
       block_creations: .block_creations.enabled,
       required_conversation_resolution:
         .required_conversation_resolution.enabled,
       lock_branch: .lock_branch.enabled,
       allow_fork_syncing: .allow_fork_syncing.enabled}' \
     | gh api -X PUT "$branch" --input -
   ```

   push, then set `allow_force_pushes` back to `false` through the same
   PUT at once — the setting, not only this one push, is what stands open
   in between.

   Every branch still open against `dev` has had its base moved out from
   under it, and reports the whole release as its own diff until it is
   rebased:

   ```shell
   git rebase --onto origin/master <the old dev tip> <branch>
   ```

   this comes before the next step rather than after it: that step's
   change is on `dev`, and the force update above would discard it.

1. Add the new work-in-progress headings back to HISTORY.md and
   CHANGELOG.md on `dev`.

1. Set `pyproject.toml`'s version to the next cycle's placeholder: the
   version just released, with its trailing component bumped by one, or
   `.1` appended if it had none. It is shaped exactly like a release, on
   purpose — nothing here has to tell the two apart by shape, that being
   what the heading just added above is for. Re-lock so `uv.lock` agrees:

   ```shell
   uv lock
   ```

1. Open a draft pull request from `dev` to `master` for the cycle just
   opened, title included, and leave its body for what the merge step
   above already asks for: written before the release is cut, not
   reconstructed from the diff at the last minute. A draft one is what
   that step could not be until now — everything that lands on `dev`
   between one release and the next has a place to be described as it
   lands, rather than a promise kept only if someone remembers to keep
   it. Marking it ready and pressing **Rebase and merge** is what that
   step still is; this one is what makes reaching it with a body already
   written the ordinary case rather than the exception.

## If something goes wrong

- The workflow failed before the `publish-pypi` job: nothing was
  uploaded. Delete the tag, fix, and tag again:

  ```shell
  git tag -d v<version>
  git push origin :refs/tags/v<version>
  ```

- The upload succeeded but the release is broken: PyPI never accepts a
  file name twice, even after deletion. Yank the bad release on PyPI and
  publish a new patch version, the fourth number bumped again
  (`2026.8.6.1` → `2026.8.6.2`).

- Only the `github-release` job failed: the PyPI upload is already done;
  re-run the failed job, or create the release by hand from the `dist`
  artifact of the run.
