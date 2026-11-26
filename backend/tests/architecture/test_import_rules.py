"""Dependency rules between modules (plan.md, "Reglas de dependencia")."""

import ast
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "src"
STDLIB = frozenset(sys.stdlib_module_names)
# Standard library modules that would let a pure module reach the network or storage.
IO_MODULES = frozenset({"socket", "ssl", "http", "urllib.request", "sqlite3", "ftplib", "smtplib"})

# module prefix -> (allowed internal prefixes, allowed third-party roots, forbidden stdlib)
RULES: dict[str, tuple[tuple[str, ...], frozenset[str], frozenset[str]]] = {
    "fdh.domain": (("fdh.domain",), frozenset(), IO_MODULES),
    "fdh.settings": (
        ("fdh.settings", "fdh.domain"),
        frozenset({"pydantic", "pydantic_settings"}),
        IO_MODULES,
    ),
    "fdh.observability": (("fdh.observability",), frozenset(), IO_MODULES),
    "fdh.dataplane.connectors": (
        ("fdh.dataplane.connectors", "fdh.domain"),
        frozenset(),
        IO_MODULES,
    ),
    "fdh.controlplane": (("fdh.controlplane", "fdh.domain"), frozenset(), IO_MODULES),
    "fdh.dataplane.discovery": (
        ("fdh.dataplane", "fdh.domain", "fdh.controlplane"),
        frozenset({"httpx"}),
        frozenset({"sqlite3"}),
    ),
    "fdh.persistence": (
        ("fdh.persistence", "fdh.domain", "fdh.controlplane"),
        frozenset({"sqlalchemy", "asyncpg", "alembic"}),
        frozenset(),
    ),
    # Entry points compose the other modules; the API must not import adapters.
    "fdh.api": (
        (
            "fdh.api",
            "fdh.domain",
            "fdh.controlplane",
            "fdh.persistence",
            "fdh.settings",
            "fdh.observability",
        ),
        frozenset({"fastapi", "starlette", "pydantic", "sqlalchemy", "uvicorn"}),
        frozenset(),
    ),
}


def module_name(path: Path) -> str:
    parts = list(path.relative_to(SOURCE).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imports(path: Path) -> list[tuple[str, list[str]]]:
    found: list[tuple[str, list[str]]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.extend((alias.name, []) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"relative import in {path}"
            found.append((node.module or "", [alias.name for alias in node.names]))
    return found


def within(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def violations(module: str, imported: str) -> str | None:
    for prefix, (internal, third_party, forbidden) in RULES.items():
        if not within(module, prefix):
            continue
        root = imported.split(".")[0]
        if root == "fdh":
            if any(within(imported, allowed) for allowed in internal):
                return None
            return f"{module} may not import {imported}"
        if root in STDLIB:
            if any(within(imported, name) for name in forbidden):
                return f"{module} may not use {imported}"
            return None
        return None if root in third_party else f"{module} may not depend on {imported}"
    return None


FILES = sorted(SOURCE.rglob("*.py"))


@pytest.mark.parametrize("path", FILES, ids=module_name)
def test_module_respects_dependency_rules(path: Path) -> None:
    module = module_name(path)
    problems = [v for name, _ in imports(path) if (v := violations(module, name))]
    assert not problems, problems


@pytest.mark.parametrize("path", FILES, ids=module_name)
def test_no_private_names_are_imported_across_modules(path: Path) -> None:
    private = [
        f"{module}.{name}"
        for module, names in imports(path)
        if module.startswith("fdh")
        for name in names
        if name.startswith("_")
    ]
    assert not private


@pytest.mark.parametrize(
    ("module", "imported"),
    [
        ("fdh.dataplane.connectors.socrata", "httpx"),
        ("fdh.dataplane.connectors.socrata", "sqlalchemy"),
        ("fdh.dataplane.connectors.socrata", "socket"),
        ("fdh.dataplane.connectors.socrata", "fdh.persistence.models"),
        ("fdh.domain.status", "pydantic"),
        ("fdh.controlplane.sources", "fdh.persistence"),
        ("fdh.api.app", "fdh.dataplane.connectors.contract"),
    ],
)
def test_rules_reject_forbidden_imports(module: str, imported: str) -> None:
    assert violations(module, imported)
