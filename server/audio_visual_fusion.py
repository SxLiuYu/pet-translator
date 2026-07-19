"""Time-windowed fusion for audio and visual pet behavior results."""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional


@dataclass
class FusionResult:
    pet_id: str
    behavior: str
    confidence: float
    sources: List[str] = field(default_factory=list)
    audio_behavior: str = ""
    visual_behavior: str = ""
    audio_confidence: float = 0.0
    visual_confidence: float = 0.0
    interpretation: str = ""
    suggestion: str = ""
    is_alert: bool = False
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "pet_id": self.pet_id,
            "behavior": self.behavior,
            "confidence": self.confidence,
            "sources": list(self.sources),
            "audio_behavior": self.audio_behavior,
            "visual_behavior": self.visual_behavior,
            "audio_confidence": self.audio_confidence,
            "visual_confidence": self.visual_confidence,
            "interpretation": self.interpretation,
            "suggestion": self.suggestion,
            "is_alert": self.is_alert,
            "timestamp": self.timestamp,
        }


class AudioVisualFusionEngine:
    """Fuse the latest audio and visual observations for each pet."""

    def __init__(
        self,
        time_window_seconds: int = 300,
        history_limit: int = 100,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        if time_window_seconds <= 0:
            raise ValueError("time_window_seconds must be greater than zero")
        self.time_window = timedelta(seconds=time_window_seconds)
        self.history_limit = max(1, history_limit)
        self._audio_buffer: Dict[str, List[dict]] = defaultdict(list)
        self._visual_buffer: Dict[str, List[dict]] = defaultdict(list)
        self._results: Dict[str, List[FusionResult]] = defaultdict(list)
        self._lock = threading.RLock()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def add_audio_result(self, pet_id: str, result: dict) -> FusionResult:
        return self._add_result(pet_id, result, "audio")

    def add_visual_result(self, pet_id: str, result: dict) -> FusionResult:
        return self._add_result(pet_id, result, "visual")

    def _add_result(self, pet_id: str, result: dict, source: str) -> FusionResult:
        target_pet_id = str(pet_id or "default")
        entry = dict(result)
        entry.update({
            "source": source,
            "pet_id": target_pet_id,
            "timestamp": self._normalize_timestamp(result.get("timestamp")),
        })
        with self._lock:
            buffer = self._audio_buffer if source == "audio" else self._visual_buffer
            buffer[target_pet_id].append(entry)
            self._cleanup_buffers(target_pet_id)
            if self._audio_buffer[target_pet_id] or self._visual_buffer[target_pet_id]:
                fused = self._fuse_unlocked(target_pet_id)
            else:
                fused = self._single_source_result(entry, target_pet_id, source)
            self._results[target_pet_id].append(fused)
            self._results[target_pet_id] = self._results[target_pet_id][-self.history_limit :]
            return self._copy_result(fused)

    def fuse(self, pet_id: str) -> Optional[FusionResult]:
        """Return the current fused state without adding a history entry."""
        target_pet_id = str(pet_id or "default")
        with self._lock:
            self._cleanup_buffers(target_pet_id)
            if not self._audio_buffer[target_pet_id] and not self._visual_buffer[target_pet_id]:
                return None
            return self._fuse_unlocked(target_pet_id)

    def _fuse_unlocked(self, pet_id: str) -> FusionResult:
        audio = self._latest(self._audio_buffer[pet_id])
        visual = self._latest(self._visual_buffer[pet_id])

        if audio and visual:
            audio_time = self._parse_timestamp(audio["timestamp"])
            visual_time = self._parse_timestamp(visual["timestamp"])
            if abs(audio_time - visual_time) <= self.time_window:
                return self._merge_results(audio, visual, pet_id)
            if audio_time > visual_time:
                return self._single_source_result(audio, pet_id, "audio")
            return self._single_source_result(visual, pet_id, "visual")
        if audio:
            return self._single_source_result(audio, pet_id, "audio")
        return self._single_source_result(visual, pet_id, "visual")

    @staticmethod
    def _latest(entries: List[dict]) -> Optional[dict]:
        if not entries:
            return None
        return max(entries, key=lambda entry: AudioVisualFusionEngine._parse_timestamp(entry["timestamp"]))

    def _merge_results(self, audio: dict, visual: dict, pet_id: str) -> FusionResult:
        audio_behavior = str(audio.get("behavior") or "")
        visual_behavior = str(visual.get("behavior") or "")
        audio_confidence = self._confidence(audio)
        visual_confidence = self._confidence(visual)
        animal = str(audio.get("animal") or visual.get("animal") or "宠物")

        if audio_behavior == visual_behavior:
            behavior = audio_behavior
            interpretation = f"声音和画面均检测到{animal}{behavior}，判断可信度较高"
        elif audio_behavior and visual_behavior:
            behavior = f"{audio_behavior} + {visual_behavior}"
            interpretation = (
                f"声音检测到{audio_behavior}，同期画面显示{visual_behavior}，"
                "已合并为多模态行为记录"
            )
        else:
            behavior = audio_behavior or visual_behavior or "unknown"
            interpretation = f"声音和画面共同提供了{animal}的行为线索"

        # Visual context is slightly more reliable for physical behavior, while
        # audio remains the primary source for vocal distress signals.
        confidence = round(audio_confidence * 0.45 + visual_confidence * 0.55, 3)
        suggestion = str(audio.get("suggestion") or visual.get("suggestion") or visual.get("description") or "继续观察")

        return FusionResult(
            pet_id=pet_id,
            behavior=behavior,
            confidence=confidence,
            sources=["audio", "visual"],
            audio_behavior=audio_behavior,
            visual_behavior=visual_behavior,
            audio_confidence=audio_confidence,
            visual_confidence=visual_confidence,
            interpretation=interpretation,
            suggestion=suggestion,
            is_alert=bool(audio.get("is_alert") or visual.get("is_alert") or visual.get("is_destructive")),
            timestamp=str(max(
                (audio, visual),
                key=lambda entry: self._parse_timestamp(entry["timestamp"]),
            )["timestamp"]),
        )

    def _single_source_result(self, entry: dict, pet_id: str, source: str) -> FusionResult:
        behavior = str(entry.get("behavior") or "unknown")
        confidence = self._confidence(entry)
        animal = str(entry.get("animal") or "宠物")
        source_name = "声音" if source == "audio" else "画面"
        return FusionResult(
            pet_id=pet_id,
            behavior=behavior,
            confidence=confidence,
            sources=[source],
            audio_behavior=behavior if source == "audio" else "",
            visual_behavior=behavior if source == "visual" else "",
            audio_confidence=confidence if source == "audio" else 0.0,
            visual_confidence=confidence if source == "visual" else 0.0,
            interpretation=f"{source_name}检测到{animal}{behavior}，等待另一数据源确认",
            suggestion=str(entry.get("suggestion") or entry.get("description") or "继续观察"),
            is_alert=bool(entry.get("is_alert") or entry.get("is_destructive")),
            timestamp=str(entry["timestamp"]),
        )

    def _cleanup_buffers(self, pet_id: str) -> None:
        all_entries = self._audio_buffer[pet_id] + self._visual_buffer[pet_id]
        if not all_entries:
            return
        latest_time = max(self._parse_timestamp(entry["timestamp"]) for entry in all_entries)
        cutoff = max(latest_time, self._now()) - self.time_window
        self._audio_buffer[pet_id] = [
            entry for entry in self._audio_buffer[pet_id]
            if self._parse_timestamp(entry["timestamp"]) >= cutoff
        ]
        self._visual_buffer[pet_id] = [
            entry for entry in self._visual_buffer[pet_id]
            if self._parse_timestamp(entry["timestamp"]) >= cutoff
        ]

    def get_recent_fusions(self, pet_id: str, limit: int = 10) -> List[FusionResult]:
        with self._lock:
            if limit <= 0:
                return []
            return [
                self._copy_result(result)
                for result in self._results[str(pet_id or "default")][-limit:]
            ]

    @staticmethod
    def _copy_result(result: FusionResult) -> FusionResult:
        return replace(result, sources=list(result.sources))

    @staticmethod
    def _confidence(entry: dict) -> float:
        try:
            return min(1.0, max(0.0, float(entry.get("confidence") or 0.0)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def _now(self) -> datetime:
        current = self._clock()
        if current.tzinfo is not None:
            current = current.astimezone(timezone.utc).replace(tzinfo=None)
        return current

    def _normalize_timestamp(self, value: object) -> str:
        try:
            return self._parse_timestamp(str(value)).isoformat() if value else self._now().isoformat()
        except (TypeError, ValueError):
            return self._now().isoformat()


_fusion_engine: Optional[AudioVisualFusionEngine] = None
_fusion_engine_lock = threading.Lock()


def get_fusion_engine() -> AudioVisualFusionEngine:
    global _fusion_engine
    if _fusion_engine is None:
        with _fusion_engine_lock:
            if _fusion_engine is None:
                _fusion_engine = AudioVisualFusionEngine()
    return _fusion_engine
