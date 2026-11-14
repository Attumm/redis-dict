import asyncio
from collections import OrderedDict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
import unittest
from uuid import UUID
import warnings

import redis as sync_redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import ResponseError

import redis_dict
from redis_dict import RedisDict

AsyncRedisDict = getattr(redis_dict, "AsyncRedisDict", None)

TEST_NAMESPACE_PREFIX = "__test_async_prefix_key_meta_8128__"

REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 11,
}

EDGE_STRING_CASES = {
    "empty": "",
    "space": " ",
    "whitespace": "\t\n\r",
    "punctuation": "Hello, World! !@#$%^&*()_+-=[]{}|;:,.<>?",
    "colons": "type:val:extra:colons",
    "unicode": "äöüßÄÖÜ 中文字符测试 こんにちは 한글 테스트",
    "emoji": "😀🙈🚀🔐",
    "null_byte": "prefix\x00suffix",
    "quotes_slashes": "\"quoted\" 'single' C:\\Program Files\\ /usr/local/bin/",
    "long_string": "Lorem ipsum dolor sit amet. " * 100,
}


class CustomPerson:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    def encode(self) -> str:
        return json.dumps({"name": self.name, "age": self.age})

    @classmethod
    def decode(cls, encoded: str) -> "CustomPerson":
        data = json.loads(encoded)
        return cls(data["name"], data["age"])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CustomPerson):
            return NotImplemented
        return self.name == other.name and self.age == other.age


class DuckMapping:
    def __init__(self, data: dict) -> None:
        self._data = data

    def keys(self):
        return self._data.keys()

    def __getitem__(self, key: str):
        return self._data[key]


class TestSyncRedisDictBaselineGuard(unittest.TestCase):
    """Guard tests ensuring standard synchronous RedisDict remains unaffected."""

    def setUp(self) -> None:
        self.sync_client = sync_redis.StrictRedis(decode_responses=True, **REDIS_CONFIG)
        self._cleanup_prefix()

    def tearDown(self) -> None:
        self._cleanup_prefix()
        self.sync_client.close()

    def _cleanup_prefix(self) -> None:
        keys = list(self.sync_client.scan_iter(f"{TEST_NAMESPACE_PREFIX}*"))
        if keys:
            self.sync_client.delete(*keys)

    def test_sync_redis_dict_crud_guard(self) -> None:
        dic = RedisDict(namespace=f"{TEST_NAMESPACE_PREFIX}_sync_guard", **REDIS_CONFIG)
        dic["alpha"] = 42
        dic["beta"] = {"nested": [1, 2, 3]}
        self.assertEqual(dic["alpha"], 42)
        self.assertEqual(dic["beta"], {"nested": [1, 2, 3]})
        self.assertIn("alpha", dic)
        self.assertEqual(len(dic), 2)
        self.assertEqual(dic.to_dict(), {"alpha": 42, "beta": {"nested": [1, 2, 3]}})


