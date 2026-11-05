"""강조 계획의 「찾을 글」을 렌더 PDF에서 찾아 영상 좌표(1920×1080)로 바꾸고, 문장 · 낱말 · 끝문장이 그 장 대본에 그대로 있는지 본다.
언제: 덱마다 강조 계획을 쓸 때 — 글 위치 찾기 · 대본 대조를 다시 만들지 않으려고 쓴다. 뒤이어 강조미리보기.py로 그려 본다.
명령: <py> workspace/강의제작/제작도구/기존제작/tools/video/강조좌표.py <렌더.pdf> <대본 폴더> <계획.json> --출력 <결과.json> [--위 104]
      <py> workspace/강의제작/제작도구/기존제작/tools/video/강조좌표.py --검사 <한 편의 대본.md> <강조_영상이름.json>

- 계획: {"표시": [{"장": 5, "문장": "…", "낱말": "…", "끝문장": "…"(없어도 됨), "찾을글": "화면 글" | ["글 하나", "글 둘"] | [["글", 1]], "대상": "…", "모양": "띠"(없으면 동그라미)}]}
  찾을글을 여럿 주면 합친 상자, ["글", 1]은 그 장에서 그 글의 둘째 자리. 찾을글 대신 "그림": [x, y, rx, ry]는 장의 큰 그림 안 좌표(그림 폭 1200 기준).
- 결과: 표시마다 모양에 맞는 칸(「상자」 또는 「중심」 · 「반지름」). 좌표는 어림이다 — 최종 확인은 미리보기 · 영상 프레임으로 한다.
- 문장 나누기는 강의영상.py cuts 그대로라 자막 문장과 같다. --위: 제목 띠로 보고 뺄 PDF 위 여백(점). 못 찾은 것은 전부 좌표와 함께 찍고 결과를 쓰지 않는다.
"""
import argparse, json, re, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.dont_write_bytecode = True
_argv, sys.argv = sys.argv, sys.argv[:1]
import 쉼옮기기 as breath  # noqa: E402
sys.argv = _argv
tool = breath.tool


def blocks(folder):
    out = {}
    for f in sorted(Path(folder).glob("*.md")):
        for first, last, text in tool.slides_text(f):
            for n in range(first, last + 1):
                out[n] = (f.name, breath.sentences(text))
    return out


def lines_of(page, top):
    """장의 글을 줄로 묶는다(글꼴이 섞인 코드 줄도 한 줄). 제목 · 메시지 띠는 뺀다."""
    ws = [w for w in page.get_text("words") if w[1] > top]
    ws.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    rows = []
    for w in ws:
        cy = (w[1] + w[3]) / 2
        if rows and abs(rows[-1][0] - cy) < 4:
            rows[-1][1].append(w)
        else:
            rows.append([cy, [w]])
    for r in rows:
        r[1].sort(key=lambda w: w[0])
    return [r[1] for r in rows]


def hits(page, q, top):
    want = q.replace(" ", "").replace(" ", "")
    out = []
    for row in lines_of(page, top):
        text, spans = "", []
        for w in row:
            s = w[4].replace(" ", "")
            spans.append((len(text), len(text) + len(s), w))
            text += s
        at = text.find(want)
        while at >= 0:
            end = at + len(want)
            used = [w for a, b, w in spans if a < end and b > at]
            out.append((min(w[0] for w in used), min(w[1] for w in used), max(w[2] for w in used), max(w[3] for w in used)))
            at = text.find(want, end)
    return out


def rect_of(page, q, top, where):
    """찾을글 → PDF 좌표 상자. 찾지 못하면 ValueError."""
    rs = []
    for one in ([q] if isinstance(q, str) else q):
        text, nth = (one, 0) if isinstance(one, str) else one
        hs = hits(page, text, top)
        if len(hs) <= nth:
            raise ValueError(f"{where}: 화면에서 「{text}」을 {nth + 1}번째로 못 찾음(찾은 수 {len(hs)})")
        rs.append(hs[nth])
    return min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs), len(rs)


def circle(x0, y0, x1, y1, n, k):
    """글의 네 귀퉁이가 동그라미 안에 들게 잡는다."""
    w, h = (x1 - x0) * k / 2, (y1 - y0) * k / 2
    ry = h + (9 if n == 1 else 12)
    rx = max(min(w / (1 - (h / ry) ** 2) ** 0.5, w + 40), w + 12)
    return [round((x0 + x1) * k / 2), round((y0 + y1) * k / 2)], [round(rx), round(ry)]


def figure(page, x, y, rx, ry, k, where):
    rect = None
    for im in page.get_images(full=True):
        rs = page.get_image_rects(im[0])
        if rs and rs[0].width > 400:
            rect = rs[0]
    if rect is None:
        raise ValueError(f"{where}: 장에 폭 400점 넘는 그림이 없다")
    s = rect.width / 1200
    return [round((rect.x0 + x * s) * k), round((rect.y0 + y * s) * k)], [round(rx * s * k), round(ry * s * k)]


