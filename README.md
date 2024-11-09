<div align="center">
<h1>
  RPGMaker_LLM_Translator
</h1>
</div>

# 介绍
这是一个基于Mtool/Translator++和Sakura模型的RPGMaker游戏本地翻译器，能够提供高质量离线日文翻译  
建议使用[Sakura-13B-Galgame翻译模型](https://github.com/SakuraLLM/Sakura-13B-Galgame)，当前支持版本为Sakura v0.8/v0.9/v0.10pre1/Galtransl-v2.6

已跑通直接使用Translator++的翻译流程，效果达到预期。但考虑到12$的价格，仍会在近期对MTool版本进行重构。

## TODO
- [ ] 添加退化检测
- [ ] 添加历史上文
- [ ] 添加prompt字典
- [x] 添加并发
- [x] 添加对sakura v0.10支持
- [ ] 去除对sakura v0.9/v0.8支持
- [ ] 添加GUI
- [x] 添加换行符分割

## 快速开始
首先需要部署Sakura模型，推荐使用Galtransl模型
请参考[Sakura模型部署教程](https://github.com/SakuraLLM/SakuraLLM/wiki)

### Mtool
部署教程：详见[本仓库wiki](https://github.com/fkiliver/RPGMaker_LLM_Translator/wiki)

### Translator++
在Sakura模型启动后，修改proxy.py的TARGET_URL为Sakura地址  
`
TARGET_URL = "http://127.0.0.1:8848/v1/chat/completions"  # 转发的目标URL
`
在Translator++上安装ChatGPT插件
![image](https://github.com/user-attachments/assets/b77fc7e6-cb04-4efc-8488-203ac74224ac)
导入Translator++目录下的form.jsv，修改Target URL为proxy.py监听的端口
![image](https://github.com/user-attachments/assets/8d22f33a-25e8-4623-abf6-9604c41bdb88)

然后便可以开始翻译了



