import json
import requests
import re
import os
import pandas as pd
from tqdm import tqdm
import unicodedata
import csv
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 读取全局配置信息
def load_config():
    if not os.path.exists("config.json"):
        config_data = {
            "last_processed": 0,
            "task_list": ["ManualTransFile.json"],
            "endpoint": ["http://127.0.0.1:5000/v1/chat/completions"],
            "model_type": "SakuraV1_0",
            "use_dict": False,
            "dict": {},
            "dict_mode": "Partial",
            "save_frequency": 100,
            "shutdown": 0,
            "max_workers": 1
        }
        with open("config.json", 'w') as file:
            json.dump(config_data, file, indent=4)
    with open('config.json', 'r', encoding='utf-8') as file:
        return json.load(file)

# 模型版本管理
def get_translation_model(model_name, model_version):
    if model_name.lower() == "sakura":
        if model_version == "0.8":
            return "SakuraV0_8"
        elif model_version == "0.10":
            return "SakuraV0_10"
        elif model_version == "1.0":
            return "SakuraV1_0"
        else:
            return "SakuraV1_0"
    elif model_name.lower() == "sakura32b":
        if model_version == "0.10":
            return "Sakura32bV0_10"
        else:
            return "Sakura32bV0_10"
    elif model_name.lower() == "galtransl":
        if model_version == "2.6":
            return "GalTranslV2_6"
        else:
            return "GalTranslV2_6"
    else:
        return "SakuraV1_0"

# 检查文本是否包含日文字符
def contains_japanese(text):
    text = unicodedata.normalize('NFKC', text)
    return bool(re.search(r'[\u3040-\u30ff\u3400-\u4DBF\u4E00-\u9FFF]', text)), text

# 分割文本段落
def split_text_with_newlines(text):
    paragraphs = re.split(r'(\r\n|\r|\n)', text)
    return paragraphs

# 符号管理工具类
def fix_translation_end(original, translation):
    if translation.endswith("。") and not original.endswith("。"):
        translation = translation[:-1]
    if translation.endswith("。」") and not original.endswith("。」"):
        translation = translation[:-2] + "」"
    return translation

def unescape_translation(original, translation):
    if "\r" not in original:
        translation = translation.replace("\r", "\r")
    if "\n" not in original:
        translation = translation.replace("\n", "\n")
    if "\t" not in original:
        translation = translation.replace("\t", "\t")
    return translation

# 翻译文本，按段落翻译
def translate_text_by_paragraph(text, index, api_idx=0, config=None):
    contains_jp, updated_text = contains_japanese(text)
    if contains_jp:
        segments = split_text_with_newlines(updated_text)
        translated_segments = []
        for segment in segments:
            if segment in ['\r\n', '\r', '\n']:
                translated_segments.append(segment)
            else:
                if segment:
                    translated_segments.append(translate_text(segment, index, api_idx=api_idx, config=config))
                else:
                    translated_segments.append(segment)
        translated_text = ''.join(translated_segments)
        return translated_text
    else:
        return text

# 处理翻译请求的JSON构造
def make_request_json(text, model_type, use_dict, dict_mode, dict_data):
    messages = [
        {"role": "system", "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"},
        {"role": "user", "content": f"将下面的日文文本翻译成中文：{text}"}
    ]
    if use_dict:
        dict_str = '\n'.join([f"{k}->{v[0]}" for k, v in dict_data.items()])
        messages.append({"role": "user", "content": f"根据以下术语表：\n{dict_str}\n将下面的日文文本翻译成中文：{text}"})
    data = {
        "model": "sukinishiro",
        "messages": messages,
        "temperature": 0.1,
        "top_p": 0.3,
        "max_tokens": 512,
        "frequency_penalty": 0.2,
        "do_sample": True,
        "num_beams": 1,
        "repetition_penalty": 1.0
    }
    return data

# 调用API进行翻译
def translate_text(text, index, api_idx=0, attempt=1, config=None):
    if attempt > 3:
        return text
    try:
        endpoint = config['endpoint'][api_idx]
        model_type = get_translation_model(config['model_type'], "1.0")
        data = make_request_json(text, model_type, config['use_dict'], config['dict_mode'], config['dict'])
        response = requests.post(endpoint, json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f'请求翻译API错误: {e}')
        return translate_text(text, index, api_idx, attempt + 1, config)
    translated_text = response.json().get("choices")[0].get("message", {}).get("content", "")
    translated_text = translated_text.replace("将下面的日文文本翻译成中文：", "").replace("<|im_end|>", "")
    translated_text = fix_translation_end(text, translated_text)
    translated_text = unescape_translation(text, translated_text)
    print(f"原文: {text}\n翻译: {translated_text}\n")  # 调试信息，输出翻译前后的文本
    return translated_text

# 保存翻译进度
def save_progress(data, filename, index, task_list):
    if filename.endswith(".json"):
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
    elif filename.endswith(".csv"):
        data.to_csv(filename, index=False, quoting=csv.QUOTE_ALL)
    config = load_config()
    config['last_processed'] = index
    config['task_list'] = task_list
    with open('config.json', 'w', encoding='utf-8') as file:
        json.dump(config, file, indent=4)

# 主流程
def main():
    config = load_config()
    if not config['endpoint']:
        print("请配置API endpoint后再运行程序。")
        return
    task_list = config['task_list']
    if not task_list:
        print("未找到待翻译文件，请更新config.json。")
        return

    for task_name in task_list:
        if not os.path.exists(task_name):
            print(f"文件{task_name}不存在，跳过。")
            continue

        if task_name.endswith(".json"):
            with open(task_name, 'r', encoding='utf-8') as file:
                data = json.load(file)
            json_keys = list(data.keys())
        elif task_name.endswith(".csv"):
            data = pd.read_csv(task_name, encoding='utf-8')
            data['Original Text'] = data['Original Text'].astype(str)
            data['Machine translation'] = data['Machine translation'].astype(str)
        else:
            print(f"不支持的文件类型: {task_name}")
            continue

        total_keys = len(data)
        start_index = config['last_processed']
        api_num = len(config['endpoint'])
        with ThreadPoolExecutor(max_workers=config['max_workers']) as executor:
            future_to_index = {}
            for i in range(start_index, total_keys):
                key = json_keys[i] if task_name.endswith(".json") else data.loc[i, 'Original Text']
                api_index = i % api_num
                future = executor.submit(translate_text_by_paragraph, key, i, api_index, config)
                future_to_index[future] = i
            for future in tqdm(as_completed(future_to_index), total=len(future_to_index), desc="任务进度"):
                index = future_to_index[future]
                try:
                    translated_text = future.result()
                    if task_name.endswith(".json"):
                        data[json_keys[index]] = translated_text
                    if task_name.endswith(".csv"):
                        data.loc[index, 'Machine translation'] = translated_text
                    if (index + 1) % config['save_frequency'] == 0 or index + 1 == total_keys:
                        save_progress(data, task_name, index + 1, task_list)
                except Exception as exc:
                    print(f'{index + 1}行翻译发生异常: {exc}')

if __name__ == "__main__":
    main()
