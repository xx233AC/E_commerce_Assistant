from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pg_host: str = "127.0.0.1"
    pg_port: int = Field(default=5432, ge=1, le=65535)
    pg_user: str = "commerce"
    pg_password: SecretStr
    pg_database: str = "commerce"
    jwt_secret: SecretStr = Field(min_length=64)
    minio_endpoint: str = "127.0.0.1:19000"
    minio_public_endpoint: str = "127.0.0.1:19000"
    minio_access_key: SecretStr
    minio_secret_key: SecretStr
    minio_bucket: str = "ecom-assistant-private"
    minio_secure: bool = False
    public_base_url: str = "http://127.0.0.1:5173"
    outbound_allowed_hosts: str = "api.openai.com,api.deepseek.com,dashscope.aliyuncs.com,open.bigmodel.cn"
    worker_poll_seconds: float = 2.0
    demo_enabled: bool = False

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.pg_user,
            password=self.pg_password.get_secret_value(),
            host=self.pg_host,
            port=self.pg_port,
            database=self.pg_database,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
