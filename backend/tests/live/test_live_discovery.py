"""Controlled checks against the real sources: one query and one page per source (AC-29).

Run on purpose with ``uv run pytest -m live``; never part of the ordinary suite or of CI.
Each execution writes sanitized evidence in ``research/sources/``: request, UTC time, code
revision, result and failures. No titles, identifiers, names or other content are stored.
Only Socrata is covered so far; the platforms without an adapter are not requested.
"""

import json
import subprocess
import time
from collections import Counter
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from fdh.dataplane.connectors.contract import AdapterContext
from fdh.dataplane.connectors.registry import default_registry
from fdh.dataplane.discovery.http import HttpExecutor, RequestFailed
from fdh.domain.datasets import DiscoveredDataset
from fdh.settings.sources import load_sources

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = {"co-datos-gov": ROOT / "research/sources/colombia/socrata/evidence"}
SOURCES = [s for s in load_sources(ROOT / "config/sources.toml") if s.source_id in EVIDENCE]

pytestmark = [pytest.mark.live, pytest.mark.enable_socket]


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def filled(datasets: tuple[DiscoveredDataset, ...]) -> dict[str, int]:
    """How many datasets declare each field. Values are never recorded."""
    counts = {}
    for item in fields(DiscoveredDataset):
        values = [getattr(dataset, item.name) for dataset in datasets]
        if item.name == "dates":
            counts[item.name] = sum(any(vars(v).values()) for v in values)
        else:
            counts[item.name] = sum(bool(v) for v in values)
    return counts


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s.source_id)
async def test_one_query_one_page(source: Any) -> None:
    adapter = default_registry().create(source.platform)
    default_registry().validate(source)
    context = AdapterContext(
        source.source_id, source.base_url, source.limits.page_size, source.options
    )
    request = adapter.build_request(context, source.queries[0], None)
    started = datetime.now(UTC)
    evidence: dict[str, Any] = {
        "kind": "live",
        "source_id": source.source_id,
        "started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository_commit": git("rev-parse", "HEAD"),
        "uncommitted_changes": bool(git("status", "--porcelain", "--", "backend", "config")),
        "request": {"method": request.method, "url": request.url, "params": dict(request.params)},
        "limits": {
            "page_size": source.limits.page_size,
            "attempt_timeout_s": source.limits.attempt_timeout_s,
            "max_retries": source.limits.max_retries,
        },
        "outcome": "failed",
    }
    clock = time.perf_counter()
    async with httpx.AsyncClient(
        timeout=None,  # noqa: S113  (the executor owns the deadline)
        trust_env=False,
        headers={"User-Agent": "fdh-discovery"},
    ) as client:
        executor = HttpExecutor(client, allowed_hosts=source.allowed_hosts, limits=source.limits)
        try:
            result = await executor.execute(request, adapter.classify)
            evidence["http_status"] = result.response.status
            evidence["response_bytes"] = len(result.response.body)
            page = adapter.parse(context, request, result.response, None)
            evidence.update(
                outcome="succeeded",
                total_declared=page.total_declared,
                datasets=len(page.datasets),
                distinct_identifiers=len({d.external_id for d in page.datasets}),
                rejected=dict(Counter(r.reason for r in page.rejected)),
                has_next_page=page.next_cursor is not None,
                filled_fields=filled(page.datasets),
            )
        except RequestFailed as error:
            evidence["error"] = {"code": error.code, "http_status": error.http_status}
            raise
        except Exception as error:
            evidence["error"] = {"code": type(error).__name__}
            raise
        finally:
            evidence["requests"] = executor.requests_sent
            evidence["elapsed_ms"] = round((time.perf_counter() - clock) * 1000)
            target = EVIDENCE[source.source_id] / f"live-{started:%Y-%m-%dT%H%M%SZ}.json"
            target.write_text(
                json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

    assert page.datasets, "the real source returned no valid dataset"
    assert len(page.datasets) <= source.limits.page_size
