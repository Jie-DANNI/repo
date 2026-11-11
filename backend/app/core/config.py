"""全局配置：所有敏感信息一律从环境变量读取，禁止硬编码。"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # 依次尝试：backend/.env（本地从 backend 目录启动）→ ../.env（项目根）
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库
    database_url: str = "postgresql+asyncpg://memoloop:memoloop_dev_pwd@localhost:5433/memoloop"

    # 大模型（OpenAI 协议兼容）
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # Embedding
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # 认证
    jwt_secret: str = "dev-only-secret"
    jwt_expire_days: int = 7

    # 其他
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_max_mb: int = 50

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
