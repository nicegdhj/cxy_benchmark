/**
 * 任务详情元数据配置
 * key 与 task_meta.py 中的 TASK_META key 保持一致
 * 可在此手动新增 / 修改任意字段
 *
 * 字段说明：
 *   format.type        - 文件格式：JSONL | JSON | folder
 *   format.desc        - 格式文字说明
 *   format.fields      - 主要字段说明 { fieldName: description }
 *   demo.input         - 一条样例数据（对象，会被 JSON.stringify 显示）
 *   demo.output        - 样例的期望输出（字符串）
 *   accuracy.formula   - 准确率公式
 *   accuracy.desc      - 计算方式说明
 *   accuracy.example   - 具体举例
 *   aisBench.suite     - ais_bench 数据集/suite 名称
 *   aisBench.evalType  - 评测类型
 *   aisBench.shot      - few-shot 设置
 *   aisBench.note      - 补充说明
 */

export const TASK_DETAIL_META = {

  // ── 通用标准基准 ────────────────────────────────────────────────────

  "mmlu_redux_gen_5_shot_str": {
    format: {
      type: "JSONL",
      desc: "每行一个 JSON 对象，包含题目（含四个选项）和标准答案字母。",
      fields: {
        input: "题干 + 四个选项，拼接为字符串",
        target: "正确答案字母，如 'A' / 'B' / 'C' / 'D'",
      },
    },
    demo: {
      input: {
        input: "Which of the following is the primary mechanism by which mRNA vaccines induce immunity?\nA. Direct injection of viral proteins\nB. Instructing cells to produce a target protein that triggers an immune response\nC. Weakened live virus stimulating antibody production\nD. DNA integration into the host genome",
        target: "B",
      },
      output: "B",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "对模型输出进行字符串提取，取最后出现的 A/B/C/D 作为答案，与 target 字段完全匹配则计为正确。",
      example: "共 2000 题，模型回答正确 1480 题 → Accuracy = 1480 / 2000 = 74.0%",
    },
    aisBench: { suite: "mmlu_redux_gen_5_shot_str", evalType: "多项选择（5-shot）", shot: "5-shot", note: "MMLU-Redux 对原始 MMLU 中标注错误题目进行了修订，共 30 个学科" },
  },

  "ceval_gen_0_shot_str": {
    format: {
      type: "JSONL",
      desc: "每行一个 JSON 对象，包含中文题目及四个选项，标准答案为选项字母。",
      fields: { input: "中文题干 + 四选项拼接", target: "答案字母 A/B/C/D" },
    },
    demo: {
      input: {
        input: "下列哪种方式不属于计算机网络的传输介质？\nA. 双绞线\nB. 光纤\nC. 声波\nD. 同轴电缆",
        target: "C",
      },
      output: "C",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "提取模型输出中的选项字母，与 target 完全匹配计为正确。",
      example: "共 1346 题，答对 968 题 → Accuracy = 71.9%",
    },
    aisBench: { suite: "ceval_gen_0_shot_str", evalType: "多项选择（0-shot）", shot: "0-shot", note: "覆盖 52 个中文学科，零样本测试中文理解与知识能力" },
  },

  "gpqa_gen_0_shot_str": {
    format: {
      type: "JSONL",
      desc: "博士级难度问题，四选一，每道题均经过专家验证。",
      fields: { input: "题干 + 四选项", target: "答案字母" },
    },
    demo: {
      input: {
        input: "A researcher performs a reaction under kinetic control. Which product is preferentially formed?\nA. The thermodynamically most stable product\nB. The product from the fastest elementary step\nC. The product with the highest activation energy\nD. The product formed via the most endothermic pathway",
        target: "B",
      },
      output: "B",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "字母完全匹配，Diamond 子集共 198 题，随机基线约 25%。",
      example: "答对 128 题 → Accuracy = 64.6%",
    },
    aisBench: { suite: "gpqa_gen_0_shot_str", evalType: "多项选择（0-shot）", shot: "0-shot", note: "GPQA-Diamond 子集，仅博士专家能可靠作答" },
  },

  "bbh_gen_3_shot_cot_chat": {
    format: {
      type: "JSONL",
      desc: "Big-Bench Hard，23 个多样化推理任务，3-shot Chain-of-Thought 格式。",
      fields: { input: "含 3 个示例的 CoT prompt + 题干", target: "最终答案（字母或短文本）" },
    },
    demo: {
      input: {
        input: "Q: Which of the following is a humorous edit of the sentence 'The dog barked at the tree.'\nOptions:\n(A) The dog barked at the car.\n(B) The dog meowed at the tree.\n(C) The cat barked at the tree.\n(D) The dog barked at the moon.",
        target: "(B)",
      },
      output: "(B)",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "提取模型输出最后一行的答案标记，与 target 匹配。",
      example: "共 6511 题，答对 5429 题 → Accuracy = 83.4%",
    },
    aisBench: { suite: "bbh_gen_3_shot_cot_chat", evalType: "多任务推理（3-shot CoT）", shot: "3-shot", note: "覆盖逻辑、算术、常识等 23 类推理任务" },
  },

  "BFCL_gen_simple": {
    format: {
      type: "JSONL",
      desc: "函数调用（Function Calling）基准，单轮任务子集，模型需输出合法的 JSON 工具调用。",
      fields: { question: "用户指令", function: "可用工具定义数组（name/description/parameters）", answer: "期望的工具调用 JSON" },
    },
    demo: {
      input: {
        question: "What is the weather like in Shanghai right now?",
        function: [{ name: "get_weather", description: "Get current weather for a city", parameters: { type: "object", properties: { city: { type: "string" } }, required: ["city"] } }],
      },
      output: '{"name": "get_weather", "arguments": {"city": "Shanghai"}}',
    },
    accuracy: {
      formula: "Accuracy = N_valid_calls / N_total × 100%",
      desc: "解析模型输出的 JSON，检查 name 字段匹配且 arguments 字段语义正确（AST 级比对）。",
      example: "共 800 题，有效调用 640 次 → Accuracy = 80.0%",
    },
    aisBench: { suite: "BFCL_gen_simple", evalType: "函数调用（单轮）", shot: "0-shot", note: "BFCL v3 单轮子集，不含多轮和并行调用场景" },
  },

  "ifeval_0_shot_gen_str": {
    format: {
      type: "JSONL",
      desc: "指令遵循评测，每条数据含一条带显式约束的 prompt，如『不使用逗号』、『回复超过 500 词』。",
      fields: { prompt: "含约束描述的用户指令", instruction_id_list: "约束 ID 列表", kwargs: "约束参数" },
    },
    demo: {
      input: {
        prompt: "写一段介绍人工智能发展历史的文字，要求不少于300个汉字，且不能包含感叹号。",
        instruction_id_list: ["length_constraint:min_chars", "punctuation:no_exclamation"],
        kwargs: [{ min_chars: 300 }, {}],
      },
      output: "（模型输出满足上述两条约束的文本）",
    },
    accuracy: {
      formula: "Prompt-level Accuracy = 满足所有约束的样本 / 总样本数",
      desc: "对每条约束逐一用规则检验（字符数、禁用标点、关键词等），所有约束全部通过才计为正确（strict 模式）。",
      example: "共 541 条，有 380 条全部约束通过 → Prompt Accuracy = 70.2%",
    },
    aisBench: { suite: "ifeval_0_shot_gen_str", evalType: "指令遵循（严格匹配）", shot: "0-shot", note: "IFEval strict-prompt，约束类型包含关键词、长度、格式、标点等 25 种" },
  },

  "math500_gen_0_shot_cot_chat_prompt": {
    format: {
      type: "JSONL",
      desc: "高难度数学题，模型需先推导过程（CoT）再给出最终数值答案。",
      fields: { problem: "题目描述", solution: "参考解题过程", answer: "最终数值答案" },
    },
    demo: {
      input: {
        problem: "Find all values of x satisfying |2x - 3| = 7.",
        answer: "x = 5 or x = -2",
      },
      output: "x = 5 or x = -2",
    },
    accuracy: {
      formula: "Accuracy = N_correct / 500 × 100%",
      desc: "从模型输出中提取 \\boxed{} 内的答案，进行数学等价判断（支持分数、根式、集合等价形式）。",
      example: "500 道题中答对 442 道 → Accuracy = 88.4%",
    },
    aisBench: { suite: "math500_gen_0_shot_cot_chat_prompt", evalType: "数学推理（0-shot CoT）", shot: "0-shot", note: "MATH 数据集中精选的 500 道竞赛级数学题" },
  },

  "aime2025_gen_0_shot_chat_prompt": {
    format: {
      type: "JSONL",
      desc: "美国数学邀请赛（AIME）2025 年真题，答案为 000-999 的整数。",
      fields: { problem: "题目描述", answer: "0-999 的整数答案" },
    },
    demo: {
      input: {
        problem: "Let the sequence a_1, a_2, ... satisfy a_1=1 and a_{n+1} = a_n + floor(sqrt(a_n)) for n≥1. Find a_{2025}.",
        answer: "15",
      },
      output: "15",
    },
    accuracy: {
      formula: "Accuracy = N_correct / 30 × 100%",
      desc: "提取模型最终输出的整数，与标准答案完全匹配，共 30 道题（AIME I + II 各 15 题）。",
      example: "答对 9 题 → Accuracy = 30.0%",
    },
    aisBench: { suite: "aime2025_gen_0_shot_chat_prompt", evalType: "竞赛数学（0-shot）", shot: "0-shot", note: "2025 年 AIME I & II，随机基线接近 0%" },
  },

  "humaneval_gen_0_shot": {
    format: {
      type: "JSONL",
      desc: "Python 代码生成，给定函数签名和 docstring，模型补全函数体，通过单元测试判断正确性。",
      fields: { task_id: "题目 ID", prompt: "函数签名 + docstring", canonical_solution: "参考实现", test: "单元测试代码", entry_point: "函数名" },
    },
    demo: {
      input: {
        task_id: "HumanEval/0",
        prompt: "def has_close_elements(numbers: List[float], threshold: float) -> bool:\n    \"\"\"Check if any two elements in the list are closer than threshold.\"\"\"\n",
        entry_point: "has_close_elements",
      },
      output: "    for i in range(len(numbers)):\n        for j in range(i+1, len(numbers)):\n            if abs(numbers[i]-numbers[j]) < threshold:\n                return True\n    return False",
    },
    accuracy: {
      formula: "pass@1 = 通过测试的样本数 / 164 × 100%",
      desc: "对每道题生成 1 次代码，在沙盒中执行全部单元测试，全部通过则计为正确（pass@1）。",
      example: "164 题中 138 道全部测试通过 → pass@1 = 84.1%",
    },
    aisBench: { suite: "humaneval_gen_0_shot", evalType: "代码生成（pass@1）", shot: "0-shot", note: "HumanEval 经典 164 题，测试 Python 基础编程能力" },
  },

  "livecodebench_0_shot_chat_v6": {
    format: {
      type: "JSONL",
      desc: "来自 LeetCode/Codeforces/AtCoder 的最新竞赛编程题，避免训练集泄漏。",
      fields: { question_id: "题目 ID", question_title: "题目名", question_content: "题目正文（含样例）", difficulty: "难度等级", platform: "来源平台" },
    },
    demo: {
      input: {
        question_title: "Count Pairs With XOR in Range",
        question_content: "Given an integer array nums and two integers low and high, return the number of nice pairs...",
        difficulty: "medium",
        platform: "leetcode",
      },
      output: "（模型生成能通过所有测试用例的代码）",
    },
    accuracy: {
      formula: "pass@1 = 通过测试的样本数 / 总样本数 × 100%",
      desc: "在在线判题系统或本地沙盒执行，所有隐藏测试点通过则为正确。LiveCodeBench v6 包含 2024 年以后的题目。",
      example: "100 道题通过 47 道 → pass@1 = 47.0%",
    },
    aisBench: { suite: "livecodebench_0_shot_chat_v6", evalType: "竞赛代码生成（pass@1）", shot: "0-shot", note: "动态更新，持续收录最新竞赛题目，防止数据污染" },
  },

  // ── 垂类通用 ─────────────────────────────────────────────────────────

  "tele_exam_gen_0_shot": {
    format: {
      type: "JSONL",
      desc: "通信工程师中级考试选择题，覆盖通信原理、网络技术等核心知识点。",
      fields: { input: "题干 + 四选项", target: "答案字母 A/B/C/D" },
    },
    demo: {
      input: {
        input: "GSM 系统中，一个基站的频率复用因子通常为多少？\nA. 3\nB. 4\nC. 7\nD. 12",
        target: "C",
      },
      output: "C",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "提取模型选择的字母，与 target 完全匹配计为正确。",
      example: "共 200 题，答对 162 题 → Accuracy = 81.0%",
    },
    aisBench: { suite: "tele_exam_gen_0_shot", evalType: "多项选择（0-shot）", shot: "0-shot", note: "通信工程师中级资格考试真题，选择题部分" },
  },

  "tele_exam_gen_0_shot_str": {
    format: {
      type: "JSONL",
      desc: "通信工程师中级考试主观题，模型需生成简答或填空内容。",
      fields: { input: "题干（简答/填空/论述）", target: "参考答案文本" },
    },
    demo: {
      input: {
        input: "简述 5G NR 相比 LTE 在信道编码方面的改进，至少列举两点。",
        target: "5G NR 采用 LDPC 替代 Turbo 码用于数据信道，采用 Polar 码用于控制信道；同时支持更大的码块长度，提升了吞吐量和低时延性能。",
      },
      output: "（模型生成的回答经 LLM Judge 评分）",
    },
    accuracy: {
      formula: "Score = Σ judge_score_i / N_total × 100%",
      desc: "由评判模型（LLM Judge）对模型回答进行 0-1 评分，判断语义是否与参考答案一致。",
      example: "共 50 题，Judge 给出总分 39.5 → Score = 79.0%",
    },
    aisBench: { suite: "tele_exam_gen_0_shot_str", evalType: "主观题（LLM Judge）", shot: "0-shot", note: "通信工程师中级考试主观题部分，需配置 LLM Judge" },
  },

  "telemath_gen_0_cot_shot": {
    format: {
      type: "JSONL",
      desc: "通信领域数学计算题，涵盖香农定理、信噪比、调制解调等计算。",
      fields: { problem: "题目描述", answer: "数值答案（含单位）" },
    },
    demo: {
      input: {
        problem: "一信道带宽为 4 kHz，信噪比为 30 dB，根据香农定理计算信道最大容量（bps）。",
        answer: "约 39.86 kbps",
      },
      output: "约 39.86 kbps",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "对数值答案进行等价判断，允许合理的单位换算和精度误差（±1%）。",
      example: "共 100 道题，答对 73 道 → Accuracy = 73.0%",
    },
    aisBench: { suite: "telemath_gen_0_cot_shot", evalType: "数学推理（0-shot CoT）", shot: "0-shot", note: "通信领域专项数学计算，考察模型的行业知识与数学能力" },
  },

  "teleqna_gen_0_shot": {
    format: {
      type: "JSONL",
      desc: "TeleQnA 通信问答，模型从文档中检索或利用知识回答专业问题，支持多选。",
      fields: { input: "问题 + 选项", target: "答案字母（单选或多选）" },
    },
    demo: {
      input: {
        input: "Which frequency bands are primarily used for 5G NR Sub-6GHz deployments?\nA. 700 MHz\nB. 2.6 GHz\nC. 3.5 GHz\nD. 26 GHz",
        target: "ABC",
      },
      output: "ABC",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "多选题要求选项集合完全匹配（严格模式），单选题字母完全匹配。",
      example: "共 500 道题，全匹配 330 道 → Accuracy = 66.0%",
    },
    aisBench: { suite: "teleqna_gen_0_shot", evalType: "知识问答（单/多选）", shot: "0-shot", note: "TeleQnA 数据集，覆盖 5G、光网络、无线接入等领域" },
  },

  "tspec_gen_0_shot": {
    format: {
      type: "JSONL",
      desc: "基于 3GPP/IETF 技术规范的问答，考察模型对标准文档的理解。",
      fields: { input: "基于规范的问题 + 选项", target: "答案字母" },
    },
    demo: {
      input: {
        input: "According to 3GPP TS 38.211, what is the subcarrier spacing for NR FR1 numerology μ=1?\nA. 15 kHz\nB. 30 kHz\nC. 60 kHz\nD. 120 kHz",
        target: "B",
      },
      output: "B",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "字母完全匹配，答案来自官方技术规范，随机基线 25%。",
      example: "共 300 道题，答对 201 道 → Accuracy = 67.0%",
    },
    aisBench: { suite: "tspec_gen_0_shot", evalType: "规范理解（0-shot）", shot: "0-shot", note: "TSpec-LLM，基于 3GPP/IETF 规范文本构建" },
  },

  "teledata_gen_0_shot": {
    format: {
      type: "JSONL",
      desc: "Tele-Data，通信网络数据分析题，需对表格、日志、指标等进行理解与推断。",
      fields: { input: "含数据表格或日志的题干 + 选项", target: "答案字母" },
    },
    demo: {
      input: {
        input: "以下是某基站 1 小时内的 PRB 利用率数据：[85%, 92%, 78%, 95%, 88%]。该时段平均利用率约为多少？\nA. 85.6%\nB. 87.6%\nC. 89.0%\nD. 91.0%",
        target: "B",
      },
      output: "B",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "字母完全匹配，部分题目需要数值计算，精度要求严格。",
      example: "共 200 道题，答对 142 道 → Accuracy = 71.0%",
    },
    aisBench: { suite: "teledata_gen_0_shot", evalType: "数据分析（0-shot）", shot: "0-shot", note: "Tele-Data，通信网络数据理解与分析能力评测" },
  },

  "telequad_gen_0_shot": {
    format: {
      type: "JSONL",
      desc: "TeleQuAD 阅读理解，给定通信领域文档段落，模型从原文中抽取答案。",
      fields: { context: "文档段落", question: "问题", answers: "标准答案对象（text + start 位置）" },
    },
    demo: {
      input: {
        context: "OFDM 技术将频带分割为若干正交子载波，每个子载波独立调制，有效抵抗多径衰落，已被 LTE 和 5G NR 系统广泛采用。",
        question: "OFDM 被哪些移动通信系统采用？",
      },
      output: "LTE 和 5G NR 系统",
    },
    accuracy: {
      formula: "Exact Match + F1 Score",
      desc: "EM（精确匹配）要求输出字符串与任一参考答案完全一致；F1 在词级别计算精准率和召回率均值，二者均报告。",
      example: "1000 条：EM = 58.2%，F1 = 73.5%（以 F1 为主要指标）",
    },
    aisBench: { suite: "telequad_gen_0_shot", evalType: "抽取式阅读理解（EM + F1）", shot: "0-shot", note: "TeleQuAD，通信领域中文 SQuAD 风格数据集" },
  },

  "opseval_gen_0_shot": {
    format: {
      type: "JSONL",
      desc: "OpsEval 运维智能评测，包含告警研判、故障根因分析、运维操作等多类场景。",
      fields: { input: "运维场景描述 + 选项", target: "答案字母" },
    },
    demo: {
      input: {
        input: "某核心路由器 CPU 利用率持续超过 95%，同时伴有大量 BGP session flap。最可能的根因是？\nA. 硬件故障\nB. 路由表震荡导致 CPU 高负载\nC. 链路带宽不足\nD. 配置错误",
        target: "B",
      },
      output: "B",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "字母完全匹配，OpsEval 涵盖网络、系统、数据库等多类运维场景。",
      example: "共 400 道题，答对 276 道 → Accuracy = 69.0%",
    },
    aisBench: { suite: "opseval_gen_0_shot", evalType: "运维问答（0-shot）", shot: "0-shot", note: "OpsEval，IT 运维智能化能力评测基准" },
  },

  // ── 垂类自定义任务 ───────────────────────────────────────────────────

  "task_1_suite": {
    format: {
      type: "JSONL",
      desc: "家庭支撑智能体数据自服务场景，每条数据为一段用户对话，模型需同时识别意图并提取工具调用所需槽位信息。",
      fields: {
        question: "用户原始输入（自然语言）",
        answer: "JSON 字符串，包含 intent（意图标签）和 slots（槽位键值对）",
      },
    },
    demo: {
      input: {
        question: "帮我查一下上个月的宽带费账单，手机号是13812345678。",
        answer: '{"intent": "账单查询", "slots": {"service_type": "宽带费", "time_range": "上个月", "phone": "13812345678"}}',
      },
      output: '{"intent": "账单查询", "slots": {"service_type": "宽带费", "time_range": "上个月", "phone": "13812345678"}}',
    },
    accuracy: {
      formula: "Accuracy = N_exact_match / N_total × 100%；补充 Slot F1",
      desc: "对 intent 字段做精确匹配，对 slots 字段做 F1（预测槽位与标准槽位的 Key-Value 精准率/召回率均值）。最终报告整体 Accuracy 和 Slot F1 两个指标。",
      example: "100 条：意图准确率 88%，Slot F1 = 82.3%",
    },
    aisBench: { suite: "task_1_suite", evalType: "意图识别 + 槽位抽取", shot: "0-shot", note: "自定义任务，数据文件路径 data/custom_task/task_1.jsonl" },
  },

  "task_34_suite": {
    format: {
      type: "JSONL",
      desc: "政企支撑智能体意图网关场景，对用户输入做多分类意图识别，输出对应意图标签。",
      fields: {
        question: "用户原始输入",
        answer: "意图标签字符串，如'套餐查询'、'故障报障'等",
      },
    },
    demo: {
      input: {
        question: "我们公司的专线最近时延很高，能帮我排查一下吗？",
        answer: "故障报障",
      },
      output: "故障报障",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "提取模型输出的意图标签文本，与 answer 完全匹配计为正确（精确字符串匹配）。",
      example: "共 500 条，精确匹配 410 条 → Accuracy = 82.0%",
    },
    aisBench: { suite: "task_34_suite", evalType: "多分类意图识别", shot: "0-shot", note: "自定义任务，政企场景意图类别约 20+，数据文件 task_34.jsonl" },
  },

  "task_36_suite": {
    format: {
      type: "JSONL",
      desc: "安全管理智能体场景，对网络安全告警事件进行研判，输出威胁等级和攻击类型标签。",
      fields: {
        question: "告警描述（含源/目的 IP、端口、频率、协议等信息）",
        answer: "研判结论，格式：'等级-攻击类型'，如'高危-SSH暴力破解'",
      },
    },
    demo: {
      input: {
        question: "源IP 192.168.10.5 在 60 秒内向目标 10.0.0.22:22 发起 2347 次连接请求，成功认证 0 次。",
        answer: "高危-SSH暴力破解攻击",
      },
      output: "高危-SSH暴力破解攻击",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "精确字符串匹配，等级和攻击类型均须正确才计分。",
      example: "共 300 条，全部匹配 234 条 → Accuracy = 78.0%",
    },
    aisBench: { suite: "task_36_suite", evalType: "多标签分类（威胁研判）", shot: "0-shot", note: "自定义任务，安全告警场景，数据文件 task_36.jsonl" },
  },

  "task_43_suite": {
    format: {
      type: "JSONL",
      desc: "核心网运维场景，对基础语音业务的用户投诉工单进行分类，输出投诉类型标签。",
      fields: {
        question: "投诉工单内容（含用户描述的故障现象）",
        answer: "投诉类型标签，如'无法主叫'、'通话质量差'、'单通'等",
      },
    },
    demo: {
      input: {
        question: "用户反映手机打出去的电话对方听不到声音，但自己能听到对方说话，已经持续两天。",
        answer: "单通",
      },
      output: "单通",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%",
      desc: "精确字符串匹配，类别数量约 10-15 类，随机基线约 7-10%。",
      example: "共 400 条，匹配 312 条 → Accuracy = 78.0%",
    },
    aisBench: { suite: "task_43_suite", evalType: "多分类（投诉工单分类）", shot: "0-shot", note: "自定义任务，核心网语音投诉场景，数据文件 task_43.jsonl" },
  },

  "task_44_suite": {
    format: {
      type: "JSONL",
      desc: "核心网运维场景，从投诉工单文本中提取关键参数（时间、号码、地点、故障类型等），输出结构化 JSON。",
      fields: {
        question: "投诉工单原文",
        answer: "JSON 字符串，包含时间、手机号、位置、故障描述等关键字段",
      },
    },
    demo: {
      input: {
        question: "用户13956781234反映2024年4月5日上午9时起，在上海徐汇区漕宝路附近手机无法打出电话，持续至今。",
        answer: '{"phone": "13956781234", "time": "2024-04-05 09:00", "location": "上海徐汇区漕宝路", "issue": "无法主叫"}',
      },
      output: '{"phone": "13956781234", "time": "2024-04-05 09:00", "location": "上海徐汇区漕宝路", "issue": "无法主叫"}',
    },
    accuracy: {
      formula: "Slot F1 = 2 × Precision × Recall / (Precision + Recall)",
      desc: "对输出 JSON 的每个键值对与标准答案做 F1 计算，精准率 = 正确预测字段 / 预测字段总数，召回率 = 正确预测字段 / 标准答案字段总数。",
      example: "100 条：Precision = 84%，Recall = 79% → Slot F1 = 81.4%",
    },
    aisBench: { suite: "task_44_suite", evalType: "关键信息抽取（Slot F1）", shot: "0-shot", note: "自定义任务，核心网语音投诉参数提取，数据文件 task_44.jsonl" },
  },

  "task_60_suite": {
    format: {
      type: "JSONL",
      desc: "投诉调度智能体场景，对用户投诉内容进行二分类：判断是否属于省内网络投诉。",
      fields: {
        question: "用户投诉内容描述",
        answer: "'是' 或 '否'",
      },
    },
    demo: {
      input: {
        question: "用户在广州天河区使用手机发现 4G 信号很弱，无法正常刷视频，已向营业厅反映。",
        answer: "是",
      },
      output: "是",
    },
    accuracy: {
      formula: "Accuracy = N_correct / N_total × 100%；补充 F1（正类）",
      desc: "二分类精确匹配（'是'或'否'），同时报告正类（省内网络投诉）的 Precision、Recall、F1，以 F1 为主要参考指标。",
      example: "共 600 条：Accuracy = 85.5%，正类 F1 = 83.2%",
    },
    aisBench: { suite: "task_60_suite", evalType: "二分类（是/否）", shot: "0-shot", note: "自定义任务，投诉调度省内判断，数据文件 task_60.jsonl" },
  },
};
