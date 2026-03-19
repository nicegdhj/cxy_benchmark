#!/bin/bash
# ==============================================================================
# run_eval_container.sh —— 启动常驻评测容器
#
# 用法:
#   bash run_eval_container.sh [选项]
#
# 参数:
#   --workspace   工作目录（默认当前目录）
#   --name        容器名称（默认 eval-worker）
#   --image-tag   镜像 tag（默认 benchmark-eval:latest）
#   --image-tar   镜像离线包路径，镜像不存在时自动 load
#   -v / --volume 额外挂载目录，可多次指定（格式同 docker -v）
#
# 示例:
#   bash run_eval_container.sh --workspace /data/eval --name my-eval
#   bash run_eval_container.sh -v /data/fmt:/app/fmt -v /data/extra:/app/extra
#
# 启动后:
#   docker exec -it eval-worker bash        # 进入容器
#   python eval_entry.py --task-id round_1 --model-config local_qwen --tasks 1 34 36
#   python eval_judge.py --infer-task round_1
# ==============================================================================

set -euo pipefail

# ── 默认参数 ─────────────────────────────────────────────────────────
WORKSPACE="$(pwd)"
CONTAINER_NAME="eval-worker"
IMAGE_TAG="benchmark-eval:latest"
IMAGE_TAR=""
EXTRA_VOLUMES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace)  WORKSPACE="$2";       shift 2 ;;
        --name)       CONTAINER_NAME="$2";  shift 2 ;;
        --image-tag)  IMAGE_TAG="$2";       shift 2 ;;
        --image-tar)  IMAGE_TAR="$2";       shift 2 ;;
        -v|--volume)  EXTRA_VOLUMES+=("-v" "$2"); shift 2 ;;
        -h|--help)    sed -n '3,17p' "$0" | sed 's/^# //;s/^#//'; exit 0 ;;
        *)            echo "❌ 未知参数: $1（使用 --help 查看用法）"; exit 1 ;;
    esac
done

# ── 路径推导 ─────────────────────────────────────────────────────────
ENV_FILE="${WORKSPACE}/.env"
DATA_DIR="${WORKSPACE}/data"
OUTPUT_DIR="${WORKSPACE}/outputs"
CODE_DIR="${WORKSPACE}/code"

# ── 前置校验 ─────────────────────────────────────────────────────────
[ -f "${ENV_FILE}" ]              || { echo "❌ 缺少 ${ENV_FILE}"; exit 1; }
[ -d "${DATA_DIR}" ]              || { echo "❌ 缺少 ${DATA_DIR}"; exit 1; }
[ -f "${CODE_DIR}/eval_entry.py" ] || { echo "❌ 缺少 ${CODE_DIR}/eval_entry.py"; exit 1; }
[ -f "${CODE_DIR}/eval_judge.py" ] || { echo "❌ 缺少 ${CODE_DIR}/eval_judge.py"; exit 1; }

mkdir -p "${OUTPUT_DIR}"

# ── Docker 镜像检测 & 自动 load ──────────────────────────────────────
if docker image inspect "${IMAGE_TAG}" > /dev/null 2>&1; then
    echo "✅ 镜像已存在: ${IMAGE_TAG}"
elif [ -n "${IMAGE_TAR}" ]; then
    [ -f "${IMAGE_TAR}" ] || { echo "❌ 找不到镜像包: ${IMAGE_TAR}"; exit 1; }
    echo "📦 正在 load 镜像: ${IMAGE_TAR} ..."
    docker load < "${IMAGE_TAR}"
    echo "✅ 镜像 load 成功"
else
    echo "❌ 镜像 ${IMAGE_TAG} 不存在，且未指定 --image-tar"
    exit 1
fi

# ── 检查同名容器 ─────────────────────────────────────────────────────
if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
    STATE=$(docker inspect -f '{{.State.Running}}' "${CONTAINER_NAME}")
    if [ "$STATE" = "true" ]; then
        echo "✅ 容器 ${CONTAINER_NAME} 已在运行中"
        echo ""
        echo "  进入容器: docker exec -it ${CONTAINER_NAME} bash"
        exit 0
    else
        echo "🔄 发现已停止的同名容器，正在移除..."
        docker rm "${CONTAINER_NAME}"
    fi
fi

# ── 启动常驻容器 ─────────────────────────────────────────────────────
echo "🚀 启动常驻容器: ${CONTAINER_NAME}"
echo "   工作目录: ${WORKSPACE}"

docker run -itd \
    --name "${CONTAINER_NAME}" \
    --env-file "${ENV_FILE}" \
    -e LOCAL_CONCURRENCY=20 \
    --memory=128g \
    --memory-swap=128g \
    --shm-size=16g \
    -v "/dpc/hejia/only_eval/res_demo/fmt:/app/fmt" \
    -v "${DATA_DIR}:/app/data" \
    -v "${OUTPUT_DIR}:/app/outputs" \
    -v "${CODE_DIR}/eval_entry.py:/app/eval_entry.py" \
    -v "${CODE_DIR}/eval_judge.py:/app/eval_judge.py" \
    -v "${CODE_DIR}/aggregate_eval_reports.py:/app/aggregate_eval_reports.py" \
    -v "${CODE_DIR}/scripts:/app/scripts" \
    "${EXTRA_VOLUMES[@]}" \
    "${IMAGE_TAG}" \
    bash

echo ""
echo "======================================================"
echo "  ✅ 容器已启动！"
echo ""
echo "  进入容器:  docker exec -it ${CONTAINER_NAME} bash"
echo "  查看状态:  docker ps --filter name=${CONTAINER_NAME}"
echo "  停止容器:  docker stop ${CONTAINER_NAME}"
echo "  重启容器:  docker start ${CONTAINER_NAME}"
echo "  删除容器:  docker rm -f ${CONTAINER_NAME}"
echo ""
echo "  容器内执行推理:"
echo "    python eval_entry.py --task-id round_1 --model-config local_qwen \\"
echo "        --tasks 1 34 36 --generic-datasets ceval_gen_0_shot_str"
echo ""
echo "  容器内执行评测:"
echo "    python eval_judge.py --infer-task round_1"
echo "======================================================"
