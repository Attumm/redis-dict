# Redis-dict
[![Build Status](https://travis-ci.com/Attumm/redis-dict.svg?branch=main)](https://travis-ci.com/Attumm/redis-dict)
[![Downloads](https://pepy.tech/badge/redis-dict)](https://pepy.tech/project/redis-dict)

RedisDict is a Python library that allows you to interact with Redis as if it were a Python dictionary. It provides a simple, convenient, and user-friendly interface for managing key-value pairs in Redis. The library is designed to work seamlessly with different data types such as strings, integers, floats, booleans, None, lists, and dictionaries. It also offers additional utility functions and features for more complex use cases.

RedisDict was developed to address the challenges associated with handling extremely large datasets, which often exceed the capacity of local memory. This package offers a powerful and efficient solution for managing vast amounts of data by leveraging the capabilities of Redis and providing a familiar Python dictionary-like interface for seamless integration into your projects.


RedisDict stores data in Redis using key-value pairs, adhering to [Redis best practices](https://redislabs.com/redis-best-practices/data-storage-patterns/) for data storage patterns. This design not only ensures optimal performance and reliability but also enables interoperability with non-Python programs, granting them seamless access to the data stored in Redis.

## Example
Redis is an exceptionally fast database when used appropriately. RedisDict leverages Redis for efficient key-value storage, enabling high-performance data management.

```python
    >>> from redis_dict import RedisDict
    >>> dic = RedisDict(namespace='bar')
    >>> 'foo' in dic
    False
    >>> dic['foo'] = 42
    >>> dic['foo']
    42
    >>> 'foo' in dic
    True
    >>> dic["baz"] = "a string"
    >>> print(dic)
    {'foo': 42, 'baz': 'a string'}

```
In Redis our example looks like this.
```
127.0.0.1:6379> KEYS "*"
1) "bar:foo"
2) "bar:baz"
```

## Features

* Dictionary-like interface: Use familiar Python dictionary syntax to interact with Redis.
* Data Type Support: Comprehensive support for various data types, including strings, integers, floats, booleans, lists, dictionaries, sets, and tuples.
* Pipelining support: Use pipelines for batch operations to improve performance.
* Expiration support: Set expiration times for keys using context managers.
* Efficiency and Scalability: RedisDict is designed for use with large datasets and is optimized for efficiency. It retrieves only the data needed for a particular operation, ensuring efficient memory usage and fast performance.
* Namespace Management: Provides simple and efficient namespace handling to help organize and manage data in Redis, streamlining data access and manipulation.
* Distributed Computing: With its ability to seamlessly connect to other instances or servers with access to the same Redis instance, RedisDict enables easy distributed computing.
* Multi-get and multi-delete: Perform batch operations for getting and deleting multiple keys at once.
* Custom data types: Add custom types and transformations to suit your specific needs.

#### Caveats and Experimental Support

Please note that the following data types have experimental support in RedisDict:
* List
* Tuple
* Set
* Dictionary

These data types are supported through JSON serialization, which means that if your lists or dictionaries can be serialized using JSON, this feature should work as expected. However, this may not be the optimal solution for all use cases. As such, use these features at your discretion and consider potential limitations.

If you encounter a need for additional support or improvements for these or other reference types, please feel free to open an issue on the GitHub repository. Your feedback and contributions are greatly appreciated.

### Distributed computing 
You can use RedisDict for distributed computing by starting multiple RedisDict instances on different servers or instances that have access to the same Redis instance:
```python
# On server 1
r = RedisDict(namespace="example", **redis_config)
r["foo"] = "bar"


# On server 2
r1 = RedisDict(namespace="example", **redis_config)
print(r1["foo"])
"bar"

```

## Advance features examples

#### Expiration 

Redis provides a valuable feature that enables keys to expire. RedisDict supports this feature in the following ways:
1. Set a default expiration time when creating a RedisDict instance:
```python
r_dic = RedisDict(namespace='app_name', expire=10)
```
In this example, the keys will have a default expiration time of 10 seconds.

2. Temporarily set the default expiration time within the scope using a context manager:
```python
seconds = 60
with r_dic.expire_at(seconds):
    r_dic['gone_in_sixty_seconds'] = 'foo'
```
In this example, the key 'gone_in_sixty_seconds' will expire after 60 seconds. The default expiration time for other keys outside the context manager remains unchanged.

Please note that the default expiration time is set to None, which indicates that the keys will not expire unless explicitly specified.

#### Batching
Efficiently batch your requests using the Pipeline feature, which can be easily utilized with a context manager.

For example, let's store the first ten items of the Fibonacci sequence using a single round trip to Redis:
[example](https://github.com/Attumm/redis-dict/blob/main/assert_test.py#L1) larger script using pipelining with batching

```python
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = (a+b), a

with r_dic.pipeline():
    for index, item in enumerate(fib(10)):
        r_dic[str(index)] = item
```

By employing the pipeline context manager, you can reduce network overhead and improve the performance of your application when executing multiple Redis operations in a single batch.

### Namespaces
RedisDict employs namespaces by default, providing an organized and efficient way to manage data across multiple projects. By using a dedicated RedisDict instance for each project, you can easily identify which data belongs to which application when inspecting Redis directly.

This approach also minimizes the risk of key collisions between different applications, preventing hard-to-debug issues. By leveraging namespaces, RedisDict ensures a cleaner and more maintainable data management experience for developers working on multiple projects.

### Additional Examples
For more advanced examples of RedisDict, please refer to the test files in the repository. All features and functionalities are thoroughly tested in either[ `assert_test.py` (here)](https://github.com/Attumm/redis-dict/blob/main/assert_test.py#L1) or in the [unit tests (here)](https://github.com/Attumm/redis-dict/blob/main/tests.py#L1). 
The test can be used as starting point for new projects

### Tests

The RedisDict library includes a comprehensive suite of tests that ensure its correctness and resilience. The test suite covers various data types, edge cases, and error handling scenarios. It also employs the Hypothesis library for property-based testing, which provides fuzz testing to evaluate the implementation

## Installation
```sh
pip install redis-dict
```

### Note
Please be aware that this project is currently being utilized by various organizations in their production environments. If you have any questions or concerns, feel free to raise issues



### Note This project only uses redis as dependency 
