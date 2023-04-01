# Redis-dict
[![Build Status](https://travis-ci.com/Attumm/redis-dict.svg?branch=main)](https://travis-ci.com/Attumm/redis-dict)
[![Downloads](https://pepy.tech/badge/redis-dict)](https://pepy.tech/project/redis-dict)

RedisDict is a Python library that provides a convenient and familiar interface for interacting with Redis as if it were a Python dictionary. This simple yet powerful library enables you to manage key-value pairs in Redis using native Python syntax. It supports various data types, including strings, integers, floats, booleans, lists, and dictionaries, and includes additional utility functions for more complex use cases.

By leveraging Redis for efficient key-value storage, RedisDict allows for high-performance data management and is particularly useful for handling large datasets that may exceed local memory capacity.


## Features

* Dictionary-like interface: Use familiar Python dictionary syntax to interact with Redis.
* Data Type Support: Comprehensive support for various data types, including strings, integers, floats, booleans, lists, dictionaries, sets, and tuples.
* Pipelining support: Use pipelines for batch operations to improve performance.
* Expiration support: Set expiration times for keys using context managers.
* Efficiency and Scalability: RedisDict is designed for use with large datasets and is optimized for efficiency. It retrieves only the data needed for a particular operation, ensuring efficient memory usage and fast performance.
* Namespace Management: Provides simple and efficient namespace handling to help organize and manage data in Redis, streamlining data access and manipulation.
* Distributed Computing: With its ability to seamlessly connect to other instances or servers with access to the same Redis instance, RedisDict enables easy distributed computing.
* Custom data types: Add custom types and transformations to suit your specific needs.

## Example
Redis is an exceptionally fast database when used appropriately. RedisDict leverages Redis for efficient key-value storage, enabling high-performance data management.

```python
from redis_dict import RedisDict

dic = RedisDict(namespace='bar')
dic['foo'] = 42
print(dic['foo'])  # Output: 42
print('foo' in dic)  # Output: True
dic["baz"] = "hello world"
print(dic)  # Output: {'foo': 42, 'baz': 'hello world'}
```
In Redis our example looks like this.
```
127.0.0.1:6379> KEYS "*"
1) "bar:foo"
2) "bar:baz"
127.0.0.1:6379> GET "bar:foo"
"int:42"
127.0.0.1:6379> GET "bar:baz"
"str:hello world"
```

### Namespaces
RedisDict employs namespaces by default, providing an organized and efficient way to manage data across multiple projects. By using a dedicated RedisDict instance for each project, you can easily identify which data belongs to which application when inspecting Redis directly.

This approach also minimizes the risk of key collisions between different applications, preventing hard-to-debug issues. By leveraging namespaces, RedisDict ensures a cleaner and more maintainable data management experience for developers working on multiple projects.


## Advanced Features

### Expiration

Redis provides a valuable feature that enables keys to expire. RedisDict supports this feature in the following ways:
1. Set a default expiration time when creating a RedisDict instance. In this example, the keys will have a default expiration time of 10 seconds.

```python
dic = RedisDict(namespace='app_name', expire=10)
dic['gone'] = 'in ten seconds'
```
2. Temporarily set the default expiration time within the scope using a context manager. In this example, the key 'gone' will expire after 60 seconds. The default expiration time for other keys outside the context manager remains unchanged.

```python
from redis_dict import RedisDict

dic = RedisDict(namespace='bar')

seconds = 60
with dic.expire_at(seconds):
    dic['gone'] = 'in sixty seconds'
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
from redis_dict import RedisDict

def expensive_function(x):
    time.sleep(2)
    return x * 2

cache = RedisDict(namespace="cache", expire=10)

def cached_expensive_function(x):
    if x not in cache:
        cache[x] = expensive_function(x)
    return cache[x]

start_time = time.time()
print(cached_expensive_function(5))  # Takes around 2 seconds to compute and caches the result.
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

# Get value by key
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
For more advanced examples of RedisDict, please refer to the unit-test files in the repository. All features and functionalities are thoroughly tested in [unit tests (here)](https://github.com/Attumm/redis-dict/blob/main/tests.py#L1) Or take a look at load test for batching [load test](https://github.com/Attumm/redis-dict/blob/main/load_test.py.py#L1).
The unit-tests can be as used as a starting point.

### Tests

The RedisDict library includes a comprehensive suite of tests that ensure its correctness and resilience. The test suite covers various data types, edge cases, and error handling scenarios. It also employs the Hypothesis library for property-based testing, which provides fuzz testing to evaluate the implementation

## Installation
```sh
pip install redis-dict
```

### Note
* Please be aware that this project is currently being utilized by various organizations in their production environments. If you have any questions or concerns, feel free to raise issues
* This project only uses redis as dependency

