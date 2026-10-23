"""3 · 4회차 최종 점검의 전 · 후를 HTML · MD로 만든다.

    python3 report34.py <저장소 루트> <점검 폴더 final4> <최종본 폴더> <3 | 4> <출력 html> <출력 md> [전 기준 git 커밋]

- 전: 저장소 대본(기준 커밋이 있으면 그 커밋의 대본). 후: <최종본 폴더>/<과정>/<NN>회차/.
- 바뀐 장마다 장 대본 전체를 싣고 지운 말 · 넣은 말을 칠한다. 점검자 · 통합 변경목록에서 그 파일 · 장의 행(구분 · 근거)을 붙인다.
- 다른 과정과 똑같이 바뀐 장(같은 전 → 같은 후)은 처음 나온 곳에서만 싣고 뒤에서는 「… 와 같음」 한 줄로 줄인다.
"""
import difflib
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT, F4, FIN, NO = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
OUT_H, OUT_M = Path(sys.argv[5]), Path(sys.argv[6])
BASE = sys.argv[7] if len(sys.argv) > 7 else None
JOBS = {"3": [("통합반", "03", "통합반 3회차"), ("실전반", "03", "실전반 3회차")],
        "4": [("통합반", "04", "통합반 4회차"), ("실전반", "04", "실전반 4회차"),
              ("통합반", "05", "통합반 5회차(실전반 4회차와 같은 문장 맞춤)"), ("통합반", "06", "통합반 6회차(실전반 4회차와 같은 문장 맞춤)")]}[NO]
HEAD = re.compile(r"^## \[SLIDE ([0-9~]+)\](.*)$", re.M)
TOK = re.compile(r"\s+|[가-힣A-Za-z0-9_]+|.", re.S)
esc = html.escape


def norm(lab): return "~".join(str(int(x)) for x in lab.split("~"))


def sections(text):
    out = {}
    for m in HEAD.finditer(text):
        nxt = re.compile(r"^#{1,2} ", re.M).search(text, m.end())
        out[norm(m.group(1))] = (m.group(2).strip(), text[m.end():nxt.start() if nxt else len(text)].strip("\n"))
    return out


def spoken(body):
    t = re.sub(r"^---\s*$|^>.*$|^\|.*$", "", body, flags=re.M).replace("**", "")
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def syll(t):   # 대본시간.py와 같은 셈
    t = re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", t)
    return len(re.findall(r"[가-힣]", t)) + len(re.findall(r"\d", t)) * 1.6 + len(re.findall(r"[A-Za-z]", t)) * 0.6


def old_text(course, nn, name):
    rel = f"산출물/{course}/이론/{nn}회차/대본/{name}"
    if BASE: return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{rel}"], capture_output=True, text=True, check=True).stdout
    return (ROOT / rel).read_text("utf-8")


def rows_of(path):
    rows = []
    if not path.exists(): return rows
    for line in path.read_text("utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s\-:|]+\|?$", line): continue
        c = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(c) >= 7 and c[0] not in ("번호", "#", "No"): rows.append((path.parent.name, c))
    return rows


ROWS = [r for d in sorted(F4.iterdir()) if d.is_dir() for r in rows_of(d / "변경목록.md")]


def nums(s): return {int(x) for x in re.findall(r"\d+", s)}


def rows_for(course, name, rng):
    out = []
    for who, c in ROWS:
        f = c[1]
        if name not in f and Path(name).stem not in f: continue
        if ("실전반" in f and course != "실전반") or ("통합반" in f and course != "통합반"): continue
        if nums(c[2]) & rng: out.append((who, c))
    return out


