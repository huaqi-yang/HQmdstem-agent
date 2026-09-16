"""HQmdstem AI 智能助手 —— Gradio 网页界面（豆包风格布局）。

启动：
  C:/Users/yhq18/miniconda3/envs/gpumdkit/python.exe app.py
然后在浏览器打开 http://127.0.0.1:7860
"""
import os
import sys

# 让子进程（tools.py 调用 scripts/hq_*.py）也继承 UTF-8 模式，避免 GBK 编码错误。
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Windows 中文环境默认 GBK，遇到 Cu₃Zn 等 Unicode 下标字符会报 UnicodeEncodeError。
# 强制 stdout/stderr 用 UTF-8（配合 start.bat 里的 PYTHONUTF8=1 双保险）。
if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import gradio as gr

import agent
import tools

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log")


def _log_error(msg):
    """把运行错误追加到 agent.log，方便定位（浏览器只显示笼统的「错误」）。"""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 40 + "\n" + msg + "\n")
    except Exception:
        pass


def _excepthook(tp, val, tb):
    import traceback
    _log_error("UNCAUGHT " + "".join(traceback.format_exception(tp, val, tb)))
    sys.__excepthook__(tp, val, tb)


sys.excepthook = _excepthook

EXAMPLES = [
    "生成 B2 CuZn 超胞 N=3，转成 cfg 文件，再做团簇分析",
    "生成 L12 Cu3Zn 超胞 N=3",
    "画 Cu-Zn 凸包",
    "画实验相图",
    "画 RDF 4x1 面板",
    "画 Cu-Zn 合金的波恩稳定性图",
]

