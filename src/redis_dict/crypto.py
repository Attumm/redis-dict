"""Cryptographic primitives for AES-GCM storage encryption."""

import base64
import binascii
import os
import re
import warnings
from functools import lru_cache
from typing import Any, Dict, Mapping, Optional, Tuple, Union

ENV_AES_KEY = "REDIS_DICT_AES_KEY"
ENV_AES_KEYS = "REDIS_DICT_AES_KEYS"
DEFAULT_KEY_ID = "default"
DEFAULT_KDF_SALT = b"redis-dict:aes-gcm-kdf:v1"
FORMAT_VERSION = "v1"
NONCE_BYTES = 12
MIN_PAYLOAD_BYTES = 28  # 12-byte GCM nonce + 16-byte GCM tag

_KEY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HEX_256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_EPHEMERAL_PROCESS_KEY: Optional[bytes] = None


class RedisDictDecryptionError(ValueError):
    """Raised when an encrypted RedisDict value fails authentication or cannot be decoded."""


def generate_key() -> str:
    """Generate a fresh 256-bit URL-safe Base64-encoded AES key.

    Returns:
        str: A 44-character URL-safe Base64 string representing 32 random bytes.
    """
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def _load_crypto_primitives() -> Tuple[Any, Any]:
    """Import cryptography AEAD and KDF classes lazily.

    Returns:
        Tuple[Any, Any]: The ``(AESGCM, Scrypt)`` classes from ``cryptography``.

    Raises:
        ImportError: If the optional ``cryptography`` package is not installed.
    """
    try:
        # pylint: disable=import-outside-toplevel
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    except ImportError as exc:
        raise ImportError(
            "AES-GCM storage encryption requires the optional 'crypto' extra. "
            "Install it with: pip install \"redis-dict[crypto]\""
        ) from exc
    return AESGCM, Scrypt


def _get_ephemeral_process_key() -> bytes:
    """Return a lazily generated 256-bit random key shared within the current Python process.

    Returns:
        bytes: 32 random bytes for zero-configuration single-process usage.
    """
    global _EPHEMERAL_PROCESS_KEY  # pylint: disable=global-statement
    if _EPHEMERAL_PROCESS_KEY is None:
        _EPHEMERAL_PROCESS_KEY = os.urandom(32)
    return _EPHEMERAL_PROCESS_KEY


def _validate_key_id(key_id: str) -> None:
    """Validate that a key identifier is safe for wire-format headers.

    Args:
        key_id (str): Identifier for a configured encryption key.

    Raises:
        ValueError: If ``key_id`` is empty or contains disallowed characters.
    """
    if not _KEY_ID_RE.match(key_id):
        raise ValueError(
            f"Invalid key_id {key_id!r}: must be 1-64 characters matching [A-Za-z0-9_-]."
        )


@lru_cache(maxsize=64)
def _derive_scrypt_key(secret: bytes, salt: bytes, scrypt_cls: Any) -> bytes:
    """Derive a 256-bit AES key from an arbitrary secret using memory-hard Scrypt.

    Args:
        secret (bytes): UTF-8 or raw secret bytes.
        salt (bytes): Domain-separation salt bytes.
        scrypt_cls (Any): ``cryptography`` ``Scrypt`` class.

    Returns:
        bytes: Derived 32-byte AES-256 key.
    """
    kdf = scrypt_cls(salt=salt, length=32, n=2**14, r=8, p=1)
    derived: bytes = kdf.derive(secret)
    return derived


def _decode_encoded_256_key(raw_key: str) -> Optional[bytes]:
    """Decode a canonical 256-bit hex or Base64 key string if valid.

    Args:
        raw_key (str): Candidate key string.

    Returns:
        Optional[bytes]: Decoded 32-byte key, or ``None`` if ``raw_key`` is a passphrase.
    """
    if _HEX_256_RE.match(raw_key):
        return bytes.fromhex(raw_key)
    if len(raw_key) == 44 and raw_key.endswith("="):
        try:
            normalized = raw_key.replace("+", "-").replace("/", "_")
            decoded = base64.urlsafe_b64decode(normalized.encode("ascii"))
            if len(decoded) == 32:
                return decoded
        except (ValueError, binascii.Error):
            return None
    return None


