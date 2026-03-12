# 多机 GPU 池化评测流水线 v2 — 设计与操作手册

> 版本：v2.0  日期：2026-03-12

---

## 1. 背景与目标

### 1.1 场景描述

多组 LLM 实验模型在 `/dpc/exp/v260306/` 共享存储中分批训练完成。
评测需要跨 6 台 GPU 机器（每台 8 张华为昇腾 910C）并行调度，最多 48 个评测任务并发运行。

### 1.2 v2 核心改进（vs v1）

| 维度 | v1 | v2 |
|------|-----|-----|
| GPU 机器 | 单机（1 个代理 API，8 卡） | **多机池化**（可配置 N 台，每台 8 卡） |
| 实验组发现 | 自动扫描 `.done` 文件 | **显式列表**（手动指定要跑的组） |
| 最大并发 | 8 | **48**（6 × 8） |
| 输出目录 | 集中 `/dpc/exp/eval_v260306/<exp>/` | **工作目录下** `./<exp>/outputs/` |
| 结果归集 | 无 | **自动归集到 `fmt/<exp>/`** |
| 数据共享 | 每次解压 | **一次部署，共享只读挂载** |
| 部署方式 | 宿主机直接运行 | **管理容器**（Docker-out-of-Docker） |
| load/unload 并发 | 无保护 | **每台机器一把锁，串行化** |
| 启动脚本 | bash `run_one_pipline.sh` | **纯 Python CLI** |

---

## 2. 系统架构

### 2.1 总体架构

```
                        ┌─────────────────────────────────────┐
                        │   管理容器 (Dockerfile.manager)       │
                        │   pipeline_daemon.py                 │
                        │     ├── MachinePool (6台×8卡=48槽)   │
                        │     ├── ThreadPoolExecutor (48 worker)│
                        │     └── 状态持久化 + 报告生成          │
                        └───────────┬─────────────────────────┘
                                    │ Docker Socket 挂载
                    ┌───────────────┼───────────────┐
                    │               │               │
              ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
              │ eval容器 1 │  │ eval容器 2 │  │ eval容器 N │  (最多48个)
              │ eval_entry │  │ eval_entry │  │ eval_entry │
              └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
                    │               │               │
        ┌───────────┴───────────────┴───────────────┴───────────┐
        │              GPU 推理机器池 (每台 :8090 代理 API)        │
        │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
        │  │ 159(8卡)│ │ 148(8卡)│ │ 149(8卡)│ │ ...     │     │
        │  └─────────┘ └─────────┘ └─────────┘ └─────────┘     │
        └───────────────────────────────────────────────────────┘
```

### 2.2 核心设计

- **集中式调度**：一台管理机运行所有评测容器，其他机器只提供推理服务
- **per-machine Lock**：每台 GPU 机器一把 `threading.Lock`，保证 `/load_model` 和 `/unload_model` 串行化（每个操作耗时 3~5 分钟，并发请求会导致"无空闲 NPU"误报）
- **Docker-out-of-Docker**：管理容器挂载宿主机 Docker Socket，可在任意共享存储机器上迅速迁移恢复
- **共享只读挂载**：`data/` 和 `code/` 以 `:ro` 挂载，所有容器复用同一份；仅 `outputs/` 独立可写

### 2.3 目录结构

```
/opt/eval_workspace/                  # 评测工作区（一次部署）
├── .env                             ← 基础环境配置
├── data/                            ← 评测数据集（所有容器共享只读）
└── code/
    ├── eval_entry.py                ← 评测入口脚本
    └── scripts/                     ← 辅助脚本

<work_dir>/                           # daemon 工作目录（--work-dir 指定）
├── pipeline_state.json              ← 状态注册表（核心数据库）
├── batch_report.md                  ← 横向对比报告（实时更新）
├── pipeline_daemon.log              ← 守护进程日志
├── pipeline_daemon.pid              ← PID 文件
├── pt14_sft0/                       ← 每个实验组独立目录
│   ├── outputs/eval_pt14_sft0/
│   │   ├── report.json
│   │   ├── report.md
│   │   └── details/
│   └── logs/
├── pt15_sft0/
│   └── ...
└── fmt/                             ← 自动归集的结果目录
    ├── pt14_sft0/
    │   ├── report.json
    │   ├── report.md
    │   └── details/
    └── pt15_sft0/
        └── ...
```

