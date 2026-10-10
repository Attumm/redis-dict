"""Style checks with pycodestyle, pyflakes and mccabe, the same checks pylama ran.

Usage: python scripts/lib/style_checks.py [path ...]   (default: src/redis_dict)

This uses the three tools the same way pylama 8.4.1 called them, with the
project's former [tool.pylama] settings:
  - pycodestyle with max_line_length 120 and its default ignore list,
  - pyflakes,
  - mccabe with a max complexity of 10,
  - messages on a line that contains "# noqa" are skipped,
  - E501 and E231 are ignored.
Exits with 1 when there are messages, like pylama did.
"""
import ast
import re
import sys
from pathlib import Path

import pycodestyle
from mccabe import McCabeChecker
from pyflakes import checker as pyflakes_checker

MAX_LINE_LENGTH = 120
MAX_COMPLEXITY = 10
IGNORE = ("E501", "E231")
NOQA = re.compile(r"# *noqa\b", re.I).search


def check_file(path: Path) -> list:
    """Return the style messages for one file as (line, col, code, text, tool)."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    messages = []

    class Report(pycodestyle.BaseReport):
        def error(self, line_number, offset, text, check):
            code, _, text = text.partition(" ")
            messages.append((line_number, offset + 1, code, text, "pycodestyle"))

    style = pycodestyle.StyleGuide(reporter=Report, max_line_length=MAX_LINE_LENGTH)
    pycodestyle.Checker(str(path), lines=lines, options=style.options).check_all()

    tree = ast.parse(source, str(path))
    for msg in pyflakes_checker.Checker(tree, str(path)).messages:
        messages.append((msg.lineno, msg.col + 1, "", msg.message % msg.message_args, "pyflakes"))

    McCabeChecker.max_complexity = MAX_COMPLEXITY
    for line, col, text, _ in McCabeChecker(tree, str(path)).run():
        code, _, text = text.partition(" ")
        messages.append((line, col + 1, code, text, "mccabe"))

    result = []
    for line, col, code, text, tool in messages:
        if line <= len(lines) and NOQA(lines[line - 1]):
            continue
        if code.startswith(IGNORE):
            continue
        result.append((line, col, code, text, tool))
    return sorted(result)


def main(argv: list) -> int:
    """Check every .py file under the given paths."""
    paths = [Path(p) for p in (argv or ["src/redis_dict"])]
    files = sorted(f for p in paths for f in ([p] if p.is_file() else p.rglob("*.py")))
    found = 0
    for path in files:
        for line, col, code, text, tool in check_file(path):
            print(f"{path}:{line}:{col} [{tool}] {code} {text}".replace("  ", " "))
            found += 1
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
