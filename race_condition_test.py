import unittest

from redis.client import StrictRedis
from requests import options

from extend_types_tests import BaseRedisDictTest


import redis
import time

from load_test_compression import format_value
from redis_dict import RedisDict

from typing import Any, Optional


class RaceConditionTestRedisDict(RedisDict):
    def _store_test(self, key: str, value: Any, redis) -> None:
        store_type, key = type(value).__name__, str(key)
        value = self.encoding_registry.get(store_type, lambda x: x)(value)  # type: ignore

        store_value = f'{store_type}:{value}'
        formatted_key = self._format_key(key)
        redis.set(formatted_key, store_value, ex=self.expire)

    def race_condition_test_setdefault(self, redis, key: str, default_value: Optional[Any] = None) -> Any:
        results = {}
        redis.set("start test", "start test")
        results["before"] = redis.get(self._format_key(key))

        found, value = self._load(key)
        results["after_load"] = redis.get(self._format_key(key))

        # Simulate another process writing here
        self._store_test(key, "competing_value", redis)

        results["after_competing_write"] = redis.get(self._format_key(key))
        if not found:
            results["before_not_found"] = redis.get(self._format_key(key))
            self[key] = default_value
            results["after_set_not_found"] = redis.get(self._format_key(key))
            redis.set("end test", "end test")
            return default_value, results
        redis.set("end test", "end test")
        return value, results

    def race_condition_test_setdefault_fix(self, redis, key: str, default_value: Optional[Any] = None) -> Any:
        results = {}
        redis.set("start test", "start test")
        results["before"] = redis.get(self._format_key(key))

        formatted_key = self._format_key(key)
        formatted_value = self._format_value(key, default_value)

        # Options with "get" present will allow us to get the parsing from "GET" command on the "SET" command.
        options = {"get": True}
        if self.preserve_expiration:
            result = redis.execute_command("SET", formatted_key, formatted_value, "NX", "GET", "KEEPTTL", **options)
        elif self.expire is not None:
            result = redis.execute_command("SET",formatted_key, formatted_value, "NX", "GET", "EX", self.expire, **options)
        else:
            result = redis.execute_command("SET", formatted_key, formatted_value, "NX", "GET", **options)

        if result is None:
            results["after_load"] = redis.get(self._format_key(key))
            return default_value, results

        # Decode if we got bytes back
        if isinstance(result, bytes):
            result = result.decode("utf-8")

        results["after_set"] = redis.get(self._format_key(key))
        formatted_result = self._transform(result)
        results["after_load"] = redis.get(self._format_key(key))

        redis.set("end test", "end test")
        return formatted_result, results


