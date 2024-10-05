import unittest
from collections.abc import MutableMapping

from redis_dict import RedisDict

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Expected:
    key: str
    value: str


class TestMutableMappingCompleteness(unittest.TestCase):

    def setUp(self):
        self.mapping = RedisDict()

    def tearDown(self):
        self.mapping.clear()
        self.mapping = None

    def test_abstract_method_implementation(self):
        """Test that all abstract methods are implemented.
        frozenset({'__setitem__', '__iter__', '__len__', '__getitem__', '__delitem__'})
        """
        abstract_methods = MutableMapping.__abstractmethods__

        for method in abstract_methods:
            self.assertTrue(
                hasattr(
                    self.mapping, method) and callable(getattr(self.mapping, method)),
                f"Abstract method {method} is not implemented")

    def test_getitem_behavior(self):
        """Test __getitem__ behavior, including KeyError for missing keys."""
        expected = Expected(key='key', value='value')
        self.mapping[expected.key] = expected.value

        self.assertEqual(self.mapping[expected.key], expected.value)
        with self.assertRaises(KeyError):
            _ = self.mapping['nonexistent']

    def test_setitem_behavior(self):
        """Test __setitem__ behavior, including overwriting existing keys."""
        expected = Expected(key='key', value='value')

        self.mapping[expected.key] = 'foobar'
        self.mapping[expected.key] = expected.value

        self.assertEqual(self.mapping[expected.key], expected.value)

    @unittest.skip
    def test_delitem_behavior(self):
        """Test __delitem__ behavior, including KeyError for missing keys.

         Note: Known difference from dictionary behavior.
         See https://github.com/Attumm/redis-dict/issues/46

         There is a race condition in which multiple instances can add and remove a key.
         Consider the following scenario:
         server_1: dict["foo"] = "bar"
         server_2: dict["foo"] = "bar"
         server_1: del dict["foo"]
         server_2: del dict["foo"]

         Adding the KeyError could cause issues downstream for users of redis-dict
         within production environments that are difficult to catch and debug.
         The issue would only arise in production environments, and since the data
         is gone, looking for data that is not present is a difficult task.

         The upside of having the same behavior as a regular dictionary is small
         compared to the potential for race conditions.

         A second downside is that it would create a double operation for deletion,
         as we would have to check the existence of the key. This would mean creating
         a transaction and sending 2 commands.

         Given these considerations, we've chosen not to raise a KeyError for
         missing keys in the __delitem__ method.

         There might be a version that will adhere more strictly to a dictionary
         in the future.
         """
        expected = Expected(key='key', value='value')

        self.mapping[expected.key] = expected.value
        del self.mapping[expected.key]

        with self.assertRaises(KeyError):
            del self.mapping[expected.key]

    def test_iter_behavior(self):
        """Test __iter__ behavior, ensuring all keys are iterable."""
        test_keys = ['a', 'b', 'c']
        for key in test_keys:
            self.mapping[key] = key
        self.assertSetEqual(set(self.mapping), set(test_keys))

    def test_len_behavior(self):
        """Test __len__ behavior with additions and deletions."""
        self.assertEqual(len(self.mapping), 0)
        self.mapping['key1'] = 'value1'
        self.mapping['key2'] = 'value2'
        self.assertEqual(len(self.mapping), 2)
        del self.mapping['key1']
        self.assertEqual(len(self.mapping), 1)

    def test_update_method(self):
        """Test the update method provided by MutableMapping."""
        self.mapping.update({'a': 1, 'b': 2})
        self.assertEqual(self.mapping['a'], 1)
        self.assertEqual(self.mapping['b'], 2)

    def test_pop_method(self):
        """Test the pop method, including KeyError and default value."""
        self.mapping['key'] = 'value'
        self.assertEqual(self.mapping.pop('key'), 'value')
        self.assertEqual(self.mapping.pop('nonexistent', 'default'), 'default')
        with self.assertRaises(KeyError):
            self.mapping.pop('nonexistent')

    def test_clear_method(self):
        """Test the clear method."""
        self.mapping.update({'a': 1, 'b': 2, 'c': 3})
        self.mapping.clear()
        self.assertEqual(len(self.mapping), 0)

    def test_view_methods(self):
        """Test keys, values, and items view methods."""
        self.mapping.update({'a': 1, 'b': 2, 'c': 3})
        self.assertIsInstance(self.mapping.keys(), MutableMapping.keys)
        self.assertIsInstance(self.mapping.values(), MutableMapping.values)
        self.assertIsInstance(self.mapping.items(), MutableMapping.items)


