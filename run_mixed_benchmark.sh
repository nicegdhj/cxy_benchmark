#!/bin/bash

# ==============================================================================
# 自动化混合模型评测脚本 (基于 Docker 私域部署)
# 根据 deploy.md 最佳实践生成
# ==============================================================================

# 生成一个唯一的时间戳作为本次评测的 task-id
TASK_ID="mixed_eval_$(date +%Y%m%d_%H%M%S)"

echo "🚀 开始执行混合评测任务，Task ID: ${TASK_ID}"
echo "---------------------------------------------------"


docker run --rm \
    --env-file /opt/eval_workspace/.env \
    -e LOCAL_CONCURRENCY=5 \
    -v /opt/eval_workspace/data:/app/data \
    -v /opt/eval_workspace/outputs:/app/outputs \
    benchmark-eval:latest \
    python eval_entry.py \
        --task-id "${TASK_ID}" \
        --model-config local_qwen \
        --num-prompts 100 \
        --tasks 1 34 36 43 44 60 \
        --generic-datasets \
            mmlu_redux_gen_5_shot_str \
            ceval_gen_0_shot_str \
            gpqa_gen_0_shot_str \
            bbh_gen_3_shot_cot_chat \
            BFCL_gen_simple \
            ifeval_0_shot_gen_str \
            math500_gen_0_shot_cot_chat_prompt \
            aime2025_gen_0_shot_chat_prompt \
            humaneval_gen_0_shot \
            livecodebench_0_shot_chat_v6 \
            telemath_gen_0_cot_shot \
            teleqna_gen_0_shot \
            tspec_gen_0_shot \
            teledata_gen_0_shot \
            telequad_gen_0_shot \
            tele_exam_gen_0_shot \
            tele_exam_gen_0_shot_str

# 获取退出状态码，判断任务是否成功
if [ $? -eq 0 ]; then
    echo "==================================================="
    echo "✅ 评测流水线全部执行完成！"
    echo "📊 报告路径: /opt/eval_workspace/outputs/${TASK_ID}/report.md"
    echo "==================================================="
else
    echo "==================================================="
    echo "❌ 评测过程中出现异常，部分或全部任务失败，请检查详情日志。"
    echo "==================================================="
    exit 1
fi
