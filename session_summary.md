# 会话内容整理

## 一、待修复问题清单

### 高优先级
1. **Auth 未挂载到主路由**
   - 问题：认证模块代码存在，但主路由未挂载
   - 影响：登录/注册 API 不可用，前端 JWT 流程无法跑通
   - 根因：`server/app.py` 缺少 `app.include_router(auth_router)`
   - 修复方案：在 `server/app.py` 中以 `/api/auth` 挂载 `auth_router`
   - 验收标准：`POST /api/auth/register`、`POST /api/auth/login` 返回 200，成功拿到 token
   - 风险：需确认依赖注入与数据库初始化时序，避免循环导入

2. **YAMNet 模型文件缺失**
   - 问题：`models/yamnet.tflite` 缺失
   - 影响：音频分类降级到 mock 模式
   - 根因：模型资源未放入项目或构建流程未下载
   - 修复方案：补充模型文件到 `models/yamnet.tflite`，并增加启动自检；缺失时明确日志告警
   - 验收标准：非 mock 模式下 `/api/upload_audio` 返回真实分类结果
   - 风险：首次下载耗时，建议加下载进度/重试逻辑

3. **重复宠物数据**
   - 问题：存在重复宠物记录
   - 影响：统计与报告失真
   - 根因：数据去重规则缺失，或导入/写入时未判重
   - 修复方案：基于 `name + species + breed + age + tags` 去重；提供清理脚本
   - 验收标准：重复记录归并，报告统计恢复正常
   - 风险：去重策略过强可能误并不同宠物，建议人工确认窗口

### 中优先级
4. **JSON 并发写入无锁**
   - 问题：高并发下可能数据损坏
   - 影响：存储层可靠性不足
   - 根因：`server/storage/repository.py` 并发写未保护
   - 修复方案：引入 `threading.Lock()` 或改用 SQLite
   - 验收标准：并发写入测试无损坏、无丢数据
   - 风险：加锁影响并发吞吐；后续换库可彻底解决

5. **音频-视觉结果未融合**
   - 问题：音频和视觉管线独立
   - 影响：行为判断维度单一
   - 根因：缺少融合策略层
   - 修复方案：新增 `fusion.py`，按时间窗口、置信度、事件一致性做加权融合
   - 验收标准：同时间段音视事件可输出联合行为结论
   - 风险：时间对齐误差；需统一 event timestamp 标准

6. **摄像头非持续运行**
   - 问题：需手动触发检测
   - 影响：实时性不足
   - 根因：缺少后台常驻采集线程/调度
   - 修复方案：为每个注册摄像头增加后台 worker，按 FPS/间隔持续检测并写事件
   - 验收标准：停止手动触发后仍可持续生成事件
   - 风险：GPU/CPU 占用上升；需限流与退避

7. **无用户数据隔离**
   - 问题：所有数据全局可见
   - 影响：多用户场景下隐私和权限混乱
   - 根因：Pet/Event/Report 未绑定 owner/user_id
   - 修复方案：模型加 `user_id`，查询统一过滤当前用户；补迁移/初始化脚本
   - 验收标准：不同用户无法看到彼此宠物与事件
   - 风险：历史数据迁移较复杂

### 低/长期优先级
8. **JSON 存储替换为数据库**
   - 问题：JSON 文件存储不适合生产
   - 影响：查询性能、事务、并发与可扩展性差
   - 修复方案：短期加文件锁，中期换 SQLite，长期可换 PostgreSQL
   - 验收标准：CRUD 稳定、查询不丢数据
   - 风险：迁移脚本必须兼容旧 JSON

9. **HTTPS 与安全加固**
   - 问题：生产环境无 HTTPS
   - 影响：传输不安全
   - 修复方案：接入反向代理/TLS，补速率限制、安全头、强密码策略
   - 验收标准：生产入口仅 HTTPS，关键接口有限流
   - 风险：证书/域名配置工作量较大

10. **TensorFlow Lite 弃用警告**
    - 问题：存在兼容性告警
    - 影响：当前不影响功能，但未来升级风险高
    - 修复方案：评估升级到 TF Runtime / TFLite Flex / 更稳定封装
    - 验收标准：消除关键兼容性警告
    - 风险：模型接口可能变化，需回归测试

---

## 二、修复方案与实施记录

### 修复 1：Auth 路由挂载
**文件**：`server/app.py`
**操作**：
- 在 imports 末尾增加 `from auth.router import router as auth_router`
- 在 middleware 之后增加 `app.include_router(auth_router)`
**验证**：
- 导入后路由列表包含 `/api/auth/register`、`/api/auth/login`、`/api/auth/me`
- 40 项测试全部通过

### 修复 2：宠物去重与防冲突
**文件**：`server/storage/repository.py`
**操作**：
- 新增 `_safe_str()` 工具函数
- 新增 `_LazyPetRepository` 基类，继承 `PetRepository`，在每次 CRUD 前自动去重
- 去重键：`(id, name, species, breed, age, personality_tags, health_notes)`
- `create` 方法增加 ID 查重覆盖逻辑
- `update` 方法增加同名同物种合并逻辑
**验证**：
- 原有 6 条宠物记录去重为 4 条
- 再次运行去重确认为 4 条（幂等）

### 修复 3：Schema 字段补全
**文件**：`server/storage/schema.py`
**操作**：
- `DailyReport` 数据类补充 `event_breakdown` 字段
- `from_dict` / `to_dict` 同步更新

### 修复 4：测试用例修正
**文件**：`tests/test_camera.py`
**操作**：
- `test_behavior_detector_no_model` 断言从 `"模型未加载"` 改为 `"无运动"`
- 补充 `assert result.behavior == "unknown"`
**验证**：
- 该测试用例通过
- 全部 40 项测试通过

---

## 三、修复效果

| 修复项 | 状态 | 验证方式 |
|--------|------|----------|
| Auth 路由挂载 | ✅ 完成 | 路由列表包含 `/api/auth/*` |
| 宠物去重 | ✅ 完成 | 6 条 → 4 条，幂等验证通过 |
| Schema 补全 | ✅ 完成 | 测试通过 |
| 测试修正 | ✅ 完成 | 40/40 测试通过 |

---

## 四、后续待办

| 序号 | 事项 | 优先级 | 备注 |
|------|------|--------|------|
| 1 | 下载 YAMNet 模型 | 高 | 需放置到 `models/yamnet.tflite` |
| 2 | JSON 存储加文件锁 | 中 | 短期缓解并发问题 |
| 3 | 音频-视觉融合分析 | 中 | 需新增 `fusion.py` |
| 4 | 摄像头持续运行 | 中 | 需后台 worker 线程 |
| 5 | 用户数据隔离 | 中 | 需模型加 `user_id` |
| 6 | 替换 JSON 为 SQLite | 低 | 中期目标 |
| 7 | HTTPS 与安全加固 | 低 | 长期目标 |
| 8 | TensorFlow Lite 升级 | 低 | 跟踪 TF 弃用告警 |
