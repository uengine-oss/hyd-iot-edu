# 3차 작업자 보고 AB — 점검의 흠 두 곳(강의 중계 길 · AI 보류 까닭)

## 지금 단계 · 남은 일
- 지금: 이어서 고치는 중(감독 의뢰 2차) — 7절의 셋(관문 연결 실패 까닭 · 점검 정리 · 승인 전 끝남)을 고치고, 시작 직후 보류 문장(관측 공백 구분)을 판정한다. 1차 판은 portal-ux `8b8f34f9`
- 남은 일: ① 관문 인증서 실패 까닭 · 문장 한 곳 · 로그 → ② cleanup 을 attention 으로 → ③ 승인 전 끝남 바로 알림 → ④ 관측 공백 구분 판정(재생 · 서명 묶음 · 정답표 · 교재 숫자에 닿는지) → 시험 · 되돌림 → 커밋 → process(바뀌면 다른 서비스도) 다시 짓기 → 재생 check_all → 9절 쓰기
- 고친 곳: `/home/user/portal-ux`(브랜치 portal-ux, 시작 머리 31a98098 → 커밋 8b8f34f9). `/home/user/main` 은 8b8f34f9 에 detach, process 만 다시 지음

## 1. 가려낸 원인(실측 근거)

### 흠 ② 「관측 공백」 — 결함이 아니라 시작 직후라 판단 기간만큼 기록이 아직 없었다
- 보류 사건(업무 DB `events`, 처리 건 `c3_cooling.1b5416da…`, 04:48:46, todo `ecbb19a9…`): 까닭 「팬 진동과 캐비닛 온도 기록에 관측 공백이 있어 …」. 근거 3개가 `OBSERVATION_GAP` — VS1 창 120초 · 표본 96 · 최대 빈틈 24.55초(한도 3초), TS4 창 120초 · 표본 18 · 빈틈 31.5초(한도 12초). CE 창 30초는 덮임. 판단 도구(dmn-mcp `diagnose`)의 `freshness.ingest` 는 ot_bridge 두 다리 모두 연결, 버림 0.
- 시계열 DB(`tag_1s`)의 맨 첫 표본은 04:46:58.136 — 수집 중계(connect-ingest) 컨테이너 시작 04:46:56.7 직후(plant-sim · ot-bridge 는 04:46:07~08 시작, 그 사이 값은 받을 곳이 없어 남지 않음). 근거 조회 시각 ≈ 04:48:33.6 이면 창 시작이 04:46:33.6 → 첫 VS1 표본까지 24.55초, 첫 TS4(04:47:05.137)까지 31.5초 — 보고된 빈틈과 소수점까지 같다. 빈틈은 「기록이 시작되기 전」 한 곳뿐이다.
- 그 뒤 45분 동안 설비 3대 × 신호 19개 모두 최대 간격 = 보고 주기(1초 신호 1.05초 · 10초 하트비트 11.0초 · 30초 신호 31.0초). 공장 쪽 다리(`ot/bridge/`)가 빠뜨리는 신호는 없고, 그동안의 점검 · 수업 한 바퀴의 설비 초기화에도 빈틈이 없었다. **수집 길의 결함 아님.**
- AI가 판단에 쓰는 기간: 코드에 고정값이 없고 지식 그래프의 `Evidence.windowSeconds`(1~3600초, 문서 등록이 정함)다. 지금 HYD-01 쿨러 원인 근거 120 · 120 · 120 · 30초. 판정은 `it/agent/agentsvc/tools/mcp_tsdb.py` `observation_coverage`(한도 = 보고 주기 + 2초) — 창의 모든 순간이 한도 안에 표본을 가져야 한다.

### 흠 ② 점검 문장 — 점검이 까닭을 짐작했다(그리고 실패는 아예 못 봤다)
- `check_stack.py` 옛 223줄은 보류 사건이 있으면 까닭과 상관없이 「기본 지식이 없는 것 같습니다」.
- 같은 함수의 실패 갈래(`status in ('FAILED','ERROR','CANCELLED')`)는 서버에 없는 값이었다 — AI 실행 실패는 `status='IN_PROGRESS' and draft_status='FAILED'`(`procdb.py` 433줄, `instances.py` `stuck`). 그래서 실패하면 7분을 기다린 뒤 「AI 판단 결과에 닿지 않았습니다」만 냈다. 옛 시험(`view(('T_agent','FAILED',…))`)이 서버에 없는 모양을 정답으로 지키고 있었다.

