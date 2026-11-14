"""데이터 원천 표 — 업무 DB · 옛 설비 DB · 시계열 DB 의 이름 · 스키마 · 읽기 계정(정본 한 곳).

데이터 패브릭(hydcommon.fabric — process 의 데이터 원천 API · dmn-mcp 의 fabric_query)이 이 표로 원천에 붙고, AI 워커(worker.ai_replay)는
조회문이 읽은 표가 어느 원천의 것인지 학생 말로 이름 붙이는 데 쓴다. 이 모듈은 아무것도 가져오지 않는다 — 워커 이미지에는 패브릭이 쓰는
조회문 검사 라이브러리(sqlglot)가 없어, 표를 fabric 에 두면 워커가 켜지자마자 가져오기 오류로 죽는다(2026-11-14 실측: test_process_control).
"""
ENT, TS, LEGACY = 'hyd-enterprise', 'hyd-timeseries', 'hyd-legacy'
TS_TABLES = ('tag_1s', 'feat_1s', 'tag_1m')
SOURCES = {
    ENT: dict(id=ENT, label='업무 DB', engine='Supabase PostgreSQL', schema='ent', role='hyd_enterprise_reader',
              env=('ENTERPRISE_READ_DSN',), systems=('sys:mes', 'sys:erp', 'sys:cmms', 'sys:qms', 'sys:scm'),
              about='ERP · MES · CMMS · QMS · SCM · EMS 업무 기록 (주문 · 계약 · 정비 · 품질 · 구매)'),
    # 실라버스 통합 40행: 옛 설비 관리 시스템에서 옮긴 덤프(제공 파일 it/portal/www/samples/legacy-plant-db.sql = 마이그레이션
    # 20261031000071_legacy_plant_db). 업무 DB 안의 스키마 하나라 같은 전용 읽기 계정 · 연결 주소로 읽는다.
    LEGACY: dict(id=LEGACY, label='옛 설비 DB', engine='Supabase PostgreSQL', schema='legacy', role='hyd_enterprise_reader',
                 env=('ENTERPRISE_READ_DSN',), systems=(),
                 about='옛 설비 관리 시스템에서 옮긴 덤프 (설비 · 측정 · 정비 요청 — 표 · 열 이름이 코드, 주석 없음)'),
    TS: dict(id=TS, label='시계열 DB', engine='TimescaleDB', schema='public', role='hyd_timeseries_reader',
             env=('TSDB_READ_DSN',), systems=('sys:historian',), tables=TS_TABLES,
             about='센서 · 설정값 1초 기록(tag_1s), 파형 특징(feat_1s), 1분 집계(tag_1m)'),
}
