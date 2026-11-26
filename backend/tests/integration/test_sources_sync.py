"""`fdh sources sync`: revocation without discovery or external services (AC-27, AC-35).

External connections are blocked for the whole test suite. All sources are synthetic.
"""

import asyncio
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from fdh.cli.main import main
from fdh.settings.env import Settings

SOURCE = """
[[sources]]
source_id = "{source_id}"
provider = "Synthetic Provider"
platform = "socrata"
base_url = "https://api.example.org/catalog"
allowed_hosts = ["api.example.org"]
official_url = "https://www.example.org"
verified_at = 2026-01-02

[sources.metadata_publication]
value = "{value}"
{audit}

[[sources.queries]]
term = "budget"
"""
AUDIT = """declared_by = "maintainer"
declared_on = 2026-01-01
evidence = "https://example.org/{value}" """


def config(tmp_path: Path, *sources: tuple[str, str], audited: bool = True) -> str:
    blocks = [
        SOURCE.format(
            source_id=source_id,
            value=value,
            audit=AUDIT.format(value=value) if audited else "",
        )
        for source_id, value in sources
    ]
    path = tmp_path / "sources.toml"
    path.write_text("".join(blocks), encoding="utf-8")
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


PUBLICATION = "SELECT source_id, metadata_publication::text FROM sources ORDER BY 1"
DECISIONS = (
    "SELECT source_id, old_value, new_value, evidence, decided_by "
    "FROM permission_decisions ORDER BY id"
)


def sync(path: str) -> int:
    return main(["sources", "sync", "--config", path])


def test_sync_registers_and_is_idempotent(migrated: str, tmp_path: Path) -> None:
    path = config(tmp_path, ("alpha", "allowed"))
    assert sync(path) == 0
    assert sync(path) == 0
    assert query(migrated, PUBLICATION) == [("alpha", "allowed")]
    assert query(migrated, DECISIONS) == [
        ("alpha", "undetermined", "allowed", "https://example.org/allowed", "maintainer")
    ]


def test_revocation_takes_effect_without_discovery(migrated: str, tmp_path: Path) -> None:
    assert sync(config(tmp_path, ("alpha", "allowed"))) == 0
    assert sync(config(tmp_path, ("alpha", "denied"))) == 0
    assert query(migrated, PUBLICATION) == [("alpha", "denied")]
    assert query(migrated, "SELECT count(*) FROM runs") == [(0,)]
    assert query(migrated, DECISIONS)[-1][1:4] == (
        "allowed",
        "denied",
        "https://example.org/denied",
    )


def test_sync_never_changes_dataset_restrictions(migrated: str, tmp_path: Path) -> None:
    assert sync(config(tmp_path, ("alpha", "allowed"))) == 0
    query(
        migrated,
        "WITH r AS (INSERT INTO runs (id, source_id, status) "
        "VALUES (gen_random_uuid(), 'alpha', 'succeeded') RETURNING id) "
        "INSERT INTO datasets (id, source_id, external_id, title, first_seen_run_id, "
        "last_seen_run_id, metadata_hash, review_status, extraction_permission, "
        "access_conditions) SELECT gen_random_uuid(), 'alpha', 'x', 'Synthetic', r.id, r.id, "
        "'h', 'restricted', 'denied', 'synthetic condition' FROM r",
    )
    state = (
        "SELECT review_status::text, extraction_permission::text, "
        "redistribution_permission::text, access_conditions FROM datasets"
    )
    before = query(migrated, state)
    for value in ("denied", "allowed"):
        assert sync(config(tmp_path, ("alpha", value))) == 0
        assert query(migrated, state) == before
    assert before == [("restricted", "denied", "undetermined", "synthetic condition")]


def test_removed_source_keeps_data_and_becomes_undetermined(migrated: str, tmp_path: Path) -> None:
    assert sync(config(tmp_path, ("alpha", "allowed"), ("beta", "allowed"))) == 0
    assert sync(config(tmp_path, ("beta", "allowed"))) == 0
    assert query(migrated, PUBLICATION) == [("alpha", "undetermined"), ("beta", "allowed")]
    assert query(migrated, DECISIONS)[-1][4] == "fdh sources sync"


def test_unaudited_change_is_refused_and_nothing_changes(
    migrated: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert sync(config(tmp_path, ("alpha", "allowed"))) == 0
    path = config(tmp_path, ("alpha", "undetermined"), ("beta", "undetermined"), audited=False)
    assert sync(path) == 2
    assert "requires" in capsys.readouterr().err
    assert query(migrated, PUBLICATION) == [("alpha", "allowed")]


def test_unreachable_database_is_a_runtime_error_without_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FDH_DB_PORT", "1")
    monkeypatch.setenv("FDH_DB_PASSWORD", "fake-password-987654")
    assert sync(config(tmp_path, ("alpha", "allowed"))) == 1
    output = capsys.readouterr()
    assert "fake-password-987654" not in output.out + output.err


def test_invalid_configuration_stops_before_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FDH_DB_PORT", "1")
    path = tmp_path / "sources.toml"
    path.write_text("unexpected = 1\n", encoding="utf-8")
    assert sync(str(path)) == 2
