"""Synchronize static lesson materials and estimates; never operates an app."""
from pathlib import Path
import html, re, json, zipfile, hashlib
import build_scenario as scenario
from build_lesson import KEYS

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]

def render_markdown(md):
    """Render the limited headings/paragraphs/tables used by the authored script."""
    parts=[]; table=False
    for line in md.splitlines():
        if not line.strip():
            if table: parts.append('</tbody></table>');table=False
            continue
        if line.startswith('|'):
            if re.match(r'^\|[- |]+\|$',line):continue
            cells=line.strip('|').split('|')
            if not table:parts.append('<table><tbody>');table=True
            parts.append('<tr>'+''.join('<td>'+html.escape(c.strip())+'</td>' for c in cells)+'</tr>')
        else:
            if table:parts.append('</tbody></table>');table=False
            if line.startswith('#'):
                level=min(len(line)-len(line.lstrip('#')),4)
                parts.append(f'<h{level}>'+html.escape(line.lstrip('# '))+f'</h{level}>')
            elif line.startswith('>'):parts.append('<aside>'+html.escape(line.lstrip('> '))+'</aside>')
            elif line.startswith('- '):parts.append('<p class="note">'+html.escape(line[2:])+'</p>')
            else:parts.append('<p>'+html.escape(line)+'</p>')
    if table:parts.append('</tbody></table>')
    return '\n'.join(parts)

def estimate(script):
    body=script.split('# 촬영 본문 끝')[0].split('## 시작 — 빈 ARROWS 그림에서')[1]
    speech=[]
    for line in body.splitlines():
        if line.startswith('|'):
            if line.startswith(('| 먼저', '| 대상 안내부터')) or re.match(r'^\|[- |]+\|$',line):continue
            speech.append(line.split('|')[1].strip())
        elif line.strip() and not line.startswith(('#','>','-')):speech.append(line)
    spoken='\n'.join(speech)
    syllables=len(re.findall('[가-힣]',spoken))+1.6*len(re.findall('[0-9]',spoken))+.6*len(re.findall('[A-Za-z]',spoken))
    nprops=sum(len(n[3]) for n in scenario.N)
    strings=[c for i,k,c,t,s in scenario.N]+[k for i,k,c,t,s in scenario.N]+[v for n in scenario.N for v in n[3]]+[k for ks in KEYS for k in ks]+[t for a,b,t in scenario.E]
    chars=sum(map(len,strings));clicks=20*4+19+nprops*3+26*2+6
    # All ranges are planning assumptions, not recorded speed.
    checks=20+nprops+26
    low=(clicks*1.0+26*1.2+chars/7+20*.25+checks*.5)/60+4
    high=(clicks*1.7+26*2.2+chars/4+20*.5+checks*1.0)/60+9
    voice=syllables/275
    report=f'''# ARROWS 발화·조작량과 시간 산정 상태 — 2026-10-23

대상: 현재 `수업원고.md` 전체. **아래 합산은 종전 순차 진행의 참고 계산이며 현행 수업 예상 시간이 아니다.** 현재 기준은 대상 안내 후 설명 중 조작하는 시간의 합집합이다. 실제 행동 타임라인이 없어 현행 전체 시간은 미측정이다. 짧은 샘플의 재생 시간을 전체 수업에 외삽하지 않았다.

| 항목 | 계산 | 예상 |
|---|---|---|
| 발화 | 한글 음절 + 숫자×1.6 + 영문×0.6 = {syllables:.1f}, 분당275음절 | {voice:.1f}분 |
| 안내가 끝난 뒤 조작·화면 확인 | 아래 정상 속도 범위, 발화와 겹치지 않음 | {low:.1f}–{high:.1f}분 |
| 종전 순차 합산 참고 | 발화 + 조작·확인(중복 포함 가능) | **{voice+low:.1f}–{voice+high:.1f}분** |

조작 산정: 노드20개·관계26개·속성{nprops}개. 클릭 약{clicks}회에 이동 포함1.0–1.7초, 관계 드래그26회에1.2–2.2초, 입력{chars}문자를 초당4–7문자, 종류 확정 Enter20회에0.25–0.5초. 눈으로 결과를 확인하는{checks}지점에0.5–1초를 별도 반영했다. 배치 조정2–5분, 저장 데이터 재열기·원본 대조2–4분을 더했다. 고정 대기를 실제 조작에 넣으라는 뜻이 아니다. 시스템 대기·음성 합성·렌더링·프레임 지연·학생 작업 대기는 제외했다.

발화 계산에서는 제목·제작 메모·조작 열·출처를 제외했다. 표의 발화 열과 설명 문단만 포함한다. 실제 화면에서 중복 클릭을 생략하면 그 안내도 함께 줄어든다. 아직 확인하지 않은 가져오기 경로의 구체적인 안내와 전체 배치 조정에 따라 범위가 달라질 수 있다. 이 계산은 중첩 시간을 빼지 않은 구판 방식이다. 현행 계획 시간에는 실제로 겹치지 않는 입력·응답·확인 시간만 더해야 한다.

이전 전체 원고는 후반 조작 안내가 비낭독 메모에 있었으므로 그 낭독 길이를 완결된 수업의 종전 시간으로 비교하지 않는다. 이번 값은 누락 안내를 채운 원고의 양을 확인하는 참고치다. 순차 진행을 촬영 지시로 사용하지 않는다. 50분에 맞추려고 지연·설명·노드를 추가하지 않는다. 촬영·전체 음성·실측은 미수행이다.
'''
    (ROOT/'예상시간.md').write_text(report,encoding='utf8')
    return report

