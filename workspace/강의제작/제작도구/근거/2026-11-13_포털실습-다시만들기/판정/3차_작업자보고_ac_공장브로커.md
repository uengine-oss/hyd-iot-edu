# 3차 작업자 보고 — AC: 공장 브로커를 EMQX에서 mosquitto로

작업자(2026-11-17)가 `portal-ux` worktree `/home/user/portal-ux`(시작 머리 `073f033d`)에서 했다. 커밋 둘 `3fad5234` · `3b7471c4`(`portal-ux`), push 하지 않음. 이 파일은 커밋하지 않음(감독 몫).

## 지금 단계 · 남은 일

- 지금: 끝남. 스택은 `/home/user/main`(`3b7471c4`에 detach)에서 재생 모드로 떠 있다 — compose 서비스 23개 모두 healthy, 한 번 도는 셋 Exited 0, process 안 키 길이 0, 워커 `AI_MODE=replay`(`/health`도 replay), 포털 메뉴 줄 「서비스 16/16」.
- 작업자 몫으로 남은 일은 없다. 감독 몫: 이 보고 커밋, 9절의 교재 자리를 남은일에 넣기, 10절에서 판단할 것(특히 10-1 · 10-5).

## 1. 조사 — 공장(OT) 브로커를 쓰는 것과 그 쓰임

| 쓰는 것 | 무엇을 위해 · 어떻게(바꾸기 전 EMQX) | 옮긴 뒤(mosquitto `ot-broker`) |
|---|---|---|
| 가상 설비 `plant-sim` | `MQTT_HOST: emqx`(compose), `hydcommon.mqtt.Link`로 이름 `plant-sim` · 비밀번호 없음 · MQTT 3.1.1 · clean session. 측정값 · 파형 발행, 상태는 보존(retain) 발행, `cmd/manual` · `cmd/auto` · `mode` 구독 | `MQTT_HOST: ot-broker`, `ot/broker/acl`의 `user plant-sim`이 같은 발행 · 구독만 허락 |
| 관제 화면 FUXA | `ot/fuxa/project.json` 장치 `emqx`(`mqtt://emqx:1883`, clientId `fuxa-ot`, 이름 `fuxa`). 태그 · 경보판(보존) 구독, 수동 조작 · 모드 발행 | 장치 이름 · 주소 `ot-broker` · `mqtt://ot-broker:1883`(생성기 `build_fuxa_project.py`로 다시 만듦 — 바뀐 67줄은 장치 열쇠 · id · 이름 · 주소와 태그 · 경보 63곳의 `variableSrc`뿐). 실측 「'ot-broker' connected!」, 화면에 값이 들어옴(그림 03) |
| 공장 쪽 브리지 `ot-bridge` | 다리 `broker`의 `address emqx:1883`, 이름 `ot-bridge`, MQTT 5 브리지, `cleansession true`, 값 · 상태 in, 명령 · 경보판 out(보존 그대로), 다리 상태 알림은 브리지 안에만(`notifications_local_only`) | `address ot-broker:1883`. 나머지 그대로 |
| 상태 확인 | `emqx ctl status` | `nc -z 127.0.0.1 1883`(DMZ 브로커와 같은 꼴) |
| `depends_on` | plant-sim · fuxa · ot-bridge가 `emqx: service_healthy` | `ot-broker: service_healthy` |
| 바깥 입구 · 포트 열기 | 호스트 `127.0.0.1:${HYD_PORT_1883}`→1884(MQTT), `${HYD_PORT_8083}`→8083(웹소켓 `/mqtt`), 계정 `student`/`student`(`users.csv`, 내장 DB) — 3회차 대시보드 구독 | 같은 호스트 포트 · 같은 컨테이너 포트 · 같은 계정(`ot/broker/passwd`, `mosquitto_passwd`로 만든 해시). `ports.json` · `.env` 키 그대로 |
| 시작 · 점검 스크립트(`scripts/`, `setup/`) | `start_all.sh` 4단계 `docker compose up -d --build`(고아 처리 없음), `check_all.sh` · `check_stack.py`는 compose 가 아는 서비스 전부를 읽음(브로커 이름 없음), `prepare_ports.py`는 compose 의 `${HYD_PORT_n}`에서 포트를 읽음, `setup/*`는 스크립트만 부름 | 시작에 `--remove-orphans`와 브로커 셋 다시 켜기를 더함(5절). 점검 · 포트 · setup은 고칠 곳 없음 |
| 이미지 미리 받기 목록 | 없음(compose 가 받는다) | 그대로. `eclipse-mosquitto:2.0.22`는 브리지 · DMZ 브로커가 이미 쓰는 이미지라 새로 받을 것 없음 |
| 선택 프로필 `monitor` | Prometheus는 파이썬 서비스의 `/metrics`만 긁음(`it/prometheus/prometheus.yml`), Grafana도 EMQX를 읽지 않음 | 고칠 곳 없음 |
| 포털 | `layers.js` 부품 `EMQX`(상태 `mqtt:EMQX` — 가상 설비 · DMZ 두 서비스의 `/healthz`로 읽음), `app.js` 그림의 상자 · 길 넷 · 관제 화면 길 | 부품 `ot-broker`(product `mosquitto`), 그림의 같은 자리 · 같은 길 |
| 문서 | README 구성 표, RUNBOOK 2절(`emqx ctl` · 18083 · 「발행하면 연결이 끊긴다」), 교재_고칠곳 | 모두 고침(2절) |
| 시험 | `test_emqx`, `test_zones`, `test_ot_bridge`, conftest `PlantMqtt`(`emqx ctl status` · `emqx ctl retainer clean`), `test_www_app`(부품 열쇠 · 18083), `test_fuxa_init` · `test_build_fuxa_project`(장치 이름), `test_mqtt` · `test_gw_main` 머리말, `test_secret_scan`의 보기 줄 | 4절 |

