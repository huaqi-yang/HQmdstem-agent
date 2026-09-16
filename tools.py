"""HQmdstem Agent 工具层。

把自然语言映射到现有 scripts/hq_*.py 的子命令。只暴露 Windows 上能稳定
运行的纯 Python 功能（结构生成 / 格式转换 / 绘图 / 微结构分析 / 输入文件
生成）。GPUMD / NEP / QSTEM / CP2K / ABACUS 的重计算在集群或 WSL 上跑，
本层只负责生成输入文件并如实说明。
"""
import json
import os
import re
import subprocess
import sys

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
# HQmdstem 仓库根目录（包含 scripts/ 与 examples/）
HQ_HOME = r"D:\Desktop\HQmdstem\github"
WORKSPACE = os.path.join(AGENT_DIR, "workspace")
os.makedirs(WORKSPACE, exist_ok=True)

TIMEOUT = 300


def _script(script, *args):
    """在 WORKSPACE 下运行 scripts/<script>，返回 (文本输出, 图片绝对路径列表)。"""
    cmd = [sys.executable, os.path.join(HQ_HOME, "scripts", script), *[str(a) for a in args]]
    # 强制子进程 UTF-8 模式：即使用户直接双击 app.py 启动（没走 start.bat），
    # hq_*.py 输出中文/Unicode 下标也不会因 GBK 编码崩溃。
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        p = subprocess.run(
            cmd, cwd=WORKSPACE, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=TIMEOUT, env=env,
        )
    except subprocess.TimeoutExpired:
        return f"命令执行超时（>{TIMEOUT}s）", []
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if err:
        out = (out + "\n[stderr]\n" + err).strip()
    return (out or "(无输出)"), _find_images(out)


def _find_images(text):
    """从脚本输出里提取已生成图片的绝对路径（用于 Gradio 图库展示）。"""
    seen = []
    for tok in re.findall(r"\S+\.(?:png|jpg|jpeg)", text, re.IGNORECASE):
        tok = tok.rstrip(".,;")
        p = tok if os.path.isabs(tok) else os.path.join(WORKSPACE, tok)
        p = os.path.normpath(p)
        if os.path.isfile(p) and p not in seen:
            seen.append(p)
    return seen


# ---------------- 工具函数 ----------------

def generate_ordered_structure(kind, n, a=3.61, out=None):
    """生成有序固溶体 L12 / B2 / L10。"""
    args = ["ordered", kind, n]
    if a:
        args += ["--a", a]
    if out:
        args += ["--out", out]
    return _script("hq_structure.py", *args)


def generate_disordered_structure(n_cu, n_zn, a=3.61, out=None):
    """生成无序固溶体（Cu 原子数 + Zn 原子数）。"""
    args = ["disordered", n_cu, n_zn]
    if a:
        args += ["--a", a]
    if out:
        args += ["--out", out]
    return _script("hq_structure.py", *args)


def convert_xyz_to_cfg(xyz_file, cfg_file=None):
    """把 xyz 结构转成 QSTEM 用的 cfg 文件。"""
    args = ["xyz2cfg", xyz_file]
    if cfg_file:
        args += [cfg_file]
    return _script("hq_qstem.py", *args)


_PHASE_MAP = {
    "convex_hull": "hull",
    "convex_hull_with_dft": "hull-dft",
    "phase_diagram": "exp",
}


def plot_cu_zn_phase_data(plot_type, out=None):
    """绘制 Cu-Zn 凸包 / 含 DFT 对比的凸包 / 实验相图。"""
    args = [_PHASE_MAP[plot_type]]
    if out:
        args += ["--out", out]
    return _script("hq_phase.py", *args)


def plot_rdf(rdf_file, out=None):
    """绘制单条径向分布函数 RDF。"""
    args = ["rdf", rdf_file]
    if out:
        args += ["--out", out]
    return _script("hq_rdf.py", *args)


def plot_rdf_4x1():
    """绘制 4x1 面板 RDF（50/100/200/250K）。"""
    base = os.path.join(HQ_HOME, "examples", "rdf_data")
    return _script("hq_rdf.py", "4x1", "--base", base, "--out", WORKSPACE, "--formats", "png")