class TestRaceCondition(BaseRedisDictTest):
    def setUp(self):
        super().setUp()
        redis_config = {
            "host": "localhost",
            "port": 6379,
            "db": 0,
        }
        self.race_redis_dict = RaceConditionTestRedisDict(**redis_config)
        self.redis = StrictRedis(**redis_config)

    def test_race_condition_setdefault(self):
        """Test that demonstrates the race condition in setdefault without pipelining"""
        key = "test_key"
        expected_value = "expected_value"

        # Clear any existing value
        self.race_redis_dict.redis.delete(self.race_redis_dict._format_key(key))

        # Run test without pipelining
        value, results = self.race_redis_dict.race_condition_test_setdefault(
            self.redis, key, expected_value
        )

        # race condition took place
        self.assertEqual(results['before'],None)
        self.assertEqual(results['after_competing_write'],b'str:competing_value')
        self.assertEqual(results['before_not_found'], b'str:competing_value')
        self.assertEqual(results['after_set_not_found'], b'str:expected_value')

        # The competing write should be overwritten
        result = self.race_redis_dict.redis.get(self.race_redis_dict._format_key(key))
        self.assertEqual(result, "str:expected_value")
        self.assertEqual(self.race_redis_dict[key], expected_value)

    def test_race_condition_setdefault_fix(self):
        """Test that demonstrates how pipelining fixes the race condition"""
        key = "test_key"
        expected_value = "expected_value"

        # Clear any existing value
        self.race_redis_dict.redis.delete(self.race_redis_dict._format_key(key))

        # Run test with pipelining
        value, results = self.race_redis_dict.race_condition_test_setdefault_fix(
            self.redis, key, expected_value
        )

        # competing write can't no longer take place
        self.assertEqual(results['before'],None)
        self.assertEqual(results['after_load'],b'str:expected_value')

        result = self.race_redis_dict.redis.get(self.race_redis_dict._format_key(key))
        self.assertEqual(result, "str:expected_value")
        self.assertEqual(self.race_redis_dict[key], expected_value)

        already_set_value = "should not show"
        value, results = self.race_redis_dict.race_condition_test_setdefault_fix(
            self.redis, key, already_set_value
        )
        self.assertEqual(self.race_redis_dict[key],expected_value)

    def test_setdefault_with_expire(self):
        """Test setdefault with expiration setting"""
        redis_dict = RaceConditionTestRedisDict(expire=3600)
        key = "test_expire_key"
        default_value = "default"

        # Clear any existing values
        redis_dict.clear()

        # First call - should set with expiry
        value, results = redis_dict.race_condition_test_setdefault_fix(
            redis_dict.redis, key, default_value
        )

        # Check TTL
        actual_ttl = redis_dict.get_ttl(key)
        self.assertAlmostEqual(3600, actual_ttl, delta=2)

        # Second call - should get existing value and maintain TTL
        time.sleep(1)
        new_value, new_results = redis_dict.race_condition_test_setdefault_fix(
            redis_dict.redis, key, "different_default",
        )

        # TTL should be ~1 second less
        new_ttl = redis_dict.get_ttl(key)
        self.assertAlmostEqual(3600 - 1, new_ttl, delta=2)

        # Value should be unchanged
        self.assertEqual(value, default_value)

    def test_setdefault_with_preserve_ttl(self):
        """Test setdefault with preserve_expiration=True"""
        redis_dict = RaceConditionTestRedisDict(expire=3600, preserve_expiration=True)
        key = "test_preserve_key"
        expected_value = "expected_value"
        default_value = "default"
        sleep_time = 5

        redis_dict[key] = expected_value
        initial_ttl = redis_dict.get_ttl(key)

        time.sleep(sleep_time)
        # Try setdefault - should keep original TTL
        result_value, results = redis_dict.race_condition_test_setdefault_fix(
            redis_dict.redis, key, default_value
        )

        self.assertEqual(result_value, expected_value)

        time.sleep(1)
        # TTL should have been preserved, thus new_ttl+sleep_time should less than initial_ttl since sleep 1 second.
        new_ttl = redis_dict.get_ttl(key)
        self.assertLess(new_ttl+sleep_time, initial_ttl)

    def test_setdefault_concurrent_ttl(self):
        """Test TTL behavior with concurrent setdefault operations"""
        redis_dict = RaceConditionTestRedisDict(expire=3600)
        competing_dict =  RaceConditionTestRedisDict(expire=1800)  # Different TTL

        key = "test_concurrent_key"
        default_value = "default"

        redis_dict.clear()

        # First operation sets with 3600s TTL
        value1, results1 = redis_dict.race_condition_test_setdefault_fix(
            redis_dict.redis, key, default_value
        )

        ttl1 = redis_dict.get_ttl(key)
        self.assertAlmostEqual(3600, ttl1, delta=2)

        # Competing operation tries with 1800s TTL
        value2, results2 = competing_dict.race_condition_test_setdefault_fix(
            competing_dict.redis, key, "competing_value"
        )

        # Original TTL should be maintained
        ttl2 = redis_dict.get_ttl(key)
        self.assertAlmostEqual(3600, ttl2, delta=3)
        self.assertEqual(value1, value2)  # Should get same value


if __name__ == "__main__":
    unittest.main()