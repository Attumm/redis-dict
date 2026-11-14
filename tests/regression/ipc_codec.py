"""Independent type-tagged IPC codec and deep exact-type comparator for cross-version workers."""
from __future__ import annotations

import base64
from collections import OrderedDict, defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
import math
from typing import Any, Callable, Dict, Tuple
from uuid import UUID


class CustomerAccount:
    """Custom extendable domain object used across cross-version extends_type tests."""

    def __init__(self, uid: int, name: str) -> None:
        """Initialize a CustomerAccount instance.

        Args:
            uid (int): Numeric customer identifier.
            name (str): Customer display name.
        """
        self.uid = uid
        self.name = name

    def encode(self) -> str:
        """Serialize CustomerAccount to a pipe-delimited string.

        Returns:
            str: Encoded string payload.
        """
        return f"{self.uid}|{self.name}"

    @classmethod
    def decode(cls, raw: str) -> CustomerAccount:
        """Deserialize CustomerAccount from a pipe-delimited string.

        Args:
            raw (str): Encoded string payload.

        Returns:
            CustomerAccount: Decoded CustomerAccount instance.
        """
        uid_str, name = raw.split("|", 1)
        return cls(int(uid_str), name)

    def __eq__(self, other: object) -> bool:
        """Check equality with another object.

        Args:
            other (object): Object to compare against.

        Returns:
            bool: True when both are CustomerAccount instances with identical fields.
        """
        return isinstance(other, CustomerAccount) and self.uid == other.uid and self.name == other.name

    def __hash__(self) -> int:
        """Compute hash so CustomerAccount can be tested inside sets and typed keys.

        Returns:
            int: Hash value.
        """
        return hash((CustomerAccount, self.uid, self.name))

    def __repr__(self) -> str:
        """Format developer representation.

        Returns:
            str: String representation.
        """
        return f"CustomerAccount({self.uid!r}, {self.name!r})"


class Rot13Token(str):
    """Custom str subclass testing extends_type string-subclass isolation."""

    def encode_rot13(self) -> str:
        """Encode string content with hex-UTF8 wrapping so it differs from plain str.

        Returns:
            str: Hex-encoded payload.
        """
        return f"rot13hex:{self.encode('utf-8').hex()}"

    @classmethod
    def decode_rot13(cls, raw: str) -> Rot13Token:
        """Decode a hex-wrapped payload back into a Rot13Token instance.

        Args:
            raw (str): Encoded payload starting with ``rot13hex:``.

        Returns:
            Rot13Token: Reconstructed Rot13Token instance.
        """
        _, hex_body = raw.split(":", 1)
        return cls(bytes.fromhex(hex_body).decode("utf-8"))


def _encode_float(val: float) -> str:
    if math.isnan(val):
        return "nan"
    if math.isinf(val):
        return "inf" if val > 0 else "-inf"
    return val.hex()


def _decode_float(raw: str) -> float:
    if raw in ("nan", "inf", "-inf"):
        return float(raw)
    return float.fromhex(raw)


_SCALAR_ENCODERS: Dict[type, Tuple[str, Callable[[Any], Any]]] = {
    type(None): ("NoneType", lambda _: None),
    bool: ("bool", bool),
    int: ("int", str),
    float: ("float", _encode_float),
    str: ("str", str),
    bytes: ("bytes", lambda b: base64.b64encode(b).decode("ascii")),
    Decimal: ("Decimal", str),
    complex: ("complex", lambda c: [_encode_float(c.real), _encode_float(c.imag)]),
    UUID: ("UUID", str),
    datetime: ("datetime", lambda dt: dt.isoformat()),
    date: ("date", lambda d: d.isoformat()),
    time: ("time", lambda t: t.isoformat()),
    timedelta: ("timedelta", lambda td: [td.days, td.seconds, td.microseconds]),
    CustomerAccount: ("CustomerAccount", lambda acc: [acc.uid, acc.name]),
    Rot13Token: ("Rot13Token", str),
}


