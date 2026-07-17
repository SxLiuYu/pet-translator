from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional

from storage.schema import DailyReport, Event, Pet, now_iso

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


class JsonRepository:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> Any:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: Any) -> None:
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)

    def _load_list(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        try:
            data = self._read()
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def all(self) -> list[dict]:
        with self._lock:
            return self._load_list()

    def save_all(self, records: list[dict]) -> None:
        with self._lock:
            self._write(records if isinstance(records, list) else [])


class PetRepository:
    def __init__(self):
        _ensure_dir(STORAGE_DIR)
        self._repo = JsonRepository(os.path.join(STORAGE_DIR, "pets.json"))
        self._lock = threading.Lock()

    def get_all(self) -> list[Pet]:
        return [Pet.from_dict(item) for item in self._repo.all()]

    def get_by_id(self, pet_id: str) -> Optional[Pet]:
        for item in self._repo.all():
            if str(item.get("id")) == str(pet_id):
                return Pet.from_dict(item)
        return None

    def create(self, pet: Pet) -> Pet:
        payload = pet.to_dict()
        if not payload.get("created_at"):
            payload["created_at"] = now_iso()
        if not payload.get("updated_at"):
            payload["updated_at"] = payload["created_at"]
        with self._lock:
            records = self._repo.all()
            records.append(payload)
            self._repo.save_all(records)
        return Pet.from_dict(payload)

    def update(self, pet_id: str, data: dict) -> Optional[Pet]:
        with self._lock:
            records = self._repo.all()
            for idx, item in enumerate(records):
                if str(item.get("id")) == str(pet_id):
                    updated = deepcopy(item)
                    updated.update({k: v for k, v in data.items() if k != "id"})
                    updated["updated_at"] = now_iso()
                    records[idx] = updated
                    self._repo.save_all(records)
                    return Pet.from_dict(updated)
        return None

    def delete(self, pet_id: str) -> bool:
        with self._lock:
            records = self._repo.all()
            filtered = [item for item in records if str(item.get("id")) != str(pet_id)]
            if len(filtered) == len(records):
                return False
            self._repo.save_all(filtered)
            return True


class EventRepository:
    def __init__(self):
        _ensure_dir(STORAGE_DIR)
        self._repo = JsonRepository(os.path.join(STORAGE_DIR, "events.json"))
        self._lock = threading.Lock()

    def add(self, event: Event) -> Event:
        payload = event.to_dict()
        if not payload.get("created_at"):
            payload["created_at"] = now_iso()
        if not payload.get("timestamp"):
            payload["timestamp"] = payload["created_at"]
        with self._lock:
            records = self._repo.all()
            records.append(payload)
            self._repo.save_all(records)
        return Event.from_dict(payload)

    def get_by_pet(self, pet_id: str, limit: int = 50, offset: int = 0) -> tuple[list[Event], int]:
        records = self._repo.all()
        filtered = [
            Event.from_dict(item)
            for item in records
            if str(item.get("pet_id")) == str(pet_id)
        ]
        filtered.sort(key=lambda x: x.timestamp or x.created_at or "", reverse=True)
        total = len(filtered)
        paged = filtered[offset : offset + limit]
        return paged, total

    def get_recent(self, limit: int = 100) -> list[Event]:
        records = self._repo.all()
        events = [Event.from_dict(item) for item in records]
        events.sort(key=lambda x: x.timestamp or x.created_at or "", reverse=True)
        return events[:limit]

    def get_by_id(self, event_id: str) -> Optional[Event]:
        for item in self._repo.all():
            if str(item.get("id")) == str(event_id):
                return Event.from_dict(item)
        return None

    def recent_by_pet(self, pet_id: str, limit: int = 50) -> list[Event]:
        events, _ = self.get_by_pet(pet_id, limit=limit)
        return events

    def update_feedback(self, event_id: str, feedback: str) -> Optional[Event]:
        with self._lock:
            records = self._repo.all()
            for idx, item in enumerate(records):
                if str(item.get("id")) == str(event_id):
                    item["feedback"] = feedback if feedback is not None else ""
                    records[idx] = item
                    self._repo.save_all(records)
                    return Event.from_dict(item)
        return None


class ReportRepository:
    def __init__(self):
        _ensure_dir(os.path.join(STORAGE_DIR, "reports"))
        self._lock = threading.Lock()

    def save_report(self, report: DailyReport) -> str:
        report_dir = os.path.join(STORAGE_DIR, "reports")
        _ensure_dir(report_dir)
        path = os.path.join(report_dir, f"{report.date or now_iso()[:10]}.json")
        payload = report.to_dict()
        with self._lock:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    def get_report(self, date: str, pet_id: str) -> Optional[DailyReport]:
        path = os.path.join(STORAGE_DIR, "reports", f"{date}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            report = DailyReport.from_dict(data)
            if pet_id and str(report.pet_id) != str(pet_id):
                return None
            return report
        except Exception:
            return None
