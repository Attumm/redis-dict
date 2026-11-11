"""Encrypted Redis Dict module."""

from datetime import timedelta
from typing import Any, Mapping, Optional, Union

from redis import StrictRedis

from .core import RedisDict
from .crypto import AESGCMCipher, DEFAULT_KDF_SALT, RedisDictDecryptionError

ENC_TYPE_TAG = "__enc__"
MAX_ENCRYPTED_PLAINTEXT_SIZE = 375 * 1024 * 1024  # 375 MB raw -> ~500 MB Base64 (< 512 MB Redis limit)


class EncryptedRedisDict(RedisDict):
    """Redis-backed dictionary that transparently encrypts all stored values with AES-GCM.

    Every value (along with its Python type tag) is serialized using ``RedisDict``'s standard
    and custom type registries and then encrypted with AES-GCM using a fresh 12-byte random
    nonce per write. Each ciphertext is cryptographically bound to ``namespace:key`` via GCM
    Associated Authenticated Data (AAD), preventing cross-key and cross-namespace value swaps.

    Key resolution order:
    1. Explicit ``cipher`` instance (``AESGCMCipher``).
    2. Explicit ``keys`` mapping (multi-key rotation) or single ``key`` argument.
    3. ``REDIS_DICT_AES_KEYS`` or ``REDIS_DICT_AES_KEY`` environment variable.
    4. Ephemeral per-process random 256-bit key (emits a ``UserWarning``).
    """

    # pylint: disable=R0913,too-many-positional-arguments
    def __init__(
        self,
        namespace: str = "main",
        expire: Union[int, timedelta, None] = None,
        preserve_expiration: Optional[bool] = False,
        redis: "Optional[StrictRedis[Any]]" = None,
        raise_key_error_delete: bool = False,
        key: Optional[Union[bytes, str]] = None,
        keys: Optional[Mapping[str, Union[bytes, str]]] = None,
        primary_key_id: Optional[str] = None,
        cipher: Optional[AESGCMCipher] = None,
        salt: bytes = DEFAULT_KDF_SALT,
        **redis_kwargs: Any,
    ) -> None:  # noqa: D202 pydocstyle clashes with Sphinx
        """Initialize an EncryptedRedisDict instance.

        Args:
            namespace (str): Key namespace prefix in Redis.
            expire (Union[int, timedelta, None], optional): Default expiration time for keys.
            preserve_expiration (Optional[bool], optional): Preserve existing TTL on key updates.
            redis (Optional[StrictRedis[Any]], optional): Pre-configured Redis client instance.
            raise_key_error_delete (bool): Raise ``KeyError`` when deleting a missing key.
            key (Optional[Union[bytes, str]], optional): AES key (bytes, 256-bit Base64/hex, or passphrase).
            keys (Optional[Mapping[str, Union[bytes, str]]], optional): Key ring ``{key_id: key}`` for rotation.
            primary_key_id (Optional[str], optional): Active ``key_id`` for new writes during rotation.
            cipher (Optional[AESGCMCipher], optional): Pre-constructed ``AESGCMCipher`` instance.
            salt (bytes): Domain salt used when deriving a key from a passphrase via Scrypt.
            **redis_kwargs (Any): Additional keyword arguments forwarded to ``StrictRedis``.
        """
        self._cipher = (
            cipher
            if cipher is not None
            else AESGCMCipher(key=key, keys=keys, primary_key_id=primary_key_id, salt=salt)
        )
        super().__init__(
            namespace, expire, preserve_expiration, redis, raise_key_error_delete, **redis_kwargs
        )
        self._max_string_size = MAX_ENCRYPTED_PLAINTEXT_SIZE

    @property
    def cipher(self) -> AESGCMCipher:
        """Return the ``AESGCMCipher`` instance backing this dictionary.

        Returns:
            AESGCMCipher: Active cipher instance (key material is redacted in ``repr()``).
        """
        return self._cipher

    def _format_value(self, value: Any, formatted_key: Optional[str] = None) -> str:
        """Serialize ``value`` and encrypt the full ``type:payload`` string with AES-GCM.

        Args:
            value (Any): Python object to store.
            formatted_key (Optional[str], optional): Full ``namespace:key`` bound into GCM AAD.

        Returns:
            str: Encrypted Redis payload prefixed with ``__enc__:``.
        """
        inner = super()._format_value(value, formatted_key)
        token = self._cipher.encrypt(inner, context=formatted_key or "")
        return f"{ENC_TYPE_TAG}{self.key_delimiter}{token}"

    def _transform(self, result: str, formatted_key: Optional[str] = None) -> Any:
        """Verify, decrypt, and deserialize an encrypted Redis payload.

        Args:
            result (str): Raw string fetched from Redis.
            formatted_key (Optional[str], optional): Expected ``namespace:key`` bound into GCM AAD.

        Returns:
            Any: Decrypted and deserialized Python object.

        Raises:
            RedisDictDecryptionError: If the payload is unencrypted, malformed, tampered with, or bound to another key.
        """
        if self.key_delimiter not in result:
            raise RedisDictDecryptionError("Stored value is missing encryption type delimiter.")
        outer_type, token = result.split(self.key_delimiter, 1)
        if outer_type != ENC_TYPE_TAG:
            raise RedisDictDecryptionError("Stored value is not encrypted with EncryptedRedisDict.")
        inner = self._cipher.decrypt(token, context=formatted_key or "")
        return super()._transform(inner, formatted_key)

    def rotate_keys(self) -> int:
        """Re-encrypt entries written under older key IDs onto ``cipher.primary_key_id``.

        Existing Redis TTLs are preserved atomically using ``SET ... KEEPTTL``.

        Returns:
            int: Number of keys re-encrypted onto the current primary key.

        Raises:
            RedisDictDecryptionError: If an existing entry fails authentication during rotation.
        """
        rotated = 0
        for raw_key in self._scan_keys(full_scan=True):
            raw_val = self.get_redis.get(raw_key)
            if raw_val is None:
                continue
            if self.key_delimiter not in raw_val:
                raise RedisDictDecryptionError("Stored value is missing encryption type delimiter.")
            outer_type, token = raw_val.split(self.key_delimiter, 1)
            if outer_type != ENC_TYPE_TAG:
                raise RedisDictDecryptionError("Stored value is not encrypted with EncryptedRedisDict.")
            if self._cipher.extract_key_id(token) == self._cipher.primary_key_id:
                continue
            plain_value = self._transform(raw_val, raw_key)
            reencrypted = self._format_value(plain_value, raw_key)
            self.get_redis.set(raw_key, reencrypted, keepttl=True)
            rotated += 1
        return rotated


RedisDictEncrypted = EncryptedRedisDict
