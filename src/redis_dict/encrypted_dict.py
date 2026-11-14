"""Encrypted Redis Dict module.

Uses cryptography's official AESGCM construction:
https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM
"""
import base64
import os
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .core import RedisDict


class EncryptedRedisDict(RedisDict):
    """RedisDict that encrypts every value with AES-GCM before it is stored.

    See https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM
    """

    def __init__(self, namespace: str = 'main', *, key: bytes, **kwargs: Any) -> None:
        """Initialize an EncryptedRedisDict instance.

        Args:
            namespace (str): A prefix for keys stored in Redis.
            key (bytes): Secret 16, 24, or 32-byte AES key.
            **kwargs (Any): Additional keyword arguments forwarded to RedisDict.
        """
        self._cipher = AESGCM(key)
        super().__init__(namespace, **kwargs)

    def _format_value(self, value: Any) -> str:
        plain = super()._format_value(value)          # "type:value", exactly as RedisDict stores it
        nonce = os.urandom(12)
        encrypted = self._cipher.encrypt(nonce, plain.encode('utf-8'), self.namespace.encode('utf-8'))
        return base64.b64encode(nonce + encrypted).decode('ascii')

    def _transform(self, result: str) -> Any:
        raw = base64.b64decode(result, validate=True)
        if len(raw) < 28:
            raise InvalidTag()
        plain = self._cipher.decrypt(raw[:12], raw[12:], self.namespace.encode('utf-8')).decode('utf-8')
        return super()._transform(plain)