---

## 3. 状态机

### 3.1 模型生命周期

```
[queued]  ← 在 experiment_groups 列表中
    ↓  有空闲 GPU 槽位
[evaluating]  ← 持有 1 个 GPU 槽位，串行 load → 并行 eval → 串行 unload
    ↓              ↓
 [done]         [failed]
```

### 3.2 崩溃恢复

Daemon 重启时，所有 `evaluating` 状态的模型自动重置为 `queued`，重新调度评测。

### 3.3 `pipeline_state.json` 格式

```json
{
  "last_scan": "2026-03-12T10:30:00",
  "stats": {
    "total": 6, "done": 3, "evaluating": 2, "queued": 0, "failed": 1
  },
  "models": {
    "pt14_sft0": {
      "status": "done",
      "model_path": "/dpc/exp/v260306/pt14_sft0/sft",
      "added_at": "2026-03-12T06:00:00",
      "eval_start": "2026-03-12T06:00:15",
      "eval_end": "2026-03-12T07:22:10",
      "model_id": "2378437c",
      "machine_ip": "188.109.35.159",
      "avg_accuracy": 78.5,
      "report_path": "/app/workdir/pt14_sft0/outputs/eval_pt14_sft0/report.json"
    }
  }
}
```

---

## 4. 配置说明

所有配置集中在 `pipeline_daemon.py` 的 `get_default_config()` 函数中：

```python
{
    # GPU 机器池（新机器加入只需追加一行）
    "gpu_machines": [
        {"ip": "188.109.35.159", "port": 8090, "slots": 8},
        {"ip": "188.109.35.148", "port": 8090, "slots": 8},
        {"ip": "188.109.35.149", "port": 8090, "slots": 8},
        {"ip": "188.109.35.150", "port": 8090, "slots": 8},
        {"ip": "188.109.35.151", "port": 8090, "slots": 8},
        {"ip": "188.109.35.152", "port": 8090, "slots": 8},
    ],

    # 本轮要跑的实验组（手动维护）
    "experiment_groups": [
        "pt14_sft0", "pt15_sft0", "pt16_sft0",
        "pt17_sft0", "pt18_sft0", "pt19_sft0",
    ],

    "models_dir": "/dpc/exp/v260306",   # 训练产物根目录（共享存储）
    "model_subpath": "sft",              # 模型权重子目录
    "workspace": "/opt/eval_workspace",  # Docker 工作区
    "work_dir": "/app/workdir",          # daemon 工作目录

    "max_workers": 48,       # 最大并发评测数
    "poll_interval": 300,    # 轮询间隔（秒）
    "eval_timeout": 14400,   # 单模型评测超时（秒），4 小时
    "load_timeout": 600,     # load_model API 超时（秒），10 分钟
    "unload_timeout": 600,   # unload_model API 超时（秒），10 分钟

    "image_tag": "benchmark-eval:latest",
    "eval_tasks": ["1", "34", "36", "43", "44", "60"],
    "eval_generic": [ ... ],  # 17 个通用基准数据集
}
```

**修改配置**：直接编辑 `pipeline_daemon.py` 中的 `get_default_config()` 函数，或通过命令行参数覆盖部分配置。

---

## 5. 部署与使用

### 5.1 前提条件

```bash
# 1. 共享存储可访问（所有 GPU 机器均可挂载）
ls /dpc/exp/v260306/

# 2. 评测工作区已部署
ls /opt/eval_workspace/
# 应有: .env  data/  code/eval_entry.py  code/scripts/

# 3. Docker 镜像已存在
docker image inspect benchmark-eval:latest

# 4. 各 GPU 机器代理 API 可达
curl -s http://188.109.35.159:8090/load_model  # 能连通即可

# 5. Python3 + requests 已安装
python3 -c "import requests; print('OK')"
```

### 5.2 方式一：宿主机直接运行

