# DrawAgent 2.x 分阶段施工计划

## 1. 文档说明

### 1.1 文档目的
本文档基于 [DrawAgent_2x_升级概要设计.md](/D:/Projects/keyanhuitu/DrawAgent/Upgrade_Plan/DrawAgent_2x_升级概要设计.md)，给出一份可执行、分阶段、可验收的施工计划，用于指导后续代码升级实施。

本文档关注：
- 每一阶段的目标、范围、主要改动点
- 实施顺序与依赖关系
- 每阶段完成标准
- 需要人工确认的停点

### 1.2 旧文档边界
- `Archive_Old_Plan/` 仅为历史归档，不作为本轮施工依据。
- 后续实施只以本施工计划和升级概要设计为准。

### 1.3 关键施工约束
- 本轮升级必须保持总体架构为：
  - 一个 `controller` 节点
  - 一个 `tool_executor` 节点
- `ask_clarification` 是 control tool，不是业务 graph node。
- 只有 `orchestrator`、`logician`、`style_configurator` 直接输入 `source_text`。
- `visual_mapper`、`summary` 不得直接输入 `source_text`。
- `critic` 的输入按审查对象动态变化，使用 `{type, pre_data, data}`，其中审查 `logician` 时 `pre_data` 可以是 `source_text`。
- `critic` 必须保留两个审查关口：
  - `critic(post_plan)`
  - `critic(post_mapper)`
- `critic(post_plan)` 与 `critic(post_mapper)` 的两轮上限必须分阶段分别计数。
- 业务子工具产物改为自然语言文本，不再继续沿用强 JSON artifact 作为业务输出约束。

---

## 2. 总体实施策略

### 2.1 施工原则
- 先收口契约，再改控制平面，再改 Prompt，再进入大规模实现。
- Prompt 改造必须单独成阶段，且在该阶段完成后暂停，等待你确认，再继续后续代码施工。
- 优先改“控制平面”和“状态/接口契约”，再改“业务内容与前端交互”，避免返工。
- 旧能力删除采用“先脱主链路、再删除死路径”的方式，降低连锁风险。

### 2.2 阶段顺序 rationale
建议按以下顺序施工：

1. 阶段 0：施工前基线收口
2. 阶段 1：状态与接口契约重构
3. 阶段 2：主控与工具运行骨架重构
4. 阶段 3：Prompt 微调与确认闸口
5. 阶段 4：业务工具文本化与双阶段 Critic 落地
6. 阶段 5：前端 `source_text-first` 交互改造
7. 阶段 6：联调、测试、清理与验收

这样安排的原因：
- 阶段 1 和阶段 2 先把“系统怎么跑”定下来。
- Prompt 微调放在阶段 3，此时上下文边界和工具契约已经明确，能做到“只改必要处”。
- Prompt 经你确认后，再进入后续大规模代码改动，可以避免在错误 Prompt 基础上继续堆实现。

---

## 3. 分阶段施工计划

## 阶段 0：施工前基线收口

### 3.0 目标
- 固化本轮施工依据，避免后续实现时混用旧方案。
- 明确受影响模块和非目标范围。

### 3.0 范围
- 仅更新计划与实施清单，不改业务代码。

### 3.0 主要任务
- 确认以下文档为唯一实施依据：
  - `Upgrade_Plan/DrawAgent_2x_升级概要设计.md`
  - `Upgrade_Plan/DrawAgent_2x_分阶段施工计划.md`
- 明确本轮受影响目录：
  - `backend/app/graph/`
  - `backend/app/agents/`
  - `backend/app/llm/`
  - `backend/app/prompts/`
  - `backend/app/api/routes/`
  - `backend/app/services/`
  - `backend/app/schemas/`
  - `frontend/src/api/`
  - `frontend/src/store/`
  - `frontend/src/components/`
  - `frontend/src/App.tsx`
