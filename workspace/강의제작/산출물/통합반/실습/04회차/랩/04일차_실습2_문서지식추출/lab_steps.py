"""문서에서 근거 있는 지식을 추출하는 기능 만들기 — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 고치지 않는다.
단계마다 정할 자리(결과/의 「제공 빈 틀」 파일)를 채웠으면 제공 코드(doc_extract.py)를 돌려 그 결과를 결과/보기.html에 보인다."""
from pathlib import Path
import json
import show_result as R
import doc_extract as X

HERE = Path(__file__).resolve().parent
TITLE = '문서에서 근거 있는 지식을 추출하는 기능 만들기'
PRACTICAL = False
TASK, ASSET, EVENT_UTC, JUDGED = 'SOP-COOL-14', 'HYD-02', '2026-10-26T16:59:00Z', 'result.json'
OTHER_DOCS = ['PM-02_정기점검표.md', 'PR-07_예비품기준.md', 'HI-01_보충매뉴얼.md']


def owner(where):
    """그 파일을 정할 자리로 가진 단계 — 「N단계 「이름」의 정할 자리」(STEPS는 이 파일 끝에서 정한다)."""
    rel = str(where).split(':')[0].split(' ')[0]
    hit = next((x for x in STEPS if rel in x['slots']), None)
    return f' — {hit["no"]}단계 「{hit["name"]}」의 정할 자리' if hit else ''


def guard(fn):
    """제공 코드의 꼴 문제(Problem) · 수업 모델 멈춤(llm_client Stop)을 결과 화면의 빨간 칸으로."""
    def run(previous):
        try:
            return fn(previous)
        except X.Problem as e:
            raise R.Stop(str(e) + owner(e.where))
        except SystemExit:
            raise R.Stop('수업 모델에 보내지 못하고 멈췄습니다 — 터미널에 찍힌 까닭을 봅니다(키가 없으면 보낼 글이 결과/요청/에 남습니다).')
    return run


def settings():
    cfg = X.settings()
    if cfg is None:
        raise R.Blank('결과/나누기.json 「단위」가 비어 있습니다.')
    return cfg


def prompt():
    p = X.prompt_text()
    if not p:
        raise R.Blank('결과/prompt.md에 요청 글이 아직 없습니다.')
    return p


def event():
    data = json.loads((X.basis(JUDGED)).read_text(encoding='utf-8'))
    near = [e for e in data['events'] if e['asset'] == ASSET]
    gap = lambda e: abs(int(e['decision_time'][8:10]) * 1440 + int(e['decision_time'][11:13]) * 60 + int(e['decision_time'][14:16])
                       - (int(EVENT_UTC[8:10]) * 1440 + int(EVENT_UTC[11:13]) * 60 + int(EVENT_UTC[14:16])))
    return min(near, key=gap), data


@guard
def look(previous):
    e, _ = event()
    ranks = {r['sop']: r['rank'] for r in e.get('ranking', [])}
    rows = [[c['sop'], c['status'], c.get('rank', ranks.get(c['sop'], ''))] for c in e['candidates']]
    sop = json.loads(X.basis('sop.json').read_text(encoding='utf-8'))
    rel = [[r['type'], r['from'], r['to'], r.get('source', '')] for r in sop['relations'] if TASK in (r['from'], r['to'])]
    docs = [[row['문서 식별자'], row['판'], row['상태'], row['파일'] or '(받은 파일 없음)', enc or '', len(text.splitlines()) if text else '',
             len(X.section_heads(text)) if text else '', (text.splitlines()[0][:60] if text else why)] for row, text, enc, raw, why in X.documents()]
    rules = sorted({r['rule_id'] for r in X.csv_rows(X.basis('조건표.csv')) if not PRACTICAL or r.get('action') == TASK})
    return [R.table(f'사건 경보 {e["id"]}(판정 요청 {e["decision_time"]} UTC)의 조치 후보', ['조치', '판정', '순위'], rows),
            R.table(f'받은 SOP 구조에서 {TASK}가 걸린 관계', ['관계', '시작', '끝', '출처'], rel),
            R.table('문서 묶음 — 목록의 판 · 상태와 읽은 결과(SHA-256이 목록과 같은 파일만 읽음)', ['문서', '판', '상태', '파일', '글자 방식', '줄 수', '절 머리 수', '첫 줄 또는 읽지 못한 까닭'], docs),
            R.note(('이 작업에 걸린 조건' if PRACTICAL else '조건표의 조건') + ': ' + ', '.join(rules))]


