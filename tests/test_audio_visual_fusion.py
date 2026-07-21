from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from audio_visual_fusion import AudioVisualFusionEngine


class MutableClock:
    def __init__(self, value: datetime):
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


def test_single_audio_result_is_recorded():
    engine = AudioVisualFusionEngine(
        time_window_seconds=60,
        clock=MutableClock(datetime.fromisoformat("2026-07-19T10:00:00")),
    )

    result = engine.add_audio_result("pet_1", {
        "animal": "狗",
        "behavior": "吠叫",
        "confidence": 0.8,
        "timestamp": "2026-07-19T10:00:00",
    })

    assert result.pet_id == "pet_1"
    assert result.sources == ["audio"]
    assert result.behavior == "吠叫"
    assert engine.get_recent_fusions("pet_1") == [result]


def test_audio_and_visual_results_are_fused_inside_window():
    engine = AudioVisualFusionEngine(
        time_window_seconds=60,
        clock=MutableClock(datetime.fromisoformat("2026-07-19T10:00:20")),
    )
    engine.add_audio_result("pet_1", {
        "animal": "狗",
        "behavior": "吠叫",
        "confidence": 0.8,
        "is_alert": True,
        "suggestion": "查看宠物状态",
        "timestamp": "2026-07-19T10:00:00",
    })

    result = engine.add_visual_result("pet_1", {
        "animal": "狗",
        "behavior": "跑动",
        "confidence": 0.6,
        "timestamp": "2026-07-19T10:00:20",
    })

    assert result.sources == ["audio", "visual"]
    assert result.behavior == "吠叫 + 跑动"
    assert result.confidence == 0.69
    assert result.is_alert is True
    assert result.suggestion == "查看宠物状态"


def test_results_outside_window_do_not_fuse():
    engine = AudioVisualFusionEngine(
        time_window_seconds=30,
        clock=MutableClock(datetime.fromisoformat("2026-07-19T10:02:00")),
    )
    engine.add_audio_result("pet_1", {
        "behavior": "喵叫",
        "confidence": 0.9,
        "timestamp": "2026-07-19T10:00:00",
    })

    result = engine.add_visual_result("pet_1", {
        "behavior": "睡觉",
        "confidence": 0.7,
        "timestamp": "2026-07-19T10:02:00",
    })

    assert result.sources == ["visual"]
    assert result.behavior == "睡觉"


def test_history_is_isolated_by_pet_and_limited():
    engine = AudioVisualFusionEngine(
        history_limit=2,
        clock=MutableClock(datetime.fromisoformat("2026-07-19T10:00:03")),
    )
    for index in range(3):
        engine.add_audio_result("pet_1", {
            "behavior": f"behavior_{index}",
            "timestamp": f"2026-07-19T10:00:0{index}",
        })
    engine.add_audio_result("pet_2", {
        "behavior": "喵叫",
        "timestamp": "2026-07-19T10:00:00",
    })

    pet_1_results = engine.get_recent_fusions("pet_1")
    assert [item.behavior for item in pet_1_results] == ["behavior_1", "behavior_2"]
    assert [item.behavior for item in engine.get_recent_fusions("pet_2")] == ["喵叫"]
    assert engine.get_recent_fusions("pet_1", limit=0) == []


def test_current_state_expires_when_clock_advances_past_window():
    clock = MutableClock(datetime.fromisoformat("2026-07-19T10:00:00"))
    engine = AudioVisualFusionEngine(time_window_seconds=30, clock=clock)
    engine.add_audio_result("pet_1", {
        "behavior": "吠叫",
        "timestamp": "2026-07-19T10:00:00",
    })

    clock.advance(seconds=31)

    assert engine.fuse("pet_1") is None


def test_malformed_timestamp_falls_back_to_ingestion_time():
    clock = MutableClock(datetime.fromisoformat("2026-07-19T10:00:00"))
    engine = AudioVisualFusionEngine(time_window_seconds=60, clock=clock)

    result = engine.add_audio_result("pet_1", {
        "behavior": "吠叫",
        "timestamp": "not-a-timestamp",
    })

    assert result.timestamp == "2026-07-19T10:00:00"


def test_timezone_timestamp_is_normalized_to_utc():
    clock = MutableClock(datetime.fromisoformat("2026-07-19T02:00:00"))
    engine = AudioVisualFusionEngine(time_window_seconds=60, clock=clock)

    result = engine.add_audio_result("pet_1", {
        "behavior": "吠叫",
        "timestamp": "2026-07-19T10:00:00+08:00",
    })

    assert result.timestamp == "2026-07-19T02:00:00"


def test_fusion_history_returns_defensive_copies():
    clock = MutableClock(datetime.fromisoformat("2026-07-19T10:00:00"))
    engine = AudioVisualFusionEngine(clock=clock)
    result = engine.add_audio_result("pet_1", {
        "behavior": "吠叫",
        "timestamp": "2026-07-19T10:00:00",
    })

    result.behavior = "mutated"
    result.sources.append("visual")
    first_read = engine.get_recent_fusions("pet_1")
    first_read[0].behavior = "changed-again"

    stored = engine.get_recent_fusions("pet_1")[0]
    assert stored.behavior == "吠叫"
    assert stored.sources == ["audio"]
