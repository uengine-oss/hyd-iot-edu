# 3차 작업자 보고 — OT: 연결을 먼저 여는 쪽을 공장 쪽으로

셋째 작업자(2026-11-17)가 `portal-ux` HEAD `159632d0` 위 작업 트리에서 이어서 끝냈다. 커밋 · push 하지 않음(감독 몫).

## 0. 남은 일

작업자 몫은 없다. 스택은 새 판으로 떠 있고(계속 도는 서비스 23개 모두 healthy, 마지막에 `scripts/start_all.sh` 전체를 `COMPOSE_PARALLEL_LIMIT=1`로 한 번 돌려 8단계 모두 통과, process 안 키 길이 0 · 워커 `AI_MODE=replay`), 전체 점검이 통과한 상태다. 감독 몫은 아래 둘과 「main 판을 쓰던 PC의 새 판 시작」 흉내, 6절의 교재 자리를 남은일에 넣는 것이다.

**감독이 커밋할 때 꼭 볼 것**
1. `workspace/개발/tests/test_ot_bridge.py`는 새 파일인데 `portal-ux`의 `.gitignore`(`/workspace/`)에 걸려 `git status`에 보이지 않는다. `git add -f`로 넣는다(`159632d0`에 빠져 있다 — `RUNBOOK.md` · `test_zones.py` · `test_mqtt.py` · `test_emqx.py`가 이 파일을 가리킨다).
2. 셋째 작업자가 고친 미커밋 파일 넷: `README.md`, `it/portal/www/layers.js`, `workspace/개발/tests/test_emqx.py`, `workspace/개발/문서/교재_고칠곳.md`.

## 1. 고른 설계와 까닭(둘째 작업자의 판정 — 그대로 이었다)

- 고른 길: 공장 쪽 브리지 `ot-bridge`(mosquitto 2.0.22, `ot/bridge/mosquitto.conf`)가 공장 브로커(emqx, OT 망에만)와 DMZ 브로커 `dmz-broker`(mosquitto 2.0.22, `dmz/broker/`, 경계 망 `ot-dmz-net`에만)에 **스스로 접속**해 값을 올리고 명령 · 경보판을 가져온다. 브리지에는 밖에서 들어오는 입구가 없다(127.0.0.1에만 듣는다). 다리 상태는 `bridge/ot/broker` · `bridge/ot/dmz`(보존, 1 = 이어짐)로 DMZ 브로커에 올라가 수집 중계 · 명령 관문의 `/healthz`가 말한다.
  - 값: 설비 → emqx → ot-bridge ⇒ dmz-broker → connect-ingest → redpanda (⇒ = 공장 쪽이 여는 연결)
  - 명령: process → redpanda → cmd-gateway → dmz-broker ⇐ ot-bridge → emqx → 설비
- 견준 길과 떨어진 까닭
  1. EMQX의 자체 MQTT 브리지(데이터 통합)로 DMZ 브로커에 내보내기(새 컨테이너 1개): EMQX가 경계 망에 붙어야 해서, 경계 망의 DMZ 컨테이너가 EMQX의 입구(1883 · 1884 · 8083)에 TCP로 닿는다. 입구를 OT 망 주소에만 묶으려면 PC마다 서브넷 · 고정 IP를 정해야 한다(기준 5가 피하라고 한 방식). 기준 1(망으로 막힘)을 못 채운다.
  2. 공장 쪽에 파이썬 엣지 중계 하나를 두고 DMZ 서비스에 HTTP로 밀고 당기기(새 컨테이너 1개, DMZ 브로커 없음): 새 코드 · 새 이미지 빌드가 생기고 메모리가 약 40 MB(기존 파이썬 서비스 실측 41~46 MB)로, mosquitto 둘(실측 합 9 MB)보다 무겁다. 현업의 흔한 꼴(공장 쪽 브로커 · 엣지가 DMZ 브로커로 브리지)과도 멀다.
  3. EMQX를 mosquitto로 바꾸기(메모리 약 −215 MB): 바깥 입구 계정 · 웹소켓 · 허락되지 않은 발행의 연결 끊기(`deny_action = disconnect`) · FUXA 연결 · 교재가 부르는 이름까지 함께 바뀌는 큰 고침이라 이번 일(연결 방향)에 넣지 않았다. 메모리를 줄일 후보로 따로 제안한다(7절).
