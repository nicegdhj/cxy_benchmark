#!/usr/bin/env bash
# ==============================================================================
# run_pipeline.sh —— 单机串联脚本：拉起推理服务 → 自动跑评测
#
# 功能：
#   1. 在指定机器上通过代理 API 批量加载模型推理服务
#   2. 从 API 返回中自动提取端口号
#   3. 自动解压评测包、注入端口配置、拉起评测容器（分批模式防 OOM）
#
# 用法:
#   bash run_pipeline.sh --ip <机器IP> [选项]
#
# 必填参数:
#   --ip              目标机器 IP（推理服务所在机器）
#
# 可选参数:
#   --proxy-port      代理服务端口（默认 8090）
#   --package         评测压缩包路径（默认自动查找当前目录下最新的 eval_workspace_*.tar.gz）
#   --workspace-base  评测工作区根目录（默认 /home/boco4a/hejia）
#   --model-path      模型路径，可多次指定（若不指定则使用脚本内 MODEL_PATHS 数组）
#   --no-verify       跳过推理验证
#   --deploy-only     仅部署推理服务，不执行评测
#   --eval-only       跳过推理部署，仅执行评测（需配合已有的部署记录文件）
#
# 示例:
#   # 在 192.168.1.100 上拉起 4 个实验组并自动跑评测
#   bash run_pipeline.sh --ip 192.168.1.100 \
#       --model-path /dpc/exp/v260306/pt14_sf0/sft \
#       --model-path /dpc/exp/v260306/pt15_sf0/sft \
#       --model-path /dpc/exp/v260306/pt16_sf0/sft \
#       --model-path /dpc/exp/v260306/pt17_sf0/sft
#
#   # 仅拉起推理服务，不跑评测
#   bash run_pipeline.sh --ip 192.168.1.100 --deploy-only
#
#   # 基于已有部署记录直接跑评测
#   bash run_pipeline.sh --ip 192.168.1.100 --eval-only
# ==============================================================================

set -euo pipefail

# ══════════════════════════════════════════════════════════════════════════════
# 用户配置区（也可通过命令行参数覆盖）
# ══════════════════════════════════════════════════════════════════════════════

MACHINE_IP="188.109.35.159"                                # 必填：目标机器 IP
PROXY_PORT=8090                              # 代理服务端口
PACKAGE_PATH="/dpc/hejia/eval_0314/eval_workspace_20260311_135303.tar.gz"                              # 评测压缩包路径（空=自动查找）
WORKSPACE_BASE="$(pwd)"                      # 评测工作区根目录（默认当前目录）
NO_VERIFY=false
DEPLOY_ONLY=false
EVAL_ONLY=false

# 推理服务操作等待时间（拉起/卸载等操作需要 3~5 分钟）
DEPLOY_WAIT_SEC=300

# 实验组模型路径（命令行 --model-path 会追加到此数组）
MODEL_PATHS=(
    "/dpc/exp/v260306/pt14_sf0/sft"
    "/dpc/exp/v260306/pt17_sf0/sft"
#    "/dpc/exp/v260306/pt16_sf0/sft"
#    "/dpc/exp/v260306/pt17_sf0/sft"
#    "/dpc/exp/v260306/pt18_sf0/sft"
#    "/dpc/exp/v260306/pt19_sf0/sft"
#    "/dpc/exp/v260306/pt1_sft0/sft"
)

# ══════════════════════════════════════════════════════════════════════════════

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; GRAY='\033[0;37m'; NC='\033[0m'
info()    { echo -e "${BLUE}ℹ  $*${NC}"; }
success() { echo -e "${GREEN}✅ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠  $*${NC}"; }
err()     { echo -e "${RED}❌ $*${NC}"; exit 1; }
dim()     { echo -e "${GRAY}   $*${NC}"; }
now()     { date '+%Y-%m-%dT%H:%M:%S'; }

