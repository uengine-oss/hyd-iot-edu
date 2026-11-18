

"""구조 검사 — output/judgement.json의 모양만 본다(제공 — 고치지 않는다).
경보와 후보의 중복, 경보 표나 조치 기준에 없는 식별자, 네 손실과 감점의 합과 다른 비교값, 비교값의 크기와 어긋난 순위와 내줄 차례, 비어 있는 결정 칸, 사례 다섯 종류의 빈 자리를 찾는다.
판정과 순위가 맞는지는 보지 않는다. 그것은 기대 판정과의 대조와 손으로 해 본 계산으로 가린다."""
from pathlib import Path
import collections
import json
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from app.utils import actions as A  # noqa: E402
from app.utils import compare as C  # noqa: E402
from app.utils import rules as R  # noqa: E402
from app.utils.results import Stop  # noqa: E402

errors = provided_errors(root)  # noqa: F821 — 이 파일 머리의 제공 파일 검사
path = root / 'output/judgement.json'
if not path.is_file():
    print('아직 검사할 결과가 없습니다. python run.py write가 output/judgement.json을 만듭니다.')
    sys.exit(1)
for point in (A.ORDER_POINT, A.STATEMENT_POINT):
    try:
        A.decision(point)
    except Stop as e:
        errors.append(str(e))
try:
    kinds = collections.Counter(r['사례_종류'] for r in A.expected_rows())
    for k in A.KINDS:
        if not kinds[k]:
            errors.append(f'app/features/expected.csv: 사례 종류 「{k}」의 경보가 없습니다. 다섯 종류마다 경보를 하나 이상 고릅니다.')
except Stop as e:
    errors.append(str(e))
doc, rules, alarms = A.load()
out = json.loads(path.read_text(encoding='utf-8'))
alarm_ids, sop_ids = [r['경보_ID'] for r in alarms], {s['id'] for s in doc['sops']}
seen = collections.Counter(e['id'] for e in out['events'])
for i, n in seen.items():
    if n > 1:
        errors.append(f'output/judgement.json: 경보 {i}가 {n}번 있습니다. 경보마다 한 번이어야 합니다.')
    if i not in alarm_ids:
        errors.append(f'output/judgement.json: 경보 {i}가 data/alarms.csv에 없습니다.')
for i in alarm_ids:
    if i not in seen:
        errors.append(f'output/judgement.json: data/alarms.csv의 경보 {i}가 없습니다.')
if not str(out.get('decisions', {}).get(A.STATEMENT_POINT, '')).strip():
    errors.append('output/judgement.json: 비교 기준 문장이 비어 있습니다.')
for e in out['events']:
    twice = [s for s, n in collections.Counter(c['sop'] for c in e['candidates']).items() if n > 1]
    if twice:
        errors.append(f'output/judgement.json: 경보 {e["id"]}에 후보 {twice}가 두 번 있습니다.')
    totals, back = {}, set()
    for c in e['candidates'] + e['not_candidates']:
        if c['sop'] not in sop_ids:
            errors.append(f'output/judgement.json: 경보 {e["id"]}의 후보 {c["sop"]}가 조치 기준의 SOP에 없습니다.')
    for c in e['candidates']:
        if c['status'] not in R.STATUSES:
            errors.append(f'output/judgement.json: 경보 {e["id"]} {c["sop"]}의 판정 「{c["status"]}」을 읽을 수 없습니다.')
        if c['comparison'] is None:
            if c['rank'] is not None:
                errors.append(f'output/judgement.json: 경보 {e["id"]} {c["sop"]}는 비교값이 없는데 순위가 있습니다.')
            continue
        if c['status'] != '허용':
            errors.append(f'output/judgement.json: 경보 {e["id"]} {c["sop"]}는 제외인데 비교값이 있습니다.')
        if abs(sum(c['comparison'][k] for k in C.PARTS) - c['comparison']['비교값']) > 0.005:
            errors.append(f'output/judgement.json: 경보 {e["id"]} {c["sop"]}의 비교값이 네 손실과 감점의 합과 다릅니다.')
        totals[c['sop']] = c['comparison']['비교값']
        if c['held_back']:
            back.add(c['sop'])
    ranks = C.ranked(totals)
    for c in e['candidates']:
        if c['sop'] in ranks and c['rank'] != ranks[c['sop']]:
            errors.append(f'output/judgement.json: 경보 {e["id"]} {c["sop"]}의 순위 {c["rank"]}가 비교값의 크기 차례({ranks[c["sop"]]})와 다릅니다. 비교값이 작을수록 앞입니다.')
    want = A.order(totals, back)
    if e['order'] != want or e['top'] != want[:1]:
        errors.append(f'output/judgement.json: 경보 {e["id"]}의 내줄 차례가 비교값과 뒤로 미룬 후보로 정한 차례와 다릅니다.')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print(f'구조 검사 통과 — 경보 {len(out["events"])} · 쓰는 조치 기준 {out["criteria"]}. 식별자와 숫자의 모양만 본 것입니다. 판정과 순위가 맞는지는 기대 판정과의 대조와 손으로 해 본 계산으로 가립니다.')
