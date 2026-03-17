import copy
import os
import re
from typing import List
from collections import defaultdict

from datasets import Dataset

from ais_bench.benchmark.registry import ICL_EVALUATORS
from ais_bench.benchmark.openicl.icl_evaluator.icl_base_evaluator import BaseEvaluator
from ais_bench.benchmark.utils.config.build import build_model_from_cfg

DEFAULT_PROMPT_TEMPLATE = """You are a fair and strict evaluator. Please score the following student's answer based on the correct answer.
The maximum score you can give is {max_score}.

Correct Answer:
{reference}

Student's Answer:
{prediction}

Please output the score only as a number at the end of your response."""

@ICL_EVALUATORS.register_module()
class LLMJudgeEvaluator(BaseEvaluator):
    def __init__(self, model_cfg: dict = None, prompt_template: str = None, **kwargs) -> None:
        super().__init__()
        self.prompt_template = prompt_template or DEFAULT_PROMPT_TEMPLATE

        if model_cfg:
            # 显式传入了配置，直接使用
            self.model_cfg = model_cfg
        else:
            # 未传入配置，尝试从 EVAL_* 环境变量自动构建评估模型配置
            self.model_cfg = self._build_eval_model_cfg_from_env()

        if not self.model_cfg:
            self.logger.warning(
                "LLMJudgeEvaluator: model_cfg is None 且未检测到 EVAL_* 环境变量，"
                "评估器将无法调用 LLM 评分。"
            )
            self.model = None
        else:
            self.model = build_model_from_cfg(self.model_cfg)

    @staticmethod
    def _build_eval_model_cfg_from_env() -> dict:
        """从 EVAL_* 环境变量构建评估模型配置（与推理的 LOCAL_* 变量完全解耦）。

        必填：EVAL_HOST_IP, EVAL_HOST_PORT, EVAL_MODEL_NAME
        可选：EVAL_URL（默认拼接 /v1/chat/completions），EVAL_CONCURRENCY（默认 100）

        Returns:
            完整的 model_cfg dict，若必填变量缺失则返回 None。
        """
        from ais_bench.benchmark.models import MaaSAPI
        from ais_bench.benchmark.utils.postprocess.model_postprocessors import (
            extract_non_reasoning_content,
        )

        host_ip   = os.environ.get("EVAL_HOST_IP")
        host_port = os.environ.get("EVAL_HOST_PORT")
        model_name = os.environ.get("EVAL_MODEL_NAME")

        # 必填变量校验
        if not all([host_ip, host_port, model_name]):
            return None

        try:
            host_port_int = int(host_port)
        except ValueError:
            return None

        eval_url = os.environ.get(
            "EVAL_URL",
            f"http://{host_ip}:{host_port}/v1/chat/completions",
        )
        concurrency = int(os.environ.get("LOCAL_CONCURRENCY", "100"))

        return dict(
            type=MaaSAPI,
            attr="service",
            abbr="eval_model",
            path="",
            model=model_name,
            stream=False,
            request_rate=0,
            retry=1,
            host_ip=host_ip,
            host_port=host_port_int,
            url=eval_url,
            max_out_len=512,
            batch_size=concurrency,
            trust_remote_code=False,
            verbose=os.environ.get("EVAL_VERBOSE", "false").lower() == "true",
            generation_kwargs=dict(
                temperature=0.01,
                ignore_eos=False,
            ),
            pred_postprocessor=dict(type=extract_non_reasoning_content),
        )
            
    def evaluate(self, k, n, original_dataset: Dataset, **score_kwargs):
        if 'predictions' in score_kwargs and 'references' in score_kwargs:
            if len(score_kwargs['predictions']) != len(score_kwargs['references']):
                return {'error': 'Predictions and references must have the same length'}

        score_kwargs['predictions'] = self.pred_postprocess(score_kwargs.get('predictions', []))

        # Enforce `test_set` in `score_kwargs` is `original_dataset`
        score_kwargs['test_set'] = original_dataset
        results = self.score(**score_kwargs)
        if 'error' in results:
            return results
            
        details = results.get('details', [])
        
        total_score = 0.0
        total_max_score = 0.0
        subdivision_scores = defaultdict(float)
        subdivision_max_scores = defaultdict(float)
        self.logger.info(details)
        for i, detail in enumerate(details):
            if i < len(original_dataset):
                example = original_dataset[i]
                subdiv = example.get('subdivision', 'unknown')
                idx = example.get('idx', i)
                detail['example_abbr'] = f"{subdiv}_{idx}"
            else:
                subdiv = 'unknown'
                
            score = detail.get('llm_score', 0.0)
            max_score = detail.get('max_score', 1.0)
            
            total_score += score
            total_max_score += max_score
            subdivision_scores[subdiv] += score
            subdivision_max_scores[subdiv] += max_score
            
        # eval_results = {
        #     'llm_judge_score_sum': round(total_score, 2),
        #     'llm_judge_max_score_sum': round(total_max_score, 2),
        # }
        eval_results={}
        for subdiv in subdivision_scores:
            score = subdivision_scores[subdiv]
            max_score = subdivision_max_scores[subdiv]
            if max_score == 0:
                percentage = 0.0     
            else:
                percentage = (score / max_score) * 100
            eval_results[f'{subdiv}/llm_judge_percentage'] = round(percentage, 2)
                
        eval_results['details'] = details
        return eval_results

    def score(self, predictions: List, references: List, test_set: Dataset = None) -> dict:
        if not self.model:
            return {'error': 'Model instance could not be created for LLMJudgeEvaluator.'}
            
        prompts = []
        max_scores = []
        for i, (pred, ref) in enumerate(zip(predictions, references)):
            max_score = 1.0
            if test_set and 'score' in test_set.features:
                score_val = test_set[i].get('score')
                if score_val is not None:
                    match = re.search(r'([\d.]+)', str(score_val))
                    if match:
                        max_score = float(match.group(1))
            
            max_scores.append(max_score)
            prompt = self.prompt_template.format(max_score=max_score, reference=ref, prediction=pred)
            prompts.append(prompt)
            
        if getattr(self.model, 'is_api', False):
            import asyncio
            from ais_bench.benchmark.models.output import RequestOutput
            import aiohttp
            
            async def _run_api_inference():
                async with aiohttp.ClientSession(trust_env=True) as session:
                    outputs = [RequestOutput(False) for _ in prompts]
                    tasks = [
                        self.model.generate(
                            input_data=prompt, 
                            max_out_len=128, 
                            output=output, 
                            session=session
                        )
                        for prompt, output in zip(prompts, outputs)
                    ]
                    await asyncio.gather(*tasks)
                    return [out.content for out in outputs]
                    
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                judgements = loop.run_until_complete(_run_api_inference())
            else:
                judgements = loop.run_until_complete(_run_api_inference())
        else:
            judgements = self.model.generate(prompts, max_out_len=128)
        
        details = []
        for i, (pred, ref, judge_output, max_score) in enumerate(zip(predictions, references, judgements, max_scores)):
            score = 0.0
            matches = re.findall(r'([\d.]+)', str(judge_output))
            if matches:
                try:
                    score = float(matches[-1])
                    score = min(max(score, 0.0), max_score)
                except ValueError:
                    pass
            
            details.append({
                'prompt': prompts[i],
                'pred': pred,
                'refr': ref,
                'judge_output': judge_output,
                'llm_score': score,
                'max_score': max_score
            })
            
        return {'details': details}
