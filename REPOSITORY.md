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

## Required checks on master

**Never name matrix contexts in the branch rule.** The rule lives outside
the repository, so a context that stops being produced blocks every merge
with nothing in the tree to explain why. `tests-passed` is an aggregate job
at the end of `test.yml` that `needs` the matrix; a new job in `test.yml`
belongs in that job's `needs`, or it gates nothing.

`master` requires four checks, and only four:

| Check | Produced by |
| --- | --- |
| `tests-passed` | `test.yml`, aggregate over the matrix |
| `Lint and type-check` | `lint.yml`, first job |
| `CodeQL` | code scanning default setup |
| `Build the documentation` | `lint.yml`, second job |

`Build the documentation` is named on its own on purpose: a rule naming
`Lint and type-check` alone would leave a red docs build outside the
required checks entirely. `lint.yml` triggers on `pull_request` with no
branch and no `paths` filter, so both its jobs report on every pull
request, forks included.

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
gh api repos/btclib-org/bitcoin-core-rpc/branches/master/protection \
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

`master`: those four checks with `strict`, one approving review,
`dismiss_stale_reviews`, **required signatures**, linear history, no force
pushes, no deletions, `required_conversation_resolution`, and
`enforce_admins` *off* — an administrator can bypass all of it.

`dev`: no force pushes, no deletions, linear history and
`required_conversation_resolution`, and nothing else — no required check,
no review, no signature, so a direct push still works, which is what both
bots rely on.

That asymmetry is a choice rather than an oversight, and each half of it
has its own reason. Commits reaching `dev` are unsigned — the bots' are,
and so is a maintainer's without a signing key configured — so
`required_signatures` there would reject every push; on `master` it holds
because the only thing that writes there is a merge GitHub performs
itself, and GitHub signs those with its web-flow key. And one approving
review cannot be satisfied by the author, GitHub not allowing
self-approval, so on a solo-maintainer branch it is a stop rather than a
speed bump — which is why `enforce_admins` is off.

What `dev` buys is that Dependabot targets it for both ecosystems,
pre-commit.ci autoupdates it, and Dependabot security updates are on, so
bot-authored commits reach `master` through it — and the branch cannot be
rewritten or deleted under them.

Requiring the four checks on `dev` as well is the next step if one is
wanted, and it costs the direct push.

## Head branches after a merge

`delete_branch_on_merge` is on, since 7 August 2026:

```shell
gh api repos/btclib-org/bitcoin-core-rpc --jq '.delete_branch_on_merge'
```

GitHub deletes the head branch of a pull request when it is merged, which
is what keeps the branch list a list of live work rather than a history of
every change ever made. It was turned on after a sweep that removed three
merged head branches from here, none of which anybody could tell from live
work without comparing each against `dev` commit by commit.

Two cases it does not cover, both deliberate. A protected branch is never
deleted, protection winning over this setting, so the release pull request
that merges `dev` into `master` leaves `dev` where it is. And a pull
request **closed without merging** keeps its head branch: GitHub cannot
know whether that work was abandoned or is waiting, so those are the ones
still worth looking at now and then.

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