def main():
    scenario.write_docs()
    script=(ROOT/'수업원고.md').read_text(encoding='utf8')
    timing=estimate(script)
    node_md='# 사건 S-01 — 입력할 대상과 속성\n\n판단→선택→조건·승인→응답→회복→정비→생산·품질 후속 확인을 연결한다. 아래는 작성할 참조 명세이며 직접 작성한 결과와 구별한다.\n\n|ID|종류|이름|속성 이름: 값|\n|---|---|---|---|\n'
    for ix,(nid,kind,caption,details,s) in enumerate(scenario.N):
        node_md+=f'|{nid}|{kind}|{caption}|'+ ' / '.join(f'{k}: {v}' for k,v in zip(KEYS[ix],details))+'|\n'
    node_md+='\n## 관계 명세\n\n|출발|관계 이름|도착|\n|---|---|---|\n'
    node_md+=''.join(f'|{a}|{t}|{b}|\n' for a,b,t in scenario.E)
    node_md+='\n## 입력 자료의 성격\n\n기존 기술사실표·HM-8에 근거한 사례 기록이다. 승인 이후 결과는 시나리오의 제공 기록이며 새 설비 실행 실적이 아니다. 관측·예측·시나리오 기록을 섞지 않는다. 상세 출처는 제작 원고의 비낭독 출처에 있다.\n'
    review='''# 관계 검토표 — 판단부터 후속 확인까지

| 출발 | 관계 이름 | 도착 | 문장으로 읽은 뜻 | 입력·매뉴얼 근거 | 수정할 부분 |
|---|---|---|---|---|---|
| | | | | | |

## 끝까지 확인할 조건

- CE 30초 평균46.2%, VS1 2분 평균0.575mm/s, TS4 2분 평균28℃로 핀 오염 조건과 다른 원인을 대조했는가.
- 남은5.98시간·출하 대기800개를 조치 비교에 연결했는가. 예측과 실제 결과를 구별했는가.
- REMOTE_AUTO·팬100% 연속24시간 이내·대안 부하60% 이상, 운전원 승인이 실행 앞에 있는가.
- 명령/응답과 TS1<55℃·경보 해제15분 유지가 구별되는가.
- 정비 일정·담당·승인, 작업 기록, 재가동CE≥80%, 생산·품질 확인이 종료 근거로 이어지는가.
- 자료·승인 부족은 보류로, 실패·회복 미달은 재검토로 돌아가는가. 원인이 다를 때 조치도 바뀌는가.

## 저장 확인 — 실제 수행 후 기록

편집 데이터 파일명 / PNG 파일명 / 재열기 결과 / 노드·관계·속성 대조 / 누락과 수정 / 남은 질문:

실제 재열기를 하지 않았다면 미확인으로 둔다. 다음 관계모형·스키마 설계에서 이 그림과 검토 근거를 이어 쓴다. 사건의 진행 관계를 원인→고장의 지식 관계와 같은 뜻으로 바꾸지 않는다.
'''
    screens='''# 후속 화면 확인 계획 — 현재 미촬영

|장면|보여 줄 대상|확인할 결과|
|---|---|---|
|시작·첫 대상|빈 캔버스, 오른쪽 Add Node·Caption·Label|대상 이름과 종류 반영|
|속성|Property 추가, 왼쪽 키·오른쪽 값|입력한 항목과 값|
|연결|원 바깥 고리→다른 원, Type|출발·도착·관계 이름|
|판단·비교|N03–N09|원인 근거·생산·품질·예측·실행 조건|
|승인·확인|N10–N17|응답≠회복, 정비·업무 후속|
|예외|N18–N20|보류·미달·다른 원인|
|저장|Download / Export, JSON・PNG|파일 생성·가독성|
|재열기|실제 가져오기 메뉴·파일 선택 경로 확인 필요|20노드26관계와 모든 속성 복원|

이번에는 촬영·브라우저 조작·음성 생성을 하지 않았다. 사진은 후속 허용 단계에서 실제 화면으로 채운다. 원고의 가져오기 경로 미확인 표시를 확인 없이 제거하지 않는다.
'''
    record='''# 실습 기록 — 사건 S-01 관계그림

- 입력·판본:
- 원인 판단과 근거:
- 조치 선택과 생산·품질 영향:
- 실행 조건·승인:
- 명령 응답과 회복 확인의 구별:
- 정비·생산·품질 후속 확인:
- 보류·재검토 조건:
- 그림 수정과 이유:
- 편집 파일·PNG·재열기 확인:
- 실제 수행 범위와 미확인:
'''
    for course in ['실전반','통합반']:
        day=REPO/'산출물'/course/'실습/01회차';lab=day/'랩/01일차_실습4_관계그림'
        final=script.replace('../../../문서/','../../../../../문서/')
        (day/'대본/08_실습_관계그림.md').write_text(final,encoding='utf8')
        local_timing=timing.replace('현재 `수업원고.md` 전체','현재 [전체 대본](../../대본/08_실습_관계그림.md)')
        for name,content in [('대상_목록.md',node_md),('관계_검토표.md',review),('채울_화면.md',screens),('실습_기록.md',record),('예상시간.md',local_timing)]:
            (lab/name).write_text(content,encoding='utf8')
        # Add the missing recovery clause without changing prior source excerpts.
        manual=lab/'매뉴얼_발췌.md';m=manual.read_text(encoding='utf8')
        if '## HM-8.6 회복 판정' not in m:
            full=(REPO/'산출물/실전반/실습/01회차/랩/01일차_실습4_관계그림/참고_HM-8_매뉴얼.md').read_text(encoding='utf8')
            recovery='## HM-8.6 회복 판정'+full.split('## HM-8.6 회복 판정')[1].split('## HM-8.7')[0]
            m=m.replace('## HM-8.7 근본 조치',recovery+'## HM-8.7 근본 조치').replace('1·4·5·7절','1·4·5·6·7절')
            manual.write_text(m,encoding='utf8')
        guide='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ARROWS — 판단과 조치의 관계그림</title><style>body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:1120px;margin:36px auto;padding:0 24px;color:#22303e}table{width:100%;border-collapse:collapse;table-layout:fixed;margin:20px 0}td{border:1px solid #cbd5e1;padding:10px;vertical-align:top;overflow-wrap:anywhere}h2{margin-top:40px}aside,.note{background:#f0f4f7;padding:12px}a{color:#145ca4}</style></head><body>
