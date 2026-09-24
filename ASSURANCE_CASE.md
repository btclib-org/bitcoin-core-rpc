# Assurance case

[SECURITY](./SECURITY.md) states what a user can and cannot expect of
this client in terms of security. This page argues why those
expectations hold: the threat model, the trust boundaries, how secure
design principles are applied, and how common implementation weaknesses
are countered. Each argument below names the file, the test or the
workflow that supports it; where SECURITY.md already states a fact,
this page points at it instead of repeating it. The components named
here are the ones [ARCHITECTURE](./ARCHITECTURE.md) describes.

## What is claimed

- **A reply is read the way the node sent it.** JSON-RPC 1.1 and 2.0 are
  each read by the function that knows that version's own rule for where
  an error can be, and a reply is trusted as this call's answer only once
  its `id` matches what was sent.
- **Malformed input from the caller is refused before anything is
  built or sent.** A url, a credential, a timeout, a body limit and a
  parameter structure are each checked at the call that supplies them,
  raising `BtcRpcTypeError` or `BtcRpcValueError`.
- **What a node sends is bounded.** A reply larger than the caller's
  `max_body_size`, or slower than its `timeout`, is refused rather than
  held in memory whole or waited out indefinitely.
- **A credential never appears where it can leak.** Not in a url, not in
  a `__repr__`, not in an exception raised about a rejected one, not sent
  to a host a redirect or an environment variable named instead of the
  one the caller built the client for.
- **A published distribution is what this tree built.** SECURITY.md's
  *Supported versions* states how that is verified.

## Threat model

This is a library in its caller's process. It opens no file the caller
did not name a path for, but for the cookie file at a path the caller
supplied or `from_chain` derived, and it starts no process. Every input
it has is one the caller handed it directly, or bytes a node — or
whatever answered instead of one — sent back over the connection this
client opened. The command below lists the top-level name of every
module `src/` imports, at any depth and in any spelling of the
statement:

```shell
python3 - <<'EOF'
import ast, pathlib
names = set()
for p in pathlib.Path("src").rglob("*.py"):
    for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            names.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.level == 0:
            names.add(n.module.split(".")[0])
print(sorted(names))
EOF
```

What it lists, beside the package's own modules, is entirely the
standard library: `pyproject.toml` declares no dependency, which
`tests/census_test.py` holds by reading the same imports with `ast`.

**What is defended.**

- The credential: what it is built from, where it is read from, and
  every place it could end up instead of on the one request it
  authenticates.
- The caller's process: against a reply built to make a parser raise an
  exception this library does not document, or allocate without bound.
- The correctness of what a reply is read as: that a `result` is
  attributed to the call that asked for it, and that a status the node
  never computed is never read as one of its errors.

**The adversaries.**

- The node this client is pointed at, or anything answering in its
  place: a proxy, a captive portal, a host a redirect or an environment
  variable named instead of the one the caller configured.
- The caller's own configuration: a cookie path or a datadir carried
  over from a different host, a chain name assumed rather than checked.
- A party between the caller and a node reached over anything but
  loopback, for whom Basic authentication over plain HTTP is cleartext
  on the wire — SECURITY.md's *Limitations, not vulnerabilities* states
  this and what mitigates it.

**What is not defended** is SECURITY.md's *Limitations, not
vulnerabilities* section, in full.

## Trust boundaries

**The caller and the public API.** Every constructor and every call
validates its own arguments before anything is built from them: a url's
scheme, its embedded credentials, its query and its port
(`_checked_url`); a credential's type and the colon it must not contain;
a timeout that is a positive, finite number of seconds
(`_assert_valid_timeout`); a body limit that is a non-negative integer
(`_assert_valid_max_body_size`); and a parameter structure walked for
what json cannot carry — a `Decimal`, a non-finite float, `bytes`, a
container reached from inside itself, one nested past a stated depth —
before the encoder ever sees it (`_assert_json_params`). Each is checked
while the caller is still looking at the line that supplied it, not
deferred to the first call.

**The node's reply.** `_parsed_json_body` decodes it through one parser,
`json.loads` with every number a `Decimal` and every non-finite constant
refused, never `eval` and never a decoder that executes anything the
reply carries. `_reply_object` refuses a body that is not a json object,
`_id_error` refuses one whose `id` does not match the request just sent,
and `_discriminate` refuses a `jsonrpc` marker that is neither absent
nor `"2.0"`. None of it is trusted as an answer until every one of those
holds.

**The network path.** Only `http` and `https` reach a built request
(`_SCHEMES`); no proxy is taken from the environment, `ProxyHandler({})`
being how the one opener this module does its I/O with has that handler
removed rather than merely left empty; and no redirect is followed
(`_NoRedirect`). The `Authorization` header is built for one host, and
each of the three is what keeps it from reaching a different one.

**The cookie file.** Read fresh at every call rather than held —
bitcoind rewrites it at every restart — through `chains.cookie_auth`:
opened, read to one octet past a bound, decoded as ascii, and refused as
a `FetchError` naming the path for anything that is not one line with a
colon in it. A file that is simply absent is `CookieNotFoundError`,
which says the node is not running rather than that something is wrong
with the file.