- 明确本轮废弃主路径：
  - 附件上传驱动输入
  - 业务 JSON artifact 输出主链路
  - 多 graph node 业务编排

### 3.0 交付物
- 本施工计划文档

### 3.0 完成标准
- 所有后续实施任务均能映射到具体阶段，不再依赖旧计划文件解释。

---

## 阶段 1：状态与接口契约重构

### 3.1 目标
- 先把“系统状态怎么表示、前后端怎么交互、工具怎么编排”的契约固定下来。
- 为后续主控原生 tool calling 和前端交互改造提供稳定边界。

### 3.1 范围
- 后端状态模型
- API 输入输出契约
- SSE 事件契约
- 文本 artifact 契约

### 3.1 主要改动点

#### 3.1.1 GraphState 收口
目标文件：
- `backend/app/graph/state.py`

任务：
- 从旧的强结构化 payload 形态，收敛到“文本 artifact + 控制状态”。
- 明确保留字段：
  - `source_text`
  - `source_text_locked`
  - `user_feedback`
  - `loop_id`
  - `loop_origin`
  - `clarification_rounds_in_loop`
  - `post_plan_review_rounds_in_loop`
  - `post_mapper_review_rounds_in_loop`
  - `pending_clarification`
  - `interrupted`
  - `bypass_warnings`
  - `artifacts`

#### 3.1.2 Artifact 契约收口
目标文件：
- `backend/app/schemas/artifacts.py`
- `backend/app/api/routes/artifacts.py`

任务：
- 将业务 artifact 的主输出契约切换为文本形态。
- 明确 artifact 槽位：
  - `logic_artifact`
  - `style_artifact`
  - `plan_review_artifact`
  - `mapper_artifact`
  - `final_review_artifact`
  - `final_prompt_artifact`
- 控制平面允许最小结构字段，但不再将业务正文约束为 JSON schema。

#### 3.1.3 API 语义拆分
目标文件：
- `backend/app/api/routes/chat.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/session_service.py`
- `frontend/src/api/chat.ts`

任务：
- 将单一 message 入口拆分为：
  - `run(source_text=...)`
  - `run(user_feedback=...)`
  - `resume(user_feedback=...)`
- 固化计数语义：
  - 新 `run(...)` 开启新回路并重置本回路计数
  - `resume(...)` 仅恢复当前回路，不重置计数

#### 3.1.4 SSE 契约收口
目标文件：
- `backend/app/api/routes/session.py`
- `backend/app/services/session_service.py`
- `frontend/src/store/useAppStore.ts`

任务：
- 明确保留事件：
  - `clarification_required`
  - `review_failed`
  - `prompt_ready`
  - `workflow_warning`
- 明确 `workflow_warning` 至少覆盖：
  - `clarification_limit_reached`
  - `review_limit_reached`

### 3.1 风险点
- 若阶段 1 契约定义不够清晰，后续 Prompt 和前端都容易返工。
- 若 `review` 计数仍写成统一字段，后续双阶段 Critic 会出现实现偏差。

### 3.1 交付物
- 状态字段清单
- API 请求/响应草案
- SSE 事件草案
- Artifact 文本契约草案

### 3.1 完成标准
- 能明确回答以下问题且无歧义：
  - 哪些字段是会话级，哪些字段是当前回路级
  - 什么情况下走 `run`，什么情况下走 `resume`
  - `critic(post_plan)` 和 `critic(post_mapper)` 的计数如何分别重置和累加

---

## 阶段 2：主控与工具运行骨架重构

### 3.2 目标
- 将工作流从“多业务 graph node”重构为“主控 + 工具执行器”双节点架构。
- 建立原生 tool calling 主链路和动态工具执行骨架。

### 3.2 范围
- LangGraph workflow
- controller 执行器
- 工具注册与动态实例化
- control tool 执行链路

### 3.2 主要改动点

#### 3.2.1 Workflow 双节点化
目标文件：
- `backend/app/graph/workflow.py`

