import json
import requests
import re
import os
import random
import string
from tqdm import tqdm
import unicodedata

def contains_japanese(text):
    # 将文本中的半角假名转换为全角假名
    text = unicodedata.normalize('NFKC', text)
    # 检查文本是否包含日文字符
    return bool(re.search(r'[\u3040-\u30ff\u3400-\u4DBF\u4E00-\u9FFF]', text)), text

def is_repetitive(text):
    # 检查文本是否包含重复的字或句子
    return re.search(r'((.|\n)+?)(?:\1){15,}', text) is not None

def log_repetitive(index):
    # 记录异常的行号到log.txt
    with open('log.txt', 'a', encoding='utf-8') as file:
        file.write(f"重复异常行号：{index}\n")

def generate_random_string(length=15):
    # 生成一个随机的五位英文字符字符串
    return ''.join(random.choices(string.ascii_letters, k=length))

def translate_text(text, index, attempt=1):
    if attempt > 3:
        # 如果重试次数超过3次，跳过这一行
        log_repetitive(index)
        return text

    # 构造POST请求的数据
    random_string = generate_random_string()
    modified_text = random_string + text
    print(modified_text)
    if ver == 1 :
        data = {
            "frequency_penalty": 0,
            "n_predict": 1000,
            "prompt": f"<|im_start|>system\n你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。<|im_end|>\n<|im_start|>user\n将下面的日文文本翻译成中文：{modified_text}<|im_end|>\n<|im_start|>assistant\n",
            "repeat_penalty": 1,
            "temperature": 0.1,
            "top_k": 40,
            "top_p": 0.3
        }
    else:
        data = {
            "frequency_penalty": 0,
            "n_predict": 1000,
            "prompt": f"<reserved_106>将下面的日文文本翻译成中文：{modified_text}<reserved_107>",
            "repeat_penalty": 1,
            "temperature": 0.1,
            "top_k": 40,
            "top_p": 0.3
        }
    # 发送POST请求
    response = requests.post("http://127.0.0.1:8080/completion", json=data)
    # 获取响应的内容
    translated_text = response.json()['content']

    # 检查翻译后的文本是否有重复异常
    if is_repetitive(translated_text):
        return translate_text(text, index, attempt + 1)

    # 如果翻译结果没有重复，从结果中去除随机字符
    return translated_text.replace(random_string, "")

def load_config():
    # 尝试读取配置文件来获取上次的进度
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
    # 删除配置文件
    if os.path.exists('config.json'):
        os.remove('config.json')

def main():
    global ver 
    veri = input("模型版本选择：*[0] v0.8    [1] v0.9\n")
    if veri == "" :
        ver = 0
    else:
        ver = int(veri)
    # 读取JSON文件
    with open('ManualTransFile.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    start_index = load_config()
    keys = list(data.keys())

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

        # 每翻译100行就保存进度和文件
        if (i + 1) % 100 == 0 or i + 1 == len(keys):
            save_config(i + 1)
            with open('ManualTransFile.json', 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)

    # 翻译完成后删除配置文件
    delete_config()

if __name__ == "__main__":
    main()
