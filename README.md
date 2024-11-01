# Redis-dict
[![PyPI](https://img.shields.io/pypi/v/redis-dict.svg)](https://pypi.org/project/redis-dict/)
[![CI](https://github.com/Attumm/redis-dict/actions/workflows/ci.yml/badge.svg)](https://github.com/Attumm/redis-dict/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Attumm/redis-dict/graph/badge.svg?token=Lqs7McQGEs)](https://codecov.io/gh/Attumm/redis-dict)
[![Downloads](https://static.pepy.tech/badge/redis-dict/month)](https://pepy.tech/project/redis-dict)

RedisDict is a Python library that offers a convenient and familiar interface for interacting with Redis, treating it as if it were a Python dictionary. Its goal is to help developers write clean, Pythonic code while using Redis as a storage solution for seamless distributed computing. This simple yet powerful library utilizes Redis as a key-value store and supports various data types, including strings, integers, floats, booleans, lists, and dictionaries. Additionally, developers can extend RedisDict to work with custom objects.

The library includes utility functions for more complex use cases such as caching, batching, and more. By leveraging Redis for efficient key-value storage, RedisDict enables high-performance data management, maintaining efficiency even with large datasets and Redis instances.

## Features

* Dictionary-like interface: Use familiar Python dictionary syntax to interact with Redis.
* Data Type Support: Comprehensive support for various data types.
* Pipelining support: Use pipelines for batch operations to improve performance.
* Expiration Support: Enables the setting of expiration times either globally or individually per key, through the use of context managers.
* Efficiency and Scalability: RedisDict is designed for use with large datasets and is optimized for efficiency. It retrieves only the data needed for a particular operation, ensuring efficient memory usage and fast performance.
* Namespace Management: Provides simple and efficient namespace handling to help organize and manage data in Redis, streamlining data access and manipulation.
* Distributed Computing: With its ability to seamlessly connect to other instances or servers with access to the same Redis instance, RedisDict enables easy distributed computing.
* Custom data: types: Add custom types encoding/decoding to store your data types.
* Encryption: allows for storing data encrypted, while retaining the simple dictionary interface.

## Example
Redis is an exceptionally fast database when used appropriately. RedisDict leverages Redis for efficient key-value storage, enabling high-performance data management.

```bash
pip install redis-dict
```

```python
>>> from redis_dict import RedisDict
>>> dic = RedisDict()
>>> dic['foo'] = 42
>>> dic['foo']
42
>>> 'foo' in dic
True
>>> dic["baz"] = "hello world"
>>> dic
{'foo': 42, 'baz': 'hello world'}
```
In Redis our example looks like this.
```
127.0.0.1:6379> KEYS "*"
1) "main:foo"
2) "main:baz"
127.0.0.1:6379> GET "main:foo"
"int:42"
127.0.0.1:6379> GET "main:baz"
"str:hello world"
```


### Namespaces
Acting as an identifier for your dictionary across different systems, RedisDict employs namespaces for organized data management. When a namespace isn't specified, "main" becomes the default. Thus allowing for data organization across systems and projects with the same redis instance.
This approach also minimizes the risk of key collisions between different applications, preventing hard-to-debug issues. By leveraging namespaces, RedisDict ensures a cleaner and more maintainable data management experience for developers working on multiple projects.

## Advanced Features

### Expiration

Redis provides a valuable feature that enables keys to expire. RedisDict supports this feature in the following ways:
1. Set a default expiration time when creating a RedisDict instance. In this example, the keys will have a default expiration time of 10 seconds. Use seconds with an integer or pass a datetime timedelta.

```python
dic = RedisDict(expire=10)
dic['gone'] = 'in ten seconds'
```
Or, for a more Pythonic approach, use a timedelta.
```python
from datetime import timedelta

dic = RedisDict(expire=timedelta(minutes=1))
dic['gone'] = 'in a minute'
```

2. Temporarily set the default expiration time within the scope using a context manager. In this example, the key 'gone' will expire after 60 seconds. The default expiration time for other keys outside the context manager remains unchanged. Either pass an integer or a timedelta.

```python
dic = RedisDict()

seconds = 60
with dic.expire_at(seconds):
    dic['gone'] = 'in sixty seconds'
```

3. Updating keys while preserving the initial timeout In certain situations, there is a need to update the value while keeping the expiration intact. This is achievable by setting the 'preserve_expiration' to true.

```python
import time

dic = RedisDict(expire=10, preserve_expiration=True)
dic['gone'] = 'in ten seconds'

time.sleep(5)
dic['gone'] = 'gone in 5 seconds'

```

### Batching
Efficiently batch your requests using the Pipeline feature, which can be easily utilized with a context manager.

```python
dic = RedisDict(namespace="example")

# one round trip to redis
with dic.pipeline():
    for index in range(100):
        dic[str(index)] = index
```

### Distributed computing
You can use RedisDict for distributed computing by starting multiple RedisDict instances on different servers or instances that have access to the same Redis instance:
```python
# On server 1
from redis_dict import RedisDict

dic = RedisDict(namespace="example")
dic["foo"] = "bar"

# On server 2
from redis_dict import RedisDict

dic = RedisDict(namespace="example")
print(dic["foo"]) # outputs "bar"
```

## More Examples

### Caching made simple
```python
import time
from datetime import timedelta
from redis_dict import RedisDict

def expensive_function(x):
    time.sleep(x)
    return x * 2

cache = RedisDict(namespace="cache", expire=timedelta(minutes=60))

def cached_expensive_function(x):
    if x not in cache:
        cache[x] = expensive_function(x)
    return cache[x]

start_time = time.time()
print(cached_expensive_function(5))  # Takes around 5 seconds to compute and caches the result.
print(f"Time taken: {time.time() - start_time:.2f} seconds")

start_time = time.time()
print(cached_expensive_function(5))  # Fetches the result from the cache, taking almost no time.
print(f"Time taken: {time.time() - start_time:.2f} seconds")
```

### Redis-dict as dictionary
```python
from redis_dict import RedisDict

# Create a RedisDict instance with a namespace
dic = RedisDict(namespace="example")

# Set key-value pairs
dic["name"] = "John Doe"
dic["age"] = 32
dic["city"] = "Amsterdam"

# Get value by key, from any instance connected to the same redis/namespace
print(dic["name"])  # Output: John Doe

# Update value by key, got a year older
dic["age"] = 33

# Check if key exists
print("name" in dic)  # Output: True
print("country" in dic)  # Output: False

# Get value with a default value if the key doesn't exist
print(dic.get("country", "NL"))  # Output: NL

# Get the length (number of keys) of the RedisDict
print(len(dic))  # Output: 3

# Iterate over keys
for key in dic:
    print(key, dic[key])

# Delete a key-value pair
del dic["city"]

# Clear all key-value pairs in the RedisDict
dic.clear()

# Get the length (number of keys) of the RedisDict
print(len(dic))  # Output: 0

# Update RedisDict with multiple key-value pairs
dic.update({"a": 1, "b": 2, "c": 3})

# Use methods of a normal dict
print(list(dic.keys()))   # Output: ['a', 'b', 'c']
print(list(dic.values()))  # Output: [1, 2, 3]
print(list(dic.items()))  # Output: [('a', 1), ('b', 2), ('c', 3)]

# Using pop() and popitem() methods
value = dic.pop("a")
print(value)  # Output: 1

key, value = dic.popitem()
print(key, value)  # Output: 'c' 3 (example)

# Using setdefault() method
dic.setdefault("d", 4)
print(dic["d"])  # Output: 4
```

### Additional Examples
For more advanced examples of RedisDict, please refer to the unit-test files in the repository. All features and functionalities are thoroughly tested in [unit tests (here)](https://github.com/Attumm/redis-dict/blob/main/tests.py#L1) Or take a look at load test for batching [load test](https://github.com/Attumm/redis-dict/blob/main/load_test.py#L1).
The unit-tests can be as used as a starting point.

## Types

### standard types
RedisDict supports a range of Python data types, from basic types to nested structures.
Basic types are handled natively, while complex data types like lists and dictionaries, RedisDict uses JSON serialization, specifically avoiding `pickle` due to its [security vulnerabilities](https://docs.python.org/3/library/pickle.html) in distributed computing contexts.
Although the library supports nested structures, the recommended best practice is to use RedisDict as a shallow dictionary.
This approach optimizes Redis database performance and efficiency by ensuring that each set and get operation efficiently maps to Redis's key-value storage capabilities, while still preserving the library's Pythonic interface.
Following types are supported: 
`str, int, float, bool, NoneType, list, dict, tuple, set, datetime, date, time, timedelta, Decimal, complex, bytes, UUID, OrderedDict, defaultdict, frozenset`
```python
from uuid import UUID
from decimal import Decimal
from collections import OrderedDict, defaultdict
from datetime import datetime, date, time, timedelta

dic = RedisDict()

dic["string"] = "Hello World"
dic["number"] = 42
dic["float"] = 3.14
dic["bool"] = True
dic["None"] = None

dic["list"] = [1, 2, 3]
dic["dict"] = {"a": 1, "b": 2}
dic["tuple"] = (1, 2, 3)
dic["set"] = {1, 2, 3}

dic["datetime"] = datetime.date(2024, 1, 1, 12, 30, 45)
dic["date"] = date(2024, 1, 1)
dic["time"] = time(12, 30, 45)
dic["delta"] = timedelta(days=1, hours=2)

dic["decimal"] = Decimal("3.14159")
dic["complex"] = complex(1, 2)
dic["bytes"] = bytes([72, 101, 108, 108, 111])
dic["uuid"] = UUID('12345678-1234-5678-1234-567812345678')

dic["ordered"] = OrderedDict([('a', 1), ('b', 2)])
dic["default"] = defaultdict(int, {'a': 1, 'b': 2})
dic["frozen"] = frozenset([1, 2, 3])
```



### Nested types
Nested Types
RedisDict supports nested structures with mixed types through JSON serialization. The feature works by utilizing JSON encoding and decoding under the hood. While this represents an upgrade in functionality, the feature is not fully implemented and should be used with caution. For optimal performance, using shallow dictionaries is recommended.
```python
from datetime import datetime, timedelta

dic["mixed"] = [1, "foobar", 3.14, [1, 2, 3], datetime.now()]

dic['dic'] = {"elapsed_time": timedelta(hours=60)}
```

### JSON Encoding - Decoding
The nested type support in RedisDict is implemented using custom JSON encoders and decoders. These JSON encoders and decoders are built on top of RedisDict's own encoding and decoding functionality, extending it for JSON compatibility. Since JSON serialization was a frequently requested feature, these enhanced encoders and decoders are available for use in other projects:
```python
import json
from datetime import datetime
from redis_dict import RedisDictJSONDecoder, RedisDictJSONEncoder

data = [1, "foobar", 3.14, [1, 2, 3], datetime.now()]
encoded = json.dumps(data, cls=RedisDictJSONEncoder)
result = json.loads(encoded, cls=RedisDictJSONDecoder)
```


### Extending RedisDict with Custom Types

RedisDict supports custom type serialization. Here's how to add a new type:


```python
import json

class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def encode(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def decode(cls, encoded_str: str) -> 'Person':
        return cls(**json.loads(encoded_str))

redis_dict = RedisDict()

# Extend redis dict with the new type
redis_dict.extends_type(Person)

# RedisDict can now seamlessly handle Person instances.
person = Person(name="John", age=32)
redis_dict["person1"] = person

result = redis_dict["person1"]

assert result.name == person.name
assert result.age == person.age
```

For more information on [extending types](https://github.com/Attumm/redis-dict/blob/main/tests/unit/extend_types_tests.py).
### Redis Encryption
Setup guide for configuring and utilizing encrypted Redis TLS for redis-dict.
[Setup guide](https://github.com/Attumm/redis-dict/blob/main/docs/tutorials/encrypted_redis.MD)

### Redis Storage Encryption
For storing encrypted data values, it's possible to use extended types. Take a look at this [encrypted test](https://github.com/Attumm/redis-dict/blob/main/tests/unit/encrypt_tests.py).

### Tests
The RedisDict library includes a comprehensive suite of tests that ensure its correctness and resilience. The test suite covers various data types, edge cases, and error handling scenarios. It also employs the Hypothesis library for property-based testing, which provides fuzz testing to evaluate the implementation

### Redis config
To configure RedisDict using your Redis config.

Configure both the host and port. Or configuration with a setting dictionary.
```python
dic = RedisDict(host='127.0.0.1', port=6380)

redis_config = {
    'host': '127.0.0.1',
    'port': 6380,
}

confid_dic = RedisDict(**redis_config)
```

## Installation
```sh
pip install redis-dict
```

### Note
* Please be aware that this project is currently being utilized by various organizations in their production environments. If you have any questions or concerns, feel free to raise issues
* This project only uses redis as dependency
