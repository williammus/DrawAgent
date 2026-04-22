# DrawAgent 2.x 阶段 6 进度文档

## 本阶段完成内容
- 已完成 2.x 主链路的联调收口，当前运行主路径统一为：
  - `source_text-first` 前端输入
  - `run(source_text)` / `run(user_feedback)` / `resume(user_feedback)`
  - 文本 artifact 主链路
  - 双阶段 Critic 与 warning 放行
- 后端旧上传主路径已退出运行入口，`/api/upload` 不再属于当前系统能力。
- 后端 `GraphState` 已移除旧上传字段和旧结构化 artifact 兼容字段，主流程只保留新状态与文本 artifact。
- 前端未再使用的上传 API 与附件托盘源码已从仓库主链路清理。
- README 与 AGENTS 中对计划目录、当前架构和联调主路径的描述已更新到当前版本口径。

## 清理边界
- 本阶段清理的是已经脱离主链路且会误导后续实现的旧能力：
  - 上传附件输入
  - 旧 `payload_*` 结构化 artifact 控制依赖
  - 旧澄清兼容字段
  - 旧文档中的错误目录与旧阶段口径
- 保留但不纳入 2.x 主链路的内容：
  - `legacy/agent1/`
  - 各 agent 的 `v1.md` prompt 历史版本
- 本阶段没有新增业务功能，也没有改变阶段 1 到阶段 5 已确定的外部接口语义。

## 验收执行与结论
- 后端自动化验证已通过：
  - `python backend/manage.py lint`
  - `python backend/manage.py test`
- 前端自动化验证已通过：
  - `npm.cmd --prefix frontend run lint`
  - `npm.cmd --prefix frontend run test`
  - `npm.cmd --prefix frontend run build`
- 前端 `test/build` 首次在沙箱内因 `esbuild spawn EPERM` 受限，后续已在提权执行下验证通过；这属于当前环境限制，不是代码问题。
- 当前仓库已满足阶段 6 的收口目标：
  - 新旧链路边界清晰
  - 主流程只走 2.x 新架构
  - 自动化回归可重复执行

## 对后续交接注意事项
- 后续若继续扩展功能，应继续沿用：
  - 文本 artifact 主链路
  - `source_text-first` 输入模型
  - `run/resume` 显式语义
- 不要重新引入上传附件作为正式输入主路径，也不要恢复 `payload_*` 作为业务控制依据。
- 若继续修改文档，优先维护：
  - `Upgrade_Plan/`
  - `progress_docs/`
  - `README.md`
- 若需要做真实外部联调，建议继续先跑：
  - `backend/manage.py diag-llm`
  - `backend/manage.py diag-image`

## 当前已知风险
- 仓库中仍保留部分历史 `v1.md` prompt 文本，它们只应作为历史版本存在，不能再作为当前实现依据。
- 真实 live integration 仍取决于本地环境变量、密钥和外部网络条件；当前自动化主回归不默认覆盖这些外部依赖。
- 前端 `test/build` 在受限沙箱中仍可能再次遇到 `esbuild` 的进程权限问题；在正常开发环境或提权执行下可通过。