- 「새 구성 요소는 하나만」에 대해: 망으로 막으려면 기다리는 쪽(DMZ)과 먼저 여는 쪽(공장) 두 자리가 있어야 한다. 그래서 컨테이너는 둘이지만 둘 다 mosquitto 2.0.22 한 이미지이고(새로 받는 이미지 하나, 새 빌드 없음), 실측 메모리는 둘을 합쳐 9.0 MiB다.

## 2. 바꾼 파일(`b0866625` 대비 — `16466bb2` · `159632d0` + 셋째 작업자의 미커밋 넷)

| 파일:줄 | 바뀐 것 |
|---|---|
| `compose.yaml:24-31`(머리말) · `:52`(emqx — `networks: [ot-net]`) · `:100`(ot-bridge) · `:131`(dmz-broker) · `:154` · `:172`(`MQTT_HOST: dmz-broker`) | 공장 브로커를 경계 망에서 뺌, 브리지 · DMZ 브로커 추가(각 `mem_limit: 24m`, 포트 안 엶), DMZ 서비스는 DMZ 브로커에만 |
| `ot/bridge/mosquitto.conf`(새 파일) | 다리 둘(`broker` · `dmz`), 토픽마다 방향 하나, `cleansession true`, 다리 상태 알림 |
| `dmz/broker/mosquitto.conf` · `dmz/broker/acl`(새 파일) | 입구 1883 하나, 이름별 토픽 규칙(명령 토픽은 cmd-gateway만 놓고 ot-bridge만 읽는다), 디스크에 안 남김 |
| `ot/emqx/acl.conf:3-7` · `ot/emqx/emqx.conf:5-12` | cmd-gateway · connect-ingest 이름을 뺌, `ot-bridge`만 `cmd/auto` · `alert` 발행 |
| `common/hydcommon/mqtt.py:43`(`behind_bridge`) · `:79`(`bridge_up`) · `:105`(`healthy`) · `:115`(`publish`) | DMZ 서비스의 연결은 다리 둘이 이어졌다고 올라온 뒤에만 건강하고 발행을 받는다 |
| `common/hydcommon/topics.py:27-33` | 다리 상태 토픽 |
| `dmz/cmd-gateway/gw/main.py:61`(`_on_bridge_up`) · `:88` · `:203`, `gw/validate.py:31-43`(주석) | 길이 이어질 때마다 경보판 다시 올림, 다리가 끊긴 동안 승인된 명령은 `MQTT` 검사로 거절 |
| `dmz/connect-ingest/app/main.py:77` | 브리지 뒤의 연결 |
| `ot/plant-sim/plantsim/edge.py:5-8` · `it/agent/agentsvc/tools/mcp_prom.py:5` | 머리말만 |
| `it/portal/www/app.js:157-158` · `:175-176` · `:214-247` · `:399-417` | 부품 둘 추가, 길 · 글 「연결은 공장 쪽이 엽니다」, 화면 없는 부품의 상태 읽기(503 본문도 읽음) |
| `it/portal/www/layers.js:10-14` · `:23-28`(`HEARD`) · `:59-72` · `:81-82` · `:88-95` | 부품 표(`ot-bridge` · `dmz-broker`), 망 목록, 「현업과 다른 곳」(「접속 방향」 줄을 지우고 「공장 쪽 브리지」 줄, 「영역 경계」 · 「인증 · 암호화」 다시 씀) |
| `README.md:13-15` | 구성 표 |
| `workspace/개발/문서/RUNBOOK.md`(2절) · `UIUX_PLAN.md:43` · `디자인기준.md:110` · `:199` · `교재_고칠곳.md` | 새 구조 · 서비스 26개 · 「서비스 16/16」 · 교재 어긋남 줄 |
| `workspace/개발/tests/conftest.py:409` · `:634` · `:946` · `:988`, `test_zones.py`, `test_emqx.py`, `test_mqtt.py`, `test_gw_main.py`, `test_www_app.py`, `test_ot_bridge.py`(새 파일) | 4절 |

