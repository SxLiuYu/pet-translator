"""
行为规则引擎
将声纹识别结果转化为可理解的行为分析 + 建议
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger("pet_translator.rules")


@dataclass
class BehaviorEvent:
    """单次行为事件"""
    timestamp: str
    animal: str
    behavior: str
    confidence: float
    is_alert: bool
    context: Dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "animal": self.animal,
            "behavior": self.behavior,
            "confidence": self.confidence,
            "is_alert": self.is_alert,
            "context": self.context,
        }


class BehaviorRulesEngine:
    """
    行为规则引擎

    规则设计: 每个规则 = (触发条件, 严重程度, 行为解读, 建议)
    """

    def __init__(self):
        self.daily_events: List[BehaviorEvent] = []
        self.hourly_stats: Dict[int, Dict] = {}
        self._load_rules()

    def _load_rules(self):
        """加载行为-行为对应规则表"""
        self.rules = {
            # ========== 狗类 ==========
            ("狗", "吠叫"): {
                "severity": "warning",
                "interpretation": "持续吠叫 = 孤独焦虑 / 对门外刺激反应",
                "suggestion": "考虑上班时开音响或开互动摄像头，训练独处安静",
            },
            ("狗", "嚎叫"): {
                "severity": "warning",
                "interpretation": "嚎叫 = 高度焦虑或回应远处声音",
                "suggestion": "检查是否有噪音刺激，增加运动量消耗精力",
            },
            ("狗", "呜咽"): {
                "severity": "info",
                "interpretation": "呜咽 = 身体不适或寻求关注",
                "suggestion": "检查身体是否有异常，陪伴安抚",
            },
            ("狗", "喘气"): {
                "severity": "info",
                "interpretation": "喘气 = 正常散热或兴奋，过热时需注意",
                "suggestion": "确认室内温度，提供饮水",
            },

            # ========== 猫类 ==========
            ("猫", "喵叫"): {
                "severity": "info",
                "interpretation": "喵叫 = 需求未被满足 (食物/关注/猫砂盆)",
                "suggestion": "检查食碗、水碗、猫砂盆状态",
            },
            ("猫", "呼噜"): {
                "severity": "info",
                "interpretation": "呼噜 = 舒适满足 (少数情况是疼痛缓解)",
                "suggestion": "正常表现，可轻柔互动",
            },
            ("猫", "嘶嘶"): {
                "severity": "alert",
                "interpretation": "嘶嘶 = 恐惧/防御/压力过大",
                "suggestion": "立即移除压力源，检查是否有其他动物或陌生人干扰",
            },
            ("猫", "嚎叫"): {
                "severity": "alert",
                "interpretation": "嚎叫 = 发情期 / 极度不适 (老年猫认知障碍)",
                "suggestion": "未绝育优先考虑绝育；老年猫建议体检",
            },
            ("猫", "低吼"): {
                "severity": "alert",
                "interpretation": "低吼 = 不满警告，可能攻击前兆",
                "suggestion": "停止当前互动，给猫空间冷静",
            },
        }

        # 时段敏感规则 (额外修饰)
        self.time_rules = {
            "midnight": lambda h: 0 <= h <= 5,
            "dawn":     lambda h: 5 < h <= 7,
            "work_hours": lambda h: 9 <= h <= 18,
            "evening":  lambda h: 18 < h <= 22,
        }

    def analyze(self, event: BehaviorEvent) -> Dict:
        """分析单次行为事件，返回行为解读和建议"""
        now = datetime.now()
        hour = now.hour
        period = self._get_time_period(hour)
        sound_pattern = self._detect_sound_pattern(event, period)

        # 查规则
        key = (event.animal, event.behavior)
        rule = self.rules.get(key, {
            "severity": "info",
            "interpretation": f"{event.animal}{event.behavior}，持续观察中",
            "suggestion": "如频繁出现建议联系宠物行为师",
        })

        # 时段修饰 (猫半夜喵叫特殊规则)
        if event.animal == "猫" and event.behavior == "喵叫" and period == "midnight":
            rule = {
                "severity": "warning",
                "interpretation": "半夜喵叫 = 精力过剩 / 饥饿 / 发情期",
                "suggestion": "睡前陪玩15分钟消耗精力，睡前喂食；持续建议绝育",
            }

        result = {
            "timestamp": event.timestamp,
            "animal": event.animal,
            "behavior": event.behavior,
            "confidence": event.confidence,
            "severity": rule.get("severity", "info"),
            "is_alert": event.is_alert or rule.get("severity") == "alert",
            "period": period,
            "sound_pattern": sound_pattern,
            "interpretation": rule.get("interpretation", "正在观察..."),
            "suggestion": rule.get("suggestion", "持续观察，必要时联系兽医"),
        }

        self.daily_events.append(event)
        self._update_hourly_stats(hour, result)
        return result

    def _get_time_period(self, hour: int) -> str:
        for name, fn in self.time_rules.items():
            if fn(hour):
                return name
        return "other"

    def _detect_sound_pattern(self, event: BehaviorEvent, period: str) -> str:
        """检测声音模式"""
        if event.behavior == "吠叫":
            return "high_frequency_short" if period == "work_hours" else "sustained"
        return "normal"

    def _update_hourly_stats(self, hour: int, result: Dict):
        if hour not in self.hourly_stats:
            self.hourly_stats[hour] = {"count": 0, "alerts": 0, "animals": {}}
        self.hourly_stats[hour]["count"] += 1
        if result["is_alert"]:
            self.hourly_stats[hour]["alerts"] += 1
        animal = result["animal"]
        self.hourly_stats[hour]["animals"][animal] = \
            self.hourly_stats[hour]["animals"].get(animal, 0) + 1

    def generate_daily_report(self) -> Dict:
        """生成今日精神状态报告"""
        now = datetime.now()
        total = len(self.daily_events)
        alerts = sum(1 for e in self.daily_events if e.is_alert)
        animals = {}
        for e in self.daily_events:
            animals[e.animal] = animals.get(e.animal, 0) + 1

        behavior_summary = {}
        for e in self.daily_events:
            key = f"{e.animal}-{e.behavior}"
            behavior_summary[key] = behavior_summary.get(key, 0) + 1

        active_hours = sorted(self.hourly_stats.items(), key=lambda x: -x[1]["count"])
        peak_hour = active_hours[0][0] if active_hours else None

        suggestions = self._generate_play_suggestions(animals, behavior_summary, peak_hour)
        health_score = self._calculate_health_score(total, alerts, animals)

        return {
            "date": now.strftime("%Y-%m-%d"),
            "summary": {
                "total_events": total,
                "alert_count": alerts,
                "animals_detected": list(animals.keys()),
                "event_breakdown": behavior_summary,
                "peak_active_hour": f"{peak_hour}:00" if peak_hour is not None else "N/A",
            },
            "health_score": health_score,
            "health_status": self._score_label(health_score),
            "suggestions": suggestions,
            "hourly_chart": {
                str(h): {"total": v["count"], "alerts": v["alerts"]}
                for h, v in sorted(self.hourly_stats.items())
            },
            "events": [e.to_dict() for e in self.daily_events[-20:]],
        }

    def _generate_play_suggestions(self, animals, behavior_summary, peak_hour) -> List[str]:
        """根据今日行为生成陪玩建议"""
        suggestions = []
        has_dog = "狗" in animals
        has_cat = "猫" in animals

        if has_dog:
            bark_count = behavior_summary.get("狗-吠叫", 0)
            if bark_count > 10:
                suggestions.append("🐕 今日吠叫偏多，建议增加遛狗时长 (至少30分钟)，消耗多余精力")
            if peak_hour and 9 <= peak_hour <= 18:
                suggestions.append("🐕 狗狗白天独自在家吠叫，考虑使用互动玩具或请宠物托管")

        if has_cat:
            meow_count = behavior_summary.get("猫-喵叫", 0)
            if meow_count > 5:
                suggestions.append("🐱 猫咪今日喵叫较多，睡前用逗猫棒陪玩15-20分钟消耗精力")
            if peak_hour and (0 <= peak_hour <= 5):
                suggestions.append("🐱 发现夜间活跃，建议调整喂食时间，傍晚多陪玩")

        if not has_dog and not has_cat:
            suggestions.append("今日未检测到宠物声音，确认摄像头是否正常工作")

        if not suggestions:
            suggestions.append("✅ 今日宠物表现安静，继续保持当前作息即可 🐾")

        return suggestions

    def _calculate_health_score(self, total: int, alerts: int, animals: Dict) -> int:
        """综合健康评分 (0-100)"""
        if total == 0:
            return 50
        alert_ratio = alerts / total
        score = max(0, 100 - int(alert_ratio * 200))
        if total > 30:
            score = min(100, score + 10)
        return score

    def _score_label(self, score: int) -> str:
        if score >= 80: return "😊 精神状态良好"
        if score >= 60: return "🙂 状态正常"
        if score >= 40: return "😐 需要注意"
        return "😟 建议关注"


# 单例
_engine: Optional[BehaviorRulesEngine] = None

def get_engine() -> BehaviorRulesEngine:
    global _engine
    if _engine is None:
        _engine = BehaviorRulesEngine()
    return _engine
