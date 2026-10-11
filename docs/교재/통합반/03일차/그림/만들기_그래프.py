"""쿨러 과열 한 건(HYD-01, 원인 쿨러 핀 오염)의 조치 후보 넷과 조치 후 예측 평형 유온.

데이터: 저장소의 판단 결과 고정본 hyd-iot-edu/tests/fixtures/a_cards_before.json(읽기 전용)에서 옮긴 값.
  순위 · 조치 · 예측 평형 유온 = 1 팬 최대 운전 49.8 / 2 부하 70 %와 야간 핀 세척 47.7 / 3 팬 최대 운전과 부하 80 % 44.6 / 4 쿨러 핀 세척 62.5
사용: uv run --no-project --with matplotlib python 만들기_그래프.py
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

cards = [("1순위  팬 최대 운전", 49.8), ("2순위  부하 70 %와 야간 핀 세척", 47.7),
         ("3순위  팬 최대 운전과 부하 80 %", 44.6), ("4순위  쿨러 핀 세척", 62.5)]
X0 = 40

fig, ax = plt.subplots(figsize=(7.9, 5.0), dpi=220)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GREY)
ax.tick_params(colors=MUTED, labelsize=13.5, length=3, color=GREY)
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color="#EDF0F4", linewidth=0.8)
ax.set_axisbelow(True)
ys = [3, 2, 1, 0]
BB = dict(facecolor="white", edgecolor="none", pad=2)
for (name, v), y in zip(cards, ys):
    hot = y == 3
    low = v == min(c[1] for c in cards)
    ax.barh(y, v - X0, left=X0, height=0.46, color=BLUE if hot else SKY if low else GREY, edgecolor=NAVY, linewidth=1.2)
    ax.text(X0 + 0.2, y + 0.31, name, ha="left", va="bottom", fontsize=15, color=NAVY, fontweight="bold" if hot else "normal")
    ax.text(v + 0.4, y, f"{v:.1f} ℃", ha="left", va="center", fontsize=15, color=NAVY, fontweight="bold", bbox=BB, zorder=6)
ax.plot([55, 55], [-0.5, 3.95], color=BLUE, linewidth=1.4, linestyle=(0, (4, 3)), zorder=1)
ax.plot([65, 65], [-0.5, 3.95], color=NAVY, linewidth=1.4, linestyle=(0, (4, 3)), zorder=1)
BB = dict(facecolor="white", edgecolor="none", pad=2)
ax.text(55, 4.02, "경보 조건의 기준 55 ℃", ha="center", va="bottom", fontsize=13.5, color=BLUE, bbox=BB, zorder=6)
ax.text(65, 4.02, "인터록 65 ℃", ha="center", va="bottom", fontsize=13.5, color=NAVY, bbox=BB, zorder=6)
ax.set_xlim(X0, 68.5)
ax.set_ylim(-0.5, 4.35)
ax.set_yticks([])
ax.set_xticks([40, 45, 50, 55, 60, 65])
ax.set_xlabel("조치 후 예측 평형 유온 (℃)", color=MUTED, fontsize=13.5)
fig.subplots_adjust(left=0.03, right=0.985, top=0.93, bottom=0.12)
fig.savefig(HERE / "그래프_조치후보_예측유온.png", facecolor="white")
print("saved")
