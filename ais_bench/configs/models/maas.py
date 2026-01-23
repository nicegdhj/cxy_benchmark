# -*- coding= utf-8 -*-
# @Time    = 2026/1/22 17=37
# @Author  = jia
# @File    = maas.py
# @Desc    =
from ais_bench.benchmark.models import MaaSAPI
from ais_bench.benchmark.utils.postprocess.model_postprocessors import extract_non_reasoning_content

models = [
    dict(
        attr="service",
        type=MaaSAPI,
        abr="maas-api",
        path="",
        model="Qwen3-32B",
        stream=True,
        request_rate=0,
        retry=2,
        api_key="sk-2c06cd23-c324-458b-a0cd-b87eb09e7d07",
        host_ip="188.103.147.179",
        host_port=30175,
        url="http://188.103.147.179:30175/gateway/api/sk-UTgWwF/kunlun/ingress/api-safe/c10ca6/73ddb0a78ac74e84a239534f7552cd5d/ai-4b41821cff61402fa11913bde0b683a6/service-877f65e9853f47baaf731f7da1b4bf8a/v1/chat/completions",
        max_out_len=512,
        batch_size=1,
        trust_remote_code=False,
        generation_kwargs=dict(
            temperature=0.01,
            ignore_eos=False,
        ),
        pred_postprocessor=dict(type=extract_non_reasoning_content)
    )
]
