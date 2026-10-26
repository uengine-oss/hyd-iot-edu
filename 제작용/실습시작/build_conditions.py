"""실전반 온라인2 조건표: 원자료 보존, 빈 결과 틀과 학생용 안내만 제공."""
from build_labs import ROOT,OUT,page,write,dump,pack,RULES
from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent
folder=OUT/'실전반/실습/02회차/랩/02일차_실습5_조치조건표'
rules=RULES.replace('입력/와 자료/는 보존한다.','작업기준.md, HM-8_매뉴얼.md, 규칙_원문.txt, 사례_입력.csv와 입력틀은 보존한다.')
for filename in ['AGENTS.md','CLAUDE.md','.github/copilot-instructions.md']:write(folder/filename,rules)
write(folder/'START.md','''# 작업 기준을 조건표로 옮기기

팬 최대 운전 후보의 경고·감점·제외 조건을 표로 정리하고, 사례별 판단의 근거를 확인합니다.

## 이번 작업

1. 작업기준.md, HM-8_매뉴얼.md, 규칙_원문.txt의 적용 범위를 읽습니다.
2. AI에 사용할 자료, 만들 결과, 추가하면 안 되는 조건, 확인할 사례를 자기 말로 전달합니다.
3. 조건표_입력틀.csv를 참고해 결과/조건표.csv를 작성합니다. 비교 하나를 한 행에 적고 같은 규칙의 비교는 묶습니다.
4. 사례_입력.csv의 A~I를 대입하고 결과/판단기록.md에 일치 규칙·사유·미확인을 기록합니다.

## 확인

- 원문의 경계값을 포함하는지 구별합니다. 경고·감점·제외를 같은 결과로 합치지 않습니다.
- 여러 규칙이 맞으면 사유를 모두 남기고, 같은 규칙의 감점을 중복해서 더하지 않습니다.
- 빠진 입력을 정상값으로 처리하지 않습니다. 알려진 제외 사유와 미확인은 함께 기록할 수 있습니다.
- 표의 각 조건에서 원문 근거로 돌아갈 수 있어야 합니다.
- 후보 유지와 작업 실행 승인을 구별합니다. 실제 설비나 평가 함수는 실행하지 않습니다.

## 저장

결과 파일을 다시 열고, 보관할 파일은 재부팅 전에 USB 또는 개인 클라우드로 복사합니다.
''')
write(folder/'결과/README.md','조건표.csv와 판단기록.md를 여기에 작성합니다.\n')
sections=[('자료 읽기','<p>작업기준.md와 HM-8_매뉴얼.md를 읽고, 규칙_원문.txt의 적용 대상과 출처를 확인하세요.</p><p>대상은 팬 최대 운전 후보입니다. 예측값과 현재 측정값을 구별합니다.</p>'),('조건표 만들기','<p>AI에 목표·자료·제약·확인 사례를 전달하세요. 조건표_입력틀.csv의 열을 참고해 결과/조건표.csv를 만듭니다.</p><p>입력, 연산자, 기준값, 단위, 결과, 원문 근거를 나누세요. 여러 비교가 한 규칙을 이루면 같은 규칙 번호로 묶습니다.</p>'),('사례 대조하기','<p>사례_입력.csv의 A~I를 조건표에 대입하고, 판단기록_입력틀.md를 참고해 결과/판단기록.md를 작성하세요.</p><p class="check">경계값 바로 아래·같은 값·바로 위에서 판단이 원문과 맞는지 확인합니다. 여러 사유는 모두 남기며 감점은 규칙당 한 번만 반영합니다.</p><p>입력이 없는 규칙은 미확인으로 남깁니다. 알려진 제외 사유와 미확인을 함께 적고, 제외 사유가 없더라도 필요한 입력이 없으면 최종 판단을 보류합니다.</p>'),('저장하고 다시 읽기','<p>조건표의 각 행에서 원문 절을 찾을 수 있는지 확인하세요. 조건표.csv와 판단기록.md를 저장하고 다시 엽니다.</p><p>후보 유지는 실행 승인이 아닙니다. 이번 실습에서는 표와 기록만 작성합니다.</p><p>보관할 결과는 USB 또는 개인 클라우드에 복사하세요.</p>')]
for filename in ['guide.html','안내.html']:write(folder/filename,page('조치 조건과 판단 근거 정리하기','원문 조건을 표로 옮기고, 경계값·겹치는 조건·누락 입력을 사례로 확인합니다.',sections))
archive=pack(folder)
catalog=json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))
catalog['labs']=[x for x in catalog['labs'] if x['id']!='practical-02-conditions']
catalog['labs'].append({'id':'practical-02-conditions','course':'실전반','session':'온라인 02회차','title':'조치 조건과 판단 근거 정리하기','version':'2026-10-26-conditions-v1','folder':'02회차/랩/'+folder.name,'path':archive.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
dump(HERE/'package-index.json',catalog)
print('실전반 조건표 가이드·독립 ZIP·목록 동기화')
