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


if __name__ == '__main__':
    unittest.main()
