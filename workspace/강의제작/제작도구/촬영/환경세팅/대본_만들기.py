"""1회차 실습 04 대본(두 과정 공통)을 실제 영상의 큐(실행환경_촬영큐.json)에서 만든다.
영상은 설치 → 시작 명령 → 포털 주소를 Ctrl을 누른 채 클릭하는 데서 끝난다. 포털 둘러보기는 06 「전체 과정 관찰」이 맡는다(사용자 2026-11-14).
사용: python 대본_만들기.py  (저장소 루트에서)"""
import json
from pathlib import Path

ROOT = Path('workspace/강의제작')
Q = json.loads((ROOT / '제작도구/촬영/환경세팅/실행환경_촬영큐.json').read_text(encoding='utf-8'))


def table(rows):
    return ['| 큐 | 발화 | 조작·결과 확인 — 비낭독 |', '|---|---|---|'] + [f'| {i} | {t} | {a} |' for i, t, a in rows]


L = ['# [실습] 실습 환경을 설치하고 시작하기 · 30분', '', '통합반·실전반 온라인 1회차 공통.', '']
seen = []
for c in Q['cues']:
    if c['segment'] not in seen: seen.append(c['segment'])
for s in seen:
    L += [f'## {s}', ''] + table([(c['id'], c['text'], c['action_observation']) for c in Q['cues'] if c['segment'] == s]) + ['']
L += ['# 촬영 본문 끝', '']
text = '\n'.join(L)
for course in ['통합반', '실전반']:
    (ROOT / f'산출물/{course}/실습/01회차/대본/04_실습_실행환경.md').write_bytes(text.encode('utf-8'))
print('큐', len(Q['cues']), '글자', len(text))
