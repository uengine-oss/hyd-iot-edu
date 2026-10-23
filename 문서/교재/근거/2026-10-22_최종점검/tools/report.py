"""2회차 최종 점검의 전 · 후를 HTML 한 장으로 만든다.

    python3 report.py <저장소 루트> <결과 폴더> <회차 01 · 02> <출력 html>

- 전: 저장소의 현재 대본. 후: <final2>/proposed/ 의 제안본(merge.py 결과).
- 바뀐 구획마다 낱말 단위로 지운 곳(전)과 넣은 곳(후)을 칠하고, 점검자 변경목록의 그 장 행(구분 · 근거)을 붙인다.
- 실전반 01~03에서 통합반과 같은 구획은 통합반 쪽에서 한 번만 보여 주고 개수만 적는다.
- 머리에 구분별 개수, 낭독 추정(분당 275음절, 대본시간.py와 같은 셈), 음성에 새로 드는 글자 수를 적는다.
"""
import difflib
import html
import re
import sys
from pathlib import Path

ROOT, F2, NN, OUT = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
SRC = {c: ROOT / f"산출물/{c}/이론/{NN}회차/대본" for c in ("통합반", "실전반")}
PROP = {c: F2 / "proposed" / c for c in ("통합반", "실전반")}
AGENTS = {"02": {("통합반", "01"): "A", ("통합반", "02"): "B", ("통합반", "03"): "C",
                  ("실전반", "01"): "A", ("실전반", "03"): "C", ("실전반", "04"): "D"},
          "01": {("통합반", "01"): "E", ("통합반", "02"): "F", ("통합반", "03"): "G"}}
AGENT = AGENTS[NN]


def norm(lab):
    """장 번호 표기를 맞춘다(04 = 4, 64~65 = 64~65)."""
    return "~".join(str(int(x)) for x in lab.split("~"))


def body(sec):
    """구획에서 제목 줄을 뺀 본문. 두 과정의 제목 줄은 번호 표기(04/4)가 다를 수 있다."""
    return sec.split("\n", 1)[1] if "\n" in sec else ""


HEAD = re.compile(r"^## \[SLIDE ([0-9~]+)\](.*)$", re.M)
esc = html.escape


def sections(text):
    out = []
    for m in HEAD.finditer(text):
        nxt = re.compile(r"^#{1,2} ", re.M).search(text, m.end())
        out.append((norm(m.group(1)), m.group(2).strip(), text[m.start():nxt.start() if nxt else len(text)]))
    return out


def spoken(sec):
    """영상 도구(강의영상.py slides_text)와 같은 방식으로 낭독 글만 남긴다."""
    t = re.split(r"^#{1,2} ", sec.split("\n", 1)[1] if "\n" in sec else "", flags=re.M)[0]
    t = re.sub(r"^---\s*$|^>.*$|^\|.*$", "", t, flags=re.M).replace("**", "")
    t = re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def syll(t):   # 대본시간.py와 같은 셈
    t = re.sub(r"\*\*|^>.*$|^# .*$", "", t, flags=re.M)
    t = re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", t)
    return len(re.findall(r"[가-힣]", t)) + len(re.findall(r"\d", t)) * 1.6 + len(re.findall(r"[A-Za-z]", t)) * 0.6


def minutes(text):
    body = re.split(r"^# (여기까지 작성|촬영 본문 끝)|^## 제작 확인용", text, flags=re.M)[0]
    parts = re.split(r"^## \[SLIDE ([0-9~]+)\](.*)$", body, flags=re.M)
    return sum(syll(parts[i + 2]) for i in range(1, len(parts), 3)) / 275


TOK = re.compile(r"\s+|[가-힣A-Za-z0-9_]+|.", re.S)


def diff_html(a, b):
    ta, tb = TOK.findall(a), TOK.findall(b)
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    A, B = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        x, y = esc("".join(ta[i1:i2])), esc("".join(tb[j1:j2]))
        if op == "equal": A.append(x); B.append(y)
        else:
            if x: A.append(f"<del>{x}</del>")
            if y: B.append(f"<ins>{y}</ins>")
    return "".join(A), "".join(B)