CSS = """
footer { display: none !important; }
html, body { height: 100%; overflow: hidden; }
body, [class*="gradio-container"] {
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background: #ffffff;
}
[class*="gradio-container"] {
  max-width: none !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
  height: 100vh;
}
gradio-app, body, html { margin: 0 !important; padding: 0 !important; }
.fillable {
  max-width: none !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* ===== 左侧边栏（豆包风格） ===== */
.sidebar {
  background: #f9f9f9 !important;
  border-right: 1px solid #e5e5e5 !important;
  padding: 20px 14px !important;
  height: 100vh;
  overflow: hidden;
  display: flex !important;
  flex-direction: column !important;
  flex: 0 0 210px !important;
  min-width: 210px !important;
  max-width: 210px !important;
  text-align: left !important;
  align-items: stretch !important;
}
.brand { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; padding: 0 4px; }
.brand-logo {
  width: 34px; height: 34px; border-radius: 9px; flex: 0 0 auto;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  color: #fff; font-weight: 800; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  letter-spacing: .5px;
}
.brand-name { font-size: 16px; font-weight: 700; color: #1f1f1f; line-height: 1.2; }
.brand-sub { font-size: 11.5px; color: #8e8e93; margin-top: 1px; }

.new-chat-btn { margin-bottom: 16px; }
.new-chat-btn button {
  background: #ffffff !important; color: #1f1f1f !important;
  border: 1px solid #e0e0e5 !important; border-radius: 10px !important;
  font-weight: 600 !important; width: 100%; height: 38px !important;
}

.side-title {
  font-size: 12px; color: #9ca3af; font-weight: 600;
  letter-spacing: .5px; margin: 0 4px 8px 4px;
}

/* 智能体执行过程：豆包历史列表风格的步骤条目 */
.proc-panel { margin-bottom: 16px; max-height: 42vh; overflow-y: auto; }
.proc-empty { color: #b0b0b5; font-size: 12px; line-height: 1.6; padding: 0 4px; }
.proc-list { display: flex; flex-direction: column; gap: 2px; }
.proc-step {
  padding: 7px 10px; border-radius: 8px; font-size: 12.5px;
  animation: procIn .2s ease;
}
.proc-step:hover { background: #ececf1; }
.proc-step.run { background: #eef2ff; }
.proc-step.error { background: #fef2f2; }
.proc-row { display: flex; align-items: center; gap: 8px; }
.proc-dot {
  width: 7px; height: 7px; border-radius: 50%; flex: 0 0 auto; display: inline-block;
}
.proc-dot.ok { background: #16a34a; }
.proc-dot.err { background: #dc2626; }
.proc-dot.run { background: #2563eb; animation: pulse 1s ease-in-out infinite; }
.proc-title { font-weight: 500; color: #1f2937; flex: 1; line-height: 1.35; }
.proc-time { color: #b0b0b5; font-size: 11px; flex: 0 0 auto; }
.proc-detail {
  color: #9ca3af; margin-top: 2px; line-height: 1.45; font-size: 11.5px;
  word-break: break-all; padding-left: 15px;
}

@keyframes procIn { from { opacity: 0; transform: translateY(-3px); } to { opacity: 1; transform: none; } }
@keyframes pulse { 0%, 100% { opacity: .35; } 50% { opacity: 1; } }

/* 生成文件区（吸底） */
.sidebar-files { margin-top: auto; padding-top: 12px; }

/* ===== 主对话区 ===== */
.app-row { height: 100vh !important; margin: 0 !important; padding: 0 !important; }
.main-col {
  padding: 0 !important;
  height: 100vh;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
  gap: 0 !important;
}
.main-col > * { flex-shrink: 0 !important; }
.chat-wrap {
  padding: 8px 24px 0 24px;
  flex: 0 0 auto !important;
}
.examples-row { margin-top: auto !important; }
.examples-row, .input-row { flex: 0 0 auto !important; }

/* 输入区：豆包式大圆角输入框 */
.input-row { padding: 8px 24px 10px 24px; gap: 10px; align-items: center; }
.input-box textarea, .input-box input {
  border-radius: 24px !important;
  background: #f4f4f5 !important;
  border: 1px solid transparent !important;
  padding: 9px 16px !important;
  font-size: 14px !important;
  box-shadow: none !important;
  min-height: 44px !important;
  height: 44px !important;
}
.input-box textarea:focus, .input-box input:focus {
  border-color: #2563eb !important;
  background: #ffffff !important;
}
.send-btn button {
  height: 44px !important;
  padding: 0 22px !important;
  border-radius: 22px !important;
  background: #2563eb !important; color: #ffffff !important;
  font-size: 14px !important; font-weight: 600 !important;
  line-height: 44px !important; min-width: 72px !important;
  box-shadow: 0 2px 8px rgba(37, 99, 235, .35) !important;
}
.send-btn button:hover { background: #1d4ed8 !important; }

/* 快速示例 chips（单行横向滚动，避免换行把输入框挤出屏幕） */
.examples-row { padding: 0 24px 10px 24px; }
.examples-row .ex-title { font-size: 12px; color: #8e8e93; margin-bottom: 4px; }
.example-chips { flex-wrap: nowrap !important; overflow: hidden !important; }
.example-chips button {
  background: #f4f4f5 !important; color: #3f3f46 !important;
  border: 1px solid #ececf1 !important; border-radius: 999px !important;
  font-size: 12.5px !important; padding: 6px 14px !important;
  margin: 0 6px 6px 0 !important;
  flex: 0 0 auto !important; white-space: nowrap !important;
}
.example-chips button:hover { background: #e8e8ec !important; }

/* ===== 豆包式气泡 ===== */
.chatbot .message-row { background: transparent !important; }
.chatbot .user-row, .chatbot .bot-row { background: transparent !important; }

.chatbot .user-row .bubble-wrap {
  background: #1f1f1f !important;
  border-radius: 18px !important;
  padding: 10px 16px !important;
}
.chatbot .user-row .bubble-wrap,
.chatbot .user-row .bubble-wrap * { color: #ffffff !important; }

.chatbot .bot-row .bubble-wrap {
  background: transparent !important;
  border-radius: 18px !important;
  padding: 8px 4px !important;
}

/* AI 结果里的图片做成卡片 */
.chatbot .bot-row img {
  border-radius: 12px !important;
  border: 1px solid #ececf1 !important;
  box-shadow: 0 1px 3px rgba(0,0,0,.05);
}

.chatbot .avatar-image {
  border-radius: 50% !important;
  border: none !important;
  box-shadow: none !important;
}

/* ===== 对话/输入区撑满主列 ===== */
.chatbot { max-width: none !important; }
.input-row, .examples-row { max-width: none !important; }
"""

theme = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="indigo",
    neutral_hue="slate",
)

AVATAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatar.png")

