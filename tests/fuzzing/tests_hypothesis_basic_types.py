import unittest

from hypothesis import given, strategies as st

from redis_dict import RedisDict, PythonRedisDict


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


class TestPythonRedisDictWithHypothesis(TestRedisDictWithHypothesis):
    """
    A test suite employing Hypothesis for property-based testing of PythonRedisDict.
    """

    def setUp(self):
        self.r = PythonRedisDict(namespace="test_with_fuzzing")


if __name__ == '__main__':
    unittest.main()