def md_rows(path):
    """변경목록.md의 표 행을 [칸…] 목록으로. 칸 수가 맞지 않는 행은 원문 그대로 둔다."""
    rows = []
    if not path.exists(): return rows
    for line in path.read_text("utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s\-:|]+\|?$", line): continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if cells and cells[0] in ("번호", "#"): continue
        rows.append(cells)
    return rows


def md_to_html(path):
    if not path.exists(): return "<p class=muted>(파일 없음)</p>"
    out, table = [], []
    def flush():
        if table:
            head, *body = table
            out.append("<table><tr>" + "".join(f"<th>{esc(c)}</th>" for c in head) + "</tr>" +
                       "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in body) + "</table>")
            table.clear()
    for line in path.read_text("utf-8").splitlines():
        if line.startswith("|"):
            if re.match(r"^\|[\s\-:|]+\|?$", line): continue
            table.append([c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]); continue
        flush()
        if m := re.match(r"^(#{1,4}) (.*)", line): out.append(f"<h{len(m.group(1))+2}>{esc(m.group(2))}</h{len(m.group(1))+2}>")
        elif line.strip(): out.append(f"<p>{esc(line)}</p>")
    flush()
    return "\n".join(out)


def slide_key(s):
    return re.sub(r"\s", "", str(s)).replace("SLIDE", "").replace("장", "")


html_parts, summary, cats_total = [], [], {}
OWN_ROWS = md_rows(F2 / "통합" / "변경목록.md")


def nums(s):
    return {int(x) for x in re.findall(r"\d+", s)}


def render(label, key, old, new, rows, shared=frozenset()):
    """파일 하나의 전 · 후. 머리(첫 SLIDE 앞의 제작 표시)도 바뀌었으면 보여 준다."""
    so, sn = {l: (t, s) for l, t, s in sections(old)}, {l: (t, s) for l, t, s in sections(new)}
    changed = [l for l in so if so[l][1] != sn.get(l, ("", ""))[1]]
    shown = [l for l in changed if l not in shared]
    h_old, h_new = old.split("## [SLIDE", 1)[0], new.split("## [SLIDE", 1)[0]
    for r in rows: cats_total[r[3]] = cats_total.get(r[3], 0) + 1
    chars_old = sum(len(spoken(s)) for _, s in so.values()); chars_new = sum(len(spoken(s)) for _, s in sn.values())
    summary.append((label, key, len(changed), len(shown), len(shared & set(changed)), minutes(old), minutes(new), chars_old, chars_new))
    if not changed and h_old == h_new: return
    html_parts.append(f"<h2>{esc(label)} · {esc(key)}</h2>")
    if shared & set(changed): html_parts.append(f"<p class=muted>통합반과 같은 구획 {len(shared & set(changed))}곳은 통합반 쪽과 똑같이 바뀝니다(여기서는 생략).</p>")
    blocks = ([("머리(제작 표시, 낭독 안 함)", "", h_old, h_new, [r for r in rows if not nums(r[2])])] if h_old != h_new else [])
    for l in shown:
        rng = set(range(int(l.split("~")[0]), int(l.split("~")[-1]) + 1))
        blocks.append((f"SLIDE {l}", so[l][0], so[l][1], sn[l][1], [r for r in rows if nums(r[2]) & rng]))
    for title, sub, a0, b0, rr in blocks:
        a, b = diff_html(a0, b0)
        meta = "".join(f"<li><b>{esc(r[3])}</b> — {esc(r[6] if len(r) > 6 else '')}</li>" for r in rr)
        html_parts.append(f"<section><h3>{esc(title)} <span class=muted>{esc(sub)}</span></h3>"
                          + (f"<ul class=why>{meta}</ul>" if meta else "")
                          + f"<div class=pair><div><div class=lab>전</div><pre>{a}</pre></div><div><div class=lab>후</div><pre>{b}</pre></div></div></section>")


for course in ("통합반", "실전반"):
    for f in sorted(SRC[course].glob("*.md")):
        old, new = f.read_text("utf-8"), (PROP[course] / f.name).read_text("utf-8")
        shared = set()
        if course == "실전반" and (SRC["통합반"] / f.name).exists():
            to = {l: s for l, _, s in sections((SRC["통합반"] / f.name).read_text("utf-8"))}
            shared = {l for l, _, s in sections(old) if l in to and body(s) == body(to[l])}
        k = AGENT.get((course, f.name[:2]))
        def row_course(r, k=k):   # 파일 칸에 과정이 없으면 점검자의 주 과정(D만 실전반)
            return "실전반" if "실전반" in r[1] else "통합반" if "통합반" in r[1] else ("실전반" if k == "D" else "통합반")
        rows = [r for r in md_rows(F2 / k / "변경목록.md") if len(r) >= 4 and row_course(r) == course
                and (f.name[:2] in r[1] or not re.search(r"\d\d_", r[1]))] if k else []
        rows += [r for r in OWN_ROWS if len(r) >= 7 and r[1] == f"{course}/{f.name}"]
        render(course, f.stem, old, new, rows, shared)

X3 = F2 / "proposed" / "통합반_03회차"   # 같은 덱 장을 쓰는 통합반 3회차의 같은 문장 맞춤
if X3.exists():
    for f in sorted(X3.glob("*.md")):
        old = (ROOT / "산출물/통합반/이론/03회차/대본" / f.name).read_text("utf-8")
        render("통합반 3회차(같은 문장 맞춤)", f.stem, old, f.read_text("utf-8"),
               [r for r in OWN_ROWS if len(r) >= 7 and r[1] == f"통합반_03회차/{f.name}"])

import hashlib, json
CACHE = ROOT / "제작용/기존제작/tools/video/음성_저장"
def cached(text):   # 강의영상.py tts()와 같은 키: [글, 목소리, 모델, 빠르기]
    h = hashlib.sha1(json.dumps([text, "tlxL9ilynpbOVf9sZXKh", "eleven_v4", 0.80], ensure_ascii=False).encode()).hexdigest()[:16]
    return (CACHE / f"{h}.mp3").exists() and (CACHE / f"{h}.json").exists()
cost = {}
for course in ("통합반", "실전반"):
    seen = set(); new = 0; reuse = 0
    for f in sorted(PROP[course].glob("*.md")):
        for _, _, s in sections(f.read_text("utf-8")):
            sp = spoken(s)
            if not sp: continue
            if course == "실전반" and sp in cost.get("통합반글", set()): reuse += len(sp); continue
            if sp in seen: continue
            seen.add(sp)
            if cached(sp): reuse += len(sp)
            else: new += len(sp)
    cost[course] = (new, reuse); cost[course + "글"] = seen
tot = lambda i, c=None: sum(s[i] for s in summary if c is None or s[0] == c)
sum_rows = "".join(f"<tr><td>{c}</td><td>{esc(n)}</td><td>{ch}</td><td>{m0:.1f} → {m1:.1f}분</td><td>{c0:,} → {c1:,}자</td></tr>" for c, n, ch, _, _, m0, m1, c0, c1 in summary)
cat_rows = "".join(f"<tr><td>{esc(c)}</td><td>{n}</td></tr>" for c, n in sorted(cats_total.items()))
extra = []
TITLES = {"02": (("A", "통합반 01편 + 실전반 01편 1~3장"), ("B", "통합반 02편"), ("C", "통합반 03편 + 실전반 03편 다른 구획"), ("D", "실전반 04편")),
          "01": (("E", "01편 지식자산화(1~11장)"), ("F", "02편 시스템구조(12~45장)"), ("G", "03편 온톨로지(46~78장)"))}
for k, title in TITLES[NN]:
    extra.append(f"<h2>점검자 {k} — {title}</h2><details><summary>덱 점검</summary>{md_to_html(F2/k/'덱점검.md')}</details>"
                 f"<details><summary>의심(넣지 않은 것)</summary>{md_to_html(F2/k/'의심.md')}</details>"
                 f"<details><summary>본 범위</summary>{md_to_html(F2/k/'범위.md')}</details>"
                 f"<details><summary>변경목록 원문(이전 점검 대조 포함)</summary>{md_to_html(F2/k/'변경목록.md')}</details>")
CSS = """:root{--bg:#fff;--fg:#1d2733;--mut:#667085;--del:#fde2e1;--ins:#d9f2df;--line:#d0d5dd;--box:#f6f8fa}
@media (prefers-color-scheme:dark){:root{--bg:#14181d;--fg:#e6e9ee;--mut:#98a2b3;--del:#5a1f1f;--ins:#1f4a2a;--line:#344054;--box:#1d232a}}
body{background:var(--bg);color:var(--fg);font:16px/1.75 "Apple SD Gothic Neo","Malgun Gothic",sans-serif;max-width:1180px;margin:32px auto;padding:0 16px}
h1{font-size:26px}h2{margin-top:40px;border-bottom:2px solid var(--line);padding-bottom:4px}h3{margin:22px 0 6px}
.muted{color:var(--mut);font-weight:normal}table{border-collapse:collapse;margin:10px 0;width:100%}td,th{border:1px solid var(--line);padding:5px 8px;vertical-align:top;font-size:14px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:800px){.pair{grid-template-columns:1fr}}
pre{white-space:pre-wrap;word-break:keep-all;background:var(--box);padding:10px;border-radius:6px;font:15px/1.8 inherit;margin:0}
del{background:var(--del);text-decoration:line-through}ins{background:var(--ins);text-decoration:none}.lab{font-size:13px;color:var(--mut)}
ul.why{margin:4px 0 8px;font-size:14px}details{margin:6px 0}summary{cursor:pointer}section{border-top:1px dashed var(--line)}"""
page = f"""<!doctype html><html lang=ko><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{int(NN)}회차 최종 점검 전후</title><style>{CSS}</style>
<h1>{int(NN)}회차 이론 대본 · 덱 최종 점검 — 전과 후</h1>
<p class=muted>전 = 저장소 develop의 현재 대본. 후 = 제안(아직 반영 안 함). 지운 곳은 <del>빨강</del>, 넣은 곳은 <ins>초록</ins>. 낭독 추정은 분당 275음절(대본시간.py와 같은 셈, 1회차 실측은 추정보다 약 8% 짧았음).</p>
<table><tr><th>과정</th><th>파일</th><th>바뀐 장</th><th>낭독 추정</th><th>낭독 글자</th></tr>{sum_rows}
<tr><td colspan=3><b>통합반 합</b></td><td>{tot(5,'통합반'):.1f} → {tot(6,'통합반'):.1f}분</td><td>{tot(7,'통합반'):,} → {tot(8,'통합반'):,}자</td></tr>
<tr><td colspan=3><b>실전반 합</b></td><td>{tot(5,'실전반'):.1f} → {tot(6,'실전반'):.1f}분</td><td>{tot(7,'실전반'):,} → {tot(8,'실전반'):,}자</td></tr></table>
{md_to_html(F2/'통합'/'요약.md') if (F2/'통합'/'요약.md').exists() else ''}<h3>음성 견적(아직 만들지 않음)</h3><table><tr><th>과정</th><th>새로 드는 글자</th><th>저장된 음성 · 통합반과 같은 글</th><th>예상 크레딧(글자당 약 0.41, 1회차 실측)</th></tr>
<tr><td>통합반 {int(NN)}회차</td><td>{cost['통합반'][0]:,}자</td><td>{cost['통합반'][1]:,}자</td><td>약 {cost['통합반'][0]*0.41:,.0f}</td></tr>
<tr><td>실전반 {int(NN)}회차(통합반을 먼저 만든다는 전제)</td><td>{cost['실전반'][0]:,}자</td><td>{cost['실전반'][1]:,}자</td><td>약 {cost['실전반'][0]*0.41:,.0f}</td></tr></table>
<p class=muted>ElevenLabs 남은 양 23,606(2026-10-22 조회), 다음 초기화 2026-11-20.</p>
<h3>구분별 변경 수(점검자 변경목록 기준)</h3><table>{cat_rows}</table>
<h2 id=deck>덱 수정</h2>{md_to_html(F2/'통합'/'덱_정리.md') if (F2/'통합'/'덱_정리.md').exists() else '<p class=muted>(정리 없음)</p>'}
<h2>대본 전 · 후</h2>{''.join(html_parts)}
<h2>점검자별 원문(덱 점검 · 의심 · 범위 · 변경목록)</h2>{''.join(extra)}</html>"""
OUT.write_text(page, "utf-8")
print(OUT, len(page), "bytes")
