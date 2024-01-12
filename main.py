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


def find_repetitive(text):
    # 查找文本中的重复部分
    match = re.search(r'((.|\n)+?)(?:\1){10,}', text)
    return match.group(1) if match else None
    # todo以特殊字符为分割，分段提交

def log_repetitive(index):
    print("存在重复异常，记录至log.txt...")
    # 记录异常的行号到log.txt
    with open('log.txt', 'a', encoding='utf-8') as file:
        file.write(f"重复异常行号：{index}\n")

def generate_random_string(length=2):
    # 生成一个随机的五位英文字符字符串
    return ''.join(random.choices(string.ascii_letters, k=length))

def translate_text(text, index, repetitive_part=None, attempt=1):
    if attempt > 3:
        # 如果重试次数超过3次，跳过这一行
        log_repetitive(index)
        return text

    # 检查文本中是否有重复部分，并在翻译前去除
    if repetitive_part is None:
        repetitive_part = find_repetitive(text)
        print(f"重复部分：{repetitive_part}")
        if repetitive_part:
            text = text.replace(repetitive_part, '', 1)  # 只替换第一个匹配项

    

    # 重试时加上随机字符
    if attempt > 1:
        random_string = generate_random_string()
        print(f"添加随机字符串重试：{random_string}")
        modified_text = random_string + text
    else:
        modified_text = text

    print(f"提交的文本为：{modified_text}")
    
    # 构造POST请求的数据
    if ver == 1 :
        data = {
            "frequency_penalty": 0.2,
            "n_predict": 1000,
            "prompt": f"<|im_start|>system\n你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。<|im_end|>\n<|im_start|>user\n将下面的日文文本翻译成中文：{modified_text}<|im_end|>\n<|im_start|>assistant\n",
            "repeat_penalty": 1,
            "temperature": 0.1,
            "top_k": 40,
            "top_p": 0.3
        }
    else:
        data = {
            "frequency_penalty": 0.2,
            "n_predict": 1000,
            "prompt": f"<reserved_106>将下面的日文文本翻译成中文：{modified_text}<reserved_107>",
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

    if is_repetitive(translated_text):
        return translate_text(text, index, repetitive_part, attempt + 1)

    # 去除翻译结果中不希望出现的特定字符串
    unwanted_string = "将下面的日文文本翻译成中文："
    translated_text = translated_text.replace(unwanted_string, "")

    # 检查翻译结果是否为全英文
    if translated_text.isascii():
        return translate_text(text, index, repetitive_part, attempt + 1)

    # 去除随机字符
    if attempt > 1:
        translated_text = translated_text.replace(random_string, "")

    # 将原本的重复部分加回翻译文本
    if repetitive_part:
        translated_text += repetitive_part

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
    #选择模型版本
    global ver 
    veri = input("模型版本选择：*[0] v0.8    [1] v0.9\n")
    if veri == "" :
        ver = 0
    else:
        ver = int(veri)
    # 读取JSON文件
    print("读取JSON文件...")
    with open('ManualTransFile.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    print("读取完成.")

    start_index = load_config()
    keys = list(data.keys())

    print('开始翻译...')
    # 使用tqdm创建进度条
    for i in tqdm(range(start_index, len(keys)), desc="任务进度"):
        print(f'索引:第{i}行')
        key = keys[i]
        original_text = data[key]
        contains_jp, updated_text = contains_japanese(original_text)
        if contains_jp:
            repetitive_part = find_repetitive(updated_text)
            translated_text = translate_text(updated_text, i, repetitive_part)
            print(f"原文: {updated_text} => 翻译: {translated_text}\n\n")
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
