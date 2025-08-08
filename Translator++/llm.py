from llama_cpp import Llama
from multiprocessing import Pool
from functools import lru_cache
import os

def contains_japanese(text):
    """检查文本是否包含日文片假名
    
    Args:
        text (str): 待检测的文本
        
    Returns:
        bool: 如果文本中包含日文片假名（Unicode范围3040-30FF）返回True，否则返回False
    """
    for char in text:
        if "\u3040" <= char <= "\u30FF":
            return True
    return False

def _init_worker(model_path: str, cuda_device: str):
    """
    初始化工作进程的LLM模型

    Args:
        model_path (str): 模型文件路径
        cuda_device (str): 指定使用的CUDA设备ID
    """
    global worker_model
    print(f"PID: {os.getpid()} CUDA: {cuda_device}")
    os.environ["CUDA_VISIBLE_DEVICES"] = cuda_device
    worker_model = Llama(model_path, n_gpu_layers=-1, n_ctx=2048, verbose=False)

def _get_glossary(gpt_dicts: list[dict]) -> str:
    """
    将术语字典列表格式化为字符串

    Args:
        gpt_dicts (list[dict]): 术语字典列表，每个字典应包含:
            - src: 源语言术语
            - dst: 目标语言翻译
            - info(可选): 附加信息

    Returns:
        str: 格式化后的术语表字符串，每行格式为"src->dst #info"或"src->dst"

    Example:
        >>> _get_glossary([{"src": "猫", "dst": "cat", "info": "动物"}])
        >>> '猫->cat #动物\\n'
    """
    glossary = ""
    for gpt in gpt_dicts:
        if "info" in gpt.keys():
            glossary += "{}->{} #{}\n".format(gpt["src"], gpt["dst"], gpt["info"])
        else:
            glossary += "{}->{}\n".format(gpt["src"], gpt["dst"])
    return glossary

def _process_translate(model_name: str, text: str, history: list[dict] = [], gpt_dicts: list[dict] = []) -> str:
    """
    执行单条文本的翻译

    Args:
        model_name (str): 模型名称，支持"sakura"或"galtransl"
        text (str): 待翻译的日文文本
        history (list[dict], optional): 对话历史记录
        gpt_dicts (list[dict], optional): 术语字典列表

    Returns:
        str: 翻译后的中文文本
    """
    messages = []
    if model_name == "sakura":
        messages.append({"role": "system", "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"})
        for item in history:
            messages.append({"role": "assistant", "content": item})
        if len(gpt_dicts) == 0:
            user_prompt = "将下面的日文文本翻译成中文：" + text
        else:
            user_prompt = "根据以下术语表（可以为空）：\n"
            user_prompt += _get_glossary(gpt_dicts)
            user_prompt += "将下面的日文文本根据对应关系和备注翻译成中文：" + text
    
    elif model_name == "galtransl":
        messages.append({"role": "system", "content": "你是一个视觉小说翻译模型，可以通顺地使用给定的术语表以指定的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，注意"})
        user_prompt = "历史翻译：\n" + "\n".join(history) + "\n"
        if len(gpt_dicts) != 0:
            user_prompt += "参考以下术语表（可为空，格式为src->dst #备注）：\n"
            user_prompt += _get_glossary(gpt_dicts)
        user_prompt += "根据以上术语表的对应关系和备注，结合历史剧情和上下文，将下面的文本从日文翻译成简体中文：\n" + text
    
    messages.append({"role": "user", "content": user_prompt})
    if model_name == "sakura":
        res = worker_model.create_chat_completion(messages=messages, temperature=0.1, top_p=0.3, repeat_penalty=1, max_tokens=512, frequency_penalty=0.2)
    elif model_name == "galtransl":
        res = worker_model.create_chat_completion(messages=messages, temperature=0.6, top_p=0.8, repeat_penalty=1, max_tokens=512, frequency_penalty=0.1)
    return res["choices"][0]["message"]["content"]

class LLM:
    """
    多进程LLM翻译器主类

    Attributes:
        model_name (str): 模型名称
        pool (multiprocessing.Pool): 工作进程池
    """
    def __init__(self, model_name: str, model_path: str, num_process: int, cuda_device: list[str]):
        """
        初始化LLM翻译器

        Args:
            model_name (str): 模型名称 ("sakura" | "galtransl")
            model_path (str): 模型文件路径
            num_process (int): 工作进程数
            cuda_device (list[str]): 每个进程使用的CUDA设备ID列表

        Note:
            - cuda_device列表长度应与num_process匹配
        """
        self.model_name = model_name
        self.pool = Pool(num_process)
        init_args = [(model_path, cuda_device[i]) for i in range(num_process)]
        self.pool.starmap(_init_worker, init_args)
    
    def translate(self, text: str, history: list[dict] = [], gpt_dicts: list[dict] = []):
        """
        提交单个翻译任务到进程池

        Args:
            text (str): 待翻译文本
            history (list[dict], optional): 历史对话
            gpt_dicts (list[dict], optional): 术语表

        Returns:
            multiprocessing.pool.AsyncResult: 异步结果对象
        """
        return self.pool.apply_async(_process_translate, (self.model_name, text, history, gpt_dicts))
    
    def batch_translate(self, datas: list[dict]) -> list[str]:
        """
        批量翻译文本

        Args:
            datas (list[dict]): 待翻译数据列表，每个元素应包含:
                - text: 待翻译文本
                - history: 历史对话
                - gpt_dicts: 术语表

        Returns:
            list[str]: 翻译结果列表，顺序与输入一致

        Note:
            - 每个 key 都必须有值，即使是空列表

        Example:
            >>> translator.batch_translate([{"text": "こんにちは", "history": [], "gpt_dicts": []}])
            >>> ['你好']
        """
        tasks = [self.__translate(data["text"], data["history"], data["gpt_dicts"]) for data in datas]
        results = [task.get() for task in tasks]
        return results

@lru_cache(maxsize=1024)
def translate(llm: LLM, text: str, history: tuple[str], local_dicts: tuple[str], global_dicts: tuple[str]) -> str:
    """带缓存的单条文本翻译核心函数
    
    Args:
        llm (LLM): 多进程LLM翻译器实例
        text (str): 待翻译文本（自动替换全角空格为半角空格）
        history (tuple[str]): 历史翻译上下文（需传入可哈希的tuple）
        local_dicts (tuple[str]): 局部字典（需传入可哈希的tuple）无论文本中是否出现都会传入翻译器
        global_dicts (tuple[str]): 全局字典（需传入可哈希的tuple）只会将文本中出现的部分传入翻译器
        
    Returns:
        str: 翻译后的中文文本
        
    Note:
        1. 使用LRU缓存（最多1024条）加速重复文本翻译
        2. 非日文文本会直接返回原内容
        3. 实际调用llm.translate()执行翻译
    """
    text = text.replace("\u3000", "  ")
    if not contains_japanese(text):
        return text
    gpt_dicts = list(local_dicts)
    for item in global_dicts:
        if item["src"] in text:
            gpt_dicts.append(item)
    result = llm.translate(text, history, gpt_dicts).get()
    return result
