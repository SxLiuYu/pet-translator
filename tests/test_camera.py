"""Test camera manager and behavior detector"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from camera.camera_manager import CameraManager, CameraFrame, get_camera_manager
from camera.behavior_detector import Detection, VisualBehavior, BehaviorDetector


def test_camera_manager_singleton():
    m1 = get_camera_manager()
    m2 = get_camera_manager()
    assert m1 is m2


def test_camera_manager_register_get():
    mgr = CameraManager()
    assert mgr.status() == {}
    # Just test that registration methods exist
    assert hasattr(mgr, "register_rtsp")
    assert hasattr(mgr, "register_usb")
    assert hasattr(mgr, "register_esp32cam")
    assert hasattr(mgr, "get")
    assert hasattr(mgr, "start_all")
    assert hasattr(mgr, "stop_all")


def test_camera_frame():
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    frame = CameraFrame(img, 1234567890.0, "test_cam")
    assert frame.source == "test_cam"
    assert frame.shape == (480, 640, 3)
    jpeg = frame.jpeg_bytes
    assert isinstance(jpeg, bytes)
    assert len(jpeg) > 0


def test_detection_dataclass():
    det = Detection(class_name="dog", confidence=0.9, bbox=[10, 20, 100, 200], track_id=1, class_id=18)
    assert det.class_name == "dog"
    assert det.confidence == 0.9
    assert det.bbox == [10, 20, 100, 200]
    assert det.track_id == 1
    assert det.class_id == 18


def test_detection_defaults():
    det = Detection(class_name="cat", confidence=0.8, bbox=[0, 0, 50, 50])
    assert det.track_id is None
    assert det.class_id is None


def test_visual_behavior_dataclass():
    vb = VisualBehavior(
        timestamp=1234567890.0,
        behavior="running",
        confidence=0.85,
        activity_level="high",
        is_destructive=False,
        description="Cat is running",
    )
    assert vb.behavior == "running"
    assert vb.activity_level == "high"
    assert vb.is_destructive is False


def test_behavior_detector_init():
    detector = BehaviorDetector(use_clip=False)
    assert detector.model is None  # No model in test env
    assert detector.conf_threshold == 0.5


def test_behavior_detector_no_model():
    detector = BehaviorDetector(use_clip=False)
    # Without model, detect should return gracefully
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(img)
    assert isinstance(result, VisualBehavior)
    assert result.description == "无运动"
    assert result.behavior == "unknown"


def test_bbox_overlaps():
    detector = BehaviorDetector(use_clip=False)
    # Two overlapping boxes
    assert detector._bbox_overlaps([0, 0, 100, 100], [50, 50, 150, 150], threshold=0.2) is True
    # Non-overlapping boxes
    assert detector._bbox_overlaps([0, 0, 10, 10], [100, 100, 200, 200], threshold=0.2) is False
    # Edge case: exactly touching
    assert detector._bbox_overlaps([0, 0, 100, 100], [100, 0, 200, 100], threshold=0.2) is False


def test_analyze_behavior_no_pet():
    detector = BehaviorDetector(use_clip=False)
    result = detector._analyze_behavior([])
    assert result[0] == "no_pet_detected"
    assert result[3] is False


def test_analyze_behavior_with_pet():
    detector = BehaviorDetector(use_clip=False)
    detections = [Detection(class_name="dog", confidence=0.9, bbox=[0, 0, 100, 200], class_id=18)]
    result = detector._analyze_behavior(detections)
    assert result[0] != "no_pet_detected"
    assert result[2] in ("low", "medium", "high")


def test_analyze_behavior_destructive():
    detector = BehaviorDetector(use_clip=False)
    # Dog close to a bottle (class_id 39)
    detections = [
        Detection(class_name="dog", confidence=0.9, bbox=[0, 0, 100, 100], class_id=18),
        Detection(class_name="bottle", confidence=0.8, bbox=[50, 50, 150, 150], class_id=39),
    ]
    result = detector._analyze_behavior(detections)
    assert result[0] == "拆家" or result[0] == "拆家"
    assert result[3] is True
