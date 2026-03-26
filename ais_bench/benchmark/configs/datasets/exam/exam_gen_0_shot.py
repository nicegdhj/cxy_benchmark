# configs/datasets/exam/exam_gen_0_shot.py
#
# 考试数据集（Exam）评测配置
#
# 数据文件存放路径：benchmark/data/exam/
# 每个试卷对应一个 JSON 文件（文件名即试卷标识）
#
# 使用方式：
#   1. 在下方 exam_papers 列表填入待评测的试卷文件名（无 .json 后缀）
#   2. 将本配置文件路径传给评测框架的 --datasets 参数

from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer

from ais_bench.benchmark.datasets.exam_dataset import ExamDataset
from ais_bench.benchmark.openicl.icl_evaluator.exam_evaluator import ExamDynamicEvaluator

# -----------------------------------------------------------------------
# 试卷列表
# 填入 benchmark/data/exam/ 下的 JSON 文件名（不含 .json 后缀）
# -----------------------------------------------------------------------
exam_papers = [
    "exam_858_2022",
    "exam_858_2023",
    "exam_858_2024",
    "exam_801-2022",
    "exam_801-2023",
    "exam_801-2024",
    "exam_804_2022",
    "exam_804_2023",
    "exam_804_2024",
]

# -----------------------------------------------------------------------
# 推理 Prompt 模板
# 题目文本（question 字段）在数据加载阶段已由 ExamDataset 根据题型
# 自动拼接对应的约束指令，此处只需直接使用 {question} 即可，
# 禁止在此处再添加全局统一的格式约束语句。
# -----------------------------------------------------------------------

exam_datasets = []

for _name in exam_papers:
    _reader_cfg = dict(
        input_columns=["question"],
        output_column="answer",
    )

    _infer_cfg = dict(
        prompt_template=dict(
            type=PromptTemplate,
            template='{question}',   # 约束指令已由 ExamDataset 拼入 question 字段
        ),
        retriever=dict(type=ZeroRetriever),
        inferencer=dict(type=GenInferencer),
    )

    _eval_cfg = dict(
        evaluator=dict(type=ExamDynamicEvaluator),
    )

    exam_datasets.append(
        dict(
            abbr=f"exam_{_name}",
            type=ExamDataset,
            path="data/exam",
            name=_name,
            reader_cfg=_reader_cfg,
            infer_cfg=_infer_cfg,
            eval_cfg=_eval_cfg,
        )
    )

del _name, _reader_cfg, _infer_cfg, _eval_cfg
