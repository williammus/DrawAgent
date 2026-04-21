# Phase 5

## 目标

实现 FastAPI 接口层、SSE 事件流、上传/下载链路，以及可切换的图片生成适配器，把内部工作流能力开放成前端可消费服务。

## 已完成

- 新增会话、对话、SSE、上传、制品、图片生成、下载接口
- 新增后台任务协调器，限制单会话单活动任务
- `WorkflowEventStore` 支持事件编号、回放和等待
- 新增 `MockImageAdapter` 与 `OpenAICompatibleImageAdapter`
- 接入图片生成后台任务与下载链路
- 补齐 API、适配器和状态相关测试

## 验证结果

- `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py lint` 通过
- `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py test` 通过
- 当前后端测试共 `35` 项，全部通过

## 交接说明

- `POST /api/chat/message` 采用立即返回，详细进度走 `GET /api/chat/stream/{session_id}`
- SSE 默认持续连接；为测试和回放场景补了 `once=true`，回放 backlog 后主动断开
- 图片适配器默认走 `IMAGE_PROVIDER=mock`；真实接入走 OpenAI 兼容格式，模型默认 `gemini-3-pro-image-preview-4k`

## 已知事项

- 当前机器上 `conda run -n DrawAgent python` 仍落到旧的 Python 3.7；实际可用环境是 `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe`
- 新增依赖 `python-multipart` 已直接安装到 `DrawAgent` 环境