브로커 기능별:

| 기능 | EMQX에서 쓰던 것 | mosquitto에서 |
|---|---|---|
| 인증 | 안쪽 입구 1883 `enable_authn = false`(이름만), 바깥 1884 · 웹소켓 8083은 내장 DB 계정 | `per_listener_settings true` — 1883 `allow_anonymous true`(이름만), 1884 · 8083 `allow_anonymous false` + `password_file passwd`(student 하나) |
| 권한(ACL) | `acl.conf` 이름(username) 기준, 맞는 줄 없으면 거절. `cmd/auto` 발행은 `ot-bridge`만 | `acl` 이름 기준, 적히지 않으면 거절. 줄마다 같은 토픽 · 같은 방향 — 3절 |
| 거절된 발행 | `deny_action = disconnect`(연결을 끊음) | 버리고, MQTT 5 클라이언트에는 PUBACK 「Not authorized」(0x87). 연결은 끊지 않음 — 10-1 |
| 보존(retain) | 상태 · 경보판. EMQX 보존 저장은 메모리(재시작하면 비움) | 같음(`persistence false` — 재시작하면 비움). 브리지 너머 보존 전달은 `test_ot_bridge`가 판정 |
| will · QoS | 우리 쪽 클라이언트는 will 없음(브리지의 다리 상태 will은 DMZ 브로커 쪽 — 그대로), QoS 0 · 1 | 같음 |
| `$SYS` · 공유 구독 · 규칙 엔진 · HTTP API | 쓰지 않음(저장소 전체 검색 0) | 해당 없음 |
| 관리 화면 18083 · `emqx ctl` | 관리 화면 · API는 꺼 둠, `emqx ctl`은 상태 확인 · 시험만 | 관리 화면 · API가 아예 없다. 듣는 입구가 셋뿐인지를 시험이 판정(4절) |

## 2. 바꾼 파일:줄

커밋 `3fad5234`(바꾸기) · `3b7471c4`(시작이 브로커 셋을 다시 켬 — 5절에서 찾은 결함).

