import ast
import pathlib

GENERIC = pathlib.Path(__file__).resolve().parents[1] / "sciqlop_vdf"
CORE_ALLOWED = {"numpy", "scipy", "__future__", "dataclasses", "typing", "warnings", "math", "datetime", "threading", "importlib", "logging", "re"}


def _imports(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module


def test_generic_never_imports_adapters():
    for py in GENERIC.rglob("*.py"):
        for mod in _imports(py):
            assert not mod.startswith("sciqlop_vdf_mms"), f"{py} imports {mod}"


def test_core_and_model_are_qt_free():
    files = [GENERIC / "model.py", GENERIC / "synthetic.py", GENERIC / "registry.py", GENERIC / "ui" / "format.py", GENERIC / "ui" / "layout.py",
             *(GENERIC / "core").rglob("*.py")]
    for py in files:
        for mod in _imports(py):
            assert mod.split(".")[0] in CORE_ALLOWED, f"{py} imports {mod}"