셋째 작업자가 고친 것: `README.md:13` · `layers.js:67` · `:90` — 앞 판의 「설비망 밖에서는 닿지 못한다」 · 「바깥에서 공장 브로커로는 닿는 길이 없습니다」가 이 PC의 구독 입구(호스트 1883 · 8083 → emqx 바깥 입구)와 어긋나, 「DMZ · IT의 부품은 닿지 못한다, 이 PC의 프로그램은 구독만 하는 입구로 값을 직접 볼 수 있다, 현업은 그런 입구를 두지 않는다」로 고쳤다. `test_emqx.py:6`(가리키는 파일 이름 `test_bridge.py` → `test_ot_bridge.py`), `교재_고칠곳.md`(사실표 줄 목록을 실물대로 넓힘).

고치지 않은 것과 까닭: 점검(`scripts/check_all.sh` · `check_stack.py`)은 compose가 아는 서비스 전부의 상태 확인을 읽으므로 새 서비스 둘이 저절로 들어간다(브리지의 상태 확인은 두 다리가 모두 이어졌을 때만 통과) — 고칠 곳이 없다. 설치 · 시작 스크립트에는 미리 받는 이미지 목록이 없다(`docker compose up`이 받는다). 홈 그림(`main.js`)의 길 「MQTT → 수집 중계(DMZ) → Kafka → 탐지」 · 「명령 관문 · DMZ」는 새 구조에서도 참이고 접속 방향을 말하지 않으므로 그대로 두었다.

## 3. 성공 기준마다 판정

| 기준 | 판정 | 근거 |
|---|---|---|
| 1. DMZ · IT가 공장 쪽에 망으로 먼저 닿지 못한다 | 통과 | `test_zones.py::test_DMZ_자리에서_공장_쪽_어느_입구로도_연결이_열리지_않는다`(경계 망에 붙인 실제 컨테이너에서 emqx · ot-bridge의 이름과 모든 주소 × 모든 입구로 `nc` — 열리는 것은 대조군 `dmz-broker:1883` 하나). 떠 있는 스택 실측: `cmd-gateway` · `connect-ingest` 안에서 `emqx` · `plant-sim` · `fuxa`는 이름이 풀리지 않고, emqx 주소 172.22.0.3의 1883 · 1884 · 8083 · 18083은 시간 초과, 브리지의 경계 망 주소 172.23.0.3은 네 포트 모두 연결 거절, `dmz-broker:1883`만 열림. `portal`(IT)에서는 `emqx` · `dmz-broker` 모두 이름이 풀리지 않음 |
| 2. 공장 쪽이 먼저 연다 · 명령은 관문 하나로 | 통과 | `test_ot_bridge.py`(실제 세 컨테이너): 값이 공장 브로커 → DMZ 브로커로 오름, DMZ 브로커의 명령 토픽은 cmd-gateway 이름만 놓을 수 있고(connect-ingest · ot-bridge · student · fuxa · plant-sim · 이름 없음은 못 놓음) 그것만 설비 자리로 내려감, 경보판은 보존된 채 내려감. `test_emqx.py`: 공장 브로커에서 `cmd/auto`를 낼 수 있는 이름은 `ot-bridge` 하나(cmd-gateway · connect-ingest 이름은 거절). `test_zones.py`: 공장 브로커를 부르는 것은 공장 안의 것뿐, 브리지 · DMZ 브로커는 호스트에 포트를 열지 않음 |
| 3. 흐름은 그대로 · 지연 | 통과 | `scripts/check_stack.py all` 통과(스택에서 1회): 경보 → 처리 건 → AI 판단(재생) → 승인 → 냉각 명령 → 효과 확인(정상) → 정비 요청 → 결과 보고. 명령 관문 `forwarded 1 · rejected 0`. 주입에서 처리 건 열림까지: 바꾸기 전 42.0초 → 바꾼 뒤 42.5초(첫째 작업자) · 43.6초(셋째 작업자, VM이 방금 다시 켜진 뒤). 승인 뒤 실행 끝까지 97.6초 → 96.5초 · 101.4초. 늘어난 것은 재는 간격(0.5초) 안팎이다 |
| 4. PC 메모리 · 새 이미지 | 통과(수치는 아래) | 새 컨테이너 둘의 실측: `ot-bridge` 1.8 MiB · `dmz-broker` 7.2 MiB(합 9.0 MiB, 한도 각 24 MiB). 새로 받는 이미지는 `eclipse-mosquitto:2.0.22` 하나(판 고정, Docker Hub — 이 VM에서는 `mirror.gcr.io/library/eclipse-mosquitto:2.0.22`로 받아 원래 이름을 붙였다). 빌드하는 이미지는 늘지 않았다. main 판을 쓰던 PC의 새 판 `시작`은 감독이 같은 폴더 흉내로 확인한다(compose가 emqx를 경계 망에서 떼어 다시 만들고 새 서비스 둘을 만든다 — 이 스택에서 그렇게 올라왔다) |
| 5. 관리할 곳 | 통과(늘어난 것을 적는다) | 새 컨테이너 2(같은 이미지 하나), 새 설정 파일 3(`ot/bridge/mosquitto.conf` · `dmz/broker/mosquitto.conf` · `dmz/broker/acl`), 새 파이썬 서비스 · 빌드 0, 고정 IP · 서브넷 0. 견준 길 1 · 2가 왜 더 가볍지 않은지는 1절 |
| 6. 화면 · 문서 | 통과 | 시스템 구성 그림 · 부품 표 · 「현업과 다른 곳」 · README · RUNBOOK · UIUX_PLAN · 디자인기준 · 교재_고칠곳(2절). `test_zones.py`의 화면 표 = compose 시험 셋, `test_www_app.py` 26개 통과. 그림은 6절 |

