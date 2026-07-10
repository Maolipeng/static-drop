# Repository Guidelines

## Project Structure & Module Organization

StaticDrop is a pnpm/Turbo monorepo for self-hosted static site deployments. `apps/web` contains the Next.js 15 console; routes live in `apps/web/src/app`, UI in `apps/web/src/components`, and API helpers in `apps/web/src/lib`. `apps/api` contains the FastAPI service under `apps/api/app`, including `main.py`, `deploy.py`, `config.py`, and `db.py`. Infrastructure lives in `infra/nginx`, with orchestration in `compose.yml`. Deployment scripts are `deploy.sh` and `uninstall.sh`.

## Build, Test, and Development Commands

- `pnpm install`: install workspace JavaScript dependencies.
- `pnpm dev`: run Turbo development tasks for workspace apps.
- `pnpm build`: build all Turbo packages; use `pnpm build:web` for the web app only.
- `pnpm lint`: run configured lint tasks.
- `cd apps/api && uv sync`: install Python dependencies and dev tools.
- `cd apps/api && DATA_DIR=/tmp/staticdrop-dev DEPLOY_TOKEN=dev-token uv run uvicorn app.main:app --reload --port 8000`: run the API.
- `cd apps/web && API_URL=http://localhost:8000 DEPLOY_TOKEN=dev-token pnpm dev`: run the web app.
- `docker compose up --build -d`: build and run the full Nginx, web, and API stack.

## Coding Style & Naming Conventions

Use 2-space indentation for TypeScript/TSX and keep React components in `PascalCase` files, such as `DropZone.tsx`. Follow App Router conventions under `src/app`. Use Tailwind utilities for styling and keep shared client logic in `src/lib`. Python code should use type hints, focused functions, and `snake_case` names. Keep environment-driven behavior in `apps/api/app/config.py` or `.env.example`, not hardcoded in handlers.

## Testing Guidelines

No committed test suite exists yet. For API changes, add pytest tests under `apps/api/tests` and run them with `cd apps/api && uv run pytest`. For frontend behavior, add tests near `apps/web/src` using the framework introduced in the same change, and document any new command in `package.json`. For deployment-path changes, verify with `docker compose up --build -d` and the `/api/health` endpoint.

## Commit & Pull Request Guidelines

The current history uses Conventional Commit style, for example `feat: init`. Continue with concise prefixes such as `feat:`, `fix:`, `docs:`, or `chore:`. Pull requests should include a problem statement, implementation summary, verification commands, linked issues if any, and screenshots for visible UI changes. Call out changes to deployment, `.env`, storage paths, or authentication tokens.

## Security & Configuration Tips

Never commit real `.env` secrets or deployment tokens. Update `.env.example` when adding configuration. Preserve upload validation and blocked-file checks in the API, and treat `DATA_DIR`, `DEPLOY_TOKEN`, and public base URL changes as deployment-sensitive.
