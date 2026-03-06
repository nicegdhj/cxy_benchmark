from ais_bench.benchmark.models import BailianAPI
import os

models = [
    dict(
        attr="service",
        type=BailianAPI,
        abbr="bailian-qwen-plus",
        path="",
        model="qwen-plus",  # Options: qwen-plus, qwen-turbo, qwen-max, qwen-max-longcontext
        stream=False,
        request_rate=0,
        retry=2,
        api_key="sk-113a66cc6c464374a4d6f06b7306132f",  # Set your DASHSCOPE_API_KEY here or via environment variable
        url=os.environ["QWEN_PLUS_URL"],
        max_out_len=2048,
        batch_size=5,
        generation_kwargs=dict(
            temperature=0.7,
            top_p=0.8,
        ),
    )
]
