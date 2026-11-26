"""The `fdh` command (contracts/cli.md).

Exit codes: 0 success, 1 runtime error, 2 invalid usage or configuration (no network),
3 partial run, 4 failed run, 5 run already in progress.
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import SecretStr

from fdh.cli.database import database_engine
from fdh.cli.discover import discover, list_runs
from fdh.controlplane.sources import SyncPlan, UnauditedChange, plan_source_sync
from fdh.dataplane.connectors.contract import UnsupportedConfiguration
from fdh.dataplane.connectors.registry import AdapterRegistry, default_registry
from fdh.domain.sources import SourceDefinition
from fdh.observability.logging import configure_logging
from fdh.persistence.session import create_sessions
from fdh.persistence.sources import SqlSourceRepository
from fdh.settings.env import InvalidSecret, Settings, read_app_token
from fdh.settings.sources import ConfigError, load_sources

OK, RUNTIME_ERROR, USAGE_ERROR = 0, 1, 2
log = logging.getLogger("fdh.cli")


def _run_limit(value: str) -> int:
    limit = int(value)
    if not 1 <= limit <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return limit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fdh", description="Financial Data Hub")
    groups = parser.add_subparsers(dest="group", required=True)
    configured = argparse.ArgumentParser(add_help=False)
    configured.add_argument("--config", type=Path, help="path to sources.toml (or FDH_CONFIG)")

    for group, action, summary in (
        ("config", "check", "validate the configuration; no network or database"),
        ("sources", "sync", "apply sources and publication permissions; database only"),
    ):
        actions = groups.add_parser(group).add_subparsers(dest="action", required=True)
        actions.add_parser(action, help=summary, description=summary, parents=[configured])

    summary = "discover datasets and record the run"
    command = groups.add_parser("discover", help=summary, description=summary, parents=[configured])
    selection = command.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source", metavar="ID", help="one configured source")
    selection.add_argument("--all", action="store_true", help="every configured source")

    runs = groups.add_parser("runs").add_subparsers(dest="action", required=True)
    summary = "show the latest runs; database only"
    listing = runs.add_parser("list", help=summary, description=summary)
    listing.add_argument("--source", metavar="ID", help="only this source")
    listing.add_argument("--limit", type=_run_limit, default=20, help="1 to 100 (default 20)")
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
    engine = database_engine(settings)
    try:
        repository = SqlSourceRepository(create_sessions(engine))
        today = datetime.now(UTC).date()
        return await repository.synchronise(
            lambda registered: plan_source_sync(sources, registered, today=today)
        )
    finally:
        await engine.dispose()


def _app_tokens(sources: Sequence[SourceDefinition]) -> dict[str, SecretStr]:
    """Optional application tokens, by source, from the variables each source names."""
    found = {}
    for source in sources:
        if source.app_token_env and (token := read_app_token(source.app_token_env)):
            found[source.source_id] = token
    return found


def _usage_error(message: object) -> int:
    print(f"error: {message}", file=sys.stderr)
    return USAGE_ERROR


def _runtime_error(summary: str, event: str) -> int:
    log.exception(summary, extra={"event": event})
    print(f"error: {summary}; see the log", file=sys.stderr)
    return RUNTIME_ERROR


def main(
    argv: Sequence[str] | None = None,
    registry: AdapterRegistry | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    arguments = build_parser().parse_args(argv)
    settings = Settings()
    configure_logging(settings.log_level)

    if arguments.group == "runs":
        try:
            return asyncio.run(list_runs(settings, arguments.source, arguments.limit))
        except Exception:
            return _runtime_error("runs could not be read", "runs_list_failed")

    registry = registry or default_registry()
    try:
        checked = load_and_validate(arguments.config or settings.config, registry)
    except (ConfigError, UnsupportedConfiguration) as error:
        return _usage_error(error)
    sources = [source for source, _ in checked]

    if arguments.group == "config":
        for source, available in checked:
            adapter = "available" if available else "not available yet"
            print(
                f"{source.source_id}: platform={source.platform} "
                f"publication={source.publication.value.value} adapter={adapter}"
            )
        print(f"configuration is valid: {len(checked)} source(s)")
        return OK

    if arguments.group == "discover":
        selected = [
            (source, available)
            for source, available in checked
            if arguments.all or source.source_id == arguments.source
        ]
        if not selected:
            return _usage_error(f"unknown source: {arguments.source}")
        # Every selected source must be usable before the first request is sent.
        missing = sorted({source.platform for source, available in selected if not available})
        if missing:
            return _usage_error(f"no adapter is available for: {', '.join(missing)}")
        try:
            tokens = _app_tokens([source for source, _ in selected])
        except InvalidSecret as error:
            return _usage_error(error)

    try:
        plan = asyncio.run(synchronise(settings, sources))
    except UnauditedChange as error:
        return _usage_error(error)
    except Exception:
        return _runtime_error("sources synchronisation failed", "sources_sync_failed")

    if arguments.group == "discover":
        targets = [source for source, _ in selected]
        return asyncio.run(discover(settings, targets, registry, transport, tokens))

    for change in plan.publication_changes:
        print(f"{change.source_id}: publication {change.old.value} -> {change.new.value}")
    print(
        f"synchronised {len(plan.upserts)} source(s); retired {len(plan.retirements)}; "
        f"permission changes {len(plan.publication_changes)}"
    )
    return OK


if __name__ == "__main__":
    sys.exit(main())
