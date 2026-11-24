"""시험 자료: 유압이 아닌 설비의 실제 규모 문서 한 편과 그 추출 제안 — 학생이 PBL 에서 자기 설비 매뉴얼을 올리는 길(문서 인제스천)을 판정한다.

문서 data/student/APU_공기공급장치_운전정비매뉴얼.md 는 가상 운영사의 지하철 차량 공기 공급 장치(APU) 운전 · 정비 매뉴얼이다(직접 쓴 글, 신호 이름은
공개 데이터셋 MetroPT-3 — CC BY 4.0). 추출 제안 data/student/APU_추출제안.json 은 AI 를 부르지 않고 쓴 시험 자료이며, 실제 추출이 낼 꼴과 같다 —
인용은 원문 그대로이고 추출 계약(manual_extraction.validate_proposal)을 지난다. 지금 지식에 없는 그 설비의 구성 요소 · 증상 · 센서는 knowledge 의
새 항목 제안(manual_knowledge.NEW_KINDS)으로 들어 있다. 인용의 원문 id 는 자리표 manual:SOURCE 이고, 보관소에 올린 원문의 id 로 바꿔 쓴다."""
import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent / 'data' / 'student'
FILENAME = 'APU_공기공급장치_운전정비매뉴얼.md'
RAW = (HERE / FILENAME).read_bytes()
_PROPOSAL = json.loads((HERE / 'APU_추출제안.json').read_text(encoding='utf-8'))
NEW_KINDS = ('components', 'symptoms', 'sensors')


def proposal(source_id):
    """이 원문 판(source_id)에 묶인 추출 제안 사본."""
    def rebind(value):
        if isinstance(value, dict):
            return {k: source_id if k == 'source_id' else rebind(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rebind(v) for v in value]
        return deepcopy(value)
    return rebind(_PROPOSAL)


def new_ids(kind):
    return [i['id'] for i in _PROPOSAL['knowledge'][kind]]


def reviewed(preview, *, drop=(), by='보전 담당 학생', batch=None, previous=None):
    """사람이 검토 화면에서 만든 적재 요청과 같은 본문(포털 hitl.js commitRequest 의 꼴): 새 항목은 drop 에 든 id 를 「제외」, 나머지를 「넣기」로 고른다
    (넣기를 고른 항목만 approved=true 로 남는다). drop 에는 지식 후보 id 도 넣을 수 있다(「적재에서 제외」)."""
    knowledge = {kind: [dict(i, **({'approved': True} if kind in NEW_KINDS else {})) for i in items if i['id'] not in drop]
                 for kind, items in deepcopy(preview['knowledge']).items()}
    return {'source_id': preview['source_id'], 'document_id': preview['document_id'], 'filename': preview['filename'],
            'batch': batch or str(uuid4()), 'previous_batch': previous, 'sections': deepcopy(preview['sections']),
            'procedures': [{k: v for k, v in p.items() if k != 'link'} for p in deepcopy(preview['procedures'])],
            'links': {p['id']: deepcopy(p['link']) for p in preview['procedures'] if p.get('link') is not None},
            'knowledge': knowledge, 'by': by, 'reviewed': True}
