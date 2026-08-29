# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`BitcoinCoreRpcClient` and `RpcChannel`: request building, reply reading.

The layer that decides what a status and a body *mean*: `_reply_object`,
`_legacy_result` and `_v2_result` are the JSON-RPC 1.1 and 2.0 reply
shapes, `_discriminate` is what picks between the latter two, and
`BitcoinCoreRpcClient.call` is what builds the request they answer.
`call_batch` sends several such requests in one HTTP exchange and reads
each member's reply with the same `_discriminate`, by way of
`_batch_reply_array`'s array-shaped counterpart to `_reply_object`;
`call_raw` builds one request the same way `call` does and hands back
whatever `_parsed_json_body` parses, unread and unshaped past that.
"""

from __future__ import annotations

import json
from base64 import b64encode
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, DecimalException
from math import isfinite
from os import PathLike
from pathlib import Path
from secrets import token_hex
from typing import Any
from urllib.parse import quote, urlsplit

from bitcoin_core_rpc.chains import (
    cookie_auth,
    cookie_path_from_chain,
    default_datadir,
    magic_from_chain,
    magic_from_signet_challenge,
    rpc_port_from_chain,
)
from bitcoin_core_rpc.errors import (
    BtcRpcTypeError,
    BtcRpcValueError,
    FetchError,
    HttpError,
    RpcError,
)
from bitcoin_core_rpc.transport import (
    _SCHEMES,
    DEFAULT_MAX_BODY_SIZE,
    DEFAULT_TIMEOUT,
    HttpTransport,
    _assert_valid_timeout,
    _is_integer,
    http_request,
    urlopen_transport,
)

# Every name this module defines, none of it imported: `__init__.py`'s own
# `__all__` is their union across the four modules of the package, and
# section 7 of the organization standard asks each of them for its own
# besides.
__all__ = [
    "USER_AGENT",
    "BitcoinCoreRpcClient",
    "RpcChannel",
]

# how many random bytes make the `id` of a request this call's. Distinct
# per call: the echo check exists to catch a reply that answers another
# request -- a caching proxy in the way -- and a value reused across calls
# cannot tell that reply from the right one. Random rather than counted
# because a counter is shared mutable state, which is the one thing that
# would make a client unsafe to call from two threads. Prefixed on the way
# out, so a node's debug log says whose call it was
_RPC_ID_BYTES = 8

# how deep a parameter structure may nest. Both the encoder and the walk
# that checks a structure before it recurse, so a bound is what turns
# something too deep for either into a refusal that names the parameters
# rather than a RecursionError out of the standard library. Core's own
# methods nest a few levels -- the inputs of a psbt, the tree of a
# descriptor -- so this is not a limit a call arrives at
_MAX_PARAMS_DEPTH = 100


USER_AGENT = "bitcoin-core-rpc"
"""What `call` sends as `User-Agent`, and a transport of a caller's own can.

