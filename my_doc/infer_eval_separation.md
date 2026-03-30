# 推理与评测分离改造说明

## 1. 背景与目的

原流程中，`eval_entry.py` 每次同时执行推理和评测（`ais_bench --mode all`）。这带来以下问题：

| 问题 | 说明 |
|------|------|
| 推理成本高 | 推理一次要几小时，若只是想调整评分规则，必须重跑推理 |
| LLM 评估器串联 | 使用 `LLMJudgeEvaluator`（调用云端大模型打分）的任务与规则型任务混在一起，评测阶段难以单独控制 |
| 结果难复用 | 无法基于同一份推理结果跑多次对比评测 |

改造目标：

1. **推理一次，评测多次** —— 推理结果持久化，评测可随时重跑
2. **LLM 评估器后置** —— 自动检测并将 LLM 型评估任务排到规则型之后执行
3. **版本化评测** —— 每次评测产出独立目录，多版本并存互不干扰

---

## 2. 改造内容

### 2.1 文件变更一览

| 文件 | 操作 | 说明 |
|------|------|------|
| `eval_entry.py` | 修改 | 只做推理，产出 `infer_meta.json` |
| `eval_judge.py` | 新增 | 评测专用脚本，读取 `infer_meta.json` 执行评测 |
| `run_mixed_benchmark.sh` | 修改 | 改为推理 → 评测两阶段串联 |
| `scripts/package_deploy.sh` | 修改 | 打包时包含 `eval_judge.py` |
| `scripts/migrate_fmt_to_infer_meta.py` | 新增 | 将旧格式 `report.json` 转换为 `infer_meta.json`（迁移工具） |

### 2.2 eval_entry.py 改动

- ais_bench 调用加 `--mode infer`（不再做评测）
- 移除 `_parse_latest_task_result()`，改用更轻量的 `_find_infer_output()`（只找时间戳目录和样本数，不解析准确率）
- 移除 `generate_report()`，改为 `generate_infer_meta()` 生成 `infer_meta.json`
- 内存控制机制 `_cleanup_leaked_shm()` + `gc.collect()` 保留不变

### 2.3 eval_judge.py 核心逻辑

```
main()
├── 读取 infer_meta.json（task_id → timestamp 映射）
├── detect_evaluator_type()   # 扫描 configs/datasets/*.py，检测是否含 LLMJudgeEvaluator
├── sort_tasks_by_eval_type() # 规则型优先，LLM 型靠后
├── run_eval_for_task()       # ais_bench --mode eval --work-dir ... --reuse {timestamp}
│   ├── _parse_eval_result()  # 从 summary 解析准确率
│   └── _move_eval_outputs()  # 将 results/summary/logs/eval 搬运到 eval_{version}/
└── generate_eval_report()    # 生成 report.md + report.json
```

当前检测到使用 `LLMJudgeEvaluator` 的任务（自动后置）：
- `telequad_gen_0_shot`
- `tele_exam_gen_0_shot_str`
- `teledata_gen_0_shot`

### 2.4 run_mixed_benchmark.sh 改动

原来一个 `docker run`，改为两阶段：

```bash
# 阶段 1：推理
docker run ... python eval_entry.py --task-id "${TASK_ID}" ...

# 推理失败则直接退出，不进入评测
INFER_RC=$?
if [ ${INFER_RC} -ne 0 ]; then exit ${INFER_RC}; fi

# 阶段 2：评测
docker run ... python eval_judge.py --infer-task "${TASK_ID}"
```

---

## 3. 目录结构设计

### 3.1 新格式（改造后）

```
outputs/{task_id}/
├── infer_meta.json                  # 推理元数据（suite → timestamp 映射）
├── details/                         # 推理产出（不含评测结果）
│   └── {timestamp}/
│       ├── predictions/             # 模型输出（jsonl）
│       ├── configs/                 # ais_bench 配置快照
│       └── logs/infer/              # 推理日志
└── eval_{version}/                  # 评测产出（版本化）
    ├── report.md
    ├── report.json
    ├── results/                     # 各任务 details.jsonl
    ├── summary/                     # accuracy summary txt
    └── logs/eval/                   # 评测日志
```

**一份推理结果可以对应多个评测版本**，例如：

