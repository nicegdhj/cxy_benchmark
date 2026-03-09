# 持续评测流水线设计方案与操作手册

> 版本：v1.0  日期：2026-03-09

---

## 1. 背景与目标

### 1.1 场景描述

47 组 LLM 实验模型在 `/dpc/exp/v260306/` 共享存储中分批训练完成。每组实验完成时，
会在实验目录下写入 `.done` 标记文件。评测需要：

- **自动发现**：定时轮询新完成的训练实验
- **并发调度**：最多同时运行 8 个评测任务（8 张 910C NPU）
- **状态持久化**：断电/重启后可从上次状态继续，不重复评测
- **结果归档**：所有评测结果统一存放在 `/dpc/exp/eval_v260306/`
- **横向对比**：实时生成跨模型的对比报告

### 1.2 核心约束

| 约束 | 值 |
|------|-----|
| 最大并发评测数 | 8（1 个模型 1 张 NPU） |
| 轮询间隔 | 10 分钟 |
| 推理服务 API | `http://188.109.35.159:8080` |
| 训练产物路径模式 | `/dpc/exp/v260306/<exp_name>/sft/` |
| 训练完成标记 | `/dpc/exp/v260306/<exp_name>/.done` |

---

## 2. 系统架构

### 2.1 目录结构

```text
/dpc/exp/
├── v260306/                          # 训练产物（只读）
│   ├── pt0_sft0/
│   │   ├── .done                    ← 训练完成标记
│   │   └── sft/                     ← 模型权重（传给 /load_model）
│   ├── pt0_sft1/
│   │   └── sft/                     ← 训练未完成（无 .done）
│   └── ...（共 47 个）
└── eval_v260306/                     # 评测产物（Daemon 写入）
    ├── pipeline_state.json           ← 状态注册表（核心数据库）
    ├── batch_report.md               ← 横向对比报告（实时更新）
    ├── pipeline_daemon.log           ← 守护进程日志
    ├── pt0_sft0/                     ← 每个模型独立输出目录
    │   ├── eval_pt0_sft0/            ← task_id 目录
    │   │   ├── report.json
    │   │   ├── report.md
    │   │   └── details/
    │   └── default/                  ← ais_bench 临时输出（自动清理）
    └── pt0_sft1/
        └── ...

/opt/eval_workspace/                  # 评测工作区（已部署）
├── .env                             ← 基础配置
├── data/                            ← 评测数据集
└── code/
    ├── eval_entry.py
    └── scripts/
        ├── pipeline_daemon.py       ← 新增：核心守护进程
        └── ...（现有脚本）

run_pipeline.sh                      ← 新增：流水线启动脚本
```

### 2.2 组件关系

```
[pipeline_daemon.py]
      │
      ├── 轮询 ──→ /dpc/exp/v260306/*/  检测 .done 文件
      │
      ├── 读写 ──→ pipeline_state.json   状态持久化
      │
      ├── 调用 ──→ POST /load_model      申请 NPU + 获取服务 URL
      │              POST /unload_model   释放 NPU
      │
      └── 启动 ──→ docker run            隔离评测容器
                     -v /dpc/exp/eval_v260306/<exp>:/app/outputs
                     -e LOCAL_HOST_PORT=<动态端口>
```

---

## 3. 状态机设计

### 3.1 模型生命周期

```
[训练中]
  训练完成 → 写入 .done
                ↓
            [queued]  ← 发现 .done，加入等待队列
                ↓  有空闲 NPU
          [evaluating]  ← 正在评测（持有 1 个 NPU 槽位）
            ↓         ↓
         [done]     [failed]  ← 跳过，记录失败原因
```

### 3.2 `pipeline_state.json` 格式

