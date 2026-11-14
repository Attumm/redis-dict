import unittest
from datetime import timedelta

from hypothesis import given, settings, strategies as st

from redis_dict import RedisDict, PythonRedisDict


def _create_hypothesis_suite(dict_cls, namespace):
    class _HypothesisSuite(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.r = dict_cls(namespace=namespace)

        @classmethod
        def tearDownClass(cls):
            cls.r.clear()

        def setUp(self):
            self.r.clear()

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

        def _assert_typed_key_round_trip(self, key, value):
            self.r.clear()
            self.r[key] = value
            self.assertIn(key, self.r)
            self.assertEqual(self.r[key], value)
            loaded_keys = list(self.r.keys())
            self.assertEqual(loaded_keys, [key])
            self.assertIs(type(loaded_keys[0]), type(key))
            self.assertEqual(list(self.r.items()), [(key, value)])
            self.assertEqual(self.r.pop(key), value)
            self.assertNotIn(key, self.r)

        @settings(deadline=None)
        @given(key=st.integers(), value=st.text())
        def test_typed_key_integer(self, key, value):
            self._assert_typed_key_round_trip(key, value)

        @settings(deadline=None)
        @given(key=st.floats(allow_nan=False, allow_infinity=False), value=st.integers())
        def test_typed_key_float(self, key, value):
            self._assert_typed_key_round_trip(key, value)

        @settings(deadline=None)
        @given(key=st.one_of(st.booleans(), st.none()), value=st.text())
        def test_typed_key_boolean_and_none(self, key, value):
            self._assert_typed_key_round_trip(key, value)

        @settings(deadline=None)
        @given(key=st.one_of(st.binary(), st.uuids()), value=st.text())
        def test_typed_key_bytes_and_uuid(self, key, value):
            self._assert_typed_key_round_trip(key, value)

        @settings(deadline=None)
        @given(
            key=st.one_of(
                st.datetimes(),
                st.dates(),
                st.times(),
                st.timedeltas(
                    min_value=timedelta(days=-36500),
                    max_value=timedelta(days=36500),
                ),
                st.decimals(allow_nan=False, allow_infinity=False),
            ),
            value=st.integers(),
        )
        def test_typed_key_temporal_and_decimal(self, key, value):
            self._assert_typed_key_round_trip(key, value)

        @settings(deadline=None)
        @given(
            key=st.one_of(
                st.tuples(st.integers(), st.text()),
                st.frozensets(st.integers(), max_size=5),
            ),
            value=st.text(),
        )
        def test_typed_key_tuples_and_frozensets(self, key, value):
            self._assert_typed_key_round_trip(key, value)

        @settings(deadline=None)
        @given(
            key=st.one_of(
                st.lists(st.integers(), max_size=5),
                st.dictionaries(st.text(min_size=1, max_size=8), st.integers(), max_size=4),
            ),
            value=st.text(),
        )
        def test_typed_key_lists_and_dicts(self, key, value):
            self._assert_typed_key_round_trip(key, value)

        @settings(deadline=None)
        @given(n=st.integers(min_value=-10000, max_value=10000))
        def test_typed_key_distinct_types_never_collide(self, n):
            self.r.clear()
            self.r[n] = "int"
            self.r[str(n)] = "str"
            self.r[(n,)] = "tuple"
            self.assertEqual(len(self.r), 3)
            self.assertEqual(self.r.to_dict(), {n: "int", str(n): "str", (n,): "tuple"})

        @settings(deadline=None)
        @given(
            nums=st.lists(st.integers(), min_size=1, max_size=8, unique=True),
            pairs=st.lists(
                st.tuples(st.text(min_size=1, max_size=6), st.integers()),
                min_size=1,
                max_size=6,
                unique_by=lambda p: p[0],
            ),
        )
        def test_typed_key_order_independent_containers(self, nums, pairs):
            self.r.clear()
            fs_fwd, fs_rev = frozenset(nums), frozenset(reversed(nums))
            set_fwd, set_rev = set(nums), set(reversed(nums))
            dict_fwd, dict_rev = dict(pairs), dict(reversed(pairs))

            self.r[fs_fwd] = "fs"
            self.assertEqual(self.r[fs_rev], "fs")
            self.assertEqual(list(self.r.items()), [(fs_fwd, "fs")])
            self.assertEqual(self.r.pop(fs_rev), "fs")

            self.r[set_fwd] = "set"
            self.assertEqual(self.r[set_rev], "set")
            self.assertEqual(self.r.pop(set_rev), "set")

            self.r[dict_fwd] = "dict"
            self.assertEqual(self.r[dict_rev], "dict")
            self.assertEqual(self.r.pop(dict_rev), "dict")

    return _HypothesisSuite


class TestRedisDictWithHypothesis(_create_hypothesis_suite(RedisDict, "test_with_fuzzing")):
    """
    A test suite employing Hypothesis for property-based testing of RedisDict.

    This class uses the Hypothesis library to perform fuzz testing on
    RedisDict instances. Through the generation of diverse inputs, edge cases, and randomized
    scenarios, this test suite aims to evaluate the correctness and resilience of the RedisDict
    implementation under various conditions. The goal is to cover a broad spectrum of potential
    interactions and behaviors, ensuring the implementation can handle complex and unforeseen
    situations.
    """


class TestPythonRedisDictWithHypothesis(_create_hypothesis_suite(PythonRedisDict, "test_with_fuzzing_python")):
    """
    A test suite employing Hypothesis for property-based testing of PythonRedisDict.
    """


if __name__ == '__main__':
    unittest.main()
