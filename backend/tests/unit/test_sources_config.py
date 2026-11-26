"""config/sources.toml validation. All values here are synthetic."""

from datetime import date
from pathlib import Path

import pytest

from fdh.domain.permissions import Permission
from fdh.settings.sources import ConfigError, load_sources

BASE = """
[defaults]
page_size = 100
max_pages = 5
attempt_timeout_s = 10.0
max_retries = 3
max_retry_after_s = 60

[[sources]]
source_id = "synthetic-source"
provider = "Synthetic Provider"
platform = "socrata"
base_url = "https://api.example.org/catalog"
allowed_hosts = ["api.example.org"]
official_url = "https://www.example.org"
verified_at = 2026-01-02
{extra}

[sources.metadata_publication]
value = "allowed"
declared_by = "maintainer"
declared_on = 2026-01-01
evidence = "https://example.org/evidence"

[[sources.queries]]
term = "budget"
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sources.toml"
    path.write_text(text, encoding="utf-8")
    return path


def load(tmp_path: Path, text: str = BASE.format(extra="")) -> object:
    return load_sources(write(tmp_path, text))


def test_loads_defaults_and_unknown_values(tmp_path: Path) -> None:
    (source,) = load_sources(write(tmp_path, BASE.format(extra="")))
    limits = source.limits
    assert (limits.page_size, limits.max_pages, limits.attempt_timeout_s) == (100, 5, 10.0)
    assert (limits.max_retries, limits.max_retry_after_s) == (3, 60)
    assert source.publication.value is Permission.ALLOWED
    assert source.publication.declared_on == date(2026, 1, 1)
    assert source.queries[0].term == "budget"
    # Omitted licence and terms mean unknown, never an inferred permission.
    assert (source.license_name, source.license_url) == (None, None)
    assert (source.terms_url, source.terms_checked_on) == (None, None)
    assert source.redistribution_conditions is None


def test_source_can_override_limits_without_code_changes(tmp_path: Path) -> None:
    (source,) = load_sources(write(tmp_path, BASE.format(extra="page_size = 10\nmax_pages = 2")))
    assert (source.limits.page_size, source.limits.max_pages) == (10, 2)


def test_missing_publication_is_undetermined(tmp_path: Path) -> None:
    text = BASE.format(extra="")
    start = text.index("[sources.metadata_publication]")
    end = text.index("[[sources.queries]]")
    (source,) = load_sources(write(tmp_path, text[:start] + text[end:]))
    assert source.publication.value is Permission.UNDETERMINED


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('source_id = "synthetic-source"', 'source_id = "Bad Id"'),
        ('platform = "socrata"', 'platform = "unknown"'),
        ('base_url = "https://api.example.org/catalog"', 'base_url = "http://api.example.org/c"'),
        ('base_url = "https://api.example.org/catalog"', 'base_url = "https://other.example.org"'),
        (
            'base_url = "https://api.example.org/catalog"',
            'base_url = "https://user:pw@api.example.org/catalog"',
        ),
        ('allowed_hosts = ["api.example.org"]', "allowed_hosts = []"),
        ('official_url = "https://www.example.org"', 'official_url = "ftp://example.org"'),
        ('official_url = "https://www.example.org"', ""),
        ("verified_at = 2026-01-02", ""),
        ("page_size = 100", "page_size = 101"),
        ("page_size = 100", "page_size = 0"),
        ("max_pages = 5", "max_pages = 0"),
        ("max_pages = 5", "max_pages = 101"),
        ("attempt_timeout_s = 10.0", "attempt_timeout_s = 0"),
        ("max_retries = 3", "max_retries = 4"),
        ("max_retries = 3", "max_retries = -1"),
        ("max_retry_after_s = 60", "max_retry_after_s = -1"),
        ('evidence = "https://example.org/evidence"', ""),
        ('declared_by = "maintainer"', 'declared_by = "  "'),
        ("declared_on = 2026-01-01", ""),
        ('value = "allowed"', 'value = "yes"'),
        ('term = "budget"', 'term = "budget"\nunexpected = 1'),
        ('provider = "Synthetic Provider"', 'provider = "P"\napi_token = "x"'),
        ("[defaults]", "unexpected = true\n[defaults]"),
    ],
)
def test_rejects_invalid_configuration(tmp_path: Path, old: str, new: str) -> None:
    text = BASE.format(extra="")
    assert old in text
    with pytest.raises(ConfigError):
        load(tmp_path, text.replace(old, new, 1))


def test_rejects_duplicated_source_ids(tmp_path: Path) -> None:
    text = BASE.format(extra="")
    duplicated = text + text[text.index("[[sources]]") :]
    with pytest.raises(ConfigError, match="duplicated"):
        load(tmp_path, duplicated)


def test_changing_undetermined_requires_nothing_but_keeps_evidence(tmp_path: Path) -> None:
    text = BASE.format(extra="").replace('value = "allowed"', 'value = "undetermined"')
    (source,) = load_sources(write(tmp_path, text))
    assert source.publication.value is Permission.UNDETERMINED
    assert source.publication.declared_by == "maintainer"


def test_errors_do_not_echo_values(tmp_path: Path) -> None:
    text = BASE.format(extra='api_token = "super-secret-value"')
    with pytest.raises(ConfigError) as error:
        load(tmp_path, text)
    assert "super-secret-value" not in str(error.value)


@pytest.mark.parametrize("text", ["not = [valid", "", "[defaults]\n"])
def test_rejects_unreadable_or_empty_files(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError):
        load(tmp_path, text)


def test_missing_file_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_sources(tmp_path / "absent.toml")


def test_repository_configuration_is_valid() -> None:
    path = Path(__file__).resolve().parents[3] / "config/sources.toml"
    sources = load_sources(path)
    first = sources[0]
    assert first.source_id == "co-datos-gov"
    assert first.publication.value is Permission.ALLOWED
    assert first.terms_url and first.access_conditions and first.attribution


def test_the_interval_and_the_token_variable_are_configurable(tmp_path: Path) -> None:
    (default,) = load_sources(write(tmp_path, BASE.format(extra="")))
    assert (default.limits.min_request_interval_s, default.app_token_env) == (1.0, None)
    extra = 'min_request_interval_s = 2.5\napp_token_env = "FDH_SOCRATA_APP_TOKEN"'
    (source,) = load_sources(write(tmp_path, BASE.format(extra=extra)))
    assert source.limits.min_request_interval_s == 2.5
    assert source.app_token_env == "FDH_SOCRATA_APP_TOKEN"


@pytest.mark.parametrize(
    "extra",
    [
        "min_request_interval_s = -1",
        "min_request_interval_s = 61",
        # Only application token variables may be named: never another secret.
        'app_token_env = "FDH_DB_PASSWORD"',
        'app_token_env = "HOME"',
        'app_token_env = "fdh_app_token"',
        'app_token_env = ""',
        'app_token = "a-literal-token"',
    ],
)
def test_rejects_an_invalid_interval_or_token_setting(tmp_path: Path, extra: str) -> None:
    with pytest.raises(ConfigError) as error:
        load(tmp_path, BASE.format(extra=extra))
    assert "a-literal-token" not in str(error.value)