def diff_pair(a, b):
    ta, tb = TOK.findall(a), TOK.findall(b)
    A, B, M = [], [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        x, y = "".join(ta[i1:i2]), "".join(tb[j1:j2])
        if op == "equal":
            A.append(esc(x)); B.append(esc(y)); M.append(re.sub(r"([~*_])", r"\\\1", x)); continue
        if x: A.append(f"<del>{esc(x)}</del>")
        if y: B.append(f"<ins>{esc(y)}</ins>")
        for s, mark in ((x, "~~"), (y, "**")):
            core = s.strip()
            if not core: M.append(s); continue
            core = re.sub(r"([~*_])", r"\\\1", core)
            parts = [p.strip() for p in re.split(r"\n\s*\n", core) if p.strip()]
            lead, trail = s[:len(s) - len(s.lstrip())], s[len(s.rstrip()):]
            M.append(lead + "\n\n".join(f"{mark}{p}{mark}" for p in parts) + trail)
    return "".join(A), "".join(B), "".join(M)


seen = {}       # (전 본문, 후 본문) → 처음 실은 곳
H, MD, summary, cats = [], [], [], {}
for course, nn, label in JOBS:
    d = FIN / course / f"{nn}회차"
    for f in sorted(d.glob("*.md")):
        old, new = old_text(course, nn, f.name), f.read_text("utf-8")
        so, sn = sections(old), sections(new)
        changed = [l for l in so if so[l][1] != sn.get(l, ("", ""))[1]]
        m0 = sum(syll(spoken(b)) for _, b in so.values()) / 275; m1 = sum(syll(spoken(b)) for _, b in sn.values()) / 275
        summary.append((label, f.stem, len(changed), m0, m1))
        h_old, h_new = old.split("## [SLIDE", 1)[0], new.split("## [SLIDE", 1)[0]
        if not changed and h_old == h_new: continue
        H.append(f"<h2>{esc(label)} · {esc(f.stem)}</h2>"); MD += ["", f"## {label} · {f.stem}", ""]
        if h_old != h_new:
            a, b, m = diff_pair(h_old.strip(), h_new.strip())
            H.append(f"<section><h3>머리(제작 표시, 낭독 안 함)</h3><div class=pair><div><div class=lab>전</div><pre>{a}</pre></div><div><div class=lab>후</div><pre>{b}</pre></div></div></section>")
            MD += ["### 머리(제작 표시, 낭독 안 함)", "", m, ""]
        for l in changed:
            rng = set(range(int(l.split("~")[0]), int(l.split("~")[-1]) + 1))
            title = f"SLIDE {l}"; sub = so[l][0]
            key = (so[l][1], sn[l][1])
            if key in seen:
                H.append(f"<section><h3>{esc(title)} <span class=muted>{esc(sub)}</span></h3><p class=muted>{esc(seen[key])}와 똑같이 바뀜(같은 문단) — 위에서 봄.</p></section>")
                MD += [f"### {title} — {sub}", "", f"_{seen[key]}와 똑같이 바뀜(같은 문단) — 위에서 봄._", ""]
                continue
            seen[key] = f"{label} {f.stem[:2]}편 SLIDE {l}"
            rr = rows_for(course, f.name, rng)
            for _, c in rr: cats[c[3]] = cats.get(c[3], 0) + 1
            why = [f"{c[3]} — {c[6]}" for _, c in rr]
            a, b, m = diff_pair(so[l][1], sn[l][1])
            if not rr: why = ["다른 과정에서 고친 같은 문단을 똑같이 옮김"]
            H.append(f"<section><h3>{esc(title)} <span class=muted>{esc(sub)}</span></h3>"
                     + ("<ul class=why>" + "".join(f"<li>{esc(w)}</li>" for w in why) + "</ul>" if why else "")
                     + f"<div class=pair><div><div class=lab>전</div><pre>{a}</pre></div><div><div class=lab>후</div><pre>{b}</pre></div></div></section>")
            MD += [f"### {title} — {sub}", ""] + [f"- {w}" for w in why] + ([""] if why else []) + [m, ""]

intro = (F4 / "통합" / f"{NO}회차_요약.md")
deck = (F4 / "통합" / f"{NO}회차_덱.md")
srow = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{c}</td><td>{d0:.1f} → {d1:.1f}분</td></tr>" for a, b, c, d0, d1 in summary)
mrow = [f"| {a} | {b} | {c} | {d0:.1f} → {d1:.1f}분 |" for a, b, c, d0, d1 in summary]
crow = "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k, v in sorted(cats.items()))
CSS = """:root{--bg:#fff;--fg:#1d2733;--mut:#667085;--del:#fde2e1;--ins:#d9f2df;--line:#d0d5dd;--box:#f6f8fa}
@media (prefers-color-scheme:dark){:root{--bg:#14181d;--fg:#e6e9ee;--mut:#98a2b3;--del:#5a1f1f;--ins:#1f4a2a;--line:#344054;--box:#1d232a}}
body{background:var(--bg);color:var(--fg);font:16px/1.75 "Apple SD Gothic Neo","Malgun Gothic",sans-serif;max-width:1180px;margin:32px auto;padding:0 16px}
h1{font-size:26px}h2{margin-top:40px;border-bottom:2px solid var(--line);padding-bottom:4px}h3{margin:22px 0 6px}
.muted{color:var(--mut);font-weight:normal}table{border-collapse:collapse;margin:10px 0;width:100%}td,th{border:1px solid var(--line);padding:5px 8px;vertical-align:top;font-size:14px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:800px){.pair{grid-template-columns:1fr}}
pre{white-space:pre-wrap;word-break:keep-all;background:var(--box);padding:10px;border-radius:6px;font:15px/1.8 inherit;margin:0}
del{background:var(--del);text-decoration:line-through}ins{background:var(--ins);text-decoration:none}.lab{font-size:13px;color:var(--mut)}
ul.why{margin:4px 0 8px;font-size:14px}section{border-top:1px dashed var(--line)}"""


def md_block(p):
    return p.read_text("utf-8") if p.exists() else ""


def md_html(p):
    if not p.exists(): return ""
    out, table = [], []
    def flush():
        if table:
            head, *body = table
            out.append("<table><tr>" + "".join(f"<th>{esc(c)}</th>" for c in head) + "</tr>" + "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in body) + "</table>")
            table.clear()
    for line in p.read_text("utf-8").splitlines():
        if line.startswith("|"):
            if not re.match(r"^\|[\s\-:|]+\|?$", line): table.append([c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))])
            continue
        flush()
        if m := re.match(r"^(#{1,4}) (.*)", line): out.append(f"<h{len(m.group(1))+2}>{esc(m.group(2))}</h{len(m.group(1))+2}>")
        elif m := re.match(r"^\s*[-*] (.*)", line): out.append(f"<li>{esc(m.group(1))}</li>")
        elif line.strip(): out.append(f"<p>{esc(line)}</p>")
    flush()
    return "\n".join(out)


