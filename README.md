# Redis Dict
[![Build Status](https://travis-ci.com/Attumm/redis-dict.svg?branch=main)](https://travis-ci.com/Attumm/redis-dict)

Dictionary with Redis as storage back-end.
Redis is a great database for all kinds of environments; from simple to complex.
redis-dict tries to make using Redis as simple as using a dictionary.
redis-dict stores data in Redis with key values, this is according to Redis best practices.
This also allows other non-python programs to access the data stored in Redis.

redis-dict was build out of the necessity of working with incredible large data sets.
It had to be possible to only send or receive data the required data over the wire and into memory.
And with redis-dict it's as simple as a dictionary.

## Example
Redis is a really fast database if used right.
redis-dict uses Redis as key value storage.
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
redis-dict can be used in drop in replacement of a normal dictionary as long no referenced datascructed are used.
i.e no nested layout
e.g values such list, instance and other dictionaries.
When used with supported types in can be used a drop in for a normal dictionary.

redis-dict has all the methods and behavior of a normal dictionary.

#### Types
Several python types can be saved and retrieved as the same type.
As of writing, redis-dict supports the following types.
* String
* Integer
* Float
* Boolean
* None

#### Expire 
Redis has the great feature of expiring keys, this feature is supported.
1. you can set default expiration when creating redis-dict instance.
```python
r_dic = RedisDict(namespace='app_name', expire=10)
```
2. With context manager you can temporary set the default expiration time you have set.
Defaults to None (do not expire)
```python
seconds = 60
with r_dic.expire_at(seconds):
    r_dic['gone_in_sixty_seconds'] = 'foo'
```

#### Batching
Batch your requests by using Pipeline, as easy as using context manager 

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

#### Namescape
Redis-dict uses name spaces by default. This allows you to have an instance of Redis-dict per project.
When looking directly at the data in Redis, this gives you the advantage of directly seeing which data belongs to which app.
This also has the advantage that it is less likely for apps to collide with keys, which is a difficult problem to debug.

### More Examples
 More complex examples of Redis-dict can be found in the tests. All functionality is tested in either[ `assert_test.py` (here)](https://github.com/Attumm/redis-dict/blob/master/assert_test.py#L1) or in the [unit tests (here)](https://github.com/Attumm/redis-dict/blob/master/tests.py#L1). 

## Installation
```sh
pip install redis-dict
```

### Note
This project is used by different companies in production.
