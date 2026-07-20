from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from storage import repository as repo
from storage.repository import PetRepository, EventRepository, ReportRepository
from storage.schema import Event, Pet, DailyReport


def test_pet_crud(tmp_path: "pathlib.Path") -> None:
    data_dir = tmp_path / "storage"
    data_dir.mkdir(parents=True, exist_ok=True)
    repo.STORAGE_DIR = str(data_dir)

    pr = PetRepository()
    pet = Pet(id="pet_001", name="旺财", species="狗", age=3)
    pr.create(pet)
    assert pr.get_by_id("pet_001").name == "旺财"
    updated = pr.update("pet_001", {"name": "旺财2"})
    assert updated is not None
    assert pr.get_by_id("pet_001").name == "旺财2"
    assert pr.delete("pet_999") is False
    assert pr.delete("pet_001") is True
    assert pr.get_by_id("pet_001") is None


def test_event_pet_filter_and_feedback(tmp_path: "pathlib.Path") -> None:
    data_dir = tmp_path / "storage"
    data_dir.mkdir(parents=True, exist_ok=True)
    repo.STORAGE_DIR = data_dir

    pr = PetRepository()
    pr.create(Pet(id="pet_001", name="旺财", species="狗"))
    pr.create(Pet(id="pet_002", name="咪咪", species="猫"))

    er = EventRepository()
    er.add(Event(id="e1", pet_id="pet_001", behavior="吠叫", timestamp="2026-07-16T10:00:00", confidence=0.9))
    er.add(Event(id="e2", pet_id="pet_002", behavior="喵叫", timestamp="2026-07-16T11:00:00", confidence=0.8))
    er.add(Event(id="e3", pet_id="pet_001", behavior="喘气", timestamp="2026-07-16T09:00:00", confidence=0.7))

    events, total = er.get_by_pet("pet_001")
    assert total == 2
    assert events[0].id == "e1"
    assert events[1].id == "e3"

    updated = er.update_feedback("e2", "false_positive")
    assert updated is not None
    assert updated.feedback == "false_positive"
    assert er.get_by_id("e2").feedback == "false_positive"


def test_report_persistence(tmp_path: "pathlib.Path") -> None:
    data_dir = tmp_path / "storage"
    data_dir.mkdir(parents=True, exist_ok=True)
    repo.STORAGE_DIR = str(data_dir)
    rr = ReportRepository()
    report = DailyReport(date="2026-07-16", pet_id="pet_001", pet_name="旺财", total_events=5, alert_count=1)
    rr.save_report(report)
    loaded = rr.get_report("2026-07-16", "pet_001")
    assert loaded is not None
    assert loaded.pet_name == "旺财"
    assert rr.get_report("2026-07-15", "pet_001") is None
