# 推理与评测分离设计文档

> 日期：2026-03-17
> 状态：待实施

---

## 1. 背景与动机

当前 `eval_entry.py` 以 `--mode all` 方式逐任务串行执行"推理 + 评测"一体化流程。存在以下问题：

1. **推理结果不可复用**：每次修改评估器后需要重新推理，浪费大量 GPU/API 资源
2. **LLM 评估器无隔离**：3 个任务（`telequad_gen_0_shot`、`tele_exam_gen_0_shot_str`、`teledata_gen_0_shot`）使用 `LLMJudgeEvaluator`，与规则型评估器混跑时 API 压力不可控
3. **无法单独重跑评测**：修改某个评估器后，必须重新跑整个流水线

**目标**：推理执行一次，评测结果可多次复用、按需重跑，且支持版本化管理。

---

## 2. 方案概览

采用**双脚本分离**架构：

| 脚本 | 职责 |
|:---|:---|
| `eval_entry.py` | 只做推理，产出 predictions + infer_meta.json |
| `eval_judge.py`（新增） | 只做评测，读取推理结果，产出 eval 版本化结果 + 报告 |
| `run_mixed_benchmark.sh` | 串联调用两者 |

---

## 3. eval_entry.py 改动

### 3.1 去掉 `--mode` 兼容

`eval_entry.py` 不再支持 `--mode all`，**只做推理**。原有参数保留，去掉评测相关逻辑。

### 3.2 参数变化

| 参数 | 变化 | 说明 |
|:---|:---|:---|
| `--task-id` | 保留 | 推理批次标识 |
| `--tasks` | 保留 | 自定义任务编号列表 |
| `--generic-datasets` | 保留 | 通用数据集列表 |
| `--model-config` | 保留 | 模型配置 |
| `--concurrency` | 保留 | 并发数 |
| `--debug` | 保留 | 调试模式 |
| `--num-prompts` | 保留 | 限制条数 |
| ~~`--mode`~~ | **删除** | 不再需要 |

### 3.3 内部调用方式

```python
# 以前（mode=all）：
cmd = ["ais_bench", "--models", model_config, "--datasets", suite]

# 现在（只推理）：
cmd = ["ais_bench", "--mode", "infer", "--models", model_config, "--datasets", suite]
```

### 3.4 产出

推理完成后生成元数据文件 `outputs/{task_id}/infer_meta.json`：

```json
{
  "task_id": "round_1",
  "model_config": "local_qwen",
  "model_name": "qwen-plus",
  "infer_time": "2026-03-17 16:00:00",
  "tasks": {
    "task_1_suite": {
      "timestamp": "20260317_160001",
      "task_name": "task_1",
      "type": "custom",
      "num_samples": 402,
      "duration_sec": 55.9,
      "status": "success"
    },
    "task_34_suite": {
      "timestamp": "20260317_160045",
      "task_name": "task_34",
      "type": "custom",
      "num_samples": 1280,
      "duration_sec": 309.7,
      "status": "success"
    },
    "telequad_gen_0_shot": {
      "timestamp": "20260317_160120",
      "task_name": "telequad_gen_0_shot",
      "type": "generic",
      "num_samples": 814,
      "duration_sec": 282.7,
      "status": "success"
    }
  }
}
```

### 3.5 内存控制（必须保留）

现有 `eval_entry.py` 中的以下内存管理机制必须在改造后保留：

- **`_cleanup_leaked_shm()`**：每个任务执行完后清理 `/dev/shm` 中残留的 Python 共享内存段（`psm_`、`wnsm_` 前缀），防止 OOM
- **`gc.collect()`**：每个任务执行完后强制垃圾回收
- **`LOCAL_CONCURRENCY=20`**：`run_mixed_benchmark.sh` 中通过 `-e LOCAL_CONCURRENCY=20` 控制并发数，限制内存峰值

### 3.6 目录结构（推理阶段）

```
outputs/{task_id}/
├── infer_meta.json
└── details/
    ├── 20260317_160001/          # task_1_suite
    │   ├── predictions/
    │   │   └── local_qwen/
    │   │       └── task_1.jsonl
    │   ├── configs/
    │   │   └── 20260317_160001_xxx.py
    │   └── logs/
    │       └── infer/            # 推理日志（ais_bench --mode infer 自动生成）
    │           └── local_qwen/
    │               └── task_1.out
    ├── 20260317_160045/          # task_34_suite
    │   ├── predictions/
    │   ├── configs/
    │   └── logs/
    │       └── infer/
    └── ...
```

