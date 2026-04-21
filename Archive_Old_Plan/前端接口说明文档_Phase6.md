# DrawAgent 2.0 前端接口说明文档

## 1. 文档说明

- 文档用途：供 Phase 6 前端页面重建时对接当前后端 FastAPI 接口。
- 基准代码：当前仓库 `backend/app` 下的实际实现，不以规划文档推测为准。
- 适用范围：Phase 5 已完成后的后端接口层，包括会话、上传、聊天工作流、SSE 事件流、产物查询、图片生成与下载。

## 2. 基础约定

### 2.1 服务地址

- 默认后端地址：`http://127.0.0.1:8000`
- Swagger 文档：`/docs`
- ReDoc：`/redoc`
- 健康检查：`/healthz`

说明：

- `host/port` 可通过后端 `.env` 配置覆盖，默认值来自 `backend/app/core/settings.py`。
- 默认允许跨域来源：`http://127.0.0.1:5173`

### 2.2 认证与请求头

当前版本无登录鉴权，无 Token 机制。

可选请求头：

- `x-request-id`: 可由前端传入，用于链路追踪。若不传，后端自动生成。

响应头：

- `x-request-id`: 后端会原样返回本次请求的 request id。

### 2.3 数据格式

- 普通接口：`application/json`
- 文件上传：`multipart/form-data`
- 事件流：`text/event-stream`
- 图片下载：二进制文件流，`content-type` 取决于生成图片类型

## 3. 推荐前端调用流程

### 3.1 首次创建科研绘图任务

1. 调用 `POST /api/session/init` 创建会话。
2. 如有论文摘要、markdown、图片等资料，调用 `POST /api/upload` 上传。
3. 建立 SSE 连接：`GET /api/chat/stream/{session_id}`。
4. 调用 `POST /api/chat/message` 提交用户需求。
5. 根据 SSE 事件更新流程状态、提示澄清问题、展示阶段进度。
6. 需要查看结构化产物时，调用 `GET /api/artifacts/{session_id}`。
7. 收到 `prompt_ready` 事件或 `payload_final.ready_for_generation=true` 后，展示最终 prompt 预览并开放“生成图片”按钮。
8. 调用 `POST /api/generate/{session_id}` 启动出图。
9. 继续监听 SSE，收到 `image_generated` 后，通过 `GET /api/download/{session_id}` 下载或展示图片。
10. 页面关闭或任务结束后，可调用 `DELETE /api/session/{session_id}` 清理会话。

### 3.2 澄清追问场景

1. 工作流可能发出 `clarification_required` 事件。
2. 前端展示 `clarification_question`。
3. 用户补充回答后，继续调用 `POST /api/chat/message`。
4. 后端会自动判断这是继续执行澄清后的工作流，而不是新建流程。

### 3.3 修改已有逻辑/风格/排版

1. 保持原 `session_id`。
2. 将用户修改意见继续通过 `POST /api/chat/message` 提交。
3. 若只想让本次消息使用部分附件，可通过 `attachments` 指定文件 id 子集。

## 4. 统一错误响应

所有业务错误统一返回：

```json
{
  "error": {
    "code": "session_not_found",
    "message": "Session not found.",
    "details": {
      "session_id": "xxx"
    },
    "request_id": "9e1b..."
  }
}
```

### 4.1 常见错误码

| error.code | 含义 |
| --- | --- |
| `input_validation_error` | 业务参数校验失败 |
| `session_not_found` | 会话不存在 |
| `session_expired` | 会话已过期 |
| `resource_conflict` | 当前会话已有后台任务在执行 |
| `file_not_found` | 文件或附件 id 不存在 |
| `image_not_ready` | 图片尚未生成完成，不能下载 |
| `artifact_validation_error` | 中间产物校验失败 |
| `prompt_render_error` | prompt 渲染失败 |
| `llm_invocation_error` | 大模型调用失败 |
| `review_rejected` | 评审未通过 |
| `adapter_invocation_error` | 图像生成适配器调用失败 |
| `http_error` | FastAPI/HTTP 层异常 |
| `request_validation_error` | 请求体结构不符合 Pydantic 定义 |
| `internal_server_error` | 未处理异常 |

### 4.2 常见状态码

