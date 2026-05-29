"""Prompt 优化服务。"""

from __future__ import annotations

import json
import time
from typing import Any

from services.sample_service import load_samples, load_predictions
from services.prompt_service import save_prompt, get_active_prompt
from core.vision import get_model, get_api_base, get_api_key

import requests


def analyze_confusion_and_suggest_prompt() -> dict[str, Any]:
    samples = load_samples()
    predictions = load_predictions()

    # 构建混淆对列表
    confusion_pairs: dict[str, dict[str, int]] = {}
    for sample in samples:
        pred = predictions.get(sample["id"])
        if not pred:
            continue
        defects = pred.get("defects") or []
        first = defects[0] if defects else {}
        predicted = str(first.get("code") or "").upper()
        expected = sample.get("defect_code", "").upper()
        if predicted != expected and predicted != "UNKNOWN" and expected != "UNKNOWN":
            pair_key = tuple(sorted([predicted, expected]))
            confusion_pairs.setdefault(pair_key, {"count": 0})
            confusion_pairs[pair_key]["count"] += 1

    if not confusion_pairs:
        return {"ok": True, "message": "无混淆需要优化"}

    # 按混淆次数排序
    sorted_pairs = sorted(confusion_pairs.items(), key=lambda x: x[1]["count"], reverse=True)

    # 调用大模型生成优化 prompt
    current_prompt = get_active_prompt() or ""
    pair_text = "\n".join(f"- {p[0][0]}↔{p[0][1]}: {p[1]['count']}次" for p in sorted_pairs[:10])

    optimization_prompt = f"""你是管道缺陷检测 prompt 优化专家。

当前混淆情况：
{pair_text}

请针对混淆最严重的前 3 对，生成具体的区分规则补充。

要求：
1. 每个混淆对给出明确的视觉区分要点
2. 基于管道 CCTV 图像的实际观察特征
3. 用简练的判断规则格式

只输出 JSON：
{{
  "new_rules": "补充的区分规则文本",
  "reason": "优化原因说明"
}}"""

    try:
        base_url = get_api_base()
        api_key = get_api_key()
        model = get_model()
        if not base_url or not api_key:
            return {"ok": False, "error": "缺少 API 配置"}

        url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "你是管道缺陷检测 prompt 优化专家。"},
                {"role": "user", "content": optimization_prompt},
            ],
        }
        resp = requests.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=60)
        resp.raise_for_status()
        result_text = resp.json()["choices"][0]["message"]["content"]
        result = json.loads(result_text)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    # 生成新 prompt
    new_rules = result.get("new_rules", "")
    current = get_active_prompt() or ""
    new_prompt = f"{current}\n\n## 补充区分规则\n\n{new_rules}"

    saved = save_prompt(new_prompt, reason=f"自动优化：{len(sorted_pairs)} 个混淆对")

    return {
        "ok": True,
        "confusion_pairs": len(sorted_pairs),
        "new_prompt_version": saved.get("version"),
        "optimization": result,
    }
