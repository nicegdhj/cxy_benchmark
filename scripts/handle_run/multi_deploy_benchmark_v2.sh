#!/usr/bin/env bash
# ==============================================================================
# 多容器批量部署执行脚本 v2 (私域机轻量部署)
#
# 与 v1 的区别：
#   - 不再为每个目标重复解压完整压缩包
#   - 共享一份 data/、code/、镜像，每个目标只创建独立的 .env + outputs/ + logs/
#   - TARGETS 使用相对目录名（在 DEPLOY_ROOT 下自动创建）
#
# 前置条件：
#   在当前目录（或指定目录）下已有一份解压好的 eval_workspace_*，包含：
#     eval_workspace_*/
#     ├── .env                  # 作为模板
#     ├── data/                 # 共享数据（符号链接到各目标）
#     ├── code/                 # 共享代码
#     ├── run_mixed_benchmark.sh
#     └── benchmark-eval.tar.gz # 可选，镜像离线包
#
# 使用方式：
#   bash multi_deploy_benchmark_v2.sh
# ==============================================================================

set -euo pipefail

# ==========================================
# 用户自定义变量区
# ==========================================

# 1. 基础工作区：已解压的 eval_workspace 目录（留空则自动查找当前目录下的 eval_workspace_*）
BASE_WORKSPACE=""

# 2. 部署根目录：各目标工作区在此目录下创建（默认当前目录）
DEPLOY_ROOT="$(pwd)"

# 3. 注入到各工作区 .env 的模型服务 IP（留空则不覆盖原有值）
LOCAL_HOST_IP=""

# 4. 定义目标：目录名:端口号（目录会在 DEPLOY_ROOT 下自动创建）
TARGETS=(
    "pt14_sf0:10052"
    "pt15_sf0:10053"
    "pt16_sf0:10054"
    "pt17_sf0:10055"
    "pt18_sf0:10056"
    "pt19_sf0:10057"
)

# ==========================================

# ── 自动定位基础工作区 ──────────────────────────────────────────────────
if [ -z "$BASE_WORKSPACE" ]; then
    # 在当前目录下查找第一个 eval_workspace_* 目录
    BASE_WORKSPACE=$(find "$DEPLOY_ROOT" -maxdepth 1 -type d -name "eval_workspace_*" | sort | tail -n 1)
    if [ -z "$BASE_WORKSPACE" ]; then
        echo "❌ 在 $DEPLOY_ROOT 下未找到 eval_workspace_* 目录"
        echo "   请先解压一份，或设置 BASE_WORKSPACE 变量指向已有目录"
        exit 1
    fi
fi

if [ ! -f "$BASE_WORKSPACE/.env" ]; then
    echo "❌ $BASE_WORKSPACE 不是有效的工作区（缺少 .env）"
    exit 1
fi

echo "📂 基础工作区: $BASE_WORKSPACE"
echo "📂 部署根目录: $DEPLOY_ROOT"

# 共享资源路径
SHARED_DATA="$BASE_WORKSPACE/data"
SHARED_CODE="$BASE_WORKSPACE/code"
BENCHMARK_SCRIPT="$BASE_WORKSPACE/run_mixed_benchmark.sh"
IMAGE_TAR="$BASE_WORKSPACE/benchmark-eval.tar.gz"

for res in "$SHARED_DATA" "$SHARED_CODE" "$BENCHMARK_SCRIPT"; do
    if [ ! -e "$res" ]; then
        echo "❌ 缺少共享资源: $res"
        exit 1
    fi
done

IMAGE_TAR_FLAG=""
if [ -f "$IMAGE_TAR" ]; then
    IMAGE_TAR_FLAG="--image-tar $IMAGE_TAR"
fi

# ── 结果记录文件 ──────────────────────────────────────────────────────────
BEIJING_DATE=$(TZ='Asia/Shanghai' date '+%Y%m%d')
RESULT_FILE="$DEPLOY_ROOT/model_eval_res_${BEIJING_DATE}.txt"

if [ ! -f "$RESULT_FILE" ]; then
    printf '%-19s | %-30s | %-8s | %s\n' \
        "日期" "工作区" "端口" "容器ID" \
        >> "$RESULT_FILE"
    printf '%s\n' "$(printf '%0.s-' {1..80})" >> "$RESULT_FILE"
fi

# ── 逐个目标部署 ──────────────────────────────────────────────────────────
for TARGET in "${TARGETS[@]}"; do
    NAME="${TARGET%%:*}"
    PORT="${TARGET##*:}"
    WORKSPACE="$DEPLOY_ROOT/$NAME"

    echo "================================================="
    echo "🚀 部署: $NAME (端口: $PORT)"

    # 创建目标工作区目录结构
    mkdir -p "$WORKSPACE/outputs" "$WORKSPACE/logs"

    # 符号链接共享的 data 目录（已存在则跳过）
    if [ ! -e "$WORKSPACE/data" ]; then
        ln -s "$(cd "$SHARED_DATA" && pwd)" "$WORKSPACE/data"
        echo "🔗 data -> $SHARED_DATA"
    fi

    # 复制 .env 并修改端口（每个目标独立一份）
    cp "$BASE_WORKSPACE/.env" "$WORKSPACE/.env"
    sed -i "s/^LOCAL_HOST_PORT=.*/LOCAL_HOST_PORT=${PORT}/g" "$WORKSPACE/.env"
    if [ -n "$LOCAL_HOST_IP" ]; then
        sed -i "s/^LOCAL_HOST_IP=.*/LOCAL_HOST_IP=${LOCAL_HOST_IP}/g" "$WORKSPACE/.env"
    fi
    echo "✅ .env: LOCAL_HOST_PORT=$PORT${LOCAL_HOST_IP:+, LOCAL_HOST_IP=$LOCAL_HOST_IP}"

    # 启动评测
    if [ -f "$BENCHMARK_SCRIPT" ]; then
        bash "$BENCHMARK_SCRIPT" \
            --workspace "$WORKSPACE" \
            --code-dir "$SHARED_CODE" \
            $IMAGE_TAR_FLAG

        sleep 5
        CONTAINER_ID=$(docker ps --latest --filter ancestor=benchmark-eval:latest --format "{{.ID}}" 2>/dev/null || echo "-")
        echo "🐳 容器 ID: $CONTAINER_ID"

        printf '%s | %-30s | %-8s | %s\n' \
            "$BEIJING_DATE" "$NAME" "$PORT" "$CONTAINER_ID" \
            >> "$RESULT_FILE"
    else
        echo "❌ 找不到启动脚本: $BENCHMARK_SCRIPT"
        printf '%s | %-30s | %-8s | %s\n' \
            "$BEIJING_DATE" "$NAME" "$PORT" "FAILED(no script)" \
            >> "$RESULT_FILE"
    fi

    echo "================================================="
    echo ""
done

echo "🎉 所有容器部署已触发完毕！"
echo "👉 查看日志: tail -f $DEPLOY_ROOT/<目标名>/logs/mixed_eval_*.log"
echo "📄 部署记录: $RESULT_FILE"
