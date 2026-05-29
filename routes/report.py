"""报告路由：报告生成 + Agent分析 + 优先级 + 优化 + 回归验证。"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, request

from config import EVALUATIONS_DIR
from services.report_service import generate_report, list_reports
from services.agent_service import (
    run_self_consistency_check,
    run_adversarial_confusion,
    run_historical_regression,
)
from services.priority_service import analyze_priorities
from services.optimizer import (
    run_optimization,
    apply_optimizations_to_prompt,
    get_optimization_history,
)

bp = Blueprint("report", __name__)


def _load_report(evaluation_id: str) -> dict | None:
    report_path = EVALUATIONS_DIR / f"report_{evaluation_id}.json"
    if not report_path.exists():
        return None
    return json.loads(report_path.read_text(encoding="utf-8"))


@bp.route("/api/report/generate", methods=["POST"])
def api_generate_report():
    """生成评测报告。"""
    data = request.get_json(silent=True) or {}
    evaluation_id = data.get("evaluation_id")

    report = generate_report(evaluation_id)
    if "error" in report:
        return jsonify({"error": report["error"]}), 400

    return jsonify({"ok": True, "report": report})


@bp.route("/api/report/list")
def api_list_reports():
    """列出所有报告。"""
    reports = list_reports()
    return jsonify({"reports": reports})


@bp.route("/api/report/agent/<evaluation_id>")
def api_agent_analysis(evaluation_id: str):
    """运行 Agent 三模块分析。"""
    report = _load_report(evaluation_id)
    if not report:
        return jsonify({"error": "报告不存在，请先生成报告"}), 404

    consistency = run_self_consistency_check(report)
    confusion = run_adversarial_confusion(report)
    regression = run_historical_regression(report)

    agent_results = {
        "self_consistency": consistency,
        "adversarial_confusion": confusion,
        "historical_regression": regression,
    }

    # 保存 agent 结果
    EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
    agent_path = EVALUATIONS_DIR / f"agent_{evaluation_id}.json"
    agent_path.write_text(json.dumps(agent_results, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({"ok": True, "agent_results": agent_results})


@bp.route("/api/report/priorities/<evaluation_id>", methods=["GET", "POST"])
def api_priorities(evaluation_id: str):
    """优先级分析（大模型读报告判断重点维度）。"""
    report = _load_report(evaluation_id)
    if not report:
        return jsonify({"error": "报告不存在，请先生成报告"}), 404

    priorities = analyze_priorities(report)

    # 保存优先级结果
    EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
    prio_path = EVALUATIONS_DIR / f"priorities_{evaluation_id}.json"
    prio_path.write_text(json.dumps(priorities, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({"ok": True, "priorities": priorities})


@bp.route("/api/report/optimize/<evaluation_id>", methods=["POST"])
def api_optimize(evaluation_id: str):
    """执行定向优化。"""
    # 加载优先级结果
    prio_path = EVALUATIONS_DIR / f"priorities_{evaluation_id}.json"
    if not prio_path.exists():
        return jsonify({"error": "请先运行优先级分析"}), 400

    priorities = json.loads(prio_path.read_text(encoding="utf-8"))
    focus_dims = priorities.get("focus_dimensions", [])

    if not focus_dims:
        return jsonify({"ok": True, "message": "无需优化", "optimizations": []})

    if priorities.get("skip_optimization"):
        return jsonify({"ok": True, "message": priorities.get("skip_reason", "跳过优化"), "optimizations": []})

    # 加载报告
    report = _load_report(evaluation_id)
    if not report:
        return jsonify({"error": "报告不存在"}), 404

    # 执行优化
    result = run_optimization(focus_dims, report)

    return jsonify(result)


@bp.route("/api/report/apply-prompt/<evaluation_id>", methods=["POST"])
def api_apply_prompt(evaluation_id: str):
    """将优化结果应用到 prompt（生成新版本）。"""
    # 加载最近的优化记录
    history = get_optimization_history()
    if not history:
        return jsonify({"error": "无优化记录"}), 400

    latest = history[-1]
    optimizations = latest.get("results", [])

    result = apply_optimizations_to_prompt(optimizations)
    return jsonify(result)


@bp.route("/api/report/regression/<evaluation_id>", methods=["POST"])
def api_regression_check(evaluation_id: str):
    """回归验证：重新运行评测，对比重点指标是否改善。"""
    # 加载当前优先级
    prio_path = EVALUATIONS_DIR / f"priorities_{evaluation_id}.json"
    if not prio_path.exists():
        return jsonify({"error": "无优先级数据"}), 400

    priorities = json.loads(prio_path.read_text(encoding="utf-8"))
    focus_dims = priorities.get("focus_dimensions", [])

    # 重新运行评测
    from services.evaluation_service import run_evaluation
    new_eval = run_evaluation(label=f"regression_after_{evaluation_id}")
    new_eval_id = new_eval.get("id")

    if not new_eval_id:
        return jsonify({"error": "重新评测失败"}), 500

    # 生成新报告
    new_report = generate_report(new_eval_id)
    if "error" in new_report:
        return jsonify({"error": new_report["error"]}), 500

    # 加载旧报告
    old_report = _load_report(evaluation_id)

    # 对比重点指标
    comparison = _compare_focus_metrics(old_report, new_report, focus_dims)

    return jsonify({
        "ok": True,
        "new_evaluation_id": new_eval_id,
        "comparison": comparison,
        "improved": comparison.get("improved", False),
    })


@bp.route("/api/report/optimize-history")
def api_optimize_history():
    """获取优化历史。"""
    history = get_optimization_history()
    return jsonify({"history": history})


def _compare_focus_metrics(old_report: dict, new_report: dict, focus_dims: list) -> dict:
    """对比新旧报告的重点指标。"""
    old_metrics = old_report.get("metrics", {})
    new_metrics = new_report.get("metrics", {})

    changes = []
    improved_count = 0
    degraded_count = 0

    for dim in focus_dims:
        dimension = dim.get("dimension", "")
        affected = dim.get("affected_codes", [])

        for code in affected:
            old_m = old_metrics.get(code, {})
            new_m = new_metrics.get(code, {})
            old_f1 = old_m.get("f1", 0)
            new_f1 = new_m.get("f1", 0)
            delta = new_f1 - old_f1

            if abs(delta) > 0.01:
                direction = "improved" if delta > 0 else "degraded"
                if delta > 0:
                    improved_count += 1
                else:
                    degraded_count += 1
                changes.append({
                    "code": code,
                    "dimension": dimension,
                    "old_f1": old_f1,
                    "new_f1": new_f1,
                    "delta": round(delta, 3),
                    "direction": direction,
                })

    # 整体对比
    old_overall = old_metrics.get("macro_avg", {}).get("f1", 0)
    new_overall = new_metrics.get("macro_avg", {}).get("f1", 0)

    return {
        "changes": changes,
        "old_overall_f1": old_overall,
        "new_overall_f1": new_overall,
        "overall_delta": round(new_overall - old_overall, 3),
        "improved_count": improved_count,
        "degraded_count": degraded_count,
        "improved": improved_count > degraded_count,
    }
