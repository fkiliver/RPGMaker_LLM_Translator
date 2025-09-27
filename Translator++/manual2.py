# 一个手动运行的脚本，用于将 AutoTranslator 导出的文件进行批量翻译
# 会自动遍历并翻译 TransFile 文件夹下的所有文件

from concurrent.futures import ThreadPoolExecutor
from llm import LLM, translate
from itertools import repeat
from tqdm import tqdm
import json
import os

folder = "../TransFile"
llm = LLM("sakura", "sakura-14b-qwen2.5-v1.0-q6k.gguf", 4, ["0", "1", "2", "3"])
# 全局字典，只会将相关项传入模型
global_dicts = ()

for filename in tqdm(os.listdir(folder)):
    filepath = f"{folder}/{filename}"
    with open(filepath, "r", encoding="utf-8") as fp:
        raw_texts = [x.split("=")[0] for x in fp.readlines()]

    with ThreadPoolExecutor(4) as executor:
        iterator = executor.map(translate, repeat(llm), raw_texts, repeat(()), repeat(()), repeat(global_dicts))
        results = list(tqdm(iterator, total=len(raw_texts)))

    with open(filepath, "w", encoding="utf-8") as fp:
        for i in range(len(raw_texts)):
            fp.write(f"{raw_texts[i]}={results[i]}\n")
