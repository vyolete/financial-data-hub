"""Settings taken from the environment. Secrets are never printed."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDH_", extra="ignore")

    config: Path = Path("config/sources.toml")
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "fdh"
    db_user: str = "fdh"
    db_password: SecretStr = SecretStr("")
    api_allowed_hosts: str = "127.0.0.1,localhost"
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.api_allowed_hosts.split(",") if host.strip()]
