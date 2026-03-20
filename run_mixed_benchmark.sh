#!/bin/bash

# ==============================================================================
# 自动化混合模型评测脚本 (基于 Docker 私域部署)
# 支持 SSH 断开后后台持续运行（nohup 模式）
#
# 用法:
#   bash run_mixed_benchmark.sh [选项]
#
# 参数:
#   --workspace   评测工作目录（默认 /opt/eval_workspace）
#                 目录下须包含 .env / data/ / code/
#   --code-dir    业务代码目录（默认 <workspace>/code）
#                 须包含 eval_entry.py 和 scripts/
#   --image-tar   Docker 镜像 tar 包路径，若镜像不存在则自动 load
#                 （可选，若镜像已存在自动跳过）
#   --image-tag   Docker 镜像 tag（默认 benchmark-eval:latest）
#
# 示例:
#   bash run_mixed_benchmark.sh --workspace /data/eval --image-tar /data/benchmark-eval.tar.gz
# ==============================================================================

# ── 参数解析 ─────────────────────────────────────────────────────────
WORKSPACE="/opt/eval_workspace"   # 默认目录
IMAGE_TAG="benchmark-eval:latest"     # 默认镜像 tag
IMAGE_TAR=""                      # tar 包路径（可选）
CODE_DIR=""                       # 业务代码目录（默认由 workspace 推导）

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace)
            WORKSPACE="$2"
            shift 2
            ;;
        --code-dir)
            CODE_DIR="$2"
            shift 2
            ;;
        --image-tar)
            IMAGE_TAR="$2"
            shift 2
            ;;
        --image-tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -h|--help)
            sed -n '3,20p' "$0" | sed 's/^# //;s/^#//'
            exit 0
            ;;
        *)
            echo "❌ 未知参数: $1（使用 --help 查看用法）"
            exit 1
            ;;
    esac
done

# ── 基于 workspace 推导各子路径 ──────────────────────────────────────
ENV_FILE="${WORKSPACE}/.env"
DATA_DIR="${WORKSPACE}/data"
OUTPUT_DIR="${WORKSPACE}/outputs"
LOG_DIR="${WORKSPACE}/logs"
CODE_DIR="${CODE_DIR:-${WORKSPACE}/code}"   # 未指定则默认 <workspace>/code

TASK_ID="mixed_eval_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/${TASK_ID}.log"

# ── 前置校验 ─────────────────────────────────────────────────────────
if [ ! -f "${ENV_FILE}" ]; then
    echo "❌ 找不到配置文件: ${ENV_FILE}"
    exit 1
fi

if [ ! -f "${CODE_DIR}/eval_entry.py" ]; then
    echo "❌ 找不到业务脚本: ${CODE_DIR}/eval_entry.py"
    echo "   请将 eval_entry.py 放置到 ${CODE_DIR}/ 目录下"
    exit 1
fi

if [ ! -d "${CODE_DIR}/scripts" ]; then
    echo "❌ 找不到 scripts 目录: ${CODE_DIR}/scripts"
    echo "   请将 scripts/ 目录放置到 ${CODE_DIR}/ 下"
    exit 1
fi

# ── Docker 镜像检测 & 自动 load ──────────────────────────────────────
if docker image inspect "${IMAGE_TAG}" > /dev/null 2>&1; then
    echo "✅ Docker 镜像已存在: ${IMAGE_TAG}，跳过 load"
elif [ -n "${IMAGE_TAR}" ]; then
    if [ ! -f "${IMAGE_TAR}" ]; then
        echo "❌ 找不到镜像包: ${IMAGE_TAR}"
        exit 1
    fi
    echo "📦 正在 load Docker 镜像: ${IMAGE_TAR} ..."
    docker load < "${IMAGE_TAR}"
    if [ $? -ne 0 ]; then
        echo "❌ Docker 镜像 load 失败，请检查 tar 包是否完整"
        exit 1
    fi
    echo "✅ 镜像 load 成功: ${IMAGE_TAG}"
else
    echo "❌ 镜像 ${IMAGE_TAG} 不存在，且未指定 --image-tar"
    echo "   请先构建镜像或通过 --image-tar 指定离线包路径"
    exit 1
fi

mkdir -p "${LOG_DIR}" "${OUTPUT_DIR}"

