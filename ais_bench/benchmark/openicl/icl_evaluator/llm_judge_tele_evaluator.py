# -*- coding: utf-8 -*-
# @Time    : 2026/4/23 14:14
# @Author  : jia
# @File    : llm_judge_tele_evaluator.py
# @Desc    :


import re
from typing import List

from datasets import Dataset

from ais_bench.benchmark.registry import ICL_EVALUATORS
from ais_bench.benchmark.utils.postprocess.model_postprocessors import extract_non_reasoning_content
from ais_bench.benchmark.openicl.icl_evaluator.llm_judge_evaluator import LLMJudgeEvaluator

TELECOM_JUDGE_PROMPT_TEMPLATE = """
# Role: 通信领域AI模型知识评估专家

## Profile:
- Description: 你是一名具有通信行业背景的AI模型输出质量评估专家，熟悉通信协议（如5G NR、LTE、IMS、SDN/NFV等）、网络规划、无线接入、核心网、传输网等专业知识。你的任务是评估候选模型的回答与参考答案（Ground Truth）之间的知识一致性，判断模型是否从训练数据中有效学习到了正确的通信领域知识。

## Skills:
1. 能准确判断候选答案是否覆盖了参考答案中的核心通信知识点和事实。
2. 擅长识别通信场景中的幻觉：如捏造不存在的协议参数、错误的技术规格（频段、时隙、编码方式等）、虚构的标准条款。
3. 能包容合理的同义替换或不同但正确的表述方式，而不拘泥于逐字匹配。
4. 能识别通信术语使用是否规范（如区分"上行/下行"、"信道/载波"等易混淆概念）。

## 评估维度（满分5分，精确到0.5分）:

### 维度1：核心事实一致性（权重50%）
评估候选答案与参考答案在核心知识点上的吻合程度。

- **5分**：候选答案完整覆盖参考答案中所有核心知识点，无事实冲突，即使换了表述本质完全一致。
- **4分**：涵盖绝大部分核心知识点，存在极细微遗漏或措辞差异，不影响技术理解。
- **3分**：涵盖超过一半的核心知识点，无严重事实冲突，但有明显遗漏。
- **2分**：遗漏大部分核心知识点，或存在明显事实冲突（如错误的数值/参数/协议名称）。
- **1分**：与参考答案完全相悖，或提供了与问题无关的内容。
- **0分**：完全未作答，或输出为乱码/无意义内容。

### 维度2：专业准确性（权重30%）
评估候选答案中通信专业术语和技术细节的正确性。

- **5分**：术语使用规范，技术参数（频率、时隙、编码、接口名称等）完全正确，无捏造内容。
- **4分**：术语基本正确，偶有细微的专业表述不够严谨但不影响理解。
- **3分**：大部分术语正确，但有个别术语使用不当或技术细节模糊。
- **2分**：存在明显的术语混淆或错误技术规格（如错误的协议版本、参数量级）。
- **1分**：大量术语错误或存在严重的技术事实错误（如把上行和下行混淆）。
- **0分**：专业内容完全错误或充斥捏造的技术描述（幻觉严重）。

### 维度3：完整性与表述（权重20%）
评估答案的内容完整程度和语言表达质量。

- **5分**：内容结构清晰，表述流畅，覆盖参考答案的逻辑层次，有合理扩展且无误。
- **4分**：内容较完整，结构清晰，表述准确，存在少量遗漏但不影响整体。
- **3分**：内容基本完整，但有明显遗漏或表述略显啰嗦/生硬。
- **2分**：内容存在较多遗漏，或结构混乱，影响理解。
- **1分**：内容严重缺失、答案被截断或逻辑支离破碎。
- **0分**：完全无法阅读或表述完全错乱。

## 用户问题（指令+附加信息）:
{question}

## 参考答案（Ground Truth）:
{reference_output}

## 候选模型输出（Candidate）:
{candidate_output}

## 评分计算规则:
最终得分 = 维度1得分 × 50% + 维度2得分 × 30% + 维度3得分 × 20%
评分范围：0 ~ 5 分，精确到 0.5 分。

## 幻觉判断标准:
满足以下任一条件，将 hallucination 设置为 true：
- 候选答案中出现参考答案未提及的、且与通信技术事实相悖的虚假技术信息（如捏造协议参数）。
- 候选答案引用了不存在的标准名称、接口名称、信道类型或频段值。
- 候选答案中存在对技术概念的根本性错误（如混淆核心网与接入网概念）。

## 输出格式:
直接以JSON对象输出，不要添加任何markdown代码块或多余前缀/后缀。输出必须以 {{ 开始，以 }} 结束。

输出示例：
{{"score": 4.0, "evaluation": "候选答案覆盖了参考答案中关于5G NR帧结构的主要知识点，时隙数量描述正确，但遗漏了子载波间隔与帧结构的关联说明，专业术语使用规范无误。", "hallucination": false}}

## 注意事项:
- evaluation字段：100字以内，简要说明得分依据，指出哪些知识点符合、哪些遗漏、是否有专业性问题。
- 如候选答案包含推理过程（如<think>标签内容），忽略推理过程，仅评估最终给出的答案。
- 评估目的是测试模型是否从通信领域训练集中有效习得正确的QA知识对。"""


