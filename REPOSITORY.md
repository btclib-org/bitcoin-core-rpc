# Repository configuration

Read this before changing a workflow, a branch rule or a repository
setting; writing code does not need it. `CLAUDE.md` points here rather than
carrying it, so that a session fixing a bug in the client does not hold it
in context.

The branch rules and the repository settings live *outside* the
repository. What is recorded is the settings the organization standard
asks about — the ones section 16's checklist sets on a new repository,
the ones a section of the standard states a rule for, and the ones a
behaviour it describes rests on — together with whatever a call quoted
for one of those answers alongside it. That is this file's scope, and
*What this file passes over* at the foot says what falls outside it.

The topics and `.homepage` have a second form in the tree —
`pyproject.toml`'s `keywords` and its `[project.urls]` field of that
name — so each is read back here for comparison rather than as the only
place the answer lives, which is what *Topics* and *Publishing* say of
them. Nothing else here is recoverable by reading the tree.

**The repository is public, and that is a prerequisite rather than a
preference.** Branch protection is a paid feature for a private repository
on the free plan, and the API says so rather than failing quietly —
`Upgrade to GitHub Pro or make this repository public to enable this
feature (HTTP 403)`. Everything below depends on it, and so does Actions
being unmetered.

```shell
gh api repos/btclib-org/bitcoin-core-rpc --jq '{visibility, has_issues}'
# {"has_issues":true,"visibility":"public"}
```

Section 10's `scorecard` sentinel is the other thing resting on the
first answer: public is what it reads at all, so a flip to private
leaves `scorecard.yml`'s row and `README.md`'s badge standing while the
run stops producing a score, and `.visibility` above is what puts that
flip one command from being seen.

`has_issues` is what `CONTRIBUTING.md`'s *The issue tracker* rests on —
an issue about this tree alone stays here — and so does the
`.github/ISSUE_TEMPLATE/` section 16's checklist gives every repository.

## Required checks on main

**Never name matrix contexts in the branch rule.** The rule lives outside
the repository, so a context that stops being produced blocks every merge
with nothing in the tree to explain why. `test: every job passed` is an
aggregate job at the end of `test.yml` that `needs` every other job there;
a new job in `test.yml` belongs in that job's `needs`, or it gates
nothing. The name
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
| `test: every job passed` | `test.yml`, aggregate over its jobs |
| `integration: every job passed` | `integration-bitcoind.yml`, over its cells |

The last row is whichever context was added most recently, that endpoint
appending rather than sorting — so the tail of this table moves whenever a
check is renamed, a rename being a drop and an add.

**Each row above is a job name or an aggregate**, and that is a
rule rather than an inconsistency: a workflow with one job needs no
aggregate, the job *being* the context. It is also the answer to why a
sibling repository's own live-node check can be a bare job name,
`Regtest against Bitcoin Core`, where this one is
`integration: every job passed`. The two workflows ask the same
question of a real node and are governed by the same rule; there it is one
job and here it is a matrix whose cells the trigger decides, so there the
job name is the context and here an aggregate has to be. Making the two
strings match would mean
inventing a job whose only purpose is to be named, or naming a matrix cell
in the rule — which is the first thing this section forbids.

`codeql: every job passed` is not among them, and it is a name this rule
could take: `codeql.yml` runs on a pull request, so the aggregate reports
on the run a pull request has, which is what a required status check needs
and what an aggregate exists to give one. Adding it is a patch to the rule
and nothing in the tree. What holds it back is the ceiling on concurrent
jobs *Plan-gated settings* below measures — the analysis is two more cells
a merge would wait for — against a workflow whose findings `lint.yml`
already covers in part on every branch.

The workflow half of the same question is required, and separately:
`zizmor` is a pre-commit hook, so `lint.yml` audits these very files for
an injected expression on every pull request. What an unrequired CodeQL
run defers is not the analysis but the blocking — the alerts are raised
against the branch either way, and a merge is what stops waiting on them.

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
`app_id` below the same value for every entry: each check is bound to the
app that produces it — `checks` with an `app_id` rather than the bare
`contexts` list, 15368 for Actions — so nothing else can satisfy one.

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
1. merge it.

