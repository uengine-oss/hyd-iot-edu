"""실전반 5 · 6회차 장별점검.md를 영상 시간표 실측 · 최종 강조 설정으로 쓴다(3 · 4회차 도구/장별점검_생성.py 꼴). 저장소 루트에서:
    python3 작업/2026-11-04_5-6회차-렌더-음성/영상/실전반/장별점검_생성.py
- 길이: 영상출력/실전반_<NN>회차_<편>/_작업/영상_자막_기록/*_시간표.md의 장 구획 음성(쉼 포함) 초. 묶음(NN~MM)은 둘째 장 시작 시각으로 나눈다.
- 강조: workspace/강의제작/제작도구/구성/실전반/<NN>회차/강조_*.json의 장별 표시 수와 대상.
- 화면 속 대상 · 까닭: 아래 TYPE(장 꼴, 덱 장 그림을 보고 감독이 정함)과 장 제목. 강조가 0인 장은 꼴의 까닭을 쓰고, 2분 넘는 장인데 강조가 0이면 꼴 까닭과 함께 굵게 표시한다.
"""
import json, re, zipfile, html
from pathlib import Path
ROOT = Path("/home/user/hyd-iot-edu"); W = Path(__file__).resolve().parents[2]
REASON = {
 "자리": "자리 장(표지 · 학습목표 · 목차 · 간지)이고 말이 비교 · 분기로 가지 않는다",
 "실습": "실습 간지 · 설명 장 — 물음과 할 일을 소개할 뿐 화면 안에서 대상을 옮겨 짚지 않는다",
 "표": "표의 행을 「첫 줄 · 둘째 줄 · 맨 아래」로 짚고, 읽는 말이 행 머리 글자와 같아 바로 찾는다",
 "두칸": "칸이 둘뿐이고 말이 「왼쪽 · 오른쪽」과 칸 제목으로 짚는다",
 "차례": "번호 · 차례가 붙은 칸을 「첫 단계 · 둘째 칸」처럼 차례로 짚고, 중심 칸은 덱이 파랗게 칠해 두었다",
 "퀴즈": "판단 문제 · 퀴즈 보기라 표시가 답을 알려 준다",
 "정의": "정의 두세 줄이 위아래로 나뉘어 있고 말이 이름을 그대로 읽는다",
 "그림": "그림의 도형마다 이름표가 붙어 있고 말이 그 이름표 글자와 위치(왼쪽 · 가운데 · 오른쪽 · 위 · 아래)로 짚는다",
 "용어": "용어 · 물음 표를 위에서부터 차례로 읽고 행 머리 글자가 말과 같다",
}
def types(spec):
    out = {}
    for part in spec.split(";"):
        k, v = part.split(":");
        for r in v.split(","):
            a, _, b = r.partition("-");
            for s in range(int(a), int(b or a) + 1): out[s] = k.strip()
    return out
TYPE = {
 "05": types("자리:1-4,20,39,57,74; 실습:16-19,37-38,53-56; 차례:5,8,23,34,40,51,62,64,65,70,71; 표:6,7,9,15,21,25,27,30,31,33,35,44,47,48,58,59,61,63,66,67,68,78;"
             " 두칸:11,22,24,28,41,45,49,50,60; 퀴즈:12,36,52,69,75-77; 코드:10,13,14,26,29,32,42,43,46; 용어:72,73"),
 "06": types("자리:1-4,14,22,33,41,51,77; 실습:61-74; 표:5,12,15,18,21,30,36,39,44,48,50,53,55,56,58,60,81; 두칸:7,8,17,23,28,52,54,57; 차례:6,9,19,20,43,47,49;"
             " 퀴즈:13,32,40,78-80; 정의:10,42; 그림:11,24,25,26,27,29,34,35,37,45; 코드:16,31,38,46,59; 용어:75,76"),
}
REASON["코드"] = "코드 상자이지만 말이 줄 머리 글자(번호 · 이름)를 그대로 읽어 바로 찾는다"
EPS = {"05": ["01", "04", "06", "08"], "06": ["01", "02", "03"]}