> 注意：推理阶段只产出 `predictions/`、`configs/`、`logs/infer/`，不产出 `results/`、`summary/`、`logs/eval/`。

---

## 4. eval_judge.py 设计（新增）

### 4.1 参数

| 参数 | 必填 | 默认值 | 说明 |
|:---|:---:|:---|:---|
| `--infer-task` | 是 | - | 推理批次标识，定位 `outputs/{infer-task}/infer_meta.json` |
| `--eval-version` | 否 | `eval_{YYYYMMDD_HHMMSS}` | 评测版本标识 |
| `--eval-tasks` | 否 | 全部任务 | 指定要评测的任务（suite 名称），按传入顺序执行 |
| `--output-dir` | 否 | `outputs/` | 输出根目录 |

### 4.2 用法示例

```bash
# 评测所有任务（自动：规则型优先，LLM 型靠后）
python eval_judge.py --infer-task round_1

# 只重新评测某些任务，按指定顺序执行
python eval_judge.py --infer-task round_1 \
    --eval-tasks telequad_gen_0_shot task_1_suite

# 指定版本号
python eval_judge.py --infer-task round_1 \
    --eval-version v2_fix_weight \
    --eval-tasks telequad_gen_0_shot
```

### 4.3 内部执行流程

```
1. 读取 outputs/{infer_task}/infer_meta.json
2. 确定待评测任务列表：
   - 未传 --eval-tasks → 取 infer_meta 中所有任务
   - 传了 --eval-tasks → 按传入顺序
3. 任务排序（仅在未传 --eval-tasks 时生效）：
   a. 扫描各任务 suite 配置文件中的 evaluator type
   b. 分为 rule_tasks（非 LLMJudgeEvaluator）和 llm_tasks（LLMJudgeEvaluator）
   c. 执行顺序：rule_tasks 在前，llm_tasks 在后
4. 逐任务调用 ais_bench：
   ais_bench --mode eval \
       --reuse {timestamp} \
       --models {model_config} \
       --datasets {suite}
5. 收集评测结果，生成报告
6. 输出到 outputs/{infer_task}/{eval_version}/
```

### 4.4 LLM 任务自动检测逻辑

```python
def detect_evaluator_type(suite_name: str) -> str:
    """扫描 suite 配置文件，检测 evaluator 类型。

    搜索路径：ais_bench/benchmark/configs/datasets/ 下递归查找 {suite_name}.py
    匹配规则：文件中包含 'LLMJudgeEvaluator' 字符串则判定为 'llm'，否则为 'rule'

    Returns:
        'llm' 或 'rule'
    """
```

### 4.5 内存控制（必须保留）

eval_judge.py 同样需要内存管理：
- 逐任务调用 ais_bench 后执行 `_cleanup_leaked_shm()` + `gc.collect()`
- 该逻辑从 eval_entry.py 复用

### 4.6 产出目录结构

```
outputs/{infer_task}/
├── infer_meta.json                          # 推理元数据（eval_entry.py 生成）
├── details/                                 # 推理产物（eval_entry.py 生成）
│   ├── 20260317_160001/
│   │   ├── predictions/
│   │   ├── configs/
│   │   └── logs/
│   │       └── infer/
│   └── ...
├── eval_20260317_170000/                    # 第一次评测（自动版本）
│   ├── results/
│   │   └── local_qwen/
│   │       ├── task_1.json
│   │       ├── task_1_details.jsonl
│   │       ├── telequad_gen_0_shot.json
│   │       └── telequad_gen_0_shot_details.jsonl
│   ├── logs/                                # 评测日志
│   │   └── eval/
│   │       └── local_qwen/
│   │           ├── task_1.out
│   │           └── telequad_gen_0_shot.out
│   ├── summary/
│   ├── report.md
│   └── report.json
└── eval_v2_fix_weight/                      # 第二次评测（手动版本）
    ├── results/
    ├── logs/
    │   └── eval/
    ├── summary/
    ├── report.md
    └── report.json
```

### 4.6 report.json 格式

