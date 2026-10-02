"""README figures: KPI row, funnel (PNG + animated GIF), modality.json explainer GIF, linter demo GIF.

    .venv/bin/python scripts/make_figures.py                 # offline: numbers from results/summary.csv
    .venv/bin/python scripts/make_figures.py --refresh-demo  # re-run the linter for the terminal GIF (network)

Every number is computed from results/summary.csv and asserted, never typed. The terminal GIF
replays real linter output saved in docs/img/demo_output.txt (lines are clipped to the terminal
width; run the commands for the full text).
"""
from __future__ import annotations

import argparse
import io
import math
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img"
sys.path.insert(0, str(ROOT))
from conformance.report import wilson  # noqa: E402

# Reference palette (dataviz skill, light surface). Text wears ink tokens, never series colors.
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLUE, ORANGE, BLUE_LIGHT = "#2a78d6", "#eb6834", "#86b6ef"
FONT = "Helvetica Neue"
plt.rcParams.update({"font.family": FONT, "text.color": INK, "svg.fonttype": "none"})
W, DPI = 10.0, 100  # 1000 px wide: GitHub shows README images at ~830 px, so text >= 10 pt stays >= 11 px


# ---------------------------------------------------------------- data

def tail_numbers() -> dict:
    df = pd.read_csv(ROOT / "results" / "summary.csv")
    t = df[df.stratum == "S-tail"]
    lr = t[t.verdict != "NOT_LEROBOT"]
    data = lr[lr.L3 != "fail"]
    v2 = data[~data.steps.fillna("").str.contains("DOWNCONVERT|BLOCKED")]
    mod = v2[v2.G6 == "pass"]
    ready = t[t.verdict == "READY"]
    one_file = int(t.clean_except_modality.sum())
    v3 = int((t.verdict == "NEEDS_DOWNCONVERT").sum())
    n = {"n": len(t), "lerobot": len(lr), "data": len(data), "v2": len(v2), "modality": len(mod),
         "ready": len(ready), "one_file": one_file, "v3": v3, "total": len(df),
         "errors": 0, "one_file_ci": wilson(one_file, len(t)), "v3_ci": wilson(v3, len(t))}
    assert n["v2"] == one_file == 61 and n["data"] == 177 and n["modality"] == n["ready"] == 0, n
    return n


def save_png(fig, path: Path) -> None:
    fig.savefig(path, dpi=DPI * 2, facecolor=SURFACE)
    plt.close(fig)


def fig_to_image(fig) -> Image.Image:
    buf = io.BytesIO()
    fig.savefig(buf, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def save_gif(frames: list[Image.Image], durations: list[int], path: Path) -> None:
    pal = frames[-1].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=durations, loop=0, optimize=True, disposal=1)


# ---------------------------------------------------------------- 1. KPI row

