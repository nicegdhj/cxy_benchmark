#!/usr/bin/env bash
# ==============================================================================
# model_deploy.sh —— 大模型推理服务管理脚本（支持批量）
#
# 功能：通过代理服务 API 批量加载/卸载模型，成功记录写入 model_deploy_records.txt
#
# 用法:
#   加载模型:  bash model_deploy.sh load   --model-path <路径1> --model-path <路径2> ...
#   卸载模型:  bash model_deploy.sh unload  --model-id <id1>   --model-id <id2>   ...
#
# 选项:
#   --model-path   模型路径，可多次指定（load 时必填）
#   --model-id     模型 ID，  可多次指定（unload 时必填）
#   --api          代理服务地址（默认 http://localhost:8080）
#   --no-verify    跳过推理验证
#
# 示例:
#   bash model_deploy.sh load \
#       --model-path /dpc/exp/v260306/pt0_sft0/sft \
#       --model-path /dpc/exp/v260306/pt0_sft1/sft
#
#   bash model_deploy.sh unload \
#       --model-id 2378437c \
#       --model-id 9ea31ec6
# ==============================================================================

set -euo pipefail

# ── 默认配置 ──────────────────────────────────────────────────────────────────
DEPLOY_API="http://188.109.35.159:8090"
NO_VERIFY=false
ACTION=""
RECORD_FILE="$(pwd)/infer_deploy_res_$(TZ='Asia/Shanghai' date '+%Y%m%d').txt"

# 多值数组
MODEL_PATHS=(
    "/dpc/exp/v260306/pt14_sft0/sft"
    "/dpc/exp/v260306/pt15_sft0/sft"
    "/dpc/exp/v260306/pt16_sft0/sft"
    "/dpc/exp/v260306/pt17_sft0/sft"
#    "/dpc/exp/v260306/pt18_sft0/sft"
#    "/dpc/exp/v260306/pt19_sft0/sft"
#    "/dpc/exp/v260306/pt1_sft0/sft"
)
MODEL_IDS=(
    # 填写 load 操作返回的 model_id，可填多个
    # "2378437c"   # pt0_sft0
    # "9ea31ec6"   # pt0_sft1
)

# ── 颜色输出 ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; GRAY='\033[0;37m'; NC='\033[0m'
info()    { echo -e "${BLUE}ℹ  $*${NC}"; }
success() { echo -e "${GREEN}✅ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠  $*${NC}"; }
err()     { echo -e "${RED}❌ $*${NC}"; exit 1; }
dim()     { echo -e "${GRAY}   $*${NC}"; }

# ── 依赖检查 ──────────────────────────────────────────────────────────────────
command -v curl &>/dev/null || err "缺少 curl，请先安装: apt-get install curl"
command -v jq   &>/dev/null || err "缺少 jq，请先安装:   apt-get install jq"

# ── 用法提示 ──────────────────────────────────────────────────────────────────
usage() { sed -n '3,22p' "$0" | sed 's/^# //;s/^#//'; exit 0; }

# ── 参数解析 ──────────────────────────────────────────────────────────────────
[[ $# -lt 1 ]] && usage

ACTION="$1"; shift
[[ "$ACTION" == "-h" || "$ACTION" == "--help" ]] && usage
[[ "$ACTION" != "load" && "$ACTION" != "unload" ]] && \
    err "操作类型必须为 load 或 unload，收到: '$ACTION'"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model-path)  MODEL_PATHS+=("$2"); shift 2 ;;
        --model-id)    MODEL_IDS+=("$2");   shift 2 ;;
        --api)         DEPLOY_API="$2";     shift 2 ;;
        --no-verify)   NO_VERIFY=true;      shift   ;;
        -h|--help)     usage ;;
        *) err "未知参数: $1" ;;
    esac
done

