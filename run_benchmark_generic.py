import sys
import os
# 强制设置命令行参数
sys.argv = [
    'ais_bench', 
    '--models', 'maas_api',
    '--datasets', 
        'mmlu_redux_gen_5_shot_str.py',
        'ceval_gen_0_shot_str.py',
        'gpqa_gen_0_shot_str.py',
        'bbh_gen_3_shot_cot_chat.py',
        'BFCL_gen_simple.py',
        'ifeval_0_shot_gen_str.py',
        'math500_gen_0_shot_cot_chat_prompt.py',
        'aime2025_gen_0_shot_chat_prompt.py',
        'humaneval_gen_0_shot.py',
        'livecodebench_0_shot_chat_v6.py',
        'telemath_gen_0_cot_shot.py',
        'teleqna_gen_0_shot.py',
        'tspec_gen_0_shot.py',
        'teledata_gen_0_shot.py',
        'telequad_gen_0_shot.py',
        'tele_exam_gen_0_shot.py',
        'tele_exam_gen_0_shot_str.py',
    '--work-dir', './outputs',
    '--max-num-workers', '1',  
]
from ais_bench.benchmark.cli.task_manager import TaskManager

def main():
    task_manager = TaskManager()
    task_manager.run()

if __name__ == '__main__':
    main()

