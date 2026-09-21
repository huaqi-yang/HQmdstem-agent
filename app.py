"""HQmdstem AI 智能助手 —— Gradio 网页界面（全屏界面布局）。

启动：
  python app.py
然后在浏览器打开 http://127.0.0.1:7860
"""
import html
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

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
PROJECTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects.json")


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

# 「选择工作空间」按钮 + 弹出菜单（模仿 WorkBuddy 输入框下方的文件夹按钮）
WS_SELECT_HTML = """
<div class="ws-select-wrap">
  <button type="button" class="ws-select-btn" id="ws-select-btn">
    <span class="ws-select-icon">📁</span>
    <span class="ws-select-label" id="ws-select-label">选择工作空间</span>
    <span class="ws-select-caret">▾</span>
  </button>
  <div class="ws-select-menu" id="ws-select-menu" style="display:none;">
    <button type="button" class="ws-select-item" data-action="local"><span class="ws-item-icon">📂</span>打开本地工作空间</button>
    <button type="button" class="ws-select-item" data-action="default"><span class="ws-item-icon">🏠</span>使用默认工作空间</button>
  </div>
</div>
"""

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

/* ===== 左侧边栏 ===== */
.sidebar {
  background: #f9f9f9 !important;
  border-right: 1px solid #e5e5e5 !important;
  padding: 14px 12px !important;
  height: 100vh;
  overflow: hidden;
  display: flex !important;
  flex-direction: column !important;
  flex-wrap: nowrap !important;
  flex: 0 0 210px !important;
  min-width: 210px !important;
  max-width: 210px !important;
  text-align: left !important;
  align-items: stretch !important;
}
.sidebar > .block, .sidebar > .column { flex-grow: 0 !important; flex-shrink: 0 !important; }
.brand { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; padding: 0 4px; }
.brand-logo {
  width: 34px; height: 34px; border-radius: 9px; flex: 0 0 auto;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  color: #fff; font-weight: 800; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  letter-spacing: .5px;
}
.brand-name { font-size: 16px; font-weight: 700; color: #1f1f1f; line-height: 1.2; }
.brand-sub { font-size: 11.5px; color: #8e8e93; margin-top: 1px; }

.new-chat-btn { margin-bottom: 10px; }
.new-chat-btn button {
  background: #ffffff !important; color: #1f1f1f !important;
  border: 1px solid #e0e0e5 !important; border-radius: 10px !important;
  font-weight: 600 !important; width: 100%; height: 38px !important;
}

.side-title {
  font-size: 12px; color: #9ca3af; font-weight: 600;
  letter-spacing: .5px; margin: 0 4px 6px 4px;
}

/* 智能体执行过程：固定高度的独立区域，步骤多了在内部滚动 */
.proc-panel {
  margin-bottom: 10px;
  flex-basis: 30vh !important;
  flex-grow: 0 !important;
  flex-shrink: 0 !important;
  min-height: 0 !important;
  overflow-y: auto !important;
}
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

/* 最近项目区：固定在智能体执行过程下方，占满剩余高度，可鼠标滚动 */
.sidebar-files { margin-top: 2px; padding-top: 0; }
.sidebar > .projects-panel {
  flex: 1 1 auto !important;
  min-height: 0 !important;
  overflow-y: auto !important;
  margin-bottom: 0;
}
.projects-list { display: flex; flex-direction: column; gap: 2px; }
.project-item {
  display: flex; align-items: center; gap: 4px;
  padding: 7px 8px 7px 10px; border-radius: 8px;
  cursor: pointer;
}
.project-item:hover { background: #ececf1; }
.project-body { flex: 1 1 auto; min-width: 0; }
.project-title {
  font-size: 12.5px; font-weight: 600; color: #1f2937;
  line-height: 1.35;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.project-meta { font-size: 11px; color: #9ca3af; margin-top: 2px; }
.project-del {
  display: none;
  flex: 0 0 auto;
  width: 20px; height: 20px; border: none; border-radius: 5px;
  background: transparent; color: #9ca3af; font-size: 16px; line-height: 20px;
  cursor: pointer; padding: 0; text-align: center;
}
.project-item:hover .project-del { display: block; }
.project-del:hover { background: #e5e5ea; color: #ef4444; }
.projects-empty { color: #b0b0b5; font-size: 12px; padding: 4px; line-height: 1.6; }

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
.chat-wrap {
  padding: 8px 24px 0 24px;
  flex: 1 1 0 !important;
  min-height: 0 !important;
}
.examples-row { margin-top: auto !important; }
.examples-row, .input-row, .ws-row { flex: 0 0 auto !important; }

/* 输入区：大圆角输入框 */
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

/* ===== 工作空间选择栏（输入框下方） ===== */
.ws-row { padding: 0 24px 8px 24px; gap: 8px; align-items: center; flex: 0 0 auto !important; }
.ws-label { font-size: 12px; color: #8e8e93; font-weight: 600; flex: 0 0 auto; white-space: nowrap; }
.ws-bar-wrap { flex: 0 0 auto !important; }
.ws-bar { display: inline-flex; align-items: center; gap: 8px; line-height: 1; }
.ws-path-box {
  display: inline-flex; align-items: center;
  height: 32px; padding: 0 12px; max-width: 340px;
  border-radius: 10px; background: #f4f4f5;
  border: 1px solid transparent;
  font-size: 12.5px; font-family: Consolas, "Courier New", monospace;
  color: #3f3f46; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ws-status { font-size: 11px; color: #8e8e93; line-height: 1.3; min-height: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
/* 「选择工作空间」按钮 + 弹出菜单（模仿 WorkBuddy） */
.ws-select-wrap { position: relative; }
.ws-select-btn {
  display: inline-flex; align-items: center; gap: 6px;
  height: 32px; padding: 0 12px;
  border: 1px solid #e0e0e5; border-radius: 8px;
  background: #ffffff; font-size: 12.5px; color: #1f1f1f;
  cursor: pointer; font-weight: 500; white-space: nowrap;
}
.ws-select-btn:hover { background: #f4f4f5; }
.ws-select-icon { font-size: 13px; line-height: 1; }
.ws-select-label { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ws-select-caret { color: #9ca3af; font-size: 10px; }
.ws-select-menu {
  position: absolute; bottom: 40px; left: 0; z-index: 60;
  min-width: 200px; background: #ffffff;
  border: 1px solid #e5e5e5; border-radius: 10px;
  box-shadow: 0 -8px 24px rgba(0,0,0,.10); padding: 4px;
}
.ws-select-item {
  display: flex; align-items: center; gap: 8px; width: 100%; text-align: left;
  padding: 8px 10px; border: none; background: transparent;
  font-size: 13px; color: #1f2937; border-radius: 6px; cursor: pointer;
  white-space: nowrap;
}
.ws-select-item:hover { background: #f4f4f5; }
.ws-item-icon { font-size: 13px; line-height: 1; flex: 0 0 auto; }

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

/* ===== 聊天气泡 ===== */
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


def _safe_name(name):
    """清理文件夹名里的非法字符。"""
    for ch in '/\\:*?"<>|':
        name = name.replace(ch, " ")
    return " ".join(name.split()).strip()


def _folder_name(steps):
    """根据本次调用的工具，概括出文件夹名。"""
    labels = []
    for s in steps:
        lbl = (s.get("label") or "").strip()
        if lbl and lbl not in labels:
            labels.append(lbl)
    if not labels:
        return "生成结果"
    name = _safe_name(" · ".join(labels[:2]))[:40].rstrip()
    return name or "生成结果"


def _move_into_folder(names, folder):
    """把本次生成的文件移入 workspace/<folder>/ 子文件夹。"""
    ws = tools.get_workspace()
    dst = os.path.join(ws, folder)
    os.makedirs(dst, exist_ok=True)
    for name in names:
        src = os.path.join(ws, name)
        if os.path.isfile(src):
            try:
                shutil.move(src, os.path.join(dst, name))
            except Exception:
                pass


def _load_projects():
    """读取最近项目列表（最新在前），并给老记录补齐 id。"""
    try:
        with open(PROJECTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            changed = False
            for p in data:
                if isinstance(p, dict) and not p.get("id"):
                    p["id"] = uuid.uuid4().hex[:12]
                    changed = True
            if changed:
                _save_projects(data)
            return data
    except Exception:
        pass
    return []


def _save_projects(projects):
    """把项目列表写回 projects.json。"""
    try:
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _project_title(steps, message):
    """根据本次对话概括出一个项目标题。"""
    if steps:
        return _folder_name(steps)
    s = (message or "").strip()
    return _safe_name(s)[:20] or "对话"


def _record_project(steps, message, new_files, history, display):
    """记录一次对话为项目（内容概括 + 生成文件 + 完整对话），返回更新后的列表。"""
    projects = _load_projects()
    projects.insert(0, {
        "id": uuid.uuid4().hex[:12],
        "title": _project_title(steps, message),
        "time": time.strftime("%Y-%m-%d %H:%M"),
        "files": list(new_files),
        "message": message,
        "history": history,
        "display": display,
        "steps": steps,
    })
    projects = projects[:50]
    _save_projects(projects)
    return projects


def _within_7days(time_str):
    """判断项目时间是否在近 7 天内。"""
    try:
        t = time.mktime(time.strptime(time_str, "%Y-%m-%d %H:%M"))
        return (time.time() - t) <= 7 * 24 * 3600
    except Exception:
        return False


def _render_projects():
    """渲染「最近项目」列表 HTML（仅显示近 7 天）。"""
    projects = [p for p in _load_projects() if _within_7days(p.get("time", ""))]
    if not projects:
        return '<div class="projects-empty">近 7 天暂无项目，开始对话后会自动记录</div>'
    parts = []
    for p in projects:
        pid = html.escape(str(p.get("id") or ""), quote=True)
        title = html.escape(p.get("title", "") or "对话")
        t = html.escape(p.get("time", "") or "")
        n = len(p.get("files") or [])
        meta = t + (f" · {n}个文件" if n else "")
        parts.append(
            '<div class="project-item" data-id="' + pid + '">'
            '<div class="project-body">'
            '<div class="project-title">' + title + '</div>'
            '<div class="project-meta">' + html.escape(meta) + '</div>'
            '</div>'
            '<button type="button" class="project-del" data-id="' + pid + '" title="删除该项目">×</button>'
            "</div>"
        )
    return '<div class="projects-list">' + "".join(parts) + "</div>"


def load_project(pid):
    """根据项目 id 载入该对话到界面，返回 (chatbot, history_state, display_state, 过程面板)。"""
    pid = (pid or "").strip()
    proj = next((p for p in _load_projects() if str(p.get("id")) == pid), None)
    if proj is None:
        return [], [], [], _proc_html([])
    history = list(proj.get("history") or [])
    display = list(proj.get("display") or [])
    steps = list(proj.get("steps") or [])
    return display, history, display, _proc_html(steps)


def delete_project(pid):
    """从「最近项目」中删除指定项目，返回更新后的列表 HTML。"""
    pid = (pid or "").strip()
    projects = [p for p in _load_projects() if str(p.get("id")) != pid]
    _save_projects(projects)
    return _render_projects()


def _workspace_names():
    """返回 workspace 里当前的文件名集合（用于 diff 出「本次生成」的文件）。"""
    ws = tools.get_workspace()
    if not os.path.isdir(ws):
        return set()
    return {
        f for f in os.listdir(ws)
        if os.path.isfile(os.path.join(ws, f)) and not f.startswith("_")
    }


def _allowed_paths():
    """允许 Gradio 访问的路径：当前/默认工作空间 + 本机所有盘符根，
    这样用户把工作空间切到任意目录后，生成的图片仍能正常显示。"""
    paths = {tools.get_workspace(), tools.DEFAULT_WORKSPACE, os.path.expanduser("~")}
    for d in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = d + ":/"
        if os.path.isdir(root):
            paths.add(root)
    return sorted(p for p in paths if p)


def apply_workspace(path):
    """切换工作空间到用户输入的路径，返回 (规范化路径, 状态提示 HTML)。"""
    path = (path or "").strip()
    if not path:
        return tools.get_workspace(), '<span style="color:#dc2626;">路径为空，未切换</span>'
    try:
        new = tools.set_workspace(path)
    except Exception as e:
        return tools.get_workspace(), f'<span style="color:#dc2626;">切换失败：{html.escape(str(e))}</span>'
    return new, f'<span style="color:#16a34a;">已切换到：{html.escape(new)}</span>'


def reset_workspace_ui():
    """恢复默认工作空间。"""
    new = tools.reset_workspace()
    return new, f'<span style="color:#16a34a;">已恢复默认：{html.escape(new)}</span>'


def _pick_folder():
    """弹出系统「选择文件夹」对话框，返回所选路径；取消返回空串。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        folder = filedialog.askdirectory(title="选择工作空间文件夹", parent=root)
        root.destroy()
        return (folder or "").strip()
    except Exception:
        return _pick_folder_powershell()


def _pick_folder_powershell():
    """无图形界面环境下的回退方案（较慢）。"""
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$f = New-Object System.Windows.Forms.FolderBrowserDialog;"
        "$f.Description = '选择工作空间文件夹';"
        "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
        "{ Write-Output $f.SelectedPath }"
    )
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600,
        )
        return (p.stdout or "").strip()
    except Exception:
        return ""


def open_local_workspace(current_path):
    """「打开本地」按钮：弹出系统文件夹选择框，选中后切换。"""
    folder = _pick_folder()
    if not folder:
        return current_path, '<span style="color:#8e8e93;">已取消选择</span>'
    return apply_workspace(folder)


def _ws_bar_html(path):
    """把「选择工作空间」按钮 + 菜单 + 路径框合并成一条水平栏，保证同一水平线。"""
    return (
        '<div class="ws-bar">'
        + WS_SELECT_HTML
        + f'<div class="ws-path-box" title="{html.escape(path)}">{html.escape(path)}</div>'
        + '</div>'
    )


def on_ws_action(action):
    """「选择工作空间」弹出菜单的动作分发，返回 (工作空间栏 HTML, 状态提示 HTML)。"""
    action = (action or "").strip()
    if action == "local":
        path, status = open_local_workspace(tools.get_workspace())
    elif action == "default":
        path, status = reset_workspace_ui()
    else:
        path, status = tools.get_workspace(), ""
    return _ws_bar_html(path), status


def _proc_html(steps):
    """把工具步骤列表渲染成左侧「智能体执行过程」面板 HTML（历史列表风格）。"""
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
            "\n\n> 文件已保存到工作目录，并记录在左侧「最近项目」中"
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
        yield "", display_state, history_state, display_state, _render_projects(), _proc_html([])
        return

    user_msg = {"role": "user", "content": message}
    steps = []

    before = _workspace_names()

    # 初始画面：用户消息 + 「正在思考」占位（回答一次性输出，不再逐字打）
    display = display_state + [user_msg, {"role": "assistant", "content": "*正在思考…*"}]
    yield "", display, history_state, display, _render_projects(), _proc_html(steps)

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
                yield "", display, history_state, display, _render_projects(), _proc_html(steps)
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
                yield "", display, history_state, display, _render_projects(), _proc_html(steps)
            elif ev["type"] == "done":
                answer = ev["answer"]
                images = ev["images"]
    except Exception as e:
        import traceback
        _log_error("respond: " + traceback.format_exc())
        answer = f"运行出错：{type(e).__name__} —— {e}"

    final_text = answer or "（无回答）"
    new_files = sorted(_workspace_names() - before)
    if new_files:
        folder = _folder_name(steps)
        _move_into_folder(new_files, folder)
        moved = {os.path.basename(n) for n in new_files}
        images = [
            (os.path.join(os.path.dirname(p), folder, os.path.basename(p))
             if os.path.basename(p) in moved else p)
            for p in images
        ]
    display[-1] = {"role": "assistant", "content": _build_result(final_text, images, new_files)}

    history_state = history_state + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": final_text},
    ]
    _record_project(steps, message, new_files, history_state, display)
    yield "", display, history_state, display, _render_projects(), _proc_html(steps)


def clear_chat():
    return [], [], [], _render_projects(), _proc_html([])


with gr.Blocks(title="HQmdstem AI 智能助手") as demo:
    with gr.Row(equal_height=True, elem_classes=["app-row"]):
        # ===== 左侧边栏 =====
        with gr.Column(scale=0, min_width=210, elem_classes=["sidebar"]):
            gr.HTML(BRAND_HTML)
            with gr.Column(elem_classes=["new-chat-btn"]):
                new_chat = gr.Button("＋ 新对话")
            gr.HTML(PROC_TITLE_HTML)
            proc_panel = gr.HTML(elem_classes=["proc-panel"], value=_proc_html([]))
            gr.HTML('<div class="sidebar-files"><div class="side-title">最近项目</div></div>')
            projects_out = gr.HTML(elem_classes=["projects-panel"], value=_render_projects())

        # ===== 主对话区 =====
        with gr.Column(scale=4, elem_classes=["main-col"]):
            with gr.Column(elem_classes=["chat-wrap"]):
                chatbot = gr.Chatbot(
                    layout="bubble",
                    height="100%",
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
                            outputs=[chatbot, history_state, display_state, projects_out, proc_panel],
                        )

            with gr.Row(elem_classes=["input-row"]):
                msg = gr.Textbox(
                    placeholder="描述你想做的计算或分析，例如：生成 B2 CuZn 结构并转成 cfg…",
                    show_label=False,
                    scale=8,
                    elem_classes=["input-box"],
                )
                send = gr.Button("发送", scale=0, variant="primary", elem_classes=["send-btn"])

            with gr.Row(elem_classes=["ws-row"]):
                ws_bar = gr.HTML(_ws_bar_html(tools.get_workspace()), scale=0, elem_classes=["ws-bar-wrap"])
                ws_status = gr.HTML('<div class="ws-status"></div>', scale=1)

    outputs = [msg, chatbot, history_state, display_state, projects_out, proc_panel]
    inputs = [msg, history_state, display_state]

    proj_click_id = gr.Textbox(visible="hidden", elem_id="proj-click-id")
    proj_click_go = gr.Button(visible="hidden", elem_id="proj-click-go")
    proj_del_id = gr.Textbox(visible="hidden", elem_id="proj-del-id")
    proj_del_go = gr.Button(visible="hidden", elem_id="proj-del-go")
    ws_action_id = gr.Textbox(visible="hidden", elem_id="ws-action-id")
    ws_action_go = gr.Button(visible="hidden", elem_id="ws-action-go")

    send.click(respond, inputs, outputs)
    msg.submit(respond, inputs, outputs)
    new_chat.click(clear_chat, None, [chatbot, history_state, display_state, projects_out, proc_panel])
    ws_action_go.click(on_ws_action, ws_action_id, [ws_bar, ws_status])
    proj_click_go.click(
        load_project, proj_click_id,
        [chatbot, history_state, display_state, proc_panel],
    )
    proj_del_go.click(delete_project, proj_del_id, [projects_out])

    demo.load(_render_projects, None, [projects_out])
    demo.load(
        None, None, None,
        js="""() => {
  function setHiddenValue(sel, val) {
    const ta = document.querySelector(sel + ' textarea') || document.querySelector(sel + ' input');
    if (!ta) return false;
    const proto = ta.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(ta, val);
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  }
  function clickHidden(sel) {
    const btn = document.querySelector(sel + ' button') || document.querySelector(sel);
    if (btn) btn.click();
  }
  const wsBtn = document.querySelector('#ws-select-btn');
  const wsMenu = document.querySelector('#ws-select-menu');
  if (wsBtn && wsMenu) {
    wsBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      wsMenu.style.display = wsMenu.style.display === 'none' ? 'block' : 'none';
    });
    wsMenu.querySelectorAll('.ws-select-item').forEach((it) => {
      it.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = it.getAttribute('data-action') || '';
        wsMenu.style.display = 'none';
        if (setHiddenValue('#ws-action-id', action)) clickHidden('#ws-action-go');
      });
    });
  }
  document.addEventListener('click', (e) => {
    if (wsMenu && e.target && e.target.closest && !e.target.closest('.ws-select-wrap')) {
      wsMenu.style.display = 'none';
    }
    const del = e.target && e.target.closest ? e.target.closest('.project-del') : null;
    if (del) {
      const pid = del.getAttribute('data-id');
      if (!pid) return;
      if (!window.confirm('确定删除该项目？')) return;
      if (setHiddenValue('#proj-del-id', pid)) clickHidden('#proj-del-go');
      return;
    }
    const item = e.target && e.target.closest ? e.target.closest('.project-item') : null;
    if (!item) return;
    const pid = item.getAttribute('data-id');
    if (!pid) return;
    if (setHiddenValue('#proj-click-id', pid)) clickHidden('#proj-click-go');
  });
}""",
    )


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=4)
    demo.launch(theme=theme, css=CSS, inbrowser=True, allowed_paths=_allowed_paths())