```json
{
  "last_scan": "2026-03-09T10:30:00",
  "stats": {
    "total_discovered": 12,
    "done": 8,
    "evaluating": 2,
    "queued": 1,
    "failed": 1
  },
  "models": {
    "pt0_sft0": {
      "model_path": "/dpc/exp/v260306/pt0_sft0/sft",
      "status": "done",
      "discovered_at": "2026-03-09T06:00:00",
      "eval_start": "2026-03-09T06:00:15",
      "eval_end": "2026-03-09T07:22:10",
      "model_id": "2378437c",
      "serving_url": "http://188.109.35.159:10051/v1/chat/completions",
      "task_id": "eval_pt0_sft0",
      "avg_accuracy": 78.5,
      "report_path": "/dpc/exp/eval_v260306/pt0_sft0/eval_pt0_sft0/report.json"
    },
    "pt0_sft1": {
      "status": "evaluating",
      "model_path": "/dpc/exp/v260306/pt0_sft1/sft",
      "discovered_at": "2026-03-09T08:00:00",
      "eval_start": "2026-03-09T08:01:00",
      "model_id": "9ea31ec6",
      "serving_url": "http://188.109.35.159:10052/v1/chat/completions",
      "task_id": "eval_pt0_sft1"
    },
    "pt0_sft2": {
      "status": "queued",
      "model_path": "/dpc/exp/v260306/pt0_sft2/sft",
      "discovered_at": "2026-03-09T09:50:00"
    },
    "pt0_sft3": {
      "status": "failed",
      "model_path": "/dpc/exp/v260306/pt0_sft3/sft",
      "error": "load_model API returned 10000: 无空闲npu",
      "eval_start": "2026-03-09T07:00:00",
      "eval_end": "2026-03-09T07:00:05"
    }
  }
}
```

---

## 4. 核心组件详细设计

### 4.1 `scripts/pipeline_daemon.py`

#### 主循环逻辑（伪代码）

```python
def main_loop():
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    running_futures: Dict[str, Future] = {}

    while True:
        state = load_state()

        # Step 1: 回收已完成的 worker，更新状态
        for exp_name, future in list(running_futures.items()):
            if future.done():
                result = future.result()
                update_state(exp_name, result)  # done or failed
                del running_futures[exp_name]

        # Step 2: 扫描新完成的训练实验
        for exp_name in scan_done_experiments():
            if exp_name not in state["models"]:
                add_to_queue(state, exp_name)

        # Step 3: 派发新任务（不超过 MAX_WORKERS 并发）
        free_slots = MAX_WORKERS - len(running_futures)
        queued = get_queued(state)
        for exp_name in queued[:free_slots]:
            mark_evaluating(state, exp_name)
            future = executor.submit(eval_worker, exp_name)
            running_futures[exp_name] = future

        save_state(state)
        log_progress(state)

        # Step 4: 全部完成则退出
        if all_done(state) and not running_futures:
            generate_final_batch_report(state)
            break

        time.sleep(POLL_INTERVAL)
```

#### Worker 线程逻辑

```python
def eval_worker(exp_name: str) -> dict:
    model_path = f"{MODELS_DIR}/{exp_name}/{MODEL_SUBPATH}"
    task_id = f"eval_{exp_name}"
    output_dir = f"{EVAL_DIR}/{exp_name}"
    os.makedirs(output_dir, exist_ok=True)

    # ① 部署模型
    resp = requests.post(f"{DEPLOY_API}/load_model",
                         json={"model_path": model_path}, timeout=120)
    data = resp.json()
    if data["code"] != 200:
        return {"status": "failed", "error": data["message"]}

    model_id = data["config"]["model_id"]
    serving_url = data["config"]["url"]
    host_ip, host_port = parse_url(serving_url)

    try:
        # ② 运行评测容器
        docker_cmd = build_docker_cmd(
            task_id=task_id,
            output_dir=output_dir,
            host_ip=host_ip,
            host_port=host_port,
            model_name=exp_name,
        )
        proc = subprocess.run(docker_cmd, timeout=EVAL_TIMEOUT)

        # ③ 读取报告
        report_path = f"{output_dir}/{task_id}/report.json"
        avg_accuracy = read_accuracy(report_path)

        return {
            "status": "done" if proc.returncode == 0 else "failed",
            "model_id": model_id,
            "serving_url": serving_url,
            "task_id": task_id,
            "avg_accuracy": avg_accuracy,
            "report_path": report_path,
        }
    finally:
        # ④ 无论成功失败，必须卸载模型，释放 NPU
        requests.post(f"{DEPLOY_API}/unload_model",
                      json={"model_id": model_id}, timeout=30)
```

#### `docker run` 命令构造

