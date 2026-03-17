#!/usr/bin/env python3
"""
本地 Mock 评估模型服务器
========================
模拟 72B 打分模型的 /v1/chat/completions OpenAI 兼容接口。
在本地启动后，配合 test_llm_judge.py 验证 LLMJudgeEvaluator 的完整代码路径。

用法：
    python mock_eval_server.py [--port 19999] [--score fixed|random|echo]

评分策略（--score）：
    fixed   每次固定返回 0.8 分（默认）
    random  在 max_score 范围内随机返回一个分数
    echo    从 prompt 中解析 max_score 并返回满分（用于验证满分路径）
"""

import argparse
import json
import random
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


SCORE_MODE = "fixed"   # 全局评分策略，由 CLI 参数覆盖


def _extract_max_score(text: str) -> float:
    """从 prompt 文本中解析 max_score 字段（如 'The maximum score you can give is 5.'）"""
    match = re.search(r"maximum score you can give is ([\d.]+)", text)
    if match:
        return float(match.group(1))
    return 1.0


def _make_score_text(prompt_text: str) -> str:
    """根据评分策略生成一段带有分数的自然语言回复"""
    max_score = _extract_max_score(prompt_text)

    if SCORE_MODE == "random":
        score = round(random.uniform(0, max_score), 1)
    elif SCORE_MODE == "echo":
        score = max_score
    else:  # fixed
        score = round(min(0.8 * max_score, max_score), 1)

    return (
        f"Based on the provided answer and the correct reference, "
        f"the student's response demonstrates a reasonable understanding. "
        f"Score: {score}"
    )


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # 抑制默认日志，改为自定义
        print(f"[MockServer] {self.address_string()} - {format % args}")

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        # 读取请求体
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}

        # 提取 prompt 文本用于评分
        messages = payload.get("messages", [])
        prompt_text = " ".join(m.get("content", "") for m in messages)
        score_text = _make_score_text(prompt_text)

        # 构造 OpenAI 格式响应
        response = {
            "id": f"mock-{int(time.time()*1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.get("model", "mock-72b"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": score_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
        }

        body_bytes = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)


def main():
    global SCORE_MODE
    parser = argparse.ArgumentParser(description="Mock Eval Model Server")
    parser.add_argument("--port", type=int, default=19999, help="监听端口（默认 19999）")
    parser.add_argument(
        "--score",
        choices=["fixed", "random", "echo"],
        default="fixed",
        help="评分策略：fixed=固定0.8倍满分，random=随机，echo=满分",
    )
    args = parser.parse_args()
    SCORE_MODE = args.score

    server = HTTPServer(("127.0.0.1", args.port), MockHandler)
    print(f"[MockServer] 启动成功：http://127.0.0.1:{args.port}/v1/chat/completions")
    print(f"[MockServer] 评分策略：{SCORE_MODE}")
    print("[MockServer] 按 Ctrl+C 停止\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[MockServer] 已停止")


if __name__ == "__main__":
    main()
