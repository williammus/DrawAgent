---
name: scientific_diagram
description: 科研绘图 skill。主控基于用户需求与附件，先派发逻辑提取、风格提取、可视化布局，再派发总结，最终在用户确认后派发生图任务。
plan:
  stages:
    - stage: logic_extraction
      agent_name: logic_extraction
      review_required: true
      review_phase: logic_review
    - stage: style_extraction
      agent_name: style_extraction
      review_required: true
      review_phase: style_review
    - stage: visual_mapping
      agent_name: visual_mapping
      review_required: true
      review_phase: visual_review
    - stage: summarization
      agent_name: summarization
      review_required: true
      review_phase: final_prompt_review
    - stage: image_generation
      agent_name: image_generation
      review_required: false
      trigger: user_confirm
---

# Scientific Diagram Skill

## Skill Intent

当用户上传论文、文档，或直接描述科研方法图/框架图需求时，主控应优先考虑本 skill。

## Entry Requirements

进入本 skill 前，必须满足两类前置信息：

1. 设计上下文
- `primary_discipline`
- `conference_name`
- `user_preferences`

2. 来源材料
- 已成功解析的附件正文
- 或用户直接粘贴的摘要、方法部分、图注、正文片段

如果只有学科、会议、偏好，而没有正文来源材料，则不能直接进入 `logic_extraction`，必须先澄清。

## Orchestration Rules

1. 先获得 `document_context`
2. 再做逻辑提取
3. 再做风格提取
4. 再做可视化布局
5. 再做总结，生成英文绘图 Prompt
6. 每一步都经过审查
7. 审查失败时回灌给对应虚拟节点
8. 通过或超过重试上限后，才能把 Prompt 交给前端
9. 用户点击确认后，再进入图片生成

## Review Rules

- 逻辑提取要检查是否忠于原文，是否缺失关键模块与依赖
- 风格提取要检查是否越界脑补具体技术路线
- 可视化布局要检查是否忠于逻辑与风格，不得随意臆造模块
- 总结要检查英文 Prompt 是否忠于前三者结果，且可直接用于生图