def connect(previous):
    import llm_client as L
    conf = L.settings()
    have = [n for n in L.NAMES if conf[n]]
    return [R.counts('수업 모델 연결 값과 응답 기록(값은 보이지 않음)', [('.env에 채운 줄', f'{len(have)} / 3'), ('응답 기록 수', len(L.records())),
                                                         ('이 폴더의 안내용 상한까지 남은 수', L.MAX_SENT - L.sent_count())]),
            R.note('연결 확인은 터미널에서 `python llm_client.py`로 합니다 — 결과 화면은 모델을 부르지 않습니다.')]


@guard
def expect(previous):
    rows = X.expected_rows()
    if not rows:
        raise R.Blank('결과/기대_항목.csv에 행이 없습니다.')
    out = [R.table('기대 항목 — 내가 적은 줄의 원문', ['파일', '줄', '종류', '원문'], [[f, n, k, X.source_line(f, n)] for f, n, k in rows])]
    for name in dict.fromkeys(f for f, _, _ in rows):
        lines = [n for f, n, _ in rows if f == name]
        out.append(R.source_lines(HERE / '자료' / name, min(lines), max(lines)))
    return out


@guard
def split(previous):
    cfg = settings()
    docs = X.by_file()
    rows = []
    for name, (row, text, enc, raw) in docs.items():
        for no, (first, body) in enumerate(X.split_chunks(text, cfg['단위'], cfg['글자_상한']), 1):
            a, b = X.chunk_range(first, body)
            rows.append([name, no, f'{a}~{b}', len(body), body.splitlines()[0][:50]])
    per = {}
    for r in rows:
        per[r[0]] = per.get(r[0], 0) + 1
    out = [R.counts('문서마다 조각 수', sorted(per.items()) + [('전체 조각', len(rows))]),
           R.table('조각 목록', ['파일', '조각', '줄 범위', '글자 수', '첫 줄'], rows)]
    try:
        need, left = X.to_send(cfg, X.prompt_text() or '(요청 글 없음)', cfg['보낼_문서'])
        out.append(R.counts('보낼 문서의 요청 수(보내지 않고 셈)', [('보낼 요청', need), ('이 폴더의 안내용 상한까지 남은 수', left)]))
    except X.Problem as e:
        out.append(R.note(f'보낼 수를 세지 못함 — {e}'))
    return out


@guard
def trial(previous):
    cfg = settings()
    p = prompt()
    if not cfg['시험_조각']:
        raise R.Blank('결과/나누기.json 「시험_조각」이 비어 있습니다 — 먼저 보내 볼 조각의 「파일:줄」을 적습니다.')
    got = X.trial(cfg, p)
    out = [R.note(f'시험 조각: {got["source_file"]} {got["chunk"][0]}~{got["chunk"][1]}줄 · 요청 해시 {got["request_hash"]}')]
    sop = json.loads(X.basis('sop.json').read_text(encoding='utf-8'))
    for a in got['answers']:
        out.append(R.table(f'{a["record"]}의 후보(끝난 까닭 {a["finish_reason"]})', ['id', '종류', '절', '절차', '줄', '찾은 방법', '인용'],
                           [[c['id'], c['kind'], c['section'], c['procedure'] or '', f'{c["line_start"]}~{c["line_end"]}', c['quote_match'], c['quote']] for c in a['candidates']]
                           + [[u['id'], u['kind'], u['section'], u['procedure'] or '', '', '찾지 못함', u['quote']] for u in a['unlocated']],
                           note=' · '.join(a['warnings'][:5])))
    if len(got['answers']) == 2:
        q = [{X.squash(c['quote']) for c in a['candidates']} for a in got['answers']]
        out.append(R.counts('같은 요청 두 답', [('두 답에 함께 있는 인용', len(q[0] & q[1])), ('첫 답에만', len(q[0] - q[1])), ('다시 보낸 답에만', len(q[1] - q[0]))]))
    procs = {c['procedure'] for a in got['answers'] for c in a['candidates'] if c['procedure']}
    rows = []
    for s in sop['sops']:
        if s['id'] in procs:
            for f in ('apply_conditions', 'prohibitions', 'steps', 'completion'):
                for x in s.get(f, []):
                    t = x.get('text') if isinstance(x, dict) else str(x)
                    hit = [c['id'] for c in got['answers'][0]['candidates'] if X.squash(c['quote']) and (X.squash(c['quote']) in X.squash(t) or X.squash(t) in X.squash(c['quote']))]
                    rows.append([s['id'], f, t, ' · '.join(hit) or '짝 없음'])
    if rows:
        out.append(R.table('받은 SOP 구조의 같은 작업 항목 ↔ 첫 답의 후보(글자 짝 — 뜻이 같은지는 원문 줄로 본다)', ['조치', '칸', '받은 SOP 구조의 글', '짝지은 후보'], rows))
    return out


