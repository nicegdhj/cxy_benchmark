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
import threading
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
    """启动 vLLM 服务并返回 PID"""
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

    process = subprocess.Popen(
        cmd,
        env=current_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # 行缓冲
        start_new_session=True  # 避免信号干扰
    )

    print(f"✅ 启动模型 {model_path}，PID={process.pid}，NPU={npu_id}")

    ready_flag = threading.Event()

    # 后台线程异步读取，防止 PIPE 阻塞
    def reader(pipe):
        for line in iter(pipe.readline, ''):
            line = line.strip()
            if line:
                print(f"[vLLM-{npu_id}] {line}")
            if "Application startup complete" in line:
                print("✅ 服务器启动完毕！")
                ready_flag.set()
        pipe.close()

    threading.Thread(target=reader, args=(process.stdout,), daemon=True).start()

    if not ready_flag.wait(timeout=300):
        print("⚠️ 启动超时，可能未检测到启动完成日志，但服务已在后台运行。")

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
    c.execute("SELECT pid FROM models WHERE model_id=?", (model_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return MsgResponse(code=10001, message="未找到该模型ID")

    pid = row[0]
    kill_process(pid)

    c.execute("DELETE FROM models WHERE model_id=?", (model_id,))
    conn.commit()
    conn.close()

    return MsgResponse(code=200, message=f"模型 {model_id} 已卸载")


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
