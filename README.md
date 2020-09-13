### Redis Dict

# Redis Dict
[![Build Status](https://travis-ci.org/Attumm/redis-dict.svg?branch=v2)](https://travis-ci.org/Attumm/redis-dict)

Dictionary with Redis as storage backend.
Redis is a great database for simple to complex distributed environments.
Redis-dict tries to make using Redis as simple as using a dictionary.
redis-dict stores data in redis with key values, this is according to Redis best practices.
This also allows other non-python programs to access the data stored in redis.


## Features

#### Dictionary
redis-dict can be used in drop in replacement of a normal dictionary as long no referenced datascructed are used.
i.e no nested layout
e.g values such list, instance and other dictionaries.
When used with supported types in can be used a drop in for a normal dictionary.

Redis-dict has all the methods of a normal dictionary and the same behavior.

#### Types
Those types can be saved and retrieved as the same type.
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
2. with context manager you can temporarily set the expiration of a key.
```python
seconds = 60
with r_dic.expire_at(seconds):
    r_dic['gone_in_sixty_seconds'] = 'foo'
```

#### Batching
Batch you requests by using Pipeline, as easy as using context manager 

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
redis-dict namespaces per default, this to have redis-dict per project, that won't is separated in redis
This has some advantages such as knowing to which data belongs to which app.
Making sure that apps don't collide with keys. Causing very difficult to debug issues.

## Examples
Some simple examples, For more examples look into the assert_test.py file or the unit test files they show all the functionality unit test by unit test.
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
This project is used in different companies in production.
