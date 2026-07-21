# 毛孩子翻译官 - 项目全景文档

> 更新日期：2026-07-19

## 1. 项目定位

毛孩子翻译官是一个宠物行为分析系统。后端接收音频和摄像头画面，结合声纹分类、视觉检测、行为规则与按宠物隔离的时间窗口融合，生成事件、警报和每日状态报告；Web SPA、Flutter 客户端和 ESP32-CAM 固件构成现有接入面。

## 2. 当前架构

```text
音频上传 -> AudioClassifier -> BehaviorRulesEngine ----+
                                                    +-> AudioVisualFusionEngine
摄像头帧 -> BehaviorDetector -> 视觉事件/图片证据 -----+
                       |
                       +-> JSON Event/Pet/Report 存储
                       +-> WebSocket / REST / 通知

认证：FastAPI Router -> JWT + bcrypt -> SQLite users.db
```

技术基线：

- Python 3.9-3.11，CI 使用 Python 3.11。
- FastAPI 0.115.0、Pydantic 2、Uvicorn。
- 音频使用 YAMNet/TensorFlow Lite；模型缺失时降级运行。
- 视觉使用 OpenCV、YOLOv8，可选 CLIP 行为分类。
- 认证使用 SQLAlchemy、JWT 和直接 bcrypt 哈希。
- 宠物、事件和报告使用带进程内锁及原子替换的 JSON 存储。

## 3. 已实现能力

### 服务与数据

- `/health` 返回模型、宠物、今日事件和摄像头状态。
- 宠物 CRUD、事件筛选与反馈、统计、趋势、导出和每日报告。
- 音频事件保存原始证据，视觉事件保存 JPEG 证据，标识符使用 UUID 派生值避免同秒碰撞。
- `GET /api/events` 未传 `pet_id` 时返回所有事件，不受摄取默认值 `PET_ID` 影响。
- 集合接口 `limit` 在 API 边界约束为 `1..100`。

### 音视频融合

- 音频与视觉结果按 `pet_id` 隔离，只有同一宠物、时间窗口内的最近观察才会融合。
- 时间戳统一为 UTC；支持 `Z`、时区偏移、非法时间戳降级和注入时钟测试。
- 同时使用真实当前时间和最近观察时间淘汰过期输入，避免回放数据误配。
- 融合置信度采用音频 45%、视觉 55% 的确定性权重，结果与历史均有界并返回防御性副本。
- 环境噪音不持久化、不融合；`unknown` 和 `no_pet_detected` 视觉结果只作诊断响应。
- `POST /api/upload_audio`、`POST /api/camera/detect` 返回当前融合结果；`GET /api/fusions` 查询指定宠物历史。

### 视觉、认证与交付

- 静止帧先执行运动检测，无运动时不加载 YOLO/CLIP 模型。
- 认证路由已挂载到 `/api/auth`，使用 bcrypt 并兼容已有标准 bcrypt 哈希。
- 项目自有代码已移除 Passlib `crypt` 和 `datetime.utcnow()` 弃用路径。
- Dockerfile 已纳入认证依赖并使用正确 Uvicorn 模块路径。
- GitHub Actions 在 Python 3.11 上执行 55 项测试、字节编译和差异检查。

## 4. 核心 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 服务、模型、宠物、事件和摄像头状态 |
| `/api/upload_audio` | POST | 音频分类、规则分析、证据、事件与融合 |
| `/api/camera/detect` | POST | 手动视觉检测、证据、事件与融合 |
| `/api/fusions` | GET | 按宠物查询最近融合结果 |
| `/api/events` | GET | 查询全部或指定宠物事件 |
| `/api/pets` | GET/POST | 宠物列表与创建 |
| `/api/report/daily` | GET | 当日状态报告 |
| `/api/auth/register` | POST | 注册并签发 JWT |
| `/api/auth/login` | POST | 登录并签发 JWT |
| `/api/auth/me` | GET | 当前认证用户 |
| `/ws` | WebSocket | 行为事件推送 |
| `/ws/camera` | WebSocket | 摄像头画面推送 |

完整路由和请求模型以启动后的 `/docs` 为准。

## 5. 验收状态

2026-07-19 本地验收结果：

```text
python -m pytest tests/ -q -W error::DeprecationWarning
55 passed

python -m compileall -q server tests
通过

应用导入、关键路由和 /health 响应模型 smoke
通过

GitHub Actions YAML 解析
通过

git diff --check
通过
```

另外在 Python 3.11 全新虚拟环境中严格按 `server/requirements-test.txt` 安装并运行，结果为 `55 passed`。唯一额外提示是 Starlette 0.38.6 内部导入方式产生的第三方 `PendingDeprecationWarning`；CI 只将 `DeprecationWarning` 视为错误，因此项目定义的 CI 命令通过。

Docker 客户端版本为 29.6.1，但本机无法连接 `unix:///var/run/docker.sock`，且没有 Docker Desktop 应用，故本次不能声称镜像构建已通过。Dockerfile 修复已由静态审查覆盖，仍需在可用 daemon 或 GitHub 构建环境验证。

详细命令、范围和证据见 `docs/acceptance-report.md`。

## 6. 已知边界与风险

- 融合历史仅在当前进程内存中，服务重启后清空。
- 摄像头检测依赖手动 API 触发，尚无持续采样、背压和退出管理 worker。
- 缺少 `models/yamnet.tflite` 时音频分类使用降级模式。
- JSON 事件存储不是事务数据库，跨进程并发和复杂查询能力有限。
- JWT 只覆盖认证端点，Pet/Event/Report 尚未按用户授权隔离。
- CORS 全开，默认 JWT 密钥只适合开发；生产仍需 HTTPS、限流、安全头和密钥管理。
- 未使用标注数据集验收真实模型准确率，也未覆盖物理摄像头和真实音频硬件。
- Flutter 客户端仍属于基础实现，尚未完成完整端到端设备验收。

## 7. 后续路线

1. 在受控数据集上补齐 YAMNet/YOLO 模型资源、准确率基线和回归样本。
2. 为摄像头持续分析设计独立 worker，明确采样频率、资源上限、背压、幂等和关闭行为。
3. 将融合历史和 JSON 业务数据迁移到具备事务与索引能力的数据库。
4. 将用户所有权引入 Pet/Event/Report，并在所有查询和写入路径强制授权。
5. 增加 Docker daemon CI、容器 `/health` smoke，以及生产安全配置检查。
