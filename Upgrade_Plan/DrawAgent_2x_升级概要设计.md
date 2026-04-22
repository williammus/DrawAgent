# DrawAgent 2.x 升级概要设计

## 1. 文档说明

### 1.1 文档目的
本文档用于指导当前 DrawAgent 项目从现有版本升级到“主控原生工具调用 + 单主控节点/单工具节点 + 文本化业务产物 + source_text 首输入驱动”的新架构。

本文档仅作为本轮升级的实现依据。

### 1.2 旧文档边界
- `Archive_Old_Plan/` 下的文档仅为历史归档，不作为本轮升级的实现输入。
- 后续 Codex 或人工实施时，应只参考本文档与当前仓库代码现状，不回退引用旧版概要设计中的工作流、接口或中间产物定义。

### 1.3 本轮升级目标
- 将现有“多业务 graph node + 结构化 JSON artifacts + 附件输入”的方案，升级为“一个主控节点 + 一个工具节点 + 原生 tool calling + 文本化业务产物 + source_text 首输入”的方案。
- 保留现有科研绘图业务链路的核心能力：逻辑梳理、风格配置、视觉映射、审查、最终 Prompt 组装、图片生成。
- 保留原有关键流程约束：`logician` 和 `style_configurator` 并行后先经过一次 `critic`，`visual_mapper` 完成后再经过一次 `critic`，而不是所有业务工具全部完成后才统一审查。

---

## 2. 核心设计结论

### 2.1 总体架构结论
- LangGraph 图中仅保留两个节点：
  - `controller`
  - `tool_executor`
- `controller` 是唯一主控 Agent。
- 其他业务子 Agent 不再作为 graph node 存在，而是注册为工具，由主控通过原生工具调用协议动态调度。

### 2.2 工具分层结论
- 控制工具：
  - `ask_clarification`
- 业务工具：
  - `logician_tool`
  - `style_configurator_tool`
  - `critic_tool`
  - `visual_mapper_tool`
  - `summary_tool`

### 2.3 输入上下文结论
- 只有以下 Agent/工具允许直接输入 `source_text`：
  - `orchestrator`
  - `logician`
  - `style_configurator`
- 以下工具不得直接读取 `source_text`，只能消费上游产物：
  - `visual_mapper`
  - `critic`
  - `summary`

### 2.4 审查链路结论
- `critic` 必须保留两个审查关口：
  1. `logician + style_configurator` 并行完成后，执行 `critic(post_plan)`
  2. `visual_mapper` 完成后，执行 `critic(post_mapper)`
- `summary` 只能在 `critic(post_mapper)` 放行后执行。

### 2.5 产物形态结论
- 业务子工具输出改为自然语言文本，不再强制结构化 JSON schema。
- 仅控制平面保留最小结构化字段，用于工作流编排、计数、回滚和告警。
- `summary` 保留为独立工具，负责最终绘图 Prompt 的自然语言组装；`critic` 不负责最终 Prompt 组装。

### 2.6 澄清与审查上限结论
- 澄清最多两轮，按当前收敛回路计数。
- 审查最多两轮，但按 `critic(post_plan)` 与 `critic(post_mapper)` 两个阶段分别计数。
- 超过上限后不再阻断流程，采用“显式警告放行”。
- 重置点：
  - 每次新的 `run(source_text=...)`
  - 每次新的 `run(user_feedback=...)`
- 不重置：
  - `resume(user_feedback=...)`

---

## 3. 当前版本现状与问题

### 3.1 后端现状
- 当前工作流使用多 graph node 模式，存在独立的：
  - `orchestrator`
  - `ask_clarification`
  - `wait_user`
  - `logician`
  - `style_configurator`
  - `visual_mapper`
  - `critic`
  - `summary`
- 当前业务 Agent 基于结构化 JSON 输出，核心依赖 `backend/app/schemas/artifacts.py` 中的强类型字段。
- 当前 `orchestrator` 主要依靠 prompt 约束模型输出 JSON 决策，而不是原生 tool calling。
- 当前默认 prompt 注册未统一切换到 `v2.md`。

### 3.2 前端现状
- 当前前端仍保留附件上传入口。
- 当前用户输入模式未区分：
  - 首次完整绘图输入 `source_text`
  - 后续补充/澄清输入 `user_feedback`
- 当前底部输入框承担了“初始需求输入 + 澄清回复 + 局部修改”三种职责，交互边界不清晰。

### 3.3 现有方案的主要问题
- 所有业务子 Agent 输出被约束为 JSON，限制了模型思路和表达空间。
- 业务子 Agent 在系统初始化时即被创建和绑定，扩展性较弱。
- 澄清被建模为独立 graph node，而不是主控的控制动作，不符合新架构目标。
- 附件输入路径与新的 `source_text` 首输入方案冲突。

