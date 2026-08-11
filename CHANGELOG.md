# Changelog

<!-- markdownlint-configure-file
  {
    // MD024/no-duplicate-heading - every release repeats the same few
    // headings ("Added", "Changed", "Repository"), which is what keeps
    // the page readable scrolling down it; only a duplicate under the
    // same release heading would be the accident this rule looks for
    "MD024": { "siblings_only": true }
  }
-->

Every change of a release, in full: what changed, why, and what it cost.
[HISTORY.md](./HISTORY.md) has the release notes, which say what a user has
to act on; this file is the record behind them, and is where a claim in
those notes can be checked.

Neither file counts its entries: `grep -c '^- '` does that, whereas a
stated number is a line every open branch has to edit, and the two files
carry a union merge driver that would keep both sides' numbers.

## v2026.9 (work in progress, not released yet)

### Added

- **`RpcChannel`**, an opt-in attribute-style façade over a client's
  `call`: `channel.getblockcount()` for `client.call("getblockcount")`,
  positional arguments the sequence form of `params` and named ones the
  mapping form, never both at once. `request_timeout` and `max_body_size`,
  `call`'s own keyword-only controls, are reserved and forwarded to `call`
  rather than reaching the node as a named parameter, and every name
  starting with `_` -- dunders included -- is an `AttributeError` instead
  of a request: without that guard `copy.copy` and `copy.deepcopy` turn
  into a bound call for `__setstate__` or `__deepcopy__`, verified against
  a transport that raises on any request rather than assumed.
  `BitcoinCoreRpcClient` itself keeps its explicit `call(method, params)`
  surface unchanged; see COMPARISON.md's "Dynamic dispatch" for why the
  façade lives here rather than in a vendoring caller's own copy.
- **`verify_chain`**, an opt-in keyword on `from_chain`: after building
  the client, calls `getblockchaininfo` and compares its `chain` field to
  the one `from_chain` was given, raising `BtcRpcValueError` on a
  mismatch. Off by default, since `from_chain` otherwise asks the node
  nothing; a cookie or a datadir authenticates the node it names, not the
  chain it is running, and `-chain=test` under a cookie or a datadir
  carried over from a `main` setup is what this catches instead of a
  wrong-network call succeeding silently.

### Changed

- **`default_datadir` is public**, no longer `_default_datadir`. `from_chain`
  already called it to find the live `HOME` at the moment of the call rather
  than the one `DEFAULT_DATADIR` froze at import; a caller deriving its own
  datadir-relative path -- a wallet directory, a second cookie under
  `datadir_subdir_from_chain` -- needed that same answer and had no way to
  ask for it short of importing the underscored name or copying the
  function. No behavior changes; the name in `__all__` is the only diff.
- **COMPARISON.md's "Dynamic dispatch"** no longer calls the façade a
  vendoring caller's own to write: `RpcChannel` above is the reason, and
  the section now says why it is offered here instead.
- **The module's docstrings and comments are shorter**, and no reason is
  stated twice: each now sits in one place and is pointed at from the
  others -- the retry policy in the module docstring, which `HttpError` and
  `call` refer to; the four obligations of a caller's transport in
  `HttpTransport`, where the comment above it repeated them; the
  truncation of a failure's body in `MAX_ERROR_BODY_SIZE`; the datadir and
  the platforms it is right on in `default_datadir`, which
  `DEFAULT_DATADIR` and `from_chain` refer to. `FetchError` names its two
  subclasses once, rather than each of them repeating that it is one. Two
  statements were also wrong: the notifications paragraph named a
  `_request` function this module does not have, and the client's class
  docstring said nothing here asks the node which chain it is on, where
  `verify_chain` above does exactly that on request.
- **The upstream url in the module docstring is right again**: it named
  the repository `btclib-bitcoin-core-rpc`, which this one was renamed
  from, and the `master` branch, which is now `main`. Both spellings still
  redirect, so nothing was broken by them -- but that url is what a
  vendored copy is asked to record beside itself, and a copy is not a
  thing to leave depending on a redirect. The raw url for a release, on
  the same line, carried the same stale repository name.

### Repository

- **Code scanning is a workflow in the tree**, `.github/workflows/codeql.yml`,
  rather than GitHub's default setup. It was the only required check whose
  definition a diff could not review: the setting generates a workflow it
  does not show, where every other check on `main` is a file here with its
  actions pinned to commit SHAs. What the setting held is reproduced rather
  than re-chosen -- `gh api
  repos/btclib-org/bitcoin-core-rpc/code-scanning/default-setup` answers
  `languages: [actions, python]`, `query_suite: default` and `schedule:
  weekly`, and those are the matrix, the unset `queries` input and the
  Tuesday cron. One job per language, so a failure names the language, and
  `codeql: every job passed` aggregates them for a rule that has to name an
  outcome rather than a matrix cell. The two are exclusive at the upload and
  not at the start -- an advanced workflow runs while the setting is
  configured and its results are refused, "Upload was rejected because
  CodeQL default setup is enabled for code scanning" -- so this costs a
  five-step switch a person performs, and the analysis is red until step 2
  of it. REPOSITORY.md's "Turning default setup off without deadlocking" is
  the order; dropping the `CodeQL` context before disabling the setting is
  what keeps the rule from waiting on a check nothing produces, that context
  being the `github-advanced-security` app's and stopping with the setting
