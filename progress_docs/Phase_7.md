# Phase 7

## 目标

完成真实联调排障、测试、验收和部署收口，让 2.0 从“mock 基线通过”收敛到“真实 LLM / 图片接口可诊断、可验证、可定位问题”的 MVP 发布态。

## 已完成

- 新增真实接口诊断能力：
  - `python backend/manage.py diag-llm`
  - `python backend/manage.py diag-image`
- 后端新增真实联调用测试：
  - `backend/tests/test_llm_live_integration.py`
  - `backend/tests/test_image_live_integration.py`
  - 默认跳过，只有显式环境变量开启时才访问真实上游
- 后端增强错误透传：
  - workflow `error` 事件现在会附带 `failing_node / failing_stage / exception_type / error`
  - LLM 失败会附带 `base_url / model / attempts` 等上下文
- 前端增强错误展示：
  - 不再只显示 `Orchestrator failed.`
  - 会同时展示 `error_code` 和关键诊断摘要
- 补充新的本地测试：
  - 诊断模块单元测试
  - workflow 失败事件诊断细节测试
  - 前端 SSE 错误详情写入测试
- 更新根目录 `README.md`，补充真实联调排障顺序和 live integration 命令

## 验证结果

- 本轮改造后将重新执行：
  - `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py lint`
  - `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py test`
  - `npm.cmd --prefix frontend run lint`
  - `npm.cmd --prefix frontend run build`
  - `npm.cmd --prefix frontend run test`
- 真实接口验证命令：
  - `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py diag-llm`
  - `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py diag-image`

## 交接说明

- 当前机器后端仍应优先使用：
  - `D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe`
- 当前真实联调的推荐顺序改为：
  - 先跑 `diag-llm`
  - 再跑 `diag-image`
  - 最后再打开前端执行整链路
- 当前前端如果仍提示 `Orchestrator failed.`，应继续查看错误卡片里的 `error_code` 和诊断摘要，而不是只看主文案

## 已知事项

- 当前 `.env` 虽然已有真实 `LLM_* / IMAGE_*` 值，但是否真正兼容仍要以 `diag-llm / diag-image` 结果为准
- `backend/tests/test_llm_live_integration.py` 和 `test_image_live_integration.py` 默认跳过，不代表真实接口已通过
- 本阶段仍未引入 `Playwright`、`Docker`、`CI/CD`，收口目标仍是单机演示 / 团队内部试用