def titles(n):
    z = zipfile.ZipFile(ROOT / f"workspace/강의제작/산출물/실전반/이론/{n}회차/실전반_{n}일차.pptx"); out = {}
    for name in z.namelist():
        m = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", name)
        if not m: continue
        ts = [html.unescape("".join(re.findall(r"<a:t>(.*?)</a:t>", p))) for p in re.findall(r"<a:p>.*?</a:p>", z.read(name).decode(), re.S)]
        ts = [t for t in ts if t.strip() and t.strip() != "경남대학교 피지컬AI 사관학교"]
        out[int(m[1])] = (ts[0] + " " + ts[1] if len(ts) > 1 and len(ts[0].strip()) <= 3 else ts[0]) if ts else ""   # 간지는 번호 + 제목
    return out

def lengths(n):
    out = {}
    for p in EPS[n]:
        t = sorted((W / "영상출력" / f"실전반_{n}회차_{p}" / "_작업" / "영상_자막_기록").glob("*_시간표.md"))
        if not t: raise SystemExit(f"실전반_{n}회차_{p}: 시간표가 없다")
        for m in re.finditer(r"^\| (\d+)(?:~(\d+))? \| (\d+):(\d+)(?: \(SLIDE \d+부터 (\d+):([\d.]+)\))? \| ([\d.]+) \|", t[0].read_text(encoding="utf-8"), re.M):
            a, b, total = int(m.group(1)), m.group(2), float(m.group(7))
            if b:
                first = int(m.group(5)) * 60 + float(m.group(6)) - (int(m.group(3)) * 60 + int(m.group(4)))
                out[a], out[int(b)] = round(first), round(total - first)
            else: out[a] = round(total)
    return out

doc = ["# 장별점검 — 실전반 5 · 6회차 온라인 덱 전 장(영상 시간표 실측 · 최종 강조 설정)", "",
       "길이(초)는 영상 시간표의 장 구획 길이(쉼을 넣은 음성, 실측)다. 굵은 장은 2분이 넘는다. 강조 수는 최종 강조 설정"
       "(`workspace/강의제작/제작도구/구성/실전반/<NN>회차/강조_*.json`)의 표시 수다. 장 꼴과 넣지 않은 까닭은 감독이 덱 장 그림과 대본을 나란히 보고 정했다"
       "(생성기 `작업/…/영상/실전반/장별점검_생성.py`의 TYPE). 강조를 고른 기준은 영상.md V-134 · V요-40 4-1.", ""]
summary = []
for n in ("05", "06"):
    T, L, ty = titles(n), lengths(n), TYPE[n]
    marks = {}
    for f in sorted((ROOT / f"workspace/강의제작/제작도구/구성/실전반/{n}회차").glob("강조_*.json")):
        for m in json.loads(f.read_text(encoding="utf-8"))["표시"]: marks.setdefault(int(m["장"]), []).append(m["대상"])
    miss = [s for s in T if s not in ty]
    if miss: raise SystemExit(f"{n}: 꼴이 없는 장 {miss}")
    long_ = [s for s in sorted(T) if L.get(s, 0) > 120]
    doc += [f"## 실전{int(n)}", "", f"덱 {len(T)}장 · 합계 {sum(L.values())/60:.1f}분 · 2분 넘는 장 {len(long_)}({', '.join(map(str, long_)) or '없음'}) · 강조 {sum(map(len, marks.values()))}개({len(marks)}장)", "",
            "| 장 | 길이(초) | 학생이 따라갈 화면 속 대상 | 강조 | 넣지 않은 까닭 |", "|---|---:|---|---|---|"]
    for s in sorted(T):
        k = ty[s]; ms = marks.get(s, [])
        target = T[s] + ("" if not ms else ": " + " → ".join(ms))
        reason = "" if ms else REASON[k]
        if not ms and L.get(s, 0) > 120 and k not in ("자리", "실습", "퀴즈"): reason = "**2분 넘음** — " + reason
        sl = f"**{s}**" if L.get(s, 0) > 120 else str(s)
        doc.append(f"| {sl} | {L.get(s, '—')} | {target.replace('|', '/')} | {'있음(%d)' % len(ms) if ms else '없음'} | {reason} |")
    doc.append("")
    summary.append((n, len(T), sum(L.values()), long_, sum(map(len, marks.values()))))
(W / "영상" / "실전반" / "장별점검.md").write_text("\n".join(doc), encoding="utf-8")
for s in summary: print(f"실전{s[0]}: {s[1]}장 · {s[2]/60:.1f}분 · 2분 넘는 장 {s[3]} · 강조 {s[4]}")