- **CONTRIBUTING.md's workflow table names what `release` calls** instead of
  counting it. The count said six where `grep -n 'uses: ./.github/workflows'
  .github/workflows/release.yml` finds five, and a row added above it would
  have made "the six above it" wrong a second way. The `workflow_dispatch`
  sentence beside it went the same way: it excepted the gates, and
  `grep -c workflow_dispatch: .github/workflows/*.yml` reports every
  workflow taking it
- **The `PATCH` REPOSITORY.md documents for the required-check list runs**,
  where the spelling it carried could not: `gh api -f` sends every value as
  a string and that endpoint types `app_id` as an integer, so
  `-f 'checks[][app_id]=15368'` earns `422 Invalid request. For
  'properties/app_id', "15368" is not a null or integer`. The body is JSON
  on stdin instead, `--input -`. Where that command is used is what makes an
  unrun one expensive: renaming a required check cannot be done in a pull
  request, so the rule moves first and by hand, and a 422 at that moment
  invites the whole-object `PUT` the same file warns drops the signatures.
  The list in it is the rule's own, read back by the `gh api` now beside the
  table -- `rpc-smoke: every job passed` was in that table and missing from
  the command, so the command as written would have dropped a required check
  rather than moved one
- **A pre-commit rev that is not a released version fails the gate.** The
  weekly autoupdate pull request has twice offered the same two moves this
  configuration must not take -- typos onto `v1`, a floating major tag its
  repository keeps beside the versioned one, and pyroma onto `5.1b1`, 5.1
  having no released tag -- and twice they were caught by hand, the second
  time after the merge, which is why the commit is reverted here. A local
  pygrep hook now names them by line instead. pre-commit itself warns that a
  mutable reference "is not supported" and exits zero anyway, which is the
  difference between the warning and this hook. A commit SHA stays
  acceptable: the pattern requires a prerelease marker to end the value
- **A merge no longer depends on bitcoincore.org answering.** The bitcoind
  archive `rpc-smoke.yml` downloads is cached across runs, keyed by the
  sha256 the matrix already pins rather than by the version, so a key can
  only ever hold the bytes it names. What it saves is nine seconds a cell,
  measured; what it removes is five fetches of Core per pull request from a
  server nobody here runs, which arrived with that workflow becoming a
  required check. The digest check and its negative control still run on a
  restored archive exactly as on a downloaded one -- verified rather than
  trusted is the property, and a cache is a mutable store
- **A pull request waits about three minutes instead of eighteen, and the
  wait was never work.** One run of the full matrix is 45 jobs, 17 minutes
  of compute and 212 minutes of queueing: no cell runs longer than a minute,
  while the two macOS images wait 15.7 and 13.1 minutes on average for a
  runner against 0.1 to 0.3 for ubuntu and windows. So `test.yml` keeps all
  seven interpreters and drops to four platforms, and the new `macos.yml`
  runs the two macOS images against the same lock weekly, on demand, and
  from a release -- which is what keeps a macOS regression from being
  published while nobody waits for one. It is scheduled the same morning as
  `latest.yml`, half an hour before, so the two read as a difference: red in
  both is the platform, red in `latest` alone is the upgrade
- **`rpc-smoke.yml` gates a merge**, where it gated only a release: the
  reason it did not was a cost the run log does not support, 12 to 24 seconds
  a cell and about 90 seconds for the workflow, live bitcoind downloads
  included. Its `paths` filter had to go with the promotion -- a required
  check that never runs blocks a merge where a skipped one satisfies it --
  so every pull request now pays those 90 seconds, and gets the one claim a
  recorded reply cannot make. The rule names its aggregate,
  `rpc-smoke: every job passed`, and not six cells
- **`published.yml` is called by `release.yml`** once PyPI has accepted the
  files, with the tag's version, and waits for the index to serve that
  version before installing -- so it can no longer pass by testing the
  release before this one, which is what the dispatch RELEASING.md asked for
  by hand could do. Not a `workflow_run` trigger, which zizmor rates
  dangerous and rightly: that runs the default branch's copy on a push
  nobody reviewed, where a call runs inside the release that gated it. Its
  schedule goes from weekly to monthly, the release path now answering the
  question the weekly was standing in for
- **Every CI job has a name, and the names say what the job answers.** The
  ids lose a suffix that distinguished nothing -- `test-py`,
  `coverage-py` and `dist-py` become `suite`, `coverage` and `dist`, there
  being one language and one package here -- while the suffix that does name
  a variant stays, `suite-latest` and `install-published` among them. Every
  job of `test.yml` and `release.yml` now declares a display name, where
  eleven of them showed their id in the checks list beside the sentences the
  other workflows wrote. The aggregate gate is `test: every job passed`,
  which carries its workflow because branch protection keys a context by
  name alone and two workflows with a job named the same thing produce one
  ambiguous check; REPOSITORY.md has the `PATCH` that moves the rule and the
  reason a rename cannot be done in a pull request
- **`release.yml` has a concurrency group**, the last workflow without one
  and the only one whose runs have side effects: two runs at once are two
  attempts at the same publication. `cancel-in-progress: false`, against
  every other workflow here, and the rule behind both is now written down --
  a superseded run is cancelled where its subject is the commit, and kept
  where its subject is a version on an index, an attestation or a release
