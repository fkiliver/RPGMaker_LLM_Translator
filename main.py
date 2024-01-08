import json
import requests
import re
from tqdm import tqdm

def contains_japanese(text):
    # 检查文本是否包含日文字符
    return bool(re.search(r'[\u3040-\u30ff\u3400-\u4DBF\u4E00-\u9FFF]', text))

def translate_text(text):
    # 构造POST请求的数据
    data = {
        "frequency_penalty": 0,
        "n_predict": 1000,
        "prompt": f"<reserved_106>将下面的日文文本翻译成中文：{text}<reserved_107>",
        "repeat_penalty": 1,
        "temperature": 0.1,
        "top_k": 40,
        "top_p": 0.3
    }
    # 发送POST请求
    response = requests.post("http://127.0.0.1:8080/completion", json=data)
    # 获取响应的内容
    return response.json()['content']

def main():
    # 读取JSON文件
    with open('ManualTransFile.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    # 使用tqdm创建进度条
    for key in tqdm(data.keys(), desc="翻译进度"):
        original_text = data[key]
        if contains_japanese(original_text):
            translated_text = translate_text(original_text)
            print(f"原文: {original_text} => 翻译: {translated_text}")
            data[key] = translated_text
        else:
            print(f"跳过（不含日文）: {original_text}")

    # 将翻译后的数据写回文件
    with open('ManualTransFile.json', 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
