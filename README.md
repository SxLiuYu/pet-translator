# 🐾 毛孩子翻译官

> **宠物行为分析师** — 声纹识别 + 视觉检测，读懂毛孩子的心情

## ✨ 功能

| 功能 | 说明 |
|------|------|
| 🎤 实时声纹监听 | ESP32-S3 + I2S 麦克风，检测狗叫/猫叫 |
| 📷 多源摄像头接入 | RTSP网络摄像头 / USB摄像头 / ESP32-CAM |
| 🧠 AI 行为分析 | YAMNet 声纹分类 + YOLOv8 视觉检测 + 行为规则引擎 |
| 🚨 实时警报推送 | 拆家 / 宠物呜咽 / 猫嘶嘶 → 微信即时通知 |
| 📊 每日精神状态报告 | 健康评分 + 活跃时段 + 行为分布图 |
| 💡 智能陪玩建议 | 根据今日行为给出针对性建议 |
| 📱 Flutter 移动端 | iOS/Android 双端实时监听 + 摄像头画面 + 报告查看 |

## 🏗️ 系统架构

```
摄像头接入 (三选一)
  ├── RTSP 网络摄像头 (小米/萤石/海康威视)
  ├── USB 摄像头 (OpenCV VideoCapture)
  └── ESP32-CAM (HTTP 快照)
         │
         ▼
FastAPI 后端 (:8000)
    ├── CameraManager     ← 多摄像头统一管理
    ├── BehaviorDetector  ← YOLOv8 视觉行为检测
    ├── AudioClassifier   ← YAMNet 声纹分类
    ├── BehaviorRulesEngine ← 声纹+视觉融合分析
    └── Notifier          ← 企业微信 / Server酱 推送
         │
         ├── WebSocket /ws        → Flutter 实时行为事件
         ├── WebSocket /ws/camera → Flutter 实时摄像头画面
         └── REST API             → Flutter 报告/快照
```

## 🚀 快速开始

### 1. 硬件准备

#### 音频部分
| 组件 | 型号 | 备注 |
|------|------|------|
| 主控 | ESP32-S3-DevKitC | N16R8 以上 |
| 麦克风 | INMP441 I2S 数字麦 | SNR 比模拟麦高 20dB+ |

**接线 (INMP441 → ESP32-S3):**
```
INMP441   ESP32-S3
  SCK  ── GPIO4
  WS   ── GPIO5
  SD   ── GPIO6
  VDD  ── 3.3V
  GND  ── GND
  L/R  ── GND (左声道)
```

#### 摄像头部分 (三选一)

**方案A: RTSP 网络摄像头 (推荐，无需额外硬件)**
```
如果你已有小米/萤石/TP-Link 家用摄像头:
1. 在摄像头 App 中查找 RTSP 地址
2. 通常格式: rtsp://admin:密码@192.168.1.100:554/stream
3. 通过后端 API 注册即可
```

**方案B: USB 摄像头 (直连服务器电脑)**
```
直接插在运行服务器的电脑 USB 口
后端自动识别，无需额外配置
```

**方案C: ESP32-CAM (自制，最便宜)**
```
AI-Thinker ESP32-CAM 开发板 (~30元)
烧录官方 camera_web_server 示例
WiFi 连接后通过 HTTP 获取画面
```

### 2. 后端部署

```bash
cd server
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 启动服务
python app.py
# 访问 http://localhost:8000/docs 查看 API 文档
```

### 3. 注册摄像头

```bash
# 方案A: RTSP 网络摄像头
curl -X POST "http://localhost:8000/api/camera/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "living_room",
    "source_type": "rtsp",
    "url": "rtsp://admin:password@192.168.1.100:554/h264Preview_01_main"
  }'

# 方案B: USB 摄像头 (设备索引 0)
curl -X POST "http://localhost:8000/api/camera/register" \
  -H "Content-Type: application/json" \
  -d '{"name": "usb_cam", "source_type": "usb", "device_index": 0}'

# 方案C: ESP32-CAM
curl -X POST "http://localhost:8000/api/camera/register" \
  -H "Content-Type: application/json" \
  -d '{"name": "esp32", "source_type": "esp32cam", "url": "192.168.1.50"}'
```

