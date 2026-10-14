"""덱 MD의 문구를 윤문에 보내고 되돌려 넣는 도구.

    python3 production/tools/deck/덱문구.py 요청문 <덱 MD> <첫 장> <끝 장> <요청문 파일>
    python3 production/tools/deck/덱문구.py 검사 <원문 파일> <윤문 파일>
    python3 production/tools/deck/덱문구.py 넣기 <덱 MD> <첫 장> <끝 장> <윤문 파일>
    python3 production/tools/deck/덱문구.py 자르기 <덱 MD> <첫 장> <끝 장> <출력 MD>

- 요청문: 장의 부제 · 메시지 · 문장 · 노트와 요소의 글을 「[키] 문구」 한 줄씩으로 뽑아 장마다 묶고(「── N장: 한 화면 ──」), 윤문에 보낼 요청문을 만든다.
  같은 이름에 `_원문.txt`도 함께 남긴다. 제목, 그림 좌표, 코드, 아이콘, 유형은 뽑지 않는다.
- 검사: 키마다 숫자, 영문 이름, 굵게 표시(**), 화면 줄바꿈( / )의 수가 원문과 같은지 본다. 다르면 키와 함께 찍고 실패한다.
- 넣기: 윤문 파일의 문구를 덱 MD의 같은 자리에 되돌려 넣는다. 키가 하나라도 빠지거나 늘면 아무것도 쓰지 않고 멈춘다.
- 자르기: 첫 장부터 끝 장까지만 담은 덱 MD를 만든다(검토용 빌드). 그림 경로는 원래 덱 폴더를 가리키게 바꾼다.
"""
import re
import sys
from pathlib import Path

상황 = ("아래는 제조 AI 교육과정 강의 슬라이드의 문구다. 내용과 설명의 수준은 자료를 보고 이미 다 맞춰 놓은 완성본이다. "
        "내용은 손대지 말고 윤문 작업만 해 달라.")
꼴 = ("[Sxx.노트]는 강사가 읽는 말이고, 나머지는 화면에 들어가는 글이다. 각 줄 맨 앞의 [키]와 줄의 수, 순서는 그대로 두고, "
     "문장 안의 \" / \"(화면 줄바꿈)와 **(강조 표시)도 그대로 둔 채 같은 꼴로 돌려 달라.")
뽑지않는유형 = ("코드", "목차", "간지", "표지")


def 장들(t, first, last):
    for b in re.split(r"(?=^## SLIDE )", t, flags=re.M):
        m = re.match(r"## SLIDE (\d+) ", b)
        if m and first <= int(m.group(1)) <= last:
            yield int(m.group(1)), b


def 뽑기(t, first, last):
    out = []
    for n, b in 장들(t, first, last):
        body = b.split("### 제작 기준")[0]
        typ = re.search(r"^- 유형: (.*)$", body, re.M).group(1)
        for k in ("부제", "메시지", "문장", "노트"):
            mm = re.search(rf"^- {k}: (.*)$", body, re.M)
            if mm:
                out.append((f"S{n:02d}.{k}", mm.group(1)))
        if typ in 뽑지않는유형:
            continue
        for e in re.finditer(r"^  (\d+)\. (.*)$", body, re.M):
            parts = e.group(2).split(" | ")
            if typ == "삽화" and len(parts) == 3:
                parts = parts[:2]          # 셋째 칸은 좌표
            for j, p in enumerate(parts):
                if p.strip():
                    out.append((f"S{n:02d}.요소{e.group(1)}.{j + 1}", p))
    return out


def 읽기(path):
    pairs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\[(S\d\d\.[^\]]+)\] (.*)$", line)
        if m:
            pairs.append((m.group(1), m.group(2)))
    return pairs


def 넣기(t, pairs, first, last):
    orig, new = dict(뽑기(t, first, last)), dict(pairs)
    if set(orig) != set(new):
        sys.exit(f"[실패] 키가 맞지 않는다. 빠짐 {sorted(set(orig) - set(new))} / 늘어남 {sorted(set(new) - set(orig))}")
    blocks = re.split(r"(?=^## SLIDE )", t, flags=re.M)
    for i, b in enumerate(blocks):
        m = re.match(r"## SLIDE (\d+) ", b)
        if not m or not (first <= int(m.group(1)) <= last):
            continue
        n = int(m.group(1))
        head, sep, tail = b.partition("### 제작 기준")
        for k in ("부제", "메시지", "문장", "노트"):
            key = f"S{n:02d}.{k}"
            if key in new:
                head = re.sub(rf"^- {k}: .*$", lambda _: f"- {k}: {new[key]}", head, count=1, flags=re.M)

        def 요소(e):
            parts = e.group(2).split(" | ")
            for j in range(len(parts)):
                key = f"S{n:02d}.요소{e.group(1)}.{j + 1}"
                if key in new:
                    parts[j] = new[key]
            return f"  {e.group(1)}. " + " | ".join(parts)

        if not re.search(rf"^- 유형: ({'|'.join(뽑지않는유형)})$", head, re.M):
            head = re.sub(r"^  (\d+)\. (.*)$", 요소, head, flags=re.M)
        blocks[i] = head + sep + tail
    return "".join(blocks)


def 지문(s):
    return (sorted(re.findall(r"\d+(?:[.,]\d+)?", s)), sorted(re.findall(r"[A-Za-z][A-Za-z0-9_\-]*", s)),
            s.count("**"), s.count(" / "))


def main():
    cmd = sys.argv[1]
    if cmd == "검사":
        a, b = dict(읽기(sys.argv[2])), dict(읽기(sys.argv[3]))
        bad = [k for k in a if k not in b or 지문(a[k]) != 지문(b[k])] + [k for k in b if k not in a]
        for k in bad:
            print(f"[다름] {k}\n  원문: {a.get(k)}\n  윤문: {b.get(k)}")
        if bad:
            sys.exit(f"[실패] {len(bad)}곳의 숫자 · 이름 · 굵게 · 줄바꿈이 원문과 다르다")
        print(f"[통과] {len(a)}개 문구의 숫자 · 이름 · 굵게 · 줄바꿈이 원문과 같다")
        return
    md, first, last, out = Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), Path(sys.argv[5])
    t = md.read_text(encoding="utf-8")
    if cmd == "요청문":
        pairs = 뽑기(t, first, last)
        lines, prev = [], None
        for k, v in pairs:      # 한 장의 문구는 한 화면에 함께 나오므로 장마다 묶는다(줄마다 따로 다듬으면 같은 말이 겹친다)
            n = int(k[1:3])
            if n != prev:
                lines += ([""] if prev is not None else []) + [f"── {n}장: 한 화면 ──"]
                prev = n
            lines.append(f"[{k}] {v}")
        out.with_name(out.stem + "_원문.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        out.write_text(상황 + "\n\n" + 꼴 + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
        print(f"{out} — 문구 {len(pairs)}개 (원문: {out.stem}_원문.txt)")
    elif cmd == "넣기":
        pairs = 읽기(out)
        md.write_text(넣기(t, pairs, first, last), encoding="utf-8")
        print(f"{md} — 문구 {len(pairs)}개를 넣음")
    elif cmd == "자르기":
        keep = "".join(b for _, b in 장들(t, first, last))
        head = t[: t.index("## SLIDE ")]
        fig = (md.parent / "figures").resolve().as_posix()
        out.write_text((head + keep).replace("- 그림: figures/", f"- 그림: {fig}/"), encoding="utf-8")
        print(f"{out} — {first}~{last}장")
    else:
        sys.exit(f"[실패] 모르는 명령: {cmd}")


if __name__ == "__main__":
    main()
