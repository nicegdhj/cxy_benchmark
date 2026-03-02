# 自动化模型评测操作手册 (Docker 私域部署版)

## 1. 概述

本指南介绍如何将现有的评测项目打包为 Docker 镜像，并在无公网连接的私域环境中进行离线、全自动化的多任务评测。
该方案支持：

- **高并发加速**：通过环境变量控制 API 并发数，极大缩短数万条数据的评测时间。
- **配置解耦**：测试数据 (`data`)、评测结果 (`outputs`)、API 密钥 (`.env`) 全部提取到宿主机，运行时动态挂载，无需修改镜像。
- **模型动态替换**：模型 URL 和 Name 可通过环境变量随时指定。
- **自动化流水线接入**：通过自定义的 `eval_entry.py` 脚本，每次评测指定唯一的 `task-id`，并输出结构化的 `report.json` 供训练框架自动解析决策。

---

## 2. 在有网环境（Mac / 打包机）构建并导出镜像

由于私域网络隔离，**必须在有网的机器上完成镜像构建，并将包含了所有依赖的镜像导出为离线包**。

### 2.1 构建镜像

在项目根目录（包含 `Dockerfile` 的目录）执行：

```bash
docker build -t benchmark-eval:latest .
```

> **提示**：此过程会下载 Python 基础镜像、安装 `requirements/runtime.txt` 和 `api.txt` 中的依赖（包括体积较大的 cpu-only 版 PyTorch），并自动下载 NLTK 所需的离线数据包。耗时取决于网络速度，请耐心等待。

### 2.2 导出离线镜像包

构建完成后，将镜像打包为压缩文件：

```bash
docker save benchmark-eval:latest | gzip > benchmark-eval.tar.gz
```

导出完成后，将 `benchmark-eval.tar.gz` 拷贝至私域服务器。

---

## 3. 私域网络部署与运行

### 3.1 导入镜像

在私域服务器上执行：

```bash
docker load < benchmark-eval.tar.gz
```

### 3.2 创建运行时工作目录结构

在私域服务器上规划一个专门的评测工作目录（如 `/opt/eval_workspace/`），并准备如下结构：

```text
/opt/eval_workspace/
├── .env                  # API 密钥与基础配置
├── data/                 # 存放所有测试数据集
│   ├── task_34.jsonl     # 数据文件名必须符合规范：task_{数字}.jsonl
│   └── task_36.jsonl
└── outputs/              # (自动创建) 存放按 task-id 分类的评测结果
```

**配置 `.env` 文件示例：**

```env
# 私域 MaaS 模型服务地址与密钥（根据实际私域服务修改）
MAAS_API_KEY=your-private-api-key
MAAS_HOST_IP=10.0.0.1            # 私域模型服务 IP
MAAS_HOST_PORT=30175             # 服务端口（默认 30175）
MAAS_URL=/v1/chat/completions    # 接口路径

# 默认模型名称与并发数（可在 docker run 时通过 -e 覆盖）
EVAL_MODEL_NAME=Qwen3-32B
EVAL_CONCURRENCY=5

# 是否开启详细调试日志（true/false，设置为 true 时会打印每个请求的完整 cURL，平时建议保持 false）
EVAL_VERBOSE=false
```

### 3.3 自动化触发评测 (核心入口)

在模型训练完成后的一轮迭代中，自动化脚本可通过以下命令触发评测。
**示例**：评测任务 34 和 36，指定本次评测 ID 为 `train_round_1`，并发数为 20，模型名为 `Qwen3-32B`。

```bash
docker run --rm \
    --env-file /opt/eval_workspace/.env \
    -e EVAL_CONCURRENCY=20 \
    -e EVAL_MODEL_NAME="Qwen3-32B" \
    -e EVAL_VERBOSE=false \
    -v /opt/eval_workspace/data:/app/data/custom_task \
    -v /opt/eval_workspace/outputs:/app/outputs \
    benchmark-eval:latest \
    python eval_entry.py \
        --task-id train_round_1 \
        --tasks 34 36 \
        --model-config maas
```