def encode_node(value: Any) -> Dict[str, Any]:
    """Encode an arbitrary Python value into an explicit type-tagged dict tree.

    Args:
        value (Any): Python object to encode.

    Raises:
        TypeError: If ``value`` has an unsupported runtime type.

    Returns:
        Dict[str, Any]: JSON-serializable type-tagged AST node.
    """
    exact_type = type(value)
    if exact_type in _SCALAR_ENCODERS:
        tag, fn = _SCALAR_ENCODERS[exact_type]
        return {"t": tag, "v": fn(value)}
    if exact_type is list:
        return {"t": "list", "v": [encode_node(item) for item in value]}
    if exact_type is tuple:
        return {"t": "tuple", "v": [encode_node(item) for item in value]}
    if exact_type in (set, frozenset):
        return {"t": exact_type.__name__, "v": [encode_node(item) for item in value]}
    if exact_type in (dict, OrderedDict, defaultdict):
        return {
            "t": exact_type.__name__,
            "v": [[encode_node(k), encode_node(v)] for k, v in value.items()],
        }
    raise TypeError(f"Unsupported IPC type: {exact_type!r}")


_SCALAR_DECODERS: Dict[str, Callable[[Any], Any]] = {
    "NoneType": lambda _: None,
    "bool": bool,
    "int": int,
    "float": _decode_float,
    "str": str,
    "bytes": lambda s: base64.b64decode(s.encode("ascii")),
    "Decimal": Decimal,
    "complex": lambda pair: complex(_decode_float(pair[0]), _decode_float(pair[1])),
    "UUID": UUID,
    "datetime": datetime.fromisoformat,
    "date": date.fromisoformat,
    "time": time.fromisoformat,
    "timedelta": lambda parts: timedelta(days=parts[0], seconds=parts[1], microseconds=parts[2]),
    "CustomerAccount": lambda parts: CustomerAccount(int(parts[0]), str(parts[1])),
    "Rot13Token": Rot13Token,
}


def decode_node(node: Dict[str, Any]) -> Any:
    """Decode a type-tagged AST node back into an exact Python object.

    Args:
        node (Dict[str, Any]): Type-tagged node produced by ``encode_node``.

    Raises:
        ValueError: If the node tag is unknown.

    Returns:
        Any: Reconstructed Python object with exact runtime types.
    """
    tag = node["t"]
    payload = node["v"]
    if tag in _SCALAR_DECODERS:
        return _SCALAR_DECODERS[tag](payload)
    if tag in ("list", "tuple"):
        seq = [decode_node(item) for item in payload]
        return seq if tag == "list" else tuple(seq)
    if tag in ("set", "frozenset"):
        items = [decode_node(item) for item in payload]
        return set(items) if tag == "set" else frozenset(items)
    if tag in ("dict", "OrderedDict", "defaultdict"):
        pairs = [(decode_node(k), decode_node(v)) for k, v in payload]
        if tag == "OrderedDict":
            return OrderedDict(pairs)
        if tag == "defaultdict":
            return defaultdict(type(None), pairs)
        return dict(pairs)
    raise ValueError(f"Unknown IPC node tag: {tag!r}")


def dumps_ipc(payload: Any) -> str:
    """Serialize an arbitrary object graph to a single-line JSON string for worker IPC.

    Args:
        payload (Any): Object graph to serialize.

    Returns:
        str: Single-line JSON string.
    """
    return json.dumps(encode_node(payload), separators=(",", ":"))


def loads_ipc(line: str) -> Any:
    """Deserialize a single-line JSON IPC frame into exact Python objects.

    Args:
        line (str): Single-line JSON frame produced by ``dumps_ipc``.

    Returns:
        Any: Reconstructed Python object graph.
    """
    return decode_node(json.loads(line))


