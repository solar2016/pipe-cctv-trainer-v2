"""定向优化器：根据重点维度自动更新 Prompt / Few-Shot / 知识库。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from pathlib import Path

from config import PROMPTS_DIR, FEWSHOT_DIR, SAMPLES_DIR, EVALUATIONS_DIR
from config import get_api_base, get_api_key, get_model


def run_optimization(focus_dimensions: list[dict], report: dict[str, Any]) -> dict[str, Any]:
    """根据重点维度执行定向优化。"""
    results = []

    for dim in focus_dimensions:
        dimension = dim.get("dimension", "")
        strategy = dim.get("strategy", "")
        affected_codes = dim.get("affected_codes", [])

        if dimension == "confusion":
            r = _optimize_for_confusion(affected_codes, strategy, report)
        elif dimension == "unknown_problems":
            r = _optimize_for_unknown(strategy, report)
        elif dimension == "low_recall":
            r = _optimize_for_low_recall(affected_codes, strategy, report)
        elif dimension == "low_precision":
            r = _optimize_for_low_precision(affected_codes, strategy, report)
        elif dimension == "overconfident":
            r = _optimize_for_overconfident(affected_codes, strategy, report)
        elif dimension == "multi_defect":
            r = _optimize_for_multi_defect(strategy, report)
        elif dimension == "image_quality":
            r = _optimize_for_image_quality(strategy, report)
        else:
            r = {"dimension": dimension, "status": "skipped", "reason": "未知维度"}

        results.append(r)

    # 保存优化记录
    _save_optimization_record(results, focus_dimensions)

    return {
        "ok": True,
        "optimizations": results,
        "applied_count": sum(1 for r in results if r.get("status") == "applied"),
    }


def _optimize_for_confusion(codes: list, strategy: str, report: dict) -> dict:
    """针对混淆：从预测数据提取真实特征差异，生成具体区分规则。"""
    from services.sample_service import load_samples, load_predictions

    pairs = report.get("confusion_pairs", [])
    relevant_pairs = [
        p for p in pairs
        if p["true_code"] in codes or p["pred_code"] in codes
    ]

    samples = load_samples()
    predictions = load_predictions()

    # 按混淆对收集特征
    pair_features: dict[tuple[str, str], dict] = {}
    for p in relevant_pairs:
        tc, pc = p["true_code"], p["pred_code"]
        key = (tc, pc)
        if key not in pair_features:
            pair_features[key] = {"true_features": [], "pred_features": [], "true_obs": [], "pred_obs": []}

    for sample in samples:
        sid = sample.get("id", "")
        true_code = sample.get("defect_code", "").upper()
        pred = predictions.get(sid, {})
        defects = pred.get("defects", [])
        first = defects[0] if defects else {}
        pred_code = str(first.get("code", "")).upper()
        features = first.get("visible_features", [])
        obs = pred.get("observation", {})

        # 检查这个样本是否属于某个混淆对
        for (tc, pc), data in pair_features.items():
            if true_code == tc and pred_code == pc:
                data["true_features"].extend(features)
                if obs:
                    data["pred_obs"].append(obs)
            elif true_code == pc and pred_code == tc:
                data["pred_features"].extend(features)
                if obs:
                    data["true_obs"].append(obs)

    # 从特征中提取区分规则
    rules = []
    for (tc, pc), data in pair_features.items():
        true_feats = [f for f in data["true_features"] if f and len(f) > 3]
        pred_feats = [f for f in data["pred_features"] if f and len(f) > 3]

        # 统计词频，找出高频特征词
        true_top = _top_terms(true_feats, 3)
        pred_top = _top_terms(pred_feats, 3)

        count = next((p["count"] for p in relevant_pairs if p["true_code"] == tc and p["pred_code"] == pc), 0)

        rule = f"【{tc}→{pc} 混淆{count}次】"
        if true_top:
            rule += f"\n  {tc}常见特征：{', '.join(true_top)}"
        if pred_top:
            rule += f"\n  {pc}常见特征：{', '.join(pred_top)}"

        # 从 taxonomy 获取定义差异和区分指引
        from core.taxonomy import get_defects
        defects = get_defects()
        tc_def = defects.get(tc, {})
        pc_def = defects.get(pc, {})
        if tc_def.get("name") and pc_def.get("name"):
            rule += f"\n  {tc}={tc_def['name']}，{pc}={pc_def['name']}"
            # 基于混淆方向给出判断指引
            if tc in ("ZA",) and pc in ("CJ",):
                rule += "\n  → 关键区分：看位置——管壁上的独立外来物=ZA，管底连续平缓堆积=CJ"
            elif tc in ("BX",) and pc in ("TJ",):
                rule += "\n  → 关键区分：看轮廓——管壁整体变形（截面失圆）=BX，接口处纵向分离=TJ"
            elif tc in ("ZA",) and pc in ("JG",):
                rule += "\n  → 关键区分：看边界——与管壁有明确边界=ZA，与管壁融为一体=JG"
            elif tc in ("ZA",) and pc in ("UNKNOWN",):
                rule += "\n  → 能看到任何附着物/堆积物/外来物就给ZA，UNKNOWN仅用于完全无法辨认"
            elif tc in ("CJ",) and pc in ("UNKNOWN",):
                rule += "\n  → 管底有堆积物就给CJ，不要因为画面模糊就退回UNKNOWN"
            elif tc in ("SG",) and pc in ("UNKNOWN",):
                rule += "\n  → 有纤维状/须状特征就给SG，不要轻易退回UNKNOWN"

        rules.append(rule)

    prompt_addition = "## 易混淆类别区分规则（基于实际混淆数据）\n\n" + "\n\n".join(rules) if rules else ""

    fewshot_suggestions = _find_candidates_for_codes(codes, relevant_pairs)

    return {
        "dimension": "confusion",
        "status": "applied",
        "prompt_addition": prompt_addition,
        "fewshot_suggestions": fewshot_suggestions,
        "affected_codes": codes,
    }


def _top_terms(features: list[str], n: int = 3) -> list[str]:
    """从特征列表中提取高频关键词。"""
    from collections import Counter
    words = []
    for f in features:
        # 简单分词：按标点和空格分割
        import re
        tokens = re.split(r'[，、；。\s]+', f)
        words.extend([t.strip() for t in tokens if len(t.strip()) >= 2])
    counter = Counter(words)
    return [word for word, _ in counter.most_common(n)]


def _optimize_for_unknown(strategy: str, report: dict) -> dict:
    """针对 UNKNOWN 泛滥：补充输出规范。"""
    prompt_addition = """
