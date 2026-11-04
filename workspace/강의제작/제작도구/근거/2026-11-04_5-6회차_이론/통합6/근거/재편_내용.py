"""통합반 6회차 재편 내용 — 덱(화면 · 노트 · 제작 기준)과 대본의 바뀐 곳. 재편_덱.py · 재편_대본.py가 읽는다."""

# 새 장 번호 순서: ('old', 옛 장) 또는 ('new', 키)
ORDER = ([('old', n) for n in range(1, 18)] + [('new', 'A')] + [('old', n) for n in range(18, 22)] + [('new', 'B')]
         + [('old', n) for n in range(22, 55)] + [('new', 'D')] + [('old', n) for n in range(55, 58)] + [('new', 'C')]
         + [('new', k) for k in ('P62a', 'P62b', 'P63a', 'P63b', 'P64a', 'P64b', 'P65a', 'P65b', 'P66a', 'P66b')]
         + [('old', n) for n in range(66, 73)])
assert len(ORDER) == 78

TITLE_EDITS = {
    30: 'MCP 서버 다섯: 닿는 시스템과 도구의 범위',
}

# 옛 장 번호 → [(옛 글, 새 글)] — 화면 내용(노트 포함) 안에서 정확히 한 번 맞아야 한다
SCREEN_EDITS = {
    1: [('· 이번 회차의 두 물음:', '· 두 물음:'),
        ('→ 실습 넷 / [다음] 이번 회차에 할 수 있게 될 일', '→ 실습 다섯 / [다음] 마치고 할 수 있게 될 일')],
    2: [('도구의 호출 기록을 대조한다 / 외부 MCP와 내 조회 도구를 잇는다', '포털에서 스킬을 붙이고 도구를 직접 부른다 / 외부 MCP와 내 조회 도구를 잇는다'),
        ('· 실습: 포털에서 준비된 에이전트의 호출 기록 대조, VS Code에서',
         '· 실습: 포털에서 나의 스킬을 붙여 답 비교, 업무 도구 직접 호출과 근거 대조, VS Code에서')],
    3: [('7. 파일 범위 · 비밀값 · 불완전한 응답 | 이론', '7. 파일 범위 · 비밀값 · 불완전한 응답 · 두 환경 | 이론'),
        ('부를 수 있는 도구를 정하는 장치, 파일 범위 · 비밀값 · 불완전한 응답', '부를 수 있는 도구를 정하는 장치, 파일 범위 · 비밀값 · 불완전한 응답, 포털과 로컬 VS Code의 차이'),
        ('8. 업무 도구 확인 · MCP 연결 · 회의록 스킬 · 학습노트 퀴즈 | 실습', '8. 스킬 붙이기 · 도구 호출 · MCP 연결 · 회의록 스킬 · 퀴즈 | 실습'),
        ('· 8 실습 넷: 호출 기록 확인, 도구 직접 연결, 스킬 · 퀴즈 에이전트 만들기',
         '· 8 실습 다섯: 포털에서 스킬 붙이기 · 도구 직접 호출, VS Code에서 도구 연결 · 회의록 스킬 · 퀴즈 에이전트')],
    5: [('판단 엔진 도구 19개, 업무 DB 도구 14개', '판단 엔진 도구 17개, 업무 DB 도구 14개'),
        ('판단 엔진 19개 + 업무 DB 14개', '판단 엔진 17개 + 업무 DB 14개')],
    8: [('- 메시지: HYD는 실행 준비 때 배정된 스킬과 이번 일의 입력을 작업 폴더에 두고, 결과를 쓸 위치를 알려 준다.',
         '- 메시지: 실행 환경은 배정된 스킬과 이번 일의 입력을 작업 폴더에 두고, 결과를 쓸 자리를 정해 알려 준다.')],
    10: [('- 메시지: 이름은 스킬을 구별하고 설명은 쓰임을 알려 주며, HYD는 배정한 스킬을 실행에 제공한다.',
          '- 메시지: 이름은 스킬을 구별하고 설명은 쓰임을 알려 주며, 실행에는 배정된 스킬만 제공된다.')],
    14: [('"fm:cooler-performance-loss"', '"fm:cooler-cooling-loss"')],
    16: [('- 메시지: HYD 냉각 대응에서는 에이전트가', '- 메시지: 이 냉각 대응에서는 에이전트가')],
    17: [('[다음] 이름 때문에 헷갈리는 Skill', '[다음] 두 문서의 원문')],
    21: [('/ HYD는 실행 준비 때 보관본을 제공한다 /', '/ 실행 준비 때 보관본을 받아 쓴다 /'),
         ('[다음] HYD의 세 스킬', '[다음] 스킬로 남길 일 가르기')],
    22: [('- 메시지: HYD의 세 에이전트는 같은 틀에 업무마다 다른 절차를 적은 스킬을 하나씩 붙이고, 그 절차가 부를 서버를 연결한다.',
          '- 메시지: 시나리오 에이전트 셋은 같은 틀에 업무마다 다른 절차를 적은 스킬을 하나씩 붙이고, 그 절차가 부를 서버를 연결한다.')],
    23: [(' / · 회의록 스킬 실습에서 이 넷을 그대로 쓴다', '')],
    27: [('· HYD 예: 지식 그래프 서버는 공개된 서버를 가져다 붙임, 판단 엔진 · 업무 DB 서버는 HYD가 만듦 — 에이전트 쪽 연결 방식은 같다',
          '· HYD 예: 지식 그래프 서버는 공개된 그래프 조회 서버의 도구 이름 · 입력을 그대로 따르고, 판단 엔진 · 업무 DB 서버는 이 공장 업무에 맞게 만듦 — 에이전트 쪽 연결 방식은 같다')],
    28: [('7. hyd-dmn · 도구 19개 |', '7. hyd-dmn · 도구 17개 |'),
         ('hyd-dmn(판단 엔진 · 도구 19개)', 'hyd-dmn(판단 엔진 · 도구 17개)')],
    29: [('- 메시지: HYD에서는 처리 건마다 띄워지는 에이전트 프로그램이', '- 메시지: 처리 건마다 띄워지는 에이전트 프로그램이')],
    30: [('- 메시지: HYD의 기본 등록 서버 다섯은 각기 다른 범위의 도구를 제공하며, 이 표는 확인한 코드 기준이다.',
          '- 메시지: 기본 등록 서버 다섯은 닿는 시스템과 내주는 도구가 달라, 에이전트마다 필요한 서버를 고른다.'),
         ('| 조회 2개만 허용', '| 읽기 2개'),
         ('diagnose · evaluate_cards · timeseries_query | 19개', 'diagnose · evaluate_cards · timeseries_query | 17개'),
         ('· neo4j: 지식 그래프, 구조 읽기 · 조회문 실행 두 도구만 허용', '· neo4j: 지식 그래프, 구조 읽기 · 조회문 실행 두 도구뿐(조회문도 실행 전에 읽기인지 검사)'),
         ('timeseries_query 등 19개', 'timeseries_query 등 17개'),
         (' / · 표는 확인한 코드 기준', '')],
    36: [('- 메시지: 화면은 HYD의 업무 결과 본문이며, MCP 응답의 오류 표시와 업무 결과의 성공 여부를 구분해 읽는다.',
          '- 메시지: 업무 결과의 처리 상태와 MCP 응답의 오류 표시는 다른 층이므로, 둘을 따로 확인한다.')],
    37: [('- 메시지: HYD의 도구 호출은 모델의 요청을', '- 메시지: 도구 호출은 모델의 요청을')],
    38: [('· HYD: 지식 그래프 서버만 stdio, 나머지 넷은 HTTP',
          '· HYD: 포털에 등록된 서버 다섯은 모두 HTTP. 실행 안에서만 쓰는 결과 파일 검사 같은 작은 도구는 stdio, 내 PC의 VS Code 실습 서버도 stdio')],
    39: None,  # 아래 SCREEN_REPLACE
    44: [('읽는 도구와 쓰는 도구, readOnlyHint, 등록 서버가 지나는 세 겹, 연결 검사의 실패 분류, 허용 목록, 쓰기의 세 층, 최소 권한 원칙',
          '읽는 도구와 쓰는 도구, readOnlyHint, 등록 서버가 지나는 세 겹, 연결 검사의 실패 분류, 허용 목록, 쓰기의 세 층, 최소 권한 원칙')],
    46: [('/ HYD는 표시와 이름으로 걸러도 동작 전체를 증명하지 못한다. /', '/ 표시와 이름으로 걸러도 동작 전체를 증명하지는 못한다. /'),
         ('3. enterprise의 도구 | 14개가 모두 true이다.', '3. enterprise의 도구 | 14개가 모두 true이다.'),
         ('2. hyd-dmn의 도구 | 19개 가운데 17개가 true이다.', '2. hyd-dmn의 도구 | 17개 가운데 15개가 true이다.'),
         ('· hyd-dmn 19개 중 17개 true,', '· hyd-dmn 17개 중 15개 true,'),
         ],
    47: [('- 메시지: HYD는 연결 검사와 설정 지문, 읽기 판정을 거친 도구를 허용하며, 표시 없는 도구는 별도 확인 없이는 막는다.',
          '- 메시지: 새로 등록한 서버의 도구는 연결 검사 · 설정 지문 · 읽기 판정을 거쳐야 허용되고, 표시 없는 도구는 막힌다.'),
         ('수업에서는 포털에 서버를 추가하지 않고 원리로 본다, 외부 서버 직접 연결은 VS Code 실습에서 / ', '수업에서는 포털에 서버를 추가하지 않고 원리로 본다 / '),
         ('표시만 빠진 도구를 강사가 읽기로 확인하는 별도 절차가 있으나, 쓰기 표시 · 쓰기 이름에는 적용 안 함. 그림은 기본 판정',
          '표시만 빠진 도구를 따로 확인해 읽기로 넣는 절차도 있으나 그림은 기본 판정'),
         ('설정 지문(설정 내용으로 계산)이 같을 때만 통과 인정. 서버 내부 동작 · 이후 변경까지 보증하지 않는다',
          '설정 지문(설정 내용으로 계산)이 같을 때만 통과 인정. 서버 내부 동작까지 보증하지는 않는다')],
    48: None,
    49: [('- 메시지: HYD의 허용 목록과 실행 정책은 모델이 낸 요청 가운데 실제로 실행할 수 있는 도구를 제한한다.',
          '- 메시지: 허용 목록은 모델이 낸 요청 가운데 실제로 실행할 수 있는 도구의 범위를 정한다.'),
         ('mcp__enterprise-purchase__* / Read · Glob · Grep · Skill', 'mcp__enterprise-purchase__* / Read · Write · Edit · Skill'),
         ('4. Read · Skill | 파일 읽기, 스킬 읽기 같은 호스트의 도구이다.', '4. Read · Write · Edit · Skill | 작업 폴더의 파일을 읽고 쓰고 고치는 도구, 스킬 읽기 같은 호스트의 도구이다.'),
         ('· neo4j: 조회 도구 둘만 이름으로. 서버도 읽기 전용으로 띄워 그래프를 고치는 도구를 막았다', '· neo4j: 조회 도구 둘만 이름으로. 이 서버는 그래프를 고치는 도구를 내주지 않는다'),
         ('· Read · Glob · Grep · Skill: 호스트 자신의 도구(파일 읽기, 스킬 읽기)', '· Read · Write · Edit · Skill: 호스트 자신의 도구(작업 폴더 파일 읽기 · 쓰기 · 고치기, 스킬 읽기). 셸 도구는 늘 막는다')],
    50: [('- 메시지: HYD 에이전트의 MCP 쓰기 둘은 판단 제출용이며, 설비 명령과 업무 실행은 승인 뒤 시스템이 맡는다.',
          '- 메시지: 에이전트에 연결한 쓰기 도구는 판단 제출용이고, 설비 명령과 업무 실행은 승인 뒤 시스템이 맡는다.')],
    51: [('[다음] 도구 권한 밖에서 새는 곳', '[다음] 도구 권한 밖에서 새는 곳')],
    52: [('- 부제: 읽고 쓸 파일의 범위, 인증 비밀값의 자리, 실패하거나 잘린 응답의 처리와 근거 표시',
          '- 부제: 파일의 범위, 비밀값의 자리, 불완전한 응답과 근거 표시, 포털과 로컬 환경의 차이'),
         ('잘림의 구분, 근거 표시 / [다음] 파일 범위', '잘림의 구분, 근거 표시, 포털과 로컬 VS Code의 비교 / [다음] 파일 범위')],
    54: [('왼쪽 아래 가린 비밀번호', '왼쪽 아래 가린 토큰'),
         ('- 메시지: HYD는 설정에 자리표시자를 두고 실행 시 비밀값을 채우며, 새 자격 증명의 유효성과 권한은 따로 확인한다.',
          '- 메시지: 설정에는 비밀값 대신 자리표시자를 두고, 값은 따로 보관했다가 실행 직전에만 채운다.'),
         (' / 화면에 보이는 접속 정보 / "NEO4J_PASSWORD": "＊＊＊＊＊＊＊＊"', ' / 값을 직접 적은 설정이 화면에 보일 때 / "Authorization": "＊＊＊＊＊＊＊＊"'),
         ('  4. 환경변수 | 워커의 비밀 상속을 줄인다. 필요한 인증과 실행 중 설정은 별도 관리한다.',
          '  4. 토큰 교체 | 설정 지문은 자리표시자로 계산해 검사 통과가 남는다. 새 토큰의 권한은 따로 확인한다.'),
         ('· 화면 · 기록에 보일 때는 별표로 가린다(지식 그래프 서버 비밀번호)', '· 화면 · 기록에 보일 때는 별표로 가린다(설정에 토큰을 직접 적은 경우도)'),
         (' / · 환경변수(실행 때 넘겨받는 설정값): 워커만 쓸 DB 비밀번호는 에이전트 프로그램이 물려받지 못하게 지운다 — 전달되면 허용 목록을 거치지 않고 DB에 바로 접속. 모델 로그인 같은 예외, MCP 비밀값은 실행 중 설정에 들어갈 수 있고 종료 뒤 정리 / · 자리표시자 · 가림은 노출을 줄이는 방법이지 완전한 보장이 아니다 / [다음] 응답을 다 받지 못했을 때',
          ' / [다음] 에이전트 프로그램이 물려받지 않는 비밀')],
    57: [('/ [다음] 실습 넷', '/ [다음] 두 환경의 차이')],
    66: [('- 메시지: 다룰 것이 방법인지, 사람의 절차인지, 도구의 정보인지, 비밀값인지에 따라 먼저 볼 자리가 다르다.',
          '- 메시지: 다룰 것이 방법인지, 사람의 절차인지, 도구의 정보인지, 비밀값인지에 따라 먼저 볼 자리가 다르다.')],
}
SCREEN_EDITS = {k: v for k, v in SCREEN_EDITS.items() if v is not None}

