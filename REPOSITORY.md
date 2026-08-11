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
with nothing in the tree to explain why. `test: every job passed` is an
aggregate job at the end of `test.yml` that `needs` the matrix; a new job in
`test.yml` belongs in that job's `needs`, or it gates nothing. The name
carries the workflow because a context is keyed by name alone: two
workflows with a job named the same thing produce one ambiguous check.

`main` requires these checks and nothing else. The rule is what says so and
this table is a copy of it, in the order the rule holds them so that the two
can be read side by side:

```shell
gh api repos/btclib-org/bitcoin-core-rpc/branches/main/protection \
  --jq '.required_status_checks'   # PATCH that sub-endpoint to change
```

| Check | Produced by |
| --- | --- |
| `Lint and type-check` | `lint.yml`, first job |
| `Build the documentation` | `docs.yml`, its only job |
| `test: every job passed` | `test.yml`, aggregate over the matrix |
| `codeql: every job passed` | `codeql.yml`, aggregate over its matrix |
| `integration: every job passed` | `integration.yml`, over its cells |

The last row is whichever context was added most recently, that endpoint
appending rather than sorting — so the tail of this table moves whenever a
check is renamed, a rename being a drop and an add.

`Build the documentation` is named on its own on purpose: a rule naming
`Lint and type-check` alone would leave a red docs build outside the
required checks entirely. It moved from `lint.yml` to a workflow of its own
without the rule changing, which is worth knowing before renaming anything:
a context is matched by name, not by the workflow that reported it, so
moving a job is free and renaming one is not. `lint.yml` and `docs.yml` both
trigger on `pull_request` with no branch and no `paths` filter, so both
report on every pull request, forks included.

Code scanning comes from `.github/workflows/codeql.yml`, and the repository
setting that would otherwise perform it — code scanning **default setup** —
has to stay off: the two are exclusive, and the collision is at the upload
rather than at the start. An advanced workflow runs to completion while the
setting is configured and its results are refused, so the workflow reports
*failure* rather than nothing:

```text
Code Scanning could not process the submitted SARIF file:
CodeQL analyses from advanced configurations cannot be processed when
the default setup is enabled
```

It is off, and `state` is what says so rather than the absence of a
complaint:

```shell
gh api repos/btclib-org/bitcoin-core-rpc/code-scanning/default-setup \
  --jq .state
```

answers `not-configured`. The `PATCH` that puts it there is the one to
repeat if the setting is ever switched back on:

```shell
gh api -X PATCH -F state=not-configured \
  repos/btclib-org/bitcoin-core-rpc/code-scanning/default-setup
```

`PATCH`, not `PUT`: that endpoint answers a PUT with a bare 404, which
reads as "no such repository" and is not.

Every required check is therefore an Actions check, which is what makes the
`app_id` below one number rather than two: each check is bound to the app
that produces it — `checks` with an `app_id` rather than the bare `contexts`
list, 15368 for Actions — so nothing else can satisfy one.

### Turning default setup off without deadlocking

Default setup produces `CodeQL`, and it is worth knowing which app does:
the Actions jobs it runs report `Analyze (actions)` and `Analyze (python)`,
while the required context comes from the `github-advanced-security` app as
a check named `CodeQL` with conclusion `neutral`, and only on a pull
request's head commit —

```shell
sha=$(gh api repos/btclib-org/bitcoin-core-rpc/pulls/<n> --jq '.head.sha')
gh api "repos/btclib-org/bitcoin-core-rpc/commits/$sha/check-runs" \
  --jq '.check_runs[] | [.name, .app.id, .conclusion] | @tsv'
```

`codeql.yml` produces `codeql: every job passed` instead, from Actions.
Disabling the setting takes the meaning out of the first without taking the
check away — see below — so the rule naming a context whose result is not
yours to produce is the state to avoid: `enforce_admins` is off, so an
administrator can merge past it, but a merge that overrides a check nobody
can produce is not the rule working. The order that never reaches it drops
the old context before the setting, and adds the new one after the merge:

1. patch the rule to drop `CodeQL`, every other context staying;
1. disable default setup with the `PATCH` above;
1. re-run the checks on the pull request carrying `codeql.yml`, whose
   analysis was red for the upload refusal above and now passes;
1. merge it;
1. patch the rule to add `codeql: every job passed`.

Between steps 1 and 5 code scanning gates nothing, which is the cost of the
switch and the reason it is five steps rather than two. Steps 1, 2 and 5 are
`gh api` calls a person makes; the two `PATCH` bodies are the list in full,
that endpoint replacing the object rather than merging into it.

