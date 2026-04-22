# DrawAgent 2.0

当前仓库已经完成 DrawAgent 2.x 的核心升级主线：

- `backend/`：FastAPI + LangGraph + 会话存储 + SSE + 图片生成适配器
- `frontend/`：React + TypeScript + Vite 单页对话工作台
- `legacy/agent1/`：1.0 Streamlit 原型归档，仅作参考
- `Upgrade_Plan/`：本轮升级概要设计、分阶段施工计划与阶段文档
- `progress_docs/`：各 Phase 的开发进度与交接记录

## 当前状态

当前主线已推进到 `DrawAgent 2.x Phase 6：联调、测试、清理与验收收口`。

已具备的能力：

- 会话创建、删除、TTL 清理
- `source_text-first` 前端交互
- 显式 `run/resume` 工作流接口
- LangGraph 双节点工作流、澄清中断、双阶段 Critic 与 warning 放行
- SSE 阶段事件流
- 文本 artifact 查询、Prompt 预览、确认生成、图片下载
- `mock` 图片生成适配器与真实 `nano_banana2` provider 接入

## 启动后端

当前机器的稳定 Python 入口是：

```powershell
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe
```

常用命令：

```powershell
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py lint
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py test
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py diag-llm
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py diag-image
```

开发启动：

```powershell
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

说明：

- `python backend/manage.py dev` 在当前 Windows/Codex 环境下可能因为 `--reload` 触发权限问题
- 后端环境变量模板见 `backend/.env.example`
- 真实联调时，优先先跑 `diag-llm` 和 `diag-image`，不要直接从前端页面盲查 `Controller failed`

## 启动前端

安装依赖：

```powershell
npm.cmd --prefix frontend install
```

开发启动：

```powershell
npm.cmd --prefix frontend run dev
```

验证命令：

```powershell
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test
```

前端环境变量模板见 `frontend/.env.example`。

## 联调基线

推荐本地联调地址：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5173`

推荐先使用：

- `backend/.env` 中 `IMAGE_PROVIDER=mock`
- 可控的 `LLM_*` 配置

等主链路稳定后，再切到真实图片生成和真实模型配置。

联调主路径：

1. 初始化 session
2. 先提交 `source_text`
3. 如收到 `clarification_required`，使用 `resume(user_feedback)` 恢复
4. 正常补充修改使用 `run(user_feedback)`
5. 等待 `prompt_ready`
6. 用户确认后调用 `/api/generate/{session_id}`

## 真实联调排障

如果前端提交后只看到 `流程失败 Controller failed.` 或工具节点失败，先不要直接怀疑前端。

推荐排查顺序：

1. 先执行 `backend/manage.py diag-llm`
2. 再执行 `backend/manage.py diag-image`
3. 两者都通过后，再跑前端完整链路

说明：

- 当前工作流层会把节点失败统一包装成 `Controller failed.`、`logician_tool failed.` 之类的文案
- 更具体的根因会出现在 SSE `error.details`、后端日志，以及诊断命令输出里
- 当前前端错误卡片会展示 `error_code` 和关键诊断摘要，便于定位 `llm_invocation_error`、`artifact_validation_error` 或图片适配器失败

## Live Integration Tests

真实上游连通性测试默认不纳入日常回归，只有显式开启时才访问外部接口：

```powershell
$env:RUN_LIVE_LLM_TESTS="1"
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe -m pytest backend/tests/test_llm_live_integration.py

$env:RUN_LIVE_IMAGE_TESTS="1"
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe -m pytest backend/tests/test_image_live_integration.py
```

建议先跑诊断命令，再跑 live pytest。

## 配置优先级

后端配置优先级是：

1. 进程环境变量
2. `backend/.env`
3. [backend/app/core/settings.py](/D:/Projects/keyanhuitu/DrawAgent/backend/app/core/settings.py:1) 中的默认值

说明：

- `settings.py` 里的字段决定配置结构和默认值
- `backend/.env` 会覆盖默认值
- 若启动进程里存在同名环境变量，它会再覆盖 `.env`
- 配置读取结果会被缓存；修改 `backend/.env` 后需要重启后端进程

## 真实出图配置

要跑通最终真实绘图流程，至少需要在 `backend/.env` 里配置：

```env
LLM_API_KEY=...
LLM_BASE_URL=...
LLM_MODEL=...
IMAGE_PROVIDER=nano_banana2
IMAGE_API_KEY=...
IMAGE_BASE_URL=...
IMAGE_MODEL=gemini-3-pro-image-preview-4k
```

说明：

- 文本侧 `LLM_*` 负责把工作流推进到 `prompt_ready`
- 图片侧 `IMAGE_*` 负责 `/api/generate/{session_id}` 的真实出图
- 当前真实图片 provider 保留双协议适配：
- `IMAGE_MODEL` 以 `gemini-` 开头时，自动走 Google 原生 `generateContent` 格式
- 其他模型继续走 OpenAI-compatible Images API
- 业务语义仍统一记为 `nano_banana2`

## 关键文档

- `Upgrade_Plan/DrawAgent_2x_升级概要设计.md`
- `Upgrade_Plan/DrawAgent_2x_分阶段施工计划.md`
- `progress_docs/DrawAgent_2x_阶段4_业务工具文本化与双阶段Critic落地进度.md`
- `progress_docs/DrawAgent_2x_阶段5_前端source_text-first交互改造进度.md`
- `progress_docs/DrawAgent_2x_阶段6_联调测试清理与验收进度.md`

## Legacy 说明

`legacy/agent1/` 下保留了 1.0 的 `appp.py`、`core/` 和旧依赖，仅用于回看原型逻辑，不再承载 2.0 新开发。
