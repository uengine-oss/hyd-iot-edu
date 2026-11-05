"""대본을 고친 뒤 쉼_저장/의 쉼을 같은 (앞 문장, 뒤 문장) 자리에서 옮겨 오고, 사람이 정할 자리만 목록(JSON)으로 낸다. 유료 호출 없음.
언제: 대본을 고치고 음성을 산 뒤, `강의영상.py --breath`로 굽기 전. 쉼을 자리마다 처음부터 정하지 않으려고 쓴다.
명령: <py> workspace/강의제작/제작도구/기존제작/tools/video/쉼옮기기.py <대본 …> --출력 목록.json [--옛판 커밋] [--쓰기] [--파형 --voice ID] [--저장 폴더]
      <py> …/쉼옮기기.py --채움 목록.json [--저장 폴더]     # 목록의 "값" 칸을 사람이 채운 뒤 저장한다

- 문장 나누기 · 저장 이름은 강의영상.py의 cuts · breath_key를 그대로 쓴다(사본 없음). 음성 없이 대본 글로도 같은 문장이 나온다.
- 찾는 순서: ① --옛판 커밋의 같은 대본 파일이 쓴 쉼 ② 쉼_저장/ 전체. 앞에서 값이 하나로 정해지면 옮긴다. 값이 둘 이상이면 정하지 않고 「값여럿」으로, 어디에도 없으면 「새자리」로 낸다.
- 저장 쓰기는 --쓰기 · --채움 때만이고, 자리가 다 찬 구획만 쓴다. 이미 값이 있는 파일은 덮지 않는다(값이 다르면 멈춘다). 한 구획에 크게(3)가 셋 이상이면 --쓰기는 사람이 읽어 가를 후보(「크게셋이상」)로 내고 쓰지 않으며, --채움은 사람이 읽고 정한 값이므로 쓰고 경고 줄만 낸다(영상.md V-12).
- --파형: 음성 캐시가 있는 구획에서 쉼을 넣을 자리에 조용한 곳이 없는 곳을 굽기 전에 찾아 목록에 적는다(굽기가 거기서 멈춘다). ffmpeg가 PATH에 있어야 한다. 값 0이면 그 자리는 자르지 않는다.
"""
import argparse
import array
import collections
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
import 강의영상 as tool  # noqa: E402


def sentences(text):
    """대본 구획 글의 문장 목록. 글자 시각만 빼면 음성 정렬과 같은 글자를 도는 cuts 그대로다."""
    n = len(text)
    c, tail = tool.cuts({"al": {"characters": list(text), "character_start_times_seconds": [0.0] * n, "character_end_times_seconds": [0.0] * n}})
    return [x for _, _, x in c] + [tail]


def load(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(d, dict) or not isinstance(d.get("문장"), list) or "쉼" not in d:
        sys.exit(f"{path}: 쉼 파일 꼴이 아니다(문장 · 쉼 칸)")
    return d


def valid(d):
    v = d.get("쉼")
    return isinstance(v, list) and len(v) == len(d["문장"]) - 1 and all(x in (0, 1, 2, 3) for x in v)


def write(path, sents, levels):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"문장": sents, "쉼": levels}, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    tmp.replace(path)


def add_pairs(table, d, where):
    for i, level in enumerate(d["쉼"]):
        table[(d["문장"][i], d["문장"][i + 1])][level] += 1
    return table


def store_pairs(bdir):
    table, files, nulls = collections.defaultdict(collections.Counter), 0, 0
    for f in sorted(bdir.glob("*.json")):
        d = load(f)
        if valid(d):
            add_pairs(table, d, f); files += 1
        else:
            nulls += 1
    return table, files, nulls


