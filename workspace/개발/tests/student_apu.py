"""시험 자료: 학생 현장(유압이 아닌 설비)의 시스템 자리 — 지하철 차량 공기 공급 장치(APU) 운영사의 감지 규칙 · 데이터 · 도구 서버를 작게 옮긴 것.

원본은 학생 쪽 재료(apu_detector.py · apu_server.py — 공개 데이터셋 MetroPT-3, UCI 791, CC BY 4.0)다. 데이터셋은 이 PC 작업 폴더에만 받고
저장소에는 두지 않는다(사용자 승인 범위 2026-11-22). 그래서 시험의 학생 시스템 데이터는 readings() 가 만든다 — 시스템 밖(학생 현장)의 데이터라
시험이 대신 만들어도 되는 자리이고, 시험이 재는 것은 그 데이터의 사실이 아니라 포털이 바깥 경보 · 도구 서버를 받는 길이다. 만드는 모양은
실측에서 잰 것이다(2026-11-23, 2020-07-15 회사 고장 보고 4번 「Air leak」): 시작 14:30~15:30 은 압축기가 쉬지 못해 부하 운전만(부하 비율 1.0,
오일 82 → 88 ℃, 모터 전류 약 5.9 A, 공기 압력 약 9.9 bar), 끝 18:45~19:15 은 부하 · 무부하를 오감(부하 비율 약 0.35, 오일 81 → 70 ℃).
10초 간격 신호 15개. 실제 규모 데이터의 검증은 작업 폴더의 원본으로 학생 대역 실측(pbl_round.py)이 한다.
감지 규칙과 경보 꼴은 원본과 같다: 15분 창마다 부하 운전 비율(DV_eletric 평균) · 오일 온도 평균, 마지막 4창(60분)이
모두 부하 비율 0.97 이상 · 오일 70 ℃ 이상 · 표본 60개 넘음이면 발생(RAISE), 발생 뒤 마지막 2창(30분)이 모두 부하 비율 0.9 미만이면 해제(CLEAR).
경보는 감지기 경보와 같은 계약(alertId · asset · pattern · name · state · severity · evidence · t)이다 — 유압 태그는 하나도 없다.
"""
import math
import sqlite3
from datetime import datetime, timedelta

SIGNALS = ('TP2', 'TP3', 'H1', 'DV_pressure', 'Reservoirs', 'Oil_temperature', 'Motor_current',
           'COMP', 'DV_eletric', 'Towers', 'MPG', 'LPS', 'Pressure_switch', 'Oil_level', 'Caudal_impulses')
ASSET, PATTERN, NAME = 'APU-01', 'APU_AIR_LEAK', '공기 누설 의심'
FMT = '%Y-%m-%d %H:%M:%S'
WINDOW = timedelta(minutes=15)
FULL_LOAD, CLEAR_LOAD, OIL_HOT, MIN_SAMPLES = 0.97, 0.9, 70.0, 60


LEAK = (datetime(2020, 7, 15, 14, 30), datetime(2020, 7, 15, 15, 30))        # 압축기가 쉬지 못함(공기 누설)
EASED = (datetime(2020, 7, 15, 18, 45), datetime(2020, 7, 15, 19, 15))       # 부하 · 무부하를 오감(누설 멈춤)
STEP = timedelta(seconds=10)
CYCLE, LOADED = 20, 7          # 끝 구간: 200초마다 70초 부하 운전(부하 비율 0.35 — 실측 0.348)


