"""Shared helpers: config, paths, logging, database connection.

Design rule: every pipeline script imports from here so that configuration,
logging format and DB access are identical across the project.
"""
from __future__ import annotations

import logging
import os
import sys
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=None)
def load_config(config_name: str | None = None) -> dict:
    name = config_name or os.getenv("FLEETPULSE_CONFIG", "settings.yaml")
    if Path(name).name != name or not name.endswith(".yaml"):
        raise ValueError("FLEETPULSE_CONFIG must be a YAML filename inside configs/")
    config_path = ROOT / "configs" / name
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def path(key: str) -> Path:
    """Resolve a path declared under `paths:` in settings.yaml (created if missing)."""
    p = ROOT / load_config()["paths"][key]
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    return logger


def load_env_file() -> None:
    """Minimal .env loader (no extra dependency). Existing env vars win."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def pg_dsn() -> dict:
    load_env_file()
    return {
        "host": os.getenv("PG_HOST", "localhost"),
        "port": int(os.getenv("PG_PORT", "5432")),
        "dbname": os.getenv("PG_DB", "fleetpulse"),
        "user": os.getenv("PG_USER", "fleet"),
        "password": os.getenv("PG_PASSWORD", "fleet"),
    }


def pg_connect():
    import psycopg2

    return psycopg2.connect(**pg_dsn())


def sa_engine():
    from sqlalchemy import create_engine

    d = pg_dsn()
    return create_engine(f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}")


def kafka_bootstrap() -> str:
    load_env_file()
    return os.getenv("KAFKA_BOOTSTRAP", "localhost:19092")
