#ais_bench --models maas --datasets gsm8k_gen_0_shot_noncot_chat_prompt --debug

# ais_bench \
#     --models maas \
#     --custom-dataset-path /path/to/your_data.jsonl \
#     --custom-dataset-data-type qa \
#     --mode all

ais_bench --models maas --datasets task_1_suite
# ais_bench --models maas --datasets custom_eval_suite --debug