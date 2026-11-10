"""저장된 요청·반환·판단과 작성한 기록만 보여 주는 이 랩의 결과 화면."""
from pathlib import Path
import csv
import html
import io
import json
import os
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
TITLE = '원인 후보와 다음 점검 계획'
STEPS = []  # 기존 lab_steps.py의 가져오기 계약만 유지한다. 학습 단계는 가이드에 있다.


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

CSS = '''
*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#20342f;font:16px/1.7 "Malgun Gothic",sans-serif}
main{max-width:1180px;margin:auto;padding:28px 20px}h1{font-size:26px;margin:0 0 6px}h2{font-size:20px;margin:0 0 12px}h3{font-size:16px;margin:16px 0 6px}
section{background:#fff;border:1px solid #dce5df;border-radius:12px;padding:18px 20px;margin:16px 0}
p,h1,h2,h3,nav,summary,label,select{overflow-wrap:anywhere}.note,.prose{white-space:pre-wrap;overflow-wrap:anywhere}.meta,.note{color:#4b5c55}.meta{font-size:14px}
.links{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.links a{color:#176554;padding:4px 10px;border:1px solid #c9d6cf;border-radius:14px;text-decoration:none}
.tbl{max-width:100%;overflow-x:auto;overscroll-behavior-x:contain}.tbl:focus{outline:2px solid #176554;outline-offset:2px}
table{border-collapse:collapse;width:100%;min-width:48rem;font-size:14px}th,td{min-width:6em;padding:8px;border-bottom:1px solid #e3e9e5;text-align:left;vertical-align:top;word-break:keep-all;overflow-wrap:break-word}th{background:#eef3f0}
.tool{border:1px solid #ccd9d2;border-radius:8px;margin:10px 0;padding:10px 14px}.tool summary{cursor:pointer;font-weight:bold}
pre{max-height:28rem;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f5;padding:14px;font-size:13px;line-height:1.6}
.model{border-left:4px solid #687f74;padding:12px 16px;background:#f3f6f4}.error{border-left:4px solid #b3392c;padding:10px 14px;background:#fff1ed;white-space:pre-wrap;overflow-wrap:anywhere}
select{display:block;max-width:100%;width:100%;padding:8px;font:inherit}.request[hidden]{display:none}.record{border-top:1px solid #dce5df;margin-top:18px;padding-top:8px}
@media(max-width:600px){main{padding:16px 12px}section{padding:14px 12px}h1{font-size:23px}}
'''
JS = '''<script>
const picker=document.getElementById('request-select');
function reveal(article){document.querySelectorAll('.request').forEach(x=>x.hidden=x!==article);if(picker)picker.value=article.id;}
if(picker)picker.addEventListener('change',()=>reveal(document.getElementById(picker.value)));
function followHash(){const target=document.getElementById(decodeURIComponent(location.hash.slice(1)));const article=target&&target.closest('.request');if(article)reveal(article);}
window.addEventListener('hashchange',followHash);followHash();
</script>'''


def escape(value):
    return html.escape(str(value), quote=True)


def compact(value, length=150):
    text=' '.join(str(value).split())
    return text if len(text)<=length else text[:length]+'…'


