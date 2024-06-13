import json
import csv
import pandas as pd
import requests
import re
import os
from tqdm import tqdm
import unicodedata
import sys

def contains_japanese(text):
    # 将文本中的半角假名转换为全角假名
    text = unicodedata.normalize('NFKC', text)
    # 检查文本是否包含日文字符
    return bool(re.search(r'[\u3040-\u30ff\u3400-\u4DBF\u4E00-\u9FFF]', text)), text

def log_repetitive(index):
    print("存在翻译异常，记录至log.txt...")
    # 记录异常的行号到log.txt
    with open('log.txt', 'a', encoding='utf-8') as file:
        file.write(f"异常行号：{index+2}\n")

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
            translated_segments.append(segment)
        #检查当前段落是否为空
        elif segment == '':
            translated_segments.append(segment)
        else:
            #检查当前段落是否为日文
            contains_jp, updated_segment = contains_japanese(segment)
            if contains_jp==0:
                translated_segments.append(updated_segment)
            else:
                # 翻译当前段落
                translated_segment = translate_text(updated_segment, index)
                translated_segments.append(translated_segment)

    # 将翻译后的段落和换行符重新组合成完整的文本
    translated_text = ''.join(translated_segments)
    return translated_text

def translate_text(text, index, attempt=1):
    if attempt > 3:
        # 如果重试次数超过3次，跳过这一行
        log_repetitive(index)
        return text

    print(f"提交的文本为：{text}")
    
    # 构造POST请求的数据
    if api_type == 0 or api_type == 2:
        data = {
            "frequency_penalty": 0.05,
            "n_predict": 1000,
            "prompt": f"<|im_start|>system\n你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。<|im_end|>\n<|im_start|>user\n将下面的日文文本翻译成中文：{text}<|im_end|>\n<|im_start|>assistant\n",
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
                    "content": f"将下面的日文文本翻译成中文：{text}"
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
        response = requests.post(endpoint[0], json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f'请求翻译API错误: {e}')
        return text
    # 获取响应的内容
    if api_type == 0 :
        translated_text = response.json()["content"]
    elif api_type == 2:
        translated_text = response.json()['choices'][0]['text']
    else :
        translated_text = response.json()["choices"][0]["message"]["content"]

    # 去除翻译结果中不希望出现的特定字符串
    unwanted_string = "将下面的日文文本翻译成中文："
    translated_text = translated_text.replace(unwanted_string, "")
    
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
            "endpoint": [],
            "api_type": 0,
            "save_frequency": 100,
            "shutdown": 0,
            "max_workers": 1,
            "use_lock": 0
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
    if endpoint == []:
        veri = input("请输入数字来选择部署类型(默认为本地部署):\n[0] 本地部署Sakura v0.9\n[1] kaggle部署Sakura v0.9 \n[2] text-generation-webui\n")
        if veri == "" :
            api_type = 0
        else:
            api_type = int(veri)
        data['api_type'] = api_type

        if api_type == 0 :
            verurl = input("请输入Api地址(默认为http://127.0.0.1:8080/completion):\n")
            if verurl == "" :
                endpoint.append("http://127.0.0.1:8080/completion")
            else:
                endpoint.append(verurl)
        elif api_type == 2:
            verurl = input("请输入Api地址(默认为http://127.0.0.1:5000/v1/completions):\n")
            if verurl == "" :
                endpoint.append("http://127.0.0.1:5000/v1/completions")
            else:
                endpoint.append(verurl)
        else :
            verurl = input("请输入Api地址(例如https://114-514-191-810.ngrok-free.app):\n")
            if verurl == "" :
                print("必须提供Api地址！")
                sys.exit()
            else :
                endpoint.append(verurl+"/v1/chat/completions")
        data['endpoint']=endpoint
        print("配置已保存到config.json,下次启动将默认加载")
    # 读取任务列表,保存频率,自动关机信息
    if task_list == []:
        print("请输入需要翻译的文件名或者文件夹名，如有多个请换行输入(默认为ManualTransFile.json):")
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
            # 判断是否是绝对路径
            if os.path.isabs(file_name) == 0:
                file_name = os.path.abspath(file_name)
                       
            if os.path.exists(str(file_name)) == 0:
                print(f"文件{file_name}不存在，请重新输入")
                continue
            
            if os.path.isdir(str(file_name)):
                for root, dirs, files in os.walk(str(file_name)):
                    for file in files:
                        if file.endswith(".json") or file.endswith(".csv"):
                            task_list.append(os.path.join(root, file))
                            print(f"已添加{os.path.join(root, file)}")
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

def save_json_safely(data, task_name):
    temp_task_name = task_name + '.tmp'
    with open(temp_task_name, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    os.replace(temp_task_name, task_name)  # 替换原文件

def save_csv_safely(data, task_name):
    temp_task_name = task_name + '.tmp'
    data.to_csv(temp_task_name, index=False, quoting=csv.QUOTE_ALL)
    os.replace(temp_task_name, task_name)  # 替换原文件

def save(data, task_name):
    if task_name.endswith(".json"):
        save_json_safely(data, task_name)
    if task_name.endswith(".csv"):
        save_csv_safely(data, task_name)

def main():
    init()
    while task_list != []:
        # 读取JSON或CSV文件
        task_name = task_list[0]
        print(f"开始翻译{task_name},正在读取文件...")
        if task_name.endswith(".json"):
            with open(task_name, 'r', encoding='utf-8') as file:
                data = json.load(file)
        elif task_name.endswith(".csv"):
            data = pd.read_csv(task_name, encoding='utf-8')
            data['Original Text'] = data['Original Text'].astype(str)
            data['Machine translation'] = data['Machine translation'].astype(str)
        print("读取完成.") 
        json_keys = list(data.keys())
        print('开始翻译...')
        # 使用tqdm创建进度条
        for i in tqdm(range(start_index, len(data)), desc="任务进度"):
            print(f'翻译文件:{task_name} 索引:第{i+2}行')
            if task_name.endswith(".json"):
                original_text = json_keys[i]
            if task_name.endswith(".csv"):
                original_text = data.loc[i, 'Original Text']
            contains_jp, updated_text = contains_japanese(original_text)
            if contains_jp:
                translated_text = translate_text_by_paragraph(updated_text, i) #以换行符作为分割点多次提交
                print(f"原文: {updated_text} => 翻译: {translated_text}\n\n")
            else:
                print(f"跳过（不含日文）: {original_text}")
                translated_text = original_text
            if task_name.endswith(".json"):
                data[original_text] = translated_text
            if task_name.endswith(".csv"):
                data.loc[i, 'Machine translation'] = translated_text

            if (i + 1) % save_frequency == 0:
                print(f"达到{save_frequency}行，保存进度和文件...")
                save_progress(i + 1,task_list)
                save(data, task_name)
                print("保存完成.")
        
        task_list.pop(0)
        save_progress(0,task_list)
        save(data, task_name)
        print(f"文件{task_name}翻译完成.")
        
    # 翻译完成后进度重置
    save_progress(0,[])
    print("All done.")
    if shutdown == 1:
        print("翻译完成，将在一分钟后关机...")
        shutdown_pc()

if __name__ == "__main__":
    main()
