"""Adapters by platform. Adding a platform does not change the engine, storage or API."""

from collections.abc import Callable

from fdh.dataplane.connectors.contract import (
    AdapterContext,
    DiscoveryAdapter,
    UnsupportedConfiguration,
    check_capabilities,
)
from fdh.dataplane.connectors.data360 import Data360Adapter
from fdh.dataplane.connectors.socrata import SocrataAdapter
from fdh.domain.sources import SourceDefinition

AdapterFactory = Callable[[], DiscoveryAdapter]


class AdapterRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}

    def register(self, platform: str, factory: AdapterFactory) -> None:
        if platform in self._factories:
            raise ValueError(f"platform already registered: {platform}")
        self._factories[platform] = factory

    def is_available(self, platform: str) -> bool:
        return platform in self._factories

    def create(self, platform: str) -> DiscoveryAdapter:
        try:
            return self._factories[platform]()
        except KeyError:
            raise LookupError(f"no adapter is available for platform: {platform}") from None

    def validate(self, source: SourceDefinition) -> None:
        """Check the capabilities and options of one source. Sends no request."""
        adapter = self.create(source.platform)
        context = AdapterContext(
            source_id=source.source_id,
            base_url=source.base_url,
            page_size=source.limits.page_size,
            options=source.options,
        )
        check_capabilities(adapter.capabilities, context, source.queries)
        if source.app_token_env and not adapter.capabilities.token_header:
            raise UnsupportedConfiguration("the platform does not accept an application token")
        adapter.validate(context, source.queries)


def default_registry() -> AdapterRegistry:
    """Adapters shipped with the product."""
    registry = AdapterRegistry()
    registry.register(SocrataAdapter.platform, SocrataAdapter)
    registry.register(Data360Adapter.platform, Data360Adapter)
    return registry
