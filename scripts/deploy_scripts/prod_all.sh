#!/usr/bin/env bash
# ==============================================================================
# prod_all.sh —— Score Platform 私域全量打包脚本
#
# 功能：
#   1. 构建三个 Docker 镜像：
#      - benchmark-eval:latest   (ais_bench 评测计算容器)
#      - score-backend:latest    (FastAPI 后端服务)
#      - score-frontend:latest   (React + nginx 前端)
#   2. 将三个镜像导出为单一离线包 score-platform-images.tar.gz
#   3. 生成生产环境 docker-compose.prod.yml（使用镜像名，不做 build）
#   4. 打包为 score_platform_<timestamp>.tar.gz，放入 outputs/
#
# 用法：
#   bash scripts/deploy_scripts/prod_all.sh
#
# 前提：
#   - 已安装 Docker，且 Docker daemon 正在运行
#   - 项目根目录下有 deploy_docker/、backend/、frontend/ 等目录
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
PACKAGE_NAME="score_platform_${TIMESTAMP}"
OUTPUTS_DIR="$PROJECT_ROOT/outputs"
TMP_DIR="/tmp/${PACKAGE_NAME}"
IMAGES_FILE="score-platform-images.tar.gz"

echo "======================================================"
echo "  Score Platform 私域全量打包"
echo "  输出目录: $OUTPUTS_DIR/${PACKAGE_NAME}.tar.gz"
echo "======================================================"

mkdir -p "$OUTPUTS_DIR"

# ── Step 1: 检查必要文件 ──────────────────────────────────────────
echo ""
echo "▶ [1/5] 检查依赖文件..."

[ -f "$PROJECT_ROOT/deploy_docker/ais_bench/Dockerfile" ] || { echo "❌ 缺少 deploy_docker/ais_bench/Dockerfile"; exit 1; }
[ -f "$PROJECT_ROOT/deploy_docker/backend/Dockerfile" ]   || { echo "❌ 缺少 deploy_docker/backend/Dockerfile"; exit 1; }
[ -f "$PROJECT_ROOT/deploy_docker/frontend/Dockerfile" ]  || { echo "❌ 缺少 deploy_docker/frontend/Dockerfile"; exit 1; }
[ -f "$PROJECT_ROOT/docker-compose.yml" ]                 || { echo "❌ 缺少 docker-compose.yml"; exit 1; }
echo "  ✅ 文件检查通过"

# ── Step 2: 构建三个镜像 ──────────────────────────────────────────
echo ""
echo "▶ [2/5] 构建 Docker 镜像（可能需要几分钟）..."

echo "  [2/5a] 构建 benchmark-eval:latest ..."
docker build -t benchmark-eval:latest \
    -f "$PROJECT_ROOT/deploy_docker/ais_bench/Dockerfile" \
    "$PROJECT_ROOT"
echo "  ✅ benchmark-eval:latest"

echo "  [2/5b] 构建 score-backend:latest ..."
docker build -t score-backend:latest \
    -f "$PROJECT_ROOT/deploy_docker/backend/Dockerfile" \
    "$PROJECT_ROOT"
echo "  ✅ score-backend:latest"

echo "  [2/5c] 构建 score-frontend:latest ..."
docker build -t score-frontend:latest \
    -f "$PROJECT_ROOT/deploy_docker/frontend/Dockerfile" \
    "$PROJECT_ROOT/frontend"
echo "  ✅ score-frontend:latest"

# ── Step 3: 导出镜像 ──────────────────────────────────────────────
echo ""
echo "▶ [3/5] 导出三个镜像为 ${IMAGES_FILE}（可能需要几分钟）..."

IMAGES_PATH="$OUTPUTS_DIR/$IMAGES_FILE"
docker save benchmark-eval:latest score-backend:latest score-frontend:latest \
    | gzip > "$IMAGES_PATH"
echo "  ✅ 镜像已导出: $IMAGES_PATH ($(du -sh "$IMAGES_PATH" | cut -f1))"

# ── Step 4: 组织部署目录结构 ──────────────────────────────────────
echo ""
echo "▶ [4/5] 组织部署目录结构..."

rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR/score_platform"

# 复制镜像包
cp "$IMAGES_PATH" "$TMP_DIR/score_platform/$IMAGES_FILE"

