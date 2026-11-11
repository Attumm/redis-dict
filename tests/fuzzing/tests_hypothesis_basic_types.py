import unittest

from hypothesis import given, strategies as st

from redis_dict import RedisDict, PythonRedisDict, EncryptedRedisDict, RedisDictDecryptionError

FUZZ_AES_KEY = b"0123456789abcdef0123456789abcdef"


def _create_hypothesis_suite(dict_cls, namespace, **init_kwargs):
    class _HypothesisSuite(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.r = dict_cls(namespace=namespace, **init_kwargs)

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


class TestEncryptedRedisDictWithHypothesis(
    _create_hypothesis_suite(EncryptedRedisDict, "test_with_fuzzing_encrypted", key=FUZZ_AES_KEY)
):
    """
    A test suite employing Hypothesis for property-based testing of EncryptedRedisDict.
    """

    @given(
        key=st.text(min_size=1),
        value=st.text(),
        flip_offset=st.integers(min_value=0, max_value=1024),
        flip_mask=st.integers(min_value=1, max_value=255),
    )
    def test_tampered_ciphertext_never_decrypts(
        self, key: str, value: str, flip_offset: int, flip_mask: int
    ) -> None:
        """Any single-byte mutation of the stored encrypted payload must raise RedisDictDecryptionError."""
        import base64

        self.r[key] = value
        formatted_key = self.r._format_key(key)
        raw = self.r.get_redis.get(formatted_key)
        self.assertIsNotNone(raw)
        assert raw is not None

        prefix, b64_blob = raw.rsplit("$", 1)
        padded = b64_blob + "=" * (-len(b64_blob) % 4)
        payload = bytearray(base64.urlsafe_b64decode(padded.encode("ascii")))
        payload[flip_offset % len(payload)] ^= flip_mask
        tampered_b64 = base64.urlsafe_b64encode(bytes(payload)).decode("ascii").rstrip("=")

        self.r.get_redis.set(formatted_key, f"{prefix}${tampered_b64}")
        with self.assertRaises(RedisDictDecryptionError):
            _ = self.r[key]


if __name__ == '__main__':
    unittest.main()
