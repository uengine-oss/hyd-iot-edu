"""학생용 완성본 — 문서 지식 네 랩을 실습 폴더와 따로 받는 ZIP으로 묶는다(코딩랩.md K-4 · K-12, 가이드.md P-3). 학생 폴더 · package-index 밖.

완성본 = 가이드의 「정답 보기」를 단계마다 차례로 따라 한 결과(replay.py — 기본 갈래 fills.py)에 기록 파일을 채운 것. 모델은 부르지 않는다:
추출 랩은 강사 추출 실행 run1의 응답 기록(+ 같은 요청을 다른 폴더에서 한 번 더 보낸 run2의 그 조각 기록)을 쓰고, 폴더 표지 · .env는 넣지 않는다 —
완성본 폴더에서 `python show_result.py`를 다시 돌려도 정할 자리가 같으면 제공 코드가 후보 파일을 그대로 두어(같은 설정 표지) 다시 보내지 않는다.
그래프 랩은 새 폴더에서 lab_db.py --no-open · show_result.py --no-open으로 실제 Neo4j에 다시 적재해 내보내기가 같은지 본다.
확인: 묶은 ZIP을 새 폴더에 풀어 키 없이 `python show_result.py --no-open` → `python check.py`가 종료 코드 0(DoD 19).
산출: 산출물/<반>/실습/NN회차/완성본/<랩>_학생용완성본.zip. 어긋나면 「불일치」를 찍고 종료 코드 1.
사용: HYD_MAIN_ROOT=<main 체크아웃> python completed.py [랩 열쇠 …]
"""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path[:0] = [str(HERE), str(TOOLS)]
import build_document_labs as BD  # noqa: E402
import replay as RP  # noqa: E402

STAMP = (2026, 1, 1, 0, 0, 0)
DROP = ['.env', '결과/폴더_표지.txt', '결과/.보기_이전.json', '랩_연결.json']
BAD = []


def fail(msg):
    BAD.append(msg)
    print('불일치: ' + msg)


def table(head, rows):
    return '| ' + ' | '.join(head) + ' |\n|' + '---|' * len(head) + '\n' + ''.join('| ' + ' | '.join(str(c).replace('|', '/').replace('\n', ' ') for c in r) + ' |\n' for r in rows)


def extract_record(folder, practical):
    sys.path.insert(0, str(folder))
    import importlib
    X = importlib.import_module('doc_extract')
    importlib.reload(X)
    rows, extra = X.compare_expected()
    diff = [(f'{f} {n}줄 {k}', s, {'종류 다름': '다른 종류로 뽑음', '줄 못 정함': '같은 글이 여러 곳 — 코드가 줄을 정하지 못함', '누락': '누락'}.get(s, s),
             '결정 표에서 그 줄을 골라 검토자가 더한 후보로 둠' if s == '줄 못 정함' else '원문 줄로 확인') for f, n, k, _, s, _ in rows if s != '맞음'] or [('기대 줄 모두', '맞음', '차이 없음', '—')]
    trial = json.loads((folder/'결과/시험_조각.json').read_text(encoding='utf-8'))
    q = [{X.squash(c['quote']) for c in a['candidates']} for a in trial['answers']]
    again = [(trial['answers'][0]['record'], trial['answers'][1]['record'], f'함께 있는 인용 {len(q[0] & q[1])} · 첫 답에만 {len(q[0] - q[1])} · 다시 보낸 답에만 {len(q[1] - q[0])}',
              '첫 기록 — 후보 파일이 이 기록으로 만들어짐(다시 보낸 답은 다른 폴더의 같은 요청)')]
    other = []
    for name in BD.OTHER_DOCS + ['HM-8_매뉴얼.md']:
        d = X.load_candidates(name)
        other.append((f'{d["doc_id"]} {d["rev"]}', len(d['candidates']), '결과 화면의 짝 표에서 원문 줄로 셈(완성본은 세지 않음)', '—', '없음', '—'))
    sys.path.remove(str(folder))
    sys.modules.pop('doc_extract', None)
    task = '## 이 사건의 작업\n\n- 작업: SOP-COOL-14 쿨러 핀 세척(근본 조치)\n- 근거(파일:줄): 입력/sop.json의 REMEDIED_BY 관계 · 자료/HM-8_매뉴얼.md:73\n\n' if practical else ''
    return ('# 문서 지식 검토 기록\n\n## 목표와 질문\n\n핀 세척 작업의 조건과 판정에 쓴 조건이 문서 어디에서 왔는지 원문 인용으로 확인한다(START.md 「해결할 질문」).\n\n'
            '## 이 답을 쓰는 사람과 쓰는 곳\n\n' + ('보전 야간조 · 설비보전팀장 — 핀 세척 전 되짚기와 작업지시 승인.' if practical else '설비보전팀장 — HYD-02 핀 세척 작업지시를 내기 전.') + '\n\n' + task +
            '## 정한 것\n\n고른 것 · 근거(파일:줄) · 바뀌는 답은 `결과/정한_것.csv`에 적습니다.\n\n## 기대 항목\n\n기대 항목은 `결과/기대_항목.csv`에 적습니다.\n\n- 기대 칸을 쓴 시각: 2026-10-28 09:00(첫 후보 파일보다 앞)\n\n'
            '## 기대와 다른 줄\n\n' + table(['문서 · 줄 · 종류', '결과 화면의 표시', '차이 종류', '까닭(원문 줄)'], diff) + '\n'
            '## 같은 요청을 한 번 더 보낸 결과\n\n' + table(['첫 응답 기록', '다시 보낸 응답 기록', '다른 점', '검토에 쓸 기록과 까닭'], again) + '\n'
            '## 다른 문서에 적용\n\n' + table(['문서 · 판', '후보 수', '실제 누락', '근거 없는 생성', '고친 점', '고친 뒤 다시 센 수'], other) + '\n'
            '## 남은 질문\n\n보류한 제조사 항목의 적용 여부(설비보전팀), 트립 뒤 복귀 절의 원문(스캔본에 그 쪽이 없음).\n\n'
            '## 저장 기록\n\n- 기준일: 2026-10-28\n- 저장 시점: 2026-10-28 11:00\n- 확인하지 못한 점: 수업 모델의 답은 다시 보내면 달라질 수 있다 — 이 완성본은 강사 실행의 응답 기록으로 만든 판이다.\n')


