from datetime import datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from redis_dict import EncryptedRedisDict, PythonRedisDict, RedisDict

key = AESGCM.generate_key(bit_length=256)

for obj in [RedisDict, PythonRedisDict, lambda **kw: EncryptedRedisDict(key=key, **kw)]:
    dic = obj(namespace='assert_test')
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

print("passed assert test")
