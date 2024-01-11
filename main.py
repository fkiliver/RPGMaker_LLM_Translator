import json
import requests
import re
import os
from tqdm import tqdm
import unicodedata

def contains_japanese(text):
    # 将文本中的半角假名转换为全角假名
    text = unicodedata.normalize('NFKC', text)
    # 检查文本是否包含日文字符
    return bool(re.search(r'[\u3040-\u30ff\u3400-\u4DBF\u4E00-\u9FFF]', text)), text

def is_repetitive(text):
    # 检查文本是否循环
    return re.search(r'(.+?)(?:\1){15,}', text) is not None

def log_repetitive(index):
    print("存在重复异常，记录至log.txt...")
    # 记录异常的行号到log.txt
    with open('log.txt', 'a', encoding='utf-8') as file:
        file.write(f"重复异常行号：{index+1}\n")

def translate_text(text, index):
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
    try:
        response = requests.post("http://127.0.0.1:8080/completion", json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f'请求翻译API错误: {e}')
        return text
    # 获取响应的内容
    translated_text = response.json()['content']

    # 检查翻译后的文本是否有重复异常
    if is_repetitive(translated_text):
        log_repetitive(index)
        # 对原文加上一个空格后重新翻译
        return translate_text(" " + text, index)

    return translated_text

def load_config():
    print("尝试读取配置文件来获取上次的进度...")
    try:
        with open('config.json', 'r', encoding='utf-8') as file:
            return json.load(file).get('last_processed', 0)
    except FileNotFoundError:
        return 0

def save_config(last_processed):
    # 保存当前的进度到配置文件
    with open('config.json', 'w', encoding='utf-8') as file:
        json.dump({'last_processed': last_processed}, file)

def delete_config():
    print("删除配置文件")
    if os.path.exists('config.json'):
        os.remove('config.json')

def main():
    print("读取JSON文件...")
    with open('ManualTransFile.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    print("读取完成.")

    start_index = load_config()
    keys = list(data.keys())

    print('开始翻译...')
    # 使用tqdm创建进度条
    for i in tqdm(range(start_index, len(keys)), desc="翻译进度"):
        key = keys[i]
        original_text = data[key]
        contains_jp, updated_text = contains_japanese(original_text)
        if contains_jp:
            translated_text = translate_text(updated_text, i)
            print(f"原文: {updated_text} => 翻译: {translated_text}")
            data[key] = translated_text
        else:
            print(f"跳过（不含日文）: {original_text}")

        if (i + 1) % 100 == 0 or i + 1 == len(keys):
            print("达到100行，保存进度和文件...")
            save_config(i + 1)
            with open('ManualTransFile.json', 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            print("保存完成.")

    # 翻译完成后删除配置文件
    delete_config()
    print("All done.")

if __name__ == "__main__":
    main()