def tool_summary(item):
    """반환 전체를 대체하지 않는 탐색용 요약. 원래 값은 접힌 상세에 모두 둔다."""
    result=item.get('result') or {}
    if item['status']!='ok':
        return '조회 오류 — '+compact(item.get('error','오류 내용 없음')), '출처를 얻지 못한 호출', ''
    name=item['tool']
    if name=='graph_query':
        shown=len(result.get('nodes',[]));total=result.get('total',shown)
        summary=f'노드 {shown}/{total}개 · 관계 {len(result.get("rels",[]))}개'
        if result.get('next_offset') is not None:summary+=' · 다음 페이지 있음'
        return summary,result.get('source',''),''
    if name=='document':
        document=result.get('document') or {}
        source=document.get('file') or result.get('source','')
        revision=f'{document.get("doc_id","")} · {document.get("revision","")}판 · {document.get("status","")}'
        region=f'{result["line_start"]}~{result["line_end"]}줄' if 'line_start' in result else f'목차 {len(result.get("headings",[]))}개'
        return revision+' · '+region,source,'시행일 '+document['effective'] if document.get('effective') else '시행일 기록 없음'
    if name=='observations':
        statistics=result.get('statistics') or {}
        tags=' · '.join(f'{tag} {values.get("count",0)}개' for tag,values in statistics.items())
        summary=f'{result.get("asset","")} · {result.get("dataset","")} · {result.get("row_count",0)}행 · {tags}'
        sources=', '.join(result.get('source_files',[])) or '해당 구간에 반환된 원천 행 없음'
        return summary,sources,f'{result.get("start_exclusive","")} 초과 ~ {result.get("end_inclusive","")} 이하'
    if name=='history':
        return f'{result.get("asset","")} · 이력 {result.get("row_count",0)}행',result.get('source',''),f'{result.get("start","")} ~ {result.get("end","")}'
    return '반환 내용 있음',result.get('source',''),''



def refs(values, suffix):
    return ', '.join('<a href="#evidence-' + escape(str(value) + suffix) + '">' + escape(value) + '</a>' for value in values)


def table(columns, rows, suffix='', ref_columns=()):
    head = ''.join('<th scope="col">' + escape(x) + '</th>' for x in columns)
    body = ''.join('<tr>' + ''.join('<td>' + (refs(cell, suffix) if number in ref_columns else escape(cell)) + '</td>' for number, cell in enumerate(row)) + '</tr>' for row in rows)
    return '<div class="tbl" tabindex="0" aria-label="표 내용. 좁은 화면에서는 좌우로 스크롤합니다.">' + '<table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>'


def section(name, title, content, suffix=''):
    return '<section id="' + escape(name + suffix) + '"><h2>' + escape(title) + '</h2>' + content + '</section>'


def render_tool(item, suffix):
    brief, source, period = tool_summary(item)
    heading = item['id'] + ' · ' + item['tool'] + ' · ' + ('조회 성공' if item['status'] == 'ok' else '조회 오류')
    content = '<b>' + escape(heading) + '</b><p class="meta">' + escape(brief) + '</p>'
    content += '<p class="meta">출처: ' + escape(source or '상세에서 확인') + '</p>'
    if period: content += '<p class="meta">자료 시각: ' + escape(period) + '</p>'
    if item.get('called_at'): content += '<p class="meta">도구 호출 시각: ' + escape(item['called_at']) + '</p>'
    original = json.dumps(item, ensure_ascii=False, indent=2)
    return ('<div class="tool" id="evidence-' + escape(item['id'] + suffix) + '">' + content +
            '<details data-tool-id="' + escape(item['id']) + '"><summary>입력·반환 원문 펼치기</summary><pre>' + escape(original) + '</pre></details></div>')


