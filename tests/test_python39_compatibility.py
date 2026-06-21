import ast
import sys
from pathlib import Path


def test_all_python_sources_use_python39_grammar() -> None:
    root = Path(__file__).parents[1]
    parse_kwargs = {"feature_version": (3, 9)} if sys.version_info >= (3, 10) else {}
    for directory in (root / "irrigationd", root / "tests"):
        for path in directory.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path), **parse_kwargs)

