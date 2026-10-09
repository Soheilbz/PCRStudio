"""Enforce the foundation's dependency seam without importing scientific code."""
from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCIENTIFIC_MODULES = {"numpy", "scipy", "pandas", "Bio", "primer3", "torch", "tensorflow", "sklearn"}


def verify_imports() -> None:
    for source in (ROOT / "backend").rglob("*.py"):
        if any(part.startswith(".") for part in source.relative_to(ROOT).parts):
            continue
        tree = ast.parse(source.read_text(), filename=str(source))
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports = [node.module]
            for module in imports:
                if module.split(".")[0] in SCIENTIFIC_MODULES:
                    raise AssertionError(f"Scientific dependency crossed platform runtime boundary: {source}")
    manifest = tomllib.loads((ROOT / "backend/pyproject.toml").read_text())
    for dependency in manifest["project"]["dependencies"]:
        name = dependency.split("[")[0].split(">")[0].split("=")[0].split("<")[0].lower()
        if name in {module.lower() for module in SCIENTIFIC_MODULES} | {"biopython", "scikit-learn", "primer3-py"}:
            raise AssertionError("Scientific dependency declared in platform manifest")
    if not (ROOT / "contracts/execution-request.schema.json").is_file():
        raise AssertionError("Versioned executor seam schema is missing")


if __name__ == "__main__":
    verify_imports()
    print("Platform scientific dependency boundary verified.")