补充规范：
- 如果图像中能看到任何异常特征（颜色变化、纹理异常、形状改变），必须给出具体缺陷代码，不能用 UNKNOWN
- UNKNOWN 仅用于：图像完全无法辨认、或特征完全矛盾无法区分的情况
- 多个特征同时存在时，输出主缺陷 + 次要特征列表，不要用 UNKNOWN"""
    return {
        "dimension": "unknown_problems",
        "status": "applied",
        "prompt_addition": prompt_addition.strip(),
        "fewshot_suggestions": [],
    }


def _optimize_for_low_recall(codes: list, strategy: str, report: dict) -> dict:
    """针对低召回率：补充正例 fewshot。"""
    suggestions = _find_candidates_for_codes(codes, [], anchor_types=["positive"])

    return {
        "dimension": "low_recall",
        "status": "applied",
        "prompt_addition": "",
        "fewshot_suggestions": suggestions,
    }


def _optimize_for_low_precision(codes: list, strategy: str, report: dict) -> dict:
    """针对低精确率：补充反例 fewshot。"""
    suggestions = _find_candidates_for_codes(codes, [], anchor_types=["negative"])

    return {
        "dimension": "low_precision",
        "status": "applied",
        "prompt_addition": "",
        "fewshot_suggestions": suggestions,
    }


def _optimize_for_overconfident(codes: list, strategy: str, report: dict) -> dict:
    """针对过度自信：添加置信度校准提示。"""
    prompt_addition = """
