from importlib.metadata import version

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

__version__ = version("redis-dict")
