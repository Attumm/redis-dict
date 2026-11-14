"""Async Redis Dict module."""
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterable,
    List,
    Mapping,
    NoReturn,
    Optional,
    Tuple,
    Union,
    cast,
)

from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import ResponseError

from .core import RedisDict
from .type_management import SENTINEL


# pylint: disable=R0904, invalid-overridden-method
class AsyncRedisDict(RedisDict):
    """Asynchronous Python dictionary with Redis as backend.

    Inherits key/value formatting, namespace validation, and custom type serialization from
    :class:`~redis_dict.core.RedisDict` while executing all Redis I/O non-blockingly via
    :class:`redis.asyncio.Redis`.
    """

    redis: "AsyncRedis[Any]"  # type: ignore[assignment]
    get_redis: "AsyncRedis[Any]"  # type: ignore[assignment]
    _temp_redis: "Optional[AsyncRedis[Any]]"  # type: ignore[assignment]

    # pylint: disable=R0913
    def __init__(
        self,
        namespace: str = 'main',
        expire: Union[int, timedelta, None] = None,
        preserve_expiration: Optional[bool] = False,
        redis: "Optional[AsyncRedis[Any]]" = None,
        raise_key_error_delete: bool = False,
        **redis_kwargs: Any,
    ) -> None:  # noqa: D202
        """Initialize an AsyncRedisDict instance.

        Args:
            namespace (str): A prefix for keys stored in Redis.
            expire (Union[int, timedelta, None], optional): Expiration time for keys.
            preserve_expiration (Optional[bool], optional): Preserve expiration on key updates.
            redis (Optional[AsyncRedis[Any]], optional): An async Redis connection instance.
            raise_key_error_delete (bool): Raise KeyError if key is not found when deleting.
            **redis_kwargs (Any): Additional kwargs for the async Redis connection if not provided.
        """
        client: AsyncRedis[Any] = redis or AsyncRedis(decode_responses=True, **redis_kwargs)
        super().__init__(
            namespace=namespace,
            expire=expire,
            preserve_expiration=preserve_expiration,
            redis=cast(Any, client),
            raise_key_error_delete=raise_key_error_delete,
        )
        self._aiter: Optional[AsyncIterator[str]] = None

    async def close(self) -> None:
        """Close the underlying async Redis client."""
        await cast(Any, self.get_redis).aclose()

    async def __aenter__(self) -> 'AsyncRedisDict':
        """Enter the async context manager.

        Returns:
            AsyncRedisDict: The current AsyncRedisDict instance.
        """
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the async context manager and close the Redis connection.

        Args:
            exc_type (Any): Exception type if raised inside the context.
            exc_val (Any): Exception instance if raised inside the context.
            exc_tb (Any): Traceback if an exception was raised inside the context.
        """
        await self.close()

    def _unsupported_sync(self, hint: str) -> NoReturn:
        raise TypeError(f"AsyncRedisDict does not support synchronous operations; use {hint}.")

    def __repr__(self) -> str:
        """Return a non-blocking string representation of the AsyncRedisDict.

        Returns:
            str: String representation including the namespace.
        """
        return f"{type(self).__name__}(namespace={self.namespace!r})"

    def __str__(self) -> str:
        """Return a non-blocking string representation of the AsyncRedisDict.

        Returns:
            str: String representation including the namespace.
        """
        return repr(self)

    def __getitem__(self, item: str) -> NoReturn:
        """Raise TypeError directing callers to await get_item(key).

        Args:
            item (str): Key passed to bracket lookup.
        """
        self._unsupported_sync("'await d.get_item(key)'")

    def __setitem__(self, key: str, value: Any) -> NoReturn:
        """Raise TypeError directing callers to await set_item(key, value).

        Args:
            key (str): Key passed to bracket assignment.
            value (Any): Value passed to bracket assignment.
        """
        self._unsupported_sync("'await d.set_item(key, value)'")

    def __delitem__(self, key: str) -> NoReturn:
        """Raise TypeError directing callers to await del_item(key).

        Args:
            key (str): Key passed to del operator.
        """
        self._unsupported_sync("'await d.del_item(key)'")

    def __contains__(self, key: str) -> NoReturn:
        """Raise TypeError directing callers to await contains(key).

        Args:
            key (str): Key passed to membership test.
        """
        self._unsupported_sync("'await d.contains(key)'")

    def __len__(self) -> NoReturn:
        """Raise TypeError directing callers to await len().

        Raises:
            TypeError: Always raised because length requires async Redis I/O.
        """
        raise TypeError("AsyncRedisDict does not support synchronous operations; use 'await d.len()'.")

    def __iter__(self) -> NoReturn:
        """Raise TypeError directing callers to async iteration.

        Raises:
            TypeError: Always raised because iteration requires async Redis I/O.
        """
        raise TypeError("AsyncRedisDict does not support synchronous operations; use 'async for key in d:'.")

    def __next__(self) -> NoReturn:
        """Raise TypeError directing callers to await __anext__()."""
        self._unsupported_sync("'await d.__anext__()'")

    def next(self) -> NoReturn:
        """Raise TypeError directing callers to await __anext__()."""
        self._unsupported_sync("'await d.__anext__()'")

    def __reversed__(self) -> NoReturn:
        """Raise TypeError directing callers to async iteration."""
        self._unsupported_sync("'async for key in d.keys():'")

    def __or__(self, other: Dict[str, Any]) -> NoReturn:
        """Raise TypeError directing callers to await to_dict().

        Args:
            other (Dict[str, Any]): Right-hand mapping operand.
        """
        self._unsupported_sync("'await d.to_dict()'")

    def __ror__(self, other: Dict[str, Any]) -> NoReturn:
        """Raise TypeError directing callers to await to_dict().

        Args:
            other (Dict[str, Any]): Left-hand mapping operand.
        """
        self._unsupported_sync("'await d.to_dict()'")

    def __ior__(self, other: Dict[str, Any]) -> NoReturn:
        """Raise TypeError directing callers to await update(other).

        Args:
            other (Dict[str, Any]): Mapping operand.
        """
        self._unsupported_sync("'await d.update(other)'")

    def __sizeof__(self) -> NoReturn:
        """Raise TypeError directing callers to await to_dict()."""
        self._unsupported_sync("'await d.to_dict()'")

    def __eq__(self, other: Any) -> bool:
        """Support identity and non-mapping checks while rejecting sync mapping I/O.

        Args:
            other (Any): Object to compare against.

        Returns:
            bool: True when comparing the same instance; NotImplemented for non-mappings.
        """
        if self is other:
            return True
        if not self._is_ducktype_dict(other):
            return NotImplemented
        self._unsupported_sync("'await d.to_dict() == ...'")

    def __ne__(self, other: Any) -> bool:
        """Support identity and non-mapping checks while rejecting sync mapping I/O.

        Args:
            other (Any): Object to compare against.

        Returns:
            bool: False when comparing the same instance; NotImplemented for non-mappings.
        """
        if self is other:
            return False
        if not self._is_ducktype_dict(other):
            return NotImplemented
        self._unsupported_sync("'await d.to_dict() != ...'")

    async def _store_set(self, formatted_key: str, formatted_value: str) -> None:  # type: ignore[override]
        if self.preserve_expiration and await self.get_redis.exists(formatted_key):
            await self.redis.set(formatted_key, formatted_value, keepttl=True)
        else:
            await self.redis.set(formatted_key, formatted_value, ex=self.expire)

    async def _store(self, key: str, value: Any) -> None:  # type: ignore[override]
        """Store a value in Redis under the given key.

        Args:
            key (str): The key to store the value under.
            value (Any): The value to be stored.

        Raises:
            ValueError: If the value or key exceeds the maximum allowed size.
        """
        if not self._valid_input(value) or not self._valid_input(key):
            raise ValueError("Invalid input value or key size exceeded the maximum limit.")

        formatted_key = self._format_key(key)
        formatted_value = self._format_value(value)
        await self._store_set(formatted_key, formatted_value)

    async def _load(self, key: str) -> Tuple[bool, Any]:  # type: ignore[override]
        """Load and decode a value from Redis.

        Args:
            key (str): The key to retrieve.

        Returns:
            Tuple[bool, Any]: Whether the key existed and its decoded value.
        """
        result = await self.get_redis.get(self._format_key(key))
        if result is None:
            return False, None
        return True, self._transform(result)

    async def get_item(self, key: str) -> Any:
        """Get the value associated with the given key, analogous to ``dict[key]``.

        Args:
            key (str): The key to retrieve.

        Returns:
            Any: The decoded value stored under ``key``.

        Raises:
            KeyError: If ``key`` is not found.
        """
        found, value = await self._load(key)
        if not found:
            raise KeyError(key)
        return value

    async def set_item(self, key: str, value: Any) -> None:
        """Set the value associated with the given key, analogous to ``dict[key] = value``.

        Args:
            key (str): The key to store the value under.
            value (Any): The value to store.
        """
        await self._store(key, value)

    async def del_item(self, key: str) -> None:
        """Delete the value associated with the given key, analogous to ``del dict[key]``.

        Args:
            key (str): The key to delete.

        Raises:
            KeyError: If ``raise_key_error_delete`` is True and ``key`` does not exist.
        """
        result = await self.redis.delete(self._format_key(key))
        if self.raise_key_error_delete and not result:
            raise KeyError(key)

    async def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Return the value for ``key`` if present, otherwise ``default``.

        Args:
            key (str): The key to retrieve.
            default (Optional[Any], optional): Fallback value if ``key`` is absent.

        Returns:
            Any: The value associated with ``key`` or ``default``.
        """
        found, item = await self._load(key)
        if not found:
            return default
        return item

    async def contains(self, key: str) -> bool:
        """Check whether ``key`` exists in Redis, analogous to ``key in dict``.

        Args:
            key (str): The key to check.

        Returns:
            bool: True if ``key`` exists, False otherwise.
        """
        return bool(await self.get_redis.exists(self._format_key(key)))

    async def len(self) -> int:
        """Count the number of items in this namespace.

        Returns:
            int: Number of keys in the namespace.
        """
        count = 0
        async for _ in self._scan_keys(full_scan=True):
            count += 1
        return count

    # pylint: disable=unused-argument
    async def _scan_keys(  # type: ignore[override]
        self,
        search_term: str = '',
        full_scan: bool = False,
    ) -> AsyncIterator[str]:
        search_query = self._create_iter_query(search_term)
        async for item in self.get_redis.scan_iter(match=search_query, count=self._batch_size):
            yield str(item)

    def __aiter__(self) -> AsyncIterator[str]:
        """Return an async iterator over the keys of the AsyncRedisDict.

        Returns:
            AsyncIterator[str]: Async iterator yielding unprefixed keys.
        """
        self._aiter = self.keys()
        return self._aiter

    async def __anext__(self) -> str:
        """Return the next key from the active async iterator.

        Returns:
            str: Next unprefixed key.

        Raises:
            StopAsyncIteration: When no active iterator exists or iteration completes.
        """
        if self._aiter is None:
            raise StopAsyncIteration
        return await self._aiter.__anext__()

    async def keys(self) -> AsyncIterator[str]:  # type: ignore[override]
        """Yield unprefixed keys in the AsyncRedisDict.

        Yields:
            str: Each key in the namespace.
        """
        async for raw_key in self._scan_keys():
            yield self._parse_key(raw_key)

    async def key(self, search_term: str = '') -> Optional[str]:  # type: ignore[override]
        """Return the first key matching ``search_term``, or None if none match.

        Args:
            search_term (str): Optional key prefix filter.

        Returns:
            Optional[str]: First matching key, or None.
        """
        async for raw_key in self._scan_keys(search_term):
            return self._parse_key(raw_key)
        return None

    async def _items(self, search_term: str = '') -> AsyncIterator[Tuple[str, Any]]:  # type: ignore[override]
        async for raw_key in self._scan_keys(search_term):
            parsed_key = self._parse_key(raw_key)
            try:
                yield parsed_key, await self.get_item(parsed_key)
            except (KeyError, ResponseError):
                pass

    async def items(self) -> AsyncIterator[Tuple[str, Any]]:  # type: ignore[override]
        """Yield ``(key, value)`` pairs in the AsyncRedisDict.

        Yields:
            Tuple[str, Any]: Key-value pairs in the namespace.
        """
        async for pair in self._items():
            yield pair

    async def values(self) -> AsyncIterator[Any]:  # type: ignore[override]
        """Yield decoded values in the AsyncRedisDict.

        Yields:
            Any: Decoded values in the namespace.
        """
        async for _, value in self._items():
            yield value

    async def to_dict(self) -> Dict[str, Any]:  # type: ignore[override]
        """Materialize the AsyncRedisDict into a standard Python ``dict``.

        Returns:
            Dict[str, Any]: Dictionary containing all key-value pairs in the namespace.
        """
        return {k: v async for k, v in self.items()}

    async def copy(self) -> Dict[str, Any]:  # type: ignore[override]
        """Return a shallow copy as a standard Python ``dict``.

        Returns:
            Dict[str, Any]: Shallow dictionary copy of the namespace.
        """
        return await self.to_dict()

    async def clear(self) -> None:  # type: ignore[override]
        """Delete all keys in this namespace in a pipelined batch."""
        async with self.pipeline():
            async for raw_key in self._scan_keys(full_scan=True):
                await self.redis.delete(raw_key)

    async def _pop(self, formatted_key: str) -> Any:
        return await cast(Any, self.get_redis).execute_command("GETDEL", formatted_key)

    async def pop(self, key: str, default: Union[Any, object] = SENTINEL) -> Any:
        """Atomically remove and return the value for ``key``, or ``default`` if absent.

        Args:
            key (str): The key to remove.
            default (Optional[Any], optional): Value returned when ``key`` is absent.

        Returns:
            Any: Removed value or ``default``.

        Raises:
            KeyError: If ``key`` is absent and ``default`` was not provided.
        """
        value = await self._pop(self._format_key(key))
        if value is not None:
            return self._transform(value)
        if default is not SENTINEL:
            return default
        raise KeyError(key)

    async def popitem(self) -> Tuple[str, Any]:  # type: ignore[override]
        """Remove and return a ``(key, value)`` pair from the AsyncRedisDict.

        Returns:
            Tuple[str, Any]: Removed ``(key, value)`` pair.

        Raises:
            KeyError: If the AsyncRedisDict is empty.
        """
        while True:
            found_key = await self.key()
            if found_key is None:
                raise KeyError("popitem(): dictionary is empty")
            try:
                return found_key, await self.pop(found_key)
            except KeyError:
                continue

    async def setdefault(
        self,
        key: str,
        default_value: Optional[Any] = None,
    ) -> Any:
        """Return ``key``'s value if present; otherwise set and return ``default_value``.

        Args:
            key (str): The key to look up or initialize.
            default_value (Optional[Any], optional): Value stored if ``key`` is missing.

        Returns:
            Any: Existing value or ``default_value``.

        Raises:
            ValueError: If ``key`` or ``default_value`` exceeds the maximum allowed size.
        """
        if not self._valid_input(default_value) or not self._valid_input(key):
            raise ValueError("Invalid input value or key size exceeded the maximum limit.")

        args, options = self._create_set_get_command(
            self._format_key(key),
            self._format_value(default_value),
        )
        result = await cast(Any, self.get_redis).execute_command(*args, **options)
        return default_value if result is None else self._transform(result)

    async def update(  # type: ignore[override]
        self,
        other: Union[Mapping[str, object], 'AsyncRedisDict', Iterable[Tuple[str, object]]] = (),
        /,
        **kwargs: object,
    ) -> None:
        """Update the AsyncRedisDict from a mapping, AsyncRedisDict, iterable, and/or kwargs.

        Args:
            other (Union[Mapping[str, object], AsyncRedisDict, Iterable[Tuple[str, object]]]): Source items.
            **kwargs (object): Additional key-value pairs to store.
        """
        async with self.pipeline():
            if isinstance(other, AsyncRedisDict):
                async for k, v in other.items():
                    await self.set_item(k, v)
            elif self._is_ducktype_dict(other):
                mapping = cast(Mapping[str, object], other)
                for k in mapping.keys():  # pylint: disable=consider-iterating-dictionary
                    await self.set_item(k, mapping[k])
            else:
                for k, v in cast(Iterable[Tuple[str, object]], other):
                    await self.set_item(k, v)
            for k, v in kwargs.items():
                await self.set_item(k, v)

    async def fromkeys(  # type: ignore[override]
        self,
        iterable: Iterable[str],
        value: Optional[Any] = None,
    ) -> 'AsyncRedisDict':
        """Populate keys from ``iterable`` with ``value`` and return ``self``.

        Args:
            iterable (Iterable[str]): Keys to populate.
            value (Optional[Any], optional): Value assigned to every key.

        Returns:
            AsyncRedisDict: The populated AsyncRedisDict instance.
        """
        async with self.pipeline():
            for key in iterable:
                await self.set_item(key, value)
        return self

    async def chain_set(self, iterable: List[str], v: Any) -> None:  # type: ignore[override]
        """Set a value using a hierarchical chain of keys.

        Args:
            iterable (List[str]): Key segments joined with ``:``.
            v (Any): Value to store.
        """
        await self.set_item(':'.join(iterable), v)

    async def chain_get(self, iterable: List[str]) -> Any:
        """Get a value using a hierarchical chain of keys.

        Args:
            iterable (List[str]): Key segments joined with ``:``.

        Returns:
            Any: Decoded value stored under the chained key.
        """
        return await self.get_item(':'.join(iterable))

    async def chain_del(self, iterable: List[str]) -> None:  # type: ignore[override]
        """Delete a value using a hierarchical chain of keys.

        Args:
            iterable (List[str]): Key segments joined with ``:``.
        """
        await self.del_item(':'.join(iterable))

    @asynccontextmanager
    async def expire_at(self, sec_epoch: Union[int, timedelta]) -> AsyncIterator[None]:  # type: ignore[override]
        """Temporarily set ``self.expire`` for writes inside the async context.

        Args:
            sec_epoch (Union[int, timedelta]): Expiration duration in seconds or timedelta.

        Yields:
            None: Execution context with temporary expiration configured.
        """
        with super().expire_at(sec_epoch):
            yield

    @asynccontextmanager
    async def pipeline(self) -> AsyncIterator[None]:  # type: ignore[override]
        """Batch write operations inside a Redis async pipeline.

        Yields:
            None: Execution context batching Redis write commands.
        """
        top_level = False
        if self._temp_redis is None:
            self.redis, self._temp_redis, top_level = (
                cast(Any, self.redis.pipeline()),
                self.redis,
                True,
            )
        try:
            yield
        finally:
            if top_level:
                pipe = self.redis
                assert self._temp_redis is not None  # nosec B101
                self.redis, self._temp_redis = self._temp_redis, None
                await cast(Any, pipe).execute()

    async def multi_get(self, key: str) -> List[Any]:  # type: ignore[override]
        """Return values for all keys matching prefix ``key``.

        Args:
            key (str): Shared key prefix.

        Returns:
            List[Any]: Decoded values matching ``key``.
        """
        return [value async for _, value in self._items(key)]

    async def multi_chain_get(self, keys: List[str]) -> List[Any]:  # type: ignore[override]
        """Return values for all keys matching the chained prefix ``keys``.

        Args:
            keys (List[str]): Key prefix segments joined with ``:``.

        Returns:
            List[Any]: Decoded values matching the chained prefix.
        """
        return await self.multi_get(':'.join(keys))

    async def multi_dict(self, key: str) -> Dict[str, Any]:  # type: ignore[override]
        """Return leaf ``{key: value}`` pairs for all keys matching prefix ``key``.

        Args:
            key (str): Shared key prefix.

        Returns:
            Dict[str, Any]: Mapping of leaf keys to decoded values.
        """
        return {k.rsplit(self.key_delimiter, 1)[-1]: v async for k, v in self._items(key)}

    async def multi_del(self, key: str) -> int:  # type: ignore[override]
        """Delete all keys matching prefix ``key``.

        Args:
            key (str): Shared key prefix.

        Returns:
            int: Number of keys deleted.
        """
        keys = [raw_key async for raw_key in self._scan_keys(key)]
        if not keys:
            return 0
        return int(await self.redis.delete(*keys))

    async def get_redis_info(self) -> Dict[str, Any]:  # type: ignore[override]
        """Retrieve information and statistics from the Redis server.

        Returns:
            Dict[str, Any]: Server info dictionary.
        """
        return dict(await self.get_redis.info())

    async def get_ttl(self, key: str) -> Optional[int]:  # type: ignore[override]
        """Return the remaining TTL in seconds for ``key``, or None if persistent/missing.

        Args:
            key (str): Key to inspect.

        Returns:
            Optional[int]: Positive TTL in seconds, or None.
        """
        val = int(await self.get_redis.ttl(self._format_key(key)))
        if val < 0:
            return None
        return val
