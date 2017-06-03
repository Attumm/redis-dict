from redis import StrictRedis


class RedisDict(object):
    def __init__(self, *args, **kwargs):
        self.namespace = ''
        if 'namespace' in kwargs:
            # Todo validate namespace
            self.namespace = kwargs['namespace'] + ':'
            del kwargs['namespace']

        self.redis = StrictRedis(*args, **kwargs)
        self.sentinel_none = "<META __None__ please.lkek.iife>"

    def _raw_get_item(self, k):
        return self.redis.get(k)

    def _get_item(self, k):
        return self._raw_get_item(self.namespace + k)

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
        self.redis.delete(self.namespace, k)

    def __contains__(self, k):
        return self._get_item(k) is not None

    def __repr__(self):
        return str(self.to_dict())   

    def keys(self):
        return self.redis.keys(self.namespace + '*')

    def to_dict(self):
        to_rm = len(self.namespace)
        return {item[to_rm:]: self._raw_get_item(item) for item in self.keys()}

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


if __name__ == '__main__':
    d = RedisDict(namespace='app_name')
    'random' in d is False
    d['random'] = 4
    d['random'] == 4
    'random' in d is True
    del d['random']
    'random' in d is False
    print('all is well')

        
        
        

