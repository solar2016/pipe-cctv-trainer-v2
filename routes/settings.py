"""设置路由。"""

import json
import os
from pathlib import Path

from flask import Blueprint, jsonify, request

from config import DATA_DIR

bp = Blueprint("settings", __name__)

SETTINGS_PATH = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "api_base": "",
    "api_key": "",
    "model": "gpt-4o-mini",
    "video_model": "",
    "temperature": 0.1,
    "fewshot_max": 8,
    "batch_concurrency": 3,
    "unknown_thresholds": {"BX": 0.55, "CJ": 0.65, "SG": 0.65, "ZA": 0.65, "JG": 0.65},
}


def _load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            merged = {**DEFAULT_SETTINGS, **saved}
            merged["unknown_thresholds"] = {**DEFAULT_SETTINGS["unknown_thresholds"], **(saved.get("unknown_thresholds") or {})}
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def _save_settings(settings: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_settings(settings: dict) -> None:
    from core import vision
    if settings.get("api_base"):
        os.environ["OPENAI_API_BASE_URL"] = settings["api_base"]
    if settings.get("api_key"):
        os.environ["OPENAI_API_KEY"] = settings["api_key"]
    if settings.get("model"):
        os.environ["VISION_MODEL"] = settings["model"]
    vision.TEMPERATURE = settings.get("temperature", 0.1)
    vision.FEWSHOT_MAX = settings.get("fewshot_max", 8)
    thresholds = settings.get("unknown_thresholds", {})
    for code, val in thresholds.items():
        if code in vision.UNKNOWN_ROUTE_THRESHOLDS:
            vision.UNKNOWN_ROUTE_THRESHOLDS[code] = val


# Apply on import
_apply_settings(_load_settings())


@bp.get("/api/settings")
def api_get_settings():
    s = _load_settings()
    s["api_key_masked"] = "***" if s.get("api_key") else ""
    s.pop("api_key", None)
    return jsonify(s)


@bp.post("/api/settings")
def api_save_settings():
    data = request.json or {}
    current = _load_settings()
    if "api_base" in data:
        current["api_base"] = str(data["api_base"]).strip()
    if "api_key" in data and data["api_key"] and data["api_key"] != "***":
        current["api_key"] = str(data["api_key"]).strip()
    if "model" in data:
        current["model"] = str(data["model"]).strip()
    if "video_model" in data:
        current["video_model"] = str(data["video_model"]).strip()
    if "temperature" in data:
        try:
            current["temperature"] = float(data["temperature"])
        except (TypeError, ValueError):
            pass
    if "fewshot_max" in data:
        try:
            current["fewshot_max"] = int(data["fewshot_max"])
        except (TypeError, ValueError):
            pass
    if "batch_concurrency" in data:
        try:
            current["batch_concurrency"] = int(data["batch_concurrency"])
        except (TypeError, ValueError):
            pass
    if "unknown_thresholds" in data and isinstance(data["unknown_thresholds"], dict):
        for k, v in data["unknown_thresholds"].items():
            if k in current["unknown_thresholds"]:
                try:
                    current["unknown_thresholds"][k] = float(v)
                except (TypeError, ValueError):
                    pass
    _save_settings(current)
    _apply_settings(current)
    return jsonify({"ok": True})


@bp.post("/api/settings/reset")
def api_reset_settings():
    _save_settings(dict(DEFAULT_SETTINGS))
    _apply_settings(dict(DEFAULT_SETTINGS))
    return jsonify({"ok": True})
