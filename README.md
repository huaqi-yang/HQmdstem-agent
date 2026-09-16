# HQmdstem AI 智能助手（Agent 外壳）

在 HQmdstem 命令行工作流工具之上叠加的一层 **DeepSeek 大模型 Agent**，
用自然语言驱动结构建模、格式转换、绘图与微结构分析，配套 Gradio 网页界面。

## 目录结构

| 文件 | 作用 |
|---|---|
| `tools.py` | 10 个 function-calling 工具，映射到 `scripts/hq_*.py` |
| `agent.py` | DeepSeek 对话循环（工具调用 + 多步执行） |
| `app.py` | Gradio 网页界面 |
| `workspace/` | 所有生成文件（xyz/cfg/csv/png）的输出目录 |
| `.env` | DeepSeek API key（不提交 git） |

## 快速开始

1. 确认 API key 已写入 `.env`（`DEEPSEEK_API_KEY=sk-...`）。
2. 用 gpumdkit 环境启动：

```bash
C:/Users/yhq18/miniconda3/envs/gpumdkit/python.exe app.py
```

3. 浏览器打开 `http://127.0.0.1:7860`。

## 演示建议（纯自然语言、全程出图）

- 「生成 L12 Cu3Zn 超胞 N=3」 → 出 xyz
- 「把它转成 cfg」 → 出 cfg
- 「画 Cu-Zn 凸包」 → 出图
- 「画含 DFT 对比的凸包」 → 出图
- 「画实验相图」 → 出图
- 「分析这个 xyz 的孪晶 / 团簇 / 偏析」 → 出文本 + 图
- 「画 RDF 4x1 面板」 → 出图

## 说明

- 本机（Windows）上只运行纯 Python 功能；GPUMD/NEP/QSTEM/CP2K/ABACUS 的
  重计算会生成输入文件，实际计算需在集群或 WSL 上跑，Agent 会如实说明。
- 电镜图像分析（`analyze_tem_image`）需要一张真实电镜图片，可先把图片
  放进 `workspace/` 再让 Agent 分析。
- 第三方势文件 / 基组（ABACUS 赝势、CP2K 基组等）不随包分发，符合版权要求。
