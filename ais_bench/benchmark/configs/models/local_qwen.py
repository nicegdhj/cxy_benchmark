# -*- coding= utf-8 -*-
# @Time    = 2026/1/22 17=37
# @Author  = jia
# @File    = maas.py
# @Desc    =
import os
from ais_bench.benchmark.models import MaaSAPI
from ais_bench.benchmark.utils.postprocess.model_postprocessors import (
    extract_non_reasoning_content,
)


models = [
    dict(
        attr="service",
        type=MaaSAPI,
        abbr="maas-api",
        path="",
        model=os.environ.get("LOCAL_MODEL_NAME", "qwen3-14b"),
        stream=False,
        request_rate=0,
        retry=1,
        host_ip=os.environ["LOCAL_HOST_IP"],
        host_port=int(os.environ.get("LOCAL_HOST_PORT", "8113")),
        url=os.environ["LOCAL_URL"],
        max_out_len=512,
        batch_size=int(os.environ.get("LOCAL_CONCURRENCY", "100")),
        trust_remote_code=False,
        verbose=os.environ.get("EVAL_VERBOSE", "false").lower() == "true",
        generation_kwargs=dict(
            temperature=0.01,
            ignore_eos=False,
        ),
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    ),
]