SCREEN_REPLACE = {}

LAYOUT_EDITS = {
    27: '풀이 석 줄. 셋째 줄은 「비유」 칸(닮은 점 한 줄, 다른 점 한 줄).',
    55: '두 칸 비교(왼쪽 첫째 실행, 오른쪽 둘째 실행). 두 칸의 첫 줄을 같은 상황으로 맞추고 둘째 칸을 강조한다. 연속 시간 흐름으로 그리지 않는다.',
    39: '왼쪽 설정 두 건(위 내 PC의 VS Code 설정, 아래 포털의 서버 설정), 오른쪽 짚을 점 셋.',
    48: '표 한 장(분류 · 뜻 · 다음 확인). 넷째 행(시간 초과)을 강조한다. 분류 이름은 화면의 원문이며 대본은 뜻으로 말한다.',
    54: '왼쪽 위가 자리표시자가 든 설정, 아래가 값을 직접 적은 설정이 화면에 가려 보이는 모양. 오른쪽 짚을 점 넷. 자리표시자를 강조한다.',
}

NEW_SLIDES = {
    'A': dict(title='같은 쿨러 조치의 두 원문: SOP 단계와 스킬 절차', screen='''
- 유형: 비교
- 메시지: SOP 원문은 사람이 설비에 할 동작과 조건을, 스킬 원문은 에이전트가 부를 도구와 막혔을 때의 행동을 적는다.
- 요소:
  1. 팬 최대 운전 SOP | 1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다 / 2. 팬 속도를 100 %로 올린다(연속 24시간 이내) / 3. 15분 재관측으로 회복을 판정한다 / 승인: 운전원 | 설비에 하는 일
  2. **냉각 긴급 대응 스킬의 절차** | 1. 입력 파일에서 설비 · 경보를 읽는다 / 2. diagnose — 근거가 없으면 보류로 낸다 / 4. evaluate_cards로 후보를 비교한다 / 5. submit_decision으로 판단을 제출한다 | 판단을 만드는 일
- 노트: [짚을 곳] 왼쪽 SOP 원문 단계 셋과 맨 아래 승인 → 오른쪽 스킬 절차(강조) / · SOP: 설비에 하는 동작과 조건 — 운전 모드가 원격 자동인지 확인, 팬 100 %(연속 24시간 이내), 15분 뒤 다시 관측해 회복 판정, 승인할 사람 운전원 / · 스킬: 설비 동작이 없다 — 입력 읽기, 원인 진단(근거 없으면 보류), 후보 비교, 판단 제출 / · 동사가 다르다: 확인하고 올리고 판정하는 일 ↔ 읽고 부르고 내는 일 / · 같은 사건의 절차라도 읽는 이가 다르면 적는 내용이 갈린다 / [다음] 이름 때문에 헷갈리는 Skill
''', layout='왼쪽 SOP 원문(단계 셋 + 승인 줄), 오른쪽 스킬 절차(강조). 두 칸 모두 원문의 단계 번호를 그대로 둔다(스킬 3단계는 업무 DB 확인이라 뺐다).'),
    'B': dict(title='스킬로 남길 일과 한 번의 요청으로 충분한 일', screen='''
- 유형: 표
- 메시지: 같은 일이 되풀이되고 같은 규칙을 따르며 다음 단계가 결과를 읽으면, 그 방법을 스킬로 남긴다.
- 머리: 맡길 일 | 되풀이와 규칙 | 남길 자리
- 요소:
  1. 쿨러 경보의 원인 진단과 조치 비교 | 경보마다 되풀이, 같은 절차 · 결과 항목 | 스킬
  2. 회의록의 결정 · 담당자 · 기한 뽑기 | 회의마다 되풀이, 「미정」 규칙이 같다 | 스킬
  3. 오늘 받은 회의록 한 편의 요약 | 이번 한 번의 목적 | 요청(프롬프트)
  4. 이번 경보에만 붙는 조건 | 이번 실행에만 해당 | 요청에 덧붙임
- 노트: [짚을 곳] 표 네 줄 위에서부터, 가운데 칸 기준 → 오른쪽 칸 자리 / · 쿨러 경보 처리: 경보마다 되풀이, 절차 · 결과 항목이 같고 다음 단계가 결과를 읽는다 → 스킬 / · 회의록에서 결정 · 담당자 · 기한 뽑기: 회의마다 되풀이, 담당 · 기한 없으면 미정이라는 규칙이 같다 → 스킬 / · 오늘 회의록 한 편 요약: 이번 목적에 묶임 → 요청 글 / · 이번 실행에만 붙는 조건(예: 이번엔 부하를 낮추지 않는다고 해 보자): 요청에 덧붙임. 스킬에 적으면 다음 경보에도 따라간다 / · 기준 셋: 되풀이되나, 같은 규칙인가, 다음 단계가 결과를 읽나 / [다음] 같은 틀의 세 스킬
''', layout='표 한 장, 네 행. 위 두 행이 스킬로 남길 일, 아래 두 행이 요청에 둘 일이다. 가운데 칸이 가르는 기준, 오른쪽 칸이 남길 자리.'),
    'D': dict(title='에이전트 프로그램이 물려받지 않는 비밀: 환경변수 정리', screen='''
- 유형: 비교
- 메시지: 워커는 자기 비밀을 환경변수에서 지운 뒤 에이전트를 띄워, 허용 목록을 거치지 않고 DB에 닿는 길을 막는다.
- 요소:
  1. 워커가 가진 값 | 처리할 일을 가져오는 DB 접속 문자열 / 그래프 · DB 비밀번호 / 다른 서비스의 토큰 · API 키 | 띄우기 전에 지움
  2. **에이전트 프로그램이 받는 값** | 이번 실행에만 쓰는 모델 호출 토큰 / 작업 폴더의 서버 설정 / 설정의 비밀값은 실행 직전에 채우고 끝나면 지움 | 실행에 필요한 것만
- 노트: [짚을 곳] 왼쪽 워커가 가진 값 → 오른쪽 에이전트 프로그램이 받는 값(강조) / · 환경변수 = 프로그램이 실행될 때 함께 넘겨받는 설정값 / · 워커: 일을 가져오는 DB 접속 문자열 · 비밀번호를 가졌다. 자기 설정을 읽은 뒤 환경변수에서 지우고 나서 에이전트 프로그램을 띄운다 / · 까닭: DB 접속값이 넘어가면 허용 목록을 거치지 않고 DB에 바로 접속할 수 있다 / · 에이전트 프로그램: 이번 실행에만 쓰는 모델 호출 토큰 + 작업 폴더의 서버 설정. 설정의 비밀값은 실행 직전에 채우고 끝나면 지운다 / · 자리표시자 · 가림 · 환경변수 정리는 노출을 줄이는 방법이지 완전한 보장이 아니다. 무엇이 어느 과정에 전달되는지 확인 / [다음] 응답을 다 받지 못했을 때
''', layout='왼쪽 워커가 가진 값, 오른쪽 에이전트 프로그램이 받는 값(강조). 같은 세 줄로 맞세운다.'),
    'C': dict(title='포털의 정해진 업무 도구와 로컬 VS Code의 직접 연결', screen='''
- 유형: 비교
- 메시지: 포털은 준비된 서버의 검사된 도구만 고르게 하고, 로컬 VS Code는 연결과 범위를 내 설정이 정한다.
- 요소:
  1. 포털의 업무 도구 | 준비된 서버 다섯, 모두 주소(HTTP)로 연결 / 에이전트마다 쓸 서버를 고르고 허용 목록 안에서만 부른다 / 쓰기는 판단 제출뿐, 설비 명령은 승인 뒤 시스템 | 미리 정한 범위
  2. **로컬 VS Code의 직접 연결** | 설정 파일에 서버를 직접 적는다(stdio · HTTP) / 서버가 내 계정으로 돌아 내 파일 · Git에 닿는다 / 읽을 폴더 · 읽기 전용 · 도구 실행 허락을 내가 정한다 / 비밀값을 설정에 그대로 적지 않는다 | 내가 정하는 범위
- 노트: [짚을 곳] 왼쪽 포털 → 오른쪽 로컬 VS Code(강조) / · 포털: 준비된 서버 다섯 모두 주소(HTTP), 에이전트마다 쓸 서버를 고르고 허용 목록 안의 도구만, 쓰기는 판단 제출뿐 · 설비 명령은 사람 승인 뒤 시스템 / · 로컬 VS Code: 설정 파일에 서버를 직접(stdio 명령 · HTTP 주소), 서버가 내 계정으로 돌아 내 파일 · Git 저장소에 닿는다 / · 그래서 읽을 폴더 · 읽기 전용 · 도구 실행 허락 · 비밀값 관리를 내 설정과 내 확인이 정한다 / · 원리는 같다: 필요한 도구만, 필요한 범위만. 다른 것은 그 범위를 누가 미리 정해 두느냐 / [다음] 실습
''', layout='왼쪽 포털, 오른쪽 로컬 VS Code(강조). 첫 줄 연결 방식 → 둘째 줄 닿는 범위 → 셋째 줄 누가 범위를 정하나로 맞세운다.'),
    'P62a': dict(title='포털에서 스킬을 만들어 에이전트에 붙이고 / 답의 차이 확인하기', screen='''
- 유형: 간지
- 구분: 실습
- 노트: [짚을 곳] 간지 제목 / · 이론에서 읽은 스킬 원문과 여섯 가지가 포털의 스킬 탭에 그대로 들어 있다 / · 스킬이 에이전트의 답을 실제로 바꾸는지 직접 붙였다 떼어 본다 / [다음] 이 실습에서 알아볼 물음
''', layout='실습 간지(제목 · 구분만).'),
    'P62b': dict(title='나의 스킬이 바꾸는 답과 근거', screen='''
- 유형: 강조
- 문장: 근거와 확인할 항목을 남기라는 스킬 한 편은 / 답의 어디를 바꿀까?
- 메시지: 기준 스킬을 읽고 나의 스킬을 써서 에이전트에 붙였다 떼며, 같은 질문의 답과 근거를 견준다.
- 노트: [짚을 곳] 가운데 질문의 「답의 어디」 / · 기준 스킬의 SKILL.md에서 목적 · 호출 조건 · 입력 · 출력 · 순서 · 예외를 찾아 읽는다 / · 쿨러 이상 답에 근거와 확인할 항목을 꼭 남기게 하는 나의 스킬을 쓴다 / · 앞에서 만든 나의 에이전트에 붙이기 전 · 붙인 뒤 · 뗀 뒤에 같은 질문을 물어 답 · 근거 · 처리 과정을 견준다 / · 차이가 정말 스킬에서 왔는지가 물음 / [다음] 둘째 실습
''', layout='가운데 질문 한 문장(두 줄), 아래 메시지. 요소 없음.'),
    'P63a': dict(title='포털의 업무 도구를 직접 호출하고 / 에이전트 근거와 대조하기', screen='''
- 유형: 간지
- 구분: 실습
- 노트: [짚을 곳] 간지 제목 / · 이론의 서버 · 도구 목록 · 입력 스키마 · 응답이 포털의 도구 연결 화면에 그대로 보인다 / · 도구를 직접 불러 본 값과 에이전트 답의 근거를 잇는다 / [다음] 이 실습에서 알아볼 물음
''', layout='실습 간지(제목 · 구분만).'),
    'P63b': dict(title='도구가 돌려준 값과 답의 근거', screen='''
- 유형: 강조
- 문장: 도구가 돌려준 값은 / 답의 어느 근거가 되었을까?
- 메시지: 업무 도구를 직접 불러 반환값을 보고, 에이전트 답의 근거를 호출 기록의 입력 · 반환값과 대조한다.
- 노트: [짚을 곳] 가운데 질문의 「어느 근거」 / · 도구 연결 화면: 지식 그래프 · 업무 DB · 판단 도구 서버의 연결 상태와 도구 목록(이름 · 입력 형식)을 열고, 도구를 직접 시험 호출해 반환값을 본다 / · 그 도구를 쓰는 에이전트에게 질문하고 호출 기록에서 도구 이름 · 입력 · 반환값을 찾는다 / · 설비 지식에서 온 내용과 지금의 업무 조회 결과를 가르고, 반환값마다 답의 어느 근거에 쓰였는지 잇는다 / [다음] 셋째 실습
''', layout='가운데 질문 한 문장(두 줄), 아래 메시지. 요소 없음.'),
    'P64a': dict(title='외부 MCP를 연결하고 / 내 조회 도구를 만들어 조합하기', screen='''
- 유형: 간지
- 구분: 실습
- 노트: [짚을 곳] 간지 제목 / · 자리를 내 PC의 VS Code로 옮긴다. 포털에서는 준비된 연결을 썼고, 이번에는 직접 연결하고 도구도 직접 만든다 / · 이론의 도구 정의(이름 · 설명 · 입력 스키마), stdio · HTTP 연결, 실패 분류와 출처를 쓴다 / [다음] 이 실습에서 알아볼 물음
''', layout='실습 간지(제목 · 구분만).'),
    'P64b': dict(title='외부 서버와 내 도구를 함께 쓸 때의 출처', screen='''
- 유형: 강조
- 문장: 외부 서버와 직접 만든 도구를 함께 부르면 / 결과의 출처는 어떻게 남을까?
- 메시지: 파일 · Git · 시간 서버를 연결하고 내 조회 도구를 만들어, 한 요청에서 함께 부른 결과를 확인한다.
- 노트: [짚을 곳] 가운데 질문의 「출처」 / · 파일 · Git · 시간 MCP를 연결하고 접근 범위를 정한 뒤 도구마다 입력 · 반환값을 본다 / · 제공 서버 골격에 점검 자료 조회 함수를 구현해 MCP 도구로 내보내고 기존 에이전트에서 부른다 / · 파일 내용 · 변경 이력 · 기준 시각을 조합한 결과에서 출처와 조회 실패가 어떻게 드러나는지가 물음 / [다음] 넷째 실습
''', layout='가운데 질문 한 문장(두 줄), 아래 메시지. 요소 없음.'),
    'P65a': dict(title='회의 내용을 실제 후속 업무로 전환하기', screen='''
- 유형: 간지
- 구분: 실습
- 노트: [짚을 곳] 간지 제목 / · 다른 축인 스킬로 돌아온다: 포털에서 써 본 스킬과 같은 구조로 회의록용 SKILL.md를 직접 쓴다 / · 스킬을 쓸 때 지킬 네 가지(설명, 실제 도구 이름, 막혔을 때, 결과 항목)를 그대로 쓴다 / [다음] 이 실습에서 알아볼 물음
''', layout='실습 간지(제목 · 구분만).'),
    'P65b': dict(title='회의록에서 다음 행동을 뽑는 스킬', screen='''
- 유형: 강조
- 문장: 회의록에 담당자가 없는 일은 / 작업 목록에 어떻게 남길까?
- 메시지: 회의록에서 결정 · 담당자 · 완료 시점을 뽑는 SKILL.md를 써서, 다음 행동이 분명한 작업 목록을 만든다.
- 노트: [짚을 곳] 가운데 질문의 「담당자가 없는 일」 / · 예제 회의록을 받아 결정사항 · 담당자 · 완료 시점을 뽑는 SKILL.md를 쓴다 / · 담당자와 기한이 없는 항목은 지어내지 않고 미정으로 표시한다 / · Markdown · JSON 작업 목록을 만들어 검토한다. 요약에서 끝내지 않고 다음 행동이 분명한지가 물음 / [다음] 마지막 실습
''', layout='가운데 질문 한 문장(두 줄), 아래 메시지. 요소 없음.'),
    'P66a': dict(title='내 Notion 학습노트로 / 출제·채점하는 퀴즈 에이전트 만들기', screen='''
- 유형: 간지
- 구분: 실습
- 노트: [짚을 곳] 간지 제목 / · 내 학습노트로 문제를 내고 채점하는 퀴즈 에이전트를 만든다 / · 앞에서 익힌 MCP 연결 원리로 Notion을 읽는다 / [다음] 이 실습에서 알아볼 물음
''', layout='실습 간지(제목 · 구분만).'),
    'P66b': dict(title='노트에 없는 질문을 받은 퀴즈 에이전트', screen='''
- 유형: 강조
- 문장: 노트에 없는 질문을 받은 퀴즈 에이전트는 / 무엇을 해야 할까?
- 메시지: 내 Notion 학습노트를 MCP로 읽어 문제를 내고 채점하며, 원문 근거로 답을 되짚는다.
- 노트: [짚을 곳] 가운데 질문의 「노트에 없는 질문」 / · 학습노트 페이지를 골라 MCP 읽기 연결로 읽는다 / · 문항 · 정답 기준 · 해설 · 원문 근거를 만들되 답하기 전에는 정답과 해설을 숨긴다 / · 답을 받으면 정답 · 부분 정답 · 오답과 이유를 알리고 원문을 다시 열어 확인, 다음 문항 · 틀린 개념 재도전, 풀이 기록 저장 / · 표현만 다른 정답 · 불완전한 답 · 노트에 없는 질문에서 근거가 모자라면 출제 · 채점을 보류하는지가 물음 / [다음] 실습 뒤 복습
''', layout='가운데 질문 한 문장(두 줄), 아래 메시지. 요소 없음.'),
}