```
outputs/round_1/
├── infer_meta.json
├── details/
├── eval_20260318_143022/    # 第一次评测
└── eval_v2_fix_weight/      # 调整权重后重新评测
```

### 3.2 infer_meta.json 结构

```json
{
  "task_id": "mixed_eval_20260318_143022",
  "model_config": "local_qwen",
  "model_name": "Qwen2.5-72B",
  "infer_time": "2026-03-18 14:30:22",
  "tasks": {
    "task_1_suite": {
      "timestamp": "20260318_143100",
      "task_name": "task_1",
      "type": "custom",
      "num_samples": 402,
      "duration_sec": 55.9,
      "status": "success"
    },
    "ceval_gen_0_shot_str": { ... }
  }
}
```

---

## 4. 使用方法

### 4.1 日常评测（Docker 私域环境）

与以前一样，执行 `run_mixed_benchmark.sh` 即可，脚本自动完成推理+评测两阶段：

```bash
bash run_mixed_benchmark.sh --workspace /opt/eval_workspace
```

### 4.2 本地开发 / 单独跑推理

```bash
python eval_entry.py \
    --task-id round_3 \
    --model-config local_qwen \
    --tasks 1 34 36 43 44 60 \
    --generic-datasets ceval_gen_0_shot_str mmlu_redux_gen_5_shot_str
```

产出：`outputs/round_3/infer_meta.json` + `outputs/round_3/details/`

### 4.3 基于已有推理结果重新评测

```bash
# 评测所有任务（规则型自动优先，LLM 型靠后）
python eval_judge.py --infer-task round_3

# 只评测指定任务，按传入顺序执行
python eval_judge.py --infer-task round_3 \
    --eval-tasks task_1_suite telequad_gen_0_shot ceval_gen_0_shot_str

# 指定版本号，避免覆盖历史评测
python eval_judge.py --infer-task round_3 --eval-version v2_fix_weight
```

### 4.4 对旧格式数据（fmt/ptXX）重新评测

旧数据没有 `infer_meta.json`，需要先用迁移脚本生成：

```bash
# Step 1：生成 infer_meta.json（单个目录）
python scripts/migrate_fmt_to_infer_meta.py \
    /path/to/fmt/pt0_sft0 \
    --model-config local_qwen

# Step 1：批量生成（fmt/ 下所有 ptXX 目录）
python scripts/migrate_fmt_to_infer_meta.py \
    /path/to/fmt \
    --all \
    --model-config local_qwen

# Step 2：重新评测
python eval_judge.py \
    --infer-task pt0_sft0 \
    --output-dir /path/to/fmt \
    --eval-version v2_new_weight
```

> **注意**：旧 `details/` 目录已包含 `results/` 和 `summary/`（上一轮评测产物）。
> `eval_judge.py` 会在新评测完成后将这些目录搬走到 `eval_{version}/`，
> `details/` 本身只保留推理相关内容（`predictions/`、`configs/`、`logs/infer/`）。

---

## 5. 参数速查

### eval_entry.py（推理）

| 参数 | 说明 | 示例 |
|------|------|------|
| `--task-id` | 本次推理唯一标识 | `round_3` |
| `--model-config` | 模型配置名 | `local_qwen` |
| `--tasks` | 自定义任务编号 | `1 34 36 43 44 60` |
| `--generic-datasets` | 通用数据集名称 | `ceval_gen_0_shot_str mmlu_redux_gen_5_shot_str` |
| `--output-dir` | 输出根目录（默认 `outputs/`） | `/app/outputs` |
| `--concurrency` | 并发数（默认 5） | `20` |
| `--debug` | 串行 debug 模式 | - |
| `--num-prompts` | 每任务最多评测条数 | `10` |

### eval_judge.py（评测）

| 参数 | 说明 | 示例 |
|------|------|------|
| `--infer-task` | 推理批次标识（必填） | `round_3` |
| `--eval-version` | 评测版本号（不传则自动生成） | `v2_fix_weight` |
| `--eval-tasks` | 指定评测任务（不传则全部，LLM 型自动后置） | `task_1_suite telequad_gen_0_shot` |
| `--output-dir` | 输出根目录（默认 `outputs/`） | `/path/to/fmt` |

### migrate_fmt_to_infer_meta.py（迁移工具）