```bash
# 启动（前台运行，适合调试）
python3 scripts/pipline_run/pipeline_daemon.py \
    --work-dir /data/eval_workdir \
    --workspace /opt/eval_workspace \
    --poll-interval 300

# 后台运行（SSH 断开后持续运行）
nohup python3 scripts/pipline_run/pipeline_daemon.py \
    --work-dir /data/eval_workdir \
    --workspace /opt/eval_workspace \
    > /data/eval_workdir/daemon.log 2>&1 &

# dry-run 模式（只打印调度计划，不实际执行）
python3 scripts/pipline_run/pipeline_daemon.py \
    --work-dir /tmp/test_workdir \
    --workspace /opt/eval_workspace \
    --poll-interval 1 \
    --dry-run
```

### 5.3 方式二：管理容器运行（推荐）

```bash
# 构建管理容器镜像
docker build -f Dockerfile.manager -t pipeline-manager:latest .

# 启动管理容器
docker run -d --name pipeline-manager \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /opt/eval_workspace:/opt/eval_workspace:ro \
    -v /data/eval_workdir:/app/workdir \
    pipeline-manager:latest \
    --work-dir /app/workdir \
    --workspace /opt/eval_workspace \
    --poll-interval 300
```

**管理容器的优势**：如果当前管理机故障，只需在另一台共享存储机器上重新启动管理容器，daemon 会自动从 `pipeline_state.json` 恢复状态继续运行。

### 5.4 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--work-dir` | `/app/workdir` | 工作目录，存放状态文件、输出、fmt |
| `--workspace` | `/opt/eval_workspace` | Docker 工作区，含 .env/data/code |
| `--max-workers` | `48` | 最大并发评测数 |
| `--poll-interval` | `300` | 轮询间隔（秒） |
| `--eval-timeout` | `14400` | 单模型评测超时（秒） |
| `--dry-run` | `false` | 只打印调度计划，不实际执行 |

### 5.5 修改实验组列表

编辑 `pipeline_daemon.py` 中 `get_default_config()` 的 `experiment_groups`：

```python
"experiment_groups": [
    "pt14_sft0",
    "pt15_sft0",
    # 新增或删除实验组...
],
```

如果需要新增 GPU 机器，在 `gpu_machines` 列表中追加一行即可。

---

## 6. 日志与监控

### 6.1 日志文件

daemon 运行后会在工作目录下生成以下文件：

| 文件 | 说明 |
|------|------|
| `pipeline_daemon.log` | 守护进程主日志（调度、状态变更、错误） |
| `pipeline_daemon.pid` | 进程 PID 文件 |
| `pipeline_state.json` | 状态注册表（JSON，实时更新） |
| `batch_report.md` | 横向对比报告（Markdown，实时更新） |

### 6.2 查看实时日志

```bash
# 方式一：宿主机运行时
tail -f /data/eval_workdir/pipeline_daemon.log

# 方式二：管理容器运行时
docker logs -f pipeline-manager
```

### 6.3 日志内容说明

```
# 启动信息
Pipeline Daemon v2 启动
  GPU 机器数: 6 台, 总槽位: 48
  实验组数: 6 组

# 调度信息
加入调度队列: pt14_sft0
▶ 派发: pt14_sft0 (剩余空闲: 47)

# Worker 进度（按实验组名过滤）
[pt14_sft0] 开始评测
[pt14_sft0] 等待机器 188.109.35.159 的加载锁...
[pt14_sft0] 调用 load_model @ 188.109.35.159
[pt14_sft0] 模型已部署: 188.109.35.159, port=10051, model_id=abc123
[pt14_sft0] 启动评测容器...
[pt14_sft0] 评测完成: done, accuracy=78.5
[pt14_sft0] 卸载模型 abc123 @ 188.109.35.159
[pt14_sft0] 结果已归集到 /app/workdir/fmt/pt14_sft0

# 轮询汇总
✅ [pt14_sft0] DONE | 准确率: 78.50% | 机器: 188.109.35.159
📊 完成:1 评测中:5 排队:0 失败:0 总计:6
   GPU 188.109.35.159: 5/8 使用中
   GPU 188.109.35.148: 3/8 使用中

# 完成
🏁 所有实验组评测完成！
```

