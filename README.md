### Redis Dict

# Redis Dict
[![Build Status](https://travis-ci.org/Attumm/redis-dict.svg?branch=v2)](https://travis-ci.org/Attumm/redis-dict)

Dictionary with Redis as storage backend.
Redis is a great database for all kinds of environments; from simple to complex.
redis-dict tries to make using Redis as simple as using a dictionary.
redis-dict stores data in redis with key values, this is according to Redis best practices.
This also allows other non-python programs to access the data stored in redis.


## Features

#### Dictionary
redis-dict can be used in drop in replacement of a normal dictionary as long no referenced datascructed are used.
i.e no nested layout
e.g values such list, instance and other dictionaries.
When used with supported types in can be used a drop in for a normal dictionary.

redis-dict has all the methods and behaviours of a normal dictionary.

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
1. you can set default experition when creating redis-dict instance.
```python
r_dic = RedisDict(namespace='app_name', expire=10)
```
2. With context manager you can temporarly set the default expiration time you have set.
Defaults to None (do not expire)
```python
seconds = 60
with r_dic.expire_at(seconds):
    r_dic['gone_in_sixty_seconds'] = 'foo'
```

#### Batching
Batch your requests by using Pipeline, as easy as using context manager 

Example storing the first ten items of fibonacci, with one roundtrip to redis.
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
Redis-dict uses namespaces by default. This allows you to have an instance of Redis-dict per project.
When looking directly at the data in redis, this gives you the advantage of directly seeing which data belongs to which app.
This also has the advantage that it is less likely for apps to collide with keys, which is a difficult problem to debug.

## Examples
Here are some more simple examples of Redis-dict. More complex examples of Redis-dict can be found in the tests. All functionality is tested in either[ `assert_test.py` (here)](https://github.com/Attumm/redis-dict/blob/master/assert_test.py#L1) or in the un[it tests (here)](https://github.com/Attumm/redis-dict/blob/master/tests.py#L1). 
```python
    >>> from redis_dict import RedisDict
    >>> r_dic = RedisDict(namespace='app_name')
    >>> 'foo' in r_dic
    False
    >>> r_dic['foo'] = 4
    >>> r_dict['foo']
    4
    >>>
```

### Note
This project is used by different companies in production.
