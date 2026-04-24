import json

with open('/Users/jia/MyProjects/pythonProjects/cmcc_cxy/Bprocss/benchmark/data/custom_task/task1_alpaca_test.json','r',encoding='utf-8') as f:
    data=json.load(f)

with open('/Users/jia/MyProjects/pythonProjects/cmcc_cxy/Bprocss/benchmark/data/custom_task/task1_alpaca_test.jsonl','w',encoding='utf-8') as f:
    for item in data:
        f.write(json.dumps(item,ensure_ascii=False)+'\n')

print('Done')
