"""Agent 三模块：自洽性校验、对抗性混淆、历史回归。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from collections import defaultdict

from config import EVALUATIONS_DIR, SAMPLES_DIR


def run_self_consistency_check(report: dict[str, Any]) -> dict[str, Any]:
    """自洽性校验：检查预测结果内部是否一致。"""
    samples = _load_samples()
    predictions = _load_predictions()

    issues = []
    checked = 0

    for sample in samples:
        sid = sample.get("id", "")
        pred = predictions.get(sid, {})
        defects = pred.get("defects", [])
        if not defects:
            continue

        checked += 1
        primary = defects[0]
        code = primary.get("code", "")
        conf = primary.get("confidence", 0)
        features = primary.get("visible_features", [])

        # 检查1：置信度与特征一致性
        if conf > 0.8 and len(features) < 2:
            issues.append({
                "type": "high_conf_low_features",
                "sample_id": sid,
                "code": code,
                "confidence": conf,
                "feature_count": len(features),
                "description": f"高置信度({conf:.0%})但特征数不足({len(features)}个)",
            })

        # 检查2：置信度与等级一致性
        grade = primary.get("grade")
        if grade is not None:
            if conf < 0.5 and grade >= 3:
                issues.append({
                    "type": "low_conf_high_grade",
                    "sample_id": sid,
                    "code": code,
                    "confidence": conf,
                    "grade": grade,
                    "description": f"低置信度({conf:.0%})但高等级({grade})",
                })

        # 检查3：UNKNOWN但有高置信度特征
        if code == "UNKNOWN" and conf > 0.6:
            issues.append({
                "type": "unknown_high_conf",
                "sample_id": sid,
                "confidence": conf,
                "description": f"UNKNOWN但置信度较高({conf:.0%})",
            })

        # 检查4：bbox与缺陷比例一致性
        bbox = primary.get("bbox")
        ratio = primary.get("defect_ratio")
        if bbox and ratio is not None:
            bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            if abs(bbox_area - ratio) > 0.3:
                issues.append({
                    "type": "bbox_ratio_mismatch",
                    "sample_id": sid,
                    "code": code,
                    "bbox_area": round(bbox_area, 3),
                    "defect_ratio": ratio,
                    "description": f"bbox面积({bbox_area:.3f})与defect_ratio({ratio:.3f})偏差大",
                })

    return {
        "module": "self_consistency",
        "checked": checked,
        "issues": issues,
        "issue_count": len(issues),
        "score": round(1 - len(issues) / max(1, checked), 3),
    }


def run_adversarial_confusion(report: dict[str, Any]) -> dict[str, Any]:
    """对抗性混淆：找出最容易被混淆的缺陷对。"""
    confusion_pairs = report.get("confusion_pairs", [])
    metrics = report.get("metrics", {})

    # 找出高混淆风险的缺陷对
    high_risk_pairs = []
    for pair in confusion_pairs:
        true_code = pair.get("true_code", "")
        pred_code = pair.get("pred_code", "")
        count = pair.get("count", 0)

        true_metrics = metrics.get(true_code, {})
        pred_metrics = metrics.get(pred_code, {})

        # 风险评分：混淆次数 × 两个类别的F1倒数
        true_f1 = true_metrics.get("f1", 0.5)
        pred_f1 = pred_metrics.get("f1", 0.5)
        risk_score = count * (1 / max(0.1, true_f1)) * (1 / max(0.1, pred_f1))

        high_risk_pairs.append({
            "true_code": true_code,
            "pred_code": pred_code,
            "count": count,
            "true_f1": true_f1,
            "pred_f1": pred_f1,
            "risk_score": round(risk_score, 2),
            "description": f"{true_code}↔{pred_code} (混淆{count}次, 风险{risk_score:.1f})",
        })

    high_risk_pairs.sort(key=lambda x: x["risk_score"], reverse=True)

    # 找出需要重点关注的缺陷类型
    focus_codes = []
    for code, m in metrics.items():
        if code == "macro_avg":
            continue
        support = m.get("support", 0)
        f1 = m.get("f1", 0)
        if support > 0 and f1 < 0.6:
            focus_codes.append({
                "code": code,
                "f1": f1,
                "support": support,
                "recall": m.get("recall", 0),
                "precision": m.get("precision", 0),
                "description": f"{code}: F1={f1:.3f}, 召回率={m.get('recall', 0):.3f}",
            })
    focus_codes.sort(key=lambda x: x["f1"])

    return {
        "module": "adversarial_confusion",
        "high_risk_pairs": high_risk_pairs[:10],
        "focus_codes": focus_codes,
        "recommendations": _generate_recommendations(high_risk_pairs, focus_codes),
    }


def run_historical_regression(report: dict[str, Any]) -> dict[str, Any]:
    """历史回归：对比当前评测与历史评测的变化。"""
    evaluations = _load_evaluations()
    if len(evaluations) < 2:
        return {
            "module": "historical_regression",
            "message": "历史数据不足，无法进行回归分析",
            "trend": "insufficient_data",
        }

    current = report.get("metrics", {}).get("macro_avg", {})
    prev_eval = evaluations[-2] if len(evaluations) >= 2 else None

    if not prev_eval:
        return {
            "module": "historical_regression",
            "message": "未找到历史评测数据",
            "trend": "insufficient_data",
        }

    prev_accuracy = prev_eval.get("metrics", {}).get("macro_avg", {}).get("accuracy", 0)
    curr_accuracy = current.get("accuracy", 0)
    delta = curr_accuracy - prev_accuracy

    # 分析各类别变化
    category_changes = []
    prev_metrics = prev_eval.get("metrics", {})
    curr_metrics = report.get("metrics", {})

    for code in set(list(prev_metrics.keys()) + list(curr_metrics.keys())):
        if code == "macro_avg":
            continue
        prev_f1 = prev_metrics.get(code, {}).get("f1", 0)
        curr_f1 = curr_metrics.get(code, {}).get("f1", 0)
        f1_delta = curr_f1 - prev_f1
        if abs(f1_delta) > 0.05:  # 变化超过5%
            category_changes.append({
                "code": code,
                "prev_f1": prev_f1,
                "curr_f1": curr_f1,
                "delta": round(f1_delta, 3),
                "direction": "improved" if f1_delta > 0 else "degraded",
            })

    category_changes.sort(key=lambda x: abs(x["delta"]), reverse=True)

    trend = "improved" if delta > 0.02 else ("degraded" if delta < -0.02 else "stable")

    return {
        "module": "historical_regression",
        "prev_accuracy": prev_accuracy,
        "curr_accuracy": curr_accuracy,
        "delta": round(delta, 4),
        "trend": trend,
        "category_changes": category_changes,
        "summary": _regression_summary(delta, category_changes),
    }


def _generate_recommendations(pairs: list, focus_codes: list) -> list[str]:
    """生成针对性建议。"""
    recs = []

    for pair in pairs[:3]:
        true_code = pair["true_code"]
        pred_code = pair["pred_code"]
        recs.append(
            f"为 {true_code}→{pred_code} 的混淆添加 fewshot 锚点，"
            f"重点展示两者视觉差异"
        )

    for code_info in focus_codes[:3]:
        code = code_info["code"]
        recall = code_info["recall"]
        if recall < 0.5:
            recs.append(f"{code} 召回率过低({recall:.0%})，建议增加正例 fewshot")
        elif code_info["precision"] < 0.5:
            recs.append(f"{code} 精确率过低({code_info['precision']:.0%})，建议增加反例 fewshot")

    return recs


def _regression_summary(delta: float, changes: list) -> str:
    """生成回归分析摘要。"""
    if delta > 0.02:
        trend = "改善"
    elif delta < -0.02:
        trend = "退化"
    else:
        trend = "稳定"

    lines = [f"整体趋势: {trend} (准确率变化: {delta:+.1%})"]

    improved = [c for c in changes if c["direction"] == "improved"]
    degraded = [c for c in changes if c["direction"] == "degraded"]

    if improved:
        lines.append(f"改善类别: {', '.join(c['code'] for c in improved[:5])}")
    if degraded:
        lines.append(f"退化类别: {', '.join(c['code'] for c in degraded[:5])}")

    return "\n".join(lines)


def _load_samples() -> list[dict[str, Any]]:
    """加载样本数据。"""
    from services.sample_service import load_samples
    return load_samples()


def _load_predictions() -> dict[str, dict[str, Any]]:
    """加载预测数据。"""
    from services.sample_service import load_predictions
    return load_predictions()


def _load_evaluations() -> list[dict[str, Any]]:
    """加载评测数据。"""
    if not EVALUATIONS_DIR.exists():
        return []
    results = []
    for f in sorted(EVALUATIONS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append(data)
        except Exception:
            pass
    return results
