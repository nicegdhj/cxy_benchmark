# ── 基础镜像：python 3.10 精简版 ────────────────────────────────────
FROM python:3.10-slim

WORKDIR /app

# ── 系统依赖（git 用于 setup.py 获取版本信息）───────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── Python 依赖（build 时从公网安装，打包进镜像，私域无需网络）────
COPY requirements/runtime.txt requirements/runtime.txt
COPY requirements/api.txt requirements/api.txt

# cpu-only torch 大幅减小体积（API 模式不需要 GPU）
RUN pip install --no-cache-dir \
        torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir \
        python-dotenv \
        -r requirements/runtime.txt \
        -r requirements/api.txt

# ── 安装 ais_bench 包（注册 ais_bench CLI 命令）─────────────────────
COPY ais_bench/ ais_bench/
COPY setup.py README.md ./
RUN pip install --no-cache-dir -e . --no-deps

# ── 提前下载 NLTK 数据（离线环境无法临时下载）──────────────────────
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

# ── 复制脚本和配置（不含数据和密钥）────────────────────────────────
COPY scripts/ scripts/
COPY eval_entry.py .
COPY run_maas_demo.sh .

# ── 数据 / 输出 通过 -v 挂载，不打包进镜像 ──────────────────────────
# -v /host/data:/app/data/custom_task
# -v /host/results:/app/outputs
VOLUME ["/app/data", "/app/outputs"]

# ── 默认命令（显示帮助）─────────────────────────────────────────────
CMD ["python", "eval_entry.py", "--help"]
