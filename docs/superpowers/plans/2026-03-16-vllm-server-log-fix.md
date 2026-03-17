# vLLM Server 日志管道优化 & Docker-in-Docker 远期规划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `vllm_server.py` 的日志管道反压缺陷，消除多模型同容器部署时"跑几个小时后挂死"的问题

**Architecture:** 将 vLLM 子进程的 stdout 从 PIPE 模式改为直接写日志文件，消除 daemon 线程 + pipe buffer 的连锁故障链；同时增加健康检查接口，提升运维可观测性

**Tech Stack:** Python 3, FastAPI, subprocess, SQLite

---

## 问题诊断

### 故障现象

- 8 个 vLLM 模型在**同一容器**内通过 `vllm_server.py` 以子进程方式启动
- 运行数小时后全部挂死，NPU 不释放，机器失去响应
- 在**独立 Docker 容器**中运行时，100% 成功

### 已排除的假设

| 假设 | 排除原因 |
|------|----------|
| NPU 显存不足 | Qwen3-14B (~30GB) 在 2×910C (192GB) 上绰绰有余 |
| CPU 内存不足 | 机器有 2TB RAM |
| vLLM 启动参数过激进 | 单模型资源充裕，不是瓶颈 |

### 根因：日志管道 (PIPE) 连锁阻塞

当前代码 (`scripts/vllm_server.py:123-148`) 的数据流：

```
vLLM 子进程 ×8 → OS pipe buffer (64KB) ×8 → daemon reader 线程 ×8 → print() 抢同一把锁 → 容器 stdout
```

**三个致命缺陷：**

1. **daemon=True 线程随主进程死亡** (line 148)
   - FastAPI/uvicorn 任何异常退出 → 8 个 reader 线程立即死亡
   - vLLM 子进程仍在运行（`start_new_session=True`）
   - pipe 无人消费 → 64KB buffer 秒满 → vLLM `write()` 阻塞 → 推理卡死

2. **8 个 reader 线程竞争同一个 stdout 锁**
   - `print()` 是线程安全的，靠全局 IO 锁实现
   - 8 路高吞吐日志串行化 → reader 消费速度 < vLLM 产出速度
   - pipe buffer 逐渐积压 → 最终阻塞

3. **`stderr=subprocess.STDOUT` 放大日志量** (line 127)
   - vLLM 的 warning、progress bar、traceback 全部合入 stdout
   - 日志量翻倍，加速 pipe 积压

**为什么独立 Docker 不受影响：**
- 每个容器有独立的 stdout，由 Docker log driver 直接消费
- vLLM 是容器 PID 1，不依赖任何外部进程
- 容器间完全隔离，无锁竞争

---

## Phase 1：日志管道修复（当前批次，立即执行）

> 保持现有架构（同容器内 8 个子进程），仅修复日志通路

### 文件变更清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `scripts/vllm_server.py` | 日志写文件 + 启动检测 + 健康检查 + 调试接口 |

---

### Task 1: 日志输出从 PIPE 改为文件直写

**Files:**
- Modify: `scripts/vllm_server.py:88-153` (launch_vllm_service 函数)

**变更说明：**
- 移除 `subprocess.PIPE`、daemon reader 线程、`threading.Event` 整套机制
- vLLM stdout/stderr 直接写入独立日志文件 `logs/vllm_npu{id}.log`
- 父进程通过轮询日志文件检测 "Application startup complete" 来判断就绪
- 父进程崩溃不影响子进程（文件 fd 由子进程内核持有）

- [x] **Step 1: 改写 launch_vllm_service 函数**

将整个函数替换为文件直写版本：

