# 自动化模型评测操作手册 (Docker 私域部署版)

## 1. 概述

本指南介绍如何将评测项目的**运行环境**打包为 Docker 镜像，并在无公网连接的私域环境中进行离线、全自动化的多任务评测。

**环境与代码分离**是本方案的核心设计：

| 内容 | 载体 | 更新方式 |
|------|------|---------|
| Python 运行时、pip 依赖、ais_bench 框架 | Docker 镜像 | 依赖变更时重新构建 |
| `eval_entry.py`、`scripts/` 业务脚本 | 宿主机 `code/` 目录（`-v` 挂载） | 直接在服务器上编辑，无需重建镜像 |
| `data/`（评测数据）、`outputs/`（结果） | 宿主机挂载目录 | 随时替换 |
| `.env`（API 密钥） | 宿主机（不进入镜像） | 随时修改 |

---

## 2. 在有网环境（Mac / 打包机）构建并导出离线部署包

由于私域网络隔离，**必须在有网的机器上完成镜像构建，并将包含了所有业务代码、数据集以及评测依赖的镜像打包导出**。

我们为您准备了**一键打包脚本**。

在项目根目录（包含 `Dockerfile` 的目录）执行：

```bash
bash scripts/package_deploy.sh
```

该脚本将自动执行以下完整流水线：

1. 校验 `.env`、`data/` 等必要文件
2. 执行 `docker build` 自动构建最新版的评测镜像
3. 执行 `docker save` 导出离线镜像包
4. 将配套脚本、数据和离线镜像一起打包成 `eval_workspace_xxxxxxxx.tar.gz` 放入 `outputs/`

完成后，将最终生成的 `tar.gz` 压缩包传输到脱机的私域服务器。

---

## 3. 私域网络部署

### 3.1 导入镜像

在私域服务器上执行：

```bash
docker load < benchmark-eval.tar.gz
```

### 3.2 创建工作目录结构

规划一个专门的评测工作目录（如 `/opt/eval_workspace/`），按如下结构准备文件：

```text
/opt/eval_workspace/
├── .env                  # API 密钥与基础配置（必须存在）
├── data/                 # 统一数据挂载根目录
│   ├── custom_task/      # 自定义任务数据
│   │   ├── task_34.jsonl
│   │   └── task_36.jsonl
│   ├── telequad/         # 通用数据集目录
│   └── mmlu_redux/       # 另一个通用数据集
├── code/                 # 业务脚本（直接在服务器上维护）
│   ├── eval_entry.py     # 主评测入口脚本
│   └── scripts/          # 辅助脚本目录
├── outputs/              # (自动创建) 按 task-id 分类的评测结果
└── logs/                 # (自动创建) 后台运行日志
```

将 `eval_entry.py` 和 `scripts/` 从开发机复制到服务器：

```bash
scp eval_entry.py user@server:/opt/eval_workspace/code/
scp -r scripts/ user@server:/opt/eval_workspace/code/
```

### 3.3 配置 `.env` 文件

```env
# ====== 私域 MaaS 服务配置 ======
MAAS_API_KEY=your-private-api-key
MAAS_HOST_IP=10.0.0.1
MAAS_HOST_PORT=30175
MAAS_URL=/v1/chat/completions

# ====== 本地部署模型配置 (local_qwen) ======
LOCAL_MODEL_NAME=qwen3-14b
LOCAL_HOST_IP=188.109.35.159
LOCAL_HOST_PORT=8113
LOCAL_URL=/v1/chat/completions
LOCAL_CONCURRENCY=100    # 控制 HTTP 请求并发数量

# ====== 默认全局控制 ======
EVAL_MODEL_NAME=Qwen3-32B
EVAL_CONCURRENCY=5
EVAL_VERBOSE=false
```

---

## 4. 执行评测

### 4.1 使用 `run_mixed_benchmark.sh` 一键启动（推荐）

将 `run_mixed_benchmark.sh` 放到服务器上（任意位置），执行：

```bash
bash run_mixed_benchmark.sh --workspace /opt/eval_workspace
```

脚本会自动以 **nohup 后台模式**启动，终端立即返回，SSH 断开后评测持续运行：

