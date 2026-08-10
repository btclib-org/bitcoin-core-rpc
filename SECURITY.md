# Security policy

## Reporting a vulnerability

If you have found a security vulnerability, please do not open a GitHub
issue: an issue is public from the moment it is filed, and so is the
window between filing it and a fix being released.

Report it privately instead, by
[opening a security advisory](https://github.com/btclib-org/bitcoin-core-rpc/security/advisories/new).
Only the maintainers can see it, the discussion stays private until an
advisory is published, and a CVE can be requested from it if the
vulnerability warrants one.

If you have no GitHub account, or would rather not use it for this,
responsible disclosure by email to *security at btclib dot org* is
equally welcome.

## What belongs here, and what belongs upstream

This project is one HTTP client. What belongs here is what it does with a
credential and with a reply:

- the credential: how it is built, where it is read from, and where it
    can end up. A credential in a url, in a `__repr__`, in an exception
    message or in a traceback is a defect here
- where a request is sent: the scheme, the redirect that is refused, the
    proxy that is not taken from the environment
- what is read back: the bound on the body, what is parsed and what is
    refused, and whether a reply can be attributed to the request that
    asked for it
- the distributions published to PyPI and their provenance

What a *method* does is Bitcoin Core's, and belongs to
[bitcoin/bitcoin](https://github.com/bitcoin/bitcoin/security/policy). So
does the node's own authentication.

Report it wherever you found it, though: routing a report is the
maintainers' job, not the reporter's, and a doubt about which project owns
a flaw is not a reason to keep it to yourself.

## Supported versions

Only the latest release is supported. A fix is published as a new release,
and nothing is backported.

**A vendored copy receives nothing automatically.** Copying
the one source file is a supported way to use this project, and this is
its price: a fix published here reaches an installed package through an
ordinary dependency bump and reaches a copy only when somebody replaces the
file. Record the release tag beside the copy — that is what says whether it
needs replacing — and watch the releases of this repository if you have
taken one.

Wheels and sdist are published to PyPI with PEP 740 attestations, through
a workflow that no long-lived token can authenticate for (PyPI Trusted
Publishing), so a distribution can be traced back to the workflow run and
the commit it was built from.

The same files are attached to the GitHub release, and those copies carry
a build provenance attestation of their own, signed in the run that built
them:

```shell
gh attestation verify bitcoin_core_rpc-<version>-py3-none-any.whl \
  --repo btclib-org/bitcoin-core-rpc \
  --signer-workflow btclib-org/bitcoin-core-rpc/.github/workflows/release.yml
```

`--signer-workflow` is what makes that say which workflow signed, rather
than accepting any attestation this repository has. The signed statement
is attached to the release as well, as `<tag>.attestation.jsonl`, so
`--bundle <tag>.attestation.jsonl` runs the same check reading it from
disk instead of asking GitHub for it; one attestation covers the wheel
and the sdist both.

## Limitations, not vulnerabilities

These are known and inherent.

- **Basic authentication is cleartext over plain HTTP**, that being what
    Core's rpc speaks. On loopback the cleartext is between one process
    and the node beside it. For a node anywhere else it is on the wire,
    and rpc credentials authorise every wallet command that node has: an
    `https` url, or a tunnel, is what keeps them off it.
- **A credential handed to this client lives in Python objects**, which
    are immutable and not zeroized: it stays in process memory until
    garbage collection, and may have been copied by the interpreter
    meanwhile. `cookie_path` is the mitigation that exists — the file is
    read at each call rather than held, so the credential lives for the
    duration of one call and the node rotates it at every restart.
- **A caller's own `transport` is outside all of this.** It does its own
    I/O, so what it holds in memory, whether it follows a redirect and
    where it sends the `Authorization` header are its author's to answer
    for. The two arguments it is handed are the whole of what this module
    can say about it.
- **`getblockchaininfo` is not asked on the caller's behalf.** Nothing
    here checks which chain a node serves, so a client pointed at a
    testnet node answers testnet questions without saying so. Ask it, and
    read the answer through `network_from_chain`.
- **There is no retry, and that is deliberate**, but it means a `503` from
    a full work queue is a failure the caller has to decide about. The
    reason the decision is theirs is that `call` carries any method and a
    timeout is not a deadline: a node that stopped answering may still be
    executing the call, so a client re-sending a wallet command of its own
    accord can execute it twice.
