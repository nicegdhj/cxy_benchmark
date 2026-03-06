# 自动化模型评测操作手册 (Docker 私域部署版)

## 1. 概述

本指南介绍如何将现有的评测项目打包为 Docker 镜像，并在无公网连接的私域环境中进行离线、全自动化的多任务评测。
该方案支持：

- **高并发加速**：通过环境变量控制 API 并发数，极大缩短数万条数据的评测时间。
- **配置解耦**：测试数据 (`data`)、评测结果 (`outputs`)、API 密钥 (`.env`) 全部提取到宿主机，运行时动态挂载，无需修改镜像。
- **本地自部署模型**：不仅支持私域 MaaS，还新增了本地直接部署推理（local_qwen）支持，并优化了并发调度。
- **自动化流水线接入**：通过自定义的 `eval_entry.py` 脚本，每次评测指定唯一的 `task-id`，混合跑自定义与通用数据集，输出结构化的 `report.json`。
- **SSH 断连持久化**：`run_mixed_benchmark.sh` 内置 nohup 后台模式，SSH 断开后评测进程持续运行，日志自动落盘。

---

## 2. 在有网环境（Mac / 打包机）构建并导出镜像

由于私域网络隔离，**必须在有网的机器上完成镜像构建，并将包含了所有依赖的镜像导出为离线包**。

### 2.1 构建镜像

在项目根目录（包含 `Dockerfile` 的目录）执行：

```bash
docker build -t benchmark-eval:latest .
```

### 2.2 导出离线镜像包

构建完成后，将镜像打包为压缩文件并拷贝至私域服务器：

```bash
docker save benchmark-eval:latest | gzip > benchmark-eval.tar.gz
```

---

## 3. 私域网络部署与运行

### 3.1 导入镜像

在私域服务器上执行：

```bash
docker load < benchmark-eval.tar.gz
```

### 3.2 创建运行时工作目录结构

在私域服务器上规划一个专门的评测工作目录（如 `/opt/eval_workspace/`），**所有的评测数据都在 `data` 目录下**：

```text
/opt/eval_workspace/
├── .env                  # API 密钥与基础配置
├── data/                 # 统一数据挂载根目录
│   ├── custom_task/      # 自定义任务的专用子目录
│   │   ├── task_34.jsonl 
│   │   └── task_36.jsonl
│   ├── telequad/         # 通用数据集的目录（以 telequad 为例）
│   └── mmlu_redux/       # 另一个通用数据集的目录
└── outputs/              # (自动创建) 存放按 task-id 分类的评测结果
```

**配置 `.env` 文件示例：**

```env
# ====== 私域 MaaS 服务配置 ======
MAAS_API_KEY=your-private-api-key
MAAS_HOST_IP=10.0.0.1            # 私域模型服务 IP
MAAS_HOST_PORT=30175             # 服务端口（默认 30175）
MAAS_URL=/v1/chat/completions    # 接口路径

# ====== 本地部署模型配置 (local_qwen) ======
LOCAL_MODEL_NAME=qwen3-14b
LOCAL_HOST_IP=188.109.35.159
LOCAL_HOST_PORT=8113
LOCAL_URL=/v1/chat/completions
LOCAL_CONCURRENCY=100            # 非常关键：控制 HTTP 请求并发数量！

# ====== 默认全局控制 ======
EVAL_MODEL_NAME=Qwen3-32B        # 默认模型名
EVAL_CONCURRENCY=5               # 如果未配置，默认的 ais_bench 层面并发度
EVAL_VERBOSE=false
```

---

## 4. 混合任务评测最佳实践

本框架支持两种类别的任务：

1. **自定义任务 (`--tasks`)**: 从 `data/custom_task/task_XX.jsonl` 中读取。
2. **内置通用数据集 (`--generic-datasets`)**: 读取 `data/` 目录下同名的内置数据集源文件。

### 推荐：使用 `run_mixed_benchmark.sh` 一键启动

项目提供了 `run_mixed_benchmark.sh` 脚本，封装了完整的评测流程，**支持 SSH 断连后后台持续运行**，无需手写 docker 命令。

**基本用法（使用默认工作目录 `/opt/eval_workspace`）：**

```bash
bash run_mixed_benchmark.sh
```

**指定自定义工作目录：**

```bash
bash run_mixed_benchmark.sh --workspace /data/myproject/eval
```

工作目录须包含以下结构（与第 3.2 节一致）：

```text
<workspace>/
├── .env          # API 密钥与基础配置（必须存在，缺失时脚本报错退出）
├── data/         # 统一数据挂载根目录
└── outputs/      # (自动创建) 评测结果
```

