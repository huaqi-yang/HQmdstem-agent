# HQmdstem AI 智能助手（Agent）

在 HQmdstem 计算材料学工作流工具之上叠加的 **DeepSeek 大模型 Agent**：
用自然语言驱动结构建模、格式转换、训练集预处理、绘图与微结构分析，
配套 Gradio 网页界面。底层 `scripts/hq_*.py` 提供计算功能，Agent 负责
「理解意图 → 选择工具 → 拆解参数 → 多步执行 → 反馈结果」的完整决策链路。

## 目录结构

| 文件/目录 | 作用 |
|---|---|
| `agent.py` | DeepSeek 对话循环（function calling + 多步执行 + 过程事件） |
| `tools.py` | 18 个工具，映射到 `scripts/hq_*.py` |
| `app.py` | Gradio 网页界面 |
| `scripts/` | 底层 HQmdstem 工具脚本（17 个） |
| `examples/` | 内置演示数据（RDF / 弹性常数） |
| `workspace/` | 生成文件输出目录 |
| `config.json` | 路径配置（第三方势文件路径留空，按需填写） |
| `.env` | DeepSeek API key（不提交 git） |

## 环境要求

- Python 3.10+
- 依赖：`pip install -r requirements.txt`

## 快速开始

1. 复制 `.env.example` 为 `.env`，填入 DeepSeek API key：
   ```
   DEEPSEEK_API_KEY=sk-...
   ```
2. 安装依赖：`pip install -r requirements.txt`
3. 启动：`python app.py`（Windows 可双击 `start.bat`）
4. 浏览器打开 http://127.0.0.1:7860

## 功能（开箱即用）

- 结构建模：有序固溶体（L12 / B2 / L10）、无序固溶体
- 格式转换：xyz ↔ cfg（QSTEM）
- NEP 训练集预处理：能量平移、坏帧筛选
- 绘图：Cu-Zn 凸包 / 含 DFT 对比凸包 / 实验相图 / RDF / RDF 4×1 面板
- 微结构分析：团簇、成分偏析、孪晶、晶粒、晶向
- 电镜图像白色链长统计
- 弹性常数：Born 力学稳定性判断 + 3×2 稳定性图

## 功能（需额外提供文件）

- GPUMD / NEP 微调 / CP2K / ABACUS 输入生成：需提供对应势函数 / 赝势 / 基组文件
  （第三方数据，版权原因不随包分发）。Agent 会生成输入文件并提示到集群运行。

## 说明

- 本机（无 GPUMD / NEP / QSTEM 等重计算程序）只运行纯 Python 功能；重计算在
  集群或 WSL 上执行，Agent 只生成输入文件并如实说明。
- 电镜分析需先把一张真实电镜图片放入 `workspace/`。