@guard
def split_trial(previous):
    return split(previous) + trial(previous)


@guard
def main_run(previous):
    cfg = settings()
    p = prompt()
    if not cfg['보낼_문서']:
        raise R.Blank('결과/나누기.json 「보낼_문서」가 비어 있습니다.')
    done = X.extract(cfg, p, cfg['보낼_문서'])
    rows = []
    for name, what in done:
        data = X.load_candidates(name)
        cut = sum(1 for w in data['warnings'] if '길이 상한' in w)
        empty, loose = X.coverage(cfg, name)
        rows.append([name, len(data['candidates']), len(data['unlocated']), cut, ' · '.join(empty) or '없음', len(loose), X.made_with(data), what])
    out = [R.table('보낸 문서 — 후보 파일(「찾지 못한 인용」은 누락이 아님 — 누락은 후보 0개 조각 · 후보가 걸리지 않은 내용 줄을 원문으로 열어 판단한다)',
                   ['파일', '후보', '찾지 못한 인용', '길이 상한에서 잘린 답', '후보 0개 조각(줄)', '후보가 걸리지 않은 내용 줄', '후보를 만든 판', '이번 실행'], rows)]
    exp, extra = X.compare_expected()
    out.append(R.table('기대 항목 ↔ 후보(줄 · 종류로 짝 — 뜻이 같은지는 원문 줄로 본다)', ['파일', '줄', '종류', '원문', '표시', '후보'], [list(r) for r in exp]))
    if extra:
        out.append(R.table('기대 줄 사이에 있는데 기대에 없는 후보', ['파일', '줄', '종류', '후보', '인용'], [list(r) for r in extra]))
    return out


@guard
def review(previous):
    if not X.decision_rows():
        raise R.Blank('결과/검토_결정.csv에 행이 없습니다.')
    written = X.apply_review(TASK if PRACTICAL else None)
    rows, task_rows = [], []
    exp = {(f, n) for f, n, _ in X.expected_rows()}
    for path in written:
        d = json.loads(path.read_text(encoding='utf-8'))
        count = {}
        for c in d['candidates']:
            count[c['decision']] = count.get(c['decision'], 0) + 1
            if any(f == d['source_file'] and c['line_start'] <= n <= c['line_end'] for f, n in exp):
                task_rows.append([d['doc_id'], d['rev'], c['line_start'], c['kind'], c['decision'], c['quote'][:80]])
        rows.append([path.name, count.get('채택', 0), count.get('수정', 0), count.get('제외', 0), count.get('보류', 0), len(d['missing']),
                     sum(1 for m in d['missing'] if m.get('added'))])
    return [R.table('검토 결과 파일', ['파일', '채택', '수정', '제외', '보류', '누락 기록', '검토자가 더한 후보'], rows),
            R.table('기대 항목 줄의 결정(이 작업의 조건이 될 것)', ['문서', '판', '줄', '종류', '결정', '인용'], task_rows)]


@guard
def rules(previous):
    linked, known = X.rule_rows(TASK if PRACTICAL else None)
    if not linked:
        raise R.Blank('결과/조건_대조.csv에 행이 없습니다.')
    X.apply_review(TASK if PRACTICAL else None)
    _, data = event()
    out = []
    rows = []
    for r in linked:
        hit = []
        for e in data['events']:
            for c in e['candidates']:
                excluded_by = {x.get('rule_id') for x in c.get('exclusions', [])} | {x.get('rule_id') for x in c.get('reasons', []) if x.get('result') == 'EXCLUDE'}
                if c['sop'] == TASK and c['status'] == '제외' and r['rule_id'] in excluded_by:
                    hit.append(e['id'])
        rows.append([r['rule_id'], r['match'], r['근거'] or '(근거 없음)', r['까닭'], r['요청할_것'], ', '.join(hit) or '없음'])
        for f, n in r['refs']:
            out.append(R.source_lines(HERE / '자료' / f, n))
    missing = [x for x in known if x not in {r['rule_id'] for r in linked}]
    head = [R.table(f'조건마다 근거 대조 — 「바뀌는 답」 칸은 그 조건이 {TASK}를 제외한 지난 판정', ['rule_id', 'match', '근거', '까닭', '요청할 것', f'{TASK}를 제외한 지난 판정'], rows)]
    if missing:
        head.append(R.note('아직 근거 대조가 없는 조건: ' + ', '.join(missing)))
    return head + out


