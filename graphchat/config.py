from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class CorsConfig:
    origins: list[str]


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class DbConfig:
    path: str


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    cors: CorsConfig
    llm: LlmConfig
    db: DbConfig


def _load_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Config at {path} must be a JSON object.")
    return data


def ensure_config(cwd: Path | None = None) -> Path:
    root = cwd or Path.cwd()
    cfg_path = root / "config.json"
    example_path = root / "config.example.json"
    if cfg_path.exists():
        return cfg_path
    if not example_path.exists():
        raise FileNotFoundError(
            "Missing config.json and config.example.json in current working directory."
        )
    shutil.copyfile(example_path, cfg_path)
    return cfg_path


def load_config(cwd: Path | None = None) -> AppConfig:
    cfg_path = ensure_config(cwd)
    data = _load_json(cfg_path)
    try:
        cfg = AppConfig(
            server=ServerConfig(
                host=str(data["server"]["host"]),
                port=int(data["server"]["port"]),
            ),
            cors=CorsConfig(origins=[str(x) for x in data["cors"]["origins"]]),
            llm=LlmConfig(
                base_url=str(data["llm"]["base_url"]).rstrip("/"),
                api_key=str(data["llm"]["api_key"]),
                model=str(data["llm"]["model"]),
            ),
            db=DbConfig(path=str(data["db"]["path"])),
        )
        _validate_config(cfg)
        return cfg
    except KeyError as exc:
        raise ValueError(f"Missing required config key: {exc}") from exc


def _validate_config(cfg: AppConfig) -> None:
    if not cfg.llm.base_url.strip():
        raise ValueError("Invalid config: llm.base_url is required.")
    if not cfg.llm.model.strip():
        raise ValueError("Invalid config: llm.model is required.")
    key = cfg.llm.api_key.strip()
    if not key or key == "replace_me":
        raise ValueError(
            "Invalid config: llm.api_key is not configured. Set a real key in config.json."
        )
