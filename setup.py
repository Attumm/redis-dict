
from os import path
from setuptools import setup

current = path.abspath(path.dirname(__file__))

with open(path.join(current, 'README.rst')) as f:
    long_description = f.read()
 
setup(
    name='redis dict',
    author='Melvin Bijman',
    author_email='bijman.m.m@gmail.com',
    version='0.1',
    py_modules=['redis_dict'],
    install_requires=['redis', 'future'],
    license='MIT',

    url='https://github.com/Attumm/redisdict',

    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: Database :: Front-Ends',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)

