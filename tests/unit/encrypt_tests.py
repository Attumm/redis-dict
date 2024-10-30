import os

import base64
import unittest

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from redis_dict import RedisDict


class EncryptedStringClassBased(str):
    """A class that behaves like a string but enables encrypted storage in Redis dictionaries.

    This class inherits from the built-in str class, providing all standard string
    functionality. However, when stored in a RedisDict, it is automatically
    encrypted. This allows for transparent encryption of sensitive data in Redis
    without changing how the string is used in your Python code.

    The class uses AES encryption with Galois/Counter Mode (GCM) for secure
    encryption and decryption. It is designed for testing purposes
    the use of proper encryption techniques, including initialization vectors (IV)
    and nonces.

    Attributes:
        nonce (bytes): A class-level attribute representing the nonce used for encryption.
        iv (bytes): The initialization vector, retrieved from an environment variable.
        key (bytes): The encryption key, retrieved from an environment variable.

    Note:
    While this class uses actual encryption for testing, in real-world applications,
    more robust key management and security practices should be implemented. Never
    use hardcoded nonces or store encryption keys in environment variables without
    proper security measures in production environments.
    """
    nonce = b"0123456789abcdef"

    def __init__(self, value: str):
        self.value = value
        self.iv = base64.b64decode(os.environ['ENCRYPTION_IV'])
        self.key = base64.b64decode(os.environ['ENCRYPTION_KEY'])

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"EncryptedStringClassBased('{self.value}')"

    def encode(self) -> str:
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(self.nonce), backend=default_backend())
        encryptor = cipher.encryptor()

        encrypted_data = encryptor.update(self.value.encode('utf-8', errors='surrogatepass')) + encryptor.finalize()
        return str(base64.b64encode(self.iv + self.nonce + encryptor.tag + encrypted_data).decode('utf-8'))

    @classmethod
    def decode(cls, encrypted_value: str) -> 'EncryptedStringClassBased':
        iv = base64.b64decode(os.environ['ENCRYPTION_IV'])
        key = base64.b64decode(os.environ['ENCRYPTION_KEY'])
        nonce = cls.nonce

        encrypted_data = base64.b64decode(encrypted_value)
        tag = encrypted_data[len(iv) + len(nonce):len(iv) + len(nonce) + 16]
        ciphertext = encrypted_data[len(iv) + len(nonce) + 16:]

        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
        decryptor = cipher.decryptor()

        decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
        return cls(decrypted_data.decode('utf-8', errors='surrogatepass'))