<h1>납기가 가까운 냉각설비 이상 대응</h1><p>원인 근거를 보고 조치를 선택한 뒤, 조건과 승인·실제 효과·정비·생산과 출하 확인까지 한 그림으로 연결합니다.</p>
<p>온라인 제작 참고용입니다. 아래 왼쪽 안내로 대상과 행동을 먼저 알리고, 설명하면서 오른쪽 조작을 수행한 뒤 결과를 확인합니다. 익숙한 기능은 짧게 안내하되 필수 입력과 과정은 생략하지 않습니다.</p>
<nav><a href="대상_목록.md">대상·속성·관계 입력</a> · <a href="매뉴얼_발췌.md">판단과 회복 기준</a> · <a href="관계_검토표.md">결과 검토</a> · <a href="예상시간.md">예상 시간</a> · <a href="채울_화면.md">미촬영 화면 계획</a> · <a href="실습_기록.md">기록</a></nav>
'''
        guide+=render_markdown(final.split('## 진행 메모 — 낭독하지 않음')[1].split('# 촬영 본문 끝')[0])
        guide+='<aside>정적 준비판입니다. 새 그림·가져오기 경로와 전체 배치·재열기는 미확인입니다. 촬영·음성·실행은 수행하지 않았습니다. 기존 교재 발췌의 두 원인 비교는 원문 참고 자료로 보존하며, 이번 작성 순서는 이 가이드와 대상 목록을 따릅니다.</aside></body></html>'
        (lab/'가이드.html').write_text(guide,encoding='utf8')
        zip_path=lab.with_suffix('.zip')
        with zipfile.ZipFile(zip_path) as old:
            first=old.namelist()[0];prefix=first.split(lab.name+'/')[0]+lab.name+'/'
        with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
            for f in sorted(lab.rglob('*')):
                if f.is_file():z.write(f,prefix+f.relative_to(lab).as_posix())
        with zipfile.ZipFile(zip_path) as z:
            for f in lab.rglob('*'):
                if f.is_file():assert z.read(prefix+f.relative_to(lab).as_posix())==f.read_bytes()
        for href in re.findall('href="([^"]+)"',guide):assert (lab/href).is_file(),href
    print(timing.split('조작 산정:')[0])

if __name__=='__main__':main()