| 参数 | 说明 |
|------|------|
| `path` | 单个 ptXX 目录，或 `--all` 时为父目录 |
| `--model-config` | 模型配置名（默认 `local_qwen`） |
| `--all` | 批量处理 path 下所有子目录 |
| `--overwrite` | 强制覆盖已有的 `infer_meta.json` |

---

## 6. 结果汇总：aggregate_eval_reports.py

### 6.1 作用

`aggregate_eval_reports.py` 用于将多个实验组（`ptXX_sftX`、`baseline` 等）的评测结果汇总为一份 Excel 报告，输出格式与 `process_results.py` 对齐。

核心功能：

| 功能 | 说明 |
|------|------|
| **总体对比表** | 生成 `总体汇总_*.xlsx`，行为任务名，列为实验组，baseline 黄色高亮，优于 baseline 绿色，劣于 baseline 红色 |
| **实验组详情 Sheet** | 每个实验组独立一个 Sheet，展示各任务准确率、样本数、耗时等 |
| **明细 Excel** | 将每个实验组每个任务的 `_details.jsonl` 转换为 Excel，存放至 `{数据集名}/{实验组名}/` 子目录 |
| **summary 拷贝** | 将 `eval_{version}/summary/{suite}/` 拷贝至对应子目录的 `summary/` 下 |
| **任务名映射** | 自动读取 `outputs/评测任务文件名对应.xlsx`，将 `ceval_gen_0_shot_str` 等内部名称转换为可读名称（如 `C-Eval`）；支持自动去除 `_suite` 后缀 |
| **实验组名映射** | 自动读取 `outputs/实验设置.xlsx`，将 `pt37_sft0` 转换为 `set37_...` 实验设置名；带 `_expXXXX` 后缀的变体（如 `pt37_sf0_exp0317`）映射为 `set37_..._exp0317` |

### 6.2 输入目录结构

脚本读取 `--fmt-dir` 下每个实验组的 `{eval_version}/report.json`：

```
fmt/
├── baseline/
│   └── v6_rule/
│       ├── report.json          # 任务准确率等汇总
│       ├── results/{suite}/     # *_details.jsonl 明细
│       └── summary/{suite}/     # 评测 summary 文件
├── pt0_sft0/
│   └── v6_rule/
│       └── ...
└── pt37_sf0_exp0317/            # 带版本后缀的变体组
    └── v6_rule/
        └── ...
```

### 6.3 输出目录结构

```
outputs/aggregated_reports_{timestamp}/
├── 总体汇总_{timestamp}.xlsx      # 主报告（总体对比 + 附录）
├── {数据集名}/                    # 例如 AIME-2025/、C-Eval/
│   ├── baseline/
│   │   ├── {task}_details.xlsx   # 明细 Excel
│   │   └── summary/              # 拷贝自 eval_{version}/summary/{suite}/
│   └── {实验组名}/
│       ├── {task}_details.xlsx
│       └── summary/
└── ...
```

### 6.4 用法

```bash
# 基本用法
python aggregate_eval_reports.py \
    --fmt-dir /path/to/fmt \
    --eval-version v6_rule \
    --output-dir ./outputs

# 不传 --output-dir 时默认输出到 fmt-dir/../benchmark/outputs/
python aggregate_eval_reports.py \
    --fmt-dir ~/Desktop/fmt_exp0316 \
    --eval-version v6_rule
```

### 6.5 参数说明

| 参数 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `--fmt-dir` | 否（有默认值） | 实验组根目录，每个子目录为一个实验组 | `~/Desktop/fmt_exp0316` |
| `--eval-version` | **是** | 评测版本号，即 `eval_judge.py` 的 `--eval-version` | `v6_rule` |
| `--output-dir` | 否 | 汇总输出目录（不传则输出到 `fmt-dir/../benchmark/outputs/`） | `./outputs` |

### 6.6 依赖映射文件

脚本从 `--output-dir` 下读取以下两个 Excel，缺失时跳过映射（直接使用原始名称）：

| 文件 | 作用 |
|------|------|
| `outputs/评测任务文件名对应.xlsx` | 第一列：任务内部名称；第二列：展示名称 |
| `outputs/实验设置.xlsx` | 第一列：编号；第二列：实验设置文件名（`.json` 后缀自动去除） |