```python
def launch_vllm_service(model_path: str, npu_id: int):
    """启动 vLLM 服务并返回 PID，日志直写文件避免 pipe 反压"""
    env_vars = {
        "ASCEND_RT_VISIBLE_DEVICES": f"{npu_id * 2},{npu_id * 2 + 1}",
        "TASK_QUEUE_ENABLE": "1",
        "LD_PRELOAD": f"/usr/lib64/libjemalloc.so.2:{os.environ.get('LD_PRELOAD', '')}",
        "HCCL_OP_EXPANSION_MODE": "AIV",
        "VLLM_ASCEND_ENABLE_FLASHCOMM1": "1",
    }

    current_env = os.environ.copy()
    current_env.update(env_vars)

    port = 10051 + npu_id
    vllm_args = {
        "--served-model-name": "qwen3-14b",
        "--trust-remote-code": None,
        "--async-scheduling": None,
        "--distributed-executor-backend": "mp",
        "--tensor-parallel-size": "2",
        "--max-model-len": "40960",
        "--max-num-batched-tokens": "256",
        "--compilation-config": '{"cudagraph_mode": "FULL_DECODE_ONLY"}',
        "--additional-config": '{"pa_shape_list":[48,64,72,80], "weight_prefetch_config":{"enabled":true}}',
        "--port": str(port),
        "--block-size": "128",
        "--gpu-memory-utilization": "0.9",
    }

    cmd = ["vllm", "serve", model_path]
    for key, value in vllm_args.items():
        cmd.append(key)
        if value is not None:
            cmd.append(value)

    # 日志直写文件，不经过 pipe
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"vllm_npu{npu_id}.log")
    log_file = open(log_path, "w")

    process = subprocess.Popen(
        cmd,
        env=current_env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log_file.close()  # 父进程关闭 fd，子进程继承的 fd 继续写

    print(f"✅ 启动模型 {model_path}，PID={process.pid}，NPU={npu_id}，日志: {log_path}")

    # 轮询日志文件检测启动完成
    for i in range(300):
        time.sleep(1)
        try:
            with open(log_path, "r") as f:
                content = f.read()
                if "Application startup complete" in content:
                    print(f"✅ NPU-{npu_id} 服务启动完毕（耗时 {i+1}s）")
                    return process.pid, port
                # 检测启动失败（进程已退出）
                if process.poll() is not None:
                    print(f"❌ NPU-{npu_id} 进程异常退出 (code={process.returncode})")
                    print(f"   查看日志: tail -100 {log_path}")
                    raise RuntimeError(f"vLLM 启动失败，exit={process.returncode}")
        except FileNotFoundError:
            pass

    print(f"⚠️ NPU-{npu_id} 启动超时(300s)，服务可能仍在加载中，日志: {log_path}")
    return process.pid, port
```

- [x] **Step 2: 移除顶层 threading import（如无其他使用）**

检查文件中 `threading` 是否还有其他用途。如果没有，从 import 中移除，并在顶层添加 `time`：

```python
# 移除:
import threading
# 新增:
import time
```

- [x] **Step 3: 验证修改**

在开发机上检查语法：
```bash
cd /Users/jia/MyProjects/pythonProjects/cmcc_cxy/Bprocss/benchmark
python -c "import ast; ast.parse(open('scripts/vllm_server.py').read()); print('语法正确')"
```
Expected: `语法正确`

- [ ] **Step 4: Commit** *(待用户确认后执行)*

```bash
git add scripts/vllm_server.py
git commit -m "fix(vllm_server): 日志从 PIPE 改为文件直写，消除反压死锁"
```

---

### Task 2: 增加 call_api 调试日志修复

**Files:**
- Modify: `scripts/handle_run/run_pipeline.sh:131-134` (call_api 函数)

**变更说明：**

`scripts/handle_run/run_pipeline.sh:131-134` 中 `call_api` 函数有个 bug——`echo` 语句在 `local` 声明之前执行，会打印未赋值的变量。这不影响功能但会在日志中产生误导输出。此项为顺手修复，不在本次 scope 内，记录待办即可。

---

### Task 3: 增加健康检查与日志查看接口

**Files:**
- Modify: `scripts/vllm_server.py` (新增 API endpoints)

**变更说明：**
- `/health` 接口：检查所有已注册模型的进程存活状态
- `/logs/{model_id}` 接口：返回指定模型最近 N 行日志（便于远程排障）
- `/models` 接口：列出所有已注册模型及其状态

- [x] **Step 1: 新增 /health 接口**

在文件末尾 `root()` 之前添加：

```python
@app.get("/health")
def health_check():
    """检查所有已注册模型的进程存活状态"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT model_id, model_path, npu_id, pid, port, status FROM models")
    rows = c.fetchall()
    conn.close()

    results = []
    for model_id, model_path, npu_id, pid, port, status in rows:
        alive = psutil.pid_exists(pid)
        results.append({
            "model_id": model_id,
            "npu_id": npu_id,
            "pid": pid,
            "port": port,
            "status": "running" if alive else "dead",
            "model_path": model_path,
        })
    all_healthy = all(r["status"] == "running" for r in results)
    return {"healthy": all_healthy, "models": results}
```

