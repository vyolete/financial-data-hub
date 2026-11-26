"""Structured logs identify the run and never carry credentials (AC-24)."""

import io
import json
import logging
from collections.abc import Iterator

import pytest

from fdh.observability.logging import configure_logging, run_context

FAKE = "fake-credential-123456"


@pytest.fixture
def stream() -> Iterator[io.StringIO]:
    buffer = io.StringIO()
    root = logging.getLogger()
    previous, level = list(root.handlers), root.level
    configure_logging("INFO", buffer)
    yield buffer
    root.handlers, root.level = previous, level


def records(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_log_line_is_json_with_run_id(stream: io.StringIO) -> None:
    log = logging.getLogger("fdh.test")
    with run_context("run-42"):
        log.info("page stored", extra={"event": "page_stored", "source_id": "synthetic"})
    log.info("outside")
    inside, outside = records(stream)
    assert inside["run_id"] == "run-42"
    assert inside["event"] == "page_stored"
    assert inside["source_id"] == "synthetic"
    assert inside["level"] == "INFO"
    assert str(inside["timestamp"]).endswith("+00:00")
    assert "run_id" not in outside


@pytest.mark.parametrize(
    "key", ["password", "api_key", "token", "Authorization", "client_secret", "cookie", "headers"]
)
def test_sensitive_fields_are_hidden(stream: io.StringIO, key: str) -> None:
    logging.getLogger("fdh.test").info("x", extra={key: FAKE, "nested": {key: FAKE}})
    assert FAKE not in stream.getvalue()


@pytest.mark.parametrize(
    "message",
    [
        f"password={FAKE}",
        f"token: {FAKE}",
        f"api_key='{FAKE}'",
        f"Authorization: Bearer {FAKE}",
        f"postgresql+asyncpg://user:{FAKE}@db:5432/fdh",
        f"GET https://example.org/x?app_token={FAKE}&q=1",
    ],
)
def test_credentials_in_messages_are_hidden(stream: io.StringIO, message: str) -> None:
    logging.getLogger("fdh.test").warning(message)
    logging.getLogger("fdh.test").warning("%s", message)
    assert FAKE not in stream.getvalue()


def test_exceptions_are_summarised_without_credentials(stream: io.StringIO) -> None:
    try:
        raise RuntimeError(f"cannot connect with password={FAKE}")
    except RuntimeError:
        logging.getLogger("fdh.test").exception("failed")
    (record,) = records(stream)
    assert record["error_type"] == "RuntimeError"
    assert FAKE not in stream.getvalue()
    assert "Traceback" not in stream.getvalue()


def test_bodies_are_never_logged(stream: io.StringIO) -> None:
    logging.getLogger("fdh.test").info("x", extra={"body": FAKE, "response_body": FAKE})
    assert FAKE not in stream.getvalue()


@pytest.mark.parametrize("name", ["uvicorn", "uvicorn.error", "uvicorn.access", "alembic"])
def test_server_and_migration_loggers_share_the_json_handler(name: str) -> None:
    third_party = logging.getLogger(name)
    own = logging.StreamHandler(io.StringIO())
    previous = (list(third_party.handlers), third_party.propagate, third_party.level)
    root = logging.getLogger()
    root_state = (list(root.handlers), root.level)
    third_party.handlers, third_party.propagate = [own], False
    buffer = io.StringIO()
    try:
        configure_logging("INFO", buffer)
        third_party.info("GET /health?token=%s", FAKE, extra={"color_message": "x"})
    finally:
        third_party.handlers, third_party.propagate, third_party.level = previous
        root.handlers, root.level = root_state
    (record,) = records(buffer)
    assert record["logger"] == name
    assert "color_message" not in record
    assert FAKE not in buffer.getvalue()
