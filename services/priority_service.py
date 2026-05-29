"""优先级分析：调用大模型读报告，判断当前最需解决的 1-2 个重点维度。"""

from __future__ import annotations

import json
from typing import Any

from config import get_api_base, get_api_key, get_model


def analyze_priorities(report: dict[str, Any]) -> dict[str, Any]:
    """大模型分析报告，输出重点维度和策略建议。"""
    prompt = _build_analysis_prompt(report)

    try:
        result = _call_llm(prompt)
    except Exception as e:
        # 降级到规则分析
        result = _fallback_analysis(report)

    result["report_id"] = report.get("evaluation_id", "")
    return result


def _build_analysis_prompt(report: dict[str, Any]) -> str:
    metrics = report.get("metrics", {})
    confusion_pairs = report.get("confusion_pairs", [])
    summary = report.get("summary", "")
    prompt_version = report.get("prompt_version", "unknown")

    # 整理各类别指标
    code_metrics = []
    for code, m in metrics.items():
        if code == "macro_avg":
            continue
        if m.get("support", 0) > 0:
            code_metrics.append(
                f"  {code}: 支持度={m['support']}, 精确率={m['precision']:.3f}, "
                f"召回率={m['recall']:.3f}, F1={m['f1']:.3f}"
            )

    overall = metrics.get("macro_avg", {})

    # 整理混淆对
    confusion_text = "\n".join(
        f"  {p['true_code']}→{p['pred_code']}: {p['count']}次"
        for p in confusion_pairs[:10]
    ) or "  无显著混淆对"

    return f"""你是排水管道 CCTV 缺陷检测系统的优化分析专家。

当前系统状态：
- Prompt 版本: {prompt_version}
- 总体准确率: {overall.get('accuracy', 0):.3f}
- 宏平均 F1: {overall.get('f1', 0):.3f}

各类别指标：
{chr(10).join(code_metrics)}

主要混淆对：
{confusion_text}

报告摘要：
{summary}

---

请分析当前系统最需要解决的 1-2 个重点维度。

可选的优化维度：
1. **confusion** — 类别间混淆严重，需要补充区分特征 + Few-Shot
2. **unknown_problems** — UNKNOWN 缺陷泛滥或误判，需要扩充分类体系 + 输出规范
3. **image_quality** — 图像质量导致误判，需要强化质量自评 + 降权规则
4. **multi_defect** — 多缺陷遗漏，需要增加共生检测指引
5. **low_recall** — 特定类别召回率过低，需要补充正例
6. **low_precision** — 特定类别精确率过低，需要补充反例
7. **overconfident** — 过度自信（高置信但错误多），需要校准策略

判断依据：
- 混淆对数量多且集中在某些类别 → confusion
- UNKNOWN 的支持度高或误判率高 → unknown_problems
- 某些类别召回率极低（<0.4）→ low_recall
- 某些类别精确率极低（<0.4）→ low_precision
- 高置信度但 F1 低 → overconfident
- 多个类别同时表现差 → 可能是图像质量问题 → image_quality

请只输出 JSON：
{{
  "focus_dimensions": [
    {{
      "dimension": "维度代码",
      "severity": "high/medium/low",
      "affected_codes": ["相关缺陷代码"],
      "evidence": "判断依据（引用具体数据）",
      "strategy": "具体优化策略",
      "expected_impact": "预期改善效果"
    }}
  ],
  "summary": "一句话总结当前最该做什么",
  "skip_optimization": false,
  "skip_reason": ""
}}

注意：
1. 最多输出 2 个重点维度，聚焦最有杠杆效应的
2. 如果所有维度都表现良好（宏平均 F1 > 0.85 且无明显短板），可以 skip_optimization=true
3. strategy 要具体到可执行动作，不要泛泛而谈"""


def _call_llm(prompt: str) -> dict[str, Any]:
    import requests

    base_url = get_api_base()
    api_key = get_api_key()
    model = get_model()

    if not base_url or not api_key:
        raise RuntimeError("缺少 API 配置")

    url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "你是缺陷检测系统优化分析专家，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
    }

    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _fallback_analysis(report: dict[str, Any]) -> dict[str, Any]:
    """规则降级分析：当 LLM 不可用时。"""
    metrics = report.get("metrics", {})
    confusion_pairs = report.get("confusion_pairs", [])
    overall = metrics.get("macro_avg", {})
    focus = []

    # 检查混淆
    if len(confusion_pairs) > 3:
        codes = set()
        for p in confusion_pairs[:5]:
            codes.add(p["true_code"])
            codes.add(p["pred_code"])
        focus.append({
            "dimension": "confusion",
            "severity": "high" if len(confusion_pairs) > 8 else "medium",
            "affected_codes": list(codes)[:6],
            "evidence": f"{len(confusion_pairs)} 个混淆对",
            "strategy": "为高混淆类别添加 fewshot 锚点（正例+反例）",
            "expected_impact": "减少误判，提升整体 F1",
        })

    # 检查低召回
    low_recall = [
        (code, m) for code, m in metrics.items()
        if code != "macro_avg" and m.get("support", 0) > 0 and m.get("recall", 1) < 0.4
    ]
    if low_recall:
        focus.append({
            "dimension": "low_recall",
            "severity": "high",
            "affected_codes": [code for code, _ in low_recall[:4]],
            "evidence": f"{', '.join(code for code, _ in low_recall[:4])} 召回率 < 0.4",
            "strategy": "为低召回类别补充正例 fewshot",
            "expected_impact": "提升漏检识别能力",
        })

    # 检查低精确率
    low_prec = [
        (code, m) for code, m in metrics.items()
        if code != "macro_avg" and m.get("support", 0) > 0 and m.get("precision", 1) < 0.4
    ]
    if low_prec and not low_recall:
        focus.append({
            "dimension": "low_precision",
            "severity": "medium",
            "affected_codes": [code for code, _ in low_prec[:4]],
            "evidence": f"{', '.join(code for code, _ in low_prec[:4])} 精确率 < 0.4",
            "strategy": "为低精确率类别补充反例 fewshot",
            "expected_impact": "减少误报",
        })

    if not focus:
        return {
            "focus_dimensions": [],
            "summary": "当前指标良好，无需优化",
            "skip_optimization": True,
            "skip_reason": "宏平均 F1 > 0.85 且无明显短板",
        }

    return {
        "focus_dimensions": focus[:2],
        "summary": f"重点解决: {', '.join(f['dimension'] for f in focus[:2])}",
        "skip_optimization": False,
        "skip_reason": "",
    }
