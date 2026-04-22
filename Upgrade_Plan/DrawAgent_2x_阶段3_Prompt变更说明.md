# DrawAgent 2.x 阶段 3 Prompt 变更说明

## 文档目的
本说明用于配合阶段 3 的 Prompt 微调结果，帮助审阅者快速理解“保留了什么”“只改了什么”，避免把阶段 3 误解为阶段 4 的业务文本化实施。

## 总体原则
- 默认 Prompt 入口统一切换到各 Agent 的 `v2.md`
- 模板变量统一使用 `[[variable_name]]`
- 尽量保留各 `v2.md` 原有角色设定、业务语气和产出目标
- 只修改与新架构直接相关的必要部分：
  - 主控原生 tool calling
  - 输入上下文边界
  - 双阶段 Critic 职责
  - Summary 的上游依赖
- 当前业务执行器仍是结构化 schema 链路，因此阶段 3 只做 Prompt 微调，不在本阶段提前落地“纯自然语言 artifact 输出”

## 各 Prompt 的保留与修改

### orchestrator/v2.md
- 保留：
  - “主控官 / 前台项目经理 / 编排者”的核心人设
  - 先思考、再编排、不要自己写绘图细节的边界
  - 澄清优先的控制理念
- 必要修改：
  - 从“输出 JSON 决策”改为“原生 tool calling 调度”
  - 明确 `ask_clarification` 是 control tool
  - 将业务编排顺序改为：
    - `logician_tool + style_configurator_tool`
    - `critic_tool(post_plan)`
    - `visual_mapper_tool`
    - `critic_tool(post_mapper)`
    - `summary_tool`
  - 引入回路计数、warning、上轮工具结果等上下文

### logician/v2.md
- 保留：
  - “项目逻辑梳理员”的定位
  - 只做逻辑结构梳理、不碰视觉风格的边界
  - 提取图标题、核心方法、关键组件、依赖关系的任务目标
- 必要修改：
  - 变量名对齐到当前执行器上下文
  - 明确允许读取 `source_text`
  - 由于阶段 4 尚未实施，当前仍保持 `LogicSpec` 结构化输出兼容

### style_configurator/v2.md
- 保留：
  - “首席信息设计师”的角色
  - 学科差异化和学术审美约束
  - 对配色、字体、形状、图例等风格规范的关注点
- 必要修改：
  - 变量名对齐到当前执行器上下文
  - 明确允许读取 `source_text`
  - 当前仍保持 `StyleSpec` 结构化输出兼容

### visual_mapper/v2.md
- 保留：
  - “科研绘图视觉定稿师”的角色
  - 严谨图表语言、组件清单、层级、连线、排版等核心要求
- 必要修改：
  - 明确只消费 logic/style/user_feedback，不直接读取 `source_text`
  - 输出约束保持 `MapperSpec` 兼容

### critic/v2.md
- 保留：
  - “学术图表质检总监”的强审查语气
  - 一致性、清晰度、缺失和冲突检查的核心职责
- 必要修改：
  - 新增 `review_phase`
  - 区分 `post_plan` 与 `post_mapper` 两个阶段的输入和审查目标
  - 明确不直接读取 `source_text`
  - 输出约束保持 `ReviewSpec` 兼容

### summary/v2.md
- 保留：
  - “科研可视化架构师 / 最终英文 Prompt 组装者”的角色
  - 最终英文 Prompt 的质量标准
- 必要修改：
  - 明确只依赖上游 artifacts 与 warning，不读取 `source_text`
  - 输入对齐到当前 `payload_logic/payload_style/payload_mapper/payload_review`
  - 引入 `bypass_warnings`
  - 输出约束保持 `FinalPromptSpec` 兼容

## 与阶段 4 的边界
- 本阶段没有把业务工具改为自然语言自由输出
- 本阶段没有替换 `StructuredAgentExecutor`
- 本阶段没有把 `payload_*` 主链路整体退场
- 阶段 4 才负责真正的业务工具文本化与双阶段 Critic 全量落地

## 审阅重点
- 是否接受默认 Prompt 全量切到 `v2.md`
- 是否接受 `[[var]]` 作为统一模板变量语法
- 是否接受当前阶段继续保留结构化输出兼容，以避免提前进入阶段 4
- 是否接受新的主控编排顺序、输入边界和双阶段 Critic 表述