# 生成生产环境 docker-compose.prod.yml
cat > "$TMP_DIR/score_platform/docker-compose.prod.yml" << 'COMPOSE_EOF'
# ── Score Platform 生产环境部署 ──────────────────────────────────
# 用法：
#   1. 修改下方 WORKSPACE_DIR、BACKEND_DATA_DIR 为服务器实际路径
#   2. docker compose -f docker-compose.prod.yml up -d
# ──────────────────────────────────────────────────────────────────

services:
  score-front:
    image: score-frontend:latest
    container_name: score-front
    ports:
      - "80:80"
    depends_on:
      - score-backend
    networks:
      - score-net

  score-backend:
    image: score-backend:latest
    container_name: score-backend
    ports:
      - "8080:8080"
    volumes:
      # !! 修改为服务器上 workspace 的实际路径（需与容器内路径保持一致）
      - ${WORKSPACE_DIR}:${WORKSPACE_DIR}
      - ${BACKEND_DATA_DIR}:/opt/eval_backend_data
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - EVAL_BACKEND_WORKSPACE_DIR=${WORKSPACE_DIR}
      - EVAL_BACKEND_BACKEND_DATA_DIR=/opt/eval_backend_data
      - EVAL_BACKEND_CODE_DIR=${WORKSPACE_DIR}/code
    networks:
      - score-net

networks:
  score-net:
    driver: bridge
COMPOSE_EOF

# 生成 .env 模板
cat > "$TMP_DIR/score_platform/.env.example" << 'ENV_EOF'
# Score Platform 生产环境配置
# 复制本文件为 .env 并填写实际值

# Workspace 路径（宿主机绝对路径，容器内外保持一致）
WORKSPACE_DIR=/opt/eval_workspace
BACKEND_DATA_DIR=/opt/eval_backend_data
ENV_EOF

# 写部署说明
cat > "$TMP_DIR/score_platform/README.txt" << 'README_EOF'
=== Score Platform 私域部署说明 ===

目录结构：
  score_platform/
  ├── score-platform-images.tar.gz   # 三个服务的 Docker 镜像离线包
  ├── docker-compose.prod.yml        # 生产环境 Compose 配置
  ├── .env.example                   # 环境变量模板
  └── README.txt                     # 本文件

部署步骤：

1. 导入 Docker 镜像（包含 benchmark-eval、score-backend、score-frontend）：
   docker load < score-platform-images.tar.gz

2. 准备配置文件：
   cp .env.example .env
   vi .env   # 填写 WORKSPACE_DIR、BACKEND_DATA_DIR 实际路径

3. 创建 workspace 目录结构：
   mkdir -p /opt/eval_workspace/{data,outputs,code}
   mkdir -p /opt/eval_backend_data/{envs,logs}

4. 启动所有服务：
   docker compose -f docker-compose.prod.yml --env-file .env up -d

5. 访问：
   前端：http://<服务器IP>:80
   后端：http://<服务器IP>:8080

6. 查看日志：
   docker compose -f docker-compose.prod.yml logs -f

注意：
  - benchmark-eval 镜像由后端动态启动，无需在 compose 中声明
  - WORKSPACE_DIR 路径在宿主机和容器内必须一致（docker run -v 的要求）
  - 更新服务时重新 load 镜像包，然后 docker compose up -d 即可
README_EOF

echo "  ✅ 部署目录已准备好"

# ── Step 5: 压缩打包 ──────────────────────────────────────────────
echo ""
echo "▶ [5/5] 压缩打包..."

FINAL_PACKAGE="$OUTPUTS_DIR/${PACKAGE_NAME}.tar.gz"
tar -czf "$FINAL_PACKAGE" -C "/tmp" "${PACKAGE_NAME}/score_platform"
rm -rf "$TMP_DIR"

echo ""
echo "======================================================"
echo "  ✅ 打包完成！"
echo "  📦 $(du -sh "$FINAL_PACKAGE") → $FINAL_PACKAGE"
echo ""
echo "  传输到私域服务器："
echo "    scp $FINAL_PACKAGE user@server:/opt/"
echo ""
echo "  服务器上执行："
echo "    cd /opt && tar -xzf ${PACKAGE_NAME}.tar.gz"
echo "    cd score_platform"
echo "    docker load < score-platform-images.tar.gz"
echo "    cp .env.example .env && vi .env"
echo "    docker compose -f docker-compose.prod.yml --env-file .env up -d"
echo "======================================================"
