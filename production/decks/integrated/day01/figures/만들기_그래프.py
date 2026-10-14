"""쿨러 열화 한 건(ALT-hyd01-0014-e0a1)의 유온 TS1 · 냉각 효율 CE 실제 기록 그래프.

데이터: 그래프_데이터_tag_1s.csv — TimescaleDB 표 tag_1s를 SELECT로 읽은 것(시각은 한국 시간).
사건 시각: alerts 표(raised_at · cleared_at), actions 표(issued_at), 처리 기록(A-7-record-text.txt)의 주입 · 승인 시각.
사용: uv run --no-project --with matplotlib python 만들기_그래프.py
"""
import csv
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
font_manager.fontManager.addfont(str(Path.home() / "Library/Fonts/malgun.ttf"))
font_manager.fontManager.addfont(str(Path.home() / "Library/Fonts/malgunbd.ttf"))
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
NAVY, SKY, BLUE, PALE, GREY, MUTED = "#13294B", "#5CB8F2", "#1A6FC4", "#E7F3FD", "#D3D9E1", "#5B6B82"

rows = {"TS1": [], "CE": []}
for t, name, v in csv.reader((HERE / "그래프_데이터_tag_1s.csv").open(encoding="utf-8")):
    if name in rows:
        rows[name].append((datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f"), float(v)))
D = lambda s: datetime.strptime("2026-10-10 " + s, "%Y-%m-%d %H:%M:%S")
t0, t1 = D("11:11:55"), D("11:17:15")
ts = [(t, v) for t, v in rows["TS1"] if t0 <= t <= t1]
ce = [(t, v) for t, v in rows["CE"] if t0 <= t <= t1]
events = [(D("11:12:25"), "쿨러 열화 시작"), (D("11:13:08"), "경보 발생"), (D("11:14:56"), "조치 승인"), (D("11:15:52"), "경보 해제")]

fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.9, 5.0), dpi=220, sharex=True, gridspec_kw=dict(height_ratios=[3, 2], hspace=0.12))
for ax in (a1, a2):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GREY)
    ax.tick_params(colors=MUTED, labelsize=11, length=3, color=GREY)
    ax.grid(axis="y", color="#EDF0F4", linewidth=0.8)
    ax.set_axisbelow(True)
    for i, (t, _) in enumerate(events):
        ax.axvline(t, color=BLUE if i in (1, 2) else GREY, linewidth=1.3, linestyle=(0, (4, 3)))
a1.axvspan(events[1][0], events[2][0], color=PALE, linewidth=0)
a2.axvspan(events[1][0], events[2][0], color=PALE, linewidth=0)

a1.plot(*zip(*ts), color=NAVY, linewidth=2.4)
a1.axhline(55, color=SKY, linewidth=1.4)
a1.set_ylim(44, 68)
a1.set_yticks([45, 50, 55, 60, 65])
a1.set_ylabel("유온 TS1 (℃)", color=NAVY, fontsize=12.5)
a1.text(t1, 55.5, "경보 조건의 기준 55 ℃", ha="right", va="bottom", fontsize=11, color=BLUE)
for i, (t, name) in enumerate(events):
    a1.text(t, 68.4, name, ha="right" if i == 0 else "left" if i == 3 else "center", va="bottom", fontsize=12, color=BLUE if i in (1, 2) else MUTED,
            fontweight="bold" if i in (1, 2) else "normal")
mid = events[1][0] + (events[2][0] - events[1][0]) / 2
a1.text(mid, 46.2, "경보에서 승인까지 108초", ha="center", va="center", fontsize=12.5, color=BLUE, fontweight="bold")
pk = max(ts, key=lambda p: p[1])
a1.annotate(f"최고 {pk[1]:.1f} ℃", xy=pk, xytext=(-6, 7), textcoords="offset points", ha="right", fontsize=11, color=NAVY)

a2.plot(*zip(*ce), color=BLUE, linewidth=2.4)
a2.axhline(70, color=SKY, linewidth=1.4)
a2.set_ylim(35, 95)
a2.set_yticks([40, 55, 70, 85])
a2.set_ylabel("냉각 효율 CE (%)", color=BLUE, fontsize=12.5)
a2.text(t1, 71.5, "경보 조건의 기준 70 %", ha="right", va="bottom", fontsize=11, color=BLUE)
a2.xaxis.set_major_locator(mdates.MinuteLocator())
a2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
a2.set_xlim(t0, t1)
a2.set_xlabel("2026-10-10 시각", color=MUTED, fontsize=11)
fig.subplots_adjust(left=0.09, right=0.985, top=0.93, bottom=0.11)
fig.savefig(HERE / "그래프_쿨러열화_TS1_CE.png", facecolor="white")
print("TS1", len(ts), "CE", len(ce), "peak", pk, "CE min/max", min(v for _, v in ce), max(v for _, v in ce), "CE end", ce[-1])
