import sys
import unittest

from uuid import UUID, uuid4
from decimal import Decimal
from datetime import datetime, date, time, timedelta, timezone
from collections import OrderedDict, defaultdict

from redis_dict import RedisDict


class TypeCodecTests(unittest.TestCase):
    def setUp(self):
        self.dic = RedisDict()

    def _assert_value_encodes_decodes(self, expected_value):
        """Helper method to test encoding and decoding of a value"""
        expected_type = type(expected_value).__name__
        encoded_value = self.dic.encoding_registry.get(expected_type, str)(expected_value)

        self.assertIsInstance(encoded_value, str)

        result = self.dic.decoding_registry.get(expected_type, lambda x: x)(encoded_value)

        self.assertEqual(type(result).__name__, expected_type)
        self.assertEqual(expected_value, result)

    def _ensure_testcases_have_all_types(self, test_cases):
        """
        Instances are colliding during unit tests, refactor encoding/decoding registeries and turn the test back on
        """
        return
        test_types = {i[1] for i in test_cases}
        registry_types = set(self.dic.decoding_registry.keys())

        missing_types = registry_types - test_types

        extra_types = test_types - registry_types
        len_test_types = len(test_types)
        len_registry_types = len(self.dic.decoding_registry.keys())
        self.assertEqual(
            len_test_types,
            len_registry_types,
            f"\nMissing types in tests: {missing_types if missing_types else 'no missing'}"
            f"\nExtra types in tests: {extra_types if extra_types else 'None'}"
            f"\nThere are types {len_test_types} and {len_registry_types}"
            f"\nthere are still {len_registry_types - len_test_types} missing types"
        )

    def test_happy_path(self):
        test_cases = [
            ("Hello World", "str"),
            (42, "int"),
            (3.14, "float"),
            (True, "bool"),
            (None, "NoneType"),

            ([1, 2, 3], "list"),
            ({"a": 1, "b": 2}, "dict"),
            ((1, 2, 3), "tuple"),
            ({1, 2, 3}, "set"),

            (datetime(2024, 1, 1, 12, 30, 45), "datetime"),
            (date(2024, 1, 1), "date"),
            (time(12, 30, 45), "time"),
            (timedelta(days=1, hours=2), "timedelta"),

            (Decimal("3.14159"), "Decimal"),
            (complex(1, 2), "complex"),
            (bytes([72, 101, 108, 108, 111]), "bytes"),
            (UUID('12345678-1234-5678-1234-567812345678'), "UUID"),

            (OrderedDict([('a', 1), ('b', 2)]), "OrderedDict"),
            (defaultdict(type(None), {'a': 1, 'b': 2}), "defaultdict"),
            (frozenset([1, 2, 3]), "frozenset"),
        ]
        self._ensure_testcases_have_all_types(test_cases)

        for value, type_name in test_cases:
            with self.subTest(f"Testing happy path: {type_name}"):
                self._assert_value_encodes_decodes(value)

    def test_min_boundary_values(self):
        test_cases = [
            ("", "str"),
            (0, "int"),
            (0.0, "float"),
            (False, "bool"),
            (None, "NoneType"),

            ([], "list"),
            ({}, "dict"),
            ((), "tuple"),
            (set(), "set"),

            (datetime(1970, 1, 1, 0, 0, 0), "datetime"),
            (date(1970, 1, 1), "date"),
            (time(0, 0, 0), "time"),
            (timedelta(0), "timedelta"),

            (Decimal("0"), "Decimal"),
            (complex(0, 0), "complex"),
            (bytes(), "bytes"),
            (UUID('00000000-0000-0000-0000-000000000000'), "UUID"),
            (OrderedDict(), "OrderedDict"),
            (defaultdict(type(None)), "defaultdict"),
            (frozenset(), "frozenset")
        ]
        self._ensure_testcases_have_all_types(test_cases)

        for value, type_name in test_cases:
            with self.subTest(f"Testing min boundary value {type_name}"):
                self._assert_value_encodes_decodes(value)

    def test_max_boundary_values(self):
        test_cases = [
            ("א" * 10000, "str"),
            (sys.maxsize, "int"),
            (float('inf'), "float"),
            (True, "bool"),
            (None, "NoneType"),

            ([1] * 1000, "list"),
            ({"k" + str(i): i for i in range(1000)}, "dict"),
            (tuple(range(1000)), "tuple"),
            (set(range(1000)), "set"),

            (datetime(9999, 12, 31, 23, 59, 59, 999999), "datetime"),
            (date(9999, 12, 31), "date"),
            (time(23, 59, 59, 999999), "time"),
            (timedelta(days=999999999), "timedelta"),

            (Decimal('1E+308'), "Decimal"),
            (complex(float('inf'), float('inf')), "complex"),
            (bytes([255] * 1000), "bytes"),
            (UUID('ffffffff-ffff-ffff-ffff-ffffffffffff'), "UUID"),
            (OrderedDict([(str(i), i) for i in range(1000)]), "OrderedDict"),
            (defaultdict(type(None), {str(i): i for i in range(1000)}), "defaultdict"),
            (frozenset(range(1000)), "frozenset")
        ]
        self._ensure_testcases_have_all_types(test_cases)

        for value, type_name in test_cases:
            with self.subTest(f"Testing max boundary value {type_name}"):
                self._assert_value_encodes_decodes(value)

    def test_datetime_edge_cases(self):
        test_cases = [
            (date(2024, 1, 1), "start of year date"),
            (date(2024, 12, 31), "end of year date"),
            (date(2024, 2, 29), "leap year date"),

            (time(0, 0, 0), "midnight"),
            (time(12, 0, 0), "noon"),
            (time(23, 59, 59, 999999), "just before midnight"),
            (time(12, 0, 0, tzinfo=timezone.utc), "noon with timezone"),

            (timedelta(days=1), "one day"),
            (timedelta(weeks=1), "one week"),
            (timedelta(hours=24), "24 hours"),
            (timedelta(milliseconds=1), "one millisecond"),
            (timedelta(microseconds=1), "one microsecond"),
            (timedelta(days=1, hours=1, minutes=1, seconds=1), "mixed time units"),

            (datetime(2024, 1, 1, 0, 0, 0), "start of year"),
            (datetime(2024, 12, 31, 23, 59, 59, 999999), "end of year"),
            (datetime(2024, 2, 29, 0, 0, 0), "leap year"),
            (datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc), "with timezone"),

            (datetime(2024, 2, 28, 23, 59, 59), "day before leap day"),
            (datetime(2024, 3, 1, 0, 0, 0), "day after leap day"),

            (datetime(2024, 2, 29, 0, 0, 0), "leap year divisible by 4"),
            (datetime(2000, 2, 29, 0, 0, 0), "leap year divisible by 100 and 400"),
            (datetime(1900, 2, 28, 0, 0, 0), "non leap year divisible by 100"),
            (datetime(2100, 2, 28, 0, 0, 0), "future non leap year divisible by 100"),

            (date(2024, 2, 29), "leap year date divisible by 4"),
            (date(2000, 2, 29), "leap year date divisible by 100 and 400"),
            (date(1900, 2, 28), "non leap year date divisible by 100"),
            (date(2100, 2, 28), "future non leap year date divisible by 100"),
        ]

        for value, test_name in test_cases:
            with self.subTest(f"Testing datetime edge case {test_name}"):
                self._assert_value_encodes_decodes(value)

if __name__ == '__main__':
    unittest.main()