@ICL_EVALUATORS.register_module()
class TelecomLLMJudgeEvaluator(LLMJudgeEvaluator):
    """通信领域 LLM 打分评估器。

    使用通信专域 prompt，输出 JSON 格式（score/evaluation/hallucination），
    最终指标与 LLMJudgeEvaluator 兼容，并额外输出 hallucination_rate。
    """

    MAX_SCORE = 5.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def score(self, predictions: List, references: List, test_set: Dataset = None) -> dict:
        if not self.model:
            return {'error': 'Model instance could not be created for TelecomLLMJudgeEvaluator.'}

        prompts = []
        for i, (pred, ref) in enumerate(zip(predictions, references)):
            question = test_set[i].get('input', '') if test_set and i < len(test_set) else ''
            prompt = TELECOM_JUDGE_PROMPT_TEMPLATE.format(
                question=question,
                reference_output=ref,
                candidate_output=pred,
            )
            prompts.append(prompt)

        self.logger.info(
            f"[TelecomLLMJudge] 打分模型: type={type(self.model).__name__}, "
            f"url={getattr(self.model, 'url', 'N/A')}, "
            f"model={getattr(self.model, 'model', 'N/A')}, "
            f"共 {len(prompts)} 条待评分"
        )

        max_out_len = 512
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
                            max_out_len=max_out_len,
                            output=output,
                            session=session,
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
            judgements = self.model.generate(prompts, max_out_len=max_out_len)

        import json as _json

        details = []
        for i, (pred, ref, judge_output) in enumerate(zip(predictions, references, judgements)):
            if judge_output is None or str(judge_output).strip() == '':
                self.logger.warning(
                    f"Empty judge output at index {i}, score set to None. "
                    f"Prompt: {prompts[i][:100]}..."
                )
                details.append({
                    'prompt': prompts[i],
                    'pred': pred,
                    'refr': ref,
                    'judge_output': '',
                    'llm_score': None,
                    'max_score': self.MAX_SCORE,
                    'hallucination': False,
                    'evaluation': '',
                    'llm_error': 'empty judge output',
                    'eval_details': {
                        'llm_score': 0.0,
                        'max_score': self.MAX_SCORE,
                        'hallucination': False,
                        'evaluation': '',
                        'llm_error': 'empty judge output',
                    },
                })
                continue

            clean_output = extract_non_reasoning_content(str(judge_output))
            score = 0.0
            evaluation = ''
            hallucination = False

            # 尝试整体解析 JSON
            parsed = None
            try:
                parsed = _json.loads(clean_output)
            except _json.JSONDecodeError:
                json_match = re.search(r'\{[^{}]*\}', clean_output, re.DOTALL)
                if json_match:
                    try:
                        parsed = _json.loads(json_match.group())
                    except _json.JSONDecodeError:
                        pass

            if parsed and isinstance(parsed, dict):
                try:
                    score = float(parsed.get('score', 0.0))
                    score = min(max(score, 0.0), self.MAX_SCORE)
                except (TypeError, ValueError):
                    pass
                evaluation = str(parsed.get('evaluation', ''))
                hallucination = bool(parsed.get('hallucination', False))
            else:
                # JSON 解析失败，回退到正则提取 score 数字
                score_match = re.search(
                    r'["\']score["\']\s*:\s*["\']?([\d.]+)["\']?', clean_output, re.IGNORECASE
                )
                if score_match:
                    try:
                        score = float(score_match.group(1))
                        score = min(max(score, 0.0), self.MAX_SCORE)
                    except ValueError:
                        pass
                else:
                    matches = re.findall(r'([\d.]+)', clean_output)
                    if matches:
                        try:
                            score = float(matches[-1])
                            score = min(max(score, 0.0), self.MAX_SCORE)
                        except ValueError:
                            pass

            details.append({
                'prompt': prompts[i],
                'pred': pred,
                'refr': ref,
                'judge_output': judge_output,
                'llm_score': score,
                'max_score': self.MAX_SCORE,
                'hallucination': hallucination,
                'evaluation': evaluation,
                'eval_details': {
                    'llm_score': score,
                    'max_score': self.MAX_SCORE,
                    'hallucination': hallucination,
                    'evaluation': evaluation,
                    'judge_output': judge_output,
                },
            })

        return {'details': details}

    def evaluate(self, k, n, original_dataset: Dataset, **score_kwargs):
        results = super().evaluate(k, n, original_dataset, **score_kwargs)

        details = results.get('details', [])
        valid = [d for d in details if d.get('llm_score') is not None]
        if valid:
            hallucinated = sum(1 for d in valid if d.get('hallucination', False))
            results['hallucination_rate'] = round(hallucinated / len(valid) * 100, 2)
        else:
            results['hallucination_rate'] = 0.0

        return results
