# 垂类模型演示数据挑选设计 (yanshi_demo)

**日期**：2026-04-10
**作者**：HeJia + Claude
**状态**：Approved (pending user review)

---

## 1. 背景与目标

### 1.1 背景

现有一份 1000 条的"垂类模型 A vs. 通用模型 B"评测数据：

- 原始 JSON：`mydata/yanshi_demo/model_knowledge_eval_results.json`
- 已整理的对比 Excel：`mydata/yanshi_demo/eval_comparison.xlsx`
- 差距较大子集：`mydata/yanshi_demo/eval_comparison_gap_ge1.xlsx`

每条样本包含：

- `instruction`（问题，末尾带 `\n/no_think` 后缀）
- `reference`（标准答案）
- `model_a_output` / `model_b_output`（垂类 A、通用 B 的回答，含 `<think>` 标签）
- `eval_a` / `eval_b`：`score` (1-5)、`evaluation`（文字评估）、`hallucination`（bool）

整体数据是 **电力/通信设备** 领域：电抗器、Framer 芯片、LPU/PIC 板卡、告警分级等。
总体平均分：**A=3.84，B=3.75**（A 略优，差距不大，但在部分子领域预计有显著优势）。

### 1.2 目标

从这 1000 条里挑选出**最适合演示的样本**，用于：

1. **现场 Demo**（主戏，ii：真·双模型同题对跑）
2. **一页 PPT**（体现系统整体优势，Z：左图 + 右案例卡）

要突出的优势方向（三类）：

- **A 分数碾压**：A 得分显著高于 B
- **B 反幻觉**：B 出现事实错误/编造而 A 答对
- **C 专业精准**：A 简洁命中专业要点，B 冗长跑题

### 1.3 演示规模与约束

| 维度 | 规格 |
|---|---|
| 精华样本 | 每类 3 条 = **9 条**；加 3 条备选（每类 1 条）共 12 条 |
| 批量样本 | **50~100 条**（目标 80），集中在"垂类最擅长的 Top 2~3 子领域" |
| 观众 | 主要为 **乙**（公司领导/业务方），部分 **甲**（行业专家） |
| 领域聚焦 | 精华 9 条里 **至少 6 条** 来自 Top 2~3 火力领域 |
| 观众层次 | 精华 9 条里 **7~8 条** 面向乙（通俗）+ **1~2 条** 面向甲（硬核） |
| 题目清洗 | 剥离 `/no_think` 后缀 + `<think>...</think>` 标签 |

### 1.4 现场 Demo 鲁棒性要求

因为是真实时调用双模型对跑（ii 方案），筛选时必须考虑：

- 挑"结果稳定、能复现"的题目，避免分差处于边界（0.9~1.1、1.9~2.1 等）
- 建议现场运行时 `temperature=0`
- 每条精华题需提前预热跑 2 次确认稳定，不稳定的题从备选池替换

---

## 2. 总体流程

```
原始 JSON (1000 条)
      │
      ├── ① 预处理：剥离 /no_think 与 <think> 标签；抽取字段；去除 failed
      │
      ├── ② 子领域识别（关键词规则 → 主 domain 标签）
      │
      ├── ③ 计算"垂类优势领域"：按 domain 算 mean_gap / win_rate
      │        → 取 Top 2~3 作为火力集中点
      │
      ├── ④ 宽松筛选 → 三类候选池 (A / B / C)，按 B>A>C 优先级去重
      │
      ├── ⑤ 演示表演力打分 → 每池内排序取 Top 10（火力领域加成 ×1.30）
      │
      ├── ⑥ 人工精修（对话 review）→ 每类定 3 条 + 备选 1 条
      │
      └── ⑦ 批量采样 + 产出物生成
              │
              └── ./mydata/yanshi_demo/demo_pick/
                  ├── domain_stats.csv
                  ├── candidates_pool.xlsx
                  ├── candidates_top10.md
                  ├── highlight_9.xlsx / .json
                  ├── batch_80.xlsx
                  ├── ppt_card.md
                  ├── ppt_card_chart.png
                  ├── ppt_card_preview.png
                  └── demo_script.md
```

---

## 3. 子领域识别 (Step ②)

### 3.1 候选领域与关键词（初稿）

