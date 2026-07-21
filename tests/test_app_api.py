from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import server.app as app_module
from audio_visual_fusion import AudioVisualFusionEngine
from camera.behavior_detector import Detection, VisualBehavior
from storage import repository as repo
from storage.repository import PetRepository, EventRepository
from storage.schema import Event, Pet


class DummyClassifier:
    def classify(self, audio_array, sample_rate=16000):
        return {
            "animal": "狗",
            "behavior": "吠叫",
            "confidence": 0.9,
            "is_pet_sound": True,
            "is_alert": True,
            "raw_predictions": {"dog bark": 0.9},
            "timestamp": datetime.now().isoformat(),
        }


class DummyEngine:
    daily_events = []

    def analyze(self, event):
        return {
            "severity": "warning",
            "interpretation": "持续吠叫",
            "suggestion": "增加运动量",
            "period": "work_hours",
        }

    def generate_daily_report(self):
        return {
            "date": "2026-07-16",
            "pet_id": None,
            "pet_name": None,
            "summary": {"total_events": 0, "alert_count": 0},
            "suggestions": ["保持现状"],
            "hourly_chart": {},
            "top_alerts": [],
        }


class DummyNotifier:
    def send_pet_report(self, report):
        return {"status": "skipped"}

    def send_alert(self, *args, **kwargs):
        return {"status": "skipped"}


class DummyCameraManager:
    def status(self):
        return {}

    def get(self, name):
        return None

    def get_frame(self, name):
        return None

    def register_rtsp(self, *args, **kwargs):
        return MagicMock()

    def register_usb(self, *args, **kwargs):
        return MagicMock()

    def register_esp32cam(self, *args, **kwargs):
        return MagicMock()


class DummyVision:
    def __init__(self):
        self.model = None


class DummyFrame:
    image = None
    jpeg_bytes = b"test-jpeg"


class DetectingCameraManager(DummyCameraManager):
    def get_frame(self, name):
        return DummyFrame()


class DetectingVision:
    model = object()

    def detect(self, image):
        return VisualBehavior(
            timestamp=datetime.now().timestamp(),
            behavior="跑动",
            confidence=0.8,
            activity_level="high",
            description="检测到快速跑动",
            detections=[Detection(class_name="dog", confidence=0.9, bbox=[0, 0, 10, 10])],
        )


@pytest.fixture()
def app(monkeypatch, tmp_path):
    repo.STORAGE_DIR = str(tmp_path / "storage")
    monkeypatch.setattr(app_module, "classifier", DummyClassifier(), raising=False)
    monkeypatch.setattr(app_module, "behavior_engine", DummyEngine(), raising=False)
    monkeypatch.setattr(app_module, "pet_repo", PetRepository(), raising=False)
    monkeypatch.setattr(app_module, "event_repo", EventRepository(), raising=False)
    monkeypatch.setattr(app_module, "report_repo", None, raising=False)
    monkeypatch.setattr(app_module, "fusion_engine", AudioVisualFusionEngine(), raising=False)
    monkeypatch.setattr(app_module, "camera_manager", DummyCameraManager(), raising=False)
    monkeypatch.setattr(app_module, "vision_detector", DummyVision(), raising=False)
    return app_module.app


def build_client(app):
    from starlette.testclient import TestClient

    client = TestClient(app)
    return client


def test_list_pets(app):
    client = build_client(app)
    response = client.post("/api/pets", json={"pet_id": "pet_1", "name": "旺财", "species": "狗"})
    assert response.status_code == 200
    assert response.json()["pet"]["name"] == "旺财"

    response = client.get("/api/pets")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_health_includes_registered_pets(app):
    client = build_client(app)
    client.post("/api/pets", json={"pet_id": "pet_1", "name": "旺财", "species": "狗"})

    response = client.get("/health")

    assert response.status_code == 200
    pets = response.json()["pets"]
    assert len(pets) == 1
    assert pets[0]["id"] == "pet_1"
    assert pets[0]["name"] == "旺财"


def test_create_pet_conflict(app):
    client = build_client(app)
    client.post("/api/pets", json={"pet_id": "pet_1", "name": "旺财", "species": "狗"})
    response = client.post("/api/pets", json={"pet_id": "pet_1", "name": "旺财2", "species": "狗"})
    assert response.status_code == 409


def test_get_update_delete_pet(app):
    client = build_client(app)
    client.post("/api/pets", json={"pet_id": "pet_1", "name": "旺财", "species": "狗"})

    response = client.get("/api/pets/pet_1")
    assert response.status_code == 200
    assert response.json()["pet"]["species"] == "狗"

    response = client.put("/api/pets/pet_1", json={"name": "旺财2"})
    assert response.status_code == 200
    assert response.json()["pet"]["name"] == "旺财2"

    response = client.delete("/api/pets/pet_1")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    response = client.get("/api/pets/pet_1")
    assert response.status_code == 404


