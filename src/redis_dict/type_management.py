"""Type management module."""

import json
import base64
from collections import OrderedDict, defaultdict
from datetime import datetime, date, time, timedelta

from typing import Callable, Any, Dict, Iterator, List, Tuple, Set

from uuid import UUID
from decimal import Decimal


SENTINEL = object()

EncodeFuncType = Callable[[Any], str]
DecodeFuncType = Callable[[str], Any]
EncodeType = Dict[str, EncodeFuncType]
DecodeType = Dict[str, DecodeFuncType]


def _create_default_encode(custom_encode_method: str) -> EncodeFuncType:
    def default_encode(obj: Any) -> str:
        return getattr(obj, custom_encode_method)()  # type: ignore[no-any-return]
    return default_encode


def _create_default_decode(cls: type, custom_decode_method: str) -> DecodeFuncType:
    def default_decode(encoded_str: str) -> Any:
        return getattr(cls, custom_decode_method)(encoded_str)
    return default_decode


def _decode_tuple(val: str) -> Tuple[Any, ...]:
    """
    Deserialize a JSON-formatted string to a tuple.

    This function takes a JSON-formatted string, deserializes it to a list, and
    then converts the list to a tuple.

    Args:
        val (str): A JSON-formatted string representing a list.

    Returns:
        Tuple[Any, ...]: A tuple with the deserialized values from the input string.
    """
    return tuple(decode_json(val))


def _encode_tuple(val: Tuple[Any, ...]) -> str:
    """
    Serialize a tuple to a JSON-formatted string.

    This function takes a tuple, converts it to a list, and then serializes
    the list to a JSON-formatted string.

    Args:
        val (Tuple[Any, ...]): A tuple with values to be serialized.

    Returns:
        str: A JSON-formatted string representing the input tuple.
    """
    return encode_json(list(val))


def _decode_set(val: str) -> Set[Any]:
    """
    Deserialize a JSON-formatted string to a set.

    This function takes a JSON-formatted string, deserializes it to a list, and
    then converts the list to a set.

    Args:
        val (str): A JSON-formatted string representing a list.

    Returns:
        set[Any]: A set with the deserialized values from the input string.
    """
    return set(decode_json(val))


def _encode_set(val: Set[Any]) -> str:
    """
    Serialize a set to a JSON-formatted string.

    This function takes a set, converts it to a list, and then serializes the
    list to a JSON-formatted string.

    Args:
        val (set[Any]): A set with values to be serialized.

    Returns:
        str: A JSON-formatted string representing the input set.
    """
    return encode_json(list(val))


decoding_registry: DecodeType = {
    type('').__name__: str,
    type(1).__name__: int,
    type(0.1).__name__: float,
    type(True).__name__: lambda x: x == "True",
    type(None).__name__: lambda x: None,

    "list": json.loads,
    "dict": json.loads,
    "tuple": _decode_tuple,
    type(set()).__name__: _decode_set,

    datetime.__name__: datetime.fromisoformat,
    date.__name__: date.fromisoformat,
    time.__name__: time.fromisoformat,
    timedelta.__name__: lambda x: timedelta(seconds=float(x)),

    Decimal.__name__: Decimal,
    complex.__name__: lambda x: complex(*map(float, x.split(','))),
    bytes.__name__: base64.b64decode,

    UUID.__name__: UUID,
    OrderedDict.__name__: lambda x: OrderedDict(json.loads(x)),
    defaultdict.__name__: lambda x: defaultdict(type(None), json.loads(x)),
    frozenset.__name__: lambda x: frozenset(decode_json(x)),
}


encoding_registry: EncodeType = {
    "list": json.dumps,
    "dict": json.dumps,
    "tuple": _encode_tuple,
    type(set()).__name__: _encode_set,

    datetime.__name__: datetime.isoformat,
    date.__name__: date.isoformat,
    time.__name__: time.isoformat,
    timedelta.__name__: lambda x: str(x.total_seconds()),

    complex.__name__: lambda x: f"{x.real},{x.imag}",
    bytes.__name__: lambda x: base64.b64encode(x).decode('ascii'),
    OrderedDict.__name__: lambda x: json.dumps(list(x.items())),
    defaultdict.__name__: lambda x: json.dumps(dict(x)),
    frozenset.__name__: lambda x: encode_json(list(x)),
}


