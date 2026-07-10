#!/usr/bin/env bash
#
# StaticDrop 一键部署脚本
#
# 用法:
#   ./deploy.sh                          # 交互式，提示输入域名
#   ./deploy.sh https://drop.example.com # 直接指定公开 URL
#   ./deploy.sh --local                  # 本地部署 (http://localhost:8080)
#
set -euo pipefail

# ── 颜色 ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}ℹ${NC}  $*"; }
success() { echo -e "${GREEN}✓${NC}  $*"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
error()   { echo -e "${RED}✗${NC}  $*"; exit 1; }

# ── 脚本所在目录（项目根） ───────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        StaticDrop 一键部署                   ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. 检查 Docker ──────────────────────────────────
info "检查 Docker 环境..."

if ! command -v docker &>/dev/null; then
    error "未找到 docker 命令。请先安装 Docker: https://docs.docker.com/get-docker/"
fi

if ! docker info &>/dev/null 2>&1; then
    error "Docker 守护进程未运行。请先启动 Docker。"
fi

# 检查 docker compose (v2)
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    warn "检测到 docker-compose (v1)，建议升级到 Docker Compose v2"
else
    error "未找到 docker compose 命令。请安装 Docker Compose v2。"
fi

success "Docker 环境就绪 ($COMPOSE_CMD)"

# ── 2. 确定公开 URL ─────────────────────────────────
PUBLIC_URL=""

if [[ "${1:-}" == "--local" ]]; then
    PUBLIC_URL="http://localhost:8080"
elif [[ "${1:-}" == http* ]]; then
    PUBLIC_URL="$1"
else
    echo -e "${BOLD}请输入 StaticDrop 的公开访问地址${NC}"
    echo -e "  例如: https://drop.example.com"
    echo -e "  或输入 ${YELLOW}local${NC} 使用 http://localhost:8080"
    echo ""
    read -rp "公开 URL: " input_url

    if [[ "$input_url" == "local" || -z "$input_url" ]]; then
        PUBLIC_URL="http://localhost:8080"
    else
        PUBLIC_URL="$input_url"
    fi
fi

# 去掉尾部斜杠
PUBLIC_URL="${PUBLIC_URL%/}"
success "公开 URL: ${BOLD}${PUBLIC_URL}${NC}"

# ── 3. 生成随机 Token ───────────────────────────────
info "生成部署 Token..."

if [[ -f .env ]]; then
    # 如果已有 .env 且包含 token，复用
    EXISTING_TOKEN=$(grep '^DEPLOY_TOKEN=' .env 2>/dev/null | cut -d'=' -f2- || true)
    if [[ -n "$EXISTING_TOKEN" && "$EXISTING_TOKEN" != "change-me-to-a-random-string" ]]; then
        DEPLOY_TOKEN="$EXISTING_TOKEN"
        success "复用已有 Token: ${DEPLOY_TOKEN:0:8}..."
    else
        DEPLOY_TOKEN=$(openssl rand -hex 24 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(24))")
        success "生成新 Token: ${BOLD}${DEPLOY_TOKEN}${NC}"
    fi
else
    DEPLOY_TOKEN=$(openssl rand -hex 24 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(24))")
    success "生成 Token: ${BOLD}${DEPLOY_TOKEN}${NC}"
fi

# 复用已有构建源配置；未配置时默认使用官方源。
IMAGE_REGISTRY="$(grep '^IMAGE_REGISTRY=' .env 2>/dev/null | cut -d'=' -f2- || true)"
NPM_REGISTRY="$(grep '^NPM_REGISTRY=' .env 2>/dev/null | cut -d'=' -f2- || true)"
PYPI_INDEX_URL="$(grep '^PYPI_INDEX_URL=' .env 2>/dev/null | cut -d'=' -f2- || true)"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmjs.org}"
PYPI_INDEX_URL="${PYPI_INDEX_URL:-https://pypi.org/simple}"

# ── 4. 写入 .env ────────────────────────────────────
info "写入配置文件 .env..."

# 从 URL 提取端口号（如果有）
PORT="8080"
if [[ "$PUBLIC_URL" =~ :([0-9]+)$ ]]; then
    PORT="${BASH_REMATCH[1]}"
fi

cat > .env <<EOF
# ─────────────────────────────────────
# StaticDrop 配置 (由 deploy.sh 生成)
# 生成时间: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# ─────────────────────────────────────

# 公开访问地址
PUBLIC_BASE_URL=${PUBLIC_URL}

# 直接跨域调用 API 的来源（Web 控制台不需要）
CORS_ORIGINS=

# 部署 Token (用于 API 鉴权)
DEPLOY_TOKEN=${DEPLOY_TOKEN}

