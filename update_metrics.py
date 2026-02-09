import pandas as pd
import json
import sys

def is_json(text):
    if not isinstance(text, str):
        return False
    text = text.strip()
    if not (text.startswith('{') or text.startswith('[')):
        return False
    try:
        json.loads(text)
        return True
    except:
        return False

def determine_metric_and_reason(row):
    # Adjust column indices if needed, using named columns is safer
    input_text = row['输入样例']
    output_text = row["""输出样例
（如 果返回是json请以json格式填写）"""]
    capability = row['能力维度（大类）']
    nature = row['能力维度（小类）']

    if pd.isna(output_text):
        return "数据缺失", "输出样例为空，无法确定指标。"

    output_str = str(output_text).strip()

    # Rule 1: JSON Output -> Json Match
    if is_json(output_str):
        return "Json Match", "输出为结构化JSON数据，适合使用Json Match进行字段级比对。"

    # Rule 2: SQL -> Execution Accuracy
    if nature == '数据自服务' or (isinstance(output_str, str) and output_str.upper().startswith('SELECT')):
        return "Execution Accuracy", "SQL生成任务，建议通过执行结果的一致性来评估。"

    # Rule 3: Classification -> Accuracy
    if nature == '分类':
        return "Accuracy", "分类任务，输出为类别标签，适合使用准确率评估。"

    # Rule 4: Generation / Reading Comprehension -> ROUGE-L
    # Be careful with short answers vs long generation
    if nature == '阅读理解' or capability == '生成类':
        # If output is very short (e.g., date, number), might be Exact Match
        if len(output_str) < 20 and '\n' not in output_str:
             return "Exact Match", "输出为简短文本或数值，适合精确匹配。"
        return "ROUGE-L", "文本生成/阅读理解任务，适合使用ROUGE-L评估文本相似度。"
    
    # Rule 5: Extraction -> Exact Match or F1
    if nature == '关键信息抽取':
        return "Exact Match", "信息抽取任务，需精确匹配提取内容。"

    # Rule 6: Tool Calling (Non-JSON) -> Accuracy
    if nature == '工具调用':
        return "Accuracy", "工具调用任务，适合准确率评估。"

    # Default
    return "ROUGE-L", "默认使用ROUGE-L评估生成质量。"

try:
    file_path = 'mydata/all_task.xlsx'
    df = pd.read_excel(file_path)
    
    # Verify column names
    print("Columns:", df.columns.tolist())
    col_metric = '评估指标'
    
    # Check if 'Reason' column exists, if not, maybe we should create one?
    # User said: "追加到该任务后面两列" (Append to the next two columns). 
    # M is Metric. N is Source. 
    # If we overwrite Source, we might lose data. 
    # But for these rows, Source might be empty.
    # Let's check if we should add a new column '评估理由'.
    
    if '评估理由' not in df.columns:
        # Insert '评估理由' after '评估指标'
        loc_index = df.columns.get_loc(col_metric) + 1
        df.insert(loc_index, '评估理由', '')
        col_reason = '评估理由'
    else:
        col_reason = '评估理由'

    count = 0
    for index, row in df.iterrows():
        # Check if Metric is empty
        if pd.isna(row[col_metric]) or str(row[col_metric]).strip() == '':
            # Access by index: Input=5, Output=6, Capability=8, Nature=9
            # Using iloc is better for safety if names change
            # But we are in a loop with iterrows, so row is a Series with index as col names.
            # We can use df.iloc[index, 6] but that is row-based access.
            # Let's use column indices from columns list
            input_text = row.iloc[5]
            output_text = row.iloc[6]
            capability = row.iloc[8]
            nature = row.iloc[9]
            
            metric, reason = determine_metric_and_reason_values(input_text, output_text, capability, nature)
            
            df.at[index, col_metric] = metric
            df.at[index, col_reason] = reason
            count += 1
            print(f"Row {index+2}: {metric} | {reason}")

    print(f"Updated {count} rows.")
    
    # Save back
    df.to_excel(file_path, index=False)
    print("File saved successfully.")

except Exception as e:
    print(f"Error: {e}")
