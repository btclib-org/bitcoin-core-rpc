# Repository configuration

Read this before changing a workflow, a branch rule or a repository
setting; writing code does not need it. `CLAUDE.md` points here rather than
carrying it, so that a session fixing a bug in the client does not hold it
in context.

The branch rules and the repository settings live *outside* the repository,
so this file is the whole of them: nothing here can be recovered by reading
the tree.

## While the repository is private, none of the rules below are in force

Branch protection is a paid feature for a private repository, and
btclib-org is on the free plan. The API says so rather than failing
quietly:

```console
$ gh api -X PUT --input - \
    repos/btclib-org/btclib-bitcoin-core-rpc/branches/master/protection
Upgrade to GitHub Pro or make this repository public to enable this
feature. (HTTP 403)
```

So this section is what the settings become, not what they are: making the
repository public is what enables them, and applying them is a step of
doing that. Everything else here — the merge methods, the token
permissions, the publishing environments — is settable now and set.

## Required checks on master

**Never name matrix contexts in the branch rule.** The rule lives outside
the repository, so a context that stops being produced blocks every merge
with nothing in the tree to explain why. `tests-passed` is an aggregate job
at the end of `test.yml` that `needs` the matrix; a new job in `test.yml`
belongs in that job's `needs`, or it gates nothing.

`master` requires three checks, and only three:

| Check | Produced by |
| --- | --- |
| `tests-passed` | `test.yml`, aggregate over the matrix |
| `Lint and type-check` | `lint.yml`, first job |
| `Build the documentation` | `lint.yml`, second job |

`Build the documentation` is named on its own on purpose: a rule naming
`Lint and type-check` alone would leave a red docs build outside the
required checks entirely. `lint.yml` triggers on `pull_request` with no
branch and no `paths` filter, so both its jobs report on every pull
request, forks included.

Each check is bound to the app that produces it — `checks` with an `app_id`
rather than the bare `contexts` list, 15368 for Actions — so nothing else
can satisfy one.

```shell
gh api repos/btclib-org/btclib-bitcoin-core-rpc/branches/master/protection \
  --jq '.required_status_checks'   # PATCH that sub-endpoint to change
```

**PATCH that sub-endpoint, never PUT the whole protection object**: a
partial PUT drops the reviews, the signatures and the rest. Repeat
`strict: true` in the body, which replaces the object rather than merging
into it.

Neither `mutation.yml`, `links.yml`, `latest.yml` nor `rpc-smoke.yml`
appears in the rule, and none of them must: each is expected to go red for
reasons no pull request introduced, and a red check nobody can act on from
a branch is noise.

## Branch protection, both branches

Both branches are protected, and differently on purpose.

`master`: those three checks with `strict`, one approving review,
`dismiss_stale_reviews`, linear history, no force pushes, no deletions,
`required_conversation_resolution`, and `enforce_admins` *off* — an
administrator can bypass all of it.

`dev`: no force pushes, no deletions, linear history, and nothing else — no
required check, no review, no signature, so a direct push still works,
which is what both bots rely on.

That asymmetry is a choice rather than an oversight. One approving review
cannot be satisfied by the author, GitHub not allowing self-approval, so on
a solo-maintainer branch it is a stop rather than a speed bump.

What `dev` buys is that Dependabot targets it for both ecosystems,
pre-commit.ci autoupdates it, and Dependabot security updates are on, so
bot-authored commits reach `master` through it — and the branch cannot be
rewritten or deleted under them.

Requiring the three checks on `dev` as well is the next step if one is
wanted, and it costs the direct push.

## Token permissions

**The default `GITHUB_TOKEN` is read-only repository-wide**, so a job
needing more must declare it. Only `release.yml`'s `github-release` does
(`contents: write`), plus `id-token: write` on the two publish jobs. The
workflow-level `permissions: contents: read` is belt and braces; keep it,
it is what makes the intent readable in the file.

## Publishing

**Publishing waits for an approval**: the `pypi` and `testpypi`
environments both require a review, and `pypi` is restricted to `v*` tags.
`RELEASING.md` records the reasoning.

## Plan-gated settings

Some settings cannot be enabled and fail silently: secret scanning's
non-provider patterns and validity checks need paid Secret Protection, and
the API answers a PATCH with 200 while leaving them disabled. Do not read
that 200 as success. The `detect-secrets` hook is the compensating control,
and it earns its place here more than in most repositories: the subject of
this project is rpc credentials, so a cookie line and a `Basic` header are
what its tests are full of.
