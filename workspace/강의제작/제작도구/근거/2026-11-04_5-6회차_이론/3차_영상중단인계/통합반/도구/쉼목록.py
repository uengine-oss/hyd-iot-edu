"""이 과정 대본들의 장 구획마다 쉼_저장 파일 이름 · 문장 목록을 강의영상.py와 같은 방법으로 셈한다.
    python3 쉼목록.py <출력.json> <대본 …>
옛 판(이미 채운 쉼_저장)의 같은 두 문장 이음이 있으면 그 단계를 제안으로 붙인다(옮김 후보). 쓰지는 않는다."""
import json, sys, hashlib, re, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
V = ROOT / "workspace/강의제작/제작도구/기존제작/tools/video"
sys.path.insert(0, str(V))
import importlib.util
spec = importlib.util.spec_from_file_location("lv", V / "강의영상.py"); lv = importlib.util.module_from_spec(spec); spec.loader.exec_module(lv)
VOICE, MODEL, SPEED = "1PdAOcPlPTz12RwMyFVp", "eleven_v4", 0.80

def decimal(ch, i): return ch[i] == "." and 0 < i < len(ch) - 1 and all(c.isascii() and c.isalnum() for c in (ch[i - 1], ch[i + 1]))   # 강의영상.py와 같게
def sentence_mark(ch, i):
    mark = i - 1 if ch[i] in "’”』」" and i else i
    if ch[mark] not in ".?!" or decimal(ch, mark): return ""
    if mark == i: return "" if i+1 < len(ch) and ch[i+1] in "’”』」" else ch[mark]
    tail = "".join(ch[i+1:i+12])
    if tail and (not tail[0].isspace() or re.match(r"\s+(?:하고|라고|하며|라며|라는|라는지)(?:\s|$)", tail)): return ""
    return ch[mark]
def cuts(al):
    ch, st, en = al.get("characters") or [], al.get("character_start_times_seconds") or [], al.get("character_end_times_seconds") or []
    out, i, b = [], 0, 0
    while i < len(ch):
        mark = sentence_mark(ch, i)
        if mark:
            j = i + 1; para = False
            while j < len(ch) and ch[j] in " \n\"'」)":
                para = para or ch[j] == "\n"; j += 1
            if j < len(ch): out.append(("para" if para else ("q" if mark == "?" else "s"), "".join(ch[b:j]).strip())); b = j
            i = j
        else: i += 1
    return out, "".join(ch[b:]).strip()

# 옛 판 이음(앞 문장, 뒤 문장) → 단계
pairs = {}
for f in glob.glob(str(V / "쉼_저장/*.json")):
    d = json.loads(Path(f).read_text())
    if isinstance(d.get("쉼"), list):
        s = d["문장"]
        for k, x in enumerate(d["쉼"]): pairs.setdefault((s[k], s[k+1]), set()).add(x)
out = []
for sc in sys.argv[2:]:
    for f, l, t in lv.slides_text(sc):
        al = json.loads((V / "음성_저장" / f"{lv.cache_key(t, VOICE, MODEL, SPEED)}.json").read_text())
        c, tail = cuts(al); sents = [x for _, x in c] + [tail]
        if len(sents) < 2: continue
        h = hashlib.sha1(json.dumps(sents, ensure_ascii=False).encode()).hexdigest()[:16]
        fp = V / "쉼_저장" / f"{h}.json"
        cur = json.loads(fp.read_text()).get("쉼") if fp.exists() else "없음"
        sug = [sorted(pairs[(sents[k], sents[k+1])])[0] if (sents[k], sents[k+1]) in pairs and len(pairs[(sents[k], sents[k+1])]) == 1 else None for k in range(len(sents) - 1)]
        out.append({"대본": Path(sc).parent.parent.name + "/" + Path(sc).name, "장": f"{f}" + (f"~{l}" if l != f else ""), "파일": fp.name, "지금": cur, "종류": [k for k, _ in c], "문장": sents, "옮김": sug})
Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(out), "구획 ·", sum(len(o["문장"]) - 1 for o in out), "자리 · 옮김 후보", sum(x is not None for o in out for x in o["옮김"]), "· 채워진 파일", sum(isinstance(o["지금"], list) for o in out))
