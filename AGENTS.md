# Repository Guidelines

## Project Structure & Module Organization
`backend/` contains the FastAPI service, LangGraph workflow, prompt assets, and tests. Core runtime code lives under `backend/app/` with modules split by concern: `api/routes/`, `agents/`, `graph/`, `services/`, `storage/`, and `prompts/`. Backend tests are in `backend/tests/`.

`frontend/` is a React + TypeScript + Vite SPA. UI code lives in `frontend/src/` and is organized by layer: `api/`, `components/`, `hooks/`, `store/`, `types/`, and `features/`. `legacy/agent1/` is archived 1.0 code for reference only. Planning and handoff docs live in `Upgrade_Plan/` and `progress_docs/`.

## Build, Test, and Development Commands
Backend uses `backend/manage.py` as the main task entrypoint:

- `python backend/manage.py dev` starts the API with reload.
- `python backend/manage.py test` runs `pytest backend/tests`.
- `python backend/manage.py lint` runs `ruff check`.
- `python backend/manage.py format` runs `ruff format`.

Frontend commands:

- `npm.cmd --prefix frontend install` installs dependencies.
- `npm.cmd --prefix frontend run dev` starts Vite locally.
- `npm.cmd --prefix frontend run build` runs `tsc --noEmit` and builds production assets.
- `npm.cmd --prefix frontend run lint` runs ESLint.
- `npm.cmd --prefix frontend run test` runs Vitest once.

## Coding Style & Naming Conventions
Use 4-space indentation in Python and 2-space indentation in TypeScript/TSX, matching the existing files. Prefer type hints in backend code and keep FastAPI/Pydantic models in `schemas/`. Use `snake_case` for Python modules/functions, `PascalCase` for React components, and `camelCase` for hooks, helpers, and Zustand state selectors. Keep prompt versions under `backend/app/prompts/<prompt_name>/v*.md`.

## Testing Guidelines
Backend tests use `pytest`; add tests as `backend/tests/test_<area>.py`. Frontend tests use Vitest and Testing Library; colocate them in `frontend/src/` as `*.test.tsx` or `*.test.ts`. Cover API flows, workflow state transitions, and UI behavior for any changed feature before opening a PR.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commit prefixes, mainly `feat:` with phase-oriented summaries such as `feat: DrawAgent 2.0 Phase 6 ...`. Keep that format and describe the affected subsystem. PRs should include a short scope summary, linked phase/issue references, test evidence (`manage.py test`, `npm run test`, `npm run build`), and screenshots or GIFs for frontend changes.

## Security & Configuration Tips
Use `backend/.env.example` and `frontend/.env.example` as templates. Do not commit real API keys or generated temp artifacts. Default local integration should use `IMAGE_PROVIDER=mock` until the full external pipeline is intentionally exercised.