- **The distribution files are reproducible**: a rebuild of a released tag
  is the same bytes as what was published, so the provenance attestation
  can be verified against a file the verifier built rather than one they
  downloaded. `release.yml` exports `SOURCE_DATE_EPOCH` from the commit
  date, which is the whole of it for the wheel, and runs
  `.github/scripts/normalize_sdist.py` for the sdist -- setuptools stages
  that archive in a directory it creates at build time and tars it as the
  first member, whose sub-second timestamp `SOURCE_DATE_EPOCH` does not
  reach and whose PAX record therefore changes length between two builds
  of one commit. The script rewrites member metadata and no content.
  RELEASING.md has the rebuild command, and the two bounds on the
  guarantee: the build backend is resolved rather than pinned, and a
  TestPyPI rehearsal is a different version by construction
- **The documentation build is a workflow of its own**, `docs.yml`, where it
  was the second job of `lint.yml`: a failed sphinx build and a failed hook
  are two different verdicts, and a workflow each is what gives them a badge
  each and a line each in the checks list. The job keeps its name, `Build the
  documentation`, so the required check on `main` did not have to move -- a
  context is matched by name and not by the workflow that reported it, which
  is what makes moving a job free where renaming one is not. `release.yml`
  calls the new workflow alongside `test.yml` and `lint.yml`, so a tag still
  cannot publish docstrings that read the docs would fail to render
- **The distribution files attached to a GitHub release carry
  provenance**, where until now only the copies on PyPI did: the publish
  action generates PEP 740 attestations for what it uploads to the index,
  and the byte-identical wheel and sdist on the releases page carried
  nothing, so whoever pinned to a release asset url or mirrored the page
  had no way to check where the files came from. `release.yml` gains an
  `attest` job -- `actions/attest`, one SLSA build provenance statement
  covering both files, signed with a short-lived Sigstore certificate --
  and `gh attestation verify <file> --repo btclib-org/bitcoin-core-rpc`
  is what checks it. The signed bundle is attached to the release too, so
  `--bundle <tag>.attestation.jsonl` verifies the same signature without
  asking the attestations API for it. The digests are the index's own,
  the job downloading the `dist` artifact rather than rebuilding it.
  A job of its own and not two more permissions on `github-release`:
  `id-token: write` and `attestations: write` stay off the job that
  writes releases, and further off the job that runs the build backend.
  It runs after whichever publish job ran, so a dispatch from an
  arbitrary branch signs nothing the `testpypi` environment approval did
  not already let through -- and the TestPyPI rehearsal exercises it,
  which on the release path would otherwise happen for the first time
  after PyPI has the files and the tag can no longer be moved.
- **`main` is the only branch**, renamed from `master` and now the whole
  of the model: `dev` is gone, every change reaches the trunk through a
  pull request -- a contributor's, a maintainer's, Dependabot's and
  pre-commit.ci's alike -- and a release is a tag on `main` rather than a
  branch merged into it. What two branches bought was somewhere bot
  commits could land with no required check in front of them; what they
  cost was a permanently draft release pull request, a rebase merge whose
  new SHAs left the two branches equal in content and unequal in identity,
  and the realign that then had to force-update `dev` behind a rule
  blocking force pushes that an administrator is not exempt from. One
  branch pays none of that, and gates every commit on the same four
  checks. Dependabot declares no `target-branch` and pre-commit.ci no
  `autoupdate_branch`, both taking the default branch; the draft exemption
  the release pull request needed (`|| github.base_ref == 'master'`, in
  five workflows) goes with it, so a draft runs no CI at all and nothing
  is exempt; `test.yml` and `lint.yml` push-trigger on `main`.
  `REPOSITORY.md` holds what the branch rule requires and why,
  `CONTRIBUTING.md` how a change lands, `RELEASING.md` how a release is
  cut from one branch.
- **`main`'s branch rule requires no approving review, and applies to
  administrators.** The four checks are unchanged and `strict` with them,
  as are required signatures, linear history, blocked force pushes and
  blocked deletions; what goes is the one approving review, which GitHub
  does not let an author give themselves -- on a solo-maintainer
  repository it either stops every merge or is waved through on every
  merge, and a rule whose normal operation is its own bypass gates nothing
  while reading as though it does. `enforce_admins` is on in its place, so
  what is left holds for everyone.

## v2026.8.8

### Added

