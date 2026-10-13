"""촬영 진행표(runsheet.html)를 만든다. 랩 폴더의 runsheet.json 을 읽는다.

    python3 build_runsheet.py <랩 폴더>

진행표는 강사가 화면 한쪽에 띄워 놓고 보면서 직접 말하고 조작하며 촬영하는 데 쓴다. 읽는 대본이 아니다.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
lab = Path(sys.argv[1]).resolve()
d = json.loads((lab / "runsheet.json").read_text(encoding="utf-8"))


def items(xs, tag="ul"):
    out = []
    for x in xs:
        if isinstance(x, dict):   # {"표": [[머리…], [행…], …]}
            rows = x["표"]
            out.append("</{0}><table><tr>{1}</tr>{2}</table><{0}>".format(
                tag, "".join(f"<th>{h}</th>" for h in rows[0]),
                "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows[1:])))
        else:
            out.append(f"<li>{x}</li>")
    return f"<{tag}>" + "".join(out) + f"</{tag}>"


clock = 0
segs = []
plan = []
for i, s in enumerate(d["구간"]):
    start = clock
    clock += s["분"]
    plan.append(f'<tr><td>{i}. {s["제목"]}</td><td>{s["분"]}분 · {start:02d}:00~{clock:02d}:00</td></tr>')
    parts = ""
    for key, cls, name, tag in (("하는 것", "do", "화면에서 하는 것", "ol"), ("말할 요점", "say", "말할 요점", "ul"),
                                ("하는 동안", "mean", "하는 동안 설명할 것", "ul"), ("보여 줄 결과", "show", "보여 줄 결과", "ul")):
        if s.get(key):
            parts += f'<div class="part {cls}"><h3>{name}</h3>{items(s[key], tag)}</div>'
    segs.append(f'<section class="seg"><header><em>{i}</em><h2>{s["제목"]}</h2><span><b>{s["분"]}분</b>{start:02d}:00 → {clock:02d}:00</span></header>{parts}</section>')

doc = (
    '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    f'<title>촬영 진행표 · {d["제목"]}</title><style>{(HERE / "runsheet.css").read_text(encoding="utf-8")}</style></head><body><main>'
    f'<p class="meta">촬영 진행표 · {d["회차"]}</p><h1>{d["제목"]}</h1><p class="meta">{d["한 줄"]} · 배정 {clock}분</p>'
    '<div class="box rule"><b>예상과 다르게 나오면</b> 무엇이 다르게 나왔는지 화면에서 짚고, 왜 그런지 말한 다음, 고친다. 미리 정해 둔 대처는 없다.</div>'
    f'<div class="box"><h2>촬영 전에</h2>{items(d["촬영 전에"])}</div>'
    f'<div class="box"><h2>구간과 시간</h2><table class="plan">{"".join(plan)}</table></div>'
    + "".join(segs) + "</main></body></html>\n"
)
(lab / "runsheet.html").write_text(doc, encoding="utf-8")
print(f"runsheet.html · 구간 {len(segs)} · 합 {clock}분")
