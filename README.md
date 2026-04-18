# DrawAgent 2.0

当前仓库已经完成 2.0 的核心重构主干：

- `backend/`：FastAPI + LangGraph + 会话存储 + SSE + 图片生成适配器
- `frontend/`：React + TypeScript + Vite 单页对话工作台
- `legacy/agent1/`：1.0 Streamlit 原型归档，仅作参考
- `Refactoring_Upgrading_Plan/`：概要设计、分阶段计划、接口与联调文档
- `progress_docs/`：各 Phase 的开发进度与交接记录

## 当前状态

当前主线已推进到 `Phase 7：联调、测试、验收与部署收口`。

已具备的能力：

- 会话创建、删除、TTL 清理
- 上传附件、结构化制品查询
- LangGraph 工作流、澄清中断、Critic 回滚
- SSE 阶段事件流
- Prompt 预览、确认生成、图片下载
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
- 真实联调时，优先先跑 `diag-llm` 和 `diag-image`，不要直接从前端页面盲查 `Orchestrator failed`

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

## 真实联调排障

如果前端首轮提交后只看到 `流程失败 Orchestrator failed.`，先不要直接怀疑前端。

推荐排查顺序：

1. 先执行 `backend/manage.py diag-llm`
2. 再执行 `backend/manage.py diag-image`
3. 两者都通过后，再跑前端完整链路

说明：

- 当前工作流层会把节点失败统一包装成 `Orchestrator failed.`、`logician failed.` 之类的文案
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

- `Refactoring_Upgrading_Plan/详细分阶段重构升级计划.md`
- `Refactoring_Upgrading_Plan/项目升级概要设计.md`
- `Refactoring_Upgrading_Plan/前端接口说明文档_Phase6.md`
- `Refactoring_Upgrading_Plan/前后端启动说明.md`
- `Refactoring_Upgrading_Plan/联调验收清单_Phase7.md`
- `progress_docs/Phase_7.md`

## Legacy 说明

`legacy/agent1/` 下保留了 1.0 的 `appp.py`、`core/` 和旧依赖，仅用于回看原型逻辑，不再承载 2.0 新开发。