# ── 参数校验 ──────────────────────────────────────────────────────────────────
[[ "$ACTION" == "load"   && ${#MODEL_PATHS[@]} -eq 0 ]] && err "load 操作至少指定一个 --model-path"
[[ "$ACTION" == "unload" && ${#MODEL_IDS[@]}   -eq 0 ]] && err "unload 操作至少指定一个 --model-id"

# ── 工具函数 ──────────────────────────────────────────────────────────────────
now() { date '+%Y-%m-%dT%H:%M:%S'; }

call_api() {
    local endpoint="$1" payload="$2"
    curl -sf -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        --connect-timeout 10 \
        --max-time 180 \
        "${DEPLOY_API}${endpoint}" \
    || { echo -e "${RED}❌ 连接代理服务失败: ${DEPLOY_API}${NC}" >&2; return 1; }
}

# 写入记录文件（追加）
# 格式: 时间戳 | 操作 | 模型路径 | model_id | model_name | 服务地址 | 状态 | 备注
write_record() {
    local ts="$1" op="$2" path="$3" mid="$4" mname="$5" url="$6" status="$7" note="${8:-}"
    printf '%s | %-6s | %-50s | %-10s | %-20s | %-50s | %-7s | %s\n' \
        "$ts" "$op" "$path" "$mid" "$mname" "$url" "$status" "$note" \
        >> "$RECORD_FILE"
}

# 初始化记录文件头（首次创建时写入）
init_record_file() {
    if [[ ! -f "$RECORD_FILE" ]]; then
        {
            echo "# model_deploy_records.txt — 模型部署操作记录"
            echo "# 时间戳             | 操作   | 模型路径                                           | model_id   | model_name           | 服务地址                                           | 状态    | 备注"
            echo "# $(printf '%0.s-' {1..160})"
        } >> "$RECORD_FILE"
    fi
}

verify_inference() {
    local url="$1" model_name="$2"
    info "  验证推理服务可用性: $url"
    local payload resp
    payload=$(jq -cn --arg m "$model_name" \
        '{model: $m, messages: [{role:"user", content:"你好，请回复OK"}], max_tokens: 10}')
    resp=$(curl -s -X POST -H "Content-Type: application/json" -d "$payload" \
        --connect-timeout 10 --max-time 60 "$url" 2>&1) || { warn "  推理服务连接超时"; return 1; }
    if echo "$resp" | jq -e '.choices[0].message.content' &>/dev/null; then
        local reply
        reply=$(echo "$resp" | jq -r '.choices[0].message.content')
        success "  推理服务响应正常: \"$reply\""
    else
        warn "  推理服务响应异常: $resp"
        return 1
    fi
}

# ══════════════════════════════════════════════════════════════════════════════
# 加载模型
# ══════════════════════════════════════════════════════════════════════════════
if [[ "$ACTION" == "load" ]]; then
    TOTAL=${#MODEL_PATHS[@]}
    echo ""
    echo "══════════════════════════════════════════════════════════"
    info "操作:     加载模型（共 $TOTAL 个）"
    info "代理服务: $DEPLOY_API"
    info "记录文件: $RECORD_FILE"
    echo "══════════════════════════════════════════════════════════"

    init_record_file

    LOAD_OK=0; LOAD_FAIL=0
    for i in "${!MODEL_PATHS[@]}"; do
        path="${MODEL_PATHS[$i]}"
        idx=$((i + 1))
        echo ""
        echo "  ── [$idx/$TOTAL] $path"
        info "  正在调用 /load_model..."

        RESP=$(call_api "/load_model" "{\"model_path\": \"$path\"}") || {
            warn "  API 请求失败，跳过"
            write_record "$(now)" "load" "$path" "-" "-" "-" "FAILED" "API请求失败"
            LOAD_FAIL=$((LOAD_FAIL + 1))
            continue
        }
        dim "响应: $RESP"

        CODE=$(echo "$RESP" | jq -r '.code' 2>/dev/null) || {
            warn "  响应非 JSON，跳过"
            write_record "$(now)" "load" "$path" "-" "-" "-" "FAILED" "响应非JSON"
            LOAD_FAIL=$((LOAD_FAIL + 1))
            continue
        }

        case "$CODE" in
            200)
                MID=$(echo "$RESP"   | jq -r '.config.model_id')
                MNAME=$(echo "$RESP" | jq -r '.config.model_name')
                URL=$(echo "$RESP"   | jq -r '.config.url')

                success "  加载成功"
                echo -e "     model_id:   ${YELLOW}${MID}${NC}"
                echo    "     model_name: $MNAME"
                echo    "     服务地址:   $URL"

                write_record "$(now)" "load" "$path" "$MID" "$MNAME" "$URL" "SUCCESS"

                if [[ "$NO_VERIFY" == "false" ]]; then
                    verify_inference "$URL" "$MNAME" || true
                fi
                LOAD_OK=$((LOAD_OK + 1))
                ;;
            10000)
                warn "  无空闲 NPU，跳过"
                write_record "$(now)" "load" "$path" "-" "-" "-" "FAILED" "无空闲NPU"
                LOAD_FAIL=$((LOAD_FAIL + 1))
                ;;
            *)
                MSG=$(echo "$RESP" | jq -r '.message // "未知错误"')
                warn "  加载失败 (code=$CODE): $MSG"
                write_record "$(now)" "load" "$path" "-" "-" "-" "FAILED" "code=$CODE $MSG"
                LOAD_FAIL=$((LOAD_FAIL + 1))
                ;;
        esac
    done

    echo ""
    echo "══════════════════════════════════════════════════════════"
    success "加载完成：成功 $LOAD_OK / 失败 $LOAD_FAIL / 共 $TOTAL"
    info "完整记录: $RECORD_FILE"
    echo "══════════════════════════════════════════════════════════"

# ══════════════════════════════════════════════════════════════════════════════
# 卸载模型
# ══════════════════════════════════════════════════════════════════════════════
elif [[ "$ACTION" == "unload" ]]; then
    TOTAL=${#MODEL_IDS[@]}
    echo ""
    echo "══════════════════════════════════════════════════════════"
    info "操作:     卸载模型（共 $TOTAL 个）"
    info "代理服务: $DEPLOY_API"
    info "记录文件: $RECORD_FILE"
    echo "══════════════════════════════════════════════════════════"

    init_record_file

    # 从记录文件反查 model_path（用于记录，方便追溯）
    lookup_path() {
        local mid="$1"
        grep "| $mid |" "$RECORD_FILE" 2>/dev/null | grep "| load " | tail -1 | \
            awk -F'|' '{gsub(/ /,"",$3); print $3}' || echo "-"
    }

    UNLOAD_OK=0; UNLOAD_FAIL=0
    for i in "${!MODEL_IDS[@]}"; do
        mid="${MODEL_IDS[$i]}"
        idx=$((i + 1))
        echo ""
        echo "  ── [$idx/$TOTAL] model_id: $mid"

        # 反查原始路径
        ORIG_PATH=$(lookup_path "$mid")
        [[ "$ORIG_PATH" != "-" ]] && dim "关联路径: $ORIG_PATH"

        info "  正在调用 /unload_model..."

        RESP=$(call_api "/unload_model" "{\"model_id\": \"$mid\"}") || {
            warn "  API 请求失败，跳过"
            write_record "$(now)" "unload" "$ORIG_PATH" "$mid" "-" "-" "FAILED" "API请求失败"
            UNLOAD_FAIL=$((UNLOAD_FAIL + 1))
            continue
        }
        dim "响应: $RESP"

        CODE=$(echo "$RESP" | jq -r '.code' 2>/dev/null) || {
            warn "  响应非 JSON，跳过"
            write_record "$(now)" "unload" "$ORIG_PATH" "$mid" "-" "-" "FAILED" "响应非JSON"
            UNLOAD_FAIL=$((UNLOAD_FAIL + 1))
            continue
        }

        case "$CODE" in
            200)
                MSG=$(echo "$RESP" | jq -r '.message')
                success "  卸载成功: $MSG"
                write_record "$(now)" "unload" "$ORIG_PATH" "$mid" "-" "-" "SUCCESS"

                if [[ "$NO_VERIFY" == "false" ]]; then
                    info "  验证（重复卸载应返回 10001）..."
                    VRSP=$(call_api "/unload_model" "{\"model_id\": \"$mid\"}") || true
                    VCODE=$(echo "$VRSP" | jq -r '.code' 2>/dev/null) || true
                    if [[ "$VCODE" == "10001" ]]; then
                        success "  验证通过：模型已彻底卸载"
                    else
                        warn "  验证异常，响应: $VRSP"
                    fi
                fi
                UNLOAD_OK=$((UNLOAD_OK + 1))
                ;;
            10001)
                warn "  未找到该 model_id，可能已卸载"
                write_record "$(now)" "unload" "$ORIG_PATH" "$mid" "-" "-" "SKIPPED" "未找到model_id"
                UNLOAD_FAIL=$((UNLOAD_FAIL + 1))
                ;;
            *)
                MSG=$(echo "$RESP" | jq -r '.message // "未知错误"')
                warn "  卸载失败 (code=$CODE): $MSG"
                write_record "$(now)" "unload" "$ORIG_PATH" "$mid" "-" "-" "FAILED" "code=$CODE $MSG"
                UNLOAD_FAIL=$((UNLOAD_FAIL + 1))
                ;;
        esac
    done

    echo ""
    echo "══════════════════════════════════════════════════════════"
    success "卸载完成：成功 $UNLOAD_OK / 失败 $UNLOAD_FAIL / 共 $TOTAL"
    info "完整记录: $RECORD_FILE"
    echo "══════════════════════════════════════════════════════════"
fi

echo ""
