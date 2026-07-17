
@app.put("/api/pets/{pet_id}", tags=["宠物"])
async def update_pet(pet_id: str, payload: dict):
    if not pet_repo:
        return JSONResponse({"error": "存储未初始化"}, status_code=500)
    updated = pet_repo.update(pet_id, payload)
    if not updated:
        return JSONResponse({"error": f"宠物 [{pet_id}] 不存�?}, status_code=404)
    return {"pet": updated.to_dict()}


@app.delete("/api/pets/{pet_id}", tags=["宠物"])
async def delete_pet(pet_id: str):
    if not pet_repo:
        return JSONResponse({"error": "存储未初始化"}, status_code=500)
    deleted = pet_repo.delete(pet_id)
    if not deleted:
        return JSONResponse({"error": f"宠物 [{pet_id}] 不存�?}, status_code=404)
    return {"status": "deleted", "pet_id": pet_id}


@app.get("/api/events", tags=["数据"])
async def get_events(pet_id: str | None = None, limit: int = 50):
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
        return JSONResponse({"error": "feedback 仅支�?useful/minor/false_positive"}, status_code=400)
    updated = event_repo.update_feedback(event_id, feedback)
    if not updated:
        return JSONResponse({"error": f"事件 [{event_id}] 不存�?}, status_code=404)
    return {"event_id": event_id, "feedback": feedback}


@app.get("/api/statistics", tags=["数据"])
async def get_statistics():
    """获取今日行为统计"""
    report = behavior_engine.generate_daily_report()
    return report["summary"]


# ========== 摄像头管理路�?==========

@app.post("/api/camera/register", tags=["摄像�?])
async def register_camera(req: CameraRegisterRequest):
    """
    注册并启动摄像头

    source_type: rtsp / usb / esp32cam
    url:
      rtsp  -> 完整 RTSP URL
      usb   -> 忽略 (�?device_index)
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
        return JSONResponse({"error": f"不支持的摄像头类�? {req.source_type}"}, status_code=400)

    cam.start()
    return {
        "status": "started",
        "name": req.name,
        "type": req.source_type,
        "area": req.area,
        "pet_ids": req.pet_ids or [],
    }
    except Exception as e:
        logger.error(f"�?摄像头注册失�? {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/camera/{name}", tags=["摄像�?])
async def unregister_camera(name: str):
    """停止并注销摄像�?""
    cam = camera_manager.get(name)
    if cam:
        cam.stop()
        camera_manager._cameras.pop(name, None)
        return {"status": "stopped", "name": name}
    return JSONResponse({"error": f"摄像�?[{name}] 不存�?}, status_code=404)


@app.get("/api/camera/status", tags=["摄像�?])
async def camera_status():
    """获取所有摄像头状�?""
    return {"cameras": camera_manager.status()}


@app.get("/api/camera/snapshot", tags=["摄像�?])
async def camera_snapshot(name: str, annotated: bool = True):
    """
    获取摄像头最新快�?(JPEG)
    ?name=cam1&annotated=true
    """
    frame = camera_manager.get_frame(name)
    if frame is None:
        return JSONResponse({"error": f"摄像�?[{name}] 无可用帧"}, status_code=404)

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
    对摄像头最新帧进行 YOLOv8 视觉行为检�?
    ?name=cam1
    """
    frame = camera_manager.get_frame(name)
    if frame is None:
        return JSONResponse({"error": f"摄像�?[{name}] 无可用帧"}, status_code=404)

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
    客户端接收到的消息格�? b"frame\x00<jpeg_bytes>"
    """
    await ws.accept()
    logger.info("📹 摄像�?WebSocket 客户端连�?)

    # 支持 ?cam=cam1 查询参数 (通过首条消息传�?
    cam_name = "default"
    try:
        first = await asyncio_ws_recv(ws, timeout=5)
        if first and first.startswith("cam:"):
            cam_name = first[4:].strip()
    except Exception:
        pass

    cam = camera_manager.get(cam_name)
    if cam is None:
        await ws.send_json({"error": f"摄像�?[{cam_name}] 未注册，请先 POST /api/camera/register"})
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
            await asyncio.sleep(1 / 15)  # ~15fps 推�?
    except WebSocketDisconnect:
        logger.info(f"📹 摄像�?WebSocket 断开 [{cam_name}]")
    except Exception as e:
        logger.error(f"📹 摄像�?WS 错误: {e}")


async def asyncio_ws_recv(ws: WebSocket, timeout: float = 5):
    """带超时的 WebSocket 接收"""
    import asyncio
    try:
        return await asyncio.wait_for(ws.receive_text(), timeout=timeout)
    except Exception:
        return None


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket 实时推送行为事�?(声纹结果)"""
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
    """加载音频文件，返�?(numpy_array, sample_rate)"""
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
