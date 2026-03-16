#!/bin/bash

# ==============================================================================
# 分批执行混合模型评测脚本（防 OOM 版本）
#
# 将所有评测任务拆成 3 批，每批使用独立 Docker 容器执行：
#   批次 1：自定义任务 + 小数据集（快速完成）
#   批次 2：多子集数据集（CEval 52 子集、BBH 27 子集、MMLU Redux 30 子集）
#   批次 3：电信领域数据集（含 LLMJudge 评估）
#
# 每批之间容器退出，Python 进程内存完全释放。
# 全部完成后自动合并为统一的 report.md / report.json（格式与原脚本一致）。
#
# 输出结构:
#   outputs/<task_id>/
#   ├── report_batch1.md      # 批次 1 阶段性报告
#   ├── report_batch2.md      # 批次 2 阶段性报告
#   ├── report_batch3.md      # 批次 3 阶段性报告
#   ├── report.md             # 合并后的统一报告
#   ├── report.json           # 合并后的 JSON 报告（供下游解析）
#   └── details/              # 全部实验组的 ais_bench 原始输出
#
# 用法:
#   bash run_mixed_benchmark_batched.sh [选项]
#
# 参数:
#   --workspace   评测工作目录（默认 /opt/eval_workspace）
#                 目录下须包含 .env / data/ / code/
#   --code-dir    业务代码目录（默认 <workspace>/code）
#                 须包含 eval_entry.py 和 scripts/
#   --image-tar   Docker 镜像 tar 包路径，若镜像不存在则自动 load
#                 （可选，若镜像已存在自动跳过）
#   --image-tag   Docker 镜像 tag（默认 benchmark-eval:latest）
#   --concurrency 并发数（默认 10，原脚本 20 偏高）
#   --restart-cmd 批间重启推理服务的命令（可选，如 "systemctl restart vllm"）
#   --skip-batch  跳过指定批次（1/2/3），用于断点续跑，可多次指定
#
# 示例:
#   bash run_mixed_benchmark_batched.sh --workspace /data/eval
#   bash run_mixed_benchmark_batched.sh --workspace /data/eval --restart-cmd "docker restart vllm"
#   bash run_mixed_benchmark_batched.sh --workspace /data/eval --skip-batch 1 --skip-batch 2
# ==============================================================================

set -euo pipefail

# ── 参数解析 ─────────────────────────────────────────────────────────
WORKSPACE="/opt/eval_workspace"
IMAGE_TAG="benchmark-eval:latest"
IMAGE_TAR=""
CODE_DIR=""
CONCURRENCY=20
RESTART_CMD=""
SKIP_BATCHES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace)     WORKSPACE="$2";          shift 2 ;;
        --code-dir)      CODE_DIR="$2";           shift 2 ;;
        --image-tar)     IMAGE_TAR="$2";          shift 2 ;;
        --image-tag)     IMAGE_TAG="$2";          shift 2 ;;
        --concurrency)   CONCURRENCY="$2";        shift 2 ;;
        --restart-cmd)   RESTART_CMD="$2";        shift 2 ;;
        --skip-batch)    SKIP_BATCHES+=("$2");    shift 2 ;;
        -h|--help)       sed -n '3,42p' "$0" | sed 's/^# //;s/^#//'; exit 0 ;;
        *)               echo "未知参数: $1（使用 --help 查看用法）"; exit 1 ;;
    esac
done

# ── 路径推导 ──────────────────────────────────────────────────────────
ENV_FILE="${WORKSPACE}/.env"
DATA_DIR="${WORKSPACE}/data"
OUTPUT_DIR="${WORKSPACE}/outputs"
LOG_DIR="${WORKSPACE}/logs"
CODE_DIR="${CODE_DIR:-${WORKSPACE}/code}"
TASK_ID="mixed_eval_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/${TASK_ID}.log"

# 统一输出目录（所有批次共用）
FINAL_DIR="${OUTPUT_DIR}/${TASK_ID}"

# ── 前置校验 ──────────────────────────────────────────────────────────
if [ ! -f "${ENV_FILE}" ]; then
    echo "找不到配置文件: ${ENV_FILE}"
    exit 1
fi
if [ ! -f "${CODE_DIR}/eval_entry.py" ]; then
    echo "找不到业务脚本: ${CODE_DIR}/eval_entry.py"
    exit 1
fi
if [ ! -d "${CODE_DIR}/scripts" ]; then
    echo "找不到 scripts 目录: ${CODE_DIR}/scripts"
    exit 1
fi

# ── Docker 镜像检测 & 自动 load ──────────────────────────────────────
if docker image inspect "${IMAGE_TAG}" > /dev/null 2>&1; then
    echo "Docker 镜像已存在: ${IMAGE_TAG}，跳过 load"