### 흠 ① 강의 중계 확인 — 다른 클라이언트로 쟀다
- 실제 process 이미지(`hyd-iot-edu-process`)에서 재 봄(키 없이, 가짜 키 `not-a-key` 로 GET /v1/models 한 번 — 비용 없음):
  - VM 인증서 덮어쓰기 없는 컨테이너(환경 `SSL_CERT_FILE` 만 VM 인증서를 믿음): 옛 확인(urllib) → `401`(= TLS 통과, 진짜 키면 「연결됨」), 새 확인 → `tls` 「강의 중계의 보안 인증서를 확인하지 못해 …」. 관문은 같은 컨테이너에서 certifi 만 믿어 실패하므로 새 확인이 관문과 같다.
  - 떠 있는 process(덮어쓰기로 certifi 자리에 VM 인증서): 새 확인 → `401`(닿음) — 관문도 닿는 환경.

## 2. 바꾼 파일 : 줄(커밋 8b8f34f9)
- `it/process/procsvc/course_model.py` 66줄 `relay_client(timeout)` 새로 — 강의 중계로 나가는 클라이언트 한 곳(`httpx.AsyncClient(timeout, follow_redirects=False, trust_env=False)` 그대로 옮김). 291줄 관문 forward 가 이것을 씀(설정 바뀜 없음, `mount` 안의 `import httpx` 지움).
- `scripts/relay_probe.py` — urllib 대신 `relay_client` 로 묻는다(26줄 가져오기, 64줄 `ask`). 인증서 확인 실패는 원인 사슬에서 `ssl.SSLCertVerificationError` 를 찾아(55줄 `certificate_refused`) 다시 묻지 않고 `tls` + 학생 문장(37줄 `UNTRUSTED`: 까닭 · 이 인터넷에서는 AI 단계가 돌지 않음 · 다른 인터넷(휴대폰 핫스팟)에서 시작 파일을 다시 실행하거나 강사에게). 그 밖의 요청 오류(`httpx.RequestError`, 91줄)는 전처럼 세 번까지. 처리 엔진의 수업 모델 이름 읽기(`course_model()`, 이 PC 안 주소)는 urllib 그대로.
- `scripts/check_stack.py`
  - 219줄 `agent_outcome`: 처리 건 보기의 `attention`(서버 `instances.attention` — 포털 처리 건 맨 위 「사람 조치 필요」 알림과 같은 판정)에서 T_agent 의 멈춤을 읽어, 보류면 「AI가 판단을 보류했습니다. AI가 남긴 까닭: 「…」 — 까닭에 적힌 것을 확인하거나 고친 뒤 다시 점검하세요」, 까닭이 없으면 「없음(AI가 까닭을 남기지 않았습니다)」, 실패 · 취소 · 멈춤이면 서버의 이름표 + 기록된 까닭 + 재생/키 할 일. 「기본 지식」 문장과 서버에 없는 상태 값 갈래는 지움.
  - 243줄 `record_gaps` · 256줄 `wait_for_record`(240줄 `RECORD_SPARE = 30`): 키 있는 PC(`AI_MODE=live`)만, 설비 초기화 뒤 결함을 넣기 전(363줄)에 판단 실험 `POST /api/agent/decide {HYD-01, COOLER_DEGRADATION}`(처리 건 AI 판단과 같은 지식 · 같은 근거 계산 · 같은 관측 범위 판정, 읽기만 — 저장 없음 확인)의 근거 가운데 `OBSERVATION_GAP` 이 없어질 때까지 5초마다 다시 묻는다. 기다리기 전에 「AI가 판단에 쓰는 설비 기록(최근 N초)이 아직 다 쌓이지 않아, 결함을 넣기 전에 최대 N+30초 기다립니다」를 찍고, 그래도 비면 빈 곳(근거 이름 · 신호 · 창 · 빈 초)과 할 일로 실패. 잴 수 없으면(지식 없음 404 등) 그 응답을 찍고 기다리지 않는다(AI 판단이 같은 까닭을 만나면 쿨러 사건 줄이 그 까닭을 말한다).
  - 63줄 `http()` 의 `ApiError` 가 구조화된 detail 원래 모양(`body`)을 지님(판단 실험의 409 근거 목록을 읽으려고).
  - 머리 안내(460 · 465줄): 「키 있는 PC는 AI 판단이 실제로 돌고, 시작 직후면 AI가 판단에 쓰는 설비 기록이 쌓이기를 먼저 기다려 더 걸린다」, [2/3] 기다리는 한도에 「키 있는 PC의 설비 기록 — AI가 판단에 쓰는 기간 + 30초」. 머리말 문서도 같은 내용.
