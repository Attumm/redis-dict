# redis-dict
[![Build Status](https://travis-ci.com/Attumm/redis-dict.svg?branch=main)](https://travis-ci.com/Attumm/redis-dict)
[![Downloads](https://pepy.tech/badge/redis-dict/month)](https://pepy.tech/project/redis-dict)

A Python dictionary with Redis as the storage back-end.
Redis is a great database for all kinds of environments; from simple to complex.
redis-dict tries to make using Redis as simple as using a dictionary.
redis-dict stores data in Redis with key-values, this is according to [Redis best practices](https://redislabs.com/redis-best-practices/data-storage-patterns/).
This also allows other non-Python programs to access the data stored in Redis.

redis-dict was built out of the necessity of working with incredibly large data sets.
It had to be possible to only send or receive the required data over the wire and into memory.
With redis-dict it's as simple as a dictionary.

## Example
Redis is a really fast database if used right.
redis-dict uses Redis for key-value storage.
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

#### Dictionary
redis-dict can be used as a drop-in replacement for a normal dictionary as long as no datastructures are used by reference.
i.e. no nested layout
e.g. values such list, instance and other dictionaries.
When used with supported types, it can be used a drop-in for a normal dictionary.

redis-dict has all the methods and behavior of a normal dictionary.

#### Types
Several Python types can be saved and retrieved as the same type.
As of writing, redis-dict supports the following types.
* String
* Integer
* Float
* Boolean
* None

#### Other Types not fully supported
Experimental support for the following types.
List, Dictionary supported provided with json serialization.
If your list or Dictionary can be serializate by json this feature will work.

Although is not the best solution, it could work for many usecases. So use at your discretion.
If there is need for other referenced types open issue on github.
* List
* Dictionary

#### Expire 
Redis has the great feature of expiring keys. This feature is supported.
1. You can set the default expiration when creating a redis-dict instance.
```python
r_dic = RedisDict(namespace='app_name', expire=10)
```
2. With a context manager you can temporarily set the default expiration time.
Defaults to None (does not expire)
```python
seconds = 60
with r_dic.expire_at(seconds):
    r_dic['gone_in_sixty_seconds'] = 'foo'
```

#### Batching
Batch your requests by using Pipeline, as easy as using a context manager 

Example storing the first ten items of Fibonacci, with one round trip to Redis.
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

#### Namespaces
redis-dict uses namespaces by default. This allows you to have an instance of redis-dict per project.
When looking directly at the data in Redis, this gives you the advantage of directly seeing which data belongs to which app.
This also has the advantage that it is less likely for apps to collide with keys, which is a difficult problem to debug.

### More Examples
More complex examples of redis-dict can be found in the tests. All functionality is tested in either[ `assert_test.py` (here)](https://github.com/Attumm/redis-dict/blob/master/assert_test.py#L1) or in the [unit tests (here)](https://github.com/Attumm/redis-dict/blob/master/tests.py#L1). 

## Installation
```sh
pip install redis-dict
```

### Note
This project is used by different companies in production.
