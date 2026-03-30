# 实验结果数据处理脚本文档 (`process_results.py`)

## 概述
此脚本旨在对多组大模型测试运行后的离散 JSONL 和复杂文件夹结构进行**清洗、字典映射与重组降维**。
针对各种实验配比和测试任务，它会自动整合核心准确率指标并导出易读带有对比色板的汇总大表，同时按易理解的“任务分类”视角（Pivoting）将底层的预测 JSONL 展开存储为对应的 Excel 格式以备溯源检查。

## 一、 输入数据形式 (Dependencies & Inputs)

### 1. 核心原始评测库
脚本默认会去扫描同级目录下由大模型系统跑出的 `outputs/fmt` 树状目录：
- **第一层 (实验组)**：`outputs/fmt/baseline/`、`outputs/fmt/pt0_sft0/` 等。
- **核心文件**：每个实验组下存在的 `report.json`（里面提取各个任务的名称与它的分类精度）。
- **底层明细数据层**：如 `outputs/fmt/pt0_sft0/details/.../results/*.jsonl`，这是模型生成的实际推理文件；以及同级的 `summary/` 实验总结数据夹。

### 2. 外部映射字典关联项
脚本强制需要 `pandas` 与 `openpyxl` 来启动计算。必须在项目的 `outputs/` 根目录里放置两张核心字典关联表格供脚本提取字典翻译：
- `outputs/评测任务文件名对应.xlsx`：用于把框架底层的“英文任务名”（如 `tele_exam_gen_0_shot`）翻译成易读的大表格中文字（如 `通信工程师中级考试真题-选择题`）。
- `outputs/实验设置.xlsx`：用于把测试底层文件夹名中的 ID 尾号（如 `pt44_sft0` 截取得到 44）匹配到该表中第 `44` 号所在行的实际评测信息上（包含语料配比，大组名称等所有列）。

## 二、 代码主要处理逻辑

1. **载入关联映射机制 (Dictionary Mapping)**：
   运行一开始，`load_mappings` 函数会用 pandas 读取上述两张字典结构，并执行非空和去除无效数值清洗（如将 float 类型强制安全转换为 `int()` 防止 `.0`。生成包含对应关系在内存里的词典。
2. **重塑聚合与大盘生成**：
   - 提取所有子目录的 `report.json`。
   - 组装出一张横列包含各组模型配置（以 `baseline` 置于数据首列）、竖列为各类测试的任务二维矩阵表 `总体汇总...xlsx`。
   - 通过 `openpyxl` 让 `baseline` 列通体填塞黄色并固定为基准值。其它参演模型成绩高于 baseline 则标绿，低于则标红。而在图表最下方追加前面载入好的原汁原味的映射图表作为备查附录。
3. **明细翻转生成 (Pivoting Output Directory)**：
   脚本的第二部会深入到 `report.json` 定位的具体 detail 产出位置。此时它会把**外层按任务名聚合，内层按模型实验名展开**进行改建目录。（把以前的模型选任务翻转为任务选模型）。
   - 解析底层的对应 JSONL 结尾的文件。将原先包裹在嵌套 JSON 结构里的复杂参数 (`{"prediction": {"origin_prompt": "...", "prediction": "...", "gold": "..."}}`) 进行解耦（JSON Unpacking），平铺为三列独立的单元格。加上剩余原始两列，共打平产生 5 列结构体保存进单个 Excel 文件中。
   - 利用 `shutil` 系统接口，同时将与之对应的整个 `summary/` 实验运行报告信息库一比一地完全拷贝到目标明细目录下。

## 三、 输出文件格式

每次顺利运行完成必定在当前工程里新建并投递一个自带精确定位时间戳的档案库，格式详见：
```text
outputs/aggregated_reports_20260310_xxxxxx/
├── 总体汇总_20260310_xxxxxx.xlsx              # 核心：Sheet1 为带颜色指标的比较矩阵（含翻译后的测试配比大字典），其余 Sheet 为单实验具体清单
├── 通信工程师中级考试真题-选择题/                   # 全面映射翻译好的测试任务名 (Pivoting 结果)
│   ├── baseline/                              # 无映射保留项 / 或具体对应的映射组方案名
│   │   ├── xxx_details.xlsx                   # 从 Jsonl 打散抽提而来的含有5列(含 prediction/gold)的重要明细
│   │   └── summary/                           # 包含着运行时间概貌的原生 summary_xyz.csv / md 报表连同目录
│   └── set11_dg70-30.../                      # 其他实验
│       └── ...
├── Tele-Data/                                 # 另一个测试大类任务名
│   ├── baseline/
│   └── set11_dg70-30.../
└── ...
```

## 四、 如何运行

请确保目前处于包含有所需基础运算包（`pandas`, `openpyxl`）的正常 Python 虚拟解析环境。通常为本项目专门设定的 `ais_bench` conda 环境。
```bash
# 1. 激活专用环境
conda activate ais_bench 

# 2. 如果缺少 Excel 编辑依赖则进行安装
pip install pandas openpyxl

# 3. 在保证 outputs/ 目录下有 `fmt` 文件夹及两份对应字典文件后，运行主体脚本：
python process_results.py
```
