import hashlib as _h
_PROVIDED = {
 "app/ui/render.py": "f2a80ab6f2d359d26b9610dadab032638decd2496da7a9aac143a1a704320c64",
 "app/utils/actions.py": "fb48cc555e4a4da6808b127ae7dd888eaa7875898b3e3efb372a57c7a852cc45",
 "app/utils/results.py": "1c5b0596745e9ac1e9b7f06d84c7463d99720597edcf46801d32a51e640ae86b",
 "app/utils/rules.py": "c6779f7040e9387f293889d96406026add6804c565451d0bae5b9e0c9f7592cb",
 "app/utils/sop.py": "361f1d4a0fa66a484157410c398cb82ae09b1111daf5e6a04810e85c55853ac7",
 "data/check_cases.csv": "ffc80773a38a6a2d03f8ddc8696d16aeb710075f40e2e23ef1b492b37d561e34",
 "data/contract.md": "1331434ba0f90fa18cc4e118ad0e93fc4e1d6c041bcd4a389fb649c78ffeb584",
 "data/decision_table_export.txt": "08e18780b3e1f5bcaecbc415e65155dfc32c2aa035de2cbc37c64efe46ff84ae",
 "data/failure_modes.csv": "1aa2b80ff1461bcc6c9cbcea1e7db036588a01851e538c9c9962e06c547212b2",
 "data/hm8_manual.md": "7f16d0dea8820a62f1bce0b3e7562b6317ae258a313859f781f3eaa661c46302",
 "data/model/graph.json": "4fdd12d8b95d9c6bd828d07ff70e865b038f08325171b8702e1eea8894af4694",
 "data/model/provenance.md": "f07514b7f42623a25f9cb76e0e854cdefb4ba82ad3829c4c6a111f3454817e1f",
 "data/model/schema.json": "75eed2fd8db15ad1c27925aee0c9cbc41318b876701d7bc319773e54d37909a2",
 "data/targets.csv": "9c1c14f12f3e19988ae6498b2f8b652bc6124f72cb4725101362f689d63d196a",
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


"""구조 검사 — output/sop.json과 결정표의 모양만 본다(제공 — 고치지 않는다).
식별자 중복, 끝이 없는 관계, 관계 방향, 설비 모델에 없는 식별자, 매뉴얼에 없는 원문 번호, 서로 잇지 않은 규칙과 조건 문장을 찾는다.
조건을 맞는 항목에 넣었는지, 판정이 맞는지는 보지 않는다. 그것은 확인 사례의 기대 판정과 원문 대조로 가린다."""
from pathlib import Path
import collections
import json
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from app.utils import rules as R  # noqa: E402
from app.utils import sop as S  # noqa: E402
from app.utils.results import Stop  # noqa: E402

errors = provided_errors(root)  # noqa: F821 — 이 파일 머리의 제공 파일 검사
path = root / 'output/sop.json'
if not path.is_file():
    print('아직 검사할 결과가 없습니다. python run.py rules가 output/sop.json을 만듭니다.')
    sys.exit(1)
try:
    S.decision('적용 범위')
except Stop as e:
    errors.append(str(e))
rules = []
try:
    rules = R.load_rules(root / 'app/features/decision_table.csv')
except Stop as e:
    errors.append(str(e))
doc = json.loads(path.read_text(encoding='utf-8'))


def twice(kind, ids):
    for i, n in collections.Counter(ids).items():
        if n > 1:
            errors.append(f'output/sop.json: {kind} {i}가 {n}번 있습니다. 식별자는 한 번이어야 합니다.')


fm_ids = [f['id'] for f in doc['failure_modes']]
cause_ids = [c['id'] for f in doc['failure_modes'] for c in f['causes']]
sop_ids = [s['id'] for s in doc['sops']]
twice('고장 유형', fm_ids)
twice('원인', cause_ids)
twice('SOP', sop_ids)
kinds = {'고장 유형': set(fm_ids), 'SOP': set(sop_ids), '원인': set(cause_ids)}
for r in doc['relations']:
    if r['type'] not in S.RELATIONS:
        errors.append(f'output/sop.json: 관계 type {r["type"]}을 읽을 수 없습니다.')
        continue
    a, b = S.RELATIONS[r['type']]
    if r['from'] in kinds[b] and r['to'] in kinds[a]:
        errors.append(f'output/sop.json: 관계 {r["type"]} {r["from"]} → {r["to"]}의 방향이 거꾸로입니다. {a}에서 {b}(으)로 긋습니다.')
    else:
        for end, kind in ((r['from'], a), (r['to'], b)):
            if end not in kinds[kind]:
                errors.append(f'output/sop.json: 관계 {r["type"]}의 끝 {end}가 {kind} 목록에 없습니다.')
linked = {r['to'] for r in doc['relations'] if r['type'] in ('MITIGATED_BY', 'REMEDIED_BY')}
assets = S.model()
known = {s['원문'] for s in S.sentences()} | {str(n) for n in S.manual_lines()}
rule_ids = {r['id'] for r in rules}
tied = set()
for s in doc['sops']:
    if s['id'] not in linked:
        errors.append(f'output/sop.json: {s["id"]}가 어느 고장 유형에도 이어지지 않았습니다(MITIGATED_BY 또는 REMEDIED_BY).')
    for a in s['assets']:
        if a not in assets:
            errors.append(f'output/sop.json: {s["id"]}에 건 설비 {a}는 설비 모델에 없는 식별자입니다.')
    if [x['order'] for x in s['steps']] != list(range(1, len(s['steps']) + 1)) or s['steps'] != S.steps(s['id']):
        errors.append(f'output/sop.json: {s["id"]}의 수행 단계가 매뉴얼의 번호 줄과 다릅니다.')
    for item in s['items']:
        if item['item'] not in S.ITEMS:
            errors.append(f'output/sop.json: {s["id"]}의 항목 「{item["item"]}」을 읽을 수 없습니다.')
        for ref in item['refs']:
            if ref not in known:
                errors.append(f'output/sop.json: {s["id"]}의 원문 번호 {ref}가 매뉴얼에 없습니다.')
        for rid in item['rules']:
            tied.add(rid)
            if rules and rid not in rule_ids:
                errors.append(f'output/sop.json: {s["id"]}의 조건 문장이 가리키는 규칙 {rid}가 결정표에 없습니다.')
for r in rules:
    for t in r['targets']:
        if t not in sop_ids:
            errors.append(f'app/features/decision_table.csv:{r["line"]}: 적용_대상 {t}가 SOP 목록에 없습니다.')
    if r['id'] not in tied:
        errors.append(f'app/features/decision_table.csv:{r["line"]}: 규칙 {r["id"]}를 가리키는 조건 문장이 없습니다. sop_items.csv의 규칙 칸에 이 이름을 적어 잇습니다.')
if (root / 'output/decision_table.csv').is_file() and (root / 'output/decision_table.csv').read_bytes() != (root / 'app/features/decision_table.csv').read_bytes():
    errors.append('output/decision_table.csv가 app/features/decision_table.csv와 다릅니다. python run.py rules를 다시 실행합니다.')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print(f'구조 검사 통과 — SOP {len(sop_ids)} · 관계 {len(doc["relations"])} · 규칙 {len(rules)}. 식별자와 연결의 모양만 본 것입니다. 조건을 맞게 나눴는지와 판정이 맞는지는 확인 사례의 기대 판정과 원문으로 가립니다.')
