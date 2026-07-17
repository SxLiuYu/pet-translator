"""notifier/wechat.py
微信通知服务
支持: 企业微信机器人 / Server酱
"""
import logging
import os
from typing import Dict

import requests

logger = logging.getLogger("pet_translator.notifier")


def _get_wechat_webhook() -> str:
    return os.environ.get("WECHAT_WEBHOOK", "")


def _get_serverchan_key() -> str:
    return os.environ.get("SERVERCHAN_KEY", "")


def send_pet_report(report: Dict) -> Dict:
    """发送每日宠物精神状态报告"""
    webhook = _get_wechat_webhook()
    sckey = _get_serverchan_key()
    if webhook and "qyapi.weixin.qq.com" in webhook:
        return _send_wecom(report, webhook)
    if sckey:
        return _send_serverchan(report, sckey)
    logger.warning("⚠️ 未配置微信推送服务 (设置 WECHAT_WEBHOOK 或 SERVERCHAN_KEY 环境变量)")
    return {"status": "skipped", "reason": "未配置推送服务"}


def _send_wecom(report: Dict, webhook: str) -> Dict:
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

    payload = {"msgtype": "markdown", "markdown": {"content": md_content}}
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        result = resp.json()
        logger.info(f"✅ 企业微信推送成功: {result}")
        return {"status": "sent", "channel": "wecom", "result": result}
    except Exception as e:
        logger.error(f"❌ 企业微信推送失败: {e}")
        return {"status": "error", "error": str(e)}


def _send_serverchan(report: Dict, sckey: str) -> Dict:
    """Server酱 微信推送"""
    title = f"🐾 毛孩子今日状态: {report['health_status']}"
    content = "\n".join(report.get("suggestions", []))
    url = f"https://sctapi.ftqq.com/{sckey}.send"
    try:
        resp = requests.post(url, data={"title": title, "desp": content}, timeout=10)
        result = resp.json()
        logger.info(f"✅ Server酱推送成功: {result}")
        return {"status": "sent", "channel": "serverchan", "result": result}
    except Exception as e:
        logger.error(f"❌ Server酱推送失败: {e}")
        return {"status": "error", "error": str(e)}


def send_alert(animal: str, behavior: str, interpretation: str) -> Dict:
    """发送实时警报 (宠物有紧急需求)"""
    webhook = _get_wechat_webhook()
    if webhook and "qyapi.weixin.qq.com" in webhook:
        payload = {
            "msgtype": "text",
            "text": {"content": f"🚨 毛孩子警报\n{animal} {behavior}\n{interpretation}"},
        }
        try:
            resp = requests.post(webhook, json=payload, timeout=10)
            return {"status": "sent", "channel": "wecom"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    logger.warning(f"⚠️ 警报未发送 (未配置 WECHAT_WEBHOOK)")
    return {"status": "skipped"}