置信度校准要求：
- 置信度应反映证据强度，而非主观确信
- 如果只看到 1 个支持特征，置信度不应超过 0.7
- 如果特征描述模糊（如"可能"、"疑似"），置信度不应超过 0.6
- 只有多个独立特征同时支持时，才能给出 >0.8 的置信度"""

    return {
        "dimension": "overconfident",
        "status": "applied",
        "prompt_addition": prompt_addition.strip(),
        "fewshot_suggestions": [],
    }


def _optimize_for_multi_defect(strategy: str, report: dict) -> dict:
    """针对多缺陷遗漏：增加共生检测指引。"""
    prompt_addition = """
共生缺陷检测指引：
- 管道缺陷常成对出现：CJ（沉积）常伴随 JG（结垢），PL（破裂）常伴随 CW（错位）
- 如果在管底发现沉积物，同时检查管壁是否有结垢
- 如果发现破裂，同时检查接口是否有错位
- 扫描阶段发现多个可疑区域时，必须独立输出每个缺陷，不要合并"""

    return {
        "dimension": "multi_defect",
        "status": "applied",
        "prompt_addition": prompt_addition.strip(),
        "fewshot_suggestions": [],
    }


def _optimize_for_image_quality(strategy: str, report: dict) -> dict:
    """针对图像质量问题：添加质量自评和降权规则。"""
    prompt_addition = """
