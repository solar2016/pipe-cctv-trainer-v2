"""样本管理：读写 index.csv、图片、文本、预测结果。"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from config import SAMPLES_DIR, FEWSHOT_DIR


def load_samples() -> list[dict[str, Any]]:
    index_path = SAMPLES_DIR / "index.csv"
    if not index_path.exists():
        return []
    samples = []
    with index_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sid = row.get("编号", "").strip()
            if not sid:
                continue
            img_path = SAMPLES_DIR / row.get("图片文件", f"images/{sid}.png")
            samples.append({
                "id": sid,
                "defect_code": row.get("缺陷名称", "").strip().upper(),
                "grade": row.get("等级", "").strip(),
                "section": row.get("管段编号", ""),
                "diameter": row.get("管径", ""),
                "distance": row.get("距离", ""),
                "clock": row.get("时钟表示", ""),
                "recommendation": row.get("修复建议", ""),
                "note": row.get("备注", ""),
                "has_image": img_path.exists(),
            })
    return samples


def get_sample(sample_id: str) -> dict[str, Any] | None:
    samples = load_samples()
    for s in samples:
        if s["id"] == sample_id:
            return s
    return None


def get_sample_image_path(sample: dict[str, Any]) -> Path | None:
    img_path = SAMPLES_DIR / "images" / f"{sample['id']}.png"
    if img_path.exists():
        return img_path
    return None


def get_sample_text(sample: dict[str, Any]) -> str:
    txt_path = SAMPLES_DIR / "texts" / f"{sample['id']}.txt"
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8")
    return ""


def load_predictions() -> dict[str, dict[str, Any]]:
    pred_dir = SAMPLES_DIR / "predictions"
    if not pred_dir.exists():
        return {}
    predictions = {}
    for f in pred_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            predictions[f.stem] = data
        except Exception:
            pass
    return predictions


def update_sample_prediction(sample_id: str, result: dict[str, Any]) -> None:
    pred_dir = SAMPLES_DIR / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    path = pred_dir / f"{sample_id}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def save_correction(sample_id: str, correct_code: str, correct_grade: str, reason: str = "") -> dict[str, Any]:
    from config import DATA_DIR
    corr_dir = DATA_DIR / "corrections"
    corr_dir.mkdir(parents=True, exist_ok=True)
    correction = {
        "sample_id": sample_id,
        "correct_code": correct_code,
        "correct_grade": correct_grade,
        "reason": reason,
    }
    path = corr_dir / f"{sample_id}.json"
    path.write_text(json.dumps(correction, ensure_ascii=False, indent=2), encoding="utf-8")

    # 同时更新 index.csv
    index_path = SAMPLES_DIR / "index.csv"
    if index_path.exists():
        rows = []
        with index_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("编号", "").strip() == sample_id:
                    row["缺陷名称"] = correct_code
                    row["等级"] = correct_grade
                rows.append(row)
        fieldnames = list(rows[0].keys()) if rows else []
        with index_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return correction


def load_fewshot_anchors() -> dict[str, list[dict[str, Any]]]:
    if not FEWSHOT_DIR.exists():
        return {}
    anchors: dict[str, list[dict[str, Any]]] = {}
    for f in FEWSHOT_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            code = data.get("target_code", "")
            if code:
                anchors.setdefault(code, []).append(data)
        except Exception:
            pass
    return anchors


def get_fewshot_anchors_for_code(code: str) -> list[dict[str, Any]]:
    return load_fewshot_anchors().get(code, [])


def get_dynamic_fewshot_anchors() -> list[dict[str, Any]]:
    all_anchors = load_fewshot_anchors()
    result = []
    type_order = {"positive": 0, "hard": 1, "boundary": 2, "negative": 3}
    for code, items in all_anchors.items():
        sorted_items = sorted(items, key=lambda a: type_order.get(a.get("anchor_type", ""), 9))
        if sorted_items:
            result.append(sorted_items[0])
    return result


def save_fewshot_anchor(sample_id: str, anchor_type: str, target_code: str, note: str = "") -> dict[str, Any]:
    FEWSHOT_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "sample_id": sample_id,
        "anchor_type": anchor_type,
        "target_code": target_code,
        "note": note,
    }
    filename = f"{sample_id}_{anchor_type}_{target_code}.json"
    path = FEWSHOT_DIR / filename
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def remove_fewshot_anchor(sample_id: str, anchor_type: str, target_code: str) -> bool:
    filename = f"{sample_id}_{anchor_type}_{target_code}.json"
    path = FEWSHOT_DIR / filename
    if path.exists():
        path.unlink()
        return True
    return False
