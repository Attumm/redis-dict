from os import path
from setuptools import setup
import io

current = path.abspath(path.dirname(__file__))

with io.open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name='redis dict',
    author='Melvin Bijman',
    author_email='bijman.m.m@gmail.com',

    description='Dictionary with Redis as storage backend',
    long_description=long_description,
    long_description_content_type='text/markdown',

    version='2.4.1',
    py_modules=['redis_dict'],
    install_requires=['redis',],
    license='MIT',

    url='https://github.com/Attumm/redisdict',

    classifiers=[
        'Development Status :: 5 - Production/Stable',

        'Intended Audience :: Developers',

        'Topic :: Database',
        'Topic :: System :: Distributed Computing',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)

