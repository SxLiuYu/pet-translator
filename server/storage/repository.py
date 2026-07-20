"""
server/storage/repository.py
数据仓库 - 使用 SQLite/SQLAlchemy 实现所有 CRUD 操作
保持原有接口不变
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional

from storage.database import (
    PetModel, EventModel, ReportModel,
    SessionLocal, get_db_session, init_db
)
from storage.schema import DailyReport, Event, Pet, now_iso


def _safe_str(value, default=""):
    return str(value) if value is not None else default


class PetRepository:
    """宠物仓库 - SQLite 实现"""

    def __init__(self):
        init_db()

    def _to_pet(self, model: PetModel) -> Pet:
        return Pet(
            id=model.id,
            name=model.name,
            species=model.species,
            breed=model.breed,
            age=model.age,
            avatar_url=model.avatar_url,
            personality_tags=model.personality_tags or [],
            health_notes=model.health_notes,
            quiet_hours=model.quiet_hours or [],
            owner_id=model.owner_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def get_all(self) -> list[Pet]:
        db = SessionLocal()
        try:
            pets = db.query(PetModel).all()
            return [self._to_pet(p) for p in pets]
        finally:
            db.close()

    def get_by_id(self, pet_id: str) -> Optional[Pet]:
        db = SessionLocal()
        try:
            pet = db.query(PetModel).filter(PetModel.id == str(pet_id)).first()
            return self._to_pet(pet) if pet else None
        finally:
            db.close()

    def create(self, pet: Pet) -> Pet:
        payload = pet.to_dict()
        if not payload.get("created_at"):
            payload["created_at"] = now_iso()
        if not payload.get("updated_at"):
            payload["updated_at"] = payload["created_at"]

        with get_db_session() as db:
            existing = db.query(PetModel).filter(PetModel.id == str(payload.get("id"))).first()
            if existing:
                for key, value in payload.items():
                    if key != "id":
                        setattr(existing, key, value)
                existing.updated_at = now_iso()
            else:
                db.add(PetModel(**{k: v for k, v in payload.items() if k in [
                    "id", "name", "species", "breed", "age", "avatar_url",
                    "personality_tags", "health_notes", "quiet_hours",
                    "owner_id", "created_at", "updated_at"
                ]}))
        return Pet.from_dict(payload)

    def update(self, pet_id: str, data: dict) -> Optional[Pet]:
        with get_db_session() as db:
            pet = db.query(PetModel).filter(PetModel.id == str(pet_id)).first()
            if pet:
                for key, value in data.items():
                    if key != "id" and hasattr(pet, key):
                        setattr(pet, key, value)
                pet.updated_at = now_iso()
                return self._to_pet(pet)

            # 尝试按名称和物种匹配
            target_name = _safe_str(data.get("name"))
            target_species = _safe_str(data.get("species"))
            for existing in db.query(PetModel).all():
                e = self._to_pet(existing)
                if e.id != pet_id and e.name == target_name and e.species == target_species:
                    for key, value in data.items():
                        if key != "id" and hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.id = pet_id
                    existing.updated_at = now_iso()
                    return self._to_pet(existing)
        return None

    def delete(self, pet_id: str) -> bool:
        with get_db_session() as db:
            pet = db.query(PetModel).filter(PetModel.id == str(pet_id)).first()
            if pet:
                db.delete(pet)
                return True
        return False


class EventRepository:
    """事件仓库 - SQLite 实现"""

    def __init__(self):
        init_db()

    def _to_event(self, model: EventModel) -> Event:
        return Event(
            id=model.id,
            pet_id=model.pet_id,
            timestamp=model.timestamp,
            source_type=model.source_type,
            source_ref=model.source_ref,
            animal=model.animal,
            behavior=model.behavior,
            confidence=model.confidence,
            is_alert=model.is_alert,
            severity=model.severity,
            period=model.period,
            interpretation=model.interpretation,
            suggestion=model.suggestion,
            evidence_paths=model.evidence_paths or {},
            feedback=model.feedback,
            created_at=model.created_at,
        )

    def add(self, event: Event) -> Event:
        payload = event.to_dict()
        if not payload.get("created_at"):
            payload["created_at"] = now_iso()
        if not payload.get("timestamp"):
            payload["timestamp"] = payload["created_at"]

        with get_db_session() as db:
            existing = db.query(EventModel).filter(EventModel.id == str(payload.get("id"))).first()
            if existing:
                for key, value in payload.items():
                    if hasattr(existing, key) and key != "id":
                        setattr(existing, key, value)
            else:
                db.add(EventModel(**{k: v for k, v in payload.items() if k in [
                    "id", "pet_id", "timestamp", "source_type", "source_ref",
                    "animal", "behavior", "confidence", "is_alert", "severity",
                    "period", "interpretation", "suggestion", "evidence_paths",
                    "feedback", "created_at"
                ]}))
        return Event.from_dict(payload)

    def get_by_pet(self, pet_id: str, limit: int = 50, offset: int = 0) -> tuple[list[Event], int]:
        db = SessionLocal()
        try:
            query = db.query(EventModel).filter(EventModel.pet_id == str(pet_id))
            total = query.count()
            events = query.order_by(EventModel.timestamp.desc()).offset(offset).limit(limit).all()
            return [self._to_event(e) for e in events], total
        finally:
            db.close()

    def get_recent(self, limit: int = 100) -> list[Event]:
        db = SessionLocal()
        try:
            events = db.query(EventModel).order_by(EventModel.timestamp.desc()).limit(limit).all()
            return [self._to_event(e) for e in events]
        finally:
            db.close()

    def get_by_id(self, event_id: str) -> Optional[Event]:
        db = SessionLocal()
        try:
            event = db.query(EventModel).filter(EventModel.id == str(event_id)).first()
            return self._to_event(event) if event else None
        finally:
            db.close()

    def recent_by_pet(self, pet_id: str, limit: int = 50) -> list[Event]:
        events, _ = self.get_by_pet(pet_id, limit=limit)
        return events

    def update_feedback(self, event_id: str, feedback: str) -> Optional[Event]:
        with get_db_session() as db:
            event = db.query(EventModel).filter(EventModel.id == str(event_id)).first()
            if event:
                event.feedback = feedback if feedback is not None else ""
                return self._to_event(event)
        return None


class ReportRepository:
    """报告仓库 - SQLite 实现"""

    def __init__(self):
        init_db()

    def _to_report(self, model: ReportModel) -> DailyReport:
        return DailyReport(
            date=model.date,
            pet_id=model.pet_id,
            pet_name=model.pet_name,
            health_score=model.health_score,
            health_status=model.health_status,
            total_events=model.total_events,
            alert_count=model.alert_count,
            event_breakdown=model.event_breakdown or {},
            hourly_chart=model.hourly_chart or {},
            top_alerts=model.top_alerts or [],
            suggestions=model.suggestions or [],
        )

    def save_report(self, report: DailyReport) -> str:
        with get_db_session() as db:
            existing = db.query(ReportModel).filter(
                ReportModel.date == report.date,
                ReportModel.pet_id == report.pet_id
            ).first()

            if existing:
                for key, value in report.to_dict().items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                db.add(ReportModel(**report.to_dict()))
        return report.date

    def get_report(self, date: str, pet_id: str) -> Optional[DailyReport]:
        db = SessionLocal()
        try:
            report = db.query(ReportModel).filter(
                ReportModel.date == date,
                ReportModel.pet_id == pet_id
            ).first()
            return self._to_report(report) if report else None
        finally:
            db.close()