任务：
- 删除旧的业务节点编排主路径。
- 收敛为：
  - `controller`
  - `tool_executor`
- 统一工具执行完成后回到 `controller`。

#### 3.2.2 主控原生 tool calling
目标文件：
- `backend/app/llm/client.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/agents/base.py`

任务：
- 新增主控专用原生 tool calling 调用方式。
- 不再依赖 prompt 约束模型输出 JSON 决策。
- 由模型返回标准工具调用结构，再由后端执行。

#### 3.2.3 动态工具注册
目标文件：
- `backend/app/agents/factory.py`
- `backend/app/agents/__init__.py`

任务：
- 将业务子 Agent 从“启动即实例化”改为“按需动态创建”。
- 统一注册：
  - 工具名
  - 输入 schema
  - 执行器构造方法

#### 3.2.4 Control Tool 落地
目标文件：
- `backend/app/agents/orchestrator.py`
- `backend/app/services/chat_service.py`

任务：
- 将 `ask_clarification` 定位为 control tool。
- 后端负责把该工具调用映射到：
  - interrupt
  - wait_for_user
  - SSE
- 不再为澄清保留业务 graph node。

### 3.2 交付物
- 新 workflow 骨架
- controller/tool_executor 主链路
- 动态工具注册骨架
- clarification control tool 映射链路

### 3.2 完成标准
- 后端已经具备“主控返回工具调用 -> 工具执行 -> 回主控”的最小可运行链路。
- 即使业务工具仍暂时保留旧内容，也不再依赖旧多节点编排模式。

---

## 阶段 3：Prompt 微调与确认闸口

### 3.3 目标
- 仅对各 Agent 的 `v2.md` 做必要微调，使其适配新架构和新输入边界。
- 在尽最大程度保留原版 `v2.md` 描述的前提下，完成 Prompt 收口。
- 本阶段完成后必须暂停，等待你确认，再继续后续施工。

### 3.3 范围
- `backend/app/prompts/registry.py`
- `backend/app/prompts/renderer.py`
- `backend/app/prompts/orchestrator/v2.md`
- `backend/app/prompts/logician/v2.md`
- `backend/app/prompts/style_configurator/v2.md`
- `backend/app/prompts/critic/v2.md`
- `backend/app/prompts/visual_mapper/v2.md`
- `backend/app/prompts/summary/v2.md`

### 3.3 调整原则
- 不重写整份 Prompt，但如果当前 `v2.md` 已偏离原始版本过多，则允许删除后基于原始基线重新写新的 `v2.md`。
- 只修改与以下事项直接相关的必要段落：
  - 工具调用方式
  - 输入上下文边界
  - 输出形态从 JSON 转为自然语言
  - 双阶段 Critic 的阶段职责
  - `summary` 的上游依赖
- `orchestrator`、`logician`、`style_configurator`、`visual_mapper`、`summary` 的正式 `v2.md` 必须以各自 `v2-informal.md` 为基线做最小改动。
- `critic` 的正式 `v2.md` 必须以 `backend/app/prompts/critic/v2-new.md` 为基线做最小改动。
- 保留各基线 prompt 中原有业务描述、风格要求、语气要求、产出目标的主体内容。
- 若某一处原文不影响新架构，就不改。

### 3.3 主要改动点

#### 3.3.1 Prompt 默认版本切换
任务：
- 确保默认注册版本切换到 `v2.md`。
- 清除默认路径上对旧 JSON 版本的依赖。

#### 3.3.2 orchestrator/v2.md 微调
任务：
- 强化其“主控 + 原生 tool calling”职责。
- 明确可调用工具及其时机。
- 保留 `source_text`、`user_feedback`、artifact 摘要、warning、计数等上下文。

#### 3.3.3 logician/style_configurator/v2.md 微调
任务：
- 明确二者允许读取 `source_text`。
- 明确输出为自然语言 artifact，而不是 JSON。
- 保持现有业务产出风格，只改必要的输入/输出约束描述。

