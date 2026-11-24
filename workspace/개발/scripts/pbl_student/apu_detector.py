"""학생 시스템의 이상 감지 프로그램 — 공기 공급 장치(APU) 실측을 시계에 맞춰 흘리며 공기 누설 의심을 감지하고 포털에 경보를 보낸다.

    py apu_detector.py --db apu.sqlite3 --portal http://127.0.0.1:8088/svc/process --asset APU-01 --start "2020-07-15 13:00:00" --speed 60 \
                       --clock clock.json [--until "2020-07-16 02:00:00"] [--dry-run]

표준 라이브러리만 쓴다(학생 PC 규칙). 데이터는 build_db.py 가 만든 SQLite(출처 MetroPT-3, UCI 791, CC BY 4.0).

시계: 데이터 시각 = --start + (지금 벽시계 - 시작 벽시계) × --speed. 시작할 때 clock.json 에 {wall0, data0, speed} 를 적는다 — 같은 학생
시스템의 도구 서버(apu_server.py)가 이 파일로 「지금」을 정한다(둘이 같은 시각을 본다). 경보의 때(t)도 이 시계의 시각(그 경보를 낸 창의 끝 =
evidence.data_time)이다 — 보낸 벽시계를 적으면 한 경보 안에서 t(오늘)와 근거(기록 시각)가 어긋나, 경보를 읽는 에이전트가 「경보 뒤의 상태를
읽을 수 없다」고 판단을 보류한다(2026-11-23 실측 겹친 처리 건 갈래). MetroPT-3 시각에는 시간대가 없어 이 학생 시스템은 데이터 시각을 UTC 로 읽는다
(도구 서버가 돌려주는 시각과 경보 t 가 같은 숫자다).

감지 규칙(데이터로 정함 — 2026-11-22, 2020-02~08 전체, 15분 창):
  공기 누설이면 압축기가 쉬지 못하고 부하 운전을 이어 가며 오일이 데워진다(회사 고장 보고 4건 모두 공기 누설 · 높은 부하 스트레스).
  - 창마다: 부하 운전 비율 = DV_eletric 이 켜진 표본 비율, 오일 온도 평균, 표본 수.
  - 발생(RAISE): 마지막 4창(60분)이 모두 부하 비율 0.97 이상 · 오일 온도 평균 70 ℃ 이상 · 표본 60개 넘음.
  - 해제(CLEAR): 발생 뒤 마지막 2창(30분)이 모두 부하 비율 0.9 미만.
  - 전체 기간을 이 규칙(발생 · 해제 모두, 판정 함수 judge)으로 훑으면 발생 10번 — 고장 보고 4건을 모두 잡았고(고장 시작 뒤 0.75~1.5시간)
    보고 밖의 경보가 6번 있었다(헛경보이거나 보고되지 않은 사건 — 판단은 사람과 에이전트가 한다). 훑기는 pbl_round.py scan.

경보는 포털의 원천 접수 입구(POST /api/instances/start 의 alert — 감지기 경보와 같은 계약: alertId · asset · pattern · name · state ·
severity · evidence · t)로 보낸다. 같은 사건의 발생과 해제는 같은 alertId 다. 같은 경보를 다시 보내면(이 프로그램을 다시 켬) 포털은 409 「이 경보로 이미 열린
처리 건이 있습니다」로 처음 받은 것을 알려 준다 — 그것은 찍고 이어 간다. 그 밖의 거절은 그 까닭을 그대로 찍고 멈춘다(조용히 넘기지 않음).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

PATTERN, NAME = 'APU_AIR_LEAK', '공기 누설 의심'
WINDOW = timedelta(minutes=15)
RAISE_WINDOWS, CLEAR_WINDOWS = 4, 2
FULL_LOAD, CLEAR_LOAD, OIL_HOT, MIN_SAMPLES = 0.97, 0.9, 70.0, 60
FMT = '%Y-%m-%d %H:%M:%S'


def windows(db: sqlite3.Connection, start: datetime, end: datetime) -> list[dict]:
    """[start, end) 를 15분 창으로 — 창마다 표본 수 · 부하 운전 비율 · 오일 온도 평균 · 모터 전류 평균 · 저장 탱크 압력 최소."""
    rows = db.execute('SELECT ts, DV_eletric, Oil_temperature, Motor_current, Reservoirs FROM readings WHERE ts >= ? AND ts < ? ORDER BY ts',
                      (start.strftime(FMT), end.strftime(FMT))).fetchall()
    out, k = [], start
    i = 0
    while k + WINDOW <= end:
        group = []
        stop = (k + WINDOW).strftime(FMT)
        while i < len(rows) and rows[i][0] < stop:
            group.append(rows[i])
            i += 1
        n = len(group)
        out.append({'start': k.strftime(FMT), 'samples': n,
                    'load_ratio': round(sum(r[1] for r in group) / n, 3) if n else None,
                    'oil_temp_c': round(sum(r[2] for r in group) / n, 2) if n else None,
                    'motor_current_a': round(sum(r[3] for r in group) / n, 2) if n else None,
                    'reservoirs_min_bar': round(min(r[4] for r in group), 3) if n else None})
        k += WINDOW
    return out


def leaking(w: dict) -> bool:
    return w['samples'] > MIN_SAMPLES and w['load_ratio'] >= FULL_LOAD and w['oil_temp_c'] >= OIL_HOT


def relieved(w: dict) -> bool:
    return w['samples'] > MIN_SAMPLES and w['load_ratio'] < CLEAR_LOAD


def stamp(data_time: str) -> str:
    """데이터 시각(시간대 없음) → 경보 계약의 t(ISO, 시간대 있음) — 이 학생 시스템은 데이터 시각을 UTC 로 읽는다(머리말 「시계」)."""
    return datetime.strptime(data_time, FMT).replace(tzinfo=timezone.utc).isoformat()


def judge(history: list[dict], i: int, open_alert: dict | None, asset: str, tag: str = '') -> tuple[str, dict] | None:
    """창 history[i] 까지 본 판정 — ('RAISE', 경보) · ('CLEAR', 해제) · None. 시계에 맞춰 흘리기(run)와 데이터 전체 훑기가 이 판정 하나를 쓴다.
    tag: 경보 id 끝에 붙이는 사건 표시(같은 기록 데이터를 다른 사건으로 다시 흘릴 때 — 사건마다 새 경보 id)."""
    w = history[i]
    data_time = (datetime.strptime(w['start'], FMT) + WINDOW).strftime(FMT)
    last = history[max(0, i - RAISE_WINDOWS + 1):i + 1]
    if open_alert is None and len(last) == RAISE_WINDOWS and all(map(leaking, last)):
        return 'RAISE', {'alertId': f'{asset}-{PATTERN}-{last[0]["start"].replace(" ", "T")}' + (f'-{tag}' if tag else ''), 'asset': asset, 'pattern': PATTERN,
                         'name': NAME, 'severity': 'HIGH', 'state': 'RAISE', 't': stamp(data_time),
                         'evidence': {'data_time': data_time, 'windows': last,
                                      'rule': f'최근 {RAISE_WINDOWS * 15}분 모든 15분 창이 부하 비율 {FULL_LOAD} 이상 · 오일 온도 {OIL_HOT} ℃ 이상'}}
    if open_alert is not None and i >= CLEAR_WINDOWS - 1 and all(map(relieved, history[i - CLEAR_WINDOWS + 1:i + 1])):
        return 'CLEAR', dict(open_alert, state='CLEAR', t=stamp(data_time), evidence={'data_time': data_time, 'windows': history[i - CLEAR_WINDOWS + 1:i + 1],
                                                                  'rule': f'최근 {CLEAR_WINDOWS * 15}분 부하 비율 {CLEAR_LOAD} 미만'})
    return None


def send(portal: str, alert: dict) -> dict:
    req = urllib.request.Request(portal.rstrip('/') + '/api/instances/start', data=json.dumps({'alert': alert}, ensure_ascii=False).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b'null')
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        if e.code == 409 and ('이미 열린 처리 건' in body or '이미 받았습니다' in body):
            # 같은 경보(같은 alertId)를 다시 보냄(이 프로그램이 다시 켜져 열린 경보를 또 냄) — 포털은 처음 받은 것을 그대로 두고 그 처리 건을 알려 준다
            return {'already': True, 'detail': json.loads(body).get('detail') if body.startswith('{') else body}
        raise SystemExit(f'포털이 경보 {alert["state"]} 를 받지 않았습니다 — HTTP {e.code}: {body[:600]}') from None


def run(a) -> None:
    db = sqlite3.connect(f'file:{a.db}?mode=ro', uri=True)
    data0 = datetime.strptime(a.start, FMT)
    until = datetime.strptime(a.until, FMT) if a.until else None
    wall0 = time.time()
    with open(a.clock, 'w', encoding='utf-8') as f:
        json.dump({'wall0': wall0, 'data0': a.start, 'speed': a.speed}, f)
    print(f'시계: 데이터 {a.start} 부터 {a.speed}배 — {a.clock}', flush=True)
    history: list[dict] = []
    done = data0 - WINDOW * RAISE_WINDOWS            # 발생 판정에 쓸 앞 창을 함께 읽는다
    open_alert: dict | None = None
    while True:
        now = data0 + timedelta(seconds=(time.time() - wall0) * a.speed)
        if until and now >= until:
            print(f'끝 시각 {a.until} 에 닿아 멈춥니다(열린 경보: {open_alert["alertId"] if open_alert else "없음"})', flush=True)
            return
        ready = data0 + WINDOW * int((now - data0) / WINDOW)
        if ready > done:
            new = windows(db, done, ready)
            history.extend(new)
            done = ready
            for i in range(len(history) - len(new), len(history)):
                got = judge(history, i, open_alert, a.asset, a.event_tag)
                if got is None:
                    continue
                state, alert = got
                print('발생' if state == 'RAISE' else '해제', json.dumps(alert, ensure_ascii=False), flush=True)
                if not a.dry_run:
                    print('포털 응답', json.dumps(send(a.portal, alert), ensure_ascii=False), flush=True)
                open_alert = alert if state == 'RAISE' else None
        time.sleep(a.tick)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--db', required=True)
    p.add_argument('--portal', required=True, help='포털을 거친 처리 엔진 주소(예: http://127.0.0.1:8088/svc/process — 서비스 포트는 PC 에 열지 않는다)')
    p.add_argument('--asset', required=True)
    p.add_argument('--start', required=True, help='흘리기 시작할 데이터 시각 YYYY-MM-DD HH:MM:SS')
    p.add_argument('--speed', type=float, required=True, help='데이터 시간이 벽시계보다 몇 배 빨리 가는가')
    p.add_argument('--clock', required=True)
    p.add_argument('--until')
    p.add_argument('--tick', type=float, default=1.0)
    p.add_argument('--dry-run', action='store_true', help='경보를 보내지 않고 찍기만')
    p.add_argument('--event-tag', default='', help='경보 id 끝에 붙일 사건 표시(같은 기록 데이터를 다른 사건으로 다시 흘릴 때)')
    run(p.parse_args(argv))


if __name__ == '__main__':
    main(sys.argv[1:])