- [x] **Step 2: 新增 /logs/{model_id} 接口**

```python
@app.get("/logs/{model_id}")
def get_model_logs(model_id: str, tail: int = 100):
    """查看指定模型的最近 N 行日志"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT npu_id FROM models WHERE model_id=?", (model_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return {"code": 10001, "message": "未找到该模型ID"}

    npu_id = row[0]
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    log_path = os.path.join(log_dir, f"vllm_npu{npu_id}.log")

    if not os.path.exists(log_path):
        return {"code": 10002, "message": f"日志文件不存在: {log_path}"}

    # 使用 deque 只保留最后 tail 行，避免大日志文件撑爆内存
    from collections import deque
    with open(log_path, "r") as f:
        lines = list(deque(f, maxlen=tail))
    return {"model_id": model_id, "npu_id": npu_id, "lines": lines}
```

- [x] **Step 3: 新增 /models 列表接口**

```python
@app.get("/models")
def list_models():
    """列出所有已注册的模型"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT model_id, model_path, npu_id, pid, port, status FROM models")
    rows = c.fetchall()
    conn.close()

    return {"count": len(rows), "models": [
        {"model_id": r[0], "model_path": r[1], "npu_id": r[2],
         "pid": r[3], "port": r[4], "status": r[5]}
        for r in rows
    ]}
```

- [x] **Step 4: 验证语法**

```bash
python -c "import ast; ast.parse(open('scripts/vllm_server.py').read()); print('语法正确')"
```

- [ ] **Step 5: Commit**

```bash
git add scripts/vllm_server.py
git commit -m "feat(vllm_server): 增加 /health /logs /models 运维接口"
```

---

### Task 4: unload_model 适配新的日志机制

**Files:**
- Modify: `scripts/vllm_server.py:241-259` (unload_model 函数)

**变更说明：**
- 卸载模型后清理对应的日志文件（可选，避免磁盘堆积）
- 增加进程已死的容错处理

- [x] **Step 1: 改写 unload_model**

```python
@app.post("/unload_model", response_model=MsgResponse)
def unload_model(req: UnloadModelRequest):
    model_id = req.model_id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT pid, npu_id FROM models WHERE model_id=?", (model_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return MsgResponse(code=10001, message="未找到该模型ID")

    pid, npu_id = row
    kill_process(pid)

    # 清理日志文件
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    log_path = os.path.join(log_dir, f"vllm_npu{npu_id}.log")
    if os.path.exists(log_path):
        os.rename(log_path, log_path + ".unloaded")

    c.execute("DELETE FROM models WHERE model_id=?", (model_id,))
    conn.commit()
    conn.close()

    return MsgResponse(code=200, message=f"模型 {model_id} 已卸载")
```

- [ ] **Step 2: Commit**

```bash
git add scripts/vllm_server.py
git commit -m "fix(vllm_server): unload_model 适配日志文件机制"
```

---

## Phase 2：Docker-in-Docker 改造（远期，待确认配置后执行）

> 将 vLLM 推理服务从子进程改为独立 Docker 容器，实现完全隔离

### 前置条件（需用户确认）

| 项目 | 需要的信息 | 状态 |
|------|-----------|------|
| vLLM 推理镜像名 | 之前成功的独立 Docker 用的什么镜像？ | ❓ 待确认 |
| NPU 设备映射方式 | `--device /dev/davinci0` 还是 `--runtime ascend`？ | ❓ 待确认 |
| 管理容器 Dockerfile | 当前的 Dockerfile 路径？ | ❓ 待确认 |
| 模型路径挂载 | `/dpc/exp/...` 在容器内如何映射？ | ❓ 待确认 |
| 网络模式 | `--network host` 还是端口映射？ | ❓ 待确认 |

### 预期改造范围

```
管理容器:
  - 挂载 /var/run/docker.sock（Docker-out-of-Docker 模式）
  - vllm_server.py 中 subprocess.Popen → docker run 命令
  - kill_process() → docker stop/rm
  - SQLite 表增加 container_id 字段

推理容器:
  - 每个容器绑定 2 张 NPU（ASCEND_RT_VISIBLE_DEVICES）
  - 独立日志卷
  - 独立网络端口
```

**此 Phase 在用户提供上述配置信息后再详细展开。**
