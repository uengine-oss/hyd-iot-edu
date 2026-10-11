"""경보가 나는 순간의 유온 TS1(실제 기록). 데이터는 그래프_데이터_tag_1s.csv(TimescaleDB tag_1s를 SELECT로 읽은 것)."""
import csv
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager
HERE = Path(__file__).resolve().parent
for f in ("malgun.ttf", "malgunbd.ttf"):
    font_manager.fontManager.addfont(str(Path.home() / "Library/Fonts" / f))
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
NAVY, SKY, BLUE, PALE, GREY, MUTED = "#13294B", "#5CB8F2", "#1A6FC4", "#E7F3FD", "#D3D9E1", "#5B6B82"
ts = []
for t, name, v in csv.reader((HERE / "그래프_데이터_tag_1s.csv").open(encoding="utf-8")):
    if name == "TS1":
        ts.append((datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f"), float(v)))
D = lambda s: datetime.strptime("2026-10-10 " + s, "%Y-%m-%d %H:%M:%S")
t0, t1 = D("11:12:40"), D("11:13:20")
ts = [(t, v) for t, v in ts if t0 <= t <= t1]
cross = next(t for t, v in ts if v > 55)
alert = datetime.strptime("2026-10-10 11:13:08.508", "%Y-%m-%d %H:%M:%S.%f")
fig, ax = plt.subplots(figsize=(7.9, 5.0), dpi=220)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color(GREY)
ax.tick_params(colors=MUTED, labelsize=11, length=3, color=GREY)
ax.grid(axis="y", color="#EDF0F4", linewidth=0.8); ax.set_axisbelow(True)
ax.axvspan(cross, alert, color=PALE, linewidth=0)
ax.axvline(cross, color=GREY, linewidth=1.3, linestyle=(0, (4, 3)))
ax.axvline(alert, color=BLUE, linewidth=1.3, linestyle=(0, (4, 3)))
ax.plot(*zip(*ts), color=NAVY, linewidth=2.6, marker="o", markersize=3.5)
ax.axhline(55, color=SKY, linewidth=1.4)
ax.set_ylim(49, 59); ax.set_xlim(t0, t1)
ax.set_ylabel("유온 TS1 (℃)", color=NAVY, fontsize=12.5)
ax.text(t0, 55.15, " 경보 조건의 기준 55 ℃", ha="left", va="bottom", fontsize=11, color=BLUE)
ax.text(cross, 59.15, "기준을 넘음 ", ha="right", va="bottom", fontsize=12, color=MUTED)
ax.text(alert, 59.15, " 경보 발생", ha="left", va="bottom", fontsize=12, color=BLUE, fontweight="bold")
ax.text(cross + (alert - cross) / 2, 49.6, "조건이\n이어진 시간", ha="center", va="bottom", fontsize=11, color=BLUE, fontweight="bold")
ax.xaxis.set_major_locator(mdates.SecondLocator(bysecond=[0, 10, 20, 30, 40, 50]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
ax.set_xlabel("2026-10-10 실제 시각", color=MUTED, fontsize=11)
fig.subplots_adjust(left=0.1, right=0.985, top=0.92, bottom=0.12)
fig.savefig(HERE / "그래프_경보순간_TS1.png", facecolor="white")
print("cross", cross, "alert", alert, "sec", (alert - cross).total_seconds())