```python
def build_docker_cmd(task_id, output_dir, host_ip, host_port, model_name):
    return [
        "docker", "run", "--rm",
        "-e", "PYTHONUNBUFFERED=1",
        "--env-file", f"{WORKSPACE}/.env",
        # 覆盖 .env 中的 LOCAL_* 为本次动态分配的模型服务地址
        "-e", f"LOCAL_HOST_IP={host_ip}",
        "-e", f"LOCAL_HOST_PORT={host_port}",
        "-e", f"LOCAL_MODEL_NAME={model_name}",
        "-e", "LOCAL_CONCURRENCY=50",
        # 数据挂载（共享只读）
        "-v", f"{WORKSPACE}/data:/app/data",
        # 代码挂载（共享只读）
        "-v", f"{WORKSPACE}/code/eval_entry.py:/app/eval_entry.py",
        "-v", f"{WORKSPACE}/code/scripts:/app/scripts",
        # 输出目录隔离（每个模型独立，避免并发冲突）
        "-v", f"{output_dir}:/app/outputs",
        IMAGE_TAG,
        "python", "eval_entry.py",
        "--task-id", task_id,
        "--model-config", "local_qwen",
        "--tasks", "1", "34", "36", "43", "44", "60",
        "--generic-datasets",
        "mmlu_redux_gen_5_shot_str", "ceval_gen_0_shot_str",
        "gpqa_gen_0_shot_str", "bbh_gen_3_shot_cot_chat",
        "BFCL_gen_simple", "ifeval_0_shot_gen_str",
        "math500_gen_0_shot_cot_chat_prompt", "aime2025_gen_0_shot_chat_prompt",
        "humaneval_gen_0_shot", "livecodebench_0_shot_chat_v6",
        "telemath_gen_0_cot_shot", "teleqna_gen_0_shot",
        "tspec_gen_0_shot", "teledata_gen_0_shot",
        "telequad_gen_0_shot", "tele_exam_gen_0_shot",
        "tele_exam_gen_0_shot_str",
    ]
```

### 4.2 `batch_report.md` 格式（实时更新）

```markdown
# 批量评测对比报告

更新时间: 2026-03-09 12:30:00
进度: 10/47 完成 | 2 评测中 | 3 排队 | 32 等待训练

## 模型对比（已完成）

| 模型 | 平均准确率 | 自定义任务 | 通用基准 | 耗时 | 状态 |
|------|-----------|-----------|---------|------|------|
| pt0_sft0 | 78.50% | 85.00% | 75.00% | 82min | ✅ |
| pt0_sft1 | 76.20% | 82.00% | 73.00% | 79min | ✅ |
| pt0_sft3 | - | - | - | - | ❌ failed |

## 当前进行中

| 模型 | 开始时间 | 服务端口 |
|------|---------|---------|
| pt1_sft0 | 11:45:00 | 10052 |
| pt1_sft1 | 11:46:00 | 10053 |
```

### 4.3 配置参数（`pipeline_daemon.py` 头部）

```python
# ── 路径配置 ──────────────────────────────────────────────────────────
MODELS_DIR      = Path("/dpc/exp/v260306")        # 训练产物根目录
EVAL_DIR        = Path("/dpc/exp/eval_v260306")   # 评测输出根目录
WORKSPACE       = Path("/opt/eval_workspace")     # Docker 工作区
MODEL_SUBPATH   = "sft"                           # 模型权重子目录名
DONE_MARKER     = ".done"                         # 训练完成标记文件名

# ── 推理服务 ──────────────────────────────────────────────────────────
DEPLOY_API      = "http://188.109.35.159:8080"    # 一键部署 API 地址

# ── 并发控制 ──────────────────────────────────────────────────────────
MAX_WORKERS     = 8                               # 最大并发评测数（= NPU 数量）
POLL_INTERVAL   = 600                             # 轮询间隔（秒），10 分钟
EVAL_TIMEOUT    = 14400                           # 单模型评测超时（秒），4 小时

# ── Docker 配置 ───────────────────────────────────────────────────────
IMAGE_TAG       = "benchmark-eval:latest"

# ── 评测任务列表（与 run_mixed_benchmark.sh 保持一致）─────────────────
EVAL_TASKS      = ["1", "34", "36", "43", "44", "60"]
EVAL_GENERIC    = [
    "mmlu_redux_gen_5_shot_str", "ceval_gen_0_shot_str",
    "gpqa_gen_0_shot_str", "bbh_gen_3_shot_cot_chat",
    "BFCL_gen_simple", "ifeval_0_shot_gen_str",
    "math500_gen_0_shot_cot_chat_prompt", "aime2025_gen_0_shot_chat_prompt",
    "humaneval_gen_0_shot", "livecodebench_0_shot_chat_v6",
    "telemath_gen_0_cot_shot", "teleqna_gen_0_shot",
    "tspec_gen_0_shot", "teledata_gen_0_shot",
    "telequad_gen_0_shot", "tele_exam_gen_0_shot",
    "tele_exam_gen_0_shot_str",
]
```

