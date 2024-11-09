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
            "model_type": "Sgaltransl",
            "model_version": "2.6",
            "use_dict": False,
            "dict": {},
            "dict_mode": "Partial",
            "save_frequency": 100,
            "shutdown": 0,
            "max_workers": 1,
            "context_size": 0
        }
        with open("config.json", 'w') as file:
            json.dump(config_data, file, indent=4)
    with open('config.json', 'r', encoding='utf-8') as file:
        return json.load(file)

# 初始化字典
def initialize_dict(dict_str):
    if not dict_str:
        return {}, ""
    try:
        dict_data = json.loads(dict_str)
        dict_converted = {}
        for key, value in dict_data.items():
            if isinstance(value, list) and len(value) > 0:
                if len(value) == 1:
                    dict_converted[key] = [value[0], ""]
                else:
                    dict_converted[key] = value[:2]
            else:
                dict_converted[key] = [value, ""]
        dict_strings = get_dict_string_list(dict_converted)
        return dict_converted, "\n".join(dict_strings)
    except Exception as e:
        print(f"Error initializing dictionary: {e}")
        return {}, ""

# 获取字典字符串列表
def get_dict_string_list(kv_pairs):
    dict_list = []
    for key, value in kv_pairs.items():
        src = key
        dst = value[0]
        info = value[1]
        if info:
            dict_list.append(f"{src}->{dst} #{info}")
        else:
            dict_list.append(f"{src}->{dst}")
    return dict_list

# 模型版本管理
def get_translation_model(model_name, model_version):
    if model_name.lower() == "sakura":
        if model_version == "0.8":
            return "SakuraV0_8"
        elif model_version == "0.9":
            return "SakuraV0_9"
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

# 判断是否是文件路径
def is_file_path(text):
    # 基于文本特征判断是否是文件路径
    return bool(re.search(r'\.[a-zA-Z0-9]{3}$', text))

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
def translate_text_by_paragraph(text, index, api_idx=0, config=None, previous_translations=None):
    # 如果是文件路径或者文件，直接跳过
    if is_file_path(text):
        return text
    
    contains_jp, updated_text = contains_japanese(text)
    if contains_jp:
        segments = split_text_with_newlines(updated_text)
        translated_segments = []
        for segment in segments:
            if segment in ['\r\n', '\r', '\n']:
                translated_segments.append(segment)
            else:
                if segment:
                    translated_segments.append(translate_text(segment, index, api_idx=api_idx, config=config, previous_translations=previous_translations))
                else:
                    translated_segments.append(segment)
        translated_text = ''.join(translated_segments)
        return translated_text
    else:
        return text

# 调用API进行翻译
def translate_text(text, index, api_idx=0, attempt=1, config=None, previous_translations=None):
    if attempt > 3:
        return text
    try:
        endpoint = config['endpoint'][api_idx]
        model_type = get_translation_model(config['model_type'], config['model_version'])
        context_size = config.get('context_size', 0)
        context = previous_translations[-context_size:] if previous_translations else []
        data = make_request_json(text, model_type, config['use_dict'], config['dict_mode'], config['dict'], context)
        response = requests.post(endpoint, json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f'请求翻译API错误: {e}')
        return translate_text(text, index, api_idx, attempt + 1, config, previous_translations)
    translated_text = response.json().get("choices")[0].get("message", {}).get("content", "")
    translated_text = translated_text.replace("将下面的日文文本翻译成中文：", "").replace("<|im_end|>", "")
    translated_text = fix_translation_end(text, translated_text)
    translated_text = unescape_translation(text, translated_text)
    print(f"原文: {text}\n翻译: {translated_text}\n")  # 调试信息，输出翻译前后的文本
    return translated_text

# 处理翻译请求的JSON构造
def make_request_json(text, model_type, use_dict, dict_mode, dict_data, context):    
    messages = []
    
    if model_type == "SakuraV0_8":
        messages.append({"role": "system", "content": "你是一个简单的日文翻译模型，将日文翻译成简体中文。"})
        messages.append({"role": "user", "content": f"将下面的日文文本翻译成中文：{text}"})
    else:
        if model_type == "SakuraV0_9":
            messages.append({"role": "system", "content": "你是一个轻小说翻译模型，可以流畅地将日文翻译成简体中文，并正确使用人称代词。"})
        elif model_type == "SakuraV0_10":
            messages.append({"role": "system", "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"})
        elif model_type == "SakuraV1_0":
            messages.append({"role": "system", "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"})
        elif model_type == "GalTranslV2_6":
            messages.append({"role": "system", "content": "你是一个视觉小说翻译模型，可以通顺地使用给定的术语表以指定的风格将日文翻译成简体中文，并联系上下文正确使用人称代词。"})
        else:
            messages.append({"role": "system", "content": "你是一个轻小说翻译模型，可以流畅通顺地将日文翻译成简体中文。"})
        
        if context:
            for c in context:
                messages.append({"role": "assistant", "content": c})
        
        if use_dict:
            dict_str = '\n'.join([f"{k}->{v[0]}" for k, v in dict_data.items()])
            messages.append({"role": "user", "content": f"根据上文和以下术语表：\n{dict_str}\n将下面的日文文本翻译成中文：{text}"})
        else:
            messages.append({"role": "user", "content": f"根据上文，将下面的日文文本翻译成中文：{text}"})
    
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
    
    # 初始化字典
    dict_data, full_dict_str = initialize_dict(json.dumps(config.get('dict', {})))
    config['dict'] = dict_data
    
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
        previous_translations = []
        with ThreadPoolExecutor(max_workers=config['max_workers']) as executor:
            future_to_index = {}
            for i in range(start_index, total_keys):
                key = json_keys[i] if task_name.endswith(".json") else data.loc[i, 'Original Text']
                api_index = i % api_num
                future = executor.submit(translate_text_by_paragraph, key, i, api_index, config, previous_translations)
                future_to_index[future] = i
            for future in tqdm(as_completed(future_to_index), total=len(future_to_index), desc="任务进度"):
                index = future_to_index[future]
                try:
                    translated_text = future.result()
                    previous_translations.append(translated_text)
                    if len(previous_translations) > config.get('context_size', 0):
                        previous_translations.pop(0)
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
