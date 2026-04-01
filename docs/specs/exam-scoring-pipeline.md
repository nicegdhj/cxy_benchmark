# exam_gen_0_shot 评分链路说明

## 概述

`exam_gen_0_shot` 使用 `ExamDynamicEvaluator`，按题型路由评分，最终指标来自 `summary.txt` 中的 `overall_score_percentage`，而非 `details.jsonl` 中的 `eval_res` 字段。

---

## 一、完整数据流

```
推理阶段
  predictions/*.jsonl（含 prediction 字符串）
         ↓
ExamDynamicEvaluator.score()   按题型路由
         ↓
ExamDynamicEvaluator.evaluate()  按试卷聚合
         ↓
openicl_eval.py._score()
  ├─ summary/summary_*.txt      写入 overall_score_percentage
  └─ results/*_details.jsonl    写入 eval_res / eval_details
         ↓
eval_judge.py._parse_eval_result()   读 summary.txt
         ↓
report.json  accuracy 字段
```

---

## 二、ExamDynamicEvaluator 按题型路由

| 题型 | 评分方式 | got_score |
|------|---------|-----------|
| `multiple_choice` | 提取字母与标准答案逐空比对 | `item_score × 匹配比例`（多选支持部分得分） |
| `fill_blank` | MATHEvaluator（LaTeX 等价比较）| 全对 → `item_score`，否则 0 |
| `subjective` | **LLMJudgeEvaluator** 连续打分 | `llm_score` ∈ [0, item_score] |
| `has_image=True` 或 `need_plot=True` | 跳过 | 0，且**不计入分母** |

主观题调用 `LLMJudgeEvaluator` 时，通过 `SCORE_*` 环境变量指定打分模型（见 `.env`）。

---

## 三、overall_score_percentage 计算方式

每张试卷独立计算：

```
overall_score_percentage = Σ got_score / Σ item_score × 100
```

- 分子：所有未跳过题目的实际得分之和
- 分母：所有未跳过题目的满分之和
- `has_image / need_plot` 题目不进分子也不进分母

写入 `summary/summary_*.txt` 的 CSV 部分，每行对应一张试卷。

---

## 四、report.json 的 accuracy 来源

`eval_judge.py._parse_eval_result()` 读取 `summary/*.txt`，取 CSV 段中所有非辅助指标行的简单算术平均：

```
exam_gen_0_shot accuracy = mean(9 张试卷的 overall_score_percentage)
```

---

## 五、details.jsonl 字段说明

`results/*_details.jsonl` 中每行格式：

```json
{
  "prediction": { "data_abbr": "...", "id": 0, "origin_prompt": "...", "prediction": "..." },
  "eval_res": true,
  "eval_details": {
    "type": "multiple_choice",
    "item_score": 3.0,
    "got_score": 3.0,
    "skipped": false,
    "correct": true
  }
}
```

主观题的 `eval_details` 还包含 `llm_judge_output`：

```json
"eval_details": {
  "type": "subjective",
  "item_score": 10.0,
  "got_score": 7.5,
  "skipped": false,
  "correct": false,
  "llm_judge_output": "该答案基本正确...评分 7.5"
}
```

### eval_res 与 accuracy 的关系

| 字段 | 来源 | 用途 |
|------|------|------|
| `eval_res` | `format_details()` 从 `correct` 字段提取的布尔值 | **仅供人工查阅**，不参与 accuracy 计算 |
| `eval_details.got_score` | `ExamDynamicEvaluator.score()` 计算 | 汇总为 `overall_score_percentage` → `accuracy` |

`eval_res=True` 代表该题字符串完全匹配（选择/填空），与试卷最终得分百分比不直接对应，原因：
- 多选题支持部分得分
- 主观题使用 LLM 连续打分
- 不同题目满分权重不同（`item_score`）

---

## 六、使用 LLMJudgeEvaluator 的其他任务

对于直接使用 `LLMJudgeEvaluator` 的任务（如 `identity_gen_0_shot`、`telequad_gen_0_shot`、`tele_exam_gen_0_shot_str` 等），`eval_details` 字段为：

```json
"eval_details": {
  "llm_score": 0.8,
  "max_score": 1.0,
  "judge_output": "该答案基本正确...0.8"
}
```

`eval_res` 为 `llm_score` 的字符串形式（如 `"0.8"`）。

accuracy 计算方式：各 subdivision 得分百分比（`llm_judge_percentage`），由 `LLMJudgeEvaluator.evaluate()` 计算：

```
subdivision accuracy = Σ llm_score / Σ max_score × 100
```

---

## 七、相关文件索引

| 文件 | 职责 |
|------|------|
| `ais_bench/benchmark/openicl/icl_evaluator/exam_evaluator.py` | 多题型路由，调用 LLMJudge，聚合试卷得分 |
| `ais_bench/benchmark/openicl/icl_evaluator/llm_judge_evaluator.py` | 调用打分模型，提取 llm_score |
| `ais_bench/benchmark/tasks/openicl_eval.py` | 读取 predictions，调用 evaluator，写 details.jsonl |
| `eval_judge.py` | 读 summary.txt，写 report.json |
| `ais_bench/benchmark/configs/datasets/exam/exam_gen_0_shot.py` | 数据集配置，指定 ExamDynamicEvaluator |
| `.env` | `SCORE_*` 变量配置打分模型 |
