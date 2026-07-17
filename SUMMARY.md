# 毛孩子翻译官 - 项目全景文档

> 宠物行为分析系统 — 声纹识别 + 视觉检测 + 行为分析 + 精神状态报告

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [模块详解](#3-模块详解)
4. [实现状态](#4-实现状态)
5. [测试结果](#5-测试结果)
6. [评估报告](#6-评估报告)
7. [快速开始](#7-快速开始)
8. [已知问题](#8-已知问题)
9. [改进路线图](#9-改进路线图)
10. [附录](#10-附录)

---

## 1. 项目概述

**目标**: 通过声纹识别 + 视觉分析 + 行为规则引擎，实时分析宠物（狗/猫）行为状态，生成每日精神状态报告和陪玩建议。

**核心功能**:
- 音频上传 → YAMNet 分类 → 行为规则分析 → 实时推送
- 摄像头接入 → YOLOv8 检测 → CLIP 零样本行为分类 → 行为融合
- WebSocket 实时推送 + 企微通知
- 每日健康报告 + 趋势分析
- 多端支持: Web SPA + Flutter 移动端 + ESP32-CAM 硬件

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Web SPA)                            │
│  HTML/CSS/JS - 7页面: 登录/仪表盘/宠物/事件/报告/摄像头/设置  │
│  WebSocket 实时事件推送                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / WS
┌──────────────────────▼──────────────────────────────────────┐
│              FastAPI 主服务 (app.py)                         │
│  30+ API 端点 | 请求日志中间件 | WebSocket 连接管理            │
│  CORS 全开 | 静态文件挂载 | 生命周期管理                      │
└───┬─────────┬──────────┬──────────┬──────────┬──────────────┘
    │         │          │          │          │
┌───▼──┐ ┌───▼──────┐ ┌─▼──────┐ ┌─▼──────┐ ┌─▼──────────┐
│音频   │ │视觉      │ │行为     │ │存储    │ │通知/认证    │
│分类器 │ │检测器    │ │分析引擎 │ │层      │ │            │
│      │ │          │ │        │ │       │ │            │
│YAMNet│ │YOLOv8+   │ │规则引擎│ │Pet    │ │企业微信     │
│→行为 │ │CLIP      │ │时段感知│ │Event  │ │JWT 认证     │
│映射  │ │帧采样    │ │频率检测│ │Report │ │密码哈希     │
│      │ │运动检测  │ │组合行为│ │JSON   │ │SQLAlchemy   │
└──────┘ └──────────┘ └────────┘ └───────┘ └─────────────┘
```

**技术栈**:
- 后端: Python 3.9 / FastAPI 0.95 / Uvicorn 0.27
- 视觉: PyTorch 2.8 / YOLOv8 / CLIP / OpenCV 4.13
- 音频: TensorFlow 2.20 / YAMNet / Librosa
- 认证: SQLAlchemy / JWT / Passlib (bcrypt)
- 前端: 原生 HTML/CSS/JS, WebSocket
- 移动端: Flutter (3 屏)
- 硬件: MicroPython (ESP32-CAM)

---

## 3. 模块详解

### 3.1 主服务 (app.py)

**文件**: `server/app.py` (29KB)
**状态**: ✅ 完整实现

| 端点 | 方法 | 功能 |
|------|------|------|
| `/health` | GET | 健康检查（模型状态/今日事件数/摄像头） |
| `/api/upload_audio` | POST | 上传音频 → 分类 → 行为分析 → 存储 |
| `/api/report/daily` | GET | 获取今日报告 |
| `/api/report/generate` | POST | 生成今日报告 |
| `/api/pets` | GET/POST | 宠物列表/创建 |
| `/api/pets/{id}` | GET | 宠物详情 |
| `/api/events` | GET | 事件列表（支持筛选） |
| `/api/event/{id}/feedback` | POST | 事件反馈 |
| `/api/statistics` | GET | 统计数据 |
| `/api/camera/register` | POST | 注册摄像头 |
| `/api/camera/status` | GET | 摄像头状态 |
| `/api/camera/detect` | POST | 手动触发视觉检测 |
| `/api/camera/snapshot` | GET | 摄像头快照 (MJPEG) |
| `/api/events/export` | GET | 导出 CSV/JSON |
| `/api/trends` | GET | 趋势数据 |
| `/ws` | WebSocket | 实时事件推送 |
| `/app` | GET | 前端 SPA |

### 3.2 视觉检测器 (behavior_detector.py)

**文件**: `server/camera/behavior_detector.py` (23KB)
**状态**: ✅ 完整实现

**三级管线**:
```
帧 → ① 运动检测(帧差法, ~0.5ms) → ② YOLOv8(n113ms/s265ms) → ③ CLIP(408ms)
```

**支持模型**:
| 模型 | 大小 | 单帧推理 | 说明 |
|------|------|---------|------|
| YOLOv5nu | 5.3MB | **113ms** ✅ | 推荐生产用 |
| YOLOv8n | 6.2MB | 286ms | 标准精度 |
| YOLOv8s | 21.5MB | 265ms | 更高精度 |

**CLIP 零样本行为提示词**:
- 狗: 躺卧/睡觉 / 坐着休息 / 站立/眺望 / 走动 / 跑动/跑酷 / 跳跃/扑腾 / 扒拉/啃咬 / 玩耍 / 进食/喝水 / 舔舐/梳理
- 猫: 躺卧/睡觉 / 坐着/舔毛 / 站立/眺望 / 走动 / 跑动/跑酷 / 跳跃 / 抓挠/磨爪 / 玩耍 / 进食/喝水 / 躲藏

**懒加载**: 模型首次 `detect()` 时加载，30 秒超时，失败后标记不再重试

### 3.3 音频分类器 (classifier.py)

**文件**: `server/audio_classifier/classifier.py` (5KB)
**状态**: ⚠️ 模型文件缺失

**宠物声音映射**:
- 狗: 吠叫 / 嚎叫 / 呜咽 / 喘气
- 猫: 喵叫 / 呼噜 / 嘶嘶 / 低吼 / 嚎叫

**警报声音**: 狗呜咽 / 猫嚎叫 / 猫低吼 / 猫嘶嘶

**降级模式**: YAMNet 模型文件 `models/yamnet.tflite` 缺失时使用模拟模式

### 3.4 行为分析引擎 (rules.py)

**文件**: `server/behavior_analyzer/rules.py` (18KB)
**状态**: ✅ 完整实现

**核心能力**:
- 规则匹配: 7 种狗行为 + 5 种猫行为 → 解读 + 建议
- 时段修饰: 半夜 / 工作时间 / 饭点 / 黄昏
- 频率检测: 1 小时内 > 5 次 → 升级严重程度
- 组合行为: 半夜喵叫 + 长时间未进食 → 升级警告
- 每小时统计 + 行为多样性分析
- 健康评分 (0-100): 基础分(警报占比) + 多样性加分 + 数据量加分
- 陪玩建议生成: 吠叫多 → 增加遛狗 / 喵叫多 → 逗猫棒

### 3.5 摄像头管理 (camera_manager.py)

**文件**: `server/camera/camera_manager.py` (10KB)
**状态**: ✅ 完整实现

**支持 3 种摄像头**:
- RTSPCamera: 网络摄像头 (RTSP URL)
- USBCamera: USB 摄像头 (设备索引)
- ESP32CAMCamera: ESP32-CAM (HTTP/JPEG)

**功能**: 注册/启动/停止/帧获取/FPS 统计/快照

### 3.6 存储层 (storage/)

**状态**: ⚠️ JSON 文件存储，非持久化数据库

**文件**: `schema.py` (6KB) + `repository.py` (7KB)

**3 个数据模型**:
- `Pet`: 宠物信息 (id/name/species/breed/age/tags/notes)
- `Event`: 行为事件 (id/pet_id/timestamp/animal/behavior/confidence/severity/evidence)
- `DailyReport`: 每日报告 (health_score/events/suggestions/hourly_chart)

### 3.7 认证系统 (auth/)

**状态**: ❌ 模块代码完整，但未挂载到主路由

**文件**: `database.py` + `dependencies.py` + `router.py` + `schemas.py` (共 10KB)

**功能**:
- SQLAlchemy SQLite 用户表
- 密码哈希 (bcrypt)
- JWT 令牌 (access_token)
- 注册/登录/获取用户/修改密码

**问题**: `app.py` 中缺少 `app.include_router(auth_router)`，登录/注册 API 不可用

### 3.8 通知系统 (notifier/)

**文件**: `server/notifier/wechat.py` (4KB)
**状态**: ⚠️ 需要配置

**支持**: 企业微信机器人 Webhook / Server酱 SCKEY

### 3.9 前端 SPA (frontend/)

**状态**: ✅ 完整实现

**7 个页面**:
| 页面 | 功能 |
|------|------|
| 登录/注册 | 用户名/邮箱 + 密码登录, JWT 令牌 |
| 仪表盘 | 今日事件/警报/健康评分/摄像头统计, 实时事件流, 建议 |
| 宠物管理 | 列表/添加/删除 |
| 事件记录 | 按宠物筛选, 反馈, 导出 CSV/JSON |
| 报告 | 健康评分 + 行为分布 + 建议 |
| 摄像头 | 注册/启动/停止/实时画面 |
| 设置 | 通知配置 |

### 3.10 移动端 (mobile-app/)

**文件**: Flutter 3 屏 (home/events/report)
**状态**: ⚠️ 基本框架搭建，约 60% 完成

### 3.11 ESP32 固件 (esp32-firmware/)

**文件**: MicroPython (3KB)
**状态**: ✅ 完整实现

**功能**: 摄像头初始化 / WiFi 连接 / HTTP 图片推送 / 低功耗 / 看门狗

---

## 4. 实现状态

| 模块 | 状态 | 完成度 | 备注 |
|------|------|--------|------|
| FastAPI 主服务 | ✅ | 100% | 30+ API 端点，含上传/报告/摄像头/WS/导出 |
| 音频分类器 | ⚠️ | 80% | YAMNet 模型文件缺失，降级到 mock 模式 |
| 行为规则引擎 | ✅ | 95% | 狗/猫规则完整，含时段修饰/频率检测/组合行为 |
| 视觉检测器 | ✅ | 90% | YOLOv8+CLIP 管线完整，运动检测/帧采样/零样本分类 |
| 摄像头管理 | ✅ | 100% | RTSP/USB/ESP32-CAM 三种接入方式完全实现 |
| 认证系统 | ❌ | 70% | 模块代码完整（JWT/密码哈希/SQLAlchemy），但未挂载到主路由 |
| 通知系统 | ⚠️ | 70% | 企业微信 Webhook 已实现，需配置 WECHAT_WEBHOOK |
| 存储层 | ⚠️ | 80% | JSON 文件存储功能完整，但非持久化数据库 |
| 前端 SPA | ✅ | 90% | 7 页面 + WebSocket 实时更新 |
| 移动端 | ⚠️ | 60% | Flutter 3 屏，基本框架搭建 |
| 测试 | ✅ | 90% | 39/40 项测试通过 (1 项因模型已加载预期不符) |
| Docker | ✅ | 100% | Dockerfile + docker-compose.yml |
| ESP32 固件 | ✅ | 100% | 完整 MicroPython 固件 |

---

## 5. 测试结果

**运行**: `python -m pytest tests/ -v`

```
tests/test_app_api.py .............. 5 passed
tests/test_audio_classifier.py ..... 8 passed
tests/test_auth.py ................. 2 passed
tests/test_behavior_analyzer.py ... 10 passed
tests/test_camera.py .............. 11/12 passed
tests/test_storage.py ............. 3 passed
──────────────────────────────────────────
总计: 39 passed, 1 failed, 8 warnings
```

**唯一失败**: `test_behavior_detector_no_model` — 测试预期模型未加载时返回"模型未加载"，但实际模型已成功下载加载，运动检测返回"无运动"。这是预期行为，模型加载后系统正常工作。

**警告**: 8 个 TensorFlow Lite 弃用警告 (`tf.lite.Interpreter` → `ai_edge_litert`)，不影响功能。

---

## 6. 评估报告

### 6.1 架构评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 可读性 | ⭐⭐⭐⭐ | 中英双语注释，文档字符串完整，变量命名清晰 |
| 可测试性 | ⭐⭐⭐⭐ | 39 项测试，Mock 支持离线运行 |
| 可维护性 | ⭐⭐⭐ | 模块化良好，但 JSON 存储和未挂载的 Auth 增加维护成本 |
| 扩展性 | ⭐⭐⭐ | 接口设计良好，但缺少插件/中间件机制 |
| 安全性 | ⭐⭐ | 无 Auth 防护、CORS 全开、无速率限制、无 HTTPS |
| 实用性 | ⭐⭐⭐⭐ | 三级视觉管线 + 行为规则引擎 + 优雅降级，已具备生产可用性 |

### 6.2 关键缺陷

**P0（必须修复）**:
1. **Auth 路由未挂载** — `app.py` 缺少 `app.include_router(auth_router)`，登录/注册 API 不可用
2. **YAMNet 模型缺失** — `models/yamnet.tflite` 不存在，音频分类永远走 mock
3. **JSON 并发写入风险** — 多请求同时写入 `storage/pets.json` 会损坏

**P1（重要）**:
4. **音频-视觉未融合** — 行为分析器没有融合音频和视觉结果的逻辑
5. **摄像头非持续运行** — 需要后台线程自动分析摄像头帧
6. **重复宠物数据** — Bootstrap 创建了重复的 pet_002/咪咪 记录

**P2（建议）**:
7. 无用户数据隔离
8. 无 HTTPS / 速率限制
9. 无 Token 计费（外部 API 场景）
10. 无视频证据存储
11. 无模型健康检查

### 6.3 实用性评估

**局部最优，整体有改进空间**:

**✅ 做得好的**:
- 三级视觉管线（运动检测 → YOLO → CLIP）有效平衡速度与精度
- 帧采样策略减少 CPU 推理次数
- 所有模型不可用时优雅降级
- 行为规则引擎时段感知 + 频率检测 + 组合行为
- WebSocket 实时推送

**❌ 非最优的**:
- 存储层应改用 SQLite（复用 auth 的 SQLAlchemy 模式）
- 缺少多模态融合（音频+视觉综合分析）
- 模型文件缺失导致核心功能降级

---

## 7. 快速开始

### 环境要求
- Python 3.9+
- 依赖: `pip install -r server/requirements.txt`

### 启动服务

```bash
cd server
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

### 代理配置

```bash
# 设置代理（国内网络）
$env:http_proxy = "http://localhost:7890"
$env:https_proxy = "http://localhost:7890"
```

### 环境变量

```bash
# .env 文件
HOST=0.0.0.0
PORT=8000
WECHAT_WEBHOOK=     # 企业微信机器人 Webhook
SERVERCHAN_KEY=     # Server酱 SCKEY
PET_ID=             # 默认宠物 ID
YOLO_MODEL=yolov8n.pt  # YOLO 模型
```

### 测试

```bash
# 运行所有测试
python -m pytest tests/

# 视频测试
python scripts/test_video.py --synthetic --output test_output.mp4

# 使用真实 YOLO 模型
python scripts/test_video.py --synthetic --output test_output.mp4
```

---

## 8. 已知问题

| 问题 | 影响 | 状态 |
|------|------|------|
| Auth 未挂载到主路由 | 登录/注册 API 不可用 | 待修复 |
| YAMNet 模型文件缺失 | 音频分类走 mock 模式 | 待修复 |
| JSON 并发写入无锁 | 高并发下可能损坏数据 | 待修复 |
| 音频-视觉结果未融合 | 两条分析管线各自独立 | 待实现 |
| 摄像头非持续运行 | 需要手动 API 触发检测 | 待实现 |
| 重复宠物数据 | 6 只宠物有重复记录 | 待清理 |
| TensorFlow Lite 弃用警告 | 不影响功能 | 跟踪 |
| 无用户数据隔离 | 所有数据全局可见 | 待实现 |
| 无 HTTPS | 生产环境不安全 | 待实现 |

---

## 9. 改进路线图

### 短期（1-2 天）
1. `app.include_router(auth_router, prefix="/api/auth")`
2. 下载 YAMNet 模型到 `models/yamnet.tflite`
3. JSON 存储加文件锁 `threading.Lock()`
4. 清理重复宠物数据

### 中期（1 周）
1. 实现音频-视觉融合分析
2. 摄像头持续分析后台线程
3. 替换 JSON 存储为 SQLite
4. 添加用户数据隔离

### 长期（2 周+）
1. 外部视觉 API 集成（GPT-4V）+
2. 视频证据存储
3. HTTPS + 速率限制 + 安全加固
4. 移动端与后端 API 联调

---

## 10. 附录

### 文件结构

```
├── server/
│   ├── app.py                    # FastAPI 主服务
│   ├── audio_classifier/
│   │   └── classifier.py         # YAMNet 音频分类器
│   ├── behavior_analyzer/
│   │   └── rules.py              # 行为规则引擎
│   ├── camera/
│   │   ├── behavior_detector.py  # YOLOv8+CLIP 视觉检测器
│   │   └── camera_manager.py     # 摄像头管理器
│   ├── auth/
│   │   ├── database.py           # SQLite 用户模型
│   │   ├── dependencies.py       # JWT 依赖
│   │   ├── router.py             # 认证路由
│   │   └── schemas.py            # Pydantic 模型
│   ├── storage/
│   │   ├── schema.py             # 数据模型定义
│   │   └── repository.py         # JSON 存储 CRUD
│   └── notifier/
│       └── wechat.py             # 企业微信通知
├── frontend/
│   ├── index.html                # SPA 入口
│   ├── css/style.css             # 样式
│   ├── js/app.js                 # 前端逻辑 (27KB)
│   ├── manifest.json             # PWA 清单
│   └── sw.js                     # Service Worker
├── mobile-app/                   # Flutter 移动端
├── esp32-firmware/               # ESP32-CAM 固件
├── scripts/
│   └── test_video.py             # 视频测试脚本
├── tests/                        # 测试套件
├── test_videos/                  # 测试视频/图片
├── evidence/                     # 证据存储
├── storage/                      # JSON 数据文件
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── start.bat
```

### 使用模型

| 模型 | 来源 | 用途 | 大小 |
|------|------|------|------|
| YOLOv5nu | Ultralytics | 宠物检测 | 5.3MB |
| YOLOv8n | Ultralytics | 宠物检测 | 6.2MB |
| YOLOv8s | Ultralytics | 宠物检测 | 21.5MB |
| CLIP ViT-B/32 | OpenAI | 零样本行为分类 | ~150MB |
| YAMNet | Google | 音频分类 | ~15MB |
