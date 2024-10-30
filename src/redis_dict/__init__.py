from importlib.metadata import version, PackageNotFoundError

from .core import RedisDict
from .core import encode_json, decode_json
from .core import encoding_registry, decoding_registry
from .core import RedisDictJSONEncoder, RedisDictJSONDecoder

__all__ = [
    'RedisDict',
    'encode_json', 'decode_json',
    'encoding_registry', 'decoding_registry',
    'RedisDictJSONEncoder', 'RedisDictJSONDecoder'
]
try:
    __version__ = version("redis-dict")
except PackageNotFoundError:
    __version__ = "0.0.0"