---

## 4. 升级后总体架构

### 4.1 分层架构

#### 前端交互层
- 负责 session 初始化、`source_text` 输入、`user_feedback` 输入、SSE 状态展示、artifact 展示、Prompt 预览和图片生成确认。

#### API 接入层
- 负责会话管理、显式 `run/resume` 请求、SSE 事件推送、artifact 查询、图片生成调用。

#### 编排层
- 基于 LangGraph，仅保留：
  - `controller`
  - `tool_executor`

#### 工具层
- 负责动态实例化和执行各业务工具。

#### 会话状态层
- 仅使用内存和临时目录，不引入数据库。

### 4.2 图结构
- 图入口进入 `controller`
- `controller` 基于当前状态决定：
  - 调用澄清工具
  - 调用一个或多个业务工具
  - 结束当前回路
- 若存在工具调用，则进入 `tool_executor`
- `tool_executor` 执行完后统一回到 `controller`
- 若 `ask_clarification` 触发真实暂停，则进入 interrupt / wait-for-user 状态

---

## 5. 工作流设计

### 5.1 新建绘图任务
标准流程如下：

1. 用户首次输入完整绘图内容，作为 `source_text`
2. `controller` 判断信息是否充分
3. 若信息不足，则触发 `ask_clarification`
4. 若信息充分，则并行调用：
   - `logician_tool`
   - `style_configurator_tool`
5. 两者完成后，执行 `critic_tool(post_plan)`
6. `critic(post_plan)` 放行后，执行 `visual_mapper_tool`
7. `visual_mapper` 完成后，执行 `critic_tool(post_mapper)`
8. `critic(post_mapper)` 放行后，执行 `summary_tool`
9. 前端进入 Prompt 可预览、可确认出图状态
10. 用户点击生成图片后，调用图片生成链路

### 5.2 修改任务

#### 修改逻辑
1. 用户输入 `user_feedback`
2. `controller` 调用 `logician_tool`
3. 若当前缺失风格产物，则补执行 `style_configurator_tool`
4. 执行 `critic_tool(post_plan)`
5. 放行后执行 `visual_mapper_tool`
6. 再执行 `critic_tool(post_mapper)`
7. 放行后执行 `summary_tool`

#### 修改风格
1. 用户输入 `user_feedback`
2. `controller` 调用 `style_configurator_tool`
3. 若当前缺失逻辑产物，则补执行 `logician_tool`
4. 执行 `critic_tool(post_plan)`
5. 放行后执行 `visual_mapper_tool`
6. 再执行 `critic_tool(post_mapper)`
7. 放行后执行 `summary_tool`

#### 仅修改排版/布局
1. 用户输入 `user_feedback`
2. `controller` 直接调用 `visual_mapper_tool`
3. 执行 `critic_tool(post_mapper)`
4. 放行后执行 `summary_tool`

### 5.3 澄清流程
- `ask_clarification` 是控制工具，不是业务工具，也不是 graph node。
- 主控发现以下情况时调用该工具：
  - 缺失关键信息
  - 上下文不足
  - 用户反馈模糊
- 后端将该工具结果映射为：
  - interrupt
  - wait_for_user
  - SSE `clarification_required`
- 用户补充后，通过 `resume(user_feedback=...)` 恢复当前回路。

### 5.4 两轮上限策略

#### 澄清上限
- 当前回路内最多两轮真正的澄清暂停。
- 第三次仍想澄清时，不再进入 interrupt。
- 系统记录 warning，并要求主控在已有信息上继续决策。

#### 审查上限
- `critic(post_plan)` 在当前回路内最多两轮审查失败回退。
- `critic(post_mapper)` 在当前回路内最多两轮审查失败回退。
- 各阶段第三次仍未通过时，对应阶段不再阻断流程。
- 系统记录 warning，并显式提示“带风险放行”。

---

## 6. 后端概要设计

### 6.1 LLM 调用方式

#### 主控调用
- `orchestrator` 使用原生 tool calling。
- 不再依赖 prompt 强制模型输出 JSON。
- 模型必须按工具调用协议返回结构化调用信息。

#### 业务工具调用
- `logician`
- `style_configurator`
- `critic`
- `visual_mapper`
- `summary`

以上工具统一采用自然语言文本输出。

### 6.2 动态工具注册
- 各业务工具不在应用启动时全部实例化。
- 系统维护工具注册表，仅注册工具定义和构造方法。
- 当 `tool_executor` 收到指定工具调用时，再动态创建对应执行器并运行。

