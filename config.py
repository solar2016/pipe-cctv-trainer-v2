from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("PIPE_CCTV_DATA_DIR", "/Volumes/os/Applications/pipe-cctv-trainer/data"))
SAMPLES_DIR = DATA_DIR / "samples"
STANDARDS_DIR = DATA_DIR / "standards"
EVALUATIONS_DIR = DATA_DIR / "evaluations"
PROMPTS_DIR = DATA_DIR / "prompts"
FEWSHOT_DIR = DATA_DIR / "fewshot"

ENV_PATH = Path(os.getenv("PIPE_CCTV_ENV_PATH", "/Volumes/os/Applications/.env"))

PORT = int(os.getenv("PORT", "8060"))


def load_env() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_api_base() -> str:
    load_env()
    return os.getenv("OPENAI_API_BASE_URL", "").rstrip("/")


def get_api_key() -> str:
    load_env()
    return os.getenv("OPENAI_API_KEY", "")


def get_model() -> str:
    load_env()
    return os.getenv("VISION_MODEL", "gpt-4o-mini")


def ensure_dirs() -> None:
    for d in [SAMPLES_DIR, STANDARDS_DIR, EVALUATIONS_DIR, PROMPTS_DIR, FEWSHOT_DIR]:
        d.mkdir(parents=True, exist_ok=True)
