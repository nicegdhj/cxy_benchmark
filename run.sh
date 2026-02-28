#!/bin/bash
set -a  # 自动 export 所有变量
source .env
set +a

# 运行你的程序
python run_benchmark_generic.py
# python test.py