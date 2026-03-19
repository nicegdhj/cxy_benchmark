#!/bin/bash

python eval_judge.py --infer-task baseline   \
                    --output-dir fmt \
                    --eval-version v2_new_eval \
                    --concurrency  8\
                    --eval-tasks \
                        task_1_suite \
                        task_34_suite \
                        task_36_suite \
                        task_43_suite \
                        task_44_suite \
                        task_60_suite \
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
                        tele_exam_gen_0_shot