| HTTP 状态码 | 场景 |
| --- | --- |
| `200` | 查询、删除成功 |
| `201` | 创建成功 |
| `202` | 已接受，后台异步处理中 |
| `400` | 业务输入错误 |
| `404` | 会话或文件不存在 |
| `409` | 资源冲突，或图片尚未就绪 |
| `410` | 会话已过期 |
| `422` | 请求体验证失败或产物校验失败 |
| `500` | 服务内部错误 |
| `502` | 外部模型/适配器调用失败 |

## 5. 枚举约定

### 5.1 `StageName`

| 值 | 含义 |
| --- | --- |
| `idle` | 会话初始态 |
| `clarifying` | 等待用户补充信息 |
| `planning` | orchestrator 规划阶段 |
| `logic_ready` | 逻辑结构产出完成 |
| `style_ready` | 风格方案产出完成 |
| `mapping_ready` | 布局映射产出完成 |
| `reviewing` | critic 评审阶段 |
| `prompt_ready` | 最终 prompt 已就绪 |
| `generating_image` | 正在生成图片 |
| `completed` | 图片生成完成 |
| `failed` | 流程失败 |

### 5.2 `IntentType`

| 值 | 含义 |
| --- | --- |
| `unknown` | 未识别 |
| `new_task` | 新任务 |
| `modify_logic` | 修改逻辑 |
| `modify_style` | 修改风格 |
| `modify_layout` | 修改排版 |
| `modify_logic_and_style` | 同时修改逻辑与风格 |
| `clarify` | 回答澄清 |

### 5.3 `GenerateStatus`

| 值 | 含义 |
| --- | --- |
| `accepted` | 已接收生成任务 |
| `running` | 预留状态，当前接口未直接返回 |
| `completed` | 预留状态，当前接口未直接返回 |
| `failed` | 预留状态，当前接口未直接返回 |

### 5.4 `EventType`

| 值 | 含义 |
| --- | --- |
| `stage_started` | 阶段开始 |
| `stage_completed` | 阶段完成 |
| `clarification_required` | 需要用户补充信息 |
| `review_failed` | 评审失败并要求回滚 |
| `prompt_ready` | 最终 prompt 已可用于出图 |
| `image_generated` | 图片已生成 |
| `error` | 流程执行失败 |

### 5.5 `ReviewErrorStage`

| 值 | 含义 |
| --- | --- |
| `input_guard` | 输入守卫 |
| `orchestrator` | 任务编排 |
| `logician` | 逻辑结构阶段 |
| `style_configurator` | 风格配置阶段 |
| `visual_mapper` | 布局映射阶段 |
| `critic` | 评审阶段 |
| `summary_agent` | 总结阶段 |
| `image_adapter` | 图片生成阶段 |
| `unknown` | 未知 |

## 6. 接口清单

### 6.1 健康检查

#### `GET /healthz`

用途：

- 检查后端服务是否正常启动。

响应示例：

```json
{
  "status": "ok",
  "service": "drawagent-backend",
  "environment": "development",
  "version": "0.1.0",
  "request_id": "0d5d..."
}
```

---

### 6.2 创建会话

#### `POST /api/session/init`

用途：

- 创建新的绘图会话，前端后续所有请求都依赖 `session_id`。

响应状态码：

- `201 Created`

响应结构：

```json
{
  "session_id": "4d7c7d...",
  "summary": {
    "session_id": "4d7c7d...",
    "stage": "idle",
    "intent": "unknown",
    "has_payload_logic": false,
    "has_payload_style": false,
    "has_payload_mapper": false,
    "has_payload_review": false,
    "has_payload_final": false,
    "needs_clarification": false,
    "user_confirmed": false,
    "error_count": 0,
    "updated_at": "2026-04-17T04:00:00Z",
    "expires_at": "2026-04-17T04:30:00Z"
  }
}
```

前端建议：

- 将 `session_id` 持久化到当前页面状态。
- 将 `summary` 作为顶部状态栏初始值。

---

### 6.3 删除会话

#### `DELETE /api/session/{session_id}`

用途：

- 删除会话状态、SSE 事件缓存、检查点和临时目录。

响应示例：

```json
{
  "session_id": "4d7c7d...",
  "deleted": true,
  "cleanup": {
    "ran_at": "2026-04-17T04:10:00Z",
    "removed_sessions": ["4d7c7d..."],
    "removed_directories": ["4d7c7d..."],
    "failed_targets": [],
    "details": {}
  }
}
```

说明：

- 当前实现中 `removed_directories` 返回的是 `session_id` 标记，不是物理路径，前端无需依赖其具体内容。

---

