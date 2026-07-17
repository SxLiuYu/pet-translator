"""
notifier/wechat.py
微信通知服务
支持: 企业微信机器人 / Server酱
"""
import logging
from typing import Dict

import requests

logger = logging.getLogger("pet_translator.notifier")

# 环境变量或配置文件注入
SERVERCHAN_KEY = "YOUR_SERVERCHAN_KEY"
WECHAT_WEBHOOK = "YOUR_WECOM_WEBHOOK_URL"


def send_pet_report(report: Dict) -> Dict:
    """发送每日宠物精神状态报告"""
    if WECHAT_WEBHOOK and "qyapi.weixin.qq.com" in WECHAT_WEBHOOK:
        return _send_wecom(report)
    if SERVERCHAN_KEY and SERVERCHAN_KEY != "YOUR_SERVERCHAN_KEY":
        return _send_serverchan(report)
    logger.warning("⚠️ 未配置微信推送服务，报告已生成但未发送")
    return {"status": "skipped", "reason": "未配置推送服务"}


def _send_wecom(report: Dict) -> Dict:
    """企业微信机器人 Webhook 推送 (Markdown 格式)"""
    health_emoji = {
        "😊 精神状态良好": "😊",
        "🙂 状态正常": "🙂",
        "😐 需要注意": "😐",
        "😟 建议关注": "😟",
    }.get(report.get("health_status", ""), "🐾")

    md_lines = [
        f"# 🐾 毛孩子翻译官 · 每日报告",
        f"**日期**: {report['date']}",
        f"**精神状态**: {report['health_status']} {health_emoji}",
        f"**健康评分**: {report['health_score']}/100",
        "",
        f"## 📊 今日概况",
        f"- 检测事件总数: **{report['total_events']}**",
        f"- 警报事件: **{report['alert_count']}**",
        f"- 检测到的动物: {', '.join(report.get('animals_detected', []))}",
        "",
        f"## 💡 陪玩建议",
    ]

    for s in report.get("suggestions", []):
        md_lines.append(f"- {s}")

    md_content = "\n".join(md_lines)

    payload = {
        "msgtype": "markdown",
        "markdown": {"content": md_content},
    }

    try:
        resp = requests.post(WECHAT_WEBHOOK, json=payload, timeout=10)
        result = resp.json()
        logger.info(f"✅ 企业微信推送成功: {result}")
        return {"status": "sent", "channel": "wecom", "result": result}
    except Exception as e:
        logger.error(f"❌ 企业微信推送失败: {e}")
        return {"status": "error", "error": str(e)}


def _send_serverchan(report: Dict) -> Dict:
    """Server酱 微信推送"""
    title = f"🐾 毛孩子今日状态: {report['health_status']}"
    content = "\n".join(report.get("suggestions", []))

    url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
    payload = {"title": title, "desp": content}

    try:
        resp = requests.post(url, data=payload, timeout=10)
        result = resp.json()
        logger.info(f"✅ Server酱推送成功: {result}")
        return {"status": "sent", "channel": "serverchan", "result": result}
    except Exception as e:
        logger.error(f"❌ Server酱推送失败: {e}")
        return {"status": "error", "error": str(e)}


def send_alert(animal: str, behavior: str, interpretation: str) -> Dict:
    """发送实时警报 (宠物有紧急需求)"""
    text = (
        f"🚨 **毛孩子翻译官警报**\n"
        f"检测到 {animal} 发出 **{behavior}**\n"
        f"📋 {interpretation}\n"
        f"请尽快查看摄像头确认情况！"
    )

    if WECHAT_WEBHOOK and "qyapi.weixin.qq.com" in WECHAT_WEBHOOK:
        payload = {
            "msgtype": "text",
            "text": {"content": f"🚨 毛孩子警报\n{animal} {behavior}\n{interpretation}"},
        }
        try:
            resp = requests.post(WECHAT_WEBHOOK, json=payload, timeout=10)
            return {"status": "sent", "channel": "wecom"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    logger.warning(f"⚠️ 警报未发送 (未配置): {text}")
    return {"status": "skipped"}
