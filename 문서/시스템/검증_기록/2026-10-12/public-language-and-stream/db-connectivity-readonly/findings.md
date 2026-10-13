# 실제 B GET timeout: 연결 경로와 준비 상태 조사

조사 범위는 현재 소스 읽기·Docker network/port inspect·공식 문서다. .env/credential/env값 조회·서비스 재시작·네트워크 설정 변경·SQL 쓰기·새 모델·카운터 변경0이다. IPv4/IPv6 실제 개별 socket 및 PostgreSQL active query 조사는 루트가 병행하고 있으므로 이 기록은 그 결과 없이 단일 원인을 확정하지 않는다.

## 직접 확인한 현재 경로

Docker process는 it-net192.168.48.3/gateway192.168.48.1 및 sim-net192.168.32.2/gateway192.168.32.1에 붙어 있다. 두 네트워크 인터페이스의 GlobalIPv6Address/IPv6Gateway는 빈 값이다. ExtraHosts는 host.docker.internal:host-gateway다. Supabase DB는 별도supabase network172.24.0.2/gateway172.24.0.1에 있으며 host54322는0.0.0.0와::에 published되어 있다. 따라서 process는동일network의db이름이아닌hostpublishedport경로를사용한다.

루트가 관찰한fdc4:f303:9324::254/54322 Network is unreachable는process의없는IPv6라우트와일치하는증상이다. 다만libpq는여러주소시도후마지막실패도보고하므로이한줄만으로IPv4접속이안됐는지원인이IPv6뿐인지판정하면안된다. IPv4주소별socket접속/시간,IPv6주소별결과,현재DNSgetaddrinfo를비교해야한다. DockerCLI호출도이호스트에서수초~수십초지연됐으므로메모리/DBIO압박과연결경로문제를동시에구분한다.

## 소스 연결과 timeout의 범위

- `procsvc/procdb.py:610` _conn은thread-localeventtransaction이없으면매호출새psycopg.connect(615행,connect_timeout5)를연다. pool이없다. event_transaction622행/assessment_transaction640행도새연결이다. 따라서DNS·TCP/TLS·Postgres세션준비비용이요청/백그라운드poll에서반복된다.
- `entsim/main.py:85`~86은동일hostDSN과connect_timeout5로새연결을만들고SupabaseEnterprise에주입한다. `supabase_backend.py:39` read는그연결에서SQL실행을기다린다. connect_timeout은**연결수립**제한이며그뒤SQL의IO/lockwait기한이아니다. processGET이timeout났다고그요청이DB에연결전인지query중인지같은증거로묶지않는다.
- `procsvc/instance_mode.py:216` retry_startup은startupDB단계의boundedbackoff다. runtimeGET/poll의network원인을자동고치는경로가아니다. 무한retry나timeout증가를근본수정으로제안하지않는다.
- `procsvc/main.py:405` healthok는Kafka와consumer/source/startup오류들에따라판정한다. 현재B업무GET이나instancepoll의매번DB준비상태를직접검사하지않는다. 따라서healthz200과업무DB읽기실패가동시에존재할수있다. `enterprise_mcp/server.py:153` health는실제readerConnection의간단한DB쿼리를하므로DBnetwork실패시unhealthy가되는것은다른health계약이다.

## 원인별 최소 교정안과 확인 순서

1. 루트의address별socket증거를먼저확인한다. IPv4는즉시연결되고IPv6만route불가이면Docker Desktop의현재네트워크/DNS가unsupportedAAAA를노출한것이직접교정대상이다. 공식DesktopSettings→Network의AutoDNS또는IPv4-only환경에맞는AAAAfilter를사용한다. application의hardcodedIP/임의hostaddrfallback으로우회하지않는다. 현재설정값은이조사에서읽거나바꾸지않았다.
2. IPv4도느리거나불가하면hostpublishedport/backendroute/firewall및Docker Desktop자원상태를확인한다. root가실제DBactiveIODataFileRead와높은CPU를관찰했으므로DNS만고쳐업무GET복구라고보고하지않는다. socket성공뒤DBquery시간/activewait를분리한다.
3. 지속운영 topology를바꿀경우에는process/enterprise와Supabase를공식관리sharednetwork에연결해고정된DB서비스alias:5432를쓰는선택을검토할수있다. 그러나현재SupabaseCLI가관리하는별도network의재생성/권한/원복계약을먼저설계해야한다. 즉시docker network connect나컨테이너IP하드코딩은이read-only조사에서실행하지않는다. 기본host.docker.internal자체는DockerDesktop이공식지원하는경로다.
4. health보강은연결원인수정과별개다. 이미존재하는instancepoll실패상태가있다면기존health에같은실패/복구상태를정확히반영하는최소안을검토하고,새숨긴DB쓰기나매health고비용fullquery는만들지않는다. DBpool은DNS원인교정의대체물이아니며별도성능변경을이번긴급원인조사에섞지않는다.

## 공식 근거

[Docker Desktop networking how-tos](https://docs.docker.com/desktop/features/networking/networking-how-tos/)는host.docker.internal을호스트접속이름으로안내하며Windows/Mac의IPv4/dualstack와DNSAuto/AAAA필터가unsupported주소족으로인한timeout을줄인다고설명한다. [Psycopg connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)는연결실패시pool요청이timeout까지기다릴수있음을설명한다. 현재코드는pool사용자가아니므로PoolTimeout을현재원인으로단정하지않는다. [Psycopg usage](https://www.psycopg.org/psycopg3/docs/basic/usage.html)의connect_timeout은연결인자이며업무query의IOwait종료를보장한다고해석하지않는다.

## 후속 루트 실제 socket 결과

루트의현재address별검사에서IPv4 `192.168.65.254:54322`는0.0256초에TCP연결성공했고IPv6 `fdc4:f303:9324::254`는0.0002초에Err101로즉시거절되었다. DNS는예상된두주소를반환했다. 따라서**현재hosthairpin의IPv4경로는정상이며DNS/IPv6가현재timeout의단독원인이라고확정할수없다.** 과거연결시IPv4가일시실패한뒤마지막IPv6오류가보고되었을가능성이남는다. 위networkDNS교정안은조건부선택이며현재설정의전역IPv4변경을권고하지않는다.

루트의DB검사에서는117초activequery가이후사라졌고현재latest_states는process_source_state3행을읽으며과거848k이벤트전체읽기와동일시할수없었다. 실제slowquery를확정하기전queryindex변경/대형이벤트rewrite를제안하지않는다. 루트의HTTP health/flows/B조회timing과DBwait관찰로연결후query/백그라운드경합을분리해야한다.

현재read-only근거로보장되는것은hosthairpin/IPv4-onlycontainerinterfaces/반복새DB연결/health와업무준비상태의분리다. 운영복구·실제B조회성공·네트워크교정완료는아직주장하지않는다.
