"""`fdh discover` and `fdh runs list` end to end (AC-01, AC-02, AC-04, AC-09, AC-19).

Real PostgreSQL and the shipped Socrata adapter over a synthetic transport. No request leaves
the process and every response is invented.
"""

import asyncio
import itertools
import json
import time
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest

from fdh.cli.main import main
from fdh.settings.env import Settings

SOURCE = """
[[sources]]
source_id = "{source_id}"
provider = "Synthetic Provider"
platform = "{platform}"
base_url = "https://api.example.org/catalog"
allowed_hosts = ["api.example.org"]
official_url = "https://www.example.org"
verified_at = 2026-01-02
max_retries = 0
page_size = {page_size}
max_pages = {max_pages}
min_request_interval_s = {interval}
{extra}

[sources.options]
domains = "{domain}"
"""


class Provider:
    """A synthetic catalog: per term, a list of identifiers or an HTTP status."""

    def __init__(self, terms: dict[str, list[str] | int]) -> None:
        self.terms = terms
        self.titles: dict[str, str] = {}
        self.broken: set[str] = set()
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = request.url.params
        answer = self.terms[params["q"]]
        if isinstance(answer, int):
            return httpx.Response(answer)
        start = answer.index(params["scroll_id"]) + 1 if params["scroll_id"] else 0
        page = answer[start : start + int(params["limit"])]
        results = [
            {
                "resource": {
                    "id": identifier,
                    "type": "dataset",
                    "name": ""
                    if identifier in self.broken
                    else self.titles.get(identifier, f"Synthetic {identifier}"),
                },
                "metadata": {"domain": params["domains"], "license": "Synthetic License"},
                "permalink": f"https://{params['domains']}/d/{identifier}",
            }
            for identifier in page
        ]
        return httpx.Response(200, json={"results": results, "resultSetSize": len(answer)})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def config(
    tmp_path: Path,
    *terms: str,
    sources: tuple[str, ...] = ("alpha",),
    page_size: int = 2,
    max_pages: int = 5,
    domain: str = "data.example.org",
    platform: str = "socrata",
    interval: float = 0,
    extra: str = "",
) -> str:
    queries = "".join(f'\n[[sources.queries]]\nterm = "{term}"\n' for term in terms)
    text = "".join(
        SOURCE.format(
            source_id=source_id,
            platform=platform,
            page_size=page_size,
            max_pages=max_pages,
            domain=domain,
            interval=interval,
            extra=extra,
        )
        + queries
        for source_id in sources
    )
    path = tmp_path / "sources.toml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def query(database: str, statement: str) -> list[tuple[Any, ...]]:
    async def run() -> list[tuple[Any, ...]]:
        settings = Settings()
        connection = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password.get_secret_value() or None,
            database=database,
        )
        try:
            return [tuple(row) for row in await connection.fetch(statement)]
        finally:
            await connection.close()

    return asyncio.run(run())


def discover(path: str, provider: Provider, *selection: str) -> int:
    arguments = selection or ("--source", "alpha")
    return main(["discover", *arguments, "--config", path], transport=provider.transport)


TOTALS = (
    "SELECT (SELECT count(*) FROM datasets), (SELECT count(*) FROM dataset_observations), "
    "(SELECT count(*) FROM runs)"
)
RUNS = (
    "SELECT source_id, status::text, pages_processed, received, created, updated, unchanged, "
    "rejected, failures FROM runs ORDER BY started_at"
)


