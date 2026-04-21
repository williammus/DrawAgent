# Phase 6

## 目标

重建前端单页应用，接通 Phase 5 后端接口、SSE、附件上传、Prompt 预览、出图与下载主链路。

## 已完成

- 将 `frontend/` 从 Phase 1 占位壳重构为单页对话工作台。
- 新增前端 `api/lib/store/hooks/types` 分层，接通 session/upload/chat/artifacts/generate 接口。
- 接入 `Zustand` 单会话状态管理和基于 `EventSource + after_id` 的 SSE 流。
- 完成主页面壳、侧栏、顶部状态条、消息流、澄清卡、评审回滚卡、Prompt 预览卡、图片结果卡、产物面板、输入区和附件托盘。
- 支持自动 init session、继续反馈修改、确认生成、重新开始、页面卸载时 best-effort 删除 session。
- 新增前端测试骨架与关键交互测试文件 `frontend/src/App.test.tsx`。

## 验证结果

- `npm.cmd --prefix frontend install` 已完成。
- `npm.cmd --prefix frontend run lint` 通过。
- `npm.cmd --prefix frontend run build` 通过。
- `npm.cmd --prefix frontend run test`：
  - 测试文件已写入并可被 Vitest 识别。
  - 当前环境下命令存在退出挂起问题，未拿到稳定结束码，需要后续继续排查 Vitest/Windows 进程退出行为。

## 交接说明

- 当前前端主链路代码已接齐，下一阶段可直接做联调与验收收口。
- 若继续排查测试挂起，优先检查：
  - `vitest + jsdom` 在当前 Windows 环境的退出行为
  - 测试中 React 组件残留的 timer / event listener / open handle
  - 是否需要单独的 Vitest runner 脚本来强制收口进程

## 已知事项

- 当前仓库 `frontend/node_modules` 与 `frontend/dist` 为本地验证产物，受 `.gitignore` 保护。
- 这台机器上前端 `build/test` 涉及的 Vite/Vitest/esbuild 进程在沙箱内可能触发 `spawn EPERM`，本阶段验证依赖提权执行。
