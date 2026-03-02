"""Tests for nested dictionary support (Issue #52).

Dict values are always stored as individual chain keys so that each leaf
value is managed independently by Redis.  Reading the parent key reassembles
the dict transparently, including arbitrary-depth nesting.  No opt-in flag
is required.
"""
import unittest

import redis

from redis_dict import RedisDict
from redis_dict.core import _DEFAULT_SEPARATOR

SEP = _DEFAULT_SEPARATOR

TEST_NAMESPACE_PREFIX = '__test_nested_dict_8130__'

redis_config = {
    'host': 'localhost',
    'port': 6379,
    'db': 11,
}


class _NestedDictTestBase(unittest.TestCase):
    """Shared setup/teardown for nested dict test classes."""

    @classmethod
    def setUpClass(cls):
        cls.redisdb = redis.StrictRedis(**redis_config)

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

    def tearDown(self):
        self.clear_test_namespace()


class TestNestedDict(_NestedDictTestBase):
    """Tests for always-on nested dict support."""

    def test_dict_stored_as_individual_chain_keys(self):
        """Dict assignment creates one Redis key per leaf item; no sentinel at the parent key."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'c2': 3}
        self.assertEqual(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:var{SEP}c'), b'int:1')
        self.assertEqual(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:var{SEP}c2'), b'int:3')
        # Parent key must not exist — no sentinel is stored.
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:var'))

    def test_getitem_reassembles_nested_dict(self):
        """__getitem__ transparently assembles chain keys back into a dict."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'c2': 3}
        self.assertEqual(r['var'], {'c': 1, 'c2': 3})

    def test_contains_nested_dict_key(self):
        """'in' returns True when chain keys exist for the given parent key."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1}
        self.assertIn('var', r)

    def test_del_removes_all_chain_keys(self):
        """Deleting a nested dict key removes all associated chain keys from Redis."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'c2': 3}
        del r['var']
        with self.assertRaises(KeyError):
            _ = r['var']
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:var{SEP}c'))
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:var{SEP}c2'))

    def test_overwrite_nested_dict_removes_stale_keys(self):
        """Overwriting a nested dict purges old chain keys not in the new dict."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'old_key': 99}
        r['var'] = {'c': 2, 'new_key': 42}
        self.assertEqual(r['var'], {'c': 2, 'new_key': 42})
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:var{SEP}old_key'))

    def test_replace_nested_dict_with_scalar(self):
        """Assigning a scalar after a nested dict replaces it correctly."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1}
        r['var'] = 'scalar'
        self.assertEqual(r['var'], 'scalar')

    def test_scalar_values_unaffected(self):
        """Scalar values still work normally."""
        r = self.create_redis_dict()
        r['key'] = 'hello'
        self.assertEqual(r['key'], 'hello')

    def test_subscript_assignment_updates_redis(self):
        """rd['key']['sub'] = value persists the new leaf value in Redis."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'c2': 3}
        r['var']['c'] = 2
        self.assertEqual(r['var'], {'c': 2, 'c2': 3})
        self.assertEqual(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:var{SEP}c'), b'int:2')

    def test_subscript_assignment_deep_nesting(self):
        """rd['key']['a']['b'] = value persists correctly for deep nesting."""
        r = self.create_redis_dict()
        r['root'] = {'a': {'b': 1, 'c': 2}}
        r['root']['a']['b'] = 99
        self.assertEqual(r['root'], {'a': {'b': 99, 'c': 2}})
        self.assertEqual(
            self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:root{SEP}a{SEP}b'), b'int:99'
        )

    def test_chain_set_and_nested_dict_interoperable(self):
        """chain_set can add sub-keys to a key that was set as a nested dict."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1}
        r.chain_set(['var', 'd'], 2)
        self.assertEqual(r['var'], {'c': 1, 'd': 2})

    def test_nested_dict_with_custom_separator(self):
        """Nested dict works correctly combined with a non-default separator."""
        r = self.create_redis_dict(separator='/')
        r['var'] = {'c': 1, 'c2': 3}
        self.assertEqual(self.redisdb.get('{}:var/c'.format(TEST_NAMESPACE_PREFIX)), b'int:1')
        self.assertEqual(self.redisdb.get('{}:var/c2'.format(TEST_NAMESPACE_PREFIX)), b'int:3')
        self.assertEqual(r['var'], {'c': 1, 'c2': 3})

    def test_deep_nested_dict_stored_as_leaf_chain_keys(self):
        """A multi-level nested dict is flattened to individual leaf keys in Redis.

        No parent key is stored (no sentinel); intermediate path segments are
        not stored either.
        """
        r = self.create_redis_dict()
        r['root'] = {'a': {'b': 1, 'c': 2}}
        self.assertEqual(
            self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:root{SEP}a{SEP}b'), b'int:1'
        )
        self.assertEqual(
            self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:root{SEP}a{SEP}c'), b'int:2'
        )
        # Top-level parent key must not exist — no sentinel is stored.
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:root'))
        # Intermediate path segment is not stored.
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:root{SEP}a'))

    def test_deep_nested_dict_round_trips(self):
        """A multi-level nested dict is reassembled correctly on read."""
        r = self.create_redis_dict()
        original = {'a': {'b': 1, 'c': 2}, 'd': 3}
        r['root'] = original
        self.assertEqual(r['root'], original)

    def test_three_level_nesting_round_trips(self):
        """Three levels of nesting are stored and reassembled correctly."""
        r = self.create_redis_dict()
        original = {'x': {'y': {'z': 42}}}
        r['root'] = original
        self.assertEqual(r['root'], original)

    def test_deep_nested_dict_del_removes_all_leaf_keys(self):
        """Deleting a deeply nested dict key removes all leaf chain keys."""
        r = self.create_redis_dict()
        r['root'] = {'a': {'b': 1, 'c': 2}}
        del r['root']
        with self.assertRaises(KeyError):
            _ = r['root']
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:root{SEP}a{SEP}b'))
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:root{SEP}a{SEP}c'))

    # --- iteration and cardinality ---

    def test_keys_returns_only_logical_top_level_keys(self):
        """keys() returns the parent key, not the individual chain sub-keys."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'c2': 3}
        self.assertEqual(sorted(r.keys()), ['var'])

    def test_keys_mixed_scalar_and_nested(self):
        """keys() includes both scalar keys and nested-dict root keys."""
        r = self.create_redis_dict()
        r['scalar'] = 42
        r['nested'] = {'a': 1, 'b': 2}
        self.assertEqual(sorted(r.keys()), ['nested', 'scalar'])

    def test_items_returns_logical_pairs(self):
        """items() yields (parent_key, assembled_dict), not raw chain sub-keys."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'c2': 3}
        self.assertEqual(dict(r.items()), {'var': {'c': 1, 'c2': 3}})

    def test_values_returns_assembled_dicts(self):
        """values() yields the assembled dict, not individual leaf values."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'c2': 3}
        self.assertEqual(list(r.values()), [{'c': 1, 'c2': 3}])

    def test_len_counts_logical_keys(self):
        """len() counts nested dicts as a single item, not as one per leaf."""
        r = self.create_redis_dict()
        r['scalar'] = 99
        r['nested'] = {'x': 1, 'y': 2}
        self.assertEqual(len(r), 2)

    def test_to_dict_assembles_nested_dicts(self):
        """to_dict() reconstructs nested dicts instead of exposing chain sub-keys."""
        r = self.create_redis_dict()
        r['a'] = 1
        r['b'] = {'x': 10, 'y': 20}
        self.assertEqual(r.to_dict(), {'a': 1, 'b': {'x': 10, 'y': 20}})

    def test_iter_yields_logical_keys(self):
        """Iterating the RedisDict yields logical top-level keys only."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1}
        r['plain'] = 'hello'
        self.assertEqual(sorted(r), ['plain', 'var'])

    def test_popitem_returns_logical_pair(self):
        """popitem() returns (parent_key, assembled_dict), not a chain sub-key."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'c2': 3}
        key, value = r.popitem()
        self.assertEqual(key, 'var')
        self.assertEqual(value, {'c': 1, 'c2': 3})
        self.assertEqual(len(r), 0)

    # --- empty dict ---

    def test_empty_dict_roundtrip(self):
        """Setting a key to {} stores and retrieves an empty dict without KeyError."""
        r = self.create_redis_dict()
        r['var'] = {}
        self.assertEqual(r['var'], {})

    def test_empty_dict_in_contains(self):
        """A key set to {} is found by the 'in' operator."""
        r = self.create_redis_dict()
        r['var'] = {}
        self.assertIn('var', r)

    def test_dict_with_empty_dict_value_roundtrip(self):
        """A dict whose only leaf values are empty dicts round-trips correctly."""
        r = self.create_redis_dict()
        r['var'] = {'a': {}}
        self.assertEqual(r['var'], {'a': {}})

    def test_overwrite_with_empty_dict(self):
        """Overwriting a populated nested dict with {} stores an empty dict and removes old chain keys."""
        r = self.create_redis_dict()
        r['var'] = {'c': 1, 'c2': 3}
        r['var'] = {}
        self.assertEqual(r['var'], {})
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:var{SEP}c'))
        self.assertIsNone(self.redisdb.get(f'{TEST_NAMESPACE_PREFIX}:var{SEP}c2'))


if __name__ == '__main__':
    unittest.main()
