# DrawAgent 2.x 阶段 4 进度文档

## 本阶段完成内容
- 业务工具主链路已从结构化 `payload_*` 输出切换为文本 artifact 主链路，业务结果统一写入 `artifacts.*.content`。
- `logician`、`style_configurator`、`visual_mapper`、`critic`、`summary` 已切到文本生成方式，`summary` 的结果直接进入 `final_prompt_artifact`。
- 双阶段 Critic 已按 gate 落地：
  - `post_plan` 先审 `logician`，再审 `style_configurator`
  - `post_mapper` 审 `visual_mapper`
- 两个审查 gate 继续各自独立计数，超限后写入 warning 并放行。
- 主控已新增对用户输入的解析职责，会维护：
  - `parsed_discipline`
  - `parsed_target_venue`
  - `parsed_target_venue_type`
  - `parsed_special_requirements`
- 当领域、目标期刊/会议、期刊/会议类型为空或 `unknown` 时，主控会优先触发澄清。
- `Upgrade_Plan/DrawAgent_2x_升级概要设计.md` 与 `Upgrade_Plan/DrawAgent_2x_分阶段施工计划.md` 已同步更新到与当前实现一致的口径。

## Prompt 契约变化
- 正式 `v2.md` 已按新要求重建：
  - `orchestrator`、`logician`、`style_configurator`、`visual_mapper`、`summary` 以各自 `v2-informal.md` 为最小改动基线
  - `critic` 以 `critic/v2-new.md` 为最小改动基线
- 业务 prompt 已去掉 JSON 强约束，但没有为 artifact 正文施加统一固定格式。
- 如需附加说明或控制信号，统一通过旁路 metadata 传递，不再回到正文 JSON 化。
- `critic` 的输入已切到 `{type, pre_data, data}` 语义。

## 兼容策略与遗留项
- `payload_*` 相关 schema 和少量兼容字段仍然保留在代码中，但不再作为业务主链路控制依据。
- Artifact API、Session Summary、图片生成入口都已经转为消费文本 artifact。
- 本阶段没有处理前端 `source_text-first` 交互改造，前端页面层仍留待阶段 5。
- 附件相关路径仍存在于仓库中，但它们不是阶段 4 的主链路。

## 对阶段 5 的交接注意事项
- 前端需要直接消费 `artifacts.*.content`，不要再假设逻辑、风格、映射、审查、最终 Prompt 是固定 JSON 结构。
- `final_prompt_artifact.content` 就是图片生成使用的主 prompt 文本。
- 页面交互必须尊重主控的强制澄清规则：当领域、期刊/会议、类型缺失时，流程会先中断等待用户补充。
- `parsed_special_requirements` 已支持追加与覆盖语义，前端不需要单独维护这套解析逻辑。

## 当前已知风险
- 旧 `payload_*` 兼容字段仍在仓库中，后续清理时需要防止误删仍被历史测试或诊断代码引用的部分。
- 文本 artifact 正文不再有统一结构，这提升了模型自由度，但也要求后续前端展示与联调更注重可读性和容错。
- Prompt 已按最小改动基线回写，但如果后续继续改 prompt，需要继续遵守“基于原始基线最小修改”的约束，避免再次偏离。
