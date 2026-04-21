# Phase 2 开发进度

## 当前状态

已完成。

## 本阶段目标

建立 2.0 后端的核心契约、GraphState、会话内存存储、临时文件目录管理、TTL 清理机制，以及后续 API/SSE 所需的事件与错误模型。

## 已完成内容

- 新增后端 schema 契约：
  - `LogicSpec`
  - `StyleSpec`
  - `MapperSpec`
  - `ReviewSpec`
  - `FinalPromptSpec`
  - `SessionStateSummary`
  - API DTO
  - 事件模型
- 新增 LangGraph 兼容 `GraphState`
- 新增统一错误类型与错误码
- 新增 `SessionStore`
- 新增 `TempFileManager`
- 新增 `CleanupService`
- 在 `settings.py` 和 `.env.example` 中补齐 Phase 2 所需配置
- 在 FastAPI app 中接入 lifespan，初始化会话存储与后台清理任务
- 补充 Phase 2 相关测试

## 验证结果

- 已通过 `conda run -n DrawAgent python backend/manage.py lint`
- 已通过 `conda run -n DrawAgent python backend/manage.py test`
- 当前 Phase 2 后端测试共 `11` 项，全部通过

## 交接说明

- Phase 2 主体代码与测试已落地并完成验证
- 验证通过后即可进入 Phase 3 的 Prompt 资产化与 Agent 节点实现

## 已知事项

- 当前 Phase 2 只建立契约和存储体系，尚未开放正式业务 API
- `legacy/agent1/` 仍保持归档状态，不参与 2.0 运行
- 当前终端默认 `python` 指向 Anaconda 基座环境；后续后端验证与运行应显式使用 `conda run -n DrawAgent ...`
