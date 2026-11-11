import base64
import json
import os
import subprocess
import sys
import unittest
import warnings
from collections import OrderedDict, defaultdict
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

from redis_dict import (
    AESGCMCipher,
    EncryptedRedisDict,
    RedisDict,
    RedisDictDecryptionError,
    RedisDictEncrypted,
    generate_key,
)

TEST_NAMESPACE = "__test_encrypted_redis_dict_v360__"


class _Person:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    def encode(self) -> str:
        return json.dumps({"name": self.name, "age": self.age})

    @classmethod
    def decode(cls, encoded: str) -> "_Person":
        data = json.loads(encoded)
        return cls(name=data["name"], age=data["age"])

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Person) and self.name == other.name and self.age == other.age


class TestEncryptedRedisDict(unittest.TestCase):
    """Comprehensive security, customization, and round-trip tests for EncryptedRedisDict."""

    def setUp(self) -> None:
        self._saved_env = {
            k: os.environ.get(k)
            for k in ("REDIS_DICT_AES_KEY", "REDIS_DICT_AES_KEYS")
        }
        os.environ.pop("REDIS_DICT_AES_KEY", None)
        os.environ.pop("REDIS_DICT_AES_KEYS", None)
        self._clean_namespaces()

    def tearDown(self) -> None:
        self._clean_namespaces()
        for k, val in self._saved_env.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val

    @staticmethod
    def _clean_namespaces() -> None:
        for ns in (TEST_NAMESPACE, f"{TEST_NAMESPACE}_other", f"{TEST_NAMESPACE}_plain"):
            RedisDict(namespace=ns).clear()

    def test_alias_points_to_encrypted_redis_dict(self) -> None:
        self.assertIs(RedisDictEncrypted, EncryptedRedisDict)

    def test_tier1_zero_config_works_out_of_the_box_with_warning(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            d1 = EncryptedRedisDict(namespace=TEST_NAMESPACE)
            d2 = EncryptedRedisDict(namespace=TEST_NAMESPACE)

        warning_messages = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
        self.assertTrue(
            any("REDIS_DICT_AES_KEY" in msg for msg in warning_messages),
            f"Expected UserWarning mentioning REDIS_DICT_AES_KEY, got: {warning_messages}",
        )

        d1["secret"] = "top-secret-value"
        self.assertEqual(d2["secret"], "top-secret-value")

        raw = d1.get_redis.get(d1._format_key("secret"))
        self.assertIsNotNone(raw)
        assert raw is not None
        self.assertTrue(raw.startswith("__enc__:v1$"))
        self.assertNotIn("top-secret-value", raw)
        self.assertNotIn("str:", raw)

    def test_tier2_passphrase_env_var_uses_scrypt_kdf_safely(self) -> None:
        os.environ["REDIS_DICT_AES_KEY"] = "my-human-readable-team-passphrase"

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            writer = EncryptedRedisDict(namespace=TEST_NAMESPACE)
            reader = EncryptedRedisDict(namespace=TEST_NAMESPACE)

        self.assertEqual([w for w in caught if issubclass(w.category, UserWarning)], [])

        writer["config"] = {"token": "sk-live-999", "retries": 3}
        self.assertEqual(reader["config"], {"token": "sk-live-999", "retries": 3})

        # Custom KDF salt isolates key derivation from default salt
        custom_salt_reader = EncryptedRedisDict(
            namespace=TEST_NAMESPACE,
            salt=b"custom-application-domain-salt-v1",
        )
        with self.assertRaises(RedisDictDecryptionError):
            _ = custom_salt_reader["config"]

    def test_tier3_generated_key_env_and_cli_helper(self) -> None:
        generated = generate_key()
        self.assertEqual(len(base64.urlsafe_b64decode(generated.encode("ascii"))), 32)

        cli_proc = subprocess.run(
            [sys.executable, "-m", "redis_dict.crypto"],
            check=True,
            capture_output=True,
            text=True,
        )
        cli_key = cli_proc.stdout.strip()
        self.assertEqual(len(base64.urlsafe_b64decode(cli_key.encode("ascii"))), 32)
        self.assertNotEqual(generated, cli_key)

        os.environ["REDIS_DICT_AES_KEY"] = cli_key
        dic = EncryptedRedisDict(namespace=TEST_NAMESPACE)
        dic["hello"] = "world"
        self.assertEqual(dic["hello"], "world")

        # 64-character hex-encoded 256-bit key is also supported directly
        hex_key = os.urandom(32).hex()
        hex_dic = EncryptedRedisDict(namespace=f"{TEST_NAMESPACE}_other", key=hex_key)
        hex_dic["hex_item"] = 12345
        self.assertEqual(hex_dic["hex_item"], 12345)

    def test_all_standard_nested_custom_and_edge_strings_round_trip(self) -> None:
        key_bytes = os.urandom(32)
        dic = EncryptedRedisDict(namespace=TEST_NAMESPACE, key=key_bytes)
        dic.extends_type(_Person)

        samples = {
            "str": "Hello World",
            "empty_str": "",
            "whitespace": " \t\n\r",
            "unicode": "äöüßÄÖÜ 😀🙈🚀 中文字符测试 こんにちは 한글 테스트 𝔘𝔫𝔦𝔠𝔬𝔡𝔢",
            "null_and_high_bytes": "prefix\x00suffix\x00\xff\uffff",
            "surrogate_pair": "\ud83d\ude00",
            "quotes_and_slashes": "\"quoted\" 'single' C:\\Program Files\\ \\n\\t",
            "long_text": "Lorem ipsum dolor sit amet. " * 200,
            "int": 42,
            "float": 3.14159,
            "bool_true": True,
            "bool_false": False,
            "none": None,
            "list": [1, "two", 3.0, [4, 5], datetime(2026, 11, 11, 12, 0)],
            "dict": {"a": 1, "nested": {"delta": timedelta(hours=5)}, "__type__": "literal", "value": 9},
            "int_key_dict": {1: "one", 2: "two"},
            "tuple": (1, (2, 3), "four"),
            "set": {1, 2, (3, 4)},
            "datetime": datetime(2024, 1, 1, 12, 30, 45),
            "date": date(2024, 2, 29),
            "time": dt_time(12, 30, 45),
            "timedelta": timedelta(days=1, hours=2, microseconds=5),
            "decimal": Decimal("3.14159265358979323846"),
            "complex": complex(1.5, -2.5),
            "bytes": b"\x00\x01\x02hello\xff",
            "uuid": UUID("12345678-1234-5678-1234-567812345678"),
            "ordered": OrderedDict([("first", 1), ("second", 2)]),
            "default": defaultdict(type(None), {"x": 10}),
            "frozen": frozenset(["a", "b", "c"]),
            "person": _Person("Ada", 36),
        }

        with dic.pipeline():
            for sample_key, sample_val in samples.items():
                dic[sample_key] = sample_val

        for sample_key, expected_val in samples.items():
            with self.subTest(sample_key=sample_key):
                raw = dic.get_redis.get(dic._format_key(sample_key))
                self.assertIsNotNone(raw)
                assert raw is not None
                self.assertTrue(raw.startswith("__enc__:v1$default$"))
                # Stored format hides Python type tags as well as values
                for leaked_prefix in ("str:", "int:", "dict:", "bool:", "_Person:"):
                    self.assertFalse(raw.startswith(leaked_prefix))
                self.assertEqual(dic[sample_key], expected_val)

    def test_nonce_is_freshly_random_on_every_write(self) -> None:
        dic = EncryptedRedisDict(namespace=TEST_NAMESPACE, key=os.urandom(32))
        seen_raw_payloads = set()

        for _ in range(50):
            dic["repeated"] = "identical-plaintext"
            raw = dic.get_redis.get(dic._format_key("repeated"))
            self.assertIsNotNone(raw)
            seen_raw_payloads.add(raw)

        self.assertEqual(len(seen_raw_payloads), 50)

    def test_tampering_wrong_key_and_plaintext_injection_raise_decryption_error(self) -> None:
        key_a = os.urandom(32)
        key_b = os.urandom(32)
        dic_a = EncryptedRedisDict(namespace=TEST_NAMESPACE, key=key_a)
        dic_b = EncryptedRedisDict(namespace=TEST_NAMESPACE, key=key_b)

        dic_a["item"] = {"admin": False}
        formatted_key = dic_a._format_key("item")
        original_raw = dic_a.get_redis.get(formatted_key)
        assert original_raw is not None

        # Wrong key fails closed
        with self.assertRaises(RedisDictDecryptionError):
            _ = dic_b["item"]

        # Bit-flip in nonce, ciphertext, or tag fails GCM authentication
        prefix, b64_blob = original_raw.rsplit("$", 1)
        padded = b64_blob + "=" * (-len(b64_blob) % 4)
        raw_bytes = bytearray(base64.urlsafe_b64decode(padded.encode("ascii")))
        for byte_idx in (0, len(raw_bytes) // 2, len(raw_bytes) - 1):
            mutated = bytearray(raw_bytes)
            mutated[byte_idx] ^= 0x01
            mutated_b64 = base64.urlsafe_b64encode(bytes(mutated)).decode("ascii").rstrip("=")
            dic_a.get_redis.set(formatted_key, f"{prefix}${mutated_b64}")
            with self.assertRaises(RedisDictDecryptionError):
                _ = dic_a["item"]

        # Tampered version or key_id fails closed
        dic_a.get_redis.set(formatted_key, f"__enc__:v2$default${b64_blob}")
        with self.assertRaises(RedisDictDecryptionError):
            _ = dic_a["item"]

        dic_a.get_redis.set(formatted_key, f"__enc__:v1$other${b64_blob}")
        with self.assertRaises(RedisDictDecryptionError):
            _ = dic_a["item"]

        # Unencrypted plaintext injected directly into Redis is strictly rejected
        dic_a.get_redis.set(formatted_key, "str:injected-plaintext")
        with self.assertRaises(RedisDictDecryptionError):
            _ = dic_a["item"]
        with self.assertRaises(RedisDictDecryptionError):
            dic_a.setdefault("item", "fallback")
        # Restore valid payload, then test pop() on injected plaintext too
        dic_a.get_redis.set(dic_a._format_key("injected_pop"), "int:999")
        with self.assertRaises(RedisDictDecryptionError):
            dic_a.pop("injected_pop")

    def test_aad_blocks_cross_key_and_cross_namespace_ciphertext_swaps(self) -> None:
        shared_key = os.urandom(32)
        ns1 = EncryptedRedisDict(namespace=TEST_NAMESPACE, key=shared_key)
        ns2 = EncryptedRedisDict(namespace=f"{TEST_NAMESPACE}_other", key=shared_key)

        ns1["alice_is_admin"] = True
        ns1["bob_is_admin"] = False

        alice_ciphertext = ns1.get_redis.get(ns1._format_key("alice_is_admin"))
        assert alice_ciphertext is not None

        # Copying Alice's valid ciphertext onto Bob's key in the same namespace must fail AAD check
        ns1.get_redis.set(ns1._format_key("bob_is_admin"), alice_ciphertext)
        with self.assertRaises(RedisDictDecryptionError):
            _ = ns1["bob_is_admin"]

        # Copying Alice's valid ciphertext onto the same key name in another namespace must fail AAD check
        ns2.get_redis.set(ns2._format_key("alice_is_admin"), alice_ciphertext)
        with self.assertRaises(RedisDictDecryptionError):
            _ = ns2["alice_is_admin"]

    def test_multi_key_rotation_and_ttl_preservation(self) -> None:
        old_key = generate_key()
        new_key = generate_key()

        # Phase 1: Write data under old_key ("k1"), including a key with TTL
        os.environ["REDIS_DICT_AES_KEYS"] = f"k1:{old_key}"
        d_old = EncryptedRedisDict(namespace=TEST_NAMESPACE)
        d_old["permanent"] = {"v": 1}
        with d_old.expire_at(120):
            d_old["expiring"] = "ephemeral-secret"

        raw_before = d_old.get_redis.get(d_old._format_key("permanent"))
        assert raw_before is not None
        self.assertTrue(raw_before.startswith("__enc__:v1$k1$"))

        # Phase 2: Add new_key ("k2") as primary while retaining "k1" for reads
        os.environ["REDIS_DICT_AES_KEYS"] = f"k2:{new_key},k1:{old_key}"
        d_rotating = EncryptedRedisDict(namespace=TEST_NAMESPACE)
        self.assertEqual(d_rotating["permanent"], {"v": 1})
        self.assertEqual(d_rotating["expiring"], "ephemeral-secret")
        d_rotating["fresh"] = "written-with-k2"

        rotated_count = d_rotating.rotate_keys()
        self.assertEqual(rotated_count, 2)
        # Running rotate_keys() again is a no-op because all keys now use "k2"
        self.assertEqual(d_rotating.rotate_keys(), 0)

        ttl_remaining = d_rotating.get_ttl("expiring")
        self.assertIsNotNone(ttl_remaining)
        assert ttl_remaining is not None
        self.assertGreater(ttl_remaining, 60)
        self.assertIsNone(d_rotating.get_ttl("permanent"))

        # Phase 3: Retire old_key completely; all keys remain readable under new_key alone
        os.environ.pop("REDIS_DICT_AES_KEYS", None)
        d_new_only = EncryptedRedisDict(namespace=TEST_NAMESPACE, keys={"k2": new_key}, primary_key_id="k2")
        self.assertEqual(d_new_only["permanent"], {"v": 1})
        self.assertEqual(d_new_only["expiring"], "ephemeral-secret")
        self.assertEqual(d_new_only["fresh"], "written-with-k2")

    def test_key_validation_and_secret_redaction(self) -> None:
        with self.assertRaises(ValueError):
            AESGCMCipher(key="")
        with self.assertRaises(ValueError):
            AESGCMCipher(key=b"")
        with self.assertRaises(ValueError):
            AESGCMCipher(keys={"invalid$id": os.urandom(32)})
        with self.assertRaises(ValueError):
            AESGCMCipher(keys={"k1": os.urandom(32)}, primary_key_id="missing")

        secret_b64 = generate_key()
        cipher = AESGCMCipher(key=secret_b64)
        self.assertNotIn(secret_b64, repr(cipher))
        self.assertNotIn(secret_b64, str(cipher))
        self.assertIn("default", repr(cipher))

    def test_missing_cryptography_raises_helpful_import_error_only_on_crypto_use(self) -> None:
        with patch.dict(
            sys.modules,
            {
                "cryptography": None,
                "cryptography.exceptions": None,
                "cryptography.hazmat": None,
                "cryptography.hazmat.primitives": None,
                "cryptography.hazmat.primitives.ciphers": None,
                "cryptography.hazmat.primitives.ciphers.aead": None,
                "cryptography.hazmat.primitives.kdf": None,
                "cryptography.hazmat.primitives.kdf.scrypt": None,
            },
        ):
            # Plain RedisDict continues working without cryptography installed
            plain = RedisDict(namespace=f"{TEST_NAMESPACE}_plain")
            plain["ok"] = 123
            self.assertEqual(plain["ok"], 123)

            with self.assertRaisesRegex(ImportError, r"redis-dict\[crypto\]"):
                AESGCMCipher(key=os.urandom(32))
            with self.assertRaisesRegex(ImportError, r"redis-dict\[crypto\]"):
                EncryptedRedisDict(namespace=TEST_NAMESPACE, key=os.urandom(32))


if __name__ == "__main__":
    unittest.main()