| 파일:줄 | 바뀐 것 |
|---|---|
| `compose.yaml:52-68` | 서비스 `emqx` → `ot-broker`: `eclipse-mosquitto:2.0.22`, `mem_limit 24m`(320m에서), `user 1883:1883`, `networks [ot-net]` 그대로, 포트 줄 그대로, 볼륨 `./ot/broker:/mosquitto/config:ro`, 상태 확인 `nc -z` |
| `compose.yaml:27-31` · `:38` · `:78` · `:82` · `:95` · `:109` · `:154` · `:397` | 머리말의 길 · `MQTT_HOST` · `depends_on` · 주석의 이름 |
| `ot/broker/mosquitto.conf`(새 파일) | 입구 셋과 입구별 인증, 머리말(하는 일 · 입구 · 규칙 · 거절 · 관리 API 없음 · 보는 법) |
| `ot/broker/acl`(`ot/emqx/acl.conf`에서) · `ot/broker/passwd`(`ot/emqx/users.csv`에서) | 3절. `ot/emqx/emqx.conf` 지움 |
| `ot/bridge/mosquitto.conf:4` · `:7` · `:25` | 공장 브로커 주소 `ot-broker:1883` |
| `common/hydcommon/mqtt.py:3` · `:9` · `:58` · `topics.py:24` · `:26` · `dmz/cmd-gateway/gw/main.py:5` · `ot/plant-sim/plantsim/edge.py:8` | 머리말의 이름 · 규칙 파일 경로, `Link`의 기본 주소 `ot-broker`(10-6) |
| `it/portal/www/layers.js:3`(product 뜻) · `:11` · `:14` · `:60` · `:68-71` | 부품 `ot-broker`(product `mosquitto`, 상태 `mqtt:ot-broker`, 「관리 화면 꺼 둠」 문장 → 「여는 화면이 없습니다. 지나가는 값은 관제 화면에서 봅니다.」), 브리지 · DMZ 브로커에 product `mosquitto` |
| `it/portal/www/app.js:169` · `:176` · `:224-225` · `:239-240` · `:246` · `:261` · `:309` | 그림 자리 · 길의 열쇠, 상자 아랫줄 `c.product || c.key`, 정보 카드 머리 `mosquitto · Layer 2 · OT` |
| `ot/fuxa/project.json` · `workspace/개발/scripts/build_fuxa_project.py:21` · `:257` | FUXA 장치 `ot-broker`(생성기 결과와 같음 — `test_build_fuxa_project`) |
| `scripts/start_all.sh:80-83` | `docker compose up -d --build --remove-orphans` |
| `scripts/start_all.sh:95-98`(`3b7471c4`) | `docker compose restart ot-broker dmz-broker ot-bridge` |
| `README.md:13-14` · `:146` | 구성 표 「`ot-broker` / Redpanda」, 세 자리가 모두 mosquitto, 4단계 명령 |
| `workspace/개발/문서/RUNBOOK.md:18` · `:39` · `:41` | 기동 명령과 그 까닭, 브로커 셋 · 설정 폴더 · 로그와 값 보는 명령 · 바깥 입구 · 파일 권한 경고, 규칙 파일 경로, 판정 시험 |
| `workspace/개발/문서/디자인기준.md:199` | 부품 상자 아랫줄 규칙(세 상자 모두 「mosquitto」, 서비스 이름은 정보 카드) |
| `workspace/개발/문서/교재_고칠곳.md:22-27` | 새 줄 하나(9절)와 기존 세 줄의 시스템 쪽 문장 |
| `workspace/개발/tests/…` | 4절 |

## 3. 권한 규칙을 옮긴 방법과 까닭

- EMQX의 규칙도 클라이언트 이름(clientid)이 아니라 사용자 이름(username) 기준이었다(`{allow, {username, "ot-bridge"}, publish, ["plant/+/cmd/auto", …]}`). 그래서 mosquitto `acl`의 `user` 줄로 줄마다 그대로 옮길 수 있었다 — 주체 넷(plant-sim · ot-bridge · fuxa · student), 토픽 · 방향(발행 = `write`, 구독 = `read`) 같음, 적히지 않은 것은 거절.
- 남는 차이는 입구별 인증이다. EMQX는 인증을 입구마다 켜고 껐고 토픽 규칙은 하나였다. mosquitto도 `per_listener_settings true`로 입구마다 `allow_anonymous` · `password_file`을 따로 둘 수 있어서 같은 꼴로 옮겼다. 안쪽 1883은 이름만(OT 망 안에서만 닿음 — `test_zones`), 바깥 1884 · 웹소켓 8083은 `passwd`에 있는 student만. 세 입구가 같은 `acl` 파일을 쓴다(파일 셋: `mosquitto.conf` · `acl` · `passwd` — DMZ 브로커의 둘에 계정 파일 하나를 더한 꼴).
- 지금보다 약하지 않은가: `cmd/auto`를 낼 수 있는 것은 안쪽 입구의 `ot-bridge` 이름 하나다. 바깥 입구에서 `ot-bridge` 이름을 대면 비밀번호가 없거나 틀려 연결 자체를 받지 않는다(실제 컨테이너로 판정). 안쪽 입구에서 `student` 이름을 대도 발행은 거절된다(EMQX 때와 같음). 바깥 입구를 이름만으로 열면 `ot-bridge` 이름으로 명령이 설비에 닿는다는 것을 깨뜨림 2 · 4가 보였다 — 그래서 입구별 인증을 빼고 하나의 계정 파일을 모든 입구에 쓰는 단순한 꼴(서비스에도 비밀번호를 주는 꼴)은 고르지 않았다: 공개 저장소라 서비스 비밀번호도 공개되고, 그러면 바깥 입구에서 `ot-bridge` 이름 · 비밀번호로 명령을 낼 수 있어 지금보다 약해진다.
- 공개 값: `passwd`는 `mosquitto_passwd -b`로 만든 해시이고 비밀번호는 문서에 적힌 공개 값 `student`다. 키 검사(`workspace/secret_scan.py 073f033d..3b7471c4`) 걸린 곳 0.

