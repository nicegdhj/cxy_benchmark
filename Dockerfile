# ── 基础镜像：python 3.10 精简版 ────────────────────────────────────
FROM python:3.10-slim

WORKDIR /app

# 强制 Python stdout/stderr 不缓冲，确保日志实时输出（与本地终端行为一致）
ENV PYTHONUNBUFFERED=1

# ── 换阿里云 apt 源（加速国内构建）──────────────────────────────────
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    || sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
    apt-get update && apt-get install -y --no-install-recommends \
        curl \
        vim \
    && rm -rf /var/lib/apt/lists/*

# ── 全局 pip 换清华源 ─────────────────────────────────────────────────
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# ── 第 1 层：torch（~1.2G，几乎不变，独立缓存）────────────────────
# cpu-only torch（--extra-index-url 保证从清华找不到时回退到官方 CPU whl 源）
RUN pip install --no-cache-dir \
        torch --extra-index-url https://download.pytorch.org/whl/cpu

# ── 第 2 层：核心运行时依赖 ────────────────────────────────────────
COPY requirements/runtime.txt requirements/runtime.txt
COPY requirements/api.txt requirements/api.txt
RUN pip install --no-cache-dir \
        python-dotenv \
        -r requirements/runtime.txt \
        -r requirements/api.txt

# ── 第 3 层：BFCL 评测专用依赖 ────────────────────────────────────
COPY requirements/datasets/bfcl_dependencies.txt requirements/datasets/bfcl_dependencies.txt
RUN pip install --no-cache-dir \
        -r requirements/datasets/bfcl_dependencies.txt --no-deps

# ── 安装 ais_bench 包（注册 ais_bench CLI 命令）─────────────────────
COPY ais_bench/ ais_bench/
COPY setup.py README.md ./
RUN pip install --no-cache-dir -e . --no-deps

# ── 强制升级 huggingface-hub（绕过其他包的版本约束）────────────────
# transformers 5.x 要求 >=1.3.0，但部分包会将其拉低到 0.34.x
# 在所有依赖装完后最后强制覆盖，确保运行时版本正确
RUN pip install --no-cache-dir --force-reinstall "huggingface-hub==1.5.0"

# ── 提前下载 NLTK 数据（离线环境无法临时下载）──────────────────────
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

# ── 数据 / 输出 / 代码 均通过 -v 挂载，不打包进镜像 ─────────────────
# -v /host/data:/app/data
# -v /host/outputs:/app/outputs
# -v /host/code/eval_entry.py:/app/eval_entry.py
# -v /host/code/scripts:/app/scripts
# （可选）-v /host/code/ais_bench:/app/ais_bench  # 若需修改评测框架内部逻辑
# -v /host/data:/app/data
# -v /host/results:/app/outputs
VOLUME ["/app/data", "/app/outputs"]

# ── 默认命令（显示帮助）─────────────────────────────────────────────
CMD ["python", "eval_entry.py", "--help"]
