# -*- coding: utf-8 -*-
"""hyd-iot-edu 마스터_가이드 전체 아키텍처 그림(ceco_demo 생성기에서 데이터만 바꿈)(위 → 아래) SVG 생성기.
부품 번호는 docs/시스템_아키텍처.html 과 같다(①~㊱). 좌표는 손으로 정한 4열 격자:
  L 70–330 · S(척추) 420–720 · R 790–1000 · M(감시 레일) 1040–1180
사용: python master_arch_svg.py > arch.svg
"""
import html

W, H = 1200, 1905
CIRC = {i: chr(0x2460 + i - 1) for i in range(1, 21)}
CIRC.update({i: chr(0x3251 + i - 21) for i in range(21, 36)})
CIRC[36] = chr(0x32B1)

ZONES = [  # id, y0, y1, 이름, 설명, 배경, 테두리
    ("z0", 10, 150, "L1 · 현장", "유압 설비 3대 + PLC", "#f3f1ec", "#b9ae98"),
    ("z2", 160, 380, "L2 · L6 · OT 공장 망 (ot-net)", "IT가 멈춰도 여기는 돈다", "#fcefe2", "#cf8a45"),
    ("z3", 390, 560, "L3 · DMZ 역할", "두 망에 동시에 붙은 서비스 2개 (전용 망·방화벽은 없음)", "#f0ecf8", "#8a76bf"),
    ("z4", 570, 935, "L3~L6 · IT 데이터 (it-net)", "장부 · 검사 · 기록 · 화면", "#e7f3f6", "#3f8ea3"),
    ("z5", 945, 1155, "L7 · L8 · 지식과 AI", "원인을 찾고 조치를 제안", "#ebeffa", "#5a6fbf"),
    ("z6", 1165, 1475, "L9 · 업무 프로세스와 사람", "승인은 사람이", "#f2f4ec", "#7a8a4a"),
]
ZDARK = dict(z0="#6b604a", z2="#9a5a1c", z3="#5b4691", z4="#1f6378", z5="#394b98", z6="#56662a")
W, H = 1200, 1485
C = dict(data="#1f6f8b", req="#d1343f", disp="#7b4fc9", mon="#7d8890", once="#8f989f", human="#2b2f33")

B = {}
def box(key, no, x, y, w, h, title, prod="", desc="", kind="normal", badge=""):
    B[key] = dict(no=no, x=x, y=y, w=w, h=h, title=title, prod=prod, desc=desc, kind=kind, badge=badge)

box("sim", 1, 420, 45, 300, 86, "설비 3대 + PLC + 데이터 수집", "plant-sim (Python)", "HYD-01~03 · 1초마다 발행 · 65 ℃ 트립")
box("emqx", 2, 420, 200, 300, 86, "EMQX (공장 게시판)", "MQTT 브로커 5.8", "온도 QoS 0 · 상태 QoS 1 retain")
box("fuxa", 3, 790, 200, 210, 86, "운전실 화면", "FUXA · SCADA", "값 · 알람 · 수동 조작")
box("oper", 0, 1040, 225, 140, 34, "운전원", kind="pill")
box("finit", 18, 800, 312, 190, 50, "화면 넣기", "기동 때 1회", kind="once")
box("gw", 4, 330, 430, 230, 96, "명령 게이트웨이", "cmd-gateway (Python)", "유일한 하향 통로 · 검사 5가지")
box("ing", 5, 590, 430, 230, 96, "수집 다리", "connect-ingest (Python)", "MQTT → Kafka · 대기열 2만 건")
box("det", 7, 70, 620, 260, 90, "검사관 (detector)", "Python · L4", "기울기 · 이상 점수 · CEP 경보")
box("rp", 6, 420, 620, 300, 90, "Redpanda (Kafka 장부)", "토픽 7개 · 디스크 보관", "온도 1일 · 경보 365일 · 감사 5년")
box("sink", 8, 790, 632, 210, 66, "저장 심부름꾼", "connect-sink (Python)")
box("tinit", 19, 70, 740, 260, 50, "토픽 만들기", "기동 때 1회", kind="once")
box("tsdb", 9, 790, 760, 210, 86, "기록 DB", "TimescaleDB · L5", "1초 값 3일 · 1분 요약 30일")
box("prom", 11, 1040, 632, 140, 66, "Prometheus", "선택 · 감시", kind="once")
box("graf", 10, 1040, 770, 140, 66, "Grafana", "추세 화면 · L6")
box("cons", 21, 1040, 862, 140, 56, "Console", "Redpanda · 선택", kind="once")
box("neo", 12, 70, 985, 260, 86, "온톨로지 (Neo4j)", "L7 · 지식 그래프", "원인·증거·조치·SOP 관계")
box("seed", 20, 70, 1090, 260, 50, "지식 채우기", "기동 때 1회", kind="once")
box("agent", 13, 420, 985, 300, 96, "AI 에이전트", "Python · L8", "원인 추정 · 조치 카드 · 가드레일")
box("llm", 17, 1030, 995, 160, 70, "LLM", "선택 · 밖(인터넷)", "요약문만 작성", kind="ext")
box("proc", 14, 420, 1205, 300, 96, "업무 프로세스 (process)", "미니 BPMN · L9", "사건 → 승인 → 명령 → 재관측")
box("ent", 15, 790, 1205, 210, 96, "기업 시스템 목업", "enterprise-sim", "ERP·MES·CMMS·QMS·SCM·EMS")
box("portal", 16, 420, 1345, 300, 66, "포털 화면", "nginx · 정적 SPA", "사건 · 카드 · 승인 버튼")
box("staff", 0, 490, 1432, 160, 30, "담당자 (브라우저)", kind="pill")

