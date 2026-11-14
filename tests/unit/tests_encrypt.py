import base64
from collections import OrderedDict, defaultdict
from datetime import date, datetime, time as dt_time, timedelta, timezone
from decimal import Decimal
import importlib
import json
import os
import sys
import unittest
from unittest.mock import patch
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import redis

from redis_dict import EncryptedRedisDict, RedisDict


class _Person:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    def encode(self) -> str:
        return json.dumps({"name": self.name, "age": self.age})

    @classmethod
    def decode(cls, raw: str) -> "_Person":
        data = json.loads(raw)
        return cls(data["name"], data["age"])

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Person) and (self.name, self.age) == (other.name, other.age)


class TestEncryptedRedisDictUnit(unittest.TestCase):
    NAMESPACE = "__test_encrypted_dict__"
    OTHER_NS = "__test_encrypted_dict_other__"

    def setUp(self) -> None:
        RedisDict(namespace=self.NAMESPACE).clear()
        RedisDict(namespace=self.OTHER_NS).clear()

    def tearDown(self) -> None:
        RedisDict(namespace=self.NAMESPACE).clear()
        RedisDict(namespace=self.OTHER_NS).clear()

    def test_key_validation(self) -> None:
        with self.assertRaises(TypeError):
            EncryptedRedisDict(namespace=self.NAMESPACE)  # type: ignore[call-arg]
        with self.assertRaises(TypeError):
            EncryptedRedisDict(namespace=self.NAMESPACE, key=None)  # type: ignore[arg-type]

        for bad_key in ("a" * 32, 123):
            with self.assertRaises(TypeError):
                EncryptedRedisDict(namespace=self.NAMESPACE, key=bad_key)  # type: ignore[arg-type]

        for bad_len in (0, 1, 15, 17, 23, 25, 31, 33, 64):
            with self.assertRaises(ValueError):
                EncryptedRedisDict(namespace=self.NAMESPACE, key=b"k" * bad_len)

        for bit_length in (128, 192, 256):
            key = AESGCM.generate_key(bit_length=bit_length)
            dic = EncryptedRedisDict(self.NAMESPACE, expire=60, key=key)
            dic["check"] = bit_length
            self.assertEqual(dic["check"], bit_length)

    def test_ciphertext_at_rest_fresh_nonce_and_all_types(self) -> None:
        key = AESGCM.generate_key(bit_length=256)
        raw_client = redis.StrictRedis(host="localhost", port=6379, decode_responses=True)
        dic = EncryptedRedisDict(namespace=self.NAMESPACE, key=key)
        dic.extends_type(_Person)

        samples = {
            "secret": "a secret message",
            "int": -42,
            "float": 3.14159,
            "bool": True,
            "none": None,
            "bytes": b"\x00\xffhello",
            "decimal": Decimal("12345.6789"),
            "complex": complex(2.5, -3.5),
            "uuid": UUID("12345678-1234-5678-1234-567812345678"),
            "dt": datetime(2026, 11, 14, 8, 0, 0, tzinfo=timezone.utc),
            "date": date(2026, 11, 14),
            "time": dt_time(8, 30, 15),
            "td": timedelta(days=2, seconds=45),
            "tuple": (1, "two", b"three"),
            "set": {"alpha", "beta"},
            "frozenset": frozenset([10, 20]),
            "od": OrderedDict([("first", 1), ("second", 2)]),
            "dd": defaultdict(type(None), {"k": "v"}),
            "nested": [OrderedDict([("a", 1)]), {"x": (1, {2}), 3: b"\x00\xff"}],
            "person": _Person("Alice", 31),
        }

        with dic.pipeline():
            for k, val in samples.items():
                dic[k] = val

        for k, expected in samples.items():
            stored = raw_client.get(dic._format_key(k))
            self.assertIsInstance(stored, str)
            decoded_raw = base64.b64decode(str(stored), validate=True)
            self.assertGreaterEqual(len(decoded_raw), 28)
            self.assertNotIn(":", str(stored))
            self.assertEqual(dic[k], expected)

        first_stored = raw_client.get(dic._format_key("secret"))
        dic["secret"] = "a secret message"
        second_stored = raw_client.get(dic._format_key("secret"))
        self.assertNotEqual(first_stored, second_stored)
        self.assertEqual(dic["secret"], "a secret message")
        raw_client.close()

    def test_tampering_malleability_and_wrong_key_rejected(self) -> None:
        key_a = AESGCM.generate_key(bit_length=256)
        key_b = AESGCM.generate_key(bit_length=256)
        dic_a = EncryptedRedisDict(namespace=self.NAMESPACE, key=key_a)
        dic_b = EncryptedRedisDict(namespace=self.NAMESPACE, key=key_b)

        dic_a["item"] = "sensitive-value"
        with self.assertRaises(InvalidTag):
            _ = dic_b["item"]

        redis_key = dic_a._format_key("item")
        orig_b64 = str(dic_a.redis.get(redis_key))
        orig_bytes = base64.b64decode(orig_b64, validate=True)

        # Non-Base64 prefix / non-ASCII payloads must fail strict Base64 validation
        for bad_b64 in ("!@#:" + orig_b64, "str:plaintext-in-redis", "ä" * 40):
            dic_a.redis.set(redis_key, bad_b64)
            with self.assertRaises(ValueError):
                _ = dic_a["item"]

        # Bit-flip in nonce (0), ciphertext (12), or GCM auth tag (-1) must fail authentication
        for idx in (0, 12, -1):
            tampered = bytearray(orig_bytes)
            tampered[idx] ^= 0x01
            dic_a.redis.set(redis_key, base64.b64encode(bytes(tampered)).decode("ascii"))
            with self.assertRaises(InvalidTag):
                _ = dic_a["item"]

        # Truncated payloads (< 28 bytes) must always fail with InvalidTag
        for length in range(len(orig_bytes)):
            dic_a.redis.set(redis_key, base64.b64encode(orig_bytes[:length]).decode("ascii"))
            with self.assertRaises(InvalidTag):
                _ = dic_a["item"]

        # Cross-namespace ciphertext copy under the same key must fail authentication
        same_key_other_ns = EncryptedRedisDict(namespace=self.OTHER_NS, key=key_a)
        dic_a.redis.set(same_key_other_ns._format_key("item"), orig_b64)
        with self.assertRaises(InvalidTag):
            _ = same_key_other_ns["item"]

        # Encrypted non-UTF-8 bytes and lone surrogates must fail UTF-8 encoding/decoding
        bad_utf8_ct = AESGCM(key_a).encrypt(b"\x01" * 12, b"\xff\xfe", self.NAMESPACE.encode("utf-8"))
        dic_a.redis.set(redis_key, base64.b64encode(b"\x01" * 12 + bad_utf8_ct).decode("ascii"))
        with self.assertRaises(UnicodeDecodeError):
            _ = dic_a["item"]

        with self.assertRaises(UnicodeEncodeError):
            dic_a["surrogate"] = "lead-\ud800-trail"

    def test_scrypt_persistence_across_deployments_and_key_rotation(self) -> None:
        # Provisioning (done ONCE before first deployment and saved in secret manager / config):
        secret_store = {
            "APP_SECRET_PASSPHRASE": "production-passphrase",
            "APP_SCRYPT_SALT_HEX": os.urandom(16).hex(),
            "APP_RAW_KEY_B64": base64.b64encode(AESGCM.generate_key(bit_length=256)).decode("ascii"),
        }

        def derive_from_config(passphrase: str, salt_hex: str) -> bytes:
            return Scrypt(
                salt=bytes.fromhex(salt_hex),
                length=32,
                n=2**14,
                r=8,
                p=1,
            ).derive(passphrase.encode("utf-8"))

        # 1. Scrypt across deployments: persisting salt + passphrase preserves access on restart
        deploy_1_key = derive_from_config(secret_store["APP_SECRET_PASSPHRASE"], secret_store["APP_SCRYPT_SALT_HEX"])
        deploy_1_vault = EncryptedRedisDict(namespace=self.NAMESPACE, key=deploy_1_key)
        deploy_1_vault["account"] = {"user": "alice", "balance": Decimal("250.75")}
        deploy_1_vault["token"] = "derived-secret"
        del deploy_1_vault, deploy_1_key

        deploy_2_key = derive_from_config(secret_store["APP_SECRET_PASSPHRASE"], secret_store["APP_SCRYPT_SALT_HEX"])
        deploy_2_vault = EncryptedRedisDict(namespace=self.NAMESPACE, key=deploy_2_key)
        self.assertEqual(deploy_2_vault["account"], {"user": "alice", "balance": Decimal("250.75")})
        self.assertEqual(deploy_2_vault["token"], "derived-secret")

        # Trap: regenerating a new random salt on deploy (even with the SAME passphrase) locks you out!
        unpersisted_salt_key = derive_from_config(secret_store["APP_SECRET_PASSPHRASE"], os.urandom(16).hex())
        with self.assertRaises(InvalidTag):
            _ = EncryptedRedisDict(namespace=self.NAMESPACE, key=unpersisted_salt_key)["account"]

        # Trap: wrong passphrase with the persisted salt also fails authentication
        wrong_passphrase_key = derive_from_config("wrong-passphrase", secret_store["APP_SCRYPT_SALT_HEX"])
        with self.assertRaises(InvalidTag):
            _ = EncryptedRedisDict(namespace=self.NAMESPACE, key=wrong_passphrase_key)["account"]

        # 2. Raw AES key persisted as Base64 in secret manager across deployments
        raw_deploy_1 = EncryptedRedisDict(
            namespace=self.OTHER_NS,
            key=base64.b64decode(secret_store["APP_RAW_KEY_B64"]),
        )
        raw_deploy_1["session"] = {"uid": 7, "active": True}
        del raw_deploy_1

        raw_deploy_2 = EncryptedRedisDict(
            namespace=self.OTHER_NS,
            key=base64.b64decode(secret_store["APP_RAW_KEY_B64"]),
        )
        self.assertEqual(raw_deploy_2["session"], {"uid": 7, "active": True})

        # Trap: calling AESGCM.generate_key() again on restart instead of loading persisted key locks you out!
        with self.assertRaises(InvalidTag):
            _ = EncryptedRedisDict(namespace=self.OTHER_NS, key=AESGCM.generate_key(bit_length=256))["session"]

        # 3. Planned key rotation across deployments without losing existing data (old_key -> new_key)
        new_key = derive_from_config("rotated-passphrase", os.urandom(16).hex())
        rotated_vault = EncryptedRedisDict(namespace=self.NAMESPACE, key=new_key)
        rotated_vault.update(deploy_2_vault.to_dict())
        del deploy_2_vault, rotated_vault

        deploy_3_vault = EncryptedRedisDict(namespace=self.NAMESPACE, key=new_key)
        self.assertEqual(deploy_3_vault["account"], {"user": "alice", "balance": Decimal("250.75")})
        self.assertEqual(deploy_3_vault["token"], "derived-secret")
        with self.assertRaises(InvalidTag):
            _ = EncryptedRedisDict(namespace=self.NAMESPACE, key=deploy_2_key)["account"]

    def test_optional_dependency_import_guard(self) -> None:
        saved_pkg = sys.modules.pop("redis_dict", None)
        saved_enc = sys.modules.pop("redis_dict.encrypted_dict", None)
        try:
            with patch.dict(
                sys.modules,
                {
                    "cryptography": None,
                    "cryptography.hazmat": None,
                    "cryptography.hazmat.primitives": None,
                    "cryptography.hazmat.primitives.ciphers": None,
                    "cryptography.hazmat.primitives.ciphers.aead": None,
                },
            ):
                pkg = importlib.import_module("redis_dict")
                self.assertFalse(hasattr(pkg, "EncryptedRedisDict"))
                self.assertNotIn("EncryptedRedisDict", pkg.__all__)
                for export_name in pkg.__all__:
                    self.assertTrue(hasattr(pkg, export_name))
                self.assertIsNotNone(pkg.RedisDict)
                with self.assertRaises(ImportError):
                    importlib.import_module("redis_dict.encrypted_dict")
        finally:
            if saved_enc is not None:
                sys.modules["redis_dict.encrypted_dict"] = saved_enc
            if saved_pkg is not None:
                sys.modules["redis_dict"] = saved_pkg


if __name__ == "__main__":
    unittest.main()
