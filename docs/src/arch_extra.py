# -*- coding: utf-8 -*-
"""시스템_아키텍처 보강 렌더러(hyd-iot-edu · ceco_demo 공용, 두 저장소에 같은 사본).
  internal_html(INTERNAL, ...) : 서비스 속 구조 그림(가운데 내부 부품, 왼쪽 바깥 인터페이스, 오른쪽 내부 연결 곡선) + 표
  lineage_html(LINEAGE, ...)   : 데이터 리니지(갈래별 경로 띠 + 단계별 필드 표)
  protocol_rows(L, C, ...)     : 연결별 프로토콜 · 데이터 형식 표
입력 데이터는 각 저장소의 arch_internal.py · arch_lineage.py 에 있다(코드를 읽어 파일:줄 근거와 함께 적은 것).
"""
import html, re

FONT = 12.5


def esc(t):
    return html.escape(str(t), quote=True)


def tw(t, size=FONT):
    return sum(size * (1.0 if ord(ch) > 0x1100 else 0.58) for ch in str(t))


def wrap(t, width, size=FONT):
    """단어 단위로 접는다(한글은 글자 단위로도 끊음)."""
    out, cur = [], ""
    for tok in re.split(r"(\s+)", str(t)):
        if tw(cur + tok, size) <= width:
            cur += tok
            continue
        if cur.strip():
            out.append(cur.rstrip())
        cur = tok.lstrip()
        while tw(cur, size) > width:          # 아주 긴 토큰
            n = max(1, int(len(cur) * width / max(1, tw(cur, size))))
            out.append(cur[:n])
            cur = cur[n:]
    if cur.strip():
        out.append(cur.rstrip())
    return out or [""]


MECH = [  # (판별 정규식, 분류, 색)
 (r"자식 프로세스|stdio|subprocess", "자식 프로세스", "#7d3f66"),
 (r"대기열|큐|queue|Queue|channel|채널", "대기열 · 큐", "#a15c00"),
 (r"SQLite|파일|볼륨|file", "파일 · SQLite", "#7a5c2e"),
 (r"HTTP|MQTT|Kafka|SQL|Bolt|Modbus|TCP|gRPC|MCP|InfluxDB|웹훅|WebSocket|SSE|PostgreSQL", "네트워크", "#1f6f8b"),
 (r".*", "같은 프로세스 안(함수 · 공유 메모리 · 콜백)", "#56646d"),
]


def mech(m):
    for pat, name, col in MECH:
        if re.search(pat, m):
            return name, col
    return MECH[-1][1], MECH[-1][2]


