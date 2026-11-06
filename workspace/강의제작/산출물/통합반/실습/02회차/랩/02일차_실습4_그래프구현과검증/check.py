"""제공 파일 · 기록 · 결과 구조 검사. 생성 · 수정 · DB 접속을 하지 않는다. 답이 맞는지는 보지 않는다 — 결과 화면에서 기대 답과 견준다."""
from pathlib import Path
import sys
import hashlib as _h
_PROVIDED = {
 "lab_cypher.py": "a6ae2b16b5fff7f923287653468098733b246e2a589d9b98a6a07818df1f04a3",
 "lab_db.py": "8328793ea21000f17b36da076b53a16791bf7247e08a7357e6c7320f6cde125a",
 "lab_steps.py": "c30955d5bce77d33f3a69d7244030f22371727f0a4b53b93e1315156b18bb1a5",
 "show_result.py": "1d7bb59ff9b3a5c3e7bd94af2838eafb891b312a1c34e43877dd700d17fd7c9d"
}
def provided_errors(root):
    out = []
    for name, digest in _PROVIDED.items():
        p = root / name
        if not p.is_file():
            out.append(f'제공 파일이 없습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
        elif _h.sha256(p.read_bytes()).hexdigest() != digest:
            out.append(f'제공 파일이 바뀌었습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
    return out
def chosen_errors(root):
    """결과/정한_것.csv — 빈 칸 · 근거 꼴(파일:줄)만 본다. 고른 것이 맞는지는 보지 않는다."""
    import csv, io, re
    p = root / '결과' / '정한_것.csv'
    if not p.is_file():
        return ['결과/정한_것.csv가 없습니다 — 받은 ZIP의 빈 틀을 지우지 않습니다.']
    lines = [x for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.lstrip().startswith('#')]
    rows = list(csv.DictReader(io.StringIO('\n'.join(lines))))
    need = ['지점', '고른_것', '근거', '바뀌는_답']
    if not lines or [c.strip() for c in csv.reader([lines[0]]).__next__()] != need:
        return ['결과/정한_것.csv: 열 이름이 ' + ','.join(need) + '이어야 합니다.']
    out = []
    for n, r in enumerate(rows, 1):
        empty = [c for c in need if not (r.get(c) or '').strip()]
        if empty:
            out.append(f'결과/정한_것.csv {n}번째 행: 빈 칸 ' + ', '.join(empty) + '(못 정했으면 고른_것에 「미결」).')
        elif not re.search(r'[^\s:]+:\d+', r['근거']):
            out.append(f'결과/정한_것.csv {n}번째 행: 근거에 파일:줄이 없습니다.')
    return out
_root = Path(__file__).resolve().parent
_pre = provided_errors(_root) + chosen_errors(_root)
for _e in _pre:
    print('확인 필요: ' + _e)
if _pre:
    sys.exit(1)
print('제공 파일 · 기록 검사 통과. 질문별 답은 결과 화면에서 기대 답과 견줍니다.')
