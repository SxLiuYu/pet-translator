            try:
                await conn.send_bytes(message_type.encode() + b"\x00" + data)
            except Exception:
                pass


manager = ConnectionManager()


# ========== 音频分析路由 ==========

@app.get("/", tags=["基础"])
async def root():
    return {
        "message": "🐾 毛孩子翻译官 API 运行�?,
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
            return JSONResponse({"error": "文件过大，最�?0MB"}, status_code=413)

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
            "data": result.model_dump(),
        })

        if result.is_alert:
            send_alert(result.animal, result.behavior, result.interpretation)

        return result

    except Exception as e:
        logger.error(f"�?音频处理失败: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.get("/api/report/daily", response_model=DailyReport, tags=["报告"])
async def daily_report():
    """获取今日精神状态报�?""
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
    """生成报告并通过微信推�?""
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
        return JSONResponse({"error": f"宠物 [{pet_id}] 已存�?}, status_code=409)
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
        return JSONResponse({"error": f"宠物 [{pet_id}] 不存�?}, status_code=404)
    return {"pet": pet.to_dict()}