### 4. 查看摄像头状态和快照

```bash
# 查看所有摄像头状态
curl http://localhost:8000/api/camera/status

# 获取快照 (JPEG)
curl http://localhost:8000/api/camera/snapshot?name=living_room > snapshot.jpg

# 视觉行为检测
curl "http://localhost:8000/api/camera/detect?name=living_room"
```

### 5. 移动端运行

```bash
cd mobile-app
flutter pub get
flutter run
```

移动端首页可同时显示:
- 顶部: 摄像头实时画面 (YOLOv8 标注)
- 中部: 监听/摄像头控制按钮
- 底部: 实时行为事件流

## 📡 API 文档

启动后访问: **http://localhost:8000/docs** (Swagger UI)

### 摄像头相关端点

| 端点 | 方法 | 功能 |
|-------|------|------|
| `POST /api/camera/register` | 注册并启动摄像头 (RTSP/USB/ESP32-CAM) |
| `DELETE /api/camera/{name}` | 停止并注销摄像头 |
| `GET /api/camera/status` | 获取所有摄像头运行状态 (FPS、连接状态) |
| `GET /api/camera/snapshot?name=xxx` | 获取最新快照 (JPEG，可选 YOLO 标注) |
| `POST /api/camera/detect?name=xxx` | 对最新帧进行 YOLOv8 行为检测 |
| `WS /ws/camera` | WebSocket 实时推送 MJPEG 视频流 |

### 音频分析端点

| 端点 | 方法 | 功能 |
|-------|------|------|
| `POST /api/upload_audio` | 上传音频 → 声纹分类 + 行为分析 |
| `GET /api/report/daily` | 今日精神状态报告 |
| `POST /api/report/generate` | 生成报告并推送到微信 |
| `GET /api/events` | 历史行为事件 |
| `WS /ws` | WebSocket 实时推送行为事件 |

## 📷 摄像头配置参考

### RTSP 地址参考

| 品牌 | RTSP 地址格式 |
|------|--------------|
| 小米 | `rtsp://admin:密码@IP:554/h264Preview_01_main` |
| 萤石 | `rtsp://admin:密码@IP:554/Streaming/Channels/101` |
| 海康威视 | `rtsp://admin:密码@IP:554/h264/ch1/main/av_stream` |
| TP-Link | `rtsp://admin:密码@IP:554/stream1` |
| 通用 ONVIF | `rtsp://IP:554/onvif1` |

> 提示: 摄像头 IP 可通过路由器管理界面或摄像头 App 查看。RTSP 用户名密码通常默认 admin/admin，建议在 App 中修改。

### USB 摄像头查看 (Windows)

```powershell
# 查看设备
ffmpeg -list_devices true -f dshow -i dummy

# 测试采集
ffmpeg -f dshow -i video="USB Camera" -vframes 1 test.jpg
```

### ESP32-CAM 固件烧录

```bash
# Arduino IDE 中打开 Examples → ESP32 → Camera → CameraWebServer
# 选择 AI-Thinker ESP32-CAM 板型
# 修改 WiFi 配置后上传
# 打开串口监视器获取 IP 地址
```

## 🐶 视觉行为检测能力

| 检测项 | 说明 |
|--------|------|
| 🐕🐱 动物检测 | YOLOv8 COCO 预训练，支持 dog/cat |
| 🧘 姿态判断 | 根据 bounding box 面积/比例推断躺卧/站立/跑动 |
| 🦷 拆家检测 | 宠物 bbox 与可被啃咬物品重叠 → 触发警报 |
| 🏃 活跃程度 | low (躺卧) / medium (走动) / high (跑酷) |
| 🔴 危险警报 | 拆家行为即时推送到微信 |

## 🔮 扩展方向

- [ ] DeepSORT 多目标追踪 (多宠物区分)
- [ ] YOLOv8-Pose 关键点检测 (精确姿态识别)
- [ ] LLM 生成个性化自然语言行为报告
- [ ] 叫声异常检测 → 疾病预警
- [ ] 云端历史数据 + 长期行为趋势分析
- [ ] 智能音箱语音反馈 (对宠物说话)
- [ ] 自动录像 (触发拆家警报时自动保存视频片段)

## 📝 License

MIT
