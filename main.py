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

def split_text_with_newlines(text):
    # 以换行符分割文本
    paragraphs = re.split(r'(\r\n|\r|\n)', text)
    return paragraphs

def translate_text_by_paragraph(text, index):
    segments = split_text_with_newlines(text)
    # 初始化变量来存储翻译后的文本和当前处理的换行符
    translated_segments = []
    for segment in segments:
        # 检查当前段落是否是换行符
        if segment in ['\r\n', '\r', '\n']:
            # 直接添加换行符到结果中，不进行翻译
            translated_segments.append(segment)
        else:
            # 如果段落不是换行符，则进行翻译
            if segment:  # 避免翻译空段落
                translated_segments.append(translate_text(segment, index))
            else:
                translated_segments.append(segment)
    # 将翻译后的段落和换行符重新组合成完整的文本
    translated_text = ''.join(translated_segments)
    return translated_text

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
            "frequency_penalty": 0.05,
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
                    "content": f"将下面的日文文本翻译成中文：{modified_text}"
                }
            ],
            "temperature": 0.1,
            "top_p": 0.3,
            "max_tokens":1000,
            "frequency_penalty":0.05,
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
    if api_type == 0 :
        translated_text = response.json()["content"]
    else :
        translated_text = response.json()["choices"][0]["message"]["content"]

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

def save_progress(last_processed,last_task):
    # 保存当前的进度到配置文件
    with open('config.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    data['last_processed'] = last_processed
    data['task_list'] = last_task
    with open('config.json', 'w') as file:
        json.dump(data, file, indent=4)

    # json.dump({'last_processed': last_processed}, file)

def Jp_hash(text):
    text = re.sub(r'[.。,，、！!？?♡「」\s]', '', text)
    return hash(text)

def init():  
    # 检查配置文件是否存在
    if not os.path.exists("config.json"):
        config_data = {
            "last_processed": 0,
            "task_list": [],
            "endpoint": "",
            "api_type": 0,
            "save_frequency": 100,
            "shutdown": 0
        }
        with open("config.json", 'w') as file:
            json.dump(config_data, file, indent=4)
    # 读取配置文件
    global api_type, endpoint, save_frequency, shutdown, task_list, start_index
    with open('config.json', 'r', encoding='utf-8') as file:
        data=json.load(file)
    endpoint = data['endpoint']
    api_type = data['api_type']
    save_frequency = data['save_frequency']
    shutdown = data['shutdown']
    task_list = data['task_list']
    start_index = data['last_processed']
    # 读取api信息
    if endpoint == '':
        veri = input("请输入数字来选择部署类型(默认为本地部署):\n[0] 本地部署Sakura v0.9\n[1] kaggle部署Sakura v0.9\n")
        if veri == "" :
            api_type = 0
        else:
            api_type = int(veri)
        data['api_type'] = api_type

        if api_type == 0 :
            verurl = input("请输入Api地址(默认为http://127.0.0.1:8080/completion):\n")
            if verurl == "" :
                endpoint = "http://127.0.0.1:8080/completion"
            else:
                endpoint = verurl
            data['endpoint'] = endpoint
        else :
            verurl = input("请输入Api地址(例如https://114-514-191-810.ngrok-free.app):\n")
            if verurl == "" :
                print("必须提供Api地址！")
                sys.exit()
            else :
                endpoint = verurl+"/v1/chat/completions"
                data['endpoint'] = endpoint
        print("配置已保存到config.json,下次启动将默认加载")
    # 读取任务列表,保存频率,自动关机信息
    if task_list == []:
        print("请输入需要翻译的文件名，如有多个请换行输入(默认为ManualTransFile.json):")
        while True:
            veri = input()
            if veri == "" :
                if task_list == []:
                    if os.path.exists("ManualTransFile.json") == 0:
                        print("文件ManualTransFile.json不存在")
                        sys.exit()
                    task_list = ["ManualTransFile.json"]
                break
            file_name = veri.split("\n")[0]
            if os.path.exists(str(file_name)) == 0:
                print(f"文件{file_name}不存在，请重新输入")
            else:
                task_list.append(file_name)
        data['task_list'] = task_list
        # 保存频率
        veri = input("请输入保存频率(默认为100行):\n")
        if veri == "" :
            save_frequency = 100
        else:
            save_frequency = int(veri)
        data['save_frequency'] = save_frequency
        # 自动关机
        veri = input("是否翻译完成后自动关机？(默认为0)\n[0] 不关机\n[1] 关机\n")
        if veri == "" :
            shutdown = 0
        else:
            shutdown = int(veri)
        data['shutdown'] = shutdown
    else:
        print(f"已加载任务列表{task_list},保存频率为{save_frequency},自动关机状态为{shutdown}")
    # 保存配置
    with open('config.json', 'w') as file:
        json.dump(data, file, indent=4)

def shutdown_pc():
    if(os.name=='nt'):
        os.system('shutdown -s -t 60')
    else:
        os.system('shutdown -h 1')

def main():
    init()              
    while task_list != []:
        # 读取JSON文件
        task_name = task_list[0]
        print(f"开始翻译{task_name},正在读取文件...")
        with open(task_name, 'r', encoding='utf-8') as file:
            data = json.load(file)
        print("读取完成.")

        keys = list(data.keys())
        hash_list = {}
        
        # 将之前已经翻译过的文本的哈希值存入列表
        for i in range(start_index):
            hash_list[Jp_hash(data[keys[i]])] = i
        print('开始翻译...')

        # 使用tqdm创建进度条
        for i in tqdm(range(start_index, len(keys)), desc="任务进度"):
            print(f'翻译文件:{task_name} 索引:第{i+2}行')
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
                    # translated_text = translate_text(updated_text, i)#直接翻译

                    translated_text = translate_text_by_paragraph(updated_text, i)#分割换行符

                    hash_list[text_hash] = i
                print(f"原文: {updated_text} => 翻译: {translated_text}\n\n")
                data[key] = translated_text
            else:
                print(f"跳过（不含日文）: {original_text}")

            if (i + 1) % save_frequency == 0:
                print(f"达到{save_frequency}行，保存进度和文件...")
                save_progress(i + 1,task_list)
                with open(task_name, 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                print("保存完成.")
        task_list.pop(0)
        save_progress(0,task_list)
        with open(task_name, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        print(f"文件{task_name}翻译完成.")
        
    # 翻译完成后进度重置
    save_progress(0,[])
    print("All done.")
    if shutdown == 1:
        print("翻译完成，将在一分钟后关机...")
        shutdown_pc()

if __name__ == "__main__":
    main()