if __name__ == '__main__':
    unittest.main()

# Most tests pass successfully, which is great. However, tests for keys(), values(), and items()
# methods fail. This is because these methods return lists or custom iterators instead of the
# special view objects (KeysView, ValuesView, ItemsView) that the MutableMapping tests expect.
# This design choice was made due to Redis's distributed nature, making true dict-like views challenging.
"""
$ python mutablemapping_tests.py 
..s......E
======================================================================
ERROR: test_view_methods (__main__.TestMutableMappingCompleteness.test_view_methods)
Test keys, values, and items view methods.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "Development/redis-dict/mutablemapping_tests.py", line 135, in test_view_methods
    self.assertIsInstance(self.mapping.keys(), MutableMapping.keys)
  File "python3/unittest/case.py", line 1294, in assertIsInstance
    if not isinstance(obj, cls):
           ^^^^^^^^^^^^^^^^^^^^
TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union

----------------------------------------------------------------------
Ran 10 tests in 0.048s

FAILED (errors=1, skipped=1)
"""

# redis_dict.py passed mypy --strict before recent changes.
# Current mypy output suggests we need to reconsider our approach.
# For better integration with LSP and IDEs, alternative methods are available:
# Python protocols, py.typed file, .pyi stub files, and mypy configuration.
"""
mypy redis_dict.py --strict 
redis_dict.py:303: error: Argument 1 of "__contains__" is incompatible with supertype "Mapping"; supertype defines the argument type as "object"  [override]
redis_dict.py:303: note: This violates the Liskov substitution principle
redis_dict.py:303: note: See https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides
redis_dict.py:303: error: Argument 1 of "__contains__" is incompatible with supertype "Container"; supertype defines the argument type as "object"  [override]
redis_dict.py:423: error: Return type "List[str]" of "keys" incompatible with return type "KeysView[Any]" in supertype "Mapping"  [override]
redis_dict.py:443: error: Return type "List[Tuple[str, Any]]" of "items" incompatible with return type "ItemsView[Any, Any]" in supertype "Mapping"  [override]
redis_dict.py:452: error: Return type "List[Any]" of "values" incompatible with return type "ValuesView[Any]" in supertype "Mapping"  [override]
redis_dict.py:574: error: Signature of "update" incompatible with supertype "MutableMapping"  [override]
redis_dict.py:574: note:      Superclass:
redis_dict.py:574: note:          @overload
redis_dict.py:574: note:          def update(self, SupportsKeysAndGetItem[Any, Any], /, **kwargs: Any) -> None
redis_dict.py:574: note:          @overload
redis_dict.py:574: note:          def update(self, Iterable[Tuple[Any, Any]], /, **kwargs: Any) -> None
redis_dict.py:574: note:          @overload
redis_dict.py:574: note:          def update(self, **kwargs: Any) -> None
redis_dict.py:574: note:      Subclass:
redis_dict.py:574: note:          def update(self, dic: Dict[str, Any]) -> None
redis_dict.py:574: note:          @overload
redis_dict.py:574: note:          def update(self, SupportsKeysAndGetItem[Any, Any], /, **kwargs: Any) -> None
redis_dict.py:574: note:          @overload
redis_dict.py:574: note:          def update(self, Iterable[Tuple[Any, Any]], /, **kwargs: Any) -> None
redis_dict.py:574: note:          @overload
redis_dict.py:574: note:          def update(self, **kwargs: Any) -> None
redis_dict.py:574: note:          def update(self, dic: Dict[str, Any]) -> None
Found 6 errors in 1 file (checked 1 source file)
"""

