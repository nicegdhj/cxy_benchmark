#!/bin/bash
# ==============================================================================
# run_pipeline.sh —— 持续评测流水线启动脚本
#
# 用法:
#   bash run_pipeline.sh [选项]
#
# 参数:
#   --models-dir    训练产物根目录 (默认 /dpc/exp/v260306)
#   --eval-dir      评测输出根目录 (默认 /dpc/exp/eval_v260306)
#   --workspace     Docker 工作区  (默认 /opt/eval_workspace)
#   --deploy-api    部署 API 地址  (默认 http://188.109.35.159:8080)
#   --max-workers   最大并发数      (默认 8)
#   --poll-interval 轮询间隔秒数   (默认 600)
#   --dry-run       只扫描，不实际评测
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON_SCRIPT="${SCRIPT_DIR}/scripts/pipeline_daemon.py"

# ── 默认参数 ──────────────────────────────────────────────────────────
MODELS_DIR="/dpc/exp/v260306"
EVAL_DIR="/dpc/exp/eval_v260306"
WORKSPACE="/opt/eval_workspace"
DEPLOY_API="http://188.109.35.159:8080"
MAX_WORKERS=8
POLL_INTERVAL=600
DRY_RUN=""

# ── 参数解析 ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --models-dir)    MODELS_DIR="$2";    shift 2 ;;
        --eval-dir)      EVAL_DIR="$2";      shift 2 ;;
        --workspace)     WORKSPACE="$2";     shift 2 ;;
        --deploy-api)    DEPLOY_API="$2";    shift 2 ;;
        --max-workers)   MAX_WORKERS="$2";   shift 2 ;;
        --poll-interval) POLL_INTERVAL="$2"; shift 2 ;;
        --dry-run)       DRY_RUN="--dry-run"; shift ;;
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

# ── 前置校验 ──────────────────────────────────────────────────────────
if [ ! -f "${DAEMON_SCRIPT}" ]; then
    echo "❌ 找不到 Daemon 脚本: ${DAEMON_SCRIPT}"
    exit 1
fi

if ! python3 -c "import requests" 2>/dev/null; then
    echo "❌ 缺少 Python 依赖: requests"
    echo "   请先执行: pip3 install requests"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker daemon"
    exit 1
fi

mkdir -p "${EVAL_DIR}"
LOG_FILE="${EVAL_DIR}/pipeline_daemon.log"

# ── 防止重复启动 ──────────────────────────────────────────────────────
PID_FILE="${EVAL_DIR}/pipeline_daemon.pid"
if [ -f "${PID_FILE}" ]; then
    OLD_PID=$(cat "${PID_FILE}")
    if kill -0 "${OLD_PID}" 2>/dev/null; then
        echo "⚠️  流水线 Daemon 已在运行（PID: ${OLD_PID}）"
        echo "   日志: tail -f ${LOG_FILE}"
        exit 0
    else
        echo "ℹ️  发现过期 PID 文件，清理后重新启动"
        rm -f "${PID_FILE}"
    fi
fi

# ── 判断是否已在 nohup 中运行 ─────────────────────────────────────────
if [ -z "${_PIPELINE_BACKGROUND:-}" ]; then
    echo "🔄 以后台模式启动（SSH 断开后进程将持续运行）"
    echo "📁 训练实验目录: ${MODELS_DIR}"
    echo "📊 评测输出目录: ${EVAL_DIR}"
    echo "🔧 最大并发数:   ${MAX_WORKERS}"
    echo "⏱  轮询间隔:     ${POLL_INTERVAL}s"
    echo "📄 日志文件:     ${LOG_FILE}"
    echo "👀 实时日志:     tail -f ${LOG_FILE}"
    echo "🛑 停止 Daemon:  kill \$(cat ${PID_FILE})"
    echo "---------------------------------------------------"
    export _PIPELINE_BACKGROUND=1
    nohup bash "$0" \
        --models-dir "${MODELS_DIR}" \
        --eval-dir "${EVAL_DIR}" \
        --workspace "${WORKSPACE}" \
        --deploy-api "${DEPLOY_API}" \
        --max-workers "${MAX_WORKERS}" \
        --poll-interval "${POLL_INTERVAL}" \
        ${DRY_RUN} \
        > "${LOG_FILE}" 2>&1 &
    echo "✅ 后台 PID: $!，安全断开 SSH 即可。"
    exit 0
fi

# ── 实际执行（在 nohup 后台中）───────────────────────────────────────
python3 "${DAEMON_SCRIPT}" \
    --models-dir "${MODELS_DIR}" \
    --eval-dir "${EVAL_DIR}" \
    --workspace "${WORKSPACE}" \
    --deploy-api "${DEPLOY_API}" \
    --max-workers "${MAX_WORKERS}" \
    --poll-interval "${POLL_INTERVAL}" \
    ${DRY_RUN}