def _normalize_key_material(raw_key: Union[bytes, str], salt: bytes, scrypt_cls: Any) -> bytes:
    """Normalize raw bytes, encoded 256-bit keys, or passphrases into valid AES key bytes.

    Args:
        raw_key (Union[bytes, str]): Key material provided by caller or environment.
        salt (bytes): Domain-separation salt used when deriving from a passphrase.
        scrypt_cls (Any): ``cryptography`` ``Scrypt`` class.

    Returns:
        bytes: Validated 16-, 24-, or 32-byte AES key.

    Raises:
        ValueError: If ``raw_key`` is empty or ``salt`` is empty.
    """
    if not salt:
        raise ValueError("KDF salt must not be empty.")
    if isinstance(raw_key, bytes):
        if len(raw_key) == 0:
            raise ValueError("Encryption key must not be empty.")
        if len(raw_key) in (16, 24, 32):
            return raw_key
        return _derive_scrypt_key(raw_key, salt, scrypt_cls)

    if len(raw_key) == 0:
        raise ValueError("Encryption key must not be empty.")
    decoded = _decode_encoded_256_key(raw_key)
    if decoded is not None:
        return decoded
    return _derive_scrypt_key(raw_key.encode("utf-8"), salt, scrypt_cls)


def _parse_env_keys(raw_env: str) -> Tuple[Dict[str, str], str]:
    """Parse ``REDIS_DICT_AES_KEYS`` formatted as ``id1:key1,id2:key2``.

    Args:
        raw_env (str): Comma-separated ``key_id:key_material`` pairs.

    Returns:
        Tuple[Dict[str, str], str]: Mapping of key IDs to raw strings and the first key ID.

    Raises:
        ValueError: If any entry is malformed or duplicated.
    """
    parsed: Dict[str, str] = {}
    first_id = ""
    for item in raw_env.split(","):
        entry = item.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(
                f"Invalid {ENV_AES_KEYS} entry: expected '<key_id>:<key>', got entry without ':'."
            )
        key_id, key_val = entry.split(":", 1)
        key_id = key_id.strip()
        _validate_key_id(key_id)
        if key_id in parsed:
            raise ValueError(f"Duplicate key_id {key_id!r} in {ENV_AES_KEYS}.")
        if not first_id:
            first_id = key_id
        parsed[key_id] = key_val.strip()

    if not parsed:
        raise ValueError(f"{ENV_AES_KEYS} is set but contains no valid keys.")
    return parsed, first_id


def _resolve_key_sources(
    key: Optional[Union[bytes, str]],
    keys: Optional[Mapping[str, Union[bytes, str]]],
    primary_key_id: Optional[str],
) -> Tuple[Mapping[str, Union[bytes, str]], str]:
    """Resolve key mapping and primary key ID from explicit args, environment, or fallback.

    Args:
        key (Optional[Union[bytes, str]]): Single explicit key.
        keys (Optional[Mapping[str, Union[bytes, str]]]): Explicit key ring for rotation.
        primary_key_id (Optional[str]): Explicit primary key ID.

    Returns:
        Tuple[Mapping[str, Union[bytes, str]], str]: Resolved key map and primary key ID.

    Raises:
        ValueError: If both ``key`` and ``keys`` are passed or ``keys`` is empty.
    """
    if key is not None and keys is not None:
        raise ValueError("Pass either 'key' or 'keys', not both.")
    if keys is not None:
        if len(keys) == 0:
            raise ValueError("'keys' mapping must not be empty.")
        chosen_primary = primary_key_id if primary_key_id is not None else next(iter(keys))
        return keys, chosen_primary
    if key is not None:
        key_id = primary_key_id or DEFAULT_KEY_ID
        return {key_id: key}, key_id

    env_keys = os.environ.get(ENV_AES_KEYS)
    if env_keys is not None and env_keys.strip():
        parsed_env, first_id = _parse_env_keys(env_keys)
        return parsed_env, primary_key_id or first_id

    env_single = os.environ.get(ENV_AES_KEY)
    if env_single is not None:
        key_id = primary_key_id or DEFAULT_KEY_ID
        return {key_id: env_single}, key_id

    warnings.warn(
        f"No encryption key or {ENV_AES_KEY} environment variable configured; "
        f"generated an ephemeral per-process AES-256 key. Set {ENV_AES_KEY} to "
        "persist or share encrypted data across processes.",
        UserWarning,
        stacklevel=3,
    )
    key_id = primary_key_id or DEFAULT_KEY_ID
    return {key_id: _get_ephemeral_process_key()}, key_id


