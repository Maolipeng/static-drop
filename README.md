# StaticDrop

Self-hosted drag-and-drop static site deployment tool — a self-built alternative to Cloudflare Drop / Netlify Drop.

Upload your static build artifact (Vite `dist`, React `build`, Next.js `out`, etc.) as a `.zip` **or a folder**, and get an instantly accessible URL like `https://drop.example.com/s/{deployId}/`.

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Nginx   │────▶│  Next.js  │     │ FastAPI  │
│  :80     │────▶│  Web UI   │     │  API     │
│          │────▶│  :3000    │     │  :8000   │
└────┬─────┘     └──────────┘     └────┬─────┘
     │                                  │
     │  /s/{deployId}/*                 │  /api/*
     │  (direct disk read)              │  (deploy, list, delete)
     ▼                                  ▼
   ┌──────────────────────────────────────┐
   │  /data/deployments/{deployId}/       │
   │  /data/db/staticdrop.db              │
   │  (shared Docker volume)              │
   └──────────────────────────────────────┘
```

**Monorepo structure:**

| Path | Purpose |
|---|---|
| `apps/web` | Next.js 15 web console (App Router, TypeScript, Tailwind) |
| `apps/api` | FastAPI deployment API (Python 3.12, uv, SQLite) |
| `infra/nginx` | Nginx reverse proxy + static file server |
| `compose.yml` | Docker Compose orchestrating all three services |

## Quick Start

### 一键部署（推荐）

```bash
# 方式 1: 交互式（提示输入域名）
./deploy.sh

# 方式 2: 直接指定 URL
./deploy.sh https://drop.example.com

# 方式 3: 本地部署
./deploy.sh --local
```

脚本会自动完成：检查 Docker → 生成随机 Token → 写入 `.env` → 构建镜像 → 启动服务 → 健康检查验证。

部署完成后会输出 Web 控制台地址和 Token，直接打开即可使用。

**卸载：**

```bash
./uninstall.sh          # 停止服务，保留数据
./uninstall.sh --purge  # 停止服务并删除所有数据
```

### 手动部署

如果你需要更多控制，也可以手动操作：

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env — 至少设置 DEPLOY_TOKEN

# 2. 构建并启动
docker compose up --build -d
```

The app will be available at `http://localhost:8080`.

### 界面语言

Web 控制台支持中文和英文。首次访问时会根据浏览器语言自动选择，也可以通过右上角切换按钮手动切换；选择会保存在浏览器 Cookie 中。

### 可选域名与 HTTPS

内网环境可以继续使用 IP 和端口访问，例如 `http://192.168.1.10:8080`。公网环境可以启用 Caddy 自动 HTTPS：

```dotenv
PUBLIC_BASE_URL=https://drop.example.com
DOMAIN_MODE=platform
PUBLIC_DOMAIN=drop.example.com
NGINX_BIND=0.0.0.0
```

然后确保 `drop.example.com` 的 DNS A/AAAA 记录指向服务器，并执行：

```bash
docker compose --profile domain up --build -d
```

Caddy 会监听 80/443 并自动申请、续期证书；原有 `/s/{deploymentId}/` 路径和 `http://服务器IP:8080` 访问仍然保留。`DOMAIN_MODE=disabled` 时不会启动 Caddy，也不会要求域名或 HTTPS。

### 构建源配置

默认使用 Docker Hub、npm 官方源和 PyPI 官方源。需要使用国内镜像时，在 `.env` 中配置：

```dotenv
IMAGE_REGISTRY=docker.m.daocloud.io/library/
NPM_REGISTRY=https://registry.npmmirror.com
PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

`IMAGE_REGISTRY` 必须包含末尾的 `/`；留空时会使用官方基础镜像。三个配置彼此独立，可以只切换其中一个源。

生产环境的 Web 控制台通过同源服务端代理访问 API，部署 Token 不会下发到浏览器。只有需要让其他站点直接调用 API 时，才配置 `CORS_ORIGINS`，多个来源用逗号分隔。

### 3. Deploy a site

1. Open `http://localhost:8080` in your browser.
2. Drag and drop a `.zip` file **or a folder** containing your static build output.
3. Get an instant live URL.

You can also deploy via the API:

**Zip upload:**

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_DEPLOY_TOKEN" \
  -F "file=@dist.zip" \
  -F "name=My Site" \
  http://localhost:8080/api/deploy
```

首次上传可以通过 `name` 创建项目；继续上传到已有项目时传入 `project_id`，系统会自动生成下一个版本：

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_DEPLOY_TOKEN" \
  -F "file=@dist-v2.zip" \
  -F "project_id=prj_xxx" \
  http://localhost:8080/api/deploy
```

**Folder upload** (multiple files with relative paths):

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_DEPLOY_TOKEN" \
  -F "files=@dist/index.html;filename=index.html" \
  -F "files=@dist/style.css;filename=style.css" \
  -F "files=@dist/assets/app.js;filename=assets/app.js" \
  -F "name=My Site" \
  http://localhost:8080/api/deploy-folder
```

**Deploy from GitHub:**

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_DEPLOY_TOKEN" \
  -F "repository=https://github.com/owner/repository" \
  -F "ref=main" \
  -F "project_id=prj_xxx" \
  http://localhost:8080/api/github/deploy
```

## API Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/health` | Health check | No |
| GET | `/api/projects` | List projects and current versions | Yes |
| GET | `/api/projects/{id}/deployments` | List project versions | Yes |
| POST | `/api/deploy` | Upload and deploy a `.zip` | Yes |
| POST | `/api/deploy-folder` | Upload and deploy a folder (multiple files) | Yes |
| GET | `/api/deployments` | List deployments (paginated) | Yes |
| GET | `/api/deployments/{id}` | Get deployment details | Yes |
| DELETE | `/api/deployments/{id}` | Delete a deployment | Yes |
| POST | `/api/projects/{id}/rollback/{version}` | Switch the stable project version | Yes |
| POST | `/api/projects/{id}/domains` | Add a custom domain and return TXT challenge | Yes |
| GET | `/api/projects/{id}/domains` | List project domains | Yes |
| POST | `/api/domains/{id}/verify` | Verify a custom domain | Yes |
| DELETE | `/api/domains/{id}` | Remove a custom domain | Yes |
| POST | `/api/github/deploy` | Download and deploy a GitHub repository | Yes |

Auth: `Authorization: Bearer <DEPLOY_TOKEN>`

## Development

### Prerequisites

- Node.js 20+ and pnpm 9
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose (for full-stack testing)

### Local development

```bash
# Install JS dependencies
pnpm install

# Start FastAPI (terminal 1)
cd apps/api
uv sync
DATA_DIR=/tmp/staticdrop-dev DEPLOY_TOKEN=dev-token uv run uvicorn app.main:app --reload --port 8000

# Start Next.js (terminal 2)
cd apps/web
API_URL=http://localhost:8000 DEPLOY_TOKEN=dev-token pnpm dev
```

## Limits (defaults, overridable via env)

| Limit | Default |
|---|---|
| Max zip size | 100 MB |
| Max total uncompressed | 500 MB |
| Max single file | 50 MB |
| Max file count | 5,000 |
| Max deployed storage | 5 GB |
| Required free-space reserve | 64 MB |
| Versions kept per project | 10 |
| Required | `index.html` in zip |

Blocked file types: `.php`, `.exe`, `.sh`, `.py`, `.jar`, `.dll`, `.so`, `.bat`, `.env`, and more (see `apps/api/app/config.py`).

## Roadmap (post-MVP)

- [x] Multi-user support (`AUTH_MODE=users`)
- [x] Platform subdomains (`project-slug.PUBLIC_DOMAIN`)
- [x] Custom domains with DNS verification and optional Caddy HTTPS
- [x] GitHub integration
- [x] Auto-cleanup of old deployments
- [x] Deployment previews / rollbacks
- [ ] GitHub webhook-based automatic redeploys