BRAND_HTML = """
<div class="brand">
  <div class="brand-logo">HQ</div>
  <div>
    <div class="brand-name">HQmdstem AI</div>
    <div class="brand-sub">计算材料学智能助手</div>
  </div>
</div>
"""

PROC_TITLE_HTML = '<div class="side-title">智能体执行过程</div>'

PLACEHOLDER = """
<div style="text-align:center; padding: 48px 20px;">
  <div style="font-size:38px; margin-bottom:12px;">🧪</div>
  <div style="font-size:21px; font-weight:700; color:#1f1f1f;">HQmdstem AI 智能助手</div>
  <div style="color:#8e8e93; margin-top:10px; font-size:14px; line-height:1.8;">
    面向 Cu-Zn 合金体系的计算材料学 Agent<br>
    结构建模 · 格式转换 · 相图凸包 · RDF · 微结构 · 弹性力学 · GPUMD 输入
  </div>
</div>
"""


def list_files():
    """列出 workspace 里 Agent 生成的文件（按修改时间倒序，供下载）。"""
    ws = tools.WORKSPACE
    if not os.path.isdir(ws):
        return []
    files = [
        os.path.join(ws, f)
        for f in os.listdir(ws)
        if os.path.isfile(os.path.join(ws, f)) and not f.startswith("_")
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    return files


def _workspace_names():
    """返回 workspace 里当前的文件名集合（用于 diff 出「本次生成」的文件）。"""
    ws = tools.WORKSPACE
    if not os.path.isdir(ws):
        return set()
    return {
        f for f in os.listdir(ws)
        if os.path.isfile(os.path.join(ws, f)) and not f.startswith("_")
    }


def _proc_html(steps):
    """把工具步骤列表渲染成左侧「智能体执行过程」面板 HTML（豆包历史列表风格）。"""
    if not steps:
        return '<div class="proc-empty">对话开始后，智能体的每一步操作会显示在这里</div>'
    items = []
    for s in steps:
        state = s.get("state")
        status = s.get("status")
        if state == "running":
            dot = '<span class="proc-dot run"></span>'
            time_html = '<span class="proc-time">…</span>'
            detail = "执行中…"
            cls = "proc-step run"
        elif status == "error":
            dot = '<span class="proc-dot err"></span>'
            time_html = f'<span class="proc-time">{s.get("elapsed_ms", 0)} ms</span>'
            detail = s.get("summary", "")
            cls = "proc-step error"
        else:
            dot = '<span class="proc-dot ok"></span>'
            time_html = f'<span class="proc-time">{s.get("elapsed_ms", 0)} ms</span>'
            detail = s.get("summary", "")
            cls = "proc-step"

        args_str = " · ".join(f"{k}={v}" for k, v in (s.get("args") or {}).items())
        if args_str and detail:
            detail = f"{args_str} · {detail}"
        elif args_str:
            detail = args_str

        items.append(
            f'<div class="{cls}">'
            f'<div class="proc-row">{dot}<span class="proc-title">{s["label"]}</span>{time_html}</div>'
            f'<div class="proc-detail">{detail}</div>'
            f"</div>"
        )
    return '<div class="proc-list">' + "".join(items) + "</div>"


def _build_result(answer, images, new_files):
    """组装最终回答：文字 + 「本次生成文件」卡片 + 图片（Gradio 原生渲染）。"""
    parts = []
    if answer:
        parts.append(answer)
    if new_files:
        chips = " ".join(f"`{f}`" for f in new_files)
        parts.append(
            "\n\n---\n\n**📦 本次生成文件**\n\n" + chips +
            "\n\n> 可在左侧「生成文件」区下载"
        )
    if not parts:
        parts = ["已完成。"]

    if images:
        content = parts + [{"path": p} for p in images]
    else:
        content = parts if len(parts) > 1 else parts[0]
    return content


def respond(message, history_state, display_state):
    message = (message or "").strip()
    if not message:
        yield "", display_state, history_state, display_state, list_files(), _proc_html([])
        return

    user_msg = {"role": "user", "content": message}
    steps = []

    before = _workspace_names()

    # 初始画面：用户消息 + 「正在思考」占位（回答一次性输出，不再逐字打）
    display = display_state + [user_msg, {"role": "assistant", "content": "*正在思考…*"}]
    yield "", display, history_state, display, list_files(), _proc_html(steps)

    answer = ""
    images = []
    try:
        for ev in agent.chat_events(message, history_state):
            if ev["type"] == "tool_start":
                steps.append({
                    "tool": ev["step"]["tool"],
                    "label": ev["step"]["label"],
                    "args": ev["step"]["args"],
                    "state": "running",
                    "status": "",
                    "summary": "",
                    "elapsed_ms": 0,
                })
                yield "", display, history_state, display, list_files(), _proc_html(steps)
            elif ev["type"] == "tool_call":
                s = ev["step"]
                for st in reversed(steps):
                    if st.get("state") == "running":
                        st.update({
                            "state": "done",
                            "status": s["status"],
                            "summary": s.get("summary", ""),
                            "elapsed_ms": s.get("elapsed_ms", 0),
                        })
                        break
                yield "", display, history_state, display, list_files(), _proc_html(steps)
            elif ev["type"] == "done":
                answer = ev["answer"]
                images = ev["images"]
    except Exception as e:
        import traceback
        _log_error("respond: " + traceback.format_exc())
        answer = f"运行出错：{type(e).__name__} —— {e}"

    final_text = answer or "（无回答）"
    new_files = sorted(_workspace_names() - before)
    display[-1] = {"role": "assistant", "content": _build_result(final_text, images, new_files)}

    history_state = history_state + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": final_text},
    ]
    yield "", display, history_state, display, list_files(), _proc_html(steps)


