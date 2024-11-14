import sys
import json
import unittest

from typing import Any

from collections import Counter, ChainMap
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address
from pathlib import Path
from queue import Queue, PriorityQueue
from typing import NamedTuple
from enum import Enum

from datetime import datetime, date, time, timedelta
from decimal import Decimal
from collections import OrderedDict, defaultdict
from uuid import UUID

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))
from redis_dict.type_management import  encode_json, decode_json, RedisDictJSONEncoder, RedisDictJSONDecoder


class TestJsonEncoding(unittest.TestCase):
    def setUp(self):

        # Below are tests that contain types that handled by default json encoding/decoding
        self.skip_assert_raise_type_error_test = {
            "str", "int", "float", "dict", "list",
            "NoneType", "defaultdict", "OrderedDict",
            "bool", "str,int,bool in list", "None,float,list in list",
            "str,dict,set in list",
        }

    def _assert_value_encodes_decodes(self, value: Any) -> None:
        """Helper method to assert a value can be encoded and decoded correctly"""
        encoded = json.dumps(value, cls=RedisDictJSONEncoder)
        result = json.loads(encoded, cls=RedisDictJSONDecoder)
        self.assertEqual(value, result)

    def test_happy_path(self):
        test_cases = [
            ("Hello World", "str"),
            (42, "int"),
            (3.14, "float"),
            (True, "bool"),
            (None, "NoneType"),

            ([1, 2, 3], "list"),
            ({"a": 1, "b": 2}, "dict"),
            #((1, 2, 3), "tuple"),
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

        for test_case_input, test_case_title in test_cases:
            with self.subTest(f"Testing happy mixed list path: {test_case_title}"):
                self._assert_value_encodes_decodes(test_case_input)

                if test_case_title not in self.skip_assert_raise_type_error_test:
                    with self.assertRaises(TypeError):
                        json.loads(json.dumps(test_case_input))

    def test_empty_path(self):
        test_cases = [
            ("", "str"),
            (0, "int"),
            (0.0, "float"),
            (False, "bool"),
            (None, "NoneType"),

            ([], "list"),
            ({}, "dict"),
            # ((), "tuple"), TODO Handle tuple
            (set(), "set"),

            (datetime.min, "datetime"),
            (date.min, "date"),
            (time.min, "time"),
            (timedelta(), "timedelta"),

            (Decimal("0"), "Decimal"),
            (complex(0, 0), "complex"),
            (bytes(), "bytes"),
            (UUID('00000000-0000-0000-0000-000000000000'), "UUID"),

            (OrderedDict(), "OrderedDict"),
            (defaultdict(type(None)), "defaultdict"),
            (frozenset(), "frozenset"),
        ]

        for test_case_input, test_case_title in test_cases:
            with self.subTest(f"Testing happy mixed list path: {test_case_title}"):
                self._assert_value_encodes_decodes(test_case_input)

                if test_case_title not in self.skip_assert_raise_type_error_test:
                    with self.assertRaises(TypeError):
                        json.loads(json.dumps(test_case_input))

    def test_happy_nested_dict(self):
        test_cases = [
            ({"value": "Hello World"}, "str"),
            ({"value": 42}, "int"),
            ({"value": 3.14}, "float"),
            ({"value": True}, "bool"),
            ({"value": None}, "NoneType"),

            ({"value": [1, 2, 3]}, "list"),
            ({"value": {"a": 1, "b": 2}}, "dict"),
            # ({"value": (1, 2, 3)}, "tuple"),  TODO Handle tuple
            ({"value": {1, 2, 3}}, "set"),

            ({"value": datetime(2024, 1, 1, 12, 30, 45)}, "datetime"),
            ({"value": date(2024, 1, 1)}, "date"),
            ({"value": time(12, 30, 45)}, "time"),
            ({"value": timedelta(days=1, hours=2)}, "timedelta"),

            ({"value": Decimal("3.14159")}, "Decimal"),
            ({"value": complex(1, 2)}, "complex"),
            ({"value": bytes([72, 101, 108, 108, 111])}, "bytes"),
            ({"value": UUID('12345678-1234-5678-1234-567812345678')}, "UUID"),

            ({"value": OrderedDict([('a', 1), ('b', 2)])}, "OrderedDict"),
            ({"value": defaultdict(type(None), {'a': 1, 'b': 2})}, "defaultdict"),
            ({"value": frozenset([1, 2, 3])}, "frozenset"),
        ]

        for test_case_input, test_case_title in test_cases:
            with self.subTest(f"Testing happy mixed list path: {test_case_title}"):
                self._assert_value_encodes_decodes(test_case_input)

                if test_case_title not in self.skip_assert_raise_type_error_test:
                    with self.assertRaises(TypeError):
                        json.loads(json.dumps(test_case_input))

    def test_happy_nested_dict_two_levels(self):
        test_cases = [
            ({"level1": {"value": "Hello World"}}, "str"),
            ({"level1": {"value": 42}}, "int"),
            ({"level1": {"value": 3.14}}, "float"),
            ({"level1": {"value": True}}, "bool"),
            ({"level1": {"value": None}}, "NoneType"),

            ({"level1": {"value": [1, 2, 3]}}, "list"),
            ({"level1": {"value": {"a": 1, "b": 2}}}, "dict"),
            # ({"level1": {"value": (1, 2, 3)}}, "tuple"),  TODO Handle tuple
            ({"level1": {"value": {1, 2, 3}}}, "set"),

            ({"level1": {"value": datetime(2024, 1, 1, 12, 30, 45)}}, "datetime"),
            ({"level1": {"value": date(2024, 1, 1)}}, "date"),
            ({"level1": {"value": time(12, 30, 45)}}, "time"),
            ({"level1": {"value": timedelta(days=1, hours=2)}}, "timedelta"),

            ({"level1": {"value": Decimal("3.14159")}}, "Decimal"),
            ({"level1": {"value": complex(1, 2)}}, "complex"),
            ({"level1": {"value": bytes([72, 101, 108, 108, 111])}}, "bytes"),
            ({"level1": {"value": UUID('12345678-1234-5678-1234-567812345678')}}, "UUID"),

            ({"level1": {"value": OrderedDict([('a', 1), ('b', 2)])}}, "OrderedDict"),
            ({"level1": {"value": defaultdict(type(None), {'a': 1, 'b': 2})}}, "defaultdict"),
            ({"level1": {"value": frozenset([1, 2, 3])}}, "frozenset"),
        ]

        for test_case_input, test_case_title in test_cases:
            with self.subTest(f"Testing happy mixed list path: {test_case_title}"):
                self._assert_value_encodes_decodes(test_case_input)

                if test_case_title not in self.skip_assert_raise_type_error_test:
                    with self.assertRaises(TypeError):
                        json.loads(json.dumps(test_case_input))

    def test_happy_list(self):
        test_cases = [
            (["Hello World"], "str"),
            ([42], "int"),
            ([3.14], "float"),
            ([True], "bool"),
            ([None], "NoneType"),

            ([[1, 2, 3]], "list"),
            ([{"a": 1, "b": 2}], "dict"),
            # ([(1, 2, 3)], "tuple"),  TODO Handle tuple
            ([{1, 2, 3}], "set"),

            ([datetime(2024, 1, 1, 12, 30, 45)], "datetime"),
            ([date(2024, 1, 1)], "date"),
            ([time(12, 30, 45)], "time"),
            ([timedelta(days=1, hours=2)], "timedelta"),

            ([Decimal("3.14159")], "Decimal"),
            ([complex(1, 2)], "complex"),
            ([bytes([72, 101, 108, 108, 111])], "bytes"),
            ([UUID('12345678-1234-5678-1234-567812345678')], "UUID"),

            ([OrderedDict([('a', 1), ('b', 2)])], "OrderedDict"),
            ([defaultdict(type(None), {'a': 1, 'b': 2})], "defaultdict"),
            ([frozenset([1, 2, 3])], "frozenset"),
        ]

        for test_case_input, test_case_title in test_cases:
            with self.subTest(f"Testing happy mixed list path: {test_case_title}"):
                self._assert_value_encodes_decodes(test_case_input)

                if test_case_title not in self.skip_assert_raise_type_error_test:
                    with self.assertRaises(TypeError):
                        json.loads(json.dumps(test_case_input))

    def test_happy_mixed_list(self):
        test_cases = [
            (["Hello World", 42, True], "str,int,bool in list"),
            ([None, 3.14, [1, 2, 3]], "None,float,list in list"),
            (["test", {"a": 1}, {1, 2, 3}], "str,dict,set in list"),

            ([datetime(2024, 1, 1), date(2024, 1, 1), time(12, 30, 45)], "datetime,date,time in list"),
            ([timedelta(days=1), Decimal("3.14159"), complex(1, 2)], "timedelta,Decimal,complex in list"),
            ([bytes([72, 101]), UUID('12345678-1234-5678-1234-567812345678'), "test"], "bytes,UUID,str in list"),

            ([OrderedDict([('a', 1)]), defaultdict(type(None), {'b': 2}), frozenset([1, 2])],
             "OrderedDict,defaultdict,frozenset in list"),
            (["a", 1, Decimal("3.14159")], "str,int,Decimal in list"),
            ([True, None, datetime(2024, 1, 1)], "bool,None,datetime in list"),
        ]

        for test_case_input, test_case_title in test_cases:
            with self.subTest(f"Testing happy mixed list path: {test_case_title}"):
                self._assert_value_encodes_decodes(test_case_input)

                if test_case_title not in self.skip_assert_raise_type_error_test:
                    with self.assertRaises(TypeError):
                        json.loads(json.dumps(test_case_input))

    def test_happy_list_dicts_mixed(self):
        test_cases = [
            (
                [
                     {"decimal": Decimal("3.14159"), "bytes": bytes([72, 101, 108, 108, 111])},
                     {"complex": complex(1, 2), "uuid": UUID('12345678-1234-5678-1234-567812345678')},
                     {"date": datetime(2024, 1, 1), "set": {1, 2, 3}}
                ],
                "list of dicts with decimal/bytes, complex/uuid, datetime/set"
            ), (
                [
                     {"ordered": OrderedDict([('a', 1)]), "default": defaultdict(type(None), {'x': 1})},
                     {"frozen": frozenset([1, 2, 3]), "time": time(12, 30, 45)},
                     {"delta": timedelta(days=1), "nested": {"a": 1, "b": 2}}
                ],
                "list of dicts with OrderedDict/defaultdict, frozenset/time, timedelta/dict"
            ), (
                [
                     {"bytes": bytes([65, 66, 67]), "decimal": Decimal("10.5"), "date": date(2024, 1, 1)},
                     {"uuid": UUID('12345678-1234-5678-1234-567812345678'), "complex": complex(3, 4), "set": {4, 5, 6}},
                     {"time": time(1, 2, 3), "delta": timedelta(hours=5), "list": [1, 2, 3]}
                ],
                "list of dicts with three mixed types each"
            ),
        ]

        for test_case_input, test_case_title in test_cases:
            with self.subTest(f"Testing happy list of dicts mixed path: {test_case_title}"):
                self._assert_value_encodes_decodes(test_case_input)

                encoded = encode_json(test_case_input)
                result = decode_json(encoded)

                for test_index, expected_test in enumerate(test_case_input):
                    for index, key in enumerate(expected_test):
                        expected_value = test_case_input[test_index][key]
                        result_value = result[test_index][key]
                        self.assertEqual(expected_value, result_value)

                        # Ordered dict, becomes regular dictionary. Since the idea is to extend json types fixing this
                        # issue is not within the scope of this feature
                        if test_case_title == "list of dicts with OrderedDict/defaultdict, frozenset/time, timedelta/dict":
                            continue
                        self.assertEqual(type(expected_value), type(result_value))

    def test_potential_candidates(self):
        """Test cases for types that could be added encoding/decoding in the future"""

        @dataclass
        class DataClassType:
            name: str
            value: int

        class NamedTupleType(NamedTuple):
            name: str
            value: int

        class EnumType_(Enum):
            ONE = 1
            TWO = 2

        potential_candidates = [
        #    (Counter(['a', 'b', 'a']), "Counter"), Encodes into other type
            (ChainMap({'a': 1}, {'b': 2}), "ChainMap"),
            (Queue(), "Queue"),
            (PriorityQueue(), "PriorityQueue"),

            (IPv4Address('192.168.1.1'), "IPv4Address"),
            (IPv6Address('2001:db8::1'), "IPv6Address"),

            (Path('/foo/bar.txt'), "Path"),

            (DataClassType("test", 42), "DataClass"),
            #(NamedTupleType("test", 42), "NamedTuple"),  Encodes into other type
            (EnumType_.ONE, "Enum"),

            #(re_compile(r'\d+'), "Pattern"),
            #(memoryview(b'Hello'), "memoryview"),
        ]

        for test_case_input, test_case_title in potential_candidates:
            with self.subTest(f"Testing potential candidate: {test_case_title}"):

                # fails with json out of the box
                with self.assertRaises(TypeError, msg=test_case_title):
                    result = json.dumps(test_case_input)
                    print(result)

                # Since these types are not yet added
                with self.assertRaises(TypeError,  msg=test_case_title):
                    result = json.dumps(test_case_input, cls=RedisDictJSONEncoder)
                    print(result)

if __name__ == '__main__':
    unittest.main()