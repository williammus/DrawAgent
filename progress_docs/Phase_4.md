# Phase 4 开发进度

## 当前状态

已完成。

## 本阶段目标

完成 LangGraph 工作流、澄清中断恢复、Critic 定向回滚、错误熔断，以及内部事件输出能力。

## 已完成内容

- 已补齐 LangGraph 工作流定义与 `WorkflowRunner`
- 已补齐内存 checkpoint store 与 event store
- 已实现 `InputGuard -> Orchestrator -> 并行/单分支 -> Critic -> Summary` 主链
- 已实现 `AskClarification -> WAIT_USER -> resume` 中断恢复
- 已实现基于 `payload_review.error_stage` 的定向回滚
- 已实现 `error_count` 熔断与过期会话的 workflow 清理 hook
- 已补齐 Phase 4 图级测试与存储清理测试

## 验证结果

- 已通过 `python backend/manage.py lint`
- 已通过 `python backend/manage.py test`
- 当前后端测试共 `32` 项，全部通过

## 交接说明

- app lifespan 已挂载 `workflow_checkpoint_store/workflow_event_store/workflow_app/workflow_runner`
- `Critic` 失败现在走结构化审查结果和图路由，不再以异常作为主路径
- `manage.py test` 已固定使用稳定可写的 pytest 临时目录，并关闭 cacheprovider，避免本机 Windows 权限噪音

## 已知事项

- Phase 4 仍未开放正式业务 API 和 SSE 路由，事件目前只保存在内存 event store 中
- 当前仓库里仍可能残留一个历史 `.pytest_tmp` 目录权限异常告警，但不影响当前测试通过
