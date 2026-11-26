"""The `fdh` command (contracts/cli.md).

Exit codes: 0 success, 1 runtime error, 2 invalid usage or configuration (no network).
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from fdh.controlplane.sources import SyncPlan, UnauditedChange, plan_source_sync
from fdh.dataplane.connectors.contract import UnsupportedConfiguration
from fdh.dataplane.connectors.registry import AdapterRegistry, default_registry
from fdh.domain.sources import SourceDefinition
from fdh.observability.logging import configure_logging
from fdh.persistence.session import create_engine, create_sessions, database_url
from fdh.persistence.sources import SqlSourceRepository
from fdh.settings.env import Settings
from fdh.settings.sources import ConfigError, load_sources

OK, RUNTIME_ERROR, USAGE_ERROR = 0, 1, 2
log = logging.getLogger("fdh.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fdh", description="Financial Data Hub")
    groups = parser.add_subparsers(dest="group", required=True)
    for group, action, summary in (
        ("config", "check", "validate the configuration; no network or database"),
        ("sources", "sync", "apply sources and publication permissions; database only"),
    ):
        actions = groups.add_parser(group).add_subparsers(dest="action", required=True)
        command = actions.add_parser(action, help=summary, description=summary)
        command.add_argument("--config", type=Path, help="path to sources.toml (or FDH_CONFIG)")
    return parser


def load_and_validate(path: Path, registry: AdapterRegistry) -> list[tuple[SourceDefinition, bool]]:
    """Sources with the availability of their adapter. Available adapters validate them."""
    checked = []
    for source in load_sources(path):
        available = registry.is_available(source.platform)
        if available:
            registry.validate(source)
        checked.append((source, available))
    return checked


async def synchronise(settings: Settings, sources: Sequence[SourceDefinition]) -> SyncPlan:
    engine = create_engine(
        database_url(
            host=settings.db_host,
            port=settings.db_port,
            name=settings.db_name,
            user=settings.db_user,
            password=settings.db_password.get_secret_value(),
        )
    )
    try:
        repository = SqlSourceRepository(create_sessions(engine))
        today = datetime.now(UTC).date()
        return await repository.synchronise(
            lambda registered: plan_source_sync(sources, registered, today=today)
        )
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None, registry: AdapterRegistry | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    settings = Settings()
    configure_logging(settings.log_level)
    try:
        checked = load_and_validate(
            arguments.config or settings.config, registry or default_registry()
        )
    except (ConfigError, UnsupportedConfiguration) as error:
        print(f"error: {error}", file=sys.stderr)
        return USAGE_ERROR

    if arguments.group == "config":
        for source, available in checked:
            adapter = "available" if available else "not available yet"
            print(
                f"{source.source_id}: platform={source.platform} "
                f"publication={source.publication.value.value} adapter={adapter}"
            )
        print(f"configuration is valid: {len(checked)} source(s)")
        return OK

    try:
        plan = asyncio.run(synchronise(settings, [source for source, _ in checked]))
    except UnauditedChange as error:
        print(f"error: {error}", file=sys.stderr)
        return USAGE_ERROR
    except Exception:
        log.exception("sources synchronisation failed", extra={"event": "sources_sync_failed"})
        print("error: sources synchronisation failed; see the log", file=sys.stderr)
        return RUNTIME_ERROR
    for change in plan.publication_changes:
        print(f"{change.source_id}: publication {change.old.value} -> {change.new.value}")
    print(
        f"synchronised {len(plan.upserts)} source(s); retired {len(plan.retirements)}; "
        f"permission changes {len(plan.publication_changes)}"
    )
    return OK


if __name__ == "__main__":
    sys.exit(main())
