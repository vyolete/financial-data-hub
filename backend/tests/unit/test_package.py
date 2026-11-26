import importlib

import pytest

MODULES = [
    "fdh",
    "fdh.domain",
    "fdh.controlplane",
    "fdh.dataplane.connectors",
    "fdh.dataplane.discovery",
    "fdh.persistence",
    "fdh.api",
    "fdh.cli",
    "fdh.settings",
    "fdh.observability",
]


@pytest.mark.parametrize("name", MODULES)
def test_package_imports(name: str) -> None:
    assert importlib.import_module(name).__doc__