class TestRedisDictEncryptionClassBased(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        iv = b"0123456789abcdef"  # 16 bytes
        key = b"0123456789abcdef0123456789abcdef"  # 32 bytes (256-bit key)

        # Set test environment variables
        os.environ['ENCRYPTION_IV'] = base64.b64encode(iv).decode('utf-8')
        os.environ['ENCRYPTION_KEY'] = base64.b64encode(key).decode('utf-8')

        cls.original_env = {
            'ENCRYPTION_IV':  os.environ['ENCRYPTION_IV'],
            'ENCRYPTION_KEY': os.environ['ENCRYPTION_KEY'],
        }

    def setUp(self):

        self.redis_dict = RedisDict()
        self.redis_dict.extends_type(EncryptedStringClassBased)

    def tearDown(self):
        self.redis_dict.clear()

    def helper_get_redis_internal_value(self, key):
        sep = ":"
        redis_dict = self.redis_dict

        stored_in_redis_as = redis_dict.redis.get(redis_dict._format_key(key))
        internal_result_type, internal_result_value = stored_in_redis_as.split(sep, 1)
        return internal_result_type, internal_result_value

    def test_encrypted_string_encoding_and_decoding(self):
        """Test adding new type and test if encoding and decoding works."""
        redis_dict = self.redis_dict

        iv = base64.b64decode(os.environ['ENCRYPTION_IV'])
        key = base64.b64decode(os.environ['ENCRYPTION_KEY'])

        encode_encrypted_function = encode_encrypted_string(iv, key, EncryptedStringClassBased.nonce)

        redis_dict.extends_type(EncryptedStringClassBased)
        key = "foo"
        expected_type = EncryptedStringClassBased.__name__
        expected = "foobar"
        encoded_expected = encode_encrypted_function(expected)

        redis_dict[key] = EncryptedStringClassBased(expected)

        # Should be stored encrypted
        internal_result_type, internal_result_value = self.helper_get_redis_internal_value(key)
        self.assertNotEqual(internal_result_value, expected)

        self.assertEqual(internal_result_type, expected_type)
        self.assertEqual(internal_result_value, encoded_expected)

        result = redis_dict[key]

        self.assertNotEqual(encoded_expected, expected)
        self.assertIsInstance(result, EncryptedStringClassBased)
        self.assertEqual(result, expected)

    def test_encoding_decoding_should_remain_equal(self):
        """Test adding new type and test if encoding and decoding results in the same value"""
        redis_dict = self.redis_dict

        key = "foo"
        key2 = "bar"
        expected = "foobar"

        redis_dict[key] = EncryptedStringClassBased(expected)

        redis_dict[key2] = redis_dict[key]

        result_one = redis_dict[key]
        result_two = redis_dict[key2]

        self.assertEqual(result_one, EncryptedStringClassBased(expected))
        self.assertEqual(result_one, result_two)

        self.assertEqual(result_one, expected)

    def test_values(self):
        """Test different values"""
        redis_dict = self.redis_dict
        expected_internal_type = EncryptedStringClassBased.__name__
        test_cases = {
            "Empty string": "",
            "Single space": " ",
            "Multiple spaces": "   ",
            "Various whitespace characters": "\t\n\r",
            "Single character": "a",
            "Two characters": "ab",
            "Three characters": "abc",
            "Normal string with punctuation": "Hello, World!",
            "Numeric string": "1234567890",
            "Special characters": "!@#$%^&*()_+-=[]{}|;:,.<>?",
            "Non-ASCII characters": "äöüßÄÖÜ",
            "Emoji": "😀🙈🚀",
            "Long string (1000 'a' characters)": "a" * 1000,
            "Very long text (Lorem ipsum)": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 100,
            "JSON-like string": '{"key": "value"}',
            "HTML-like string": "<html><body>Test</body></html>",
            "SQL-like string": "SELECT * FROM users;",
            "URL-like string": "https://www.example.com/path?query=value",
            "String with null byte": "prefix\0suffix",
            "String with low ASCII characters": "\u0000\u0001\u0002\u0003",
            "String with high Unicode character (U+FFFF)": "\uFFFF",
            "Surrogate pair (Unicode smiley face)": "\uD83D\uDE00",
            "Mathematical script letters": "𝔘𝔫𝔦𝔠𝔬𝔡𝔢",
            "Chinese characters": "中文字符测试",
            "Japanese Hiragana": "こんにちは",
            "Korean Hangul": "한글 테스트",
            "String with right-to-left override character": "\u202Eexample",
            "String with escaped newlines and tabs": "\\n\\t\\r",
            "String with double quotes": "\"quoted\"",
            "String with single quotes": "'single quotes'",
            "String with backslash": "back\\slash",
            "Windows file path": "C:\\Program Files\\",
            "Unix file path": "/usr/local/bin/",
            "Decimal number string": "3.14159",
            "Negative decimal number string": "-273.15",
            "Scientific notation string": "1e10",
            "Not-a-Number (NaN) string": "NaN",
            "Infinity string": "Infinity",
            "String with byte values (0x00 and 0xFF)": "\x00\xFF",
            "Octal number string": "01234567",
            "Hexadecimal string": "0xDEADBEEF",
            "Null-like string": "null",
            "Undefined-like string": "undefined",
            "Boolean true string": "true",
            "Boolean false string": "false",
            "String with Python-like code": "import os\nos.system('echo Hello')",
            "String with a print statement": "print('Hello')",
            "Very long string (10,000 'a' characters)": "a" * 10000,
        }

        for test_num, (test_name, expected) in enumerate(test_cases.items()):
            key = f"test_{test_num+1}"
            redis_dict[key] = EncryptedStringClassBased(expected)
            result = redis_dict[key]
            # Assert result is same as the expected input value
            self.assertEqual(result, expected, f"testcase {test_num+1} failed {test_name}")

            # Assert that the value internally stored in Redis is encoded, and the type is correct.
            internal_result_type, internal_result_value = self.helper_get_redis_internal_value(key)

            self.assertNotEqual(internal_result_value, expected, f"testcase {test_num+1} failed")
            self.assertNotEqual(internal_result_value, expected, f"testcase {test_num+1} failed")
            self.assertEqual(internal_result_type, expected_internal_type, f"testcase {test_num+1} failed")


class EncryptedString(str):
    """
    A class that behaves exactly like a string but has a distinct type for redis-dict encoding and decoding.

    This class inherits from the built-in str class, automatically providing all
    string functionality. The only difference is its class name, which allows for
    type checking of "encrypted" strings. Used to encode and decode for storage.

    Usage:
    >>> normal_string = "Hello, World!"
    >>> encrypted_string = EncryptedString("Hello, World!")
    >>> assert normal_string == encrypted_string
    >>> assert type(encrypted_string) == EncryptedString
    >>> assert isinstance(encrypted_string, str)
    """
    pass

def encode(value: str, iv: bytes, key: bytes, nonce: bytes) -> str:
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()

    encrypted_data = encryptor.update(value.encode('utf-8', errors='surrogatepass')) + encryptor.finalize()
    return base64.b64encode(iv + nonce + encryptor.tag + encrypted_data).decode('utf-8')


def decode(encrypted_value: str, iv: bytes, key: bytes, nonce: bytes) -> str:
    encrypted_data = base64.b64decode(encrypted_value)
    tag = encrypted_data[len(iv) + len(nonce):len(iv) + len(nonce) + 16]
    ciphertext = encrypted_data[len(iv) + len(nonce) + 16:]

    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
    decryptor = cipher.decryptor()

    decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
    return decrypted_data.decode('utf-8', errors='surrogatepass')


def encode_encrypted_string(iv, key, nonce):
    def encode_value(value):
        return encode(value, iv, key, nonce)
    return encode_value


def decode_encrypted_string(iv, key, nonce):
    def decode_value(value):
        return EncryptedString(decode(value, iv, key, nonce))
    return decode_value


class TestRedisDictEncryption(unittest.TestCase):
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

    def helper_get_redis_internal_value(self, key):
        sep = ":"
        redis_dict = self.redis_dict

        stored_in_redis_as = redis_dict.redis.get(redis_dict._format_key(key))
        internal_result_type, internal_result_value = stored_in_redis_as.split(sep, 1)
        return internal_result_type, internal_result_value

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

        # Should be stored encrypted
        internal_result_type, internal_result_value = self.helper_get_redis_internal_value(key)
        self.assertNotEqual(internal_result_value, expected)

        self.assertEqual(internal_result_type, expected_type)
        self.assertEqual(internal_result_value, encoded_expected)

        result = redis_dict[key]

        self.assertNotEqual(encoded_expected, expected)
        self.assertIsInstance(result, EncryptedString)
        self.assertEqual(result, expected)

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

        self.assertEqual(result_one, expected)

    def test_values(self):
        """Test different values"""
        redis_dict = self.redis_dict
        expected_internal_type = EncryptedString.__name__
        test_cases = {
            "Empty string": "",
            "Single space": " ",
            "Multiple spaces": "   ",
            "Various whitespace characters": "\t\n\r",
            "Single character": "a",
            "Two characters": "ab",
            "Three characters": "abc",
            "Normal string with punctuation": "Hello, World!",
            "Numeric string": "1234567890",
            "Special characters": "!@#$%^&*()_+-=[]{}|;:,.<>?",
            "Non-ASCII characters": "äöüßÄÖÜ",
            "Emoji": "😀🙈🚀",
            "Long string (1000 'a' characters)": "a" * 1000,
            "Very long text (Lorem ipsum)": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 100,
            "JSON-like string": '{"key": "value"}',
            "HTML-like string": "<html><body>Test</body></html>",
            "SQL-like string": "SELECT * FROM users;",
            "URL-like string": "https://www.example.com/path?query=value",
            "String with null byte": "prefix\0suffix",
            "String with low ASCII characters": "\u0000\u0001\u0002\u0003",
            "String with high Unicode character (U+FFFF)": "\uFFFF",
            "Surrogate pair (Unicode smiley face)": "\uD83D\uDE00",
            "Mathematical script letters": "𝔘𝔫𝔦𝔠𝔬𝔡𝔢",
            "Chinese characters": "中文字符测试",
            "Japanese Hiragana": "こんにちは",
            "Korean Hangul": "한글 테스트",
            "String with right-to-left override character": "\u202Eexample",
            "String with escaped newlines and tabs": "\\n\\t\\r",
            "String with double quotes": "\"quoted\"",
            "String with single quotes": "'single quotes'",
            "String with backslash": "back\\slash",
            "Windows file path": "C:\\Program Files\\",
            "Unix file path": "/usr/local/bin/",
            "Decimal number string": "3.14159",
            "Negative decimal number string": "-273.15",
            "Scientific notation string": "1e10",
            "Not-a-Number (NaN) string": "NaN",
            "Infinity string": "Infinity",
            "String with byte values (0x00 and 0xFF)": "\x00\xFF",
            "Octal number string": "01234567",
            "Hexadecimal string": "0xDEADBEEF",
            "Null-like string": "null",
            "Undefined-like string": "undefined",
            "Boolean true string": "true",
            "Boolean false string": "false",
            "String with Python-like code": "import os\nos.system('echo Hello')",
            "String with a print statement": "print('Hello')",
            "Very long string (10,000 'a' characters)": "a" * 10000,
        }

        for test_num, (test_name, expected) in enumerate(test_cases.items()):
            key = f"test_{test_num+1}"
            redis_dict[key] = EncryptedString(expected)
            result = redis_dict[key]
            # Assert result is same as the expected input value
            self.assertEqual(result, expected, f"testcase {test_num + 1} failed {test_name}")

            # Assert that the value internally stored in Redis is encoded, and the type is correct.
            internal_result_type, internal_result_value = self.helper_get_redis_internal_value(key)
            self.assertNotEqual(internal_result_value, expected, f"testcase {test_num+1} failed")
            self.assertNotEqual(internal_result_value, expected, f"testcase {test_num+1} failed")
            self.assertEqual(internal_result_type, expected_internal_type, f"testcase {test_num+1} failed")




if __name__ == '__main__':
    unittest.main()