## 4. 시험 — 붙이고 고친 것과 깨뜨림 확인

고친 시험:
- `test_emqx.py` → `test_ot_broker.py`(같은 약속을 mosquitto로 판정):
  - `test_공장_브로커에서_설비_명령_토픽은_공장_쪽_브리지만_낼_수_있다` — 15가지(안쪽 7 · 바깥 5 · 웹소켓 3). 결과는 `delivered`(PUBACK 성공 + 설비 자리에 닿음) · `denied`(PUBACK 「Not authorized」 + 닿지 않음) · `refused`(연결을 받지 않음). 「닿지 않음」은 뒤에 브리지 이름으로 낸 표식이 설비 자리에 닿은 뒤에 본다(옛 시험은 EMQX의 연결 끊김을 기다렸다 — EMQX 고유 동작이라 다시 씀). 바깥 입구의 `student`+틀린 비밀번호, 안쪽 입구의 `student` 이름을 더했다.
  - `test_공장_브로커가_듣는_입구는_설정한_셋뿐이다` — 옛 「관리 API는 꺼져 있다」(18083에 HTTP 로그인 시도)를 갈음: 컨테이너 안에서 실제로 듣는 TCP 입구가 1883 · 1884 · 8083뿐(토픽 규칙을 거치지 않는 옆문이 없다).
  - `test_학생은_바깥_입구에서_설비_토픽을_구독해_받는다` — 바깥 1884와 웹소켓 8083 둘로(3회차 대시보드가 쓰는 웹소켓을 실제로 판정).
  - `test_FUXA는_수동_조작과_모드를_보내고_설비가_받는다` — 모드 발행도 판정.
- `conftest.py`: `MqttClient.puback`(PUBACK 이유), `_accepts`, `PlantMqtt`가 mosquitto 공장 브로커를 띄우고 보존 메시지를 비우는 법을 「다시 켜기」로(공장 브로커를 다시 켰으면 DMZ 브로커도 — 거기 남은 옛 다리 상태를 믿지 않게), `PORTS` · `REUSED_CONTAINERS` · 메모리 칸 주석(`ot-broker` 24m).
- `test_zones.py`: `PLANT_BROKER = 'ot-broker'`, 길 넷, 호스트에 여는 포트, DMZ 자리에서 공장 쪽으로 여는 입구 목록(1883 · 1884 · 8083 — 그 셋뿐인지는 `test_ot_broker`).
- `test_ot_bridge.py`(망 다시 붙일 때 별칭), `test_www_app.py`(부품 열쇠 `ot-broker`, 세 상자의 글이 [화면 이름, 「mosquitto」]이고 정보 카드에 서비스 이름이 보임, 없어진 18083 줄 지움), `test_fuxa_init.py` · `test_build_fuxa_project.py`(장치 이름), `test_start_all.py`(docker 대역이 새 두 명령을 안다), `test_mqtt.py` · `test_gw_main.py`(머리말), `test_secret_scan.py`(보기 줄의 이름을 `GF_SECURITY_ADMIN_PASSWORD`로 — 같은 뜻의 허용 표시 시험).

돌린 것(모두 `portal-ux` 작업 트리, 접두 `env -u … AI_MODE=replay`):

| 시험 | 결과 |
|---|---|
| `test_ot_broker` · `test_zones` · `test_ot_bridge` | 44 통과 |
| `test_mqtt` · `test_gw_main` · `test_fuxa_init` · `test_build_fuxa_project` · `test_start_all` · `test_edge` · `test_plantsim_main` · `test_connect_ingest` · `test_service_images` · `test_topics` · `test_check_stack` · `test_prepare_ports` · `test_conftest` | 254 통과 · 1 실패 — `test_service_images.py::test_개발_요구_파일은_모든_서비스_요구_파일을_읽는다`(이 worktree에 workspace 브랜치 파일 `workspace/requirements-dev.txt`가 없음 — 앞 작업자 보고와 같은 무관 실패) |
| `test_www_app` | 26 통과 |
| `test_start_all` · `test_setup`(`3b7471c4` 뒤) | 11 통과 |
| `test_secret_scan`(workspace 브랜치의 `secret_scan.py`를 잠깐 복사해 돌리고 지움) | 29 통과 |
| 돌리지 않음 | `stack` 고정물을 쓰는 무거운 묶음(`test_main` · `test_det_main` 등) — 같은 `PlantMqtt`를 `test_gw_main`이 이미 거친다 |