#### 3.3.4 critic/v2.md 微调
任务：
- 支持：
  - `post_plan`
  - `post_mapper`
- 明确两个阶段的输入差异和判断目标。
- 改为按审查对象输入：
  - `type`
  - `pre_data`
  - `data`
- 明确输出包括：
  - 自然语言审查意见
  - 最小控制字段

#### 3.3.5 visual_mapper/summary/v2.md 微调
任务：
- 明确二者不读取 `source_text`。
- `visual_mapper` 仅消费上游 logic/style 及必要反馈。
- `summary` 仅消费上游 artifacts 和 warning 信息，组装最终 Prompt。

### 3.3 人工确认闸口
- 本阶段完成后必须暂停。
- 需要你确认以下内容后，才进入阶段 4：
  - 各 `v2.md` 的修改范围是否足够克制
  - 是否确实保留了原版描述主体
  - 是否接受新的输入边界与输出约束

### 3.3 交付物
- 微调后的各 Agent `v2.md`
- Prompt 变更说明
- “原文保留 / 新增修改”对照清单

### 3.3 完成标准
- 所有 Prompt 已满足升级概要设计中的上下文边界。
- Prompt 修改是最小必要集，而不是重写。
- 你完成确认前，不进入下一阶段。

---

## 阶段 4：业务工具文本化与双阶段 Critic 落地

### 3.4 目标
- 让业务工具真正脱离 JSON artifact 主链路，改为自然语言输出。
- 将双阶段 Critic 落到运行逻辑里。

### 3.4 范围
- `backend/app/agents/*.py`
- `backend/app/schemas/artifacts.py`
- `backend/app/services/chat_service.py`
- `backend/app/graph/workflow.py`

### 3.4 主要改动点

#### 3.4.1 各业务工具文本化
目标文件：
- `backend/app/agents/logician.py`
- `backend/app/agents/style_configurator.py`
- `backend/app/agents/visual_mapper.py`
- `backend/app/agents/critic.py`
- `backend/app/agents/summary.py`

任务：
- 统一改为自然语言 artifact 输出。
- 去除对旧强结构化 artifact schema 的核心依赖。
- 不强制各 artifact 采用统一正文格式。
- 如需附加说明或控制信息，统一走旁路 metadata。

#### 3.4.2 双阶段 Critic 执行链路
任务：
- 在 workflow/controller 决策中保留：
  - `logician + style_configurator -> critic(post_plan)`
  - `visual_mapper -> critic(post_mapper)`
- 两阶段计数分别累加、分别限流、分别放行。
- `critic(post_plan)` 需要在同一 gate 内分别审查：
  - `type=logician, pre_data=source_text, data=logic_artifact`
  - `type=style_configurator, pre_data={parsed_discipline, parsed_target_venue, parsed_target_venue_type, parsed_special_requirements}, data=style_artifact`
- `critic(post_mapper)` 需要审查：
  - `type=visual_mapper, pre_data={logic_artifact, style_artifact}, data=mapper_artifact`
- `post_plan_review_rounds_in_loop` 按 gate 计数，不按 gate 内部的两个 critic 子调用分别计数。

#### 3.4.3 Warning 放行机制
任务：
- 达到澄清或审查上限后，写入 warning 并继续流程。
- 对 `critic(post_plan)` 和 `critic(post_mapper)` 分别支持“超限放行”。

#### 3.4.4 主控解析字段落地
任务：
- 在 `GraphState` 中新增并维护：
  - `parsed_discipline`
  - `parsed_target_venue`
  - `parsed_target_venue_type`
  - `parsed_special_requirements`
- 解析并填充这些字段的工作由主控 agent 完成。
- 若 `parsed_discipline`、`parsed_target_venue`、`parsed_target_venue_type` 任一为空或 `unknown`，主控必须优先调用澄清工具。
- `parsed_special_requirements` 允许后续反馈追加；当用户明确表达替换语义时，以最新反馈覆盖。