def old_pairs(rel, commit, bdir, root, warn):
    """그 커밋의 같은 대본(rel = 저장소 기준 경로)이 실제로 쓴 쉼 파일들의 쌍."""
    r = subprocess.run(["git", "show", f"{commit}:{rel}"], capture_output=True, cwd=root)
    table = collections.defaultdict(collections.Counter)
    if r.returncode:
        warn.append(f"{rel}: 커밋 {commit}에 없다 — 전체 사전만 본다")
        return table
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "옛판.md"; p.write_bytes(r.stdout)
        blocks = tool.slides_text(p)
    for first, _, text in blocks:
        ss = sentences(text)
        if len(ss) < 2: continue
        f = bdir / f"{tool.breath_key(ss)}.json"
        if f.exists() and valid(load(f)):
            add_pairs(table, load(f), f)
    return table


def wave_check(block, levels, voice, ffmpeg_ok):
    """쉼을 넣을 자리 가운데 조용한 곳이 없는 자리."""
    first, _, text = block
    h = tool.cache_key(text, voice, tool.a.model, tool.a.speed)
    mp3, js = tool.CACHE / f"{h}.mp3", tool.CACHE / f"{h}.json"
    if not (mp3.exists() and js.exists()):
        return None
    al = json.loads(js.read_text(encoding="utf-8"))
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(mp3), "-ac", "1", "-ar", "44100", "-f", "s16le", "-"])
    data = array.array("h", raw)
    c, _ = tool.cuts({"al": al})
    bad = []
    for i, (win, kind, sent) in enumerate(c):
        level = levels[i] if i < len(levels) else None
        if level == 0 and kind == "s":   # 0초 쉼은 소리를 끊지 않는다
            continue
        at, peak = tool.quiet_point(data, 44100, win)
        if peak > tool.QUIET_MAX:
            bad.append({"장": first, "번호": i + 1, "종류": kind, "값": level, "세기": peak, "앞": sent[-30:]})
    return bad


