"""학생 시스템 자리(지하철 차량 공기 공급 장치 APU 운영사)의 데이터 저장소를 만든다 — MetroPT-3 CSV → SQLite.

    py build_db.py <MetroPT3(AirCompressor).csv> <apu.sqlite3>

데이터 출처: MetroPT-3 Dataset(UCI 791, CC BY 4.0, Davari · Veloso · Ribeiro · Gama 2021, DOI 10.24432/C5VW3R).
표준 라이브러리만 쓴다(학생 PC 규칙). 표:
  readings(ts TEXT 'YYYY-MM-DD HH:MM:SS' 기본 키, 신호 15칸)  — 10초 간격 실측
  failure_reports(no, start, end, failure, severity, report)   — 데이터셋 설명서의 회사 고장 보고 4건
  maintenance_log(id, at, case_id, sop, action, by, idempotency_key UNIQUE) — 포털 승인 뒤 기록이 쌓이는 곳(처음엔 비어 있음)
"""
import csv
import sqlite3
import sys

SIGNALS = ('TP2', 'TP3', 'H1', 'DV_pressure', 'Reservoirs', 'Oil_temperature', 'Motor_current',
           'COMP', 'DV_eletric', 'Towers', 'MPG', 'LPS', 'Pressure_switch', 'Oil_level', 'Caudal_impulses')
# 데이터셋 설명서(Data Description_Metro.pdf) 「Failure Information」 표 그대로(시각은 설명서의 M/D/YYYY H:MM — 여기서는 ISO 로 적는다)
FAILURES = (
    (1, '2020-04-18 00:00:00', '2020-04-18 23:59:00', 'Air leak', 'High stress', ''),
    (2, '2020-05-29 23:30:00', '2020-05-30 06:00:00', 'Air leak', 'High stress', 'Maintenance on 30Apr at 12:00'),
    (3, '2020-06-05 10:00:00', '2020-06-07 14:30:00', 'Air leak', 'High stress', 'Maintenance on 8Jun at 16:00'),
    (4, '2020-07-15 14:30:00', '2020-07-15 19:00:00', 'Air leak', 'High stress', 'Maintenance on 16Jul at 00:00'),
)


def build(csv_path: str, db_path: str) -> int:
    db = sqlite3.connect(db_path)
    db.executescript(
        'DROP TABLE IF EXISTS readings; DROP TABLE IF EXISTS failure_reports;'
        'CREATE TABLE readings (ts TEXT PRIMARY KEY, ' + ', '.join(f'{s} REAL NOT NULL' for s in SIGNALS) + ') WITHOUT ROWID;'
        'CREATE TABLE failure_reports (no INTEGER, start TEXT, end TEXT, failure TEXT, severity TEXT, report TEXT);'
        'CREATE TABLE IF NOT EXISTS maintenance_log (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, case_id TEXT NOT NULL,'
        ' sop TEXT NOT NULL, action TEXT NOT NULL, by_whom TEXT NOT NULL, idempotency_key TEXT UNIQUE);')
    n = 0
    with open(csv_path, newline='', encoding='utf-8') as f:
        rows = csv.DictReader(f)
        missing = [s for s in ('timestamp', *SIGNALS) if s not in (rows.fieldnames or [])]
        if missing:
            raise SystemExit(f'{csv_path}: 칸이 없습니다 — {missing}')
        batch = []
        for r in rows:
            batch.append((r['timestamp'], *(float(r[s]) for s in SIGNALS)))
            if len(batch) == 50_000:
                db.executemany(f'INSERT INTO readings VALUES ({",".join("?" * (len(SIGNALS) + 1))})', batch)
                n += len(batch)
                batch.clear()
        db.executemany(f'INSERT INTO readings VALUES ({",".join("?" * (len(SIGNALS) + 1))})', batch)
        n += len(batch)
    db.executemany('INSERT INTO failure_reports VALUES (?,?,?,?,?,?)', FAILURES)
    db.commit()
    db.close()
    return n


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print('행', build(sys.argv[1], sys.argv[2]))
