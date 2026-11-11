"""__init__ module for redis dict."""
from importlib.metadata import version, PackageNotFoundError

from .core import RedisDict
from .crypto import AESGCMCipher, RedisDictDecryptionError, generate_key
from .encrypted_dict import EncryptedRedisDict, RedisDictEncrypted
from .python_dict import PythonRedisDict
from .type_management import decoding_registry, encoding_registry, RedisDictJSONEncoder, RedisDictJSONDecoder

__all__ = [
    'RedisDict',
    'PythonRedisDict',
    'EncryptedRedisDict',
    'RedisDictEncrypted',
    'AESGCMCipher',
    'RedisDictDecryptionError',
    'generate_key',
    'decoding_registry',
    'encoding_registry',
    'RedisDictJSONEncoder',
    'RedisDictJSONDecoder',
]
try:
    __version__ = version("redis-dict")
except PackageNotFoundError:
    __version__ = "0.0.0"