The five have been performed, which is why the table above ends in
`codeql: every job passed` and the setting reads `not-configured`. They are
kept because the setting can be configured again from the repository's code
security settings, and this is the order that takes it off again without
leaving the rule waiting on a check nothing produces.

Two things outlive the switch, and a reader meets both with nothing in the
tree to explain them. GitHub keeps a generated
`dynamic/github-code-scanning/codeql` workflow, still `active` and still
running, which now uploads *code quality* results rather than security ones
— `python.quality.sarif` in its log, where the security analysis produced
`python.sarif` and `actions.sarif`. That is a separate setting, and the
`code-scanning/default-setup` endpoint does not report it:

```shell
gh api repos/btclib-org/bitcoin-core-rpc/actions/workflows \
  --jq '.workflows[] | select(.path | startswith("dynamic/"))
        | {name, path, state}'
```

And the `CodeQL` context did not stop with the setting: it still reports on
a pull request's head commit, now `neutral` with the summary
`1 configuration not found`. Whether a rule naming it would be satisfied by
that has not been tested, and testing it means deadlocking `main` to find
out — which is the argument for the order above, not against it.

**PATCH that sub-endpoint, never PUT the whole protection object**: a
partial PUT drops the signatures and the rest. Repeat `strict: true` in
the body, which replaces the object rather than merging into it.

Renaming a required check is the one change that cannot be made in a pull
request. The rule names a context by the job's display name, so the pull
request that renames the job stops producing the old name and never
produces a check the rule is still waiting for -- and the administrator
bypass that could merge it anyway is the same bypass this file argues
against relying on. The rule moves first, against the branch, and then the
pull request that renames the job reports the name the rule now wants:

```shell
branch=repos/btclib-org/bitcoin-core-rpc/branches/main
gh api -X PATCH "$branch"/protection/required_status_checks --input - <<'JSON'
{"strict": true,
 "checks": [{"context": "Lint and type-check", "app_id": 15368},
            {"context": "Build the documentation", "app_id": 15368},
            {"context": "test: every job passed", "app_id": 15368},
            {"context": "codeql: every job passed", "app_id": 15368},
            {"context": "integration: every job passed", "app_id": 15368}]}
JSON
```

The body arrives on stdin because `-f 'checks[][app_id]=15368'` cannot
work: `-f` sends every value as a string, where the endpoint types
`app_id` as an integer, and what comes back is `422 Invalid request. For
'properties/app_id', "15368" is not a null or integer`. A shell variable
holds the path for the same reason the JSON is not on one line — 80
columns.

Between the two, every open pull request that predates the rename is
blocked until it is rebased, which is the reason to do it with none open
but the one doing the renaming. Moving a job to another workflow needs none
of this: the name is what the rule matches, and `Build the documentation`
kept reporting when it left `lint.yml` for `docs.yml`.

Neither `mutation.yml`, `links.yml`, `latest.yml`, `macos.yml` nor
`published.yml` appears in the rule, and none of them must: each is
expected to go red for reasons no pull request introduced -- an upgrade
upstream, a link on somebody else's website, a runner image -- and a red
check nobody can act on from a branch is noise. `integration.yml` was in that
list until its cost was measured rather than assumed: 90 seconds for six
cells, a live bitcoind of two versions included, which is less than the
matrix it now runs beside. What it answers is the one claim a recording
cannot make, and that belongs in front of a merge.

## Branch protection

`main` is the only branch, and everything reaches it through a pull
request: the checks above with `strict`, one approving review,
`dismiss_stale_reviews`, **required signatures**, linear history, no force
pushes, no deletions, `required_conversation_resolution`, and
`enforce_admins` *off* — an administrator can bypass all of it.

That last one is what carries the review. A review cannot be satisfied by
its author, GitHub not allowing self-approval, so on a solo-maintainer
repository the rule as written stops every pull request the maintainer
opens, and the bypass is what lets one merge at all. The trade is the
review's other half: it is there for a contributor's pull request, where
there *is* somebody else to ask, and for the bots', which nobody
self-approves either.

The required checks are the half that holds regardless, because they are
earned by the tree rather than granted: a bypass is a decision somebody
makes on a pull request in front of them, where a green matrix is not.

Required signatures cost the maintainer nothing for the same reason
nothing here pushes to `main` directly: the only thing writing to it is a
merge GitHub performs itself, and GitHub signs those with its web-flow
key.

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
| Code scanning default setup (CodeQL) | not configured |

Code scanning itself is enabled, and the row above says the opposite of
that: what performs it is `codeql.yml`, and configuring the setting would
not stop that workflow running — it would refuse the results at the upload.
"Required checks on main" above has the switch and the `gh api` that reads
the setting back.

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