@guard
def other(previous):
    cfg = settings()
    if not set(cfg['보낼_문서']) & set(OTHER_DOCS):
        raise R.Blank('결과/나누기.json 「보낼_문서」에 다른 문서(' + ' · '.join(OTHER_DOCS) + ')가 아직 없습니다.')
    X.extract(cfg, prompt(), cfg['보낼_문서'])
    rows = []
    for name in cfg['보낼_문서']:
        d = X.load_candidates(name)
        empty, loose = X.coverage(cfg, name)
        rows.append([name, len(d['candidates']), len(d['unlocated']), sum(1 for w in d['warnings'] if '계약 꼴' in w), ' · '.join(empty) or '없음', len(loose), ' '.join(map(str, loose[:40])), X.made_with(d)])
    name, data, pairs = X.compare_baseline()
    out = [R.table('문서마다 후보와 누락을 가를 재료 — 후보 0개 조각은 그 조각의 답이 비었다는 뜻(원문 문장을 모델이 지시로 읽었는지 요청 글로 본다)',
                   ['파일', '후보', '찾지 못한 인용', '계약 꼴 아님', '후보 0개 조각(줄)', '후보가 걸리지 않은 내용 줄', '그 줄 번호(앞 40개)', '후보를 만든 판'], rows)]
    if data is None:
        out.append(R.note(f'받은 SOP 구조가 옮긴 문서({name})의 후보 파일이 아직 없습니다 — 보낼_문서에 넣습니다.'))
    else:
        out.append(R.table(f'받은 SOP 구조 ↔ {name} 후보(글자 짝 없음 = 원문 줄을 열어 실제 누락인지 내가 본다)', ['조치', '칸', '글', '짝지은 후보'], [list(p) for p in pairs]))
    return out


@guard
def collect(previous):
    if not X.role_rows():
        raise R.Blank('결과/역할.csv에 행이 없습니다.')
    e, _ = event()
    src = X.basis(JUDGED)
    n = next((i for i, x in enumerate(src.read_text(encoding='utf-8').splitlines(), 1) if f'"{e["id"]}"' in x), 0)
    got = X.collect_task(TASK, f'{src.relative_to(HERE).as_posix()}:{n}')
    out = [R.counts('이 작업의 조건', [(k, len(got[k])) for k in ('preparation', 'prohibitions', 'completion', 'remaining_questions', 'sop_diff')])]
    for k in ('preparation', 'prohibitions', 'completion'):
        out.append(R.table(k, ['검토 후보', '문서', '판', '절', '인용'], [[i['candidate'], i['doc_id'], i['rev'], i['section'], i['quote']] for i in got[k]]))
    out.append(R.table('sop_diff', ['where', 'item', 'note'], [[d['where'], d['item'], d['note']] for d in got['sop_diff']]))
    return out


@guard
def main_other(previous):
    out = main_run(previous)
    try:
        out += other(previous)
    except R.Blank as e:
        out.append(R.note(str(e)))
    return out


def save(previous):
    import subprocess, sys
    run = subprocess.run([sys.executable, str(HERE / 'check.py')], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=HERE)
    tail = run.stdout.strip().splitlines()[-12:]
    return [R.note('python check.py 출력(끝 12줄, 종료 코드 ' + str(run.returncode) + ')\n' + '\n'.join(tail))]


STEPS = [
    dict(no=1, name='폴더 · 사건 · 문서 묶음 파악', slots=[], run=look),
    dict(no=2, name='수업 모델 연결 확인', slots=[], run=connect),
    dict(no=3, name='기대 항목 먼저', slots=['결과/기대_항목.csv'], run=expect),
    dict(no=4, name='판단① 문서를 나누는 단위', slots=['결과/나누기.json'], run=split),
    dict(no=5, name='판단② 요청 글과 한 조각', slots=['결과/prompt.md'], run=trial),
    dict(no=6, name='주 대상 문서에 실행하고 기대와 대조', slots=[], run=main_run),
    dict(no=7, name='판단③ 검토 — 사내 문서와 제조사 지침', slots=['결과/검토_결정.csv'], run=review),
    dict(no=8, name='판단④ 조건표의 조건의 근거', slots=['결과/조건_대조.csv'], run=rules),
    dict(no=9, name='다른 문서에 다시 적용', slots=[], run=other),
    dict(no=10, name='고침 · 저장하고 다시 열기', slots=[], run=save),
]

