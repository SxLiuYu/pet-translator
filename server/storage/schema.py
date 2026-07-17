from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _coerce_str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def now_iso() -> str:
    return datetime.now().isoformat()


@dataclass
class Pet:
    id: str
    name: str = ""
    species: str = ""
    breed: str = ""
    age: int = 0
    avatar_url: str = ""
    personality_tags: list[str] = field(default_factory=list)
    health_notes: str = ""
    quiet_hours: list[str] = field(default_factory=list)
    owner_id: str = "default"
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, payload: dict) -> "Pet":
        return cls(
            id=_coerce_str(payload.get("id")),
            name=_coerce_str(payload.get("name")),
            species=_coerce_str(payload.get("species")),
            breed=_coerce_str(payload.get("breed")),
            age=int(payload.get("age") or 0),
            avatar_url=_coerce_str(payload.get("avatar_url")),
            personality_tags=list(payload.get("personality_tags") or []),
            health_notes=_coerce_str(payload.get("health_notes")),
            quiet_hours=list(payload.get("quiet_hours") or []),
            owner_id=_coerce_str(payload.get("owner_id"), "default"),
            created_at=_coerce_str(payload.get("created_at")),
            updated_at=_coerce_str(payload.get("updated_at")),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "species": self.species,
            "breed": self.breed,
            "age": self.age,
            "avatar_url": self.avatar_url,
            "personality_tags": self.personality_tags,
            "health_notes": self.health_notes,
            "quiet_hours": self.quiet_hours,
            "owner_id": self.owner_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Event:
    id: str
    pet_id: str
    timestamp: str = ""
    source_type: str = ""
    source_ref: str = ""
    animal: str = ""
    behavior: str = ""
    confidence: float = 0.0
    is_alert: bool = False
    severity: str = "info"
    period: str = ""
    interpretation: str = ""
    suggestion: str = ""
    evidence_paths: dict = field(default_factory=dict)
    feedback: str = ""
    created_at: str = ""

    @classmethod
    def from_dict(cls, payload: dict) -> "Event":
        return cls(
            id=_coerce_str(payload.get("id")),
            pet_id=_coerce_str(payload.get("pet_id")),
            timestamp=_coerce_str(payload.get("timestamp")),
            source_type=_coerce_str(payload.get("source_type")),
            source_ref=_coerce_str(payload.get("source_ref")),
            animal=_coerce_str(payload.get("animal")),
            behavior=_coerce_str(payload.get("behavior")),
            confidence=float(payload.get("confidence") or 0.0),
            is_alert=_coerce_bool(payload.get("is_alert"), False),
            severity=_coerce_str(payload.get("severity"), "info"),
            period=_coerce_str(payload.get("period")),
            interpretation=_coerce_str(payload.get("interpretation")),
            suggestion=_coerce_str(payload.get("suggestion")),
            evidence_paths=dict(payload.get("evidence_paths") or {}),
            feedback=_coerce_str(payload.get("feedback")),
            created_at=_coerce_str(payload.get("created_at")),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "timestamp": self.timestamp,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "animal": self.animal,
            "behavior": self.behavior,
            "confidence": self.confidence,
            "is_alert": self.is_alert,
            "severity": self.severity,
            "period": self.period,
            "interpretation": self.interpretation,
            "suggestion": self.suggestion,
            "evidence_paths": dict(self.evidence_paths or {}),
            "feedback": self.feedback,
            "created_at": self.created_at,
        }


@dataclass
class DailyReport:
    date: str = ""
    pet_id: str = ""
    pet_name: str = ""
    health_score: int = 0
    health_status: str = ""
    total_events: int = 0
    alert_count: int = 0
    event_breakdown: dict = field(default_factory=dict)
    hourly_chart: dict = field(default_factory=dict)
    top_alerts: list = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict) -> "DailyReport":
        return cls(
            date=_coerce_str(payload.get("date")),
            pet_id=_coerce_str(payload.get("pet_id")),
            pet_name=_coerce_str(payload.get("pet_name")),
            health_score=int(payload.get("health_score") or 0),
            health_status=_coerce_str(payload.get("health_status")),
            total_events=int(payload.get("total_events") or 0),
            alert_count=int(payload.get("alert_count") or 0),
            event_breakdown=dict(payload.get("event_breakdown") or {}),
            hourly_chart=dict(payload.get("hourly_chart") or {}),
            top_alerts=list(payload.get("top_alerts") or []),
            suggestions=list(payload.get("suggestions") or []),
        )

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "pet_id": self.pet_id,
            "pet_name": self.pet_name,
            "health_score": self.health_score,
            "health_status": self.health_status,
            "total_events": self.total_events,
            "alert_count": self.alert_count,
            "event_breakdown": dict(self.event_breakdown or {}),
            "hourly_chart": dict(self.hourly_chart or {}),
            "top_alerts": list(self.top_alerts or []),
            "suggestions": list(self.suggestions or []),
        }
