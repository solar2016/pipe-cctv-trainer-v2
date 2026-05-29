"""报告生成服务：基于评测结果生成结构化报告。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from collections import defaultdict

from config import EVALUATIONS_DIR, SAMPLES_DIR


def generate_report(evaluation_id: str | None = None) -> dict[str, Any]:
    """生成评测报告。"""
    # 加载评测数据
    evaluations = _load_evaluations()
    if not evaluations:
        return {"error": "没有评测数据"}

    # 使用最新的评测，或指定的评测
    if evaluation_id:
        eval_data = next((e for e in evaluations if e.get("id") == evaluation_id), None)
    else:
        eval_data = evaluations[-1] if evaluations else None

    if not eval_data:
        return {"error": "评测数据不存在"}

    # 加载样本和预测
    samples = _load_samples()
    predictions = _load_predictions()

    # 计算混淆矩阵
    confusion = _build_confusion_matrix(samples, predictions)

    # 计算各类指标
    metrics = _calculate_metrics(confusion)

    # 生成混淆对
    confusion_pairs = _find_confusion_pairs(confusion)

    # 计算扩展指标
    extended = _calculate_extended_metrics(samples, predictions, metrics)

    # 生成报告
    report = {
        "evaluation_id": eval_data.get("id", ""),
        "evaluation_time": eval_data.get("created_at", ""),
        "prompt_version": eval_data.get("prompt_version", ""),
        "total_samples": len(samples),
        "predicted_samples": len([s for s in samples if s.get("status") == "predicted"]),
        "confusion_matrix": confusion,
        "metrics": metrics,
        "confusion_pairs": confusion_pairs,
        "extended": extended,
        "summary": _generate_summary(metrics, confusion_pairs, extended),
    }

    # 保存报告
    _save_report(report)

    return report


def _load_evaluations() -> list[dict[str, Any]]:
    """加载评测数据。"""
    if not EVALUATIONS_DIR.exists():
        return []
    results = []
    for f in sorted(EVALUATIONS_DIR.glob("*.json")):
        if f.name.startswith("report_") or f.name.startswith("agent_") or f.name.startswith("priorities_") or f.name.startswith("optimization_"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                results.append(data)
        except Exception:
            pass
    return results


def _load_samples() -> list[dict[str, Any]]:
    """加载样本数据。"""
    from services.sample_service import load_samples
    return load_samples()


def _load_predictions() -> dict[str, dict[str, Any]]:
    """加载预测数据。"""
    from services.sample_service import load_predictions
    return load_predictions()


def _build_confusion_matrix(samples: list[dict], predictions: dict) -> dict[str, dict[str, int]]:
    """构建混淆矩阵。"""
    matrix = defaultdict(lambda: defaultdict(int))

    for sample in samples:
        sid = sample.get("id", "")
        true_code = sample.get("defect_code", "").upper()
        pred = predictions.get(sid, {})
        pred_defects = pred.get("defects", [])
        pred_code = pred_defects[0].get("code", "UNKNOWN") if pred_defects else "UNKNOWN"

        if true_code and pred_code:
            matrix[true_code][pred_code] += 1

    return {k: dict(v) for k, v in matrix.items()}


def _calculate_metrics(confusion: dict) -> dict[str, Any]:
    """计算各类指标。"""
    metrics = {}
    all_codes = set(confusion.keys())
    for preds in confusion.values():
        all_codes.update(preds.keys())

    for code in sorted(all_codes):
        tp = confusion.get(code, {}).get(code, 0)
        fp = sum(confusion.get(other, {}).get(code, 0) for other in confusion if other != code)
        fn = sum(confusion.get(code, {}).get(other, 0) for other in confusion.get(code, {}) if other != code)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        metrics[code] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": tp + fn,
        }

    # 整体指标
    total_tp = sum(m["tp"] for m in metrics.values())
    total_support = sum(m["support"] for m in metrics.values())
    metrics["macro_avg"] = {
        "precision": round(sum(m["precision"] for m in metrics.values() if m["support"] > 0) / max(1, len([m for m in metrics.values() if m["support"] > 0])), 3),
        "recall": round(sum(m["recall"] for m in metrics.values() if m["support"] > 0) / max(1, len([m for m in metrics.values() if m["support"] > 0])), 3),
        "f1": round(sum(m["f1"] for m in metrics.values() if m["support"] > 0) / max(1, len([m for m in metrics.values() if m["support"] > 0])), 3),
        "accuracy": round(total_tp / total_support, 3) if total_support > 0 else 0,
    }

    return metrics


def _calculate_extended_metrics(samples: list, predictions: dict, metrics: dict) -> dict[str, Any]:
    """计算扩展指标：过度自信率、共生遗漏率等。"""
    total = 0
    overconfident_wrong = 0
    overconfident_total = 0
    unknown_count = 0
    unknown_total = 0

    for sample in samples:
        sid = sample.get("id", "")
        true_code = sample.get("defect_code", "").upper()
        pred = predictions.get(sid, {})
        defects = pred.get("defects", [])
        if not defects:
            continue

        total += 1
        primary = defects[0]
        pred_code = str(primary.get("code", "")).upper()
        conf = primary.get("confidence", 0)

        # 过度自信：置信度 > 0.8 但预测错误
        if conf > 0.8:
            overconfident_total += 1
            if pred_code != true_code and true_code != "NONE":
                overconfident_wrong += 1

        # UNKNOWN 统计
        if pred_code == "UNKNOWN":
            unknown_count += 1
        if true_code == "NONE":
            unknown_total += 1

    overconfident_rate = overconfident_wrong / max(1, overconfident_total)
    unknown_rate = unknown_count / max(1, total)

    # 共生遗漏：检查是否有样本包含多个真实缺陷但只预测了一个
    multi_defect_samples = 0
    multi_defect_missed = 0
    # 简化实现：统计预测为单一缺陷但实际可能是多缺陷的样本
    for sample in samples:
        sid = sample.get("id", "")
        pred = predictions.get(sid, {})
        defects = pred.get("defects", [])
        # 如果预测只有一个 UNKNOWN，可能是多缺陷遗漏
        if len(defects) == 1 and defects[0].get("code") == "UNKNOWN":
            multi_defect_samples += 1
            # 检查是否有 scan_findings 暗示多个区域
            scan = pred.get("scan_findings", [])
            if len(scan) > 1:
                multi_defect_missed += 1

    co_occurrence_miss_rate = multi_defect_missed / max(1, multi_defect_samples)

    return {
        "overconfident_rate": round(overconfident_rate, 3),
        "overconfident_wrong": overconfident_wrong,
        "overconfident_total": overconfident_total,
        "unknown_rate": round(unknown_rate, 3),
        "unknown_count": unknown_count,
        "co_occurrence_miss_rate": round(co_occurrence_miss_rate, 3),
        "multi_defect_candidates": multi_defect_samples,
    }


def _find_confusion_pairs(confusion: dict, min_count: int = 2) -> list[dict[str, Any]]:
    """找出混淆对。"""
    pairs = []
    for true_code, preds in confusion.items():
        for pred_code, count in preds.items():
            if true_code != pred_code and count >= min_count:
                pairs.append({
                    "true_code": true_code,
                    "pred_code": pred_code,
                    "count": count,
                    "description": f"{true_code} 被误判为 {pred_code} ({count}次)",
                })
    return sorted(pairs, key=lambda x: x["count"], reverse=True)


def _generate_summary(metrics: dict, confusion_pairs: list, extended: dict | None = None) -> str:
    """生成报告摘要。"""
    overall = metrics.get("macro_avg", {})
    accuracy = overall.get("accuracy", 0)

    lines = [f"总体准确率: {accuracy:.1%}"]
    lines.append(f"宏平均 F1: {overall.get('f1', 0):.3f}")

    if extended:
        lines.append(f"过度自信率: {extended.get('overconfident_rate', 0):.1%} ({extended.get('overconfident_wrong', 0)}/{extended.get('overconfident_total', 0)})")
        lines.append(f"UNKNOWN 率: {extended.get('unknown_rate', 0):.1%}")
        if extended.get('co_occurrence_miss_rate', 0) > 0:
            lines.append(f"共生遗漏率: {extended['co_occurrence_miss_rate']:.1%}")

    if confusion_pairs:
        lines.append(f"\n主要混淆问题 ({len(confusion_pairs)}对):")
        for pair in confusion_pairs[:5]:
            lines.append(f"  - {pair['description']}")

    # 找出低 F1 的类别
    low_f1 = [(code, m) for code, m in metrics.items()
              if code not in ("macro_avg",) and m["support"] > 0 and m["f1"] < 0.6]
    if low_f1:
        lines.append(f"\n需要改进的类别 (F1 < 0.6):")
        for code, m in sorted(low_f1, key=lambda x: x[1]["f1"]):
            lines.append(f"  - {code}: F1={m['f1']:.3f}, 召回率={m['recall']:.3f}")

    return "\n".join(lines)


def _save_report(report: dict) -> None:
    """保存报告。"""
    EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"report_{report.get('evaluation_id', 'unknown')}.json"
    path = EVALUATIONS_DIR / filename
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def list_reports() -> list[dict[str, Any]]:
    """列出所有报告。"""
    if not EVALUATIONS_DIR.exists():
        return []
    reports = []
    for f in sorted(EVALUATIONS_DIR.glob("report_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            reports.append({
                "id": data.get("evaluation_id", ""),
                "time": data.get("evaluation_time", ""),
                "accuracy": data.get("metrics", {}).get("macro_avg", {}).get("accuracy", 0),
                "confusion_count": len(data.get("confusion_pairs", [])),
            })
        except Exception:
            pass
    return reports
