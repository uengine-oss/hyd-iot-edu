"""1회차 실습 04 대본(두 과정 공통)을 실제 영상의 큐에서 만든다. 앞부분(설치 → 포털 주소 Ctrl 클릭)은 실행환경_촬영큐.json,
포털 둘러보기는 ../포털/통합_01_04_포털둘러보기_큐.json(확정 대본에서 큐만들기가 만든 것)이다.
사용: python 대본_만들기.py  (저장소 루트에서)"""
import json
from pathlib import Path

ROOT = Path('workspace/강의제작')
Q = json.loads((ROOT / '제작도구/촬영/환경세팅/실행환경_촬영큐.json').read_text(encoding='utf-8'))
P = json.loads((ROOT / '제작도구/촬영/포털/통합_01_04_포털둘러보기_큐.json').read_text(encoding='utf-8'))
SEG = {1: '포털 둘러보기 — 첫 화면과 재생 모드', 2: '포털 둘러보기 — 홈의 위 네 칸과 맨 위 막대', 3: '포털 둘러보기 — 연결 그림과 둘러볼 차례',
       4: '포털 둘러보기 — 설비 메뉴', 5: '포털 둘러보기 — 지식 메뉴', 6: '포털 둘러보기 — 인공지능 설정 메뉴', 7: '포털 둘러보기 — 판단 메뉴',
       8: '포털 둘러보기 — 작업 메뉴', 9: '포털 둘러보기 — 성과 · 시스템 메뉴', 10: '포털 둘러보기 — 홈으로 돌아와 맺음'}
TAB = {'inbox': '내 작업함', 'instances': '처리 건', 'scenario': '결함 시뮬레이션', 'oil': '오일 분석 입력', 'incidents': '이상 확인 · 조치', 'trends': '실시간 모니터링',
       'decision': '조치 판단 규칙', 'whatif': '조건별 손익', 'process': '승인과 실행', 'flows': '흐름 가져오기', 'ontology': '지식 지도', 'skills': '조치 방법', 'knowledge': '지식 관리',
       'fabric': '데이터 연결', 'ask': '에이전트에게 질문', 'agents': '에이전트', 'mcp': '도구 연결', 'compare': '시험 비교', 'eval': '판단 채점', 'kpi': '성과 지표', 'main': '홈', 'home': '시스템 구성', 'admin': '관리'}
# 글로 찾지 않는(선택자만 있는) 대상의 이름 — 녹화 화면에서 확인한 것
CSS = {'#openCount': '맨 위 막대의 진행 중 사건', '#courseStatus': '맨 위 막대의 「지금 단계」', '#healthDots': '맨 위 막대의 서비스 수', '#shellMe': '맨 위 막대의 「나」', '#shellBell': '알림 종',
       '#view-main svg.m-hero-svg': '홈의 연결 그림', '#view-scenario span.v': '설비 칸의 숫자', '#view-scenario .threshold-note': '숫자 밑 기준 막대',
       '#view-scenario span.chip.tone-success': '설비 상태 표시', '#pTs1': '유온 그래프', '#view-skills span.sub': '조치 방법 줄의 괄호',
       '#view-ask textarea': '질문 칸', '#view-ask button.btn.small': '저장된 질문 단추', '#view-mcp span.chip.tone-success': '연결 상태 표시',
       '#decRun': '「판단 실행」 단추', 'select[data-inbox-me]': '「나」를 고르는 칸', '#view-inbox p.field-hint': '고르는 칸 밑 안내 글',
       '#view-home span.role-desc': '역할 설명', '#view-home .dot': '상태 점', 'nav.page-navigation button.next': '화면 아래 「다음」'}


def name(t):
    css = t['css']
    if css.startswith('.rail nav button[data-tab='):
        k = css.split('"')[1]
        if k not in TAB: raise SystemExit(f'포털 둘러보기 큐: 메뉴 이름 없음 {css}')
        return f'왼쪽 메뉴 「{TAB[k]}」'
    if css == '.rail .navgroup': return f'왼쪽 메뉴 제목 「{t["exact"]}」'
    if t.get('exact') or t.get('contains'): return f'「{t.get("exact") or t.get("contains")}」'
    if css not in CSS: raise SystemExit(f'포털 둘러보기 큐: 이름 없는 대상 {css}')
    return CSS[css]


def ops(c):
    out = []
    for o in c.get('ops', []):
        if o[0] == 'click': out.append(name(o[1]) + ' 클릭')
        elif o[0] == 'point': out.append(name(o[1]) + ' 가리키기')
        elif o[0] == 'scroll': out.append(name(o[1]) + '까지 내림')
        elif o[0] == 'wait': out.append(name(o[1]) + '이 뜰 때까지 기다림')
        else: raise SystemExit(f'포털 둘러보기 큐 {c["id"]}: 모르는 조작 {o[0]}')
    return ' → '.join(out) or '화면을 그대로 둔 채 설명'


def table(rows):
    return ['| 큐 | 발화 | 조작·결과 확인 — 비낭독 |', '|---|---|---|'] + [f'| {i} | {t} | {a} |' for i, t, a in rows]


L = ['# [실습] 실습 환경을 시작하고 HYD 포털 둘러보기 · 30분', '', '통합반·실전반 온라인 1회차 공통.', '']
seen = []
for c in Q['cues']:
    if c['segment'] not in seen: seen.append(c['segment'])
for s in seen:
    L += [f'## {s}', ''] + table([(c['id'], c['text'], c['action_observation']) for c in Q['cues'] if c['segment'] == s]) + ['']
for s, title in SEG.items():
    L += [f'## {title}', ''] + table([(c['id'], c['text'], ops(c)) for c in P['cues'] if c['segment'] == s]) + ['']
L += ['# 촬영 본문 끝', '']
text = '\n'.join(L)
for course in ['통합반', '실전반']:
    (ROOT / f'산출물/{course}/실습/01회차/대본/04_실습_실행환경.md').write_bytes(text.encode('utf-8'))
print('큐', len(Q['cues']) + len(P['cues']), '글자', len(text))