```json
{
  "infer_task": "round_1",
  "eval_version": "eval_20260317_170000",
  "model": "local_qwen",
  "timestamp": "2026-03-17 17:00:00",
  "avg_accuracy": 58.06,
  "summary": {
    "custom": {
      "count": 6,
      "total_duration_sec": 45.9,
      "avg_accuracy": 59.25
    },
    "generic": {
      "count": 17,
      "total_duration_sec": 120.1,
      "avg_accuracy": 57.65
    }
  },
  "tasks": [
    {
      "task": "task_1",
      "suite": "task_1_suite",
      "type": "custom",
      "eval_type": "rule",
      "status": "success",
      "accuracy": 57.8,
      "num_samples": 402,
      "duration_sec": 12.3,
      "details_dir": "results/local_qwen/task_1_details.jsonl"
    },
    {
      "task": "telequad_gen_0_shot",
      "suite": "telequad_gen_0_shot",
      "type": "generic",
      "eval_type": "llm",
      "status": "success",
      "accuracy": 34.14,
      "num_samples": 814,
      "duration_sec": 85.2,
      "details_dir": "results/local_qwen/telequad_gen_0_shot_details.jsonl"
    }
  ]
}
```

---

## 5. run_mixed_benchmark.sh 改动

### 5.1 改为两阶段串联

```bash
# ── 阶段 1：推理 ──
docker run --rm \
    --env-file "${ENV_FILE}" \
    -e LOCAL_CONCURRENCY=20 \
    -v "${DATA_DIR}:/app/data" \
    -v "${OUTPUT_DIR}:/app/outputs" \
    -v "${CODE_DIR}/eval_entry.py:/app/eval_entry.py" \
    -v "${CODE_DIR}/scripts:/app/scripts" \
    "${IMAGE_TAG}" \
    python eval_entry.py \
        --task-id "${TASK_ID}" \
        --model-config local_qwen \
        --tasks 1 34 36 43 44 60 \
        --generic-datasets \
            ceval_gen_0_shot_str \
            mmlu_redux_gen_5_shot_str \
            ... # 其余 generic datasets

# ── 阶段 2：评测 ──
docker run --rm \
    --env-file "${ENV_FILE}" \
    -e LOCAL_CONCURRENCY=20 \
    -v "${DATA_DIR}:/app/data" \
    -v "${OUTPUT_DIR}:/app/outputs" \
    -v "${CODE_DIR}/eval_judge.py:/app/eval_judge.py" \
    -v "${CODE_DIR}/scripts:/app/scripts" \
    "${IMAGE_TAG}" \
    python eval_judge.py \
        --infer-task "${TASK_ID}"
```

### 5.2 部署影响

| 变更点 | 说明 |
|:---|:---|
| Docker 挂载 | 新增挂载 `eval_judge.py` |
| `multi_deploy_benchmark.sh` | 无需改动（只调用 `run_mixed_benchmark.sh`） |
| `scripts/package_deploy.sh` | 打包时包含 `eval_judge.py` |
| `.env` | 无变化 |

---

## 6. 新旧目录结构对比

### 旧格式（eval_entry.py --mode all）

```
outputs/{task_id}/
├── report.md
├── report.json
└── details/
    ├── 20260309_140520/             # 每个任务一个时间戳目录
    │   ├── configs/
    │   ├── logs/
    │   │   ├── infer/
    │   │   └── eval/
    │   ├── predictions/
    │   │   └── local_qwen/
    │   │       └── task_1.jsonl
    │   ├── results/
    │   │   └── local_qwen/
    │   │       ├── task_1.json
    │   │       └── task_1_details.jsonl
    │   └── summary/
    │       ├── summary_*.txt
    │       ├── summary_*.csv
    │       └── summary_*.md
    └── 20260309_140616/
        └── ...
```

### 新格式（eval_entry.py + eval_judge.py）

```
outputs/{task_id}/
├── infer_meta.json                  # 推理元数据
├── details/                         # 推理产物（只生成一次）
│   ├── 20260317_160001/
│   │   ├── predictions/
│   │   │   └── local_qwen/
│   │   │       └── task_1.jsonl
│   │   ├── configs/
│   │   └── logs/
│   │       └── infer/
│   │           └── local_qwen/
│   │               └── task_1.out
│   └── 20260317_160045/
│       ├── predictions/
│       ├── configs/
│       └── logs/
│           └── infer/
├── eval_20260317_170000/            # 评测版本（可多次生成）
│   ├── results/
│   │   └── local_qwen/
│   │       ├── task_1.json
│   │       ├── task_1_details.jsonl
│   │       └── ...
│   ├── logs/
│   │   └── eval/
│   │       └── local_qwen/
│   │           └── task_1.out
│   ├── summary/
│   ├── report.md
│   └── report.json
└── eval_v2_fix_weight/              # 另一个评测版本
    ├── results/
    ├── logs/
    │   └── eval/
    ├── summary/
    ├── report.md
    └── report.json
```

