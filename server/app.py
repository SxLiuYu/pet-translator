"""
app.py
毛孩子翻译官 主服务 (FastAPI)
功能: 音频上传 -> YAMNet分类 -> 行为分析 -> WebSocket实时推送
       摄像头接入 -> YOLOv8 视觉检测 -> 行为融合
"""
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from audio_classifier.classifier import AudioClassifier
from behavior_analyzer.rules import BehaviorEvent, get_engine
from camera.camera_manager import get_camera_manager, BaseCamera, CameraFrame
from camera.behavior_detector import BehaviorDetector
from notifier.wechat import send_pet_report, send_alert
from storage.schema import Event, Pet
from storage.repository import EventRepository, PetRepository, ReportRepository
from auth.router import router as auth_router
from audio_visual_fusion import AudioVisualFusionEngine, get_fusion_engine

# ========== 日志 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("pet_translator")

# ========== 全局实例 ==========
classifier: AudioClassifier = None
behavior_engine = None
camera_manager = None
vision_detector: BehaviorDetector = None
pet_repo: Optional[PetRepository] = None
event_repo: Optional[EventRepository] = None
report_repo: Optional[ReportRepository] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global classifier, behavior_engine, camera_manager, vision_detector
    global pet_repo, event_repo, report_repo
    logger.info("🚀 毛孩子翻译官 启动中...")
    classifier = AudioClassifier()
    behavior_engine = get_engine()
    camera_manager = get_camera_manager()
    vision_detector = BehaviorDetector()
    pet_repo = PetRepository()
    event_repo = EventRepository()
    report_repo = ReportRepository()
    _bootstrap_pets(pet_repo)
    _ensure_evidence_dirs()
    logger.info("✅ 系统就绪，等待音频和视频输入...")
    yield
    if camera_manager:
        camera_manager.stop_all()
    logger.info("👋 服务关闭")