### 6.3 GraphState 重构
- 删除旧的强结构化业务字段依赖。
- 新状态应至少包含：
  - `session_id`
  - `stage`
  - `intent`
  - `source_text`
  - `source_text_locked`
  - `user_feedback`
  - `artifacts`
  - `pending_clarification`
  - `loop_id`
  - `loop_origin`
  - `clarification_rounds_in_loop`
  - `post_plan_review_rounds_in_loop`
  - `post_mapper_review_rounds_in_loop`
  - `interrupted`
  - `bypass_warnings`
  - `generated_image_meta`
  - `last_error`

### 6.4 Artifact 设计
- Artifact 改为文本化存储，不再要求逻辑/风格/映射必须符合固定字段 schema。
- 建议会话内保留以下 artifact 槽位：
  - `logic_artifact`
  - `style_artifact`
  - `plan_review_artifact`
  - `mapper_artifact`
  - `final_review_artifact`
  - `final_prompt_artifact`

每个 artifact 至少包含：
- `tool_name`
- `content`
- `prompt_version`
- `updated_at`

### 6.5 双阶段 Critic 设计

#### critic(post_plan)
输入：
- `logic_artifact`
- `style_artifact`

职责：
- 检查逻辑与风格是否冲突
- 检查是否已经具备进入 `visual_mapper` 的条件
- 给出失败原因和回退建议

#### critic(post_mapper)
输入：
- `logic_artifact`
- `style_artifact`
- `mapper_artifact`

职责：
- 检查映射结果与上游产物是否一致
- 检查排版、表达、可生成性风险
- 给出失败原因和回退建议

### 6.6 Prompt 版本切换
- 所有 Agent 默认 prompt 均切换到各自目录下的 `v2.md`
- 需要同步补齐和微调各工具输入上下文
- 必须统一模板变量规范，避免后续渲染器与模板语法不匹配

### 6.7 Prompt 输入边界

#### orchestrator
输入：
- `source_text`
- `user_feedback`
- 各 artifact 摘要
- 当前回路计数
- warning 信息
- 可用工具列表

#### logician
输入：
- `source_text`
- `user_feedback`
- 旧版 `logic_artifact` 摘要
- 必要的状态摘要

#### style_configurator
输入：
- `source_text`
- `user_feedback`
- 旧版 `style_artifact` 摘要
- 必要的状态摘要

#### visual_mapper
输入：
- `logic_artifact`
- `style_artifact`
- `user_feedback`

不得输入：
- `source_text`

#### critic
输入：
- 对应阶段所需 artifact
- 审查轮次
- warning 信息

不得输入：
- `source_text`

#### summary
输入：
- `logic_artifact`
- `style_artifact`
- `mapper_artifact`
- `final_review_artifact`
- warning 信息

不得输入：
- `source_text`

### 6.8 API 调整
- 废弃“单一 message 接口自动猜测语义”的方式。
- 新聊天接口应拆分为：
  - `POST /api/chat/run`
  - `POST /api/chat/resume`

#### run
用于启动新回路。

请求体：
- `session_id`
- `source_text` 或 `user_feedback`

#### resume
用于恢复当前已中断回路。

请求体：
- `session_id`
- `user_feedback`

### 6.9 SSE 事件设计
保留并调整以下事件：
- `stage_started`
- `stage_completed`
- `clarification_required`
- `review_failed`
- `prompt_ready`
- `image_generated`
- `error`
- `workflow_warning`

其中 `workflow_warning` 用于显式提示：
- `clarification_limit_reached`
- `review_limit_reached`

---

## 7. 前端概要设计

### 7.1 输入模式重构
- 去除附件上传入口。
- session 首次创建后，页面出现独立的 `source_text` 输入框。
- 提示文案固定为：
  - `请在此处输入用于绘图的完整内容(论文/代码)`
- 用户首次提交后：
  - 将内容写入全局状态 `source_text`
  - 调用后端 `run(source_text=...)`
  - 输入框变为只读

### 7.2 聊天输入框职责调整
- 底部中心输入框不再用于首次完整绘图输入。
- 仅用于：
  - 澄清回复
  - 局部修改
  - 补充细节
- 在 `source_text` 未提交前，底部输入框必须禁用。
- 该输入对应全局状态中的 `user_feedback`。

### 7.3 页面布局建议
- `source_text` 输入框应放置在当前工作区中最显著、最适合承载长文本的位置。
- 推荐放在：
  - Workspace 标题下方
  - 消息流上方
- 这样可以体现其“项目基础输入”的角色，而不是普通聊天消息。