```text
🔄 以后台模式启动（SSH 断开后进程将持续运行）
📂 工作目录: /opt/eval_workspace
💻 代码目录: /opt/eval_workspace/code
📄 日志文件: /opt/eval_workspace/logs/mixed_eval_20260305_160000.log
👀 实时查看日志: tail -f /opt/eval_workspace/logs/mixed_eval_20260305_160000.log
🛑 终止任务: docker stop $(docker ps -q --filter ancestor=benchmark-eval:latest)
---------------------------------------------------
✅ 后台 PID: 12345，安全断开 SSH 即可。
```

**脚本参数说明：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--workspace` | `/opt/eval_workspace` | 评测工作目录 |
| `--code-dir` | `<workspace>/code` | 业务代码目录，含 `eval_entry.py` 和 `scripts/` |
| `--image-tag` | `benchmark-eval:latest` | Docker 镜像 tag |
| `--image-tar` | （无） | 镜像离线包路径，镜像不存在时自动 load |

**重连后查看进度：**

```bash
tail -f /opt/eval_workspace/logs/mixed_eval_*.log
docker ps   # 确认容器仍在运行
```

### 4.2 直接调用 `docker run`（临时调试用）

```bash
docker run --rm \
    -e PYTHONUNBUFFERED=1 \
    --env-file /opt/eval_workspace/.env \
    -v /opt/eval_workspace/data:/app/data \
    -v /opt/eval_workspace/outputs:/app/outputs \
    -v /opt/eval_workspace/code/eval_entry.py:/app/eval_entry.py \
    -v /opt/eval_workspace/code/scripts:/app/scripts \
    benchmark-eval:latest \
    python eval_entry.py \
        --task-id pipeline_round_1 \
        --tasks 34 36 \
        --generic-datasets telequad_gen_0_shot mmlu_redux_gen_5_shot_str \
        --model-config local_qwen
```

> **注意**：直接 `docker run` 为前台模式，SSH 断开后进程会终止。如需后台运行，请使用 `run_mixed_benchmark.sh`。

---

## 5. 在服务器上修改代码（无需重建镜像）

这是本方案的核心优势。修改业务逻辑时，直接在服务器上编辑对应文件，重新执行脚本即可生效。

**修改 `eval_entry.py`：**

```bash
vi /opt/eval_workspace/code/eval_entry.py
# 或从本地 scp 覆盖：
scp eval_entry.py user@server:/opt/eval_workspace/code/eval_entry.py
```

**修改 `ais_bench` 框架内部逻辑：**

`ais_bench` 以 editable 模式安装在镜像内的 `/app/ais_bench/`，可通过额外挂载宿主机目录来覆盖它：

```bash
# 先将 ais_bench 源码复制到服务器
scp -r ais_bench/ user@server:/opt/eval_workspace/code/ais_bench/

# 在 docker run 中追加挂载（或修改 run_mixed_benchmark.sh 中的 docker run 命令）
-v /opt/eval_workspace/code/ais_bench:/app/ais_bench
```

**什么时候需要重建镜像：**

- 新增或升级 pip 依赖（修改 `requirements/` 文件后）

---

## 6. 报告解析

执行完成后，在 `/opt/eval_workspace/outputs/<task-id>/` 下生成：

1. **`report.md`**：综合战报，便于人工浏览。
2. **`report.json`**：结构化报告，适合 CI/CD 自动解析。
3. **`details/`**：单条推理结果与评分明细，按时间戳子目录组织。

**`report.json` 示例：**

```json
{
  "task_id": "pipeline_round_1",
  "model": "qwen3-14b",
  "timestamp": "2026-03-04 15:30:00",
  "avg_accuracy": 78.33,
  "summary": {
    "custom": { "count": 2, "tasks_with_accuracy": 2, "total_duration_sec": 45.9, "avg_accuracy": 85.0 },
    "generic": { "count": 2, "tasks_with_accuracy": 2, "total_duration_sec": 120.1, "avg_accuracy": 75.0 }
  },
  "tasks": [
    {
      "task": "task_34",
      "type": "custom",
      "suite": "task_34_suite",
      "status": "success",
      "accuracy": 90.0,
      "num_samples": 1000,
      "duration_sec": 15.2,
      "returncode": 0,
      "details_dir": "details/20260304_153000"
    }
  ]
}
```

**在流水线中解析结果：**

```bash
python eval_entry.py ...
if [ $? -eq 0 ]; then
    SCORE=$(jq '.avg_accuracy' /opt/eval_workspace/outputs/pipeline_round_1/report.json)
    if (( $(echo "$SCORE >= 80.0" | bc -l) )); then
        echo "模型达标！"
    fi
fi
```
