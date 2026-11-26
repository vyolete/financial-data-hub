"""The optional application token comes from the environment and is never shown (AC-38)."""

import pytest

from fdh.settings.env import InvalidSecret, read_app_token

NAME = "FDH_SYNTHETIC_APP_TOKEN"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_an_absent_or_empty_variable_means_no_token(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv(NAME, raising=False)
    else:
        monkeypatch.setenv(NAME, value)
    assert read_app_token(NAME) is None


def test_a_token_is_returned_as_a_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(NAME, "fake-Token_123")
    token = read_app_token(NAME)
    assert token is not None
    assert token.get_secret_value() == "fake-Token_123"
    assert "fake-Token_123" not in f"{token!r} {token}"


@pytest.mark.parametrize(
    "value", ["fake token", "fake\ntoken", " fake-token", "fáke-token", "x" * 257]
)
def test_a_malformed_token_is_refused_without_showing_it(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(NAME, value)
    with pytest.raises(InvalidSecret) as error:
        read_app_token(NAME)
    assert NAME in str(error.value)
    assert value not in str(error.value)
