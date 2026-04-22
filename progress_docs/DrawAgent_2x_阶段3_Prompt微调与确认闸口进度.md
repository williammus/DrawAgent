# DrawAgent 2.x 阶段 3：Prompt 微调与确认闸口进度

## 本阶段完成内容
- 默认 Prompt 入口已统一切换到 6 个 Agent 的 `v2.md`
- 启用中的 `v2.md` 已统一改为 `[[variable_name]]` 模板语法
- `orchestrator` Prompt 已切换为主控原生 tool calling 语义，并纳入双阶段 Critic 编排顺序
- `logician`、`style_configurator`、`visual_mapper`、`critic`、`summary` 的输入边界已按升级概要设计收口
- 已补充 Prompt 级测试，覆盖默认版本、模板变量存在性和关键输入边界

## Prompt 契约变化
- `orchestrator` 不再描述为“输出 JSON 路由决策”，而是“通过 tool calling 调度工具”
- `visual_mapper`、`critic`、`summary` 已明确不直接读取 `source_text`
- `critic` 已区分 `post_plan` 和 `post_mapper` 两个审查阶段
- `summary` 现在明确依赖终审结果与 warning 信息

## 原文保留原则执行情况
- 各 `v2.md` 的角色设定、语气风格和主要业务目标已尽量保留
- 修改集中在工具调用方式、变量命名、输入边界和双阶段审查职责
- 没有在本阶段重写整份 Prompt，也没有把阶段 4 的业务文本化直接前置

## 需要确认的点
- 是否接受当前默认 Prompt 全量切换到 `v2.md`
- 是否接受 `[[var]]` 作为统一模板语法
- 是否接受阶段 3 继续保留结构化输出兼容，而把业务文本化延后到阶段 4
- 是否接受新的主控编排顺序和双阶段 Critic 表述

## 对阶段 4 的交接注意事项
- 当前 Prompt 已经完成输入边界和职责收口，阶段 4 不应再改工具名、主控顺序或审查阶段命名
- 阶段 4 可以基于这些 Prompt 再推进业务工具文本化，但要谨慎处理与现有 `StructuredAgentExecutor`、`payload_*` 的兼容退场
- `summary` 已可读取 warning 信息；阶段 4 如切文本 artifact，需要同步重命名输入装配层

## 当前已知风险
- 当前业务执行器仍是结构化 schema 链路，Prompt 与运行时之间存在“阶段 3 已收口、阶段 4 尚未落地”的过渡态
- 若阶段 4 文本化实施时直接替换变量名或 artifact 命名，需同步调整 Prompt 传参层，避免模板再次漂移