일부러 깨뜨림(스크래치에 원본을 두고 바꿨다 되돌림, 되돌린 뒤 `cmp`로 같음 확인):

| 깨뜨린 것 | 실패한 시험 |
|---|---|
| 1 `acl`에서 fuxa에게 `cmd/auto` 발행 허락 | `test_ot_broker[1883-fuxa-…-denied]` |
| 2 바깥 입구 1884를 이름만으로(`allow_anonymous true`, 계정 파일 없음) | `test_ot_broker`의 1884 `refused` 넷(그 가운데 `ot-bridge` 이름은 명령이 설비에 닿음) |
| 3 옆문 입구 `listener 9001` 더함 | `test_공장_브로커가_듣는_입구는_설정한_셋뿐이다` |
| 4 웹소켓 8083을 이름만으로 | `test_ot_broker`의 8083 `refused` 둘 |
| 5 compose에서 `ot-broker`를 경계 망 `ot-dmz-net`에도 붙임 | `test_zones` 셋(그 가운데 실제 연결 시도 — DMZ 자리에서 `ot-broker:1883`이 열림) |
| 6 `acl`에서 `ot-bridge`의 `cmd/auto` 발행을 뺌 | `test_ot_broker` 9개 · `test_ot_bridge` 9개(명령이 설비 자리에 내려가지 않음) |
| 7 `app.js` 상자 아랫줄을 `c.key`로(제품 이름을 뺌) | `test_www_app::test_여는_화면이_없는_브로커_둘과_브리지…`(`['공장 브로커', 'ot-broker'] != ['공장 브로커', 'mosquitto']`) |

## 5. 이미 main 판을 쓰던 PC가 새 판을 받는 길 — 실측

먼저 밟은 것(커밋 `3fad5234`, 시작에 `--remove-orphans`만 있던 판):
- 4단계: `emqx` 컨테이너 Stopping → Removed, `ot-broker` Created → Started. 고아 처리는 의도대로 됐다.
- 5단계에서 멈춤: 「cmd-gateway · connect-ingest · ot-bridge: 응답 확인 실패」. 까닭: `ot-bridge` 컨테이너가 다시 만들어지지 않고 07:01에 켠 그대로 옛 설정(`address emqx:1883`)으로 돌며 「Error creating bridge: Name does not resolve」를 되풀이했다. compose 는 `ot-bridge`의 정의에서 `depends_on`만 바뀐 것을 바뀜으로 치지 않고, 붙여 쓰는 설정 파일의 내용이 바뀐 것은 보지 않는다(실험: compose v5.6.1에서 bind mount도 `configs:` 파일도 내용만 바꾸면 컨테이너를 다시 만들지 않음). 학생이 화면의 안내대로 시작만 다시 하면 같은 자리에서 또 멈춘다.
- 고침(`3b7471c4`): `up` 뒤 `docker compose restart ot-broker dmz-broker ot-bridge`. 세 브로커는 설정을 켤 때 한 번 읽으므로 시작마다 다시 켠다(몇 초, 붙는 서비스들은 스스로 다시 붙고, 명령 관문은 다리가 이어지면 경보판을 다시 올린다 — 실측으로 hyd01 · hyd02 경보판이 공장 브로커에 다시 올라옴). 견준 길: 설정 내용의 해시를 compose 라벨에 적고 시험이 맞춰 보게 하는 꼴(바뀔 때만 다시 만듦)은 설정을 고칠 때마다 라벨도 고쳐야 해서 관리할 곳이 늘어 고르지 않았다.