### 7.4 状态管理调整
前端全局状态需新增或重构：
- `sourceText`
- `sourceTextLocked`
- `workflowWarnings`
- `clarificationQuestion`
- `artifacts`
- `workspaceStatus`

需移除：
- `uploadedFiles`
- `selectedAttachmentIds`
- 附件上传相关状态与动作

### 7.5 Artifact 展示调整
- Artifact 面板改为文本展示模式。
- 不再假设逻辑、风格、映射、审查、最终 Prompt 为固定 JSON 结构。
- `plan_review_artifact` 和 `final_review_artifact` 应分别展示，便于用户理解两个审查关口。

### 7.6 Warning 交互
- 达到澄清或审查上限后，页面必须显式展示 warning。
- warning 不阻止继续流程，但必须对用户可见。
- 若最终 Prompt 是在 warning 条件下放行，Prompt 预览卡片应标记“带风险放行”。

---

## 8. 接口与数据契约调整

### 8.1 SessionSummary
建议新增字段：
- `has_source_text`
- `source_text_locked`
- `has_bypass_warning`

### 8.2 ArtifactResponse
改为文本 artifact 返回：
- `logic_artifact`
- `style_artifact`
- `plan_review_artifact`
- `mapper_artifact`
- `final_review_artifact`
- `final_prompt_artifact`

### 8.3 Generate 接口
- 图片生成仍由用户在 Prompt 预览确认后触发。
- 图片生成依赖 `final_prompt_artifact` 中的最终英文 Prompt。

---

## 9. 实现顺序建议

### 第一阶段：设计与契约收口
- 完成本文档
- 明确新 `GraphState`
- 明确 `run/resume` API
- 明确双阶段 `critic` 契约
- 明确各工具的 prompt 输入边界

### 第二阶段：后端控制平面重构
- 重构图为 `controller + tool_executor`
- 接入主控原生 tool calling
- 实现动态工具注册与执行
- 实现回路计数与 warning 策略

### 第三阶段：业务工具文本化
- 取消业务工具 JSON artifact 输出约束
- 将业务子工具切换为自然语言文本产物
- 切换默认 prompt 到 `v2.md`
- 补齐各工具输入上下文

### 第四阶段：前端交互改造
- 新增 `source_text` 独立输入框
- 锁定首次输入后再开放底部聊天框
- 去除附件上传入口
- 改造 artifact 和 warning 展示

### 第五阶段：测试与清理
- 重写后端 workflow 测试
- 重写前端交互测试
- 删除附件链路与旧结构化 artifact 假设
- 清理旧 prompt 注册与无效字段

---

## 10. 验收标准

### 10.1 后端验收
- 图中仅存在 `controller` 和 `tool_executor` 两个节点
- 主控通过原生工具调用协议调度工具
- `logician` 与 `style_configurator` 完成后先经过 `critic(post_plan)`
- `visual_mapper` 完成后再经过 `critic(post_mapper)`
- `visual_mapper`、`critic`、`summary` 不直接输入 `source_text`
- `critic(post_plan)` 与 `critic(post_mapper)` 的两轮上限分阶段分别计数
- 超过澄清/审查上限后能显式 warning 并继续流程

### 10.2 前端验收
- 首次进入页面时出现独立 `source_text` 输入框
- `source_text` 提交后变为只读
- 在 `source_text` 提交前，底部聊天输入框不可用
- 无附件上传入口
- Artifact 面板能展示文本化逻辑/风格/两阶段审查/最终 Prompt

### 10.3 业务验收
- 新建绘图任务可以完成：
  - `source_text -> logician/style -> critic(post_plan) -> mapper -> critic(post_mapper) -> summary`
- 修改任务可以按需局部回滚
- warning 放行时用户可感知

---

## 11. 风险与注意事项
- 当前仓库中已有部分 `v2.md`，但其内容仍需补齐和微调，不能直接视为可用实现。
- 当前 prompt 模板语法需要统一，避免渲染器与模板变量占位符不匹配。
- 从结构化 JSON artifact 切换到文本 artifact 后，artifact API、前端展示、测试用例都需要同步重写，不能只改 Agent 层。
- 附件输入链路与 `source_text` 首输入模式是冲突关系，后续实施时必须彻底收敛到单一路径。

---

## 12. 默认假设
- 本轮升级保留 `summary` 工具，不将其职责合并进 `critic`。
- `critic(post_plan)` 与 `critic(post_mapper)` 各自拥有“当前回路内最多两轮”的独立上限。
- `source_text` 是科研绘图的完整基础输入，后续修改均通过 `user_feedback` 驱动。
- 本文档只定义概要设计，不包含具体代码实现细节、补丁或迁移脚本。
