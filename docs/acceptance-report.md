# 验收报告

> 最后更新：2026-07-21

---

## 生产安全加固验收 (2026-07-21)

> 分支：`master`
> 实施提交：`05d6381`

### 验收范围

环境门控的 JWT/CORS 强制检查、slowapi 内存限流、安全响应头中间件、启动安全自检。

设计文档：`docs/superpowers/specs/2026-07-21-production-security-hardening-design.md`

### 功能验收

| 验收项 | 结果 | 证据 |
|--------|------|------|
| `ENVIRONMENT=production` 检查 JWT_SECRET 未设置 → 启动失败 | 通过 | `test_production_mode_raises` |
| `ENVIRONMENT=production` 检查 CORS_ORIGINS=* → 启动失败 | 通过 | `test_wildcard_flagged` |
| `ENVIRONMENT=development` 不安全配置仅警告 | 通过 | `test_development_mode_warns_only` |
| 认证端点 5/min 限流 → 429 | 通过 | `test_auth_login_rate_limited` |
| 上传端点 10/min 限流 → 429 | 通过 | `test_upload_audio_rate_limited` |
| 所有响应携带安全头 (X-Content-Type-Options 等) | 通过 | `test_standard_security_headers_present` |
| 开发模式不返回 HSTS | 通过 | `test_hsts_absent_in_development` |

### 自动化验证

```bash
python -m pytest tests/ -q
```

结果：`66 passed, 2 warnings in 1.92s`（+11 项新测试）。

```bash
python -m compileall -q server tests
git diff --check
```

结果：均通过。

应用导入 smoke：30 个路由，`SecureHeadersMiddleware` 和 `CORSMiddleware` 已挂载。

### 新增文件

| 文件 | 用途 |
|------|------|
| `server/config.py` | `is_production()`、安全自检 |
| `server/rate_limiter.py` | 共享 slowapi Limiter 实例 |
| `server/security_headers.py` | 安全响应头中间件 |
| `tests/test_config.py` | 7 项安全配置测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `server/app.py` | 挂载限流器、安全头中间件、启动安全自检、端点装饰器 |
| `server/auth/router.py` | 登录/注册端点添加限流 |
| `server/requirements.txt` | 添加 slowapi |
| `server/requirements-test.txt` | 添加 slowapi |
| `.env.example` | 添加 ENVIRONMENT、JWT_SECRET、CORS_ORIGINS |
| `README.md` | 添加生产部署说明、更新边界 |
| `tests/test_app_api.py` | 添加限流和安全头测试 |

### 结论

安全加固代码、离线测试、字节编译和 diff 检查全部通过，已推送至 `origin/master`。

---

## 可靠性优化验收 (2026-07-19)

## 1. 验收范围

本次验收覆盖按宠物隔离的音视频融合、事件与证据持久化、API 查询契约、认证兼容、视觉降级顺序、依赖与 Dockerfile 修复、离线测试依赖及 GitHub Actions。设计与实施计划分别位于：

- `docs/superpowers/specs/2026-07-19-reliability-optimization-design.md`
- `docs/superpowers/plans/2026-07-19-reliability-optimization.md`

不在本次范围：持久化融合历史、持续摄像头 worker、用户级业务数据授权、模型准确率评测和生产网络安全设施。

## 2. 功能验收

| 验收项 | 结果 | 证据 |
|--------|------|------|
| 同一宠物、时间窗口内音视频融合 | 通过 | 融合单测与 API 集成测试 |
| 不同宠物隔离、历史有界 | 通过 | `test_history_is_isolated_by_pet_and_limited` |
| 真实时间过期、非法时间戳、时区规范化 | 通过 | 融合时钟与时间戳单测 |
| 音频事件、证据及融合响应 | 通过 | 上传 API 集成测试 |
| 视觉事件、JPEG 证据及融合响应 | 通过 | 摄像头检测 API 集成测试 |
| 环境噪音和无意义视觉结果不持久化/融合 | 通过 | 分支审查与现有分类/视觉测试 |
| `/api/events` 无参数返回全部事件 | 通过 | 设置 `PET_ID` 后的 API 回归测试 |
| `limit` 仅接受 `1..100` | 通过 | 事件与融合 API 参数化测试 |
| bcrypt 认证及 JWT | 通过 | 认证功能和严格导入测试 |
| 静止帧不触发视觉模型加载 | 通过 | 摄像头测试与实现顺序审查 |

## 3. 自动化验证

### 当前开发环境

```bash
python -m pytest tests/ -q -W error::DeprecationWarning
```

结果：`55 passed in 1.65s`。

```bash
python -m pytest tests/test_audio_visual_fusion.py tests/test_app_api.py -q
```

结果：`19 passed`。

```bash
python -m compileall -q server tests
```

结果：通过，无输出。

应用导入、认证/融合关键路由和 `/health` 的 `pets` 响应模型 smoke：通过。

使用真实 Uvicorn 进程在 `127.0.0.1:18765` 启动应用后请求：

```bash
curl -fsS http://127.0.0.1:18765/health
```

