#!/usr/bin/env python3
"""
视频视觉检测测试脚本
"""
import argparse
import json
import os
import sys
import time
from collections import Counter

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
from camera.behavior_detector import BehaviorDetector


def create_synthetic_test_video(output_path: str, duration_sec: int = 10):
    """生成合成测试视频: 模拟宠物在画面中移动"""
    width, height, fps = 640, 480, 15
    total_frames = duration_sec * fps
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    for i in range(total_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (200, 200, 200)
        t = i / fps
        cx = int(width // 2 + width // 3 * np.sin(t * 0.5))
        cy = int(height // 2 + height // 4 * np.sin(t * 0.8))
        size = 40 + int(20 * np.sin(t * 1.2))
        cv2.ellipse(frame, (cx, cy), (size, size // 2), 0, 0, 360, (0, 165, 255), -1)
        cv2.circle(frame, (cx + size, cy - size // 2), size // 3, (0, 165, 255), -1)
        if 3 < t < 5:
            cv2.rectangle(frame, (cx + 20, cy - 10), (cx + 60, cy + 10), (0, 0, 255), 2)
        if 6 < t < 7:
            cv2.putText(frame, "JUMPING", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        out.write(frame)
    out.release()
    return output_path


def run_video_test(video_path, output_path=None, use_clip=False, max_frames=300):
    print(f"\n{'='*60}")
    print(f"视觉检测视频测试")
    print(f"{'='*60}")
    detector = BehaviorDetector(use_clip=use_clip)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"视频: {width}x{height}, {fps:.1f}fps, {total}帧")
    out_writer = None
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    behavior_counts = Counter()
    frame_count = 0
    processed_count = 0
    motion_count = 0
    total_inference_ms = 0.0
    start_time = time.time()
    print(f"\n开始检测...")
    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        result = detector.detect(frame)
        if not result.skipped:
            processed_count += 1
            total_inference_ms += result.inference_ms
            if result.motion_detected:
                motion_count += 1
            if result.behavior not in ("unknown", "静止"):
                behavior_counts[result.behavior] += 1
            if frame_count % 15 == 0 or result.is_destructive:
                print(f"  [{frame_count:4d}] {result.behavior:12s} conf={result.confidence:.0%} act={result.activity_level:6s} {result.inference_ms:6.0f}ms{' DESTRUCTIVE' if result.is_destructive else ''}")
        if out_writer:
            if result.annotated_image:
                annotated = cv2.imdecode(np.frombuffer(result.annotated_image, dtype=np.uint8), cv2.IMREAD_COLOR)
                if annotated is not None:
                    out_writer.write(annotated)
                else:
                    out_writer.write(frame)
            else:
                out_writer.write(frame)
    cap.release()
    if out_writer:
        out_writer.release()
    elapsed = time.time() - start_time
    print(f"\n报告:")
    print(f"  总帧数: {frame_count}")
    print(f"  处理帧: {processed_count} ({processed_count/max(1,frame_count)*100:.1f}%)")
    print(f"  运动帧: {motion_count}")
    print(f"  平均推理: {total_inference_ms/max(1,processed_count):.0f}ms")
    print(f"  处理速度: {frame_count/elapsed:.1f} fps")
    if behavior_counts:
        print(f"\n行为分布:")
        for behavior, count in behavior_counts.most_common():
            print(f"  {behavior:12s}: {count} 次")
    if output_path:
        print(f"标注视频: {output_path}")
    return {"frames": frame_count, "processed": processed_count, "fps": round(frame_count/elapsed, 1)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", help="输入视频")
    parser.add_argument("--output", default="test_output.mp4")
    parser.add_argument("--use-clip", action="store_true")
    parser.add_argument("--max-frames", type=int, default=300)
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()
    video_path = args.video
    if not video_path or not os.path.exists(video_path):
        synth_path = "test_synthetic_pet.mp4"
        print(f"生成合成测试视频: {synth_path}")
        create_synthetic_test_video(synth_path, duration_sec=10)
        video_path = synth_path
    run_video_test(video_path, args.output, args.use_clip, args.max_frames)
