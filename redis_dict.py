from redis import StrictRedis

from contextlib import contextmanager
from future.utils import python_2_unicode_compatible


@python_2_unicode_compatible
class RedisDict(object):
    def __init__(self, *args, **kwargs):
        self.namespace = ''
        if 'namespace' in kwargs:
            # Todo validate namespace
            self.namespace = kwargs['namespace'] + ':'
            del kwargs['namespace']

        self.expire = None
        if 'expire' in kwargs:
            self.expire = kwargs['expire']
            del kwargs['expire']

        self.redis = StrictRedis(*args, decode_responses=True, **kwargs)
        self.sentinel_none = '<META __None__ 9cab>'

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
            v = self.sentinel_none
        self.redis.set(self.namespace + k, v, ex=self.expire)

    def __delitem__(self, k):
        self.redis.delete(self.namespace + k)

    def __contains__(self, k):
        return self._get_item(k) is not None

    def __repr__(self):
        return str(self.to_dict())

    def __str__(self):
        return self.__repr__()

    def __len__(self):
        return len(self._keys())

    def _scan_keys(self, search_term=''):
        return self.redis.scan(match=self.namespace + search_term + '*')

    def _keys(self, search_term=''):
        return self._scan_keys(search_term)[1]

    def keys(self):
        to_rm = len(self.namespace)
        return [item[to_rm:] for item in self._keys()]

    def to_dict(self):
        to_rm = len(self.namespace)
        return {item[to_rm:]: self._raw_get_item(item) for item in self._keys()}

    def chain_set(self, iterable, v):
        self[':'.join(iterable)] = v

    def chain_get(self, iterable):
        return self[':'.join(iterable)]

    def chain_del(self, iterable):
        return self.__delitem__(':'.join(iterable))

    @contextmanager
    def expire_at(self, sec_epoch):
        self.expire, temp = sec_epoch, self.expire
        yield
        self.expire = temp

    def __iter__(self):
        """This contains a racecondition"""
        self.keys_iter = self.keys()
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        """This contains a racecondition"""
        try:
            return self.keys_iter.pop()
        except (IndexError, KeyError):
            raise StopIteration

    def multi_get(self, key):
        found_keys = self._keys(key)
        if len(found_keys) == 0:
            return []

        return self.redis.mget(found_keys)

    def multi_chain_get(self, keys):
        return self.multi_get(':'.join(keys))

    def multi_dict(self, key):
        keys = self._keys(key)
        if len(keys) == 0:
            return {}
        to_rm = len(self.namespace)
        return dict(zip([i[to_rm:] for i in keys], self.redis.mget(keys)))

    def multi_del(self, key):
        keys = self._keys(key)
        if len(keys) == 0:
            return 0
        return self.redis.delete(*keys)

    def items(self):
        return zip(self.keys(), self.multi_get(self._keys()))


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
    import time

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

    try:
        d.chain_get(deep)
    except KeyError:
        pass
    except Exception:
        print('failed to throw KeyError')
    else:
        print('failed to throw KeyError')

    assert 'random' not in d
    d['random'] = 4
    dd = RedisDict(namespace='app_name_too')
    assert len(dd) == 0

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

    with dd.expire_at(1):
        dd['gone_in_one_sec'] = 'gone'

    assert dd['gone_in_one_sec'] == 'gone'

    time.sleep(1.1)

    try:
        dd['gone_in_one_sec']
    except KeyError:
        pass
    except Exception:
        print('failed to throw KeyError')
    else:
        print('failed to throw KeyError')

    assert len(dd) == 0

    items = {'k1': 'v1', 'k2': 'v2', 'k3': 'v3'}
    for key, val in items.items():
        dd.chain_set(['keys', key], val)

    assert len(dd) == len(items)
    assert sorted(dd.multi_get('keys')) == sorted(list(items.values()))
    assert dd.multi_dict('keys') == items

    dd['one_item'] = 'im here'
    dd.multi_del('keys')

    assert len(dd) == 1

    del(dd['one_item'])
    assert len(dd) == 0

    print('all is well')

