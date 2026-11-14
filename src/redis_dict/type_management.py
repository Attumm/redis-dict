"""Type management module."""

import json
import base64
from collections import OrderedDict, defaultdict
from datetime import datetime, date, time, timedelta

from typing import Callable, Any, Dict, Iterator, List, Optional, Tuple

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


decoding_registry: DecodeType = {
    type('').__name__: str,
    type(1).__name__: int,
    type(0.1).__name__: float,
    type(True).__name__: lambda x: x == "True",
    type(None).__name__: lambda x: None,

    datetime.__name__: datetime.fromisoformat,
    date.__name__: date.fromisoformat,
    time.__name__: time.fromisoformat,
    timedelta.__name__: lambda x: timedelta(seconds=float(x)),

    Decimal.__name__: Decimal,
    complex.__name__: lambda x: complex(*map(float, x.split(','))),
    bytes.__name__: base64.b64decode,

    UUID.__name__: UUID,
}


encoding_registry: EncodeType = {
    datetime.__name__: datetime.isoformat,
    date.__name__: date.isoformat,
    time.__name__: time.isoformat,
    timedelta.__name__: lambda x: str(x.total_seconds()),

    complex.__name__: lambda x: f"{x.real},{x.imag}",
    bytes.__name__: lambda x: base64.b64encode(x).decode('ascii'),
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

    def __init__(
        self,
        *args: Any,
        encoding_reg: Optional[EncodeType] = None,
        decoding_reg: Optional[DecodeType] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the JSON encoder with optional per-instance type registries.

        Args:
            *args (Any): Positional arguments forwarded to json.JSONEncoder.
            encoding_reg (Optional[EncodeType]): Encoding registry override.
            decoding_reg (Optional[DecodeType]): Decoding registry override.
            **kwargs (Any): Keyword arguments forwarded to json.JSONEncoder.
        """
        super().__init__(*args, **kwargs)
        self._encoding_reg = encoding_reg if encoding_reg is not None else encoding_registry
        self._decoding_reg = decoding_reg if decoding_reg is not None else decoding_registry

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
        if type_name in self._decoding_reg:
            return {
                "__type__": type_name,
                "value": self._encoding_reg.get(type_name, _default_encoder)(o)
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

    def __init__(
        self,
        *args: Any,
        decoding_reg: Optional[DecodeType] = None,
        **kwargs: Any,
    ) -> None:
        """
        Overwrite the __init__ method from JSON decoder.

        Args:
            *args (Any): Positional arguments for initialization.
            decoding_reg (Optional[DecodeType]): Decoding registry override.
            **kwargs (Any): Keyword arguments for initialization.

        """
        active_decoding_reg = decoding_reg if decoding_reg is not None else decoding_registry

        def _object_hook(obj: Dict[Any, Any]) -> Any:
            if "__type__" in obj and "value" in obj:
                type_name, value = obj["__type__"], obj["value"]
                if isinstance(value, list) and type_name in _json_container_decoders:
                    return _json_container_decoders[type_name](value)
                if type_name in active_decoding_reg:
                    return active_decoding_reg[type_name](value)
            return obj

        super().__init__(object_hook=_object_hook, *args, **kwargs)


def encode_json(
    obj: Any,
    encoding_reg: Optional[EncodeType] = None,
    decoding_reg: Optional[DecodeType] = None,
) -> str:
    """
    Encode a Python object to a JSON string using the existing encoding registry.

    Args:
        obj (Any): The Python object to be encoded.
        encoding_reg (Optional[EncodeType]): Optional per-instance encoding registry.
        decoding_reg (Optional[DecodeType]): Optional per-instance decoding registry.

    Returns:
        str: The JSON-encoded string representation of the object.
    """
    return json.dumps(
        obj,
        cls=RedisDictJSONEncoder,
        encoding_reg=encoding_reg,
        decoding_reg=decoding_reg,
    )


def decode_json(s: str, decoding_reg: Optional[DecodeType] = None) -> Any:
    """
    Decode a JSON string to a Python object using the existing decoding registry.

    Args:
        s (str): The JSON string to be decoded.
        decoding_reg (Optional[DecodeType]): Optional per-instance decoding registry.

    Returns:
        Any: The decoded Python object.
    """
    return json.loads(s, cls=RedisDictJSONDecoder, decoding_reg=decoding_reg)


def _bind_json_containers(
    enc: EncodeType,
    dec: DecodeType,
    enc_json: EncodeFuncType,
    dec_json: DecodeFuncType,
) -> None:
    enc["dict"] = enc_json
    enc["list"] = enc_json
    enc["tuple"] = lambda x: enc_json(list(x))
    enc["set"] = lambda x: enc_json(list(x))
    enc["frozenset"] = lambda x: enc_json(list(x))
    enc["OrderedDict"] = lambda x: enc_json(list(x.items()))
    enc["defaultdict"] = lambda x: enc_json(dict(x))

    dec["dict"] = dec_json
    dec["list"] = dec_json
    dec["tuple"] = lambda x: tuple(dec_json(x))
    dec["set"] = lambda x: set(dec_json(x))
    dec["frozenset"] = lambda x: frozenset(dec_json(x))
    dec["OrderedDict"] = lambda x: OrderedDict(dec_json(x))
    dec["defaultdict"] = lambda x: defaultdict(type(None), dec_json(x))


def _create_instance_registries() -> Tuple[EncodeType, DecodeType]:
    """Create isolated per-instance encode/decode registries wired to each other for nested JSON.

    Returns:
        Tuple[EncodeType, DecodeType]: Isolated encoding and decoding registry copies.
    """
    enc = encoding_registry.copy()
    dec = decoding_registry.copy()
    _bind_json_containers(
        enc,
        dec,
        lambda obj: encode_json(obj, encoding_reg=enc, decoding_reg=dec),
        lambda raw: decode_json(raw, decoding_reg=dec),
    )
    return enc, dec


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


_bind_json_containers(encoding_registry, decoding_registry, encode_json, decode_json)
