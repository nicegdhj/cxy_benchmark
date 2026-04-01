#!/usr/bin/env bash
# ==============================================================================
# run_235b_lack.sh - 补跑 qwen3-max 缺失的推理请求（启用深度思考）
#
# 输入: outputs/235b_lack_retry.json
# 输出: outputs/lack_report_retry.txt
#
# 用法:
#   nohup bash scripts/run_235b_lack.sh > outputs/235b_lack_console.log 2>&1 &
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_JSON="${1:-$PROJECT_ROOT/outputs/235b_lack_retry.json}"
OUTPUT_FILE="${2:-$PROJECT_ROOT/outputs/lack_report_retry.txt}"
API_KEY="sk-113a66cc6c464374a4d6f06b7306132f"
MODEL="qwen3-max"

if [ ! -f "$INPUT_JSON" ]; then
    echo "❌ 找不到输入文件: $INPUT_JSON"
    exit 1
fi

# 读取总条数
TOTAL=$(python3 -c "import json; print(len(json.load(open('$INPUT_JSON'))))")

echo "========================================" > "$OUTPUT_FILE"
echo "  Qwen3-Max 补跑结果 (Enable Thinking)" >> "$OUTPUT_FILE"
echo "  开始时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$OUTPUT_FILE"
echo "  总条数: $TOTAL" >> "$OUTPUT_FILE"
echo "========================================" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

STATS_FILE=$(mktemp)
echo "0 0" > "$STATS_FILE"

# 逐条读取 JSON 并串行处理
# 使用 python 脚本处理核心请求逻辑，以支持流式输出和深度思考内容提取
while IFS=$'\t' read -r id suite jsonl_file row prompt_json; do

    echo "[$id/$TOTAL] $suite / row $row ..."

    start_ts=$(python3 -c "import time; print(time.time())")

    # 执行 Python 脚本进行推理
    response_json=$(python3 - <<EOF
import json
import os
import sys
from openai import OpenAI

try:
    client = OpenAI(
        api_key="$API_KEY",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    
    prompt = json.loads('''$prompt_json''')
    
    completion = client.chat.completions.create(
        model="$MODEL",
        messages=[{"role": "user", "content": prompt}],
        extra_body={"enable_thinking": True},
        stream=True,
        timeout=1200
    )
    
    reasoning_parts = []
    content_parts = []
    
    for chunk in completion:
        if not chunk.choices: continue
        delta = chunk.choices[0].delta
        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
            reasoning_parts.append(delta.reasoning_content)
        if hasattr(delta, "content") and delta.content:
            content_parts.append(delta.content)
            
    reasoning = "".join(reasoning_parts)
    content = "".join(content_parts)
    
    result = ""
    if reasoning:
        result += "<thought>\n" + reasoning + "\n</thought>\n"
    result += content
    
    print(json.dumps({"status": "SUCCESS", "result": result}))
except Exception as e:
    print(json.dumps({"status": "FAILED", "error": str(e)}))
EOF
)

    end_ts=$(python3 -c "import time; print(time.time())")
    elapsed=$(python3 -c "print(round($end_ts - $start_ts, 2))")

    status=$(echo "$response_json" | python3 -c "import json, sys; print(json.load(sys.stdin).get('status'))")
    
    if [ "$status" = "SUCCESS" ]; then
        result=$(echo "$response_json" | python3 -c "import json, sys; print(json.load(sys.stdin).get('result'))")
        error=""
        read s f < "$STATS_FILE"; echo "$((s+1)) $f" > "$STATS_FILE"
    else
        result="null"
        error=$(echo "$response_json" | python3 -c "import json, sys; print(json.load(sys.stdin).get('error'))")
        read s f < "$STATS_FILE"; echo "$s $((f+1))" > "$STATS_FILE"
    fi

    # 写入结果
    {
        echo "────────────────────────────────────────"
        echo "id:       $id"
        echo "suite:    $suite"
        echo "file:     $jsonl_file"
        echo "row:      $row"
        echo "status:   $status"
        echo "elapsed:  ${elapsed}s"
        if [ -n "$error" ]; then
            echo "error:    $error"
        fi
        echo "result:"
        if [ "$result" = "null" ]; then
            echo "  null"
        else
            # 记录完整内容，不进行 head 截断以保证结果完整性
            echo "$result"
        fi
        echo ""
    } >> "$OUTPUT_FILE"

    echo "  -> $status (${elapsed}s)"
done < <(python3 -c "
import json, sys
tasks = json.load(open('$INPUT_JSON'))
for t in tasks:
    prompt_json = json.dumps(t['prompt'], ensure_ascii=False)
    print(f\"{t['id']}\t{t['suite']}\t{t['jsonl_file']}\t{t['row']}\t{prompt_json}\")
")

read success failed < "$STATS_FILE"
rm -f "$STATS_FILE"

{
    echo "========================================"
    echo "  补跑完成"
    echo "  结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  成功: $success  失败: $failed"
    echo "========================================"
} >> "$OUTPUT_FILE"

echo ""
echo "全部完成，结果: $OUTPUT_FILE"
