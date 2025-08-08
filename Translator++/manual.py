from concurrent.futures import ThreadPoolExecutor
from llm import LLM, translate
from itertools import repeat
from tqdm import tqdm
import json

llm = LLM("sakura", "sakura-14b-qwen2.5-v1.0-q6k.gguf", 4, ["0", "1", "2", "3"])
# 全局字典，只会将相关项传入模型
global_dicts = ()

with open("ManualTransFile.json", "r", encoding="utf-8") as fp:
    data = json.load(fp)
    raw_texts = list(data.keys())

with ThreadPoolExecutor(4) as executor:
    iterator = executor.map(translate, repeat(llm), list(data.keys()), repeat(()), repeat(()), repeat(global_dicts))
    results = list(tqdm(iterator, total=len(raw_texts)))

with open("TranslatedFile.json", "w", encoding="utf-8") as fp:
    json.dump(dict(zip(raw_texts, results)), fp, ensure_ascii=False, indent=4)