_MICRO_MAP = {
    "cluster": "cluster",
    "segregation": "segregate",
    "twin": "twin",
    "grain": "grain",
}


def analyze_microstructure(analysis, xyz_file, axis="z", bins=20, rcut=None):
    """微结构分析：团簇 / 成分偏析 / 孪晶 / 晶粒。"""
    sub = _MICRO_MAP[analysis]
    args = [sub, xyz_file]
    if sub == "segregate":
        args += ["--axis", axis, "--bins", bins]
    elif sub == "twin":
        args += ["--axis", axis]
    elif rcut is not None:
        args += ["--rcut", rcut]
    return _script("hq_micro.py", *args)


def analyze_orientation(xyz_file, out=None):
    """最近邻键角分布（晶向统计）。"""
    args = ["orientation", xyz_file]
    if out:
        args += ["--out", out]
    return _script("hq_micro.py", *args)


def analyze_tem_image(image_file):
    """电镜图像白色链长统计。"""
    return _script("hq_micro.py", "chain", image_file, "--output-dir", WORKSPACE)


def prepare_gpumd_input(directory="gpumd_demo", temperature=300, steps=1100000):
    """生成 GPUMD 分子动力学输入 run.in（缺 model.xyz/nep.txt 时自动复制示例）。"""
    return _script("hq_gpumd.py", "auto", directory, "--T", temperature, "--steps", steps)


_ELASTIC_OUT_DEFAULT = os.path.join(HQ_HOME, "examples", "elastic", "elastic.out")


def analyze_elastic_born(elastic_out=None):
    """波恩力学稳定性判断：读 6x6 弹性常数矩阵（GPa），判主余子式是否全 > 0。"""
    p = elastic_out or _ELASTIC_OUT_DEFAULT
    return _script("hq_elastic.py", "born", p)


def plot_born_stability(out=None):
    """绘制波恩稳定性 3x2 面板图（C11/C44/C55/C66 + 二阶/三阶行列式随温度变化）。"""
    args = ["born-plot"]
    if out:
        args += ["--out", out]
    return _script("hq_elastic.py", *args)


# ---------------- 调度表 ----------------

TOOL_DISPATCH = {
    "generate_ordered_structure": generate_ordered_structure,
    "generate_disordered_structure": generate_disordered_structure,
    "convert_xyz_to_cfg": convert_xyz_to_cfg,
    "plot_cu_zn_phase_data": plot_cu_zn_phase_data,
    "plot_rdf": plot_rdf,
    "plot_rdf_4x1": plot_rdf_4x1,
    "analyze_microstructure": analyze_microstructure,
    "analyze_orientation": analyze_orientation,
    "analyze_tem_image": analyze_tem_image,
    "prepare_gpumd_input": prepare_gpumd_input,
    "analyze_elastic_born": analyze_elastic_born,
    "plot_born_stability": plot_born_stability,
}


def _fn(name, desc, props, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        },
    }