### 6.4 按实验组过滤日志

```bash
# 查看某个实验组的完整日志
grep "pt14_sft0" /data/eval_workdir/pipeline_daemon.log

# 查看所有失败的日志
grep "❌\|FAILED\|部署失败\|评测超时" /data/eval_workdir/pipeline_daemon.log

# 查看 GPU 使用情况
grep "GPU" /data/eval_workdir/pipeline_daemon.log | tail -20
```

### 6.5 查看状态摘要

```bash
# 查看当前状态
python3 -c "
import json
s = json.load(open('/data/eval_workdir/pipeline_state.json'))
print('=== 评测流水线状态 ===')
for k, v in s.get('stats', {}).items():
    print(f'  {k}: {v}')
print()
print('=== 各模型状态 ===')
for name, m in sorted(s['models'].items()):
    acc = m.get('avg_accuracy')
    acc_str = f'{acc:.2f}%' if acc else '-'
    print(f'  {name}: {m[\"status\"]:12s}  准确率: {acc_str}  机器: {m.get(\"machine_ip\", \"-\")}')
"

# 查看横向对比报告
cat /data/eval_workdir/batch_report.md

# 查看正在运行的评测容器
docker ps --filter ancestor=benchmark-eval:latest
```

### 6.6 查看某个模型的评测详情

```bash
# 查看 report.json
cat /data/eval_workdir/pt14_sft0/outputs/eval_pt14_sft0/report.json | python3 -m json.tool

# 查看 report.md（综合战报）
cat /data/eval_workdir/pt14_sft0/outputs/eval_pt14_sft0/report.md

# 查看 fmt 归集结果
ls /data/eval_workdir/fmt/pt14_sft0/
```

---

## 7. 运维操作

### 7.1 停止 daemon

```bash
# 宿主机运行时
kill $(cat /data/eval_workdir/pipeline_daemon.pid)

# 管理容器运行时
docker stop pipeline-manager
```

> 注意：停止 daemon 不会停止已启动的评测容器，它们会继续运行直到完成。

### 7.2 强制重跑某个实验组

```bash
python3 -c "
import json
f = '/data/eval_workdir/pipeline_state.json'
s = json.load(open(f))
s['models']['pt14_sft0']['status'] = 'queued'
s['models']['pt14_sft0'].pop('error', None)
json.dump(s, open(f, 'w'), ensure_ascii=False, indent=2)
print('已重置 pt14_sft0 为 queued')
"
# daemon 下次轮询时会自动重新调度
```

### 7.3 终止所有评测容器

```bash
docker stop $(docker ps -q --filter ancestor=benchmark-eval:latest)
```

### 7.4 故障排查

| 现象 | 排查方法 | 解决办法 |
|------|---------|---------|
| 模型长时间停在 `evaluating` | `docker ps` 查看容器状态 | 容器可能卡住，手动 `docker stop` 后 daemon 会重试 |
| `/load_model` 返回"无空闲npu" | 查看对应机器的 GPU 占用 | 等待其他评测完成，或手动 `/unload_model` 残留模型 |
| daemon 进程意外退出 | `tail pipeline_daemon.log` 查看错误 | 重新启动即可，会从 state 文件自动恢复 |
| 某模型评测超时 | 日志中搜索 `评测超时` | 检查模型推理服务是否正常，手动重置为 queued 重试 |
| state 文件损坏 | JSON 格式错误 | 删除 `.tmp` 文件，从备份恢复或手动重建 |
| 容器启动失败 | 日志中搜索 `docker exit code` | 检查镜像、挂载路径、环境变量是否正确 |

---

## 8. 文件清单

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `scripts/pipline_run/pipeline_daemon.py` | **重写** | v2 核心守护进程 |
| `tests/test_pipeline_daemon.py` | **重写** | 17 个单元测试 |
| `Dockerfile.manager` | **新增** | 管理容器镜像（Python + Docker CLI） |
| `scripts/pipline_run/run_one_pipline.sh` | **废弃** | v1 启动脚本，功能已合并到 Python CLI |
| `eval_entry.py` / `Dockerfile` / `package_deploy.sh` | **不变** | 评测核心不变 |