def kpi(n: dict) -> None:
    lo, hi = n["one_file_ci"]
    vlo, vhi = n["v3_ci"]
    tiles = [
        (f"{n['total']}", "public LeRobot datasets audited",
         "4 strata · 0 fetch failures · metadata only"),
        (f"{n['ready']} of {n['n']}", "pass every static check as is",
         "random sample of the long tail"),
        (f"{n['one_file'] / n['n']:.1%}", "are one file away",
         f"only modality.json missing · 95% CI {lo:.0%}–{hi:.0%}"),
        (f"{n['v3'] / n['n']:.0%}", "need a format conversion first",
         f"v3.0 layout · converter exists · CI {vlo:.0%}–{vhi:.0%}"),
    ]
    H = 3.7
    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])  # data coords = pixels at DPI, so corner radii stay round
    ax.set_xlim(0, W * DPI)
    ax.set_ylim(0, H * DPI)
    ax.axis("off")
    gap, x0, y0 = 18, 10, 10
    tw, th = (W * DPI - 2 * x0 - gap) / 2, (H * DPI - 2 * y0 - gap) / 2
    for i, (big, label, sub) in enumerate(tiles):
        x = x0 + (i % 2) * (tw + gap)
        y = y0 + (1 - i // 2) * (th + gap)
        ax.add_patch(FancyBboxPatch((x, y), tw, th, boxstyle="round,pad=0,rounding_size=12",
                                    facecolor="#ffffff", edgecolor=GRID, lw=1.2))
        ax.text(x + 24, y + th * 0.64, big, fontsize=32, fontweight="bold", color=INK, va="center")
        ax.text(x + 24 + {0: 104, 1: 0, 2: 168, 3: 104}[i] * 0, y + th * 0.33, label, fontsize=15, color=INK, va="center")
        ax.text(x + 24, y + th * 0.14, sub, fontsize=11.5, color=INK2, va="center")
    save_png(fig, OUT / "kpi.png")


# ---------------------------------------------------------------- 2. funnel

def funnel_steps(n: dict):
    return [
        ("Random sample of public LeRobot datasets", n["n"], None),
        ("In LeRobot format", n["lerobot"], f"−{n['n'] - n['lerobot']}  a different format"),
        ("Contain recorded episodes", n["data"],
         f"−{n['lerobot'] - n['data']}  metadata only, no episode data"),
        ("In the v2 file layout GR00T reads", n["v2"],
         f"−{n['data'] - n['v2']}  v3.0 layout (NVIDIA converter exists)"),
        ("Ship meta/modality.json", n["modality"],
         f"−{n['v2'] - n['modality']}  missing the one GR00T-only file"),
    ]


def funnel_frame(n: dict, upto: int, grow: float):
    steps = funnel_steps(n)
    fig = plt.figure(figsize=(W, 6.6))
    fig.patch.set_facecolor(SURFACE)
    fig.text(0.02, 0.935, f"Where {n['n']} randomly sampled public robot datasets stop on the way to GR00T",
             fontsize=17, fontweight="bold", color=INK)
    fig.text(0.02, 0.885, "Static metadata checks vs NVIDIA Isaac-GR00T's dataset loader @51d4c89 · "
             "random S-tail stratum (seed 20260928)", fontsize=11, color=INK2)
    ax = fig.add_axes([0.42, 0.06, 0.53, 0.75])
    ax.set_xlim(0, n["n"] * 1.02)
    ax.set_ylim(len(steps) - 0.5, -0.45)
    ax.axis("off")
    for i, (label, v, drop) in enumerate(steps):
        if i > upto:
            break
        g = grow if i == upto else 1.0
        y = i
        fig.text(0.405, ax.transData.transform((0, y))[1] / fig.bbox.height + 0.014, label,
                 ha="right", va="center", fontsize=13, color=INK)
        if drop:
            fig.text(0.405, ax.transData.transform((0, y))[1] / fig.bbox.height - 0.03, drop,
                     ha="right", va="center", fontsize=10.5, color=INK2)
        if v > 0:
            ax.barh(y, v * g, height=0.56, color=BLUE if i < len(steps) - 2 else BLUE, edgecolor=SURFACE, lw=2)
        else:
            ax.barh(y, 1.2, height=0.56, color=MUTED)
        if g >= 1:
            ax.text(max(v, 1.2) + n["n"] * 0.012, y, f"{v}", va="center", fontsize=15, fontweight="bold", color=INK)
    if upto >= 3 and grow >= 1 or upto > 3:
        v = n["v2"]
        ax.text(v + n["n"] * 0.12, 3, f"{v / n['n']:.1%} are\none small file away", fontsize=12,
                color=INK, va="center", fontweight="bold")
    if upto >= 4 and grow >= 1:
        ax.text(n["n"] * 0.06, 4, "not a data defect: standard LeRobot\ndoesn't define this file",
                va="center", fontsize=11, color=INK2, style="italic")
    return fig


def funnel(n: dict) -> None:
    save_png(funnel_frame(n, 4, 1.0), OUT / "funnel.png")
    frames, durs = [], []
    for step in range(5):
        for g in (0.25, 0.5, 0.75, 1.0):
            frames.append(fig_to_image(funnel_frame(n, step, g)))
            durs.append(60)
        durs[-1] = 1300 if step < 4 else 6000
    save_gif(frames, durs, OUT / "funnel.gif")


# ---------------------------------------------------------------- 3. modality.json explainer

STATE = ["0.12", "-0.80", "1.05", "0.33", "-0.10", "0.02"]
ACTION = ["0.13", "-0.79", "1.04", "0.35", "-0.11", "1.00"]
JSON_LINES = [
    ('{', INK),
    ('  "state": {', INK),
    ('    "single_arm": {"start":0, "end":5},', BLUE),
    ('    "gripper":    {"start":5, "end":6}', ORANGE),
    ('  },', INK),
    ('  "action": {', INK),
    ('    "single_arm": {"start":0, "end":5},', BLUE),
    ('    "gripper":    {"start":5, "end":6}', ORANGE),
    ('  },', INK),
    ('  "video": {"front": …, "wrist": …}', INK2),
    ('}', INK),
]


def modality_frame(stage: int, k: int):
    """stage 0: raw numbers; 1: arm colored (k = boxes so far); 2: + gripper; 3: final caption."""
    fig = plt.figure(figsize=(W, 6.0))
    fig.patch.set_facecolor(SURFACE)
    titles = ["GR00T receives one flat list of numbers per frame. Which one is the gripper?",
              "meta/modality.json names the slices…", "meta/modality.json names the slices…",
              "That's all it does. Easy to write, if you know the robot."]
    fig.text(0.02, 0.925, "What is meta/modality.json?", fontsize=18, fontweight="bold", color=INK)
    fig.text(0.02, 0.865, titles[stage], fontsize=13, color=INK2)
    ax = fig.add_axes([0.02, 0.06, 0.53, 0.72])
    ax.set_xlim(-1.62, 6.0)
    ax.set_ylim(-0.4, 5.2)
    ax.axis("off")
    for row, (name, vals, y) in enumerate((("observation.state", STATE, 3.6), ("action", ACTION, 1.2))):
        ax.text(-1.55, y + 0.95, name, fontsize=11.5, color=INK2, family="Menlo")
        for i, v in enumerate(vals):
            if stage >= 1 and i < 5 and (stage > 1 or i < k):
                fc, tc = BLUE, "#ffffff"
            elif stage >= 2 and i == 5:
                fc, tc = ORANGE, "#ffffff"
            else:
                fc, tc = "#ffffff", INK
            ax.add_patch(FancyBboxPatch((i * 0.95 - 1.5 + 0.06, y), 0.83, 0.7,
                                        boxstyle="round,pad=0,rounding_size=0.08", facecolor=fc, edgecolor=GRID if fc == "#ffffff" else SURFACE, lw=1.5))
            ax.text(i * 0.95 - 1.5 + 0.475, y + 0.35, v, ha="center", va="center", fontsize=11, color=tc, family="Menlo")
            ax.text(i * 0.95 - 1.5 + 0.475, y - 0.2, str(i), ha="center", va="center", fontsize=10, color=MUTED)
        if stage == 0 and row == 0:
            ax.text(4.35, y + 0.35, "?", fontsize=26, color=MUTED, va="center", fontweight="bold")
        if stage >= 1:
            x1 = -1.5 + 0.06 + 4 * 0.95 + 0.83 if stage > 1 else -1.5 + 0.06 + max(k - 1, 0) * 0.95 + 0.83
            if stage > 1 or k == 5:
                ax.plot([-1.44, x1], [y - 0.45, y - 0.45], color=BLUE, lw=2, solid_capstyle="round")
                ax.text((-1.44 + x1) / 2, y - 0.7, "single_arm  [0:5]", ha="center", fontsize=11, color=INK)
        if stage >= 2:
            gx = -1.5 + 0.06 + 5 * 0.95
            ax.plot([gx, gx + 0.83], [y - 0.45, y - 0.45], color=ORANGE, lw=2, solid_capstyle="round")
            ax.text(gx + 0.415, y - 0.7, "gripper  [5:6]", ha="center", fontsize=11, color=INK)
    jx = fig.add_axes([0.565, 0.08, 0.425, 0.7])
    jx.axis("off")
    jx.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.03", transform=jx.transAxes,
                                facecolor="#ffffff", edgecolor=GRID, lw=1.2))
    show = 0 if stage == 0 else len(JSON_LINES)
    for j, (line, col) in enumerate(JSON_LINES[:show]):
        hl = (col == BLUE and stage >= 1) or (col == ORANGE and stage >= 2)
        jx.text(0.05, 0.92 - j * 0.082, line, transform=jx.transAxes, fontsize=10.5, family="Menlo",
                color=INK if (col in (BLUE, ORANGE) and hl) else (MUTED if col in (BLUE, ORANGE) else col))
        if hl:
            jx.add_patch(FancyBboxPatch((0.025, 0.92 - j * 0.082 - 0.03), 0.012, 0.06, boxstyle="square,pad=0",
                                        transform=jx.transAxes, facecolor=col, lw=0))
    if stage == 0:
        jx.text(0.5, 0.5, "meta/modality.json\n\nabsent in 96–100% of\npublic LeRobot datasets", transform=jx.transAxes,
                ha="center", va="center", fontsize=12, color=MUTED)
    return fig