elif [ -n "${IMAGE_TAR}" ]; then
    if [ ! -f "${IMAGE_TAR}" ]; then
        echo "找不到镜像包: ${IMAGE_TAR}"
        exit 1
    fi
    echo "正在 load Docker 镜像: ${IMAGE_TAR} ..."
    docker load < "${IMAGE_TAR}"
    if [ $? -ne 0 ]; then
        echo "Docker 镜像 load 失败"
        exit 1
    fi
    echo "镜像 load 成功: ${IMAGE_TAG}"
else
    echo "镜像 ${IMAGE_TAG} 不存在，且未指定 --image-tar"
    exit 1
fi

mkdir -p "${LOG_DIR}" "${OUTPUT_DIR}" "${FINAL_DIR}"

# ── nohup 后台逻辑（避免二次套娃） ───────────────────────────────────
if [ -z "${_EVAL_BACKGROUND:-}" ]; then
    echo "以后台模式启动（SSH 断开后进程将持续运行）"
    echo "工作目录: ${WORKSPACE}"
    echo "代码目录: ${CODE_DIR}"
    echo "日志文件: ${LOG_FILE}"
    echo "实时查看日志: tail -f ${LOG_FILE}"
    echo "终止任务:     docker stop \$(docker ps -q --filter ancestor=${IMAGE_TAG})"
    echo "---------------------------------------------------"
    export _EVAL_BACKGROUND=1
    # 透传所有必要参数
    NOHUP_CMD="bash \"$0\" --workspace \"${WORKSPACE}\" --code-dir \"${CODE_DIR}\" --image-tag \"${IMAGE_TAG}\" --concurrency \"${CONCURRENCY}\""
    [ -n "${IMAGE_TAR}" ] && NOHUP_CMD+=" --image-tar \"${IMAGE_TAR}\""
    [ -n "${RESTART_CMD}" ] && NOHUP_CMD+=" --restart-cmd \"${RESTART_CMD}\""
    for sb in "${SKIP_BATCHES[@]:-}"; do
        [ -n "$sb" ] && NOHUP_CMD+=" --skip-batch \"$sb\""
    done
    nohup bash -c "${NOHUP_CMD}" > "${LOG_FILE}" 2>&1 &
    echo "后台 PID: $!，安全断开 SSH 即可。"
    exit 0
fi

# ── 判断是否跳过某个批次 ──────────────────────────────────────────────
should_skip() {
    local batch_num="$1"
    for sb in "${SKIP_BATCHES[@]:-}"; do
        [ "$sb" = "$batch_num" ] && return 0
    done
    return 1
}

# ── 公共 docker run 函数 ─────────────────────────────────────────────
# 每个批次用临时 task_id 运行，运行结束后将产物搬到统一目录
# 参数: batch_num batch_label eval_entry_args...
run_batch() {
    local batch_num="$1"
    local batch_label="$2"
    local tmp_task_id="${TASK_ID}__tmp_batch${batch_num}"
    shift 2

    echo ""
    echo "==================================================="
    echo "  批次 ${batch_num} [${batch_label}] 开始"
    echo "  并发: ${CONCURRENCY}"
    echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "==================================================="

    docker run --rm \
        --env-file "${ENV_FILE}" \
        -e LOCAL_CONCURRENCY="${CONCURRENCY}" \
        -v "${DATA_DIR}:/app/data" \
        -v "${OUTPUT_DIR}:/app/outputs" \
        -v "${CODE_DIR}/eval_entry.py:/app/eval_entry.py" \
        -v "${CODE_DIR}/scripts:/app/scripts" \
        "${IMAGE_TAG}" \
        python eval_entry.py \
            --num-prompts 3 \
            --task-id "${tmp_task_id}" \
            --model-config local_qwen \
            "$@"

    local rc=$?

    # ── 搬运产物到统一目录 ────────────────────────────────────────────
    local tmp_dir="${OUTPUT_DIR}/${tmp_task_id}"
    if [ -d "${tmp_dir}" ]; then
        # 搬运 report.md → report_batchN.md
        if [ -f "${tmp_dir}/report.md" ]; then
            cp "${tmp_dir}/report.md" "${FINAL_DIR}/report_batch${batch_num}.md"
        fi
        # 搬运 details/ 内容合并到统一 details/
        if [ -d "${tmp_dir}/details" ]; then
            mkdir -p "${FINAL_DIR}/details"
            cp -rn "${tmp_dir}/details/"* "${FINAL_DIR}/details/" 2>/dev/null || true
        fi
        # 保留 report.json 供最终合并
        if [ -f "${tmp_dir}/report.json" ]; then
            cp "${tmp_dir}/report.json" "${FINAL_DIR}/report_batch${batch_num}.json"
        fi
        # 清理临时目录
        rm -rf "${tmp_dir}"
    fi

    echo "==================================================="
    echo "  批次 ${batch_num} [${batch_label}] $([ $rc -eq 0 ] && echo '完成' || echo '失败')"
    echo "  阶段报告: ${FINAL_DIR}/report_batch${batch_num}.md"
    echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "==================================================="
    return $rc
}