title = f"{NO}회차 최종 점검 전후"
OUT_H.write_text(f"""<!doctype html><html lang=ko><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style>
<h1>{NO}회차 이론 대본 · 덱 최종 점검 — 전과 후</h1>
<p class=muted>전 = 점검 전 대본{f'(develop {BASE[:8]})' if BASE else ''}. 후 = 점검 · 마지막 손질 · 통합을 거친 대본. 지운 곳은 <del>빨강</del>, 넣은 곳은 <ins>초록</ins>. 낭독 추정은 분당 275음절(대본시간.py와 같은 셈).</p>
{md_html(intro)}
<table><tr><th>과정</th><th>파일</th><th>바뀐 장</th><th>낭독 추정</th></tr>{srow}</table>
<h3>구분별 변경 수(변경목록 행, 1차 + 마지막 손질 + 통합)</h3><table>{crow}</table>
<h2 id=deck>덱 화면 수정</h2>{md_html(deck) or '<p class=muted>(없음)</p>'}
<h2>대본 전 · 후</h2>{''.join(H)}</html>""", "utf-8")
OUT_M.write_text("\n".join([f"# {NO}회차 이론 대본 · 덱 최종 점검 — 전과 후", "",
                            "지운 말은 ~~취소선~~, 넣은 말은 **굵게**. `>` 줄은 낭독하지 않는 제작 표시.", "",
                            md_block(intro), "", "| 과정 | 파일 | 바뀐 장 | 낭독 추정 |", "|---|---|---|---|", *mrow, "",
                            "## 덱 화면 수정", "", md_block(deck) or "(없음)", "", "# 대본 전 · 후", *MD]) + "\n", "utf-8")
print(OUT_H, OUT_M, sum(s[2] for s in summary), "장")