def _tag_json_value(obj: Any) -> Any:
    """
    Prepare a value for JSON encoding, so types JSON can't represent round-trip.

    Tuples, sets and frozensets become {"__type__": name, "value": [items]}. A dict with a non-str key or
    a "__type__" key becomes {"__type__": "dict", "value": [[key, value], ...]}. Other values are unchanged.

    Args:
        obj (Any): The value to prepare.

    Returns:
        Any: The value with every nested tuple, set, frozenset and such dict tagged.
    """
    obj_type = type(obj)
    if obj_type is list:
        return [_tag_json_value(item) for item in obj]
    if obj_type in (tuple, set, frozenset):
        return {"__type__": obj_type.__name__, "value": [_tag_json_value(item) for item in obj]}
    if obj_type is dict:
        if "__type__" in obj or not all(isinstance(key, str) for key in obj):
            return {"__type__": "dict", "value": [[_tag_json_value(k), _tag_json_value(v)] for k, v in obj.items()]}
        return {key: _tag_json_value(value) for key, value in obj.items()}
    return obj


_json_container_decoders: Dict[str, Callable[[List[Any]], Any]] = {
    "tuple": tuple,
    "set": set,
    "frozenset": frozenset,
    "dict": dict,
}


class RedisDictJSONEncoder(json.JSONEncoder):
    """
    Extends JSON encoding capabilities by reusing RedisDict type conversion.

    Uses existing decoding_registry to know which types to handle specially and
    encoding_registry (falls back to str) for converting to JSON-compatible formats.

    Example:
        The encoded format looks like::

            {
                "__type__": "TypeName",
                "value": <encoded value>
            }

    Notes:
        Uses decoding_registry (containing all supported types) to check if type
        needs special handling. For encoding, defaults to str() if no encoder exists
        in encoding_registry.
    """

    def default(self, o: Any) -> Any:
        """Overwrite default from json encoder.

        Args:
            o (Any): Object to be serialized.

        Raises:
            TypeError: If the object `o` cannot be serialized.

        Returns:
            Any: Serialized value.
        """
        type_name = type(o).__name__
        if type_name in decoding_registry:
            return {
                "__type__": type_name,
                "value": encoding_registry.get(type_name, _default_encoder)(o)
            }
        try:
            return json.JSONEncoder.default(self, o)
        except TypeError as e:
            raise TypeError(f"Object of type {type_name} is not JSON serializable") from e

    def iterencode(self, o: Any, _one_shot: bool = False) -> Iterator[str]:
        """Overwrite iterencode from json encoder, to tag tuples, sets and dicts JSON can't represent.

        Args:
            o (Any): Object to be serialized.
            _one_shot (bool): Passed on to json.JSONEncoder.iterencode.

        Returns:
            Iterator[str]: The encoded JSON chunks.
        """
        return super().iterencode(_tag_json_value(o), _one_shot)


class RedisDictJSONDecoder(json.JSONDecoder):
    """
    JSON decoder leveraging RedisDict existing type conversion system.

    Works with RedisDictJSONEncoder to reconstruct Python objects from JSON using
    RedisDict decoding_registry.

    Still needs work but allows for more types than without.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Overwrite the __init__ method from JSON decoder.

        Args:
            *args (Any): Positional arguments for initialization.
            **kwargs (Any): Keyword arguments for initialization.

        """
        def _object_hook(obj: Dict[Any, Any]) -> Any:
            if "__type__" in obj and "value" in obj:
                type_name, value = obj["__type__"], obj["value"]
                if isinstance(value, list) and type_name in _json_container_decoders:
                    return _json_container_decoders[type_name](value)
                if type_name in decoding_registry:
                    return decoding_registry[type_name](value)
            return obj

        super().__init__(object_hook=_object_hook, *args, **kwargs)


def encode_json(obj: Any) -> str:
    """
    Encode a Python object to a JSON string using the existing encoding registry.

    Args:
        obj (Any): The Python object to be encoded.

    Returns:
        str: The JSON-encoded string representation of the object.
    """
    return json.dumps(obj, cls=RedisDictJSONEncoder)


def decode_json(s: str) -> Any:
    """
    Decode a JSON string to a Python object using the existing decoding registry.

    Args:
        s (str): The JSON string to be decoded.

    Returns:
        Any: The decoded Python object.
    """
    return json.loads(s, cls=RedisDictJSONDecoder)


def _default_decoder(x: str) -> str:
    """
    Pass-through decoder that returns the input string unchanged.

    Args:
        x (str): The input string.

    Returns:
        str: The same input string.
    """
    return x


def _default_encoder(x: Any) -> str:
    """
    Take x and returns the result str of the object.

    Args:
        x (Any): The input object

    Returns:
        str: output of str of the object
    """
    return str(x)


encoding_registry["dict"] = encode_json
decoding_registry["dict"] = decode_json


encoding_registry["list"] = encode_json
decoding_registry["list"] = decode_json