# 옛 39 · 48은 화면 내용을 통째로 바꾼다
NEW_SCREEN = {
    39: '''- 유형: 코드
- 메시지: 설정에서 stdio 서버는 실행할 명령으로, HTTP 서버는 접속할 주소로 적혀 있어 연결 방식이 그대로 드러난다.
- 코드: 내 PC의 VS Code 설정(.vscode\\/mcp.json) / "servers": { /   "filesystem": { "type": "stdio", /     "command": "python", /     "args": ["서버\\/파일시스템_서버.py", /              "--read-only", "업무자료"] } } /  / 포털의 서버 설정(mcpServers) / "neo4j": { "type": "url", /   "url": "http:\\/\\/dmn-mcp:8198\\/neo4j\\/mcp", /   "transport": "streamable_http" }
- 요소:
  1. **command · args** | 실행할 프로그램과 인자를 적는다. stdio 서버이다. 인자가 읽을 범위도 정한다.
  2. **url** | 접속할 주소를 적는다. Streamable HTTP 서버이다.
  3. 포털의 등록 | 명령형 서버는 받지 않고 주소로 접속하는 서버만 등록한다.
- 노트: [짚을 곳] 왼쪽 위 VS Code 설정(command · args) → 아래 포털 설정(url) → 오른쪽 셋째 항목 / · stdio 서버는 실행할 명령과 인자(명령에 덧붙여 넘기는 값)로 적힌다. VS Code가 이 명령으로 서버를 직접 띄운다. 인자의 읽기 전용 표시 · 읽을 폴더가 서버가 닿을 범위를 정한다 / · HTTP 서버는 접속할 주소로 적힌다. 이미 떠 있는 서버에 접속 / · 포털은 명령형 서버를 등록하지 않는다 — 남이 적은 명령을 포털 안에서 띄우지 않으려고. 명령으로 띄울 서버는 쓸 PC의 설정에 두거나 HTTP로 띄워 주소를 등록 / · 설정 한 줄이 연결의 길과 서버가 도는 자리를 정한다 / [다음] 스킬과 MCP를 한 실행에 놓기
''',
    48: '''- 유형: 표
- 메시지: 연결 검사는 실패를 빈 성공으로 넘기지 않고, 무엇이 막혔는지를 분류와 사람이 읽는 사유로 돌려준다.
- 머리: 분류 | 뜻 | 다음에 확인할 곳
- 요소:
  1. config | 설정 형식이 맞지 않는다 | 주소 · 연결 방식
  2. refused | 접속이 거절됐다 | 서버 상태 · 주소 · 포트
  3. unreachable | 이름 해석 또는 네트워크 접근 실패 | 이름 · 네트워크 경로
  4. **timeout** | 제한 시간 안에 응답을 못 받았다 | 처리 상태 · 응답 지연
  5. auth | 인증이 만료되었거나 없다 | 자격 증명 · 필요한 권한
  6. not_mcp | 주소의 경로가 MCP 끝점이 아니다 | 접속 주소 · 끝점
- 노트: [짚을 곳] 표 여섯 줄 위에서부터, 왼쪽 분류 → 오른쪽 다음에 확인할 곳 / · 원칙: 목록을 못 받으면 빈 목록을 성공처럼 돌려주지 않고 분류 + 사람이 읽는 사유로 실패를 알린다 / · config: 연결 방식 · 주소 모양이 틀림. 명령형(stdio) 서버는 그 앞의 형식 검사에서 등록을 거절 / · refused 접속 거절 → 서버가 켜졌나 · 주소 · 포트(주소에 붙는 번호). unreachable → 이름 해석(서버 이름으로 주소 찾기) · 네트워크 경로 / · timeout → 정해진 몇 초 안에 응답 없음, 서버가 느리거나 방화벽. auth → 토큰 같은 자격 증명이 없거나 만료. not_mcp → 주소의 경로가 MCP 끝점이 아님 / · 분류가 고칠 곳을 좁힌다 / [다음] 셋째 겹, 허용 목록
''',
}