다시 처음부터 한 번에(깨끗한 재현):
1. `/home/user/main`을 옛 판 `073f033d`로 되돌려 시작 → 8단계 모두 통과. `emqx` 실행 중(호스트 127.0.0.1:1883→1884, 8083→8083, 익명 볼륨 `71d85316…` · `8c508d93…`), 브리지 다리 둘 1, FUXA 장치 `emqx` 연결.
2. 학생 기록(업무 DB · 시계열 · 그래프): 처리 건 20 · 할 일 129 · 사건 668 · 알림 56 · 정비 이력 5 · 시계열 경보 6 · 지식 그래프 노드 626.
3. `git checkout -q --detach 3b7471c4` → `bash scripts/start_all.sh`(접두 · `COMPOSE_PARALLEL_LIMIT=1`) → **8단계 모두 통과, 종료 코드 0**. 4단계 기록: `ot-broker` Created → `emqx` Stopping · Stopped · Removing · Removed → `ot-broker` Started → `dmz-broker` · `ot-bridge` · `ot-broker` Restarting → Started.
4. 뒤: `emqx` 컨테이너 0개, 호스트 1883 · 8083은 `ot-broker`가 쥠, 브리지 다리 `broker 1` · `dmz 1`, FUXA 「'ot-broker' created / connected!」, 학생 기록 같은 수(처리 건 20 · 할 일 129 · 사건 668 · 알림 56 · 정비 이력 5 · 경보 6 · 노드 626, 시계열 `tag_1s`는 83,266 → 84,194로 계속 쌓임). 이름 붙은 볼륨 8개 + 업무 DB 볼륨 그대로.
5. 옛 EMQX 익명 볼륨: **남는다.** `--remove-orphans`는 컨테이너만 지우고 그 이미지가 선언한 익명 볼륨(`/opt/emqx/data` · `/opt/emqx/log`)은 남긴다(실험과 실측 같음). 어느 컨테이너도 붙들지 않고 크기는 쌍마다 약 210~330 KB, 실습 기록은 없다(EMQX 노드 자료 · 로그). 지우는 장치를 더하지 않은 까닭: 크기가 작고, 지우려면 고아를 compose 보다 먼저 직접 찾아 `docker rm -v` 하는 단계(서비스 목록 비교)를 새로 들여야 한다. 이 VM에는 확인용으로 넷을 남겨 두었다: `102e9dac…` · `562eff5b…`(처음 스택의 emqx) · `71d85316…` · `8c508d93…`(재현 때의 emqx). 지우려면 `docker volume rm <이름>`.
6. 고아 컨테이너 실험(스크래치 compose): 옛 서비스가 바깥 포트를 쥔 채 그냥 `up` → 「Bind … failed: port is already allocated」로 새 서비스가 뜨지 못함, `--remove-orphans` → 옛 것을 지우고 새 것이 뜸. 선택 프로필 서비스(tools)는 지우지 않음, 같은 프로젝트 라벨을 단 compose 밖 컨테이너(업무 DB 컨테이너가 다는 꼴)도 지우지 않음.
7. 옛 이미지 `emqx/emqx:5.8`(351 MB)은 학생 PC 디스크에 남는다 — 시작은 이미지를 지우지 않는다(10-4).

## 6. 점검 결과

`bash scripts/check_all.sh`(`/home/user/main`, `3b7471c4`, 재생 모드) — 모두 통과:
- 서비스 · 포털 통과, 경보 통과(유온 56.0 ℃ · 냉각 효율 46.2 %), 처리 건 열림 통과(기본 제공 흐름 냉각 긴급 대응), AI 판단 · 제안 통과(「팬 최대 운전」 — 승인 대기), 승인 뒤 실행 통과(승인 → 냉각 명령 → 효과 확인(정상) → 정비 요청 WO-1117-8495FD8E41C0 → 결과 보고(정상)), 점검 정리 통과, 강의 중계 해당 없음(키 없음).
- 승인된 명령의 길: cmd-gateway → dmz-broker ⇐ ot-bridge → **ot-broker** → plant-sim.

그림(`/home/user/hyd-iot-edu/작업/2026-11-16_포털-lite-참고/ac/`): `01_시스템구성_정상.png`(1440 × 900, 「서비스 16/16」, 세 상자 「공장 브로커 · 공장 쪽 브리지 · DMZ 브로커」의 아랫줄 모두 「mosquitto」), `02_공장브로커_정보.png`(정보 카드 「공장 브로커 `ot-broker` mosquitto · Layer 2 · OT · 정상」), `03_FUXA_값.png`(세 설비의 값이 공장 브로커로 들어옴).

## 7. 메모리 전후

`docker stats --no-stream`, 재생 모드, 쉬는 상태(이 VM). 전 = `073f033d` 스택(07:41), 후 = `3b7471c4` 시작 · 점검 뒤(08:2x).

| | 전 | 후 |
|---|---|---|
| 공장 브로커 | `emqx` 198.7 MiB(한도 320 MiB) | `ot-broker` 2.7 MiB(한도 24 MiB) |
| 공장 쪽 브리지 · DMZ 브로커 | 1.7 · 1.2 MiB | 1.7 · 1.4 MiB |
| 스택 합(`hyd-iot-edu-*` 23개) | 2,556 MiB | 2,370 MiB(−186) |
| neo4j · redpanda를 뺀 합 | 1,355 MiB | 1,170 MiB(−185) |

나머지 서비스는 ±10 MiB 안팎으로 오르내렸다(재는 때의 차이). 강사 PC에서 볼 값은 「공장 브로커 몫 약 −195 MiB」다. 새로 받을 이미지 없음, 빌드하는 이미지 수 그대로.

