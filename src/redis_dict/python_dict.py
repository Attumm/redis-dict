"""Python Redis Dict module."""
from typing import Any, Iterator, Tuple, Union, Optional, List, Dict

import time
from datetime import timedelta

from redis import StrictRedis

from .core import RedisDict


class PythonRedisDict(RedisDict):
    """Python dictionary with Redis as backend.

    With support for advanced features, such as custom data types, pipelining, and key expiration.

    This class focuses on having one-to-on behavior of a dictionary while using Redis as storage layer, allowing
    for efficient storage and retrieval of key-value pairs. It supports various data types, including
    strings, integers, floats, lists, dictionaries, tuples, sets, and user-defined types. The class
    leverages the power of Redis pipelining to minimize network round-trip time, latency, and I/O load,
    thereby optimizing performance for batch operations. Additionally, it allows for the management of
    key expiration through the use of context managers.

    The RedisDict class is designed to be analogous to a standard Python dictionary while providing
    enhanced functionality, such as support for a wider range of data types and efficient batch operations.
    It aims to offer a seamless and familiar interface for developers familiar with Python dictionaries,
    enabling a smooth transition to a Redis-backed data store.

    Extendable Types: You can extend RedisDict by adding or overriding encoding and decoding functions.
    This functionality enables various use cases, such as managing encrypted data in Redis,
    To implement this, simply create and register your custom encoding and decoding functions.
    By delegating serialization to redis-dict, reduce complexity and have simple code in the codebase.
    """

    def __init__(self,
                 namespace: str = 'main',
                 expire: Union[int, timedelta, None] = None,
                 preserve_expiration: Optional[bool] = False,
                 redis: "Optional[StrictRedis[Any]]" = None,
                 **redis_kwargs: Any) -> None:  # noqa: D202 pydocstyle clashes with Sphinx
        """
        Initialize a RedisDict instance.

        Init the RedisDict instance.

        Args:
            namespace (str): A prefix for keys stored in Redis.
            expire (Union[int, timedelta, None], optional): Expiration time for keys.
            preserve_expiration (Optional[bool], optional): Preserve expiration on key updates.
            redis (Optional[StrictRedis[Any]], optional): A Redis connection instance.
            **redis_kwargs (Any): Additional kwargs for Redis connection if not provided.
        """
        super().__init__(
            namespace=namespace,
            expire=expire,
            preserve_expiration=preserve_expiration,
            redis=redis,
            raise_key_error_delete=True,
            **redis_kwargs
        )
        self._insertion_order_key = f"redis-dict-insertion-order-{namespace}"

    def __delitem__(self, key: str) -> None:
        """
        Delete the value associated with the given key, analogous to a dictionary.

        For distributed systems, we intentionally don't raise KeyError when the key doesn't exist.
        This ensures identical code running across different systems won't randomly fail
        when another system already achieved the deletion goal (key not existing).

        Warning:
            Setting dict_compliant=True will raise KeyError when key doesn't exist.
            This is not recommended for distributed systems as it can cause KeyErrors
            that are hard to debug when multiple systems interact with the same keys.

        Args:
            key (str): The key to delete

        Raises:
            KeyError: Only if dict_compliant=True and key doesn't exist
        """
        formatted_key = self._format_key(key)

        result = self.redis.delete(formatted_key)
        self._insertion_order_delete(formatted_key)
        if not result:
            raise KeyError(key)

    def _store(self, key: str, value: Any) -> None:
        """
        Store a value in Redis with the given key.

        Args:
            key (str): The key to store the value.
            value (Any): The value to be stored.

        Raises:
            ValueError: If the value or key fail validation.

        Note: Validity checks could be refactored to allow for custom exceptions that inherit from ValueError,
        providing detailed information about why a specific validation failed.
        This would enable users to specify which validity checks should be executed, add custom validity functions,
        and choose whether to fail on validation errors, or drop the data and only issue a warning and continue.
        Example use case is caching, to cache data only when it's between min and max sizes.
        Allowing for simple dict set operation, but only cache data that makes sense.

        """
        if not self._valid_input(value) or not self._valid_input(key):
            raise ValueError("Invalid input value or key size exceeded the maximum limit.")

        formatted_key = self._format_key(key)
        formatted_value = self._format_value(value)

        with self.pipeline():
            self._insertion_order_add(formatted_key)
            self._store_set(formatted_key, formatted_value)

    def setdefault(self, key: str, default_value: Optional[Any] = None) -> Any:
        """Get value under key, and if not present set default value.

        Return the value associated with the given key if it exists, otherwise set the value to the
        default value and return it. Analogous to a dictionary's setdefault method.

        Args:
            key (str): The key to retrieve the value.
            default_value (Optional[Any], optional): The value to set if the key is not found.

        Returns:
            Any: The value associated with the key or the default value.
        """
        formatted_key = self._format_key(key)
        formatted_value = self._format_value(default_value)

        # Todo bind both commands
        args, options = self._create_set_get_command(formatted_key, formatted_value)
        result = self.get_redis.execute_command(*args, **options)
        self._insertion_order_add(formatted_key)

        if result is None:
            return default_value

        return self._transform(result)

    def __len__(self) -> int:
        """
        Get the number of items in the RedisDict, analogous to a dictionary.

        Returns:
            int: The number of items in the RedisDict.
        """
        return self._insertion_order_len()

    def _scan_keys(self, search_term: str = '', full_scan: bool = False) -> Iterator[str]:
        return self._insertion_order_iter()

    def clear(self) -> None:
        """Remove all key-value pairs from the RedisDict in one batch operation using pipelining.

        This method mimics the behavior of the `clear` method from a standard Python dictionary.
        Redis pipelining is employed to group multiple commands into a single request, minimizing
        network round-trip time, latency, and I/O load, thereby enhancing the overall performance.

        """
        with self.pipeline():
            self._insertion_order_clear()
            for key in self._scan_keys(full_scan=True):
                self.redis.delete(key)

    def popitem(self) -> Tuple[str, Any]:
        """Remove and return a random (key, value) pair from the RedisDict as a tuple.

        This method is analogous to the `popitem` method of a standard Python dictionary.

        if dict_compliant set true stays true to In Python 3.7+, removes the last inserted item (LIFO order)

        Returns:
            tuple: A tuple containing a randomly chosen (key, value) pair.

        Raises:
            KeyError: If RedisDict is empty.
        """
        key = self._insertion_order_latest()
        if key is None:
            raise KeyError("popitem(): dictionary is empty")
        return self._parse_key(key), self._transform(self._pop(key))

    def _pop(self, formatted_key: str) -> Any:
        """
        Remove the value associated with the given key and return it.

        Or return the default value if the key is not found.

        Args:
            formatted_key (str): The formatted key to remove the value.

        Returns:
            Any: The value associated with the key or the default value.
        """
        # TODO bind both commands
        self._insertion_order_delete(formatted_key)
        return self.get_redis.execute_command("GETDEL", formatted_key)

    def multi_get(self, _key: str) -> List[Any]:
        """
        Not part of Python Redis Dict.

        Args:
            _key (str): Not used.

        Raises:
            NotImplementedError: Not part of Python Redis Dict.
        """
        raise NotImplementedError("Not part of PythonRedisDict")

    def multi_chain_get(self, _keys: List[str]) -> List[Any]:
        """
        Not part of Python Redis Dict.

        Args:
            _keys (List[str]): Not used.

        Raises:
            NotImplementedError: Not part of Python Redis Dict.
        """
        raise NotImplementedError("Not part of PythonRedisDict")

    def multi_dict(self, _key: str) -> Dict[str, Any]:
        """
        Not part of Python Redis Dict.

        Args:
            _key (str): Not used.

        Raises:
            NotImplementedError: Not part of Python Redis Dict.
        """
        raise NotImplementedError("Not part of PythonRedisDict")

    def multi_del(self, _key: str) -> int:
        """
        Not part of Python Redis Dict.

        Args:
            _key (str): Not used.

        Raises:
            NotImplementedError: Not part of Python Redis Dict.
        """
        raise NotImplementedError("Not part of PythonRedisDict")

    def _insertion_order_add(self, formatted_key: str) -> bool:
        """Record a key's insertion into the dictionary.

        This private method updates the insertion order tracking when a new key is added
        to the dictionary.

        Args:
            formatted_key (str): The key being added to the dictionary.

        Returns:
            bool: True if the insertion order was updated, False otherwise.
        """
        return bool(self.redis.zadd(self._insertion_order_key, {formatted_key: time.time()}))

    def _insertion_order_delete(self, formatted_key: str) -> bool:
        """Remove a key from the insertion order tracking.

        This private method updates the insertion order tracking when a key is removed
        from the dictionary.

        Args:
            formatted_key (str): The key being removed from the dictionary.

        Returns:
            bool: True if the insertion order was updated, False otherwise.
        """
        return bool(self.redis.zrem(self._insertion_order_key, formatted_key))

    def _insertion_order_iter(self) -> Iterator[str]:
        """Create an iterator for dictionary keys in their insertion order.

        This private method allows for iterating over the dictionary's keys in the order
        they were inserted.

        Yields:
            str: Keys in their insertion order.
        """
        # TODO add full_scan boolean and search terms.
        first = True
        cursor = -1
        while cursor != 0:
            if first:
                cursor = 0
                first = False
            cursor, data = self.get_redis.zscan(
                name=self._insertion_order_key,
                cursor=cursor,
                count=1
            )
            yield from (item[0] for item in data)

    def _insertion_order_clear(self) -> bool:
        """Clear all insertion order information.

        This private method resets the insertion order tracking for the dictionary.

        Returns:
            bool: True if the insertion order was successfully cleared, False otherwise.
        """
        return bool(self.redis.delete(self._insertion_order_key))

    def _insertion_order_len(self) -> int:
        """Get the number of keys in the insertion order tracking.

        This private method returns the count of keys being tracked for insertion order.

        Returns:
            int: The number of keys in the insertion order tracking.
        """
        return self.get_redis.zcard(self._insertion_order_key)

    def _insertion_order_latest(self) -> Union[str, None]:
        """Get the most recently inserted key in the dictionary.

        This private method retrieves the key that was most recently added to the dictionary.

        Returns:
            Union[str, None]: The most recently inserted key, or None if the dictionary is empty.
        """
        result = self.redis.zrange(self._insertion_order_key, -1, -1)
        return result[0] if result else None