| 主 domain | 关键词 |
|---|---|
| 电力测量与损耗 | 电抗器, 损耗, 相电, 瓦特, 电压, 电流, 励磁, 铁心, 绕组, 变压器, 有功, 无功, 互感 |
| 设备硬件故障 | 单板, 板卡, 故障, 损坏, 失效, 掉卡, 烧毁, 故障码 |
| 告警与运维 | 告警, 等级, 严重, 监控, 日志, 排查, 恢复, 一级告警, 二级告警 |
| 芯片与接口 | Framer, PHY, MAC, FPGA, CPU, 芯片, ID寄存器, 寄存器, 晶振 |
| 板卡与硬件结构 | LPU, PIC, SPU, 背板, 槽位, 接口卡, 风扇, 电源模块 |
| 网络协议与传输 | SDH, SONET, 帧同步, 光模块, 误码, 封装, VLAN, MPLS |
| 配置与命令行 | display, reset, undo, view, 配置命令, 命令行, CLI |
| 其他专业知识 | （兜底，无命中归此） |

### 3.2 打标签规则

- 按上表 **从上到下** 的顺序依次匹配（简单可预测），第一个命中的即主 domain
- 一条样本可同时带多个 tag（写入 `tags` 字段），但排名时只用主 domain
- 全部未命中 → "其他专业知识"

**说明**：词表是初稿，脚本第一次跑时会同时输出**全量问题关键词词频 Top 100**，便于人工微调词表后再重跑。

### 3.3 "垂类优势领域" 指标

每个 domain 算：

| 指标 | 计算 |
|---|---|
| `n` | 该 domain 样本数 |
| `mean_gap` | `mean(score_a - score_b)` |
| `win_rate` | `count(score_a > score_b) / n` |
| `a_hallu_rate` | A 幻觉率 |
| `b_hallu_rate` | B 幻觉率 |
| `rank_score` | `mean_gap × win_rate`（排序用） |

**筛选规则**：

- `n ≥ 30`（样本太少不参与，避免噪声）
- 按 `rank_score` 降序排序
- 取 Top 2~3 为**火力集中点**（`selected=True`）

产出：`domain_stats.csv`

---

## 4. 三类候选池的宽松筛选 (Step ④)

> 注意：脚本实现时，每类的筛选规则**和原因**都必须写到注释里。

### 4.1 A 类：分数碾压

```
条件:
  eval_a.score >= 4.0            # A 至少是"看得过去的正确答案"
  eval_b.score <= 2.5            # B 明显不及格
  (eval_a.score - eval_b.score) >= 1.5  # 一眼能看出差距
```

比硬阈值（4.5/2.0/2.5）略宽，保证池子够大（预计 15~30 条）。

### 4.2 B 类：反幻觉

```
条件:
  eval_b.hallucination == True
  eval_a.hallucination == False
  eval_a.score >= 3.5            # A 答得过去
  (eval_a.score - eval_b.score) >= 1.0
```

如果此池不足 10 条，脚本打印告警，人工降阈值 `eval_a.score >= 3.0` 重跑。

### 4.3 C 类：专业精准

```
条件:
  eval_a.score >= 4.0
  eval_b.score <= 3.5
  (eval_a.score - eval_b.score) >= 1.0
  len(model_b_output) >= 2.5 * len(model_a_output)  # 啰嗦度
  len(model_a_output) <= 600 字                      # A 本身必须短
```

`len` 基于**清洗后的文本**（剥除 `<think>`、markdown 装饰）。

### 4.4 去重与归属优先级

一条样本可能同时落入多个池子，按 **B > A > C** 归属到单一池。

**原因**：B 类样本最稀缺、故事感最强（揭穿幻觉），要优先保护；A 类是"直观震撼"的主力；C 类是"简洁 vs. 冗长"的增色。

---

## 5. 演示表演力打分 (Step ⑤)

### 5.1 信号因子

所有信号归一化到 `[0, 1]`：

| 符号 | 含义 | 计算 |
|---|---|---|
| `s_gap` | 分差 | `clip((score_a - score_b) / 4, 0, 1)` |
| `s_a_short` | A 简洁度 | `1 - clip(len_a / 300, 0, 1)` |
| `s_b_long` | B 啰嗦度 | `clip(len_b / 1500, 0, 1)` |
| `s_ratio` | 长度比 | `clip(log(len_b / len_a) / log(10), 0, 1)` |
| `s_q_short` | 问题简洁度 | `1 - clip(len_q / 120, 0, 1)` |
| `s_audience` | 观众友好度 | `1 - 硬核术语密度`（见 5.2） |
| `s_halluB` | B 幻觉 | `1 if eval_b.hallucination else 0` |
| `s_robust` | 鲁棒性 | 见 5.3 |

### 5.2 硬核术语密度

维护一个"硬核术语"小词表：

```
LPU, PIC, SPU, Framer, PHY, MAC, FPGA, SDH, SONET, STM-1, STM-4, STM-16,
VC-12, VC-3, IEEE, MPLS, VLAN, GPON, ID寄存器, BIP, CRC, 背板, ASIC
```

