"""
audio_visual_fusion.py
??+?????????
?????????????????????????
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger("pet_translator.fusion")


@dataclass
class FusionResult:
    """??????"""
    behavior: str
    confidence: float
    sources: List[str] = field(default_factory=list)  # ["audio", "visual"]
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
            "behavior": self.behavior,
            "confidence": self.confidence,
            "sources": self.sources,
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
    """
    ??-??????
    
    ????:
    1. ??????: ????? 5 ??????+????????
    2. ?????: ??????????????????
    3. ????: ???????????, ??? "????"
    4. ????: ????? alert ?????? alert
    """
    
    # ????????? (???)
    BEHAVIOR_SIMILARITY = {
        ("?", "??"): {"?": ["??", "??"], "?": []},
        ("?", "??"): {"?": ["??", "??"], "?": []},
        ("?", "??"): {"?": ["??", "??"], "?": []},
        ("?", "??"): {"?": [], "?": ["??", "??"]},
        ("?", "??"): {"?": [], "?": ["??", "??"]},
        ("?", "??"): {"?": [], "?": ["??", "??"]},
    }
    
    # ??????
    INTERPRETATION_TEMPLATES = {
        "both_match": "??????{behavior}??????{behavior}?????{animal}??{behavior}",
        "audio_only": "???{animal}??{behavior}?????????",
        "visual_only": "??????{animal}??{behavior}?????????",
        "conflict": "????{audio_behavior}?????{visual_behavior}???????????",
        "mixed": "{animal}?????{audio_behavior}?{visual_behavior}??",
    }
    
    def __init__(self, time_window_seconds: int = 300):
        """
        Args:
            time_window_seconds: ????????? 5 ???
        """
        self.time_window = timedelta(seconds=time_window_seconds)
        self._audio_buffer: Dict[str, List[dict]] = defaultdict(list)
        self._visual_buffer: Dict[str, List[dict]] = defaultdict(list)
        self._results: List[FusionResult] = []
    
    def add_audio_result(self, pet_id: str, result: dict):
        """????????????"""
        entry = {
            "source": "audio",
            "pet_id": pet_id,
            "timestamp": datetime.now().isoformat(),
            **result,
        }
        self._audio_buffer[pet_id].append(entry)
        self._cleanup_buffers(pet_id)
    
    def add_visual_result(self, pet_id: str, result: dict):
        """????????????"""
        entry = {
            "source": "visual",
            "pet_id": pet_id,
            "timestamp": datetime.now().isoformat(),
            **result,
        }
        self._visual_buffer[pet_id].append(entry)
        self._cleanup_buffers(pet_id)
    
    def fuse(self, pet_id: str) -> Optional[FusionResult]:
        """
        ???????????
        
        ??: FusionResult ? None???????
        """
        audio_entries = self._audio_buffer.get(pet_id, [])
        visual_entries = self._visual_buffer.get(pet_id, [])
        
        if not audio_entries and not visual_entries:
            return None
        
        # ??????????
        best_audio = self._find_matching(audio_entries, visual_entries) if audio_entries and visual_entries else None
        best_visual = self._find_matching(visual_entries, audio_entries) if audio_entries and visual_entries else None
        
        now = datetime.now()
        
        if best_audio and best_visual:
            # ???????? ? ??
            return self._merge_results(best_audio, best_visual, pet_id, now)
        elif best_audio:
            # ????
            return self._single_source_result(best_audio, pet_id, now, "audio")
        elif best_visual:
            # ????
            return self._single_source_result(best_visual, pet_id, now, "visual")
        
        return None
    
    def _find_matching(self, primary: List[dict], secondary: List[dict]) -> Optional[dict]:
        """? secondary ???? primary ?????????"""
        if not secondary:
            return None
        primary_ts = datetime.fromisoformat(primary[-1]["timestamp"])
        for entry in reversed(secondary):
            entry_ts = datetime.fromisoformat(entry["timestamp"])
            if abs(primary_ts - entry_ts) <= self.time_window:
                return entry
        return None
    
    def _merge_results(self, audio: dict, visual: dict, pet_id: str, now: datetime) -> FusionResult:
        """?????????"""
        audio_behavior = audio.get("behavior", "")
        visual_behavior = visual.get("behavior", "")
        audio_conf = audio.get("confidence", 0.0)
        visual_conf = visual.get("confidence", 0.0)
        animal = audio.get("animal", visual.get("animal", "??"))
        
        # ????????
        if audio_conf >= visual_conf:
            behavior = audio_behavior
            confidence = audio_conf
        else:
            behavior = visual_behavior
            confidence = visual_conf
        
        # ??????
        if audio_behavior == visual_behavior:
            interpretation = self.INTERPRETATION_TEMPLATES["both_match"].format(
                behavior=behavior, animal=animal
            )
        elif audio_behavior and visual_behavior:
            interpretation = self.INTERPRETATION_TEMPLATES["conflict"].format(
                audio_behavior=audio_behavior, visual_behavior=visual_behavior
            )
            behavior = f"{audio_behavior}/{visual_behavior}"
        else:
            behavior = audio_behavior or visual_behavior
            interpretation = "??????????????"
        
        # ????
        is_alert = audio.get("is_alert", False) or visual.get("is_destructive", False)
        
        suggestion = audio.get("suggestion", visual.get("description", "????"))
        
        return FusionResult(
            behavior=behavior,
            confidence=confidence,
            sources=["audio", "visual"],
            audio_behavior=audio_behavior,
            visual_behavior=visual_behavior,
            audio_confidence=audio_conf,
            visual_confidence=visual_conf,
            interpretation=interpretation,
            suggestion=suggestion,
            is_alert=is_alert,
            timestamp=now.isoformat(),
        )
    
    def _single_source_result(self, entry: dict, pet_id: str, now: datetime, source: str) -> FusionResult:
        """??????"""
        is_alert = entry.get("is_alert", False)
        if source == "audio":
            behavior = entry.get("behavior", "")
            confidence = entry.get("confidence", 0.0)
            animal = entry.get("animal", "??")
            interpretation = self.INTERPRETATION_TEMPLATES["audio_only"].format(
                behavior=behavior, animal=animal
            )
        else:
            behavior = entry.get("behavior", "unknown")
            confidence = entry.get("confidence", 0.0)
            animal = entry.get("animal", "??")
            interpretation = self.INTERPRETATION_TEMPLATES["visual_only"].format(
                behavior=behavior, animal=animal
            )
        
        return FusionResult(
            behavior=behavior,
            confidence=confidence,
            sources=[source],
            audio_behavior=entry.get("behavior", "") if source == "audio" else "",
            visual_behavior=entry.get("behavior", "") if source == "visual" else "",
            audio_confidence=confidence if source == "audio" else 0.0,
            visual_confidence=confidence if source == "visual" else 0.0,
            interpretation=interpretation,
            suggestion=entry.get("suggestion", entry.get("description", "????")),
            is_alert=is_alert,
            timestamp=now.isoformat(),
        )
    
    def _cleanup_buffers(self, pet_id: str):
        """???????"""
        now = datetime.now()
        cutoff = now - self.time_window
        
        for buf in [self._audio_buffer, self._visual_buffer]:
            if pet_id in buf:
                buf[pet_id] = [
                    e for e in buf[pet_id]
                    if datetime.fromisoformat(e["timestamp"]) >= cutoff
                ]
    
    def get_recent_fusions(self, pet_id: str, limit: int = 10) -> List[FusionResult]:
        """?????????"""
        return self._results[-limit:]


# ??
_fusion_engine: Optional[AudioVisualFusionEngine] = None


def get_fusion_engine() -> AudioVisualFusionEngine:
    global _fusion_engine
    if _fusion_engine is None:
        _fusion_engine = AudioVisualFusionEngine()
    return _fusion_engine