TOOL_SCHEMAS = [
    _fn(
        "generate_ordered_structure",
        "生成 Cu-Zn 有序固溶体结构（L12=Cu3Zn、B2=CuZn、L10=CuZn），输出 xyz 文件。用户要求建有序结构时用这个。",
        {
            "kind": {"type": "string", "enum": ["L12", "B2", "L10"],
                     "description": "有序结构类型"},
            "n": {"type": "integer", "description": "超胞大小 N（NxNxN）"},
            "a": {"type": "number", "description": "晶格常数 a，缺省 3.61"},
            "out": {"type": "string", "description": "输出文件名，缺省自动命名"},
        },
        ["kind", "n"],
    ),
    _fn(
        "generate_disordered_structure",
        "生成 Cu-Zn 无序固溶体结构，指定 Cu 与 Zn 原子数，输出 xyz 文件。",
        {
            "n_cu": {"type": "integer", "description": "Cu 原子数"},
            "n_zn": {"type": "integer", "description": "Zn 原子数"},
            "a": {"type": "number", "description": "晶格常数 a，缺省 3.61"},
            "out": {"type": "string", "description": "输出文件名，缺省自动命名"},
        },
        ["n_cu", "n_zn"],
    ),
    _fn(
        "convert_xyz_to_cfg",
        "把 xyz 结构文件转换为 QSTEM 用的 cfg 文件（格式转换）。",
        {
            "xyz_file": {"type": "string", "description": "输入 xyz 文件名"},
            "cfg_file": {"type": "string", "description": "输出 cfg 文件名，缺省同名前缀 .cfg"},
        },
        ["xyz_file"],
    ),
    _fn(
        "plot_cu_zn_phase_data",
        "绘制 Cu-Zn 相图相关图表：convex_hull=凸包、convex_hull_with_dft=含 NEP/DFT 对比的凸包、phase_diagram=实验相图。",
        {
            "plot_type": {"type": "string",
                          "enum": ["convex_hull", "convex_hull_with_dft", "phase_diagram"],
                          "description": "图表类型"},
            "out": {"type": "string", "description": "输出图片文件名，缺省自动命名"},
        },
        ["plot_type"],
    ),
    _fn(
        "plot_rdf",
        "根据 rdf 数据文件绘制径向分布函数 g(r) 曲线。",
        {
            "rdf_file": {"type": "string", "description": "rdf 数据文件（如 rdf.out / gr.txt）"},
            "out": {"type": "string", "description": "输出图片文件名，缺省 rdf.png"},
        },
        ["rdf_file"],
    ),
    _fn(
        "plot_rdf_4x1",
        "绘制 4 种结构在 4 个温度下的 RDF 对比面板图。",
        {},
        [],
    ),
    _fn(
        "analyze_microstructure",
        "对 xyz 结构做微结构分析：cluster=团簇尺寸、segregation=成分偏析、twin=孪晶检测、grain=晶粒统计。",
        {
            "analysis": {"type": "string",
                         "enum": ["cluster", "segregation", "twin", "grain"],
                         "description": "分析类型"},
            "xyz_file": {"type": "string", "description": "输入 xyz 文件名"},
            "axis": {"type": "string", "enum": ["x", "y", "z"], "description": "偏析/孪晶分析方向，缺省 z"},
            "bins": {"type": "integer", "description": "偏析分桶数，缺省 20"},
            "rcut": {"type": "number", "description": "团簇/晶粒近邻截断半径，缺省自动估计"},
        },
        ["analysis", "xyz_file"],
    ),
    _fn(
        "analyze_orientation",
        "计算结构内最近邻键角分布并绘图（晶向/取向统计）。",
        {
            "xyz_file": {"type": "string", "description": "输入 xyz 文件名"},
            "out": {"type": "string", "description": "输出图片文件名，缺省 orientation.png"},
        },
        ["xyz_file"],
    ),
    _fn(
        "analyze_tem_image",
        "对透射电镜（TEM）图像做白色链长统计。输入是一张电镜图片文件。",
        {
            "image_file": {"type": "string", "description": "电镜图片文件路径"},
        },
        ["image_file"],
    ),
    _fn(
        "prepare_gpumd_input",
        "生成 GPUMD 分子动力学模拟输入文件（run.in）。若目录里缺 model.xyz/nep.txt 会自动复制内置示例。",
        {
            "directory": {"type": "string", "description": "输出目录，缺省 gpumd_demo"},
            "temperature": {"type": "integer", "description": "温度 K，缺省 300"},
            "steps": {"type": "integer", "description": "步数，缺省 1100000"},
        },
        [],
    ),
    _fn(
        "analyze_elastic_born",
        "波恩力学稳定性判断：读 6x6 弹性常数矩阵（GPa），根据主余子式是否全为正判断结构是否力学稳定。缺省用内置 Cu-Zn 示例矩阵。",
        {
            "elastic_out": {"type": "string",
                            "description": "弹性常数输出文件路径（6x6 矩阵文本），缺省用内置示例 elastic.out"},
        },
        [],
    ),
    _fn(
        "plot_born_stability",
        "绘制波恩稳定性 3x2 面板图：C11/C44/C55/C66 弹性常数及二阶/三阶行列式随温度的变化曲线，用于判断结构在不同温度下的力学稳定性。",
        {
            "out": {"type": "string", "description": "输出图片文件名，缺省 Born_Stability_3x2.png"},
        },
        [],
    ),
]