E = []
def line(kind, pts, arrow="end", dot="start", labels=(), width=None):
    E.append(dict(kind=kind, pts=pts, arrow=arrow, dot=dot, labels=list(labels), width=width))

# 현장 ↔ 게시판
line("data", [(660, 131), (660, 200)], "end", "start", [(670, 146, "값 발행 · 1초", "start")])
line("req", [(480, 200), (480, 131)], "end", "end", [(470, 146, "명령 받기 (cmd/auto)", "end")])
# 운전실
line("data", [(790, 232), (720, 232)], "both", "start", [(755, 224, "구독·조작", "middle")])
line("disp", [(720, 266), (790, 266)], "end", "end", [(755, 282, "경보", "middle")])
line("human", [(1040, 242), (1000, 242)], "end", "start")
line("once", [(895, 312), (895, 286)], "end", "start")
# 게시판 ↔ DMZ 역할
line("data", [(660, 286), (660, 430)], "end", "end", [(670, 360, "구독: 값·상태 (QoS 0/1)", "start")])
line("req", [(480, 430), (480, 286)], "end", "start", [(470, 360, "명령 발행 (QoS 1)", "end")])
line("disp", [(540, 430), (540, 286)], "end", "start", [(548, 405, "경보 retain", "start")])
# DMZ 역할 ↔ 장부
line("data", [(660, 526), (660, 620)], "end", "start", [(670, 578, "값 → 토픽 plant.tag", "start")])
line("req", [(480, 620), (480, 526)], "end", "end", [(470, 578, "action.cmd 읽기", "end")])
line("disp", [(540, 620), (540, 526)], "end", "end", [(548, 600, "alerts 읽기", "start")])
# IT 데이터
line("data", [(330, 665), (420, 665)], "both", "start", [(375, 657, "온도", "middle"), (375, 681, "경보", "middle")])
line("once", [(330, 765), (398, 765), (398, 692), (420, 692)], "end", "start")
line("data", [(790, 665), (720, 665)], "start", "start", [(755, 657, "읽기", "middle")])
line("data", [(895, 698), (895, 760)], "end", "start", [(905, 732, "모아 쓰기", "start")])
line("data", [(1040, 803), (1000, 803)], "start", "start")
# 지식·AI
line("data", [(570, 710), (570, 985)], "end", "end", [(578, 860, "경보(RAISE)가", "start"), (578, 876, "에이전트를 깨움", "start")])
line("data", [(420, 1028), (330, 1028)], "both", "start", [(375, 1020, "조회", "middle")])
line("data", [(720, 1000), (762, 1000), (762, 820), (790, 820)], "start", "start", [(770, 900, "증거 조회(SQL)", "start")])
line("data", [(720, 1045), (1030, 1045)], "both", "start", [(1020, 1037, "요약만 (선택)", "end")])
line("data", [(720, 1066), (895, 1066), (895, 1205)], "start", "start", [(905, 1150, "기업 데이터 조회", "start")])
line("once", [(200, 1090), (200, 1071)], "end", "start")
# 업무 · 사람
line("data", [(570, 1081), (570, 1205)], "end", "start", [(578, 1150, "조치 카드 제출", "start")])
line("req", [(420, 1235), (372, 1235), (372, 705), (420, 705)], "end", "start", [(364, 880, "승인된 명령", "end"), (364, 896, "action.cmd · 120초 만료", "end")])
line("data", [(420, 1280), (345, 1280), (345, 1060), (330, 1060)], "end", "start", [(337, 1300, "사례 기록", "end")])
line("data", [(720, 1253), (790, 1253)], "both", "start", [(755, 1245, "실행", "middle")])
line("data", [(570, 1345), (570, 1301)], "both", "start")
line("human", [(570, 1432), (570, 1411)], "end", "start")

