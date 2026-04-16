# DrawAgent

当前仓库已进入 2.0 重构阶段，目录职责如下：

- `backend/`：FastAPI 后端骨架，承载后续 LangGraph、会话和 Agent 编排
- `frontend/`：React + TypeScript + Vite 前端骨架
- `legacy/agent1/`：1.0 Streamlit 原型归档，仅作参考和回归比对
- `Refactoring_Upgrading_Plan/`：重构设计与分阶段计划文档

## 启动后端

```powershell
python backend/manage.py dev
```

常用命令：

```powershell
python backend/manage.py test
python backend/manage.py lint
python backend/manage.py format
```

后端环境变量模板见 `backend/.env.example`。

## 启动前端

```powershell
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run dev
```

常用命令：

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run format
```

前端环境变量模板见 `frontend/.env.example`。

## Legacy 说明

`legacy/agent1/` 下保留了 1.0 原型代码，包括原 `appp.py`、`core/` 和旧依赖文件。该目录不再承载 2.0 新功能开发。

## 当前阶段

当前仅完成 Phase 1 工程骨架搭建：

- 后端可独立启动并提供 `GET /healthz`
- 前端可独立启动并渲染 2.0 占位壳
- 业务工作流、会话状态、LangGraph 编排将在后续阶段接入
