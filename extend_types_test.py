import unittest
from redis_dict import RedisDict


def rot13(s):
    return ''.join([chr((ord(c) - 97 + 13) % 26 + 97) if c.isalpha() else c for c in s.lower()])


def rot13_encode(encrypted_string):
    return rot13(encrypted_string.value)


def rot13_decode(s):
    return EncryptedRot13String(rot13(s))


class EncryptedRot13String:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        return self.value

    def __class__(self):
        return "EncryptedRot13String"

    def __repr__(self):
        return f"EncryptedRot13String({self.value})"

    def __eq__(self, other):
        return self.value == other.value


class TestRedisDict(unittest.TestCase):
    def setUp(self):
        self.redis_dict = RedisDict()

    def tearDown(self):
        self.redis_dict.clear()

    def test_encrypted_string_encoding_and_decoding(self):
        """Test adding new type and test if encoding and decoding works."""
        redis_dict = self.redis_dict
        redis_dict.extends_type(EncryptedRot13String, rot13_encode, rot13_decode)
        key = "foo"
        expected_type = EncryptedRot13String.__name__
        expected = "foobar"
        encoded_expected = rot13(expected)

        redis_dict[key] = EncryptedRot13String(expected)

        stored_in_redis_as = redis_dict.redis.get(redis_dict._format_key(key))
        internal_result_type, internal_result_value = stored_in_redis_as.split(":", 1)
        self.assertEqual(internal_result_type, expected_type)
        self.assertEqual(internal_result_value, encoded_expected)

        result = redis_dict[key]

        self.assertNotEqual(encoded_expected, expected)
        self.assertIsInstance(result, EncryptedRot13String)
        self.assertEqual(result.value, expected)

    def test_encoding_decoding_should_remain_equal(self):
        """Test adding new type and test if encoding and decoding results in the same value"""
        redis_dict = RedisDict()
        redis_dict.extends_type(EncryptedRot13String, rot13_encode, rot13_decode)

        key = "foo"
        key2 = "bar"
        expected = "foobar"

        redis_dict[key] = EncryptedRot13String(expected)

        redis_dict[key2] = redis_dict[key]

        result_one = redis_dict[key]
        result_two = redis_dict[key2]

        self.assertEqual(result_one, EncryptedRot13String(expected))
        self.assertEqual(result_one, result_two)

        result_str = result_two.value
        self.assertEqual(result_str, expected)


if __name__ == '__main__':
    unittest.main()