There is no further step adding `codeql: every job passed` to the rule: the
section above is why that context is not required, so what the rule holds
is what step 1 leaves it with. Between step 1 and the merge code scanning
gates nothing, which was the cost of the switch; it gates nothing now
either, which was the trade made afterwards and deliberately.

Steps 1 and 2 are `gh api` calls a person makes; the `PATCH` body is the
list in full, that endpoint replacing the object rather than merging into
it.

The steps above have been performed, and the setting reads `not-configured`.
They are kept because the setting can be configured again from the repository's
code security settings, and this is the order that takes it off again without
leaving the rule waiting on a check nothing produces.

Things outlive the switch, and a reader meets them with nothing in the
tree to explain them. GitHub keeps a generated
`dynamic/github-code-scanning/codeql` workflow, still `active` and still
running, which now uploads *code quality* results rather than security ones
— `python.quality.sarif` in its log, where the security analysis produced
`python.sarif` and `actions.sarif`. That is a separate setting with an
endpoint of its own, the "Code quality" section below, and the
`code-scanning/default-setup` endpoint reports nothing about it:

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

No sentinel appears in the rule, and none of them may: `mutation.yml`,
`links.yml`, `deps-latest.yml`, `os-ubuntu.yml`, `os-macos.yml`,
`os-windows.yml` and `pypi-install.yml` are each expected to go red for
reasons no pull request introduced -- an upgrade upstream, a link on
somebody else's website, a runner image -- and a red check nobody can act
on from a branch is noise.
`integration-bitcoind.yml` is in the rule rather than in that list, its cost
having been measured rather than assumed: 12 to 24 seconds a cell, the download
of a live bitcoind included, and the cells run concurrently. What it
answers is the one claim a recording cannot make, and that belongs in
front of a merge.

## Code quality

The analysis the generated workflow above was left running, and it is off.
Its setting is not `code-scanning/default-setup`, and the Actions API is
not the way in either: a generated workflow is not one this repository
owns, and `actions/workflows/<id>/disable` answers 422. The endpoint that
reports the setting is the one that sets it:

```shell
gh api repos/btclib-org/bitcoin-core-rpc/code-quality/setup
# {"state":"not-configured","languages":["python"], ...}

gh api -X PATCH repos/btclib-org/bitcoin-core-rpc/code-quality/setup \
  -F state=not-configured
```

What decided it is the ceiling the section above already trades against,
not the queries. `Analyze (python)` ran on every pull request and every
push to `main`, and what it cost is still readable from the check runs of
a commit of that era rather than from the run list, which no longer names
it:

```shell
gh api \
  "repos/btclib-org/bitcoin-core-rpc/commits/dbd3263/check-runs?per_page=100" \
  --jq '.check_runs[] | select(.name == "Analyze (python)")
        | (.completed_at | fromdate) - (.started_at | fromdate)'
# 44
```

`per_page` is load-bearing: that commit carries more check runs than a
default page holds, and this one is not on the first page. A slot held for
that long on every commit is a slot shared with every other repository in
the organization, where the same setting was on -- *Plan-gated settings*
below is where the ceiling's own figure lives.

What it produced in exchange cannot be read from outside a browser. There
is no `code-quality/alerts` and no `code-quality/analyses`, both 404, and
a quality upload appears in neither endpoint that does answer: the alert
list is empty, and every analysis carries `codeql.yml`'s own category.

```shell
gh api "repos/btclib-org/bitcoin-core-rpc/code-scanning/alerts?per_page=100" \
  --jq length
gh api "repos/btclib-org/bitcoin-core-rpc/code-scanning/analyses?per_page=100" \
  --jq '[.[] | .category] | unique'
```

