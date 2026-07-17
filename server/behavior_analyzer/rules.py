"""
行为规则引擎
将声纹识别结果转化为可理解的行为分析 + 建议
纯规则驱动，无需训练，所有解读基于预定义知识库
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

    纯规则驱动设计:
    - 每条规则 = (触发条件, 严重程度, 行为解读, 建议)
    - 时段敏感 + 频率敏感 + 组合行为检测
    - 模拟 LLM prompt 风格的自然语言解读
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
                "interpretation": "持续吠叫可能意味着分离焦虑、门外有动静，或者单纯想吸引你的注意",
                "suggestion": "白天独自在家吠叫 → 可留互动玩具或开电视/收音机；傍晚吠叫 → 先遛狗消耗精力再观察",
            },
            ("狗", "嚎叫"): {
                "severity": "warning",
                "interpretation": "嚎叫通常是高度焦虑的表现，也可能是在回应远处的同类声音",
                "suggestion": "检查窗外是否有噪音刺激（救护车、施工等），增加每日运动量有助于缓解焦虑",
            },
            ("狗", "呜咽"): {
                "severity": "info",
                "interpretation": "呜咽可能表示身体不适、害怕，或者只是想要你陪它玩",
                "suggestion": "先检查身体有无异常（外伤、腹部硬等），如无异常可尝试安抚陪伴",
            },
            ("狗", "喘气"): {
                "severity": "info",
                "interpretation": "喘气是正常散热方式，但过度喘气可能提示过热或紧张",
                "suggestion": "确认室内通风良好、饮水充足；如持续过度喘气且无运动，建议测量体温",
            },

            # ========== 猫类 ==========
            ("猫", "喵叫"): {
                "severity": "info",
                "interpretation": "喵叫是猫咪和你沟通的方式——可能在说\"我饿了\"\"陪我玩\"或\"猫砂盆该铲了\"",
                "suggestion": "依次检查：食碗有水吗？猫砂盆干净吗？上次陪玩是什么时候？",
            },
            ("猫", "呼噜"): {
                "severity": "info",
                "interpretation": "呼噜通常表示舒适和满足，是猫咪心情好的标志",
                "suggestion": "继续保持当前状态，可以轻柔抚摸或陪它玩耍",
            },
            ("猫", "嘶嘶"): {
                "severity": "alert",
                "interpretation": "嘶嘶声是猫咪的防御警告，说明它感到害怕或受到威胁",
                "suggestion": "立即停止当前互动，给猫咪安全空间；检查是否有陌生动物、人或噪音刺激",
            },
            ("猫", "嚎叫"): {
                "severity": "alert",
                "interpretation": "猫嚎叫常见于发情期、老年认知障碍，或身体明显不适",
                "suggestion": "未绝育建议优先安排绝育手术；老年猫频繁嚎叫建议做全面体检",
            },
            ("猫", "低吼"): {
                "severity": "alert",
                "interpretation": "低吼意味着猫咪已经很不耐烦了，再靠近可能会被攻击",
                "suggestion": "不要再靠近或试图抱它，给它空间冷静；等它主动靠近你再互动",
            },
        }

        # 时段敏感规则
        self.time_rules = {
            "midnight":   lambda h: 0 <= h <= 5,
            "dawn":       lambda h: 5 < h <= 7,
            "work_hours": lambda h: 9 <= h <= 18,
            "evening":    lambda h: 18 < h <= 22,
        }

        # 声音模式分类
        self.sound_patterns = {
            "吠叫": "sharp_repetitive",
            "嚎叫": "sustained_low",
            "呜咽": "high_pitch_intermittent",
            "喘气": "rhythmic_heavy",
            "喵叫": "mid_pitch_varied",
            "呼噜": "low_continuous",
            "嘶嘶": "sharp_short",
            "低吼": "low_guttural",
        }

        # 组合行为检测规则
        self.combo_rules = [
            {
                "behaviors": [("狗", "吠叫"), ("狗", "呜咽")],
                "window_minutes": 10,
                "interpretation": "吠叫+呜咽组合：分离焦虑可能性极高，宠物处于明显的心理压力状态",
                "suggestion": "建议使用摄像头双向语音安抚，或考虑宠物保姆/日托服务",
                "severity": "alert",
            },
            {
                "behaviors": [("猫", "嘶嘶"), ("猫", "低吼")],
                "window_minutes": 5,
                "interpretation": "嘶嘶+低吼组合：猫咪处于高度应激状态，可能有其他动物入侵它的领地",
                "suggestion": "立即检查家中是否有其他动物或陌生人，给猫咪安全藏身处",
                "severity": "alert",
            },
        ]

    def analyze(self, event: BehaviorEvent) -> Dict:
        """分析单次行为事件，返回行为解读和建议"""
        now = datetime.now()
        hour = now.hour
        period = self._get_time_period(hour)
        sound_pattern = self._detect_sound_pattern(event, period)

        # 查基础规则
        key = (event.animal, event.behavior)
        rule = self.rules.get(key, {
            "severity": "info",
            "interpretation": f"{event.animal}发出了{event.behavior}的声音，目前没有匹配的解读规则",
            "suggestion": "如频繁出现，建议用手机录下声音咨询宠物医生或行为师",
        })

        # 时段修饰规则
        rule = self._apply_time_modifiers(event, rule, period)

        # 频率修饰：短时间多次触发 → 升级严重程度
        freq = self._get_recent_frequency(event.animal, event.behavior, window_minutes=60)
        if freq >= 5 and rule["severity"] == "warning":
            rule = {
                "severity": "alert",
                "interpretation": f"{rule['interpretation']}（1小时内出现{freq}次，频率异常偏高）",
                "suggestion": f"短时间内频繁{event.behavior}，建议尽快查看摄像头确认情况；{rule['suggestion']}",
            }

        # 组合行为检测
        combo = self._detect_combo(event)
        if combo:
            rule = {
                "severity": combo["severity"],
                "interpretation": combo["interpretation"],
                "suggestion": combo["suggestion"],
            }

        result = {
            "timestamp": event.timestamp,
            "animal": event.animal,
            "behavior": event.behavior,
            "confidence": event.confidence,
            "severity": rule["severity"],
            "is_alert": rule["severity"] in ("alert",),
            "period": period,
            "sound_pattern": sound_pattern,
            "interpretation": rule["interpretation"],
            "suggestion": rule["suggestion"],
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
        return self.sound_patterns.get(event.behavior, "unknown")

    def _apply_time_modifiers(self, event: BehaviorEvent, rule: dict, period: str) -> dict:
        """时段修饰规则"""
        # 猫半夜喵叫
        if event.animal == "猫" and event.behavior == "喵叫" and period == "midnight":
            return {
                "severity": "warning",
                "interpretation": "猫咪半夜喵叫可能是精力过剩、饿了，或者处于发情期",
                "suggestion": "睡前用逗猫棒陪玩15分钟消耗精力，睡前放少量猫粮；持续半夜叫建议安排绝育",
            }
        # 狗半夜吠叫
        if event.animal == "狗" and event.behavior == "吠叫" and period == "midnight":
            return {
                "severity": "warning",
                "interpretation": "狗狗半夜吠叫可能是听到外面动静、需要上厕所，或身体不舒服",
                "suggestion": "睡前确保已遛狗+上厕所，检查院子/楼道是否有异常；如持续发生建议白噪音辅助",
            }
        # 工作日白天长时间吠叫
        if event.animal == "狗" and event.behavior == "吠叫" and period == "work_hours":
            return {
                "severity": "warning",
                "interpretation": "上班时间持续吠叫，分离焦虑可能性很高",
                "suggestion": "考虑留互动益智玩具（藏食球/Kong），开电视或宠物音乐；严重时请宠物保姆",
            }
        return rule

    def _get_recent_frequency(self, animal: str, behavior: str, window_minutes: int = 60) -> int:
        """统计最近 window_minutes 内某行为出现次数"""
        from datetime import timedelta
        if not self.daily_events:
            return 0
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        count = 0
        for e in reversed(self.daily_events):
            try:
                et = datetime.fromisoformat(e.timestamp)
                if et < cutoff:
                    break
                if e.animal == animal and e.behavior == behavior:
                    count += 1
            except (ValueError, TypeError):
                pass
        return count

    def _detect_combo(self, event: BehaviorEvent) -> Optional[dict]:
        """检测组合行为模式"""
        for combo in self.combo_rules:
            if (event.animal, event.behavior) not in combo["behaviors"]:
                continue
            # 检查最近的 events 是否有组合中的其他行为
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(minutes=combo["window_minutes"])
            matched = set()
            matched.add((event.animal, event.behavior))
            for e in self.daily_events[-50:]:
                try:
                    et = datetime.fromisoformat(e.timestamp)
                    if et < cutoff:
                        continue
                    key = (e.animal, e.behavior)
                    if key in combo["behaviors"]:
                        matched.add(key)
                except (ValueError, TypeError):
                    pass
            if len(matched) >= len(combo["behaviors"]):
                return combo
        return None

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

        # 检测行为多样性
        unique_behaviors = len(set((e.animal, e.behavior) for e in self.daily_events))

        suggestions = self._generate_play_suggestions(
            animals, behavior_summary, peak_hour, unique_behaviors, total
        )
        health_score = self._calculate_health_score(
            total, alerts, animals, unique_behaviors
        )

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

    def _generate_play_suggestions(
        self, animals, behavior_summary, peak_hour,
        unique_behaviors: int, total_events: int
    ) -> List[str]:
        """根据今日行为生成陪玩建议"""
        suggestions = []
        has_dog = "狗" in animals
        has_cat = "猫" in animals

        if has_dog:
            bark_count = behavior_summary.get("狗-吠叫", 0)
            whine_count = behavior_summary.get("狗-呜咽", 0)
            if bark_count > 10:
                suggestions.append(
                    "🐕 今日吠叫偏多，建议增加遛狗时长至30分钟以上，"
                    "出门前用益智玩具（藏食球/嗅闻垫）消耗精力"
                )
            if whine_count > 3:
                suggestions.append(
                    "🐕 今日多次呜咽，多关注狗狗情绪，回家后优先陪它玩耍建立安全感"
                )
            if peak_hour and 9 <= peak_hour <= 18:
                suggestions.append(
                    "🐕 白天在家活跃度高，考虑添置互动摄像头或请宠物托管陪伴"
                )

        if has_cat:
            meow_count = behavior_summary.get("猫-喵叫", 0)
            hiss_count = behavior_summary.get("猫-嘶嘶", 0)
            if meow_count > 5:
                suggestions.append(
                    "🐱 今日喵叫较多，睡前用逗猫棒陪玩15-20分钟，"
                    "并检查食物和水是否充足"
                )
            if hiss_count > 0:
                suggestions.append(
                    "🐱 检测到嘶嘶声（防御信号），检查家中是否有环境变化"
                    "或安全隐患，给猫咪留出安全躲藏空间"
                )
            if peak_hour and (0 <= peak_hour <= 5):
                suggestions.append(
                    "🐱 发现猫咪夜间活跃，建议傍晚增加陪玩时间消耗精力，"
                    "调整喂食时间至睡前"
                )

        if not has_dog and not has_cat:
            suggestions.append("今日未检测到宠物声音，请确认摄像头是否正常工作、宠物是否在家")

        if not suggestions:
            suggestions.append("✅ 今日宠物表现平静，继续保持当前作息即可 🐾")

        # 行为多样性建议
        if unique_behaviors <= 1 and total_events > 5:
            suggestions.append(
                "💡 今日宠物行为种类较少，考虑增加互动形式（新玩具、新散步路线）"
                "丰富它的日常体验"
            )

        return suggestions

    def _calculate_health_score(
        self, total: int, alerts: int, animals: Dict,
        unique_behaviors: int = 1
    ) -> int:
        """综合健康评分 (0-100)"""
        if total == 0:
            return 50  # 无数据 = 中性

        # 基础分：警报占比
        alert_ratio = alerts / total
        base_score = max(0, 100 - int(alert_ratio * 200))

        # 行为多样性加分（表现丰富说明精神状态好）
        diversity_bonus = min(10, unique_behaviors * 2)

        # 数据量加分（采样多更可信）
        if total > 30:
            data_bonus = 5
        elif total > 10:
            data_bonus = 3
        else:
            data_bonus = 0

        score = min(100, base_score + diversity_bonus + data_bonus)
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
