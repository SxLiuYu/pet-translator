"""Test audio classifier"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from audio_classifier.classifier import AudioClassifier


def test_classifier_init():
    clf = AudioClassifier()
    assert clf is not None
    assert clf.interpreter is None  # No model loaded in test env


def test_classify_mock_silence():
    clf = AudioClassifier()
    audio = np.zeros(1600, dtype=np.float32)
    result = clf.classify(audio)
    assert "animal" in result
    assert "behavior" in result
    assert "confidence" in result
    assert "is_pet_sound" in result
    assert "is_alert" in result
    assert result["confidence"] >= 0


def test_classify_mock_loud():
    clf = AudioClassifier()
    audio = np.ones(1600, dtype=np.float32) * 0.5
    result = clf.classify(audio)
    assert result["animal"] is not None
    assert result["is_pet_sound"] is True


def test_classify_mock_very_loud():
    clf = AudioClassifier()
    audio = np.ones(1600, dtype=np.float32) * 0.8
    result = clf.classify(audio)
    assert result["is_alert"] is True


def test_classify_mock_very_quiet():
    clf = AudioClassifier()
    audio = np.ones(1600, dtype=np.float32) * 0.01
    result = clf.classify(audio)
    assert result["animal"] is None
    assert result["is_pet_sound"] is False
    assert result["is_alert"] is False


def test_pet_sound_map():
    clf = AudioClassifier()
    assert "狗" in [v[0] for v in clf.PET_SOUND_MAP.values()]
    assert "猫" in [v[0] for v in clf.PET_SOUND_MAP.values()]
    assert "dog bark" in clf.PET_SOUND_MAP
    assert "cat meow" in clf.PET_SOUND_MAP
    assert "dog whine" in clf.ALERT_SOUNDS
    assert "cat caterwaul" in clf.ALERT_SOUNDS


def test_compute_mel_spectrogram():
    clf = AudioClassifier()
    audio = np.random.randn(16000).astype(np.float32)
    spec = clf._compute_mel_spectrogram(audio, 16000)
    assert isinstance(spec, np.ndarray)
    assert spec.ndim == 4  # (batch, time, freq, channels)


def test_mock_classify_returns_raw_predictions():
    clf = AudioClassifier()
    audio = np.ones(1600, dtype=np.float32) * 0.3
    result = clf.classify(audio)
    assert "raw_predictions" in result
    assert "mock_energy" in result["raw_predictions"]
