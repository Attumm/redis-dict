import unittest

import redis

from redis_dict import RedisDict

# !! Make sure you don't have keys named like this, they will be deleted.
TEST_NAMESPACE_PREFIX = 'test_rd'

redis_config = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
}


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

    def test_keys_empty(self):
        """Calling RedisDict.keys() should return an empty list."""
        keys = self.r.keys()

        self.assertEqual(keys, [])

    def test_set_namespace(self):
        """Test that RedisDict keys are inserted with the given namespace."""
        self.r['foo'] = 'bar'

        expected_keys = ['{}:foo'.format(TEST_NAMESPACE_PREFIX)]
        actual_keys = self.redisdb.keys('{}:*'.format(TEST_NAMESPACE_PREFIX))

        self.assertEqual(expected_keys, actual_keys)

    def test_set_and_get(self):
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

    def test_get_nonexisting(self):
        """Test that retrieving a non-existing key raises a KeyError."""
        with self.assertRaises(KeyError):
            _ = self.r['nonexistingkey']

    def test_delete(self):
        """Test deleting a key."""
        self.r['foobargone'] = 'bars'

        del self.r['foobargone']

        self.assertEqual(self.redisdb.get('foobargone'), None)

    def test_contains_empty(self):
        """Tests the __contains__ function with no keys set."""
        self.assertFalse('foobar' in self.r)

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
        self.r['foobars'] = 'barrbars'
        expected_repr = str({u'foobars': u'barrbars'})
        actual_repr = repr(self.r)
        self.assertEqual(actual_repr, expected_repr)

    def test_str_nonempty(self):
        """Tests the __repr__ function with keys set."""
        self.r['foobars'] = 'barrbars'
        expected_str = str({u'foobars': u'barrbars'})
        actual_str = str(self.r)
        self.assertEqual(actual_str, expected_str)

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
        self.assertEqual(self.redisdb.get(expected_key), 'melons')

    def test_chain_set_2(self):
        """Test setting a chain with 2 elements."""
        self.r.chain_set(['foo', 'bar'], 'melons')

        expected_key = '{}:foo:bar'.format(TEST_NAMESPACE_PREFIX)
        self.assertEqual(self.redisdb.get(expected_key), 'melons')

    def test_chain_set_overwrite(self):
        """Test setting a chain with 1 element and then overwriting it."""
        self.r.chain_set(['foo'], 'melons')
        self.r.chain_set(['foo'], 'bananas')

        expected_key = '{}:foo'.format(TEST_NAMESPACE_PREFIX)
        self.assertEqual(self.redisdb.get(expected_key), 'bananas')

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
        """Test adding keys with an expire value by using the contextmanager."""
        with self.r.expire_at(3600):
            self.r['foobar'] = 'barbar'

        actual_ttl = self.redisdb.ttl('{}:foobar'.format(TEST_NAMESPACE_PREFIX))
        self.assertAlmostEqual(3600, actual_ttl, delta=2)

    def test_expire_keyword(self):
        """Test ading keys with an expire value by using the expire config keyword."""
        r = self.create_redis_dict(expire=3600)

        r['foobar'] = 'barbar'
        actual_ttl = self.redisdb.ttl('{}:foobar'.format(TEST_NAMESPACE_PREFIX))
        self.assertAlmostEqual(3600, actual_ttl, delta=2)

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


if __name__ == '__main__':
    unittest.main()
