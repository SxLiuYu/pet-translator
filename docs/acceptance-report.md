# 可靠性优化验收报告

> 日期：2026-07-19
> 分支：`master`
> 实施基线：`e93da91a1c525eece8e8c1de7ee07640a53f8fe6`

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

结果：`55 passed in 1.66s`。

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

GitHub Actions YAML 使用本地 YAML 解析器加载：通过。

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

本机 Docker 客户端可用：`Docker Engine Community 29.6.1`。构建时无法连接：

```text
failed to connect to the docker API at unix:///var/run/docker.sock
```

尝试启动桌面应用时系统返回：

```text
Unable to find application named 'Docker'
```

因此本次未执行镜像构建和容器 `/health` smoke，不能将 Docker 构建标记为通过。Dockerfile 的 requirements 复制和 Uvicorn 模块路径已完成静态审查；剩余验证需在具备 Docker daemon 的环境执行。

## 5. 交付审查

- 检查完整差异，未发现新增凭据、令牌、私钥或真实 webhook。
- 默认开发 JWT 密钥仍存在，已列为生产部署限制。
- `evidence/`、Python 缓存、测试缓存和 `.DS_Store` 已忽略，不纳入提交。
- 已跟踪的 `server/auth/users.db` 属于历史仓库内容，本次未修改。
- CI 固定 Python 3.11，并执行完整测试、字节编译和 `git diff --check`。

## 6. 结论与限制

除 Docker daemon 环境阻塞和明确排除的模型/硬件场景外，本次设计范围内的代码与离线验收通过，可交付到 `master`。仍需持续跟踪：

- 融合历史仅内存保存，重启清空。
- 摄像头检测仍由 API 手动触发。
- YAMNet 文件缺失时音频采用降级模式。
- JSON 存储不是事务数据库。
- 认证用户尚未隔离 Pet/Event/Report 数据。
- CORS 全开，尚无 HTTPS、限流、安全头和完整生产密钥管理。
- 尚未验收真实模型准确率、物理摄像头、真实音频数据集和完整移动端设备流程。

最终交付以 Git 历史中的本次可靠性优化提交和远端 `origin/master` 一致性核验为准。