app = FastAPI(
    title="🐾 毛孩子翻译官 API",
    description="宠物行为分析 + 声纹识别 + 视觉检测 + 精神状态报告",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载认证路由
app.include_router(auth_router)



@app.post("/api/fusion/analyze")
async def fusion_analyze(request: FusionAnalyzeRequest):
    """融合分析端点 - 结合音频和视觉数据进行行为分析"""
    global fusion_results
    
    fusion_engine = get_fusion_engine()
    
    result = fusion_engine.analyze(
        audio_data=request.audio.model_dump(),
        visual_data=request.visual.model_dump()
    )
    
    response = FusionResponse(
        behavior=result.get("behavior", "unknown"),
        confidence=result.get("confidence", 0.0),
        sources=result.get("sources", ["audio", "visual"]),
        audio_behavior=request.audio.behavior,
        visual_behavior=request.visual.behavior,
        audio_confidence=request.audio.confidence,
        visual_confidence=request.visual.confidence,
        interpretation=result.get("interpretation", ""),
        suggestion=result.get("suggestion", ""),
        is_alert=result.get("is_alert", False),
        timestamp=datetime.now().isoformat()
    )
    
    fusion_results.append(response)
    
    return response


@app.get("/api/fusion/results")
async def fusion_results_endpoint():
    """获取所有融合分析结果"""
    return fusion_results





# ========== 数据模型 ==========
class BehaviorResult(BaseModel):
    animal: Optional[str]
    behavior: str
    confidence: float
    is_pet_sound: bool
    is_alert: bool
    interpretation: str
    suggestion: str
    severity: str
    period: str
    timestamp: str
    event_id: Optional[str] = None
    evidence: Optional[dict] = None


class DailyReport(BaseModel):
    date: str
    health_score: int
    health_status: str
    total_events: int
    alert_count: int
    suggestions: list[str]
    hourly_chart: dict
    pet_id: Optional[str] = None
    pet_name: Optional[str] = None
    top_alerts: Optional[list] = None


class StatusResponse(BaseModel):
    status: str
    model_loaded: bool
    events_today: int
    cameras: dict


class CameraRegisterRequest(BaseModel):
    name: str
    source_type: str   # "rtsp" | "usb" | "esp32cam"
    url: str           # RTSP URL 或 IP 地址
    device_index: int = 0  # USB 设备索引
    area: str = ""
    pet_ids: Optional[list[str]] = None


class VisualBehaviorResponse(BaseModel):
    behavior: str
    confidence: float
    activity_level: str
    is_destructive: bool
    description: str
    detections: list
    timestamp: str
    pet_id: Optional[str] = None


class AudioInput(BaseModel):
    animal: str
    behavior: str
    confidence: float
    is_pet_sound: bool
    is_alert: bool
    suggestion: str


class VisualInput(BaseModel):
    behavior: str
    confidence: float
    activity_level: str
    is_destructive: bool
    description: str
    detections: list


class FusionAnalyzeRequest(BaseModel):
    pet_id: Optional[str] = None
    audio: AudioInput
    visual: VisualInput


class FusionResponse(BaseModel):
    behavior: str
    confidence: float
    sources: list[str]
    audio_behavior: str
    visual_behavior: str
    audio_confidence: float
    visual_confidence: float
    interpretation: str
    suggestion: str
    is_alert: bool
    timestamp: str


# ========== WebSocket 连接管理 ==========
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
        logger.info(f"📱 客户端连接，当前 {len(self.active_connections)} 个在线")

    def disconnect(self, ws: WebSocket):
        self.active_connections.remove(ws)

    async def broadcast(self, message: dict):
        for conn in list(self.active_connections):
            try:
                await conn.send_json(message)
            except Exception:
                pass

    async def broadcast_bytes(self, message_type: str, data: bytes):
        """广播二进制帧 (JPEG 图像)"""
        for conn in list(self.active_connections):
            try:
                await conn.send_bytes(message_type.encode() + b"\x00" + data)
            except Exception:
                pass


manager = ConnectionManager()
fusion_engine = None
fusion_results = []


# ========== 音频分析路由 ==========

@app.get("/", tags=["基础"])
async def root():
    return {
        "message": "🐾 毛孩子翻译官 API 运行中",
        "docs": "/docs",
        "websocket": "/ws",
        "camera_stream": "/ws/camera",
        "pets": "/api/pets",
    }


@app.get("/health", response_model=StatusResponse, tags=["基础"])
async def health():
    return {
        "status": "ok",
        "model_loaded": classifier is not None,
        "pets": [pet.to_dict() for pet in (pet_repo.get_all() if pet_repo else [])],
        "events_today": len(behavior_engine.daily_events),
        "cameras": camera_manager.status() if camera_manager else {},
    }


@app.post("/api/upload_audio", response_model=BehaviorResult, tags=["分析"])
async def upload_audio(file: UploadFile = File(...)):
    """上传音频文件进行声纹 + 行为分析"""
    tmp_path = None
    try:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            return JSONResponse({"error": "文件过大，最大10MB"}, status_code=413)

        suffix = Path(file.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        audio_array, sr = _load_audio(tmp_path)
        logger.info(f"📥 收到音频: {file.filename}, {len(audio_array)} samples @ {sr}Hz")

        pet_id = _read_pet_id_from_request()
        classification = classifier.classify(audio_array, sr)
        logger.info(f"🔍 声纹分类: {classification}")

        if not classification["is_pet_sound"]:
            result = BehaviorResult(
                **{**classification,
                   "interpretation": "未检测到宠物声音，可能是环境噪音",
                   "suggestion": "无需处理",
                   "severity": "info",
                   "period": _get_period(),
                   "timestamp": datetime.now().isoformat()},
            )
            await _broadcast_behavior_result(result)
            return result

        event = BehaviorEvent(
            timestamp=datetime.now().isoformat(),
            animal=classification["animal"],
            behavior=classification["behavior"],
            confidence=classification["confidence"],
            is_alert=classification["is_alert"],
            context={"pet_id": pet_id, "source": "upload_audio", "filename": file.filename},
        )
        analysis = behavior_engine.analyze(event)

        evidence = {}
        if tmp_path and os.path.exists(tmp_path):
            try:
                suffix = Path(file.filename).suffix or ".wav"
                evidence_path = _save_evidence(tmp_path, f"audio/evt_{datetime.now().timestamp():.0f}{suffix}")
                if evidence_path:
                    evidence["audio"] = evidence_path
            except Exception as evidence_error:
                logger.warning(f"⚠️ 音频证据保存失败: {evidence_error}")

        persisted_event = _store_event(
            pet_id=pet_id,
            classification=classification,
            analysis=analysis,
            evidence=evidence,
            source="upload_audio",
        )
        result = BehaviorResult(
            **{**classification, **analysis},
            event_id=persisted_event.get("id"),
            evidence=persisted_event.get("evidence_paths", evidence),
        )

        await manager.broadcast({
            "type": "behavior_alert" if result.is_alert else "behavior_update",
            "data": result.dict(),
        })

        if result.is_alert:
            send_alert(result.animal, result.behavior, result.interpretation)

        return result

    except Exception as e:
        logger.error(f"❌ 音频处理失败: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.get("/api/report/daily", response_model=DailyReport, tags=["报告"])
async def daily_report():
    """获取今日精神状态报告"""
    report = behavior_engine.generate_daily_report()
    return DailyReport(
        date=report["date"],
        health_score=report["health_score"],
        health_status=report["health_status"],
        total_events=report["summary"]["total_events"],
        alert_count=report["summary"]["alert_count"],
        suggestions=report["suggestions"],
        hourly_chart=report["hourly_chart"],
        pet_id=report.get("pet_id"),
        pet_name=report.get("pet_name"),
        top_alerts=report.get("top_alerts") or [],
    )


@app.post("/api/report/generate", tags=["报告"])
async def generate_and_send_report():
    """生成报告并通过微信推送"""
    report = behavior_engine.generate_daily_report()
    result = send_pet_report(report)
    return {"status": "sent", "result": result}


@app.get("/api/pets", tags=["宠物"])
async def list_pets():
    if not pet_repo:
        return JSONResponse({"error": "存储未初始化"}, status_code=500)
    pets = [pet.to_dict() for pet in pet_repo.get_all()]
    return {"pets": pets, "total": len(pets)}


@app.post("/api/pets", tags=["宠物"])
async def create_pet(payload: dict):
    if not pet_repo:
        return JSONResponse({"error": "存储未初始化"}, status_code=500)
    pet_id = _safe_str(payload.get("pet_id") or payload.get("id"))
    if not pet_id:
        return JSONResponse({"error": "pet_id 必填"}, status_code=400)
    if pet_repo.get_by_id(pet_id):
        return JSONResponse({"error": f"宠物 [{pet_id}] 已存在"}, status_code=409)
    pet = Pet(
        id=pet_id,
        name=_safe_str(payload.get("name"), pet_id),
        species=_safe_str(payload.get("species")),
    )
    saved = pet_repo.create(pet)
    return {"pet": saved.to_dict()}


@app.get("/api/pets/{pet_id}", tags=["宠物"])
async def get_pet(pet_id: str):
    if not pet_repo:
        return JSONResponse({"error": "存储未初始化"}, status_code=500)
    pet = pet_repo.get_by_id(pet_id)
    if not pet:
        return JSONResponse({"error": f"宠物 [{pet_id}] 不存在"}, status_code=404)
    return {"pet": pet.to_dict()}


@app.put("/api/pets/{pet_id}", tags=["宠物"])
async def update_pet(pet_id: str, payload: dict):
    if not pet_repo:
        return JSONResponse({"error": "存储未初始化"}, status_code=500)
    updated = pet_repo.update(pet_id, payload)
    if not updated:
        return JSONResponse({"error": f"宠物 [{pet_id}] 不存在"}, status_code=404)
    return {"pet": updated.to_dict()}


@app.delete("/api/pets/{pet_id}", tags=["宠物"])
async def delete_pet(pet_id: str):
    if not pet_repo:
        return JSONResponse({"error": "存储未初始化"}, status_code=500)
    deleted = pet_repo.delete(pet_id)
    if not deleted:
        return JSONResponse({"error": f"宠物 [{pet_id}] 不存在"}, status_code=404)
    return {"status": "deleted", "pet_id": pet_id}


@app.get("/api/events", tags=["数据"])
async def get_events(pet_id: Optional[str] = None, limit: int = 50):
    """获取最近的行为事件"""
    if not event_repo:
        return JSONResponse({"error": "存储未初始化"}, status_code=500)
    target_pet_id = pet_id or _read_pet_id_from_request()
    if target_pet_id:
        events = event_repo.recent_by_pet(target_pet_id, limit=limit)
    else:
        events = event_repo.get_recent(limit=limit)
    return {
        "events": [e.to_dict() for e in events],
        "total": len(events),
        "pet_id": target_pet_id,
    }


@app.post("/api/event/{event_id}/feedback", tags=["数据"])
async def submit_event_feedback(event_id: str, payload: dict):
    if not event_repo:
        return JSONResponse({"error": "存储未初始化"}, status_code=500)
    feedback = _safe_str(payload.get("feedback"))
    if feedback not in {"useful", "minor", "false_positive"}:
        return JSONResponse({"error": "feedback 仅支持 useful/minor/false_positive"}, status_code=400)
    updated = event_repo.update_feedback(event_id, feedback)
    if not updated:
        return JSONResponse({"error": f"事件 [{event_id}] 不存在"}, status_code=404)
    return {"event_id": event_id, "feedback": feedback}


@app.get("/api/statistics", tags=["数据"])
async def get_statistics():
    """获取今日行为统计"""
    report = behavior_engine.generate_daily_report()
    return report["summary"]


# ========== 摄像头管理路由 ==========

@app.post("/api/camera/register", tags=["摄像头"])
async def register_camera(req: CameraRegisterRequest):
    """
    注册并启动摄像头

    source_type: rtsp / usb / esp32cam
    url:
      rtsp  -> 完整 RTSP URL
      usb   -> 忽略 (用 device_index)
      esp32cam -> IP 地址，如 192.168.1.100
    """
    try:
        if req.source_type == "rtsp":
            cam = camera_manager.register_rtsp(req.name, req.url)
        elif req.source_type == "usb":
            cam = camera_manager.register_usb(req.name, req.device_index)
        elif req.source_type == "esp32cam":
            cam = camera_manager.register_esp32cam(req.name, req.url)
        else:
            return JSONResponse({"error": f"不支持的摄像头类型: {req.source_type}"}, status_code=400)

        cam.start()
        return {
            "status": "started",
            "name": req.name,
            "type": req.source_type,
            "area": req.area,
            "pet_ids": req.pet_ids or [],
        }
    except Exception as e:
        logger.error(f"❌ 摄像头注册失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/camera/{name}", tags=["摄像头"])
async def unregister_camera(name: str):
    """停止并注销摄像头"""
    cam = camera_manager.get(name)
    if cam:
        cam.stop()
        camera_manager._cameras.pop(name, None)
        return {"status": "stopped", "name": name}
    return JSONResponse({"error": f"摄像头 [{name}] 不存在"}, status_code=404)


@app.get("/api/camera/status", tags=["摄像头"])
async def camera_status():
    """获取所有摄像头状态"""
    return {"cameras": camera_manager.status()}


@app.get("/api/camera/snapshot", tags=["摄像头"])
async def camera_snapshot(name: str, annotated: bool = True):
    """
    获取摄像头最新快照 (JPEG)
    ?name=cam1&annotated=true
    """
    frame = camera_manager.get_frame(name)
    if frame is None:
        return JSONResponse({"error": f"摄像头 [{name}] 无可用帧"}, status_code=404)

    if annotated and vision_detector.model is not None:
        result = vision_detector.detect(frame.image)
        if result.annotated_image:
            return StreamingResponse(
                iter([result.annotated_image]),
                media_type="image/jpeg",
                headers={"Cache-Control": "no-cache"},
            )

    return StreamingResponse(
        iter([frame.jpeg_bytes]),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/api/camera/detect", tags=["视觉"])
async def camera_detect(name: str):
    """
    对摄像头最新帧进行 YOLOv8 视觉行为检测
    ?name=cam1
    """
    frame = camera_manager.get_frame(name)
    if frame is None:
        return JSONResponse({"error": f"摄像头 [{name}] 无可用帧"}, status_code=404)

    result = vision_detector.detect(frame.image)
    return VisualBehaviorResponse(
        behavior=result.behavior,
        confidence=result.confidence,
        activity_level=result.activity_level,
        is_destructive=result.is_destructive,
        description=result.description,
        detections=[
            {
                "class": d.class_name,
                "confidence": round(d.confidence, 3),
                "bbox": d.bbox,
            }
            for d in result.detections
        ],
        timestamp=datetime.fromtimestamp(result.timestamp).isoformat(),
    )


@app.websocket("/ws/camera")
async def camera_websocket(ws: WebSocket):
    """
    WebSocket 实时推送摄像头画面 (MJPEG over WS)
    客户端接收到的消息格式: b"frame\x00<jpeg_bytes>"
    """
    await ws.accept()
    logger.info("📹 摄像头 WebSocket 客户端连接")

    # 支持 ?cam=cam1 查询参数 (通过首条消息传递)
    cam_name = "default"
    try:
        first = await asyncio_ws_recv(ws, timeout=5)
        if first and first.startswith("cam:"):
            cam_name = first[4:].strip()
    except Exception:
        pass

    cam = camera_manager.get(cam_name)
    if cam is None:
        await ws.send_json({"error": f"摄像头 [{cam_name}] 未注册，请先 POST /api/camera/register"})
        await ws.close()
        return

    try:
        while True:
            frame = cam.get_latest_frame()
            if frame:
                jpeg = frame.jpeg_bytes
                if jpeg:
                    await ws.send_bytes(b"frame\x00" + jpeg)
            import asyncio
            await asyncio.sleep(1 / 15)  # ~15fps 推送
    except WebSocketDisconnect:
        logger.info(f"📹 摄像头 WebSocket 断开 [{cam_name}]")
    except Exception as e:
        logger.error(f"📹 摄像头 WS 错误: {e}")


async def asyncio_ws_recv(ws: WebSocket, timeout: float = 5):
    """带超时的 WebSocket 接收"""
    import asyncio
    try:
        return await asyncio.wait_for(ws.receive_text(), timeout=timeout)
    except Exception:
        return None


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket 实时推送行为事件 (声纹结果)"""
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(ws)
        logger.info("📱 客户端断开")


# ========== 辅助函数 ==========

def _load_audio(path: str):
    """加载音频文件，返回 (numpy_array, sample_rate)"""
    import wave

    try:
        with wave.open(path, "rb") as wf:
            sr = wf.getframerate()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            return audio, sr
    except wave.Error:
        pass

    try:
        import librosa
        audio, sr = librosa.load(path, sr=16000, mono=True)
        return audio.astype(np.float32), sr
    except ImportError:
        raise RuntimeError("无法解码音频，请安装 librosa: pip install librosa")


def _get_period() -> str:
    from behavior_analyzer.rules import BehaviorRulesEngine
    engine = BehaviorRulesEngine()
    return engine._get_time_period(datetime.now().hour)


def _safe_str(value: Optional[str], default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _read_pet_id_from_request() -> Optional[str]:
    return None


def _bootstrap_pets(pet_repo: PetRepository) -> None:
    if not pet_repo or not pet_repo.get_all():
        pet_repo.create(Pet(id="pet_001", name="旺财", species="狗"))
        pet_repo.create(Pet(id="pet_002", name="咪咪", species="猫"))


def _ensure_evidence_dirs() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    Path(base_dir, "evidence", "audio").mkdir(parents=True, exist_ok=True)
    Path(base_dir, "evidence", "img").mkdir(parents=True, exist_ok=True)


def _save_evidence(src_path: str, relative_path: str) -> Optional[str]:
    base_dir = Path(__file__).resolve().parent.parent
    target_path = base_dir / "evidence" / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    Path(src_path).replace(target_path)
    return str(target_path)


def _save_bytes_as_evidence(data: bytes, relative_path: str) -> Optional[str]:
    base_dir = Path(__file__).resolve().parent.parent
    target_path = base_dir / "evidence" / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(data)
    return str(target_path)


def _broadcast_behavior_result(result: BehaviorResult) -> None:
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast({
                "type": "behavior_alert" if result.is_alert else "behavior_update",
                "data": result.model_dump(),
            }))
    except Exception as broadcast_error:
        logger.warning(f"⚠️ 广播失败: {broadcast_error}")


def _store_event(
    pet_id: Optional[str],
    classification: dict,
    analysis: dict,
    evidence: dict,
    source: str,
) -> dict:
    if not event_repo:
        return {}
    event = Event(
        id=f"evt_{datetime.now().timestamp():.0f}",
        pet_id=pet_id or "default",
        timestamp=datetime.now().isoformat(),
        source_type="audio",
        source_ref=source,
        animal=classification.get("animal", ""),
        behavior=classification.get("behavior", ""),
        confidence=float(classification.get("confidence") or 0.0),
        is_alert=bool(classification.get("is_alert")),
        severity=analysis.get("severity", "info"),
        period=analysis.get("period", ""),
        interpretation=analysis.get("interpretation", ""),
        suggestion=analysis.get("suggestion", ""),
        evidence_paths=evidence,
    )
    stored = event_repo.add(event)
    return stored.to_dict()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
