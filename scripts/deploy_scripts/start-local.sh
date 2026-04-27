#!/bin/bash
set -e

# ── Score Platform 本地一键启动脚本 ─────────────────────────────────
# 用法: bash scripts/deploy_scripts/start-local.sh [-d] [其他 docker-compose 参数]
# ──────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export WORKSPACE_DIR="$PROJECT_DIR/workspace"
export BACKEND_DATA_DIR="$PROJECT_DIR/backend/backend_data"

echo "========================================"
echo "  Score Platform 本地启动"
echo "========================================"
echo ""
echo "项目目录:    $PROJECT_DIR"
echo "Workspace:   $WORKSPACE_DIR"
echo "Backend数据: $BACKEND_DATA_DIR"
echo ""

# ── 创建必要目录 ───────────────────────────────────────────────────
mkdir -p "$WORKSPACE_DIR"/{data,outputs,code}
mkdir -p "$BACKEND_DATA_DIR"/{envs,logs}

# ── 将 ais_bench 需要的代码文件软链到项目根目录 ──────────────────────
#（符号链接使容器始终挂载最新源文件，无需手动同步）
ln -sf "$PROJECT_DIR/eval_entry.py"  "$WORKSPACE_DIR/code/eval_entry.py"
ln -sf "$PROJECT_DIR/eval_judge.py"  "$WORKSPACE_DIR/code/eval_judge.py"
rm -rf "$WORKSPACE_DIR/code/scripts" && ln -sf "$PROJECT_DIR/scripts" "$WORKSPACE_DIR/code/scripts"
ln -sf "$PROJECT_DIR/setup.py"       "$WORKSPACE_DIR/code/setup.py"
ln -sf "$PROJECT_DIR/README.md"      "$WORKSPACE_DIR/code/README.md"

# ── 构建 ais_bench 镜像（如果尚未构建）─────────────────────────────
# 避免 desktop-linux 等 context 导致 buildx 报错
if docker context ls >/dev/null 2>&1; then
    docker context use default >/dev/null 2>&1 || true
fi

if ! docker image inspect benchmark-eval:latest >/dev/null 2>&1; then
    echo "[1/2] 构建 ais_bench 计算镜像 (benchmark-eval:latest)..."
    BUILDX_BUILDER=default docker build -t benchmark-eval:latest \
        -f "$PROJECT_DIR/deploy_docker/ais_bench/Dockerfile" \
        "$PROJECT_DIR"
    echo "✅ ais_bench 镜像构建完成"
else
    echo "[1/2] ais_bench 镜像已存在，跳过构建"
fi

# ── 启动 score-front + score-backend ─────────────────────────────
echo ""
echo "[2/2] 启动 score-front (http://localhost:80) + score-backend (http://localhost:8080)..."

# 用 docker compose images 判断是否已有构建产物
BUILT=$(docker compose -f "$PROJECT_DIR/deploy_docker/docker-compose.yml" images -q 2>/dev/null | wc -l | tr -d ' ')

if [ "$BUILT" -ge 2 ]; then
    echo "      镜像已存在，跳过构建直接启动..."
    docker compose -f "$PROJECT_DIR/deploy_docker/docker-compose.yml" up "$@"
else
    echo "      镜像不存在，使用本地 builder 构建..."
    BUILDX_BUILDER=default \
        docker compose -f "$PROJECT_DIR/deploy_docker/docker-compose.yml" up --build "$@"
fi
