import sys
if sys.platform == "darwin":
    import multiprocessing
    multiprocessing.set_start_method("fork", force=True)
import os

# 强制设置命令行参数
sys.argv = [
    'ais_bench', 
    '--models', 'bailian_qwen_plus',
    '--datasets', 
        'math500_gen_0_shot_cot_chat_prompt',
    '--debug',
    '--work-dir', './outputs',
    '--max-num-workers', '1',  
    '--num-prompts', '1',
    '--mode','eval',
    '--reuse','20260316_205810'
]
#'--models', 'maas_api',
#'--reuse',"20260227_113125"
from ais_bench.benchmark.cli.task_manager import TaskManager

def main():
    task_manager = TaskManager()
    task_manager.run()

if __name__ == '__main__':
    main()
    
# DATASETS = [
#     'mmlu_redux_gen_5_shot_str',
#     'ceval_gen_0_shot_str',
#     'gpqa_gen_0_shot_str',
#     'bbh_gen_3_shot_cot_chat',
#     'BFCL_gen_simple',
#     'ifeval_0_shot_gen_str',
#     'math500_gen_0_shot_cot_chat_prompt',
#     'aime2025_gen_0_shot_chat_prompt',
#     'humaneval_gen_0_shot',
#     'livecodebench_0_shot_chat_v6',
#     'telemath_gen_0_cot_shot',
#     'teleqna_gen_0_shot',
#     'tspec_gen_0_shot',
#     'teledata_gen_0_shot',
#     'telequad_gen_0_shot',
# ]

# MODEL = 'bailian_qwen_plus'
# WORK_DIR = './outputs'

# def run_single_dataset(dataset_name):
#     """模拟 ais_bench --models xxx --datasets yyy"""
#     print(f"\n[INFO] Running dataset: {dataset_name}")
    
#     # 临时覆盖 sys.argv
#     original_argv = sys.argv.copy()
#     try:
#         sys.argv = [
#             'ais_bench',
#             '--models', MODEL,
#             '--datasets', dataset_name,
#             '--work-dir', WORK_DIR,
#             '--max-num-workers', '1',
#         ]
        
#         from ais_bench.benchmark.cli.task_manager import TaskManager
#         task_manager = TaskManager()
#         task_manager.run()
        
#     except Exception as e:
#         print(f"[ERROR] Failed on {dataset_name}: {e}")
#     finally:
#         # 恢复原始 argv（可选）
#         sys.argv = original_argv

# def main():
#     for ds in DATASETS:
#         run_single_dataset(ds)
#     print("\n[INFO] All datasets completed.")

# if __name__ == '__main__':
#     main()   

