"""쉼목록.py가 낸 목록과 정한 단계(줄마다 「구획번호 단계열」)로 쉼_저장의 빈 파일을 채운다. 이미 채워진 파일은 덮지 않는다.
    python3 쉼채움.py <쉼목록.json> <쉼정함.txt>"""
import json, sys
from pathlib import Path
V = Path(__file__).resolve().parents[5] / "workspace/강의제작/제작도구/기존제작/tools/video/쉼_저장"
d = json.loads(Path(sys.argv[1]).read_text())
w = k = 0
for line in Path(sys.argv[2]).read_text().splitlines():
    if not line.strip(): continue
    i, s = line.split(); o = d[int(i)]; v = [int(c) for c in s]
    assert len(v) == len(o["문장"]) - 1 and s.count("3") <= 2, i
    f = V / o["파일"]; cur = json.loads(f.read_text()) if f.exists() else {"문장": o["문장"], "쉼": None}   # 도구를 고쳐 문장 목록이 바뀐 구획은 아직 파일이 없다
    assert cur["문장"] == o["문장"], i
    if cur.get("쉼") is None:
        cur["쉼"] = v; f.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8"); w += 1
    elif cur["쉼"] != v: k += 1; print("이미 다르게 채워짐(두고 감)", i, o["파일"])
print("채움", w, "· 이미 있던 것 중 다름", k)
