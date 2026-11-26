"""The API contract is a valid OpenAPI document and exposes read operations only."""

from pathlib import Path
from typing import Any

import yaml
from openapi_spec_validator import validate

CONTRACT = Path(__file__).resolve().parents[3] / "specs/001-source-discovery/contracts/openapi.yaml"
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def document() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    return loaded


def test_contract_is_valid_openapi() -> None:
    validate(document())


def test_contract_only_reads() -> None:
    methods = {
        method for path in document()["paths"].values() for method in path if method in HTTP_METHODS
    }
    assert methods == {"get"}


def test_detail_includes_bounded_provenance_and_source_licence() -> None:
    schemas = document()["components"]["schemas"]
    recent = schemas["RecentProvenance"]["properties"]["items"]
    assert recent["maxItems"] == 20
    assert "provenance" in schemas["DatasetDetail"]["allOf"][1]["required"]
    assert {"license_name", "license_url", "terms_url"} <= set(schemas["SourceInfo"]["required"])