### 6.4 上传附件

#### `POST /api/upload`

用途：

- 上传论文摘要、markdown、截图、参考图等附件到会话。

请求类型：

- `multipart/form-data`

表单字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | `string` | 是 | 当前会话 id |
| `files` | `file[]` | 是 | 支持多文件上传 |

响应状态码：

- `201 Created`

响应结构：

```json
{
  "session_id": "4d7c7d...",
  "files": [
    {
      "file_id": "a1b2c3",
      "original_name": "paper.md",
      "stored_name": "20260417_xxx_paper.md",
      "media_type": "text/markdown",
      "size_bytes": 2048,
      "relative_path": "4d7c7d/uploads/20260417_xxx_paper.md",
      "uploaded_at": "2026-04-17T04:01:00Z"
    }
  ]
}
```

当前默认限制：

- 单会话最多 `10` 个文件
- 单文件最大 `25MB`

业务规则：

- 若 `files` 为空，返回 `400 input_validation_error`
- 如果超出文件数量上限，返回 `400 input_validation_error`
- 如果任一文件超过大小限制，返回 `400 input_validation_error`
- 上传成功后，后端会将这些文件同时设为本 session 的默认 `source_files`

前端建议：

- 上传完成后缓存 `file_id`，后续 `attachments` 字段使用它。
- 允许多次追加上传。

---

### 6.5 删除已上传附件

#### `DELETE /api/upload/{session_id}/{file_id}`

用途：

- 删除会话内某个已上传文件。

响应示例：

```json
{
  "session_id": "4d7c7d...",
  "file_id": "a1b2c3",
  "deleted": true
}
```

业务规则：

- 删除后会同时从 `uploaded_files` 和当前 `source_files` 中移除。
- 若 `file_id` 不存在，返回 `404 file_not_found`

---

### 6.6 提交聊天消息并启动工作流

#### `POST /api/chat/message`

用途：

- 提交用户需求或修改意见。
- 后端接受后立即返回，实际工作流在后台异步执行。

请求体：

```json
{
  "session_id": "4d7c7d...",
  "message": "请基于论文摘要生成一张科研流程图。",
  "attachments": ["a1b2c3", "d4e5f6"]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | `string` | 是 | 会话 id |
| `message` | `string` | 是 | 用户输入，最短 1 字符 |
| `attachments` | `string[]` | 否 | 本次消息绑定的附件 id 列表 |

响应状态码：

- `202 Accepted`

响应结构：

```json
{
  "session_id": "4d7c7d...",
  "stage": "idle",
  "summary": {
    "session_id": "4d7c7d...",
    "stage": "idle",
    "intent": "unknown",
    "has_payload_logic": false,
    "has_payload_style": false,
    "has_payload_mapper": false,
    "has_payload_review": false,
    "has_payload_final": false,
    "needs_clarification": false,
    "user_confirmed": false,
    "error_count": 0,
    "updated_at": "2026-04-17T04:00:00Z",
    "expires_at": "2026-04-17T04:30:00Z"
  },
  "accepted": true,
  "stream_url": "/api/chat/stream/4d7c7d...",
  "response_message": "Workflow request accepted."
}
```

关键业务规则：

- 若 `attachments` 为空数组，后端默认使用当前 session 的全部已上传文件。
- 若 `attachments` 非空，则仅使用指定文件作为本次工作流的 `source_files`。
- 若附件 id 非法，返回 `404 file_not_found`
- 若当前 session 已有后台任务在跑，返回 `409 resource_conflict`
- 若当前 session 处于澄清中断态，则本次调用会走“继续工作流”，`response_message` 为 `Clarification response accepted.`

前端建议：

- 不要轮询该接口等待结果，真实执行进度应通过 SSE 获取。
- 提交消息后立即监听 `stream_url`。

---

### 6.7 订阅工作流事件流

#### `GET /api/chat/stream/{session_id}`

用途：

- 订阅当前会话的工作流阶段事件。
- 前端应将其作为主状态驱动源。

请求参数：

| 参数 | 位置 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | path | `string` | - | 会话 id |
| `after_id` | query | `int` | `0` | 只拉取 event_id 大于该值的事件 |
| `once` | query | `boolean` | `false` | `true` 时返回一批事件后立即断开 |
| `Last-Event-ID` | header | `string` | - | SSE 断线重连时可传最近 event id |

响应类型：

- `text/event-stream`

后端推送格式示例：

```text
id: 12
event: stage_started
data: {"event_id":12,"event_type":"stage_started","data":{"event_type":"stage_started","session_id":"4d7c7d...","stage":"planning","timestamp":"2026-04-17T04:02:00Z","request_id":"req-123","message":"Orchestrator started."}}

