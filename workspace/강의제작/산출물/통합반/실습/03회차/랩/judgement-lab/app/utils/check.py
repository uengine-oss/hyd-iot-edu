import hashlib as _h
_PROVIDED = {
 "app/ui/render.py": "f2a80ab6f2d359d26b9610dadab032638decd2496da7a9aac143a1a704320c64",
 "app/utils/actions.py": "c8aa086eb56f9487e0ffb80480b1484284a720eb0f8d0743331715905a1e744c",
 "app/utils/compare.py": "67fd114a29c0633548742f538259d9ff61ea39f795491226004fc06a377b3f8e",
 "app/utils/results.py": "1c5b0596745e9ac1e9b7f06d84c7463d99720597edcf46801d32a51e640ae86b",
 "app/utils/rules.py": "c6779f7040e9387f293889d96406026add6804c565451d0bae5b9e0c9f7592cb",
 "data/alarms.csv": "c0a2c153ca2e06dfd99b75d047b6c06ff58c204c9be3db15c836e854620e6af2",
 "data/contract.md": "d549398f0458d116c20c805f26224464f3e6f3b95c3e58cffe5e370a23e4c8c9",
 "data/criteria/decision_table.csv": "6834fbc17810812619f912b30a3385823e30477596ac89c63af97660d011d18d",
 "data/criteria/provenance.md": "2295e9e121556ac814f568488377069d2e2ab9f1aa1fb54deebeeaf1fefdb30a",
 "data/criteria/sop.json": "e63c0a8f956707fc8522ae5073bc6f8f57909874a383e8b5b0bcbfc22da3c8c0",
 "data/hm8_manual.md": "7f16d0dea8820a62f1bce0b3e7562b6317ae258a313859f781f3eaa661c46302",
 "data/metrics/business_values.json": "588323c34d12f2dcc7f08469bc4392cdbb0a9573e53ebd46a08cbef26caf33a8",
 "data/metrics/candidate_settings.csv": "0856825d67964bb59aabaaa7edd5982aa830f71c5e543758e2461f43d7a9172c",
 "data/metrics/metric_definitions.md": "3a85d683a8fd99f515bbde90a9c6cf3622af4e253b238ec5607c3c92f6369758",
 "data/night_operation_rule.md": "4987c0c23595fe46d16557069f1d02969509122fb8d088429537c37b9327c53b",
 "run.py": "a2be7676a114229a2f866a562d53df8f281f5acba64e724816df9cb0a78f1878"
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
