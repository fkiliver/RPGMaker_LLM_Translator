<div align="center">
<h1>
  RPGMaker_LLM_Translator
</h1>
</div>

# 介绍
这是一个基于Mtool/Translator++和Sakura模型的RPGMaker游戏本地翻译器，能够提供高质量离线日文翻译  
建议使用[Sakura-13B-Galgame翻译模型](https://github.com/SakuraLLM/Sakura-13B-Galgame)，当前支持版本为Sakura v0.8/v0.9/v0.10pre1/Galtransl-v2.6

项目经过重构，支持Mtool和Translator和最新版本Sakura模型。

## TODO
- [x] 添加退化检测（仅MTool）
- [x] 添加历史上文（仅MTool）
- [x] 添加prompt字典（仅MTool）
- [x] 添加并发
- [x] 添加对Sakura v0.10支持
- [x] 添加对Sakura v1.0支持
- [x] 添加对Galtransl-v2.6支持

## 快速开始
首先需要部署Sakura模型，推荐使用Galtransl模型
请参考[Sakura模型部署教程](https://github.com/SakuraLLM/SakuraLLM/wiki)

### Mtool
部署教程：详见[本仓库wiki](https://github.com/fkiliver/RPGMaker_LLM_Translator/wiki)

### Translator++
详见[本仓库wiki](https://github.com/fkiliver/RPGMaker_LLM_Translator/wiki)

在Translator++上安装ChatGPT插件
![image](https://github.com/user-attachments/assets/b77fc7e6-cb04-4efc-8488-203ac74224ac)

然后便可以开始翻译了
