# -*- coding= utf-8 -*-
# @Time    = 2026/1/22 17=37
# @Author  = jia
# @File    = maas.py
# @Desc    =
import os
from pathlib import Path

from dotenv import load_dotenv

from ais_bench.benchmark.models import MaaSAPI, VLLMCustomAPIChat
from ais_bench.benchmark.utils.postprocess.model_postprocessors import (
    extract_non_reasoning_content,
)

# 从项目根目录加载 .env 文件（不覆盖已有的系统环境变量）
_env_path = Path(__file__).resolve().parents[4] / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

models = [
    dict(
        attr="service",
        type=MaaSAPI,
        abbr="maas-api",
        path="",
        model="Qwen3-32B",
        stream=True,
        request_rate=0,
        retry=1,
        api_key=os.environ["MAAS_API_KEY"],
        host_ip=os.environ["MAAS_HOST_IP"],
        host_port=30175,
        url=os.environ["MAAS_URL"],
        max_out_len=512,
        batch_size=1,
        trust_remote_code=False,
        verbose=True,
        generation_kwargs=dict(
            temperature=0.01,
            ignore_eos=False,
        ),
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    ),
    dict(
        attr="service",
        type=VLLMCustomAPIChat,
        abbr="qwen-plus-api",
        path="",
        model="qwen-plus",
        stream=True,
        request_rate=0,
        retry=2,
        api_key=os.environ["QWEN_PLUS_API_KEY"],
        url=os.environ["QWEN_PLUS_URL"],
        max_out_len=512,
        batch_size=1,
        trust_remote_code=False,
        verbose=True,
        generation_kwargs=dict(
            temperature=0.01,
            ignore_eos=False,
        ),
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    ),
]
