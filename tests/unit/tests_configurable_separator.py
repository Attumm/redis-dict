"""Tests for configurable chain separator (Issue #52).

The chain separator defaults to '➡️    ' (right-arrow emoji + spaces) to avoid
key collisions.  Users can supply any explicit separator instead.
"""
import unittest

import redis

from redis_dict import RedisDict
from redis_dict.core import _DEFAULT_SEPARATOR


TEST_NAMESPACE_PREFIX = '__test_separator_8129__'

redis_config = {
    'host': 'localhost',
    'port': 6379,
    'db': 11,
}


class TestConfigurableSeparator(unittest.TestCase):

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

    def test_default_separator_is_arrow(self):
        """Default chain separator is the collision-safe emoji+spaces string."""
        r = self.create_redis_dict()
        self.assertEqual(r.separator, _DEFAULT_SEPARATOR)

    def test_chain_set_slash_separator_redis_key(self):
        """chain_set with '/' separator creates the correct Redis key."""
        r = self.create_redis_dict(separator='/')
        r.chain_set(['foo', 'bar'], 'melons')
        self.assertEqual(self.redisdb.get('{}:foo/bar'.format(TEST_NAMESPACE_PREFIX)), b'str:melons')

    def test_chain_get_slash_separator(self):
        """chain_get round-trips through a '/' separator."""
        r = self.create_redis_dict(separator='/')
        r.chain_set(['foo', 'bar'], 'melons')
        self.assertEqual(r.chain_get(['foo', 'bar']), 'melons')

    def test_chain_del_slash_separator(self):
        """chain_del removes the key built with a custom separator."""
        r = self.create_redis_dict(separator='/')
        r.chain_set(['foo', 'bar'], 'melons')
        r.chain_del(['foo', 'bar'])
        with self.assertRaises(KeyError):
            r.chain_get(['foo', 'bar'])

    def test_multi_chain_get_slash_separator(self):
        """multi_chain_get works correctly with a custom separator."""
        r = self.create_redis_dict(separator='/')
        r.chain_set(['foo', 'bar', 'bar'], 'barbar')
        r.chain_set(['foo', 'bar', 'baz'], 'bazbaz')
        self.assertEqual(sorted(r.multi_chain_get(['foo', 'bar'])), sorted(['barbar', 'bazbaz']))

    def test_separator_avoids_colon_key_collision(self):
        """With '/' separator, a user key containing ':' does not collide with chain key."""
        r = self.create_redis_dict(separator='/')
        r['foo:bar'] = 'direct'
        r.chain_set(['foo', 'bar'], 'chained')
        self.assertEqual(r['foo:bar'], 'direct')
        self.assertEqual(r.chain_get(['foo', 'bar']), 'chained')


if __name__ == '__main__':
    unittest.main()