- **COMPARISON.md**, the case for this client against `AuthServiceProxy`:
  the comparison table row by row, the three rows that carry the weight --
  amounts, credentials and errors, enforced by construction rather than
  left to discipline -- and the consequence of the typed errors that
  nothing announces, a refused connection arriving as a `FetchError` and
  no longer as the `OSError` an `except` clause was written for. Then the
  three features this client does not have and what decides each: dynamic
  dispatch, which absorbs typos of the client's own surface and returns
  `Any` where the package ships `py.typed`; batching, whose correlation
  and partial failure JSON-RPC 2.0 section 6 settles, and whose cost is a
  timeout covering several node operations, a `max_body_size` that stops
  mapping onto an answer, and a third parsing branch -- reachable through
  `http_request` and `auth_header` for the WAN link a batch pays on; and
  one connection per call, which is CPython's `do_open` setting
  `Connection: close` rather than a choice made here, negligible per call
  on loopback and socket churn in aggregate. The README's
  ["Migrating from `AuthServiceProxy`"](./README.md#migrating-from-authserviceproxy)
  is the line-by-line rewrite; this is why the rewrite is worth doing.
  Linked from the README, and from `docs/source/index.rst` alongside the
  other root documents.

### Changed

- **The timeout bounds the body of a failure too**, where
  `MAX_ERROR_BODY_SIZE` and the socket timeout bounded it alone -- and a
  socket timeout is per recv, so a peer sending an octet just inside it
  holds the call for as many packets as 64 KiB takes. `http_request` takes
  a `monotonic()` deadline before the transport call and reads the
  `HTTPError` through `_read_bounded`: an `HTTPError` forwards `read1` to
  the response it wraps and answers `headers` with the ones it carries, so
  it is read as the response it is. A page still arriving at the deadline
  goes back as its status with an empty body, which is what a page that
  cannot be read at all already did -- the status is the part a caller has
  a policy for. A transport of a caller's own is held to that deadline for
  the error body alone, that being the only part of such an exchange this
  module does the reading of.

  `_read_bounded` grows a `truncate` keyword, the two bounds differing in
  what they do at the limit: an answer over `max_body_size` is refused, a
  diagnostic over `MAX_ERROR_BODY_SIZE` is cut to it and answered, and an
  announced `Content-Length` over the limit is not grounds for refusal
  under `truncate` either.
- **`_read_bounded` accumulates into one `bytearray` now, not a `list` of
  chunks joined at the end.** A `list` keeps every chunk alive as its own
  object until the join, so a response near `max_body_size` sat in memory
  twice over -- once as the pieces, once as the joined result -- for as
  long as both stayed in scope; a single growing buffer replaces the
  pieces instead of standing beside a second copy of them. The one copy
  this function cannot avoid is `bytes(buffer)` at the end, since a
  `bytearray` is not the immutable value it promises: the docstring now
  says so directly, `max_body_size` bounding what is read and not the
  memory reading it costs, which is that bound plus the one copy the
  return type is worth.
- **`http_request`'s `timeout` is validated at the boundary now, and not
  only `max_body_size`.** `BitcoinCoreRpcClient` already refused a `0`, a
  negative number, `True` or a `NaN` for its own `timeout` and
  `request_timeout`, but `http_request` is public on its own, so a direct
  caller with a transport of its own reached the socket layer with
  whichever of those it passed. `_assert_valid_timeout` runs alongside
  `_assert_valid_max_body_size` now, before the request is built, so every
  public timeout argument is refused the same way and the transport is
  never reached with one that cannot work.
- **Three documented claims narrowed to what the code does.** The named
  parameter form was one "no attribute lookup can express", which a
  `**kwargs` façade expresses; what no attribute lookup can carry is both
  parameter forms together with the client's own per-call controls, and
  that belongs to [COMPARISON.md](./COMPARISON.md)'s account of the
  non-goal rather than to a migration example, so the claim is gone and
  the example stands on its own. A loop over `call` was the replacement
  for a batch without qualification, and it is an equivalent beside the
  node and not over a link where the round trip costs something, which is
  where a batch pays -- the README and the module docstring both say so
  now, the second because a vendored copy has no README beside it. And a
  connection per call "costs nothing" beside the node per call, while a
  great many of them are socket churn: RFC 9112 section 9.6 has the server
  initiating the close on `Connection: close`, so the node is what holds
  the sockets in TIME_WAIT, and the docstring now sends a caller polling
  in a loop to its own `transport` on loopback too and not only over
  `https`.
- **The between-releases placeholder is the month, `2026.9`, and no longer
  the last release with its trailing component bumped.** The old
  placeholder was shaped exactly like a release on purpose, which left one
  guard in front of it: `version-check`'s heading check against HISTORY.md
  and CHANGELOG.md. A version with no day cannot be published at all --
  the same `version-check` requires three components of anything tagged,
  and always did -- so the month-only shape puts a second, independent
  guard behind the first, and a checkout of `dev` stops reporting itself
  as a release it is not. `pyproject.toml`, `uv.lock` and the two
  work-in-progress headings move with it, and `release.yml`'s comment on
  the three-component check says which guard it now is.
- **RELEASING.md takes back eight steps from btclib's copy of it.** The
  rehearsal from `master` after the version bump, and the annotated tag
  that names the release commit and is read back with `git show` before
  the push, the argumentless `git tag` being one `cd` away from tagging
  the commit before the bump; the local gates as the evidence they are
  here, `test.yml` and `lint.yml` triggering on `pull_request` and a push
  to `master` alone, so a commit pushed straight to `dev` runs neither;
  the read-the-docs *builds* page, which a rendered page answering 200
  does not stand in for; the 100-commit ceiling on "Rebase and merge",
  past which the button reads `This branch can't be rebased` and the
  command line it wraps is what is left; the fast-forward that ceiling's
  `git merge-base --is-ancestor` also detects, which makes the realign
  step below it moot and is now the question that step opens with; the
  404 a `workflow_dispatch`-only workflow answers until its file reaches
  the default branch; `git tag --sort=v:refname`, without which `v2026.10`
  lists before `v2026.7`; and deleting a botched tag locally in every
  worktree, a tag being per-repository where a branch is per-worktree.
  `latest` gets the short form of btclib's paragraph, there being no
  sibling pin here for the long one.
- **`keywords` and the GitHub repository topics name the same things.**
  The keyword list had neither `zero-dependency` nor `vendorable`, which
  the topics already carried and which are two of the three things the
  README leads with; `bitcoin-rpc` is new to both, and is what somebody
  looking for this searches for. The order is by relevance rather than
  alphabetical, PyPI showing keywords as the metadata gives them; GitHub
  sorts its own, so there the order decides only which topic goes when the
  twenty it allows are full, which nine is well short of. Three candidates
  are left out, and the comment beside the list says why: `python`, which
  names no feature and repeats the `Programming Language ::` classifiers,
  `type-hints`, which repeats `Typing :: Typed`, and a chain name,
  `from_chain` carrying Core's defaults for all five. The `python` topic
  goes for the first of those reasons, leaving the two lists identical.

### Repository

- **The README's migration section pairs each `AuthServiceProxy` command
  with the one that replaces it, where it listed lines and left the reader
  to pair them.** One block held three changes, each of them a comment
  followed by two or three lines in no marked order: the `AuthServiceProxy`
  spelling and the one here were told apart only by the class name where a
  line happened to carry one, so the two `client.call` lines under
  `rpc.getblock` read as a sequence to run rather than as the same call
  twice, and the `for_wallet` change had no "before" line at all. It is now
  one block per change, each opening `# AuthServiceProxy` and continuing
  `# this client`, under a sentence of prose saying what moved and why --
  connecting, invoking a method, a wallet command, a batch and an error,
  the last two of which were prose with no command in them. `batch_`
  gains the loop that replaces it, spelled out. The claim that an unknown
  method "arrives at the node, not an AttributeError here" is gone with
  it: `AuthServiceProxy.__getattr__` builds a proxy for any name too, so
  the sentence named a difference that is not one, where what does differ
  is that a method name is data here and cannot collide with the client's
  own attributes. No count of the changes either, the old "four changes"
  having counted three blocks and a paragraph. Every `# this client` line
  was run against a stub transport before the section was rewritten around
  them, which is what the section had never been.

- **The README gained the badges it was missing -- `status`, `downloads`,
  `docs` and `pre-commit.ci` among them -- and now carries only the ones
  that can turn red.** None of the additions claimed something new:
  `pre-commit.ci` is the check already configured in
  `.pre-commit-config.yaml`'s `ci:` block and already running against
  `dev`; what was missing was the badge saying so. They read on three
  lines, in the order the reader asks for them: version, downloads,
  development status, license and supported interpreters first; test,
  lint, pre-commit.ci and the documentation build second; the repository
  and the `slack` channel third, "where is the code" and "where do I ask"
  being the two questions a reader has once the first two lines have
  answered theirs. Version and downloads are adjacent, both being PyPI
  reading back the same project, and `test` precedes `lint`, a red suite
  and a red linter not weighing the same. The badges that report no state
  -- `cal_ver`, `uv`, ruff, mypy, markdownlint-cli2 and `pre-commit
  enabled` -- name a choice rather than measure anything, so they open
  CONTRIBUTING.md, which is the file that says how each choice is enforced
  and what the command for it is; ruff is three of them, its formatter,
  its linter and its docstring rules being three gates with three
  documentation pages and three ways to fail, where one badge announced
  them as one. `pre-commit` closes that run because it is what runs the
  others, and the repository and `slack` badges close the line, a
  contributor wanting both. No `twitter` badge, which the sibling projects
  dropped too. The alternative text says what a badge means -- "PyPI
  version", "supported Python versions", "test workflow status" -- rather
  than naming the site that serves the image: it is the accessible name of
  the link, and a flat list has nothing else to carry the meaning. One
  badge per source line, which puts a badge change in one line of a diff
  and needs no `markdownlint-disable MD013`: the rule's 80 columns bind
  only where a space follows them, and in a bare URL none does. btclib and
  btclib_libsecp256k1 carry the same three lines and the same
  CONTRIBUTING.md run, which is what makes the three comparable; the badge
  sets differ only where the projects do.

- **The GitHub repository is `btclib-org/bitcoin-core-rpc`**, where it was
  `btclib-org/btclib-bitcoin-core-rpc`: the distribution took the shorter
  name in v0.1.0 already, and the repository read as the wrong thing to
  clone for a client that is not part of btclib for exactly as long as it
  kept the old one. GitHub redirects `git clone`, the web UI and most of
  the REST API from the old path, so nothing with it cached breaks
  outright; every URL this tree spells out regardless -- `release.yml`'s
  `github.repository` guard on the publish jobs, `pyproject.toml`'s
  `[project.urls]`, RELEASING.md's and REPOSITORY.md's `gh api` runbook
  commands, the README's badges and Links section, CONTRIBUTING.md,
  SECURITY.md, AUTHORS.md and both issue templates -- now names the new
  one, so none of it depends on the redirect staying up. PyPI's Trusted
  Publisher entry lives outside this tree and does not follow a GitHub
  rename automatically; RELEASING.md's setup step now records the new
  repository name, and the entry on pypi.org needs updating to match
  before the next release, or that release's OIDC handshake fails.

## v2026.8.7

### Added

- **`rpc_port_from_chain` and `datadir_subdir_from_chain`**, the port and
  the subdirectory Core gives a chain, which `from_chain` reads and a
  caller could not derive: `main` keeps its cookie in the datadir itself
  and `test` lives under `testnet3`, neither of them a name the chain name
  gives away. A node on another host, or one started with `-datadir=`
  elsewhere, is a url and a `cookie_path` the caller assembles, and these
  two are what it assembles them out of instead of a table copied from
  here. Functions rather than the dicts behind them, for the reason the
  vocabulary pair are functions: an unknown chain is refused where it is
  named, and a published dict is a table a caller can write to.

- **`Chain` and `Network`**, a `Literal` each for the five names of each
  vocabulary, and what `chain_from_network` and `network_from_chain` are
  now annotated as returning. Not what they take: an argument arrives from
  a config file or from `getblockchaininfo`, as a `str` no annotation
  narrows, so a parameter of that type would only mean a cast at the call
  site — the runtime refusal is what checks a name either way. Not an
  `Enum` either: both vocabularies are `str` in every place they are
  spoken, `-chain=` and a json body included, so an enum would be an
  island every caller converts at, and this file has to import on 3.10,
  where `StrEnum` does not exist and the `str, Enum` that stands in for it
  formats as `Chain.MAIN` inside an f-string.

- **`USER_AGENT`**, what `call` now sends as the `User-Agent` header:
  `bitcoin-core-rpc`, where urllib's default named the interpreter and
  identified neither this client nor the program running it. What a node's
  access log and any proxy in front of it record, the request `id` already
  marking the same call in the node's debug log. No version in it, for the
  reason there is none anywhere here -- the release tag is the version,
  and a copied file would carry whichever one it was copied from forever.
  Published so that a caller writing a transport of their own can send the
  same thing.

### Changed

- **every public name reaches the documentation.** `docs/source/api.rst`
  says the page lists the whole public interface, and it listed fourteen
  of the twenty-three names in `__all__`. `automodule` with `:members:`
  documents a class or a function by its docstring and a module-level
  assignment by the string literal that *follows* it; a `#` comment is
  neither, so a name carrying one is absent from the built page rather
  than undescribed on it. The nine were `COOKIE_USER`, `DEFAULT_DATADIR`,
  `DEFAULT_MAX_BODY_SIZE`, `DEFAULT_TIMEOUT`, `MAX_ERROR_BODY_SIZE`,
  `USER_AGENT`, `Chain`, `Network` and `HttpTransport` -- the last of
  which is the type a caller has to implement to pass a transport of their
  own, so the interface the module tells them to use was the one they
  could not look up.

  Each has a docstring now, and the `#` comment above it keeps the
  reasoning that is not a caller's business: the docstring states the
  contract, the comment says why not the alternative, which is the split
  CONTRIBUTING.md already draws between the two.
  `test_every_public_name_carries_a_docstring` fails on the next name that
  arrives without one.
- **a read asks for a chunk, not for the whole limit.** `read1` allocates
  what it was asked for, and the response narrows that request only where
  it knows how -- `HTTPResponse.read1` caps n at the remaining
  `Content-Length`, or at the rest of the current chunk, and does neither
  for a body the close of the connection delimits. Against a peer like
  that, `max_body_size` was paid in full on every reply however small,
  which is the limit behaving backwards: widening it to allow one large
  answer cost that much on each little one. Measured with `tracemalloc`
  against a local HTTP/1.0 server sending a fifty-octet reply with no
  announced length, peak allocation for one `call`:

  | `max_body_size` | before | after |
  | --- | --- | --- |
  | 8001024 (the default) | 8.27 MB | 0.34 MB |
  | 1024 | 0.14 MB | 0.20 MB |

  Core announces a length, so a call to a node was never the case that
  paid it; something in the way that does not is. Not a regression from
  the `read1` of the deadline change either -- the `read(max_body_size +
  1)` before it allocated the same, measured at the same 8.27 MB on the
  commit before. `test_a_read_asks_for_no_more_than_a_chunk` is what keeps
  the request bounded.
- **three arguments are checked where they are written**, which is
  `_checked_url`'s rule and the three that escaped it. A `transport` that
  is not callable built a client and failed at the first `call`, from
  inside urllib; a `cookie_path` that is no path left through pathlib's
  TypeError about `__fspath__`; a `wallet_name` that is not a string left
  through urllib's about `quote_from_bytes` -- and `for_wallet(b"hot")`
  did not fail at all, `quote` taking bytes, so it built an endpoint from
  a name nobody spelled. Each is a `BtcRpcTypeError` naming the argument
  now.

  `cookie_path` is annotated `str | PathLike[str] | None` with that, where
  it said `Path | str | None`. The runtime check is what `Path()` on the
  next line accepts, and an annotation narrower than the check is the
  disagreement that matters: a `PurePosixPath` worked and a type checker
  said it would not. Widening a parameter breaks no caller -- `Path` is a
  `PathLike[str]` -- and what the attribute holds is a `Path` either way.
- **`for_wallet` builds `type(self)`**, where it named this class. A
  subclass kept its type through `from_chain`, which builds with `cls`,
  and lost it at the one call whose whole subject is carrying this
  client's configuration over.
- **the timeout bounds the whole exchange**, where it bounded each socket
  operation. A socket timeout is reset by every packet, so a peer sending
  one octet just inside it held a call open until `max_body_size` octets
  had arrived -- with the default that is eight megabytes at a byte a
  time, and no number of seconds a caller could write said otherwise.
  `urlopen_transport` takes a `monotonic()` deadline before the connect
  and `_read_bounded` stops at it, so the wait is the timeout plus the one
  recv in flight when it passes. Refused as
  `still arriving when the timeout expired`, a FetchError like the other
  ways an exchange does not produce an answer. What it costs is a reply
  that legitimately takes longer than the timeout to arrive -- a large
  `getblock` over a slow link -- and `request_timeout` is what that call
  passes.

  The read is `read1` and not `read`, which is the half without which the
  deadline is decoration: the response reads through a `BufferedReader`,
  whose `read(n)` blocks until it holds *n* octets, so the whole drip
  happened inside one call and no check ran between packets. Measured
  against a server sending an octet every 0.3s under a one-second timeout:
  the `read` spelling returned only when that server stopped, the `read1`
  one at the deadline. `FakeResponse` in the tests answers the two calls
  differently for the same reason -- a fake whose `read` returned early
  cannot tell a bounded read from an unbounded wait.

  Two bounds are unchanged, and deliberately. A caller's own transport
  gets no deadline: two positional arguments have nowhere to carry one,
  and `HttpTransport`'s comment lists this with the rest of what such a
  transport owes. And the body of a *failure*, which `http_request` reads
  off the `HTTPError`, is still bounded by `MAX_ERROR_BODY_SIZE` and by
  the socket timeout alone -- a drip there is 64 KiB of diagnostic rather
  than eight megabytes of answer, and threading the deadline into that
  path is a change to the exception handling rather than to the read.
- **a refusal on size names `max_body_size`**, in all three places one is
  raised, where they said `more than the 8001024 allowed` and left the
  reader to find which knob carried that number.
- **`core_chain_from_network` and `network_from_core_chain` are
  `chain_from_network` and `network_from_chain`.** In this module `chain`
  is Core's vocabulary and `network` the BIP one -- `from_chain` is named
  for it, and so are the parameters of both functions -- so `core_` was
  spelling a distinction the names around it already carry. What it costs
  is a rename in a caller: the old names are gone rather than aliased, one
  release being a short enough life for a name that a second spelling of
  it is the worse thing to publish.
- **an unknown chain is refused as `unknown Core chain`** wherever it is
  refused, `from_chain` included, where that one said `unknown chain: ...
  These are Core's names, not the BIP ones`. The check there is now
  `rpc_port_from_chain`'s, so the three functions a chain name reaches say
  the same thing, and the three words say what the sentence did.
- **the class docstring says that a call opens its own connection.**
  urllib holds none, so every `call` sends `Connection: close` and
  connects again. Beside the node that is loopback and costs nothing; to a
  node over `https` it is a TLS handshake each time, which is a caller
  polling one in a loop wanting a `transport` of their own. Documented and
  not fixed: keeping a connection alive means a pool, its own
  thread-safety and its own eviction, none of which one bounded request
  needs, and `HttpTransport` is the seam a caller who wants all three
  already has.

### Tests

- **the five chains are checked against every table that takes one.** They
  are written down four times -- a port, a datadir subdirectory, a network
  name and a `Literal` each way -- and only the `Literal`s failed anything
  when one was forgotten, at a type check rather than here. A port with no
  subdirectory beside it derives a cookie path under a directory that is
  not the node's.

### Repository

- **the smoke script stops waiting on a credential the node refused.**
  `wait_for_rpc` retried every `FetchError` until `STARTUP_TIMEOUT`, and a
  401 is a `FetchError` -- so a wrong cookie was two minutes of polling
  followed by `no rpc answer in 120.0 s`, which names the symptom. It is
  the case `HttpError.status` exists for, and the script already asserted
  the property from the other side in `check_credentials_refused`. Every
  other status is still retried: a 503 from a full work queue is the one
  that does clear on its own, and the rpc error -28 of a node reading its
  index arrives as an `RpcError`.
- **`except (FetchError, RpcError)` is `except FetchError`**, there and in
  `stop`. `RpcError` and `HttpError` are both a `FetchError`, so the pair
  read as two families where there is one.
- **RELEASING.md asks griffe whether the breaking-change list is
  complete**, as a release step carrying the command. HISTORY.md promises
  that a break is announced there, the calendar version promising nothing,
  and until now nothing read that promise back: the suite judges the code,
  and review weighs what the notes say rather than what they leave out.
  griffe reads the public API at the previous release and at the tree and
  reports the breakage between them -- against v2026.8.6 it names
  `core_chain_from_network` and `network_from_core_chain`, which this cycle
  removed and HISTORY.md announces, so the first cycle the step applies to
  is one it passes. A step and not a hook, for the reason RELEASING.md
  gives: the comparison is against the previous *release*, so a deliberate
  break stays a finding until the release that announces it, leaving every
  pull request in between red for something no branch introduced.

## v2026.8.6

The first release.

### Added

- **the distribution ships `py.typed`**, so a consumer's type checker reads
  these annotations with no configuration at all. That marker has to sit
  inside a package directory, which is why the source is
  `bitcoin_core_rpc/__init__.py`: measured against a built wheel of each
  layout, a top-level module leaves `mypy --strict` reporting "missing
  library stubs or py.typed marker" and treating every name as `Any` --
  and a `py.typed` or a `.pyi` placed beside such a module changes
  nothing, mypy looking for the marker under `<module>/`. What it costs is
  that vendoring is now a copy *and a rename*, which the module docstring
  and the README both say.

### Changed

- **`BTClibValueError`, `BTClibTypeError` and `BTClibRuntimeError` are
  `BtcRpcValueError`, `BtcRpcTypeError` and `BtcRpcRuntimeError`.** The old
  names were this file's while it lived inside btclib, and btclib declares
  three of its own spelled exactly that way -- so a consumer holding both
  had two same-named classes and an `except BTClibValueError` that reads
  correct at every call site while being the wrong one at some of them.
  btclib hit that taking the dependency, in an `except` around a function
  of this module. Nothing catches these names inside this package, so the
  change is a rename; nothing has shipped, so no caller has to act.
- **a request id is prefixed `btcrpc-`**, where it said `btclib-`. The
  prefix reaches a node's `debug.log`, and naming a library the caller may
  not be using was a claim this package had no business making.

- `BitcoinCoreRpcClient`, one Bitcoin Core JSON-RPC endpoint and the
  credentials to reach it. `call` invokes any one method with positional or
  named parameters, `from_chain` builds a client for the local node of one
  of Core's chains from Core's own port and datadir tables, and
  `for_wallet` derives the `/wallet/<name>` endpoint with the name
  percent-encoded.
- JSON-RPC 2.0 with 1.1 read back, so a node older than v28 — which does
  not know the `"jsonrpc": "2.0"` marker and replies 1.1 to it — is
  answered correctly, an rpc error under an HTTP 500 included.
- `FetchError`, `HttpError` and `RpcError`: one exception for a backend
  that did not answer, one for an exchange that failed with a status, one
  for an error the node computed with its code and its `data`. All three
  are `FetchError`, so one `except` catches the lot, and the fields are
  what a caller's own retry policy reads. `HttpError` and `RpcError` hand
  every constructor argument to `BaseException.__init__` and compose their
  message in `__str__`, which is what makes them picklable —
  `BaseException.__reduce__` rebuilds an exception from `self.args`, and a
  class carrying two or three fields is not rebuilt by calling it with the
  one composed string those two used to leave in `args` — and what a
  `ProcessPoolExecutor` needs to send one back from a worker rather than
  report the pool broken.
- Amounts as `Decimal` in both directions: a number in a reply is parsed
  exactly, a `Decimal` parameter is refused rather than rounded through
  `float`, and `NaN` and `Infinity` are refused either way.
- `cookie_auth` and `DEFAULT_DATADIR`, for the credential bitcoind writes
  and rotates at every restart — read at each call rather than held.
- `core_chain_from_network` and `network_from_core_chain`, the two
  vocabularies written down once: `main` where BIP32 and BIP173 say
  `mainnet`.
- `HttpTransport`, `urlopen_transport` and `http_request`: the seam that
  lets code calling a node be tested without one, and the bounded urllib
  implementation behind it.

### Security

- No credential in the url: a url carrying `user:password@` is refused,
  that string being what ends up in configuration files and tracebacks.
  The class has no generated `__repr__` for the same reason.
- No redirect followed, and no proxy taken from the environment: a request
  already carries the `Authorization` for the host it names, and both
  would send it somewhere else.
- `http` and `https` only, so a url from configuration cannot make this
  read the local disk through `file:`.
- Every response body is read under a bound, `Content-Length` checked
  first and then not believed.

### Repository

- The project standards of btclib-org: the lint gate is
  `.pre-commit-config.yaml` and `lint.yml` runs that very file; every
  action is pinned to a commit SHA; coverage is a 100% ratchet rather than
  a report; `mutation.yml` asks weekly whether a line the suite executes is
  a line the suite checks; `rpc-smoke.yml` asks two live bitcoind versions
  whether the recorded replies are still what Core sends.
- Calendar versioning, `YYYY.M.D`: a release is named by the day it was
  cut, and what it breaks is read in HISTORY.md rather than inferred from
  the number. The month carries no leading zero, PEP 440 normalizing
  `2026.08` to `2026.8` and `release.yml` comparing the tag to the declared
  string as written. `release.yml`'s version-check job also refuses a tag
  with fewer than three components: without it a tag naming only the
  month, `v2026.8`, would pass every other check and publish a version
  indistinguishable from the placeholder `pyproject.toml` declares between
  releases, which names the same month and is never tagged.
- `.github/scripts/rpc_smoke.py` restructured for `tests/rpc_smoke_test.py`
  to cover: every function with no live node behind it —
  `check`, `port_is_free`, `check_legacy_reply`, `check_v2_reply`,
  `check_cookie`, `print_log_tail`, and `main`'s own argument parsing —
  now has a test with no `bitcoind` in the loop, and every function that
  does talk to one carries `# pragma: no cover`, that half staying
  `rpc-smoke.yml`'s to monitor against Core itself.
- `mutation.yml`'s session runs under `timeout --signal=INT` rather than
  the default SIGTERM, with a `git diff --quiet` check afterwards that
  restores the tracked source if anything is left changed. The local
  distributor applies a mutant and restores it from a `finally` block that
  only runs if the process can unwind; SIGTERM kills it outright,
  mid-mutant, before that block runs, where SIGINT is what Python turns
  into a catchable `KeyboardInterrupt`. A session cut at its budget could
  otherwise leave `bitcoin_core_rpc.py` mutated for whatever ran next.
- The MIT permission notice in full at the head of every source file, and
  `COPYRIGHT` — the text a hook requires them all to carry — is that notice
  rather than a pointer to `LICENSE`: `bitcoin_core_rpc.py` is meant to be
  copied out, and a copy has no `LICENSE` beside it to point at. No year in
  it, so a vendored copy nobody has touched does not look out of date every
  January.