- `workspace/개발/tests/conftest.py` 1166줄 `FakeRelay(tls=(인증서, 키))` — HTTPS 로 받는 칸.

## 3. 붙인 시험과 되돌림 확인
- `test_relay_probe.py` 160줄 `test_강의_중계_확인은_관문과_같은_인증서를_믿어_실제_AI_호출과_같은_결과를_낸다`: 시험이 만든 인증 기관이 127.0.0.1 에 서명한 HTTPS 대역에 **실제 관문(실제 DB · 장부 · 토큰)** 과 **확인(따로 뜬 파이썬 프로세스 — 컨테이너 안의 `python -` 처럼)** 을 함께 붙인다. ① 환경(`SSL_CERT_FILE`)만 그 기관을 믿음 → 관문 `relay_failed`, 확인 `tls`. ② 관문의 묶음(certifi)이 믿음 → 둘 다 200 · 연결됨.
  - 되돌림: `relay_probe.py` 를 31a98098 판(urllib)으로 → ① 확인이 「연결됨 · 답 ok」(관문은 relay_failed — 이 VM 증상 그대로), ② 확인이 「닿지 않습니다(SSLCertVerificationError)」(관문은 200) — 두 경우 모두 실패함을 확인.
  - 알게 된 것: 이미 돈 시험 프로세스에서 `SSL_CERT_FILE` 을 바꾸면 OpenSSL 이 따르지 않는 경우가 있어(같은 프로세스 두 번째부터) 확인은 새 프로세스로 잰다 — 시험 머리말에 적음. 기존 지역 대역 이름 `relay` 는 conftest 의 session `relay`(관문 묶음)를 가려 `asked` 로 바꿈.
- `test_check_stack.py`
  - 191줄 `test_AI_판단_단계가_멈추면_서버가_판정한_멈춤의_까닭을_그대로_말한다`(4경우): 처리 건 보기의 attention 을 **서버 함수 `procsvc.instances.attention` 으로 계산**하고, 보류 행 · 사건은 `task_deferral.defer` 가 쓰는 모양, 까닭은 이번 실제 AI 점검의 업무 DB 문장. 보류 까닭 그대로 · 「기본 지식」 없음 / 까닭 없음 → 「남기지 않았습니다」 / 실패(키) → 기록된 까닭 + 키 할 일 / 실패(재생) → 「새 판 받기」.
    - 되돌림: `agent_outcome` 을 옛 판으로 → 4경우 모두 실패.
  - 180줄 승인 닿음 · 아직(옛 시험의 둘을 실제 모양으로).
  - 306 · 315 · 329줄 기록 기다리기(실제 HTTP 대역, 시계 주입): 시작 직후 빈틈 → 세 번 묻고 10초 기다린 뒤 진행, 안내 한 줄에 「최근 120초」 · 「최대 150초」 / 끝까지 비면 150초 뒤 실패, 빈 곳 「VS1 … 24.55초 동안 값 없음」(덮인 CE 는 말하지 않음) / 이미 쌓였거나 잴 수 없으면 0초, 잴 수 없음은 그 까닭을 한 줄로.
    - 되돌림: `wait_for_record` 를 바로 돌아가게 → 넷 모두 실패.
- 돌린 시험: `test_relay_probe.py` · `test_check_stack.py` · `test_course_model.py`(관문을 건드림) 함께 103개 통과. 시험 DB `hyd_test_chk` 는 끝에 지움.

