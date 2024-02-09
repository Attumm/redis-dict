import json
from datetime import timedelta
from typing import Any, Callable, Dict, Iterator, Set, List, Tuple, Union, Optional
from redis import StrictRedis

from contextlib import contextmanager

SENTINEL = object()


transform_type = Dict[str, Callable[[str], Any]]
pre_transform_type = Dict[str, Callable[[Any], str]]


def _transform_tuple(val: str) -> Tuple[Any, ...]:
    """
    Deserialize a JSON-formatted string to a tuple.

    This function takes a JSON-formatted string, deserializes it to a list, and
    then converts the list to a tuple.

    Args:
        val (str): A JSON-formatted string representing a list.

    Returns:
        Tuple[Any, ...]: A tuple with the deserialized values from the input string.
    """
    return tuple(json.loads(val))


def _pre_transform_tuple(val: Tuple[Any, ...]) -> str:
    """
    Serialize a tuple to a JSON-formatted string.

    This function takes a tuple, converts it to a list, and then serializes
    the list to a JSON-formatted string.

    Args:
        val (Tuple[Any, ...]): A tuple with values to be serialized.

    Returns:
        str: A JSON-formatted string representing the input tuple.
    """
    return json.dumps(list(val))


def _transform_set(val: str) -> Set[Any]:
    """
    Deserialize a JSON-formatted string to a set.

    This function takes a JSON-formatted string, deserializes it to a list, and
    then converts the list to a set.

    Args:
        val (str): A JSON-formatted string representing a list.

    Returns:
        set[Any]: A set with the deserialized values from the input string.
    """
    return set(json.loads(val))


def _pre_transform_set(val: Set[Any]) -> str:
    """
    Serialize a set to a JSON-formatted string.

    This function takes a set, converts it to a list, and then serializes the
    list to a JSON-formatted string.

    Args:
        val (set[Any]): A set with values to be serialized.

    Returns:
        str: A JSON-formatted string representing the input set.
    """
    return json.dumps(list(val))