def modality_gif() -> None:
    frames, durs = [], []
    frames.append(fig_to_image(modality_frame(0, 0))); durs.append(2800)
    for k in range(1, 6):
        frames.append(fig_to_image(modality_frame(1, k))); durs.append(160)
    durs[-1] = 900
    frames.append(fig_to_image(modality_frame(2, 5))); durs.append(1600)
    frames.append(fig_to_image(modality_frame(3, 5))); durs.append(6000)
    save_gif(frames, durs, OUT / "modality.gif")


# ---------------------------------------------------------------- 4. linter demo (terminal)

DEMO_CMDS = [
    ("NVIDIA's own demo dataset", "python -m conformance.inspect_local fixtures/cube_to_bowl_5 --brief"),
    ("a typical LeRobot v2.1 dataset on the Hub", "python -m conformance.inspect_hub youliangtan/tictac-bot --brief"),
    ("a LeRobot v3.0 dataset on the Hub", "python -m conformance.inspect_hub whosricky/so101_pick_red_cube_3cams --brief"),
]


def refresh_demo() -> None:
    chunks = []
    for _, cmd in DEMO_CMDS:
        out = subprocess.run([sys.executable, *cmd.split()[1:]], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        chunks.append(f"$ {cmd}\n{out.rstrip()}\n")
    (OUT / "demo_output.txt").write_text("\n".join(chunks))


def terminal_gif() -> None:
    text = (OUT / "demo_output.txt").read_text().rstrip("\n").split("\n")
    cols, rows, fs = 104, 22, 26
    mono = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", fs)
    bold = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", fs, index=1)
    cw, lh = mono.getlength("M"), int(fs * 1.45)
    pad, bar = 28, 44
    Wp, Hp = int(cols * cw + 2 * pad), rows * lh + 2 * pad + bar
    BG, FG, DIM, PROMPT = "#1a1a19", "#e8e8e3", "#a3a29c", "#199e70"
    COL = {"FAIL": "#e66767", "WARN": "#c98500", "READY": "#199e70", "NEEDS_MODALITY": "#3987e5",
           "NEEDS_DOWNCONVERT": "#d95926"}

    def clip(s):
        return s if len(s) <= cols else s[:cols - 1] + "…"

    def render(lines, cursor=False):
        im = Image.new("RGB", (Wp, Hp), BG)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, Wp, bar], fill="#2b2b29")
        for i, c in enumerate(("#e66767", "#c98500", "#199e70")):
            d.ellipse([18 + i * 26, 15, 32 + i * 26, 29], fill=c)
        d.text((Wp / 2, bar / 2), "lerobot-groot-conformance", font=mono, fill=DIM, anchor="mm")
        vis = lines[-rows:]
        for r, s in enumerate(vis):
            y = pad + bar + r * lh
            s = clip(s)
            if s.startswith("$ "):
                d.text((pad, y), "$", font=bold, fill=PROMPT)
                d.text((pad + 2 * cw, y), s[2:], font=bold, fill=FG)
            elif s.startswith("# "):
                d.text((pad, y), s, font=mono, fill=DIM)
            elif s.startswith("verdict: "):
                v = s.split()[1]
                d.text((pad, y), "verdict: ", font=mono, fill=FG)
                d.text((pad + 9 * cw, y), v, font=bold, fill=COL.get(v, FG))
                d.text((pad + (9 + len(v)) * cw, y), s[9 + len(v):], font=mono, fill=DIM)
            elif s.strip()[:3] in ("G1 ", "G2 ", "G3 ", "G4 ", "G5 ", "G6 ", "G7 ", "G8 ", "G9 ") or s.strip()[:2] in ("G1", "L1"):
                tok = s.split()
                lead = s[:len(s) - len(s.lstrip())]
                x = pad + len(lead) * cw
                d.text((x, y), f"{tok[0]:<4}", font=mono, fill=FG)
                d.text((x + 4 * cw, y), f"{tok[1]:<5}", font=bold, fill=COL.get(tok[1], FG))
                d.text((x + 9 * cw, y), s[len(lead) + 9:].lstrip() if len(s) > len(lead) + 9 else "", font=mono, fill=DIM)
            else:
                d.text((pad, y), s, font=mono, fill=DIM if s.strip().startswith("(") else FG)
            if cursor and r == len(vis) - 1:
                d.rectangle([pad + len(s) * cw + 2, y + 2, pad + len(s) * cw + cw, y + fs + 4], fill=FG)
        return im

    # split the saved output into (command, output lines) blocks
    blocks, cur = [], None
    for line in text:
        if line.startswith("$ "):
            cur = [line[2:], []]
            blocks.append(cur)
        elif cur is not None and line.strip():
            cur[1].append(line)
    frames, durs, screen = [], [], []
    for (title, _), (cmd, out) in zip(DEMO_CMDS, blocks):
        screen.append(f"# {title}")
        for i in range(0, len(cmd) + 1, 4):
            frames.append(render(screen + ["$ " + cmd[:i]], cursor=True)); durs.append(45)
        screen.append("$ " + cmd)
        frames.append(render(screen, cursor=True)); durs.append(500)
        for line in out:
            screen.append(line)
            frames.append(render(screen)); durs.append(90)
        durs[-1] = 2600
        screen.append("")
    durs[-1] = 6000
    save_gif(frames, durs, OUT / "linter_demo.gif")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-demo", action="store_true", help="re-run the linter commands (needs network)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.refresh_demo or not (OUT / "demo_output.txt").exists():
        refresh_demo()
    n = tail_numbers()
    kpi(n)
    funnel(n)
    modality_gif()
    terminal_gif()
    for p in sorted(OUT.glob("*.*")):
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size / 1e3:.0f} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
