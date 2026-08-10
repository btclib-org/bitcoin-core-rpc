# Repository configuration

Read this before changing a workflow, a branch rule or a repository
setting; writing code does not need it. `CLAUDE.md` points here rather than
carrying it, so that a session fixing a bug in the client does not hold it
in context.

The branch rules and the repository settings live *outside* the repository,
so this file is the whole of them: nothing here can be recovered by reading
the tree.

**The repository is public, and that is a prerequisite rather than a
preference.** Branch protection is a paid feature for a private repository
on the free plan, and the API says so rather than failing quietly —
`Upgrade to GitHub Pro or make this repository public to enable this
feature (HTTP 403)`. Everything below depends on it, and so does Actions
being unmetered.

## Required checks on main

**Never name matrix contexts in the branch rule.** The rule lives outside
the repository, so a context that stops being produced blocks every merge
with nothing in the tree to explain why. `tests-passed` is an aggregate job
at the end of `test.yml` that `needs` the matrix; a new job in `test.yml`
belongs in that job's `needs`, or it gates nothing.

`main` requires four checks, and only four:

| Check | Produced by |
| --- | --- |
| `tests-passed` | `test.yml`, aggregate over the matrix |
| `Lint and type-check` | `lint.yml`, first job |
| `CodeQL` | code scanning default setup |
| `Build the documentation` | `docs.yml`, its only job |

`Build the documentation` is named on its own on purpose: a rule naming
`Lint and type-check` alone would leave a red docs build outside the
required checks entirely. It moved from `lint.yml` to a workflow of its own
without the rule changing, which is worth knowing before renaming anything:
a context is matched by name, not by the workflow that reported it, so
moving a job is free and renaming one is not. `lint.yml` and `docs.yml` both
trigger on `pull_request` with no branch and no `paths` filter, so both
report on every pull request, forks included.

`CodeQL` comes from the default setup rather than from a workflow in this
tree, which is why no `codeql.yml` is here to find: it is a repository
setting, `actions` and `python` at the default query suite, and the
`PATCH` below is what turns it on.

```shell
setup='{"state":"configured","query_suite":"default",'
setup="${setup}"'"languages":["actions","python"]}'
gh api -X PATCH --input - \
  repos/btclib-org/bitcoin-core-rpc/code-scanning/default-setup \
  <<<"${setup}"
```

`PATCH`, not `PUT`: that endpoint answers a PUT with a bare 404, which
reads as "no such repository" and is not.

Each check is bound to the app that produces it — `checks` with an
`app_id` rather than the bare `contexts` list, 15368 for Actions and 57789
for CodeQL — so nothing else can satisfy one.

```shell
gh api repos/btclib-org/bitcoin-core-rpc/branches/main/protection \
  --jq '.required_status_checks'   # PATCH that sub-endpoint to change
```

**PATCH that sub-endpoint, never PUT the whole protection object**: a
partial PUT drops the signatures and the rest. Repeat `strict: true` in
the body, which replaces the object rather than merging into it.

Neither `mutation.yml`, `links.yml`, `latest.yml` nor `rpc-smoke.yml`
appears in the rule, and none of them must: each is expected to go red for
reasons no pull request introduced, and a red check nobody can act on from
a branch is noise.

## Branch protection

`main` is the only branch, and everything reaches it through a pull
request: those four checks with `strict`, **required signatures**, linear
history, no force pushes, no deletions,
`required_conversation_resolution`, and `enforce_admins` *on* — the rule
holds for an administrator too, which is what makes it a rule.

**No approving review is required**, and that omission is the deliberate
half of the setup. A review cannot be satisfied by the author, GitHub not
allowing self-approval, so on a solo-maintainer repository it is a stop
rather than a speed bump: either nothing merges, or an administrator waves
it through on every pull request and the rule teaches its own bypass. The
four checks gate instead, and they cannot be self-approved either — they
are earned by the tree.

Required signatures cost nothing because the only thing writing to `main`
is a merge GitHub performs itself, and GitHub signs those with its
web-flow key. Said from the other side: a maintainer with no signing key
configured cannot push straight to `main`, which is the rule working
rather than the rule in the way.

`strict` means a pull request merges only from a head up to date with
`main`, so landing one asks the next to update and re-run. That is a queue
rather than a cost at this traffic, and it is one `PATCH` away if it stops
being.

Dependabot, its security updates and pre-commit.ci all open pull requests
here, none of them naming a target branch: what they get is the default
branch, and it is the only branch there is.

## Head branches after a merge

`delete_branch_on_merge` is on, since 7 August 2026:

```shell
gh api repos/btclib-org/bitcoin-core-rpc --jq '.delete_branch_on_merge'
```

GitHub deletes the head branch of a pull request when it is merged, which
is what keeps the branch list a list of live work rather than a history of
every change ever made: a merged head branch is indistinguishable from
live work without comparing it against `main` commit by commit.

The case it does not cover is deliberate. A pull request **closed without
merging** keeps its head branch, GitHub not being able to know whether
that work was abandoned or is waiting, so those are the ones worth looking
at now and then.

## Token permissions

**The default `GITHUB_TOKEN` is read-only repository-wide**, so a job
needing more must declare it. Only `release.yml`'s `github-release` does
(`contents: write`), plus `id-token: write` on the two publish jobs and
`id-token: write` with `attestations: write` on `attest`. The
workflow-level `permissions: contents: read` is belt and braces; keep it,
it is what makes the intent readable in the file.

One elevation per job, and none of them holding another's: the job that
signs the distribution files writes no release, the job that writes the
release holds no OIDC token, and neither builds anything. `attest` is
where that costs a job rather than two lines, and it is the shape to
keep.

Artifact attestations are free on public repositories on every current
plan, and unavailable on a private one outside Enterprise Cloud — so
making this repository private would break `attest` and nothing else.

## Publishing

**Publishing waits for an approval**: the `pypi` and `testpypi`
environments both require a review, and `pypi` is restricted to `v*` tags.
`RELEASING.md` records the reasoning.

## Security settings

All of these are repository settings and none of them is in the tree, so
this list is the whole of them:

| Setting | State |
| --- | --- |
| Dependabot alerts | enabled |
| Dependabot security updates | enabled |
| Private vulnerability reporting | enabled |
| Secret scanning | enabled |
| Secret scanning push protection | enabled |
| Code scanning default setup (CodeQL) | configured |

Private vulnerability reporting is what `SECURITY.md` sends a reporter to,
and the link in `.github/ISSUE_TEMPLATE/config.yml` is the same door: with
it disabled that link is a 404, so the setting and the two files go
together.

## Plan-gated settings

Some settings cannot be enabled and fail silently: secret scanning's
non-provider patterns and validity checks need paid Secret Protection, and
the API answers a PATCH with 200 while leaving them disabled. Do not read
that 200 as success. The `detect-secrets` hook is the compensating control,
and it earns its place here more than in most repositories: the subject of
this project is rpc credentials, so a cookie line and a `Basic` header are
what its tests are full of.