def run(a):
    bdir = Path(a.store) if a.store else tool.HERE / "쉼_저장"
    if not bdir.is_dir():
        sys.exit(f"{bdir}: 쉼 저장 폴더가 없다")
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=tool.HERE, check=True).stdout.strip())
    table, files, nulls = store_pairs(bdir)
    warn, sections, waves = [], [], []
    ct = collections.Counter()
    seen = set()
    for script in a.scripts:
        olds = old_pairs(Path(script).resolve().relative_to(root).as_posix(), a.old, bdir, root, warn) if a.old else {}
        blocks = tool.slides_text(script)
        for block in blocks:
            first, last, text = block
            ss = sentences(text)
            if len(ss) < 2: continue
            key = tool.breath_key(ss)
            f = bdir / f"{key}.json"
            if key in seen: continue
            seen.add(key)
            if f.exists() and valid(load(f)):
                ct["이미있음_구획"] += 1
                if a.wave:
                    bad = wave_check(block, load(f)["쉼"], a.voice, True)
                    if bad is None: ct["파형_음성없음"] += 1
                    else: waves += [dict(x, 파일=Path(script).name) for x in bad]
                continue
            levels, seats = [], []
            for i, (x, y) in enumerate(zip(ss, ss[1:])):
                o, s = (olds.get((x, y)) if olds else None), table.get((x, y))
                if o and len(o) == 1:
                    levels.append(next(iter(o))); ct["옮김_옛판"] += 1
                elif (o and len(o) > 1) or (s and len(s) > 1):
                    c = o if o and len(o) > 1 else s
                    levels.append(None); ct["값여럿"] += 1
                    seats.append({"번호": i + 1, "앞": x, "뒤": y, "까닭": "값여럿", "후보": {str(k): v for k, v in sorted(c.items())}, "값": None})
                elif s:
                    levels.append(next(iter(s))); ct["옮김_사전"] += 1
                else:
                    levels.append(None); ct["새자리"] += 1
                    seats.append({"번호": i + 1, "앞": x, "뒤": y, "까닭": "새자리", "값": None})
            big = levels.count(3)
            state = "판단필요" if seats else ("크게셋이상" if big > 2 else "다옮김")
            ct[state + "_구획"] += 1
            sec = {"파일": Path(script).name, "장": first if first == last else f"{first}~{last}", "키": key, "상태": state, "문장": ss, "쉼": levels, "자리": seats}
            sections.append(sec)
            if a.write and state == "다옮김":
                write(f, ss, levels); ct["쓴_구획"] += 1
            if a.wave:
                bad = wave_check(block, levels, a.voice, True)
                if bad is None: ct["파형_음성없음"] += 1
                else: waves += [dict(x, 파일=Path(script).name) for x in bad]
    total = ct["옮김_옛판"] + ct["옮김_사전"] + ct["값여럿"] + ct["새자리"]
    single = sum(1 for v in table.values() if len(v) == 1)
    summary = {"저장": str(bdir), "저장_값있는파일": files, "저장_빈파일": nulls, "사전_문장쌍": len(table), "사전_값하나": single, "옛판": a.old, "자리_합": total, **dict(ct), "경고": warn}
    Path(a.out).write_text(json.dumps({"요약": summary, "구획": sections, "조용한곳없음": waves}, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    for k, v in summary.items():
        if k != "경고": print(f"{k}: {v}")
    for w in warn: print("경고:", w)
    if a.wave: print("조용한곳없음:", len(waves))
    print(f"목록 {a.out} · 사람이 정할 자리 {ct['값여럿'] + ct['새자리']}")


def fill(a):
    bdir = Path(a.store) if a.store else tool.HERE / "쉼_저장"
    d = json.loads(Path(a.fill).read_text(encoding="utf-8"))
    errs, todo, warns = [], [], []
    for sec in d["구획"]:
        levels = list(sec["쉼"])
        for seat in sec["자리"]:
            v = seat.get("값")
            if v not in (0, 1, 2, 3):
                errs.append(f"{sec['파일']} 장 {sec['장']} 자리 {seat['번호']}: 값이 0~3이 아니다({v!r}) — 「{seat['앞'][-20:]}」 → 「{seat['뒤'][:20]}」")
            levels[seat["번호"] - 1] = v
        if levels.count(3) > 2:
            warns.append(f"경고: {sec['파일']} 장 {sec['장']}: 크게(3)가 {levels.count(3)}곳이다 — 화제가 바뀌는 자리만인지 읽었는가(영상.md V-12)")
        if tool.breath_key(sec["문장"]) != sec["키"]:
            errs.append(f"{sec['파일']} 장 {sec['장']}: 문장과 키가 맞지 않는다(목록을 손으로 고쳤는가)")
        f = bdir / f"{sec['키']}.json"
        if f.exists():
            old = load(f)
            if valid(old) and old["쉼"] != levels:
                errs.append(f"{f}: 이미 다른 값이 있어 덮지 않는다")
            elif valid(old):
                continue
        todo.append((f, sec["문장"], levels))
    if errs:
        sys.exit("쓰지 않았다 —\n  " + "\n  ".join(errs))
    for w in warns:
        print(w)
    for f, ss, levels in todo:
        write(f, ss, levels)
    print(f"썼다 {len(todo)}구획 → {bdir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("scripts", nargs="*")
    ap.add_argument("--출력", dest="out")
    ap.add_argument("--옛판", dest="old", help="고치기 전 대본이 있는 커밋")
    ap.add_argument("--쓰기", dest="write", action="store_true", help="자리가 다 찬 구획을 저장에 쓴다")
    ap.add_argument("--채움", dest="fill", help="사람이 값을 채운 목록을 저장에 쓴다")
    ap.add_argument("--저장", dest="store", help="쉼 저장 폴더(기본 쉼_저장/, 시험은 사본으로)")
    ap.add_argument("--파형", dest="wave", action="store_true")
    ap.add_argument("--voice", help="--파형이 음성 캐시를 찾을 음성 ID")
    a = ap.parse_args()
    if a.fill:
        fill(a)
    else:
        if not a.scripts or not a.out:
            ap.error("대본 파일과 --출력을 준다")
        if a.wave and not a.voice:
            ap.error("--파형은 --voice가 필요하다")
        run(a)