图像质量自评：
- 在输出中增加 image_quality 字段：good/fair/poor
- poor 质量时：置信度上限 0.5，必须标记 needs_human_review=true
- fair 质量时：置信度上限 0.7
- 质量判断依据：光照是否均匀、是否有强反光/深阴影、管壁是否清晰可辨"""

    return {
        "dimension": "image_quality",
        "status": "applied",
        "prompt_addition": prompt_addition.strip(),
        "fewshot_suggestions": [],
    }


def apply_optimizations_to_prompt(optimizations: list[dict]) -> dict[str, Any]:
    """将优化结果应用到当前 prompt，生成带变更记录的新版本。"""
    from services.prompt_service import get_active_prompt, get_active_prompt_info, save_prompt

    current_prompt = get_active_prompt()
    if not current_prompt:
        return {"ok": False, "error": "无活跃 prompt"}

    current_info = get_active_prompt_info()
    base_version = current_info.get("version", "unknown") if current_info else "unknown"

    additions = [o.get("prompt_addition", "") for o in optimizations if o.get("prompt_addition")]
    if not additions:
        return {"ok": True, "message": "无 prompt 修改", "new_version": base_version}

    new_prompt = current_prompt + "\n\n" + "\n\n".join(additions)

    # 保存为新版本
    version = f"auto_opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dimensions = [o["dimension"] for o in optimizations if o.get("dimension")]
    fewshot_count = sum(len(o.get("fewshot_suggestions", [])) for o in optimizations)
    reason = "自动优化：" + ", ".join(dimensions)
    if fewshot_count:
        reason += f"（{fewshot_count}个fewshot建议待确认）"

    prompt_data = save_prompt(new_prompt, version=version, reason=reason)

    # 保存变更记录（方便回溯）
    change_log = {
        "version": version,
        "base_version": base_version,
        "timestamp": datetime.now().isoformat(),
        "dimensions": dimensions,
        "additions": additions,
        "fewshot_count": fewshot_count,
        "prompt_length": len(new_prompt),
    }
    EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = EVALUATIONS_DIR / f"prompt_change_{version}.json"
    log_path.write_text(json.dumps(change_log, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "new_version": version,
        "base_version": base_version,
        "reason": reason,
        "dimensions": dimensions,
        "prompt_preview": new_prompt[-500:],  # 预览最后500字符
    }


def get_optimization_history() -> list[dict]:
    """获取优化历史。"""
    history_file = EVALUATIONS_DIR / "optimization_history.json"
    if not history_file.exists():
        return []
    try:
        return json.loads(history_file.read_text(encoding="utf-8"))
    except Exception:
        return []


def _find_candidates_for_codes(
    codes: list[str],
    confusion_pairs: list[dict] | None = None,
    anchor_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """为指定缺陷代码查找候选样本，附带图片路径。"""
    from services.sample_service import load_samples, load_predictions, load_fewshot_anchors

    samples = load_samples()
    predictions = load_fewshot_anchors_data = load_predictions()
    existing = load_fewshot_anchors()
    existing_ids = set()
    for code_anchors in existing.values():
        for a in code_anchors:
            existing_ids.add(a.get("sample_id", ""))

    if anchor_types is None:
        anchor_types = ["positive", "hard", "negative"]

    # 构建混淆对索引：code -> 被误判为哪些
    confusion_map: dict[str, set[str]] = {}
    if confusion_pairs:
        for p in confusion_pairs:
            tc, pc = p.get("true_code", ""), p.get("pred_code", "")
            if tc not in confusion_map:
                confusion_map[tc] = set()
            confusion_map[tc].add(pc)

    suggestions = []
    per_code_count: dict[str, int] = {}

    for sample in samples:
        sid = sample.get("id", "")
        if sid in existing_ids:
            continue

        true_code = sample.get("defect_code", "").upper()
        pred = predictions.get(sid, {})
        defects = pred.get("defects", [])
        first = defects[0] if defects else {}
        pred_code = str(first.get("code", "")).upper()
        conf = float(first.get("confidence", 0) or 0)

        for code in codes:
            if per_code_count.get(code, 0) >= 3:
                continue

            # 正例：真实标签匹配且判对
            if "positive" in anchor_types and true_code == code and pred_code == code:
                suggestions.append({
                    "target_code": code,
                    "anchor_type": "positive",
                    "sample_id": sid,
                    "image_path": f"/sample-images/{sid}.png",
                    "confidence": conf,
                    "note": f"#{sid} 置信度{conf:.0%}",
                })
                per_code_count[code] = per_code_count.get(code, 0) + 1

            # 困难例：判对但置信度低
            if "hard" in anchor_types and true_code == code and pred_code == code and 0.4 <= conf < 0.75:
                suggestions.append({
                    "target_code": code,
                    "anchor_type": "hard",
                    "sample_id": sid,
                    "image_path": f"/sample-images/{sid}.png",
                    "confidence": conf,
                    "note": f"#{sid} 判对但置信度仅{conf:.0%}",
                })
                per_code_count[code] = per_code_count.get(code, 0) + 1

            # 反例：被误判为该代码
            if "negative" in anchor_types and pred_code == code and true_code != code and true_code not in ("NONE", "UNKNOWN"):
                suggestions.append({
                    "target_code": code,
                    "anchor_type": "negative",
                    "sample_id": sid,
                    "image_path": f"/sample-images/{sid}.png",
                    "confidence": conf,
                    "note": f"#{sid} 实际{true_code}被误判为{code}",
                })
                per_code_count[code] = per_code_count.get(code, 0) + 1

    return suggestions


def _save_optimization_record(results: list, focus_dimensions: list) -> None:
    """保存优化记录。"""
    EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
    history_file = EVALUATIONS_DIR / "optimization_history.json"

    history = get_optimization_history()
    record = {
        "timestamp": datetime.now().isoformat(),
        "focus_dimensions": [d.get("dimension") for d in focus_dimensions],
        "results": results,
    }
    history.append(record)

    # 只保留最近 50 条
    history = history[-50:]
    history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
