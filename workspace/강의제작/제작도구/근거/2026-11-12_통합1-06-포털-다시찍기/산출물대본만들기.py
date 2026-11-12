# 확정 대본 · 큐 · 최종 자막으로 산출물 실습 대본(06_실습_전체과정관찰.md)을 만든다.
import json,re
R='/home/user/hyd-iot-edu/'
Q=json.load(open(R+'workspace/강의제작/제작도구/촬영/포털/전체과정관찰_다시찍기_큐.json'))['cues']
srt=open(R+'작업/촬영/포털/06-최종/06-최종.srt',encoding='utf-8').read().strip().split('\n\n')
times=[]
for b in srt:
    l=b.split('\n');m=re.match(r'(\d+):(\d+):(\d+),(\d+)',l[1]);times.append(int(m[1])*3600+int(m[2])*60+int(m[3])+int(m[4])/1000)
assert len(times)==len(Q)
src=open(R+'workspace/강의제작/제작도구/근거/2026-11-12_통합1-06-포털-다시찍기/06_전체과정관찰_다시찍을판.md',encoding='utf-8').read()
stages=dict(re.findall(r'\n### (\d+)\. ([^\n]*)',src[src.index('## 2. 새 대본 전문'):]))
TAB={'knowledge':'지식 관리','ontology':'지식 지도','scenario':'결함 시뮬레이션','instances':'처리 건','inbox':'내 작업함'}
def tg(t):
    if isinstance(t,str):
        k,v=t.split(':',1)
        return '왼쪽 메뉴 「%s」'%TAB.get(v,v) if k=='tab' else {'알림':'위 막대 알림 종'}.get(v,v)
    if 'text' in t: return '「%s」'%t['text']
    c=t['css'];c=re.sub(r'\s+',' ',c)
    if t.get('contains'): c+=' ∋「%s」'%t['contains']
    if 'nth' in t: c+=' #%d'%(t['nth']+1)
    return '`%s`'%c
def op(o):
    k=o[0]
    if k=='point':return '짚기 '+tg(o[1])
    if k=='click':return '누르기 '+tg(o[1])
    if k=='open':return '펼치기 '+tg(o[1])
    if k=='download':return '받기 '+tg(o[1])+' → `%s`'%o[2]
    if k=='file':return '파일 선택 '+tg(o[1])+' → `%s`'%o[2]
    if k=='selectwith':return '고르기 '+tg(o[1])+' → 「%s」'%' · '.join(o[2])
    if k=='select':return '고르기 '+tg(o[1])+' → 최운전 · 운전원'
    if k=='type':return '입력 「%s」'%o[1]
    if k=='phrase':return '원문 칸에서 짚기 「%s」'%o[1]
    if k=='stepmark':return '처리 과정 「%s」 짚기'%o[1]
    if k=='scroll':return '굴리기 '+tg(o[1])
    if k=='clickuntil':return '결과가 나올 때까지 다시 누름 '+tg(o[1])
    if k=='waittext':return '「%s」가 뜰 때까지 기다림'%o[1]
    if k in('wait','waitjs','settle'):return {'wait':'나타날 때까지 기다림','waitjs':'화면 상태가 될 때까지 기다림','settle':'화면이 멈출 때까지 기다림'}[k]
    return k
fm=lambda s:'%d:%04.1f'%(s//60,s%60)
out=["# 통합반 1회차 실습(포털) — 설비 이상 발생부터 판단·승인·조치까지 전체 과정 경험하기 · 20분","",
"두 과정 공통 영상 하나(Release 「영상」의 `int-01-06-lab.mp4`)의 대본이다. 2026-11-12 새 대본으로 처음부터 다시 찍었다(클라우드 Playwright, 구간 7개를 나눠 찍고 한 번에 찍은 것처럼 이음, 쉼은 이어지는 말 0.6초 · 큐 사이 1.3초 · 결과 뒤 2.0초 · 구간 사이 2.3초). 실라버스 두 시트 같은 행(실습(포털), 배정 20분).","",
"## 진행 메모 — 낭독하지 않음","",
"- 발화는 촬영 큐 [`전체과정관찰_다시찍기_큐.json`](../../../../../제작도구/촬영/포털/전체과정관찰_다시찍기_큐.json)의 글자 그대로이고, 시각은 최종 영상의 말 시작이다. 조작 칸의 짚기 · 누르기는 그 큐 말 안의 구절에서 일어난다(구절 시점은 큐 파일의 `at`).",
"- 시작 상태: 포털 홈, 「나 선택 안 함」, 처리 건 0, 기본 지식 세 문서(HM-8 · PM-02 · PR-07) 적재, 수업 흐름 배포, 서비스 13/13. AI 응답은 키 없는 수업과 같은 재생 모드로 찍었고, 재생 설명은 04 첫 포털 화면 몫이라 이 영상에는 없다.",
"- 되돌릴 수 없는 조작: 미리보기 · 추출 요청 · 적재 · 쿨러 열화 주입 · 「나」 고르기 · 승인. 운전원은 승인 바로 앞(12단계)에서 내 작업함의 「나」로 고르고, 승인은 처리 건 화면의 승인 요청에서 한다(내 작업함의 줄을 누르면 단계 자세히에 1순위 이름 · 점수가 먼저 뜨기 때문). 승인 전에는 추천안 이름을 말하지 않는다.",
"- 기다림 세 곳(적재 · 승인 뒤 · 재관측)은 같은 화면이 멈춘 가운데만 잘라 냈다(cut.py, 5.1 · 1.5 · 1.0 · 4.4초). 재관측 값 · 시각 · 명령 · 오더 번호는 실행마다 달라 낭독하지 않는다.",""]
cur=None
for c,t in zip(Q,times):
    st=int(c['id'][1:3])
    if st!=cur:
        cur=st;out+=["",f"## {st}. {stages[str(st)]}","","| 큐 | 시각 | 발화 | 조작·결과 확인 — 비낭독 |","|---|---|---|---|"]
    ops='<br>'.join(op(o) for o in c['ops']) or '—'
    out.append(f"| {c['id']} | {fm(t)} | {c['text']} | {ops} |")
out+=["","# 촬영 본문 끝",""]
# 제작 확인용: 작업 대본의 §5를 그대로 옮기되 실측 분을 붙인다
sec=src[src.index('## 5. 제작 확인용'):src.index('## 검토 지적 처리표')].replace('## 5. 제작 확인용(낭독하지 않음)','## 제작 확인용 — 낭독하지 않음')
out.append(sec.strip())
first={st:None for st in range(1,16)}
for c,t in zip(Q,times):
    st=int(c['id'][1:3]);first[st]=first[st] if first[st] is not None else t
end=times[-1]+20
def span(a,b): return (first[b+1] if b<15 else 1466.8)-first[a]
out+=["","단계별 실측(최종 영상 1466.8초, 24:26.8): "+' · '.join(f"{st}단계 {fm(first[st])}" for st in range(1,16))+".",
f"실라버스 문장별 실측: 지식 관리~적재(2~8단계) {span(2,8)/60:.1f}분, 지식 지도 · 고장 내기 · 처리 건(9~11단계) {span(9,11)/60:.1f}분, 승인~결과(12~15단계) {span(12,15)/60:.1f}분. 배정 20분보다 길어진 몫은 원문 · 지식을 맞춰 보는 풀이와 말 사이 쉼이다(영상 V-1)."]
open(R+'workspace/강의제작/산출물/통합반/실습/01회차/대본/06_실습_전체과정관찰.md','w',encoding='utf-8').write('\n'.join(out)+'\n')
print('ok',len(out))
