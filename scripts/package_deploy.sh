#!/usr/bin/env bash
# ==============================================================================
# package_deploy.sh —— 私域部署打包脚本
#
# 功能：
#   1. 将 Docker 镜像导出为 .tar.gz（如果 outputs/ 下还没有则自动导出）
#   2. 按 deploy.md 目录结构组织文件：
#      eval_workspace/
#      ├── .env                        # API 密钥（需在服务器上修改）
#      ├── data/                       # 评测数据集
#      ├── code/                       # 业务脚本（可直接在服务器上修改）
#      │   ├── eval_entry.py
#      │   └── scripts/
#      ├── run_mixed_benchmark.sh      # 启动脚本
#      └── benchmark-eval.tar.gz      # Docker 镜像离线包
#   3. 最终压缩包放到 outputs/ 目录，方便拷贝到私域服务器
#
# 使用方式：
#   bash scripts/package_deploy.sh
#
# 前提：
#   - Docker 已构建好 benchmark-eval:latest 镜像
#   - 项目根目录下有 data/、.env、eval_entry.py、scripts/、run_mixed_benchmark.sh
# ==============================================================================

set -euo pipefail

# ── 项目根目录（脚本所在目录的上一级）────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

IMAGE_NAME="benchmark-eval:latest"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
PACKAGE_NAME="eval_workspace_${TIMESTAMP}"
OUTPUTS_DIR="$PROJECT_ROOT/outputs"
TMP_DIR="/tmp/${PACKAGE_NAME}"
IMAGE_FILE="benchmark-eval.tar.gz"
IMAGE_PATH="$OUTPUTS_DIR/$IMAGE_FILE"

echo "======================================================"
echo "  私域部署打包脚本"
echo "  打包目录: $OUTPUTS_DIR/${PACKAGE_NAME}.tar.gz"
echo "======================================================"

# ── Step 1: 检查必要文件 ───────────────────────────────────────────────────────
echo ""
echo "▶ [1/4] 检查依赖文件..."

[ -f "$PROJECT_ROOT/.env" ]                   || { echo "❌ 缺少 .env 文件"; exit 1; }
[ -d "$PROJECT_ROOT/data" ]                   || { echo "❌ 缺少 data/ 目录"; exit 1; }
[ -f "$PROJECT_ROOT/eval_entry.py" ]          || { echo "❌ 缺少 eval_entry.py"; exit 1; }
[ -d "$PROJECT_ROOT/scripts" ]                || { echo "❌ 缺少 scripts/ 目录"; exit 1; }
[ -f "$PROJECT_ROOT/run_mixed_benchmark.sh" ] || { echo "❌ 缺少 run_mixed_benchmark.sh"; exit 1; }

mkdir -p "$OUTPUTS_DIR"

# ── Step 2: 导出 Docker 镜像（如果已存在则跳过）────────────────────────────────
echo ""
echo "▶ [2/4] 导出 Docker 镜像..."

if [ -f "$IMAGE_PATH" ]; then
    echo "  ℹ️  镜像文件已存在，跳过导出: $IMAGE_PATH"
else
    echo "  正在导出 $IMAGE_NAME → ${IMAGE_FILE}（可能需要几分钟）..."
    docker save "$IMAGE_NAME" | gzip > "$IMAGE_PATH"
    echo "  ✅ 镜像已导出: $IMAGE_PATH ($(du -sh "$IMAGE_PATH" | cut -f1))"
fi

# ── Step 3: 构建临时目录结构 ────────────────────────────────────────────────────
echo ""
echo "▶ [3/4] 组织部署目录结构..."

rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR/eval_workspace/outputs"
mkdir -p "$TMP_DIR/eval_workspace/code"

# 复制数据集
echo "  复制 data/ ($(du -sh "$PROJECT_ROOT/data" | cut -f1))，请稍候..."
cp -r "$PROJECT_ROOT/data/" "$TMP_DIR/eval_workspace/data/"

# 复制 .env
echo "  复制 .env..."
cp "$PROJECT_ROOT/.env" "$TMP_DIR/eval_workspace/.env"

# 复制业务代码到 code/
echo "  复制 eval_entry.py → code/..."
cp "$PROJECT_ROOT/eval_entry.py" "$TMP_DIR/eval_workspace/code/eval_entry.py"

echo "  复制 scripts/ → code/scripts/..."
cp -r "$PROJECT_ROOT/scripts/" "$TMP_DIR/eval_workspace/code/scripts/"

# 复制启动脚本
echo "  复制 run_mixed_benchmark.sh..."
cp "$PROJECT_ROOT/run_mixed_benchmark.sh" "$TMP_DIR/eval_workspace/run_mixed_benchmark.sh"
chmod +x "$TMP_DIR/eval_workspace/run_mixed_benchmark.sh"

# 复制镜像文件
echo "  复制镜像文件 $IMAGE_FILE..."
cp "$IMAGE_PATH" "$TMP_DIR/eval_workspace/$IMAGE_FILE"

# 写简易部署说明
cat > "$TMP_DIR/eval_workspace/README.txt" << 'EOF'
=== 私域评测环境部署说明 ===

目录结构：
  eval_workspace/
  ├── .env                     # API 密钥（部署前请修改）
  ├── data/                    # 评测数据集
  ├── code/                    # 业务脚本（可直接在服务器上修改，无需重建镜像）
  │   ├── eval_entry.py
  │   └── scripts/
  ├── run_mixed_benchmark.sh   # 启动脚本
  └── benchmark-eval.tar.gz   # Docker 镜像离线包

部署步骤：

1. 导入 Docker 镜像：
   docker load < benchmark-eval.tar.gz

2. 编辑 .env 配置（填写实际 IP / 密钥）：
   vi .env

3. 执行评测（默认读取当前目录下的 code/ 作为脚本目录）：
   bash run_mixed_benchmark.sh --workspace $(pwd)

4. 查看结果：
   outputs/<task-id>/report.md
   outputs/<task-id>/report.json

提示：
  - 修改评测逻辑时直接编辑 code/eval_entry.py，无需重建镜像
  - 重连后查看进度：tail -f logs/mixed_eval_*.log
  - 终止任务：docker stop $(docker ps -q --filter ancestor=benchmark-eval:latest)

详细说明请参考项目 deploy.md。
EOF

# ── Step 4: 压缩打包 ────────────────────────────────────────────────────────────
echo ""
echo "▶ [4/4] 压缩打包..."

FINAL_PACKAGE="$OUTPUTS_DIR/${PACKAGE_NAME}.tar.gz"
tar -czf "$FINAL_PACKAGE" -C "/tmp" "${PACKAGE_NAME}/eval_workspace"

# 清理临时目录
rm -rf "$TMP_DIR"

echo ""
echo "======================================================"
echo "  ✅ 打包完成！"
echo "  📦 $(du -sh "$FINAL_PACKAGE") → $FINAL_PACKAGE"
echo ""
echo "  私域服务器上执行："
echo "  1. scp $FINAL_PACKAGE user@server:/opt/"
echo "  2. cd /opt && tar -xzf ${PACKAGE_NAME}.tar.gz"
echo "  3. cd eval_workspace"
echo "  4. docker load < benchmark-eval.tar.gz"
echo "  5. bash run_mixed_benchmark.sh --workspace \$(pwd)"
echo "======================================================"
