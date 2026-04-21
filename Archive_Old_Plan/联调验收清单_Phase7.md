# DrawAgent 2.0 Phase 7 联调验收清单

## 1. 验收基线

- 正式发布基线：`Mock 全链路稳定通过`
- 冒烟验证：在具备可用密钥时补一轮真实 `LLM + 图片生成` 验证
- 不新增功能，以稳定性、测试和交付文档为验收重点

## 2. 自动化校验

### 后端

- `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py lint`
- `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py test`

### 前端

- `npm.cmd --prefix frontend run lint`
- `npm.cmd --prefix frontend run build`
- `npm.cmd --prefix frontend run test`

通过标准：

- 所有命令退出码为 `0`
- 前端测试不再出现 `Vitest` 挂起或无法退出

## 3. Mock 主链路联调

联调前配置：

- `backend/.env` 中 `IMAGE_PROVIDER=mock`
- `frontend/.env` 中 `VITE_API_BASE_URL=http://127.0.0.1:8000`

### 场景 A：新建任务闭环

1. 打开前端页面，自动创建 session
2. 上传一个或多个附件
3. 输入新任务需求
4. 观察 SSE 阶段流转
5. 收到 `prompt_ready`
6. 展示 `payload_final`
7. 点击“确认生成”
8. 收到 `image_generated`
9. 页面展示图片并可下载

验收点：

- 前端不依赖轮询推进流程
- `payload_final.ready_for_generation=true` 前禁止出图
- 图片展示和下载统一走 `/api/download/{session_id}`

### 场景 B：澄清追问

1. 提交信息不足的输入
2. 收到 `clarification_required`
3. 前端切换到“继续流程”
4. 补充内容并再次提交
5. 工作流恢复并继续推进

验收点：

- 继续流程沿用原 `session_id`
- SSE 恢复后不丢失事件顺序

### 场景 C：修改反馈

分别验证：

- 修改逻辑
- 修改风格
- 修改排版

验收点：

- 保持原 `session_id`
- 流程只触发必要的局部重跑
- 最终仍能回到 `prompt_ready` 或明确失败

### 场景 D：评审失败自动回滚

1. 触发 `review_failed`
2. 前端展示失败原因和回滚阶段
3. 后端自动继续回滚修正

验收点：

- UI 出现明确的“评审未通过”提示
- 回滚后流程能继续，或进入 `failed` 并给出错误说明

### 场景 E：异常与清理

需覆盖：

- `resource_conflict`
- `session_expired`
- `file_not_found`
- `image_not_ready`
- 页面关闭或点击“重新开始”后的 session 清理

验收点：

- 错误提示文案明确
- 会话删除后旧附件、事件流和下载地址不再可用

## 4. 真实 Provider 冒烟

前置条件：

- `backend/.env` 中已填写可用 `LLM_*` 和 `IMAGE_*` 配置
- `IMAGE_PROVIDER` 已切到真实 provider

最小步骤：

1. 完成一次新建任务到 `prompt_ready`
2. 点击“确认生成”
3. 等待真实出图结果

记录项：

- 使用的模型与 provider
- 是否成功出图
- 若失败，失败阶段、错误码和排查建议

## 5. 收口标准

Phase 7 可视为完成，当且仅当：

- Mock 自动化命令全部通过
- Mock 主链路联调清单全部跑通
- 真实 provider 至少完成一次冒烟，或明确记录受阻原因
- `README.md`、部署说明、进度文档已同步到当前阶段