## 8. 옛 이름 검색(`git grep -i emqx 3b7471c4`, 저장소 코드 · 설정 · 시험 · 문서)

남은 것과 까닭:
- `scripts/start_all.sh:80` · `:96`, `workspace/개발/문서/RUNBOOK.md:18` — 고아 지우기 · 브로커 다시 켜기의 까닭(옛 emqx 컨테이너가 남아 포트를 쥠, 브리지가 지운 emqx를 찾음)을 설명한다.
- `workspace/개발/tests/test_ot_broker.py:9` — 「듣는 입구는 셋뿐」 시험이 왜 있는지(옛 EMQX 관리 API의 옆문 실측).
- `workspace/개발/문서/교재_고칠곳.md:22` · `:23` · `:25` · `:26` · `:27` — 교재에 아직 남은 옛 문장을 인용한다(그 표의 할 일).
- 그 밖 0. (`.git` · `__pycache__` 밖, 작업 트리도 같음.)

## 9. 교재에서 고칠 자리(고치지 않음 — 다른 작업 몫, 같은 목록을 `교재_고칠곳.md:25`에 넣음)

- `지침/사실표/통합반_01일차_기술사실표.md` :122 · :134 · :135 · :153 · :159 · :174 · :179 · :180 · :184 · :190 · :194 · :203 · :284 · :286 · :318 · :476 · :544 · :553 · :577 · :810 · :858 · :879 · :889 · :890 · :930 · :942 · :964 — 「EMQX 5.8」(`emqx/emqx:5.8`), 서비스 `emqx`, `ot/emqx/emqx.conf` · `acl.conf`, 「EMQX 대시보드 http://127.0.0.1:18083 (admin / public123)」(관리 화면이 이제 아예 없음), 「실제 제품 그대로(EMQX · FUXA …)」, 용어표 「브로커 — EMQX」, FUXA 원천 `mqtt://emqx:1883`, 「EMQX 안쪽 입구 인증 한계」(문장은 여전히 참 — 이름만 댄다), 「EMQX가 협상한 MQTT 버전」.
- `제작도구/온라인/decks/integrated/sample/샘플.md` :65 · :73 · :84 · :85 · :97 · :102 · :103 · :115 · :130 · :132 · :134 · :138 — 「브로커 EMQX」 등.
- `제작도구/촬영/포털/README_큐.json:64` — `row:EMQX / Redpanda`(README 줄 이름이 「`ot-broker` / Redpanda」로 바뀜).
- `남은일.md:122` · `:129` — 메시지 중계기 관리 화면(18083) · 「공장 브로커(EMQX — OT 망에만)」.
- 덱 삽화 생성기 `제작도구/온라인/decks/integrated/day01/figures/만들기_삽화.py` · `day03/figures/삽화_기본.py` · `day04/figures/조각_1일차.py` · `day06/figures/삽화_기본.py` · `sample/figures/만들기_삽화.py` · `제작도구/온라인/tools/deck/삽화_기본.py` — `emqx`는 그림 안 부품 열쇠 이름이라 보이는 글이 아니다(바꿔도 두어도 됨).
- 음성 캐시 `제작도구/기존제작/tools/video/쉼_저장/f9817e6870b03137.json` · `d3cf9f45dc5a1049.json` — 「이 역할의 도구에는 EMQX가 있습니다」. 지금 대본 · 자막 기록에는 없는 옛 문장.
- 포털 「시스템 구성」 · FUXA 장치 화면이 나오는 영상 · 가이드 사진 · 덱 캡처 — 「공장 브로커」 상자 아랫줄 「EMQX」 → 「mosquitto」(세 상자 모두 「mosquitto」), 정보 카드 이름 `ot-broker`, FUXA 장치 이름 `ot-broker`, `docker compose ps`의 `emqx` → `ot-broker`.
- 이론 대본 · 실습 랩 HTML의 검색 결과는 그림 base64 안의 우연한 글자뿐이었다(글로 된 EMQX 없음).

## 10. 범위 밖 · 판단할 것 · 알릴 것