def clear_chat():
    return [], [], [], list_files(), _proc_html([])


with gr.Blocks(title="HQmdstem AI 智能助手") as demo:
    with gr.Row(equal_height=True, elem_classes=["app-row"]):
        # ===== 左侧边栏 =====
        with gr.Column(scale=0, min_width=210, elem_classes=["sidebar"]):
            gr.HTML(BRAND_HTML)
            with gr.Column(elem_classes=["new-chat-btn"]):
                new_chat = gr.Button("＋ 新对话")
            gr.HTML(PROC_TITLE_HTML)
            proc_panel = gr.HTML(elem_classes=["proc-panel"])
            gr.HTML('<div class="sidebar-files"><div class="side-title">生成文件</div></div>')
            files_out = gr.File(label="", file_count="multiple", interactive=False, value=list_files())

        # ===== 主对话区 =====
        with gr.Column(scale=4, elem_classes=["main-col"]):
            with gr.Column(elem_classes=["chat-wrap"]):
                chatbot = gr.Chatbot(
                    layout="bubble",
                    height="calc(100vh - 200px)",
                    show_label=False,
                    placeholder=PLACEHOLDER,
                    group_consecutive_messages=False,
                    avatar_images=(None, AVATAR),
                    buttons=["copy"],
                )

            history_state = gr.State([])
            display_state = gr.State([])

            with gr.Column(elem_classes=["examples-row"]):
                gr.HTML('<div class="ex-title">快速示例（点击直接运行）</div>')
                with gr.Row(elem_classes=["example-chips"]):
                    for p in EXAMPLES:
                        btn = gr.Button(p, size="sm")

                        def _handler(h, d, _p=p):
                            for out in respond(_p, h, d):
                                yield out[1], out[2], out[3], out[4], out[5]

                        btn.click(
                            fn=_handler,
                            inputs=[history_state, display_state],
                            outputs=[chatbot, history_state, display_state, files_out, proc_panel],
                        )

            with gr.Row(elem_classes=["input-row"]):
                msg = gr.Textbox(
                    placeholder="描述你想做的计算或分析，例如：生成 B2 CuZn 结构并转成 cfg…",
                    show_label=False,
                    scale=8,
                    elem_classes=["input-box"],
                )
                send = gr.Button("发送", scale=0, variant="primary", elem_classes=["send-btn"])

    outputs = [msg, chatbot, history_state, display_state, files_out, proc_panel]
    inputs = [msg, history_state, display_state]

    send.click(respond, inputs, outputs)
    msg.submit(respond, inputs, outputs)
    new_chat.click(clear_chat, None, [chatbot, history_state, display_state, files_out, proc_panel])


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=4)
    demo.launch(theme=theme, css=CSS, inbrowser=True)