def snap_counts(snaps, title):
    """그 개수 블록이 처음 나온 단계의 값 — {이름: 값}."""
    for s in snaps:
        if 'counts:' + title in s:
            return dict(s['counts:' + title])
    raise RuntimeError(f'정답 재생 스냅숏에 「{title}」 개수가 없습니다')


def graph_record(folder, snaps):
    """통합 04-3 구축 기록 — 정답 재생의 단계별 개수(snaps)와, 켜 둔 랩 DB에 제공 조회를 다시 돌린 결과로 칸을 채운다."""
    sys.path.insert(0, str(folder))
    import importlib
    G = importlib.import_module('doc_graph')
    importlib.reload(G)
    vals = G.ask_values()
    q = {name: G.ask(name, vals) for name in ('q1', 'q2', 'q3', 'q4', 'hold', 'q5_target', 'q5_section')}
    now = G.now_rows()
    rq = json.loads((folder/'결과/남은_질문.json').read_text(encoding='utf-8'))
    sys.path.remove(str(folder))
    sys.modules.pop('doc_graph', None)
    rows1 = [dict(zip(q['q1'][0], r)) for r in q['q1'][1]]
    task = [r for r in rows1 if r['sop'] == BD.TASK]
    prep = [r for r in task if r['role'] in ('준비', '승인')]
    body = [r for r in task if r['role'] in ('순서', '금지', '완료')]
    remote = sorted({r['sop'] for r in rows1 if r['section'] in ('HM-8.5', 'HM-8.6', 'HM-8.8')})
    rules = {}
    for r in q['q2'][1]:
        rules.setdefault(r[0], set()).add(r[2] or '원문 없음')
    rule_text = ' · '.join(f'{k} {"/".join(sorted(v))}' for k, v in sorted(rules.items()))
    sources = sorted({r['읽을_원천'] for r in now})
    exp = [
        ('질문 1 핀 세척 준비 · 승인', f'SOP-COOL-14 준비 · 승인 {len(prep)}행', any('CMMS' in r['quote'] for r in prep), 'HM-8 1.1 HM-8.7 74줄 문장이 준비 · 승인으로 나옴'),
        ('질문 1 핀 세척 단계 · 금지 · 완료', f'SOP-COOL-14 순서 · 금지 · 완료 {len(body)}행', any('고압수' in r['quote'] for r in body if r['role'] == '금지') and any('80' in r['quote'] for r in body if r['role'] == '완료'),
         '세 단계 · 고압수 금지 · CE 80 % 확인이 나옴(제조사 지침 고압수 금지도 함께)'),
        ('질문 1 원격 조치 공통 조건', f'HM-8.5 · 8.6 · 8.8 지식이 걸린 조치 {", ".join(remote)}', remote == ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13'], '세 원격 조치에 같은 공통 조건이 걸림'),
        ('질문 2 규칙 근거', rule_text, rules.get('R4') == {'불일치'} and rules.get('R5') == {'원문 없음'} and all(rules.get(k) == {'일치'} for k in ('R1', 'R2', 'R3')),
         'R5는 근거 지식이 없어 빈 행 — HM-9.4 본문이 묶음에 없음'),
        ('질문 3 현재 값 원천', f'그래프: 확인할 센서 {", ".join(r[0] for r in q["q3"][1])}(값은 그래프 밖) · 읽을 원천 {" · ".join(sources)}', any('시계열' in s for s in sources) and any('MES' in s for s in sources),
         '센서는 그래프로, 값은 현재값_원천.csv의 원천에서 읽음'),
    ]
    model, first, again, more = (snap_counts(snaps, t) for t in ('랩 DB — 설비 모델과 조치 기준 적재 뒤', '적재 전후', '다시 적재한 뒤(직전 실행과 같으면 늘지 않은 것)', '다른 문서 추가 전후'))
    diff = snap_counts(snaps, '추가 전 그래프와 비교')
    kinds = {}
    for x in rq:
        kinds[x['kind']] = kinds.get(x['kind'], 0) + 1
    hold = q['hold'][1][0]
    target, section = q['q5_target'][1][0], q['q5_section'][1][0]
    return ('# 온톨로지 구축 기록\n\n## 목표와 질문\n\nHYD-02 냉각 성능 상실의 조치와 핀 세척(SOP-COOL-14)의 조건 · 근거를 검토한 문서 지식으로 그래프에 잇고, START.md 「해결할 질문」 다섯에 원문대로 답하는지 확인한다.\n\n'
            '## 이 답을 쓰는 사람과 쓰는 곳\n\n설비보전팀장 — 핀 세척 작업지시를 내기 전에 조건 · 근거를 그래프로 찾는다.\n\n'
            '## 정한 것\n\n고른 것 · 근거(파일:줄) · 바뀌는 답은 `결과/정한_것.csv`에 적습니다.\n\n'
            '## 질문별 기대와 실제\n\n기대 답은 `결과/기대_답.csv`에 적습니다.\n\n- 기대 칸을 쓴 시각: 2026-10-28 09:00(첫 적재보다 앞)\n\n'
            + table(['질문', '실제 결과(결과 화면)', '같음 · 다름과 까닭'], [(a, b, ('같음 — ' if ok else '다름 — ') + why) for a, b, ok, why in exp]) + '\n'
            '## 적재 수\n\n' + table(['시점', '노드 수', '관계 수', '확인한 것'], [
                ('설비 모델 · 조치 기준 적재 뒤', model['노드'], model['관계'], '입력 모델 · SOP 구조 · 조건표만'),
                ('첫 적재 뒤', first['노드'], first['관계'], f'적재한 지식 {first["적재한 지식"]} · 기존 ID에 이은 지식 {first["기존 ID에 이은 지식"]}'),
                ('같은 적재 다시', again['노드'], again['관계'], '다른 문서의 조건 행을 더해 적재한 뒤 다시 실행 — 수가 늘지 않음'),
                ('다른 문서 추가 뒤', more['노드'], more['관계'], '제조사 지침 · 예비품 기준 행을 더함')]) + '\n'
            '## 다른 문서 추가 뒤 기존 연결\n\n' + table(['확인한 것', '추가 전', '추가 뒤', '같음 · 다름'], [
                ('노드 · 관계 수', f'{again["노드"]} · {again["관계"]}', f'{more["노드"]} · {more["관계"]}', f'늘어남(노드 {diff["늘어난 노드"]} · 관계 {diff["늘어난 관계"]})'),
                ('속성이 바뀐 기존 노드', '—', diff['속성이 바뀐 기존 노드'], '같음' if diff['속성이 바뀐 기존 노드'] == 0 else '다름'),
                ('사라진 노드 · 관계', '—', f'{diff["사라진 노드"]} · {diff["사라진 관계"]}', '같음' if diff['사라진 노드'] == diff['사라진 관계'] == 0 else '다름')]) + '\n'
            '## 보류 후보 · 제공되지 않은 것 조회\n\n' + table(['물은 것', '결과', '원문 · 목록 근거'], [
                ('보류 후보 둘(HM-9-M008 · OEM-HPP45A-MM-M054)', f'물은 {hold[0]} · 그래프에 있는 {hold[1]}', '입력/검토결과의 status pending'),
                (f'작업 · 대상 {target[0]}', f'대상 {target[1]} · 이은 지식 {target[2]}', '설비 모델에는 있고 검토한 문서 지식은 없음'),
                (f'절 {section[0]}', f'절 노드 {section[1]}', '자료/HM-9장_스캔본.txt 목차에만 있고 본문 쪽이 없음')]) + '\n'
            '## 답할 수 있는 것과 없는 것\n\n' + table(['질문', '그래프로 답함 · 현재 값 필요 · 추가 자료 필요 · 원문에 없음', '근거(원천 이름 · 파일)'], [
                ('질문 1', '그래프로 답함', '자료/HM-8_매뉴얼.md 73~88줄 · 다른 문서의 조건 행'),
                ('질문 2', '그래프로 답함(R1~R4) · 원문에 없음(R5)', '자료/SR-04_설비안전규정_발췌.txt 10 · 11줄, 자료/HM-9장_스캔본.txt 15줄'),
                ('질문 3', '현재 값 필요', ' · '.join(sources)),
                ('질문 4', '그래프로 답함', '자료/OEM-HPP45A_정비지침_영한.md · 자료/PR-07_예비품기준.md'),
                ('질문 5', '추가 자료 필요', '결과/남은_질문.json의 제공되지 않은 문서 · 절')]) + '\n'
            '## 남은 질문\n\n`결과/남은_질문.json` — ' + ' · '.join(f'{k} {v}' for k, v in sorted(kinds.items())) + '.\n\n'
            '## 저장 기록\n\n- 랩 DB 주소(인증값 제외): 127.0.0.1의 이 폴더 전용 랩 DB(포트는 랩_연결.json — 폴더마다 다름)\n- 기준일: 2026-10-28\n- 저장 시점: 2026-10-28 12:00\n'
            '- 확인하지 못한 점: 보류한 제조사 항목의 적용 여부, HM-9.4 본문.\n')


CARD_CHECK = {'준비 조건': ('CMMS',), '금지 · 제한': ('고압수',), '작업 순서': ('잠금', '압축공기', '80'), '완료 기준': ('80',),
              '작업 직전 확인할 현재 값': ('시계열',), '승인': ('설비보전팀장',), '남은 질문': ('HM-9.4',)}


def card_record(folder, snaps):
    """실전 03-5 구축 기록 — 카드 절마다 기대 글자가 실제 카드에 있는지, 단계별 개수(snaps), 켜 둔 랩 DB의 제공 조회로 칸을 채운다."""
    sys.path.insert(0, str(folder))
    import importlib
    G = importlib.import_module('doc_graph')
    importlib.reload(G)
    vals = G.ask_values()
    q = {name: G.ask(name, vals) for name in ('q5_target', 'q5_section')}
    now = G.now_rows()
    rq = json.loads((folder/'결과/남은_질문.json').read_text(encoding='utf-8'))
    sys.path.remove(str(folder))
    sys.modules.pop('doc_graph', None)
    card = (folder/f'결과/작업확인카드_{BD.TASK}.md').read_text(encoding='utf-8')
    secs, cur = {}, None
    for line in card.splitlines():
        if line.startswith('## '):
            cur = line[3:].strip()
            secs[cur] = []
        elif cur and (line.startswith('- ') or line[:1].isdigit()):
            secs[cur].append(line)
    rows = []
    for head, words in CARD_CHECK.items():
        body = '\n'.join(secs.get(head, []))
        ok = all(w in body for w in words)
        rows.append((head, f'{len(secs.get(head, []))}줄', ('같음 — ' if ok else '다름 — ') + ' · '.join(words) + (' 이(가) 원문 인용과 함께 나옴' if ok else ' 이(가) 카드에 없음')))
    other = (folder/'결과/작업확인카드_SOP-COOL-11.md')
    model, first, again = (snap_counts(snaps, t) for t in ('랩 DB — 설비 모델과 조치 기준 적재 뒤', '적재 전후', '다시 적재한 뒤(직전 실행과 같으면 늘지 않은 것)'))
    kinds = {}
    for x in rq:
        kinds[x['kind']] = kinds.get(x['kind'], 0) + 1
    target, section = q['q5_target'][1][0], q['q5_section'][1][0]
    sources = sorted({r['읽을_원천'] for r in now})
    return ('# 온톨로지 구축 기록\n\n## 목표와 질문\n\nHYD-02 핀 세척(SOP-COOL-14)의 작업 확인 카드 — 준비 · 금지 · 순서 · 완료 · 작업 직전 확인할 현재 값 · 승인 · 남은 질문을 검토한 문서 지식의 원문 절 · 인용으로 만든다.\n\n'
            '## 이 답을 쓰는 사람과 쓰는 곳\n\n보전 야간조 · 설비보전팀장 — 핀 세척 작업지시 전 되짚기.\n\n'
            '## 정한 것\n\n고른 것 · 근거(파일:줄) · 바뀌는 답은 `결과/정한_것.csv`에 적습니다.\n\n'
            '## 카드 항목별 기대와 실제\n\n기대 답은 `결과/기대_답.csv`에 적습니다.\n\n- 기대 칸을 쓴 시각: 2026-10-28 09:00(카드를 만들기 앞)\n\n'
            + table(['카드 항목', '실제 결과(결과 화면)', '같음 · 다름과 까닭'], rows) + '\n'
            '## 적재 수\n\n' + table(['시점', '노드 수', '관계 수', '확인한 것'], [
                ('설비 모델 · 조치 기준 적재 뒤', model['노드'], model['관계'], '입력 모델 · SOP 구조 · 조건표만'),
                ('첫 적재 뒤', first['노드'], first['관계'], f'적재한 지식 {first["적재한 지식"]} · 기존 ID에 이은 지식 {first["기존 ID에 이은 지식"]}'),
                ('같은 적재 다시', again['노드'], again['관계'], '다른 문서의 조건 행을 더해 적재한 뒤 다시 실행 — 수가 늘지 않음')]) + '\n'
            '## 다른 작업 · 제공되지 않은 것\n\n' + table(['물은 것', '결과', '원문 · 목록 근거'], [
                ('다른 작업 SOP-COOL-11 카드', '카드 있음' if other.is_file() else '결과 없음', '입력/sop.json의 MITIGATED_BY · 자료/HM-8_매뉴얼.md 47줄'),
                (f'작업 · 대상 {target[0]}', f'대상 {target[1]} · 이은 지식 {target[2]}', '설비 모델에는 있고 검토한 문서 지식은 없음'),
                (f'절 {section[0]}', f'절 노드 {section[1]}', '자료/HM-9장_스캔본.txt 목차에만 있고 본문 쪽이 없음')]) + '\n'
            '## 답할 수 있는 것과 없는 것\n\n' + table(['질문', '그래프로 답함 · 현재 값 필요 · 승인 필요 · 공급 정보 · 원문에 없음', '근거(원천 이름 · 파일)'], [
                ('준비 · 금지 · 순서 · 완료', '그래프로 답함', '자료/HM-8_매뉴얼.md 74~79줄 · 자료/OEM-HPP45A_정비지침_영한.md 112줄'),
                ('작업 직전 확인할 현재 값', '현재 값 필요', ' · '.join(sources)),
                ('작업 실행', '승인 필요 — 카드는 설비보전팀장 승인을 대신하지 않음', '자료/HM-8_매뉴얼.md 74줄'),
                ('쿨러 코어 교체 부품', '공급 정보 — 품번 · 공급사는 예비품 기준, 재고는 ERP', '자료/PR-07_예비품기준.md 16줄'),
                ('트립 뒤 복귀', '원문에 없음', '자료/HM-9장_스캔본.txt 15줄')]) + '\n'
            '## 남은 질문\n\n`결과/남은_질문.json` — ' + ' · '.join(f'{k} {v}' for k, v in sorted(kinds.items())) + '.\n\n'
            '## 저장 기록\n\n- 랩 DB 주소(인증값 제외): 127.0.0.1의 이 폴더 전용 랩 DB(포트는 랩_연결.json — 폴더마다 다름)\n- 기준일: 2026-10-28\n- 저장 시점: 2026-10-28 12:00\n'
            '- 확인하지 못한 점: 보류한 제조사 항목의 적용 여부, HM-9.4 본문.\n')


def guide_md(title, practical, graph):
    run = ('python lab_db.py\npython show_result.py\npython check.py' if graph else 'python show_result.py\npython check.py')
    return (f'# {title} — 학생용 완성본\n\nZIP 전체를 실습 폴더와 다른 새 폴더에 풀고, 이 문서가 있는 폴더를 VS Code에서 연 뒤 터미널에서 아래 명령을 차례로 실행합니다.\n\n```\n{run}\n```\n\n'
            '`결과/`의 정할 자리 파일은 가이드의 「정답 보기」를 단계마다 따라 채운 판이고, 다른 파일은 결과 화면이 그 자리로 만든 것입니다. '
            + ('응답 기록은 강의에서 미리 받아 둔 수업 모델의 답이라, 다시 보내면 답이 달라질 수 있습니다 — 이 폴더에서는 정할 자리를 바꾸지 않으면 다시 보내지 않습니다. ' if not graph else
               'Docker Desktop이 켜져 있어야 랩 DB가 켜집니다. ')
            + '정할 자리를 바꾸면 결과가 달라집니다 — 그 선택과 근거는 `결과/정한_것.csv`에 있습니다.\n')


def zipped(root, folder):
    out = io_bytes = None
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for p in sorted(folder.rglob('*'), key=lambda x: x.relative_to(folder).as_posix().lower()):
            if p.is_file() and '__pycache__' not in p.parts:
                info = zipfile.ZipInfo(f'{root}/{p.relative_to(folder).as_posix()}', STAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, p.read_bytes())
    return buf.getvalue()


def build(key, tmp):
    graph = key in BD.GLABS
    practical = key in ('practical-03-extract', 'practical-03-card')
    src = (BD.GLABS if graph else BD.LABS)[key]
    snaps = []
    res, folder = RP.replay(key, tmp/'make', keep_db=graph, snaps=snaps)
    try:
        for i, n, s, log in res:
            if s not in ('채움', '볼 것 없음', '결과 보기'):
                fail(f'{key} {i:02d} {n}: {s}')
        if not graph:
            (folder/BD.REC).write_text(extract_record(folder, practical), encoding='utf-8', newline='\n')
        else:
            (folder/BD.GREC).write_text((card_record if practical else graph_record)(folder, snaps), encoding='utf-8', newline='\n')
            r = RP.run(folder, 'show_result.py', '--no-open')     # 마지막 단계의 check.py가 채운 기록을 보게
            if r.returncode:
                fail(f'{key}: 기록을 채운 뒤 show_result {r.returncode}\n{r.stdout[-1500:]}')
    finally:
        if graph:
            RP.drop_db(folder)
    for rel in DROP:
        (folder/rel).unlink(missing_ok=True)
    (folder/'완성본_안내.md').write_text(guide_md((BD.GTITLES if graph else BD.TITLES)[key], practical, graph), encoding='utf-8', newline='\n')
    name = f'{src.name}_학생용완성본'
    data = zipped(name, folder)
    out = src.parent.parent/'완성본'/f'{name}.zip'
    # 새 폴더에 풀어 키 없이 다시 실행 → 검사기 통과
    check = tmp/'check'
    if check.exists():
        shutil.rmtree(check)
    check.mkdir()
    import io
    zipfile.ZipFile(io.BytesIO(data)).extractall(check)
    f2 = check/name
    try:
        if graph:
            RP.run(f2, 'lab_db.py', '--no-open', check=True)
        r = RP.run(f2, 'show_result.py', '--no-open')
        c = RP.run(f2, 'check.py')
        if r.returncode or c.returncode:
            fail(f'{key}: 완성본 새 폴더에서 show_result {r.returncode} · check {c.returncode}\n{r.stdout[-1200:]}\n{c.stdout[-1500:]}')
        if not graph and any((f2/'결과/응답_기록').glob('*')) and len(list((f2/'결과/응답_기록').glob('*'))) != len(list((folder/'결과/응답_기록').glob('*'))):
            fail(f'{key}: 완성본 폴더에서 다시 실행하자 응답 기록 수가 바뀜(다시 보냄)')
    finally:
        if graph:
            RP.drop_db(f2)
    out.write_bytes(data)
    print(f'{out.name}: {len(data)} 바이트 · 새 폴더 키 없이 show_result {r.returncode} · check {c.returncode}')


def main(argv=None):
    keys = (argv if argv is not None else sys.argv[1:]) or sorted(BD.LABS) + sorted(BD.GLABS)
    for key in keys:
        with tempfile.TemporaryDirectory(prefix='doc_done_') as t:
            build(key, Path(t))
    print('불일치 0' if not BAD else f'불일치 {len(BAD)}')
    return 1 if BAD else 0


if __name__ == '__main__':
    sys.exit(main())