def _canonical_freeze(value: Any) -> Any:
    """Create a strictly typed hashable signature differentiating ``1`` vs ``True`` vs ``1.0``.

    Args:
        value (Any): Value to convert into a hashable typed tuple.

    Returns:
        Any: Hashable canonical representation encoding exact runtime types.
    """
    exact_type = type(value)
    if exact_type is float and math.isnan(value):
        return (float, "nan")
    if exact_type in (list, tuple):
        return (exact_type, tuple(_canonical_freeze(item) for item in value))
    if exact_type in (set, frozenset):
        return (exact_type, frozenset(_canonical_freeze(item) for item in value))
    if exact_type is OrderedDict:
        return (OrderedDict, tuple((_canonical_freeze(k), _canonical_freeze(v)) for k, v in value.items()))
    if exact_type in (dict, defaultdict):
        return (exact_type, frozenset((_canonical_freeze(k), _canonical_freeze(v)) for k, v in value.items()))
    return (exact_type, value)


def _assert_mapping_deep_equal(actual: Any, expected: Any, path: str) -> None:
    if len(actual) != len(expected):
        raise AssertionError(f"{path}: length {len(actual)} != {len(expected)}")
    if isinstance(expected, OrderedDict):
        for idx, ((act_k, act_v), (exp_k, exp_v)) in enumerate(zip(actual.items(), expected.items())):
            assert_deep_equal_and_typed(act_k, exp_k, f"{path}.order[{idx}].key")
            assert_deep_equal_and_typed(act_v, exp_v, f"{path}.order[{idx}].val")
        return
    exp_by_sig = {_canonical_freeze(k): (k, v) for k, v in expected.items()}
    act_by_sig = {_canonical_freeze(k): (k, v) for k, v in actual.items()}
    if set(act_by_sig.keys()) != set(exp_by_sig.keys()):
        raise AssertionError(f"{path}: typed keys mismatch: {list(actual.keys())!r} != {list(expected.keys())!r}")
    for sig, (_, exp_v) in exp_by_sig.items():
        act_k, act_v = act_by_sig[sig]
        assert_deep_equal_and_typed(act_v, exp_v, f"{path}[{act_k!r}]")


def _assert_sequence_deep_equal(actual: Any, expected: Any, path: str) -> None:
    if len(actual) != len(expected):
        raise AssertionError(f"{path}: sequence length {len(actual)} != {len(expected)}")
    for idx, (act_item, exp_item) in enumerate(zip(actual, expected)):
        assert_deep_equal_and_typed(act_item, exp_item, f"{path}[{idx}]")


def assert_deep_equal_and_typed(actual: Any, expected: Any, path: str = "root") -> None:
    """Recursively assert both value equality and exact runtime type identity at every depth.

    Distinguishes ``bool`` vs ``int`` (``True`` vs ``1``), ``int`` vs ``float`` (``1`` vs ``1.0``),
    ``tuple`` vs ``list``, ``set`` vs ``frozenset``, ``Rot13Token`` vs ``str``, and ``OrderedDict``
    key ordering even when nested inside lists, tuples, or dicts.

    Args:
        actual (Any): Actual decoded Python object.
        expected (Any): Expected ground-truth Python object.
        path (str): Human-readable path for failure diagnostics.

    Raises:
        AssertionError: If any nested type, order, or value differs.
    """
    if type(actual) is not type(expected):
        raise AssertionError(
            f"{path}: exact type mismatch: {type(actual).__name__} ({actual!r}) != "
            f"{type(expected).__name__} ({expected!r})"
        )
    if isinstance(expected, float) and math.isnan(expected):
        if not math.isnan(actual):
            raise AssertionError(f"{path}: expected NaN, got {actual!r}")
        return
    if type(expected) in (list, tuple):
        _assert_sequence_deep_equal(actual, expected, path)
        return
    if type(expected) in (set, frozenset):
        if {_canonical_freeze(x) for x in actual} != {_canonical_freeze(x) for x in expected}:
            raise AssertionError(f"{path}: typed set mismatch: {actual!r} != {expected!r}")
        return
    if type(expected) in (dict, OrderedDict, defaultdict):
        _assert_mapping_deep_equal(actual, expected, path)
        return
    if actual != expected:
        raise AssertionError(f"{path}: value mismatch: {actual!r} != {expected!r}")