def check_config(script, config):
    """영상 없이 확정 설정의 앵커가 이 편의 자막에서 한 곳으로 정해지는지 본다."""
    from 강조표시 import shape_problem

    script = script.resolve()
    if script.parent.name != "대본" or script.parents[2].name != "이론":
        sys.exit(f"{script}: <과정>/이론/<회차>/대본/ 아래의 정본을 준다")
    expected = f"강조_{script.parents[3].name}_{script.parents[1].name}_{script.stem}.json"
    if config.name != expected:
        sys.exit(f"{script.name}: 대응하는 설정 이름은 {expected}이다")
    cfg = json.loads(config.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or not isinstance(cfg.get("표시"), list):
        sys.exit(f"{config}: 표시 목록이 없다")
    blocks = {first: (last, breath.sentences(text)) for first, last, text in tool.slides_text(script)}
    errors = []
    for i, mark in enumerate(cfg["표시"], 1):
        if not isinstance(mark, dict):
            errors.append(f"표시 {i}: 설정은 장과 앵커가 있는 객체여야 한다")
            continue
        n = mark.get("장")
        where = f"표시 {i} · {n}장"
        problem = shape_problem(mark)
        if problem:
            errors.append(f"{where}: {problem}")
        if "파일" in mark and mark["파일"] != script.name:
            errors.append(f"{where}: 대본 파일이 다르다")
        if type(n) is not int or n not in blocks:
            errors.append(f"{where}: 이 편의 시간표에 독립된 시작 장이 없다(묶음 구획은 첫 장만 있음)")
            continue
        last, sentences = blocks[n]
        start, word, end = mark.get("문장"), mark.get("낱말"), mark.get("끝문장")
        if not isinstance(start, str) or not start.strip() or sentences.count(start) != 1:
            errors.append(f"{where}: 시작 문장은 이 장에서 한 번 나와야 한다 — {start}")
            continue
        if (not isinstance(word, str) or not word.strip()
                or start.find(word) < 0 or start.find(word) != start.rfind(word)):
            errors.append(f"{where}: 낱말은 시작 문장에서 한 곳을 가리켜야 한다 — {word}")
        if end and (sentences.count(end) != 1 or sentences.index(end) <= sentences.index(start)):
            errors.append(f"{where}: 끝문장은 시작 뒤에 한 번 나와야 한다 — {end}")
        if last != n and (start != sentences[0] or len(sentences) < 2 or end != sentences[1]):
            errors.append(f"{where}: 묶음의 첫 장은 첫 문장에서 보이고 둘째 문장에서 지워야 한다")
    if errors:
        sys.exit("\n".join(errors))
    print(f"{script.name}: 강조 {len(cfg['표시'])}개 · 대본 앵커·모양 문제 0")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    if sys.argv[1:2] == ["--검사"]:
        ap.add_argument("--검사", nargs=2, type=Path, metavar=("대본", "강조설정"))
        check_config(*ap.parse_args().검사)
        return
    import fitz

    ap.add_argument("pdf"); ap.add_argument("scripts"); ap.add_argument("plan")
    ap.add_argument("--출력", dest="out", required=True)
    ap.add_argument("--위", dest="top", type=float, default=104)
    a = ap.parse_args()
    doc = fitz.open(a.pdf)
    k = 1920 / doc[0].rect.width
    bl = blocks(a.scripts)
    errs, out = [], []
    for i, m in enumerate(json.loads(Path(a.plan).read_text(encoding="utf-8"))["표시"], 1):
        n = int(m["장"]); where = f"표시 {i} · {n}장"
        if n not in bl:
            errs.append(f"{where}: 대본에 그 장이 없다"); continue
        ss = bl[n][1]
        s, w, e = m["문장"], m["낱말"], m.get("끝문장")
        if s not in ss:
            errs.append(f"{where}: 문장이 대본에 없다 — {s}")
        elif w not in s:
            errs.append(f"{where}: 낱말 「{w}」이 문장에 없다")
        if e and e not in ss:
            errs.append(f"{where}: 끝문장이 대본에 없다 — {e}")
        elif e and s in ss and ss.index(e) <= ss.index(s):
            errs.append(f"{where}: 끝문장이 문장보다 앞이다 — {e}")
        r = {x: m[x] for x in m if x not in ("찾을글", "그림")}
        r["파일"] = bl[n][0]
        r.setdefault("모양", "동그라미")
        try:
            if "그림" in m:
                c, rad = figure(doc[n - 1], *m["그림"], k, where)
                if r["모양"] == "동그라미":
                    r["중심"], r["반지름"] = c, rad
                else:
                    r["상자"] = [c[0] - rad[0], c[1] - rad[1], c[0] + rad[0], c[1] + rad[1]]
            else:
                x0, y0, x1, y1, cnt = rect_of(doc[n - 1], m["찾을글"], a.top, where)
                if r["모양"] == "동그라미":
                    r["중심"], r["반지름"] = circle(x0, y0, x1, y1, cnt, k)
                else:
                    r["상자"] = [round(x0 * k), round(y0 * k), round(x1 * k), round(y1 * k)]
        except ValueError as ex:
            errs.append(str(ex))
        out.append(r)
    if errs:
        sys.exit("쓰지 않았다 — " + f"{len(errs)}건\n  " + "\n  ".join(errs))
    Path(a.out).write_text(json.dumps({"표시": out}, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"표시 {len(out)} · 장 {len({x['장'] for x in out})} → {a.out}")


if __name__ == "__main__":
    main()