# ── 用法提示 ────────────────────────────────────────────────────────────────
usage() { sed -n '3,40p' "$0" | sed 's/^# //;s/^#//'; exit 0; }

# ── 参数解析 ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ip)              MACHINE_IP="$2";      shift 2 ;;
        --proxy-port)      PROXY_PORT="$2";      shift 2 ;;
        --package)         PACKAGE_PATH="$2";    shift 2 ;;
        --workspace-base)  WORKSPACE_BASE="$2";  shift 2 ;;
        --model-path)      MODEL_PATHS+=("$2");  shift 2 ;;
        --no-verify)       NO_VERIFY=true;       shift   ;;
        --deploy-only)     DEPLOY_ONLY=true;     shift   ;;
        --eval-only)       EVAL_ONLY=true;       shift   ;;
        -h|--help)         usage ;;
        *) err "未知参数: $1（使用 --help 查看用法）" ;;
    esac
done

# ── 参数校验 ────────────────────────────────────────────────────────────────
[[ -z "$MACHINE_IP" ]] && err "必须指定 --ip <机器IP>"
[[ "$DEPLOY_ONLY" == "true" && "$EVAL_ONLY" == "true" ]] && err "--deploy-only 和 --eval-only 不能同时使用"

# 自动剥离协议头，只保留纯 IP
MACHINE_IP="${MACHINE_IP#http://}"
MACHINE_IP="${MACHINE_IP#https://}"
MACHINE_IP="${MACHINE_IP%%/*}"

DEPLOY_API="http://${MACHINE_IP}:${PROXY_PORT}"

command -v curl &>/dev/null || err "缺少 curl"
command -v jq   &>/dev/null || err "缺少 jq"

# ── 脚本所在目录 & 记录文件 ─────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEIJING_DATE=$(TZ='Asia/Shanghai' date '+%Y%m%d')
DEPLOY_RECORD="${SCRIPT_DIR}/pipeline_deploy_${MACHINE_IP}_${BEIJING_DATE}.txt"

# ── 工具函数 ────────────────────────────────────────────────────────────────

# 从模型路径提取实验组名称: /dpc/exp/v260306/pt14_sf0/sft → pt14_sf0
extract_exp_name() {
    local path="$1"
    # 取倒数第二段路径作为实验名
    echo "$path" | awk -F'/' '{print $(NF-1)}'
}

# 从服务 URL 提取端口号: http://x.x.x.x:10052/v1/... → 10052
extract_port() {
    local url="$1"
    echo "$url" | sed -n 's|.*://[^:]*:\([0-9]*\).*|\1|p'
}

call_api() {
    echo DEPLOY_API
    echo $endpoint
    echo $payload
    local endpoint="$1" payload="$2"
    curl -sf -X POST \
        -H "Content-Type: application/json" \
        --data-binary "$payload" \
        --connect-timeout 10 \
        --max-time 300 \
        "${DEPLOY_API}${endpoint}" \
    || {
        local exit_code=$?
        echo -e "${RED}❌ 连接代理服务失败: ${DEPLOY_API}${endpoint} (curl exit=${exit_code})${NC}" >&2
        echo -e "${RED}   exit=6: DNS 解析失败 | exit=7: 连接拒绝 | exit=28: 超时${NC}" >&2
        echo -e "${RED}   手动验证: curl -v -X POST ${DEPLOY_API}${endpoint} -H 'Content-Type: application/json' -d '${payload}'${NC}" >&2
        return 1
    }


}

verify_inference() {
    local url="$1" model_name="$2"
    info "  验证推理服务: $url"
    local payload resp
    payload=$(jq -cn --arg m "$model_name" \
        '{model: $m, messages: [{role:"user", content:"你好，请回复OK"}], max_tokens: 10}')
    resp=$(curl -s -X POST -H "Content-Type: application/json" -d "$payload" \
        --connect-timeout 10 --max-time 60 "$url" 2>&1) || { warn "  推理服务连接超时"; return 1; }
    if echo "$resp" | jq -e '.choices[0].message.content' &>/dev/null; then
        success "  推理服务响应正常: \"$(echo "$resp" | jq -r '.choices[0].message.content')\""
    else
        warn "  推理服务响应异常: $resp"
        return 1
    fi
}

