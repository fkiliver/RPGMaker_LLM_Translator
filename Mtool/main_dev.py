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
        elif model_version == "3.0":
            return "GalTranslV3"
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
    try:
        endpoint = config['endpoint'][api_idx]
        model_type = get_translation_model(config['model_type'], config['model_version'])
        context_size = config.get('context_size', 0)
        context = previous_translations[-context_size:] if previous_translations else []
        data = make_request_json(text, model_type, config['use_dict'], config['dict_mode'], config['dict'], context)
        response = requests.post(endpoint, json=data)
        response.raise_for_status()

        response_data = response.json()
        completion_tokens = response_data.get("usage", {}).get("completion_tokens", 0)
        max_tokens = data["max_tokens"]

        # 检查是否发生退化，重试时调整 frequency_penalty
        if completion_tokens == max_tokens:
            print("模型可能发生退化，调整 frequency_penalty 并重试...")
            data["frequency_penalty"] = 0.8
            response = requests.post(endpoint, json=data)
            response.raise_for_status()
            response_data = response.json()

    except requests.RequestException as e:
        print(f'请求翻译API错误: {e}')
        return ""
    
    translated_text = response_data.get("choices")[0].get("message", {}).get("content", "")
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
        elif model_type == "GalTranslV3":
            messages.append({"role": "system", "content": "你是一个视觉小说翻译模型，可以通顺地使用给定的术语表以指定的风格将日文翻译成简体中文，并联系上下文正确使用人称代词。"})
        else:
            messages.append({"role": "system", "content": "你是一个轻小说翻译模型，可以流畅通顺地将日文翻译成简体中文。"})
        
        if context:
            history_text = "历史翻译：" + "\n".join(context)
        else:
            history_text = ""
        
        if model_type == "GalTranslV3":
            if use_dict:
                dict_str = '\n'.join([f"{k}->{v[0]}" for k, v in dict_data.items()])
                user_content = f"{history_text}\n参考以下术语表\n{dict_str}\n根据以上术语表的对应关系和备注，结合历史剧情和上下文，将下面的文本从日文翻译成简体中文：\n{text}"
            else:
                user_content = f"{history_text}\n结合历史剧情和上下文，将下面的文本从日文翻译成简体中文：\n{text}"
            messages.append({"role": "user", "content": user_content})
        else:
            if context:
                for c in context:
                    messages.append({"role": "assistant", "content": c})
            
            if use_dict:
                dict_str = '\n'.join([f"{k}->{v[0]}" for k, v in dict_data.items()])
                messages.append({"role": "user", "content": f"根据上文和以下术语表：\n{dict_str}\n将下面的日文文本翻译成中文：{text}"})
            else:
                messages.append({"role": "user", "content": f"根据上文，将下面的日文文本翻译成中文：{text}"})
    
    temperature = 0.6 if model_type == "GalTranslV3" else 0.2
    
    data = {
        "model": "sukinishiro",
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.3,
        "max_tokens": 512,
        "frequency_penalty": 0.2,
        "do_sample": True,
        "num_beams": 1,
        "repetition_penalty": 1.0
    }
    return data

