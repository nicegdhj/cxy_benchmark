# 垂类模型演示数据挑选 - 实施计划

**对应 spec**: `docs/superpowers/specs/2026-04-10-yanshi-demo-data-pick-design.md`
**日期**: 2026-04-10

---

## 总览

做一个**简单直接**的两阶段脚本，中间插一次人工 review。

- **Stage 1 脚本**：`scripts/pick_demo_stage1.py`（跑完后用户在对话里选条目）
- **Stage 2 脚本**：`scripts/pick_demo_stage2.py`（读取用户选择，产出最终文件）
- **输出目录**：`mydata/yanshi_demo/demo_pick/`

共 **2 个脚本文件**。不拆模块、不写测试（一次性数据处理工具，验证靠肉眼看输出）。

---

## Stage 1 脚本步骤

**文件**：`scripts/pick_demo_stage1.py`

1. **读 JSON** → 展开为 DataFrame，字段：`item_index, instruction, reference, model_a_output, model_b_output, score_a, score_b, hallu_a, hallu_b, eval_a_text, eval_b_text`
2. **文本清洗**（新增列，原列保留）
   - `instruction_clean`：剥 `\n/no_think`
   - `model_a_output_clean`、`model_b_output_clean`：剥 `<think>...</think>`
   - `len_q`, `len_a`, `len_b`（基于 clean 后）
3. **关键词打标签**
   - 按 spec §3.1 词表，按顺序优先级匹配出 `main_domain`
   - 同时输出 `question_keyword_freq_top100.txt`（调试用，放 demo_pick/ 下）
4. **算 domain_stats** → 写 `domain_stats.csv`
   - 过滤 `n >= 30` 的 domain，按 `mean_gap * win_rate` 排序，标记 Top 3 为 `selected=True`
5. **宽松筛选三类候选池**（spec §4，每个条件都配中文注释说明规则和原因）
   - 按 B > A > C 优先级去重
6. **演示表演力打分**（spec §5）
   - 每个信号函数单独写，方便调阅
   - 每池各自用对应权重算 `show_score`
   - 火力领域 ×1.30
7. **每池取 Top 10** → 写 `candidates_top10.md`
   - 按 spec §6.1 格式：分数、domain、长度、Q/A/B 摘录、评语
   - 长答案截前 200 字 + 省略号
8. **画 PPT 左图** → `ppt_card_chart.png`
   - matplotlib 分组柱状图
   - X 轴：总体 + Top 3 domain；Y 轴：平均分
   - 300dpi, 1440×1080
   - 柱顶标数值，中文字体要处理好

**验收**（跑完后肉眼检查）：
- [ ] `domain_stats.csv` 存在，Top 3 domain 看起来合理
- [ ] `candidates_top10.md` 三类各有 ≥10 条（B 类 <10 给出警告）
- [ ] `ppt_card_chart.png` 能打开，中文正常、数值正常

---

## 人工 review（对话里完成）

1. 用户打开 `candidates_top10.md` 阅读
2. 用户告诉 Claude：每类选哪 3 条 + 备选 1 条 + 哪一条当 PPT 门面
3. Claude 把选择写入 **选择配置**（直接写成 Python dict 贴到 Stage 2 脚本顶部，或者写一个简单的 `selection.json`）

**选择配置格式**（`mydata/yanshi_demo/demo_pick/selection.json`）：
```json
{
  "highlight": {
    "A": [int, int, int],
    "B": [int, int, int],
    "C": [int, int, int]
  },
  "backup": {
    "A": int,
    "B": int,
    "C": int
  },
  "ppt_card_id": int
}
```
（里面的 int 是 `item_index`）

---

## Stage 2 脚本步骤

**文件**：`scripts/pick_demo_stage2.py`

1. **读取** Stage 1 的打分结果（从 candidates_pool 里重建，或者 Stage 1 顺手存个 `_cache.pkl`）+ `selection.json`
2. **生成 `demo_data.xlsx`**（3 个 sheet）
   - `精华`：9 条，列：序号、类别(A/B/C)、domain、问题、标准答案、垂类答案、A得分、评语A、通用答案、B得分、评语B、B幻觉
   - `备选`：3 条，同上
   - `批量`：80 条，从 `gap>=1 ∩ main_domain in Top3` 的池子里按 domain 等比例分层采样，排除已在精华+备选里的
