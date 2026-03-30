from ais_bench.benchmark.models import MaaSAPI
from ais_bench.benchmark.utils.postprocess.model_postprocessors import (
    extract_non_reasoning_content,
)
import os

models = [
    dict(
        attr="service",
        type=MaaSAPI,
        abbr="maas-api",
        path="",
        model="Qwen3-32B",
        stream=False,
        request_rate=0,
        retry=2,
        api_key=os.environ["MAAS_API_KEY"],
        host_ip=os.environ["MAAS_HOST_IP"],
        host_port=30175,
        url=os.environ["MAAS_URL"],
        max_out_len=512,
        batch_size=1,
        trust_remote_code=False,
        generation_kwargs=dict(
            temperature=0.01,
            ignore_eos=False,
            enable_thinking=False,
        ),
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    )
]