`state=configured` is the way back, and the argument for it is that these
queries are a class of finding nothing else here makes: ruff, mypy and the
spell checkers are the cover, and they are not the same questions. What
refuses them is the ceiling, so a fleet not waiting for slots is what
would change the answer.

## Branch protection

`main` is the repository's default branch and its only one:

```shell
gh api repos/btclib-org/bitcoin-core-rpc --jq '.default_branch'
# main
```

Everything reaches it through a pull request: the checks above with
`strict`, an approving review,
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
makes on a pull request in front of them, where a green gate is not.

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

## Tag protection

`tag-integrity`, `target: tag`, `refs/tags/v*`: required signatures, and
nothing else. No bypass actor, for anyone, ever. `GET /rulesets` answers a
summary per ruleset, with neither `rules` nor `bypass_actors` among its
keys, so those two come from the single-ruleset endpoint, keyed by the id
the list step above it derives:

```shell
id=$(gh api repos/btclib-org/bitcoin-core-rpc/rulesets \
  --jq '.[] | select(.name=="tag-integrity") | .id')
gh api repos/btclib-org/bitcoin-core-rpc/rulesets/"$id" \
  --jq '{rules: [.rules[].type], bypass: [.bypass_actors[].bypass_mode]}'
```

`release.yml` triggers on `push: tags: ["v*"]`, and the `pypi` environment
is restricted to that pattern, so the tag was the one unattested link in
an otherwise fully-attested chain — the commit it points at signed,
`main-integrity` requiring that with no bypass actor, the workflow pinned,
the upload Trusted Publishing with no long-lived token. RELEASING.md's
tagging step already produces a signed tag by default (`git tag -s`), so
the ruleset enforces what the procedure already does rather than changing
it; what it adds is that an unsigned `v*` tag is refused outright rather
than merely undocumented (issue #139).

It carries no `deletion` or `non_fast_forward` rule on purpose:
RELEASING.md's own recovery path deletes and re-tags a release that
failed before `publish-pypi`, and either rule would block exactly that.
Existing tags are unaffected — the ruleset applies to pushes going
forward, not retroactively; a tag cannot be signed after the fact without
moving it, and moving a released tag is worse than leaving it unsigned.

This is a live repository-settings change, created directly rather than
through a pull request — the same reasoning `main-integrity` and
`main-self-merge` are, and why RELEASING.md's `-s` half of issue #139
went through review while this half did not.

## Merge methods

**Squash is the only method GitHub can be asked for**, so it is a setting
and not only the convention CONTRIBUTING.md states:

```shell
gh api repos/btclib-org/bitcoin-core-rpc \
  --jq '{allow_squash_merge, allow_merge_commit, allow_rebase_merge,
         allow_auto_merge}'
# {"allow_auto_merge":true,"allow_merge_commit":false,
#  "allow_rebase_merge":false,"allow_squash_merge":true}
```

`allow_auto_merge` is in that object because the landing described
below rests on it rather than being a convenience beside it: off,
auto-merge is not offered, every landing waits on somebody pressing
*Squash and merge* at the moment the last check goes green, and nothing
turns red.

The merge commit was refused by the required linear history above already,
so turning it off takes away a button that could not have worked. The
rebase merge could have, and that is the one this removes: it replays a
branch's commits onto `main`, where the rule is one commit per landed
change and the steps of a review belong to the pull request that carries
them.

What a single method buys is not the button on a pull request somebody is
looking at. GitHub preselects whichever method was used last, and the
dialog that switches auto-merge on carries the same dropdown — so the
answer can be given hours before anything merges, by whoever switched it
on, with nothing asking again. One method is one entry: there is no wrong
one to preselect, and nothing to read before pressing.

Two fields shape the commit it writes, and both are GitHub's defaults:

```shell
gh api repos/btclib-org/bitcoin-core-rpc \
  --jq '{squash_merge_commit_title, squash_merge_commit_message}'
```

`COMMIT_OR_PR_TITLE` is the subject: the pull request title with its
number, or the subject of the single commit where a branch has one, which
the convention of writing the two alike keeps the same text.
`COMMIT_MESSAGES` is the body, and `BLANK` is what would cost something —
a `Co-Authored-By` trailer is written in the commits of the branch, and
the squash body is the only place it survives one commit standing for all
of them.

That setting is what the button writes, and the button is what lands
every pull request here: auto-merge presses it once the review and the
checks are in. There is no second landing. The `main-self-merge` bypass
is in `pull_request` mode, so it excuses the approving review a
solo-maintainer repository cannot produce and excuses nothing else — a
direct push to `main` is refused for everyone, the holder included — and
the ruleset names `squash` as the only merge method it will accept,
stating the constraint where the rule is rather than only in the setting
above. *Tag protection* above already gives the reason the id has to be
read off the list rather than named directly:

```shell
id=$(gh api repos/btclib-org/bitcoin-core-rpc/rulesets \
  --jq '.[] | select(.name=="main-self-merge") | .id')
gh api repos/btclib-org/bitcoin-core-rpc/rulesets/"$id" \
  --jq '{bypass: [.bypass_actors[].bypass_mode],
         methods: [.rules[] | select(.type=="pull_request")
                            | .parameters.allowed_merge_methods]}'
```

The other mode, `always`, permits a direct push as well, and it is not
used here. What it would buy is a landing that keeps the maintainer's
own signature on the commit; what it costs is a `main` any local mistake
can reach. The first half is worth nothing once the branch rule is read
as asking for a valid signature rather than for a particular signer,
which makes GitHub's web-flow key as good as the maintainer's.

`main-integrity` is what the commit answers to either way, and the
squash GitHub composes answers all four of its rules: it is signed, the
history stays linear, nothing is rewritten and nothing is deleted.

Because every landing is one GitHub performs, it reconciles every one of
them: the pull request reads `MERGED`, its `Closes #N` closes the issue,
and the head branch is deleted as `delete_branch_on_merge` below has it,
with nothing left to do by hand.

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
(`contents: write`), plus `id-token: write` on `publish-pypi` and
`publish-testpypi`, and `id-token: write` with `attestations: write`
on `attest`. The
workflow-level `permissions: contents: read` is belt and braces; keep it,
it is what makes the intent readable in the file.

`release.yml`'s `test` job declares a `permissions:` block too, and for a
different reason: not because it needs more itself, but because
`uses: ./.github/workflows/test.yml` caps every job of the called
workflow at what the caller grants here rather than at what `test.yml`'s
own top-level declaration gives them — a caller's grant *replaces* the
callee's default outright, for every job over there and not only for the
one that needed more. `test.yml`'s `changes` job needs
`pull-requests: read` for the file list of a pull request, which
`contents: read` does not carry; naming only that would leave every
other job in `test.yml` without even `contents: read`, refusing their
checkout steps. Both are named here for that reason (issue #145,
mirroring btclib-secp256k1#281's fix for the same mechanism).

One elevation per job, and none of them holding another's: the job that
signs the distribution files writes no release, the job that writes the
release holds no OIDC token, and neither builds anything. `attest` is
where that costs a job rather than two lines, and it is the shape to
keep.

Artifact attestations are free on public repositories on every current
plan, and unavailable on a private one outside Enterprise Cloud — so
making this repository private would break `attest` and nothing else.

### The value above is pinned here, not inherited

`default_workflow_permissions` is a repository setting that falls back
to an organization default until a repository sets its own; once set,
the repository stops following that default, and there is no
documented way back to inheriting it. **This repository pins its own**
rather than inheriting the organization's, set by hand on 21 August
2026:

```shell
gh api -X PUT repos/btclib-org/bitcoin-core-rpc/actions/permissions/workflow \
  -f default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=false
```

Read back:

```shell
gh api repos/btclib-org/bitcoin-core-rpc/actions/permissions/workflow \
  --jq '{default_workflow_permissions, can_approve_pull_request_reviews}'
# {"default_workflow_permissions":"read",
#  "can_approve_pull_request_reviews":false}
```

It had to be set by hand because it had already drifted from the
organization default: other repositories in the organization followed
the same default's move to `read`, and this one stayed `write` until
the command above — which is how the override was found, there being
no endpoint that reports which repositories carry one.
Nothing is wrong today: the value read back is `read`,
`can_approve_pull_request_reviews` is `false`, and every workflow here
declares `permissions: contents: read` besides.

What is left is that the *next* move of the organization default will not reach
this repository, and nothing says so. Neither this endpoint nor
`/actions/permissions` beside it (`enabled`, `allowed_actions`,
`sha_pinning_required`) carries a field distinguishing an override from an
inheritance, and `PUT` accepts `read` or `write` and neither `null` nor
`inherit` — checked against [the REST
documentation](https://docs.github.com/en/rest/actions/permissions?apiVersion=2022-11-28)
rather than assumed. The repository's Settings → Actions → General page is the
only other candidate for a control that clears the override; it was not checked
— no interactive session against it was available when this section was written,
so its absence here is a gap in what was checked, not a finding that no such
control exists.

**Whoever moves the organization default must move this repository
with it**, by hand, with the command above, or it is left behind again.

No sibling repository is known good either, and none is named here: each
records its own status in its own `REPOSITORY.md`, a roster in this file
being one more thing to keep true about repositories this one cannot
read. What they have in common is the reason — each already held `read`
when the organization default moved on 21 August 2026, so none could
have been observed following it, and any of them may carry the same kind
of override this repository did. Establishing which would mean moving
the organization default to `write` and back, which is not worth doing
for the answer.

## Publishing

**Publishing waits for an approval**: the `pypi` and `testpypi`
environments both require a review, and `pypi` is restricted to `v*` tags.
`RELEASING.md` records the reasoning.

**The repository's `.homepage` names this tree's own documentation
site**, read back from the endpoint rather than from `pyproject.toml`'s
own copy of it (issue btclib-org/.github#533):

```shell
gh api repos/btclib-org/bitcoin-core-rpc --jq '.homepage'
# https://bitcoin-core-rpc.readthedocs.io/
```

`[project.urls] homepage` carries the identical string: a releasing
tree's home is its own documentation, not `btclib.org`, the sibling's
project page the field named before.

```shell
gh api repos/btclib-org/bitcoin-core-rpc/pages   # 404
```

This tree serves no GitHub Pages site of its own.

## Read the Docs, which is bitcoin-core-rpc.readthedocs.io

The project's slug is `bitcoin-core-rpc`, and its public API answers
without a token for what section 11 asks of the project — `latest`
follows the default branch, `stable` is the highest release tag, and an
automation rule activates each new tag:

```shell
p=https://app.readthedocs.org/api/v3/projects/bitcoin-core-rpc
curl -s "$p/" | jq -c '{default_branch, repository: .repository.url}'
# {"default_branch":"main",
#  "repository":"https://github.com/btclib-org/bitcoin-core-rpc.git"}
curl -s "$p/versions/?active=true" \
  | jq -c '.results[] | select(.slug == "latest" or .slug == "stable")
           | [.slug, .type, .ref]'
# ["stable","tag","v2026.8.29"]
# ["latest","branch",null]
git tag --list 'v*' --sort=version:refname | tail -1
# v2026.8.29
```

`repository.url` says which repository the slug serves. `latest` is a
branch, and the branch it follows is the project's `default_branch`;
`stable` is a tag, and its `ref` is the one `git tag` sorts highest. The
tags beside those two in the same answer are the automation rule's
result rather than the rule, which that API does not expose —
`automation-rules/` answers 404 where an endpoint needing a token, such
as `redirects/`, answers 401.

**What connects this repository to Read the Docs is the organization-wide
`read-the-docs-community` GitHub App, not a per-repository webhook.**

```shell
gh api orgs/btclib-org/installations \
  --jq '.installations[] | select(.app_slug == "read-the-docs-community")
        | [.app_slug, .repository_selection]'
# ["read-the-docs-community","all"]
```

`repository_selection: all` is what makes that the connection for every
repository of the organization at once, this one included, rather than a
setting this repository carries on its own. The repository itself carries
no hook:

```shell
gh api repos/btclib-org/bitcoin-core-rpc/hooks --jq length
# 0
```

**A per-repository webhook existed here and is gone.** It pointed at
`https://app.readthedocs.org/api/v2/webhook/btclib-bitcoin-core-rpc/330990/`,
carried `active: true`, and its last delivery had been answered 404 for a
push that still built and served the documentation — the App, not the
hook, was what carried the build. A hook in that state is not a fallback
the App can be checked against: nothing reads its delivery log unless
asked, so an `active: true` webhook silently refused reads as configured
right up until somebody opens the settings page, and if the App were ever
removed it would be trusted to still be serving a connection it had
already stopped serving. It was deleted rather than repaired, since the
App already does the whole of what the hook was for (issue #291).

A hook that command finds is stale and is deleted rather than repaired:
that is section 11's rule and not a decision of this tree's alone, and
the secret is its reason — Read the Docs issues it on the project's own
integration page and GitHub returns it masked, so nothing read back from
the repository says whether a hook still carries the right one.

## Security settings

All of these are repository settings and none of them is in the tree, so
this list is the whole of them:

```shell
gh api repos/btclib-org/bitcoin-core-rpc --jq '.security_and_analysis'
# the alerts themselves are not in that object: the endpoint that
# answers for them has no body, and says so with its status -- 204 for
# enabled, 404 for not
gh api -i repos/btclib-org/bitcoin-core-rpc/vulnerability-alerts | head -1
gh api repos/btclib-org/bitcoin-core-rpc/private-vulnerability-reporting
```

| Setting | State |
| --- | --- |
| Dependabot alerts | enabled |
| Dependabot security updates | enabled |
| Private vulnerability reporting | enabled |
| Secret scanning | enabled |
| Secret scanning push protection | enabled |
| Secret scanning non-provider patterns | disabled |
| Secret scanning validity checks | disabled |
| Code scanning default setup (CodeQL) | not configured |

The two secret-scanning rows reading `disabled` are not settings this
repository declined: *Plan-gated settings* below is where that belongs,
and reading their state as something to go and fix is the mistake that
section exists to prevent.

Code scanning itself is enabled, and the row above says the opposite of
that: what performs it is `codeql.yml`, and configuring the setting would
not stop that workflow running — it would refuse the results at the upload.
"Required checks on main" above has the switch and the `gh api` that reads
the setting back.

Private vulnerability reporting is what `SECURITY.md` sends a reporter to,
and the link in `.github/ISSUE_TEMPLATE/config.yml` is the same door: with
it disabled that link is a 404, so the setting and the two files go
together.

## Topics

```shell
diff <(gh api repos/btclib-org/bitcoin-core-rpc --jq '.topics[]' | sort) \
     <(sed -n '/^keywords = \[/,/^]/s/^ *"\(.*\)",$/\1/p' pyproject.toml \
       | sort)
```

Section 3 makes a package's `keywords` its topics, entry for entry, and
this `pyproject.toml` declares a `[project]` table, so `topics_test.py`
holds this repository to that comparison. The diff above is empty: the
two lists already agree, sorted because GitHub returns topics in an
order of its own rather than `pyproject.toml`'s declared order.

## Plan-gated settings

**The ceiling on concurrent jobs lives here**, and nowhere else in this
tree: it is a number the plan decides rather than anything this repository
configures, so prose that needs the reasoning — a workflow header,
`CONTRIBUTING.md` — states the ceiling unnumbered and points here. A date
beside the figure would say when it was true and not that it still is,
where the command answers for the day it is run:

```shell
gh api orgs/btclib-org --jq .plan.name    # free
```

[GitHub's own table](https://docs.github.com/en/actions/reference/limits)
is what turns that answer into a number, and on the free plan it is twenty
concurrent jobs, shared across every repository in the organization. That
is what every trade above spends: a check required of a pull request holds
a slot every other pull request in the organization then waits for.

Some settings cannot be enabled and fail silently: secret scanning's
non-provider patterns and validity checks need paid Secret Protection, and
the API answers a PATCH with 200 while leaving them disabled. Do not read
that 200 as success. The `detect-secrets` hook is the compensating control,
and it earns its place here more than in most repositories: the subject of
this project is rpc credentials, so a cookie line and a `Basic` header are
what its tests are full of.

## What this file passes over

The endpoints above answer for more than this repository decides, and the
scope at the top is what leaves the rest out.

**Most of the repository document is not a setting.** `gh api
repos/btclib-org/bitcoin-core-rpc --jq 'keys[]'` answers with URLs,
counts, timestamps and derived state beside the switches, and the
switches among them this file records are the ones a section above reads
back with a call of its own.

**A switch no section of the standard states a rule for stays out.**
`allow_forking`, `allow_update_branch`, `has_discussions`,
`has_downloads` and `web_commit_signoff_required` are in that document
and no section above reads any of them back. Against the standard's own
`README.md`, `grep -c allow_forking` answers `0` where
`grep -c 'default branch'` does not, which is what makes the first an
absence rather than a file that was not read. Recording them would grow
this file with GitHub's API rather than with the standard, and what that
costs is a change to one of
them showing up nowhere here. `has_wiki` and `has_projects` are outside
the perimeter by section 11's own sentence, which states no rule about
either, so this file neither reads them back nor explains an answer to
them.

**A credential this repository spends and does not hold.**
`claude-review.yml` reads `secrets.CLAUDE_CODE_OAUTH_TOKEN`, and both
secret stores here answer empty for it:

```shell
gh api repos/btclib-org/bitcoin-core-rpc/actions/secrets --jq .total_count
gh api repos/btclib-org/bitcoin-core-rpc/dependabot/secrets \
  --jq .total_count
# 0, both
gh api orgs/btclib-org/actions/secrets \
  --jq '.secrets[] | [.name, .visibility]'
gh api orgs/btclib-org/dependabot/secrets \
  --jq '.secrets[] | [.name, .visibility]'
# ["CLAUDE_CODE_OAUTH_TOKEN","all"], both
```

Those two zeros record a decision, and it is section 11's: the token is
an organization secret at `visibility=all`, in both stores, so a
repository adopting the workflow configures nothing for it, and a copy
of it in a store here would be that decision undone.

**A switch this repository does not set.** `claude-review.yml` guards
its jobs with `vars.CLAUDE_REVIEW_ENABLED`, and neither variable store
holds it:

```shell
gh api repos/btclib-org/bitcoin-core-rpc/actions/variables \
  --jq .total_count
# 0
gh api orgs/btclib-org/actions/variables --jq '.variables[].name'
# (nothing)
gh api orgs/btclib-org/actions/variables --jq .total_count
# 0
```

The organization secret above answering with a name is what makes these
zeros absences rather than an endpoint that answers empty for everyone.
The variable store prints nothing at all when it answers, so its own
`total_count` of `0` is what shows the call reached it: one that does
not reach it prints an error and exits non-zero. Section 11 reads that
empty name list as `vars.CLAUDE_REVIEW_ENABLED`'s off state, an
undefined `vars.X` being the empty string. Both stores are read because
a variable set here would take precedence over one of the same name set
on the organization, so the organization's answer alone would not show
the switch off for this tree.

**A facility this repository has never reached for answers empty.**

```shell
for e in actions/runners keys autolinks properties/values; do
  gh api "repos/btclib-org/bitcoin-core-rpc/$e"
done
```

An empty answer there records no decision, so whichever of them is used
one day arrives with the section that uses it. The webhook list answers
empty as well and is recorded anyway: *Read the Docs* above is about
what that particular zero means, and *A switch this repository does not
set* about the variable store's.
