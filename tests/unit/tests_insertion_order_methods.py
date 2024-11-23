import unittest

from redis_dict import PythonRedisDict

TEST_NAMESPACE_PREFIX = "TEST_NAMESPACE_PREFIX_eojfe"

class TestRedisDictInsertionOrder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = cls.create_redis_dict()

    @classmethod
    def tearDownClass(cls):
        cls.clear_test_namespace()

    @classmethod
    def create_redis_dict(cls, namespace=TEST_NAMESPACE_PREFIX, **kwargs):
        return PythonRedisDict(namespace=namespace, **kwargs)

    @classmethod
    def clear_test_namespace(cls):
        cls.r.redis.flushdb()

    def setUp(self):
        self.clear_test_namespace()
        self.redis_dict = self.create_redis_dict()


    def test_insertion_order_empty(self):
        result = list(self.redis_dict._insertion_order_iter())
        self.assertEqual([], result)
        self.assertFalse(self.redis_dict._insertion_order_len())
        self.assertIsNone(self.redis_dict._insertion_order_latest())

    def test_insertion_order_add_single(self):
        self.assertTrue(self.redis_dict._insertion_order_add("foo"))

        items = list(self.redis_dict._insertion_order_iter())
        self.assertEqual(1, len(items))
        self.assertEqual("foo", items[0])

        self.assertTrue(self.redis_dict._insertion_order_len())
        self.assertEqual("foo", self.redis_dict._insertion_order_latest())

    def test_insertion_order_delete_single(self):
        self.redis_dict._insertion_order_add("foo")
        self.assertTrue(self.redis_dict._insertion_order_delete("foo"))

        items = list(self.redis_dict._insertion_order_iter())
        self.assertEqual(0, len(items))
        self.assertFalse(self.redis_dict._insertion_order_len())
        self.assertIsNone(self.redis_dict._insertion_order_latest())

    def test_insertion_order_multiple_items(self):
        self.redis_dict._insertion_order_add("foo1")
        self.redis_dict._insertion_order_add("foo2")

        items = list(self.redis_dict._insertion_order_iter())
        self.assertEqual(2, len(items))
        self.assertTrue(self.redis_dict._insertion_order_len())
        self.assertEqual("foo2", self.redis_dict._insertion_order_latest())

    def test_insertion_order_clear(self):
        self.redis_dict._insertion_order_add("foo1")
        self.redis_dict._insertion_order_add("foo2")

        self.assertTrue(self.redis_dict._insertion_order_clear())

        items = list(self.redis_dict._insertion_order_iter())
        self.assertEqual(0, len(items))
        self.assertFalse(self.redis_dict._insertion_order_len())
        self.assertIsNone(self.redis_dict._insertion_order_latest())

    def test_insertion_order_add_empty_string(self):
        self.assertTrue(self.redis_dict._insertion_order_add(""))
        self.assertEqual("", self.redis_dict._insertion_order_latest())
        self.assertTrue(self.redis_dict._insertion_order_len())

    def test_insertion_order_add_duplicate(self):
        self.assertTrue(self.redis_dict._insertion_order_add("foo"))
        self.assertFalse(self.redis_dict._insertion_order_add("foo"))
        items = list(self.redis_dict._insertion_order_iter())
        self.assertEqual(1, len(items))

    def test_insertion_order_delete_nonexistent(self):
        self.assertFalse(self.redis_dict._insertion_order_delete("nonexistent"))

    def test_insertion_order_delete_empty_string(self):
        self.redis_dict._insertion_order_add("")
        self.assertTrue(self.redis_dict._insertion_order_delete(""))
        self.assertIsNone(self.redis_dict._insertion_order_latest())

    def test_insertion_order_iter_100(self):
        expected, expected_items = "", 100
        for i in range(expected_items):
            expected = f"foo{i}"
            self.redis_dict._insertion_order_add(expected)
        items = list(self.redis_dict._insertion_order_iter())
        self.assertEqual(expected_items, len(items))
        self.assertEqual(expected_items, self.redis_dict._insertion_order_len())

    def test_insertion_order_iter_10000(self):
        expected, expected_items = "", 10000
        with self.redis_dict.pipeline():
            for i in range(expected_items):
                expected = f"foo{i}"
                self.redis_dict._insertion_order_add(expected)

        items = list(self.redis_dict._insertion_order_iter())
        self.assertEqual(expected_items, len(items))
        self.assertEqual(self.redis_dict._insertion_order_latest(), expected)
        self.assertEqual(expected_items, self.redis_dict._insertion_order_len())

    def test_insertion_order_latest_after_delete_last(self):
        self.redis_dict._insertion_order_add("foo1")
        self.redis_dict._insertion_order_add("foo2")
        self.redis_dict._insertion_order_delete("foo2")
        self.assertEqual("foo1", self.redis_dict._insertion_order_latest())

if __name__ == "__main__":
    unittest.main()
