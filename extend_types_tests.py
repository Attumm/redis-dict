import unittest
import json

from encrypt_tests import decode_encrypted_string
from redis_dict import RedisDict


class Person:
    def __init__(self, name, age, address):
        self.name = name
        self.age = age
        self.address = address

    def __eq__(self, other):
        if not isinstance(other, Person):
            return False
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return f"Person(name='{self.name}', age={self.age}, address='{self.address}')"


def person_encode(obj):
    return json.dumps(obj.__dict__)


def person_decode(json_str):
    return Person(**json.loads(json_str))


class TestRedisDictExtendTypes(unittest.TestCase):
    def setUp(self):
        self.redis_dict = RedisDict()
        self.redis_dict_seperator = ":"

    def tearDown(self):
        self.redis_dict.clear()

    def helper_get_redis_internal_value(self, key):
        sep = self.redis_dict_seperator
        redis_dict = self.redis_dict

        stored_in_redis_as = redis_dict.redis.get(redis_dict._format_key(key))
        internal_result_type, internal_result_value = stored_in_redis_as.split(sep, 1)
        return internal_result_type, internal_result_value

    def test_person_encoding_and_decoding(self):
        """Test adding Person type and test if encoding and decoding works."""
        redis_dict = self.redis_dict
        redis_dict.extends_type(Person, person_encode, person_decode)
        key = "person1"
        expected_type = Person.__name__
        expected_person = Person("John Doe", 30, "123 Main St")

        redis_dict[key] = expected_person

        internal_result_type, internal_result_value = self.helper_get_redis_internal_value(key)

        self.assertEqual(internal_result_type, expected_type)
        self.assertEqual(json.loads(internal_result_value), expected_person.__dict__)

        result = redis_dict[key]

        self.assertIsInstance(result, Person)
        self.assertEqual(result, expected_person)

    def test_person_encoding_decoding_should_remain_equal(self):
        """Test adding Person type and test if encoding and decoding results in the same value"""
        redis_dict = self.redis_dict
        redis_dict.extends_type(Person, person_encode, person_decode)

        key1 = "person1"
        key2 = "person2"
        expected_person = Person("Jane Smith", 25, "456 Elm St")

        redis_dict[key1] = expected_person
        redis_dict[key2] = redis_dict[key1]

        result_one = redis_dict[key1]
        result_two = redis_dict[key2]

        self.assertEqual(result_one, expected_person)
        self.assertEqual(result_one, result_two)

        self.assertEqual(result_two.name, expected_person.name)
        self.assertEqual(result_two.age, expected_person.age)
        self.assertEqual(result_two.address, expected_person.address)


#  Start test for simple encryption storing of data.


class EncryptedRot13String(str):
    """
    A class that behaves exactly like a string but has a distinct type for redis-dict encoding and decoding.

    This class will allow for encoding and decoding with ROT13. Demonstrating the serialization.
    https://en.wikipedia.org/wiki/ROT13

    This class inherits from the built-in str class, automatically providing all
    string functionality. The only difference is its class name, which allows for
    type checking of "EncryptedRot13String" strings. Used to encode and decode for storage.

    Usage:
    >>> normal_string = "Hello, World!"
    >>> encrypted_string = EncryptedRot13String("Hello, World!")
    >>> assert normal_string == encrypted_string
    >>> assert type(encrypted_string) == EncryptedRot13String
    >>> assert isinstance(encrypted_string, str)
    """
    pass


def rot13(s):
    """
    Applies the ROT13 substitution cipher to the input string.

    ROT13 is a simple letter substitution cipher that replaces a letter with
    the 13th letter after it in the alphabet. It's often described as the
    "bubble sort" of encryption due to its simplicity and reversibility.

    This implementation is for testing purposes and should not be used
    for actual data encryption.

    Example:
        >>> rot13("Hello, World!")
        "uryyb, jbeyq!"
        >>> rot13("uryyb, jbeyq!")
        "hello, world!"

    For more information:
        https://en.wikipedia.org/wiki/ROT13
    """
    return ''.join([chr((ord(c) - 97 + 13) % 26 + 97) if c.isalpha() else c for c in s.lower()])


def rot13_encode(encrypted_rot13_str: EncryptedRot13String):
    """
    Example of encoding function for redis-dict extended types.

    Encodes an EncryptedRot13String to encoded string for storage on redis.

    Converts the input to a string using ROT13 encoding.

    Args:
        encrypted_rot13_str (Any): The EncryptedRot13String to be encoded.

    Returns:
        str: The ROT13 encoded string representation of the input.

    """
    return rot13(encrypted_rot13_str)


def rot13_decode(encoded_string: str) -> 'EncryptedRot13String':
    """
    Example of decoding function for redis-dict extended types.

    Decodes a ROT13 encoded string back to an EncryptedRot13String object.

    It converts a ROT13 encoded string back to an EncryptedRot13String object.

    Args:
        encoded_string (str): The ROT13 encoded string to be decoded.

    Returns:
        EncryptedRot13String: An instance of EncryptedRot13String containing the decoded string.
    """
    decoded_string = rot13(encoded_string)
    return EncryptedRot13String(decoded_string)


class TestRedisDictExtendTypesEncodingDecoding(unittest.TestCase):
    def setUp(self):
        self.redis_dict = RedisDict()
        self.redis_dict_seperator = ":"

    def tearDown(self):
        self.redis_dict.clear()

    def helper_get_redis_internal_value(self, key):
        sep = self.redis_dict_seperator
        redis_dict = self.redis_dict

        stored_in_redis_as = redis_dict.redis.get(redis_dict._format_key(key))
        internal_result_type, internal_result_value = stored_in_redis_as.split(sep, 1)
        return internal_result_type, internal_result_value

    def test_encrypted_string_encoding_and_decoding(self):
        """Test adding new type and test if encoding and decoding works."""
        redis_dict = self.redis_dict
        redis_dict.extends_type(EncryptedRot13String, rot13_encode, rot13_decode)
        key = "foo"
        expected_type = EncryptedRot13String.__name__
        expected = "foobar"
        encoded_expected = rot13(expected)

        # Store string that should be encoded using Rot13
        redis_dict[key] = EncryptedRot13String(expected)

        # Assert the stored string is correctly stored encoded with Rot13
        internal_result_type, internal_result_value = self.helper_get_redis_internal_value(key)

        self.assertNotEqual(internal_result_value, expected)
        self.assertEqual(internal_result_type, expected_type)
        self.assertEqual(internal_result_value, encoded_expected)

        # Assert the result from getting the value is decoding correctly
        result = redis_dict[key]
        self.assertNotEqual(encoded_expected, expected)
        self.assertIsInstance(result, EncryptedRot13String)
        self.assertEqual(result, expected)

    def test_encoding_decoding_should_remain_equal(self):
        """Test adding new type and test if encoding and decoding results in the same value"""
        redis_dict = RedisDict()
        redis_dict.extends_type(EncryptedRot13String, rot13_encode, rot13_decode)

        key = "foo"
        key2 = "bar"
        expected = "foobar"

        redis_dict[key] = EncryptedRot13String(expected)

        # Decodes the value, And stores the value encoded. Seamless usage of new type.
        redis_dict[key2] = redis_dict[key]

        result_one = redis_dict[key]
        result_two = redis_dict[key2]

        # Assert the single encoded decoded value is the same as double encoding decoded value.
        self.assertEqual(result_one, EncryptedRot13String(expected))
        self.assertEqual(result_one, result_two)

        self.assertEqual(result_two, expected)


if __name__ == '__main__':
    unittest.main()
