import time
from datetime import datetime

from redis_dict import RedisDict

dic = RedisDict(namespace='assert_test')
assert 'random' not in dic
dic['random'] = 4
assert dic['random'] == 4
assert 'random' in dic
del dic['random']
assert 'random' not in dic

now = datetime.now()
dic['datetime'] = now
assert dic['datetime'] == now
dic.clear()

deep = ['key', 'key1', 'key2']
deep_val = 'mister'
dic.chain_set(deep, deep_val)

assert deep_val == dic.chain_get(deep)
dic.chain_del(deep)

try:
    dic.chain_get(deep)
except KeyError:
    pass
except Exception:
    print('failed to throw KeyError')
else:
    print('failed to throw KeyError')

assert 'random' not in dic
dic['random'] = 4
dd = RedisDict(namespace='app_name_too')
assert len(dd) == 0

dd['random'] = 5

assert dic['random'] == 4
assert 'random' in dic

assert dd['random'] == 5
assert 'random' in dd

del dic['random']
assert 'random' not in dic

assert dd['random'] == 5
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

long_key = 'thekeyislongbutstill'
items = {'K1': 'V1', 'KK22': 'VV22', 'KKK333': 'VVV333'}
for key, val in items.items():
    dd.chain_set([long_key, key], val)

assert sorted(dd.multi_get(long_key)) == sorted(list(items.values()))
assert dd.multi_dict(long_key) == items
dd.multi_del(long_key)

dd['one_item'] = 'im here'
dd.multi_del('keys')

assert len(dd) == 1

del dd['one_item']
assert len(dd) == 0

print('all is well')
