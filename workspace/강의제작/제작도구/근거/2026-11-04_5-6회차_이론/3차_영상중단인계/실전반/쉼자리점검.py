"""굽기 전에 쉴 자리마다 조용한 곳이 있는지 강의영상.py와 같은 방법(0.1초 창, 없으면 0.4초 창)으로 잰다. 저장소 루트에서: python3 쉼자리점검.py <대본 …>"""
import sys, json, re, array, subprocess, importlib.util, hashlib
from pathlib import Path
files = sys.argv[1:]; sys.argv = ['x', '_', '_']
V = Path('workspace/강의제작/제작도구/기존제작/tools/video')
spec = importlib.util.spec_from_file_location('lv', V / '강의영상.py'); M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
def dec(ch, i): return ch[i] == "." and 0 < i < len(ch) - 1 and all(c.isascii() and c.isalnum() for c in (ch[i - 1], ch[i + 1]))
def mark_(ch, i):
    mark = i - 1 if ch[i] in "’”』」" and i else i
    if ch[mark] not in ".?!" or dec(ch, mark): return ""
    if mark == i: return "" if i + 1 < len(ch) and ch[i + 1] in "’”』」" else ch[mark]
    tail = "".join(ch[i + 1:i + 12])
    if tail and (not tail[0].isspace() or re.match(r"\s+(?:하고|라고|하며|라며|라는|라는지)(?:\s|$)", tail)): return ""
    return ch[mark]
bad = 0
for f in files:
    for a, b, t in M.slides_text(f):
        h = M.cache_key(t, '1PdAOcPlPTz12RwMyFVp', 'eleven_v4', 0.8)
        al = json.loads((V / '음성_저장' / f'{h}.json').read_text())
        ch, st, en = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
        cuts = []; i = 0; b0 = 0
        while i < len(ch):
            m = mark_(ch, i)
            if m:
                j = i + 1; para = False
                while j < len(ch) and ch[j] in " \n\"'」)": para = para or ch[j] == "\n"; j += 1
                if j < len(ch): cuts.append(((en[i], st[j]), "para" if para else ("q" if m == "?" else "s"), "".join(ch[b0:j]).strip())); b0 = j
                i = j
            else: i += 1
        sents = [x for _, _, x in cuts] + ["".join(ch[b0:]).strip()]
        lv = None
        if len(sents) > 1:
            hh = hashlib.sha1(json.dumps(sents, ensure_ascii=False).encode()).hexdigest()[:16]
            p = V / '쉼_저장' / f'{hh}.json'
            lv = json.loads(p.read_text())['쉼'] if p.exists() else None
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(V / '음성_저장' / f'{h}.mp3'), '-ac', '1', '-ar', '44100', '-f', 's16le', '-'], capture_output=True).stdout
        d = array.array('h', raw); fr = 44100; hs = int(fr * 0.01)
        for k, (win, typ, s) in enumerate(cuts):
            level = lv[k] if lv else 1
            need = max({0: 0, 1: .15, 2: .45, 3: .8}[level], {"s": 0, "q": .5, "para": .4}[typ]) > 0
            if not need: continue
            ok = None
            for back in (0.1, 0.4):
                a0, b1 = max(0.0, win[0] - back), max(win[0], win[1])
                fs = [(a0 + x * 0.01, max(abs(v) for v in d[int((a0 + x * 0.01) * fr):int((a0 + x * 0.01) * fr) + hs] or [0])) for x in range(max(1, int((b1 - a0) / 0.01)))]
                lim = max(min(e for _, e in fs) * 2, 60); best, run = [], []
                for t0, e in fs:
                    run = run + [t0] if e <= lim else []
                    if len(run) > len(best): best = run
                peak = max(e for t0, e in fs if best[0] <= t0 <= best[-1])
                if peak <= 300: ok = back; break
            if ok is None: bad += 1; print(f"없음 {Path(f).stem} 장 {a} 자리 {k} 종류 {typ} 쉼 {level} 「{s[-20:]}」 세기 {peak}")
            elif ok == 0.4: print(f"넓힌 창 {Path(f).stem} 장 {a} 자리 {k} 「{s[-20:]}」")
print("조용한 곳 없는 자리", bad)
