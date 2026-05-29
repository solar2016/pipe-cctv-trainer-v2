"""Prompt 版本管理。"""

from __future__ import annotations

import json
import time
from typing import Any

from config import PROMPTS_DIR


def list_prompts() -> list[dict[str, Any]]:
    if not PROMPTS_DIR.exists():
        return []
    prompts = []
    for f in sorted(PROMPTS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            prompts.append({
                "version": data.get("version", f.stem),
                "created_at": data.get("created_at", ""),
                "reason": data.get("reason", ""),
                "is_active": data.get("is_active", False),
            })
        except Exception:
            pass
    return prompts


def get_prompt(version: str) -> dict[str, Any] | None:
    path = PROMPTS_DIR / f"{version}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_active_prompt() -> str | None:
    for f in PROMPTS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("is_active"):
                return data.get("prompt_text", "")
        except Exception:
            pass
    return None


def get_active_prompt_info() -> dict[str, Any] | None:
    for f in PROMPTS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("is_active"):
                return {
                    "version": data.get("version", f.stem),
                    "reason": data.get("reason", ""),
                }
        except Exception:
            pass
    return None


def set_active_prompt(version: str) -> bool:
    path = PROMPTS_DIR / f"{version}.json"
    if not path.exists():
        return False

    # 先取消所有活跃
    for f in PROMPTS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("is_active"):
                data["is_active"] = False
                f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # 激活目标
    data = json.loads(path.read_text(encoding="utf-8"))
    data["is_active"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def save_prompt(prompt_text: str, reason: str = "", version: str | None = None) -> dict[str, Any]:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    if not version:
        version = f"auto_{int(time.time())}"
    data = {
        "version": version,
        "prompt_text": prompt_text,
        "reason": reason,
        "is_active": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path = PROMPTS_DIR / f"{version}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def delete_prompt(version: str) -> bool:
    path = PROMPTS_DIR / f"{version}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def get_prompt_diff(version_a: str, version_b: str) -> dict[str, Any]:
    """对比两个 prompt 版本的差异。"""
    a = get_prompt(version_a)
    b = get_prompt(version_b)
    if not a or not b:
        return {"error": "版本不存在"}

    text_a = a.get("prompt_text", "")
    text_b = b.get("prompt_text", "")

    # 简单行级 diff
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    added = [l for l in lines_b if l not in lines_a]
    removed = [l for l in lines_a if l not in lines_b]

    # 找新增内容（b 有 a 没有的连续段）
    # 用最长公共子序列简化：只报告差异
    return {
        "version_a": version_a,
        "version_b": version_b,
        "length_a": len(text_a),
        "length_b": len(text_b),
        "added_lines": len(added),
        "removed_lines": len(removed),
        "added": added[:50],  # 最多显示50行
        "removed": removed[:50],
        "is_newer": b.get("created_at", "") > a.get("created_at", ""),
    }


def list_prompts_with_details() -> list[dict[str, Any]]:
    """列出所有 prompt 版本，含详细信息。"""
    if not PROMPTS_DIR.exists():
        return []
    prompts = []
    for f in sorted(PROMPTS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            prompts.append({
                "version": data.get("version", f.stem),
                "created_at": data.get("created_at", ""),
                "reason": data.get("reason", ""),
                "is_active": data.get("is_active", False),
                "prompt_length": len(data.get("prompt_text", "")),
                "prompt_preview": data.get("prompt_text", "")[:200],
            })
        except Exception:
            pass
    return prompts


def list_change_logs() -> list[dict[str, Any]]:
    """列出所有优化变更记录。"""
    from config import EVALUATIONS_DIR
    if not EVALUATIONS_DIR.exists():
        return []
    logs = []
    for f in sorted(EVALUATIONS_DIR.glob("prompt_change_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            logs.append(data)
        except Exception:
            pass
    return logs