# 새 장 번호 → 제작 기준(근거만)
S = '사실표 05-08'
BASIS = {
    1: '실라버스 「통합반 온라인 44H」 06회차 주제와 59~66행. 큰 제목은 회차의 두 축(지침의 재사용, 외부 시스템 연결)을 명사구로 썼다. MCP는 배우는 표준이라 정식 이름을 쓴다.',
    2: '실라버스 「통합반 온라인 44H」 59~66행. 카드 1~3은 이론 59 · 60 · 61행, 카드 4는 실습 62~66행.',
    3: '실라버스 59~66행. 단원 1 · 2 = 59행, 3 · 4 · 5 = 60행, 6 · 7 = 61행, 8 = 실습 62~66행.',
    4: '실라버스 59행 「Agent Skill의 목적, SKILL.md의 작업 목적·호출 조건·입력·출력·순서·예외 지침」.',
    5: f'도구 수: `it/dmn-mcp/dmn_mcp/server.py`의 `@mcp.tool` 17개, `it/enterprise-mcp/enterprise_mcp/server.py`의 `@mcp.tool` 14개. 냉각 긴급 대응 에이전트의 서버: `it/supabase/seed.sql` users `agent:cooling` tools(neo4j · enterprise · hyd-dmn). 「도구만 있고 스킬이 없으면 무엇을 어떤 순서로 부를지 에이전트가 처음부터 정한다」: {S} §6.2.3. 다음 단계가 결과를 항목 이름으로 읽는다: {S} §5.2.4.',
    6: f'실행 고리 그림 `figures/만들기_삽화.py` loop(True). 처리 건이 열리자 지침 파일을 먼저 읽고 원인 진단을 그 뒤에 부른 기록: {S} §5.1.2 기록 ①. 지침을 둬도 실행이 같아지지는 않는다(두 기록의 호출 차이): §5.1.2 기록 ① · ②.',
    7: f'Agent Skill의 정의와 SKILL.md 구성(머리말 name · description + 본문, 참고 자료 · 스크립트): https://agentskills.io/specification, {S} §6.1.1. 스킬 `cooling-emergency-response`: `it/supabase/seed.sql` tenant_skills. 이 덱의 「스킬」은 에이전트 스킬이고 그래프의 Skill 클래스는 「조치 방법」으로 부른다({S} §6.1.2).',
    8: f'작업 폴더의 자리(context/task.json · .claude/skills/<이름>/SKILL.md · output/result.json): `it/agent-worker/worker/workspace.py` RESULT_FILE, `it/process/procsvc/agents_store.py` SKILL_ROOTS · instructions, {S} §5.1.2 기록 ② · §6.1.1. 스킬 본문은 포털 DB(tenant_skills)에 보관되고 실행 때 파일로 쓰인다: `it/portal/www/agents.js` 스킬 상세 문구.',
    9: '원문 `it/supabase/seed.sql` tenant_skills `cooling-emergency-response`. 제목 · description 끝의 구분 꼬리 「(시나리오 A)」는 화면에서 뺐고 description은 화면 폭에 맞춰 두 줄로 끊었다. 그 밖의 문장은 원문 그대로다. 원문 표기 「쿨러 과열 경보」 「추천 카드」는 이 과정의 이름(쿨러 성능 저하 경보, 추천안)과 다르므로 노트에서 대응을 밝힌다.',
    10: '이름 규칙 `SKILL_NAME_RE = ^[a-z0-9][a-z0-9-]{0,63}$`(`it/process/procsvc/agents_store.py`), 머리말 name이 폴더 이름과 다르면 저장 거절(`it/process/procsvc/agent_authoring.py` 「문서 머리의 name(…)이 스킬 폴더 이름(…)과 다릅니다」). 짧은 이름 · 설명을 먼저 보이고 본문은 필요할 때 읽는 방식: https://agentskills.io/client-implementation/adding-skills-support. 배정된 스킬만 실행에 들어간다: `it/portal/www/agents.js` 「붙이지 않은 스킬은 어떤 실행에도 들어가지 않습니다」.',
    11: f'원문 `it/supabase/seed.sql` cooling-emergency-response 절차 1~5. 화면 폭 · 높이에 맞춰 2단계 괄호 풀이 「(top cause)」 「(권장 조치)」 「(__deferred__)」, 4단계의 「예측 유온 · 성과 지표 득실」과 둘째 줄 괄호, 5단계 인자 목록(「…」)을 줄였다. 뜻은 원문과 같다. 「예외」는 별도 절이 아니라 절차 안 문장이다({S} §6.5).',
    12: f'실라버스 59행의 여섯 항목(작업 목적 · 호출 조건 · 입력 · 출력 · 순서 · 예외)을 실제 파일의 자리에 댄 그림. 실제 파일은 머리말 + 제목 + 요약 + 절차 + 결과이고 「호출 조건」 · 「예외」 절이 따로 없다({S} §6.1.1 · §6.5). 그림 `figures/만들기_삽화.py` skilldoc().',
    13: f'diagnose 설명 「withheld=true이면 근거 미확인 또는 지지 근거 없음이므로 원인을 임의로 골라 후속 조치 판단을 하지 않는다」(`it/dmn-mcp/dmn_mcp/server.py` diagnose). 실제 응답 `"withheld": false` · `"freshness": {{"ok": true, …}}`와 원인 1순위 cause:cooler-fin-fouling: {S} §5.1.2 기록 ②. 보류의 형식(상태 · 이유 · 증거)은 5회차 멈춤 조건의 이름으로 받는다.',
    14: f'결과 절 원문(`seed.sql`)과 실제 출력 `output/result.json`의 최상위 키 · 값(cause:cooler-fin-fouling · recommended skill:sop-cool-11 · DEC-1010-056-0972): {S} §5.2.4 · §6.1.1, 기록 ②(경보 ALT-hyd01-0025-b8ed). 고장 유형은 지금 그래프의 같은 노드 id `fm:cooler-cooling-loss`(이름 「쿨러 냉각 성능 상실」, 덤프 `workspace/강의제작/제작도구/근거/2026-11-03_5-6회차_인계/실측/그래프_노드.txt`)로 적었다.',
    15: '실라버스 59행 「SOP의 현장 작업 절차와 에이전트 실행 지침의 차이」 「재사용 지침과 한번의 프롬프트를 구분」.',
    16: '경보 11:13:08 · 운전원 11:14:56: `workspace/강의제작/지침/사실표/통합반_01일차_기술사실표.md` 「같은 말 · 같은 값」 대표 값. 스킬 범위 「승인 전에는 조회 · 계산만 한다」: 스킬 원문(`seed.sql`). SOP-COOL-11 「팬 속도를 100 %로 올린다」: `it/portal/www/samples/HM-8_cooler-fan-manual.md` SOP-COOL-11. 그림 `figures/만들기_삽화.py` twoproc().',
    17: f'SOP와 에이전트 스킬의 구분(읽는 이 · 적는 것 · 예): {S} §6.1.2. SOP-COOL-11: HM-8 매뉴얼. 냉각 대응 에이전트는 판단을 만들고 제출한다: `it/supabase/seed.sql` users agent:cooling goal.',
    18: '실라버스 59행 「SOP의 현장 작업 절차와 에이전트 실행 지침의 차이」. SOP 원문: `it/portal/www/samples/HM-8_cooler-fan-manual.md` SOP-COOL-11(단계 셋 · 「승인: 운전원」), 그래프 skill:sop-cool-11 HAS_STEP 셋 · APPROVED_BY role:operator(덤프 `workspace/강의제작/제작도구/근거/2026-11-03_5-6회차_인계/실측/그래프_관계.txt`). 셋째 단계의 「HM-8.6 회복 판정」은 「회복을 판정한다」로 줄였다. 스킬 쪽은 `seed.sql` cooling-emergency-response 절차 1 · 2 · 4 · 5를 줄였다(3단계 업무 DB 확인은 뺐다).',
    19: f'조치 방법(Skill 클래스) · skill:sop-cool-11 · HAS_STEP · APPROVED_BY · 근거 매뉴얼(REFERS_TO): 덤프 그래프_관계.txt, {S} §6.1.2. 둘은 저장소에서 서로 가리키지 않는다({S} §6.1.2 「서로의 관계」).',
    20: f'절차 1단계가 입력에서 asset · pattern · alert.alertId · incident를 읽는다: 스킬 원문. 스킬 본문은 조치 방법 노드를 직접 가리키지 않는다: {S} §6.1.2. 냉각 효율 46.2 %: 사실표 01 「같은 말 · 같은 값」 대표 값. 납기 5.98 h(`mes_orders` facts.due_in_h): {S} §6.2.2. 후보 넷: HM-8 매뉴얼 SOP-COOL-11~14.',
    21: f'두 실행의 경보 · 판단 번호: {S} §5.1.2 기록 ①(ALT-hyd01-0014-e0a1 → DEC-1010-002-408b) · 기록 ②(ALT-hyd01-0025-b8ed → DEC-1010-056-0972), 두 기록 모두 스킬 cooling-emergency-response. 둘째 실행의 조치 효과 예측(forecast_actions 세 번): 기록 ②. 그림 `figures/만들기_삽화.py` reuse().',
    22: '실라버스 59행 「재사용 지침과 한번의 프롬프트를 구분」. 보관된 스킬을 실행 준비 때 작업 폴더에 쓴다: `it/process/procsvc/agents_store.py` instructions, `it/portal/www/agents.js` 「붙은 에이전트가 실행될 때 작업 폴더에 이 문서가 SKILL.md 로 들어갑니다」. 프롬프트 템플릿 재사용은 [일반] 서술이다.',
    23: '실라버스 59행 「재사용 지침과 한번의 프롬프트를 구분」. 쿨러 경보의 절차 · 결과 항목: `it/supabase/seed.sql` cooling-emergency-response, 회의록의 결정 · 담당자 · 기한 · 미정 규칙: 실라버스 65행. 넷째 줄의 「이번 경보에만 붙는 조건」은 대본이 가정으로 드는 예다. 가르는 기준 셋(되풀이 · 같은 규칙 · 다음 단계가 읽는 결과)은 7 · 14 · 22장의 내용을 판단 기준으로 묶은 [일반] 서술이다.',
    24: '`it/supabase/seed.sql` users agent:cooling · agent:pm-plan · agent:spare-buy의 tools와 agent_skills, 스킬 셋의 이름 · description(구분 꼬리 「(시나리오 A · B · C)」는 뺐다). 「시나리오 에이전트 셋」: 같은 파일의 주석. 「붙이지 않은 스킬은 어떤 실행에도 들어가지 않습니다」: `it/portal/www/agents.js`. 서버의 정의는 다음 단원에서 하고 여기서는 「절차가 부를 도구가 있는 곳」으로 읽는다.',
    25: '스킬을 쓸 때의 네 가지: description이 호출 조건, 절차의 도구 이름은 연결된 실제 이름, 막혔을 때의 행동, 결과 항목 이름 고정 — 스킬 원문(`seed.sql`)과 https://agentskills.io/specification. 지어내지 않기: `it/process/procsvc/work_rules.py` _NO_INVENTION. 남는 후보가 없을 때(후보 0개 · 모두 규정상 제외)를 그대로 내는 결과: `it/dmn-mcp/dmn_mcp/tools.py` read_outcome(no_candidates · no_feasible_option).',
    26: '실라버스 60행 「MCP의 Host·Client·Server·Tool 구성」.',
    27: f'절차 2단계 원문 「hyd-dmn `diagnose(asset, pattern, alert_id)`」: 스킬 원문. 스킬은 방법을 말하고 도구는 hyd-dmn MCP 서버가 실행한다: {S} §6.2.3.',
    28: '[일반] 표준 프로토콜의 필요(조합 N × M 대 구현 N + M). 셋과 셋은 개념도를 위한 가정한 수다. 그림 `figures/만들기_삽화.py` nm().',
    29: f'MCP의 정의와 JSON-RPC 2.0: https://modelcontextprotocol.io/specification/2025-06-18/architecture, {S} §6.2.1. 지식 그래프 서버가 공개 서버(mcp-neo4j-cypher)의 읽기 · 구조 도구 계약을 따른다: `common/hydcommon/neo4j_mcp.py` 머리말. 비유는 이 덱에서 이 한 곳에만 둔다.',
    30: f'네 구성요소와 일대일 연결: MCP 명세 architecture, {S} §6.2.1. 도구 수 17 · 14: `dmn_mcp/server.py` · `enterprise_mcp/server.py`의 `@mcp.tool`. neo4j 읽기 도구 둘: `common/hydcommon/neo4j_mcp.py`. hyd-dmn이 그래프와 시계열 DB를 읽는다: {S} §5.2.1(라벨은 대표 시스템 하나만). 그림 `figures/만들기_삽화.py` mcp_parts().',
    31: f'네 구성요소의 정의: MCP 명세 architecture. 호스트 = 처리 건마다 워커가 띄우는 에이전트 프로그램, 클라이언트 = 작업 폴더 `.mcp.json`의 서버 항목마다 하나: `it/agent-worker/worker/bridge.py` 머리말, {S} §6.2.1. 포털 도구 시험 화면의 클라이언트: `it/process/procsvc/mcp_check.py`.',
    32: '서버 다섯: `it/supabase/seed.sql` tenants.mcp, `it/process/procsvc/mcp_registry.py` BASE_SERVERS. 도구 수 17(`it/dmn-mcp/dmn_mcp/server.py` `@mcp.tool`), 14 · 4 · 3(`it/enterprise-mcp/enterprise_mcp/server.py` `@mcp.tool` · TOOLSETS), neo4j 읽기 둘(`common/hydcommon/neo4j_mcp.py` — 쓰기 도구 없음, 실행 전 EXPLAIN으로 읽기 확인). 에이전트에 붙이지 않는 메일 서버(effects-mcp)는 넣지 않았다.',
    33: '실라버스 60행 「도구 목록 발견, 입력 스키마와 응답, stdio·HTTP 연결 방식」.',
    34: 'initialize · initialized · tools/list(페이지 이어 받기) · tools/call: https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle, https://modelcontextprotocol.io/specification/2025-06-18/server/tools. 포털 연결 검사는 초기화 + 목록 받기까지: `it/process/procsvc/mcp_check.py` 머리말, PROTOCOL_VERSION 2025-06-18.',
    35: '포털은 호출 직전에 서버에서 목록을 다시 받아 판정한다: `it/process/procsvc/mcp_check.py` 머리말. 구매 판단 도구 셋(purchase_context · evaluate_purchase · submit_purchase): `it/dmn-mcp/dmn_mcp/server.py`. 목록 변경 · 허용 구분: MCP 명세 server/tools.',
    36: 'part_quotes 정의: `it/enterprise-mcp/enterprise_mcp/server.py` part_quotes(설명은 원문 앞뒤를 「…」로 줄였다), 항목 이름 inputSchema: MCP 명세 server/tools, annotations READ. JSON Schema의 default는 안내다: https://json-schema.org/understanding-json-schema/reference/annotations.',
    37: f'기록 ②의 호출 `mcp__hyd-dmn__diagnose`와 입력: {S} §5.1.2 기록 ②. 같은 이름 도구가 두 서버에(mcp__enterprise-purchase__part_quotes): {S} §6.2.2. 포털 도구 시험의 입력 검증 「도구 입력이 서버가 정한 입력 형식과 맞지 않습니다」: `it/process/procsvc/mcp_check.py` _argument_problem. diagnose의 입력 셋: `it/dmn-mcp/dmn_mcp/server.py` diagnose.',
    38: f'mes_orders 응답: {S} §6.2.2 「응답의 실제 모양」(facts는 세 값만, 시각은 초 아래를 줄였다). 응답 봉투 result ok · error: `it/dmn-mcp/dmn_mcp/tools.py` enveloped, enterprise 서버도 같다. 도구 오류 표시(isError)와 봉투 오류를 함께 보는 포털: `it/process/procsvc/mcp_check.py` is_error.',
    39: f'호스트가 허용 목록으로 도구 사용을 가린다: `it/agent-worker/worker/settings.py` DEFAULT_ALLOWED_TOOLS · run_allowed_tools, {S} §6.3.1.',
    40: f'stdio · Streamable HTTP: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports, {S} §6.2.1. 포털의 수업 도구 서버 다섯은 모두 streamable_http: `it/supabase/seed.sql` tenants.mcp. 실행 안에서 워커가 붙이는 stdio 창구(결과 파일 검사 · 질문 창구): `it/agent-worker/worker/bridge.py` 머리말, `worker/result_check.py`, `worker/question_tools.py`. 로컬 VS Code 실습 서버는 stdio: `workspace/강의제작/산출물/통합반/실습/06회차/랩/06일차_실습2_MCP서버조합/코드/설정_작성.md`. 그림 `figures/만들기_삽화.py` transports().',
    41: '포털 설정 neo4j `{"type":"url","url":"http://dmn-mcp:8198/neo4j/mcp","transport":"streamable_http"}`: `it/supabase/seed.sql` tenants.mcp. VS Code 설정 `.vscode/mcp.json` servers · type stdio · command · args(`--read-only`, 읽을 폴더): 실습 2 `코드/설정_작성.md`(경로는 화면 폭에 맞춰 상대 경로로 줄였다), https://code.visualstudio.com/docs/copilot/customization/mcp-servers. 포털은 명령형 등록을 거절한다: `it/process/procsvc/mcp_check.py` STDIO_REFUSED.',
    42: '실라버스 60행 「Skill은 수행 방법, MCP는 연결된 실행 도구라는 역할을 명확히 구분한다」.',
    43: f'스킬이 diagnose → evaluate_cards → submit_decision 순서를 말하고 그 도구는 hyd-dmn 서버가 실행한다: {S} §6.2.3. 스킬 묶음의 실행 스크립트: https://agentskills.io/specification.',
    44: f'「스킬만 있고 도구가 없으면 방법만 알고 못 한다. 도구만 있고 스킬이 없으면 무엇을 어떤 순서로 부를지 에이전트가 처음부터 정한다」, 시험 실행에서 enterprise가 없으면 업무 DB 값을 받지 못함: {S} §6.2.3.',
    45: f'기록 ②의 호출과 출력 요지(diagnose → cause:cooler-fin-fouling, mes_orders · qms_lots → MO-0930-0412 · L-0930-A17, evaluate_cards 응답 128,468자 본문 미전달, forecast_actions 세 번, submit_decision → DEC-1010-056-0972): {S} §5.1.2 기록 ②. 실제 호출 순서는 diagnose → evaluate_cards → mes_orders · qms_lots → 예측 셋 → submit_decision이고 표의 행은 스킬 단계 순서다. 제출 도구가 서버 안에서 후보 비교를 다시 한다: `it/dmn-mcp/dmn_mcp/tools.py` decide(do_submit=True).',
    46: '실라버스 61행 「도구별 읽기 · 쓰기 권한」.',
    47: '읽는 도구 mes_orders(readOnlyHint true): `it/enterprise-mcp/enterprise_mcp/server.py`. 쓰는 도구 send_mail(readOnlyHint false): `it/effects-mcp/effects_mcp/server.py`. 읽기의 노출 위험: https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices.',
    48: f'readOnlyHint: MCP 명세 server/tools(ToolAnnotations). hyd-dmn 17개 가운데 READ 15 · WRITE 2(submit_decision · submit_purchase), enterprise 14개 모두 READ: `it/dmn-mcp/dmn_mcp/server.py` · `it/enterprise-mcp/enterprise_mcp/server.py`. 이름까지 보는 판정: `it/process/procsvc/mcp_check.py` read_only_verdict. 쓰기 표시 도구는 도구 시험에서 거절: 같은 파일(not_read_only). 읽기 전용 계정 · 읽기 트랜잭션: {S} §6.3.1 「읽기 전용 보장 겹」, enterprise `/healthz`.',
    49: '등록 · 고치기 = 형식 검사 → 실제 연결 검사 → 실패면 저장 안 함, 붙일 수 있음 = 마지막 검사 ok · 설정 지문 같음 · 읽기 도구(또는 따로 확인한 읽기 도구) 하나 이상: `it/process/procsvc/mcp_registry.py` 머리말. 판정 `mcp_check.py` read_only_verdict · confirmable. 워커는 검사 통과한 읽기 도구 이름만 허용: `it/agent-worker/worker/settings.py` run_allowed_tools. 수업 단계에서는 서버 등록이 열리지 않는다: `it/process/procsvc/course_policy.py` tool_servers.register. 그림의 part_quotes · send_mail은 표시의 예다. 그림 `figures/만들기_삽화.py` gates().',
    50: '실패 분류 error_kind와 사유 원문: `it/process/procsvc/mcp_check.py` _http_error(refused · unreachable · timeout · auth · not_mcp), config(주소 · transport 형식), 명령형 등록 거절 STDIO_REFUSED(normalize). 「폴백 · 빈 성공은 없다」: 같은 파일 머리말. 열한 분류 가운데 서버를 찾고 접속하는 여섯만 실었다.',
    51: '허용 목록 원문 DEFAULT_ALLOWED_TOOLS(`it/agent-worker/worker/settings.py`): neo4j 둘 · 기준 서버 넷의 별표 · Read · Write · Edit · Skill. 셸 도구 Bash · PowerShell은 늘 막는다(BLOCKED_SHELL_TOOLS). 새로 등록한 서버는 읽기로 판정된 이름만: run_allowed_tools. neo4j 서버는 쓰기 도구가 없고 조회문을 실행 전에 읽기인지 확인한다: `common/hydcommon/neo4j_mcp.py` read. 목록에 없는 요청은 권한 검사로 간다: 사실표 05-08 §5.2.3. 영문 Allowlist는 [일반] 보안 용어.',
    52: '서버 설명 「submit_decision·submit_purchase는 판단 카드를 쓰며(process /api/decisions), 설비 명령은 어디서도 나가지 않는다」: `it/dmn-mcp/dmn_mcp/server.py`. send_mail은 에이전트 서버 목록(tenants.mcp)에 없다: `it/supabase/seed.sql`, 사실표 05-08 §6.3.1.',
    53: f'최소 권한 원칙 [일반]. TOOLSETS maintenance 4(pm_status · maintenance_windows · cmms_history · mes_orders) · purchasing 3(spare_stock · part_quotes · scm_suppliers), 나눈 서버에 자유 SQL 없음: `it/enterprise-mcp/enterprise_mcp/server.py`, {S} §6.2.2. 에이전트와 연결 서버: `it/supabase/seed.sql` users tools.',
    54: '실라버스 61행 「파일 접근 범위, 인증 정보, 실패 · 시간 초과와 근거 표시」.',
    55: '지시 원문: `it/process/procsvc/work_rules.py` _WORKSPACE(둘째 인용은 괄호를 뺐다). 결과 경로: `it/agent-worker/worker/workspace.py` RESULT_FILE. 폴더 분리는 OS 접근 통제가 아니다: 같은 파일 머리말. 홈 디렉터리에 무엇이 있는지는 [일반] 서술이다.',
    56: '자리표시자 ${SECRET:KEY}, 설정 예 원문, 실행 직전 채움, 지문은 자리표시자가 든 설정으로 계산: `it/process/procsvc/mcp_secrets.py` 머리말. 값이 없으면 그 서버를 실행에서 뺀다: `it/agent-worker/worker/bridge.py` 머리말 ①. 헤더 비밀값 가림 `********`: `it/process/procsvc/mcp_check.py` masked · MASK(화면은 별표를 전각으로 적었다).',
    57: '워커가 자기 설정을 읽은 뒤 비밀 이름의 환경변수를 지우고 에이전트 프로그램을 띄운다, 에이전트 프로그램은 실행마다 받은 관문 토큰으로만 모델을 부른다: `it/agent-worker/worker/env_guard.py` 머리말 · DEFAULT_BLOCK · BLOCK_SUFFIXES. 서버 설정의 비밀값은 실행 직전에 채우고 실행 뒤 지운다: `it/agent-worker/worker/bridge.py` 머리말 ⓪ · ① · cleanup.',
    58: '첫째 실행 결과 128,466자 · 「필요한 항목만 좁혀 다시 뽑겠습니다」: 사실표 05-08 §5.1.2 기록 ① · §6.3.4. 둘째 실행 결과 128,468자 · 마지막 메시지의 못 읽은 범위: 기록 ② · §6.3.4. 기록 ①은 그 말 뒤 다음 호출이 판단 제출이라 재조회 성공은 확인되지 않는다. 잘림이 모든 실행에서 일어나는지는 확인되지 않아(§12) 「두 실행에서」로만 쓴다.',
    59: '응답 봉투(result ok · error)와 지시 「조회 실패와 값 없음을 구분합니다」: `it/dmn-mcp/dmn_mcp/tools.py` enveloped, `it/process/procsvc/work_rules.py` _NO_INVENTION. 시간 제한: 업무 · 시계열 조회 5초(`common/hydcommon/fabric.py` statement_timeout), 포털 도구 호출 기본 15초(`it/process/procsvc/mcp_api.py` CALL_TIMEOUT), 분류 timeout(`mcp_check.py`). 잘림 표시와 원래 크기: `mcp_check.py` truncated. 한도의 수치는 화면에 싣지 않았다.',
    60: '처리 기록 한 줄(11:13:18 원인 진단, hyd-dmn diagnose, 218 ms, 원문 13,763자): 사실표 05-08 §5.1.2 기록 ①. 판단 결과의 값 출처(원천 · 표 · 조건 · 실행 조회문): 사실표 05-08 §6.3.4 「근거 표시」. 납기 값의 원천 MES: mes_orders 응답의 system(38장).',
    61: '실라버스 61행 「정해진 업무 도구만 고르게 한 포털 환경과, 로컬 VS Code에서 MCP 서버를 직접 연결하는 환경이 권한 · 범위에서 어떻게 다른지 비교한다」. 포털: 서버 다섯 모두 HTTP(`it/supabase/seed.sql` tenants.mcp), 허용 목록(`it/agent-worker/worker/settings.py`), 쓰기는 판단 제출(`it/dmn-mcp/dmn_mcp/server.py`), 명령형 등록 거절(`it/process/procsvc/mcp_check.py` STDIO_REFUSED). 로컬: `.vscode/mcp.json` servers · stdio 명령 · `--read-only` · 읽을 폴더(실습 2 `코드/설정_작성.md`), 서버 신뢰 · 도구 실행 허락 확인: https://code.visualstudio.com/docs/copilot/customization/mcp-servers. 서버가 사용자 계정으로 돈다는 것은 [일반] 서술이다.',
    62: '실라버스 「통합반 온라인 44H」 62행.',
    63: '실라버스 62행(기준 스킬의 SKILL.md 읽기 · 근거와 확인할 항목을 남기게 하는 나의 스킬 · 5회차에 만든 나의 에이전트에 붙이고 떼어 같은 질문의 답 · 근거 · 처리 과정 비교). 포털 스킬 탭 · 붙이기: `it/portal/www/agents.js`. 이 행의 실습 대본 · 랩은 `workspace/강의제작/산출물/통합반/실습/06회차/`에 없다.',
    64: '실라버스 「통합반 온라인 44H」 63행.',
    65: '실라버스 63행(도구 연결 화면의 연결 상태 · 도구 목록 · 직접 시험 호출, 에이전트 질문의 호출 기록 대조, 설비 지식 ↔ 현재 업무 조회 구분). 포털 도구 연결 화면: `it/portal/www/mcp.js`. 쓰기 도구는 시험 호출에서 거절: `it/process/procsvc/mcp_check.py` not_read_only.',
    66: '실라버스 「통합반 온라인 44H」 64행.',
    67: '실라버스 64행(파일 · Git · 시간 MCP 연결과 접근 범위, 제공 서버 골격에 점검 자료 조회 함수 구현 · MCP 도구로 노출, 조합 결과의 출처와 조회 실패).',
    68: '실라버스 「통합반 온라인 44H」 65행.',
    69: '실라버스 65행(결정사항 · 담당자 · 완료 시점 추출 SKILL.md, 담당자 · 기한이 없으면 미정, Markdown/JSON 작업 목록 생성 · 검토, 다음 행동).',
    70: '실라버스 「통합반 온라인 44H」 66행.',
    71: '실라버스 66행(Notion 학습노트 MCP 읽기, 문항 · 정답 기준 · 해설 · 원문 근거, 답 전 정답 숨김, 정답 · 부분 정답 · 오답과 이유, 재도전 · 풀이 기록, 표현만 다른 정답 · 불완전한 답 · 노트에 없는 질문 검증, 근거 부족 시 보류).',
    72: '복습(오늘의 흐름을 사건에 적용해 되짚는 유일한 자리). 새 사실 없음: 1행 22 · 24장, 2행 16 · 17 · 18장, 3행 34 · 35장(구매 판단 도구 셋), 4행 56장. 퀴즈 세 문항(서버 연결 · 시간 초과 · 등록 서버의 허용)과 겹치지 않는 상황을 골랐다.',
    73: '용어 정리(용어 · 정식 명칭 · 풀이, 예 열 없음). 풀이는 본문 정의 장(7 · 29 · 31 · 36 · 40 · 48 · 53 · 56)의 뜻을 한 줄로 줄였다. 정식 명칭: 사실표 05-08 §13. 표는 아홉 행이 상한이라 JSON-RPC · 작업 폴더 · 허용 목록(51장 제목에 Allowlist)은 넣지 않았다.',
    74: '퀴즈 간지 고정 문구.',
    75: '시나리오 해석 문항. 스킬은 방법을 적은 글이고 실행은 서버가 한다, 서버가 없으면 그 사실을 받지 못한다: 사실표 05-08 §6.2.3. mes_orders는 enterprise 서버 도구: `it/enterprise-mcp/enterprise_mcp/server.py`. 문항의 연결 서버 구성은 문제용 설정이다. 정답 2번.',
    76: '근거 구분 문항. 조회 실패와 값 없음의 구분, 실패를 0이나 빈 값으로 바꾸지 않는다: `it/process/procsvc/work_rules.py` _NO_INVENTION, 사실표 05-08 §5.2.3. spare_stock은 실제 도구 이름(`enterprise_mcp/server.py`). 문항의 상황은 문제용 설정이다. 정답 4번.',
    77: '책임 경계 판단 문항. 새로 등록한 서버는 읽기로 판정된 도구 이름만 허용 목록에 오르고, 표시가 없거나 false이면 거절: `it/process/procsvc/mcp_check.py` read_only_verdict, `it/agent-worker/worker/settings.py` run_allowed_tools. read_rows · update_row · export는 문제용으로 지은 이름이다. 따로 확인하는 예외는 이 문항의 전제(별도 확인 없음)에 들지 않는다. 정답 1번.',
    78: '정답 표. 정답 번호 2 · 4 · 1. 근거 장: Quiz 1은 43 · 44, Quiz 2는 59, Quiz 3은 48 · 49 · 51.',
}
assert sorted(BASIS) == list(range(1, 79))

