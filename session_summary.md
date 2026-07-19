# 会话内容整理

> 更新日期：2026-07-19

## 一、历史问题与处理结果

| 问题 | 结果 | 当前状态 |
|------|------|----------|
| 认证路由未挂载 | 主应用挂载 `/api/auth`，注册、登录、用户信息和改密可用 | 已完成 |
| 宠物数据重复 | 仓储写入增加去重/覆盖策略，历史数据完成幂等清理 | 已完成 |
| JSON 并发写风险 | 增加进程内锁、全局写锁和临时文件原子替换 | 已缓解，仍非事务数据库 |
| 音频和视觉独立 | 新增按宠物隔离的有界时间窗口融合及查询 API | 已完成 |
| 事件/证据 ID 同秒冲突 | 改为 UUID 派生 ID | 已完成 |
| FastAPI/Pydantic 兼容 | FastAPI 升级至 0.115.0，并处理 Pydantic 2 模型命名空间 | 已完成 |
| Passlib/Python 弃用告警 | 改用直接 bcrypt，清除项目内 `datetime.utcnow()` | 已完成 |
| 静止帧加载视觉模型 | 运动检测提前，无运动时直接降级返回 | 已完成 |
| 部署依赖和模块路径 | Dockerfile 纳入认证依赖并修正 Uvicorn 启动路径 | 已完成，待可用 daemon 构建 |
| 缺少重复 CI | 新增 Python 3.11 GitHub Actions | 已完成 |

## 二、本轮设计决策

本轮采用 superpowers brainstorming、TDD、systematic debugging 和 verification 的工作方式，设计记录位于：

- `docs/superpowers/specs/2026-07-19-reliability-optimization-design.md`
- `docs/superpowers/plans/2026-07-19-reliability-optimization.md`

核心取舍：

- 选择事件驱动、单进程内存、有界历史的融合引擎，不在本轮引入数据库迁移或常驻摄像头 worker。
- 融合按 `pet_id` 隔离，输入时间统一规范为 UTC，超出窗口或真实时间过期的观察不配对。
- 有效宠物声音和有意义视觉行为进入事件与融合；环境噪音、`unknown`、`no_pet_detected` 不进入。
- `/api/events` 的查询过滤与 `PET_ID` 摄取默认值解耦，所有集合 `limit` 限制为 `1..100`。
- 保留已有标准 bcrypt 哈希兼容，不做用户数据库迁移。

## 三、实现记录

### 音视频融合与事件

- 重写 `server/audio_visual_fusion.py`：线程安全、按宠物隔离、有界历史、可注入时钟、非法时间戳降级、真实时间过期、置信度约束和防御性结果副本。
- `POST /api/upload_audio` 接受 `pet_id`，保存音频证据与事件，并返回融合结果。
- `POST /api/camera/detect` 接受 `pet_id`，保存视觉事件和 JPEG 证据，并广播融合更新。
- 新增 `GET /api/fusions`；修复 `GET /api/events` 的无筛选语义；事件及证据使用 UUID 派生标识。

### 兼容、依赖和交付

- 直接使用 bcrypt 替代 Passlib，认证导入在 `DeprecationWarning` 严格模式下通过。
- FastAPI 固定为 0.115.0，`python-multipart` 固定为 0.0.20，生产 requirements 纳入认证依赖。
- 新增轻量 `server/requirements-test.txt` 和 `.github/workflows/ci.yml`。
- 修复 Dockerfile 认证依赖复制和应用模块路径。
- `.gitignore` 覆盖 Python 缓存、测试缓存、运行时证据和本地 `.DS_Store`。

## 四、最终验收

当前测试总数为 55 项，覆盖音频分类、融合时间语义、API 契约、认证、行为规则、摄像头和存储。

```text
python -m pytest tests/ -q -W error::DeprecationWarning
55 passed

Python 3.11 全新虚拟环境，按 server/requirements-test.txt 安装
55 passed，1 个来自 Starlette 的第三方 PendingDeprecationWarning

python -m compileall -q server tests
通过

应用导入、关键路由、/health schema smoke
通过

GitHub Actions YAML 解析
通过

git diff --check
通过
```

Docker 客户端可执行，但无法连接 `unix:///var/run/docker.sock`，本机也未安装可启动的 Docker Desktop，因此镜像构建和容器 `/health` 未执行。该限制已在验收报告中如实记录。

## 五、未完成边界

1. 融合历史尚未持久化，服务重启后清空。
2. 摄像头仍需 API 手动触发检测，没有持续分析 worker。
3. YAMNet 模型缺失时使用降级分类，未做真实模型准确率验收。
4. JSON 存储不具备事务数据库语义。
5. Pet/Event/Report 尚未按认证用户隔离。
6. CORS、HTTPS、限流、安全头和生产密钥管理仍需加固。
7. 未覆盖物理摄像头、真实音频数据集和完整 Flutter 设备链路。

完整验收证据见 `docs/acceptance-report.md`。