urllib's default names the interpreter -- `Python-urllib/3.14` -- which
identifies neither this client nor the program running it, where a node's
access log and any proxy in front of it record this. No version in it:
the release tag is the version, and a constant inside the package is a
second one that drifts against it.
"""


def _rpc_id() -> str:
    """Return the `id` of one request, distinct from every other."""
    return f"btcrpc-{token_hex(_RPC_ID_BYTES)}"


def _checked_url(url: str) -> str:
    """Return the endpoint url, having refused what is not one.

    Checked when the client is built and not at the first call, which is
    where `urlopen` would refuse most of it: a url is configuration, and
    configuration that cannot work is worth refusing while the caller who
    supplied it is still looking at the line.
    """
    split = urlsplit(url)
    if split.scheme not in _SCHEMES:
        err_msg = f"invalid rpc url scheme: '{split.scheme}' instead of http(s)"
        raise BtcRpcValueError(err_msg)
    if split.username is not None or split.password is not None:
        err_msg = "credentials in the rpc url:"
        err_msg += " pass user and password, or use the cookie file"
        raise BtcRpcValueError(err_msg)
    if not split.hostname:
        raise BtcRpcValueError(f"no host in the rpc url: {url}")
    if split.query or split.fragment:
        err_msg = f"query or fragment in the rpc url: {url}"
        err_msg += " -- an rpc endpoint is a path, and the call is the body"
        raise BtcRpcValueError(err_msg)
    try:
        # the port is parsed on access and not before, so this is what
        # refuses `http://node:https` here rather than at the first call
        _ = split.port
    except ValueError as e:
        raise BtcRpcValueError(f"invalid port in the rpc url: {url}") from e
    return url


def _params_member(params: Sequence[Any] | Mapping[str, Any] | None) -> Any:
    """Return what goes in the request as `params`, refusing what cannot.

    JSON-RPC has two parameter structures and Core takes both: an array,
    read positionally, and an object, read by name. Which of them a
    method wants is the method's business, so both go through unchanged
    -- Core's `args` convenience included, a named call carrying an array
    of leading positional values, which is one key of a caller's mapping
    and needs nothing here.

    A str, bytes or bytearray is a Sequence and is never a list of
    parameters: `call("getblock", block_id)` means one parameter, where
    json would have sent sixty-four of them. Refused rather than wrapped,
    since a caller who meant a sequence of one has `[block_id]` to say so
    and nothing tells the two intentions apart from here.
    """
    if params is None:
        return []
    if isinstance(params, Mapping):
        return dict(params)
    if isinstance(params, (str, bytes, bytearray)):
        err_msg = f"rpc params is a {type(params).__name__} and not a sequence"
        err_msg += " of parameters: pass [params] for a single positional one"
        raise BtcRpcTypeError(err_msg)
    if isinstance(params, Sequence):
        return list(params)
    # unreachable under the annotation above, which is not a promise a
    # caller that skips type checking keeps
    err_msg = "rpc params is neither a sequence nor a mapping, but a"  # type: ignore[unreachable]
    err_msg += f" {type(params).__name__}"
    raise BtcRpcTypeError(err_msg)


def _assert_json_params(
    value: Any, depth: int = 0, enclosing: tuple[int, ...] = ()
) -> None:
    """Refuse a parameter structure json cannot carry, before it is encoded.

    Walked rather than left to the encoder, because most of what goes
    wrong here is silent or unhelpful in it. A mapping keyed by anything
    but a string is *rewritten*: `{1: "a"}` encodes as `{"1": "a"}`, so a
    caller's value reaches the node changed rather than refused, and only
    the outermost mapping is a name a caller wrote by hand. A structure
    containing itself raises ValueError("Circular reference detected"),
    which is the same type a non-finite number raises and means something
    else entirely. One nested past the interpreter's stack raises
    RecursionError from inside the encoder. And a Decimal or a `bytes`
    reaches `default`, which cannot say where in the structure it was.

    `enclosing` carries the ids of the containers this value sits inside,
    which is what a cycle is: a container reached from within itself. No
    depth bound tells that from a structure that is merely deep, and no
    bound on a *reply* helps -- these are the caller's own objects.
    """
    if depth > _MAX_PARAMS_DEPTH:
        err_msg = f"rpc params nested deeper than the {_MAX_PARAMS_DEPTH} allowed"
        raise BtcRpcValueError(err_msg)
    if _json_scalar(value):
        return
    if isinstance(value, Mapping):
        _assert_no_cycle(value, enclosing)
        for name, item in value.items():
            if not isinstance(name, str):
                raise BtcRpcTypeError(f"non-string rpc parameter name: {name!r}")
            _assert_json_params(item, depth + 1, (*enclosing, id(value)))
        return
    if isinstance(value, Sequence):
        _assert_no_cycle(value, enclosing)
        for item in value:
            _assert_json_params(item, depth + 1, (*enclosing, id(value)))
        return
    raise BtcRpcTypeError(f"rpc parameter that is not a json value: {value!r}")


def _json_scalar(value: Any) -> bool:
    """Say whether a value is a json scalar, refusing three that look like one.

    A Decimal, a non-finite float and a `bytes` are each a value a caller
    has a reason to pass and json has no rendering for, so each is refused
    where what to pass instead can be named -- rather than reported as
    "not a json value" from the end of the walk, or, for the `bytes`,
    walked as the list of the ints of its octets.
    """
    if isinstance(value, Decimal):
        err_msg = "Decimal rpc parameter: json carries no exact decimal, so"
        err_msg += " pass what the method documents -- an int of satoshis,"
        err_msg += " or the string it accepts -- rather than a rounded float"
        raise BtcRpcTypeError(err_msg)
    if isinstance(value, float) and not isfinite(value):
        raise BtcRpcValueError(f"not a json number in the rpc params: {value}")
    if isinstance(value, (bytes, bytearray)):
        raise BtcRpcTypeError(f"rpc parameter that is not a json value: {value!r}")
    return value is None or isinstance(value, (bool, int, float, str))


def _assert_no_cycle(value: Any, enclosing: tuple[int, ...]) -> None:
    """Refuse a container reached from inside itself, by the ids it is in."""
    if id(value) in enclosing:
        raise BtcRpcValueError("rpc params contains itself, so it has no json")


def _refuse_param(value: Any) -> Any:
    """Refuse a parameter the walk before the encoder did not anticipate.

    The backstop, and every type it can be reached with today is one
    `_assert_json_params` refuses first. What keeps it here is that
    `json.dumps` calling this is the alternative to a TypeError from
    inside the encoder: an object that is a `Sequence` of json values and
    still has no json -- `range(3)` is one -- passes the walk and arrives
    here.
    """
    raise BtcRpcTypeError(f"rpc parameter that is not a json value: {value!r}")


def _json_number(token: str) -> Decimal:
    """Return the Decimal a json number is, having refused a non-finite one.

    `Decimal(token)` is built in whatever decimal context the *caller* is
    running under, and that context decides whether an exponent the
    implementation cannot represent raises or is answered quietly: with
    `InvalidOperation` untrapped -- `ctx.traps[InvalidOperation] = False`,
    which a program doing its own arithmetic has reason to want --
    `1e999999999999999999999999999` comes back as `Decimal("NaN")`, an
    amount that compares false against itself for the rest of its life,
    arriving past the refusal of NaN this module states and raising nothing
    for the `DecimalException` normalization to catch. So the value is
    checked rather than the exception waited for.

    Size is deliberately not the question: a finite number is an answer
    however large, which is what lets pypy's decimal build exponents
    libmpdec declines to.
    """
    number = Decimal(token)
    if not number.is_finite():
        raise FetchError(f"not a json number in the reply: {token}")
    return number


def _refuse_constant(name: str) -> Any:
    """Refuse the three non-numbers Python's json decodes by default.

    `NaN`, `Infinity` and `-Infinity` are what Python writes and reads
    for floats json has no numbers for. A node does not send them; a
    proxy or a stub in the way can, and a nan arriving as an amount
    compares false against itself for the rest of its life.
    """
    raise FetchError(f"not a json number in the reply: {name}")


def _http_error(where: str, status: int) -> HttpError:
    """Turn a status that is itself the failure into the exception for it."""
    if status == 401:
        message = f"{where}: HTTP 401, the node refused the credentials"
        return HttpError(message, status)
    return HttpError(f"{where}: HTTP {status}", status)


def _id_error(where: str, request_id: str, reply: Mapping[str, Any]) -> FetchError:
    """Say that a reply answers some request other than this one."""
    err_msg = f"{where}: reply id {reply.get('id')!r}"
    err_msg += f" is not the {request_id!r} asked for"
    return FetchError(err_msg)


def _rpc_error(where: str, error: Any) -> FetchError:
    """Turn what the node put in `error` into the exception for it.

    An error object is a code that is an integer and a message that is a
    string; a caller acts on the first and reads the second, so neither is
    something to render whatever arrived. A missing message would become
    an empty one and a list would be formatted into the exception, both of
    which report the node as having said something it did not.
    """
    if not isinstance(error, Mapping):
        return FetchError(f"{where}: unreadable rpc error {error!r}")
    # Any, both of them: every value of a reply is whatever the backend
    # put there, which is what the two checks below are for
    code: Any = error.get("code")
    message: Any = error.get("message")
    if not _is_integer(code) or not isinstance(message, str):
        return FetchError(f"{where}: unreadable rpc error {error!r}")
    return RpcError(f"{where}: {message}", code, error.get("data"))


def _unreadable(where: str, cause: Exception) -> FetchError:
    """Say what shape a body was, for the 200 where the status says nothing.

    Each shape gets its own sentence, being a different thing to go and
    look at: not utf-8, nested past the interpreter's stack, not json.
    Anything else -- a json integer longer than
    `sys.get_int_max_str_digits` allows, a number whose exponent the
    decimal module refuses to build, and whatever a later Python adds --
    is the parser refusing the reply, which is what happened.

    Only for a 200. Under any other status the shape is not the answer:
    see `_reply_object`, which reaches this only after ruling that out.
    """
    if isinstance(cause, UnicodeDecodeError):
        return FetchError(f"{where}: a reply that is not utf-8 ({cause})")
    if isinstance(cause, RecursionError):
        return FetchError(f"{where}: a reply nested too deeply to parse")
    if isinstance(cause, json.JSONDecodeError):
        return FetchError(f"{where}: not json ({cause})")
    return FetchError(f"{where}: a reply the json parser refused ({cause})")


def _parsed_json_body(where: str, status: int, payload: bytes) -> Any:
    """Return the json value a reply's body decodes to, whatever shape it is.

    The parsing half of `_reply_object`, split out so `_batch_reply_array`
    and `call_raw` share it rather than repeating it: every caller reads
    the body the same way this far -- the same `Decimal` numbers, the
    same three refused constants, the same non-200 outranking a body that
    will not parse -- and what differs is whether anything is asked of
    the shape once parsing succeeds, which is each caller's own question
    and not this function's. `call_raw` asks nothing of it at all: the
    envelope is the caller's own question there, an object, an array or a
    bare scalar alike.

    One rule for every body that is not readable json, whichever way it
    is not: none of them can be a *correlated* answer, so on a non-200
    what is left to report is the status -- the 401 with the empty body
    Core sends, or a 503 whose body is whatever stands in front of the
    node. Reporting the encoding of an error page would name the symptom
    and hide the cause.

    The status cannot be consulted before this, which is why the rule
    lives here and not at the top of `_result`: a 1.1 error object
    arriving with an HTTP 500 *is* a reply -- `_legacy_result` says what
    giving up on the status first would cost.
    """
    try:
        return json.loads(
            payload, parse_float=_json_number, parse_constant=_refuse_constant
        )
    except FetchError as e:
        # one of this module's own two refusals of a number: the three
        # non-numbers Python decodes by default, through `_refuse_constant`,
        # or a `Decimal` that came back non-finite because the caller's
        # context does not trap that, through `_json_number`. Each names
        # what it saw, so under a 200 it is re-raised as it stands -- `raise
        # _unreadable(...) from e` would hand back this very object and make
        # the exception its own `__cause__`, which anything walking that
        # chain follows in a loop
        if status == 200:
            raise
        raise _http_error(where, status) from e
    except (ValueError, RecursionError, DecimalException) as e:
        # the rest of the ways a parse fails: JSONDecodeError and
        # UnicodeDecodeError are both ValueError, the bare ValueError of
        # the integer digit limit is a third, and json recurses.
        # `DecimalException` is none of those and is the price of
        # `parse_float=Decimal`: `1e999999999999999999999999999` is a json
        # number this parser will not build, an `InvalidOperation` out of
        # the decimal module, and an ArithmeticError rather than a
        # ValueError -- so it escaped a promise this module makes about
        # every unreadable reply
        if status != 200:
            raise _http_error(where, status) from e
        raise _unreadable(where, e) from e


def _reply_object(where: str, status: int, payload: bytes) -> Mapping[str, Any]:
    """Return the json object a reply is, or say what arrived instead.

    `_parsed_json_body` is the parsing, shared with `_batch_reply_array`;
    what is this function's own is the shape a *lone* call's reply has to
    be -- an array, a string or a number is no more a json-rpc answer
    than a page of html is, so a 503 whose body is `[1, 2, 3]` is a 503.
    """
    reply = _parsed_json_body(where, status, payload)
    if not isinstance(reply, dict):
        if status != 200:
            raise _http_error(where, status)
        raise FetchError(f"{where}: not a json-rpc reply, but a {type(reply).__name__}")
    return reply


def _batch_reply_array(where: str, status: int, payload: bytes) -> Sequence[Any]:
    """Return the json array a batch reply is, or say what arrived instead.

    `_reply_object`'s own check, widened for the one place a top-level
    array is the answer instead of one object: a batch reply is an array
    of the same reply objects a lone call's is, so what is shared is
    `_parsed_json_body`'s safe reading, and what differs is only the
    container `isinstance` demands of it.

    `call_batch` calls this only once it has already ruled out a non-200
    status, unlike `_reply_object`, which is reached before that question
    is settled -- so there is no second status check here, a body that
    parses to something other than an array being this function's own
    refusal to make in every case that reaches it.
    """
    reply = _parsed_json_body(where, status, payload)
    if not isinstance(reply, list):
        err_msg = f"{where}: not a json-rpc batch reply, but a {type(reply).__name__}"
        raise FetchError(err_msg)
    return reply


def _discriminate(
    where: str, request_id: str, status: int, reply: Mapping[str, Any]
) -> Any:
    """Return a reply object's `result`, 1.1 and 2.0 read the same way.

    The version-reading half of `_result`, kept apart from `_reply_object`
    so `call_batch` can reuse exactly this for each member of a batch
    reply: which of `_legacy_result` and `_v2_result` applies is the
    `jsonrpc` member's presence, and that question does not care whether
    `reply` came from a lone call's own body or from one element of a
    batch's array -- there is no second version check to write for it.
    """
    if "jsonrpc" not in reply:
        # the member and not its value: `"jsonrpc": null` is a reply
        # that names no protocol, which is not the same thing as a
        # 1.1 reply, and it is the member's absence that means 1.1
        return _legacy_result(where, request_id, status, reply)
    marker = reply["jsonrpc"]
    if marker != "2.0":
        # a version this module does not read, so the object is no
        # answer -- and under a non-200 the status is what is left to
        # report, as it is for a body that would not parse at all. A
        # `"jsonrpc": "1.0"` beside a 503 is a 503, and losing that
        # would cost the caller the policy `HttpError.status` is for
        if status != 200:
            raise _http_error(where, status)
        err_msg = f"{where}: json-rpc version {marker!r}, neither 2.0"
        err_msg += " nor the legacy reply that carries no version at all"
        raise FetchError(err_msg)
    return _v2_result(where, request_id, status, reply)


def _legacy_result(
    where: str, request_id: str, status: int, reply: Mapping[str, Any]
) -> Any:
    """Return the `result` of a reply carrying no version marker.

    Core's legacy JSON-RPC 1.1: what a node answers to a request without
    the 2.0 marker, and what v27 and older answer to every request.
    `result` and `error` are both present, one of them null, and an rpc
    error arrives with an HTTP 500 -- so the error is read before the
    status, or every "no such transaction" from an old node would be
    reported as a server fault.

    Before the status, but not before the id. A 500 from something in the
    way, carrying an error object of its own or another call's, is a
    failure of the HTTP exchange and not this call's rpc error.

    And not before the status either when the `error` member is no error
    object: `{"id": ours, "error": "bad"}` under a 503 is a correlated
    something, but nothing the node computed -- so what is left to report is
    the status, which is the thing a caller has a policy for. Only a
    readable error object outranks it.
    """
    ours = reply.get("id") == request_id
    error = reply.get("error")
    if ours and error is not None:
        rpc_error = _rpc_error(where, error)
        if isinstance(rpc_error, RpcError) or status == 200:
            raise rpc_error
        raise _http_error(where, status) from rpc_error
    if status != 200:
        raise _http_error(where, status)
    if not ours:
        raise _id_error(where, request_id, reply)
    if "result" not in reply:
        raise FetchError(f"{where}: a reply with neither result nor error")
    return reply["result"]


def _v2_result(
    where: str, request_id: str, status: int, reply: Mapping[str, Any]
) -> Any:
    """Return the `result` of a JSON-RPC 2.0 reply.

    The status is read first, and that is the whole gain of asking for
    2.0: a non-200 is a failure of the HTTP exchange and never an rpc
    error, Core answering 200 with an `error` member for those. So a 401
    from the node, a 403 from something in front of it and a 503 from a
    full work queue cannot be reported as anything the node computed,
    however json-shaped the body beside them is.

    Then exactly one of `result` and `error`, which is 2.0's own rule and
    what tells a 2.0 reply from a 1.1 one wearing the marker. Which member
    is *present*, and not which is non-null: `"error": null` beside a
    result is the 1.1 shape, and a reply that is 1.1 under a 2.0 marker is
    one whose errors this function would look for in the wrong place.
    """
    if status != 200:
        raise _http_error(where, status)
    if reply.get("id") != request_id:
        raise _id_error(where, request_id, reply)
    has_result = "result" in reply
    has_error = "error" in reply
    if has_result == has_error:
        both = "both result and error" if has_result else "neither result nor error"
        raise FetchError(f"{where}: a 2.0 reply with {both}")
    if has_error:
        raise _rpc_error(where, reply["error"])
    return reply["result"]


def _batch_member_request(
    index: int, method: Any, params: Any, request_id: str
) -> dict[str, Any]:
    """Return one batch member's request object, refusing what `call` would.

    Built exactly as `call` builds a lone request -- the 2.0 marker, this
    member's own id, the same params validation, through the same
    `_params_member` and `_assert_json_params` -- with `index` named in
    whatever this refuses, since a caller building `calls` from its own
    data needs to know which entry is wrong rather than that entry number
    `n` of an unindexed list is.
    """
    where = f"call_batch member {index}"
    if not isinstance(method, str):
        raise BtcRpcTypeError(f"{where}: rpc method that is not a string: {method!r}")
    try:
        params_member = _params_member(params)
        _assert_json_params(params_member)
    except BtcRpcTypeError as e:
        raise BtcRpcTypeError(f"{where}: {e}") from e
    except BtcRpcValueError as e:
        raise BtcRpcValueError(f"{where}: {e}") from e
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params_member,
    }


def _correlated_batch_replies(
    where: str, request_ids: Sequence[str], replies: Sequence[Any]
) -> dict[Any, Mapping[str, Any]]:
    """Return each batch reply keyed by the id of the member it answers.

    JSON-RPC 2.0 section 6 lets a batch answer in any order, matched by
    `id` alone, so a reply's position in the array is not what tells one
    member's answer from another's -- `call_batch` looks each one up by
    id rather than trusting the order Core happened to send them in.

    Every failure here is the whole exchange's, as `call_batch`'s own
    docstring promises: a reply that is not itself a json object cannot
    be attributed to any member, so it is not one member's failure to
    report; two replies sharing an id or one answering an id nobody sent
    are a node that did not read the batch it was sent; and a request
    with no reply among them is `len(replies)` disagreeing with the
    batch that was sent, whatever the count says.
    """
    if len(replies) != len(request_ids):
        err_msg = f"{where}: {len(replies)} replies for {len(request_ids)} requests"
        raise FetchError(err_msg)
    by_id: dict[Any, Mapping[str, Any]] = {}
    for reply in replies:
        if not isinstance(reply, Mapping):
            err_msg = f"{where}: a batch reply member that is not a json"
            err_msg += f" object, but a {type(reply).__name__}"
            raise FetchError(err_msg)
        reply_id = reply.get("id")
        if reply_id in by_id:
            err_msg = f"{where}: two replies answering the same id {reply_id!r}"
            raise FetchError(err_msg)
        by_id[reply_id] = reply
    sent_ids = set(request_ids)
    unsent = [reply_id for reply_id in by_id if reply_id not in sent_ids]
    if unsent:
        err_msg = f"{where}: a reply answering id {unsent[0]!r}, which nobody sent"
        raise FetchError(err_msg)
    # every reply's id is distinct (checked above) and sent (checked just
    # above this), and there are as many replies as requests (checked at
    # the top): a set of N distinct members of a set of N is that set, so
    # every request's id is a key of `by_id` by construction and no
    # further check names one that is not
    return by_id


class BitcoinCoreRpcClient:
    """One Bitcoin Core JSON-RPC endpoint, and the credentials to reach it.

    Not a dataclass, and that is about the password: a generated
    `__repr__` prints every field, so the credential would appear in any
    traceback or log line that renders the client.

    Credentials or a cookie path, and not both: each of the two says who
    is calling, so a client given both would have to rank them, and a
    caller who passed both has a mistaken idea of which one is in use.
    `from_chain` is the constructor that fills in a cookie path, along
    with the port, from Core's own defaults.

    **Concurrent calls are supported while the configuration is not
    mutated.** `call` writes nothing on the client, opens its own
    connection and takes its request id from no shared counter, so one
    client serves any number of threads. What is not promised is a client
    whose url, credentials or transport are reassigned while a call is in
    flight, or a caller's transport that is not itself thread-safe --
    that one is the transport's own contract.

    **Basic authentication is cleartext over plain HTTP**, that being
    what Core's rpc speaks. On loopback, which is what `from_chain`
    builds, the cleartext is between one process and the node beside it.
    For a node anywhere else it is on the wire, and rpc credentials
    authorise every wallet command that node has: an `https` url, or a
    tunnel, is what keeps them off it.

    **One connection per call by default**, urllib holding none open:
    every `call` sends `Connection: close` and opens a socket of its own.
    Beside the node that is a loopback connect, which costs nothing for
    one call and is socket churn for a great many -- RFC 9112 section 9.6
    has the server initiating the close on that option, so it is the node
    that holds the sockets in TIME_WAIT -- and to a node reached over
    `https` it is a TLS handshake each time. `SessionTransport` is this
    module's own alternative, one connection kept per `(scheme, host,
    port)` and reused across calls; passing it as `transport=` is what a
    caller polling one node in a loop wants, ahead of a `requests` session
    or an `httpx` client.

    No call asks the node which chain it is on: the url and the cookie path
    say where to ask, and what the answers mean is the caller's to hold.
    `getblockchaininfo` is the question, its `chain` member the answer, and
    `network_from_chain` the vocabulary to read it in -- worth the one
    round trip, because a client built for a testnet node under code that
    believes it is on mainnet fails silently. `from_chain`'s `verify_chain`
    makes exactly that call once, at construction.
    """

    def __init__(
        self,
        url: str,
        *,
        user: str | None = None,
        password: str | None = None,
        cookie_path: str | PathLike[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport: HttpTransport = urlopen_transport,
    ) -> None:
        self.url = _checked_url(url)
        if (user is None) != (password is None):
            raise BtcRpcValueError("rpc user and password go together, or neither")
        if user is not None and cookie_path is not None:
            err_msg = "both rpc credentials and a cookie path:"
            err_msg += " either of them says who is calling, so pass one"
            raise BtcRpcValueError(err_msg)
        if user is None and cookie_path is None:
            err_msg = "no rpc credentials: pass user and password, or the"
            err_msg += " path of the cookie file the node writes"
            raise BtcRpcValueError(err_msg)
        for name, value in (("user", user), ("password", password)):
            if value is not None and not isinstance(value, str):
                # the annotation is not a check, and neither half of the
                # credential survives being something else: a `bytes` or an
                # `int` user made the colon test below raise a bare TypeError
                # from underneath the library, and a list passed it and was
                # formatted into the credential -- `['alice']:secret` reaching
                # the node as a username nobody wrote.
                #
                # The type and not the value: a rejected `password` is a
                # credential, and putting it in an exception writes it into
                # every traceback that renders one -- the same reason this
                # class has no generated `__repr__`. The type is what a
                # caller needs to see, `bytes` being the mistake this
                # catches most often.
                #
                # Unreachable under `user: str | None` and `password: str
                # | None` above, which is not a promise a caller that
                # skips type checking keeps
                err_msg = f"non-string rpc {name}: {type(value).__name__}"  # type: ignore[unreachable]
                raise BtcRpcTypeError(err_msg)
        if user is not None and ":" in user:
            # the Basic credential is `user:password`, and Core splits it at
            # the *first* colon -- `RPCAuthorized` in src/httprpc.cpp. So a
            # user of `alice:admin` reaches the node as the user `alice`,
            # whose credential begins `admin:`: a different rpc user, a
            # different `-rpcwhitelist` and no error anywhere, the two
            # spellings encoding to the same header so that nothing
            # downstream can tell them apart. A colon on the other side is
            # unambiguous and stays valid, everything after the first one
            # belonging to the second field by definition.
            #
            # The user is not quoted back: the string being refused has a
            # colon in it, so the likeliest thing it holds is `user:password`
            # written into the first argument -- a credential, and one that
            # would go into the traceback with it. `_checked_url` refuses a
            # url with userinfo in it without echoing the url either
            err_msg = "colon in the rpc user. The credential is user:password"
            err_msg += " and the node splits it at the first colon, so a user"
            err_msg += " containing one names a different user than intended"
            raise BtcRpcValueError(err_msg)
        _assert_valid_timeout(timeout, "rpc timeout")
        if cookie_path is not None and not isinstance(cookie_path, (str, PathLike)):
            # what `Path()` on the next line takes, asked before it is asked
            # there: an int reaches it and leaves through a bare TypeError
            # about `__fspath__`, which names pathlib rather than the
            # argument this class was given.
            #
            # Unreachable under `cookie_path: str | PathLike[str] | None`
            # above, which is not a promise a caller that skips type
            # checking keeps
            err_msg = f"rpc cookie_path that is no path: {type(cookie_path).__name__}"  # type: ignore[unreachable]
            raise BtcRpcTypeError(err_msg)
        if not callable(transport):
            # configuration checked while the caller is still looking at the
            # line that supplied it -- `_checked_url` says why -- and a
            # transport is the one argument where not doing so is a failure
            # at the first `call` instead, out of urllib rather than here.
            #
            # Unreachable under `transport: HttpTransport` above, which is
            # not a promise a caller that skips type checking keeps
            err_msg = f"rpc transport that is not callable: {type(transport).__name__}"  # type: ignore[unreachable]
            raise BtcRpcTypeError(err_msg)
        self.user = user
        self._password = password
        self.cookie_path = None if cookie_path is None else Path(cookie_path)
        self.timeout = timeout
        self.transport = transport

    @classmethod
    def from_chain(
        cls,
        chain: str = "main",
        *,
        user: str | None = None,
        password: str | None = None,
        cookie_path: str | PathLike[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport: HttpTransport = urlopen_transport,
        verify_chain: bool = False,
        signet_challenge: str | bytes | bytearray | None = None,
    ) -> BitcoinCoreRpcClient:
        """Return a client for the local node of one of Core's chains.

        The convenience of not writing out a loopback url, a port and a
        datadir: all three come from Core's own tables, and everything
        else is the constructor's. `chain` is spelled as Core spells it, so
        `main` where BIP32 and BIP173 say `mainnet`; `chain_from_network`
        translates for a caller holding a BIP name, and a chain Core has no
        default port for is an explicit url with a `cookie_path`, which is
        the constructor.

        It asks the node nothing, so it is no claim that one is listening
        on that port, nor that it serves this chain if it is. The first
        `call` is what finds out -- unless `verify_chain` says to ask now,
        which is `assert_chain` and its docstring for what that settles.

        Off by default, because a cookie authenticates only that the node
        is the one this call was told about -- a file only that node could
        have written -- and says nothing about which chain it is running:
        `-chain=test` and a `main` cookie both exist. A caller for whom
        that gap matters -- a cookie path or a datadir carried over from a
        differently-configured host, an environment variable naming the
        wrong chain -- opts in and gets `BtcRpcValueError` naming both
        chains instead of a wrong-network call succeeding silently, at the
        cost of one round trip here rather than trust in every call after.

        `signet_challenge` is the signet the caller means, and is what
        `assert_chain` compares by: without it, `signet` means the default
        signet and a node on any other is refused. It is the one argument
        here that does nothing to the client built -- every signet answers
        on 38332 and keeps its cookie in the same subdirectory -- so it is
        refused rather than ignored when `verify_chain` is off, that being
        a caller expecting a check that would not be made.

        The datadir comes from `default_datadir` at this call, which is
        Core's own for the platform underneath; where there is no absolute
        directory to hang it off, deriving a cookie path is what this
        refuses -- naming `cookie_path` as the answer.

        Nothing is derived when the caller said who is calling: a `user` or
        a `password`, either of them, is an answer to that question, and
        the constructor is where the two are held to going together. A
        cookie derived before that check would report a missing home
        directory to a caller who passed a password and forgot the user.
        """
        port = rpc_port_from_chain(chain)
        if signet_challenge is not None and not verify_chain:
            err_msg = "a signet_challenge is what verify_chain compares,"
            err_msg += " and checks nothing with it off"
            raise BtcRpcValueError(err_msg)
        if user is None and password is None and cookie_path is None:
            # the datadir is resolved here, rather than left to
            # `cookie_path_from_chain`'s own default, because the remedy
            # differs: that function names `datadir`, which this
            # constructor does not take, where what a caller of this one
            # passes instead is a `cookie_path`, or credentials
            datadir = default_datadir()
            if datadir is None:
                err_msg = "no absolute home directory (APPDATA on Windows),"
                err_msg += " so no default datadir to find the cookie file"
                err_msg += " in: pass cookie_path, or user and password"
                raise BtcRpcValueError(err_msg)
            cookie_path = cookie_path_from_chain(chain, datadir)
        client = cls(
            f"http://127.0.0.1:{port}",
            user=user,
            password=password,
            cookie_path=cookie_path,
            timeout=timeout,
            transport=transport,
        )
        if verify_chain:
            client.assert_chain(chain, signet_challenge=signet_challenge)
        return client

    def assert_chain(
        self,
        chain: str = "main",
        *,
        signet_challenge: str | bytes | bytearray | None = None,
    ) -> None:
        """Raise unless the node serves this chain, and this signet of it.

        One round trip, `getblockchaininfo`, and the answer cannot change
        under a client that goes on pointing at the same node -- so this is
        a question asked at a moment of the caller's choosing: at startup,
        after a client was repointed, or by `from_chain(verify_chain=True)`,
        which is this method.

        Worth asking, because the failure it catches is silent. Nothing in
        an rpc exchange says which chain is behind it: a cookie
        authenticates the node that wrote it and not what that node is
        running, so a url, a datadir or an environment variable carried
        over from another host answers every call and answers about the
        wrong chain.

        Signet is the case a name cannot settle. Core reports `signet` for
        the default signet and for every custom one alike, so two nodes
        sharing nothing but the shape of a challenge answer the same
        string; the challenge is what tells them apart, and the p2p magic
        it derives is what this compares -- `magic_from_signet_challenge`
        of what the node reports, against the caller's `signet_challenge`
        or, with none, `magic_from_chain("signet")`. Comparing the derived
        magic rather than the challenge text is what makes a challenge
        written in upper case the same challenge.

        A challenge off signet is refused before the reply is read: a
        caller passing one has a signet in mind and this client is on no
        signet at all, which is the caller's configuration either way.

        `BtcRpcValueError` for a disagreement, the node being the authority
        on what it serves and the client's label therefore the thing to
        fix. `FetchError` for a reply with nothing to compare -- a result
        that is not a mapping, a `chain` that is not a string, a signet
        answering without a `signet_challenge` member -- this being an
        interpretation of an untrusted reply like any other.
        """
        expected_magic: bytes | None = None
        if signet_challenge is None:
            if chain == "signet":
                expected_magic = magic_from_chain(chain)
        elif chain != "signet":
            err_msg = f"a signet_challenge for chain {chain!r}, which is no signet"
            raise BtcRpcValueError(err_msg)
        else:
            expected_magic = magic_from_signet_challenge(signet_challenge)

        result = self.call("getblockchaininfo")
        # the shape of the result is the node's and not a given, so it is
        # read rather than indexed: `result["chain"]` on an array is a
        # TypeError about list indices and on a mapping without the member a
        # KeyError, both from underneath a library that reports every other
        # unreadable answer as a FetchError. A mismatch stays a
        # BtcRpcValueError below: that one is a node this client was built
        # for the wrong chain of, which is the caller's configuration, where
        # this is the backend's reply
        info: Mapping[str, Any] = result if isinstance(result, Mapping) else {}
        reported = info.get("chain")
        if not isinstance(reported, str):
            err_msg = f"getblockchaininfo at {self.url}: no string"
            err_msg += f" chain in the {type(result).__name__} result"
            raise FetchError(err_msg)
        if reported != chain:
            err_msg = f"node at {self.url} reports chain {reported!r},"
            err_msg += f" not the {chain!r} this client was built for"
            raise BtcRpcValueError(err_msg)
        if expected_magic is None:
            return

        # `signet_challenge` is a member of the reply on signet alone, and
        # of every signet's: a node too old to report it is one this cannot
        # answer for, which is the FetchError and not a pass
        challenge = info.get("signet_challenge")
        if not isinstance(challenge, str):
            err_msg = f"getblockchaininfo at {self.url}: no string"
            err_msg += " signet_challenge in the reply of a node on signet"
            raise FetchError(err_msg)
        try:
            node_magic = magic_from_signet_challenge(challenge)
        except ValueError as e:
            # `BtcRpcValueError` is a ValueError, so this one clause covers
            # a challenge that is not hex and one no node would have taken:
            # either way it is the reply that cannot be read, and not the
            # disagreement below
            err_msg = f"getblockchaininfo at {self.url}:"
            err_msg += f" unreadable signet_challenge: {e}"
            raise FetchError(err_msg) from e
        if node_magic != expected_magic:
            err_msg = f"node at {self.url} is on a signet this client is not:"
            err_msg += f" its challenge derives magic {node_magic.hex()},"
            err_msg += f" where {expected_magic.hex()} was expected"
            raise BtcRpcValueError(err_msg)

    def for_wallet(self, wallet_name: str) -> BitcoinCoreRpcClient:
        """Return a client for this node's `/wallet/<name>` endpoint.

        Which is how a node with several wallets loaded is told which one
        a wallet command is about. The name is percent-encoded, a wallet
        being a directory and free to be called anything a filesystem
        accepts: a space, a `#` or a `/` written into the path unencoded
        addresses a different endpoint, or none.

        The credentials, the timeout and the transport are this client's,
        the endpoint being the only difference -- so a caller working on
        several wallets builds one client and derives the rest, each from
        that one client and not from another wallet's: a client that is
        already a wallet endpoint is one this refuses to extend, naming the
        client to call it on.

        `type(self)` and not this class by name, as `from_chain` builds
        with `cls`: a subclass that derives a wallet client keeps whatever
        it added.
        """
        if not isinstance(wallet_name, str):
            # `quote` takes `bytes` as well, so this is a refusal and not a
            # convenience: `for_wallet(b"hot")` built an endpoint rather
            # than failing, and anything else left through a TypeError of
            # urllib's about `quote_from_bytes`.
            #
            # Unreachable under `wallet_name: str` above, which is not a
            # promise a caller that skips type checking keeps
            err_msg = f"rpc wallet name that is not a string: {wallet_name!r}"  # type: ignore[unreachable]
            raise BtcRpcTypeError(err_msg)
        # a wallet endpoint takes no second one. `/wallet/hot/wallet/cold`
        # is not a path Core serves, so composing the two fails at the node
        # with an HttpError about a path, where every other wrong argument
        # to this class is refused while the caller is still looking at the
        # line that supplied it -- `_checked_url` refuses a query or a
        # fragment for that reason, and the name above is checked for it.
        # The mistake belongs to the arrangement this method recommends,
        # one client per wallet: deriving the second wallet's client from
        # the first, rather than from the client both came from.
        #
        # Refused rather than repaired. Replacing the trailing segment
        # would make `for_wallet("hot")` and
        # `for_wallet("hot").for_wallet("cold")` two spellings of one
        # endpoint, and nothing tells a caller who meant the second from
        # one who lost track of which client they were holding.
        #
        # The last two segments of the path, with a trailing slash not
        # counting as one: what that admits is a wallet *named* `wallet`,
        # which a filesystem allows and which this builds `/wallet/wallet`
        # for, since the segment is then the name rather than the marker
        # before it. A url a caller wrote by hand ending in `/wallet/hot`
        # is refused by the same check, and correctly: the constructor
        # takes the endpoint of a node, and the wallet is what this adds
        if "wallet" in urlsplit(self.url).path.rstrip("/").split("/")[-2:]:
            err_msg = "this client is already the /wallet/<name> endpoint of"
            err_msg += " a node: call for_wallet on the client it was derived"
            err_msg += " from"
            raise BtcRpcValueError(err_msg)
        url = f"{self.url.rstrip('/')}/wallet/{quote(wallet_name, safe='')}"
        return type(self)(
            url,
            user=self.user,
            password=self._password,
            cookie_path=self.cookie_path,
            timeout=self.timeout,
            transport=self.transport,
        )

    def auth_header(self) -> str:
        """Return the Basic credential, from the arguments or the cookie.

        RFC 7617 leaves the charset of the credential unspecified and
        Core compares the decoded bytes, so utf-8 is a choice that only
        matters for a password with a non-ascii character in it -- where
        it is the choice that matches what a shell and a config file
        would have written.
        """
        if self.cookie_path is not None:
            credential = cookie_auth(self.cookie_path)
        else:
            credential = f"{self.user}:{self._password}"
        return "Basic " + b64encode(credential.encode()).decode("ascii")

    def call(
        self,
        method: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
        *,
        request_timeout: float | None = None,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    ) -> Any:
        """Invoke one rpc method, returning its `result`.

        `params` is one value, shaped as json-rpc shapes it: a sequence
        for the positional form, a mapping for the named one. The
        client's own controls are keyword-only for that reason --
        `timeout` is a parameter of several Core methods, and a signature
        mixing the two would have to decide which of them owns the name.

        Amounts do not travel as binary floating point in either
        direction: a number in the reply decodes as a Decimal, and a
        Decimal parameter is refused rather than rounded through `float`.
        `NaN` and `Infinity` are refused both ways, being what Python
        writes for floats json has no numbers for.

        `request_timeout` is this call's, defaulting to the client's, and
        for the default transport it bounds the whole exchange -- the
        node's thinking and the reply's arrival together. What it is for
        is the methods that legitimately run long
        -- `rescanblockchain`, `scantxoutset`, `dumptxoutset` -- and the
        replies large enough to take a while on the wire; the alternative
        is a second client whose wider timeout applies to everything.

        `max_body_size` is what the reply may weigh: widen it for the
        answers larger than the default, which `DEFAULT_MAX_BODY_SIZE`
        names, and tighten it where the reply is a number, this being the
        caller's node and the caller's memory.

        There is no retry: one call is one HTTP request, whatever comes
        back. `HttpError.status` is what a caller's own policy reads, and
        this module's docstring says why the policy is theirs.
        """
        request_id = _rpc_id()
        if not isinstance(method, str):
            # json-rpc's `method` is a string, and the annotation is not a
            # check: `call(7)` otherwise built `"method": 7` and sent it,
            # which is this client constructing an invalid request while it
            # walks the caller's params for exactly that reason. An unknown
            # method is a value the node answers for -- that is the point of
            # taking it as an argument -- and a number is not one
            raise BtcRpcTypeError(f"rpc method that is not a string: {method!r}")
        timeout = self.timeout if request_timeout is None else request_timeout
        _assert_valid_timeout(timeout, "rpc request_timeout")
        params_member = _params_member(params)
        _assert_json_params(params_member)
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params_member,
        }
        try:
            body = json.dumps(request, allow_nan=False, default=_refuse_param).encode()
        except ValueError as e:
            # an int of more digits than `sys.get_int_max_str_digits`
            # allows, which is the mirror of the limit a *reply* holding
            # one runs into: json has the number and this interpreter will
            # not write it. The walk above refuses the types json has no
            # rendering for, and this is a value of a type it does, so the
            # encoder is where it surfaces
            raise BtcRpcValueError(f"rpc params json cannot carry: {e}") from e
        status, payload = http_request(
            self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": self.auth_header(),
                # the request `id` marks this client in the node's debug
                # log, and `USER_AGENT` is the half a proxy and an access
                # log see
                "User-Agent": USER_AGENT,
            },
            timeout=timeout,
            max_body_size=max_body_size,
            transport=self.transport,
        )
        return self._result(method, request_id, status, payload)

    def _result(self, method: str, request_id: str, status: int, payload: bytes) -> Any:
        where = f"{method} at {self.url}"
        reply = _reply_object(where, status, payload)
        return _discriminate(where, request_id, status, reply)

    def call_batch(
        self,
        calls: Sequence[tuple[str, Sequence[Any] | Mapping[str, Any] | None]],
        *,
        request_timeout: float | None = None,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    ) -> list[Any]:
        """Invoke several rpc methods in one HTTP request.

        `calls` is a sequence of `(method, params)` pairs, one per member,
        `params` shaped exactly as `call`'s own -- a sequence for the
        positional form, a mapping for the named one, `None` for no
        parameters at all. Each member is built the way `call` builds its
        one request: the 2.0 marker, an id of its own from the same
        source `call` draws from, and the same params validation -- a
        member that fails it is refused before anything is sent, naming
        its position in `calls` rather than a position in a request Core
        never sees.

        The answer is a list aligned with `calls` rather than with
        whatever order the array came back in: position i holds member
        i's `result`, or its `RpcError` **as a value** -- a batch partly
        failing is the ordinary case, and raising the first error would
        discard every answer beside it. JSON-RPC 2.0 section 6 lets the
        replies arrive in any order, matched by `id`, and that is how
        this aligns them: never by position in the reply array.

        Only a failure of the *whole* exchange raises, exactly as `call`
        raises -- `HttpError` or `FetchError` for the lot: a non-2xx
        status, a reply that is not an array, a reply that cannot be
        attributed to any member, or a member with no reply among them.
        Each member's own reply, once correlated by id, is read by the
        same `_reply_object`-then-version discrimination `call` reads its
        own with; there is no second parsing branch for a batch's shape.

        `request_timeout` and `max_body_size` are `call`'s own controls,
        and what each bounds changes shape here: this is one HTTP
        exchange that is now N node operations, so `request_timeout`
        bounds all of them together rather than one, and `max_body_size`
        bounds the sum of every member's reply rather than any one of
        them -- widen either the way a single large `call` would ask you
        to, and for the same reason.

        An empty `calls` is refused with `BtcRpcValueError`: JSON-RPC 2.0
        section 6 has no shape for a batch of zero requests, its own rule
        being that the server's answer to an invalid batch is a single
        reply object rather than the array this method promises.
        """
        if not calls:
            err_msg = "call_batch with no members: JSON-RPC 2.0 section 6 has"
            err_msg += " no shape for an empty batch"
            raise BtcRpcValueError(err_msg)
        timeout = self.timeout if request_timeout is None else request_timeout
        _assert_valid_timeout(timeout, "rpc request_timeout")
        request_ids = [_rpc_id() for _ in calls]
        members = [
            _batch_member_request(index, method, params, request_id)
            for index, ((method, params), request_id) in enumerate(
                zip(calls, request_ids, strict=True)
            )
        ]
        try:
            body = json.dumps(members, allow_nan=False, default=_refuse_param).encode()
        except ValueError as e:
            raise BtcRpcValueError(f"rpc params json cannot carry: {e}") from e
        status, payload = http_request(
            self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": self.auth_header(),
                "User-Agent": USER_AGENT,
            },
            timeout=timeout,
            max_body_size=max_body_size,
            transport=self.transport,
        )
        where = f"call_batch at {self.url}"
        # read first, as `_v2_result` reads it for a lone 2.0 call: every
        # member was sent with the 2.0 marker, so a non-2xx here is a
        # failure of the one HTTP exchange behind the whole array and not
        # a shape to attribute to any member's own reply
        if status != 200:
            raise _http_error(where, status)
        replies = _batch_reply_array(where, status, payload)
        by_id = _correlated_batch_replies(where, request_ids, replies)
        results: list[Any] = []
        for index, ((method, _params), request_id) in enumerate(
            zip(calls, request_ids, strict=True)
        ):
            member_where = f"{method} at {self.url} (call_batch member {index})"
            try:
                result = _discriminate(
                    member_where, request_id, status, by_id[request_id]
                )
            except RpcError as e:
                results.append(e)
            else:
                results.append(result)
        return results

    def call_raw(
        self,
        method: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
        *,
        jsonrpc: str | None = "2.0",
        request_timeout: float | None = None,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    ) -> tuple[int, Any]:
        """Send one rpc request and hand back the envelope, unread.

        The same authenticated POST `call` builds -- this url, the
        `Authorization` header, `USER_AGENT`, a fresh id, the same params
        validation -- with the protocol marker itself an argument rather
        than the `"2.0"` `call` always sends: a string is sent verbatim
        as `jsonrpc`, `None` sends no `jsonrpc` member at all, and the
        default is `"2.0"`, `call`'s own.

        The answer is the pair as it arrived: the HTTP status, and
        whatever `_parsed_json_body` safely parses the body into --
        `Decimal` numbers, the three non-number constants refused -- but
        **not interpreted**: no id check, no version discrimination, no
        `RpcError` raised, no `result` extracted, and no shape assumed
        either. A conformant node answers with a json object, but this is
        the seam a caller tests a server's own conformance through, so an
        array, a bare string or number, or `null` comes back exactly as
        parsed rather than being refused the way `call`'s own reply has
        to be -- `_reply_object`'s object-shape gate is a rule about a
        *correlated* answer, which is one interpretation this method does
        not make. What the envelope holds is the caller's own question,
        so the envelope is the answer, read exactly as far as `call`
        reads before it starts asking what the reply *means*.

        Below the status everything stays a `FetchError`, exactly as
        `http_request` promises: a refused connection, an expired
        timeout, a body that is not json at all -- a non-200 status with
        an unparsable body is `HttpError`, precisely as it is for `call`.
        This is a raw *reply*, not raw bytes -- a caller wanting the bytes
        has `http_request` and `auth_header()` already, both public.

        Deliberately out of scope: a request this client refuses to
        build -- a missing `method`, a non-string one, params that are
        neither a sequence nor a mapping. A client constructing an
        invalid request on purpose is a conformance harness's job, and
        `http_request` is the public seam such a harness builds on.
        """
        request_id = _rpc_id()
        if not isinstance(method, str):
            raise BtcRpcTypeError(f"rpc method that is not a string: {method!r}")
        if jsonrpc is not None and not isinstance(jsonrpc, str):
            # unreachable under `jsonrpc: str | None` above, which is not a
            # promise a caller that skips type checking keeps -- the same
            # shape as the constructor's own `cookie_path` check
            err_msg = "call_raw jsonrpc marker that is neither a string nor None:"  # type: ignore[unreachable]
            err_msg += f" {jsonrpc!r}"
            raise BtcRpcTypeError(err_msg)
        timeout = self.timeout if request_timeout is None else request_timeout
        _assert_valid_timeout(timeout, "rpc request_timeout")
        params_member = _params_member(params)
        _assert_json_params(params_member)
        request: dict[str, Any] = {}
        if jsonrpc is not None:
            request["jsonrpc"] = jsonrpc
        request["id"] = request_id
        request["method"] = method
        request["params"] = params_member
        try:
            body = json.dumps(request, allow_nan=False, default=_refuse_param).encode()
        except ValueError as e:
            raise BtcRpcValueError(f"rpc params json cannot carry: {e}") from e
        status, payload = http_request(
            self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": self.auth_header(),
                "User-Agent": USER_AGENT,
            },
            timeout=timeout,
            max_body_size=max_body_size,
            transport=self.transport,
        )
        where = f"{method} at {self.url}"
        return status, _parsed_json_body(where, status, payload)


