"""HQmdstem DeepSeek Agent 对话循环（function calling）。"""
import json
import os
import time

from openai import OpenAI

import tools

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_env():
    env = {}
    p = os.path.join(AGENT_DIR, ".env")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = _load_env()
API_KEY = ENV.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = ENV.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
MODEL = ENV.get("DEEPSEEK_MODEL") or "deepseek-chat"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = """你是「HQmdstem 智能助手」，一个面向 Cu-Zn 合金体系的计算材料学 AI Agent。

你的能力：通过调用工具函数，完成结构建模、格式转换（xyz↔cfg）、NEP 训练集预处理
（能量平移 / 坏帧筛选）、相图/凸包绘制、RDF 绘图、微结构（团簇/偏析/孪晶/晶粒/晶向）
分析、电镜图像白链长统计，以及生成各类重计算程序的输入文件：GPUMD 分子动力学
（run.in）、NEP 微调（nep.in 等）、CP2K / ABACUS 单点能（input.inp / STRU+INPUT）。

工作规则：
1. 【必须调用工具】当用户要求「画 / 生成 / 转换 / 分析 / 绘图」任何东西时，你
   必须调用对应的工具函数真实执行，绝不能只回复文字说明、绝不能假装已完成。
   每一次绘图或分析请求都要真实调用一次工具，哪怕多轮对话中前面的请求已经
   做过类似的图。
2. 先理解用户意图，再调用最合适的工具；一次可连续调用多个工具完成多步任务。
3. 所有生成的文件（xyz/cfg/csv/png）都保存在工作目录里，工具返回的
   "saved -> xxx" 就是文件名，后续工具直接用这个文件名引用即可。
4. 本机是演示环境，GPUMD/NEP/QSTEM/CP2K/ABACUS 等重计算程序未安装，
   这类任务你只生成输入文件，并明确告诉用户「输入文件已生成，请到集群或
   WSL 上运行」。
5. 回答用中文，简洁、准确，突出每一步做了什么、生成了什么结果。
6. 工具报错时如实说明原因并给出补救建议，不要编造结果。"""

MAX_STEPS = 10

# 工具名 -> 过程面板上展示的中文动作名。
TOOL_LABELS = {
    "generate_ordered_structure": "结构建模（有序固溶体）",
    "generate_disordered_structure": "结构建模（无序固溶体）",
    "convert_xyz_to_cfg": "格式转换（xyz → cfg）",
    "convert_cfg_to_xyz": "格式转换（cfg → xyz）",
    "shift_energy": "NEP 训练集能量平移",
    "remove_frames": "训练集坏帧筛选",
    "plot_cu_zn_phase_data": "相图 / 凸包绘制",
    "plot_rdf": "径向分布函数 RDF",
    "plot_rdf_4x1": "RDF 4×1 面板",
    "analyze_microstructure": "微结构分析",
    "analyze_orientation": "晶向 / 键角分析",
    "analyze_tem_image": "电镜白链统计",
    "prepare_gpumd_input": "GPUMD 输入生成",
    "analyze_elastic_born": "弹性常数 · 波恩稳定性分析",
    "plot_born_stability": "波恩稳定性 3×2 图",
    "prepare_nep_finetune": "NEP 微调输入生成",
    "prepare_cp2k_input": "CP2K 单点能输入生成",
    "prepare_abacus_input": "ABACUS 单点能输入生成",
}

# 这些动作词出现时，视为「任务型」请求，第一步强制调用工具，避免 LLM 只回文字。
_TASK_ACTION_WORDS = (
    "画", "绘制", "生成", "建模", "转换", "转成", "分析", "统计",
    "制作", "创建", "计算", "做一个", "建一个",
)


def _looks_like_task(text):
    return any(w in text for w in _TASK_ACTION_WORDS)


def _summarize(text, limit=220):
    """把工具返回的长文本压成一行摘要，供过程面板展示。"""
    text = (text or "").strip()
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[:limit] + "…"
    return text


def chat_events(user_text, history):
    """生成器：逐步产出 Agent 运行过程事件。

    事件类型：
      {"type": "tool_start", "step": {...}}   —— 工具即将执行（过程面板点亮中）
      {"type": "tool_call", "step": {...}}    —— 工具执行完成
      {"type": "done", "answer": str, "images": [str]}  —— 对话结束

    step 字段：tool / label / args / status / summary / images / elapsed_ms
    """
    system = SYSTEM_PROMPT + (
        f"\n\n【当前工作空间】{tools.get_workspace()}\n"
        "所有生成的文件和读取的输入文件都在这个目录下；用户问“文件在哪 / 存到哪”时，直接给出这个路径。"
    )
    messages = [{"role": "system", "content": system}]
    for h in history or []:
        c = h.get("content")
        if isinstance(c, str) and c.strip():
            messages.append({"role": h.get("role", "user"), "content": c})

    messages.append({"role": "user", "content": user_text})

    images = []
    first = True
    for _ in range(MAX_STEPS):
        tool_choice = "required" if (first and _looks_like_task(user_text)) else "auto"
        first = False
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools.TOOL_SCHEMAS,
            tool_choice=tool_choice,
            temperature=0.0,
        )
        msg = resp.choices[0].message

        calls_raw = list(getattr(msg, "tool_calls", None) or [])
        assistant = {"role": "assistant"}
        content = getattr(msg, "content", None)
        if content:
            assistant["content"] = content
        if calls_raw:
            assistant["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": getattr(tc, "type", "function"),
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in calls_raw
            ]
        messages.append(assistant)

        if not calls_raw:
            yield {"type": "done", "answer": (content or "").strip(), "images": images}
            return

        for tc in calls_raw:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            label = TOOL_LABELS.get(name, name)
            yield {"type": "tool_start", "step": {"tool": name, "label": label, "args": args}}

            func = tools.TOOL_DISPATCH.get(name)
            t0 = time.perf_counter()
            if func is None:
                text = f"未知工具: {name}"
                imgs = []
                status = "error"
            else:
                try:
                    text, imgs = func(**args)
                    status = "ok"
                except Exception as e:
                    text = f"工具执行出错: {e}"
                    imgs = []
                    status = "error"
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            images.extend(imgs)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})

            yield {
                "type": "tool_call",
                "step": {
                    "tool": name,
                    "label": label,
                    "args": args,
                    "status": status,
                    "summary": _summarize(text),
                    "images": imgs,
                    "elapsed_ms": elapsed_ms,
                },
            }

    yield {
        "type": "done",
        "answer": "抱歉，这次任务步骤过多，我先停一下。你可以换个更简洁的说法再试。",
        "images": images,
    }


def chat(user_text, history):
    """便捷封装：跑完一轮，返回 (回答文本, 图片列表, 工具调用轨迹)。"""
    answer = ""
    images = []
    trace = []
    for ev in chat_events(user_text, history):
        if ev["type"] == "tool_call":
            trace.append(ev["step"])
        elif ev["type"] == "done":
            answer = ev["answer"]
            images = ev["images"]
    return answer, images, trace