### 3.4 交付物
- 文本 artifact 主链路
- 双阶段 Critic 执行逻辑
- warning 放行逻辑

### 3.4 完成标准
- 系统能够在不依赖业务 JSON artifact 的前提下走完整后端链路。
- 双阶段 Critic 的顺序、输入、计数、放行都符合概要设计。

---

## 阶段 5：前端 `source_text-first` 交互改造

### 3.5 目标
- 前端输入模型从“统一输入 + 附件入口”改为“先 `source_text`，后 `user_feedback`”。
- 去除附件上传入口，并适配新的中断恢复与 warning 展示。

### 3.5 范围
- `frontend/src/App.tsx`
- `frontend/src/api/chat.ts`
- `frontend/src/store/useAppStore.ts`
- `frontend/src/components/chat/Composer.tsx`
- `frontend/src/components/chat/AttachmentTray.tsx`
- `frontend/src/components/chat/ClarificationCard.tsx`
- `frontend/src/components/chat/ReviewRollbackCard.tsx`
- `frontend/src/components/artifact/ArtifactDrawer.tsx`

### 3.5 主要改动点

#### 3.5.1 source_text 独立输入框
任务：
- 新增首屏独立大文本输入区。
- 提示文案固定为：
  - `请在此处输入用于绘图的完整内容(论文/代码)`
- 提交后写入全局状态并锁定只读。

#### 3.5.2 底部输入框职责切换
任务：
- 底部输入框仅用于：
  - 澄清回复
  - 局部修改
  - 补充细节
- `source_text` 未提交前必须禁用。

#### 3.5.3 API 调用语义切换
任务：
- 首次提交走 `run(source_text=...)`
- 后续主动修改走 `run(user_feedback=...)`
- 澄清恢复走 `resume(user_feedback=...)`

#### 3.5.4 Artifact / warning 展示适配
任务：
- Artifact 面板切换为文本展示。
- 显示：
  - `plan_review_artifact`
  - `final_review_artifact`
- warning 能在消息区或顶部区域显式可见。

#### 3.5.5 附件入口下线
任务：
- 前端去除上传入口和附件托盘。
- 不再允许用户通过附件参与主流程。

### 3.5 交付物
- 新输入交互
- 新 API 调用逻辑
- 文本 artifact 展示
- warning 可视化

### 3.5 完成标准
- 用户首次进入必须先提交 `source_text`。
- `source_text` 提交后不可编辑。
- 底部聊天框不会再承担首次完整输入职责。

---

## 阶段 6：联调、测试、清理与验收

### 3.6 目标
- 对新链路做完整回归，删除旧主路径残留，形成可验收版本。

### 3.6 范围
- 后端测试
- 前端测试
- 旧链路清理
- 验收脚本与手工走查

### 3.6 主要改动点

#### 3.6.1 后端测试补齐
目标文件：
- `backend/tests/`

任务：
- 覆盖：
  - `run(source_text=...)`
  - `run(user_feedback=...)`
  - `resume(user_feedback=...)`
  - `critic(post_plan)` 两轮计数
  - `critic(post_mapper)` 两轮计数
  - 澄清两轮上限
  - warning 放行

#### 3.6.2 前端测试补齐
目标文件：
- `frontend/src/**/*.test.ts*`

任务：
- 覆盖：
  - 首次 `source_text` 输入与锁定
  - 底部输入框禁用/解禁
  - clarification resume
  - warning 展示
  - artifact 文本展示

#### 3.6.3 旧链路清理
任务：
- 清理旧附件主路径
- 清理旧结构化 artifact 主链路依赖
- 清理旧多节点 workflow 的残留入口
- 清理未再使用的 prompt 注册和无效字段

