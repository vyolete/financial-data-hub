"""Adapter registry and capability checks, with a synthetic adapter (AC-33, AC-34)."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from fdh.cli.main import load_and_validate, main
from fdh.dataplane.connectors.contract import (
    AdapterCapabilities,
    AdapterContext,
    DiscoveryPage,
    ErrorKind,
    HttpRequest,
    HttpResponse,
    UnsupportedConfiguration,
)
from fdh.dataplane.connectors.registry import AdapterRegistry, default_registry
from fdh.domain.sources import DiscoveryLimits, DiscoveryQuery, SourceDefinition


class SyntheticAdapter:
    platform = "socrata"
    capabilities = AdapterCapabilities(
        text_search=True,
        declares_total=True,
        cursor_pagination=True,
        supported_filters=("kind",),
        max_page_size=50,
    )

    def validate(self, context: AdapterContext, queries: tuple[DiscoveryQuery, ...]) -> None:
        if context.options:
            raise UnsupportedConfiguration("unknown option")

    def build_request(
        self, context: AdapterContext, query: DiscoveryQuery, cursor: str | None
    ) -> HttpRequest:
        return HttpRequest("GET", context.base_url)

    def classify(self, response: HttpResponse) -> ErrorKind | None:
        return None

    def parse(
        self,
        context: AdapterContext,
        request: HttpRequest,
        response: HttpResponse,
        cursor: str | None,
    ) -> DiscoveryPage:
        return DiscoveryPage((), (), 0, None)


REPOSITORY_CONFIG = Path(__file__).resolve().parents[3] / "config/sources.toml"


def registry() -> AdapterRegistry:
    created = AdapterRegistry()
    created.register("socrata", SyntheticAdapter)
    return created


def source(
    *queries: DiscoveryQuery, page_size: int = 50, options: dict[str, str] | None = None
) -> SourceDefinition:
    return SourceDefinition(
        source_id="synthetic",
        provider="P",
        platform="socrata",
        base_url="https://api.example.org",
        allowed_hosts=("api.example.org",),
        official_url="https://www.example.org",
        verified_at=date(2026, 1, 1),
        queries=queries or (DiscoveryQuery("budget", {"kind": "dataset"}),),
        limits=DiscoveryLimits(page_size=page_size),
        options=options or {},
    )


def test_only_implemented_adapters_ship() -> None:
    assert default_registry().is_available("socrata")
    assert not default_registry().is_available("data360")
    with pytest.raises(LookupError, match="no adapter"):
        default_registry().create("data360")


def test_registered_adapter_validates_a_supported_source() -> None:
    registry().validate(source())


def test_a_platform_is_registered_once() -> None:
    with pytest.raises(ValueError, match="already registered"):
        registry().register("socrata", SyntheticAdapter)


@pytest.mark.parametrize(
    ("definition", "message"),
    [
        (source(page_size=100), "page_size"),
        (source(DiscoveryQuery("x", {"colour": "red"})), "unsupported filters: colour"),
        (source(options={"unknown": "1"}), "unknown option"),
    ],
)
def test_unsupported_configuration_is_rejected(definition: SourceDefinition, message: str) -> None:
    with pytest.raises(UnsupportedConfiguration, match=message):
        registry().validate(definition)


def test_text_search_must_be_supported() -> None:
    class WithoutSearch(SyntheticAdapter):
        capabilities = AdapterCapabilities(False, False, False)

    created = AdapterRegistry()
    created.register("socrata", WithoutSearch)
    with pytest.raises(UnsupportedConfiguration, match="text search"):
        created.validate(source(DiscoveryQuery("x")))


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH"])
def test_adapters_cannot_build_writing_requests(method: str) -> None:
    with pytest.raises(ValueError, match="GET or POST"):
        HttpRequest(method, "https://api.example.org")


def test_config_check_rejects_unsupported_capabilities_without_any_request() -> None:
    with pytest.raises(UnsupportedConfiguration):
        load_and_validate(
            REPOSITORY_CONFIG, registry()
        )  # page_size 100 exceeds the synthetic maximum
    assert main(["config", "check", "--config", str(REPOSITORY_CONFIG)], registry=registry()) == 2


def test_config_check_reports_a_missing_adapter(capsys: pytest.CaptureFixture[str]) -> None:
    arguments = ["config", "check", "--config", str(REPOSITORY_CONFIG)]
    assert main(arguments, registry=AdapterRegistry()) == 0
    assert "adapter=not available yet" in capsys.readouterr().out


def test_config_check_reports_the_shipped_adapter(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["config", "check", "--config", str(REPOSITORY_CONFIG)]) == 0
    assert "adapter=available" in capsys.readouterr().out


def test_a_token_variable_needs_a_platform_that_accepts_a_token() -> None:
    definition = replace(source(), app_token_env="FDH_SYNTHETIC_APP_TOKEN")
    with pytest.raises(UnsupportedConfiguration, match="application token"):
        registry().validate(definition)


def test_the_shipped_socrata_adapter_declares_its_token_header() -> None:
    assert default_registry().create("socrata").capabilities.token_header == "X-App-Token"
