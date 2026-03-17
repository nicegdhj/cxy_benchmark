# -*- coding: utf-8 -*-
# @Time    : 2026/3/16 13:54
# @Author  : jia
# @File    : vllm_server.py
# @Desc    :
# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sqlite3
import subprocess
import time
import uuid

import psutil
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="vLLM NPU Manager")

DB_PATH = "models.db"


# =============== 初始化 SQLite ===============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS models (
        model_id TEXT PRIMARY KEY,
        model_path TEXT,
        npu_id INTEGER,
        pid INTEGER,
        port INTEGER,
        status TEXT
    )
    """)
    conn.commit()
    conn.close()


init_db()


# =============== 工具函数部分 ===============
def get_npu_smi_info():
    try:
        result = subprocess.run(["npu-smi", "info"], capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        print(f"❌ npu-smi 执行失败: {e}")
        return ""


def parse_npu_process_table(output: str):
    """返回 {npu_id: [pid1, pid2, ...]}"""
    npu_processes = {}
    process_line = re.compile(r"^\|\s*(\d+)\s+\d+\s+\|\s*(\d+)\s*\|")

    for line in output.splitlines():
        m = process_line.match(line)
        if m:
            npu_id, pid = int(m.group(1)), int(m.group(2))
            npu_processes.setdefault(npu_id, []).append(pid)
            continue

        m2 = re.search(r"No running processes found in NPU\s+(\d+)", line)
        if m2:
            npu_id = int(m2.group(1))
            npu_processes.setdefault(npu_id, [])

    return dict(sorted(npu_processes.items()))


def get_idle_npu():
    """返回一个空闲的NPU id，如果没有，返回None"""
    output = get_npu_smi_info()
    if not output:
        return None
    npu_processes = parse_npu_process_table(output)
    idle_npus = [k for k, v in npu_processes.items() if not v]
    if not idle_npus:
        return None
    return idle_npus[0]


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


def kill_process(parent_pid):
    """
    找到并杀死指定 PID 的所有子孙进程
    """
    try:
        parent = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        print(f"主进程 {parent_pid} 不存在。")
        return
    # recursive=True 会递归找到所有的子进程（孙子、曾孙等）
    descendants = parent.children(recursive=True)

    if not descendants:
        print(f"进程 {parent_pid} 没有子孙进程。")
        return

    print(f"发现 {len(descendants)} 个子孙进程，正在清理...")

    for child in descendants:
        try:
            # 同样建议先 terminate，给进程“交代遗言”的时间
            child.terminate()
        except psutil.NoSuchProcess:
            continue
    # 等待所有进程结束，处理那些“死硬分子”
    gone, alive = psutil.wait_procs(descendants, timeout=3)
    for p in alive:
        print(f"进程 {p.pid} 未响应，强制杀掉...")
        p.kill()


# =============== FastAPI 模型定义 ===============
class LoadModelRequest(BaseModel):
    model_path: str


class LoadModelResponse(BaseModel):
    code: int
    message: str
    config: dict[str, str]


class UnloadModelRequest(BaseModel):
    model_id: str


class MsgResponse(BaseModel):
    code: int
    message: str


# =============== 接口实现 ===============

@app.post("/load_model", response_model=LoadModelResponse)
def load_model(req: LoadModelRequest):
    model_path = req.model_path
    npu_id = get_idle_npu()
    if npu_id is None:
        return LoadModelResponse(code=10000, message="无空闲npu")

    model_id = str(uuid.uuid4())[:8]
    pid, port = launch_vllm_service(model_path, npu_id)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO models (model_id, model_path, npu_id, pid, port, status) VALUES (?, ?, ?, ?, ?, ?)",
        (model_id, model_path, npu_id, pid, port, "running")
    )
    conn.commit()
    conn.close()

    model_url = f"http://188.109.35.159:{port}/v1/chat/completions"

    return LoadModelResponse(
        code=200,
        message="模型已启动",
        config={
            "model_id": model_id,
            "model_name": "qwen3-14b",
            "url": model_url,
        }
    )


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

    from collections import deque
    with open(log_path, "r") as f:
        lines = list(deque(f, maxlen=tail))
    return {"model_id": model_id, "npu_id": npu_id, "lines": lines}


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


@app.get("/")
def root():
    return {"message": "vLLM NPU Manager 正在运行"}


# =============== 启动命令 (开发调试用) ===============
# nohup uvicorn fastapi_server:app --host 0.0.0.0 --port 8090 > fastapi_server.log 2>&1 &

"""
curl -X POST "http://188.109.35.159:8080/load_model" \
  -H "Content-Type: application/json" \
  -d '{"model_path": "/dpc/exp/v260306/pt15_sft0/sft"}'

curl -X POST "http://188.109.35.159:8080/unload_model" \
  -H "Content-Type: application/json" \
  -d '{"model_id": "22283ede"}'
"""
