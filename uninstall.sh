#!/usr/bin/env bash
#
# StaticDrop 卸载脚本 — 停止服务并清理
#
# 用法:
#   ./uninstall.sh          # 停止服务，保留数据
#   ./uninstall.sh --purge  # 停止服务并删除所有数据（部署文件 + 数据库）
#
set -euo pipefail

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检测 docker compose
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    error "未找到 docker compose 命令"
fi

echo ""
echo -e "${BOLD}StaticDrop 卸载${NC}"
echo ""

PURGE=false
if [[ "${1:-}" == "--purge" ]]; then
    PURGE=true
fi

if $PURGE; then
    warn "${BOLD}--purge 模式：将删除所有部署文件和数据库！${NC}"
    echo -e "  此操作不可逆。"
    echo ""
    read -rp "确认删除所有数据？输入 yes 继续: " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "已取消。"
        exit 0
    fi
fi

# 停止并移除容器
info "停止服务..."
$COMPOSE_CMD --profile domain down 2>&1
success "服务已停止"

# 清理数据
if $PURGE; then
    echo ""
    info "清理 Docker volume..."
    $COMPOSE_CMD --profile domain down -v 2>&1
    success "数据已删除"

    info "清理本地 data 目录..."
    if [ -d "data" ]; then
        rm -rf data/
        success "data/ 目录已删除"
    fi
fi

echo ""
if $PURGE; then
    success "${BOLD}StaticDrop 已完全卸载（含数据）${NC}"
else
    success "${BOLD}StaticDrop 服务已停止${NC}"
    echo -e "  数据已保留。重新启动: ${BLUE}./deploy.sh${NC}"
    echo -e "  彻底清理数据: ${BLUE}./uninstall.sh --purge${NC}"
fi
echo ""