# ── 批间清理：重启推理服务释放 KV Cache ───────────────────────────────
between_batches() {
    echo ""
    echo "--- 批间清理 ---"
    if [ -n "${RESTART_CMD}" ]; then
        echo "重启推理服务: ${RESTART_CMD}"
        eval "${RESTART_CMD}"
        echo "等待推理服务完成重启（5 分钟）..."
        sleep 300
    else
        echo "等待系统回收资源（30 秒）..."
        sleep 30
    fi
    echo "--- 继续下一批 ---"
}

# ══════════════════════════════════════════════════════════════════════
# 开始执行
# ══════════════════════════════════════════════════════════════════════
echo ""
echo "开始分批评测，Task ID: ${TASK_ID}"
echo "统一输出目录: ${FINAL_DIR}"
echo "并发数: ${CONCURRENCY}"
echo "---------------------------------------------------"

FAILED=0

# ── 批次 1：自定义任务 + 小数据集 ────────────────────────────────────
if ! should_skip "1"; then
    run_batch 1 "自定义任务 + 小数据集" \
        --tasks 1 34 36 43 44 60 \
        --generic-datasets \
            gpqa_gen_0_shot_str \
            ifeval_0_shot_gen_str \
            math500_gen_0_shot_cot_chat_prompt \
            aime2025_gen_0_shot_chat_prompt \
            humaneval_gen_0_shot \
            livecodebench_0_shot_chat_v6 \
            BFCL_gen_simple \
    || FAILED=$((FAILED + 1))

    between_batches
fi

# ── 批次 2：多子集数据集（CEval/BBH/MMLU Redux） ─────────────────────
if ! should_skip "2"; then
    run_batch 2 "CEval + BBH + MMLU Redux" \
        --generic-datasets \
            ceval_gen_0_shot_str \
            bbh_gen_3_shot_cot_chat \
            mmlu_redux_gen_5_shot_str \
    || FAILED=$((FAILED + 1))

    between_batches
fi

# ── 批次 3：电信领域数据集 ────────────────────────────────────────────
if ! should_skip "3"; then
    run_batch 3 "电信领域数据集" \
        --generic-datasets \
            telemath_gen_0_cot_shot \
            teleqna_gen_0_shot \
            tspec_gen_0_shot \
            teledata_gen_0_shot \
            telequad_gen_0_shot \
            tele_exam_gen_0_shot \
            tele_exam_gen_0_shot_str \
    || FAILED=$((FAILED + 1))
fi

# ══════════════════════════════════════════════════════════════════════
# 合并报告
# ══════════════════════════════════════════════════════════════════════
echo ""
echo "==================================================="
echo "  合并分批报告 → ${FINAL_DIR}/"
echo "==================================================="

# 收集各批次 JSON 报告路径（容器内路径）
CONTAINER_BATCH_JSONS=""
for n in 1 2 3; do
    if [ -f "${FINAL_DIR}/report_batch${n}.json" ]; then
        CONTAINER_BATCH_JSONS+=" /app/outputs/${TASK_ID}/report_batch${n}.json"
    fi
done

if [ -n "${CONTAINER_BATCH_JSONS}" ]; then
    docker run --rm \
        -v "${OUTPUT_DIR}:/app/outputs" \
        -v "${CODE_DIR}/scripts:/app/scripts" \
        "${IMAGE_TAG}" \
        python /app/scripts/merge_batch_reports.py \
            --task-id "${TASK_ID}" \
            --output-dir /app/outputs \
            --model local_qwen \
            --batch-jsons ${CONTAINER_BATCH_JSONS}

    # 清理临时的 batch JSON（只保留 batch md 和最终的 report.json）
    rm -f "${FINAL_DIR}"/report_batch*.json

    echo "合并完成！"
else
    echo "没有找到有效的批次报告，跳过合并"
fi

# ── 最终汇总 ──────────────────────────────────────────────────────────
echo ""
echo "==================================================="
if [ $FAILED -eq 0 ]; then
    echo "全部 3 批评测完成！"
else
    echo "${FAILED} 个批次失败，请检查对应日志。"
fi
echo "统一报告:   ${FINAL_DIR}/report.md"
echo "JSON 报告:  ${FINAL_DIR}/report.json"
echo "阶段报告:"
for n in 1 2 3; do
    [ -f "${FINAL_DIR}/report_batch${n}.md" ] && echo "  - report_batch${n}.md"
done
echo "原始输出:   ${FINAL_DIR}/details/"
echo "==================================================="

exit $FAILED