class TestAsyncRedisDict(unittest.IsolatedAsyncioTestCase):
    """Comprehensive live-Redis TDD suite for AsyncRedisDict."""

    async def asyncSetUp(self) -> None:
        if AsyncRedisDict is None:
            self.fail("AsyncRedisDict is not exported from redis_dict")
        self.raw_redis = AsyncRedis(decode_responses=True, **REDIS_CONFIG)
        await self._cleanup_prefix()
        self.ns = f"{TEST_NAMESPACE_PREFIX}_main"
        self.tested_dic = AsyncRedisDict(namespace=self.ns, **REDIS_CONFIG)
        self.expected_dic: dict = {}

    async def asyncTearDown(self) -> None:
        if hasattr(self, "tested_dic") and self.tested_dic is not None:
            await self.tested_dic.close()
        if hasattr(self, "raw_redis") and self.raw_redis is not None:
            await self._cleanup_prefix()
            await self.raw_redis.aclose()

    async def _cleanup_prefix(self) -> None:
        keys = [k async for k in self.raw_redis.scan_iter(f"{TEST_NAMESPACE_PREFIX}*")]
        if keys:
            await self.raw_redis.delete(*keys)

    def create_async_dict(self, suffix: str = "extra", **kwargs):
        config = REDIS_CONFIG.copy()
        config.update(kwargs)
        return AsyncRedisDict(namespace=f"{TEST_NAMESPACE_PREFIX}_{suffix}", **config)

    # ------------------------------------------------------------------
    # 1. Export, Inheritance, Constructor & Lifecycle
    # ------------------------------------------------------------------

    async def test_export_inheritance_and_type_subscript(self) -> None:
        self.assertIn("AsyncRedisDict", redis_dict.__all__)
        self.assertTrue(issubclass(AsyncRedisDict, RedisDict))
        self.assertIsInstance(self.tested_dic, RedisDict)
        self.assertIs(AsyncRedisDict[str, int], AsyncRedisDict)

    async def test_invalid_namespace_raises_value_error(self) -> None:
        for bad_ns in ("bad:ns", "bad*ns", "bad?ns", "bad[ns]", "bad]ns", "bad\\ns"):
            with self.subTest(bad_ns=bad_ns):
                with self.assertRaises(ValueError):
                    AsyncRedisDict(namespace=bad_ns, **REDIS_CONFIG)

    async def test_injected_async_redis_client_and_context_manager(self) -> None:
        injected = AsyncRedis(decode_responses=False, **REDIS_CONFIG)
        async with AsyncRedisDict(
            namespace=f"{TEST_NAMESPACE_PREFIX}_ctx",
            redis=injected,
        ) as ctx_dic:
            self.assertTrue(injected.connection_pool.connection_kwargs["decode_responses"])
            await ctx_dic.set_item("hello", "world")
            self.assertEqual(await ctx_dic.get_item("hello"), "world")

        with self.assertRaises(RuntimeError):
            async with self.create_async_dict("ctx_err") as err_dic:
                await err_dic.set_item("before_err", 123)
                raise RuntimeError("boom")

        verify_dic = self.create_async_dict("ctx_err")
        try:
            self.assertEqual(await verify_dic.get_item("before_err"), 123)
        finally:
            await verify_dic.close()

    async def test_repr_and_str_are_non_blocking_without_warnings(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            rep = repr(self.tested_dic)
            as_str = str(self.tested_dic)
        self.assertEqual(caught, [])
        self.assertIn("AsyncRedisDict", rep)
        self.assertIn(self.ns, rep)
        self.assertEqual(rep, as_str)

    # ------------------------------------------------------------------
    # 2. Core CRUD, Falsy Values, Size Validation & Edge Strings
    # ------------------------------------------------------------------

    async def test_crud_and_delete_modes(self) -> None:
        self.assertEqual(await self.tested_dic.len(), 0)
        self.assertFalse(await self.tested_dic.contains("missing"))
        self.assertIsNone(await self.tested_dic.get("missing"))
        self.assertEqual(await self.tested_dic.get("missing", "fallback"), "fallback")

        with self.assertRaises(KeyError) as ctx:
            await self.tested_dic.get_item("missing")
        self.assertEqual(ctx.exception.args[0], "missing")

        await self.tested_dic.set_item("alpha", 10)
        self.assertTrue(await self.tested_dic.contains("alpha"))
        self.assertEqual(await self.tested_dic.len(), 1)
        self.assertEqual(await self.tested_dic.get_item("alpha"), 10)
        self.assertEqual(await self.tested_dic.get("alpha", "fallback"), 10)

        # Idempotent delete by default (distributed-safe)
        await self.tested_dic.del_item("alpha")
        await self.tested_dic.del_item("alpha")
        self.assertFalse(await self.tested_dic.contains("alpha"))
        self.assertEqual(await self.tested_dic.len(), 0)

        # Strict delete when raise_key_error_delete=True
        strict_dic = self.create_async_dict("strict_del", raise_key_error_delete=True)
        try:
            with self.assertRaises(KeyError) as strict_ctx:
                await strict_dic.del_item("ghost")
            self.assertEqual(strict_ctx.exception.args[0], "ghost")
        finally:
            await strict_dic.close()

    async def test_falsy_values_preserved_across_all_reads(self) -> None:
        falsy = {
            "none": None,
            "false": False,
            "zero": 0,
            "zero_float": 0.0,
            "empty_str": "",
            "empty_list": [],
            "empty_dict": {},
            "empty_tuple": (),
            "empty_set": set(),
        }
        for key, val in falsy.items():
            await self.tested_dic.set_item(key, val)

        self.assertEqual(await self.tested_dic.len(), len(falsy))
        for key, expected in falsy.items():
            self.assertTrue(await self.tested_dic.contains(key))
            self.assertEqual(await self.tested_dic.get_item(key), expected)
            self.assertEqual(await self.tested_dic.get(key, "SENTINEL_DEFAULT"), expected)

        self.assertEqual(await self.tested_dic.to_dict(), falsy)

    async def test_edge_string_keys_and_values(self) -> None:
        for label, edge_str in EDGE_STRING_CASES.items():
            await self.tested_dic.set_item(edge_str, edge_str)
            self.expected_dic[edge_str] = edge_str
            await self.tested_dic.set_item(f"label:{label}", edge_str)
            self.expected_dic[f"label:{label}"] = edge_str

        self.assertEqual(await self.tested_dic.len(), len(self.expected_dic))
        self.assertEqual(await self.tested_dic.to_dict(), self.expected_dic)

    async def test_max_string_size_validation(self) -> None:
        self.tested_dic._max_string_size = 16
        with self.assertRaises(ValueError):
            await self.tested_dic.set_item("ok", "x" * 16)
        with self.assertRaises(ValueError):
            await self.tested_dic.set_item("x" * 16, "ok")
        with self.assertRaises(ValueError):
            await self.tested_dic.setdefault("ok", "x" * 16)
        with self.assertRaises(ValueError):
            await self.tested_dic.setdefault("x" * 16, "ok")

    # ------------------------------------------------------------------
    # 3. Full Type Round-Trips, Custom Types & Sync Interoperability
    # ------------------------------------------------------------------

    async def test_all_supported_types_and_sync_redis_dict_interop(self) -> None:
        payloads = {
            "str": "hello:world",
            "int": -42,
            "float": 3.14159,
            "bool_t": True,
            "bool_f": False,
            "none": None,
            "list": [1, "two", None, [True, False]],
            "dict": {"nested": {"a": 1, "b": [2, 3]}, "__type__": "not_a_tag"},
            "tuple": (1, "two", 3),
            "set": {1, 2, 3},
            "frozenset": frozenset({"x", "y"}),
            "datetime": datetime(2026, 11, 14, 13, 45, 12),
            "date": date(2026, 11, 14),
            "time": time(13, 45, 12),
            "timedelta": timedelta(days=2, seconds=35),
            "decimal": Decimal("12345.6789"),
            "complex": complex(2.5, -3.5),
            "bytes": b"\x00\x01binary\xff",
            "uuid": UUID("12345678-1234-5678-1234-567812345678"),
            "ordered_dict": OrderedDict([("first", 1), ("second", 2)]),
        }
        await self.tested_dic.update(payloads)

        # Read everything written by AsyncRedisDict via synchronous RedisDict
        sync_dic = RedisDict(namespace=self.ns, **REDIS_CONFIG)
        try:
            for key, expected in payloads.items():
                sync_val = sync_dic[key]
                async_val = await self.tested_dic.get_item(key)
                self.assertEqual(sync_val, expected)
                self.assertEqual(async_val, expected)
                self.assertIs(type(async_val), type(expected))

            # Write via synchronous RedisDict and read via AsyncRedisDict
            sync_dic["written_by_sync"] = ("sync", 99, True)
            self.assertEqual(await self.tested_dic.get_item("written_by_sync"), ("sync", 99, True))
        finally:
            sync_dic.redis.close()

    async def test_extends_type_and_instance_isolation(self) -> None:
        other_dic = self.create_async_dict("isolated")
        try:
            self.tested_dic.extends_type(CustomPerson)
            alice = CustomPerson("Alice", 30)
            await self.tested_dic.set_item("alice", alice)
            loaded = await self.tested_dic.get_item("alice")
            self.assertEqual(loaded, alice)
            self.assertIsInstance(loaded, CustomPerson)

            # Per-instance registry isolation: other_dic did NOT register CustomPerson
            self.assertNotIn("CustomPerson", other_dic.encoding_registry)
            self.assertNotIn("CustomPerson", other_dic.decoding_registry)

            class Incomplete:
                pass

            with self.assertRaises(NotImplementedError):
                self.tested_dic.extends_type(Incomplete)
        finally:
            await other_dic.close()

    # ------------------------------------------------------------------
    # 4. Async Iterators (__aiter__, __anext__, keys, values, items)
    # ------------------------------------------------------------------

    async def test_empty_iterators_and_anext_stop(self) -> None:
        with self.assertRaises(StopAsyncIteration):
            await self.tested_dic.__anext__()

        self.assertEqual([k async for k in self.tested_dic], [])
        self.assertEqual([k async for k in self.tested_dic.keys()], [])
        self.assertEqual([v async for v in self.tested_dic.values()], [])
        self.assertEqual([item async for item in self.tested_dic.items()], [])

    async def test_aiter_anext_and_concurrent_independent_iterators(self) -> None:
        sample = {f"k{i}": i for i in range(6)}
        await self.tested_dic.update(sample)

        # __aiter__ shares cursor with instance __anext__
        it = self.tested_dic.__aiter__()
        first = await it.__anext__()
        second = await self.tested_dic.__anext__()
        rest = [k async for k in it]
        self.assertEqual(len({first, second, *rest}), 6)
        self.assertEqual({first, second, *rest}, set(sample.keys()))

        with self.assertRaises(StopAsyncIteration):
            await self.tested_dic.__anext__()

        # Two simultaneous iterators do NOT clobber each other's cursor
        it1 = self.tested_dic.__aiter__()
        it2 = self.tested_dic.__aiter__()
        seen1 = [await it1.__anext__()]
        seen2 = [await it2.__anext__(), await it2.__anext__()]
        seen1.extend([k async for k in it1])
        seen2.extend([k async for k in it2])
        self.assertEqual(sorted(seen1), sorted(sample.keys()))
        self.assertEqual(sorted(seen2), sorted(sample.keys()))

    async def test_partial_iteration_exception_and_large_multibatch_scan(self) -> None:
        data = {f"item_{i:04d}": i for i in range(450)}
        await self.tested_dic.update(data)

        taken = 0
        async for _ in self.tested_dic.items():
            taken += 1
            if taken == 5:
                break
        self.assertEqual(taken, 5)

        with self.assertRaises(ValueError):
            async for k, _ in self.tested_dic.items():
                if k.endswith("0010"):
                    raise ValueError("abort mid-scan")

        full = {k: v async for k, v in self.tested_dic.items()}
        self.assertEqual(full, data)
        self.assertEqual(sorted([k async for k in self.tested_dic.keys()]), sorted(data.keys()))
        self.assertEqual(sorted([v async for v in self.tested_dic.values()]), sorted(data.values()))

    async def test_items_skips_wrongtype_and_disappearing_keys_cleanly(self) -> None:
        await self.tested_dic.set_item("valid_1", "one")
        await self.tested_dic.set_item("valid_2", "two")
        # Inject a non-string WRONGTYPE Redis key inside the same namespace
        await self.raw_redis.rpush(self.tested_dic._format_key("foreign_list"), "elem")

        items = {k: v async for k, v in self.tested_dic.items()}
        self.assertEqual(items, {"valid_1": "one", "valid_2": "two"})
        with self.assertRaises(ResponseError):
            await self.tested_dic.get_item("foreign_list")

    # ------------------------------------------------------------------
    # 5. Standard Dict Methods (pop, popitem, setdefault, update, etc.)
    # ------------------------------------------------------------------

    async def test_pop_and_popitem(self) -> None:
        with self.assertRaises(KeyError):
            await self.tested_dic.popitem()

        with self.assertRaises(KeyError) as missing_pop:
            await self.tested_dic.pop("does_not_exist")
        self.assertEqual(missing_pop.exception.args[0], "does_not_exist")

        self.assertIsNone(await self.tested_dic.pop("does_not_exist", None))
        self.assertEqual(await self.tested_dic.pop("does_not_exist", "def"), "def")

        # Populate sibling namespace to ensure key()/popitem() scan isolated namespace
        sibling = self.create_async_dict("sibling")
        try:
            await sibling.update({f"sib_{i}": i for i in range(25)})
            await self.tested_dic.update({"a": 1, "b": None, "c": [1, 2]})

            val_a = await self.tested_dic.pop("a")
            self.assertEqual(val_a, 1)
            self.assertFalse(await self.tested_dic.contains("a"))

            popped = dict([await self.tested_dic.popitem(), await self.tested_dic.popitem()])
            self.assertEqual(popped, {"b": None, "c": [1, 2]})

            with self.assertRaises(KeyError):
                await self.tested_dic.popitem()
            self.assertEqual(await sibling.len(), 25)
        finally:
            await sibling.close()

    async def test_popitem_retries_when_key_disappears_concurrently(self) -> None:
        await self.tested_dic.set_item("survivor", 99)
        calls = 0
        original_key = self.tested_dic.key

        async def flaky_key(search_term: str = ""):
            nonlocal calls
            calls += 1
            if calls == 1:
                return "vanished_between_scan_and_pop"
            return await original_key(search_term)

        self.tested_dic.key = flaky_key  # type: ignore[method-assign]
        try:
            k, v = await self.tested_dic.popitem()
            self.assertEqual((k, v), ("survivor", 99))
            self.assertEqual(calls, 2)
        finally:
            self.tested_dic.key = original_key  # type: ignore[method-assign]

    async def test_setdefault(self) -> None:
        self.assertIsNone(await self.tested_dic.setdefault("null_key"))
        self.assertEqual(await self.tested_dic.setdefault("null_key", "ignored"), None)
        self.assertEqual(await self.tested_dic.setdefault("false_key", False), False)
        self.assertEqual(await self.tested_dic.setdefault("false_key", True), False)
        self.assertEqual(await self.tested_dic.setdefault("count", 10), 10)
        self.assertEqual(await self.tested_dic.setdefault("count", 99), 10)

    async def test_update_fromkeys_copy_and_clear_isolation(self) -> None:
        source_async = self.create_async_dict("source")
        untouched = self.create_async_dict("untouched")
        try:
            await untouched.set_item("keep_me", "safe")
            await source_async.set_item("from_async", 77)

            await self.tested_dic.update({"d": 1}, extra=2)
            await self.tested_dic.update([("pair", 3)])
            await self.tested_dic.update(DuckMapping({"duck": 4}))
            await self.tested_dic.update(source_async)
            # Positional-only `other` allows `other=` and `self=` keyword keys!
            await self.tested_dic.update(other="kw_other", self="kw_self")

            expected = {
                "d": 1,
                "extra": 2,
                "pair": 3,
                "duck": 4,
                "from_async": 77,
                "other": "kw_other",
                "self": "kw_self",
            }
            copied = await self.tested_dic.copy()
            self.assertEqual(copied, expected)
            self.assertIsInstance(copied, dict)

            await self.tested_dic.clear()
            self.assertEqual(await self.tested_dic.len(), 0)
            # Clear on already-empty dict is also a safe no-op
            await self.tested_dic.clear()
            self.assertEqual(await untouched.get_item("keep_me"), "safe")

            returned = await self.tested_dic.fromkeys(["x", "y"], 0)
            self.assertIs(returned, self.tested_dic)
            self.assertEqual(await self.tested_dic.to_dict(), {"x": 0, "y": 0})
        finally:
            await source_async.close()
            await untouched.close()

    # ------------------------------------------------------------------
    # 6. Expiration, Pipelining, Chain/Multi Operations & Concurrency
    # ------------------------------------------------------------------

    async def test_expiration_preserve_ttl_and_expire_at(self) -> None:
        await self.tested_dic.set_item("persistent", "v")
        self.assertIsNone(await self.tested_dic.get_ttl("persistent"))
        self.assertIsNone(await self.tested_dic.get_ttl("missing"))

        async with self.tested_dic.expire_at(timedelta(seconds=20)):
            await self.tested_dic.set_item("temp", "initial")

        self.assertIsNone(self.tested_dic.expire)
        ttl = await self.tested_dic.get_ttl("temp")
        self.assertIsNotNone(ttl)
        assert ttl is not None
        self.assertGreater(ttl, 0)

        # expire_at restores self.expire even when an exception occurs
        with self.assertRaises(RuntimeError):
            async with self.tested_dic.expire_at(5):
                self.assertEqual(self.tested_dic.expire, 5)
                raise RuntimeError("abort")
        self.assertIsNone(self.tested_dic.expire)

        # preserve_expiration keeps TTL on update and sets expire on new keys
        keep_dic = self.create_async_dict("keep_ttl", expire=30, preserve_expiration=True)
        try:
            await keep_dic.set_item("k", "v1")
            await self.raw_redis.expire(keep_dic._format_key("k"), 12)
            await keep_dic.set_item("k", "v2")
            kept_ttl = await keep_dic.get_ttl("k")
            self.assertEqual(await keep_dic.get_item("k"), "v2")
            self.assertIsNotNone(kept_ttl)
            assert kept_ttl is not None
            self.assertLessEqual(kept_ttl, 12)

            await keep_dic.set_item("fresh_key", "val")
            self.assertIsNotNone(await keep_dic.get_ttl("fresh_key"))

            self.assertEqual(await keep_dic.setdefault("k", "ignored"), "v2")
            sd_ttl = await keep_dic.get_ttl("k")
            self.assertIsNotNone(sd_ttl)
            assert sd_ttl is not None
            self.assertLessEqual(sd_ttl, 12)
        finally:
            await keep_dic.close()

        # Short-lived key actually expires
        async with self.tested_dic.expire_at(1):
            await self.tested_dic.set_item("ephemeral", "bye")
        await asyncio.sleep(1.15)
        self.assertFalse(await self.tested_dic.contains("ephemeral"))

    async def test_setdefault_with_timedelta_subsecond_expire(self) -> None:
        sub_dic = self.create_async_dict("subsec", expire=timedelta(milliseconds=500))
        try:
            self.assertEqual(await sub_dic.setdefault("fast", 1), 1)
            self.assertIsNotNone(await sub_dic.get_ttl("fast"))
        finally:
            await sub_dic.close()

    async def test_pipeline_batching_nested_reads_and_error_recovery(self) -> None:
        await self.tested_dic.set_item("preexisting", "ready")

        async with self.tested_dic.pipeline():
            await self.tested_dic.set_item("p1", 1)
            # Reads inside pipeline use self.get_redis so preexisting keys remain readable
            self.assertEqual(await self.tested_dic.get_item("preexisting"), "ready")
            self.assertTrue(await self.tested_dic.contains("preexisting"))
            # p1 is still queued in the pipeline, not yet executed
            self.assertFalse(await self.tested_dic.contains("p1"))
            async with self.tested_dic.pipeline():
                await self.tested_dic.set_item("p2", 2)
                self.assertFalse(await self.tested_dic.contains("p2"))

        self.assertEqual(await self.tested_dic.get_item("p1"), 1)
        self.assertEqual(await self.tested_dic.get_item("p2"), 2)

        # Verify self.redis is restored even when an error happens inside pipeline()
        with self.assertRaises(ValueError):
            async with self.tested_dic.pipeline():
                await self.tested_dic.set_item("p3", 3)
                raise ValueError("boom inside pipeline")

        self.assertIsNone(self.tested_dic._temp_redis)
        await self.tested_dic.set_item("after_err", 4)
        self.assertEqual(await self.tested_dic.get_item("after_err"), 4)

    async def test_chain_and_multi_operations_and_redis_info(self) -> None:
        deep = ["users", "u1", "role"]
        await self.tested_dic.chain_set(deep, "admin")
        self.assertEqual(await self.tested_dic.chain_get(deep), "admin")
        await self.tested_dic.chain_del(deep)
        with self.assertRaises(KeyError):
            await self.tested_dic.chain_get(deep)

        self.assertEqual(await self.tested_dic.multi_get("group"), [])
        self.assertEqual(await self.tested_dic.multi_dict("group"), {})
        self.assertEqual(await self.tested_dic.multi_del("group"), 0)

        items = {"K1": "V1", "KK22": "VV22", "KKK333": "VVV333"}
        for k, v in items.items():
            await self.tested_dic.chain_set(["group", "sub", k], v)

        self.assertEqual(await self.tested_dic.key("group:sub:KK2"), "group:sub:KK22")
        self.assertIsNone(await self.tested_dic.key("no_such_prefix"))
        self.assertEqual(sorted(await self.tested_dic.multi_get("group:sub")), sorted(items.values()))
        self.assertEqual(sorted(await self.tested_dic.multi_chain_get(["group", "sub"])), sorted(items.values()))
        self.assertEqual(await self.tested_dic.multi_dict("group:sub"), items)
        self.assertEqual(await self.tested_dic.multi_del("group:sub"), 3)
        self.assertEqual(await self.tested_dic.multi_dict("group:sub"), {})

        info = await self.tested_dic.get_redis_info()
        self.assertIsInstance(info, dict)
        self.assertTrue("redis_version" in info or "valkey_version" in info)

    async def test_concurrent_gather_operations(self) -> None:
        await asyncio.gather(*(self.tested_dic.set_item(f"c_{i}", i * 10) for i in range(25)))
        values = await asyncio.gather(*(self.tested_dic.get_item(f"c_{i}") for i in range(25)))
        self.assertEqual(values, [i * 10 for i in range(25)])
        self.assertEqual(await self.tested_dic.len(), 25)

    # ------------------------------------------------------------------
    # 7. Sync Dunder Misuse Protection (No Silent Unawaited Coroutines)
    # ------------------------------------------------------------------

    async def test_sync_dunders_raise_type_error_with_zero_unawaited_warnings(self) -> None:
        ops = [
            lambda: self.tested_dic["k"],
            lambda: self.tested_dic.__setitem__("k", 1),
            lambda: self.tested_dic.__delitem__("k"),
            lambda: "k" in self.tested_dic,
            lambda: len(self.tested_dic),
            lambda: iter(self.tested_dic),
            lambda: next(self.tested_dic),
            lambda: self.tested_dic.next(),
            lambda: reversed(self.tested_dic),
            lambda: self.tested_dic | {"a": 1},
            lambda: {"a": 1} | self.tested_dic,
            lambda: self.tested_dic.__ior__({"a": 1}),
            lambda: self.tested_dic == {"a": 1},
            lambda: self.tested_dic != {"a": 1},
            lambda: self.tested_dic.__sizeof__(),
        ]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for op in ops:
                with self.assertRaises(TypeError):
                    op()

            # Identity and non-mapping equality must still work normally
            self.assertTrue(self.tested_dic == self.tested_dic)
            self.assertFalse(self.tested_dic != self.tested_dic)
            self.assertFalse(self.tested_dic == None)  # noqa: E711
            self.assertTrue(self.tested_dic != None)  # noqa: E711
            self.assertFalse(self.tested_dic == 42)
            self.assertTrue(self.tested_dic != 42)

        self.assertEqual(caught, [])


if __name__ == "__main__":
    unittest.main()
