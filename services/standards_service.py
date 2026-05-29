"""标准文档管理：上传、AI解析、修正、激活。"""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import requests

from config import STANDARDS_DIR, get_api_base, get_api_key, get_model


def list_standards() -> list[dict[str, Any]]:
    if not STANDARDS_DIR.exists():
        return []
    results = []
    for f in sorted(STANDARDS_DIR.glob("*.json"), reverse=True):
        if f.name == "active.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "id": data.get("id", f.stem),
                "name": data.get("name", ""),
                "source_file": data.get("source_file", ""),
                "uploaded_at": data.get("uploaded_at", ""),
                "status": data.get("status", ""),
                "defect_count": len(data.get("defects", [])),
                "has_evaluation_formulas": bool(data.get("evaluation_formulas")),
            })
        except Exception:
            pass
    return results


def get_standard(standard_id: str) -> dict[str, Any] | None:
    path = STANDARDS_DIR / f"{standard_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_standard(standard_id: str, data: dict[str, Any]) -> None:
    path = STANDARDS_DIR / f"{standard_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_standard(standard_id: str) -> bool:
    path = STANDARDS_DIR / f"{standard_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def upload_and_parse_standard(file_bytes: bytes, filename: str, mime_type: str) -> dict[str, Any]:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    standard_id = f"std_{stamp}"
    parsed = _parse_document(file_bytes, mime_type, filename)
    data = {
        "id": standard_id,
        "name": parsed.get("name", filename),
        "source_file": filename,
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "parsed",
        "defects": parsed.get("defects", []),
        "evaluation_formulas": parsed.get("evaluation_formulas", {}),
        "evaluation_params": parsed.get("evaluation_params", {}),
        "distance_rules": parsed.get("distance_rules", {}),
    }
    save_standard(standard_id, data)
    return data


def update_standard(standard_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    data = get_standard(standard_id)
    if not data:
        return None
    for key in ("defects", "evaluation_formulas", "evaluation_params", "distance_rules", "name", "status"):
        if key in patch:
            data[key] = patch[key]
    save_standard(standard_id, data)
    return data


def get_active_standard() -> dict[str, Any] | None:
    active_path = STANDARDS_DIR / "active.json"
    if not active_path.exists():
        return None
    try:
        active = json.loads(active_path.read_text(encoding="utf-8"))
        return get_standard(active.get("standard_id", ""))
    except Exception:
        return None


def set_active_standard(standard_id: str) -> bool:
    data = get_standard(standard_id)
    if not data:
        return False
    active_path = STANDARDS_DIR / "active.json"
    active_path.write_text(json.dumps({
        "standard_id": standard_id,
        "activated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def _parse_document(file_bytes: bytes, mime_type: str, filename: str) -> dict[str, Any]:
    base_url = get_api_base()
    api_key = get_api_key()
    model = get_model()
    if not base_url or not api_key:
        raise RuntimeError("缺少 OPENAI_API_BASE_URL 或 OPENAI_API_KEY")

    url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"

    content: list[dict[str, Any]] = []
    if mime_type.startswith("image/"):
        data_url = f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode()}"
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    else:
        data_url = f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode()}"
        content.append({"type": "text", "text": f"以下是标准文档「{filename}」的内容，请解析其中的缺陷标准数据。"})

    content.append({"type": "text", "text": PARSE_PROMPT})

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "你是管道检测标准文档解析助手。从文档中提取结构化的缺陷标准数据。"},
            {"role": "user", "content": content},
        ],
    }

    resp = requests.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=120)
    resp.raise_for_status()
    result_text = resp.json()["choices"][0]["message"]["content"]

    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        start = result_text.find("{")
        end = result_text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(result_text[start:end + 1])
        raise RuntimeError("模型没有返回合法 JSON")


PARSE_PROMPT = """请从这份管道缺陷检测标准文档中，提取以下结构化数据。如果某些字段在文档中找不到，留空即可。

输出 JSON 格式：
{
  "name": "标准名称",
  "defects": [
    {
      "code": "PL",
      "name": "破裂",
      "category": "结构性缺陷",
      "definition": "定义",
      "evidence_cues": "证据特征",
      "recommendation": "修复建议",
      "grades": {
        "1": {"description": "1级描述", "score": 1},
        "2": {"description": "2级描述", "score": 3}
      }
    }
  ],
  "evaluation_formulas": {
    "structural": {
      "name": "管道结构性状况评估",
      "formula": "F = max(缺陷分值) × avg(缺陷分值)",
      "density_formula": "Sx = 缺陷长度 / 管段长度",
      "repair_index": "RI = 0.7×F + 0.1×K + 0.05×E + 0.15×T",
      "levels": {"I": {"range": "F≤1", "description": "..."}}
    },
    "functional": {
      "name": "管道功能性状况评估",
      "formula": "G = max(缺陷分值) × avg(缺陷分值)",
      "maintenance_index": "MI = 0.8×G + 0.15×K + 0.05×E",
      "levels": {"I": {"range": "G≤1", "description": "..."}}
    }
  },
  "evaluation_params": {
    "K": {"name": "地区重要性参数", "description": "...", "values": {}},
    "E": {"name": "管道重要性参数", "description": "...", "values": {}},
    "T": {"name": "土质影响参数", "description": "...", "values": {}}
  },
  "distance_rules": {
    "close_threshold": 1.5,
    "very_close_threshold": 1.0,
    "alpha": 1.1
  }
}

重要要求：
1. 每个缺陷类型必须包含完整的等级定义和对应的分值（score）。
2. 如果文档中有评估公式（结构性/功能性），必须提取。
3. 如果文档中有评估参数（K/E/T）的取值表，必须提取。
4. 如果文档中没有分值信息，根据等级严重程度合理推断：1级=1分，2级=3分，3级=5分，4级=10分。
5. 保持代码（code）与行业标准一致。
6. 只输出 JSON，不要其他文字。"""