**参数释义：**

- `--rm`：运行结束后自动销毁容器，保持环境干净。
- `--env-file`：注入环境变量。
- `-e EVAL_VERBOSE=true`：可选，若需要临时排查底层 API 请求，可传入为 `true` 打印完整 cURL 命令。
- `-v /opt/eval_workspace/data:/app/data/custom_task`：将宿主机的测试数据挂载到容器内 `ais_bench` 读取的路径。
- `-v /opt/eval_workspace/outputs:/app/outputs`：将容器内的输出结果同步回宿主机。
- `python eval_entry.py` 的参数：
  - `--task-id`：**必填**！标记本次评测的唯一 ID（如模型版本或 epoch 号），所有结果将保存在 `outputs/<task-id>/` 目录下。
  - `--tasks`：**必填**！指定要跑的任务编号列表，空格分隔（如 `34 36` 对应 `task_34_suite` 和 `task_36_suite`）。
  - `--model-config`：指定使用的模型配置，默认是 `maas`（代表私域 MaaSAPI）。

---

## 4. 评估报告解析

执行完成后，在宿主机的 `/opt/eval_workspace/outputs/train_round_1/` 目录下会生成如下文件：

1. **`report.md`**：综合战报，Markdown 格式，便于人工快速浏览各项任务的准确率及状态。
2. **`report.json`**：结构化的自动化报告，**非常适合由训练框架读取并用于程序化决策**。
3. **`details/`**：底层 `ais_bench` 的完整原始日志目录，包含单条推理结果和错题记录，供排查错误时使用。

**`report.json` 样板：**

```json
{
  "task_id": "train_round_1",
  "model": "my-new-model-v1",
  "timestamp": "2026-02-28 11:39:39",
  "avg_accuracy": 85.50,
  "tasks": [
    {
      "task": "task_34",
      "suite": "task_34_suite",
      "status": "success",
      "accuracy": 91.82,
      "returncode": 0,
      "details_dir": "details/20260228_113000"
    },
    {
      "task": "task_36",
      "suite": "task_36_suite",
      "status": "success",
      "accuracy": 79.18,
      "returncode": 0,
      "details_dir": "details/20260228_113149"
    }
  ]
}
```

> **说明**：`details_dir` 提供了该任务本次运行的原始日志相对路径，您可以通过拼接 `/opt/eval_workspace/outputs/train_round_1/{details_dir}/results/...` 快速定位到包含请求体和错题分析明细的 JSON 结果。

---

## 5. 持续训练自动化示例

在你的主训练流水线（Shell 或 Python 脚本）中，可以捕获 Docker 执行的退出状态码并解析 `report.json` 来决定下一步动作：

```bash
#!/bin/bash

TASK_ID="round_$(date +%s)"

echo "开始自动评测..."
docker run --rm \
    --env-file /opt/eval_workspace/.env \
    -e EVAL_CONCURRENCY=20 \
    -v /opt/eval_workspace/data:/app/data/custom_task \
    -v /opt/eval_workspace/outputs:/app/outputs \
    benchmark-eval:latest \
    python eval_entry.py --task-id "$TASK_ID" --tasks 34 36 43

# eval_entry.py 在有任务失败时会返回非 0 退出码
if [ $? -eq 0 ]; then
    echo "所有评估任务运行成功！检查总体精度..."
    
    # 使用 jq 提取总分（需要服务器安装 jq）
    REPORT_PATH="/opt/eval_workspace/outputs/${TASK_ID}/report.json"
    SCORE=$(jq '.avg_accuracy' $REPORT_PATH)
    
    echo "本轮综合得分: $SCORE"
    
    # 假设阈值为 80 分
    if (( $(echo "$SCORE >= 80.0" | bc -l) )); then
        echo "精度达标，进入下一轮训练阶段..."
        # start_next_round_training()
    else
        echo "精度未达标，终止流水线。"
        exit 1
    fi
else
    echo "自动化评测执行异常（详情请查看日志），流水线终止。"
    exit 1
fi
```
