"""옛 틀 판정을 현재 틀로 옮기고 근거를 「위치 — 내용」 꼴로 맞춘다. 사용: python3 판정옮기기.py <일> <대상> <판정.json> <위치 접두>"""
import json, subprocess, sys
일, 대상, f, 위치 = sys.argv[1:5]
new = json.loads(subprocess.run(["python3", "workspace/강의제작/제작도구/검사/인수검사.py", "--틀", 일, "--대상", 대상], capture_output=True, text=True, check=True).stdout)
old = json.load(open(f))
for k, v in new["판정"].items():
    o = old["판정"].get(k)
    if not o: continue
    v["상태"] = o["상태"]; g = o["근거"]
    v["근거"] = g if " — " in g else f"{위치} — {g}"
for k in old: 
    if k not in ("판정",) and k not in new: new[k] = old[k]
json.dump(new, open(f, "w"), ensure_ascii=False, indent=1)
