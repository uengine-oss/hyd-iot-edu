"""전체 재독 후 대본과 가이드의 문서 정합성만 검사한다."""
from pathlib import Path
import re, json, ast

ROOT=Path(__file__).resolve().parents[4]
S=ROOT/'산출물/교재/대본/실전반_온라인/01회차'
reports=[]
for p in sorted(S.glob('*_실습_*.md')):
    text=p.read_text('utf-8')
    speech='\n'.join(line for line in text.splitlines() if not line.startswith(('#','>')))
    assert not re.search(r'영상|스크립트|후속 촬영',speech),(p.name,'발화 제작 용어')
    assert '다운로드' in text or '내려받' in text
    assert 'VS Code' in text and '폴더 열기' in text
    assert not re.search(r'답변을 기다리|학생이 답|여러분이 조작',speech),p.name
    assert len(re.findall(r'\[화면 ',text))>=6
    reports.append({'file':p.name,'speech_chars':len(speech),'start_from_download':True,'live_practice_executed':False})
for p in (ROOT/'산출물/실습/실전반_온라인/01일차_실습3_기록추적/시작코드').glob('*.py'):
    ast.parse(p.read_text('utf-8'))
(ROOT/'.evidence/practical01/final-readthrough-check.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
print('4 practice scripts: download, solo delivery and no production language in speech checked')
