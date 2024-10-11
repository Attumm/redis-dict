import unittest
from redis_dict import RedisDict


def rot13(s):
    return ''.join([chr((ord(c) - 97 + 13) % 26 + 97) if c.isalpha() else c for c in s.lower()])

def rot13_encode(encrypted_string):
    return rot13(encrypted_string.value)


def rot13_decode(s):
    return EncryptedString(rot13(s))  # ROT13 is its own inverse


class EncryptedString:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        return self.value

    def __class__(self):
        return "EncryptedString"

    def __repr__(self):
        return f"EncryptedString({self.value})"


class TestRedisDict(unittest.TestCase):
    def setUp(self):
        self.redis_dict = RedisDict()

    def test_encrypted_string_storage_and_retrieval(self):
        """Test storing and retrieving an EncryptedString."""
        redis_dict = RedisDict()
        redis_dict.extends_type(EncryptedString, rot13_encode, rot13_decode)
        key = "foo"
        expected_type = EncryptedString.__name__
        expected = "foobar"
        encoded_expected = rot13(expected)

        redis_dict[key] = EncryptedString(expected)

        stored_in_redis_as = redis_dict.redis.get(redis_dict._format_key(key))
        internal_result_type, internal_result_value = stored_in_redis_as.split(":", 1)
        self.assertEqual(internal_result_type, expected_type)
        self.assertEqual(internal_result_value, encoded_expected)


        result = redis_dict[key]
        self.assertNotEqual(encoded_expected, expected)

        self.assertIsInstance(result, EncryptedString)

        self.assertEqual(result.value, expected)

if __name__ == '__main__':
    unittest.main()