def test_events_filter_by_pet_and_feedback(app, monkeypatch):
    client = build_client(app)
    client.post("/api/pets", json={"pet_id": "pet_1", "name": "旺财", "species": "狗"})
    client.post("/api/pets", json={"pet_id": "pet_2", "name": "咪咪", "species": "猫"})

    event_repo = app_module.event_repo
    event_repo.add(Event(id="e1", pet_id="pet_1", behavior="吠叫", confidence=0.9))
    event_repo.add(Event(id="e2", pet_id="pet_2", behavior="喵叫", confidence=0.8))
    event_repo.add(Event(id="e3", pet_id="pet_1", behavior="喘气", confidence=0.7))

    response = client.get("/api/events", params={"pet_id": "pet_1"})
    assert response.status_code == 200
    body = response.json()
    assert body["pet_id"] == "pet_1"
    assert len(body["events"]) == 2
    assert {event["id"] for event in body["events"]} == {"e1", "e3"}

    monkeypatch.setenv("PET_ID", "pet_1")
    response = client.get("/api/events")
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["pet_id"] is None

    response = client.post("/api/event/e2/feedback", json={"feedback": "false_positive"})
    assert response.status_code == 200
    assert response.json()["feedback"] == "false_positive"


@pytest.mark.parametrize("path", [
    "/api/events?limit=0",
    "/api/events?limit=101",
    "/api/fusions?pet_id=pet_1&limit=0",
    "/api/fusions?pet_id=pet_1&limit=101",
])
def test_collection_limits_are_validated(app, path):
    response = build_client(app).get(path)

    assert response.status_code == 422


def test_upload_audio_persists_event_and_evidence(app, tmp_path, monkeypatch):
    wav_path = tmp_path / "pet.wav"
    wav_path.write_bytes(b"RIFF" + b"\x00" * 100)

    monkeypatch.setattr(app_module, "_load_audio", lambda path: ([0.0] * 1600, 16000), raising=False)
    monkeypatch.setenv("PET_ID", "pet_1")
    client = build_client(app)
    client.post("/api/pets", json={"pet_id": "pet_1", "name": "旺财", "species": "狗"})

    with open(wav_path, "rb") as f:
        response = client.post(
            "/api/upload_audio",
            params={"pet_id": "pet_1"},
            files={"file": ("pet.wav", f, "audio/wav")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"]
    assert body["animal"] == "狗"
    assert body["fusion"]["pet_id"] == "pet_1"
    assert body["fusion"]["sources"] == ["audio"]
    assert body["evidence"].get("audio")
    assert body["evidence"]["audio"].startswith(str(app_module.Path(__file__).resolve().parent.parent / "evidence" / "audio"))
    stored = app_module.event_repo.get_by_id(body["event_id"])
    assert stored is not None
    assert stored.pet_id == "pet_1"

    response = client.get("/api/fusions", params={"pet_id": "pet_1"})
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_camera_detection_persists_and_fuses_visual_result(app, monkeypatch):
    monkeypatch.setattr(app_module, "camera_manager", DetectingCameraManager(), raising=False)
    monkeypatch.setattr(app_module, "vision_detector", DetectingVision(), raising=False)
    app_module.fusion_engine.add_audio_result("pet_1", {
        "animal": "狗",
        "behavior": "吠叫",
        "confidence": 0.6,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    response = build_client(app).post(
        "/api/camera/detect",
        params={"name": "living_room", "pet_id": "pet_1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pet_id"] == "pet_1"
    assert body["event_id"]
    assert body["fusion"]["sources"] == ["audio", "visual"]
    assert body["fusion"]["behavior"] == "吠叫 + 跑动"
    stored = app_module.event_repo.get_by_id(body["event_id"])
    assert stored is not None
    assert stored.source_type == "visual"
    assert stored.evidence_paths["image"].endswith(".jpg")


class TestRateLimiting:
    def test_auth_login_rate_limited(self, app):
        """Auth login endpoint should return 429 after 5 attempts in a minute."""
        from app import limiter
        limiter.reset()
        client = build_client(app)
        statuses = []
        for _ in range(6):
            resp = client.post(
                "/api/auth/login",
                json={"username": "nonexistent", "password": "wrong"},
            )
            statuses.append(resp.status_code)
        assert 429 in statuses, f"Expected 429 in responses, got {statuses}"
        assert statuses[-1] == 429

    def test_upload_audio_rate_limited(self, app, tmp_path, monkeypatch):
        """Upload audio endpoint should return 429 after 10 attempts."""
        from app import limiter
        limiter.reset()
        monkeypatch.setattr(app_module, "_load_audio", lambda path: ([0.0] * 1600, 16000), raising=False)
        monkeypatch.setenv("PET_ID", "pet_1")
        client = build_client(app)
        client.post("/api/pets", json={"pet_id": "pet_1", "name": "旺财", "species": "狗"})
        wav_path = tmp_path / "pet.wav"
        wav_path.write_bytes(b"RIFF" + b"\x00" * 100)

        statuses = []
        for _ in range(12):
            with open(wav_path, "rb") as f:
                resp = client.post(
                    "/api/upload_audio",
                    params={"pet_id": "pet_1"},
                    files={"file": ("pet.wav", f, "audio/wav")},
                )
            statuses.append(resp.status_code)
        assert 429 in statuses, f"Expected 429 in responses, got {statuses}"
        assert statuses[-1] == 429


class TestSecurityHeaders:
    def test_standard_security_headers_present(self, app):
        """Every response should include standard security headers."""
        from app import limiter
        limiter.reset()
        client = build_client(app)
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_hsts_absent_in_development(self, app):
        """HSTS header should not be set in development mode."""
        from app import limiter
        limiter.reset()
        client = build_client(app)
        resp = client.get("/health")
        assert "Strict-Transport-Security" not in resp.headers
