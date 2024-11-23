from redis_dict import RedisDict
### Insertion Order
from redis_dict import PythonRedisDict

dic = PythonRedisDict()
dic["1"] = "one"
dic["2"] = "two"
dic["3"] = "three"

assert list(dic.keys()) == ["1", "2", "3"]

### Extending RedisDict with Custom Types
import json

class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def encode(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def decode(cls, encoded_str: str) -> 'Person':
        return cls(**json.loads(encoded_str))

redis_dict = RedisDict()

# Extend redis dict with the new type
redis_dict.extends_type(Person)

# RedisDict can now seamlessly handle Person instances.
person = Person(name="John", age=32)
redis_dict["person1"] = person

result = redis_dict["person1"]

assert result.name == person.name
assert result.age == person.age