# 进度管理类
class TranslationProgress:
    def __init__(self, task_name, total_items, num_threads):
        self.progress_file = f"{task_name}.progress.json"
        self.task_name = task_name
        self.total_items = total_items
        self.num_threads = num_threads
        self.lock = threading.Lock()
        self.initialize()
    
    def initialize(self):
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r', encoding='utf-8') as file:
                self.progress_data = json.load(file)
        else:
            # 创建新的进度文件
            chunk_size = self.total_items // self.num_threads
            remainder = self.total_items % self.num_threads
            
            threads_info = []
            start_idx = 0
            
            for i in range(self.num_threads):
                # 计算每个线程的起止范围
                end_idx = start_idx + chunk_size - 1
                if i == self.num_threads - 1:
                    end_idx += remainder
                
                threads_info.append({
                    "thread_id": i,
                    "start_index": start_idx,
                    "end_index": end_idx,
                    "current_index": start_idx,
                    "previous_translations": []
                })
                
                start_idx = end_idx + 1
            
            self.progress_data = {
                "task_name": self.task_name,
                "total_items": self.total_items,
                "num_threads": self.num_threads,
                "threads": threads_info
            }
            self.save()
    
    def update_progress(self, thread_id, current_index, translation=None, context_size=0):
        with self.lock:
            thread_info = self.progress_data["threads"][thread_id]
            thread_info["current_index"] = current_index
            
            # 更新历史翻译记录
            if translation and context_size > 0:
                thread_info.setdefault("previous_translations", [])
                thread_info["previous_translations"].append(translation)
                # 仅保留最近的N条翻译
                if len(thread_info["previous_translations"]) > context_size:
                    thread_info["previous_translations"] = thread_info["previous_translations"][-context_size:]
            
            self.save()
    
    def get_thread_info(self, thread_id):
        return self.progress_data["threads"][thread_id]
    
    def get_previous_translations(self, thread_id):
        thread_info = self.progress_data["threads"][thread_id]
        return thread_info.get("previous_translations", [])
    
    def is_completed(self):
        for thread_info in self.progress_data["threads"]:
            if thread_info["current_index"] <= thread_info["end_index"]:
                return False
        return True
    
    def save(self):
        with open(self.progress_file, 'w', encoding='utf-8') as file:
            json.dump(self.progress_data, file, ensure_ascii=False, indent=4)

# 翻译工作线程函数
def translate_worker(thread_id, task_name, data, json_keys, progress_manager, config):
    thread_info = progress_manager.get_thread_info(thread_id)
    start_index = thread_info["current_index"]
    end_index = thread_info["end_index"]
    api_num = len(config['endpoint'])
    
    # 获取该线程的历史翻译记录
    previous_translations = progress_manager.get_previous_translations(thread_id)
    
    for i in range(start_index, end_index + 1):
        api_index = thread_id % api_num  # 使用线程ID来分配API端点
        
        if task_name.endswith(".json"):
            key = json_keys[i]
            original_text = key
        else:  # CSV文件
            original_text = data.loc[i, 'Original Text']
        
        translated_text = translate_text_by_paragraph(
            original_text, i, api_index, config, previous_translations
        )
        
        # 更新数据
        if task_name.endswith(".json"):
            data[json_keys[i]] = translated_text
        else:  # CSV文件
            data.loc[i, 'Machine translation'] = translated_text
        
        # 更新进度和历史翻译
        progress_manager.update_progress(
            thread_id, i + 1, translated_text, config.get('context_size', 0)
        )
        
        # 定期保存整个翻译文件
        if (i + 1) % config['save_frequency'] == 0 or i + 1 > end_index:
            save_translation_data(data, task_name)
            print(f"线程 {thread_id}: 已保存进度 {i + 1}/{end_index + 1}")

# 保存翻译数据
def save_translation_data(data, filename):
    if filename.endswith(".json"):
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
    elif filename.endswith(".csv"):
        data.to_csv(filename, index=False, quoting=csv.QUOTE_ALL)

# 主函数
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

        # 加载数据
        if task_name.endswith(".json"):
            with open(task_name, 'r', encoding='utf-8') as file:
                data = json.load(file)
            json_keys = list(data.keys())
            total_items = len(json_keys)
        elif task_name.endswith(".csv"):
            data = pd.read_csv(task_name, encoding='utf-8')
            data['Original Text'] = data['Original Text'].astype(str)
            data['Machine translation'] = data['Machine translation'].astype(str)
            total_items = len(data)
            json_keys = None
        else:
            print(f"不支持的文件类型: {task_name}")
            continue

        # 创建或加载进度管理器
        num_threads = config['max_workers']
        progress_manager = TranslationProgress(task_name, total_items, num_threads)
        
        # 创建并启动工作线程
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(
                target=translate_worker,
                args=(thread_id, task_name, data, json_keys, progress_manager, config)
            )
            threads.append(thread)
            thread.start()
            thread_info = progress_manager.get_thread_info(thread_id)
            print(f"线程 {thread_id} 已启动，处理范围: {thread_info['start_index']} - {thread_info['end_index']}, 当前进度: {thread_info['current_index']}")
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        print(f"任务 {task_name} 翻译完成")
        
        # 任务完成后，可以删除进度文件或保留作为记录
        # os.remove(f"{task_name}.progress.json")

if __name__ == "__main__":
    main()
