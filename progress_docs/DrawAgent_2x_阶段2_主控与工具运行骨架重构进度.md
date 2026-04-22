# DrawAgent 2.x 阶段 2 进度文档

## 本阶段完成内容
- 后端工作流主链路已从旧多节点 graph 收敛为双节点结构：
  - `controller`
  - `tool_executor`
- 主控决策已切换为原生 tool calling 主链路，不再依赖 `orchestrator_decision` 作为 graph 路由依据。
- 已建立动态工具注册与按需构造机制，运行时不再在启动阶段预创建全部业务执行器实例。
- `ask_clarification` 已落为 control tool，澄清暂停不再依赖独立 graph node。
- `tool_executor` 已具备顺序执行多工具调用、记录工具执行结果、处理 review phase 计数、写入 warning 和回到主控的最小闭环。
- `critic(post_plan)` 与 `critic(post_mapper)` 的分阶段计数字段已经接入真实控制逻辑，不再共用同一 review 计数。

## 运行骨架变化
- 新主链路已变为“主控返回工具调用 -> 工具执行器消费 -> 回到主控继续决策”的回路。
- 主控与工具层之间的协议已经固定为工具名 + 参数对象，不再走 `selected_nodes` 这类旧路由字段。
- 当前 `controller_tool_calls` 和 `last_tool_results` 已进入 `GraphState`，用于承载当前轮调度和上一轮工具执行摘要。
- 澄清流程已改为：
  - 工具执行器先写入结构化澄清动作
  - 控制器在下一次进入时负责触发真实 interrupt / SSE
  - `resume(user_feedback=...)` 恢复后由主控继续决策

## 兼容策略与遗留项
- 为避免阶段 2 一次性打断全部业务工具，`StructuredAgentExecutor` 和 `payload_*` 仍然保留，业务工具内部暂时仍可复用旧结构化输出。
- `orchestrator_decision`、`pending_clarification_question`、`rollback_target` 仍保留在 state 中作为兼容字段，但已经不再参与新 workflow 的主控制逻辑。
- `critic` 与 `summary` 仍通过旧 `payload_review` / `payload_final` 兼容运行；真正的文本化业务产物改造仍属于后续阶段。
- `logician` 的 prompt 注册路径已修正到现有文件，避免阶段 2 运行骨架因为缺失 prompt 文件而中断。

## 对阶段 3 的交接注意事项
- 阶段 3 的 Prompt 微调应直接围绕当前已经固定下来的工具协议进行，不要再变更：
  - 工具名
  - 工具参数名
  - `controller + tool_executor` 双节点结构
  - `ask_clarification` 的 control tool 语义
- Prompt 微调时要重点补齐主控上下文，使主控能够稳定理解：
  - `last_tool_results`
  - 双阶段 critic 的 `review_phase`
  - warning 放行信息
- 阶段 3 不应回退到 JSON 路由决策，也不应重新引入独立的澄清业务节点。

## 当前已知风险
- 目前仍处于“新控制平面 + 旧业务产物兼容执行”的过渡状态，后续阶段若不继续收敛，`payload_*` 与文本 artifact 会长期并存。
- 当前工具执行器按顺序执行同轮多个 tool call，没有实现真正并发；这是阶段 2 的有意简化，不属于遗漏。
- 由于 Prompt 还未进入阶段 3 微调，主控对新工具协议的理解目前更多依赖工具 schema 和运行骨架，真实效果仍需要后续 Prompt 收口来稳定。