class RedisDict:
    """
    A Redis-backed dictionary-like data structure with support for advanced features, such as
    custom data types, pipelining, and key expiration.

    This class provides a dictionary-like interface that interacts with a Redis database, allowing
    for efficient storage and retrieval of key-value pairs. It supports various data types, including
    strings, integers, floats, lists, dictionaries, tuples, sets, and user-defined types. The class
    leverages the power of Redis pipelining to minimize network round-trip time, latency, and I/O load,
    thereby optimizing performance for batch operations. Additionally, it allows for the management of
    key expiration through the use of context managers.

    The RedisDict class is designed to be analogous to a standard Python dictionary while providing
    enhanced functionality, such as support for a wider range of data types and efficient batch operations.
    It aims to offer a seamless and familiar interface for developers familiar with Python dictionaries,
    enabling a smooth transition to a Redis-backed data store.

    Attributes:
        transform (Dict[str, Callable[[str], Any]]): A dictionary of data type transformation functions for loading data.
        pre_transform (Dict[str, Callable[[Any], str]]): A dictionary of data type transformation functions for storing data.
        namespace (str): A string used as a prefix for Redis keys to separate data in different namespaces.
        expire (Union[int, None]): An optional expiration time for keys, in seconds.

    """

    transform: transform_type = {
        type('').__name__: str,
        type(1).__name__: int,
        type(0.1).__name__: float,
        type(True).__name__: lambda x: x == "True",
        type(None).__name__: lambda x: None,

        "list": json.loads,
        "dict": json.loads,
        "tuple": _transform_tuple,
        type(set()).__name__: _transform_set,
    }

    pre_transform: pre_transform_type = {
        "list": json.dumps,
        "dict": json.dumps,
        "tuple": _pre_transform_tuple,
        type(set()).__name__: _pre_transform_set,
    }

    def __init__(self,
                 namespace: str = 'main',
                 expire: Union[int, timedelta, None] = None,
                 preserve_expiration: Optional[bool] = False,
                 **redis_kwargs: Any) -> None:
        """
        Initialize a RedisDict instance.

        Args:
            namespace (str, optional): A prefix for keys stored in Redis.
            expire (int, timedelta, optional): Expiration time for keys in seconds.
            preserve_expiration (bool, optional): Whether or not to preserve the expiration.
            **redis_kwargs: Additional keyword arguments passed to StrictRedis.
        """
        self.temp_redis: Optional[StrictRedis[Any]] = None
        self.namespace: str = namespace
        self.expire: Union[int, timedelta, None] = expire
        self.preserve_expiration: Optional[bool] = preserve_expiration
        self.redis: StrictRedis[Any] = StrictRedis(decode_responses=True, **redis_kwargs)
        self.get_redis: StrictRedis[Any] = self.redis

    def _format_key(self, key: str) -> str:
        """
        Format a key with the namespace prefix.

        Args:
            key (str): The key to be formatted.

        Returns:
            str: The formatted key with the namespace prefix.
        """
        return '{}:{}'.format(self.namespace, str(key))

    def _valid_input(self, val: Any, val_type: str) -> bool:
        """
        Check if the input value is valid based on the specified value type.

        This method ensures that the input value is within the acceptable constraints for the given
        value type. For example, when the value type is "str", the method checks that the string
        length does not exceed the maximum allowed size (500 MB).

        Args:
            val (Union[str, int, float, bool]): The input value to be validated.
            val_type (str): The type of the input value ("str", "int", "float", or "bool").

        Returns:
            bool: True if the input value is valid, False otherwise.
        """
        if val_type == "str":
            return len(val) < (500 * 1024 * 1024)
        return True

    def _store(self, key: str, value: Any) -> None:
        """
        Store a value in Redis with the given key.

        Args:
            key (str): The key to store the value.
            value (Any): The value to be stored.
        """
        store_type, key = type(value).__name__, str(key)
        if not self._valid_input(value, store_type) or not self._valid_input(key, "str"):
            # TODO When needed, make valid_input, pass the reason, or throw a exception.
            raise ValueError("Invalid input value or key size exceeded the maximum limit.")
        value = self.pre_transform.get(store_type, lambda x: x)(value)  # type: ignore

        store_value = '{}:{}'.format(store_type, value)
        formatted_key = self._format_key(key)

        if self.preserve_expiration and self.redis.exists(formatted_key):
            self.redis.set(formatted_key, store_value, keepttl=True)
        else:
            self.redis.set(formatted_key, store_value, ex=self.expire)

    def _load(self, key: str) -> Tuple[bool, Any]:
        """
        Load a value from Redis with the given key.

        Args:
            key (str): The key to retrieve the value.

        Returns:
            tuple: A tuple containing a boolean indicating whether the value was found and the value itself.
        """
        result = self.get_redis.get(self._format_key(key))
        if result is None:
            return False, None
        t, value = result.split(':', 1)
        return True, self.transform.get(t, lambda x: x)(value)

    def _transform(self, result: str) -> Any:
        """
        Transform the result string from Redis into the appropriate Python object.

        Args:
            result (str): The result string from Redis.

        Returns:
            Any: The transformed Python object.
        """
        t, value = result.split(':', 1)
        return self.transform.get(t, lambda x: x)(value)

    def add_type(self, k: str, v: Callable[[str], Any]) -> None:
        """
        Add a custom type to the transform mapping.

        Args:
            k (str): The key representing the type.
            v (Callable): The transformation function for the type.
        """
        self.transform[k] = v

    def __cmp__(self, other: Any) -> int:
        """
        Compare the current RedisDict with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            int: 1 if equal, -1 otherwise.
        Note:
            TODO add the following methods
            __lt__(self, other)
            __le__(self, other)
            __eq__(self, other)
            __ne__(self, other)
            __gt__(self, other)
            __ge__(self, other)
        """
        if len(self) != len(other):
            return -1
        for key, value in self.iteritems():
            if value != other.get(key, SENTINEL):
                return -1
        return 1

    def __getitem__(self, item: str) -> Any:
        """
        Get the value associated with the given key, analogous to a dictionary.

        Args:
            item (str): The key to retrieve the value.

        Returns:
            Any: The value associated with the key.

        Raises:
            KeyError: If the key is not found.
        """
        found, value = self._load(item)
        if not found:
            raise KeyError(item)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Set the value associated with the given key, analogous to a dictionary.

        Args:
            key (str): The key to store the value.
            value (Any): The value to be stored.
        """
        self._store(key, value)

    def __delitem__(self, key: str) -> None:
        """
        Delete the value associated with the given key, analogous to a dictionary.

        Args:
            key (str): The key to delete the value.
        """
        self.redis.delete(self._format_key(key))

    def __contains__(self, key: str) -> bool:
        """
        Check if the given key exists in the RedisDict, analogous to a dictionary.

        Args:
            key (str): The key to check for existence.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        return self._load(key)[0]

    def __len__(self) -> int:
        """
        Get the number of items in the RedisDict, analogous to a dictionary.

        Returns:
            int: The number of items in the RedisDict.
        """
        return len(list(self._scan_keys()))

    def __iter__(self) -> Iterator[str]:
        """
        Return an iterator over the keys of the RedisDict, analogous to a dictionary.

        Returns:
            Iterator[str]: An iterator over the keys of the RedisDict.
        """
        self.iter = self.iterkeys()
        return self

    def __repr__(self) -> str:
        """
        Create a string representation of the RedisDict.

        Returns:
            str: A string representation of the RedisDict.
        """
        return str(self)

    def __str__(self) -> str:
        """
        Create a string representation of the RedisDict.

        Returns:
            str: A string representation of the RedisDict.
        """
        return str(self.to_dict())

    def __next__(self) -> str:
        """
        Get the next item in the iterator.

        Returns:
            str: The next item in the iterator.

        Raises:
            StopIteration: If there are no more items.
        """
        return next(self.iter)

    def next(self) -> str:
        """
        Get the next item in the iterator (alias for __next__).

        Returns:
            str: The next item in the iterator.

        Raises:
            StopIteration: If there are no more items.
        """
        return self.__next__()

    def _scan_keys(self, search_term: str = '') -> Iterator[str]:
        """
        Scan for Redis keys matching the given search term.

        Args:
            search_term (str, optional): A search term to filter keys. Defaults to ''.

        Returns:
            Iterator[str]: An iterator of matching Redis keys.
        """
        return self.get_redis.scan_iter(match='{}:{}{}'.format(self.namespace, search_term, '*'))

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Return the value for the given key if it exists, otherwise return the default value.
        Analogous to a dictionary's get method.

        Args:
            key (str): The key to retrieve the value.
            default (Optional[Any], optional): The value to return if the key is not found.

        Returns:
            Optional[Any]: The value associated with the key or the default value.
        """
        found, item = self._load(key)
        if not found:
            return default
        return item

    def iterkeys(self) -> Iterator[str]:
        """
            Note: for pythone2 str is needed
        """
        to_rm = len(self.namespace) + 1
        return (str(item[to_rm:]) for item in self._scan_keys())

    def key(self, search_term: str = '') -> Optional[str]:
        """
        Note: for pythone2 str is needed
        """
        to_rm = len(self.namespace) + 1
        cursor, data = self.get_redis.scan(match='{}:{}{}'.format(self.namespace, search_term, '*'), count=1)
        for item in data:
            return str(item[to_rm:])

        return None

    def keys(self) -> List[str]:
        """
        Return a list of keys in the RedisDict, analogous to a dictionary's keys method.

        Returns:
            List[str]: A list of keys in the RedisDict.
        """
        return list(self.iterkeys())

    def iteritems(self) -> Iterator[Tuple[str, Any]]:
        """
        Note: for pythone2 str is needed
        """
        to_rm = len(self.namespace) + 1
        for item in self._scan_keys():
            try:
                yield (str(item[to_rm:]), self[item[to_rm:]])
            except KeyError:
                pass

    def items(self) -> List[Tuple[str, Any]]:
        """
        Return a list of key-value pairs (tuples) in the RedisDict, analogous to a dictionary's items method.

        Returns:
            List[Tuple[str, Any]]: A list of key-value pairs in the RedisDict.
        """
        return list(self.iteritems())

    def values(self) -> List[Any]:
        """
        Return a list of values in the RedisDict, analogous to a dictionary's values method.

        Returns:
            List[Any]: A list of values in the RedisDict.
        """
        return list(self.itervalues())

    def itervalues(self) -> Iterator[Any]:
        """
        Iterate over the values in the RedisDict.

        Returns:
            Iterator[Any]: An iterator of values in the RedisDict.
        """
        to_rm = len(self.namespace) + 1
        for item in self._scan_keys():
            try:
                yield self[item[to_rm:]]
            except KeyError:
                pass

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the RedisDict to a Python dictionary.

        Returns:
            Dict[str, Any]: A dictionary with the same key-value pairs as the RedisDict.
        """
        return dict(self.items())

    def clear(self) -> None:
        """
        Remove all key-value pairs from the RedisDict in one batch operation using pipelining.

        This method mimics the behavior of the `clear` method from a standard Python dictionary.
        Redis pipelining is employed to group multiple commands into a single request, minimizing
        network round-trip time, latency, and I/O load, thereby enhancing the overall performance.

        It is important to highlight that the clear method can be safely executed within the context of an initiated pipeline operation
        """
        with self.pipeline():
            for key in self:
                del (self[key])

    def pop(self, key: str, default: Union[Any, object] = SENTINEL) -> Any:
        """
        Remove the value associated with the given key and return it, or return the default value
        if the key is not found. Analogous to a dictionary's pop method.

        Args:
            key (str): The key to remove the value.
            default (Optional[Any], optional): The value to return if the key is not found.

        Returns:
            Optional[Any]: The value associated with the key or the default value.

        Raises:
            KeyError: If the key is not found and no default value is provided.
        """
        try:
            value = self[key]
        except KeyError:
            if default is not SENTINEL:
                return default
            raise

        del (self[key])
        return value

    def popitem(self) -> Tuple[str, Any]:
        """
        Remove and return a random (key, value) pair from the RedisDict as a tuple.
        This method is analogous to the `popitem` method of a standard Python dictionary.

        Returns:
            tuple: A tuple containing a randomly chosen (key, value) pair.

        Raises:
            KeyError: If RedisDict is empty.
        """
        while True:
            key = self.key()
            if key is None:
                raise KeyError("popitem(): dictionary is empty")
            try:
                return key, self.pop(key)
            except KeyError:
                continue

    def setdefault(self, key: str, default_value: Optional[Any] = None) -> Any:
        """
        Return the value associated with the given key if it exists, otherwise set the value to the
        default value and return it. Analogous to a dictionary's setdefault method.

        Args:
            key (str): The key to retrieve the value.
            default (Optional[Any], optional): The value to set if the key is not found.

        Returns:
            Any: The value associated with the key or the default value.
        """
        found, value = self._load(key)
        if not found:
            self[key] = default_value
            return default_value
        return value

    def copy(self) -> Dict[str, Any]:
        """
        Create a shallow copy of the RedisDict and return it as a standard Python dictionary.
        This method is analogous to the `copy` method of a standard Python dictionary

        Returns:
            dict: A shallow copy of the RedisDict as a standard Python dictionary.

        Note:
            does not create a new RedisDict instance.
        """
        return self.to_dict()

    def update(self, dic: Dict[str, Any]) -> None:
        """
        Update the RedisDict with key-value pairs from the given mapping, analogous to a dictionary's update method.

        Args:
            other (Mapping[str, Any]): A mapping containing key-value pairs to update the RedisDict.
        """
        with self.pipeline():
            for key, value in dic.items():
                self[key] = value

    def fromkeys(self, iterable: List[str], value: Optional[Any] = None) -> 'RedisDict':
        """
        Create a new RedisDict with keys from the provided iterable and values set to the given value.
        This method is analogous to the `fromkeys` method of a standard Python dictionary, populating
        the RedisDict with the keys from the iterable and setting their corresponding values to the
        specified value.


        Args:
            iterable (List[str]): An iterable containing the keys to be added to the RedisDict.
            value (Optional[Any], optional): The value to be assigned to each key in the RedisDict. Defaults to None.

        Returns:
            RedisDict: The current RedisDict instance, now populated with the keys from the iterable and their corresponding values.
        """
        for key in iterable:
            self[key] = value
        return self

    def __sizeof__(self) -> int:
        """
        Return the approximate size of the RedisDict in memory, in bytes.
        This method is analogous to the `__sizeof__` method of a standard Python dictionary, estimating
        the memory consumption of the RedisDict based on the serialized in-memory representation.

        Returns:
            int: The approximate size of the RedisDict in memory, in bytes.
        """
        return self.to_dict().__sizeof__()

    def chain_set(self, iterable: List[str], v: Any) -> None:
        """
        Set a value in the RedisDict using a chain of keys.

        Args:
            iterable (List[str]): A list of keys representing the chain.
            v (Any): The value to be set.
        """
        self[':'.join(iterable)] = v

    def chain_get(self, iterable: List[str]) -> Any:
        """
        Get a value from the RedisDict using a chain of keys.

        Args:
            iterable (List[str]): A list of keys representing the chain.

        Returns:
            Any: The value associated with the chain of keys.
        """
        return self[':'.join(iterable)]

    def chain_del(self, iterable: List[str]) -> None:
        """
        Delete a value from the RedisDict using a chain of keys.

        Args:
            iterable (List[str]): A list of keys representing the chain.
        """
        return self.__delitem__(':'.join(iterable))

    @contextmanager
    def expire_at(self, sec_epoch: int | timedelta) -> Iterator[None]:
        """
        Context manager to set the expiration time for keys in the RedisDict.

        Args:
            sec_epoch (int, timedelta): The expiration duration is set using either an integer or a timedelta.

        Returns:
            ContextManager: A context manager during which the expiration time is the time set.
        """
        self.expire, temp = sec_epoch, self.expire
        yield
        self.expire = temp

    @contextmanager
    def pipeline(self) -> Iterator[None]:
        """
        Context manager to create a Redis pipeline for batch operations.

        Returns:
            ContextManager: A context manager to create a Redis pipeline batching all operations within the context.
        """
        top_level = False
        if self.temp_redis is None:
            self.redis, self.temp_redis, top_level = self.redis.pipeline(), self.redis, True
        try:
            yield
        finally:
            if top_level:
                _, self.temp_redis, self.redis = self.redis.execute(), None, self.temp_redis  # type: ignore

    def multi_get(self, key: str) -> List[Any]:
        """
        Get multiple values from the RedisDict using a shared key prefix.

        Args:
            key (str): The shared key prefix.

        Returns:
            List[Any]: A list of values associated with the key prefix.
        """
        found_keys = list(self._scan_keys(key))
        if len(found_keys) == 0:
            return []
        return [self._transform(i) for i in self.redis.mget(found_keys) if i is not None]

    def multi_chain_get(self, keys: List[str]) -> List[Any]:
        """
        Get multiple values from the RedisDict using a chain of keys.

        Args:
            keys (List[str]): A list of keys representing the chain.

        Returns:
            List[Any]: A list of values associated with the chain of keys.
        """
        return self.multi_get(':'.join(keys))

    def multi_dict(self, key: str) -> Dict[str, Any]:
        """
        Get a dictionary of key-value pairs from the RedisDict using a shared key prefix.

        Args:
            key (str): The shared key prefix.

        Returns:
            Dict[str, Any]: A dictionary of key-value pairs associated with the key prefix.
        """
        keys = list(self._scan_keys(key))
        if len(keys) == 0:
            return {}
        to_rm = keys[0].rfind(':') + 1
        return dict(zip([i[to_rm:] for i in keys], (self._transform(i) for i in self.redis.mget(keys) if i is not None)))

    def multi_del(self, key: str) -> int:
        """
        Delete multiple values from the RedisDict using a shared key prefix.

        Args:
            key (str): The shared key prefix.

        Returns:
            int: The number of keys deleted.
        """
        keys = list(self._scan_keys(key))
        if len(keys) == 0:
            return 0
        return self.redis.delete(*keys)

    def get_redis_info(self) -> Dict[str, Any]:
        """
        Retrieve information and statistics about the Redis server.

        Returns:
            dict: The information and statistics from the Redis server in a dictionary.
        """
        return dict(self.redis.info())

    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get the Time To Live (TTL) in seconds for a given key. If the key does not exist or does not have an
        associated expire, return None.

        Args:
            key (str): The key for which to get the TTL.

        Returns:
            Optional[int]: The TTL in seconds if the key exists and has an expire set; otherwise, None.
        """
        val = self.redis.ttl(self._format_key(key))
        if val < 0:
            return None
        return val