def request_content(state, suffix):
    request = state['request']; plan = state.get('plan'); ledger = state.get('ledger', [])
    labels = []; sections = []
    if state.get('notices'):
        sections.append(section('input-notices', '실행 입력 확인', ''.join('<div class="error">' + escape(x) + '</div>' for x in state['notices']), suffix))
    if plan:
        if plan.get('candidates'):
            rows = [[x.get('name', x['cause_id']), x['status'], x['reason'], x['evidence_refs']] for x in plan['candidates']]
            sections.append(section('candidates', '원인 후보의 증거 대조', table(['후보', '상태', '이유', '근거'], rows, suffix, (3,)), suffix)); labels.append(('candidates', '원인 후보'))
        if plan.get('delivery_questions'):
            rows = [[x['recipient'], x['question']] for x in plan['delivery_questions']]
            content = '<p>수집과 후보 판정은 위 결과대로 보존됩니다. 아래는 점검 전달 전에 확인할 업무 입력이며 다음 점검 계획이 아닙니다.</p>'
            content += table(['확인할 역할', '정해지지 않은 전달 요구'], rows)
            sections.append(section('delivery-questions', '전달 요구 확인 필요', content, suffix)); labels.append(('delivery-questions', '전달 요구'))
        if plan.get('next_checks'):
            rows = [[x['recipient'], x['action'], ' / '.join(x['preconditions']), x['evidence_refs']] for x in plan['next_checks']]
            content = table(['받을 역할', '확인할 일', '작업 전제', '근거'], rows, suffix, (3,))
            content += '<p class="note">전달 판단: ' + escape(plan.get('delivery_reason', '')) + '</p>'
            if plan.get('safety'): content += '<p class="note">' + escape(plan['safety'].get('meaning', '')) + '</p>'
            sections.append(section('checks', '다음 점검', content, suffix)); labels.append(('checks', '다음 점검'))
        if plan.get('delivery_choices'):
            rows = [[x['choice'], x['source'], x['changed_action'], x['input_file'] + ':' + str(x['input_line'])] for x in plan['delivery_choices']]
            sections.append(section('delivery-basis', '점검 전달에 사용한 요구', table(['선택한 요구', '근거', '달라질 행동', '입력 위치'], rows), suffix))
        if plan.get('unresolved'):
            content = '<pre>' + escape(json.dumps(plan['unresolved'], ensure_ascii=False, indent=2)) + '</pre>'
            sections.append(section('questions', '추가 확인할 근거', content, suffix)); labels.append(('questions', '추가 확인'))
    errors = [x for x in ledger if x['status'] != 'ok']
    if errors:
        content = '<p>실제 호출에서 발생한 오류입니다. 이후 성공한 조회와 함께 대조합니다.</p>'
        content += ''.join('<div class="error">' + refs([x['id']], suffix) + ' · ' + escape(x['tool']) + '\n' + escape(x.get('error', '')) + '</div>' for x in errors)
        sections.append(section('errors', '도구 조회 오류', content, suffix)); labels.append(('errors', '조회 오류'))
    if state.get('status') not in ('완료', '진행 중') and state.get('termination'):
        sections.append(section('execution', '실행에서 확인할 내용', '<div class="error">' + escape(state['termination']) + '</div>', suffix)); labels.append(('execution', '실행 확인'))
    model_report = (plan or {}).get('model_summary', state.get('model_report'))
    if model_report is not None:
        report = model_report; summary = report.get('summary', '') if isinstance(report, dict) else str(report)
        references = report.get('evidence_refs', []) if isinstance(report, dict) else []
        content = ('<div class="model"><p>모델의 원문 응답입니다. 문장의 통계량·시각·출처를 도구 반환과 대조합니다. 이 표시가 내용 검증을 뜻하지는 않습니다.</p>'
                   '<div class="prose" data-model-summary>' + escape(summary) + '</div><p class="meta">모델이 든 근거: ' + refs(references, suffix) + '</p></div>')
        sections.append(section('model-summary', '모델이 쓴 요약', content, suffix)); labels.append(('model-summary', '모델 요약'))
    if ledger:
        content = '<p>도구의 출처·자료 시각을 보고 필요한 호출의 입력·반환 원문을 펼칩니다.</p>' + ''.join(render_tool(x, suffix) for x in ledger)
        sections.append(section('evidence', '조회한 근거', content, suffix)); labels.append(('evidence', '조회 근거'))
    if state.get('previous'):
        content = '<p>아래 파일은 이전판의 기록이며 현재 후보·점검 결과에 합치지 않습니다.</p>'
        content += '<ul>' + ''.join('<li><a href="' + escape(x['path']) + '">' + escape(x['name']) + '</a></li>' for x in state['previous']) + '</ul>'
        sections.append(section('previous-results', '이전판 결과', content, suffix)); labels.append(('previous-results', '이전판 결과'))
    if not sections: sections.append('<p class="note">요청을 읽었습니다. 도구가 반환한 근거와 판단 결과는 실행이 이어지면 이곳에 나타납니다.</p>')
    nav = '<nav class="links" aria-label="요청 결과">' + ''.join('<a href="#' + escape(key + suffix) + '">' + escape(title) + '</a>' for key, title in labels) + '</nav>'
    heading = '<h2>' + escape(request['request_id']) + '</h2><p class="note">' + escape(request['asset'] + ' · 기준시각 ' + request['as_of']) + '</p>'
    return heading + nav + ''.join(sections)


