"""Test behavior analyzer rules engine"""
from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from behavior_analyzer.rules import BehaviorEvent, BehaviorRulesEngine, get_engine


def test_behavior_event_creation():
    event = BehaviorEvent(
        timestamp="2026-07-17T10:00:00",
        animal="狗",
        behavior="吠叫",
        confidence=0.9,
        is_alert=True,
        context={"location": "客厅"},
    )
    assert event.animal == "狗"
    assert event.behavior == "吠叫"
    assert event.is_alert is True
    d = event.to_dict()
    assert d["animal"] == "狗"
    assert d["confidence"] == 0.9


def test_rules_engine_analyze_dog_bark():
    engine = BehaviorRulesEngine()
    event = BehaviorEvent(
        timestamp=datetime.now().isoformat(),
        animal="狗",
        behavior="吠叫",
        confidence=0.9,
        is_alert=False,
    )
    result = engine.analyze(event)
    assert result["severity"] == "warning"
    assert "吠叫" in result["interpretation"]
    # 优化后的提示词包含益智玩具/互动建议
    assert any(kw in result["suggestion"] for kw in ["玩具", "互动", "陪伴", "遛狗"])


def test_rules_engine_analyze_cat_hiss():
    engine = BehaviorRulesEngine()
    event = BehaviorEvent(
        timestamp=datetime.now().isoformat(),
        animal="猫",
        behavior="嘶嘶",
        confidence=0.85,
        is_alert=True,
    )
    result = engine.analyze(event)
    assert result["severity"] == "alert"
    assert "嘶嘶" in result["interpretation"]
    # 优化后的提示词包含安全空间/停止互动建议
    assert any(kw in result["suggestion"] for kw in ["停止", "安全", "空间", "检查"])


def test_rules_engine_analyze_cat_midnight_meow():
    engine = BehaviorRulesEngine()
    # 直接 mock 时段判断，模拟凌晨3点
    engine._get_time_period = lambda h: "midnight"
    event = BehaviorEvent(
        timestamp="2026-07-17T03:00:00",
        animal="猫",
        behavior="喵叫",
        confidence=0.8,
        is_alert=False,
    )
    result = engine.analyze(event)
    assert result["severity"] == "warning"
    assert "半夜" in result["interpretation"]


def test_rules_engine_daily_report():
    engine = BehaviorRulesEngine()
    engine.analyze(BehaviorEvent(datetime.now().isoformat(), "狗", "吠叫", 0.9, False))
    engine.analyze(BehaviorEvent(datetime.now().isoformat(), "猫", "呼噜", 0.8, False))
    engine.analyze(BehaviorEvent(datetime.now().isoformat(), "狗", "呜咽", 0.7, True))

    report = engine.generate_daily_report()
    assert report["date"] == datetime.now().strftime("%Y-%m-%d")
    assert report["summary"]["total_events"] == 3
    assert report["summary"]["alert_count"] == 1
    assert "狗" in report["summary"]["animals_detected"]
    assert "猫" in report["summary"]["animals_detected"]
    assert report["health_score"] >= 0
    assert len(report["suggestions"]) > 0
    assert len(report["events"]) == 3


def test_health_score_calculation():
    engine = BehaviorRulesEngine()
    # No events -> score 50
    assert engine._calculate_health_score(0, 0, {}) == 50
    # All alerts, 1 unique behavior -> score = 0 + 2(diversity) + 0(data) = 2
    assert engine._calculate_health_score(10, 10, {"狗": 10}, unique_behaviors=1) == 2
    # No alerts, many events -> score 100
    assert engine._calculate_health_score(40, 0, {"狗": 40}, unique_behaviors=2) == 100
    # Mixed
    score = engine._calculate_health_score(20, 5, {"狗": 20}, unique_behaviors=2)
    assert 0 <= score <= 100


def test_score_label():
    engine = BehaviorRulesEngine()
    assert "良好" in engine._score_label(85)
    assert "正常" in engine._score_label(70)
    assert "注意" in engine._score_label(50)
    assert "关注" in engine._score_label(30)


def test_generate_play_suggestions():
    engine = BehaviorRulesEngine()
    suggestions = engine._generate_play_suggestions(
        {"狗": 5}, {"狗-吠叫": 15}, None, unique_behaviors=1, total_events=15
    )
    assert len(suggestions) > 0
    assert any("遛狗" in s or "吠叫" in s or "益智" in s for s in suggestions)

    suggestions = engine._generate_play_suggestions(
        {"猫": 3}, {"猫-喵叫": 8}, None, unique_behaviors=1, total_events=8
    )
    assert len(suggestions) > 0
    assert any("逗猫" in s or "喵叫" in s or "陪玩" in s for s in suggestions)

    suggestions = engine._generate_play_suggestions(
        {}, {}, None, unique_behaviors=0, total_events=0
    )
    assert len(suggestions) > 0
    assert any("检测到" in s or "摄像头" in s for s in suggestions)


def test_get_engine_singleton():
    e1 = get_engine()
    e2 = get_engine()
    assert e1 is e2


def test_unknown_behavior():
    engine = BehaviorRulesEngine()
    event = BehaviorEvent(
        timestamp=datetime.now().isoformat(),
        animal="鸟",
        behavior="鸣叫",
        confidence=0.5,
        is_alert=False,
    )
    result = engine.analyze(event)
    assert result["severity"] == "info"
    # 优化后的提示词：没有匹配规则时会给出咨询建议
    assert "规则" in result["interpretation"] or "咨询" in result["suggestion"]