메모리(`docker stats --no-stream` 합계, 재생 모드): 바꾸기 전 `b0866625` 2.41 GiB(2,467 MiB) · 컨테이너 24개 → 바꾼 뒤 **2.82 GiB(2,892 MiB) · 26개**(마지막 시작 뒤 쉬는 상태에서 잼. 전체 점검 한 바퀴 직후에는 2.80 GiB). 늘어난 425 MiB 가운데 이 고침의 몫은 새 컨테이너 둘(쉴 때 6.8 MiB, 점검 직후 9.0 MiB)과 emqx +3 MiB다. 나머지는 이 고침이 건드리지 않은 두 서비스의 상태 차이다: neo4j 555 → 897 MiB(이 세션에서 지식 시드를 다시 넣고 점검을 돈 뒤 — JVM이 한번 쓴 메모리를 돌려주지 않는다), redpanda 152 → 250 MiB(VM 재시작으로 방금 다시 켜짐). 이 둘을 뺀 합계는 1,760 → 1,745 MiB로 같다. 같은 상태(오래 쉰 스택)끼리의 비교는 아니므로, 강사 PC에서 볼 값은 「바꾸기 전 값 + 약 10 MiB」로 읽는 것이 맞다.

## 4. 더한 · 고친 시험과 「되돌리면 실패」

돌린 것(작업 트리, 모두 통과): `test_zones.py` · `test_mqtt.py` · `test_emqx.py` · `test_ot_bridge.py` 51개, `test_gw_main.py` · `test_connect_ingest.py` · `test_service_images.py` · `test_start_all.py` · `test_prepare_ports.py` · `test_conftest.py` · `test_check_stack.py` · `test_fuxa_init.py` · `test_build_fuxa_project.py` · `test_edge.py` · `test_topics.py` · `test_plantsim_main.py` 232개 가운데 231개(실패 1개 `test_service_images.py::test_개발_요구_파일은_모든_서비스_요구_파일을_읽는다`는 이 worktree에 `workspace/requirements-dev.txt`가 없어서 — workspace 브랜치의 파일이라 이 고침과 무관), `test_www_app.py` 26개. 그래프 · 시계열을 띄우는 무거운 묶음(`stack` 고정물을 쓰는 에이전트 · process 시험)은 돌리지 않았다.