执行后终端立即返回，日志自动写入 `<workspace>/logs/<task-id>.log`：

```text
🔄 以后台模式启动（SSH 断开后进程将持续运行）
📂 工作目录: /opt/eval_workspace
📄 日志文件: /opt/eval_workspace/logs/mixed_eval_20260305_160000.log
👀 实时查看日志: tail -f /opt/eval_workspace/logs/mixed_eval_20260305_160000.log
🛑 终止任务: docker stop $(docker ps -q --filter ancestor=benchmark-eval:latest)
---------------------------------------------------
✅ 后台 PID: 12345，安全断开 SSH 即可。
```

**重连后查看进度：**

```bash
# 实时跟踪日志
tail -f /opt/eval_workspace/logs/mixed_eval_*.log

# 确认容器仍在运行
docker ps
```

### 控制评测条数（快速冒烟测试）

修改脚本中的 `--num-prompts` 参数，限制每个任务最多评测 N 条数据：

```bash
# 脚本中对应行：
        --num-prompts 5    # 改为 5 条，用于验证环境连通性
```

### 直接调用 docker run（高级用法）

如需临时调整参数，也可以绕过脚本直接调用：

```bash
docker run --rm \
    -e PYTHONUNBUFFERED=1 \
    --env-file /opt/eval_workspace/.env \
    -e LOCAL_CONCURRENCY=100 \
    -v /opt/eval_workspace/data:/app/data \
    -v /opt/eval_workspace/outputs:/app/outputs \
    benchmark-eval:latest \
    python eval_entry.py \
        --task-id pipeline_round_1 \
        --tasks 34 36 \
        --generic-datasets telequad_gen_0_shot mmlu_redux_gen_5_shot_str \
        --model-config local_qwen
```

> **注意**：直接 `docker run` 为前台模式，SSH 断开后进程会终止。如需后台运行，请使用 `run_mixed_benchmark.sh` 脚本或在命令前加 `nohup ... &`。

---

## 5. 补充：直接使用 ais_bench 原生并行运行 (特殊排查时使用)

如果你希望真正打破“任务与任务之间的串行隔离”，让若干个任务在**同一时刻同时向大模型发包**，可以直接不走 `eval_entry.py`，而是调用底层的 `ais_bench` 命令。

> **注意：** 该模式**无法**统一汇总带子类别的 `report.json`，且当模型 API 处理能力有限时，并行发包不一定比独占串行快。

```bash
docker run --rm \
    --env-file /opt/eval_workspace/.env \
    -v /opt/eval_workspace/data:/app/data \
    -v /opt/eval_workspace/outputs:/app/outputs \
    benchmark-eval:latest \
    ais_bench \
        --models local_qwen \
        --datasets task_34_suite task_36_suite \
        --max-num-workers 2    # ← 开启此开关：让 2 个任务同时开跑
```

这种场景下，`LOCAL_CONCURRENCY=100` 的资源会被这 `2` 个 task 瓜分并用。

---

## 6. 报告解析与持续集成 (CI/CD) 接入

执行完 `eval_entry.py` 后，在宿主机的 `/opt/eval_workspace/outputs/<task-id>/` 目录下会生成如下文件：

1. **`report.md`**：综合战报，便于人工快速浏览。
2. **`report.json`**：结构化的自动化报告，按任务类别提供了执行耗时和总体打分。
3. **`details/`**：包含单条推理结果和带错题分析明细。

**`report.json` 样板：**

```json
{
  "task_id": "pipeline_round_1",
  "model": "qwen3-14b",
  "timestamp": "2026-03-04 15:30:00",
  "avg_accuracy": 78.33,
  "summary": {
    "custom": {
      "count": 2,
      "total_duration_sec": 45.9,
      "avg_accuracy": 85.0
    },
    "generic": {
      "count": 2,
      "total_duration_sec": 120.1,
      "avg_accuracy": 75.0
    }
  },
  "tasks": [
    {
      "task": "task_34",
      "type": "custom",
      "suite": "task_34_suite",
      "status": "success",
      "accuracy": 90.0,
      "num_samples": 85,
      "duration_sec": 15.2,
      "returncode": 0,
      "details_dir": "details/20260304_153000"
    }
    // ...
  ]
}
```

在训练流水线中可以通过检测返回码和解析 `avg_accuracy` 等字段：

```bash
python eval_entry.py ...
if [ $? -eq 0 ]; then
    SCORE=$(jq '.avg_accuracy' outputs/pipeline_round_1/report.json)
    if (( $(echo "$SCORE >= 80.0" | bc -l) )); then
        echo "模型达标！"
    fi
fi
```
