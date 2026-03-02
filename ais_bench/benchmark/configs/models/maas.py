# -*- coding= utf-8 -*-
# @Time    = 2026/1/22 17=37
# @Author  = jia
# @File    = maas.py
# @Desc    =
import os
from ais_bench.benchmark.models import MaaSAPI, VLLMCustomAPIChat
from ais_bench.benchmark.utils.postprocess.model_postprocessors import (
    extract_non_reasoning_content,
)


# models = [
#     dict(
#         attr="service",
#         type=MaaSAPI,
#         abbr="maas-api",
#         path="",
#         model=os.environ.get("EVAL_MODEL_NAME", "Qwen3-32B"),
#         stream=True,
#         request_rate=0,
#         retry=1,
#         api_key=os.environ["MAAS_API_KEY"],
#         host_ip=os.environ["MAAS_HOST_IP"],
#         host_port=int(os.environ.get("MAAS_HOST_PORT", "30175")),
#         url=os.environ["MAAS_URL"],
#         max_out_len=512,
#         batch_size=int(os.environ.get("EVAL_CONCURRENCY", "5")),
#         trust_remote_code=False,
#         verbose=os.environ.get("EVAL_VERBOSE", "false").lower() == "true",
#         generation_kwargs=dict(
#             temperature=0.01,
#             ignore_eos=False,
#         ),
#         pred_postprocessor=dict(type=extract_non_reasoning_content),
#     ),
# ]

models = [
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
        batch_size=int(os.environ.get("EVAL_CONCURRENCY", "5")),
        trust_remote_code=False,
        verbose=True,
        generation_kwargs=dict(
            temperature=0.01,
            ignore_eos=False,
        ),
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    ),
]