# 等待推理服务就绪（拉起/卸载后需要 3~5 分钟）
wait_for_service() {
    local msg="${1:-推理服务操作}"
    local wait_sec="${2:-$DEPLOY_WAIT_SEC}"
    info "  ${msg}，等待 ${wait_sec} 秒（约 $((wait_sec / 60)) 分钟）..."
    sleep "${wait_sec}"
}


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1: 部署推理服务
# ══════════════════════════════════════════════════════════════════════════════

# 存储成功部署的结果: "实验名:端口" 格式
DEPLOYED_TARGETS=()

if [[ "$EVAL_ONLY" == "false" ]]; then
    [[ ${#MODEL_PATHS[@]} -eq 0 ]] && err "至少指定一个 --model-path（或在脚本内填写 MODEL_PATHS）"

    TOTAL=${#MODEL_PATHS[@]}
    echo ""
    echo "══════════════════════════════════════════════════════════════"
    echo "  Phase 1: 部署推理服务"
    echo "══════════════════════════════════════════════════════════════"
    info "目标机器:   $MACHINE_IP"
    info "代理地址:   $DEPLOY_API"
    info "实验组数量: $TOTAL"
    echo "──────────────────────────────────────────────────────────────"

    # 初始化记录文件
    if [[ ! -f "$DEPLOY_RECORD" ]]; then
        {
            echo "# pipeline_deploy — 串联部署记录 ($MACHINE_IP)"
            printf '%-19s | %-40s | %-12s | %-10s | %-8s | %s\n' \
                "时间" "模型路径" "实验名" "model_id" "端口" "状态"
            printf '%s\n' "$(printf '%0.s-' {1..120})"
        } > "$DEPLOY_RECORD"
    fi

    LOAD_OK=0; LOAD_FAIL=0
    for i in "${!MODEL_PATHS[@]}"; do
        path="${MODEL_PATHS[$i]}"
        exp_name=$(extract_exp_name "$path")
        idx=$((i + 1))
        echo ""
        echo "  ── [$idx/$TOTAL] $exp_name  ($path)"
        info "  正在调用 /load_model..."

        RESP=$(call_api "/load_model" "$(jq -cn --arg p "$path" '{model_path: $p}')") || {
            warn "  API 请求失败，跳过"
            printf '%s | %-40s | %-12s | %-10s | %-8s | %s\n' \
                "$(now)" "$path" "$exp_name" "-" "-" "FAILED" >> "$DEPLOY_RECORD"
            LOAD_FAIL=$((LOAD_FAIL + 1))
            continue
        }
        dim "响应: $RESP"

        # 标准化响应：将 Python 风格的单引号 key（'key':）转为合法 JSON 双引号
        RESP=$(echo "$RESP" | sed "s/'\([^']*\)':/\"\1\":/g")
        dim "标准化后响应: $RESP"

        CODE=$(echo "$RESP" | jq -r '.code' 2>/dev/null) || {
            warn "  响应非合法 JSON，jq 解析失败，跳过"
            warn "  原始响应内容: >>>$RESP<<<"
            warn "  请检查 API 是否返回了非 JSON 内容（如 HTML 错误页、空响应等）"
            printf '%s | %-40s | %-12s | %-10s | %-8s | %s\n' \
                "$(now)" "$path" "$exp_name" "-" "-" "FAILED(json_parse)" >> "$DEPLOY_RECORD"
            LOAD_FAIL=$((LOAD_FAIL + 1))
            continue
        }

        case "$CODE" in
            200)
                MID=$(echo "$RESP"   | jq -r '.config.model_id')
                MNAME=$(echo "$RESP" | jq -r '.config.model_name')
                URL=$(echo "$RESP"   | jq -r '.config.url')
                PORT=$(extract_port "$URL")

                if [[ -z "$PORT" ]]; then
                    warn "  加载成功但无法从 URL 提取端口，跳过"
                    warn "  config.url 原始值: '$URL'（期望格式: http://x.x.x.x:PORT/...）"
                    printf '%s | %-40s | %-12s | %-10s | %-8s | %s\n' \
                        "$(now)" "$path" "$exp_name" "$MID" "-" "FAILED(no_port)" >> "$DEPLOY_RECORD"
                    LOAD_FAIL=$((LOAD_FAIL + 1))
                    continue
                fi

                success "  加载成功"
                echo -e "     model_id:   ${YELLOW}${MID}${NC}"
                echo    "     model_name: $MNAME"
                echo    "     服务地址:   $URL"
                echo    "     端口:       $PORT"

                printf '%s | %-40s | %-12s | %-10s | %-8s | %s\n' \
                    "$(now)" "$path" "$exp_name" "$MID" "$PORT" "SUCCESS" >> "$DEPLOY_RECORD"

                DEPLOYED_TARGETS+=("${exp_name}:${PORT}")

                # 等待推理服务完全就绪
                wait_for_service "等待推理服务就绪" "$DEPLOY_WAIT_SEC"

                if [[ "$NO_VERIFY" == "false" ]]; then
                    verify_inference "$URL" "$MNAME" || true
                fi
                LOAD_OK=$((LOAD_OK + 1))
                ;;
            10000)
                warn "  无空闲 NPU，跳过"
                printf '%s | %-40s | %-12s | %-10s | %-8s | %s\n' \
                    "$(now)" "$path" "$exp_name" "-" "-" "NO_NPU" >> "$DEPLOY_RECORD"
                LOAD_FAIL=$((LOAD_FAIL + 1))
                ;;
            *)
                MSG=$(echo "$RESP" | jq -r '.message // "未知错误"')
                warn "  加载失败 (code=$CODE): $MSG"
                printf '%s | %-40s | %-12s | %-10s | %-8s | %s\n' \
                    "$(now)" "$path" "$exp_name" "-" "-" "FAILED" >> "$DEPLOY_RECORD"
                LOAD_FAIL=$((LOAD_FAIL + 1))
                ;;
        esac
    done

    echo ""
    echo "──────────────────────────────────────────────────────────────"
    success "Phase 1 完成：成功 $LOAD_OK / 失败 $LOAD_FAIL / 共 $TOTAL"
    info "部署记录: $DEPLOY_RECORD"

    if [[ ${#DEPLOYED_TARGETS[@]} -eq 0 ]]; then
        err "没有成功部署的模型，无法继续评测"
    fi

    if [[ "$DEPLOY_ONLY" == "true" ]]; then
        echo ""
        echo "══════════════════════════════════════════════════════════════"
        success "仅部署模式，已跳过评测。成功部署 ${#DEPLOYED_TARGETS[@]} 个实验组："
        for t in "${DEPLOYED_TARGETS[@]}"; do
            echo "  - ${t%%:*} → 端口 ${t##*:}"
        done
        echo ""
        info "后续手动跑评测时可使用 --eval-only 模式"
        echo "══════════════════════════════════════════════════════════════"
        exit 0
    fi

else
    # --eval-only 模式：从记录文件中读取已部署的实验组和端口
    if [[ ! -f "$DEPLOY_RECORD" ]]; then
        err "找不到部署记录: $DEPLOY_RECORD（请先执行部署，或去掉 --eval-only）"
    fi
    info "从部署记录加载已部署的实验组..."
    while IFS='|' read -r _ts _path exp_name _mid port status _rest; do
        # 去除空格
        exp_name=$(echo "$exp_name" | xargs)
        port=$(echo "$port" | xargs)
        status=$(echo "$status" | xargs)
        [[ "$status" == "SUCCESS" ]] && DEPLOYED_TARGETS+=("${exp_name}:${port}")
    done < <(grep "SUCCESS" "$DEPLOY_RECORD" || true)

    if [[ ${#DEPLOYED_TARGETS[@]} -eq 0 ]]; then
        err "部署记录中没有成功的实验组"
    fi
    success "从记录中加载了 ${#DEPLOYED_TARGETS[@]} 个实验组"
fi

# ══════════════════════════════════════════════════════════════════════════════
# Phase 2: 执行评测
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Phase 2: 部署评测容器"
echo "══════════════════════════════════════════════════════════════"

# 自动查找评测压缩包
if [[ -z "$PACKAGE_PATH" ]]; then
    PACKAGE_PATH=$(ls -t eval_workspace_*.tar.gz 2>/dev/null | head -1 || true)
    if [[ -z "$PACKAGE_PATH" ]]; then
        err "未找到评测压缩包 eval_workspace_*.tar.gz，请通过 --package 指定"
    fi
    info "自动发现评测压缩包: $PACKAGE_PATH"
fi

[[ ! -f "$PACKAGE_PATH" ]] && err "找不到压缩包: $PACKAGE_PATH"

info "机器 IP:     $MACHINE_IP"
info "工作区根:    $WORKSPACE_BASE"
info "压缩包:      $PACKAGE_PATH"
info "实验组数量:  ${#DEPLOYED_TARGETS[@]}"
echo "──────────────────────────────────────────────────────────────"

# 结果记录
EVAL_RECORD="${SCRIPT_DIR}/pipeline_eval_${MACHINE_IP}_${BEIJING_DATE}.txt"
if [[ ! -f "$EVAL_RECORD" ]]; then
    printf '%-19s | %-35s | %-8s | %s\n' "时间" "工作区" "端口" "状态" > "$EVAL_RECORD"
    printf '%s\n' "$(printf '%0.s-' {1..80})" >> "$EVAL_RECORD"
fi

EVAL_OK=0; EVAL_FAIL=0
TOTAL_EVAL=${#DEPLOYED_TARGETS[@]}

for i in "${!DEPLOYED_TARGETS[@]}"; do
    target="${DEPLOYED_TARGETS[$i]}"
    exp_name="${target%%:*}"
    port="${target##*:}"
    idx=$((i + 1))
    work_dir="${WORKSPACE_BASE}/${exp_name}"

    echo ""
    echo "  ── [$idx/$TOTAL_EVAL] $exp_name (端口 $port → $work_dir)"

    # 步骤1: 创建目录并解压
    mkdir -p "$work_dir"
    info "  解压评测包到 $work_dir ..."
    if ! tar -xzf "$PACKAGE_PATH" -C "$work_dir"; then
        warn "  解压失败: $PACKAGE_PATH → $work_dir"
        warn "  请检查: 压缩包是否完整 / 目标目录是否有写权限 / 磁盘空间是否充足"
        printf '%s | %-35s | %-8s | %s\n' "$(now)" "$work_dir" "$port" "FAILED(tar_error)" >> "$EVAL_RECORD"
        EVAL_FAIL=$((EVAL_FAIL + 1))
        continue
    fi

    # 定位真实工作区（查找 .env 所在目录）
    REAL_WORKSPACE=$(dirname "$(find "$work_dir" -name ".env" -maxdepth 3 | head -n 1)")
    if [[ -z "$REAL_WORKSPACE" || "$REAL_WORKSPACE" == "." ]]; then
        warn "  解压后未找到 .env，跳过"
        warn "  解压目录 $work_dir 内容:"
        ls -lA "$work_dir" 2>&1 | while IFS= read -r line; do dim "    $line"; done
        printf '%s | %-35s | %-8s | %s\n' "$(now)" "$work_dir" "$port" "FAILED(no .env)" >> "$EVAL_RECORD"
        EVAL_FAIL=$((EVAL_FAIL + 1))
        continue
    fi
    dim "实际工作区: $REAL_WORKSPACE"

    # 步骤2: 注入端口和 IP 到 .env
    sed -i "s/^LOCAL_HOST_PORT=.*/LOCAL_HOST_PORT=${port}/g" "$REAL_WORKSPACE/.env"
    sed -i "s/^LOCAL_HOST_IP=.*/LOCAL_HOST_IP=${MACHINE_IP}/g" "$REAL_WORKSPACE/.env"
    success "  已注入 .env: LOCAL_HOST_IP=$MACHINE_IP, LOCAL_HOST_PORT=$port"

    # 步骤3: 加载 Docker 镜像（仅首次）
    TAR_IMG="$REAL_WORKSPACE/benchmark-eval.tar.gz"
    IMAGE_TAR_FLAG=""
    if [[ -f "$TAR_IMG" ]]; then
        IMAGE_TAR_FLAG="--image-tar $TAR_IMG"
    fi

    # 步骤4: 拉起评测容器（分批模式防 OOM）
    if [[ -f "$REAL_WORKSPACE/run_mixed_benchmark_batched.sh" ]]; then
        info "  拉起评测容器（分批模式）..."
        info "  执行: bash run_mixed_benchmark_batched.sh --workspace $REAL_WORKSPACE $IMAGE_TAR_FLAG"
        cd "$REAL_WORKSPACE"
        if ! bash run_mixed_benchmark_batched.sh --workspace "$REAL_WORKSPACE" $IMAGE_TAR_FLAG; then
            local rc=$?
            cd - > /dev/null
            warn "  run_mixed_benchmark_batched.sh 执行失败 (exit=${rc})"
            warn "  请检查脚本日志: $REAL_WORKSPACE/logs/"
            printf '%s | %-35s | %-8s | %s\n' "$(now)" "$work_dir" "$port" "FAILED(script_exit=${rc})" >> "$EVAL_RECORD"
            EVAL_FAIL=$((EVAL_FAIL + 1))
            continue
        fi
        cd - > /dev/null

        sleep 3
        CONTAINER_ID=$(docker ps --latest --filter ancestor=benchmark-eval:latest --format "{{.ID}}" 2>/dev/null || echo "-")
        if [[ "$CONTAINER_ID" == "-" || -z "$CONTAINER_ID" ]]; then
            warn "  脚本执行完成但未检测到运行中的评测容器，请确认容器是否正常启动"
            warn "  检查: docker ps -a --filter ancestor=benchmark-eval:latest"
        else
            success "  评测已启动（分批模式），容器 ID: $CONTAINER_ID"
        fi

        printf '%s | %-35s | %-8s | %s\n' "$(now)" "$work_dir" "$port" "OK($CONTAINER_ID)" >> "$EVAL_RECORD"
        EVAL_OK=$((EVAL_OK + 1))
    else
        warn "  未找到 run_mixed_benchmark_batched.sh"
        warn "  实际工作区路径: $REAL_WORKSPACE"
        warn "  工作区内容:"
        ls -lA "$REAL_WORKSPACE" 2>&1 | while IFS= read -r line; do dim "    $line"; done
        printf '%s | %-35s | %-8s | %s\n' "$(now)" "$work_dir" "$port" "FAILED(no script)" >> "$EVAL_RECORD"
        EVAL_FAIL=$((EVAL_FAIL + 1))
    fi
done

echo ""
echo "══════════════════════════════════════════════════════════════"
success "Phase 2 完成：成功 $EVAL_OK / 失败 $EVAL_FAIL / 共 $TOTAL_EVAL"
info "部署记录: $DEPLOY_RECORD"
info "评测记录: $EVAL_RECORD"
echo ""
echo "查看日志:  tail -f ${WORKSPACE_BASE}/*/eval_workspace/logs/mixed_eval_*.log"
echo "停止全部:  docker stop \$(docker ps -q --filter ancestor=benchmark-eval:latest)"
echo "══════════════════════════════════════════════════════════════"
