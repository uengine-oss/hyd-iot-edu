"""강사 참조의 공통 판단. 학생 묶음에는 복사하지 않는다."""
from datetime import datetime, timedelta
import math


def instructions(request):
    return '''원인 후보는 그래프의 Cause에서 모두 읽되, 문서의 사전 확률을 관측 증거로 바꾸지 않는다.
현재 적용되는 Knowledge의 출처와 문서 목록의 판본 상태를 조회한다. HM-8.4 조건과 원문 주변 절,
작업 전 안전 조건, 해당 설비의 사건·정비 이력을 함께 확인한다. 그래프에서 찾지 못한 연결은 원문으로 보완하고 연결이 있다고 만들지 않는다.
HM-8.3의 26줄 부하90% 운전 전제를 원문으로 확인한다. 후보 관측은 RUN·부하90%로 조회하고, 현재 운전 이력도 함께 확인한다.
Knowledge의 채택·현행 판과 STATED_IN으로 이어지는 실제 원문 절·줄을 반환받는다. 없는 관계를 추가하지 않는다.
관측은 요청 기준시각에서 끝나는 1초 자료로 CE 최근30초, VS1·TS4 최근120초, TS1 최근60초를 각각 집계한다.
현재값뿐 아니라 같은 설비의 다른 날짜 장기 10초 자료에서 같은 운전 상태·부하를 골라 비교한다. 기간/상태가 다르면 같은 근거로 합치지 않는다.
표본 수, 최대 공백, 마지막 관측시각, 수집 품질을 확인한다. 관측이 없거나 질의가 실패하면 숫자를 채우지 않는다.
정비 완료 메모와 정비 상태는 구별한다. 이번 결과는 정비 담당자가 검토할 점검 제안이며 실제 정지·LOCAL·동력 잠금을 확인했다는 뜻이 아니다.
필요한 근거를 조회한 뒤 finish에 요약과 사용한 T번호를 쓴다. 도구 이름과 인수는 매 단계 현재까지의 반환 내용을 보고 정한다.'''


def prepare_query(name, arguments, request):
    args = dict(arguments)
    if name in ['observations', 'history']:
        # 요청과 다른 설비의 증거가 섞이지 않게 하되 비교 요청 자체는 별도 실행한다.
        args['asset'] = request['asset']
        if datetime.fromisoformat(args['end'].replace('Z', '+00:00')) > datetime.fromisoformat(request['as_of']):
            args['end'] = request['as_of']
    if name == 'observations' and args.get('dataset', '1s') == '1s':
        args['state'] = 'RUN'
        args['load_pct'] = 90
    if name == 'document' and args.get('doc_id') == 'HM-8':
        # 숫자가 든 한 줄만 선택해도 표의 적용 조건과 같은 절의 예외를 함께 받는다.
        args['revision'] = '1.1'
        if not args.get('section') and args.get('line_start'):
            line = int(args['line_start'])
            ranges = [(7,15,'HM-8.1'),(16,24,'HM-8.2'),(25,34,'HM-8.3'),(35,43,'HM-8.4'),(44,69,'HM-8.5'),(70,72,'HM-8.6'),(73,85,'HM-8.7'),(86,89,'HM-8.8')]
            for begin, end, section in ranges:
                if begin <= line <= end:
                    args['section'] = section
                    args.pop('line_start',None); args.pop('line_end',None); break
    return args


def parsed_time(text):
    return datetime.fromisoformat(text.replace('Z','+00:00'))


def unique(values):
    return list(dict.fromkeys(values))


def document_sources(ledger, line):
    found = []
    for entry in ledger:
        if entry['tool'] != 'document' or entry['status'] != 'ok': continue
        result = entry['result']; doc = result.get('document', {})
        if (doc.get('doc_id'), doc.get('revision'), doc.get('status')) != ('HM-8', '1.1', '현행'): continue
        for row in result.get('lines', []):
            if row['line'] == line:
                found.append({'ref': entry['id'], 'file': result.get('source', doc.get('file')),
                              'line': line, 'text': row['text'], 'revision': doc['revision'], 'status': doc['status']})
    return found


