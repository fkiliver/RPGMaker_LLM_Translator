import json
import requests
import re
import os
import random
import string
from tqdm import tqdm
import unicodedata
import time
import sys

def contains_japanese(text):
    # 将文本中的半角假名转换为全角假名
    text = unicodedata.normalize('NFKC', text)
    # 检查文本是否包含日文字符
    return bool(re.search(r'[\u3040-\u30ff\u3400-\u4DBF\u4E00-\u9FFF]', text)), text

def contains_chinese(text):
    # 检查文本是否包含中文字符
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def is_repetitive(text):
    # 检查文本是否包含重复的字或句子
    return re.search(r'((.|\n)+?)(?:\1){15,}', text) is not None

def log_repetitive(index):
    print("存在翻译异常，记录至log.txt...")
    # 记录异常的行号到log.txt
    with open('log.txt', 'a', encoding='utf-8') as file:
        file.write(f"异常行号：{index+2}\n")

def generate_random_string(length=2):
    # 生成一个随机的五位英文字符字符串
    return ''.join(random.choices(string.ascii_letters, k=length))

def translate_text(text, index, attempt=1):
    if attempt > 3:
        # 如果重试次数超过3次，跳过这一行
        log_repetitive(index)
        return text

    # 重试时加上随机字符
    if attempt > 1:
        random_string = generate_random_string()
        print(f"添加随机字符串重试：{random_string}")
        modified_text = random_string + text
    else:
        modified_text = text

    print(f"提交的文本为：{modified_text}")
    
    # 构造POST请求的数据
    if api_type == 0 :
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
            "model": "sukinishiro",
            "messages": [{
                    "role": "system",
                    "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"
                },
                {
                    "role": "user",
                    "content": "将下面的日文文本翻译成中文：{modified_text}"
                }
            ],
            "temperature": 0.1,
            "top_p": 0.3,
            "max_tokens":1000,
            "frequency_penalty":0.2,
            "do_sample": "false",
            "top_k": 40,
            "um_beams": 1,
            "repetition_penalty": 1.0
        }

    # 发送POST请求
    try:
        response = requests.post(endpoint, json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f'请求翻译API错误: {e}')
        return text
    # 获取响应的内容
    translated_text = response.json()['content']

    if is_repetitive(translated_text):
        return translate_text(text, index, attempt + 1)

    # 去除翻译结果中不希望出现的特定字符串
    unwanted_string = "将下面的日文文本翻译成中文："
    translated_text = translated_text.replace(unwanted_string, "")

    # 如果结果不含中文
    if not contains_chinese(translated_text):
        print(translated_text)
        print("翻译结果不含中文，重试...")
        return translate_text(text, index, attempt + 1)

    # 去除随机字符
    if attempt > 1:
        translated_text = translated_text.replace(random_string, "")
    
    # 去除高版本llama.cpp结尾的<|im_end|>
    translated_text = translated_text.replace("<|im_end|>", "")

    return translated_text

def load_progress():
    print("尝试读取配置文件来获取上次的进度...")
    try:
        with open('config.json', 'r', encoding='utf-8') as file:
            return json.load(file).get('last_processed', 0)
    except FileNotFoundError:
        return 0

def save_progress(last_processed):
    # 保存当前的进度到配置文件
    with open('config.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    data['last_processed'] = last_processed
    with open('config.json', 'w') as file:
        json.dump(data, file, indent=4)

    # json.dump({'last_processed': last_processed}, file)

def Jp_hash(text):
    text = re.sub(r'[.。,，、！!？?♡「」\s]', '', text)
    return hash(text)

def main():
    #选择模型版本
    if not os.path.exists("config.json"):
        config_data = {
            "last_processed": 0,
            "endpoint": "",
            "api_type": 0
        }
        with open("config.json", 'w') as file:
            json.dump(config_data, file, indent=4)

    global api_type
    global endpoint

    with open('config.json', 'r', encoding='utf-8') as file:
        endpoint = json.load(file).get('endpoint')

    with open('config.json', 'r', encoding='utf-8') as file:
        api_type = json.load(file).get('api_type')

    if endpoint == '':
        
        veri = input("请输入数字来选择部署类型(默认为本地部署):\n[0] 本地部署\n[1] kaggle部署\n")
        if veri == "" :
            api_type = 0
        else:
            api_type = int(veri)

        with open('config.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
        data['api_type'] = api_type
        with open('config.json', 'w') as file:
            json.dump(data, file, indent=4)
            # json.dump({'api_type': api_type}, file)

        if api_type == 0 :
            verurl = input("请输入Api地址(默认为http://127.0.0.1:8080/completion):\n")
            if verurl == "" :
                endpoint = "http://127.0.0.1:8080/completion"
            else:
                endpoint = verurl
            #保存url
            with open('config.json', 'r', encoding='utf-8') as file:
                data = json.load(file)
            data['endpoint'] = endpoint
            with open('config.json', 'w') as file:
                json.dump(data, file, indent=4)
                    # json.dump({'endpoint': endpoint}, file)

        else :
            verurl = input("请输入Api地址(例如https://114-514-191-810.ngrok-free.app):\n")
            if verurl == "" :
                print("必须提供Api地址！")
                sys.exit()
            else :
                endpoint = verurl
                #保存url
                with open('config.json', 'r', encoding='utf-8') as file:
                    data = json.load(file)
                data['endpoint'] = endpoint
                with open('config.json', 'w') as file:
                    json.dump(data, file, indent=4)
                # json.dump({'endpoint': endpoint}, file)

        print("配置已保存到config.json,下次启动将默认加载")

    # 读取JSON文件
    print("读取待翻译的文本...")
    with open('ManualTransFile.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    print("读取完成.")


    #读取进度
    start_index = load_progress()
    keys = list(data.keys())
    hash_list = {}
    
    # 将之前已经翻译过的文本的哈希值存入列表
    for i in range(start_index):
        hash_list[Jp_hash(data[keys[i]])] = i
    print('开始翻译...')

    # 使用tqdm创建进度条
    for i in tqdm(range(start_index, len(keys)), desc="任务进度"):
        print(f'索引:第{i+2}行')
        key = keys[i]
        original_text = data[key]
        contains_jp, updated_text = contains_japanese(original_text)
        if contains_jp:
            # 计算字符串的哈希值，并检查是否重复
            text_hash = Jp_hash(updated_text)
            if text_hash in hash_list:
                print("翻译结果重复，跳过...")
                time.sleep(0.1)
                translated_text = data[keys[hash_list[text_hash]]]
            else:
                translated_text = translate_text(updated_text, i)
                hash_list[text_hash] = i
            print(f"原文: {updated_text} => 翻译: {translated_text}\n\n")
            data[key] = translated_text
        else:
            print(f"跳过（不含日文）: {original_text}")

        if (i + 1) % 100 == 0 or i + 1 == len(keys):
            print("达到100行，保存进度和文件...")
            save_progress(i + 1)
            with open('ManualTransFile.json', 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            print("保存完成.")

    # 翻译完成后进度重置
    save_progress(0)
    print("All done.")

if __name__ == "__main__":
    main()
