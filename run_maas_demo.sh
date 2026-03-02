#!/usr/bin/env bash
# 加载 .env（export 给 ais_bench 子进程，让 maas.py 里的 os.environ 能读到）
set -a; source "$(dirname "$0")/.env"; set +a


# ais_bench \
#     --models maas \
#     --custom-dataset-path /path/to/your_data.jsonl \
#     --custom-dataset-data-type qa \
#     --mode all


# ais_bench --models maas --datasets task_36_suite --debug

ais_bench --models maas --datasets task_60_suite --debug


# python scripts/run_all_tasks.py --start 37 --end 85