class RpcChannel:
    """Attribute-style convenience over a client's `call`.

    `channel.getblockcount()` is `client.call("getblockcount")`.
    `channel.getblock(block_hash, 2)` passes the positional form,
    `channel.getblock(blockhash=block_hash, verbosity=2)` the named one
    -- whichever the caller wrote, since json-rpc has one params shape
    per call and not both at once.

    `request_timeout` and `max_body_size`, `call`'s own keyword-only
    controls, are caught by the wrapper and passed to `call` rather than
    travelling to the node as named rpc parameters. That reservation is why
    this class lives here rather than in a caller's own script: it has to
    know which names are `call`'s own, that list is this module's to grow,
    and a copy written against one release is silently wrong against a
    later one that adds a third control -- neither mypy nor a test catches
    a keyword that now reaches Core instead of this class.

    A hand-written guard sits in front of every name starting with `_`,
    dunders included. Without it, `copy.deepcopy`, a pickling path this
    object does not otherwise reach, and an interactive shell probing
    for `_repr_html_` or `_ipython_canary_method_should_not_exist_`
    would each turn into a bound method for an rpc call of that name --
    and calling one is not the same failure as an `AttributeError` a
    caller can catch by name.

    `client`, the one public attribute, is reserved for the same reason:
    it is how a caller reaches the `BitcoinCoreRpcClient` this channel
    wraps, and an rpc method named `client` -- Core has none -- would
    otherwise shadow it.

    Not `BitcoinCoreRpcClient.__getattr__`: that class stays the explicit
    surface `call(method, params)` is, where an unknown attribute is an
    `AttributeError` and `for_walet("hot")` a typo caught at the call
    rather than one more method name sent to the node. This is the
    opt-in beside it, for a caller who has weighed that trade the other
    way for a given script.
    """

    __slots__ = ("client",)

    def __init__(self, client: BitcoinCoreRpcClient) -> None:
        self.client = client

    def __getattr__(self, method: str) -> Callable[..., Any]:
        """Return a bound call to `method`, unless its name starts with `_`."""
        if method.startswith("_"):
            raise AttributeError(method)

        def bound_call(
            *args: Any,
            request_timeout: float | None = None,
            max_body_size: int = DEFAULT_MAX_BODY_SIZE,
            **kwargs: Any,
        ) -> Any:
            if args and kwargs:
                err_msg = f"{method}: positional and named arguments together,"
                err_msg += " json-rpc params being one shape or the other"
                raise BtcRpcValueError(err_msg)
            params: Sequence[Any] | Mapping[str, Any] | None
            params = kwargs or (list(args) if args else None)
            return self.client.call(
                method,
                params,
                request_timeout=request_timeout,
                max_body_size=max_body_size,
            )

        return bound_call