**The credential in memory.** `BitcoinCoreRpcClient` defines no
`__repr__`: a generated one prints every field, which would put the
password in any traceback or log line that renders the client. A
rejected `user` or `password` is reported by its type, never echoed by
value, and the same holds for a url carrying embedded credentials —
refused without repeating the url that carried them.

**The environment.** `chains.default_datadir` reads `HOME` or `APPDATA`,
once at import for the module-level `DEFAULT_DATADIR`, and again at
every `from_chain` call that derives a cookie path because the caller
supplied neither a credential nor a `cookie_path` of its own. Nothing
else in the package reads an environment variable.

## Secure design principles

Saltzer and Schroeder's principles, against the layering ARCHITECTURE
describes.

- **Economy of mechanism.** One `HttpTransport` protocol both
  `urlopen_transport` and `SessionTransport` satisfy; one `_checked_url`
  serving both clients through its `kind` argument rather than a second
  copy of the same checks; one `_read_bounded` every transport built
  here reads a reply through.
- **Fail-safe defaults.** A caller giving neither a credential nor a
  cookie path is refused rather than answered with a client that sends
  an empty `Authorization`; `DEFAULT_MAX_BODY_SIZE` bounds a reply even
  where the caller passes nothing; a caller giving both a credential and
  a cookie path is refused rather than one silently ranked over the
  other.
- **Complete mediation.** *Trust boundaries* above is this principle
  applied at every entry point a caller or a node reaches: nothing
  downstream of the checks it lists is handed an argument that has not
  passed them.
- **Open design.** Every refusal in the source names what it refused and
  why, in the comment beside it; SECURITY.md publishes what this client
  defends and what it does not, rather than leaving either to be
  inferred.
- **Least privilege.** *Threat model* above is the census: nothing but
  the standard library. No proxy is read from the environment and no
  redirect is followed, and `BitcoinCoreRestClient` takes no credential
  at all, `-rest` needing none.
- **Psychological acceptability.** One call is one HTTP request and
  never a silent retry, so a caller is never surprised by a wallet
  command re-executed on their behalf; `HttpError.status` and
  `RpcError.code` are typed fields a caller reads, rather than a message
  a caller's policy has to parse.
- **Layering.** `errors < chains < transport < client`, one direction,
  held by `tests/census_test.py`.

## Common implementation weaknesses

Weaknesses from MITRE's CWE list that a network client of this kind is
exposed to, and what counters each.

- **Improper input validation (CWE-20).** *Trust boundaries*'s first
  paragraph, and the suite's own coverage floor under *Code that is
  wrong and still passes* below, which holds every one of those
  refusals reached: `tests/client_test.py`, `tests/chains_test.py` and
  `tests/transport_test.py` are where the client's, the chain
  vocabulary's and the transport's own are judged.
- **Insufficiently protected credentials (CWE-522) and cleartext
  transmission (CWE-319).** What SECURITY.md's *Limitations, not
  vulnerabilities* states about Basic authentication over plain HTTP is
  the transmission this client does not change, Core's rpc speaking
  nothing else; what this client does hold is where the credential can
  end up beside the wire, which *Trust boundaries*'s credential
  paragraphs above state in full.
- **Generation of an error message containing sensitive information
  (CWE-209).** The same paragraphs: a rejected credential is reported by
  type, and no `__repr__` renders one that was accepted.
- **URL redirection to an untrusted site (CWE-601) and exposure of a
  resource to the wrong sphere (CWE-668).** A credential built for one
  host reaching a different one through a followed redirect or an
  environment-derived proxy is what `_NoRedirect` and `ProxyHandler({})`
  refuse, under *The network path* above.
- **Use of insufficiently random values (CWE-330).** Every request `id`
  is `secrets.token_hex`, never a counter: a counter is shared mutable
  state, which would be the one thing making a client unsafe to call
  from two threads at once, and a value predictable across calls is
  weaker at the one thing an `id` is for here — telling this call's
  reply from a caching proxy's answer to another one.
- **Uncontrolled resource consumption (CWE-400, CWE-770).**
  `_read_bounded`'s bound on what one reply may weigh, checked before a
  byte past it is read, and its deadline, checked before each chunk
  rather than reset by one — under *The transport layer* in
  ARCHITECTURE.md.
- **Deserialization of untrusted data (CWE-502).** `_parsed_json_body`
  is the only place a reply's bytes become Python objects, through
  `json.loads` alone: no `pickle`, no `marshal`, no `eval`, and a custom
  `parse_float` and `parse_constant` refuse what `json` would otherwise
  hand back as an unusable amount.
- **Type confusion (CWE-843).** mypy runs `strict = true`
  (`pyproject.toml`) over the package and the suite, as a hook of the
  lint gate in `.pre-commit-config.yaml`.
- **Code that is wrong and still passes.** Line and branch coverage of
  the package and of the suite is held at 100% by `fail_under` in
  `pyproject.toml`.
- **Supply chain.** SECURITY.md's *Supported versions* describes the
  attestations and the bill of materials this package publishes.
  `uv.lock` pins every dependency of the development environment, and
  CONTRIBUTING.md's *The environment and the gates* states that every
  job installs with `--locked`. Every third-party GitHub Action is
  pinned to a commit sha; `actionlint` and `zizmor` run as hooks in
  `.pre-commit-config.yaml`. What a live node's own binary is checked
  against before this client is asked to talk to it is
  ARCHITECTURE.md's *What proves it, and what a live node adds*.
