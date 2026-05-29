"""视频智能抽帧：基于画面变化检测，不是固定频率。"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any


def extract_frames(video_path: str, output_dir: str, threshold: float = 0.3, min_interval: float = 1.0) -> list[dict[str, Any]]:
    """从视频中智能抽帧。

    基于帧间差异检测，只在画面发生显著变化时抽帧。
    返回: [{"frame_index": int, "timestamp": float, "image_path": str}, ...]
    """
    try:
        import cv2
    except ImportError:
        return _fallback_extract(video_path, output_dir)

    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    min_frame_gap = int(fps * min_interval)

    prev_hist = None
    frames = []
    last_extract_frame = -min_frame_gap
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 计算帧直方图用于比较
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        cv2.normalize(hist, hist)

        should_extract = False
        if prev_hist is None:
            should_extract = True
        elif frame_idx - last_extract_frame >= min_frame_gap:
            diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
            if diff > threshold:
                should_extract = True

        if should_extract:
            timestamp = frame_idx / fps
            out_path = os.path.join(output_dir, f"frame_{frame_idx:06d}.png")
            cv2.imwrite(out_path, frame)
            frames.append({
                "frame_index": frame_idx,
                "timestamp": round(timestamp, 2),
                "image_path": out_path,
            })
            last_extract_frame = frame_idx
            prev_hist = hist

        frame_idx += 1

    cap.release()
    return frames


def _fallback_extract(video_path: str, output_dir: str, interval: float = 2.0) -> list[dict[str, Any]]:
    """OpenCV 不可用时的 fallback：按固定间隔抽帧。"""
    try:
        import subprocess
        os.makedirs(output_dir, exist_ok=True)

        # 获取视频时长
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=30,
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0

        frames = []
        t = 0.0
        idx = 0
        while t < duration:
            out_path = os.path.join(output_dir, f"frame_{idx:06d}.png")
            subprocess.run(
                ["ffmpeg", "-ss", str(t), "-i", video_path, "-frames:v", "1",
                 "-q:v", "2", out_path, "-y"],
                capture_output=True, timeout=30,
            )
            if os.path.exists(out_path):
                frames.append({
                    "frame_index": idx,
                    "timestamp": round(t, 2),
                    "image_path": out_path,
                })
            t += interval
            idx += 1

        return frames
    except Exception:
        return []