1. **거절된 발행의 알림이 달라졌다**(감독 판단): EMQX는 허락되지 않은 발행에 연결을 끊었고, mosquitto는 버리며 MQTT 5 클라이언트에만 PUBACK 「Not authorized」를 준다. 막는 힘(누가 무엇을 낼 수 있나)은 같다(4절). 다른 곳: MQTT 3.1.1 클라이언트(plant-sim · FUXA · 브라우저 mqtt.js 기본)는 거절을 듣지 못하고, 브리지(MQTT 5)는 거절을 받아도 다리를 끊지 않는다(실험: 공장 브로커 규칙에서 브리지의 명령 발행을 빼고 DMZ 쪽에 명령을 놓음 → 다리 상태 그대로 1 · 1, 명령은 설비에 닿지 않음). 다만 EMQX 때도 브리지 다리가 잠깐 끊겼다 이어질 뿐 명령 관문은 이미 「보냄」으로 적은 뒤라, 명령 기록을 바로잡는 힘은 그때도 없었다. 지키는 것은 시험(이름별 · 입구별 15가지와 브리지 길)이다. 학생이 바깥 입구로 발행해 보면 EMQX는 연결이 끊겼고 지금은 아무 일도 없다(MQTT 5 도구는 「Not authorized」) — 수업이 그 장면을 쓰면 교재가 고칠 곳이다(지금 교재 검색에서는 찾지 못함).
2. mosquitto 2.0.22는 시작할 때마다 `acl` · `passwd`가 누구나 읽을 수 있고 주인이 mosquitto가 아니라는 경고(「Future versions will refuse to load this file」)를 남긴다. DMZ 브로커의 `acl`도 앞 판부터 같다. 저장소에서 읽기 전용으로 붙인 공개 파일이라 지금은 그대로 두고 RUNBOOK에 적었다 — 이미지 판을 올릴 때 거절로 바뀌었는지 봐야 한다.
3. 붙여 쓰는 설정 파일의 내용만 바뀐 새 판을 떠 있는 스택이 받으면 compose 가 컨테이너를 다시 만들지 않는 성질은 브로커 셋 밖에도 있다(Grafana provisioning, monitor 프로필의 `prometheus.yml` 등). 이번 고침은 브로커 셋만 시작마다 다시 켠다.
4. 옛 이미지 `emqx/emqx:5.8`(351 MB)이 학생 · 강사 PC 디스크에 남는다. 시작이 이미지를 지우지 않기 때문이다. 지우는 안내(`docker image rm emqx/emqx:5.8`)를 둘지는 감독 판단.
5. **이 VM에서 내가 한 넓은 정리**: 브리지 거절 실험을 정리하며 `docker volume prune -f --filter label=com.docker.volume.anonymous`를 돌려, 이 VM에서 어느 컨테이너도 붙들지 않던 익명 볼륨 약 51개(약 0.8 MB, 지운 시험 · 옛 컨테이너의 것)를 함께 지웠다. 이름 붙은 볼륨(compose 8개 · 업무 DB)과 떠 있던 컨테이너의 익명 볼륨은 그대로였고 스택은 계속 healthy였다. 내가 만든 것만 이름으로 지웠어야 했다.
6. `hydcommon.mqtt.Link`의 `MQTT_HOST` 기본값은 이름만 `ot-broker`로 바꿔 남겼다. 모든 서비스가 compose 에서 값을 받고, 값이 빠져 이 기본값으로 가도 DMZ 서비스는 그 이름을 풀지 못해 `/healthz`가 실패로 드러난다(조용히 다른 곳으로 가지 않는다). 기본값을 없애면 `test_edge` · `test_plantsim_main` 등 환경 값 없이 `Edge`를 만드는 시험까지 고쳐야 해서 이번에 넣지 않았다.
7. FUXA 「최근 경보」 칸이 경보가 한 번도 없었던 설비(이 스택의 HYD-03)에서 「경보 없음」 대신 `NaN`을 보인다. 명령 관문이 경보가 있었던 설비의 경보판만 올리기 때문이고(`dmz/cmd-gateway/gw/main.py` `boards`), 브로커와 무관하게 앞 판부터 같은 동작이다(그림 03).
8. 끄기(`compose stop`)는 compose 에 없는 옛 `emqx`를 멈추지 않는다. 새 판을 받고 시작 전에 끄기만 하면 옛 `emqx`가 다음 시작까지 돈다(다음 시작이 지운다).

## 11. 커밋

- `3fad5234` 공장 브로커를 EMQX에서 mosquitto로(작업자 AC) — 33개 파일.
- `3b7471c4` 시작이 MQTT 브로커 셋을 다시 켬(작업자 AC 2) — `scripts/start_all.sh` · `README.md` · `test_start_all.py` · `RUNBOOK.md`.
- 둘 다 `portal-ux`, push 안 함. 키 검사 `073f033d..3b7471c4` 걸린 곳 0.
- 정리: 시험 DB `hyd_test_brk` 지움, `hyd-test-*` 컨테이너 · 망 0, 실험 컨테이너 · 망 0, 실험이 만든 익명 볼륨 셋 지움(옛 EMQX 넷은 5-5대로 남김), 디스크 남은 몫 5.3 GB.
