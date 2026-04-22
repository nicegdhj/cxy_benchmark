#!/bin/bash
set -e

# ── Score Platform 本地一键启动脚本 ─────────────────────────────────
# 用法: ./start-local.sh [docker-compose up 的额外参数，如 -d]
# ──────────────────────────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
export WORKSPACE_DIR="$PROJECT_DIR/workspace"
export BACKEND_DATA_DIR="$PROJECT_DIR/backend/backend_data"
export CODE_DIR="$PROJECT_DIR"

echo "========================================"
echo "  Score Platform 本地启动"
echo "========================================"
echo ""
echo "项目目录: $PROJECT_DIR"
echo "Workspace:  $WORKSPACE_DIR"
echo "Backend数据: $BACKEND_DATA_DIR"
echo ""

# ── 创建必要目录 ───────────────────────────────────────────────────
mkdir -p "$WORKSPACE_DIR"/{data,outputs,code}
mkdir -p "$BACKEND_DATA_DIR"/{envs,logs}

# ── 将 ais_bench 需要的代码文件复制到 workspace/code ──────────────
#（后端通过 docker run -v 将这些文件挂载到 ais_bench 容器）
cp -n "$CODE_DIR/eval_entry.py" "$WORKSPACE_DIR/code/" 2>/dev/null || true
cp -n "$CODE_DIR/eval_judge.py" "$WORKSPACE_DIR/code/" 2>/dev/null || true
cp -rn "$CODE_DIR/scripts" "$WORKSPACE_DIR/code/" 2>/dev/null || true
cp -n "$CODE_DIR/setup.py" "$WORKSPACE_DIR/code/" 2>/dev/null || true
cp -n "$CODE_DIR/README.md" "$WORKSPACE_DIR/code/" 2>/dev/null || true

# ── 构建 ais_bench 镜像（如果尚未构建）─────────────────────────────
if ! docker image inspect benchmark-eval:latest >/dev/null 2>&1; then
    echo "[1/2] 构建 ais_bench 计算镜像 (benchmark-eval:latest)..."
    docker build -t benchmark-eval:latest "$PROJECT_DIR"
    echo "✅ ais_bench 镜像构建完成"
else
    echo "[1/2] ais_bench 镜像已存在，跳过构建"
fi

# ── 启动 score-front + score-backend ─────────────────────────────
echo ""
echo "[2/2] 启动 score-front (http://localhost:80) + score-backend (http://localhost:8080)..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" up --build "$@"
