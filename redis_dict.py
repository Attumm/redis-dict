import json

from redis import StrictRedis

from contextlib import contextmanager
from future.utils import python_2_unicode_compatible

SENTINEL = object()


@python_2_unicode_compatible
class RedisDict:
    trans = {
        'json': json.loads,
        type('').__name__: str,
        type(1).__name__: int,
        type(0.1).__name__: float,
        type(True).__name__: lambda x: x == "True",
        type(None).__name__: lambda x: None,
    }

    def __init__(self, **kwargs):
        self.temp_redis = None
        # Todo validate namespace
        self.namespace = kwargs.pop('namespace', '')
        self.expire = kwargs.pop('expire', None)

        self.redis = StrictRedis(decode_responses=True, **kwargs)
        self.get_redis = self.redis
        self.iter = self.iterkeys()

    def _format_key(self, key):
        return '{}:{}'.format(self.namespace, str(key))

    def _store(self, key, value, set_type=None):
        store_type = set_type if set_type is not None else type(value).__name__
        store_value = '{}:{}'.format(store_type, value)
        self.redis.set(self._format_key(key), store_value, ex=self.expire)

    def _load(self, key):
        result = self.get_redis.get(self._format_key(key))
        if result is None:
            return False, None
        t, value = result.split(':', 1)
        return True, self.trans.get(t, lambda x: x)(value)

    def _transform(self, result):
        t, value = result.split(':', 1)
        return self.trans.get(t, lambda x: x)(value)

    def add_type(self, k, v):
        self.trans[k] = v

    def __cmp__(self, other):
        if len(self) != len(other):
            return False
        for key in self:
            if self[key] != other[key]:
                return False
        return True

    def __getitem__(self, item):
        found, value = self._load(item)
        if not found:
            raise KeyError(item)
        return value

    def __setitem__(self, key, value):
        self._store(key, value)

    def __delitem__(self, key):
        self.redis.delete(self._format_key(key))

    def __contains__(self, key):
        return self._load(key)[1]

    def __len__(self):
        return len(list(self._scan_keys()))

    def __iter__(self):
        self.iter = self.iterkeys()
        return self

    def __repr__(self):
        return str(self)

    def __str__(self):
        return str(self.to_dict())

    def __next__(self):
        return next(self.iter)

    def next(self):
        return self.__next__()

    def _scan_keys(self, search_term=''):
        return self.get_redis.scan_iter(match='{}:{}{}'.format(self.namespace, search_term, '*'))

    def get(self, key, default=None):
        found, item = self._load(key)
        if not found:
            return default
        return item

    def iterkeys(self):
        """Note: for pythone2 str is needed"""
        to_rm = len(self.namespace) + 1
        return (str(item[to_rm:]) for item in self._scan_keys())

    def iter_keys(self):
        """Deprecated: should be removed after major version change"""
        print("Warning: deprecated method. use iterkeys instead")
        return self.iterkeys()

    def key(self, search_term=''):
        """Note: for pythone2 str is needed"""
        to_rm = len(self.namespace) + 1
        cursor, data = self.get_redis.scan(match='{}:{}{}'.format(self.namespace, search_term, '*'), count=1)
        for item in data:
            return str(item[to_rm:])

    def keys(self):
        return list(self.iterkeys())

    def iteritems(self):
        """Note: for pythone2 str is needed"""
        to_rm = len(self.namespace) + 1
        for item in self._scan_keys():
            try:
                yield (str(item[to_rm:]), self[item[to_rm:]])
            except KeyError:
                pass

    def items(self):
        return list(self.iteritems())

    def values(self):
        return list(self.itervalues())

    def itervalues(self):
        to_rm = len(self.namespace) + 1
        for item in self._scan_keys():
            try:
                yield self[item[to_rm:]]
            except KeyError:
                pass

    def to_dict(self):
        return dict(self.items())

    def clear(self):
        with self.pipeline():
            for key in self:
                del(self[key])

    def pop(self, key, default=SENTINEL):
        try:
            value = self[key]
        except KeyError:
            if default is not SENTINEL:
                return default
            raise

        del(self[key])
        return value

    def popitem(self):
        while True:
            key = self.key()
            if key is None:
                raise KeyError("popitem(): dictionary is empty")
            try:
                return key, self.pop(key)
            except KeyError:
                continue

    def setdefault(self, key, default_value=None):
        found, value = self._load(key)
        if not found:
            self[key] = default_value
            return default_value
        return value

    def copy(self):
        return self.to_dict()

    def update(self, dic):
        with self.pipeline():
            for key, value in dic.items():
                self[key] = value

    def fromkeys(self, iterable, value=None):
        return {}.fromkeys(iterable, value)

    def __sizeof__(self):
        return self.to_dict().__sizeof__()

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

    @contextmanager
    def pipeline(self):
        top_level = False
        if self.temp_redis is None:
            self.redis, self.temp_redis, top_level = self.redis.pipeline(), self.redis, True
        try:
            yield
        finally:
            if top_level:
                _, self.temp_redis, self.redis = self.redis.execute(), None, self.temp_redis

    def multi_get(self, key):
        found_keys = list(self._scan_keys(key))
        if len(found_keys) == 0:
            return []
        return [self._transform(i) for i in self.redis.mget(found_keys) if i is not None]

    def multi_chain_get(self, keys):
        return self.multi_get(':'.join(keys))

    def multi_dict(self, key):
        keys = list(self._scan_keys(key))
        if len(keys) == 0:
            return {}
        to_rm = keys[0].rfind(':') + 1
        return dict(zip([i[to_rm:] for i in keys], (self._transform(i) for i in self.redis.mget(keys) if i is not None)))

    def multi_del(self, key):
        keys = list(self._scan_keys(key))
        if len(keys) == 0:
            return 0
        return self.redis.delete(*keys)