#### 3.6.4 联调验收
任务：
- 按业务场景执行端到端验证：
  - 新建绘图任务
  - 修改逻辑任务
  - 修改风格任务
  - 仅改排版任务
  - 澄清超限放行
  - 两阶段 Critic 各自超限放行

### 3.6 交付物
- 可回归测试集
- 清理后的主链路
- 最终验收记录

### 3.6 完成标准
- 新旧链路边界清楚，主流程只走新架构。
- 关键场景测试通过。
- 残留死路径降到可接受范围。

---

## 4. 阶段间依赖关系

### 4.1 强依赖
- 阶段 2 依赖阶段 1 的状态与接口契约收口。
- 阶段 3 依赖阶段 1 和阶段 2，原因是 Prompt 微调必须建立在已确认的工具契约和上下文边界之上。
- 阶段 4 必须等待阶段 3 经你确认后再开始。
- 阶段 5 依赖阶段 1 的 API 契约和阶段 4 的 artifact 形态稳定。
- 阶段 6 依赖前述所有阶段完成。

### 4.2 人工确认停点
- 唯一强制人工确认停点设在阶段 3 结束后。
- 未获得你的确认，不进入阶段 4。

---

## 5. 推荐实施节奏

### 5.1 推荐提交粒度
- 每一阶段尽量形成单独提交或一组紧密相关提交。
- Prompt 微调阶段建议单独提交，便于你审阅差异。

### 5.2 推荐施工顺序
建议按以下粒度推进：

1. 先做阶段 1，输出契约草案并自检
2. 再做阶段 2，打通最小后端运行骨架
3. 再做阶段 3，微调 Prompt 并停下等你确认
4. 你确认后，再做阶段 4 到阶段 6

### 5.3 不建议的做法
- 不建议一开始就同时改 workflow、Prompt、前端和测试。
- 不建议先重写 Prompt 再去定义上下文边界。
- 不建议在 Prompt 未确认前大规模实现业务工具逻辑。

---

## 6. 风险控制

### 6.1 Prompt 风险
- 风险：
  - 对 `v2.md` 改动过大，丢失原版业务描述与经验约束。
- 控制策略：
  - 只做最小必要修改
  - 输出对照清单
  - 阶段 3 后人工确认

### 6.2 双阶段 Critic 风险
- 风险：
  - 实现时误写成统一审查计数或错误审查顺序。
- 控制策略：
  - 阶段 1 明确双计数字段
  - 阶段 4 明确分阶段放行逻辑
  - 阶段 6 补针对性测试

### 6.3 前后端语义漂移风险
- 风险：
  - 前端误把普通反馈走成 `resume`
  - 后端误把恢复操作当成新回路
- 控制策略：
  - 阶段 1 固化契约
  - 阶段 5 严格区分提交入口
  - 阶段 6 做端到端验证

### 6.4 旧链路残留风险
- 风险：
  - 表面上切了新架构，实际上部分链路仍偷偷依赖附件或 JSON artifact。
- 控制策略：
  - 阶段 6 统一清理
  - 测试中强制覆盖无附件路径和文本 artifact 路径

---

## 7. 最终验收口径

满足以下条件，可视为施工完成：
- 图结构收敛为 `controller + tool_executor`
- 主控使用原生 tool calling
- `ask_clarification` 仅作为 control tool 存在
- `source_text` 输入边界符合设计
- `critic(post_plan)` 与 `critic(post_mapper)` 顺序正确且各自独立计数
- 业务产物改为自然语言文本
- 前端去除附件入口并切换为 `source_text-first`
- Prompt 已切到 `v2.md` 且修改范围经你确认
- 核心场景测试通过并完成联调验收

---

## 8. 本阶段结论
- 本文档是后续升级实施的执行计划，不直接替代概要设计。
- 后续实际施工时，应严格按阶段推进。
- Prompt 微调阶段必须单独完成，并在你确认后才能进入后续代码改造阶段。