# 构建源（IMAGE_REGISTRY 留空表示 Docker Hub）
IMAGE_REGISTRY=${IMAGE_REGISTRY}
NPM_REGISTRY=${NPM_REGISTRY}
PYPI_INDEX_URL=${PYPI_INDEX_URL}

# 宿主机端口 (Nginx 映射)
PORT=${PORT}

# 文件限制 (字节)
MAX_ZIP_SIZE=104857600
MAX_TOTAL_SIZE=524288000
MAX_FILE_SIZE=52428800
MAX_FILE_COUNT=5000
MAX_STORAGE_SIZE=5368709120
MIN_FREE_SPACE=67108864
EOF

success ".env 已写入"

# ── 5. 构建 Docker 镜像 ─────────────────────────────
echo ""
info "构建 Docker 镜像（首次可能需要几分钟）..."
echo ""

if ! $COMPOSE_CMD build 2>&1; then
    error "Docker 镜像构建失败。请检查上方错误信息。"
fi

success "镜像构建完成"

# ── 6. 启动服务 ─────────────────────────────────────
echo ""
info "启动服务..."

# 如果已有旧容器在运行，先停止
if $COMPOSE_CMD ps --services --filter "status=running" 2>/dev/null | grep -q .; then
    warn "检测到已有运行中的容器，正在停止..."
    $COMPOSE_CMD down 2>&1
fi

$COMPOSE_CMD up -d 2>&1

echo ""
info "等待服务健康检查..."

# 等待 API 健康
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -sf "${PUBLIC_URL}/api/health" >/dev/null 2>&1 || \
       curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1; then
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -n "."
done
echo ""

if [ $WAITED -ge $MAX_WAIT ]; then
    warn "服务健康检查超时，查看日志: $COMPOSE_CMD logs"
else
    success "服务已启动并通过健康检查"
fi

# ── 7. 验证 ─────────────────────────────────────────
echo ""
info "验证部署..."

# 测试 health
HEALTH=$(curl -sf "http://localhost:${PORT}/api/health" 2>/dev/null || echo "")
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    success "API 健康检查: OK"
else
    warn "API 健康检查未通过（可能需要更多时间启动）"
fi

# 测试 Web 控制台
WEB_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/" 2>/dev/null || echo "000")
if [ "$WEB_STATUS" = "200" ]; then
    success "Web 控制台: OK"
else
    warn "Web 控制台未就绪 (HTTP $WEB_STATUS)"
fi

# ── 8. 输出部署信息 ─────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        🎉 部署完成!                          ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Web 控制台:${NC}  ${PUBLIC_URL}"
echo -e "  ${BOLD}API 地址:${NC}    ${PUBLIC_URL}/api"
echo -e "  ${BOLD}部署 Token:${NC}  ${DEPLOY_TOKEN}"
echo ""
echo -e "  ${BOLD}常用命令:${NC}"
echo -e "    查看日志:   ${BLUE}${COMPOSE_CMD} logs -f${NC}"
echo -e "    查看状态:   ${BLUE}${COMPOSE_CMD} ps${NC}"
echo -e "    停止服务:   ${BLUE}${COMPOSE_CMD} down${NC}"
echo -e "    重启服务:   ${BLUE}${COMPOSE_CMD} restart${NC}"
echo -e "    更新部署:   ${BLUE}git pull && ./deploy.sh${NC}"
echo ""
echo -e "  ${BOLD}API 示例:${NC}"
echo -e "    ${BLUE}curl -X POST \\${NC}"
echo -e "      ${BLUE}-H \"Authorization: Bearer ${DEPLOY_TOKEN}\" \\${NC}"
echo -e "      ${BLUE}-F \"file=@dist.zip\" \\${NC}"
echo -e "      ${BLUE}${PUBLIC_URL}/api/deploy${NC}"
echo ""

# 如果不是 localhost，提示 HTTPS
if [[ "$PUBLIC_URL" == http://* && "$PUBLIC_URL" != *"localhost"* ]]; then
    warn "当前使用 HTTP。建议在前面加一层 Nginx/Caddy 反向代理配置 HTTPS。"
    echo -e "  如果用 Caddy，添加以下配置即可自动获取 HTTPS 证书:"
    echo -e ""
    echo -e "  ${BLUE}drop.example.com {${NC}"
    echo -e "  ${BLUE}  reverse_proxy localhost:${PORT}${NC}"
    echo -e "  ${BLUE}}${NC}"
    echo ""
fi

echo -e "${GREEN}完成!${NC} 打开 ${BOLD}${PUBLIC_URL}${NC} 开始使用。"
