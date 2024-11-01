import time
import statistics

from redis_dict import RedisDict
import json

# Constants
BATCH_SIZE = 1000


import os
import csv
import zipfile
import requests
from typing import Iterator, Dict
from io import TextIOWrapper
import gzip
import base64

class GzippedDict:
    """
    A class that can encode its attributes to a compressed string and decode from a compressed string,
    optimized for the fastest possible gzipping.

    Methods:
        encode: Compresses and encodes the object's attributes to a base64 string using the fastest settings.
        decode: Creates a new object from a compressed and encoded base64 string.
    """

    def encode(self) -> str:
        """
        Encodes the object's attributes to a compressed base64 string using the fastest possible settings.

        Returns:
            str: A base64 encoded string of the compressed object attributes.
        """
        json_data = json.dumps(self.__dict__, separators=(',', ':'))
        compressed_data = gzip.compress(json_data.encode('utf-8'), compresslevel=1)
        return base64.b64encode(compressed_data).decode('ascii')

    @classmethod
    def decode(cls, encoded_str: str) -> 'GzippedDict':
        """
        Creates a new object from a compressed and encoded base64 string.

        Args:
            encoded_str (str): A base64 encoded string of compressed object attributes.

        Returns:
            GzippedDict: A new instance of the class with decoded attributes.
        """
        json_data = gzip.decompress(base64.b64decode(encoded_str)).decode('utf-8')
        attributes = json.loads(json_data)
        return cls(**attributes)


def encode_dict(dic: dict) -> str:
    json_data = json.dumps(dic, separators=(',', ':'))
    compressed_data = gzip.compress(json_data.encode('utf-8'), compresslevel=1)
    return str(base64.b64encode(compressed_data).decode('ascii'))


def decode_dict(s) -> dict:
    return json.loads(gzip.decompress(base64.b64decode(s)).decode('utf-8'))

import binascii

def encode_dict(dic: dict) -> str:
    json_data = json.dumps(dic, separators=(',', ':'))
    compressed_data = gzip.compress(json_data.encode('utf-8'), compresslevel=1)
    return binascii.hexlify(compressed_data).decode('ascii')

def decode_dict(s: str) -> dict:
    compressed_data = binascii.unhexlify(s)
    return json.loads(gzip.decompress(compressed_data).decode('utf-8'))


import os
import zipfile
import gzip
import csv
from typing import Iterator, Dict
from io import TextIOWrapper
import requests
from urllib.parse import urlparse

def download_file(url: str, filename: str):
    response = requests.get(url)
    with open(filename, 'wb') as f:
        f.write(response.content)

def csv_iterator(file) -> Iterator[Dict[str, str]]:
    reader = csv.DictReader(file)
    for row in reader:
        yield row

def get_filename_from_url(url: str) -> str:
    return os.path.basename(urlparse(url).path)

def create_data_gen(url: str) -> Iterator[Dict[str, str]]:
    filename = get_filename_from_url(url)
    print(filename)
    if not os.path.exists(filename):
        download_file(url, filename)

    if filename.endswith('.zip'):
        with zipfile.ZipFile(filename, 'r') as zip_ref:
            csv_filename = zip_ref.namelist()[0]
            with zip_ref.open(csv_filename) as csv_file:
                text_file = TextIOWrapper(csv_file, encoding='utf-8')
                yield from csv_iterator(text_file)
    elif filename.endswith('.gz'):
        with gzip.open(filename, 'rt', encoding='utf-8') as gz_file:
            yield from csv_iterator(gz_file)
    else:
        raise ValueError("Unsupported file format. Use .zip or .gz files.")


def run_load_test(dataset, times=1, use_compression=False):
    redis_dict = RedisDict()
    redis_dict.clear()
    initial_size = redis_dict.redis.info(section="memory")["used_memory"]
    if use_compression:
        redis_dict.extends_type(dict, encode_dict, decode_dict)


    operation_times = []
    start_total = time.time()

    total_operations = 0

    for _ in range(times):
        key = "bla"
        for i, value in enumerate(create_data_gen(dataset), 1):
            #key = f"key{i}"
            #print(value)
            start_time = time.time()
            redis_dict[key] = value
            _ = redis_dict[key]
            end_time = time.time()

            operation_times.append(end_time - start_time)

        total_operations += i

    print(f"\nTotal operations completed: {total_operations}")

    end_total = time.time()
    total_time = end_total - start_total

    final_size = redis_dict.redis.info(section="memory")["used_memory"]
    redis_dict.clear()

    return {
        "dataset": dataset,
        "compression": use_compression,
        "total_operations": total_operations,
        "batch_size": BATCH_SIZE,
        "mean_time": statistics.mean(operation_times) if operation_times else None,
        "min_time": min(operation_times) if operation_times else None,
        "max_time": max(operation_times) if operation_times else None,
        "std_dev": statistics.stdev(operation_times) if len(operation_times) > 1 else None,
        "total_time": total_time,
        "initial_size": human_readable_size(initial_size),
        "final_size": human_readable_size(final_size),
        "size_difference": human_readable_size(final_size - initial_size),
    }

def format_value(value):
    if isinstance(value, bool):
        return "With" if value else "Without"
    elif isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def human_readable_size(size_in_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"


def display_results(results, sort_key="mean_time", reverse=False):
    if not results:
        print("No results to display.")
        return

    sorted_results = sorted(results, key=lambda x: x[sort_key], reverse=reverse)

    keys = list(sorted_results[0].keys())

    headers = [key.replace("_", " ").capitalize() for key in keys]

    col_widths = [max(len(header), max(len(format_value(result[key])) for result in sorted_results)) for header, key in zip(headers, keys)]

    header = " | ".join(header.ljust(width) for header, width in zip(headers, col_widths))
    print(header)
    print("-" * len(header))

    # Print each result row
    for result in sorted_results:
        row = [format_value(result[key]).ljust(width) for key, width in zip(keys, col_widths)]
        print(" | ".join(row))


if __name__ == "__main__":
    times = 1
    results = []
    datasets = [
        "https://www.briandunning.com/sample-data/us-500.zip",
        #"https://datasets.imdbws.com/name.basics.tsv.gz",
        "https://datasets.imdbws.com/title.basics.tsv.gz"
    ]
    for dataset in datasets:
        print("Running load test without compression...")
        results.append(run_load_test(times=times, use_compression=False, dataset=dataset))
        print("\nRunning load test with compression...")
        results.append(run_load_test(times=times, use_compression=True, dataset=dataset))

    print("\nPerformance Comparison (sorted by Mean Time):")
    display_results(results)