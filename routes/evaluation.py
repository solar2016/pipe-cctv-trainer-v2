"""评测路由。"""

from flask import Blueprint, jsonify, request

from services.evaluation_service import run_evaluation, list_evaluations, get_evaluation
from services.report_service import generate_report

bp = Blueprint("evaluation", __name__)


@bp.post("/api/evaluate")
@bp.post("/api/evaluate/run")
def api_evaluate():
    data = request.get_json(silent=True) or {}
    label = data.get("label", "eval")
    eval_record = run_evaluation(label)

    eval_id = eval_record.get("id")
    result = eval_record.get("result", {})

    # 生成报告
    report = None
    if eval_id:
        r = generate_report(eval_id)
        if "error" not in r:
            report = r

    return jsonify({
        "ok": True,
        "evaluation_id": eval_id,
        "total": result.get("total", 0),
        "type_accuracy": result.get("code_accuracy", 0),
        "grade_accuracy": result.get("grade_accuracy", 0),
        "unknown_rate": result.get("unknown_rate", 0),
        "report": report,
    })


@bp.get("/api/evaluations")
def api_evaluations():
    return jsonify({"evaluations": list_evaluations()})


@bp.get("/api/evaluations/<eval_id>")
def api_evaluation(eval_id: str):
    eval_record = get_evaluation(eval_id)
    if not eval_record:
        return jsonify({"error": "评估记录不存在"}), 404
    return jsonify(eval_record)
