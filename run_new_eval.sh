#!/bin/bash



python eval_judge.py --infer-task pt46_sft0 \
                    --output-dir ~/Desktop/fmt_exp0317 \
                    --eval-version v6_rule_fix \
                    --score-worker-concurrency 8 \
                    --eval-tasks \
                        task_1_suite \
                        task_43_suite \
                        task_44_suite \
                        task_60_suite



#
#bash scripts/run_batch_eval.sh \
#    --fmt-dir ~/Desktop/fmt_exp0316 \
#    --version v6_rule_fix \
#    --concurrency 8 \
#    --eval-tasks "task_1_suite task_43_suite task_44_suite task_60_suite"
#

 python aggregate_eval_reports.py  --fmt-dir /Users/jia/Desktop/fmt_exp0316 --eval-version v6_rule  --output-dir ./outputs