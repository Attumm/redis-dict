"""Redis Dict module."""
from typing import Any, Dict, Iterator, List, Tuple, Union, Optional, Type

from datetime import timedelta
from contextlib import contextmanager
from collections.abc import Mapping

from redis import StrictRedis

from redis_dict.type_management import SENTINEL, EncodeFuncType, DecodeFuncType, EncodeType, DecodeType
from redis_dict.type_management import _create_default_encode, _create_default_decode, _default_decoder
from redis_dict.type_management import encoding_registry as enc_reg
from redis_dict.type_management import decoding_registry as dec_reg


# pylint: disable=R0902, R0904
class RedisDict:
    """Python dictionary with Redis as backend.

    With support for advanced features, such as custom data types, pipelining, and key expiration.

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

    Extendable Types: You can extend RedisDict by adding or overriding encoding and decoding functions.
    This functionality enables various use cases, such as managing encrypted data in Redis,
    To implement this, simply create and register your custom encoding and decoding functions.
    By delegating serialization to redis-dict, reduce complexity and have simple code in the codebase.
    """

    encoding_registry: EncodeType = enc_reg
    decoding_registry: DecodeType = dec_reg

    def __init__(self,
                 namespace: str = 'main',
                 expire: Union[int, timedelta, None] = None,
                 preserve_expiration: Optional[bool] = False,
                 redis: "Optional[StrictRedis[Any]]" = None,
                 **redis_kwargs: Any) -> None:
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

        self.namespace: str = namespace
        self.expire: Union[int, timedelta, None] = expire
        self.preserve_expiration: Optional[bool] = preserve_expiration
        if redis:
            redis.connection_pool.connection_kwargs["decode_responses"] = True

        self.redis: StrictRedis[Any] = redis or StrictRedis(decode_responses=True, **redis_kwargs)
        self.get_redis: StrictRedis[Any] = self.redis

        self.custom_encode_method = "encode"
        self.custom_decode_method = "decode"

        self._iter: Iterator[str] = iter([])
        self._max_string_size: int = 500 * 1024 * 1024  # 500mb
        self._temp_redis: Optional[StrictRedis[Any]] = None

    def _format_key(self, key: str) -> str:
        """
        Format a key with the namespace prefix.

        Args:
            key (str): The key to be formatted.

        Returns:
            str: The formatted key with the namespace prefix.
        """
        return f'{self.namespace}:{str(key)}'

    def _valid_input(self, val: Any, val_type: str) -> bool:
        """
        Check if the input value is valid based on the specified value type.

        This method ensures that the input value is within the acceptable constraints for the given
        value type. For example, when the value type is "str", the method checks that the string
        length does not exceed the maximum allowed size (500 MB).

        Args:
            val (Any): The input value to be validated.
            val_type (str): The type of the input value ("str", "int", "float", or "bool").

        Returns:
            bool: True if the input value is valid, False otherwise.
        """
        if val_type == "str":
            return len(val) < self._max_string_size
        return True

    def _format_value(self, key: str, value: Any) -> str:
        """Format a valid value with the type and encoded representation of the value.

        Args:
            key (str): The key of the value to be formatted.
            value (Any): The value to be encoded and formatted.

        Raises:
            ValueError: If the value or key fail validation.

        Returns:
            str: The formatted value with the type and encoded representation of the value.
        """
        store_type, key = type(value).__name__, str(key)
        if not self._valid_input(value, store_type) or not self._valid_input(key, "str"):
            raise ValueError("Invalid input value or key size exceeded the maximum limit.")
        encoded_value = self.encoding_registry.get(store_type, lambda x: x)(value)  # type: ignore

        return f'{store_type}:{encoded_value}'

    def _store(self, key: str, value: Any) -> None:
        """
        Store a value in Redis with the given key.

        Args:
            key (str): The key to store the value.
            value (Any): The value to be stored.

        Note: Validity checks could be refactored to allow for custom exceptions that inherit from ValueError,
        providing detailed information about why a specific validation failed.
        This would enable users to specify which validity checks should be executed, add custom validity functions,
        and choose whether to fail on validation errors, or drop the data and only issue a warning and continue.
        Example use case is caching, to cache data only when it's between min and max sizes.
        Allowing for simple dict set operation, but only cache data that makes sense.

        """
        formatted_key = self._format_key(key)
        formatted_value = self._format_value(key, value)
        if self.preserve_expiration and self.redis.exists(formatted_key):
            self.redis.set(formatted_key, formatted_value, keepttl=True)
        else:
            self.redis.set(formatted_key, formatted_value, ex=self.expire)

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
        return True, self._transform(result)

    def _transform(self, result: str) -> Any:
        """
        Transform the result string from Redis into the appropriate Python object.

        Args:
            result (str): The result string from Redis.

        Returns:
            Any: The transformed Python object.
        """
        type_, value = result.split(':', 1)
        return self.decoding_registry.get(type_, _default_decoder)(value)

    def new_type_compliance(
            self,
            class_type: type,
            encode_method_name: Optional[str] = None,
            decode_method_name: Optional[str] = None,
    ) -> None:
        """Check if a class complies with the required encoding and decoding methods.

        Args:
            class_type (type): The class to check for compliance.
            encode_method_name (str, optional): Name of encoding method of the class for redis-dict custom types.
            decode_method_name (str, optional): Name of decoding method of the class for redis-dict custom types.

        Raises:
            NotImplementedError: If the class does not implement the required methods when the respective check is True.
        """
        if encode_method_name is not None:
            if not (hasattr(class_type, encode_method_name) and callable(
                    getattr(class_type, encode_method_name))):
                raise NotImplementedError(
                    f"Class {class_type.__name__} does not implement the required {encode_method_name} method.")

        if decode_method_name is not None:
            if not (hasattr(class_type, decode_method_name) and callable(
                    getattr(class_type, decode_method_name))):
                raise NotImplementedError(
                    f"Class {class_type.__name__} does not implement the required {decode_method_name} class method.")

    # pylint: disable=too-many-arguments
    def extends_type(
            self,
            class_type: type,
            encode: Optional[EncodeFuncType] = None,
            decode: Optional[DecodeFuncType] = None,
            encoding_method_name: Optional[str] = None,
            decoding_method_name: Optional[str] = None,
    ) -> None:
        """
        Extend RedisDict to support a custom type in the encode/decode mapping.

        This method enables serialization of instances based on their type,
        allowing for custom types, specialized storage formats, and more.
        There are three ways to add custom types:
        1. Have a class with an `encode` instance method and a `decode` class method.
        2. Have a class and pass encoding and decoding functions, where
        `encode` converts the class instance to a string, and
        `decode` takes the string and recreates the class instance.
        3. Have a class that already has serialization methods, that satisfies the:
        EncodeFuncType = Callable[[Any], str]
        DecodeFuncType = Callable[[str], Any]

        `custom_encode_method`
        `custom_decode_method`

        If no encoding or decoding function is provided, default to use the `encode` and `decode` methods of the class.

        The `encode` method should be an instance method that converts the object to a string.
        The `decode` method should be a class method that takes a string and returns an instance of the class.

        The method names for encoding and decoding can be changed by modifying the
        - `custom_encode_method`
        - `custom_decode_method`
        attributes of the RedisDict instance

        Example:
            >>> class Person:
            ...     def __init__(self, name, age):
            ...         self.name = name
            ...         self.age = age
            ...
            ...     def encode(self) -> str:
            ...         return json.dumps(self.__dict__)
            ...
            ...     @classmethod
            ...     def decode(cls, encoded_str: str) -> 'Person':
            ...         return cls(**json.loads(encoded_str))
            ...
            >>> redis_dict.extends_type(Person)

        Args:
            class_type (type): The class `__name__` will become the key for the encoding and decoding functions.
            encode (Optional[EncodeFuncType]): function that encodes an object into a storable string format.
            decode (Optional[DecodeFuncType]): function that decodes a string back into an object of `class_type`.
            encoding_method_name (str, optional): Name of encoding method of the class for redis-dict custom types.
            decoding_method_name (str, optional): Name of decoding method of the class for redis-dict custom types.

        Raises:
            NotImplementedError

        Note:
            You can check for compliance of a class separately using the `new_type_compliance` method:

            This method raises a NotImplementedError if either `encode` or `decode` is `None`
            and the class does not implement the corresponding method.
        """

        if encode is None or decode is None:
            encode_method_name = encoding_method_name or self.custom_encode_method
            if encode is None:
                self.new_type_compliance(class_type, encode_method_name=encode_method_name)
                encode = _create_default_encode(encode_method_name)

            if decode is None:
                decode_method_name = decoding_method_name or self.custom_decode_method
                self.new_type_compliance(class_type, decode_method_name=decode_method_name)
                decode = _create_default_decode(class_type, decode_method_name)

        type_name = class_type.__name__
        self.decoding_registry[type_name] = decode
        self.encoding_registry[type_name] = encode

    def __eq__(self, other: Any) -> bool:
        """
        Compare the current RedisDict with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if equal, False otherwise
        """
        if len(self) != len(other):
            return False
        for key, value in self.items():
            if value != other.get(key, SENTINEL):
                return False
        return True

    def __ne__(self, other: Any) -> bool:
        """
        Compare the current RedisDict with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: False if equal, True otherwise
        """
        return not self.__eq__(other)

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
        self._iter = self.keys()
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

    def __or__(self, other: Dict[str, Any]) -> Dict[str, Any]:
        """Implement the | operator (dict union).

        Returns a new dictionary with items from both dictionaries.

        Args:
            other (Dict[str, Any]): The dictionary to merge with.

        Raises:
            TypeError: If other does not adhere to Mapping.

        Returns:
            Dict[str, Any]: A new dictionary containing items from both dictionaries.
        """
        if not isinstance(other, Mapping):
            raise TypeError(f"unsupported operand type(s) for |: '{type(other).__name__}' and 'RedisDict'")

        result = {}
        result.update(self.to_dict())
        result.update(other)
        return result

    def __ror__(self, other: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implement the reverse | operator.

        Called when RedisDict is on the right side of |.

        Args:
            other (Dict[str, Any]): The dictionary to merge with.

        Raises:
            TypeError: If other does not adhere to Mapping.

        Returns:
            Dict[str, Any]: A new dictionary containing items from both dictionaries.
        """
        if not isinstance(other, Mapping):
            raise TypeError(f"unsupported operand type(s) for |: 'RedisDict' and '{type(other).__name__}'")

        result = {}
        result.update(other)
        result.update(self.to_dict())
        return result

    def __ior__(self, other: Dict[str, Any]) -> 'RedisDict':
        """
        Implement the |= operator (in-place union).

        Modifies the current dictionary by adding items from other.

        Args:
            other (Dict[str, Any]): The dictionary to merge with.

        Raises:
            TypeError: If other does not adhere to Mapping.

        Returns:
            RedisDict: The modified RedisDict instance.
        """
        if not isinstance(other, Mapping):
            raise TypeError(f"unsupported operand type(s) for |: '{type(other).__name__}' and 'RedisDict'")

        self.update(other)
        return self

    @classmethod
    def __class_getitem__(cls: Type['RedisDict'], key: Any) -> Type['RedisDict']:
        """
        Enable type hinting support like RedisDict[str, Any].

        Args:
            key (Any): The type parameter(s) used in the type hint.

        Returns:
            Type[RedisDict]: The class itself, enabling type hint usage.
        """
        return cls

    def __reversed__(self) -> Iterator[str]:
        """
        Implement reversed() built-in.

        Returns an iterator over dictionary keys in reverse insertion order.

        Warning:
            RedisDict Currently does not support 'insertion order' as property thus also not reversed.

        Returns:
            Iterator[str]: An iterator yielding the dictionary keys in reverse order.
        """
        return reversed(list(self.keys()))

    def __next__(self) -> str:
        """
        Get the next item in the iterator.

        Returns:
            str: The next item in the iterator.
        """
        return next(self._iter)

    def next(self) -> str:
        """
        Get the next item in the iterator (alias for __next__).

        Returns:
            str: The next item in the iterator.

        """
        return next(self)

    def _create_iter_query(self, search_term: str) -> str:
        """
        Create a Redis query string for iterating over keys based on the given search term.

        This method constructs a query by prefixing the search term with the namespace
        followed by a wildcard to facilitate scanning for keys that start with the
        provided search term.

        Args:
            search_term (str): The term to search for in Redis keys.

        Returns:
            str: A formatted query string that can be used to find keys in Redis.

        Example:
            >>> d = RedisDict(namespace='foo')
            >>> query = self._create_iter_query('bar')
            >>> print(query)
            'foo:bar*'
        """
        return f'{self.namespace}:{search_term}*'

    def _scan_keys(self, search_term: str = '') -> Iterator[str]:
        """
        Scan for Redis keys matching the given search term.

        Args:
            search_term (str): A search term to filter keys. Defaults to ''.

        Returns:
            Iterator[str]: An iterator of matching Redis keys.
        """
        search_query = self._create_iter_query(search_term)
        return self.get_redis.scan_iter(match=search_query)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Return the value for the given key if it exists, otherwise return the default value.

        Analogous to a dictionary's get method.

        Args:
            key (str): The key to retrieve the value.
            default (Optional[Any], optional): The value to return if the key is not found.

        Returns:
            Any: The value associated with the key or the default value.
        """
        found, item = self._load(key)
        if not found:
            return default
        return item

    def keys(self) -> Iterator[str]:
        """Return an Iterator of keys in the RedisDict, analogous to a dictionary's keys method.

        Returns:
            Iterator[str]: A list of keys in the RedisDict.
        """
        to_rm = len(self.namespace) + 1
        return (str(item[to_rm:]) for item in self._scan_keys())

    def key(self, search_term: str = '') -> Optional[str]:
        """Return the first value for search_term if it exists, otherwise return None.

        Args:
            search_term (str): A search term to filter keys. Defaults to ''.

        Returns:
            str: The first key associated with the given search term.
        """
        to_rm = len(self.namespace) + 1
        search_query = self._create_iter_query(search_term)
        _, data = self.get_redis.scan(match=search_query, count=1)
        for item in data:
            return str(item[to_rm:])

        return None

    def items(self) -> Iterator[Tuple[str, Any]]:
        """Return a list of key-value pairs (tuples) in the RedisDict, analogous to a dictionary's items method.

        Yields:
            Iterator[Tuple[str, Any]]: A list of key-value pairs in the RedisDict.
        """
        to_rm = len(self.namespace) + 1
        for item in self._scan_keys():
            try:
                yield str(item[to_rm:]), self[item[to_rm:]]
            except KeyError:
                pass

    def values(self) -> Iterator[Any]:
        """Analogous to a dictionary's values method.

        Return a list of values in the RedisDict,

        Yields:
            List[Any]: A list of values in the RedisDict.
        """
        to_rm = len(self.namespace) + 1
        for item in self._scan_keys():
            try:
                yield self[item[to_rm:]]
            except KeyError:
                pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert the RedisDict to a Python dictionary.

        Returns:
            Dict[str, Any]: A dictionary with the same key-value pairs as the RedisDict.
        """
        return dict(self.items())

    def clear(self) -> None:
        """Remove all key-value pairs from the RedisDict in one batch operation using pipelining.

        This method mimics the behavior of the `clear` method from a standard Python dictionary.
        Redis pipelining is employed to group multiple commands into a single request, minimizing
        network round-trip time, latency, and I/O load, thereby enhancing the overall performance.

        It is important to highlight that the clear method can be safely executed within
        the context of an initiated pipeline operation.
        """
        with self.pipeline():
            for key in self:
                del self[key]

    def pop(self, key: str, default: Union[Any, object] = SENTINEL) -> Any:
        """Analogous to a dictionary's pop method.

        Remove the value associated with the given key and return it, or return the default value
        if the key is not found.

        Args:
            key (str): The key to remove the value.
            default (Optional[Any], optional): The value to return if the key is not found.

        Returns:
            Any: The value associated with the key or the default value.

        Raises:
            KeyError: If the key is not found and no default value is provided.
        """
        formatted_key = self._format_key(key)
        value = self.get_redis.execute_command("GETDEL", formatted_key)
        if value is None:
            if default is not SENTINEL:
                return default
            raise KeyError(formatted_key)

        return self._transform(value)

    def popitem(self) -> Tuple[str, Any]:
        """Remove and return a random (key, value) pair from the RedisDict as a tuple.

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
        formatted_value = self._format_value(key, default_value)

        # Setting {"get": True} enables parsing of the redis result as "GET", instead of "SET" command
        options = {"get": True}
        args = ["SET", formatted_key, formatted_value, "NX", "GET"]
        if self.preserve_expiration:
            args.append("KEEPTTL")
        elif self.expire is not None:
            expire_val = int(self.expire.total_seconds()) if isinstance(self.expire, timedelta) else self.expire
            expire_str = str(1) if expire_val <= 1 else str(expire_val)
            args.extend(["EX", expire_str])

        result = self.get_redis.execute_command(*args, **options)
        if result is None:
            return default_value

        return self._transform(result)

    def copy(self) -> Dict[str, Any]:
        """Create a shallow copy of the RedisDict and return it as a standard Python dictionary.

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
            dic (Mapping[str, Any]): A mapping containing key-value pairs to update the RedisDict.
        """
        with self.pipeline():
            for key, value in dic.items():
                self[key] = value

    def fromkeys(self, iterable: List[str], value: Optional[Any] = None) -> 'RedisDict':
        """Create a new RedisDict from an iterable of key-value pairs.

        Create a new RedisDict with keys from the provided iterable and values set to the given value.
        This method is analogous to the `fromkeys` method of a standard Python dictionary, populating
        the RedisDict with the keys from the iterable and setting their corresponding values to the
        specified value.


        Args:
            iterable (List[str]): An iterable containing the keys to be added to the RedisDict.
            value (Optional[Any], optional): The value to be assigned to each key in the RedisDict. Defaults to None.

        Returns:
            RedisDict: The current RedisDict instance,populated with the keys from the iterable and their
            corresponding values.
        """
        for key in iterable:
            self[key] = value
        return self

    def __sizeof__(self) -> int:
        """Return the approximate size of the RedisDict in memory, in bytes.

        This method is analogous to the `__sizeof__` method of a standard Python dictionary, estimating
        the memory consumption of the RedisDict based on the serialized in-memory representation.
        Should be changed to redis view of the size.

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
        del self[':'.join(iterable)]

    #  def expire_at(self, sec_epoch: int | timedelta) -> Iterator[None]:
    #  compatibility with Python 3.9 typing
    @contextmanager
    def expire_at(self, sec_epoch: Union[int, timedelta]) -> Iterator[None]:
        """Context manager to set the expiration time for keys in the RedisDict.

        Args:
            sec_epoch (int, timedelta): The expiration duration is set using either an integer or a timedelta.

        Yields:
            ContextManager: A context manager during which the expiration time is the time set.
        """
        self.expire, temp = sec_epoch, self.expire
        yield
        self.expire = temp

    @contextmanager
    def pipeline(self) -> Iterator[None]:
        """
        Context manager to create a Redis pipeline for batch operations.

        Yields:
            ContextManager: A context manager to create a Redis pipeline batching all operations within the context.
        """
        top_level = False
        if self._temp_redis is None:
            self.redis, self._temp_redis, top_level = self.redis.pipeline(), self.redis, True
        try:
            yield
        finally:
            if top_level:
                _, self._temp_redis, self.redis = self.redis.execute(), None, self._temp_redis  # type: ignore

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
        return dict(
            zip([i[to_rm:] for i in keys], (self._transform(i) for i in self.redis.mget(keys) if i is not None))
        )

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
        """Get the Time To Live from Redis.

        Get the Time To Live (TTL) in seconds for a given key. If the key does not exist or does not have an
        associated `expire`, return None.

        Args:
            key (str): The key for which to get the TTL.

        Returns:
            Optional[int]: The TTL in seconds if the key exists and has an expiry set; otherwise, None.
        """
        val = self.redis.ttl(self._format_key(key))
        if val < 0:
            return None
        return val
