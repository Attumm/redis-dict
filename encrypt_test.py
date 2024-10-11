import unittest
import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from redis_dict import RedisDict


class EncryptedString:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        return self.value

    def __class__(self):
        return "EncryptedString"

    def __repr__(self):
        return f"EncryptedString({self.value})"

    def __eq__(self, other):
        return self.value == other.value


def encode(value: str, iv: bytes, key: bytes, nonce: bytes) -> str:
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(value.encode('utf-8')) + encryptor.finalize()
    return base64.b64encode(iv + nonce + encryptor.tag + encrypted_data).decode('utf-8')


def decode(encrypted_value: str, iv: bytes, key: bytes, nonce: bytes) -> str:
    encrypted_data = base64.b64decode(encrypted_value)
    tag = encrypted_data[len(iv) + len(nonce):len(iv) + len(nonce) + 16]
    ciphertext = encrypted_data[len(iv) + len(nonce) + 16:]

    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
    decryptor = cipher.decryptor()

    decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
    return decrypted_data.decode('utf-8')


def encode_encrypted_string(iv, key, nonce):
    def encode_value(value):
        if isinstance(value, EncryptedString):
            value = value.value
        return encode(value, iv, key, nonce)
    return encode_value


def decode_encrypted_string(iv, key, nonce):
    def decode_value(value):
        return EncryptedString(decode(value, iv, key, nonce))
    return decode_value


class TestRedisDict(unittest.TestCase):
    def setUp(self):
        self.redis_dict = RedisDict()

        iv = b"0123456789abcdef"  # 16 bytes
        key = b"0123456789abcdef0123456789abcdef"  # 32 bytes (256-bit key)
        nonce = b"0123456789abcdef"  # 16 bytes

        encode_encrypted = encode_encrypted_string(iv, key, nonce)
        decode_encrypted = decode_encrypted_string(iv, key, nonce)

        self.redis_dict.extends_type(
            EncryptedString,
            encode_encrypted,
            decode_encrypted,
        )

    def tearDown(self):
        self.redis_dict.clear()

    def test_encrypted_string_encoding_and_decoding(self):
        """Test adding new type and test if encoding and decoding works."""
        redis_dict = self.redis_dict

        iv = b"0123456789abcdef"  # 16 bytes
        key = b"0123456789abcdef0123456789abcdef"  # 32 bytes (256-bit key)
        nonce = b"0123456789abcdef"  # 16 bytes

        encode_encrypted = encode_encrypted_string(iv, key, nonce)
        decode_encrypted = decode_encrypted_string(iv, key, nonce)

        redis_dict.extends_type(EncryptedString,
                                encode_encrypted,
                                decode_encrypted,
                                )
        key = "foo"
        expected_type = EncryptedString.__name__
        expected = "foobar"
        encoded_expected = encode_encrypted(expected)

        redis_dict[key] = EncryptedString(expected)

        stored_in_redis_as = redis_dict.redis.get(redis_dict._format_key(key))

        internal_result_type, internal_result_value = stored_in_redis_as.split(":", 1)

        # Should be stored encrypted
        self.assertNotEqual(internal_result_value, expected)

        self.assertEqual(internal_result_type, expected_type)
        self.assertEqual(internal_result_value, encoded_expected)

        result = redis_dict[key]

        self.assertNotEqual(encoded_expected, expected)
        self.assertIsInstance(result, EncryptedString)
        self.assertEqual(result.value, expected)

    def test_encoding_decoding_should_remain_equal(self):
        """Test adding new type and test if encoding and decoding results in the same value"""
        redis_dict = self.redis_dict

        key = "foo"
        key2 = "bar"
        expected = "foobar"

        redis_dict[key] = EncryptedString(expected)

        redis_dict[key2] = redis_dict[key]

        result_one = redis_dict[key]
        result_two = redis_dict[key2]

        self.assertEqual(result_one, EncryptedString(expected))
        self.assertEqual(result_one, result_two)

        result_str = result_two.value
        self.assertEqual(result_str, expected)

    def test_values(self):
        """Test different values"""
        redis_dict = self.redis_dict
        expected_internal_type = EncryptedString.__name__
        test_cases = [
            "",  # Empty string
            " ",  # Single space
            "   ",  # Multiple spaces
            "\t\n\r",  # Various whitespace characters
            "a",  # Single character
            "ab",  # Two characters
            "abc",  # Three characters
            "Hello, World!",  # Normal string with punctuation
            "1234567890",  # Numeric string
            "!@#$%^&*()_+-=[]{}|;:,.<>?",  # Special characters
            "äöüßÄÖÜ",  # Non-ASCII characters
            "😀🙈🚀",  # Emoji
            "a" * 1000,  # Long string
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 100,  # Very long text
            '{"key": "value"}',  # JSON-like string
            "<html><body>Test</body></html>",  # HTML-like string
            "SELECT * FROM users;",  # SQL-like string
            "https://www.example.com/path?query=value",  # URL-like string
            "prefix" + "\0" + "suffix",  # String with null byte
            "\u0000\u0001\u0002\u0003",  # String with low ASCII characters
        ]

        for test_num, expected in enumerate(test_cases):
            key = str(test_num)
            redis_dict[key] = EncryptedString(expected)
            result = redis_dict[key]
            self.assertEqual(result.value, expected)

            stored_in_redis_as = redis_dict.redis.get(redis_dict._format_key(key))
            internal_result_type, internal_result_value = stored_in_redis_as.split(":", 1)
            self.assertNotEqual(internal_result_value, expected)
            self.assertNotEqual(internal_result_value, expected)
            self.assertEqual(internal_result_type, expected_internal_type)


if __name__ == '__main__':
    unittest.main()
