"""강사 참조 — 문서 지식 묶음 그래프 랩(통합 04-3 · 실전 03-5)의 적재 · 조회 · 카드. 학생 폴더 · ZIP에 넣지 않는다.

입력 = 추출 랩 강사 판(지점5 나 · 지점6 가)의 검토 결과(학생 폴더 입력/검토결과/와 같은 바이트). 정할 것은 지점7 —
다른 문서(PM-02 PM-2.4 「예정된 정비 시간은 생산 오더가 없는 시간 … 낮에 생산 중인 설비는 세우지 않는 것이 원칙」)의 조건을 핀 세척(SOP-COOL-14)에 이을지:
가 = 준비 조건으로 잇는다(근거: HM-8 1.1 SOP-COOL-13 4단계가 같은 말을 빌림) / 나 = 잇지 않는다(PM-02의 범위는 정기 정비 — PM-2.1).
적재는 학생 도구(lab_cypher.py run)로 한다 — 이 파일은 검토 결과에서 적재 파일(.cypher)을 만들고, 조회문 · 카드 · 구축 기록을 쓴다.
새 종류 · 관계(schema_ext): Document · Revision · Section · Knowledge, HAS_REVISION · REPLACES · HAS_SECTION · STATED_IN · REFERS_TO(Step → Section) ·
CONDITION_OF(Knowledge → Skill, role) · DESCRIBES(Knowledge → Step) · SUPPORTS(Knowledge → Rule, match · note) · EVIDENCE_FOR(Knowledge → Cause · FailureMode) · APPLIES_TO(Knowledge → 설비 대상).
새 대상 ID: 문서 = 문서 식별자, 판 = <문서>@<판>, 절 = <문서>@<판>#<절 표기>, 지식 = <문서>@<판>:<후보 id> — 다른 문서의 같은 번호(T-3.1 등)가 겹치지 않고 다시 적재해도 늘지 않는다.
"""
from __future__ import annotations

from pathlib import Path
import csv
import io
import json
import re

P7 = ('가', '나')
BASE_P7 = '가'                      # 학생용 완성본 갈래(구성안 12절)
PHASE2 = {'OEM-HPP45A-MM', 'PR-07'}   # 통합 04-3 10단계에서 더하는 문서
REMOTE = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13']
HPP45A = ['HYD-01', 'HYD-02', 'HYD-03']
ROLE = {'precondition': 'preparation', 'prohibition': 'prohibition', 'completion': 'completion', 'step': 'step', 'unit_value': 'value'}
SECTION_SKILLS = {'HM-8.1': ['SOP-FAN-11'], 'HM-8.2': ['SOP-FAN-12'], 'HM-8.5': REMOTE, 'HM-8.6': REMOTE, 'HM-8.7': ['SOP-COOL-14', 'SOP-COOL-15'], 'HM-8.8': REMOTE}
CAUSE_WORDS = [('핀 오염', 'cause:cooler-fin-fouling'), ('주변 온도', 'cause:ambient-temperature-rise'), ('팬 구동 불량', 'cause:fan-drive-fault')]
PART_WORDS = [('축 씰', 'P-PMP-SEAL'), ('리턴 필터', 'P-RTN-FLT'), ('P-PMP-SEAL', 'P-PMP-SEAL'), ('P-FAN-BRG', 'P-FAN-BRG'), ('P-CLR-CORE', 'P-CLR-CORE'),
              ('펌프 축 씰 키트', 'P-PMP-SEAL'), ('팬 베어링', 'P-FAN-BRG'), ('쿨러 코어', 'P-CLR-CORE'), ('Pump shaft seal', 'P-PMP-SEAL'), ('Fluid change', 'P-HYD-OIL')]
