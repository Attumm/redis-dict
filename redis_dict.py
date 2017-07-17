from redis import StrictRedis
from future.utils import python_2_unicode_compatible


@python_2_unicode_compatible
class RedisDict(object):
    def __init__(self, *args, **kwargs):
        self.namespace = ''
        if 'namespace' in kwargs:
            # Todo validate namespace
            self.namespace = kwargs['namespace'] + ':'
            del kwargs['namespace']

        self.redis = StrictRedis(*args, decode_responses=True, **kwargs)
        self.sentinel_none = "<META __None__ 9cab>"

    def _raw_get_item(self, k):
        return self.redis.get(k)

    def _get_item(self, k):
        result = self._raw_get_item(self.namespace + k)
        return result

    def __getitem__(self, k):
        result = self._get_item(k)
        if result is None:
            raise KeyError

        return result if result != self.sentinel_none else None

    def __setitem__(self, k, v):
        if v is None:
            v = self.none_
        self.redis.set(self.namespace + k, v)

    def __delitem__(self, k):
        self.redis.delete(self.namespace + k)

    def __contains__(self, k):
        return self._get_item(k) is not None

    def __repr__(self):
        return str(self.to_dict())

    def __str__(self):
        return self.__repr__()

    def keys(self):
        return self.redis.keys(self.namespace + '*')

    def to_dict(self):
        to_rm = len(self.namespace)
        return {item[to_rm:]: self._raw_get_item(item) for item in self.keys()}

    def chain_set(self, iterable, v):
        self[':'.join(iterable)] = v

    def chain_get(self, iterable):
        return self._get_item(':'.join(iterable))

    def chain_del(self, iterable):
        return self.__delitem__(':'.join(iterable))

    def __iter__(self):
        """This contains a racecondition"""
        self.keys_iter = self.keys()
        self.keys_counter = -1
        self.keys_iter_stop = len(self.keys_iter)
        return self

    def __next__(self):
        """This contains a racecondition"""
        self.keys_counter +=1
        if self.keys_counter < self.keys_iter_stop:
            return self.keys_iter[self.keys_counter]
        else:
            del self.keys_iter
            raise StopIteration


class RedisListIterator(object):

    def __init__(self, redis_instance, key, start=0, end=-1):
        """Creates a redis list iterator.

        Args:
            redis_instance (object): instance of redis
            key (str): redis list key
            start (int): list slice start (inclusive)
            end (int): list slice end (exclusive)

        """
        self.position = start
        self.key = key
        self.redis = redis_instance
        llen = redis_instance.llen(key)
        self.endpos = llen if (end == -1 or (end - start) > llen) else end

    def __iter__(self):
        return self

    def __next__(self):
        if self.position >= self.endpos:
            raise StopIteration

        item = self.redis.lindex(self.key, self.position)
        self.position += 1
        return item

    next = __next__


class RedisList(object):
    """Emulate a python list."""

    def __init__(self, redis_instance, key):
        self.key = key
        self.redis = redis_instance

    def __len__(self):
        return self.redis.llen(self.key)

    def __getitem__(self, index):
        if isinstance(index, slice):
            start = index.start or 0
            end = (index.stop - 1) if index.stop is not None else -1
            return self.redis.lrange(self.key, start, end)
        if index + 1 > len(self):
            raise IndexError("Index out of bounds.")
        return self.redis.lindex(self.key, index)

    def __iter__(self):
        return RedisListIterator(self.redis, self.key)

if __name__ == '__main__':
    d = RedisDict(namespace='app_name')
    assert 'random' not in d
    d['random'] = 4
    assert d['random'] == '4'
    assert 'random' in d
    del d['random']
    assert 'random' not in d
    deep = ['key', 'key1', 'key2']
    deep_val = 'mister'
    d.chain_set(deep, deep_val)

    assert deep_val == d.chain_get(deep)
    d.chain_del(deep)

    assert 'random' not in d
    d['random'] = 4
    dd = RedisDict(namespace='app_name_too')
    dd['random'] = 5

    assert d['random'] == '4'
    assert 'random' in d

    assert dd['random'] == '5'
    assert 'random' in dd

    del d['random']
    assert 'random' not in d

    assert dd['random'] == '5'
    assert 'random' in dd

    del dd['random']
    assert 'random' not in dd

    print('all is well')
