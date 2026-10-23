"""39장(집계 방식): 같은 24시간에 얻은 설비별 인터록 여유 셋과 그 평균 · 목표값.

데이터: `문서/교재/사실표/통합반_02-04일차_기술사실표.md:626`(GET /api/kpi?period=24h, 2026-10-11) —
  HYD-01 2.53 · HYD-02 16.72 · HYD-03 14.55 ℃. 평균 11.27 ℃ = (2.53 + 16.72 + 14.55) ÷ 3
  (`.evidence/수정_03/계산_시험_실측.md`, Python statistics.mean 11.266…), 목표 10 ℃(`it/neo4j/v2/instances.cypher:53`).
  KPI 실적은 최솟값(`it/process/procsvc/kpi.py:224-243`).
꼴 · 색 · 글꼴은 같은 폴더의 `만들기_그래프.py`(조치 후보 예측 유온 그래프)와 같다.
사용: uv run --no-project --with matplotlib python 만들기_그래프_재구성.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
font_manager.fontManager.addfont(str(Path.home() / "Library/Fonts/malgun.ttf"))
font_manager.fontManager.addfont(str(Path.home() / "Library/Fonts/malgunbd.ttf"))
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
NAVY, SKY, BLUE, PALE, GREY, MUTED = "#13294B", "#5CB8F2", "#1A6FC4", "#E7F3FD", "#D3D9E1", "#5B6B82"

margins = [("HYD-01", 2.53), ("HYD-02", 16.72), ("HYD-03", 14.55)]
TARGET = 10.0
MEAN = round(sum(v for _, v in margins) / len(margins), 2)        # 11.27

fig, ax = plt.subplots(figsize=(7.9, 5.0), dpi=220)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GREY)
ax.tick_params(colors=MUTED, labelsize=13.5, length=3, color=GREY)
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color="#EDF0F4", linewidth=0.8)
ax.set_axisbelow(True)
BB = dict(facecolor="white", edgecolor="none", pad=2)
low = min(v for _, v in margins)
for (name, v), y in zip(margins, (2, 1, 0)):
    hot = v == low                                                 # 한계에 가장 가까운 설비(최솟값)
    ax.barh(y, v, left=0, height=0.46, color=BLUE if hot else GREY, edgecolor=NAVY, linewidth=1.2, zorder=2)
    ax.text(0.15, y + 0.31, name, ha="left", va="bottom", fontsize=15, color=NAVY, fontweight="bold" if hot else "normal")
    ax.text(v + 0.3, y, f"{v:.2f} ℃", ha="left", va="center", fontsize=15, color=NAVY, fontweight="bold", bbox=BB, zorder=6)
ax.plot([TARGET, TARGET], [-0.5, 2.62], color=BLUE, linewidth=1.4, linestyle=(0, (4, 3)), zorder=3)
ax.plot([MEAN, MEAN], [-0.5, 2.62], color=NAVY, linewidth=1.4, linestyle=(0, (4, 3)), zorder=3)
ax.text(TARGET - 0.15, 2.68, f"목표 {TARGET:g} ℃", ha="right", va="bottom", fontsize=13.5, color=BLUE, bbox=BB, zorder=6)
ax.text(MEAN + 0.15, 2.68, f"평균 {MEAN:.2f} ℃", ha="left", va="bottom", fontsize=13.5, color=NAVY, bbox=BB, zorder=6)
ax.set_xlim(0, 20.5)
ax.set_ylim(-0.5, 3.05)
ax.set_yticks([])
ax.set_xticks([0, 5, 10, 15, 20])
ax.set_xlabel("설비별 인터록 여유 (℃) · 같은 24시간", color=MUTED, fontsize=13.5)
fig.subplots_adjust(left=0.03, right=0.985, top=0.93, bottom=0.12)
fig.savefig(HERE / "그래프_설비별여유_집계.png", facecolor="white")
print("saved", MEAN)
