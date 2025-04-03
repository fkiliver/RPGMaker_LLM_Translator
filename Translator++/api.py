from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request
from functools import lru_cache
from llm import LLM
import logging
import uvicorn
import json
import re

port = 1500
logging.basicConfig(filename="log.log")
history_deque = deque(maxlen=3)
llm = LLM("galtransl", "Sakura-GalTransl-7B-v3-Q5_K_S.gguf", 8, ["0", "1", "2", "3", "0", "1", "2", "3"])
app = FastAPI()
dicts = [
    {"src": "控制符", "dst": "控制符"},
    {"src": "ヘレナ・ルビンシュタイン", "dst": "海伦娜·鲁宾斯坦"},
    {"src": "セシリア・フェリシアーノ", "dst": "塞西莉亚·费利西亚诺"},
    {"src": "シャルロット・ローザリエ", "dst": "夏洛特·罗莎莉亚"},
    {"src": "ソレイニャ", "dst": "索蕾妮娅"},
    {"src": "シスター・ルシア", "dst": "修女·露西亚"},
    {"src": "ヌーディア", "dst": "努迪娅"},
    {"src": "ルイス・グレイバーン", "dst": "路易斯·格雷文"}
]

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

@lru_cache(maxsize=1024)
def api_translate(text: str, history: tuple[str]) -> str:
    """带缓存的单条文本翻译核心函数
    
    Args:
        text (str): 待翻译文本（自动替换全角空格为半角空格）
        history (tuple[str]): 历史翻译上下文（需传入可哈希的tuple）
        
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
    result = llm.translate(text, history, dicts).get()
    return result

def text_translate(text: str, history: tuple[str]) -> str:
    """预处理文本并执行翻译
    
    Args:
        text (str): 可能包含`${dat[数字]}`格式控制符的文本
        history (tuple[str]): 历史翻译上下文（需传入可哈希的tuple）
        
    Returns:
        str: 翻译后的文本
        
    Note:
        1. 自动转换 ${dat[1]} ↔ 控制符1 的格式
        2. 校验翻译前后控制符数量和行数是否一致
        3. 不一致时会记录警告日志
    """
    pattern1 = r"\$\{dat\[(\d+)\]\}"
    pattern2 = r"控制符\1"
    pattern3 = r"控制符(\d+)"
    pattern4 = r"${dat[\1]}"
    before = Counter(re.findall(pattern1, text))
    line_num = len(text.splitlines())
    text = re.sub(pattern1, pattern2, text)
    text = api_translate(text, history)
    text = re.sub(pattern3, pattern4, text)
    after = Counter(re.findall(pattern1, text))
    if before != after:
        logging.warning(f"{before} != {after}\n{text}")
    if line_num != len(text.splitlines()):
        logging.warning(f"line_num mismatch\n{text}")
    return text

def data_translate(data: str, history: tuple[str]) -> str:
    """处理包含<SG标签>的复合数据翻译
    
    Args:
        data (str): 可能包含<SG...>标签的文本
        history (tuple[str]): 历史翻译上下文（需传入可哈希的tuple）
        
    Returns:
        str: 翻译后的完整文本
        
    Note:
        1. 优先提取<SG...:内容>结构进行分段翻译
        2. 无标签时直接调用text_translate
        3. 保持原标签结构不变只翻译内容部分
    """
    pattern = r"<SG.*?>"
    finds = re.findall(pattern, data, re.DOTALL)
    if len(finds) > 0:
        for raw in finds:
            index = raw.find(":")
            if index == -1:
                continue
            text = raw[index + 1 : -1]
            text = text_translate(text, history)
            data = data.replace(raw, f"{raw[:index]}:{text}>")
    else:
        data = text_translate(data, history)
    return data

@app.post("/v1/chat/completions")
async def read_item(request: Request):
    """批量翻译API端点（POST方法）
    
    Args:
        request (Request): FastAPI请求对象，需包含：
        {
            "messages": [{
                "role": "user",
                "content": "[\"text1\", \"text2\"]"  # JSON字符串数组
            }]
        }
        
    Returns:
        dict: 格式化的响应数据：
        {
            "choices": [{
                "message": {
                    "content": "[\"trans1\", \"trans2\"]"  # JSON字符串数组
                }
            }]
        }
        
    Note:
        1. 使用ThreadPoolExecutor实现多文本并发翻译
        2. 维护全局history_deque保存最近3条历史记录
        3. 每个文本会附带其之前3条文本作为上文
    """
    data = await request.json()
    data = data["messages"][0]["content"]
    data = json.loads(data)
    history = []
    for d in data:
        history.append(tuple(history_deque))
        history_deque.append(d)
    with ThreadPoolExecutor(len(data)) as executor:
        data = executor.map(data_translate, data, history)
    return {"choices": [{"message": {"content": json.dumps(list(data))}}]}

@app.get("/")
def read_item(text: str):
    """单条文本翻译API端点（GET方法）
    
    Args:
        text (str): 通过URL参数传递的待翻译文本
        
    Returns:
        str: 直接返回翻译结果字符串
    """
    result = api_translate(text, [])
    return result

if __name__ == '__main__':
    uvicorn.run(app, port=port)