计算：`硬核术语出现次数 / 题干字数`（×100 后归一化到 [0,1]），取 `1 - 密度`。越通俗分越高。

### 5.3 鲁棒性评分

```
s_robust 计算逻辑：
  · 分差在边界带 (0.9~1.1, 1.9~2.1, 2.9~3.1) 内 → 0.0 (扣分，临界易翻)
  · A >= 4.5 且 B 幻觉 True → 1.0 (铁案)
  · 其他 → 0.5 (中性)
```

### 5.4 三类权重（每类侧重项到 0.40）

| 权重 | A 分数碾压 | B 反幻觉 | C 专业精准 |
|---|---|---|---|
| `s_gap` | **0.40** | 0.13 | 0.12 |
| `s_halluB` | 0.04 | **0.40** | 0.04 |
| `s_ratio` | 0.09 | 0.09 | **0.40** |
| `s_a_short` | 0.09 | 0.09 | 0.12 |
| `s_b_long` | 0.04 | 0.04 | 0.08 |
| `s_q_short` | 0.13 | 0.13 | 0.12 |
| `s_audience` | 0.13 | 0.08 | 0.08 |
| `s_robust` | 0.08 | 0.04 | 0.04 |
| **合计** | 1.00 | 1.00 | 1.00 |

### 5.5 领域加成

```
if sample.main_domain in TOP_DOMAINS (火力集中点):
    show_score *= 1.30
```

让 Top 10 里优势领域占大多数，但不完全屏蔽别家领域的戏剧性样本。

### 5.6 输出

每池按 `show_score` 降序取 **Top 10**，写入 `candidates_top10.md`（Markdown 表格 + 样本详情，便于人工阅读）。

---

## 6. 人工精修 (Step ⑥)

### 6.1 展示材料

`candidates_top10.md` 的每条记录格式：

```markdown
### [A#3] show_score=0.78

- **主 domain**: 设备硬件故障
- **分数**: A=4.5 / B=2.0 / gap=2.5
- **B 幻觉**: False
- **长度**: Q=22 字, A=40 字, B=1240 字, ratio=31.0

**Q**: 单板发生故障时可能造成什么业务影响？

**A (垂类)**:
> 单板发生故障时可能造成设备局部故障，进而可能导致业务受影响...

**B (通用)** [前 150 字摘要]:
> 单板发生故障时，可能对业务造成的影响取决于该单板在系统中的角色和功能...

**评语 A**: 候选答案基本涵盖了参考答案的核心事实...
**评语 B**: 候选答案涵盖了参考答案中提到的业务中断和硬件告警...
```

### 6.2 挑选原则（按优先级）

1. 每类挑 3 条 + 备选 1 条
2. 9 条里 ≥6 条来自火力领域（Top 2~3 domain）
3. 9 条里 7~8 条面向乙（通俗）+ 1~2 条面向甲（硬核）
4. 从 9 条里钦点 **1 条 PPT 门面卡**，硬标准：
   - 分差 ≥ 2.5
   - B 幻觉 == True
   - 题干 ≤ 30 字
   - A 答案 ≤ 120 字
   - 乙类观众能秒懂
   - 若无完全满足的，取最接近的

### 6.3 流程

1. 脚本输出 `candidates_top10.md`
2. 用户单独开窗口阅读
3. 回到对话，按 ID 指定选哪 3+1 条 / 类
4. Claude 根据选择生成最终产物 (§7)

---

## 7. 产出物清单 (Step ⑦)

**输出目录**：`mydata/yanshi_demo/demo_pick/`

精简到 **7 个文件**（已合并冗余项）：

| 文件 | 内容 | 用途 |
|---|---|---|
| `domain_stats.csv` | 各领域 n / mean_gap / win_rate / 幻觉率 / selected | 数据证据底（也是演示附录） |
| `candidates_top10.md` | 三类 Top 10 的人工 review 材料 | 人工精修输入（Stage 1 产物） |
| `demo_data.xlsx` | 三个 sheet：精华 9 / 备选 3 / 批量 80 | 演示主数据（Excel 留档、观众翻阅） |
| `demo_data.json` | 精华 9 + 备选 3 的完整字段 | 现场 Demo 程序读取 |
| `ppt_card_chart.png` | 分组柱状图（matplotlib，300dpi） | 直接拖进 PPT 一页左半 |
| `ppt_card_preview.png` | 门面卡完整效果预览（左图+右卡） | 所见即所得，也可当 PPT 底图 |
| `demo_script.md` | 口播稿 + 门面卡文案 + 鲁棒性建议 + 顺序建议 | 现场剧本（合并了原 ppt_card.md） |