---

## 5. 关键设计决策

### 5.1 输出目录隔离（解决并发冲突）

`eval_entry.py` 在启动时会清空 `/app/outputs/default/`。若多个容器挂载同一个宿主机目录，会相互覆盖。

**解决方案**：每个评测容器挂载独立的宿主机目录：

```
-v /dpc/exp/eval_v260306/pt0_sft0:/app/outputs   ← 模型 A 的容器
-v /dpc/exp/eval_v260306/pt0_sft1:/app/outputs   ← 模型 B 的容器（完全隔离）
```

容器内路径相同（`/app/outputs`），但宿主机路径各不相同，并发安全。

### 5.2 NPU 槽位管理

Daemon 维护一个 `running_futures` 字典（`{exp_name: Future}`），其长度即为当前占用的 NPU 数。
只有 `len(running_futures) < MAX_WORKERS` 时才派发新任务，不依赖 API 的"无空闲npu"错误进行控制，
避免竞态条件。

若 `/load_model` 仍返回"无空闲npu"（如外部占用），该任务标记为 `failed`，下次轮询时重新尝试（改为
重新入队而非永久 failed）。

### 5.3 状态文件并发写入保护

多个 worker 线程同时完成时会同时写 `pipeline_state.json`，使用文件级互斥锁（`threading.Lock`）保护。

### 5.4 Daemon 崩溃恢复

- 启动时加载已有的 `pipeline_state.json`
- 状态为 `evaluating` 的模型：说明上次 Daemon 崩溃时正在评测。检查对应 Docker 容器是否仍在运行：
  - 仍在运行 → 继续监控（重新加入 running_futures）
  - 不在运行 → 重置为 `queued`，重新评测

---

## 6. 操作手册

### 6.1 前提条件检查

在启动流水线前，确认以下条件：

```bash
# 1. Docker 镜像已存在
docker image inspect benchmark-eval:latest

# 2. 工作区结构完整
ls /opt/eval_workspace/
# 应有: .env  data/  code/eval_entry.py  code/scripts/

# 3. 推理服务 API 可达
curl -s http://188.109.35.159:8080/load_model   # 会报错但能连通即可

# 4. 评测输出目录已创建
mkdir -p /dpc/exp/eval_v260306

# 5. Python3 requests 库已安装（Daemon 运行时依赖）
python3 -c "import requests; print('OK')"
# 若缺少：pip3 install requests
```

### 6.2 启动流水线

```bash
# 放置脚本到工作区
cp scripts/pipeline_daemon.py /opt/eval_workspace/code/scripts/

# 启动（后台运行，SSH 断开后持续运行）
bash run_pipeline.sh

# 输出示例：
# 🔄 流水线守护进程已启动（后台模式）
# 📁 训练实验目录: /dpc/exp/v260306
# 📊 评测输出目录: /dpc/exp/eval_v260306
# 📄 日志文件: /dpc/exp/eval_v260306/pipeline_daemon.log
# 👀 实时日志: tail -f /dpc/exp/eval_v260306/pipeline_daemon.log
# ✅ 后台 PID: 23456，安全断开 SSH 即可。
```

### 6.3 实时监控

