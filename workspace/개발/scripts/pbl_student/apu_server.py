"""학생 시스템의 도구 서버 — 공기 공급 장치(APU) 실측과 정비 기록을 포털 에이전트 · 흐름이 읽고 쓰게 내는 HTTP MCP 서버.

    py apu_server.py --db apu.sqlite3 --clock clock.json --host <이 PC 의 루프백이 아닌 주소> --port 8711

포털에는 「도구 연결」에서 http://<주소>:<포트>/mcp 로 등록한다(포털은 컨테이너 안에서 부르므로 127.0.0.1 은 받지 않는다 — RUNBOOK §6).
데이터 출처: MetroPT-3 Dataset(UCI 791, CC BY 4.0). 「지금」은 감지 프로그램(apu_detector.py)이 적은 시계 파일의 데이터 시각이다 — 감지와
같은 시각을 본다. 시계 파일이 없으면 지금을 정할 수 없어 그 까닭으로 거절한다. 정비 기록의 때(at)도 이 시계의 지금이다(데이터 시각을 UTC 로
읽는다 — 감지 프로그램 머리말 「시계」). 벽시계를 적으면 기록 데이터의 시각과 정비 기록의 시각이 다른 해가 된다.

도구(읽기 표시 readOnlyHint 를 단다 — 포털 연결 검사의 읽기 도장 근거):
  apu_status      지금 시각의 마지막 값(신호 15개)과 지금까지 15분 창 하나의 요약
  apu_windows     지금까지 최근 N시간(최대 24)의 15분 창 요약 — 부하 운전 비율 · 부하 기동 횟수 · 오일 온도 · 모터 전류 · 저장 탱크 압력 · LPS 비율
  apu_readings    [start, end) 원시 값(10초 안팎 간격 — 1시간에 360행 남짓, 한 번에 1시간까지)
  failure_reports 회사 고장 보고(데이터셋 설명서의 표)
  maintenance_log 정비 기록(최근 것부터)
쓰기:
  record_maintenance  정비 기록 한 줄(처리 건 · 절차 번호 · 한 일 · 한 사람). 같은 idempotency_key 는 한 번만 쓴다(포털 「승인 뒤 MCP 호출」의 재시도 열쇠)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

SIGNALS = ('TP2', 'TP3', 'H1', 'DV_pressure', 'Reservoirs', 'Oil_temperature', 'Motor_current',
           'COMP', 'DV_eletric', 'Towers', 'MPG', 'LPS', 'Pressure_switch', 'Oil_level', 'Caudal_impulses')
FMT = '%Y-%m-%d %H:%M:%S'
WINDOW = timedelta(minutes=15)
READ = ToolAnnotations(readOnlyHint=True)


def build(db_path: str, clock_path: str) -> FastMCP:
    app = FastMCP('지하철 APU 운영 데이터')

    def connect(write: bool = False) -> sqlite3.Connection:
        return sqlite3.connect(db_path) if write else sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)

    def now() -> datetime:
        try:
            with open(clock_path, encoding='utf-8') as f:
                c = json.load(f)
        except FileNotFoundError:
            raise ValueError('시계 파일이 없어 「지금」을 정할 수 없습니다 — 감지 프로그램(apu_detector.py)을 먼저 켜세요') from None
        return datetime.strptime(c['data0'], FMT) + timedelta(seconds=(time.time() - float(c['wall0'])) * float(c['speed']))

    def summarize(rows: list[tuple]) -> dict:
        n = len(rows)
        if not n:
            return {'samples': 0}
        col = {s: [r[1 + i] for r in rows] for i, s in enumerate(SIGNALS)}
        starts = sum(1 for a, b in zip(col['DV_eletric'], col['DV_eletric'][1:]) if a == 0 and b == 1)
        return {'samples': n, 'load_ratio': round(sum(col['DV_eletric']) / n, 3), 'load_starts': starts,
                'oil_temp_c_mean': round(sum(col['Oil_temperature']) / n, 2), 'oil_temp_c_max': round(max(col['Oil_temperature']), 2),
                'motor_current_a_mean': round(sum(col['Motor_current']) / n, 2), 'reservoirs_bar_min': round(min(col['Reservoirs']), 3),
                'tp2_bar_mean': round(sum(col['TP2']) / n, 3), 'lps_ratio': round(sum(col['LPS']) / n, 3),
                'oil_level_low_ratio': round(sum(col['Oil_level']) / n, 3)}

    def rows_between(db, start: datetime, end: datetime) -> list[tuple]:
        return db.execute(f'SELECT ts, {", ".join(SIGNALS)} FROM readings WHERE ts >= ? AND ts < ? ORDER BY ts',
                          (start.strftime(FMT), end.strftime(FMT))).fetchall()

    @app.tool(annotations=READ)
    def apu_status() -> dict:
        """지금(데이터 시각)의 마지막 값과 지금까지의 15분 창 요약을 돌려준다."""
        t = now()
        with connect() as db:
            last = db.execute(f'SELECT ts, {", ".join(SIGNALS)} FROM readings WHERE ts <= ? ORDER BY ts DESC LIMIT 1', (t.strftime(FMT),)).fetchone()
            window = summarize(rows_between(db, t - WINDOW, t))
        return {'asset': 'APU-01', 'now': t.strftime(FMT), 'last': dict(zip(('ts', *SIGNALS), last)) if last else None, 'last_15min': window}

    @app.tool(annotations=READ)
    def apu_windows(hours: float = 2.0) -> dict:
        """지금까지 최근 hours 시간(0.25~24)의 15분 창 요약 목록(오래된 것부터)."""
        if not 0.25 <= hours <= 24:
            raise ValueError('hours 는 0.25 ~ 24 입니다')
        t = now()
        start = t - timedelta(hours=hours)
        out = []
        with connect() as db:
            k = start
            while k + WINDOW <= t:
                out.append({'start': k.strftime(FMT), **summarize(rows_between(db, k, k + WINDOW))})
                k += WINDOW
        return {'asset': 'APU-01', 'now': t.strftime(FMT), 'windows': out}

    @app.tool(annotations=READ)
    def apu_readings(start: str, end: str, signals: list[str] | None = None) -> dict:
        """[start, end) 원시 값(10초 안팎 간격 — 1시간에 360행 남짓), 한 번에 1시간까지. 시각은 YYYY-MM-DD HH:MM:SS, 지금보다 뒤는 읽지 않는다."""
        a, b = datetime.strptime(start, FMT), min(datetime.strptime(end, FMT), now())
        # 기간으로 자른다 — 표본 간격이 10초보다 조금 짧아 1시간이 363~364행이다. 행 수(360)로 자르면 매뉴얼의 「최근 1시간」 기준을 읽는
        # 요청이 늘 거절되어 에이전트가 원시 값 없이 판단했다(2026-11-23 실측: 갈래 아홉 가운데 여덟에서 첫 요청이 거절)
        if b - a > timedelta(hours=1):
            raise ValueError('한 번에 1시간까지 읽습니다 — 기간을 나누거나 apu_windows 로 요약을 읽으세요')
        chosen = list(signals or SIGNALS)
        unknown = [s for s in chosen if s not in SIGNALS]
        if unknown:
            raise ValueError(f'없는 신호: {unknown} — 신호는 {list(SIGNALS)}')
        with connect() as db:
            rows = db.execute(f'SELECT ts, {", ".join(chosen)} FROM readings WHERE ts >= ? AND ts < ? ORDER BY ts',
                              (a.strftime(FMT), b.strftime(FMT))).fetchall()
        return {'columns': ['ts', *chosen], 'rows': [list(r) for r in rows]}

    @app.tool(annotations=READ)
    def failure_reports() -> dict:
        """회사 고장 보고(번호 · 시작 · 끝 · 고장 · 심각도 · 보고)."""
        with connect() as db:
            rows = db.execute('SELECT no, start, end, failure, severity, report FROM failure_reports ORDER BY start').fetchall()
        return {'columns': ['no', 'start', 'end', 'failure', 'severity', 'report'], 'rows': [list(r) for r in rows]}

    @app.tool(annotations=READ)
    def maintenance_log(limit: int = 20) -> dict:
        """정비 기록(최근 것부터, 최대 100)."""
        with connect() as db:
            rows = db.execute('SELECT id, at, case_id, sop, action, by_whom FROM maintenance_log ORDER BY id DESC LIMIT ?',
                              (max(1, min(int(limit), 100)),)).fetchall()
        return {'columns': ['id', 'at', 'case_id', 'sop', 'action', 'by'], 'rows': [list(r) for r in rows]}

    @app.tool(annotations=ToolAnnotations(readOnlyHint=False))
    def record_maintenance(case_id: str, sop: str, action: str, performed_by: str, idempotency_key: str) -> dict:
        """정비 기록 한 줄을 쓴다. 같은 idempotency_key 는 한 번만 쓰고 처음 기록을 돌려준다."""
        for name, value in (('case_id', case_id), ('sop', sop), ('action', action), ('performed_by', performed_by), ('idempotency_key', idempotency_key)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} 가 비었습니다')
        with connect(write=True) as db:
            old = db.execute('SELECT id, at FROM maintenance_log WHERE idempotency_key = ?', (idempotency_key,)).fetchone()
            if old:
                return {'id': old[0], 'at': old[1], 'replayed': True}
            at = now().replace(tzinfo=timezone.utc).isoformat(timespec='seconds')
            cur = db.execute('INSERT INTO maintenance_log (at, case_id, sop, action, by_whom, idempotency_key) VALUES (?,?,?,?,?,?)',
                             (at, case_id.strip(), sop.strip(), action.strip(), performed_by.strip(), idempotency_key))
            return {'id': cur.lastrowid, 'at': at, 'replayed': False}

    return app


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--db', required=True)
    p.add_argument('--clock', required=True)
    p.add_argument('--host', required=True)
    p.add_argument('--port', type=int, required=True)
    a = p.parse_args()
    build(a.db, a.clock).run(transport='http', host=a.host, port=a.port, path='/mcp')


if __name__ == '__main__':
    main()