def knowledge_sources(ledger, line):
    """실제로 받은 채택 지식→STATED_IN→절→현행 원문만 연결한다."""
    nodes = {}; relations = []
    for entry in ledger:
        if entry['tool'] != 'graph_query' or entry['status'] != 'ok': continue
        for node in entry['result']['nodes']: nodes[node['props']['id']] = (node, entry['id'])
        relations.extend((rel, entry['id']) for rel in entry['result'].get('rels', []))
    paths = []
    for identity, (node, node_ref) in nodes.items():
        props = node['props']
        if 'Knowledge' not in node['labels'] or props.get('decision') != '채택': continue
        if (props.get('doc_id'), props.get('rev'), props.get('doc_status')) != ('HM-8', '1.1', '현행'): continue
        if props.get('line_start') != line or props.get('line_end') != line: continue
        quote = ' '.join(str(props.get('quote', '')).split())
        if not quote: continue
        for rel, relation_ref in relations:
            if rel['type'] != 'STATED_IN' or rel['a'] != identity or rel['b'] not in nodes: continue
            section, section_ref = nodes[rel['b']]; section_props = section['props']
            if (section_props.get('doc_id'), section_props.get('rev'), section_props.get('ref')) != ('HM-8', '1.1', props.get('section')): continue
            for source in document_sources(ledger, line):
                if quote not in ' '.join(source['text'].split()): continue
                path = {'knowledge_id': identity, 'knowledge_ref': node_ref, 'relation': rel,
                        'relation_ref': relation_ref, 'section_ref': section_ref, 'raw_source': source,
                        'binding': '후보별 원문 조건 행 대응; 없는 EVIDENCE_FOR 관계를 추가하지 않음'}
                if path not in paths: paths.append(path)
    return paths


def operating_evidence(ledger, result, request):
    filters = result.get('filters', {})
    if filters.get('state') == 'RUN' and filters.get('load_pct') == 90 and result.get('row_count', 0) > 0:
        return {'status': 'confirmed', 'method': '반환에 기록된 RUN·90% 필터', 'evidence_refs': []}
    begin = parsed_time(result['start_exclusive']); end = parsed_time(result['end_inclusive'])
    for entry in reversed(ledger):
        if entry['tool'] != 'history' or entry['status'] != 'ok': continue
        history = entry['result']
        if history.get('asset') != request['asset'] or not history.get('query_succeeded'): continue
        if history.get('source') not in ['자료/state_changes.csv', 'data/state_changes.csv']: continue
        if parsed_time(history['start']) > begin or parsed_time(history['end']) < end: continue
        rows = sorted(history.get('rows', []), key=lambda row: parsed_time(row['observed_at']))
        prior = [row for row in rows if parsed_time(row['observed_at']) <= begin]
        if not prior: continue
        active = [prior[-1]] + [row for row in rows if begin < parsed_time(row['observed_at']) <= end]
        matching = all(row.get('asset') == request['asset'] and row.get('state') == 'RUN' and float(row.get('load_pct', -1)) == 90 for row in active)
        return {'status': 'confirmed' if matching else 'not_satisfied', 'method': '해당 창을 덮는 실제 운전 상태 변화 이력',
                'evidence_refs': [entry['id']], 'source_rows': [{'file': row['source'], 'line': row['line'], 'record_id': row['record_id']} for row in active]}
    return {'status': 'unconfirmed', 'method': 'RUN·90% 필터 또는 해당 창의 운전 조건 근거가 없음', 'evidence_refs': []}