**精简理由**：
- 原 `candidates_pool.xlsx` → 中间产物，review 用 `candidates_top10.md` 足够
- 原 `highlight_9.xlsx` + `batch_80.xlsx` → 合并为 `demo_data.xlsx`（多 sheet）
- 原 `ppt_card.md` → 文案并入 `demo_script.md`

### 7.1 批量 80 条的采样

- **池子**：`mean_gap >= 1` 的所有样本 ∩ 主 domain 属于 Top 2~3 火力领域
- **分层采样**：按 domain 等比例分配 80 个名额
- **去重**：排除已在 `highlight_9` 和备选 3 条里的样本
- **排序**：按 `show_score` 降序（批量部分不单独重算 show_score，沿用打分结果）

### 7.2 文本清洗规则（所有产出共享）

- 剥离题干末尾的 `\n/no_think`
- 剥离输出开头的 `<think>\n\n</think>\n\n`（以及任何 `<think>.*?</think>` 对）
- 保留原始列（`model_a_output_raw`）+ 清洗列（`model_a_output`）
- 长答案（> 300 字）额外给一个 `model_b_output_summary`（前 200 字 + 省略号）

### 7.3 `ppt_card_chart.png` 规格

- 类型：分组柱状图
- X 轴：总体、Top 1 领域、Top 2 领域、Top 3 领域
- Y 轴：平均分 (0~5)
- 两组柱子：垂类 A（主色） vs. 通用 B（对比色）
- 柱顶标数值
- matplotlib 保存为 300dpi PNG，尺寸 1440×1080（方便 PPT 缩放）

### 7.4 `ppt_card_preview.png` 规格

- 使用 matplotlib 或 PIL 渲染门面卡模板（§6.2 的硬标准选出的那条）
- 尺寸 1920×1080，左右分栏：左图 + 右文字卡
- 字体使用系统字体，题干/垂类/通用三块分区

### 7.5 `demo_script.md` 结构

```markdown
# 现场 Demo 口播脚本

## 演示顺序
推荐：B 反幻觉 → A 分数碾压 → C 专业精准
（情绪曲线：先震惊 → 后认同 → 再信服）

## 鲁棒性建议
- temperature=0
- 每题预热跑 2 次
- 不稳定的题从备选池 (3 条) 替换

## 9 条精华口播稿
### [B-1] ...
**30 秒口播**: 这一题是 XXX，通用模型 B 的回答乍一听很专业，但...

### [A-1] ...
...

## 备选 3 条
### [备选 B] ...
...
```

---

## 8. 实现范围与非范围

### 范围

- 一个 Python 脚本 `scripts/pick_demo_data.py`（或拆成若干辅助脚本）
- 输入：`mydata/yanshi_demo/model_knowledge_eval_results.json`
- 输出：`mydata/yanshi_demo/demo_pick/` 下所有文件
- 依赖：`pandas, openpyxl, matplotlib, pillow`（若无请 pip 安装）
- 每个筛选/打分函数都有中文注释说明规则和原因
- 两阶段运行：
  - **Stage 1**：预处理 + 领域统计 + 候选池 + 打分 → 产出 `domain_stats.csv` / `candidates_top10.md` / `ppt_card_chart.png`
  - **人工 review**（对话里确认）
  - **Stage 2**：根据人工选择生成 `demo_data.xlsx` / `demo_data.json` / `ppt_card_preview.png` / `demo_script.md`

### 非范围

- 不修改原始 JSON / Excel
- 不重新评测（完全基于已有评分）
- 不做文本语义相似度/embedding（用关键词规则够用）
- 不做领域聚类（用显式词表，可解释）
- 不连接真实模型 API（鲁棒性建议写到文档里即可，不做实际预热跑）

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| B 反幻觉池不足 10 条 | 脚本打印告警 + 提示降阈值方案 |
| 关键词词表未覆盖重要领域 | Stage 1 输出词频 Top 100，允许人工修订后重跑 |
| Top 2~3 火力领域的样本不够填满批量 80 条 | 降级到 Top 4 甚至放宽 `mean_gap >= 1` 条件 |
| 现场 Demo 翻车（模型复现失败） | 鲁棒性打分 + temperature=0 + 备选 3 条 + 预热跑 |
| 门面卡硬标准没有完全匹配的样本 | 取最接近的，并在 `ppt_card.md` 说明妥协项 |

---

## 10. 后续步骤

1. 用户 review 本 spec
2. 写 implementation plan（通过 writing-plans skill）
3. 实施 Stage 1 脚本
4. 对话里人工精修
5. 实施 Stage 2 产出
6. 用户验收