class AESGCMCipher:
    """Misuse-resistant AES-GCM cipher supporting fresh 96-bit nonces, AAD, and key rotation."""

    def __init__(
        self,
        key: Optional[Union[bytes, str]] = None,
        keys: Optional[Mapping[str, Union[bytes, str]]] = None,
        primary_key_id: Optional[str] = None,
        salt: bytes = DEFAULT_KDF_SALT,
    ) -> None:
        """Initialize an AES-GCM cipher from explicit keys, environment variables, or safe fallback.

        Args:
            key (Optional[Union[bytes, str]], optional): Single AES key (bytes, Base64/hex, or passphrase).
            keys (Optional[Mapping[str, Union[bytes, str]]], optional): Mapping of ``key_id`` to key material.
            primary_key_id (Optional[str], optional): Key ID used for new writes.
            salt (bytes): Domain salt used when deriving keys from passphrases via Scrypt.

        Raises:
            ValueError: If key configuration or ``primary_key_id`` is invalid.
        """
        aesgcm_cls, scrypt_cls = _load_crypto_primitives()
        resolved_keys, resolved_primary = _resolve_key_sources(key, keys, primary_key_id)

        aeads: Dict[str, Any] = {}
        for current_id, raw_material in resolved_keys.items():
            _validate_key_id(current_id)
            normalized = _normalize_key_material(raw_material, salt, scrypt_cls)
            aeads[current_id] = aesgcm_cls(normalized)

        if resolved_primary not in aeads:
            raise ValueError(f"primary_key_id {resolved_primary!r} is not present in configured keys.")

        self._aeads = aeads
        self._primary_key_id = resolved_primary

    @property
    def primary_key_id(self) -> str:
        """Return the identifier of the key used to encrypt new writes.

        Returns:
            str: Active primary key identifier.
        """
        return self._primary_key_id

    @staticmethod
    def _build_aad(key_id: str, context: str) -> bytes:
        return f"redis-dict:{FORMAT_VERSION}:{key_id}:{context}".encode("utf-8", errors="surrogatepass")

    def encrypt(self, plaintext: str, context: str = "") -> str:
        """Encrypt a string with a fresh 12-byte random nonce and context-bound AAD.

        Args:
            plaintext (str): Serialized ``type:value`` string to encrypt.
            context (str): Associated context (such as ``namespace:key``) bound into GCM AAD.

        Returns:
            str: Self-describing token ``v1$<key_id>$<urlsafe_b64>``.
        """
        nonce = os.urandom(NONCE_BYTES)
        aad = self._build_aad(self._primary_key_id, context)
        plaintext_bytes = plaintext.encode("utf-8", errors="surrogatepass")
        ct_and_tag: bytes = self._aeads[self._primary_key_id].encrypt(nonce, plaintext_bytes, aad)
        encoded = base64.urlsafe_b64encode(nonce + ct_and_tag).decode("ascii").rstrip("=")
        return f"{FORMAT_VERSION}${self._primary_key_id}${encoded}"

    def decrypt(self, token: str, context: str = "") -> str:
        """Verify and decrypt a ``v1$<key_id>$<urlsafe_b64>`` token.

        Args:
            token (str): Encrypted token string stored in Redis.
            context (str): Expected AAD context (such as ``namespace:key``).

        Returns:
            str: Decrypted plaintext string.

        Raises:
            RedisDictDecryptionError: If the header, key ID, authentication tag, or payload is invalid.
        """
        version, key_id, b64_payload = self._split_token(token)
        if version != FORMAT_VERSION or key_id not in self._aeads:
            raise RedisDictDecryptionError("Unsupported encryption version or unknown key_id.")

        raw = self._decode_b64_payload(b64_payload)
        nonce, ct_and_tag = raw[:NONCE_BYTES], raw[NONCE_BYTES:]
        aad = self._build_aad(key_id, context)
        try:
            decrypted_bytes: bytes = self._aeads[key_id].decrypt(nonce, ct_and_tag, aad)
            return decrypted_bytes.decode("utf-8", errors="surrogatepass")
        except Exception:
            raise RedisDictDecryptionError(
                "Encrypted payload authentication failed (wrong key, tampered value, or mismatched key context)."
            ) from None

    def extract_key_id(self, token: str) -> str:
        """Extract the ``key_id`` recorded in a ``v1$<key_id>$<payload>`` token.

        Args:
            token (str): Encrypted token string.

        Returns:
            str: The ``key_id`` embedded in the token header.
        """
        _, key_id, _ = self._split_token(token)
        return key_id

    @staticmethod
    def _split_token(token: str) -> Tuple[str, str, str]:
        parts = token.split("$")
        if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2]:
            raise RedisDictDecryptionError("Malformed encrypted token header.")
        return parts[0], parts[1], parts[2]

    @staticmethod
    def _decode_b64_payload(b64_payload: str) -> bytes:
        padded = b64_payload + "=" * (-len(b64_payload) % 4)
        try:
            raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        except (ValueError, binascii.Error):
            raise RedisDictDecryptionError("Malformed Base64 in encrypted payload.") from None
        if len(raw) < MIN_PAYLOAD_BYTES:
            raise RedisDictDecryptionError("Encrypted payload is truncated.")
        return raw

    def __repr__(self) -> str:
        """Return a safe representation with key material redacted.

        Returns:
            str: Redacted representation listing configured key IDs only.
        """
        key_ids = list(self._aeads.keys())
        return f"AESGCMCipher(key_ids={key_ids!r}, primary_key_id={self._primary_key_id!r})"


if __name__ == "__main__":
    print(generate_key())