def evidence_for(ledger, tag, seconds, request):
    """수집 유효성·적용 조건·측정값 유무를 구분한 근거를 돌려준다."""
    matches = []; failures = []
    units = {'CE': '%', 'VS1': 'mm/s', 'TS4': '℃', 'TS1': '℃'}
    for entry in ledger:
        if entry['tool'] != 'observations': continue
        if entry['status'] != 'ok':
            args = entry.get('arguments', entry.get('model_arguments', {}))
            if args.get('asset') == request['asset'] and tag in args.get('tags', []): failures.append(entry['id'])
            continue
        result = entry['result']; stats = result.get('statistics', {}).get(tag)
        if not stats or result.get('asset') != request['asset'] or result.get('dataset') != '1s': continue
        begin = parsed_time(result['start_exclusive']); end = parsed_time(result['end_inclusive'])
        if (end-begin).total_seconds() != seconds or end != parsed_time(request['as_of']): continue
        count = stats.get('count'); mean = stats.get('mean')
        value_state = 'no_samples' if count == 0 else 'null_value' if mean is None else 'zero' if mean == 0 else 'value'
        operating = operating_evidence(ledger, result, request)
        # 최대 공백3초가 허용하는 최소 표본 수. 양쪽 경계도 공백 계산에 포함된다.
        minimum_count = max(1, math.ceil(seconds / 3) - 1)
        rows = result.get('row_count'); bad = result.get('bad_rows')
        quality = isinstance(count, int) and isinstance(rows, int) and isinstance(bad, int) and 0 <= bad <= rows and 0 <= count <= rows-bad
        last = parsed_time(stats['last_observed_at']) if stats.get('last_observed_at') else None
        computed_age = (end-last).total_seconds() if last else None
        gap = stats.get('max_gap_s'); age = stats.get('age_at_end_s')
        checks = {'window': True, 'sample_interval': result.get('sample_interval_s') == 1,
                  'sample_count': isinstance(count, int) and minimum_count <= count <= seconds,
                  'quality': quality, 'gap': isinstance(gap, (int, float)) and 0 < gap <= 3,
                  'freshness': age is not None and computed_age is not None and 0 <= age <= 60 and abs(age-computed_age) < 1e-6,
                  'unit': stats.get('unit') == units[tag],
                  'numeric_value': isinstance(mean, (int, float)) and math.isfinite(mean),
                  'operating_condition': operating['status'] == 'confirmed'}
        matches.append({'tag': tag, 'ref': entry['id'], 'stats': stats, 'value_state': value_state, 'checks': checks,
                        'minimum_samples': minimum_count, 'operating': operating,
                        'valid': all(checks.values()), 'evidence_refs': unique([entry['id'], *operating['evidence_refs']])})
    if matches: return matches[-1]
    return {'tag': tag, 'ref': failures[-1] if failures else None, 'stats': None,
            'value_state': 'query_failed' if failures else 'not_queried', 'checks': {},
            'minimum_samples': max(1, math.ceil(seconds / 3) - 1),
            'operating': {'status': 'unconfirmed', 'evidence_refs': []}, 'valid': False,
            'evidence_refs': failures[-1:]}