| 되돌린 것(스크래치 사본 `ot-copy/`) | 실패한 시험 |
|---|---|
| compose에서 emqx를 `ot-dmz-net`에 다시 붙임 | `test_zones.py::test_공장_브로커에는_OT만_닿고_경계_망에_나온_공장_쪽_부품은_브리지_하나다` · `::test_DMZ_자리에서_공장_쪽_어느_입구로도_연결이_열리지_않는다`(실제 연결이 열림) · `::test_시스템_구성_화면의_부품마다_붙은_망이_compose와_같다` |
| `Link.healthy()`가 다리 상태를 보지 않게 | `test_mqtt.py` 3개, `test_ot_bridge.py::test_브리지가_멈추면_…` · `::test_공장_브로커와_끊기면_어느_다리인지와_함께_드러난다` |
| `Link.publish()`가 다리가 끊겨도 받게 | `test_mqtt.py::test_다리가_끊긴_동안_못_보냄으로_답한_명령은_…`, `test_ot_bridge.py::test_브리지가_멈추면_…`, `test_gw_main.py::test_브리지가_끊겼다_이어지면_이미_올린_경보판도_다시_올린다` |
| `dmz/broker/acl`에서 connect-ingest도 명령 토픽에 놓을 수 있게 | `test_ot_bridge.py::test_DMZ_브로커에_명령_관문이_놓은_명령만_설비_자리로_내려간다[connect-ingest-False]` |
| `ot/emqx/acl.conf`에서 cmd-gateway 이름도 명령을 낼 수 있게 | `test_emqx.py::test_공장_브로커에서_설비_명령_토픽은_공장_쪽_브리지만_낼_수_있다[1883-cmd-gateway-…-dropped]` |
| `ot/bridge/mosquitto.conf`의 `cleansession true` → `false` | **실패하지 않음** — 아래 |

시험이 잡지 못하는 한 줄: 브리지 설정의 `cleansession true`를 `false`로 바꿔도 `test_ot_bridge.py`는 통과한다. 브리지를 멈췄다 켜는 경우와, 브리지는 켠 채 경계 망만 끊었다 잇는 경우(사본에서 시험을 하나 써서 따로 재 봄) 둘 다, 끊긴 동안 DMZ 브로커에 놓인 명령은 그 설정과 무관하게 내려가지 않았다(mosquitto 2.0.22의 MQTT 5 브리지가 세션을 남기지 않는다). 그래서 「끊긴 동안의 명령이 뒤늦게 설비에 닿지 않는다」는 성질은 시험이 판정하지만, 그 성질이 이 설정 한 줄 덕이라는 주석의 말은 시험으로 가려지지 않는다. 가려내지 못하는 시험은 넣지 않았고, 설정은 뜻을 밝히는 값으로 그대로 두었다.

## 5. 떠 있는 스택에서 밟은 길

1. 이어받았을 때 스택은 새 판 이미지로 떠 있었으나(컨테이너 안 `hydcommon/mqtt.py` · `gw/main.py` · 포털 `app.js` · `layers.js`의 해시 = 작업 트리), VM 재시작으로 `kg-seed`가 종료 코드 255로 끊겨 `agent` · `dmn-mcp`가 뜨지 못한 상태였다. 다시 짓지 않고 `COMPOSE_PARALLEL_LIMIT=1 docker compose up -d --no-build`로 올렸다(process 안 키 길이 0, 워커 `AI_MODE=replay` 확인).
2. `check_stack.py all` 통과(3절 기준 3).
3. DMZ · IT 컨테이너에서 공장 쪽으로 연결 시도(3절 기준 1).
4. `docker stop ot-bridge` → 1초 안에 수집 중계 · 명령 관문 `/healthz`가 503(`mqtt: true`, `ot_bridge: false`), 포털 메뉴 줄 「서비스 13/16 · 3개 응답 없음」, 시스템 구성 머리 「응답 없음 3 — ot-bridge, connect-ingest, cmd-gateway」(공장 브로커 · DMZ 브로커는 초록 그대로), `check_stack.py services`는 「ot-bridge: 멈춤」으로 실패 → `docker start` 뒤 1초 안에 두 서비스 200, 다리 둘 이어짐.

그림(`/home/user/hyd-iot-edu/작업/2026-11-16_포털-lite-참고/ot/`): `01_시스템구성_정상.png`(1440 × 900, 「서비스 16/16」, 길 · 「연결은 공장 쪽이 엽니다」), `02_공장쪽브리지_정보.png`(브리지에 올렸을 때의 정보 카드), `03_브리지_멈춤.png`.

## 6. 새 구조와 어긋나게 된 교재 · 사실표 자리(고치지 않음 — 남은일에 넣을 것)

