export const meta = {
  name: 'luna-rehearsal-doc',
  description: 'Student-path rehearsal with luna (Codex + course relay coding) for the four document-knowledge lab ZIPs; stand-in follows the guide, pastes the three .env lines via helper, uses the lab DB on Docker',
  phases: [{ title: 'Rehearse', detail: 'one student stand-in per lab drives luna through every guide step' }],
}
const S = '/tmp/claude-0/-home-user-hyd-iot-edu/476059fc-242d-55b3-911f-45e453197017/scratchpad/rehearse'
const W = '/home/user/hyd-iot-edu/작업/2026-11-03_코딩랩개편'
const REF = '/home/user/hyd-iot-edu/workspace/강의제작/제작도구/실습시작/reference/session3_docs'
const labs = args
phase('Rehearse')
const results = await parallel(labs.map(L => () => agent(`서브에이전트 생성 금지. 저장소 /home/user/hyd-iot-edu 의 어떤 파일도 고치지 않는다(쓰는 것은 ${S}/${L.tag}/ 아래와 기록 파일 ${W}/리허설_${L.tag}.md 뿐). 커밋 · push 금지.

## 너의 역할: 코딩을 모르는 노베이스 학생 대역(지시를 잘 따르는 성실한 학생)
학생이 받는 ZIP 하나로, 가이드(guide.html)만 보고 처음부터 끝까지 실습한다. 학생 AI는 루나(Codex CLI + 강의 중계 모델 coding)이고, 루나에게는 반드시 아래 스크립트로만 말한다:
\`${S}/luna_turn.sh <실습 폴더> <프롬프트 파일> new\` (첫 턴), 이후 \`… resume\`. 출력이 루나의 답이다. 프롬프트는 파일에 써서 넘긴다.

준비: \`mkdir -p ${S}/${L.tag}\` 뒤 ZIP \`${L.zip}\`을 \`${S}/${L.tag}/lab\`에 푼다(ZIP 안 맨 위 경로 \`${L.prefix}\`를 벗겨 lab/ 바로 아래가 랩 루트가 되게, python3 -I zipfile). 이미 있으면 멈추고 보고.
읽어도 되는 것: 그 lab/ 폴더 안의 파일만(START.md · guide.html — 텍스트로 뽑아 읽어도 됨 · 자료/ · 입력/ · 결과/ · 코드). **저장소의 강사 참조 · 완성본 · 생성기 · 구성안 · 지침은 리허설이 끝나기 전에는 열지 않는다**(학생은 못 본다).

키(어기면 즉시 멈춤): 가이드가 「.env.example을 복사한 .env에 받은 접속 세 줄을 붙여 넣는다」고 하는 단계에서는, 복사 · 이름 바꾸기는 가이드대로 직접 하고, 세 줄 붙여 넣기만 \`${S}/make_env.sh <lab 폴더>\`로 대신한다(키 파일 위치를 알 필요 없음, 값은 출력되지 않는다). .env 내용을 cat · 출력 · 루나에게 보내기 금지 — 루나에게도 「.env를 열어 보라」고 하지 않는다. 기록 파일에 키 · 주소를 쓰지 않는다. 끝나면 lab/.env를 지운다.

진행 규칙(학생처럼):
- 가이드 단계를 1번부터 순서대로. 단계마다 그 절의 「할 일 · 정하거나 물을 것 · 요청에 담을 것(다섯 요소 힌트) · 명령 · 판단할 증거」를 읽고, **힌트의 값은 원자료에서 내가 찾아** 내 말로 요청을 짠다(가이드 문장을 통째 붙여 넣지 않는다). AI 화면이 아닌 일(탐색기 확인 · 터미널 명령)은 네가 직접 한다(터미널 명령은 lab/에서 Bash로, 가이드의 명령 그대로).
- 루나 답을 원자료 · 실행 결과와 대조해 판단할 증거를 확인한다. 틀리면 고쳐 달라고 다시 요청한다(학생답게 구체적으로). 루나가 추천 · 권장을 붙이거나 결정을 대신하려 하면 따르지 않고 원문을 열어 내 선택과 근거를 말한다.
- 「학생이 정할 것」 지점에서는 근거(파일 · 줄)를 찾아 직접 정하고, 그 선택으로 바뀌는 답을 적는다. 못 정하면 미결로.
- 막히면(가이드만으로 다음에 뭘 할지 모름, 루나가 엉뚱함, 명령 실패) 그 사실과 어떻게 풀었는지를 그대로 적는다 — 가이드에 없는 지식으로 몰래 메우지 않는다.
- 랩 코드가 모델을 부르는 단계(추출 랩): 학생 코드가 실제로 강의 중계를 부른다 — 보낸 수 · 응답 기록 수 · 걸린 시간을 적는다. 첫 응답은 1분쯤 걸릴 수 있다(콜드스타트 — 실패로 보지 말고 기다린다).
- Docker가 필요한 단계(lab_db.py, 그래프 랩): 메인이 dockerd를 미리 켜 둔다 — \`docker info\`가 안 되면 dockerd를 직접 켜지 말고 그 사실을 적고 그 단계를 막힘으로 남긴다. 끝나면 이 랩 폴더가 만든 컨테이너(lab/랩_연결.json의 이름)만 지운다. dockerd는 끄지 않는다(다른 리허설이 쓴다).
- 각 단계 시작 · 끝에 \`date +%T\`를 남겨 단계별 걸린 시간을 잰다(루나 대기 · 학생 코드의 모델 대기 포함, 구분해 적음).
- 비용 상한: 루나 턴 45회. 넘으면 멈추고 보고.

끝난 뒤(이제 강사 쪽을 봐도 된다): ${REF}/사건_갈래표.md 와 ${REF}/갈래/ 중 ${L.ref} 를 읽고 내 결과와 견준다 — 같은 갈래인지, 다르면 내 근거가 성립하는지.

기록 파일 ${W}/리허설_${L.tag}.md (한국어, 쉬운 말): 랩 이름 · ZIP SHA-256 앞 10자 · 판 · 시작/끝 시각, 단계별 표(단계 · 보낸 요청 요약 · 루나 답 요약 · 바뀐 파일 · 내가 확인한 증거 · 걸린 분 · 막힘/우회), 「학생이 정할 것」별 내 선택 · 근거 줄 · 바뀐 답, 루나가 추천하거나 대신 정하려 한 순간, 가이드만으로 부족했던 곳(절 · 문장 · 고칠 방향), 강사 참조와의 대조, 루나 턴 수 · 토큰 합, 학생 코드의 모델 호출 수(추출 랩), 완료 판정(START 「완료 판정」 기준 · check.py 결과).
마지막 답(한국어): 완료 여부, 총 걸린 분, 막힘 목록(가이드 고칠 곳), 판단 지점에서 실제로 판단이 생겼는지, 강사 참조와 대조 결과.`, { label: `rehearse-${L.tag}`, phase: 'Rehearse' })))
return results