def compose(request, ledger, model_report, delivery):
    causes = {}
    for entry in ledger:
        if entry['tool'] == 'graph_query' and entry['status'] == 'ok':
            for node in entry['result']['nodes']:
                if 'Cause' in node['labels']:
                    causes[node['props']['id']] = node['props'] | {'evidence_ref': entry['id']}
    if not causes: raise ValueError('모델이 원인 후보 그래프를 조회하지 않았습니다. 조회 계획을 고칩니다.')
    evidence = {tag: evidence_for(ledger, tag, seconds, request) for tag, seconds in [('CE', 30), ('VS1', 120), ('TS4', 120), ('TS1', 60)]}
    application = [source for source in document_sources(ledger, 26) if ' '.join(source['text'].split()) == '판정은 부하 90 % 운전 중의 값으로 한다.']
    safety_refs = [x['id'] for x in ledger if x['tool'] == 'document' and x['status'] == 'ok' and any('잠금' in row['text'] or '정지하고' in row['text'] for row in x['result'].get('lines', []))]
    criteria = {
        'cause:cooler-fin-fouling': (38, ['CE', 'VS1'], lambda: evidence['CE']['stats']['mean'] < 70 and evidence['VS1']['stats']['mean'] < .9, '최근30초 CE 평균<70 %, 최근120초 VS1 평균<0.9 mm/s'),
        'cause:ambient-temperature-rise': (39, ['TS4'], lambda: evidence['TS4']['stats']['mean'] >= 35, '최근120초 TS4 평균≥35 ℃'),
        'cause:fan-drive-fault': (40, ['VS1'], lambda: evidence['VS1']['stats']['mean'] >= .9, '최근120초 VS1 평균≥0.9 mm/s')}
    candidates, unresolved = [], []
    for identity, cause in sorted(causes.items()):
        if identity not in criteria:
            refs = [cause['evidence_ref']]
            candidates.append({'cause_id': identity, 'name': cause['name'], 'status': '보류', 'reason': '이 후보의 원문 조건을 이번 구현에서 연결하지 못함', 'evidence_refs': refs})
            unresolved.append({'cause_id': identity, 'needed': cause['name'] + '의 적용 원문 조건 확인', 'evidence_refs': refs}); continue
        line, tags, condition, explanation = criteria[identity]
        sources = knowledge_sources(ledger, line)
        observations = [evidence[tag] for tag in tags]
        refs = unique([cause['evidence_ref'], *[p[key] for p in sources for key in ['knowledge_ref', 'relation_ref', 'section_ref']],
                       *[p['raw_source']['ref'] for p in sources], *[p['ref'] for p in application], *[ref for item in observations for ref in item['evidence_refs']]])
        sufficient = bool(application and sources) and all(item['valid'] for item in observations)
        condition_result = bool(condition()) if sufficient else None
        status = '보류' if condition_result is None else '충족' if condition_result else '해당 없음'
        missing = []
        if not application: missing.append('부하90% 운전 적용 원문')
        if not sources: missing.append('채택 지식·실제 출처 관계·현행 원문 연결')
        for item in observations:
            if not item['valid']:
                reasons = ','.join(name for name, passed in item['checks'].items() if not passed)
                missing.append(item['tag'] + ' ' + item['value_state'] + (' (' + reasons + ')' if reasons else ''))
        reason = explanation + ('에 대한 적용 조건·유효 관측 충족' if status == '충족' else '에 대한 유효 관측의 수치 조건 불충족' if status == '해당 없음' else ' 대조 보류: ' + '; '.join(missing))
        candidates.append({'cause_id': identity, 'name': cause['name'], 'status': status, 'reason': reason, 'evidence_refs': refs,
                           'assessment': {'condition_result': condition_result, 'application_sources': application, 'knowledge_sources': sources,
                                          'observations': observations, 'missing': missing}})
        if status == '보류': unresolved.append({'cause_id': identity, 'needed': cause['name'] + ': ' + '; '.join(missing) + ' 확인. 기존 승인 없이 운전 부하를 변경하지 않음', 'evidence_refs': refs})
    if not evidence['TS1']['valid']: unresolved.append({'needed': '현재 유온의 적용 운전 조건·관측 시각·최근60초 추이 확인', 'evidence_refs': evidence['TS1']['evidence_refs']})
    if not safety_refs: unresolved.append({'needed': '점검 작업 전제의 안전 원문 확인', 'evidence_refs': []})
    checks, reason = delivery(candidates, unresolved, safety_refs)
    return {'request_id': request['request_id'], 'asset': request['asset'], 'as_of': request['as_of'], 'candidates': candidates,
            'next_checks': checks, 'unresolved': unresolved, 'delivery_reason': reason, 'model_summary': model_report,
            'safety': {'field_confirmed': False, 'meaning': '문서상 작업 전제와 실제 현장 확인은 별개. 운전 변경·정비·발주는 기존 승인 절차를 따른다.'}}