def authored_records(root):
    """빈 틀·열 이름·빈 제목은 나열하지 않고 실제 작성된 내용만 읽는다."""
    pieces = []; errors = []
    for name, title in [('requirements.md', '요구'), ('정한_것.csv', '선택과 근거'), ('plan.md', '조회와 판단 계획'), ('expected.csv', '원문으로 정한 기대'), ('review.csv', '원자료와 결과 대조'), ('검토_정정.md', '검토와 정정')]:
        path = root / '결과' / name
        if not path.is_file(): continue
        try:
            text = path.read_text(encoding='utf-8-sig')
            if path.suffix == '.csv':
                lines = text.splitlines(keepends=True)
                while lines and (not lines[0].strip() or lines[0].lstrip().startswith('#')): lines.pop(0)
                reader = csv.DictReader(io.StringIO(''.join(lines))); rows = list(reader)
                if not rows: continue
                if any(None in row or None in row.values() for row in rows): raise ValueError('열 이름과 행의 칸 수가 다릅니다.')
                columns = reader.fieldnames or []
                content = table(columns, [[row.get(key, '') for key in columns] for row in rows])
            else:
                lines = [line for line in text.splitlines() if '제공 빈 틀' not in line]
                if not any(line.strip() and not line.lstrip().startswith('#') for line in lines): continue
                content = '<div class="prose">' + escape('\n'.join(lines).strip()) + '</div>'
            pieces.append('<div class="record"><h3>' + escape(title) + '</h3><p class="meta">결과/' + escape(name) + '</p>' + content + '</div>')
        except (OSError, UnicodeError, ValueError, csv.Error) as error:
            errors.append('결과/' + name + ': ' + str(error))
    return ''.join(pieces), errors


def render_document(root=None):
    root = Path(root or ROOT); states = []; errors = []
    for path in sorted((root / '결과/runs').glob('*/state.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True):
        try: states.append(read_json(path))
        except (OSError, ValueError, UnicodeError) as error: errors.append(path.relative_to(root).as_posix() + ': ' + str(error))
    body = ''; picker = ''
    if len(states) > 1:
        options = ''.join('<option value="request-' + str(i) + '">' + escape(s['request']['request_id'] + ' · ' + s['request']['asset'] + ' · ' + s['request']['as_of']) + '</option>' for i, s in enumerate(states))
        picker = '<label for="request-select">확인할 요청 — 최근 저장한 요청부터</label><select id="request-select">' + options + '</select>'
    for number, state in enumerate(states):
        suffix = '' if number == 0 else '-' + state['request']['request_id']
        body += '<article class="request" id="request-' + str(number) + '"' + (' hidden' if number else '') + '>' + request_content(state, suffix) + '</article>'
    if not states: body = '<p class="note">요청을 실행하면 원인 후보·다음 점검·조회 근거가 이곳에 나타납니다.</p>'
    records, record_errors = authored_records(root); errors.extend(record_errors)
    if errors: body += section('file-errors', '결과 파일 읽기 오류', ''.join('<div class="error">' + escape(x) + '</div>' for x in errors))
    if records: body += section('records', '내가 작성한 요구·계획·대조', records)
    counts = {}
    try:
        data = read_json(root / '자료/data_manifest.json'); sources = read_json(root / '입력/source_manifest.json')
        counts = {'지식 노드': sources['graph_counts']['nodes'], '관계': sources['graph_counts']['rels'], '요청': data['request_count'], '관측 설비': len(data['assets'])}
        content = '<p>' + escape(' · '.join(f'{key} {value}개' for key, value in counts.items())) + '</p><p class="note">관측 내보내기 범위: ' + escape(data['from'] + ' ~ ' + data['through']) + '</p>'
        body += section('inputs', '제공 입력', content)
    except (OSError, ValueError, KeyError) as error:
        errors.append('제공 입력 목록: ' + str(error)); body += section('input-errors', '입력 목록 읽기 오류', '<div class="error">' + escape(errors[-1]) + '</div>')
    doc = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>' + escape(TITLE) + '</title><style>' + CSS + '</style></head><body><main><h1>' + escape(TITLE) + '</h1>'
           '<p class="note">실행 뒤 이 화면을 새로고침합니다. 저장된 결과는 python run_agent.py --show로 다시 엽니다.</p>' + picker + body + '</main>' + JS + '</body></html>\n')
    latest = states[0] if states else None
    report = {'requests': len(states), 'latest_request': latest['request'] if latest else None,
              'candidates': len((latest.get('plan') or {}).get('candidates', [])) if latest else 0,
              'checks': len((latest.get('plan') or {}).get('next_checks', [])) if latest else 0,
              'tools': len(latest.get('ledger', [])) if latest else 0,
              'tool_errors': [x for x in latest.get('ledger', []) if x['status'] != 'ok'] if latest else [],
              'file_errors': errors, 'input_counts': counts}
    return doc, report


def write(open_browser=True, root=None, output=None):
    root = Path(root or ROOT); out = Path(output) if output else root / '결과/보기.html'
    doc, report = render_document(root)
    first = not out.exists(); out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.name + '.tmp'); temporary.write_text(doc, encoding='utf-8', newline='\n'); os.replace(temporary, out)
    if report['latest_request']:
        request = report['latest_request']; print(request['request_id'] + ' · ' + request['asset'] + ' · ' + request['as_of'])
        print(f'원인 후보 {report["candidates"]}개 · 다음 점검 {report["checks"]}개 · 도구 조회 {report["tools"]}건')
        for error in report['tool_errors']: print('조회 오류 ' + error['id'] + ' · ' + error.get('error', ''))
    else:
        print('제공 입력: ' + ' · '.join(f'{key} {value}개' for key, value in report['input_counts'].items()))
    for error in report['file_errors']: print('파일 읽기 오류: ' + error)
    print('결과/보기.html — 실행 결과와 원자료를 대조하고 브라우저에서 새로고침합니다.')
    if first and open_browser: webbrowser.open(out.resolve().as_uri())
    return int(bool(report['file_errors']))