SENSOR_TAGS = [('TS1', 'TS1'), ('PS1', 'PS1'), ('VS1', 'VS1')]
SCHEMA_EXT = {
    'classes': {
        'Document': {'meaning': '회사 문서 하나(문서 목록의 문서 식별자). 받은 파일이 없는 문서는 두지 않는다', 'required': {'id': 'string', 'title': 'string', 'owner': 'string'}},
        'Revision': {'meaning': '문서의 한 판(문서 목록의 한 행). 상태는 목록 그대로', 'required': {'id': 'string', 'doc_id': 'string', 'rev': 'string', 'status': 'string', 'file': 'string', 'sha256': 'string'},
                     'optional': {'effective': 'string', 'replaces_note': 'string'}},
        'Section': {'meaning': '판 안의 절 — 그 문서의 절 표기 그대로. 원문에 절 머리가 없는 절은 두지 않는다', 'required': {'id': 'string', 'ref': 'string'}},
        'Knowledge': {'meaning': '검토에서 승인(approved)한 후보 하나 — 원문 인용 · 줄과 검토 결정을 함께 둔다', 'required': {'id': 'string', 'kind': 'string', 'text': 'string', 'quote': 'string',
                      'line_start': 'number', 'line_end': 'number', 'decision': 'string', 'review_file': 'string'},
                      'optional': {'page': 'string', 'lang': 'string', 'value': 'number', 'value_max': 'number', 'unit': 'string', 'comparator': 'string', 'value_text': 'string', 'reason': 'string'}},
    },
    'relations': {
        'HAS_REVISION': {'from': 'Document', 'to': 'Revision'}, 'REPLACES': {'from': 'Revision', 'to': 'Revision', 'note': '문서 목록의 대체 관계'},
        'HAS_SECTION': {'from': 'Revision', 'to': 'Section'}, 'STATED_IN': {'from': 'Knowledge', 'to': 'Section', 'note': '출처'},
        'REFERS_TO': {'from': 'Step', 'to': 'Section', 'note': '기존 단계의 근거 절(sop.json 단계의 source)'},
        'CONDITION_OF': {'from': 'Knowledge', 'to': 'Skill', 'properties': {'role': ['preparation', 'prohibition', 'completion', 'step', 'value']}},
        'DESCRIBES': {'from': 'Knowledge', 'to': 'Step', 'note': '같은 단계의 원문'},
        'SUPPORTS': {'from': 'Knowledge', 'to': 'Rule', 'properties': {'match': ['일치', '불일치', '보류'], 'note': 'string'}},
        'EVIDENCE_FOR': {'from': 'Knowledge', 'to': ['Cause', 'FailureMode']},
        'APPLIES_TO': {'from': 'Knowledge', 'to': ['Asset', 'Component', 'Sensor', 'Part']},
    },
    'constraints': ['새 대상 ID — 문서 = 문서 식별자, 판 = <문서>@<판>, 절 = <문서>@<판>#<절 표기>, 지식 = <문서>@<판>:<후보 id>',
                    '승인(approved) 후보만 Knowledge로 둔다 — 보류 · 제외는 남은 질문 · 검토 결과에만', '현재 값(재고 · 작업지시 상태 · 센서 값)은 두지 않는다'],
}