# 61행 시간을 맞추며 대본에서 덜어 낸 말을 노트에서도 덜어 낸다 — 옛 장 번호
NOTE_TRIM = {
    46: [(' / · false인 판단 제출 도구는 포털 시험 화면에서 못 부르고 처리 건 안 에이전트만 부른다. 업무 DB · 시계열 DB를 읽는 서버는 읽기 전용 계정으로 접속 — 실제로 막는 장치는 서버 뒤에',
          ' / · 업무 DB · 시계열 DB를 읽는 서버는 읽기 전용 계정으로 접속 — 실제로 막는 장치는 서버 뒤에')],
    49: [('· 사전 허용 범위를 넘는 요청은 호스트의 권한 검사가 다룬다. 추가 확인인지 차단인지는 실행 정책에 따라', '· 사전 허용 범위를 넘는 요청은 호스트의 권한 검사가 다룬다')],
    50: [('. 이 사례에서 에이전트에 연결된 MCP 쓰기는 이 둘(작업 폴더의 결과 파일은 따로 작성)', '. 이 사례에서 에이전트에 연결된 MCP 쓰기는 이 둘뿐'),
         ('이 MCP 경로에는 실행할 도구가 없다. 다른 경로까지 없는지는 전체 권한에서 확인', '이 MCP 경로에는 실행할 도구가 없다')],
    56: [('. 포털 시험 화면도 잘린 표시와 원래 크기를 함께 보여 준다', '')],
    57: [('. 모든 외부 서버가 출처를 자동으로 주지는 않는다', '')],
}
for k, v in NOTE_TRIM.items():
    SCREEN_EDITS.setdefault(k, []).extend(v)

