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

class TestRedisDictBehaviorDict(unittest.TestCase):
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

        input_values = (("int", 1), ("float", 0.9), ("str", "im a string"), ("bool", True), ("None", None))

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

        for key in redis_dic.iterkeys():
            self.assertTrue(key in input_items)

        for key in redis_dic.keys():
            self.assertTrue(key in input_items)

        for key, value in redis_dic.items():
            self.assertEqual(input_items[key], value)
            self.assertEqual(dic[key], value)

        for key, value in redis_dic.iteritems():
            self.assertEqual(input_items[key], value)
            self.assertEqual(dic[key], value)

        input_values = list(input_items.values())
        dic_values = list(input_items.values())
        result_values = list(redis_dic.itervalues())

        self.assertEqual(sorted(map(str, input_values)), sorted(map(str, result_values)))
        self.assertEqual(sorted(map(str, dic_values)), sorted(map(str, result_values)))

        result_values = list(redis_dic.itervalues())
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
            self.assertEqual(len(dic), len(input_items)-i)
            self.assertEqual(len(redis_dic), len(input_items)-i)

        with self.assertRaises(KeyError):
            dic.pop("item")
        with self.assertRaises(KeyError):
            redis_dic.pop("item")

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

        with self.assertRaisesRegex(KeyError, "popitem\(\): dictionary is empty"):
            dic.popitem()
        with self.assertRaisesRegex(KeyError, "popitem\(\): dictionary is empty"):
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
            'b': 3,
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

    def test_dict_method_pipeline_buffer_sets(self):
        redis_dic = self.create_redis_dict()
        expected = {
            'a': 1,
            'b': 2,
            'b': 3,
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
                redis_dic[k] = v*2
            for k, v in expected.items():
                self.assertEqual(redis_dic[k], v)

        for k, v in expected.items():
            self.assertEqual(redis_dic[k], v*2)
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

    # TODO behavior of multi and chain methods should be discussed.
    @unittest.skip
    def test_multi_get_with_key_none(self):
        """Tests that multi_get with key None raises TypeError."""
        with self.assertRaises(TypeError):
            self.r.multi_get(None)

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


if __name__ == '__main__':
    unittest.main()