```bash
# 查看进度日志（推荐）
tail -f /dpc/exp/eval_v260306/pipeline_daemon.log

# 查看当前状态摘要
python3 -c "
import json
s = json.load(open('/dpc/exp/eval_v260306/pipeline_state.json'))
print('=== 评测流水线状态 ===')
for k, v in s.get('stats', {}).items():
    print(f'  {k}: {v}')
print('=== 各模型状态 ===')
for name, m in s['models'].items():
    acc = m.get('avg_accuracy', '-')
    print(f'  {name}: {m[\"status\"]}  准确率: {acc}')
"

# 查看横向对比报告
cat /dpc/exp/eval_v260306/batch_report.md

# 确认评测容器正在运行
docker ps --filter ancestor=benchmark-eval:latest

# 查看某个模型的详细报告
cat /dpc/exp/eval_v260306/pt0_sft0/eval_pt0_sft0/report.json | python3 -m json.tool
```

### 6.4 手动干预

#### 强制重跑某个模型

```bash
# 1. 编辑 state.json，将该模型状态改回 queued
python3 -c "
import json
f = '/dpc/exp/eval_v260306/pipeline_state.json'
s = json.load(open(f))
s['models']['pt0_sft3']['status'] = 'queued'
s['models']['pt0_sft3'].pop('error', None)
json.dump(s, open(f, 'w'), ensure_ascii=False, indent=2)
print('已重置 pt0_sft3 为 queued')
"
# Daemon 下次轮询（最多 10 分钟后）会自动重新调度
```

#### 暂停流水线

```bash
# 查找 Daemon PID
cat /dpc/exp/eval_v260306/pipeline_daemon.pid
# 或
pgrep -f pipeline_daemon.py

# 发送暂停信号（SIGTERM，Daemon 会在当前轮完成后安全退出）
kill $(cat /dpc/exp/eval_v260306/pipeline_daemon.pid)
```

#### 查看某模型评测的实时日志

评测日志直接包含在 `pipeline_daemon.log` 中，可通过模型名过滤：

```bash
grep "pt0_sft2" /dpc/exp/eval_v260306/pipeline_daemon.log
```

### 6.5 终止所有评测容器

```bash
# 停止所有正在运行的评测容器
docker stop $(docker ps -q --filter ancestor=benchmark-eval:latest)

# 同时停止 Daemon
kill $(cat /dpc/exp/eval_v260306/pipeline_daemon.pid)
```

### 6.6 故障排查

| 现象 | 排查方法 | 解决办法 |
|------|---------|---------|
| 模型长时间停在 `queued` | 检查 NPU 占用：`docker ps` | 确认 MAX_WORKERS 未超出空闲 NPU 数 |
| `/load_model` 返回"无空闲npu" | `docker ps` 查看容器数量 | 等待其他评测完成或手动 `unload` 残留模型 |
| Daemon 进程意外退出 | `tail /dpc/exp/eval_v260306/pipeline_daemon.log` | 重新执行 `bash run_pipeline.sh`（会续跑） |
| 某模型 Docker 容器异常退出 | 该模型 state 自动变为 `failed` | 修改 state 为 `queued` 后重新调度 |
| `pipeline_state.json` 损坏 | 文件格式错误 | 从备份恢复，或手动重建（仅需保留 `done` 状态的条目） |

### 6.7 流水线结束后

```bash
# 查看最终对比报告
cat /dpc/exp/eval_v260306/batch_report.md

# 导出 JSON 格式（供上层系统解析）
cat /dpc/exp/eval_v260306/pipeline_state.json

# 清理评测容器（应已全部退出）
docker ps --filter ancestor=benchmark-eval:latest
```

---

## 7. 新增文件清单

| 文件路径 | 说明 |
|---------|------|
| `scripts/pipeline_daemon.py` | 核心守护进程 |
| `run_pipeline.sh` | 流水线启动脚本 |

**不修改任何现有文件**（`eval_entry.py`、`run_mixed_benchmark.sh`、`deploy.md` 等保持不变）。

---

## 8. 与现有架构关系

```
现有架构:                        新增能力:
run_mixed_benchmark.sh          run_pipeline.sh
  └── docker run                  └── pipeline_daemon.py
        └── eval_entry.py               ├── 轮询 .done 文件
              └── ais_bench             ├── 调用 /load_model + /unload_model
                                        ├── 并发 docker run（复用现有镜像）
                                        └── 生成 batch_report.md
```

新方案**完全复用**现有的 Docker 镜像和 `eval_entry.py`，仅在外层新增调度编排层。