def readings() -> list[tuple]:
    """학생 시스템의 10초 간격 실측 행(모양은 머리말 — 실측에서 잰 수준). 같은 입력이면 늘 같은 값."""
    rows = []
    for (start, end), leaking_now in ((LEAK, True), (EASED, False)):
        n = int((end - start) / STEP)
        for i in range(n):
            wave = math.sin(i / 7.0)
            if leaking_now:
                loaded, oil = True, 82.0 + 6.0 * i / (n - 1)
            else:
                loaded, oil = i % CYCLE < LOADED, 81.0 - 11.0 * i / (n - 1)
            tp2 = 9.9 + 0.3 * wave if loaded else 0.02 * abs(wave)
            tank = 9.65 + 0.25 * wave if leaking_now else 8.7 + 0.8 * wave
            values = {'TP2': tp2, 'TP3': tank, 'H1': -0.002 if loaded else 9.5 + 0.4 * wave, 'DV_pressure': -0.009,
                      'Reservoirs': tank, 'Oil_temperature': oil, 'Motor_current': 5.9 + 0.15 * wave if loaded else 0.04,
                      'COMP': 0.0 if loaded else 1.0, 'DV_eletric': 1.0 if loaded else 0.0, 'Towers': float((i // 12) % 2) if leaking_now else 1.0,
                      'MPG': 0.0 if loaded else 1.0, 'LPS': 0.0, 'Pressure_switch': 1.0, 'Oil_level': 1.0, 'Caudal_impulses': 1.0}
            rows.append(((start + i * STEP).strftime(FMT), *(round(values[s], 3) for s in SIGNALS)))
    return rows


def build(db_path) -> sqlite3.Connection:
    """학생 시스템의 저장소(readings · maintenance_log)를 만든다 — 실측 행은 readings()."""
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.executescript('CREATE TABLE readings (ts TEXT PRIMARY KEY, ' + ', '.join(f'{s} REAL NOT NULL' for s in SIGNALS) + ') WITHOUT ROWID;'
                     'CREATE TABLE maintenance_log (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, case_id TEXT NOT NULL, sop TEXT NOT NULL,'
                     ' action TEXT NOT NULL, by_whom TEXT NOT NULL, idempotency_key TEXT UNIQUE);')
    db.executemany(f'INSERT INTO readings VALUES ({",".join("?" * (len(SIGNALS) + 1))})', readings())
    db.commit()
    return db


def windows(db, start: datetime, end: datetime) -> list[dict]:
    """[start, end) 의 15분 창 요약(원본 apu_detector.windows 와 같은 계산)."""
    rows = db.execute('SELECT ts, DV_eletric, Oil_temperature FROM readings WHERE ts >= ? AND ts < ? ORDER BY ts',
                      (start.strftime(FMT), end.strftime(FMT))).fetchall()
    out, k = [], start
    while k + WINDOW <= end:
        group = [r for r in rows if k.strftime(FMT) <= r[0] < (k + WINDOW).strftime(FMT)]
        n = len(group)
        out.append({'start': k.strftime(FMT), 'samples': n, 'load_ratio': round(sum(r[1] for r in group) / n, 3) if n else None,
                    'oil_temp_c': round(sum(r[2] for r in group) / n, 2) if n else None})
        k += WINDOW
    return out


def leaking(w: dict) -> bool:
    return w['samples'] > MIN_SAMPLES and w['load_ratio'] >= FULL_LOAD and w['oil_temp_c'] >= OIL_HOT


def relieved(w: dict) -> bool:
    return w['samples'] > MIN_SAMPLES and w['load_ratio'] < CLEAR_LOAD


def detected(db) -> tuple[dict, dict]:
    """표본에서 감지 규칙이 낸 발생 · 해제 경보(같은 alertId). 규칙이 표본에서 둘 다 내지 않으면 시험 자료가 틀린 것 — 그 까닭으로 실패한다."""
    rise = windows(db, datetime(2020, 7, 15, 14, 30), datetime(2020, 7, 15, 15, 30))
    fall = windows(db, datetime(2020, 7, 15, 18, 45), datetime(2020, 7, 15, 19, 15))
    if len(rise) != 4 or not all(map(leaking, rise)) or len(fall) != 2 or not all(map(relieved, fall)):
        raise AssertionError(f'표본이 감지 규칙의 발생 · 해제를 내지 않습니다: {rise} / {fall}')
    raise_ = {'alertId': f'{ASSET}-{PATTERN}-{rise[0]["start"].replace(" ", "T")}', 'asset': ASSET, 'pattern': PATTERN, 'name': NAME,
              'severity': 'HIGH', 'state': 'RAISE',
              'evidence': {'data_time': '2020-07-15 15:30:00', 'windows': rise, 'rule': '최근 60분 모든 15분 창이 부하 비율 0.97 이상 · 오일 온도 70 ℃ 이상'}}
    clear = dict(raise_, state='CLEAR', evidence={'data_time': '2020-07-15 19:15:00', 'windows': fall, 'rule': '최근 30분 부하 비율 0.9 미만'})
    return raise_, clear


class ApuSystem:
    """학생 시스템의 HTTP MCP 도구 서버(원본 apu_server.py 에서 읽기 하나 · 쓰기 하나). 받은 호출을 남긴다. 「지금」은 now(데이터 시각)."""

    def __init__(self, db, host, now='2020-07-15 15:30:00'):
        from fastmcp import FastMCP
        from mcp.types import ToolAnnotations
        from conftest import Served
        self.db, self.now, self.calls = db, now, []
        app = FastMCP('지하철 APU 운영 데이터')

        @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
        def apu_windows(hours: float = 1.0) -> dict:
            """지금까지 최근 hours 시간(0.25~24)의 15분 창 요약 목록(오래된 것부터) — 부하 운전 비율 · 오일 온도"""
            self.calls.append(('apu_windows', {'hours': hours}))
            t = datetime.strptime(self.now, FMT)
            return {'asset': ASSET, 'now': self.now, 'windows': windows(self.db, t - timedelta(hours=hours), t)}

        @app.tool(annotations=ToolAnnotations(readOnlyHint=False))
        def record_maintenance(case_id: str, sop: str, action: str, performed_by: str, idempotency_key: str) -> dict:
            """정비 기록 한 줄을 쓴다. 같은 idempotency_key 는 한 번만 쓰고 처음 기록을 돌려준다."""
            self.calls.append(('record_maintenance', {'case_id': case_id, 'sop': sop, 'action': action, 'performed_by': performed_by,
                                                      'idempotency_key': idempotency_key}))
            old = self.db.execute('SELECT id FROM maintenance_log WHERE idempotency_key = ?', (idempotency_key,)).fetchone()
            if old:
                return {'id': old[0], 'replayed': True}
            cur = self.db.execute('INSERT INTO maintenance_log (at, case_id, sop, action, by_whom, idempotency_key) VALUES (?,?,?,?,?,?)',
                                  (self.now, case_id, sop, action, performed_by, idempotency_key))
            self.db.commit()
            return {'id': cur.lastrowid, 'replayed': False}
        self.served = Served(app.http_app(path='/mcp'), host=host)
        self.url = self.served.url + '/mcp'

    def called(self, name):
        return [args for tool, args in self.calls if tool == name]

    def log(self):
        return self.db.execute('SELECT case_id, sop, action, by_whom FROM maintenance_log ORDER BY id').fetchall()
