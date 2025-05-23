"""__init__ module for redis dict."""
from importlib.metadata import version, PackageNotFoundError

from .core import RedisDict
from .python_dict import PythonRedisDict
from .type_management import decoding_registry, encoding_registry, RedisDictJSONEncoder, RedisDictJSONDecoder

__all__ = [
    'RedisDict',
    'PythonRedisDict',
    'decoding_registry',
    'encoding_registry',
    'RedisDictJSONEncoder',
    'RedisDictJSONDecoder',
]
try:
    __version__ = version("redis-dict")
except PackageNotFoundError:
    __version__ = "0.0.0"