结果：HTTP 请求成功，响应包含 `status: ok`、`model_loaded: true`、`pets`、`events_today` 和 `cameras`。

GitHub Actions YAML 使用本地 YAML 解析器加载，容器 smoke 脚本使用 `bash -n`
检查：均通过。

```bash
git diff --check
```

结果：通过，无输出。

### Python 3.11 干净环境

创建全新 Python 3.11 虚拟环境，仅安装 `server/requirements-test.txt` 后执行完整测试：

```text
55 passed, 1 warning in 39.23s
```

唯一警告是 Starlette 0.38.6 内部对 `multipart` 的导入触发第三方 `PendingDeprecationWarning`：`Please use import python_multipart instead.` 项目 CI 命令将 `DeprecationWarning` 视为错误，不将 `PendingDeprecationWarning` 升级，因此 CI 验收通过；项目自有认证代码的弃用告警已清除。

## 4. Docker 验收

本机 Docker 客户端可用（`Docker Engine Community 29.6.1`），但 daemon 不可用：

```text
failed to connect to the docker API at unix:///var/run/docker.sock
```

因此使用 GitHub 托管 runner 完成权威容器验收。首次运行
[`29669778689`](https://github.com/SxLiuYu/pet-translator/actions/runs/29669778689)
在系统包安装阶段发现浮动的 `python:3.9-slim` 已指向 Debian Trixie，且
`libgl1-mesa-glx` 已无安装候选。随后将基础镜像固定为
`python:3.9-slim-bookworm`，并使用 Bookworm 提供 `libGL.so.1` 的 `libgl1`。

修复提交 `536e065cd2935df83d4684d5053ef7abd7d610e7` 对应的 GitHub Actions
运行 [`29669863702`](https://github.com/SxLiuYu/pet-translator/actions/runs/29669863702)
全部通过：

- `test`：23 秒，完整测试、字节编译和 diff 检查通过。
- `docker-smoke`：3 分 33 秒，生产镜像构建及容器健康检查通过。
- 镜像使用完整生产依赖，包括 TensorFlow、Ultralytics、Torch 和 OpenCV；未用轻量测试依赖替代。
- 容器按 Dockerfile 的 Uvicorn 命令启动；约 4 秒后 `/health` 可访问。
- 响应断言通过：`status == "ok"`、`model_loaded is true`，且 `pets`、
  `events_today`、`cameras` 类型符合 API 契约。
- smoke 脚本在失败时输出容器日志，并在所有结果下强制删除测试容器。

另使用 `pip download --only-binary=:all:` 按 Python 3.9/Linux x86_64 目标解析
`server/requirements.txt`，全部依赖均有二进制轮子；下载集合约 `1.4G`。

## 5. 交付审查

- 检查完整差异，未发现新增凭据、令牌、私钥或真实 webhook。
- 默认开发 JWT 密钥仍存在，已列为生产部署限制。
- `evidence/`、Python 缓存、测试缓存和 `.DS_Store` 已忽略，不纳入提交。
- 已跟踪的 `server/auth/users.db` 属于历史仓库内容，本次未修改。
- CI 固定 Python 3.11，并执行完整测试、字节编译和 `git diff --check`；独立
  Docker job 验证完整生产镜像和真实 `/health`。
- 实现提交：`6a3a8c740780f97ac5c90020745c835ca44cce15`（`feat: harden multimodal fusion and delivery`）。
- 容器 CI 提交：`ba30890256ad83ce1b631008d92f078df8cae234`；Docker 兼容修复提交：
  `536e065cd2935df83d4684d5053ef7abd7d610e7`。
- 上述提交均已推送至 `origin/master`；最终文档提交后再次核对本地 HEAD、远端
  SHA 和 GitHub Actions 状态。

## 6. 结论与限制

本次设计范围内的代码、离线测试、生产镜像构建和容器健康检查全部通过，可交付到 `master`。本机 daemon 缺失不再构成交付阻塞，因为同一 Dockerfile 已在 GitHub 托管 Linux runner 上完成端到端验收。仍需持续跟踪：

- 融合历史仅内存保存，重启清空。
- 摄像头检测仍由 API 手动触发。
- YAMNet 文件缺失时音频采用降级模式。
- JSON 存储不是事务数据库。
- 认证用户尚未隔离 Pet/Event/Report 数据。
- ~~CORS 全开，尚无 HTTPS、限流、安全头和完整生产密钥管理。~~ 已于 2026-07-21 生产安全加固迭代解决（限流、安全头、JWT/CORS 强制检查已上线；HTTPS 反向代理仍需部署侧配置）。
- 当前完整镜像会解析 Torch 的 CUDA 依赖，构建体积和时间较高；后续可单独设计 CPU-only 生产依赖锁定方案。
- 尚未验收真实模型准确率、物理摄像头、真实音频数据集和完整移动端设备流程。

最终交付以 Git 历史中的可靠性优化实现提交、容器 CI/兼容修复提交、文档收尾提交，以及远端 `origin/master` 一致性核验为准。