def test_discovery_persists_and_repeating_it_does_not_duplicate(
    migrated: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    provider = Provider({"budget": ["a-1", "a-2", "a-3"], "finance": ["a-3", "a-4"]})
    path = config(tmp_path, "budget", "finance")
    assert discover(path, provider) == 0
    assert query(migrated, TOTALS) == [(4, 5, 1)]
    output = capsys.readouterr().out
    assert "succeeded" in output
    assert "requests=3 pages=3 received=5 unique=4 created=4 updated=0 unchanged=0" in output
    assert 'term="budget" pages=2 total_declared=3 truncated=no' in output

    provider.titles["a-1"] = "Synthetic renamed"
    assert discover(path, provider) == 0
    assert query(migrated, TOTALS) == [(4, 10, 2)]
    assert query(migrated, RUNS)[-1] == ("alpha", "succeeded", 3, 5, 0, 1, 3, 0, 0)
    assert query(migrated, "SELECT title FROM datasets WHERE external_id = 'a-1'") == [
        ("Synthetic renamed",)
    ]
    assert query(
        migrated, "SELECT count(*) FROM datasets WHERE first_seen_run_id <> last_seen_run_id"
    ) == [(4,)]


def test_sources_are_synchronised_before_discovery(migrated: str, tmp_path: Path) -> None:
    assert discover(config(tmp_path, "budget"), Provider({"budget": []})) == 0
    assert query(migrated, "SELECT source_id, metadata_publication::text FROM sources") == [
        ("alpha", "undetermined")
    ]


def test_configuration_changes_the_requests_without_code(migrated: str, tmp_path: Path) -> None:
    provider = Provider({"budget": ["a-1", "a-2", "a-3"], "salud": ["b-1", "b-2", "b-3"]})
    assert discover(config(tmp_path, "budget"), provider) == 0
    path = config(tmp_path, "salud", page_size=1, max_pages=2, domain="other.example.org")
    assert discover(path, provider) == 0
    sent = [
        (r.url.host, r.url.params["domains"], r.url.params["q"], r.url.params["limit"])
        for r in provider.requests
    ]
    assert sent == [
        ("api.example.org", "data.example.org", "budget", "2"),
        ("api.example.org", "data.example.org", "budget", "2"),
        ("api.example.org", "other.example.org", "salud", "1"),
        ("api.example.org", "other.example.org", "salud", "1"),
    ]
    assert query(migrated, "SELECT truncated, total_declared FROM run_queries WHERE truncated") == [
        (True, 3)
    ]
    assert query(migrated, RUNS)[-1][1] == "succeeded"


def test_a_partial_run_keeps_valid_records_and_can_be_repeated(
    migrated: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    provider = Provider({"budget": ["a-1", "a-2"], "finance": 503})
    provider.broken = {"a-2"}
    path = config(tmp_path, "budget", "finance")
    assert discover(path, provider) == 3
    output = capsys.readouterr().out
    assert "partial" in output
    assert "rejected: missing_title=1" in output
    assert "error: code=http_error query=1 http_status=503 attempts=1" in output
    assert discover(path, provider) == 3
    assert query(migrated, "SELECT external_id FROM datasets") == [("a-1",)]
    assert query(migrated, RUNS)[0] == ("alpha", "partial", 1, 2, 1, 0, 0, 1, 1)


def test_a_failed_run_exits_with_four_and_changes_no_data(migrated: str, tmp_path: Path) -> None:
    path = config(tmp_path, "budget")
    assert discover(path, Provider({"budget": ["a-1"]})) == 0
    before = query(migrated, "SELECT external_id, title, last_seen_run_id FROM datasets")
    assert discover(path, Provider({"budget": 404})) == 4
    assert query(migrated, "SELECT external_id, title, last_seen_run_id FROM datasets") == before
    assert query(migrated, RUNS)[-1][1] == "failed"
    (errors,) = query(migrated, "SELECT errors FROM runs WHERE status = 'failed'")[0]
    assert json.loads(errors) == [
        {
            "code": "http_error",
            "message": "the provider answered with HTTP status 404",
            "query_index": 0,
            "http_status": 404,
            "attempts": 1,
        }
    ]


def test_all_records_rejected_is_a_failure(migrated: str, tmp_path: Path) -> None:
    provider = Provider({"budget": ["a-1"]})
    provider.broken = {"a-1"}
    assert discover(config(tmp_path, "budget"), provider) == 4
    assert query(migrated, RUNS) == [("alpha", "failed", 1, 1, 0, 0, 0, 1, 0)]


def test_all_sources_run_even_if_one_fails(migrated: str, tmp_path: Path) -> None:
    class FirstFails(Provider):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            answer = super().__call__(request)
            return httpx.Response(404) if len(self.requests) == 1 else answer

    provider = FirstFails({"budget": ["a-1"]})
    path = config(tmp_path, "budget", sources=("alpha", "beta"))
    assert discover(path, provider, "--all") == 4
    assert [row[:2] for row in query(migrated, RUNS)] == [
        ("alpha", "failed"),
        ("beta", "succeeded"),
    ]


def test_a_run_in_progress_exits_with_five_without_requests(
    migrated: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    provider = Provider({"budget": ["a-1"]})
    path = config(tmp_path, "budget")
    settings = Settings()
    loop = asyncio.new_event_loop()
    holder = loop.run_until_complete(
        asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password.get_secret_value() or None,
            database=migrated,
        )
    )
    try:
        loop.run_until_complete(
            holder.execute("SELECT pg_advisory_lock(hashtext('fdh.discover:alpha'))")
        )
        assert discover(path, provider) == 5
    finally:
        loop.run_until_complete(holder.close())
        loop.close()
    assert provider.requests == []
    assert "already in progress" in capsys.readouterr().err
    assert query(migrated, "SELECT count(*) FROM runs") == [(0,)]


@pytest.mark.parametrize(
    ("arguments", "platform", "message"),
    [
        (("--source", "unknown"), "socrata", "unknown source"),
        (("--source", "alpha"), "data360", "no adapter"),
        (("--all",), "data360", "no adapter"),
    ],
)
def test_unusable_selections_stop_before_any_request(
    migrated: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    arguments: tuple[str, ...],
    platform: str,
    message: str,
) -> None:
    provider = Provider({})
    path = config(tmp_path, "budget", platform=platform)
    assert discover(path, provider, *arguments) == 2
    assert message in capsys.readouterr().err
    assert provider.requests == []
    assert query(migrated, "SELECT count(*) FROM sources") == [(0,)]


def test_an_unsupported_option_stops_before_any_request(tmp_path: Path) -> None:
    provider = Provider({})
    path = config(tmp_path, "budget", domain="not a domain")
    assert discover(path, provider) == 2
    assert provider.requests == []


def test_source_and_all_are_exclusive_and_one_is_required() -> None:
    for arguments in (["discover"], ["discover", "--all", "--source", "alpha"]):
        with pytest.raises(SystemExit) as stopped:
            main(arguments)
        assert stopped.value.code == 2


def test_an_unreachable_database_is_a_runtime_error_without_requests_or_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FDH_DB_PORT", "1")
    monkeypatch.setenv("FDH_DB_PASSWORD", "fake-password-987654")
    provider = Provider({})
    assert discover(config(tmp_path, "budget"), provider) == 1
    assert provider.requests == []
    output = capsys.readouterr()
    assert "fake-password-987654" not in output.out + output.err
    assert main(["runs", "list"]) == 1


def test_runs_list_shows_recent_runs(
    migrated: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = config(tmp_path, "budget", sources=("alpha", "beta"), page_size=1, max_pages=1)
    assert discover(path, Provider({"budget": ["a-1", "a-2"]}), "--all") == 0
    capsys.readouterr()
    assert main(["runs", "list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    summaries = [line for line in lines if not line.startswith(" ")]
    assert [line.split()[2] for line in summaries] == ["beta", "alpha"]
    assert all(" succeeded " in line and "truncated=1" in line for line in summaries)
    assert main(["runs", "list", "--source", "alpha", "--limit", "1"]) == 0
    output = capsys.readouterr().out
    assert "alpha" in output
    assert "beta" not in output


def test_runs_list_without_runs(migrated: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["runs", "list"]) == 0
    assert "no runs" in capsys.readouterr().out


@pytest.mark.parametrize("limit", ["0", "101", "x"])
def test_runs_list_limit_is_bounded(limit: str) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["runs", "list", "--limit", limit])
    assert stopped.value.code == 2


METRICS = (
    "SELECT requests, duration_ms >= 0, persistence_ms >= 0, rejection_reasons::text "
    "FROM runs ORDER BY started_at DESC LIMIT 1"
)


def test_run_metrics_are_persisted_and_listed(
    migrated: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    provider = Provider({"budget": ["a-1", "a-2"], "finance": 503})
    provider.broken = {"a-2"}
    assert discover(config(tmp_path, "budget", "finance"), provider) == 3
    assert query(migrated, METRICS) == [(2, True, True, '{"missing_title": 1}')]
    capsys.readouterr()
    assert main(["runs", "list"]) == 0
    assert " requests=2 " in capsys.readouterr().out
    query(
        migrated,
        "UPDATE runs SET requests = NULL, duration_ms = NULL, persistence_ms = NULL, "
        "rejection_reasons = NULL",
    )
    assert main(["runs", "list"]) == 0
    assert " requests=- duration=- persistence=-" in capsys.readouterr().out


def test_requests_are_spaced_by_the_configured_interval(migrated: str, tmp_path: Path) -> None:
    starts: list[float] = []

    class Timed(Provider):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            starts.append(time.monotonic())
            return super().__call__(request)

    path = config(tmp_path, "budget", interval=0.2, page_size=1)
    assert discover(path, Timed({"budget": ["a-1", "a-2", "a-3"]})) == 0
    assert len(starts) == 3
    assert all(later - earlier >= 0.2 for earlier, later in itertools.pairwise(starts))


TOKEN_SETTING = 'app_token_env = "FDH_SYNTHETIC_APP_TOKEN"'
TOKEN = "fake-app-token-5566778899"


@pytest.mark.parametrize("value", [None, "", TOKEN])
def test_the_application_token_is_optional_and_never_exposed(
    migrated: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("FDH_SYNTHETIC_APP_TOKEN", raising=False)
    else:
        monkeypatch.setenv("FDH_SYNTHETIC_APP_TOKEN", value)
    provider = Provider({"budget": ["a-1"]})
    assert discover(config(tmp_path, "budget", extra=TOKEN_SETTING), provider) == 0
    sent = provider.requests[0].headers.get("x-app-token")
    assert sent == (value or None)
    output = capsys.readouterr()
    stored = query(
        migrated,
        "SELECT concat((SELECT json_agg(r) FROM runs r), "
        "(SELECT json_agg(o) FROM dataset_observations o), "
        "(SELECT json_agg(s) FROM sources s))",
    )
    assert TOKEN not in output.out + output.err + str(stored)


def test_a_malformed_token_stops_before_any_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FDH_SYNTHETIC_APP_TOKEN", "broken token value")
    monkeypatch.setenv("FDH_DB_PORT", "1")  # the database is not reached either
    provider = Provider({})
    assert discover(config(tmp_path, "budget", extra=TOKEN_SETTING), provider) == 2
    assert provider.requests == []
    output = capsys.readouterr()
    assert "FDH_SYNTHETIC_APP_TOKEN" in output.err
    assert "broken token value" not in output.out + output.err