3. **生成 `demo_data.json`**：精华 9 + 备选 3 的完整字段（含原始未清洗文本，给 demo 程序最大灵活度）
4. **生成 `ppt_card_preview.png`**
   - 用 matplotlib + figure 画布，左半贴 `ppt_card_chart.png`，右半用 `text()` 画文字卡
   - 1920×1080，中文字体
   - 问题、垂类答案、通用答案三块分区，"得分"、"幻觉" 标签用颜色标出
5. **生成 `demo_script.md`**
   - 结构见 spec §7.5
   - 演示顺序：B → A → C
   - 每条精华生成一段 30~60 秒口播稿（基于问题/答案差异点/评语自动填空，允许后续人工润色）
   - 包含门面卡文案（原 `ppt_card.md` 的内容）
   - 末尾贴 temperature=0 + 预热跑 2 次 + 备选替换的鲁棒性建议

**验收**（肉眼检查）：
- [ ] `demo_data.xlsx` 三个 sheet 打开正常
- [ ] `demo_data.json` 能被 `json.load` 解析
- [ ] `ppt_card_preview.png` 能打开、排版没崩
- [ ] `demo_script.md` 9 条口播稿都有内容，顺序是 B→A→C

---

## 实施顺序

1. 先跑 **Stage 1 的前半**（读 JSON + 清洗 + 关键词词频统计），让用户先看一眼 `question_keyword_freq_top100.txt`，**确认词表初稿是否需要微调**
2. 用户确认词表后，跑完整 Stage 1
3. 用户打开 `candidates_top10.md` review
4. 用户告诉 Claude 选择 → Claude 写 `selection.json`
5. 跑 Stage 2
6. 用户验收

---

## 依赖

- `pandas`, `openpyxl`, `matplotlib`, `pillow`
- 脚本开头检查依赖，缺了就 `print` 安装命令让用户手动装

---

## 非事项（避免过度工程）

- 不写单元测试
- 不做 argparse（路径都写死在脚本顶部的常量）
- 不做配置文件 YAML（直接 Python 常量）
- 不做日志模块（`print` 就够）
- 不拆 `utils/` `models/` 等子模块，两个脚本各自独立可运行

---

## 使用指南（从头到尾怎么跑）

所有命令都在仓库根目录 `benchmark/` 下执行。输出全部落到 `mydata/yanshi_demo/demo_pick/`。

### Step 1：看关键词词频，确认词表
```bash
python scripts/pick_demo_stage1.py --preview-keywords
```
- 脚本只跑到"关键词词频统计"就停
- 产物：`mydata/yanshi_demo/demo_pick/question_keyword_freq_top100.txt`
- 你打开这个文件确认 spec §3.1 的词表够不够用

### Step 2：如需调整词表
- 直接编辑 `scripts/pick_demo_stage1.py` 顶部的 `DOMAIN_KEYWORDS` 常量（已按 spec §3.1 内置）
- 保存后继续下一步

### Step 3：跑完整 Stage 1
```bash
python scripts/pick_demo_stage1.py
```
- 产物：
  - `domain_stats.csv`
  - `candidates_top10.md`
  - `ppt_card_chart.png`
  - `_stage1_cache.pkl`（Stage 2 要读）
- 如果某池 <10 条，终端会打印黄色 `⚠ WARNING` 并建议如何放宽阈值

### Step 4：人工 review
- 打开 `mydata/yanshi_demo/demo_pick/candidates_top10.md`
- 回到对话里，按如下格式告诉 Claude 你的选择：
  ```
  A类精华: A#1, A#3, A#7
  B类精华: B#2, B#4, B#5
  C类精华: C#1, C#2, C#6
  备选: A#5, B#8, C#3
  PPT门面: B#2
  ```
- Claude 会生成 `selection.json` 写到 `demo_pick/` 下

### Step 5：跑 Stage 2
```bash
python scripts/pick_demo_stage2.py
```
- 产物：
  - `demo_data.xlsx`（三 sheet：精华/备选/批量）
  - `demo_data.json`
  - `ppt_card_preview.png`
  - `demo_script.md`

### Step 6：验收
- 打开 Excel、PNG、MD 文件逐个看
- 不满意的话可以回到 Step 4 改 selection 再跑 Step 5（Stage 1 不用重跑）

### 如果想完全重来
```bash
rm -rf mydata/yanshi_demo/demo_pick/
python scripts/pick_demo_stage1.py
...
```