```

说明：

- SSE 外层 `event` 字段与 JSON 内部的 `event_type` 一致。
- `data` 内部又包了一层对象，结构固定为：

```json
{
  "event_id": 12,
  "event_type": "stage_started",
  "data": {
    "...具体事件字段..."
  }
}
```

无新事件时的连接保活：

- 如果当前没有后台任务，服务端可能发送注释行：`: keep-alive`
- 如果当前仍有后台任务但暂时无新事件，服务端可能发送：

```text
event: heartbeat
data: {}

```

前端处理建议：

- `keep-alive` 和 `heartbeat` 都不需要更新业务 UI。
- 建议保存最新 `event_id`，断线重连时通过 `Last-Event-ID` 或 `after_id` 补拉。
- 建议将 SSE 作为阶段条、消息气泡、出图按钮状态的单一事实来源。

#### 事件类型详情

##### 1. `stage_started`

```json
{
  "event_type": "stage_started",
  "session_id": "4d7c7d...",
  "stage": "planning",
  "timestamp": "2026-04-17T04:02:00Z",
  "request_id": "req-123",
  "message": "Orchestrator started."
}
```

##### 2. `stage_completed`

```json
{
  "event_type": "stage_completed",
  "session_id": "4d7c7d...",
  "stage": "logic_ready",
  "timestamp": "2026-04-17T04:02:10Z",
  "request_id": "req-123",
  "message": "logician completed."
}
```

##### 3. `clarification_required`

```json
{
  "event_type": "clarification_required",
  "session_id": "4d7c7d...",
  "stage": "clarifying",
  "timestamp": "2026-04-17T04:02:20Z",
  "request_id": "req-123",
  "message": "Clarification is required before the workflow can continue.",
  "clarification_question": "请补充论文摘要、方法说明或希望修改的具体内容。"
}
```

前端动作：

- 展示补充信息输入框
- 将发送按钮语义切换为“继续流程”

##### 4. `review_failed`

```json
{
  "event_type": "review_failed",
  "session_id": "4d7c7d...",
  "stage": "reviewing",
  "timestamp": "2026-04-17T04:02:40Z",
  "request_id": "req-123",
  "message": "Critic requested a rollback.",
  "reason": "布局层级不清晰。",
  "error_stage": "visual_mapper",
  "fix_suggestion": ["强化主路径", "减少交叉箭头"]
}
```

前端动作：

- 可提示“评审未通过，系统正在自动回滚重试”
- 可展示 `reason` 与 `fix_suggestion`

##### 5. `prompt_ready`

```json
{
  "event_type": "prompt_ready",
  "session_id": "4d7c7d...",
  "stage": "prompt_ready",
  "timestamp": "2026-04-17T04:03:00Z",
  "request_id": "req-123",
  "message": "Final prompt is ready for generation.",
  "prompt_version": "v1",
  "ready_for_generation": true
}
```

前端动作：

- 读取 `GET /api/artifacts/{session_id}` 中的 `payload_final`
- 开放“生成图片”按钮

##### 6. `image_generated`

```json
{
  "event_type": "image_generated",
  "session_id": "4d7c7d...",
  "stage": "completed",
  "timestamp": "2026-04-17T04:03:30Z",
  "request_id": "req-123",
  "message": "Image generated successfully.",
  "image_path": "4d7c7d/generated/final.png"
}
```

注意：

- `image_path` 是后端临时目录中的相对路径，不建议前端直接拼接访问。
- 前端应使用 `GET /api/download/{session_id}` 进行展示或下载。

##### 7. `error`

```json
{
  "event_type": "error",
  "session_id": "4d7c7d...",
  "stage": "failed",
  "timestamp": "2026-04-17T04:03:30Z",
  "request_id": "req-123",
  "message": "Workflow background execution failed.",
  "error_code": "internal_server_error",
  "details": {
    "error": "..."
  }
}
```

前端动作：

- 将任务状态设为失败
- 展示错误信息并允许用户再次提交修改意见

---

### 6.8 获取结构化产物

#### `GET /api/artifacts/{session_id}`

用途：

- 获取当前会话中的结构化中间产物与最终 prompt。

响应结构：

```json
{
  "session_id": "4d7c7d...",
  "payload_logic": null,
  "payload_style": null,
  "payload_mapper": null,
  "payload_review": null,
  "payload_final": null
}
```

说明：

- 任一字段都可能为 `null`，取决于流程执行到哪个阶段。
- 前端需要按字段是否为空做渐进式展示。

#### `payload_logic`

```json
{
  "chart_title": "XXX机制图",
  "core_method_summary": "概述文本",
  "containers": [
    {
      "container_id": "c1",
      "name": "模块A",
      "description": "可选",
      "children": ["n1", "n2"]
    }
  ],
  "nodes": [
    {
      "node_id": "n1",
      "label": "步骤1",
      "description": "可选",
      "node_type": "optional"
    }
  ],
  "edges": [
    {
      "source": "n1",
      "target": "n2",
      "label": "促进",
      "relation": "activation"
    }
  ]
}
```

#### `payload_style`

```json
{
  "discipline": "biology",
  "target_journal": "Nature",
  "primary_palette": ["#123456", "#abcdef"],
  "secondary_palette": ["#eeeeee"],
  "font_family": "Arial",
  "line_style": "solid",
  "node_shape_rules": {
    "input": "rounded-rect",
    "output": "circle"
  },
  "layout_style": "left-to-right",
  "legend_style": "minimal",
  "forbidden_visual_elements": ["3d effect"],
  "style_keywords": ["clean", "high contrast"]
}
```

#### `payload_mapper`

```json
{
  "narrative_direction": "left_to_right",
  "section_layout": ["input", "process", "output"],
  "module_positions": {
    "module_a": "left-top"
  },
  "grouping_strategy": "by function",
  "edge_style_mapping": {
    "activation": "solid-arrow"
  },
  "visual_hierarchy": ["main_path", "secondary_notes"],
  "annotation_strategy": "numbered callouts",
  "legend_placement": "bottom-right"
}
```

#### `payload_review`

```json
{
  "passed": false,
  "error_stage": "visual_mapper",
  "reason": "布局不清晰",
  "fix_suggestion": ["减少交叉", "突出主路径"]
}
```

#### `payload_final`

```json
{
  "final_prompt_en": "A clean scientific pathway diagram...",
  "final_prompt_cn": "一张清晰的科研通路示意图...",
  "prompt_version": "v1",
  "generation_notes": ["Use compact labels."],
  "ready_for_generation": true
}
```

前端建议：

- `payload_final.ready_for_generation` 是是否允许调用出图接口的唯一可靠开关。
- `payload_review.passed=false` 时，可提示系统正在回滚修正，除非最终进入 `failed`。

---

### 6.9 启动图片生成

#### `POST /api/generate/{session_id}`

用途：

- 根据最终 prompt 发起图片生成任务。

前置条件：

- `payload_final` 必须存在
- `payload_final.ready_for_generation` 必须为 `true`
- 当前会话没有其他后台任务在执行

响应状态码：

- `202 Accepted`

响应示例：

```json
{
  "session_id": "4d7c7d...",
  "stage": "generating_image",
  "status": "accepted",
  "generated_image_path": "/api/download/4d7c7d...",
  "generated_image_meta": null,
  "download_url": "/api/download/4d7c7d..."
}
```

说明：

- 当前实现里 `generated_image_path` 与 `download_url` 返回值相同，均为下载接口地址。
- `generated_image_meta` 在该接口响应中固定为 `null`，前端不要依赖这里拿图片元信息。
- 真正的完成信号应以 SSE 的 `image_generated` 事件为准。

错误场景：

- 未准备好最终 prompt：`400 input_validation_error`
- 当前 session 有其他任务进行中：`409 resource_conflict`

---

### 6.10 下载生成图片

#### `GET /api/download/{session_id}`

用途：

- 下载或展示当前会话已生成的最终图片。

返回：

- 文件流响应
- `content-type` 取决于生成图片媒体类型，例如 `image/png`
- `Content-Disposition` 中会带文件名

错误场景：

- 尚未生成图片：`409 image_not_ready`
- 会话不存在或已过期：`404/410`

前端建议：

- 可直接将该地址作为 `<img src>` 使用。
- 也可作为下载按钮链接。

## 7. 核心数据结构

### 7.1 `SessionStateSummary`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | `string` | 会话 id |
| `stage` | `StageName` | 当前阶段 |
| `intent` | `IntentType` | 当前任务意图 |
| `has_payload_logic` | `boolean` | 是否已有逻辑产物 |
| `has_payload_style` | `boolean` | 是否已有风格产物 |
| `has_payload_mapper` | `boolean` | 是否已有布局产物 |
| `has_payload_review` | `boolean` | 是否已有评审产物 |
| `has_payload_final` | `boolean` | 是否已有最终 prompt |
| `needs_clarification` | `boolean` | 是否等待用户澄清 |
| `user_confirmed` | `boolean` | 是否已确认出图 |
| `error_count` | `number` | 当前累计错误次数 |
| `updated_at` | `datetime` | 最近一次状态更新时间 |
| `expires_at` | `datetime` | 会话过期时间 |

### 7.2 `StoredFileMeta`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `file_id` | `string` | 文件唯一 id |
| `original_name` | `string` | 用户原始文件名 |
| `stored_name` | `string` | 后端保存后的文件名 |
| `media_type` | `string` | MIME 类型 |
| `size_bytes` | `number` | 文件大小 |
| `relative_path` | `string` | 后端临时目录相对路径 |
| `uploaded_at` | `datetime` | 上传时间 |

### 7.3 `GeneratedImageMeta`

当前只存在于后端内部状态中，当前接口层没有单独对外查询接口。字段定义如下，供后续扩展参考：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `file_name` | `string` | 图片文件名 |
| `media_type` | `string` | MIME 类型 |
| `size_bytes` | `number` | 文件大小 |
| `relative_path` | `string` | 相对路径 |
| `provider` | `string` | 当前默认 `nano-banana2` |
| `generated_at` | `datetime` | 生成时间 |

## 8. 前端实现注意事项

### 8.1 以 SSE 为主，不要只看同步响应

- `POST /api/chat/message` 和 `POST /api/generate/{session_id}` 都是异步启动型接口。
- 它们返回的只是“已接收”，不是流程最终结果。
- 真正的流程推进、失败、澄清、可出图、已出图，都应以 SSE 事件为准。

### 8.2 `attachments=[]` 的语义不是“不带附件”

- 当前实现中，`attachments` 为空时，后端会自动选用该会话所有已上传文件。
- 如果前端需要精确控制本次任务只用哪些文件，应显式传入附件 id 数组。

### 8.3 建议缓存最近的 `event_id`

- 支持断线重连。
- 可通过 `Last-Event-ID` 或 `after_id` 从上次位置继续拉取。

### 8.4 会话有 TTL

- 默认 TTL 为 `1800` 秒。
- 会话过期后再访问会返回 `410 session_expired`。
- 前端可根据 `summary.expires_at` 做倒计时提示，但仍应以接口实际返回为准。

### 8.5 出图按钮的启用条件

建议同时满足：

1. `payload_final` 不为 `null`
2. `payload_final.ready_for_generation === true`
3. 当前没有进行中的后台任务

### 8.6 当前没有“查询任务运行中状态”的独立接口

- 当前前端只能通过 SSE 和已有响应侧面判断。
- 如果后续 Phase 6 需要更强的刷新恢复能力，建议追加 session detail/status 接口。

## 9. 建议的前端状态模型

前端至少维护以下状态：

- `sessionId`
- `summary`
- `uploadedFiles`
- `artifacts`
- `eventStreamConnected`
- `latestEventId`
- `isWorkflowRunning`
- `isGeneratingImage`
- `clarificationQuestion`
- `generatedImageUrl`
- `lastError`

推荐判定逻辑：

- 收到 `stage_started` 且 `stage !== generating_image` 时，可视为工作流执行中
- 收到 `prompt_ready` 时，可刷新 `artifacts` 并启用出图
- 收到 `image_generated` 时，令 `generatedImageUrl = /api/download/{session_id}`
- 收到 `error` 时，结束运行态并展示错误

## 10. 后续可扩展点

基于当前接口实现，前端开发时需要注意以下空白能力：

- 无“获取会话详情”接口，只能靠 `summary + artifacts + SSE`
- 无“获取已上传文件列表”独立接口，需依赖上传响应自行缓存
- 无“取消运行中任务”接口
- 无“图片元信息查询”接口
- 无鉴权机制，未来若接入登录体系，接口层需要统一补充

---

如果后续 Phase 6 前端需要，我建议在此文档基础上再补一版“页面状态机 + 接口时序图”文档，便于直接映射到页面交互与状态管理实现。