def read(path):
    raw = Path(path).read_bytes()
    for enc in ('utf-8-sig', 'cp949'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(path)


def register(folder):
    lines = [x for x in read(Path(folder)/'자료/문서_목록.csv').splitlines() if not x.startswith('#')]
    return list(csv.DictReader(io.StringIO('\n'.join(lines))))


def q(value):
    """Cypher 글 상수."""
    return "'" + str(value).replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n') + "'"


def props(d):
    return '{' + ', '.join(f'{k}: ' + (q(v) if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for k, v in d.items() if v is not None) + '}'


def rev_id(doc, rev):
    return f'{doc}@{rev}' if rev else doc


def sec_id(doc, rev, ref):
    return f'{rev_id(doc, rev)}#{ref}'


def k_id(data, c):
    return f'{rev_id(data["doc_id"], data["rev"])}:{c["id"]}'


def targets(data, c, sop, p5='나', p7='가', lines=None):
    """승인 후보 하나가 잇는 기존 ID — [(관계, 대상 ID, 속성)]. 강사 참조의 연결 규칙(구성안 6절)."""
    skills = {s['id'] for s in sop['sops']}
    steps = {f'{s["id"]}:{st["order"]}' for s in sop['sops'] for st in s['steps']}
    doc, sec, proc, kind, quote = data['doc_id'], c['section'], c['procedure'], c['kind'], c['quote']
    role = {'role': 'approval'} if kind == 'precondition' and re.search(r'승인', quote) else {'role': ROLE[kind]}
    out = []
    if doc == 'HM-8' and data['rev'] == '1.1':
        if proc in skills:
            if kind == 'step' and f'{proc}:{c.get("order")}' in steps:
                out.append(('DESCRIBES', f'{proc}:{c["order"]}', {}))
            else:
                out.append(('CONDITION_OF', proc, role))
        elif sec == 'HM-8.3':
            out.append(('EVIDENCE_FOR', 'fm:cooler-cooling-loss', {}))
        elif sec == 'HM-8.4':
            out += [('EVIDENCE_FOR', cause, {}) for word, cause in CAUSE_WORDS if word in quote] or [('EVIDENCE_FOR', 'fm:cooler-cooling-loss', {})]
        else:
            refs = [r for r in c.get('refs', []) if r in skills]
            for s in refs or SECTION_SKILLS.get(sec, []):
                out.append(('CONDITION_OF', s, role))
    elif doc == 'OEM-HPP45A-MM':
        if proc == 'T-7.1':
            out.append(('CONDITION_OF', 'SOP-COOL-14', {'role': {1: 'preparation', 2: 'preparation', 4: 'prohibition', 5: 'completion', 6: 'completion'}.get(_order(c, lines), ROLE[kind])}))
        elif sec == '7':
            out += [('APPLIES_TO', f'{a}:cooler', {}) for a in HPP45A]
        elif sec == '3' or proc == 'T-3.1':
            out += [('APPLIES_TO', f'{a}:rtn-filter', {}) for a in HPP45A]
        elif sec == '4' or proc == 'T-4.1':
            out += [('APPLIES_TO', f'{a}:accumulator', {}) for a in HPP45A]
        else:
            parts = [p for w, p in PART_WORDS if w in quote]
            out += [('APPLIES_TO', p, {}) for p in dict.fromkeys(parts)] or [('APPLIES_TO', a, {}) for a in HPP45A]
    elif doc == 'SR-04' and sec == '제4조' and re.search(r'실측 유온|다가가는', quote):
        if p5 in ('가',):
            out += [('CONDITION_OF', s, {'role': 'prohibition'}) for s in REMOTE + ['SOP-COOL-14']]
        elif p5 == '나':
            out += [('CONDITION_OF', s, {'role': 'prohibition'}) for s in REMOTE]
    elif doc == 'HM-9':
        if sec == 'HM-9.1' and kind != 'unit_value':
            out += [('CONDITION_OF', s, {'role': 'prohibition'}) for s in REMOTE]
        elif sec == 'HM-9.3' and kind == 'unit_value':
            out += [('APPLIES_TO', f'{a}:{tag}', {}) for word, tag in SENSOR_TAGS if word in quote for a in HPP45A]
    elif doc == 'PM-02':
        if sec == 'PM-2.1':
            out += [('APPLIES_TO', a, {}) for a in HPP45A]
        elif sec == 'PM-2.4' and re.search(r'예정된 정비 시간은 생산 오더|낮에 생산 중인 설비', quote):
            if p7 == '가':
                out.append(('CONDITION_OF', 'SOP-COOL-14', {'role': 'preparation'}))
        else:
            parts = [p for w, p in PART_WORDS if w in quote]
            out += [('APPLIES_TO', p, {}) for p in dict.fromkeys(parts)]
    elif doc == 'PR-07':
        parts = [p for w, p in PART_WORDS if w in quote]
        out += [('APPLIES_TO', p, {}) for p in dict.fromkeys(parts)]
        if 'HYD-01~03' in quote:
            out += [('APPLIES_TO', a, {}) for a in HPP45A]
    elif doc == 'HI-01' and sec == 'HI-1' and 'HYD-01, HYD-02, HYD-03' in quote:
        out += [('APPLIES_TO', a, {}) for a in HPP45A]
    return out


def _order(c, lines):
    if c.get('order'):
        return c['order']
    if lines is None:
        return None
    m = re.match(r'^\s*(\d+)\.', lines[c['line_start'] - 1])
    return int(m.group(1)) if m else None


def load_cypher(folder, reviews, sop, p5='나', p7='가', with_register=True):
    """검토 결과 → 적재 파일 글. reviews = [(파일 이름, 검토 dict)]. 모든 문장은 MERGE · SET(다시 실행해도 같음)."""
    out = ['// 강사 참조 적재 — 문서 · 판 · 절, 승인 후보와 기존 ID 연결(MERGE만)']
    reg = register(folder)
    if with_register:
        for r in reg:
            if not r['파일']:
                continue          # 받은 파일이 없는 문서는 두지 않는다
            out.append(f'MERGE (d:Document {{id: {q(r["문서 식별자"])}}}) SET d += {props({"title": r["제목"], "owner": r["소유 부서"]})};')
            rid = rev_id(r['문서 식별자'], r['판'])
            out.append(f'MERGE (v:Revision {{id: {q(rid)}}}) SET v += {props({"doc_id": r["문서 식별자"], "rev": r["판"], "status": r["상태"], "effective": r["시행일"] or None, "file": r["파일"], "sha256": r["SHA-256"], "replaces_note": r["대체 관계"] or None})};')
            out.append(f'MATCH (d:Document {{id: {q(r["문서 식별자"])}}}), (v:Revision {{id: {q(rid)}}}) MERGE (d)-[:HAS_REVISION]->(v);')
        for r in reg:
            m = re.match(r'^(\S+)판을 대체$', r['대체 관계'] or '')
            if r['파일'] and m:
                out.append(f'MATCH (a:Revision {{id: {q(rev_id(r["문서 식별자"], r["판"]))}}}), (b:Revision {{id: {q(rev_id(r["문서 식별자"], m.group(1)))}}}) MERGE (a)-[:REPLACES]->(b);')
        for s in sop['sops']:
            for st in s['steps']:
                m = re.match(r'^(HM-8\.\d+)\s', st['source'])
                if m:
                    sid = sec_id('HM-8', '1.1', m.group(1))
                    out.append(f'MATCH (v:Revision {{id: {q(rev_id("HM-8", "1.1"))}}}) MERGE (x:Section {{id: {q(sid)}}}) SET x.ref = {q(m.group(1))} MERGE (v)-[:HAS_SECTION]->(x);')
                    out.append(f'MATCH (t:Step {{id: {q(s["id"] + ":" + str(st["order"]))}}}), (x:Section {{id: {q(sid)}}}) MERGE (t)-[:REFERS_TO]->(x);')
    for fname, data in reviews:
        lines = read(Path(folder)/'자료'/data['source_file']).splitlines()
        approved = [c for c in data['candidates'] if c['status'] == 'approved']
        rid = rev_id(data['doc_id'], data['rev'])
        for c in approved:
            sid = sec_id(data['doc_id'], data['rev'], c['section'])
            kprops = {'kind': c['kind'], 'text': c['text'], 'quote': c['quote'], 'quote_match': c.get('quote_match'), 'line_start': c['line_start'], 'line_end': c['line_end'],
                      'page': c.get('page'), 'lang': c.get('lang'), 'value': c.get('value'), 'value_max': c.get('value_max'), 'unit': c.get('unit'), 'comparator': c.get('comparator'),
                      'value_text': c.get('value_text'), 'decision': c['decision'], 'reason': c['reason'], 'review_file': f'입력/검토결과/{fname}'}
            out.append(f'MATCH (v:Revision {{id: {q(rid)}}}) MERGE (x:Section {{id: {q(sid)}}}) SET x.ref = {q(c["section"])} MERGE (v)-[:HAS_SECTION]->(x);')
            out.append(f'MATCH (x:Section {{id: {q(sid)}}}) MERGE (k:Knowledge {{id: {q(k_id(data, c))}}}) SET k += {props(kprops)} MERGE (k)-[:STATED_IN]->(x);')
            for rel, target, rp in targets(data, c, sop, p5, p7, lines):
                set_part = f' SET r += {props(rp)}' if rp else ''
                out.append(f'MATCH (k:Knowledge {{id: {q(k_id(data, c))}}}), (t {{id: {q(target)}}}) MERGE (k)-[r:{rel}]->(t){set_part};')
        ok = {c['id'] for c in approved}
        for link in data.get('rule_links', []):
            for cid in link['candidates']:
                if cid in ok:
                    out.append(f'MATCH (k:Knowledge {{id: {q(rev_id(data["doc_id"], data["rev"]) + ":" + cid)}}}), (r:Rule {{id: {q(link["rule_id"])}}}) '
                               f'MERGE (k)-[s:SUPPORTS]->(r) SET s += {props({"match": link["match"], "note": link["note"]})};')
    return '\n'.join(out) + '\n'


QUERIES = {
    'Q1': ("// 질문 1 — HYD-02 냉각 성능 상실의 조치마다 단계 · 조건과 근거 문서 · 판 · 절 · 인용\n"
           "MATCH (f:FailureMode {id: 'fm:cooler-cooling-loss'})-[m:MITIGATED_BY|REMEDIED_BY]->(s:Skill)-[:ACTS_ON]->(:Component)<-[:HAS_COMPONENT]-(:Asset {id: $asset})\n"
           "WITH DISTINCT f, m, s\n"
           "OPTIONAL MATCH (k:Knowledge)-[c:CONDITION_OF|DESCRIBES]->(t) WHERE t = s OR (s)-[:HAS_STEP]->(t)\n"
           "OPTIONAL MATCH (k)-[:STATED_IN]->(x:Section)<-[:HAS_SECTION]-(v:Revision)\n"
           "RETURN s.id AS sop, type(m) AS kind, s.approval_role AS approval, coalesce(c.role, 'step') AS role, v.doc_id AS doc, v.rev AS rev, x.ref AS section, k.quote AS quote\n"
           "ORDER BY sop, role, doc, quote"),
    'Q2': ("// 질문 2 — 판정 규칙마다 근거 원문과 맞는 정도\n"
           "MATCH (r:Rule) OPTIONAL MATCH (k:Knowledge)-[s:SUPPORTS]->(r) OPTIONAL MATCH (k)-[:STATED_IN]->(x:Section)<-[:HAS_SECTION]-(v:Revision)\n"
           "RETURN r.id AS rule, r.when AS condition, s.match AS match, v.doc_id AS doc, x.ref AS section, k.quote AS quote ORDER BY rule, doc, quote"),
    'Q3': ("// 질문 3 — 핀 세척 전에 확인할 현재 값(그래프 밖 원천)\n"
           "MATCH (s:Skill {id: $sop})-[:CHECKS]->(n:Sensor)<-[:MONITORED_BY]-(:Component)<-[:HAS_COMPONENT]-(:Asset {id: $asset})\n"
           "RETURN 'sensor' AS what, n.id AS id, n.unit AS unit, '시계열(관측값)' AS read_from\n"
           "UNION\n"
           "MATCH (k:Knowledge)-[:CONDITION_OF {role: 'preparation'}]->(:Skill {id: $sop}) WHERE k.quote CONTAINS 'MES'\n"
           "RETURN 'plan' AS what, k.id AS id, null AS unit, 'MES 생산 계획' AS read_from"),
    'Q4': ("// 질문 4 — 더한 문서(제조사 지침)의 작업이 걸리는 설비 대상\n"
           "MATCH (k:Knowledge)-[:STATED_IN]->(:Section)<-[:HAS_SECTION]-(v:Revision {doc_id: $doc}) MATCH (k)-[r:APPLIES_TO|CONDITION_OF]->(t)\n"
           "RETURN type(r) AS rel, labels(t)[0] AS label, t.id AS target, count(k) AS knowledge ORDER BY rel, target"),
    'Q5a': ("// 질문 5 — 제공되지 않은 작업: HYD-04 냉각 정비의 원문\n"
            "MATCH (:Asset {id: 'HYD-04'})-[:HAS_COMPONENT]->(c:Component {id: 'HYD-04:cooler'}) OPTIONAL MATCH (k:Knowledge)-[:APPLIES_TO|CONDITION_OF]->(t) WHERE t = c OR (t:Skill AND (t)-[:ACTS_ON]->(c))\n"
            "RETURN c.id AS component, count(k) AS knowledge"),
    'Q5b': ("// 질문 5 — 제공되지 않은 절: 트립 뒤 복귀의 원문 절\n"
            "OPTIONAL MATCH (x:Section) WHERE x.ref = $ref RETURN $ref AS section, count(x) AS found"),
    'HOLD': ("// 보류 후보가 그래프에 없는가\nMATCH (k:Knowledge) WHERE k.id IN $ids RETURN count(k) AS found"),
    'CARD': ("// 카드 — 작업 하나의 준비 · 금지 · 순서 · 완료와 출처\n"
             "MATCH (s:Skill {id: $sop}) OPTIONAL MATCH (s)-[:HAS_STEP]->(st:Step)\n"
             "WITH s, collect(DISTINCT {order: st.order, text: st.text, source: st.source}) AS steps\n"
             "OPTIONAL MATCH (k:Knowledge)-[c:CONDITION_OF|DESCRIBES]->(t) WHERE t = s OR (s)-[:HAS_STEP]->(t)\n"
             "OPTIONAL MATCH (k)-[:STATED_IN]->(x:Section)<-[:HAS_SECTION]-(v:Revision)\n"
             "RETURN s.id AS sop, s.name AS name, s.source AS source, s.approval_role AS approval, s.apply_conditions AS apply, s.prohibitions AS prohibitions, s.completion AS completion, steps,\n"
             "       collect(DISTINCT {role: coalesce(c.role, 'step'), doc: v.doc_id, rev: v.rev, status: v.status, section: x.ref, quote: k.quote, id: k.id}) AS evidence"),
}


def query_file():
    params = ':param asset => \'HYD-02\';\n:param sop => \'SOP-COOL-14\';\n:param doc => \'OEM-HPP45A-MM\';\n:param ref => \'HM-9.4\';\n'
    return '// 강사 참조 조회문 — Neo4j Browser에서는 :param 줄부터, run_reference.py는 같은 매개변수로 HTTP 실행\n' + params + '\n'.join(v + ';' for v in QUERIES.values()) + '\n'


# ───────────── 작업 확인 카드(실전 03-5) ─────────────
def csv_rows(path):
    lines = [x for x in read(path).splitlines() if x.strip() and not x.startswith('#')]
    return list(csv.DictReader(io.StringIO('\n'.join(lines))))


WO_WORDS = {'SOP-COOL-14': re.compile(r'SOP-COOL-14|SOP-COOL-04|핀 ?세척|핀 ?청소|핀 막힘|fin|HM-7\.6'), 'SOP-COOL-11': re.compile(r'SOP-COOL-11|팬 100|SOP-COOL-01')}
CARD_PARTS = {'SOP-COOL-14': [], 'SOP-COOL-11': []}       # 이 작업에 품번이 붙은 부품이 없다(압축공기 세척) — 코어 교체는 지점6 나에서만
ALIAS = {'1호기': 'HYD-01', '2호기': 'HYD-02', '3호기': 'HYD-03', 'HPU-L2-01': 'HYD-01', 'HPU-L2-02': 'HYD-02', 'HPU-L2-03': 'HYD-03',
         '#1 파워팩': 'HYD-01', '#2 파워팩': 'HYD-02', '#3 파워팩': 'HYD-03', 'HYD01': 'HYD-01', 'HYD02': 'HYD-02', 'HYD03': 'HYD-03'}


def history(folder, sop):
    rows = csv_rows(Path(folder)/'자료/작업지시_이력.csv')
    out = []
    for r in rows:
        asset = ALIAS.get(r['설비'], r['설비'])
        if asset in HPP45A and WO_WORDS[sop].search(r['작업 내용']) and r['작업유형'] != '운전':
            out.append(dict(r, asset=asset))
    return out


def card(card_row, folder, sop, p6='가', p7='가', remaining=()):
    """조회 결과(QUERIES['CARD']의 한 행)와 원천 기록으로 카드 글을 쓴다."""
    sop_id, name, source, approval, apply_, ban, done, steps, ev = card_row
    ev = [e for e in ev if e.get('quote')]
    def quoted(role):
        seen, out_ = set(), []
        for e in ev:
            key = e['quote'].splitlines()[-1].strip()
            if e['role'] == role and key not in seen:
                seen.add(key)
                out_.append(e)
        return out_
    def line(e):
        return f'- {e["doc"]} {e["rev"]} {e["section"]}: 「{e["quote"].splitlines()[-1].strip()}」(후보 {e["id"].split(":", 1)[1]})'
    reg = {r['문서 식별자'] + '@' + r['판']: r for r in register(folder)}
    hm8 = reg['HM-8@1.1']
    out = [f'# 작업 확인 카드 — {sop_id} {name}', '', '## 대상 작업', '',
           f'- {sop_id} {name} — 근거 문서 HM-8 {hm8["판"]}판({hm8["상태"]}, 시행 {hm8["시행일"]}) {source} · 설비 HYD-02(같은 모델 HYD-01 · HYD-03)', '',
           '## 준비 조건', '']
    prep = quoted('preparation')
    out += [line(e) for e in prep] or ['- 없음 — 승인한 준비 조건 후보가 그래프에 없다(남은 질문 참고)']
    out += ['', '## 금지 · 제한', '']
    out += [line(e) for e in quoted('prohibition')] or ['- 없음 — 승인한 금지 후보가 그래프에 없다']
    out += ['', '## 작업 순서', '']
    by_order = {e['id']: e for e in ev if e['role'] == 'step'}
    for st in sorted([s for s in steps if s.get('order')], key=lambda s: s['order']):
        hit = next((e for e in by_order.values() if e['quote'].splitlines()[-1].strip().endswith(st['text']) or st['text'] in e['quote']), None)
        out.append(f'{st["order"]}. {st["text"]} — ' + (f'{hit["doc"]} {hit["rev"]} {hit["section"]} 「{st["text"]}」' if hit else f'{st["source"]} 「{st["text"]}」'))
    out += ['', '## 완료 기준', '']
    out += [line(e) for e in quoted('completion')] or ['- 없음 — 승인한 완료 기준 후보가 그래프에 없다']
    out += ['', '## 작업 직전 확인할 현재 값', '',
            '- 쿨러 냉각 효율 CE · 유온 TS1(HYD-02) — 그래프에 없는 현재 값. 시계열(관측값)에서 읽는다. 문서의 기준값(완료 기준)과 구별한다.',
            '- PLC 운전 모드 · 상태 — 그래프에 없는 현재 값. PLC 상태 수신(시계열)에서 읽는다.']
    if p7 == '가' and sop_id == 'SOP-COOL-14':
        out.append('- 오늘 밤 생산 오더가 없는 시간 — 그래프에 없는 현재 값. MES 생산 계획에서 읽는다(준비 조건 PM-02 PM-2.4).')
    out += ['', '## 부품 준비', '']
    stock = csv_rows(Path(folder)/'자료/재고_현황.csv')
    stamp = read(Path(folder)/'자료/재고_현황.csv').splitlines()[0]
    parts = CARD_PARTS[sop_id] + (['P-CLR-CORE'] if (p6 == '나' and sop_id == 'SOP-COOL-14') else [])
    if parts:
        for p in parts:
            r = next(x for x in stock if x['품번'] == p)
            out.append(f'- {p} {r["품명"]} — 필요 1{r["단위"]}(코어 교체로 바꿀 때) · 원천 기록: 현재고 {r["현재고(on_hand)"]} · 예약 {r["예약(reserved)"]} · 입고 예정 {r["입고 예정(on_order)"] or 0}({stamp.split(" — ")[0].lstrip("# ")})')
    else:
        out.append(f'- 없음 — 이 작업의 단계 · 조건에 품번이 붙은 부품이 없다(재고 기준: {stamp.split(" — ")[0].lstrip("# ")})')
    out += ['', '## 지난 시행 기록', '']
    rows = history(folder, sop_id)
    for r in rows:
        done_ = f'완료 {r["완료일"]}' if r['완료일'] else '완료일 없음 — 확인 필요(HI-01 SOP-HI-02)'
        record = r['측정·시운전 기록'] or '기록 없음 — 완료 기준(CE 80 %)을 보여 주지 않음'
        note = ' · 고압 세척 — 현행 금지(HM-8 1.1 SOP-COOL-14 2단계)와 맞지 않는 시행' if '고압' in r['작업 내용'] else ''
        old_rev = ' · 옛 판 번호(HM-8 1.0 SOP-COOL-04)로 적힌 시행' if re.search(r'SOP-COOL-04|HM-7\.6', r['작업 내용']) else ''
        out.append(f'- {r["작업지시"]} {r["설비"]}({r["asset"]}) · {r["상태"]} · {done_} · 기록 그대로: 「{r["작업 내용"]}」 · 측정: {record}{note}{old_rev}')
    if not rows:
        out.append('- 없음 — 작업지시 이력에 이 작업의 시행이 없다')
    out += ['', '## 승인', '', f'- {approval} — 원문(HM-8 1.1 {source}). 카드는 승인을 대신하지 않는다.', '', '## 남은 질문', '']
    out += [f'- {x["item"]} — {x["kind"]} · {x["source"]} · {x["note"]}' for x in remaining] or ['- 없음']
    return '\n'.join(out) + '\n'