def write_workflow(root, states, inventory):
    """기능별 실행 고리가 판본을 확인한 현재 결과만 표시한다."""
    root = Path(root); sections = []
    for number, state in enumerate(states):
        suffix = '' if number == 0 else '-' + state['request']['request_id']
        sections.append('<article class="request">' + request_content(state, suffix) + '</article>')
    if not states: sections.append('<p class="note">요청을 실행하면 조회 근거와 판단 결과가 이곳에 나타납니다.</p>')
    records = []
    for path in sorted((root / 'app/features').glob('*')):
        if path.suffix not in ['.md', '.csv']: continue
        text = path.read_text(encoding='utf-8-sig')
        lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
        if path.suffix == '.csv':
            rows = list(csv.reader(lines))
            if len(rows) < 2: continue
            content = table(rows[0], rows[1:])
        else:
            if not lines: continue
            content = '<div class="prose">' + escape(text) + '</div>'
        records.append('<h3>' + escape(path.name) + '</h3>' + content)
    if records: sections.append(section('records', '내가 작성한 요구·계획·대조', ''.join(records)))
    data = inventory['data']
    content = f'<p>지식 노드 {inventory["nodes"]}개 · 관계 {inventory["rels"]}개 · 요청 {data["request_count"]}개 · 관측 설비 {len(data["assets"])}개</p>'
    sections.append(section('inputs', '제공 입력', content))
    doc = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(TITLE) + '</title><style>' + CSS + '</style></head>'
           '<body><main><h1>' + escape(TITLE) + '</h1><p class="note">실행 뒤 이 화면을 새로고침하고 원자료와 대조합니다.</p>' + ''.join(sections) + '</main></body></html>\n')
    output = root / 'output/result.html'; output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.tmp'); temporary.write_text(doc, encoding='utf-8', newline='\n'); os.replace(temporary, output)
    print('output/result.html — 실제 결과와 원자료를 대조합니다.')
    return 0