- `지침/사실표/통합반_01일차_기술사실표.md` :122(L2 줄 — `compose.yaml:37` 인용) · :153(compose 망 인용) · :174 · :176 · :179 · :180 · :184(「IT 서비스가 OT의 MQTT 브로커(EMQX)에 닿는 길은 DMZ의 두 서비스뿐」) · :194(「두 망에 함께 붙는 서비스를 둘로 제한한 배치 + 서비스 코드의 방향 규칙으로 DMZ를 흉내 낸다」) · :203-204(데이터 흐름 그림 「EMQX ─▶ connect-ingest」) · :286 · :302 · :318(「EMQX의 발행자(plant-sim, FUXA, cmd-gateway)와 구독자(FUXA, connect-ingest, cmd-gateway, plant-sim)」) · :544(compose 줄 번호 `:351`) · :577(「plant-sim → EMQX → connect-ingest」).
- `제작도구/온라인/decks/integrated/sample/샘플.md:85`(「connect-ingest — EMQX를 구독해」).
- 포털 「시스템 구성」 화면이 나오는 실습 영상 · 가이드 사진 · 덱 캡처: 부품 17 → 19개, 「MQTT 브로커」 → 「공장 브로커」, 메뉴 줄 「서비스 14/14」 → 「16/16」, 그림 아래 「접속 방향」 줄이 없어지고 「공장 쪽 브리지」 줄, `docker compose ps`의 서비스 24 → 26개.
- 덱 통합 1일차 23 · 39 · 43장과 노트(「두 길 모두 먼저 움직이는 쪽은 OT」)는 고칠 것이 없다 — 실습 시스템이 이제 그 문장대로 돈다.
- 같은 목록이 `portal-ux`의 `workspace/개발/문서/교재_고칠곳.md`에 있다.

## 7. 현업과 아직 다른 곳 · 하지 못한 것

| 다른 곳 | 화면이 밝히는가 |
|---|---|
| 영역 사이에 방화벽 · 단방향 전송 장치가 없다(망 배치가 방향을 지킨다) | 밝힌다(「영역 경계」) |
| 이 PC의 프로그램이 공장 브로커를 구독하는 입구(호스트 1883 · 8083)가 있다 — 3회차 대시보드 실습이 쓴다 | 밝힌다(「영역 경계」 — 셋째 작업자가 더함) |
| 브로커에 암호화 · 인증이 없고 이름만 댄다 | 밝힌다(「인증 · 암호화」) |
| 브리지가 끊긴 동안의 값을 쌓아 두지 않는다 | 밝힌다(「공장 쪽 브리지」) |
| 올라가는 값과 내려가는 명령이 DMZ 브로커 하나를 함께 쓴다(현업은 통로를 나누기도 한다) | 밝히지 않는다 — 토픽 규칙이 이름별로 방향을 나누므로 화면 줄을 더하지 않았다. 감독이 판단할 것 |
| 브리지의 경계 망 주소에는 DMZ 컨테이너가 IP로는 닿는다(듣는 입구가 없어 연결 거절) | 밝히지 않는다(부품 설명 「바깥에서 들어오는 입구 없음」이 같은 사실을 말한다) |

하지 못한 것 · 제안
- 다리가 끊긴 동안 승인하면 처리 건에 「설비 통신(MQTT)이 끊겨 명령을 설비로 보내지 못했습니다」가 뜨는 것을 떠 있는 스택의 화면에서 밟지는 않았다(`test_gw_main.py`가 실제 DMZ 브로커 · 대역 브로커로 그 거절을 판정한다).
- main 판을 쓰던 PC가 새 판을 받아 `시작`하는 흉내는 감독 몫으로 남겼다.
- 메모리 제안: EMQX(226 MiB)를 mosquitto(수 MiB)로 바꾸면 약 215 MiB가 준다. 바깥 입구 계정 · 웹소켓 · 거절 시 연결 끊기 · FUXA 연결 · 교재의 이름이 함께 바뀌므로 사용자 판단을 받아 따로 할 일이다.
- 시험 뒤 정리: `hyd-test-` 컨테이너 · 망 0개, 시험 DB `hyd_test_ot` 지움, `docker builder prune -f`(124 MB), 디스크 남은 몫 5.3 GB.