def internal_svg(key, d, idp):
    parts = d["parts"]
    pid = [p[0] for p in parts]
    ext = {p: [e for e in d.get("ext", []) if e[0] == p] for p in pid}
    X0, PW, EW = 360, 380, 330
    y, pos = 16, {}
    for p in parts:
        lines_e = sum(max(1, len(wrap(e[2], EW - 20, 11.5))) + 1 for e in ext[p[0]])
        nd = len(wrap(p[3], PW - 24, 11.8)[:2])
        h = max(56 + nd * 15, 14 + lines_e * 15 + 6 * len(ext[p[0]]))
        pos[p[0]] = (y, h)
        y += h + 16
    H = y + 4
    # 내부 연결 차선 배정(세로 구간이 겹치면 다른 차선)
    links = [l for l in d.get("links", []) if l[0] in pos and l[1] in pos and l[0] != l[1]]
    spans, lanes = [], []
    for i, l in enumerate(links):
        a, b = pos[l[0]], pos[l[1]]
        ya, yb = a[0] + min(a[1] - 12, 18 + 8 * (i % 3)), b[0] + min(b[1] - 12, 30 + 8 * (i % 3))
        lo, hi = min(ya, yb), max(ya, yb)
        lane = 0
        while any(s[2] == lane and not (hi + 6 < s[0] or lo - 6 > s[1]) for s in spans):
            lane += 1
        spans.append((lo, hi, lane))
        lanes.append((ya, yb, lane))
    nl = max([s[2] for s in spans], default=-1) + 1
    W = X0 + PW + 30 + nl * 30 + 20
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" class="inner" role="img" aria-label="{esc(key)} 속 구조">', "<defs>"]
    for _n, name, col in MECH:
        cid = re.sub(r"\W", "", col)
        o.append(f'<marker id="{idp}-{cid}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    o.append(f'<marker id="{idp}-ext" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#1f6f8b"/></marker></defs>')
    o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
    o.append(f'<rect x="{X0 - 14}" y="6" width="{PW + 28}" height="{H - 12}" rx="12" fill="#f6f8f9" stroke="#cfd6da" stroke-dasharray="5 4"/>')
    # 연결 곡선
    for i, (l, (ya, yb, lane)) in enumerate(zip(links, lanes), 1):
        _nm, col = mech(l[2])
        cid = re.sub(r"\W", "", col)
        lx = X0 + PW + 22 + lane * 30
        o.append(f'<path d="M{X0 + PW},{ya} H{lx} V{yb} H{X0 + PW + 2}" fill="none" stroke="{col}" stroke-width="1.8" marker-end="url(#{idp}-{cid})"/>')
        o.append(f'<circle cx="{X0 + PW}" cy="{ya}" r="3.6" fill="{col}"/>')
        my = (ya + yb) / 2
        o.append(f'<g><circle cx="{lx}" cy="{my}" r="10" fill="#fff" stroke="{col}" stroke-width="1.4"/><text x="{lx}" y="{my + 4}" font-size="10.5" font-weight="700" fill="{col}" text-anchor="middle">{i}</text></g>')
    # 부품 상자와 바깥 인터페이스
    for p in parts:
        y0, h = pos[p[0]]
        o.append(f'<rect x="{X0}" y="{y0}" width="{PW}" height="{h}" rx="9" fill="#fff" stroke="#8fa0a9" stroke-width="1.4"/>')
        o.append(f'<text x="{X0 + 12}" y="{y0 + 20}" font-size="14" font-weight="800" fill="#14212a">{esc(p[1])}</text>')
        for j, t in enumerate(wrap(p[3], PW - 24, 11.8)[:2]):
            o.append(f'<text x="{X0 + 12}" y="{y0 + 38 + j * 15}" font-size="11.8" fill="#33424b">{esc(t)}</text>')
        f = wrap(p[2], PW - 24, 10)[0]
        o.append(f'<text x="{X0 + 12}" y="{y0 + h - 8}" font-size="10" fill="#7a868e" font-family="JetBrains Mono,Consolas,monospace">{esc(f)}</text>')
        ey = y0 + 2
        for e in ext[p[0]]:
            ls = wrap(e[2], EW - 20, 11.5)
            eh = 12 + len(ls) * 15
            o.append(f'<rect x="10" y="{ey}" width="{EW}" height="{eh}" rx="7" fill="#eef6f9" stroke="#9cc4d2"/>')
            for j, t in enumerate(ls):
                o.append(f'<text x="20" y="{ey + 16 + j * 15}" font-size="11.5" fill="#174d60">{esc(t)}</text>')
            ay = ey + eh / 2
            mk = {"in": f' marker-end="url(#{idp}-ext)"', "out": f' marker-start="url(#{idp}-ext)"', "both": f' marker-start="url(#{idp}-ext)" marker-end="url(#{idp}-ext)"'}.get(e[1], "")
            o.append(f'<line x1="{10 + EW + 2}" y1="{ay}" x2="{X0 - 2}" y2="{ay}" stroke="#1f6f8b" stroke-width="1.6"{mk}/>')
            ey += eh + 6
    o.append("</svg>")
    return "\n".join(o), links


def internal_html(INTERNAL, title_of, anchor_prefix="in", easy=None):
    out = ['<div class="mechlegend">' + "".join(f'<span><i style="background:{c}"></i>{n}</span>' for _p, n, c in MECH) + '<span><i style="background:#1f6f8b;height:2px"></i>왼쪽 파란 상자 = 바깥 인터페이스(→ 들어옴 · ← 나감)</span></div>']
    for k, d in INTERNAL.items():
        svg, links = internal_svg(k, d, f"{anchor_prefix}{k}")
        rows = "".join(f'<tr><td class="c">{i}</td><td>{esc(_name(d, l[0]))} → {esc(_name(d, l[1]))}</td><td><span class="mech" style="border-color:{mech(l[2])[1]};color:{mech(l[2])[1]}">{esc(l[2])}</span></td><td>{esc(l[3])}</td><td class="ref">{esc(l[4] if len(l) > 4 else "")}</td></tr>'
                       for i, l in enumerate(links, 1))
        self_links = [l for l in d.get("links", []) if l[0] == l[1] or l[0] not in {p[0] for p in d["parts"]} or l[1] not in {p[0] for p in d["parts"]}]
        rows += "".join(f'<tr><td class="c">·</td><td>{esc(_name(d, l[0]))} → {esc(_name(d, l[1]))}</td><td><span class="mech">{esc(l[2])}</span></td><td>{esc(l[3])}</td><td class="ref">{esc(l[4] if len(l) > 4 else "")}</td></tr>' for l in self_links)
        erows = "".join(f'<tr><td>{esc(_name(d, e[0]))}</td><td class="c">{ {"in": "→ 들어옴", "out": "← 나감", "both": "↔ 양쪽"}.get(e[1], esc(e[1])) }</td><td>{esc(e[2])}</td><td>{esc(e[3])}</td><td class="ref">{esc(e[4] if len(e) > 4 else "")}</td></tr>' for e in d.get("ext", []))
        prow = "".join(f'<tr><td>{esc(p[1])}</td><td>{esc(p[3])}</td><td class="ref">{esc(p[2])}</td></tr>' for p in d["parts"])
        notes = "".join(f"<li>{esc(n)}</li>" for n in d.get("notes", []))
        out.append(f'<section class="inner-sec" id="{anchor_prefix}-{k}"><h3>{title_of(k)}</h3>'
                   + (f'<div class="easy"><span class="lane">쉬운 말</span><p>{esc(easy[k])}</p></div>' if easy and k in easy else "")
                   + f'<p class="meta-note"><b>실행 형태</b> {esc(d.get("runtime", "미확인"))}</p>'
                   f'<div class="figcard inner-fig">{svg}</div>'
                   f'<details open><summary>안쪽 부품 {len(d["parts"])}개 · 내부 연결 {len(d.get("links", []))}개 · 바깥 인터페이스 {len(d.get("ext", []))}개 — 표</summary>'
                   f'<div class="tscroll"><table class="tbl small"><tr><th>안쪽 부품</th><th>하는 일</th><th>코드</th></tr>{prow}</table></div>'
                   f'<div class="tscroll"><table class="tbl small"><tr><th>#</th><th>내부 연결</th><th>방식</th><th>오가는 것</th><th>근거</th></tr>{rows}</table></div>'
                   f'<div class="tscroll"><table class="tbl small"><tr><th>안쪽 부품</th><th>방향</th><th>바깥 인터페이스(프로토콜 · 포트 · 토픽/표)</th><th>오가는 것</th><th>근거</th></tr>{erows}</table></div>'
                   + (f'<ul class="notes">{notes}</ul>' if notes else "") + "</details></section>")
    return "\n".join(out)


def _name(d, pid):
    for p in d["parts"]:
        if p[0] == pid:
            return p[1]
    return pid


def lineage_html(LINEAGE, anchor_prefix="lin", easy=None):
    out = []
    for k, d in LINEAGE.items():
        hops = d["hops"]
        branches = []
        for h in hops:
            b = h.get("branch") or "본선"
            if b not in branches:
                branches.append(b)
        # 갈래별 경로 띠(SVG)
        BW, BH, GX, GY, LBL = 196, 76, 24, 16, 128
        rows = {b: [h for h in hops if (h.get("branch") or "본선") == b] for b in branches}
        maxn = max(len(v) for v in rows.values())
        W = LBL + maxn * (BW + GX) + 10
        H = len(branches) * (BH + GY) + 10
        s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" class="lin" role="img" aria-label="{esc(d["title"])} 경로">',
             f'<defs><marker id="{anchor_prefix}{k}a" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#1f6f8b"/></marker></defs>',
             f'<rect width="{W}" height="{H}" fill="#fff"/>']
        for bi, b in enumerate(branches):
            y = 6 + bi * (BH + GY)
            for j, t in enumerate(wrap(b, LBL - 12, 11.5)[:3]):
                s.append(f'<text x="4" y="{y + 18 + j * 14}" font-size="11.5" font-weight="700" fill="#394b98">{esc(t)}</text>')
            for j, h in enumerate(rows[b]):
                x = LBL + j * (BW + GX)
                s.append(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="8" fill="#f7fafb" stroke="#9cb3bf"/>')
                s.append(f'<text x="{x + 8}" y="{y + 16}" font-size="10.5" font-weight="700" fill="#7a868e">{esc(h.get("step", ""))}</text>')
                ws = wrap(h.get("where", ""), BW - 34, 11.5)
                for jj, t in enumerate(ws[:2]):
                    s.append(f'<text x="{x + 30}" y="{y + 16 + jj * 14}" font-size="11.5" font-weight="800" fill="#14212a">{esc(t)}</text>')
                hw = wrap(h.get("how", ""), BW - 14, 10.5)
                yb = y + 16 + min(2, len(ws)) * 14 + 4
                for jj, t in enumerate(hw[:max(1, (y + BH - 6 - yb) // 13 + 1)]):
                    s.append(f'<text x="{x + 8}" y="{yb + jj * 13}" font-size="10.5" fill="#1f6f8b">{esc(t)}</text>')
                if j:
                    s.append(f'<line x1="{x - GX + 2}" y1="{y + BH / 2}" x2="{x - 2}" y2="{y + BH / 2}" stroke="#1f6f8b" stroke-width="1.6" marker-end="url(#{anchor_prefix}{k}a)"/>')
        s.append("</svg>")
        trs = "".join(
            f'<li class="hop"><p class="hophead"><span class="hopno">{esc(h.get("step", ""))}</span><span class="hopbr">{esc(h.get("branch") or "본선")}</span><b>{esc(h.get("where", ""))}</b></p>'
            f'<dl class="spec hopdl"><dt>방법</dt><dd>{esc(h.get("how", ""))}</dd><dt>형식</dt><dd>{esc(h.get("fmt", ""))}</dd>'
            f'<dt>필드 · 컬럼</dt><dd class="fld">{esc(h.get("fields", ""))}</dd><dt>바뀐 것</dt><dd>{esc(h.get("change", ""))}</dd>'
            f'<dt>보관</dt><dd>{esc(h.get("keep", ""))}</dd><dt>근거</dt><dd class="ref">{esc(h.get("ref", ""))}</dd></dl></li>'
            for h in hops)
        ends = "".join(f"<li>{esc(x)}</li>" for x in d.get("ends", []))
        loss = "".join(f"<li>{esc(x)}</li>" for x in d.get("loss", []))
        out.append(f'<section class="lin-sec" id="{anchor_prefix}-{k}"><h3>{esc(d["title"])}</h3>'
                   + (f'<div class="easy"><span class="lane">쉬운 말</span><p>{esc(easy[k])}</p></div>' if easy and k in easy else "")
                   + f'<p class="meta-note"><b>태어나는 곳</b> {esc(d.get("origin", ""))}</p>'
                   f'<div class="figcard lin-fig">{"".join(s)}</div>'
                   f'<ol class="hops">{trs}</ol>'
                   + (f'<div class="two lin-two"><div><h4>끝나는 곳</h4><ul>{ends}</ul></div>' if ends else '<div class="two lin-two">')
                   + (f'<div><h4>사라지거나 늦어질 수 있는 곳</h4><ul>{loss}</ul></div>' if loss else "") + "</div></section>")
    return "\n".join(out)


PROTO = [  # (정규식, 짧은 이름, 기본 형식)
 (r"^Modbus", "Modbus TCP", "16비트 레지스터 · 코일"),
 (r"^MQTT 5|MQTT5", "MQTT 5", "JSON"),
 (r"^MQTT", "MQTT", "JSON"),
 (r"^MCP", "MCP(HTTP)", "JSON-RPC"),
 (r"remote_write", "HTTP remote_write", "protobuf + snappy"),
 (r"/federate|긁기", "HTTP 지표 긁기", "Prometheus 텍스트"),
 (r"^Kafka 관리", "Kafka 관리", "토픽 설정"),
 (r"^Kafka", "Kafka", "JSON(값) · 키 문자열"),
 (r"PostgreSQL", "PostgreSQL", "SQL 행"),
 (r"^Bolt", "Bolt", "Cypher"),
 (r"ZooKeeper", "ZooKeeper", "znode"),
 (r"8086.*write|/api/v2/write|라인 프로토콜", "HTTP InfluxDB 쓰기", "line protocol"),
 (r"8086", "HTTP InfluxDB 조회", "InfluxQL/Flux → JSON"),
 (r"^HTTPS", "HTTPS", "JSON"),
 (r"^HTTP|웹훅", "HTTP", "JSON"),
 (r"^파일", "파일", "파일"),
 (r".*", "—", "—"),
]


def proto_of(text):
    for pat, name, fmt in PROTO:
        if re.search(pat, text):
            return name, fmt
    return "—", "—"
