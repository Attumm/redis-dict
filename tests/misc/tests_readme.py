import ast
import contextlib
import io
import os
import re
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

from redis_dict import PythonRedisDict, RedisDict

README_PATH = Path(__file__).resolve().parents[2] / "README.md"


def _extract_python_blocks_by_heading(markdown_text: str) -> Dict[str, List[str]]:
    """Extract fenced ```python code blocks grouped by their nearest Markdown heading."""
    blocks_by_heading: Dict[str, List[str]] = {}
    current_heading = ""
    in_python_block = False
    current_lines: List[str] = []

    for line in markdown_text.splitlines():
        if not in_python_block:
            heading_match = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
            if heading_match:
                current_heading = heading_match.group(1)
            elif line.strip() == "```python":
                in_python_block = True
                current_lines = []
        else:
            if line.strip() == "```":
                in_python_block = False
                blocks_by_heading.setdefault(current_heading, []).append("\n".join(current_lines))
            else:
                current_lines.append(line)

    return blocks_by_heading


class TestReadmeExamples(unittest.TestCase):
    """Ensure standalone Python examples in README.md remain syntactically valid and runnable."""

    blocks_by_heading: Dict[str, List[str]] = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.blocks_by_heading = _extract_python_blocks_by_heading(
            README_PATH.read_text(encoding="utf-8")
        )

    def setUp(self) -> None:
        self._clean_namespaces()

    def tearDown(self) -> None:
        self._clean_namespaces()

    @staticmethod
    def _clean_namespaces() -> None:
        PythonRedisDict(namespace="main").clear()
        RedisDict(namespace="main").clear()
        RedisDict(namespace="example").clear()
        RedisDict(namespace="vault").clear()

    def _run_section_block(self, heading: str, index: int = 0) -> Dict[str, Any]:
        self.assertIn(heading, self.blocks_by_heading, f"Missing README heading: {heading!r}")
        code = self.blocks_by_heading[heading][index]
        namespace: Dict[str, Any] = {"__name__": "__readme_test__"}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(code, f"README.md [{heading}]", "exec"), namespace)
        return namespace

    def test_all_non_repl_python_blocks_parse(self) -> None:
        parsed_count = 0
        for heading, blocks in self.blocks_by_heading.items():
            for idx, block in enumerate(blocks):
                if block.lstrip().startswith(">>>"):
                    continue
                ast.parse(block, filename=f"README.md [{heading} #{idx}]")
                parsed_count += 1
        self.assertGreaterEqual(parsed_count, 10)

    def test_standard_types_example(self) -> None:
        ns = self._run_section_block("Standard types")
        dic = ns["dic"]
        self.assertEqual(len(dic), 20)
        for key in list(dic.keys()):
            self.assertIsNotNone(key)
            _ = dic[key]

    def test_distributed_computing_example(self) -> None:
        ns = self._run_section_block("Distributed computing")
        self.assertEqual(ns["dic"]["foo"], "bar")

    def test_redis_dict_as_dictionary_example(self) -> None:
        ns = self._run_section_block("Redis-dict as dictionary")
        dic = ns["dic"]
        self.assertIn("now", dic)
        self.assertIn("time", dic)
        self.assertEqual(dic["d"], 4)

    def test_json_encoding_decoding_example(self) -> None:
        ns = self._run_section_block("JSON Encoding - Decoding")
        self.assertEqual(ns["result"], ns["data"])

    def test_extending_custom_types_example(self) -> None:
        ns = self._run_section_block("Extending RedisDict with Custom Types")
        self.assertEqual(ns["result"].name, "John")
        self.assertEqual(ns["result"].age, 32)

    def test_insertion_order_example(self) -> None:
        ns = self._run_section_block("Insertion Order")
        self.assertEqual(list(ns["dic"].keys()), ["1", "2", "3"])

    def test_storage_encryption_example(self) -> None:
        ns_aesgcm = self._run_section_block("Storage Encryption", index=0)
        vault = ns_aesgcm["vault"]
        self.assertEqual(vault["secret"], "a secret message")
        self.assertEqual(vault["limits"], {"rpm": 1000, "active": True})

        persisted_env = {
            "APP_SECRET_PASSPHRASE": "readme-test-passphrase",
            "APP_SCRYPT_SALT_HEX": os.urandom(16).hex(),
        }
        with patch.dict(os.environ, persisted_env):
            ns_deploy_1 = self._run_section_block("Storage Encryption", index=1)
            ns_deploy_1["vault"]["persisted_user"] = {"id": 42, "plan": "pro"}
            del ns_deploy_1

            # Simulate a second deployment restarting and reading pre-existing encrypted data
            ns_deploy_2 = self._run_section_block("Storage Encryption", index=1)
            self.assertEqual(ns_deploy_2["vault"]["persisted_user"], {"id": 42, "plan": "pro"})
            self.assertEqual(ns_deploy_2["vault"]["secret"], "derived-key-secret")


if __name__ == "__main__":
    unittest.main()
