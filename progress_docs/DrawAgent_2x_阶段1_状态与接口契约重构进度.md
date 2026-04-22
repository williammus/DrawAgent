# DrawAgent 2.x 阶段 1 进度文档

## 本阶段完成内容
- 已完成后端状态与接口契约收口，主链路外部接口已从单 `message` 语义切换为显式 `run` / `resume`。
- 已完成 `GraphState` 的阶段 1 扩展，加入 `source_text_locked`、`artifacts`、`pending_clarification`、`loop_id`、`loop_origin`、澄清计数和双阶段审查计数字段。
- 已完成文本 artifact 返回契约，`/api/artifacts/{session_id}` 现在返回：
  - `logic_artifact`
  - `style_artifact`
  - `plan_review_artifact`
  - `mapper_artifact`
  - `final_review_artifact`
  - `final_prompt_artifact`
- 已完成 SSE 契约升级：
  - `clarification_required` 改为返回 `question`、`reason`、`missing_fields`
  - `review_failed` 增加 `review_phase`
  - 新增 `workflow_warning` 事件类型和前端接收能力
- 已完成前端类型层、API 层和 store 层同步，当前前端可以按新契约消费 `run` / `resume`、新 summary、新 artifacts、新 SSE 字段。

## 外部契约变化
- 聊天接口已变更为：
  - `POST /api/chat/run`
  - `POST /api/chat/resume`
- `run` 只接受 `source_text` 或 `user_feedback` 二选一。
- `resume` 只接受 `user_feedback`。
- `SessionSummary` 已不再返回 `has_payload_*`，改为：
  - `has_source_text`
  - `source_text_locked`
  - `has_logic_artifact`
  - `has_style_artifact`
  - `has_plan_review_artifact`
  - `has_mapper_artifact`
  - `has_final_review_artifact`
  - `has_final_prompt_artifact`
  - `has_bypass_warning`
  - `interrupted`
- 前端当前仍保留附件上传能力，但该能力已经不是聊天主链路的一部分。

## 兼容策略与遗留项
- 为避免在阶段 1 就打断旧 workflow，本阶段保留了旧 `payload_*`、`pending_clarification_question`、`needs_clarification` 等兼容字段。
- 当前 `/api/artifacts/{session_id}` 对旧 `payload_*` 仍有读取层适配，会临时映射为文本 artifact 返回。
- 当前后端 workflow、agents、generation 主链路仍然依赖旧 `payload_*` 运行；这属于阶段 2 之后的改造范围，不属于本阶段未完成。
- 当前前端 Prompt 预览已经改为展示文本 artifact 内容，因此旧 `payload_final` 的中英文分栏展示不再作为接口假设保留。

## 对阶段 2 的交接注意事项
- 阶段 2 开始时，不要再新增任何基于 `ChatMessageRequest`、`/api/chat/message` 或 `has_payload_*` 的新逻辑。
- 阶段 2 的双节点 workflow 重构必须直接复用本阶段已经定下的：
  - `loop_id`
  - `loop_origin`
  - `clarification_rounds_in_loop`
  - `post_plan_review_rounds_in_loop`
  - `post_mapper_review_rounds_in_loop`
  - `pending_clarification`
  - `bypass_warnings`
- `visual_mapper`、`critic`、`summary` 不直接读取 `source_text` 的边界，本阶段只体现在契约和文档上，真正执行链路约束要在阶段 2 和阶段 4 落实。
- `workflow_warning` 已经预留好了事件与前端接收口，阶段 2/4 可以直接接入真实放行逻辑，不需要重新设计事件字段。

## 当前已知风险
- 当前仍是“新契约 + 旧执行骨架并存”状态，兼容字段较多，阶段 2 不及时收敛会继续增加维护成本。
- artifact 读取层的旧 payload 文本映射只是过渡方案，不能被后续阶段反向依赖为正式实现。
- 前端 `vite build` 在当前沙箱环境下会因 `esbuild` 子进程启动权限触发 `EPERM`；已用 `tsc --noEmit` 完成类型验证，但完整 Vite 打包需在权限正常环境再验证一次。
