# DrawAgent 2.0 Phase 7 部署与运行说明

## 1. 部署目标

本阶段收口到单机演示 / 团队内部试用版：

- 前端：静态资源托管
- 后端：FastAPI + Uvicorn 单进程运行
- 不依赖数据库、Redis、对象存储

## 2. 环境要求

### 后端

- Python 环境：`D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe`
- 依赖安装：

```powershell
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt
```

### 前端

- Node.js + npm
- 依赖安装：

```powershell
npm.cmd --prefix frontend install
```

## 3. 最小配置

### `backend/.env`

最小可运行配置：

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
FRONTEND_ORIGIN=http://127.0.0.1:5173
TEMP_DIR=./tmp
IMAGE_PROVIDER=mock
```

真实 provider 需要额外配置：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `IMAGE_API_KEY`
- `IMAGE_BASE_URL`
- `IMAGE_MODEL`

### `frontend/.env`

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_APP_TITLE=DrawAgent 2.0
```

## 4. 推荐启动顺序

1. 先启动后端
2. 校验 `GET /healthz`
3. 再启动前端
4. 打开 `http://127.0.0.1:5173`

## 5. 启动命令

### 后端

当前环境推荐使用不带热重载的命令：

```powershell
cd D:\Projects\keyanhuitu\DrawAgent\backend
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

说明：

- `python backend/manage.py dev` 在当前 Windows/Codex 环境下可能因 `--reload` 触发权限问题

### 前端开发

```powershell
npm.cmd --prefix frontend run dev
```

### 前端构建

```powershell
npm.cmd --prefix frontend run build
```

构建产物位于：

- `frontend/dist/`

## 6. 发布前验证

### 后端

```powershell
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py lint
D:\ProgramData\Anaconda3\envs\DrawAgent\python.exe backend\manage.py test
```

### 前端

```powershell
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test
```

## 7. 常见故障排查

### 前端打开后立即初始化失败

优先检查：

- 后端是否已启动
- `http://127.0.0.1:8000/healthz` 是否可访问
- `frontend/.env` 的 `VITE_API_BASE_URL` 是否正确
- `backend/.env` 的 `FRONTEND_ORIGIN` 是否匹配

### `python backend/manage.py dev` 报权限或重载问题

处理方式：

- 使用不带 `--reload` 的 `uvicorn` 启动命令

### 前端命令出现 `spawn EPERM`

说明：

- 这通常是当前受限执行环境对子进程启动的限制，不是仓库代码问题
- 在本机终端直接运行 `npm.cmd --prefix frontend run <...>` 更稳定

### 会话过期或图片下载失败

优先检查：

- session 是否已被删除或 TTL 到期
- 当前是否仍使用旧的 `session_id`
- `IMAGE_PROVIDER` 是否与预期一致

## 8. 运行建议

- 第一轮联调优先使用 `IMAGE_PROVIDER=mock`
- 主链路稳定后，再切真实模型与真实图片生成
- 当前项目定位是单机演示 / 内部试用，不建议在 Phase 7 额外引入 Docker、CI 或多机部署方案
