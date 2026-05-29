"""标准文档路由。"""

from flask import Blueprint, jsonify, request

from services.standards_service import (
    list_standards, get_standard, upload_and_parse_standard,
    update_standard, delete_standard, get_active_standard, set_active_standard,
)

bp = Blueprint("standards", __name__)


@bp.get("/api/standards")
def api_list_standards():
    return jsonify({"standards": list_standards()})


@bp.get("/api/standards/<standard_id>")
def api_get_standard(standard_id: str):
    data = get_standard(standard_id)
    if not data:
        return jsonify({"error": "标准不存在"}), 404
    return jsonify(data)


@bp.post("/api/standards/upload")
def api_upload_standard():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"ok": False, "error": "请上传文件"}), 400
    filename = uploaded.filename or "standard.pdf"
    mime_type = uploaded.content_type or "application/octet-stream"
    file_bytes = uploaded.read()
    if not file_bytes:
        return jsonify({"ok": False, "error": "文件为空"}), 400
    try:
        result = upload_and_parse_standard(file_bytes, filename, mime_type)
        return jsonify({"ok": True, "standard": result})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@bp.put("/api/standards/<standard_id>")
def api_update_standard(standard_id: str):
    data = request.get_json(silent=True) or {}
    result = update_standard(standard_id, data)
    if not result:
        return jsonify({"error": "标准不存在"}), 404
    return jsonify({"ok": True, "standard": result})


@bp.delete("/api/standards/<standard_id>")
def api_delete_standard(standard_id: str):
    ok = delete_standard(standard_id)
    if not ok:
        return jsonify({"error": "标准不存在"}), 404
    return jsonify({"ok": True})


@bp.get("/api/standards/active")
def api_get_active_standard():
    data = get_active_standard()
    if not data:
        return jsonify({"standard": None})
    return jsonify({"standard": data})


@bp.post("/api/standards/<standard_id>/activate")
def api_activate_standard(standard_id: str):
    ok = set_active_standard(standard_id)
    if not ok:
        return jsonify({"error": "标准不存在"}), 404
    return jsonify({"ok": True, "standard_id": standard_id})
