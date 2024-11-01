from typing import Any

import sys
import time
import json
import unittest

from datetime import datetime, timedelta

import redis

from redis_dict import RedisDict
from redis_dict import RedisDictJSONEncoder, RedisDictJSONDecoder

from hypothesis import given, strategies as st

# !! Make sure you don't have keys within redis named like this, they will be deleted.
TEST_NAMESPACE_PREFIX = '__test_prefix_key_meta_8128__'

redis_config = {
    'host': 'localhost',
    'port': 6379,
    'db': 11,
}


def skip_before_python39(test_item):
    """
    Decorator to skip tests for Python versions before 3.9
    where dictionary union operations are not supported.

    Can be used to decorate both test methods and test classes.

    Args:
        test_item: The test method or class to be decorated

    Returns:
        The decorated test item that will be skipped if Python version < 3.9
    """
    reason = "Dictionary union operators (|, |=) require Python 3.9+"

    if sys.version_info < (3, 9):
        if isinstance(test_item, type):
            return unittest.skip(reason)(test_item)
        return unittest.skip(reason)(test_item)
    return test_item


class TestRedisDictBehaviorDict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.redisdb = redis.StrictRedis(**redis_config)
        cls.r = cls.create_redis_dict()

    @classmethod
    def tearDownClass(cls):
        cls.clear_test_namespace()
        pass

    @classmethod
    def create_redis_dict(cls, namespace=TEST_NAMESPACE_PREFIX, **kwargs):
        config = redis_config.copy()
        config.update(kwargs)
        return RedisDict(namespace=namespace, **config)

    @classmethod
    def clear_test_namespace(cls):
        for key in cls.redisdb.scan_iter('{}:*'.format(TEST_NAMESPACE_PREFIX)):
            cls.redisdb.delete(key)

    def setUp(self):
        self.clear_test_namespace()

    def test_python3_all_methods_from_dictionary_are_implemented(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        self.assertEqual(set(dir({})) - set(dir(RedisDict)), set())
        self.assertEqual(len(set(dir(dic)) - set(dir(redis_dic))), 0)

    def test_input_items(self):
        """Calling RedisDict.keys() should return an empty list."""
        redis_dic = self.create_redis_dict()
        dic = dict()

        expected = 0
        self.assertEqual(expected, len(dic))
        self.assertEqual(expected, len(redis_dic))

        expected = 1
        expected_key = 'one item'
        expected_value = 1
        redis_dic[expected_key] = expected_value
        dic[expected_key] = expected_value
        self.assertEqual(expected, len(dic))
        self.assertEqual(expected, len(redis_dic))

        self.assertTrue(expected_key in redis_dic)
        self.assertTrue(expected_key in dic)

        self.assertEqual(dic[expected_key], redis_dic[expected_key])

        items = (('{} item'.format(i), i) for i in range(1, 5))
        for key, value in items:
            redis_dic[key] = value
            dic[key] = value

        expected = 5
        self.assertEqual(expected, len(dic))
        self.assertEqual(expected, len(redis_dic))

        for key, expected_value in items:
            self.assertEqual(dic[key], expected_value)
            self.assertEqual(dic[key], redis_dic[key])

    def test_supported_types(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_values = [
            ("int", 1),
            ("float", 0.9),
            ("str", "im a string"),
            ("bool", True),
            ("None", None),
            ("list", [1, 2, 3]),
            ("dict", {"foo": "bar"}),
        ]

        for key, value in input_values:
            redis_dic[key] = value
            dic[key] = value

        expected_len = len(input_values)
        self.assertEqual(expected_len, len(redis_dic))
        self.assertEqual(len(dic), len(redis_dic))

        for expected_key, expected_value in input_values:
            result = redis_dic[expected_key]
            self.assertEqual(expected_value, result)
            self.assertEqual(dic[expected_key], result)

        self.assertTrue(len(redis_dic) > 2)
        redis_dic.clear()
        dic.clear()
        self.assertEqual(len(redis_dic), 0)
        self.assertEqual(len(dic), 0)

    def test_update(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_values = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        self.assertEqual(len(redis_dic), 0)
        self.assertEqual(len(dic), 0)
        self.assertEqual(len(input_values), 5)

        redis_dic.update(input_values)
        dic.update(input_values)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_values), 5)

        for expected_key, expected_value in input_values.items():
            self.assertEqual(redis_dic[expected_key], expected_value)
            self.assertEqual(dic[expected_key], expected_value)

    def test_iter(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        self.assertEqual(len(redis_dic), 0)
        self.assertEqual(len(dic), 0)
        self.assertEqual(len(input_items), 5)

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

        for expected_key, expected_value in input_items.items():
            self.assertEqual(redis_dic[expected_key], expected_value)
            self.assertEqual(dic[expected_key], expected_value)

        for key in redis_dic:
            self.assertTrue(key in input_items)

        for key in redis_dic.keys():
            self.assertTrue(key in input_items)

        for key, value in redis_dic.items():
            self.assertEqual(input_items[key], value)
            self.assertEqual(dic[key], value)

        input_values = list(input_items.values())
        dic_values = list(dic.values())
        result_values = list(redis_dic.values())

        self.assertEqual(sorted(map(str, input_values)), sorted(map(str, result_values)))
        self.assertEqual(sorted(map(str, dic_values)), sorted(map(str, result_values)))

        result_values = list(redis_dic.values())
        self.assertEqual(sorted(map(str, input_values)), sorted(map(str, result_values)))
        self.assertEqual(sorted(map(str, dic_values)), sorted(map(str, result_values)))

    def test_dict_method_update(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

    def test_dict_method_pop(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

        for i, key in enumerate(input_items.keys(), start=1):
            expected = dic.pop(key)
            result = redis_dic.pop(key)
            self.assertEqual(expected, result)
            self.assertEqual(len(dic), len(input_items) - i)
            self.assertEqual(len(redis_dic), len(input_items) - i)

        with self.assertRaises(KeyError):
            dic.pop("item")
        with self.assertRaises(KeyError):
            redis_dic.pop("item")

    def test_dict_method_pop_default(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

        for i, key in enumerate(input_items.keys(), start=1):
            expected = dic.pop(key)
            result = redis_dic.pop(key)
            self.assertEqual(expected, result)
            self.assertEqual(len(dic), len(input_items) - i)
            self.assertEqual(len(redis_dic), len(input_items) - i)

        expected = "default item"
        self.assertEqual(dic.pop("item", expected), expected)
        self.assertEqual(redis_dic.pop("item", expected), expected)

        expected = None
        self.assertEqual(dic.pop("item", expected), expected)
        self.assertEqual(redis_dic.pop("item", expected), expected)

    def test_dict_method_popitem(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

        expected = [dic.popitem() for _ in range(5)]
        result = [redis_dic.popitem() for _ in range(5)]

        self.assertEqual(sorted(map(str, expected)), sorted(map(str, result)))

        self.assertEqual(len(dic), 0)
        self.assertEqual(len(redis_dic), 0)

        with self.assertRaises(KeyError):
            dic.popitem()
        with self.assertRaises(KeyError):
            redis_dic.popitem()

    @skip_before_python39
    def test_dict_method_or(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        additional_items = {
            "str": "new string",
            "new_int": 42,
            "new_bool": False,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

        redis_result = redis_dic | additional_items
        dict_result = dic | additional_items

        self.assertEqual(len(redis_result), len(dict_result))
        self.assertEqual(dict(redis_result), dict_result)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(dict(redis_dic), dict(dic))

        with self.assertRaises(TypeError):
            dic | [1, 2]

        with self.assertRaises(TypeError):
            redis_dic | [1, 2]

    @skip_before_python39
    def test_dict_method_ror(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        additional_items = {
            "str": "new string",
            "new_int": 42,
            "new_bool": False,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

        redis_result = additional_items | redis_dic
        dict_result = additional_items | dic

        self.assertEqual(len(redis_result), len(dict_result))
        self.assertEqual(dict(redis_result), dict_result)

        # Verify original dicts weren't modified
        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(dict(redis_dic), dict(dic))

        with self.assertRaises(TypeError):
            [1, 2] | dic

        with self.assertRaises(TypeError):
             [1, 2] | redis_dic

    @skip_before_python39
    def test_dict_method_ior(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        additional_items = {
            "str": "new string",
            "new_int": 42,
            "new_bool": False,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

        redis_dic |= additional_items
        dic |= additional_items

        self.assertEqual(len(redis_dic), len(dic))
        self.assertEqual(dict(redis_dic), dict(dic))

        with self.assertRaises(TypeError):
            dic |= [1, 2]

        with self.assertRaises(TypeError):
            redis_dic |= [1, 2]


    def test_dict_method_reversed_(self):
        """
        RedisDict Currently does not support insertion order as property thus also not reversed.
        This test only test `reversed` can be called.
        """
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "bool": True,
            "None": None,
        }

        redis_dic.update(input_items)
        dic.update(input_items)
        redis_reversed = sorted(reversed(redis_dic))
        dict_reversed = sorted(reversed(dic))

        self.assertEqual(redis_reversed, dict_reversed)

    @unittest.skip
    def test_dict_method_reversed(self):
        """
        RedisDict Currently does not support insertion order as property thus also not reversed.
        """
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

        redis_reversed = list(reversed(redis_dic))
        dict_reversed = list(reversed(dic))

        self.assertEqual(redis_reversed, dict_reversed)

    def test_dict_method_class_getitem(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)
        self.assertEqual(len(input_items), 5)

        def accepts_redis_dict(d: RedisDict[str, Any]) -> None:
            self.assertIsInstance(d, RedisDict)

        accepts_redis_dict(redis_dic)

    def test_dict_method_setdefault(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        dic.setdefault("item", 4)
        redis_dic.setdefault("item", 4)

        self.assertEqual(dic["item"], redis_dic["item"])

        self.assertEqual(len(dic), 1)
        self.assertEqual(len(redis_dic), 1)

        dic.setdefault("item", 5)
        redis_dic.setdefault("item", 5)

        self.assertEqual(dic["item"], redis_dic["item"])

        self.assertEqual(len(dic), 1)
        self.assertEqual(len(redis_dic), 1)

        dic.setdefault("foobar", 6)
        redis_dic.setdefault("foobar", 6)

        self.assertEqual(dic["item"], redis_dic["item"])
        self.assertEqual(dic["foobar"], redis_dic["foobar"])

        self.assertEqual(len(dic), 2)
        self.assertEqual(len(redis_dic), 2)

    def test_dict_method_setdefault_with_expire(self):
        """Test setdefault with expiration setting"""
        redis_dic = self.create_redis_dict(expire=3600)
        key = "test_expire_key"
        expected_value = "expected value"
        other_expected_value = "other_default_value"

        # Clear any existing values
        redis_dic.clear()

        # First call - should set with expiry
        result_one = redis_dic.setdefault(
            key, expected_value
        )
        self.assertEqual(result_one, expected_value)
        # Check TTL
        actual_ttl = redis_dic.get_ttl(key)
        self.assertAlmostEqual(3600, actual_ttl, delta=2)

        # Second call - should get existing value and maintain TTL
        time.sleep(1)
        result_two = redis_dic.setdefault(
            key, other_expected_value,
        )
        self.assertEqual(result_one, expected_value)
        self.assertNotEqual(result_two, other_expected_value)
        # TTL should be ~1 second less
        new_ttl = redis_dic.get_ttl(key)
        self.assertAlmostEqual(3600 - 1, new_ttl, delta=2)

        # Value should be unchanged
        self.assertEqual(result_one, result_two)

        self.assertEqual(expected_value, redis_dic[key])
        del redis_dic[key]
        with redis_dic.expire_at(timedelta(seconds=1)):
            result_one_three = redis_dic.setdefault(
                key, other_expected_value,
            )
            self.assertEqual(other_expected_value, redis_dic[key])
        time.sleep(1.5)
        with self.assertRaisesRegex(KeyError, key):
            redis_dic[key]

    def test_setdefault_with_preserve_ttl(self):
        """Test setdefault with preserve_expiration=True"""
        redis_dic = self.create_redis_dict(expire=5, preserve_expiration=True)
        key = "test_preserve_key"
        expected_value = "expected_value"
        default_value = "default"
        sleep_time = 2

        redis_dic[key] = expected_value
        initial_ttl = redis_dic.get_ttl(key)

        time.sleep(sleep_time)
        # Try setdefault - should keep original TTL
        result = redis_dic.setdefault(
            key, default_value
        )
        self.assertEqual(result, expected_value)

        time.sleep(sleep_time)
        # TTL should have been preserved, thus new_ttl+sleep_time should less than initial_ttl since sleep 1 second.
        new_ttl = redis_dic.get_ttl(key)
        self.assertLess(new_ttl+sleep_time, initial_ttl)
        time.sleep(sleep_time)

        # TTL should be expired, thus key and value should be missing, and thus we will set the default value.
        with self.assertRaisesRegex(KeyError, key):
            redis_dic[key]

        expected_value_two = "expected_value_two"
        result_two = redis_dic.setdefault(
            key, expected_value_two
        )
        self.assertEqual(result_two, expected_value_two)
        self.assertEqual(redis_dic[key], expected_value_two)

    def test_setdefault_concurrent_ttl(self):
        """Test TTL behavior with concurrent setdefault operations"""
        redis_dic =  self.create_redis_dict(expire=3600)
        other_redis_dic =   self.create_redis_dict(expire=1800)  # Different TTL

        key = "test_concurrent_key"
        default_value = "default"
        other_default_value = "other_default"

        redis_dic.clear()

        # First operation sets with 3600s TTL
        value1 = redis_dic.setdefault(
            key, default_value
        )

        ttl1 = redis_dic.get_ttl(key)
        self.assertAlmostEqual(3600, ttl1, delta=2)

        # Competing operation tries with 1800s TTL
        value2 = other_redis_dic.setdefault(
        key, other_default_value
        )

        # Original TTL should be maintained
        ttl2 = other_redis_dic.get_ttl(key)
        self.assertAlmostEqual(3600, ttl2, delta=3)
        self.assertEqual(value1, value2)  # Should get same value

    def test_dict_method_get(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        dic.setdefault("item", 4)
        redis_dic.setdefault("item", 4)

        self.assertEqual(dic["item"], redis_dic["item"])

        self.assertEqual(len(dic), 1)
        self.assertEqual(len(redis_dic), 1)

        self.assertEqual(dic.get("item"), redis_dic.get("item"))
        self.assertEqual(dic.get("foobar"), redis_dic.get("foobar"))
        self.assertEqual(dic.get("foobar", "foobar"), redis_dic.get("foobar", "foobar"))

    def test_dict_method_clear(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)

        dic.clear()
        redis_dic.clear()

        self.assertEqual(len(redis_dic), 0)
        self.assertEqual(len(dic), 0)

        # Boundary check. clear on empty dictionary is valid
        dic.clear()
        redis_dic.clear()

        self.assertEqual(len(redis_dic), 0)
        self.assertEqual(len(dic), 0)

    def test_dict_method_clear_1(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "int": 1,
            "float": 0.9,
            "str": "im a string",
            "bool": True,
            "None": None,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), 5)
        self.assertEqual(len(dic), 5)

        dic_id = id(dic)
        redis_dic_id = id(id)

        dic_copy = dic.copy()
        redis_dic_copy = redis_dic.copy()

        self.assertNotEqual(dic_id, id(dic_copy))
        self.assertNotEqual(redis_dic_id, id(redis_dic_copy))

        dic.clear()
        redis_dic.clear()

        self.assertEqual(len(redis_dic), 0)
        self.assertEqual(len(dic), 0)

        self.assertEqual(len(dic_copy), 5)
        self.assertEqual(len(redis_dic_copy), 5)

    def test_dict_exception_keyerror(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        with self.assertRaisesRegex(KeyError, "appel"):
            dic['appel']
        with self.assertRaisesRegex(KeyError, "appel"):
            redis_dic['appel']

        with self.assertRaisesRegex(KeyError, r"popitem\(\): dictionary is empty"):
            dic.popitem()
        with self.assertRaisesRegex(KeyError, r"popitem\(\): dictionary is empty"):
            redis_dic.popitem()

    def test_dict_types_bool(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        input_items = {
            "True": True,
            "False": False,
            "NotTrue": False,
            "NotFalse": True,
        }

        redis_dic.update(input_items)
        dic.update(input_items)

        self.assertEqual(len(redis_dic), len(input_items))
        self.assertEqual(len(dic), len(input_items))

        for key, expected_value in input_items.items():
            self.assertEqual(redis_dic[key], expected_value)
            self.assertEqual(dic[key], expected_value)

        dic.clear()
        redis_dic.clear()

        self.assertEqual(len(redis_dic), 0)
        self.assertEqual(len(dic), 0)

        for k, v in input_items.items():
            redis_dic[k] = v
            dic[k] = v

        for key, expected_value in input_items.items():
            self.assertEqual(redis_dic[key], expected_value)
            self.assertEqual(dic[key], expected_value)

        for k, v in redis_dic.items():
            self.assertEqual(input_items[k], v)
            self.assertEqual(dic[k], v)

        self.assertEqual(len(redis_dic), len(input_items))
        self.assertEqual(len(dic), len(input_items))

    def test_dict_method_pipeline(self):
        redis_dic = self.create_redis_dict()
        expected = {
            'a': 1,
            'b': 2,
            'c': 3,
        }
        with redis_dic.pipeline():
            for k, v in expected.items():
                redis_dic[k] = v

        self.assertEqual(len(redis_dic), len(expected))
        for k, v in expected.items():
            self.assertEqual(redis_dic[k], v)
        redis_dic.clear()
        self.assertEqual(len(redis_dic), 0)

        with redis_dic.pipeline():
            with redis_dic.pipeline():
                for k, v in expected.items():
                    redis_dic[k] = v

        self.assertEqual(len(redis_dic), len(expected))
        for k, v in expected.items():
            self.assertEqual(redis_dic[k], v)
        redis_dic.clear()
        self.assertEqual(len(redis_dic), 0)

        with redis_dic.pipeline():
            with redis_dic.pipeline():
                with redis_dic.pipeline():
                    for k, v in expected.items():
                        redis_dic[k] = v

        self.assertEqual(len(redis_dic), len(expected))
        for k, v in expected.items():
            self.assertEqual(redis_dic[k], v)
        redis_dic.clear()
        self.assertEqual(len(redis_dic), 0)

        with redis_dic.pipeline():
            with redis_dic.pipeline():
                with redis_dic.pipeline():
                    with redis_dic.pipeline():
                        for k, v in expected.items():
                            redis_dic[k] = v

        self.assertEqual(len(redis_dic), len(expected))
        for k, v in expected.items():
            self.assertEqual(redis_dic[k], v)
        redis_dic.clear()
        self.assertEqual(len(redis_dic), 0)

    def test_dict_method_pipeline_buffer_sets(self):  # noqa: C901
        redis_dic = self.create_redis_dict()
        expected = {
            'a': 1,
            'b': 2,
            'c': 3,
        }
        with redis_dic.pipeline():
            for k, v in expected.items():
                redis_dic[k] = v
            self.assertEqual(len(redis_dic), 0)

        self.assertEqual(len(redis_dic), len(expected))

        for k, v in expected.items():
            self.assertEqual(redis_dic[k], v)

        with redis_dic.pipeline():
            for k, v in redis_dic.items():
                redis_dic[k] = v * 2
            for k, v in expected.items():
                self.assertEqual(redis_dic[k], v)

        for k, v in expected.items():
            self.assertEqual(redis_dic[k], v * 2)
        self.assertEqual(len(redis_dic), len(expected))

        redis_dic.clear()
        self.assertEqual(len(redis_dic), 0)

        with redis_dic.pipeline():
            with redis_dic.pipeline():
                for k, v in expected.items():
                    redis_dic[k] = v
                self.assertEqual(len(redis_dic), 0)

        self.assertEqual(len(redis_dic), len(expected))

        for k, v in expected.items():
            self.assertEqual(redis_dic[k], v)

        with redis_dic.pipeline():
            with redis_dic.pipeline():
                for k, v in redis_dic.items():
                    redis_dic[k] = v * 2
                for k, v in expected.items():
                    self.assertEqual(redis_dic[k], v)

        for k, v in expected.items():
            self.assertEqual(redis_dic[k], v * 2)
        self.assertEqual(len(redis_dic), len(expected))

        with redis_dic.pipeline():
            redis_dic.clear()
            self.assertEqual(len(redis_dic), len(expected))

        self.assertEqual(len(redis_dic), 0)

    def test_dict_method_fromkeys(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        keys = ['a', 'b', 'c', 'd']
        expected_dic = {k: None for k in keys}

        result_dic = dic.fromkeys(keys)
        result_redis_dic = redis_dic.fromkeys(keys)

        self.assertEqual(len(result_dic), len(keys))
        self.assertEqual(len(result_redis_dic), len(keys))
        self.assertEqual(len(expected_dic), len(keys))
        for k, v in expected_dic.items():
            self.assertEqual(result_redis_dic[k], v)
            self.assertEqual(result_dic[k], v)

    def test_dict_method_fromkeys_with_default(self):
        redis_dic = self.create_redis_dict()
        dic = dict()

        expected_default = 42
        keys = ['a', 'b', 'c', 'd']
        expected_dic = {k: expected_default for k in keys}

        result_dic = dic.fromkeys(keys, expected_default)
        result_redis_dic = redis_dic.fromkeys(keys, expected_default)

        self.assertEqual(len(result_dic), len(keys))
        self.assertEqual(len(result_redis_dic), len(keys))
        self.assertEqual(len(expected_dic), len(keys))
        for k, v in expected_dic.items():
            self.assertEqual(result_redis_dic[k], v)


class TestRedisDict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.redisdb = redis.StrictRedis(**redis_config)
        cls.r = cls.create_redis_dict()

    @classmethod
    def tearDownClass(cls):
        cls.clear_test_namespace()

    @classmethod
    def create_redis_dict(cls, namespace=TEST_NAMESPACE_PREFIX, **kwargs):
        config = redis_config.copy()
        config.update(kwargs)
        return RedisDict(namespace=namespace, **config)

    @classmethod
    def clear_test_namespace(cls):
        for key in cls.redisdb.scan_iter('{}:*'.format(TEST_NAMESPACE_PREFIX)):
            cls.redisdb.delete(key)

    def setUp(self):
        self.clear_test_namespace()

    def test_get_redis_info(self):
        """Ensure get_redis_info() returns a dictionary with Redis server information."""
        result = self.r.get_redis_info()
        self.assertIsInstance(result, dict)
        self.assertIn('redis_version', result)

    def test_sizeof(self):
        """Verify that RedisDict's __sizeof__() method returns the correct size."""
        self.r.clear()
        self.r['key'] = 'value'
        expected = self.r.to_dict().__sizeof__()
        result = self.r.__sizeof__()
        self.assertEqual(expected, result)

    def test_keys_empty(self):
        """Calling RedisDict.keys() should return an empty Iterator."""
        keys = self.r.keys()
        self.assertEqual(list(keys), [])

    def test_set_and_get_foobar(self):
        """Test setting a key and retrieving it."""
        self.r['foobar'] = 'barbar'

        self.assertEqual(self.r['foobar'], 'barbar')

    def test_set_none_and_get_none(self):
        """Test setting a key with no value and retrieving it."""
        self.r['foobar'] = None

        self.assertIsNone(self.r['foobar'])

    def test_set_and_get_multiple(self):
        """Test setting two different keys with two different values, and reading them."""
        self.r['foobar1'] = 'barbar1'
        self.r['foobar2'] = 'barbar2'

        self.assertEqual(self.r['foobar1'], 'barbar1')
        self.assertEqual(self.r['foobar2'], 'barbar2')

    def test_get_non_existing(self):
        """Test that retrieving a non-existing key raises a KeyError."""
        with self.assertRaises(KeyError):
            _ = self.r['non_existing_key']

    def test_delete(self):
        """Test deleting a key."""
        key = 'foobar_gone'
        self.r[key] = 'bar'

        del self.r[key]
        self.assertEqual(self.redisdb.get(key), None)

    def test_contains_empty(self):
        """Tests the __contains__ function with no keys set."""
        self.assertFalse('foobar' in self.r)
        self.assertFalse('foobar1' in self.r)
        self.assertFalse('foobar_is_not_found' in self.r)
        self.assertFalse('1' in self.r)

    def test_contains_nonempty(self):
        """Tests the __contains__ function with keys set."""
        self.r['foobar'] = 'barbar'
        self.assertTrue('foobar' in self.r)

    def test_repr_empty(self):
        """Tests the __repr__ function with no keys set."""
        expected_repr = str({})
        actual_repr = repr(self.r)
        self.assertEqual(actual_repr, expected_repr)

    def test_repr_nonempty(self):
        """Tests the __repr__ function with keys set."""
        key = 'foobar'
        val = 'bar'
        self.r[key] = val
        expected = str({key: val})
        result = repr(self.r)
        self.assertEqual(result, expected)

    def test_str_nonempty(self):
        """Tests the __repr__ function with keys set."""
        key = 'foobar'
        val = 'bar'
        self.r[key] = val
        expected = str({key: val})
        result = str(self.r)
        self.assertEqual(result, expected)

    def test_len_empty(self):
        """Tests the __repr__ function with no keys set."""
        self.assertEqual(len(self.r), 0)

    def test_len_nonempty(self):
        """Tests the __repr__ function with keys set."""
        self.r['foobar1'] = 'barbar1'
        self.r['foobar2'] = 'barbar2'
        self.assertEqual(len(self.r), 2)

    def test_to_dict_empty(self):
        """Tests the to_dict function with no keys set."""
        expected_dict = {}
        actual_dict = self.r.to_dict()
        self.assertEqual(actual_dict, expected_dict)

    def test_to_dict_nonempty(self):
        """Tests the to_dict function with keys set."""
        self.r['foobar'] = 'barbaros'
        expected_dict = {u'foobar': u'barbaros'}
        actual_dict = self.r.to_dict()
        self.assertEqual(actual_dict, expected_dict)

    def test_chain_set_1(self):
        """Test setting a chain with 1 element."""
        self.r.chain_set(['foo'], 'melons')

        expected_key = '{}:foo'.format(TEST_NAMESPACE_PREFIX)
        self.assertEqual(self.redisdb.get(expected_key), b'str:melons')

    def test_chain_set_2(self):
        """Test setting a chain with 2 elements."""
        self.r.chain_set(['foo', 'bar'], 'melons')

        expected_key = '{}:foo:bar'.format(TEST_NAMESPACE_PREFIX)
        self.assertEqual(self.redisdb.get(expected_key), b'str:melons')

    def test_chain_set_overwrite(self):
        """Test setting a chain with 1 element and then overwriting it."""
        self.r.chain_set(['foo'], 'melons')
        self.r.chain_set(['foo'], 'bananas')

        expected_key = '{}:foo'.format(TEST_NAMESPACE_PREFIX)
        self.assertEqual(self.redisdb.get(expected_key), b'str:bananas')

    def test_chain_get_1(self):
        """Test setting and getting a chain with 1 element."""
        self.r.chain_set(['foo'], 'melons')

        self.assertEqual(self.r.chain_get(['foo']), 'melons')

    def test_chain_get_empty(self):
        """Test getting a chain that has not been set."""
        with self.assertRaises(KeyError):
            _ = self.r.chain_get(['foo'])

    def test_chain_get_2(self):
        """Test setting and getting a chain with 2 elements."""
        self.r.chain_set(['foo', 'bar'], 'melons')

        self.assertEqual(self.r.chain_get(['foo', 'bar']), 'melons')

    def test_chain_del_1(self):
        """Test setting and deleting a chain with 1 element."""
        self.r.chain_set(['foo'], 'melons')
        self.r.chain_del(['foo'])

        with self.assertRaises(KeyError):
            _ = self.r.chain_get(['foo'])

    def test_chain_del_2(self):
        """Test setting and deleting a chain with 2 elements."""
        self.r.chain_set(['foo', 'bar'], 'melons')
        self.r.chain_del(['foo', 'bar'])

        with self.assertRaises(KeyError):
            _ = self.r.chain_get(['foo', 'bar'])

    def test_expire_context(self):
        """Test adding keys with an `expire` value by using the contextmanager."""
        with self.r.expire_at(3600):
            self.r['foobar'] = 'barbar'

        actual_ttl = self.redisdb.ttl('{}:foobar'.format(TEST_NAMESPACE_PREFIX))
        self.assertAlmostEqual(3600, actual_ttl, delta=2)

    def test_expire_context_timedelta(self):
        """ Test adding keys with an `expire` value by using the contextmanager. With timedelta as argument. """
        timedelta_one_hour = timedelta(hours=1)
        timedelta_one_minute = timedelta(minutes=1)
        hour_in_seconds = 60 * 60
        minute_in_seconds = 60

        with self.r.expire_at(timedelta_one_hour):
            self.r['one_hour'] = 'one_hour'
        with self.r.expire_at(timedelta_one_minute):
            self.r['one_minute'] = 'one_minute'

        actual_ttl = self.redisdb.ttl('{}:one_hour'.format(TEST_NAMESPACE_PREFIX))
        self.assertAlmostEqual(hour_in_seconds, actual_ttl, delta=2)
        actual_ttl = self.redisdb.ttl('{}:one_minute'.format(TEST_NAMESPACE_PREFIX))
        self.assertAlmostEqual(minute_in_seconds, actual_ttl, delta=2)

    def test_expire_keyword(self):
        """Test adding keys with an `expire` value by using the `expire` config keyword."""
        r = self.create_redis_dict(expire=3600)

        r['foobar'] = 'barbar'
        actual_ttl = self.redisdb.ttl('{}:foobar'.format(TEST_NAMESPACE_PREFIX))
        self.assertAlmostEqual(3600, actual_ttl, delta=2)

    def test_expire_keyword_timedelta(self):
        """ Test adding keys with an `expire` value by using the `expire` config keyword. With timedelta as argument."""
        timedelta_one_hour = timedelta(hours=1)
        timedelta_one_minute = timedelta(minutes=1)
        hour_in_seconds = 60 * 60
        minute_in_seconds = 60

        r_hour = self.create_redis_dict(expire=timedelta_one_hour)
        r_minute = self.create_redis_dict(expire=timedelta_one_minute)

        r_hour['one_hour'] = 'one_hour'
        r_minute['one_minute'] = 'one_minute'

        actual_ttl = self.redisdb.ttl('{}:one_hour'.format(TEST_NAMESPACE_PREFIX))
        self.assertAlmostEqual(hour_in_seconds, actual_ttl, delta=2)
        actual_ttl = self.redisdb.ttl('{}:one_minute'.format(TEST_NAMESPACE_PREFIX))
        self.assertAlmostEqual(minute_in_seconds, actual_ttl, delta=2)

    def test_iter(self):
        """Tests the __iter__ function."""
        key_values = {
            'foobar1': 'barbar1',
            'foobar2': 'barbar2',
        }

        for key, value in key_values.items():
            self.r[key] = value

        # TODO made the assumption that iterating the redisdict should return keys, like a normal dict
        for key in self.r:
            self.assertEqual(self.r[key], key_values[key])

    # TODO behavior of multi and chain methods should be discussed.
    # TODO python 2 couldn't skip
    # @unittest.skip
    # def test_multi_get_with_key_none(self):
    #     """Tests that multi_get with key None raises TypeError."""
    #     with self.assertRaises(TypeError):
    #         self.r.multi_get(None)

    def test_multi_get_empty(self):
        """Tests the multi_get function with no keys set."""
        self.assertEqual(self.r.multi_get('foo'), [])

    def test_multi_get_nonempty(self):
        """Tests the multi_get function with 3 keys set, get 2 of them."""
        self.r['foobar'] = 'barbar'
        self.r['foobaz'] = 'bazbaz'
        self.r['goobar'] = 'borbor'

        expected_result = ['barbar', 'bazbaz']
        self.assertEqual(sorted(self.r.multi_get('foo')), sorted(expected_result))

    def test_multi_get_chain_with_key_none(self):
        """Tests that multi_chain_get with key None raises TypeError."""
        with self.assertRaises(TypeError):
            self.r.multi_chain_get(None)

    def test_multi_chain_get_empty(self):
        """Tests the multi_chain_get function with no keys set."""
        self.assertEqual(self.r.multi_chain_get(['foo']), [])

    def test_multi_chain_get_nonempty(self):
        """Tests the multi_chain_get function with keys set."""
        self.r.chain_set(['foo', 'bar', 'bar'], 'barbar')
        self.r.chain_set(['foo', 'bar', 'baz'], 'bazbaz')
        self.r.chain_set(['foo', 'baz'], 'borbor')

        # redis.mget seems to sort keys in reverse order here
        expected_result = sorted([u'bazbaz', u'barbar'])
        self.assertEqual(sorted(self.r.multi_chain_get(['foo', 'bar'])), expected_result)

    def test_multi_dict_empty(self):
        """Tests the multi_dict function with no keys set."""
        self.assertEqual(self.r.multi_dict('foo'), {})

    def test_multi_dict_one_key(self):
        """Tests the multi_dict function with 1 key set."""
        self.r['foobar'] = 'barbar'
        expected_dict = {u'foobar': u'barbar'}
        self.assertEqual(self.r.multi_dict('foo'), expected_dict)

    def test_multi_dict_two_keys(self):
        """Tests the multi_dict function with 2 keys set."""
        self.r['foobar'] = 'barbar'
        self.r['foobaz'] = 'bazbaz'
        expected_dict = {u'foobar': u'barbar', u'foobaz': u'bazbaz'}
        self.assertEqual(self.r.multi_dict('foo'), expected_dict)

    def test_multi_dict_complex(self):
        """Tests the multi_dict function by setting 3 keys and matching 2."""
        self.r['foobar'] = 'barbar'
        self.r['foobaz'] = 'bazbaz'
        self.r['goobar'] = 'borbor'
        expected_dict = {u'foobar': u'barbar', u'foobaz': u'bazbaz'}
        self.assertEqual(self.r.multi_dict('foo'), expected_dict)

    def test_multi_del_empty(self):
        """Tests the multi_del function with no keys set."""
        self.assertEqual(self.r.multi_del('foobar'), 0)

    def test_multi_del_one_key(self):
        """Tests the multi_del function with 1 key set."""
        self.r['foobar'] = 'barbar'
        self.assertEqual(self.r.multi_del('foobar'), 1)
        self.assertIsNone(self.redisdb.get('foobar'))

    def test_multi_del_two_keys(self):
        """Tests the multi_del function with 2 keys set."""
        self.r['foobar'] = 'barbar'
        self.r['foobaz'] = 'bazbaz'
        self.assertEqual(self.r.multi_del('foo'), 2)
        self.assertIsNone(self.redisdb.get('foobar'))
        self.assertIsNone(self.redisdb.get('foobaz'))

    def test_multi_del_complex(self):
        """Tests the multi_del function by setting 3 keys and deleting 2."""
        self.r['foobar'] = 'barbar'
        self.r['foobaz'] = 'bazbaz'
        self.r['goobar'] = 'borbor'
        self.assertEqual(self.r.multi_del('foo'), 2)
        self.assertIsNone(self.redisdb.get('foobar'))
        self.assertIsNone(self.redisdb.get('foobaz'))
        self.assertEqual(self.r['goobar'], 'borbor')

    def test_set_and_get(self):
        self.r['key1'] = 'value1'
        self.assertEqual(self.r['key1'], 'value1')

    def test_set_and_delete(self):
        self.r['key2'] = 'value2'
        del self.r['key2']
        self.assertNotIn('key2', self.r)

    def test_set_and_update(self):
        self.r['key3'] = 'value3'
        self.r.update({'key3': 'new_value3'})
        self.assertEqual(self.r['key3'], 'new_value3')

    def test_clear(self):
        self.r['key4'] = 'value4'
        self.r.clear()
        self.assertEqual(len(self.r), 0)

    def test_set_and_pop(self):
        self.r['key5'] = 'value5'
        popped_value = self.r.pop('key5')
        self.assertEqual(popped_value, 'value5')
        self.assertNotIn('key5', self.r)

    def test_set_and_popitem(self):
        self.r['key6'] = 'value6'
        key, value = self.r.popitem()
        self.assertEqual(key, 'key6')
        self.assertEqual(value, 'value6')
        self.assertNotIn('key6', self.r)

    def test_set_and_get_with_different_types(self):
        data = {
            'key_str': 'string_value',
            'key_int': 42,
            'key_float': 3.14,
            'key_bool': True,
            'key_list': [1, 2, 3],
            'key_dict': {'a': 1, 'b': 2},
            'key_none': None
        }

        for key, value in data.items():
            self.r[key] = value

        for key, expected_value in data.items():
            self.assertEqual(self.r[key], expected_value)

    def test_namespace_isolation(self):
        other_namespace = RedisDict(namespace='other_namespace')
        self.r['key7'] = 'value7'
        self.assertNotIn('key7', other_namespace)

        # teardown
        other_namespace.clear()

    def test_namespace_global_expire(self):
        other_namespace = RedisDict(namespace='other_namespace', expire=1)
        other_namespace['key'] = 'value'

        self.assertEqual(other_namespace['key'], 'value')
        self.assertIn('key', other_namespace)

        time.sleep(2)
        self.assertNotIn('key', other_namespace)
        self.assertRaises(KeyError, lambda: self.r['key11'])

        # teardown
        other_namespace.clear()

    def test_pipeline(self):
        with self.r.pipeline():
            self.r['key8'] = 'value8'
            self.r['key9'] = 'value9'

        self.assertEqual(self.r['key8'], 'value8')
        self.assertEqual(self.r['key9'], 'value9')

    def test_expire_at(self):
        self.r['key10'] = 'value10'
        with self.r.expire_at(1):
            self.r['key11'] = 'value11'

        time.sleep(2)
        self.assertEqual(self.r['key10'], 'value10')
        self.assertRaises(KeyError, lambda: self.r['key11'])

    def test_expire_ttl(self):
        expected = 2
        key, value = 'key12', 'value12'
        self.r[key] = value
        with self.r.expire_at(expected):
            self.r[key] = value
            # test within the context manager
            result = self.r.get_ttl(key)
            self.assertAlmostEqual(expected, result, delta=1)

        # test outside the context manager
        result = self.r.get_ttl(key)

        self.assertAlmostEqual(expected, result, delta=1)
        self.assertEqual(self.r[key], value)

        time.sleep(2.2)
        self.assertRaises(KeyError, lambda: self.r[key])

        # test after expire
        expected = None
        result = self.r.get_ttl(key)
        self.assertEqual(result, expected)

    def test_set_get_empty_tuple(self):
        key = "empty_tuple"
        value = ()
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    def test_set_get_single_element_tuple(self):
        key = "single_element_tuple"
        value = (42,)
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    def test_set_get_empty_set(self):
        key = "empty_set"
        value = set()
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    def test_set_get_single_element_set(self):
        key = "single_element_set"
        value = {42}
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    def test_set_get_mixed_type_list(self):
        key = "mixed_type_list"
        value = [1, "foobar", 3.14, [1, 2, 3]]
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    def test_set_get_mixed_type_list_readme(self):
        key = "mixed_type_list"
        now = datetime.now()
        value = [1, "foobar", 3.14, [1, 2, 3], now]
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    def test_set_get_dict_with_timedelta_readme(self):
        key = "dic_with_timedelta"
        value = {"elapsed_time": timedelta(hours=60)}
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    def test_json_encoder_decoder_readme(self):
        """Test the custom JSON encoder and decoder"""
        now = datetime.now()
        expected = [1, "foobar", 3.14, [1, 2, 3], now]

        encoded = json.dumps(expected, cls=RedisDictJSONEncoder)
        result = json.loads(encoded, cls=RedisDictJSONDecoder)

        self.assertEqual(result, expected)

    @unittest.skip
    def test_set_get_mixed_type_set(self):
        key = "mixed_type_set"
        value = {1, "foobar", 3.14, (1, 2, 3)}
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @unittest.skip  # this highlights that sets, and tuples not fully supported
    def test_set_get_nested_tuple(self):
        key = "nested_tuple"
        value = (1, (2, 3), (4, 5))
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @unittest.skip  # this highlights that sets, and tuples not fully supported
    def test_set_get_nested_tuple_triple(self):
        key = "nested_tuple"
        value = (1, (2, 3), (4, (5, 6)))
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    def test_init_redis_dict_with_redis_instance(self):
            test_key = "test_key"
            expected = "expected value"
            test_inputs = {
                "config from_url": redis.Redis.from_url("redis://127.0.0.1/0"),
                "config from kwargs": redis.Redis(**redis_config),
                "config passed as keywords": redis.Redis(host="127.0.0.1", port=6379),
            }
            for test_name, test_input in test_inputs.items():
                assert_fail_msg = f"test with: {test_name} failed"

                dict_ = RedisDict(redis=test_input)
                dict_[test_key] = expected
                result = dict_[test_key]
                self.assertEqual(result, expected, msg=assert_fail_msg)

                self.assertIs(dict_.redis, test_input)
                self.assertTrue(
                    dict_.redis.get_connection_kwargs().get("decode_responses"),
                    msg=assert_fail_msg,
                    )

                test_input.flushdb()

class TestRedisDictSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.redisdb = redis.StrictRedis(**redis_config)
        cls.r = cls.create_redis_dict()

    @classmethod
    def tearDownClass(cls):
        cls.clear_test_namespace()

    @classmethod
    def create_redis_dict(cls, namespace=TEST_NAMESPACE_PREFIX, **kwargs):
        config = redis_config.copy()
        config.update(kwargs)
        return RedisDict(namespace=namespace, **config)

    @classmethod
    def clear_test_namespace(cls):
        for key in cls.redisdb.scan_iter('{}:*'.format(TEST_NAMESPACE_PREFIX)):
            cls.redisdb.delete(key)

    def setUp(self):
        self.clear_test_namespace()

    def test_unicode_key(self):
        # Test handling of Unicode keys
        unicode_key = '你好'
        self.r[unicode_key] = 'value'
        self.assertEqual(self.r[unicode_key], 'value')

    def test_unicode_value(self):
        # Test handling of Unicode values
        unicode_value = '世界'
        self.r['key'] = unicode_value
        self.assertEqual(self.r['key'], unicode_value)

    def test_special_characters_key(self):
        special_chars_key = '!@#$%^&*()-=_+[]{}|;:\'",.<>/?`~'
        self.r[special_chars_key] = 'value'
        self.assertEqual(self.r[special_chars_key], 'value')

    def test_special_characters_value(self):
        special_chars_value = '!@#$%^&*()-=_+[]{}|;:\'",.<>/?`~'
        self.r['key'] = special_chars_value
        self.assertEqual(self.r['key'], special_chars_value)

    def test_large_key(self):
        # Test handling of large keys (size limit is 512MB)
        large_key = 'k' * (512 * 1024 * 1024)
        with self.assertRaises(ValueError):
            self.r[large_key] = 'value'

    def test_large_value(self):
        # Test handling of large values (size limit is 512MB)
        large_value = 'v' * (512 * 1024 * 1024)
        with self.assertRaises(ValueError):
            self.r['key'] = large_value

    def test_injection_attack_get(self):
        injection_key = 'key; GET another_key'
        self.r['another_key'] = 'value'
        with self.assertRaises(KeyError):
            self.r[injection_key]
        self.assertEqual(self.r['another_key'], 'value')

        self.r[injection_key] = "foo"
        self.assertEqual(self.r[injection_key], "foo")
        self.assertEqual(self.r['another_key'], 'value')

    def test_injection_attack_mget(self):
        injection_key = 'foo; MGET foo2 foo3'
        self.r['foo2'] = 'bar2'
        self.r['foo3'] = 'bar3'
        with self.assertRaises(KeyError):
            self.r[injection_key]
        self.assertEqual(sorted(self.r.multi_get('foo')), sorted(['bar2', 'bar3']))
        self.assertEqual(self.r['foo2'], 'bar2')
        self.assertEqual(self.r['foo3'], 'bar3')

        self.r[injection_key] = "bar"
        self.assertEqual(sorted(self.r.multi_get('foo')), sorted(['bar2', 'bar3', 'bar']))
        self.assertEqual(self.r[injection_key], 'bar')
        self.assertEqual(self.r['foo2'], 'bar2')
        self.assertEqual(self.r['foo3'], 'bar3')

    def test_injection_attack_scan(self):
        injection_key = 'bar; SCAN 0 MATCH *'
        self.r['foo2'] = 'bar2'
        self.r['foo3'] = 'bar3'
        with self.assertRaises(KeyError):
            self.r[injection_key]
        self.assertNotIn(injection_key, self.r.keys())
        self.assertEqual(self.r['foo2'], 'bar2')
        self.assertEqual(self.r['foo3'], 'bar3')

        self.r[injection_key] = 'bar'
        self.assertEqual(self.r[injection_key], 'bar')
        self.assertEqual(self.r['foo2'], 'bar2')
        self.assertEqual(self.r['foo3'], 'bar3')

    def test_injection_attack_rename(self):
        injection_key = 'key1; RENAME key2 key3'
        self.r['foo2'] = 'bar2'
        self.r['foo3'] = 'bar3'
        with self.assertRaises(KeyError):
            self.r[injection_key]
        self.assertNotIn(injection_key, self.r.keys())
        self.assertEqual(self.r['foo2'], 'bar2')
        self.assertEqual(self.r['foo3'], 'bar3')

        self.r[injection_key] = 'bar'
        self.assertEqual(self.r[injection_key], 'bar')
        self.assertEqual(self.r['foo2'], 'bar2')
        self.assertEqual(self.r['foo3'], 'bar3')


class TestRedisDictComparison(unittest.TestCase):
    def setUp(self):
        self.r1 = RedisDict(namespace="test1")
        self.r2 = RedisDict(namespace="test2")
        self.r3 = RedisDict(namespace="test3")
        self.r4 = RedisDict(namespace="test4")

        self.r1.update({"a": 1, "b": 2, "c": "foo", "d": [1, 2, 3], "e": {"a": 1, "b": [4, 5, 6]}})
        self.r2.update({"a": 1, "b": 2, "c": "foo", "d": [1, 2, 3], "e": {"a": 1, "b": [4, 5, 6]}})
        self.r3.update({"a": 1, "b": 3, "c": "foo", "d": [1, 2, 3], "e": {"a": 1, "b": [4, 5, 6]}})
        self.r4.update({"a": 1, "b": 2, "c": "foo", "d": [1, 2, 3], "e": {"a": 1, "b": [4, 5, 7]}})

        self.d1 = {"a": 1, "b": 2, "c": "foo", "d": [1, 2, 3], "e": {"a": 1, "b": [4, 5, 6]}}
        self.d2 = {"a": 1, "b": 3, "c": "foo", "d": [1, 2, 3], "e": {"a": 1, "b": [4, 5, 6]}}

    def tearDown(self):
        self.r1.clear()
        self.r2.clear()
        self.r3.clear()
        self.r4.clear()

    @classmethod
    def clear_test_namespace(cls):
        names_spaces = [
            "test1", "test2", "test3", "test4",
            "sequential_comparison", "test_empty",
            "test_nested_empty"
        ]
        for namespace in names_spaces:
            RedisDict(namespace).clear()

    @classmethod
    def tearDownClass(cls):
        cls.clear_test_namespace()

    def test_eq(self):
        self.assertTrue(self.r1 == self.r2)
        self.assertFalse(self.r1 == self.r3)
        self.assertFalse(self.r1 == self.r4)
        self.assertTrue(self.r2 == self.r1)
        self.assertFalse(self.r2 == self.r3)
        self.assertFalse(self.r2 == self.r4)
        self.assertFalse(self.r3 == self.r4)

    def test_eq_with_redis_dict(self):
        self.assertEqual(self.r1, self.r2)

    def test_eq_with_dict(self):
        self.assertEqual(self.r1, self.d1)

    def test_eq_empty(self):
        empty_r = RedisDict(namespace="test_empty")
        self.assertEqual(empty_r, {})
        empty_r.clear()

    def test_eq_nested_empty(self):
        nested_empty_r = RedisDict(namespace="test_nested_empty")
        nested_empty_r.update({"a": {}})
        nested_empty_d = {"a": {}}
        self.assertEqual(nested_empty_r, nested_empty_d)
        nested_empty_r.clear()

    def test_neq(self):
        self.assertFalse(self.r1 != self.r2)
        self.assertTrue(self.r1 != self.r3)
        self.assertTrue(self.r1 != self.r4)
        self.assertFalse(self.r2 != self.r1)
        self.assertTrue(self.r2 != self.r3)
        self.assertTrue(self.r2 != self.r4)
        self.assertTrue(self.r3 != self.r4)

    def test_neq_with_redis_dict(self):
        self.assertNotEqual(self.r1, self.r3)
        self.assertNotEqual(self.r1, self.r4)

    def test_neq_with_dict(self):
        self.assertNotEqual(self.r1, self.d2)

    def test_neq_empty(self):
        empty_r = RedisDict(namespace="test_empty")
        self.assertNotEqual(self.r1, {})
        self.assertNotEqual(empty_r, self.d1)
        empty_r.clear()

    def test_neq_nested_empty(self):
        nested_empty_r = RedisDict(namespace="test_nested_empty")
        nested_empty_r.update({"a": {}})
        nested_empty_d = {"a": {}}
        self.assertNotEqual(self.r1, nested_empty_d)
        self.assertNotEqual(nested_empty_r, self.d1)
        nested_empty_r.clear()

    def test_is_comparison(self):
        self.assertTrue(self.r1 is self.r1)
        self.assertFalse(self.r1 is self.r2)
        self.assertTrue(self.r2 is self.r2)
        self.assertFalse(self.r2 is self.r3)

    def test_is_comparison_with_dict(self):
        self.assertFalse(self.r1 is self.d1)
        self.assertFalse(self.d2 is self.d1)

    def test_is_not_comparison(self):
        self.assertFalse(self.r1 is not self.r1)
        self.assertTrue(self.r1 is not self.r2)
        self.assertFalse(self.r2 is not self.r2)
        self.assertTrue(self.r2 is not self.r3)

    def test_is_not_comparison_with_dict(self):
        self.assertTrue(self.r1 is not self.d1)
        self.assertTrue(self.d2 is not self.d1)

    def test_lt(self):
        with self.assertRaises(TypeError):
            self.r1 < self.r2

    def test_lt_with_different_type(self):
        with self.assertRaises(TypeError):
            self.r1 < self.d1

    def test_le(self):
        with self.assertRaises(TypeError):
            self.r1 <= self.r2

    def test_le_with_different_type(self):
        with self.assertRaises(TypeError):
            self.r1 <= self.d1

    def test_ge(self):
        with self.assertRaises(TypeError):
            self.r1 >= self.r2

    def test_ge_with_different_type(self):
        with self.assertRaises(TypeError):
            self.r1 >= self.d1

    def test_gt(self):
        with self.assertRaises(TypeError):
            self.r1 > self.r2

    def test_gt_with_different_type(self):
        with self.assertRaises(TypeError):
            self.r1 > self.d1

    def test_sequential_comparison(self):
        d = {}
        d2 = {}
        rd = RedisDict(namespace="sequential_comparison")

        # Testing for identity
        self.assertTrue(d is not d2)
        self.assertTrue(d is not rd)

        # Testing for equality
        self.assertTrue(d == d2)
        self.assertTrue(d == rd)
        self.assertTrue(d.items() == d2.items())
        self.assertTrue(list(d.items()) == list(rd.items()))

        d["foo1"] = "bar1"

        # Testing for inequality after modification in 'd'
        self.assertTrue(d != d2)
        self.assertTrue(d != rd)
        self.assertTrue(d.items() != d2.items())
        self.assertTrue(list(d.items()) != list(rd.items()))

        # Modifying 'd2' and 'rd'
        d2["foo1"] = "bar1"
        rd["foo1"] = "bar1"

        # Testing for equality
        self.assertTrue(d == d2)
        self.assertTrue(d == rd)
        self.assertTrue(d.items() == d2.items())
        self.assertTrue(list(d.items()) == list(rd.items()))

        d.clear()
        d2.clear()
        rd.clear()

        rd.update({"a": {}})
        d.update({"a": {}})
        d2.update({"a": {}})

        # Testing for nested comparison
        self.assertTrue(d == d2)
        self.assertTrue(d == rd)
        self.assertTrue(d.items() == d2.items())
        self.assertTrue(list(d.items()) == list(rd.items()))

        d.clear()

        # Testing for inequality after clear
        self.assertFalse(d == d2)
        self.assertFalse(d == rd)
        self.assertFalse(d.items() == d2.items())
        self.assertFalse(list(d.items()) == list(rd.items()))

        d2.clear()
        rd.clear()

        # Testing for equality after clear
        self.assertTrue(d == d2)
        self.assertTrue(d == rd)
        self.assertTrue(d.items() == d2.items())
        self.assertTrue(list(d.items()) == list(rd.items()))


class TestRedisDictPreserveExpire(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.redisdb = redis.StrictRedis(**redis_config)
        cls.r = cls.create_redis_dict()

    @classmethod
    def tearDownClass(cls):
        cls.clear_test_namespace()
        pass

    @classmethod
    def create_redis_dict(cls, namespace=TEST_NAMESPACE_PREFIX, **kwargs):
        config = redis_config.copy()
        config.update(kwargs)
        return RedisDict(namespace=namespace, **config)

    @classmethod
    def clear_test_namespace(cls):
        for key in cls.redisdb.scan_iter('{}:*'.format(TEST_NAMESPACE_PREFIX)):
            cls.redisdb.delete(key)

    def setUp(self):
        self.clear_test_namespace()

    def test_preserve_expiration(self):
        """Test preserve_expiration configuration parameter."""
        redis_dict = self.create_redis_dict(expire=3600, preserve_expiration=True)

        key = "foo"
        value = "bar"
        redis_dict[key] = value

        # Ensure the TTL (time-to-live) of the "foo" key is approximately the global `expire` time.
        actual_ttl = redis_dict.get_ttl(key)
        self.assertAlmostEqual(3600, actual_ttl, delta=1)

        time_sleeping = 3
        time.sleep(time_sleeping)

        # Override the "foo" value and create a new "bar" key.
        new_key = "bar"
        redis_dict[key] = "value"
        redis_dict[new_key] = "value too"

        # Ensure the TTL of the "foo" key has passed 3 seconds.
        actual_ttl_foo = redis_dict.get_ttl(key)
        self.assertAlmostEqual(3600 - time_sleeping, actual_ttl_foo, delta=1)

        # Ensure the TTL of the "bar" key is also approximately the global `expire` time.
        actual_ttl_bar = redis_dict.get_ttl(new_key)

        self.assertAlmostEqual(3600, actual_ttl_bar, delta=1)

        # Ensure the difference between the TTLs of "foo" and "bar" is at least 2 seconds.
        self.assertTrue(abs(actual_ttl_foo - actual_ttl_bar) >= 1)

    def test_preserve_expiration_not_used(self):
        """Test preserve_expiration configuration parameter."""
        redis_dict = self.create_redis_dict(expire=3600)

        key = "foo"
        value = "bar"
        redis_dict[key] = value

        # Ensure the TTL (time-to-live) of the "foo" key is approximately the global `expire` time.
        actual_ttl = redis_dict.get_ttl(key)
        self.assertAlmostEqual(3600, actual_ttl, delta=1)

        time_sleeping = 3
        time.sleep(time_sleeping)

        # Override the "foo" value and create a new "bar" key.
        new_key = "bar"
        redis_dict[key] = "value"
        redis_dict[new_key] = "value too"

        # Ensure the TTL of the "foo" key is global expire again.
        actual_ttl_foo = redis_dict.get_ttl(key)
        self.assertAlmostEqual(3600, actual_ttl_foo, delta=1)

        # Ensure the TTL of the "bar" key is also approximately the global `expire` time.
        actual_ttl_bar = redis_dict.get_ttl(new_key)

        self.assertAlmostEqual(3600, actual_ttl_bar, delta=1)

        # Ensure the difference between the TTLs of "foo" and "bar" is no more than one second.
        self.assertTrue(abs(actual_ttl_foo - actual_ttl_bar) <= 1)


class TestRedisDictWithHypothesis(unittest.TestCase):
    """
    A test suite employing Hypothesis for property-based testing of RedisDict.

    This class uses the Hypothesis library to perform fuzz testing on
    RedisDict instances. Through the generation of diverse inputs, edge cases, and randomized
    scenarios, this test suite aims to evaluate the correctness and resilience of the RedisDict
    implementation under various conditions. The goal is to cover a broad spectrum of potential
    interactions and behaviors, ensuring the implementation can handle complex and unforeseen
    situations.
    """

    def setUp(self):
        self.r = RedisDict(namespace="test_with_fuzzing")

    def tearDown(self):
        self.r.clear()

    @given(key=st.text(min_size=1), value=st.text())
    def test_set_get_text(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.integers())
    def test_set_get_integer(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.floats(allow_nan=False, allow_infinity=False))
    def test_set_get_float(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.booleans())
    def test_set_get_boolean(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.none())
    def test_set_get_none(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.lists(st.integers()))
    def test_set_get_list_of_integers(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.lists(st.text()))
    def test_set_get_list_of_text(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.dictionaries(st.text(min_size=1), st.text()))
    def test_set_get_dictionary(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.dictionaries(st.text(min_size=1), st.integers()))
    def test_set_get_dictionary_with_integer_values(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1),
           value=st.dictionaries(st.text(min_size=1), st.floats(allow_nan=False, allow_infinity=False)))
    def test_set_get_dictionary_with_float_values(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.dictionaries(st.text(min_size=1), st.lists(st.integers())))
    def test_set_get_dictionary_with_list_values(self, key, value):
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1),
           value=st.dictionaries(st.text(min_size=1), st.dictionaries(st.text(min_size=1), st.text())))
    def test_set_get_nested_dictionary(self, key, value):
        """
        Test setting and getting a nested dictionary.
        """
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.lists(st.lists(st.integers())))
    def test_set_get_nested_list(self, key, value):
        """
        Test setting and getting a nested list.
        """
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1),
           value=st.tuples(st.integers(), st.text(), st.floats(allow_nan=False, allow_infinity=False), st.booleans()))
    def test_set_get_tuple(self, key, value):
        """
        Test setting and getting a tuple.
        """
        self.r[key] = value
        self.assertEqual(self.r[key], value)

    @given(key=st.text(min_size=1), value=st.sets(st.integers()))
    def test_set_get_set(self, key, value):
        """
        Test setting and getting a set.
        """
        self.r[key] = value
        self.assertEqual(self.r[key], value)

if __name__ == '__main__':
    unittest.main()