SCREEN_EDITS.setdefault(71, []).extend([
    ('- 메시지: HYD에서 연결 검사는 통과했고, read_rows(true), update_row(false), export(표시 없음)에 강사의 별도 확인은 없다.',
     '- 메시지: 연결 검사는 통과했고 read_rows(true) · update_row(false) · export(표시 없음)를 따로 확인하지는 않았다.'),
    ('강사의 별도 읽기 확인 없음', '따로 읽기로 확인한 도구 없음')])
SCREEN_EDITS.setdefault(41 + 0, [])

# 검토 뒤 고친 것(판정 온6통합.json 고칠목록) — 옛 장 번호
REVIEW = {
    1: [('- 과정: 업무 능력을 재사용하고 여러 외부 시스템을 연결하기', '- 과정: 통합반 6회차 · 업무 능력을 재사용하고 여러 외부 시스템을 연결하기')],
    10: [('1. name | HYD 저장 검사: 소문자 · 숫자 · 하이픈, 64자 이내 / 폴더 이름과 일치하는 식별자 | 이름',
          '1. name | 소문자 · 숫자 · 하이픈, 이 설비의 저장 검사는 64자 이내 / 폴더 이름과 일치하는 식별자 | 이름'),
         ('3. HYD의 배정 | 에이전트나 업무 단계에 지정한 스킬을 제공한다. / 설명 작성만으로 모든 실행에 자동 배정되지 않는다. | 구현 사례',
          '3. 배정 | 스킬은 에이전트나 업무 단계에 붙여야 실행에 제공된다. / 설명을 적는 일과 실행에 배정하는 일은 다르다. | 이 설비의 예'),
         ('→ 셋째 줄 HYD의 배정 /', '→ 셋째 줄 배정 /'),
         ('폴더 이름과 일치, HYD 저장 검사는 64자 이내.', '폴더 이름과 일치, 이 설비의 저장 검사는 64자 이내.'),
         ('· HYD: 에이전트 · 업무 단계에 지정된 스킬만', '· 배정: 에이전트 · 업무 단계에 지정된 스킬만')],
    14: [('· decision_id: 같은 스킬로 두 번 처리된 쿨러 경보 중 둘째 건의 번호',
          '· decision_id: 같은 스킬로 처리된 같은 종류의 쿨러 경보 두 건 가운데 둘째 건(따라온 쿨러 사건과 다른 경보 한 건)의 번호')],
    22: [('- 메시지: 시나리오 에이전트 셋은', '- 메시지: 기준 에이전트 셋은')],
    35: [('"alert_id": "ALT-hyd01-0025-b8ed" /       }', '"alert_id": "ALT-hyd01-0025-b8ed" /       } /  / 같은 이름 · 다른 서버 / mcp__enterprise__part_quotes / mcp__enterprise-purchase__part_quotes')],
    43: [('- 메시지: 아래 표는 스킬 단계별 대응이며, 실제 호출은 원인 진단 뒤 후보 비교를 거쳐 업무 값을 확인했다.',
          '- 메시지: 한 실행의 기록에서 스킬은 단계와 순서를 정하고, 각 단계의 값은 그 도구를 가진 서버가 돌려준다.')],
    47: [('- 메시지: 새로 등록한 서버의 도구는 연결 검사 · 설정 지문 · 읽기 판정을 거쳐야 허용되고, 표시 없는 도구는 막힌다.',
          '- 메시지: 새로 등록한 서버의 도구는 표시 · 연결 검사 · 허용 목록의 세 겹을 지나야 닿고, 표시 없는 도구는 막힌다.')],
    54: [('1. **${SECRET:이름}** | 값이 들어갈 자리와 그 값의 이름이다.', '1. **${SECRET:이름}** | 자리표시자(Placeholder): 값이 들어갈 자리와 그 값의 이름이다.'),
         ('· 자리표시자 ${SECRET:이름}: 값 대신 이름,', '· 자리표시자(Placeholder) ${SECRET:이름}: 값 대신 이름,')],
    57: [('"alert_id": "ALT-hyd01-0014-e0a1"} /  / 받음  원문 13,763자 (JSON)',
          '"alert_id": "ALT-hyd01-0014-e0a1"} /  / 받음  원문 13,763자 (JSON) /  / 판단 결과의 값 출처(provenance) /   원천 · 표 · 열 · 조건 · /   실행한 조회문 · 관측 시각'),
         ('4. **값의 출처** | HYD 판단에는 원천 · 조회 근거가 붙는다. / 관측 시각과 조회 시각을 구분한다.',
          '4. **값의 출처** | 이 설비의 판단 결과에는 원천 · 조회 근거가 붙는다. / 관측 시각과 조회 시각을 구분한다.'),
         ('→ 오른쪽 맨 아래 값의 출처 /', '→ 왼쪽 아래 값 출처 칸 · 오른쪽 맨 아래 값의 출처 /'),
         ('· 겹 하나 더: HYD 판단 결과에는', '· 겹 하나 더: 이 설비의 판단 결과에는')],
    69: [('- 메시지: 스킬에 mes_orders 직접 호출이 있지만, 연결된 서버는 neo4j와 hyd-dmn뿐이며 그 도구는 제공되지 않는다.',
          '- 메시지: 스킬의 mes_orders 호출 단계에서 값을 받지 못했고, 연결된 서버는 neo4j와 hyd-dmn이다.'),
         ('연결된 서버는 neo4j와 hyd-dmn뿐 /', '연결된 서버는 neo4j와 hyd-dmn /')],
    71: [('· 상황: HYD 포털에 새로 등록한 서버,', '· 상황: 포털에 새로 등록한 서버,')],
    72: [('3. Quiz 3 | HYD의 기본 판정이다. 별도 확인 없는 표시 누락 도구는 자동 허용하지 않는다. | 1번',
          '3. Quiz 3 | 읽기임이 확인된 도구만 허용 목록에 오른다. 표시가 없으면 명세의 기본값대로 읽기 도구로 보지 않는다. | 1번'),
         ('export는 표시가 없어 걸러진다.', 'export는 표시가 없어 명세 기본값대로 읽기가 아니라 걸러진다.')],
}
for k, v in REVIEW.items():
    SCREEN_EDITS.setdefault(k, []).extend(v)
BASIS[1] += ' 표지 `과정:` 칸은 「통합반 6회차 · 회차 주제」 꼴이다(앞 회차 덱과 같다).'
BASIS[24] = BASIS[24].replace('「시나리오 에이전트 셋」: 같은 파일의 주석.', '「기준 에이전트 · 기준 스킬」: 이 과정의 이름(실라버스 50 · 62행, 5회차 덱).')
BASIS[37] += ' 같은 이름 · 다른 서버의 전체 이름: 사실표 05-08 §6.2.2.'
BASIS[60] = BASIS[60].replace('판단 결과의 값 출처(원천 · 표 · 조건 · 실행 조회문)', '판단 결과의 값 출처 칸 provenance의 항목(원천 · 표 · 열 · 조건 · 실행 조회문 · 관측 시각 — 값은 싣지 않았다)')
BASIS[78] += ' 표시가 없으면 읽기 전용이 아닌 것으로 본다: MCP 명세 server/tools ToolAnnotations readOnlyHint 기본값 false, `it/process/procsvc/mcp_check.py` read_only_verdict.'