## 4. 스택(/home/user/main, 8b8f34f9, 재생 모드)에서
- process 만 `COMPOSE_PARALLEL_LIMIT=1` 로 다시 지음 → healthy, 재시작 0.
- `bash scripts/check_all.sh`(접두 포함) → **모두 통과**: 서비스 · 포털 / 경보(유온 56.0 ℃ · 냉각 효율 46.2 %) / 처리 건 열림 / AI 판단 · 제안(팬 최대 운전 — 승인 대기) / 승인 뒤 실행(냉각 명령 → 효과 확인 정상 → 정비 요청 → 결과 보고 정상) / 점검 정리 / 강의 중계 해당 없음. 머리 안내 새 문장 확인. 재생 모드라 기록 기다리기는 건너뜀(설계대로).
- 실제 에이전트 서비스로 `record_gaps` → `[]`(오래 켜 둔 스택). connect-ingest 를 `docker restart` 해도 빈틈 없음(재접속 전 값이 남는다).
- 기록 기다리기 실측(`check_stack.wait_for_record` 를 실제 에이전트 서비스에 붙이고, ot-bridge 를 10초 멈춰 기록에 빈틈을 만듦): 멈추기 전 빈 근거 0 → 다리 다시 켠 5초 뒤 빈 근거 4(VS1 120초 창 빈틈 12.0초, CE 30초 창 12.0초, TS4 120초 창 22.0초) → 안내 「AI가 판단에 쓰는 설비 기록(최근 120초)이 아직 다 쌓이지 않아, 결함을 넣기 전에 최대 150초 기다립니다.」 → **111초 기다린 뒤 빈 근거 0으로 끝**(빈틈이 120초 창 밖으로 나간 때). 그 뒤 `check_stack.py services` 통과, ot-bridge · connect-ingest · cmd-gateway · process healthy 재시작 0.

## 5. trust_env 조사(바꾸지 않음 — 사용자가 정할 일)
- 근거: `trust_env=False` 는 커밋 `883cd620`(2026-10-30 「시스템 전체 점검 반영」 — 관문이 모델 호출을 httpx 로 넘기게 다시 쓴 커밋)에서 처음 들어왔고, 커밋 글 · 코드 주석 · 개발 문서 · 근거 기록 어디에도 **까닭이 적혀 있지 않다**(저장소 전체 검색). 같은 설정이 워커의 질문 도구(`it/agent-worker/worker/question_tools.py` 25줄, 커밋 `52e02ffb`, 컨테이너 안 process 로 가는 내부 호출)에도 있고 역시 까닭이 없다. 짐작되는 까닭(기록 없음): 강의 중계 키를 실은 요청이 환경 변수로 정해진 프록시를 거치지 않게, 컨테이너 환경에 따라 동작이 바뀌지 않게.
- httpx 0.28.1(process 이미지)에서 이 설정이 하는 일(코드 읽음): 환경의 `HTTP(S)_PROXY` · `ALL_PROXY` · `NO_PROXY` 를 따르지 않고, `SSL_CERT_FILE` · `SSL_CERT_DIR` 대신 certifi 묶음(Mozilla 루트)만 믿고, `.netrc` 를 읽지 않는다.
- 학교망 · 회사망에서 생기는 일:
  - HTTPS 를 다시 서명하는 망(보안 장비의 사설 루트 인증서를 PC에 깔아 둔 곳): 컨테이너는 Windows · macOS 의 인증서 저장소를 보지 않으므로, PC는 믿어도 컨테이너는 믿지 않는다. 관문은 그 인증서를 믿을 길이 없어 실제 AI 호출이 모두 `relay_failed`(학생 문장 「AI 중계 서버에 닿지 못했거나 … 잠시 뒤 다시 실행」 — 인증서 까닭은 말하지 않음). 이번 고침으로 시작 8단계 · 점검은 그 까닭(`tls`)을 말한다. Docker Desktop 은 기본으로 컨테이너에 `SSL_CERT_FILE` 을 넣지 않으므로, 옛 확인도 이런 PC에서는 실패했다(「닿지 않습니다(SSLCertVerificationError) — 인터넷 연결 확인」 — 엉뚱한 할 일). 옛 확인이 통과하고 관문만 실패하는 어긋남은 이 VM 처럼 컨테이너 환경에 인증서가 들어올 때 생겼다.
  - 프록시를 거쳐야만 밖에 나가는 망: Docker 설정(`~/.docker/config.json` 의 proxies, Docker Desktop 프록시 설정)이 컨테이너에 `HTTPS_PROXY` 를 넣어 주더라도 관문은 따르지 않고 직접 나가려다 실패한다(`relay_failed`). 확인은 「강의 중계에 닿지 않습니다(ConnectError 등) — 인터넷 연결 확인」을 말한다(관문과 같은 결과, 까닭은 「프록시」까지는 모름).
