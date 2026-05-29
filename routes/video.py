"""视频路由。"""

import os
import shutil
import threading
import time
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from config import DATA_DIR

bp = Blueprint("video", __name__)

VIDEO_DEMO_BASE = os.getenv("VIDEO_DEMO_URL", "http://localhost:8085")
VIDEO_JOBS_PATH = DATA_DIR / "video_jobs.json"
_video_job_lock = threading.Lock()


def _load_video_jobs() -> dict[str, dict]:
    if VIDEO_JOBS_PATH.exists():
        try:
            import json
            return json.loads(VIDEO_JOBS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_video_jobs(jobs: dict) -> None:
    import json
    VIDEO_JOBS_PATH.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")


_video_jobs: dict[str, dict] = _load_video_jobs()


@bp.get("/api/video/config")
def api_video_config():
    import requests as req
    try:
        resp = req.get(f"{VIDEO_DEMO_BASE}/api/config", timeout=5)
        return jsonify({"ok": True, "video_demo": resp.json(), "video_demo_url": VIDEO_DEMO_BASE})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "video_demo_url": VIDEO_DEMO_BASE})


@bp.post("/api/video/extract-frames")
def api_extract_frames():
    """上传视频，智能抽帧，返回帧列表。"""
    uploaded = request.files.get("video")
    if not uploaded:
        return jsonify({"ok": False, "error": "请上传视频文件"}), 400

    job_id = uuid.uuid4().hex[:12]
    filename = uploaded.filename or "video.mp4"
    ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ".mp4"

    # 保存视频
    tmp_dir = DATA_DIR / "video_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{job_id}{ext}"
    uploaded.save(str(tmp_path))

    # 抽帧
    output_dir = DATA_DIR / "frame_extracts" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from core.frame_extractor import extract_frames
        frames = extract_frames(str(tmp_path), str(output_dir))
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        tmp_path.unlink(missing_ok=True)

    # 保存帧元数据
    import json
    meta_path = output_dir / "meta.json"
    meta_path.write_text(json.dumps({
        "job_id": job_id,
        "filename": filename,
        "frame_count": len(frames),
        "frames": frames,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({
        "ok": True,
        "job_id": job_id,
        "filename": filename,
        "frame_count": len(frames),
        "frames": frames,
    })


@bp.get("/api/video/frames/<job_id>")
def api_get_frames(job_id: str):
    output_dir = DATA_DIR / "frame_extracts" / job_id
    meta_path = output_dir / "meta.json"
    if not meta_path.exists():
        return jsonify({"error": "任务不存在"}), 404
    import json
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return jsonify(meta)


@bp.get("/api/video/frame-image/<job_id>/<filename>")
def api_serve_frame_image(job_id: str, filename: str):
    frame_dir = DATA_DIR / "frame_extracts" / job_id
    return send_from_directory(str(frame_dir), filename)


@bp.post("/api/video/import-frames")
def api_import_frames():
    """将视频帧导入为训练样本。"""
    import base64
    import csv
    from config import SAMPLES_DIR

    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id", "")
    frame_ids = data.get("frame_ids", [])  # 要导入的帧索引列表，空=全部

    meta_path = DATA_DIR / "frame_extracts" / job_id / "meta.json"
    if not meta_path.exists():
        return jsonify({"ok": False, "error": "帧数据不存在"}), 404

    import json
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    frames = meta.get("frames", [])

    if frame_ids:
        frames = [f for i, f in enumerate(frames) if i in frame_ids]

    # 分配新样本编号（以 index.csv 为准，而非 images 目录）
    index_path = SAMPLES_DIR / "index.csv"
    max_id = 0
    if index_path.exists():
        import csv as _csv
        with index_path.open(encoding="utf-8-sig", newline="") as f:
            for row in _csv.DictReader(f):
                try:
                    num = int(row.get("编号", "0"))
                    if num > max_id:
                        max_id = num
                except (ValueError, TypeError):
                    pass

    imported = []
    for frame in frames:
        max_id += 1
        new_id = str(max_id).zfill(3)
        src = Path(frame.get("image_path", ""))
        if not src.exists():
            continue
        dst = SAMPLES_DIR / "images" / f"{new_id}.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))

        # 文本
        txt_path = SAMPLES_DIR / "texts" / f"{new_id}.txt"
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        ts = frame.get("timestamp", 0)
        txt_path.write_text(f"来源：视频帧提取\n视频：{meta.get('filename', '')}\n时间：{ts}s\n", encoding="utf-8")

        # 追加到 index.csv（保留原有列结构）
        index_path = SAMPLES_DIR / "index.csv"
        rows = []
        fieldnames = []
        if index_path.exists():
            with index_path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames or [])
                rows = list(reader)

        new_row = {fn: "" for fn in fieldnames}
        new_row["编号"] = new_id
        new_row["图片文件"] = f"images/{new_id}.png"
        new_row["文字文件"] = f"texts/{new_id}.txt"
        new_row["管段编号"] = f"video-{job_id}"
        new_row["备注"] = f"视频帧提取 @{ts}s"
        rows.append(new_row)

        with index_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        imported.append({"sample_id": new_id, "timestamp": ts})

    return jsonify({"ok": True, "imported": len(imported), "samples": imported})