# ── 判断是否已在 nohup 后台中运行（避免二次套娃） ──────────────────
if [ -z "${_EVAL_BACKGROUND}" ]; then
    echo "🔄 以后台模式启动（SSH 断开后进程将持续运行）"
    echo "📂 工作目录: ${WORKSPACE}"
    echo "💻 代码目录: ${CODE_DIR}"
    echo "📄 日志文件: ${LOG_FILE}"
    echo "👀 实时查看日志: tail -f ${LOG_FILE}"
    echo "🛑 终止任务:     docker stop \$(docker ps -q --filter ancestor=${IMAGE_TAG})"
    echo "---------------------------------------------------"
    export _EVAL_BACKGROUND=1
    nohup bash "$0" --workspace "${WORKSPACE}" --code-dir "${CODE_DIR}" --image-tag "${IMAGE_TAG}" > "${LOG_FILE}" 2>&1 &
    echo "✅ 后台 PID: $!，安全断开 SSH 即可。"
    exit 0
fi

# ── 以下是真正的评测逻辑（在 nohup 后台中执行） ────────────────────
echo "🚀 开始执行混合评测任务，Task ID: ${TASK_ID}"
echo "---------------------------------------------------"

# ── 阶段 1：推理 ──────────────────────────────────────────────────────
echo ""
echo "📌 阶段 1/2：执行推理..."
echo "---------------------------------------------------"

docker run --rm \
    --memory=128g \
    --memory-swap=128g \
    --shm-size=16g \
    --env-file "${ENV_FILE}" \
    -v "${DATA_DIR}:/app/data" \
    -v "${OUTPUT_DIR}:/app/outputs" \
    -v "${CODE_DIR}/eval_entry.py:/app/eval_entry.py" \
    -v "${CODE_DIR}/eval_judge.py:/app/eval_judge.py" \
    -v "${CODE_DIR}/scripts:/app/scripts" \
    "${IMAGE_TAG}" \
    python eval_entry.py \
        --task-id "${TASK_ID}" \
        --model-config local_qwen \
        --tasks 1 34 36 43 44 60 \
        --generic-datasets \
            ceval_gen_0_shot_str \
            mmlu_redux_gen_5_shot_str \
            teledata_gen_0_shot \
            gpqa_gen_0_shot_str \
            bbh_gen_3_shot_cot_chat \
            BFCL_gen_simple \
            ifeval_0_shot_gen_str \
            math500_gen_0_shot_cot_chat_prompt \
            aime2025_gen_0_shot_chat_prompt \
            humaneval_gen_0_shot \
            telemath_gen_0_cot_shot \
            teleqna_gen_0_shot \
            tspec_gen_0_shot \
            telequad_gen_0_shot \
            tele_exam_gen_0_shot \
            tele_exam_gen_0_shot_str

## livecodebench_0_shot_chat_v6 \

INFER_RC=$?
if [ ${INFER_RC} -ne 0 ]; then
    echo "==================================================="
    echo "❌ 推理阶段出现异常（退出码: ${INFER_RC}），跳过评测阶段。"
    echo "==================================================="
    exit ${INFER_RC}
fi

echo ""
echo "✅ 推理阶段完成"

# ── 阶段 2：评测 ──────────────────────────────────────────────────────
echo ""
echo "📌 阶段 2/2：执行评测..."
echo "---------------------------------------------------"

docker run --rm \
    --memory=128g \
    --memory-swap=128g \
    --shm-size=16g \
    --env-file "${ENV_FILE}" \
    -v "${DATA_DIR}:/app/data" \
    -v "${OUTPUT_DIR}:/app/outputs" \
    -v "${CODE_DIR}/eval_entry.py:/app/eval_entry.py" \
    -v "${CODE_DIR}/eval_judge.py:/app/eval_judge.py" \
    -v "${CODE_DIR}/scripts:/app/scripts" \
    "${IMAGE_TAG}" \
    python eval_judge.py \
        --infer-task "${TASK_ID}"

if [ $? -eq 0 ]; then
    echo "==================================================="
    echo "✅ 评测流水线全部执行完成！"
    echo "📊 报告路径: ${OUTPUT_DIR}/${TASK_ID}/eval_*/report.md"
    echo "==================================================="
else
    echo "==================================================="
    echo "❌ 评测阶段出现异常，请检查详情日志。"
    echo "==================================================="
    exit 1
fi