ROUTERS = []
ROUTER_PORT_NOTE = []

def esc(t): return html.escape(t, quote=True)

def text(x, y, t, size=13, weight=400, fill="#1d2830", anchor="start", extra=""):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{esc(t)}</text>'

out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="hyd-iot-edu 전체 아키텍처: 현장에서 업무까지 위에서 아래로" class="arch">']
out.append('<defs>')
for k, col in C.items():
    out.append(f'<marker id="a-{k}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
out.append('</defs>')
out.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

for zid, y0, y1, name, desc, bg, bd in ZONES:
    out.append(f'<rect x="6" y="{y0}" width="{W-12}" height="{y1-y0}" rx="14" fill="{bg}" stroke="{bd}" stroke-width="1.4"/>')
    out.append(f'<text x="22" y="{y0 + 27}" font-size="17" font-weight="700" fill="{ZDARK[zid]}">{esc(name)}<tspan font-size="13" font-weight="400" fill="#4b5963" dx="10">{esc(desc)}</tspan></text>')

# 선(후광 먼저, 그다음 선)
def pts_str(p): return " ".join(f"{x},{y}" for x, y in p)
STY = dict(data=("", 2.2), req=("", 3.0), disp=("7 4", 2.2), mon=("2 4", 1.6), once=("9 5", 1.5), human=("", 1.6))
for e in E:
    out.append(f'<polyline points="{pts_str(e["pts"])}" fill="none" stroke="#ffffff" stroke-width="7" stroke-linejoin="round" opacity="0.9"/>')
def shorten(p, which, d):
    p = list(p)
    if which == "end": (x0, y0), (x1, y1) = p[-2], p[-1]
    else: (x0, y0), (x1, y1) = p[1], p[0]
    L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 or 1
    nx, ny = x1 - (x1 - x0) / L * d, y1 - (y1 - y0) / L * d
    if which == "end": p[-1] = (nx, ny)
    else: p[0] = (nx, ny)
    return p
for e in E:
    p = e["pts"]
    for w in ("start", "end"):
        if e["arrow"] in (w, "both"):
            p = shorten(p, w, 7 if e["dot"] == w else 1.5)
    e["draw"] = p
for e in E:
    dash, wd = STY[e["kind"]]
    col = C[e["kind"]]
    m = ""
    if e["arrow"] in ("end", "both"): m += f' marker-end="url(#a-{e["kind"]})"'
    if e["arrow"] in ("start", "both"): m += f' marker-start="url(#a-{e["kind"]})"'
    da = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<polyline points="{pts_str(e["draw"])}" fill="none" stroke="{col}" stroke-width="{wd}" stroke-linejoin="round"{da}{m}/>')

# 라우터 막대(선 위에 그려 구멍으로 통과를 보인다)
for y0, y1, lt, rt, holes in ROUTERS:
    out.append(f'<rect x="6" y="{y0}" width="{W-12}" height="{y1-y0}" rx="6" fill="#23292e"/>')
    for hx0, hx1, ht in holes:
        out.append(f'<rect x="{hx0}" y="{y0-2}" width="{hx1-hx0}" height="{y1-y0+4}" rx="4" fill="#ffffff" stroke="#23292e" stroke-width="1.2"/>')
        if ht:
            out.append(text(hx1 + 6, (y0 + y1) / 2 + 5, ht, 12, 700, "#ffe08a"))
    out.append(text(22, y0 + 21, lt, 14, 700, "#ffffff"))
    out.append(text(22, y0 + 40, rt, 12.5, 400, "#dfe5e8"))
# 라우터 구멍 사이로 지나가는 선을 다시 그림
for e in E:
    xs = [p[0] for p in e["pts"]]; ys = [p[1] for p in e["pts"]]
    for (a, b) in zip(e["pts"], e["pts"][1:]):
        if a[0] == b[0]:
            for y0, y1, *_ in ROUTERS:
                lo, hi = min(a[1], b[1]), max(a[1], b[1])
                if lo < y0 and hi > y1:
                    dash, wd = STY[e["kind"]]
                    da = f' stroke-dasharray="{dash}"' if dash else ""
                    out.append(f'<line x1="{a[0]}" y1="{y0-2}" x2="{a[0]}" y2="{y1+2}" stroke="{C[e["kind"]]}" stroke-width="{wd}"{da}/>')
for x, y, t, anc in ROUTER_PORT_NOTE:
    out.append(text(x, y, t, 11.5, 700, "#23292e", anc))

# 연 쪽 표시 ●
def endpoint(e, which):
    return e["pts"][0] if which == "start" else e["pts"][-1]
for e in E:
    if e["dot"]:
        x, y = endpoint(e, e["dot"])
        out.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{C[e["kind"]]}" stroke="#fff" stroke-width="1.5"/>')

# 상자
for k, b in B.items():
    x, y, w, h = b["x"], b["y"], b["w"], b["h"]
    kind = b["kind"]
    if kind == "pill":
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="#2b2f33"/>')
        out.append(text(x + w / 2, y + h / 2 + 5, b["title"], 13, 700, "#ffffff", "middle"))
        continue
    if kind == "reqpill":
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#fff5f5" stroke="{C["req"]}" stroke-width="1.6" stroke-dasharray="6 3"/>')
        out.append(text(x + 14, y + 19, b["title"], 13.5, 700, C["req"]))
        out.append(text(x + 14, y + 36, b["prod"], 12, 400, "#5a6872"))
        continue
    stroke, sw, dash, fill = "#9aa7ae", 1.3, "", "#ffffff"
    if kind == "once": stroke, dash, fill = "#8f989f", "6 4", "#fbfcfc"
    if kind == "ext": stroke, dash, fill = "#5a6fbf", "4 3", "#f7f8fd"
    da = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da} filter="url(#none)"/>')
    tx = x + 12
    ty = y + 22
    num = CIRC.get(b["no"], "")
    small = w <= 160
    tsize = 13.5 if small else 15
    out.append(text(tx, ty, f"{num} {b['title']}" if num else b["title"], tsize, 700, "#1d2830"))
    if b["prod"]:
        out.append(text(tx, ty + 18 if h >= 56 else ty + 17, b["prod"], 12 if small else 12.5, 400, "#4b5963"))
    if b["desc"] and k != "edge":
        out.append(text(tx, ty + 36, b["desc"], 12 if small else 12.5, 400, "#1f6f8b" if not small else "#4b5963"))
    if b["badge"]:
        out.append(text(x + w - 8, (y + h - 7) if small else (y + 17), b["badge"], 12, 700, "#7d8890", "end"))
# 선 라벨(흰 바탕)
for e in E:
    for (x, y, t, anc) in e["labels"]:
        out.append(text(x, y, t, 12, 600, C[e["kind"]] if e["kind"] != "mon" else "#5f6a71", anc,
                        ' paint-order="stroke" stroke="#ffffff" stroke-width="4" stroke-linejoin="round"'))

out.append('</svg>')
print("\n".join(out))