**关键区别**：
- details/ 下保留 predictions + configs + logs/infer/（推理日志）
- 评测结果独立成 eval_{version}/ 目录，包含 results + logs/eval/ + summary
- report.md/json 从根目录移到 eval_{version}/ 内
- 多版本并存，互不干扰

---

## 7. 测试计划

### 7.1 测试数据来源

使用 `/Users/jia/MyProjects/pythonProjects/cmcc_cxy/Bprocss/fmt/` 下的线上旧格式数据作为参照基准。其中 `pt*` 开头的目录为线上实验组，每个包含完整的 `details/` + `report.json`。

可将 `fmt/pt0_sft0/details/` 中各任务的 `predictions/` 和 `configs/` 子目录复制出来，构造 `infer_meta.json`，模拟推理阶段产出，用于测试 eval_judge.py 的评测流程。

### 7.2 测试用例

#### TC-1：eval_entry.py 仅推理模式
- **操作**：`python eval_entry.py --task-id test_infer --model-config local_qwen --tasks 1 --generic-datasets telequad_gen_0_shot`
- **预期**：
  - 生成 `outputs/test_infer/infer_meta.json`
  - `details/` 下有对应时间戳目录，仅包含 `predictions/` 和 `configs/`
  - 不生成 `results/`、`summary/`、`report.*`

#### TC-2：eval_judge.py 全量评测
- **操作**：`python eval_judge.py --infer-task test_infer`
- **预期**：
  - 读取 `infer_meta.json` 定位推理结果
  - 规则型任务（task_1_suite）先执行
  - LLM 型任务（telequad_gen_0_shot）后执行
  - 生成 `eval_{timestamp}/` 目录，包含 results/、summary/、report.md、report.json
  - report.json 中 tasks 列表包含 eval_type 字段

#### TC-3：eval_judge.py 指定任务 + 版本号
- **操作**：`python eval_judge.py --infer-task test_infer --eval-tasks telequad_gen_0_shot --eval-version v2_test`
- **预期**：
  - 只评测 telequad_gen_0_shot
  - 输出目录为 `eval_v2_test/`
  - report.json 中只包含 telequad_gen_0_shot 的结果

#### TC-4：多版本并存
- **操作**：先执行 TC-2，再执行 TC-3
- **预期**：
  - `outputs/test_infer/` 下同时存在 `eval_{timestamp}/` 和 `eval_v2_test/`
  - 两个版本的 report.json 独立，数据不串扰

#### TC-5：LLM 任务自动检测
- **预期**：eval_judge.py 能正确识别以下任务为 LLM 型：
  - `telequad_gen_0_shot`
  - `tele_exam_gen_0_shot_str`
  - `teledata_gen_0_shot`
- 其余任务识别为规则型

#### TC-6：Docker 部署端到端验证
- **操作**：通过 `run_mixed_benchmark.sh` 执行完整流程
- **预期**：
  - 阶段 1（推理）和阶段 2（评测）分别在两个 docker run 中完成
  - 最终目录结构符合新格式
  - report.json 内容完整可解析

#### TC-7：用旧数据验证 eval_judge.py
- **数据准备**：从 `fmt/pt0_sft0/` 复制 predictions + configs，构造 infer_meta.json
- **操作**：`python eval_judge.py --infer-task pt0_sft0_test`
- **预期**：
  - 基于旧推理结果成功产出评测结果
  - 评测分数与 `fmt/pt0_sft0/report.json` 中的分数基本一致（误差容许范围内）

---

## 8. 实施范围

### 需要修改的文件

| 文件 | 改动类型 | 说明 |
|:---|:---|:---|
| `eval_entry.py` | 修改 | 去掉评测逻辑，改为只推理 + 生成 infer_meta.json |
| `eval_judge.py` | **新增** | 评测专用脚本 |
| `run_mixed_benchmark.sh` | 修改 | 两阶段串联调用 |
| `scripts/package_deploy.sh` | 修改 | 打包时包含 eval_judge.py |

### 不需要修改的文件

| 文件 | 理由 |
|:---|:---|
| `ais_bench/` 框架代码 | 利用现有 `--mode infer`、`--mode eval`、`--reuse` 能力，无需改框架 |
| `multi_deploy_benchmark.sh` | 只调用 `run_mixed_benchmark.sh`，无需改动 |
| 数据集 / 模型配置文件 | 无影响 |
| `.env` | 无变化 |