- 선택지(쉬운 말):
  - 가) 그대로 둔다 — 그런 망의 PC는 실제 AI가 안 되고, 점검이 그렇다고 말한다. 학생은 휴대폰 핫스팟 같은 다른 인터넷을 쓰거나 키 없는 재생으로 수업한다. 바꿀 것 없음.
  - 나) `trust_env=True` 로 — 컨테이너 환경의 프록시 · 인증서를 따른다. 다만 컨테이너는 PC의 인증서 저장소를 저절로 받지 않으므로, 다시 서명하는 망은 누군가 컨테이너에 인증서를 넣어 줘야 풀리고(설정 일이 하나 생김), 키가 환경이 정한 프록시를 거쳐 나간다(TLS 는 끝까지 암호화 — 다시 서명하는 장비는 볼 수 있음). `relay_client` 한 곳만 바꾸면 관문과 확인이 함께 바뀐다.
  - 다) 수업 PC 의 인증서를 넣는 칸을 명시적으로 하나 둔다 — 새 기능이라 이번 범위 밖.

## 6. 학생이 시작 직후 포털에서 결함을 넣으면(코드로 확인, 화면은 고치지 않음)
- 같은 보류가 난다: 처리 건의 AI 단계는 dmn-mcp `diagnose` → `mcp_tsdb.evaluate`(점검과 같은 관측 범위 판정) → 근거가 비면 `withheld` → AI 가 `__deferred__` 로 보류. 감지기 경보는 자기 기간만 보므로 시작 직후에도 경보는 바로 난다(점검 실측: 결함 몇 초 뒤 경보).
- 화면은 그 까닭을 보인다: 처리 건 맨 위 빨간 알림(`it/portal/www/instances.js` 815줄 `topCardHtml`)이 「멈춤 — 사람 조치 필요」 · 단계 이름 · 「AI 가 판단을 보류함」 · **AI 가 남긴 까닭 문장**(서버 attention 의 reason = 보류 사건 message) · [이 단계에서 조치하기](다시 평가 · 닫기). 거짓 문구는 찾지 못함.
- 덜 친절한 곳(보고만): AI 의 까닭은 「관측 공백이 있어 … 센서 기록의 연속성을 확인한 뒤 다시 평가해 주세요」처럼 센서 고장으로 읽힐 수 있다. 실제 까닭은 「막 켜져 판단에 쓰는 최근 2분 기록이 아직 덜 쌓임 — 2분쯤 뒤 [다시 평가]」인데, 판단 도구의 근거 결과(`coverage`)가 빈 곳이 「기록 시작 전」인지 「중간 끊김」인지 구분하지 않아 AI 도 그렇게 말할 수 없다. 고친다면 `mcp_tsdb.observation_coverage` 가 그 구분을 결과에 싣는 쪽(제안 — 이번 범위 밖).

## 7. 고치지 않고 남긴 것과 까닭
- 점검 정리(`check_stack.py` `cleanup`)는 「멈춘 AI 단계」를 `status == 'PENDING' and agent_mode` 로만 찾아 닫는다 — 실행 실패(IN_PROGRESS + draft FAILED) · 취소 단계는 닫지 않아, AI 실행이 실패하면 3분 뒤 「점검 정리 실패(처리 건 … 이 아직 열려 있습니다)」가 하나 더 나온다(이번 고침 전에도 같음 — 그땐 7분 기다린 뒤). 서버 attention 의 `actions` 에 'close' 가 있는 단계를 닫으면 한 곳으로 맞는다. 범위 밖이라 보고만.
- 관문(`course_model.forward`)은 연결 실패의 종류를 버리고 늘 `relay_failed` 로 거절한다(`except Exception: raise Refusal('relay_failed')`) — 인증서 · 프록시 까닭이 학생 화면 · 워커 기록에 남지 않는다. 확인은 이제 까닭을 말하지만 수업 중 AI 단계의 실패 문장은 그대로. 범위 밖이라 보고만(5절 선택과 함께 정할 일).
- 점검의 `agent_outcome` 은 처리 건이 승인 전에 끝나 버린 경우(RUNNING 아님 — attention 없음)는 여전히 7분을 기다린 뒤 「닿지 않았다」로 말한다. 이번 흠과 다른 갈래라 그대로.
- README 「점검」 줄은 걸리는 시간을 말하지 않아 고치지 않음(머리 안내만 바꿈 — 지시대로).

## 8. 커밋
- `portal-ux` `8b8f34f9`(push 안 함): course_model.py · relay_probe.py · check_stack.py · tests/conftest.py · test_relay_probe.py · test_check_stack.py. 이 보고 파일은 커밋하지 않음.
