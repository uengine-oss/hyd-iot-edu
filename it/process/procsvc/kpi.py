"""A8 KPI 실적 · 역추적 (단위 U11). 읽기 전용.

지표 21개(온톨로지 Measure: 목표값 · 방향 · 식 문자열 · kpiRole)는 지식 그래프에서 읽고, 실적은 세 원천에서 계산한다.
  처리 기록  Supabase public.bpm_proc_inst (처리 건 · 고른 조치)
  업무 DB    Supabase ent.* (작업지시 · 구매요청 · 재고 · 에너지 요율 · 공급사 견적)
  시계열 DB  TimescaleDB tag_1m (1분 집계) · alerts (경보 · 트립)
지표마다 계산 정의(원천 표 · 열 · 식)를 DEFINITIONS 에 한 줄씩 둔다. 원천이 없으면 숫자를 지어내지 않고 "계산 불가 — 사유"를 낸다.
식 문자열이 있는 합성 지표(영업이익 · 총비용)는 그래프의 식을 그대로 풀어 구성 지표 실적으로 계산하고, 구성 지표 하나라도
계산할 수 없으면 계산 불가다.

미달 지표의 역추적: 그래프의 INFLUENCES(지표 ← 상태 변수 · 지표) · AFFECTS(조치 → 대상) · SUPPORTS(목표 → 목표)로 영향 경로를
찾고, 같은 기간 처리 기록에서 그 경로에 걸린 처리 건(경보 일치 · 이상 패턴 · 원인 · 고른 조치)과 설비를 고른다.

시간: 시계열 시각은 벽시계다. 설비 시간(시간 단위 지표 MTBF)은 벽시계 × 배속(TIME_SCALE, 기본 20)으로 바꾼다.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

PERIODS = {'1h': ('최근 1시간', 1), '24h': ('최근 24시간', 24), '7d': ('최근 7일', 168), '30d': ('최근 30일', 720),
           'all': ('전체 기록', None)}
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

SYSTEM = {'ts': '시계열 DB', 'biz': '업무 DB', 'proc': '처리 기록', 'graph': '지식 그래프'}
STATUS = {'met': '달성', 'missed': '미달', 'no_target': '목표 없음', 'partial': '부분 실적', 'no_data': '기록 없음',
          'unavailable': '계산 불가', 'error': '조회 실패'}
COMPUTED = ('met', 'missed', 'no_target')


class SourceError(Exception):
    """원천 조회 실패. str(exc)는 사람이 읽는 한국어 사유다."""


@dataclass
class Window:
    period: str
    label: str
    start: datetime          # aware UTC (전체 기록이면 EPOCH)
    end: datetime            # aware UTC

    @property
    def params(self) -> dict:
        return {'t0': self.start, 't1': self.end}

    @property
    def naive(self) -> dict:  # bpm_proc_inst.start_date 는 timestamp without time zone (UTC 값)
        return {'t0': self.start.replace(tzinfo=None), 't1': self.end.replace(tzinfo=None)}

    def view(self) -> dict:
        return {'period': self.period, 'label': self.label,
                'start': None if self.start == EPOCH else self.start.isoformat(), 'end': self.end.isoformat()}


def window(period: str = '24h', now: datetime | None = None, start: str | None = None, end: str | None = None) -> Window:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if start or end:
        try:
            t0 = _parse(start) if start else EPOCH
            t1 = _parse(end) if end else now
        except ValueError as exc:
            raise ValueError(f'기간 시각을 읽을 수 없습니다 (ISO 8601 형식): {exc}') from exc
        if t1 <= t0:
            raise ValueError('기간의 끝이 시작보다 늦어야 합니다')
        return Window('custom', f'{t0:%m-%d %H:%M} ~ {t1:%m-%d %H:%M} (UTC)', t0, t1)
    if period not in PERIODS:
        raise ValueError('기간은 ' + ' · '.join(f'{k}({v[0]})' for k, v in PERIODS.items()) + ' 중 하나입니다')
    label, hours = PERIODS[period]
    return Window(period, label, EPOCH if hours is None else now - timedelta(hours=hours), now)


def _parse(text: str) -> datetime:
    dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _utc(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _parse(value)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# ============================================================== 원천 접근 (요청 하나 동안 같은 질의는 한 번만)
class Fetch:
    """sources: graph(name, cypher, params) · ts(name, sql, params) · biz(name, sql, params) → list[dict].
    같은 (원천, 이름, 인자) 질의는 요청 안에서 한 번만 읽고, 실패도 기억해 같은 사유를 낸다."""

    def __init__(self, sources):
        self.sources = sources
        self._memo: dict = {}

    def __call__(self, kind: str, name: str, query: str, params: dict | None = None) -> list[dict]:
        key = (kind, name, tuple(sorted((k, str(v)) for k, v in (params or {}).items())))
        if key not in self._memo:
            try:
                self._memo[key] = ('ok', list(getattr(self.sources, kind)(name, query, params or {})))
            except SourceError as exc:
                self._memo[key] = ('err', str(exc))
            except Exception as exc:  # noqa: BLE001 — 원천 드라이버 예외도 사람이 읽을 사유로 바꾼다
                self._memo[key] = ('err', f'{SYSTEM[kind]} 조회 실패: {type(exc).__name__}: {str(exc)[:200]}')
        state, value = self._memo[key]
        if state == 'err':
            raise SourceError(value)
        return value


@dataclass
class Calc:
    value: float | None
    per_asset: dict = field(default_factory=dict)       # 설비 → 값
    rows: list = field(default_factory=list)            # [(원천, 표, 행 수)]
    events: list = field(default_factory=list)          # 역추적에 쓰는 근거 사건 {asset, at, end, alert_id, label}
    note: str | None = None
    status: str | None = None                           # None = 목표로 판정 · 'partial' · 'no_data'
    reason: str | None = None
    detail: list = field(default_factory=list)          # 화면 표: 계산에 쓴 행 요약


# ============================================================== 질의 (원천 표 · 열이 계산 정의의 근거다)
SQL_TAG_MINUTES = """SELECT asset, count(*)::int AS minutes FROM tag_1m
 WHERE name = %(tag)s AND bucket >= %(t0)s AND bucket < %(t1)s GROUP BY asset ORDER BY asset"""
SQL_TRIPS = """SELECT alert_id, asset, pattern, raised_at, cleared_at FROM alerts
 WHERE right(pattern, 5) = '_TRIP' AND raised_at IS NOT NULL AND raised_at < %(t1)s
   AND (cleared_at IS NULL OR cleared_at > %(t0)s) ORDER BY raised_at"""
SQL_TAG_PEAK = """SELECT DISTINCT ON (asset) asset, bucket AS at, max AS peak, count(*) OVER (PARTITION BY asset)::int AS n
 FROM tag_1m WHERE name = %(tag)s AND bucket >= %(t0)s AND bucket < %(t1)s ORDER BY asset, max DESC NULLS LAST"""
SQL_TAG_AVG = """SELECT asset, avg(avg) AS mean, count(*)::int AS n FROM tag_1m
 WHERE name = %(tag)s AND bucket >= %(t0)s AND bucket < %(t1)s GROUP BY asset ORDER BY asset"""
SQL_ENERGY_RATE = "SELECT site, energy_rate FROM ent.energy_demand ORDER BY site"
SQL_WORK_ORDERS = """SELECT w.id, w.asset, w.task, w.option_id, w.decision_id, w.created_at, m.clean_cost
 FROM ent.work_orders w LEFT JOIN ent.maintenance_profiles m ON m.asset = w.asset
 WHERE w.cancelled_at IS NULL AND w.created_at >= %(t0)s AND w.created_at < %(t1)s ORDER BY w.created_at"""
SQL_PURCHASES = """SELECT r.id, r.part, r.supplier, r.supplier_name, r.asset, r.decision_id, r.created_at,
       s.price, s.quality_score, p.name AS quote_part
 FROM ent.purchase_requests r LEFT JOIN ent.suppliers s ON s.id = r.supplier LEFT JOIN ent.parts p ON p.part_no = s.part_no
 WHERE r.cancelled_at IS NULL AND r.created_at >= %(t0)s AND r.created_at < %(t1)s ORDER BY r.created_at"""
SQL_INVENTORY = "SELECT asset, fg_item, fg_stock FROM ent.fg_inventory ORDER BY asset"
SQL_INSTANCES = """SELECT proc_inst_id, proc_def_id, status::text AS status, start_date, end_date, end_event, variables_data
 FROM public.bpm_proc_inst WHERE tenant_id = %(tenant)s AND NOT is_deleted
   AND start_date >= %(t0)s AND start_date < %(t1)s ORDER BY start_date DESC LIMIT 2000"""

Q_MEASURES = """MATCH (m:Measure)
OPTIONAL MATCH (m)-[:MEASURES]->(o:Objective)
OPTIONAL MATCH (o)-[:IN_PERSPECTIVE]->(p:Perspective)
OPTIONAL MATCH (m)-[:OWNED_BY]->(d:OrgUnit)
RETURN m.id AS id, m.name AS name, m.unit AS unit, m.direction AS direction, m.target AS target, m.formula AS formula,
       m.frequency AS frequency, m.kpiRole AS kpiRole, m.thresholdWarn AS warn, m.thresholdCrit AS crit,
       o.id AS objective, o.name AS objectiveName, o.description AS objectiveDescription,
       p.id AS perspective, p.name AS perspectiveName, p.order AS perspectiveOrder, d.name AS owner
ORDER BY m.id"""
Q_SUPPORTS = "MATCH (a:Objective)-[:SUPPORTS]->(b:Objective) RETURN a.id AS source, b.id AS target ORDER BY a.id, b.id"
# 인터록 여유: 이 지표에 INFLUENCES 하는 상태 변수 중 한계값(limit)이 있는 것과 그 변수를 관측하는 센서 태그
Q_LIMIT = """MATCH (v:StateVariable)-[:INFLUENCES]->(:Measure {id: $id}) WHERE v.limit IS NOT NULL
OPTIONAL MATCH (s:Sensor)-[:OBSERVES]->(v)
RETURN v.id AS id, v.name AS name, v.limit AS limit, v.unit AS unit, s.tag AS tag ORDER BY v.id"""


# ============================================================== 지표별 계산
def _minutes(f: Fetch, w: Window) -> tuple[dict, int]:
    rows = f('ts', 'tag_minutes', SQL_TAG_MINUTES, {**w.params, 'tag': 'TS1'})
    return {r['asset']: int(r['minutes']) for r in rows}, sum(int(r['minutes']) for r in rows)


def _trips(f: Fetch, w: Window) -> list[dict]:
    out = []
    for r in f('ts', 'trips', SQL_TRIPS, w.params):
        raised, cleared = _utc(r['raised_at']), _utc(r['cleared_at'])
        lo, hi = max(raised, w.start), min(cleared or w.end, w.end)
        out.append({'alert_id': r['alert_id'], 'asset': r['asset'], 'pattern': r['pattern'], 'raised_at': raised,
                    'cleared_at': cleared, 'minutes': max(0.0, (hi - lo).total_seconds() / 60),
                    'in_window': raised >= w.start})
    return out


def _uptime(f: Fetch, w: Window):
    obs, n_tag = _minutes(f, w)
    trips = _trips(f, w)
    down = {}
    for t in trips:
        down[t['asset']] = down.get(t['asset'], 0.0) + t['minutes']
    up = {a: max(0.0, m - down.get(a, 0.0)) for a, m in obs.items()}
    return obs, n_tag, trips, down, up


def _trip_events(trips):
    return [{'asset': t['asset'], 'at': t['raised_at'], 'end': t['cleared_at'], 'alert_id': t['alert_id'], 'weight': round(t['minutes'], 1),
             'label': f"{t['asset']} 보호 정지 {t['minutes']:.1f}분" + ('' if t['cleared_at'] else ' (해제 기록 없음)')} for t in trips]


def calc_availability(f: Fetch, w: Window, ctx: dict) -> Calc:
    obs, n_tag, trips, down, up = _uptime(f, w)
    rows = [('ts', 'tag_1m', n_tag), ('ts', 'alerts', len(trips))]
    if not obs:
        return Calc(None, rows=rows, status='no_data', reason='기간 안 TS1 1분 집계(tag_1m)가 없습니다 — 설비 시뮬레이터 · 수집기가 '
                    '꺼져 있었거나 기간이 1분보다 짧습니다')
    per = {a: round(100 * up[a] / m, 2) for a, m in obs.items() if m}
    value = round(100 * sum(up.values()) / sum(obs.values()), 2)
    detail = [{'설비': a, '관측 분': obs[a], '보호 정지 분': round(down.get(a, 0.0), 1), '가동률 %': per.get(a)} for a in sorted(obs)]
    return Calc(value, per, rows, _trip_events(trips), detail=detail)


def calc_mtbf(f: Fetch, w: Window, ctx: dict) -> Calc:
    obs, n_tag, trips, down, up = _uptime(f, w)
    scale = ctx['time_scale']
    rows = [('ts', 'tag_1m', n_tag), ('ts', 'alerts', len(trips))]
    if not obs:
        return Calc(None, rows=rows, status='no_data', reason='기간 안 TS1 1분 집계(tag_1m)가 없어 운전 시간을 알 수 없습니다')
    run_h = {a: up[a] / 60 * scale for a in obs}
    fails = {a: sum(1 for t in trips if t['asset'] == a and t['in_window']) for a in obs}
    per = {a: (round(run_h[a] / fails[a], 1) if fails[a] else None) for a in obs}
    detail = [{'설비': a, '운전 시간 h(설비 시간)': round(run_h[a], 1), '고장(보호 정지) 건': fails[a], 'MTBF h': per[a]} for a in sorted(obs)]
    total_f = sum(fails.values())
    if not total_f:
        return Calc(None, per, rows, [], status='no_data', detail=detail,
                    reason=f'기간 안 고장(보호 정지) 0건 — 운전 {sum(run_h.values()):.0f} h(설비 시간) 동안 고장이 없어 평균 간격을 나눌 수 없습니다')
    return Calc(round(sum(run_h.values()) / total_f, 1), per, rows, _trip_events([t for t in trips if t['in_window']]), detail=detail,
                note=f'운전 시간 = (관측 분 − 보호 정지 분) ÷ 60 × 배속 {scale:g}')


def calc_safety_margin(f: Fetch, w: Window, ctx: dict) -> Calc:
    limits = [r for r in f('graph', 'limit', Q_LIMIT, {'id': ctx['measure']['id']}) if r.get('tag')]
    if len(limits) != 1:
        raise SourceError(f'지식 그래프에서 이 지표의 한계값을 가진 관측 변수를 하나로 정할 수 없습니다 (찾은 수 {len(limits)})')
    lim = limits[0]
    rows_ = f('ts', 'tag_peak:' + lim['tag'], SQL_TAG_PEAK, {**w.params, 'tag': lim['tag']})
    n = sum(int(r['n']) for r in rows_)
    rows = [('graph', 'StateVariable.limit', 1), ('ts', 'tag_1m', n)]
    if not rows_:
        return Calc(None, rows=rows, status='no_data', reason=f"기간 안 {lim['tag']} 1분 집계(tag_1m)가 없습니다")
    per = {r['asset']: round(float(lim['limit']) - float(r['peak']), 2) for r in rows_ if r['peak'] is not None}
    events = [{'asset': r['asset'], 'at': _utc(r['at']), 'end': _utc(r['at']) + timedelta(minutes=1), 'alert_id': None, 'weight': float(r['peak']),
               'label': f"{r['asset']} 최고 {lim['tag']} {float(r['peak']):.1f} {lim['unit'] or ''} ({_utc(r['at']):%m-%d %H:%M})"}
              for r in rows_ if r['peak'] is not None]
    if not per:
        return Calc(None, rows=rows, status='no_data', reason=f"기간 안 {lim['tag']} 최고값이 모두 비어 있습니다")
    detail = [{'설비': r['asset'], f"최고 {lim['tag']}": round(float(r['peak']), 2), '한계': lim['limit'], '여유': per.get(r['asset'])} for r in rows_]
    return Calc(min(per.values()), per, rows, events, detail=detail,
                note=f"{lim['name']} 한계 {lim['limit']} {lim['unit'] or ''} − 기간 최고값, 설비 중 가장 작은 여유")


def calc_energy_use(f: Fetch, w: Window, ctx: dict) -> Calc:
    rows_ = f('ts', 'tag_avg:EPS1', SQL_TAG_AVG, {**w.params, 'tag': 'EPS1'})
    rows = [('ts', 'tag_1m', sum(int(r['n']) for r in rows_))]
    if not rows_:
        return Calc(None, rows=rows, status='no_data', reason='기간 안 EPS1(주 모터 전력) 1분 집계가 없습니다')
    per = {r['asset']: round(float(r['mean']) * 24, 2) for r in rows_}
    detail = [{'설비': r['asset'], '평균 전력 kW': round(float(r['mean']), 3), 'kWh/일': per[r['asset']]} for r in rows_]
    return Calc(round(sum(per.values()), 2), per, rows, detail=detail, note='주 모터(EPS1)만 — 팬 전력 태그는 없음')


def calc_energy_cost(f: Fetch, w: Window, ctx: dict) -> Calc:
    use = calc_energy_use(f, w, ctx)
    rates = f('biz', 'energy_rate', SQL_ENERGY_RATE)
    rows = use.rows + [('biz', 'ent.energy_demand', len(rates))]
    if use.value is None:
        return Calc(None, rows=rows, status='no_data', reason=use.reason)
    if len(rates) != 1:
        return Calc(None, rows=rows, status='no_data',
                    reason=f'ent.energy_demand 사업장 행이 {len(rates)}개 — 적용할 전력량 요율을 하나로 정할 수 없습니다')
    rate = float(rates[0]['energy_rate'])
    per = {a: round(v * 30 * rate, 2) for a, v in use.per_asset.items()}
    return Calc(round(use.value * 30 * rate, 2), per, rows, detail=[{'kWh/일': use.value, '요율 만원/kWh': rate, '만원/월': round(use.value * 30 * rate, 2)}],
                note='한 달 = 30일(설비 시간), 기본요금 제외')


def calc_maint_cost(f: Fetch, w: Window, ctx: dict) -> Calc:
    rows_ = f('biz', 'work_orders', SQL_WORK_ORDERS, w.params)
    rows = [('biz', 'ent.work_orders', len(rows_))]
    per, unknown, detail = {}, [], []
    for r in rows_:
        cost = float(r['clean_cost']) if '세척' in (r['task'] or '') and r['clean_cost'] is not None else None
        detail.append({'작업지시': r['id'], '설비': r['asset'], '작업': r['task'], '비용 만원': cost})
        if cost is None:
            unknown.append(r)
        else:
            per[r['asset']] = per.get(r['asset'], 0.0) + cost
    value = round(sum(per.values()), 2)
    if unknown:
        return Calc(value, per, rows, status='partial', detail=detail,
                    reason=f'작업지시 {len(rows_)}건 중 {len(unknown)}건은 업무 DB에 작업 비용 열이 없습니다 (세척 비용 '
                           f'maintenance_profiles.clean_cost 만 있음): ' + ', '.join(sorted({u["task"] for u in unknown}))[:200])
    return Calc(value, per, rows, detail=detail, note=f'기간 합계 · 작업지시 {len(rows_)}건')


def _purchases(f: Fetch, w: Window):
    rows_ = f('biz', 'purchases', SQL_PURCHASES, w.params)
    known, unknown = [], []
    for r in rows_:
        (known if r['price'] is not None and r['quote_part'] and r['quote_part'] in (r['part'] or '') else unknown).append(r)
    return rows_, known, unknown


def _purchase_reason(rows_, unknown) -> str:
    pairs = sorted({f"{u['part']}({u['supplier_name'] or u['supplier']})" for u in unknown})
    return (f'구매요청 {len(rows_)}건 중 {len(unknown)}건은 업무 DB 공급사 견적(ent.suppliers)에 같은 부품의 단가가 없습니다: '
            + ', '.join(pairs)[:200])


def _purchase_detail(rows_):
    return [{'구매요청': r['id'], '부품': r['part'], '공급사': r['supplier_name'] or r['supplier'],
             '견적 부품': r['quote_part'], '단가 만원': float(r['price']) if r['price'] is not None and r['quote_part'] and r['quote_part'] in (r['part'] or '') else None}
            for r in rows_]


def calc_part_cost(f: Fetch, w: Window, ctx: dict) -> Calc:
    rows_, known, unknown = _purchases(f, w)
    rows = [('biz', 'ent.purchase_requests', len(rows_)), ('biz', 'ent.suppliers', len(known))]
    per = {}
    for r in known:
        per[r['asset']] = per.get(r['asset'], 0.0) + float(r['price'])
    value = round(sum(per.values()), 2)
    if unknown:
        return Calc(value, per, rows, status='partial', reason=_purchase_reason(rows_, unknown), detail=_purchase_detail(rows_))
    return Calc(value, per, rows, detail=_purchase_detail(rows_), note=f'기간 합계 · 요청 1건 = 1개 (구매요청 표에 수량 열 없음)')


def _purchase_avg(f, w, column, label):
    rows_, known, unknown = _purchases(f, w)
    rows = [('biz', 'ent.purchase_requests', len(rows_)), ('biz', 'ent.suppliers', len(known))]
    if not rows_:
        return Calc(None, rows=rows, status='no_data', reason='기간 안 구매요청이 없습니다')
    if not known:
        return Calc(None, rows=rows, status='no_data', reason=_purchase_reason(rows_, unknown), detail=_purchase_detail(rows_))
    value = round(sum(float(r[column]) for r in known) / len(known), 3)
    calc = Calc(value, {}, rows, detail=_purchase_detail(rows_), note=f'{label} · 단가를 아는 구매요청 {len(known)}건 평균')
    if unknown:
        calc.status, calc.reason = 'partial', _purchase_reason(rows_, unknown)
    return calc


def calc_part_price(f, w, ctx):
    return _purchase_avg(f, w, 'price', '공급사 견적 단가')


def calc_part_quality(f, w, ctx):
    return _purchase_avg(f, w, 'quality_score', '공급사 품질 점수(0~1)')


def calc_inventory(f: Fetch, w: Window, ctx: dict) -> Calc:
    rows_ = f('biz', 'inventory', SQL_INVENTORY)
    rows = [('biz', 'ent.fg_inventory', len(rows_))]
    if not rows_:
        return Calc(None, rows=rows, status='no_data', reason='ent.fg_inventory 에 재고 행이 없습니다')
    per = {r['asset']: int(r['fg_stock']) for r in rows_}
    return Calc(sum(per.values()), per, rows, detail=[{'설비': r['asset'], '품목': r['fg_item'], '재고 ea': r['fg_stock']} for r in rows_],
                note='현재값 — 재고 표는 이력이 없어 기간 선택과 무관')


def instances(f: Fetch, w: Window, tenant: str) -> list[dict]:
    out = []
    for r in f('biz', 'instances', SQL_INSTANCES, {**w.naive, 'tenant': tenant}):
        v = {x.get('key'): x.get('value') for x in (r.get('variables_data') or []) if isinstance(x, dict)}
        alert = v.get('alert') if isinstance(v.get('alert'), dict) else {}
        out.append({'id': r['proc_inst_id'], 'definition': r['proc_def_id'], 'status': r['status'],
                    'start': _utc(r['start_date']), 'end': _utc(r['end_date']), 'endEvent': r['end_event'],
                    'asset': v.get('asset'), 'pattern': v.get('pattern') or alert.get('pattern'),
                    'alertId': v.get('alert_id') or alert.get('alertId'), 'cause': v.get('cause'),
                    'failureMode': v.get('failure_mode'), 'chosenSkill': v.get('chosen_skill'), 'recovered': v.get('recovered')})
    return out


Q_SKILL_NAMES = "MATCH (k:Skill) WHERE k.id IN $ids RETURN k.id AS id, k.name AS name"


def calc_precedent(f: Fetch, w: Window, ctx: dict) -> Calc:
    insts = instances(f, w, ctx['tenant'])
    chosen = [i for i in insts if i['chosenSkill']]
    per, by_skill = {}, {}
    for i in chosen:
        per[i['asset']] = per.get(i['asset'], 0) + 1
        by_skill[i['chosenSkill']] = by_skill.get(i['chosenSkill'], 0) + 1
    names = {r['id']: r['name'] for r in f('graph', 'skill_names', Q_SKILL_NAMES, {'ids': sorted(by_skill)})} if by_skill else {}
    return Calc(len(chosen), per, [('proc', 'bpm_proc_inst', len(insts))],
                detail=[{'고른 조치': names.get(k) or '그래프에 없는 조치', '건수': n} for k, n in sorted(by_skill.items(), key=lambda x: -x[1])],
                note=f'처리 건 {len(insts)}건 중 사람이 조치를 고른 건')


# 지표별 계산 정의 — 원천 표 · 열 · 식. 'reason' 이 있으면 계산 불가 사유다. 합성 지표는 그래프 식 문자열(formula)을 쓴다.
DEFINITIONS: dict[str, dict] = {
    'msr:availability': dict(fn=calc_availability, sources=[('ts', 'tag_1m', 'bucket · asset · name=TS1 (관측 분)'),
                                                            ('ts', 'alerts', 'pattern *_TRIP · raised_at · cleared_at')],
                             formula='100 × Σ(관측 분 − 보호 정지 분) ÷ Σ 관측 분 (보호 정지 = 경보 pattern *_TRIP 의 발생~해제, 기간 경계로 자름)'),
    'msr:mtbf': dict(fn=calc_mtbf, sources=[('ts', 'tag_1m', 'name=TS1 (관측 분)'), ('ts', 'alerts', 'pattern *_TRIP · raised_at · cleared_at')],
                     formula='Σ 운전 시간(설비 h = (관측 분 − 보호 정지 분) ÷ 60 × 배속) ÷ 기간 안에 시작한 보호 정지(트립) 수'),
    'msr:safety-margin': dict(fn=calc_safety_margin, sources=[('graph', 'StateVariable', 'limit (이 지표에 INFLUENCES 하는 변수) · Sensor.tag'),
                                                              ('ts', 'tag_1m', 'max (그 태그의 1분 최고값)')],
                              formula='한계값 − 기간 최고값, 설비 중 최솟값'),
    'msr:energy-use': dict(fn=calc_energy_use, sources=[('ts', 'tag_1m', 'avg · name=EPS1 (주 모터 전력 kW)')],
                           formula='Σ 설비별 평균 전력(kW) × 24'),
    'msr:energy-cost': dict(fn=calc_energy_cost, sources=[('ts', 'tag_1m', 'avg · name=EPS1'), ('biz', 'ent.energy_demand', 'energy_rate (만원/kWh)')],
                            formula='전력 사용량(kWh/일) × 30 × energy_rate'),
    'msr:maint-cost': dict(fn=calc_maint_cost, unit='만원 (기간 합계)', sources=[('biz', 'ent.work_orders', 'created_at · task · asset (취소 제외)'),
                                                        ('biz', 'ent.maintenance_profiles', 'clean_cost (세척 작업 1회 비용)')],
                           formula='Σ 기간 작업지시 비용 (세척 작업 = clean_cost, 그 밖의 작업은 비용 원천 없음 → 부분 실적)'),
    'msr:part-cost': dict(fn=calc_part_cost, unit='만원 (기간 합계)', sources=[('biz', 'ent.purchase_requests', 'created_at · part · supplier (취소 제외)'),
                                                      ('biz', 'ent.suppliers · ent.parts', 'price · part_no → name')],
                          formula='Σ 기간 구매요청 견적 단가 (요청 1건 = 1개, 견적 부품과 요청 부품이 같을 때만)'),
    'msr:part-price': dict(fn=calc_part_price, sources=[('biz', 'ent.purchase_requests', 'part · supplier'), ('biz', 'ent.suppliers', 'price')],
                           formula='단가를 아는 기간 구매요청의 견적 단가 평균'),
    'msr:part-quality': dict(fn=calc_part_quality, sources=[('biz', 'ent.purchase_requests', 'part · supplier'), ('biz', 'ent.suppliers', 'quality_score')],
                             formula='단가를 아는 기간 구매요청 공급사의 품질 점수 평균'),
    'msr:inventory': dict(fn=calc_inventory, sources=[('biz', 'ent.fg_inventory', 'fg_stock')], formula='Σ fg_stock (현재값)'),
    'msr:precedent': dict(fn=calc_precedent, unit='건 (기간)', sources=[('proc', 'bpm_proc_inst', 'start_date · variables_data.chosen_skill')],
                          formula='기간에 시작한 처리 건 중 chosen_skill(사람이 고른 조치)이 있는 건 수'),
    'msr:revenue': dict(reason='업무 DB에 판매 · 매출 원장이 없습니다 — production_orders.hour_value 는 계획상 시간당 생산 가치, '
                               'shipments 는 대체 출하 수량만 있고 단가가 없습니다'),
    'msr:inventory-cost': dict(reason='보관 단가(개당 · 일당 보관비) 열이 업무 DB에 없습니다 — fg_inventory 에는 수량만 있습니다'),
    'msr:penalty': dict(reason='오더 완료 · 출하 시각 기록이 없어 지연 시간을 셀 수 없습니다 — production_orders 에는 납기(due_at)만, '
                               'sales_contracts 에는 시간당 지체상금 단가(penalty_per_h)만 있습니다'),
    'msr:otd': dict(reason='납기 대비 실제 완료 · 출하 시각 기록이 없습니다 — production_orders 에는 due_at 만 있고 완료 시각 열이 없습니다'),
    'msr:quality-claim': dict(reason='클레임 접수 기록 표가 없습니다 — quality_profiles 에는 고온 로트의 클레임 위험 금액, '
                                     'lot_dispositions 에는 격리 · 출하 처분만 있습니다'),
    'msr:brand': dict(reason='브랜드 신뢰 지수(고객 설문 · 평가) 원천이 없습니다'),
    'msr:throughput': dict(reason='생산 개수 실적(생산 카운터 태그 · MES 실적 표)이 없습니다 — LoadSP 는 부하 설정(%)이고 '
                                  'production_orders.rate_per_h 는 계획 속도입니다'),
    'msr:oil-life': dict(reason='작동유 상태(산화도 · 수분 · 교환 기록) 측정 원천이 없습니다 — 유온 TS1 은 열화 요인일 뿐 잔여 수명 값이 아닙니다'),
}
TOKEN = re.compile(r'(msr|kpi):([\w-]+)')


def formula_terms(formula: str) -> list[tuple[int, str]]:
    """'msr:revenue - kpi:cost' → [(1,'msr:revenue'), (-1,'msr:cost')]. 식의 kpi: 접두는 같은 Measure(msr:)를 가리킨다."""
    terms, sign, rest = [], 1, formula.strip()
    pos = 0
    for m in TOKEN.finditer(rest):
        between = rest[pos:m.start()].strip()
        if between not in ('', '+', '-'):
            raise ValueError(f'식을 풀 수 없습니다: {formula}')
        sign = -1 if between == '-' else 1
        terms.append((sign, 'msr:' + m.group(2)))
        pos = m.end()
    if rest[pos:].strip() or not terms:
        raise ValueError(f'식을 풀 수 없습니다: {formula}')
    return terms


def definition_view(m: dict, names: dict | None = None) -> dict:
    d = DEFINITIONS.get(m['id'])
    if m.get('formula'):
        terms = formula_terms(m['formula'])
        text = ' '.join(('− ' if s < 0 else ('+ ' if i else '')) + (names or {}).get(t, t) for i, (s, t) in enumerate(terms))
        return {'kind': 'formula', 'formula': text, 'raw': m['formula'],
                'terms': [{'sign': s, 'measure': t, 'name': (names or {}).get(t, t)} for s, t in terms],
                'sources': [{'system': SYSTEM['graph'], 'table': 'Measure.formula = ' + m['formula'], 'columns': '구성 지표 실적'}]}
    if d is None:
        return {'kind': 'unavailable', 'reason': '이 지표의 계산 정의가 없습니다 (그래프에 새로 생긴 지표)'}
    if 'reason' in d:
        return {'kind': 'unavailable', 'reason': d['reason']}
    return {'kind': 'calc', 'formula': d['formula'],
            'sources': [{'system': SYSTEM[k], 'table': t, 'columns': c} for k, t, c in d['sources']]}


# ============================================================== 판정
def achievement(value: float, target, direction: str) -> tuple[bool | None, float | None]:
    if target is None:
        return None, None
    target = float(target)
    if direction == 'DOWN':
        met = value <= target
        rate = (100.0 if value <= 0 else target / value * 100) if target > 0 else (100.0 if value <= 0 else 0.0)
    else:
        met = value >= target
        rate = value / target * 100 if target else None
    return met, None if rate is None else round(max(0.0, rate), 1)


def _rows_view(rows) -> list[dict]:
    return [{'system': SYSTEM[k], 'table': t, 'rows': n} for k, t, n in rows]


def evaluate(m: dict, f: Fetch, w: Window, ctx: dict, done: dict) -> dict:
    """한 지표의 실적. done: 이미 계산한 지표(합성 지표가 구성 지표를 다시 계산하지 않게)."""
    if m['id'] in done:
        return done[m['id']]
    base = {k: m.get(k) for k in ('id', 'name', 'unit', 'direction', 'target', 'frequency', 'kpiRole', 'owner', 'warn', 'crit')}
    try:
        definition = definition_view(m, {k: v['name'] for k, v in ctx['measures'].items()})
    except ValueError as exc:
        definition = {'kind': 'unavailable', 'reason': str(exc)}
    out = dict(base, definition=definition, value=None, rate=None, met=None, perAsset={}, rows=[], detail=[], note=None, reason=None,
               displayUnit=(DEFINITIONS.get(m['id']) or {}).get('unit') or m.get('unit'))
    done[m['id']] = out   # 순환 식 방지: 계산 중인 자신은 미완으로 보인다
    if definition['kind'] == 'unavailable':
        out.update(status='unavailable', reason=definition['reason'])
        return out
    if definition['kind'] == 'formula':
        parts, missing, total, rows = [], [], 0.0, []
        for sign, mid in formula_terms(m['formula']):
            sub = ctx['measures'].get(mid)
            r = evaluate(sub, f, w, ctx, done) if sub else None
            if r is None or r.get('status') not in COMPUTED:
                missing.append(f"{(sub or {}).get('name', mid)}({STATUS.get((r or {}).get('status'), '없음')})")
                continue
            total += sign * r['value']
            rows += r['rows']
            parts.append({'sign': sign, 'measure': mid, 'name': sub['name'], 'value': r['value']})
        if missing:
            out.update(status='unavailable', reason=f"식({definition['formula']})의 구성 지표를 계산할 수 없습니다: " + ', '.join(missing))
            return out
        out.update(value=round(total, 2), rows=rows, detail=parts)
    else:
        try:
            calc: Calc = DEFINITIONS[m['id']]['fn'](f, w, ctx | {'measure': m})
        except SourceError as exc:
            out.update(status='error', reason=str(exc))
            return out
        out.update(value=calc.value, perAsset=calc.per_asset, rows=_rows_view(calc.rows), detail=calc.detail, note=calc.note,
                   reason=calc.reason, events=calc.events)
        if calc.status:
            out['status'] = calc.status
            return out
    met, rate = achievement(out['value'], m.get('target'), m.get('direction') or 'UP')
    out.update(met=met, rate=rate, status='no_target' if met is None else 'met' if met else 'missed')
    if met is not None and out['perAsset']:
        out['perAssetMet'] = {a: (None if v is None else achievement(v, m['target'], m.get('direction') or 'UP')[0])
                              for a, v in out['perAsset'].items()}
    return out


def _measures(f: Fetch) -> dict[str, dict]:
    try:
        rows = f('graph', 'measures', Q_MEASURES)
    except SourceError as exc:
        raise SourceError('지표 목록 · 목표값은 지식 그래프에 있습니다. ' + str(exc)) from exc
    if not rows:
        raise SourceError('지식 그래프에 성과 지표(Measure)가 없습니다 — 온톨로지 적재(kg-seed)를 확인하세요')
    return {r['id']: r for r in rows}


# ============================================================== B5 목표값 바꿔 보기 (시험 실행 — 그래프의 Measure.target 은 읽기만)
def check_targets(measures: dict, targets) -> dict[str, float]:
    """{지표 id: 시험 목표값}. 없는 지표 · 숫자가 아닌 값은 사람이 읽을 사유로 거절한다."""
    if targets is None:
        return {}
    if not isinstance(targets, dict):
        raise ValueError('목표 시험값은 {지표: 숫자} 모양이어야 합니다')
    out = {}
    for mid, v in targets.items():
        m = measures.get(mid)
        if m is None:
            raise ValueError(f'지식 그래프에 없는 성과 지표입니다: {mid}')
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            raise ValueError(f"「{m['name']}」 목표 시험값은 숫자여야 합니다 (받은 값: {v!r})")
        out[mid] = float(v)
    return out


def _with_targets(measures: dict, trial: dict) -> dict:
    """시험 목표를 넣은 사본. 원본 행(그래프에서 읽은 것)은 바꾸지 않는다."""
    return {mid: (dict(m, target=trial[mid]) if mid in trial else m) for mid, m in measures.items()}


def _judged(value, target, direction) -> dict:
    met, rate = achievement(value, target, direction or 'UP')
    return {'target': target, 'met': met, 'rate': rate, 'status': 'no_target' if met is None else 'met' if met else 'missed'}


def _trial_view(results: dict, original: dict, trial: dict) -> dict:
    """지표마다 원래 목표로 본 판정을 옆에 붙이고, 판정이 바뀐 지표를 모은다(실적 값은 같다 — 목표만 다르다)."""
    changed = []
    for mid, r in results.items():
        if mid not in trial:
            continue
        before = _judged(r['value'], original[mid].get('target'), original[mid].get('direction')) if r.get('status') in COMPUTED \
            else {'target': original[mid].get('target'), 'met': None, 'rate': None, 'status': r.get('status')}
        r['original'] = before
        r['trialTarget'] = trial[mid]
        if before['status'] != r.get('status') or before['rate'] != r.get('rate'):
            changed.append({'id': mid, 'name': r['name'], 'unit': r.get('unit'), 'value': r.get('value'),
                            'before': before, 'after': {k: r.get(k) for k in ('target', 'met', 'rate', 'status')}})
    return {'targets': [{'id': mid, 'name': original[mid]['name'], 'unit': original[mid].get('unit'),
                         'original': original[mid].get('target'), 'trial': v} for mid, v in sorted(trial.items())],
            'changed': changed,
            'note': '시험 목표는 이 계산에만 썼습니다. 지식 그래프의 목표값(Measure.target)은 읽기만 했고 그대로입니다'}


def report(sources, period='24h', *, now=None, start=None, end=None, time_scale=20.0, tenant='hyd', targets=None) -> dict:
    """BSC 관점 → 목표 → 지표 실적. 원천 하나가 실패해도 그 원천을 쓰는 지표만 '조회 실패'다.
    targets: B5 목표값 바꿔 보기 — {지표 id: 시험 목표}. 달성/미달 · 달성률을 그 목표로 다시 판정한다(원본 목표 불변)."""
    w = window(period, now, start, end)
    f = Fetch(sources)
    original = _measures(f)
    trial = check_targets(original, targets)
    measures = _with_targets(original, trial)
    try:
        supports = f('graph', 'supports', Q_SUPPORTS)
    except SourceError:
        supports = []
    ctx = {'time_scale': float(time_scale), 'tenant': tenant, 'measures': measures, 'window': w}
    done: dict = {}
    results = {mid: evaluate(m, f, w, ctx, done) for mid, m in measures.items()}
    persp: dict = {}
    for mid, m in measures.items():
        p = persp.setdefault(m.get('perspective') or '-', {'id': m.get('perspective'), 'name': m.get('perspectiveName') or '관점 없음',
                                                          'order': m.get('perspectiveOrder') or 0, 'objectives': {}})
        o = p['objectives'].setdefault(m.get('objective') or '-', {
            'id': m.get('objective'), 'name': m.get('objectiveName') or '목표 없음', 'description': m.get('objectiveDescription'),
            'supports': [s['target'] for s in supports if s['source'] == m.get('objective')], 'measures': []})
        o['measures'].append({k: v for k, v in results[mid].items() if k != 'events'})
    names = {m.get('objective'): m.get('objectiveName') for m in measures.values()}
    out = []
    for p in sorted(persp.values(), key=lambda p: -p['order']):        # 재무(4) → 고객 → 내부 → 학습(1): 전략맵 위에서 아래
        objs = list(p['objectives'].values())
        for o in objs:
            o['supports'] = [{'id': s, 'name': names.get(s, s)} for s in o['supports']]
            o['measures'].sort(key=lambda x: (x['kpiRole'] != 'lagging', x['id']))
        out.append({'id': p['id'], 'name': p['name'], 'objectives': objs})
    counts = {s: sum(1 for r in results.values() if r['status'] == s) for s in STATUS}
    rep = {'window': w.view(), 'timeScale': float(time_scale), 'perspectives': out,
           'summary': {'total': len(results), **counts, 'labels': STATUS}}
    if trial:
        rep['trial'] = _trial_view(results, original, trial)
        for p in out:                       # 지표 카드는 results 의 사본이라 원래 판정을 다시 붙인다
            for o in p['objectives']:
                for x in o['measures']:
                    if x['id'] in trial:
                        x.update(original=results[x['id']]['original'], trialTarget=trial[x['id']])
        before = dict(counts)
        for c in rep['trial']['changed']:
            before[c['after']['status']] -= 1
            before[c['before']['status']] += 1
        rep['summaryOriginal'] = {'total': len(results), **before, 'labels': STATUS}
    return rep


def definitions(sources) -> list[dict]:
    """지표별 계산 정의 표 (원천 표 · 열 · 식 / 계산 불가 사유). 실적은 읽지 않는다."""
    f = Fetch(sources)
    out = []
    measures = _measures(f)
    for mid, m in sorted(measures.items()):
        try:
            d = definition_view(m, {k: v['name'] for k, v in measures.items()})
        except ValueError as exc:
            d = {'kind': 'unavailable', 'reason': str(exc)}
        out.append({'id': mid, 'name': m['name'], 'unit': m['unit'], 'target': m.get('target'), 'kpiRole': m.get('kpiRole'),
                    'objective': m.get('objectiveName'), 'perspective': m.get('perspectiveName'), 'definition': d})
    return out


# ============================================================== 역추적
Q_PATHS = """MATCH path = (x)-[:INFLUENCES*1..4]->(m:Measure {id: $id})
WHERE all(n IN nodes(path) WHERE n:Measure OR n:StateVariable)
RETURN [n IN nodes(path) | {id: n.id, name: n.name, kind: CASE WHEN n:Measure THEN 'measure' ELSE 'state' END}] AS nodes,
       [r IN relationships(path) | {sign: r.sign, strength: r.strength, condition: r.condition, note: r.note}] AS rels
ORDER BY size(relationships(path)) LIMIT 300"""
Q_PATTERNS = """MATCH (ap:AnomalyPattern)-[:TESTS]->(:InputData)-[:REPRESENTS]->(v:StateVariable) WHERE v.id IN $ids
RETURN ap.id AS id, ap.code AS code, ap.name AS name, collect(DISTINCT v.id) AS via ORDER BY ap.id"""
Q_PATTERN_NAMES = "MATCH (ap:AnomalyPattern) WHERE ap.code IS NOT NULL RETURN ap.code AS code, ap.name AS name"
Q_CAUSES = """MATCH (c:Cause)-[:DISTURBS]->(v:StateVariable) WHERE v.id IN $ids
RETURN c.id AS id, c.name AS name, collect(DISTINCT v.id) AS via ORDER BY c.id"""
Q_SKILLS = """MATCH (k:Skill)-[a:AFFECTS]->(t) WHERE t.id IN $ids
RETURN k.id AS id, k.name AS name, k.sopId AS sopId, t.id AS target, a.sign AS sign, a.note AS note ORDER BY k.id, t.id"""
Q_OBJECTIVES = """MATCH (m:Measure {id: $id})-[:MEASURES]->(o:Objective)
OPTIONAL MATCH (o)-[:SUPPORTS*1..4]->(up:Objective)
OPTIONAL MATCH (up)-[:IN_PERSPECTIVE]->(p:Perspective)
RETURN o.id AS id, o.name AS name, collect(DISTINCT {id: up.id, name: up.name, perspective: p.name}) AS supports"""


def _drivers(f: Fetch, mid: str) -> dict[str, dict]:
    """지표에 INFLUENCES 경로로 닿는 상태 변수 · 지표. signs = {경로 부호의 곱: 그 부호의 첫(가장 짧은) 경로}.
    sign = 부호가 하나면 그 부호(+1 같은 방향, −1 반대), 경로마다 다르면 0."""
    nodes: dict[str, dict] = {}
    for row in f('graph', 'paths:' + mid, Q_PATHS, {'id': mid}):
        ns, rs = row['nodes'], row['rels']
        sign = 1
        for r in rs:
            sign *= 1 if (r.get('sign') or 1) > 0 else -1
        head = ns[0]
        text = ' → '.join(n['name'] for n in ns)
        cur = nodes.setdefault(head['id'], dict(head, signs={}, path=text, depth=len(rs), strength=rs[0].get('strength'),
                                                condition=next((r.get('condition') for r in rs if r.get('condition')), None)))
        cur['signs'].setdefault(sign, text)
    for n in nodes.values():
        n['sign'] = next(iter(n['signs'])) if len(n['signs']) == 1 else 0
    return nodes


def trace(sources, measure_id: str, period='24h', *, now=None, start=None, end=None, time_scale=20.0, tenant='hyd', targets=None) -> dict:
    """미달 지표 → 영향 경로(그래프) + 같은 기간 처리 기록의 원인 업무 · 조치 · 설비. targets: B5 시험 목표(원본 불변)."""
    w = window(period, now, start, end)
    f = Fetch(sources)
    original = _measures(f)
    trial = check_targets(original, targets)
    measures = _with_targets(original, trial)
    m = measures.get(measure_id)
    if m is None:
        raise KeyError(measure_id)
    ctx = {'time_scale': float(time_scale), 'tenant': tenant, 'measures': measures, 'window': w}
    result = evaluate(m, f, w, ctx, {})
    good = 1 if (m.get('direction') or 'UP') == 'UP' else -1
    drivers = _drivers(f, measure_id)
    ids = sorted(set(drivers) | {measure_id})
    sign_of = {measure_id: 1} | {k: v['sign'] for k, v in drivers.items()}
    patterns = {p['code']: p for p in f('graph', 'patterns:' + measure_id, Q_PATTERNS, {'ids': ids}) if p.get('code')}
    try:
        pattern_names = {r['code']: r['name'] for r in f('graph', 'pattern_names', Q_PATTERN_NAMES)}
    except SourceError:
        pattern_names = {}
    causes = {c['id']: c for c in f('graph', 'causes:' + measure_id, Q_CAUSES, {'ids': ids})}
    skills: dict[str, dict] = {}
    for s in f('graph', 'skills:' + measure_id, Q_SKILLS, {'ids': ids}):
        k = skills.setdefault(s['id'], {'id': s['id'], 'name': s['name'], 'sopId': s['sopId'], 'harm': [], 'help': []})
        af = 1 if (s.get('sign') or 1) > 0 else -1
        paths = {1: m['name']} if s['target'] == measure_id else drivers[s['target']]['signs']
        for sign, path in paths.items():
            (k['help'] if af * sign * good > 0 else k['harm']).append(path)
    for k in skills.values():   # +1 지표에 좋음 · −1 나쁨 · 0 경로마다 다름
        k['effect'] = 0 if k['harm'] and k['help'] else -1 if k['harm'] else 1
    objectives = f('graph', 'objectives:' + measure_id, Q_OBJECTIVES, {'id': measure_id})
    events = result.get('events') or []
    insts = instances(f, w, tenant)
    found = []
    for i in insts:
        why, score, tier = [], 0, 0
        ev = next((e for e in events if e.get('alert_id') and e['alert_id'] == i['alertId']), None)
        if ev:
            why.append('이 처리 건의 경보가 지표를 깎은 기록: ' + ev['label']); score, tier = 4, 2
        else:
            ev = next((e for e in events if e['asset'] == i['asset'] and i['start'] and e['at']
                       and i['start'] <= (e.get('end') or e['at']) and (i['end'] or w.end) >= e['at']), None)
            if ev:
                why.append('지표를 깎은 시각에 열려 있던 처리 건: ' + ev['label']); score, tier = 3, 1
        p = patterns.get(i['pattern'])
        if p:
            via = ', '.join(sorted({(drivers.get(v) or {}).get('name', v) for v in p['via']}))
            why.append(f"이상 패턴 「{p['name']}」 — 영향 경로의 {via} 값을 보고 울린 경보"); score += 2
        c = causes.get(i['cause'])
        if c:
            why.append(f"판정 원인 「{c['name']}」 — 영향 경로의 상태 변수를 흔드는 원인"); score += 1
        k = skills.get(i['chosenSkill'])
        if k and k['harm']:
            text = f"고른 조치 「{k['name']}」 — 이 지표를 나쁜 쪽으로 움직일 수 있음 (나쁜 경로: {' / '.join(k['harm'])}"
            why.append(text + (f"; 좋은 경로: {' / '.join(k['help'])})" if k['help'] else ')')); score += 1 if k['help'] else 2
        if why:
            found.append(dict(i, start=i['start'].isoformat() if i['start'] else None, end=i['end'].isoformat() if i['end'] else None,
                              reasons=why, score=score, tier=tier, weight=(ev or {}).get('weight', 0), link=f"#/instances/{i['id']}",
                              chosenSkillName=(skills.get(i['chosenSkill']) or {}).get('name'),
                              patternName=pattern_names.get(i['pattern']),
                              causeName=(causes.get(i['cause']) or {}).get('name')))
    # 지표를 많이 깎은 기록에 걸린 처리 건 먼저 → 그 기록의 경보 당사자 → 영향 경로 근거가 많은 것 → 최근 것
    found.sort(key=lambda x: x['start'] or '', reverse=True)
    found.sort(key=lambda x: (-x['weight'], -x['tier'], -x['score']))
    per = result.get('perAsset') or {}
    target = m.get('target')
    assets = []
    for a in sorted({*per, *(i['asset'] for i in found if i['asset'])}):
        v = per.get(a)
        assets.append({'asset': a, 'value': v, 'met': None if v is None or target is None else achievement(v, target, m.get('direction') or 'UP')[0],
                       'instances': sum(1 for i in found if i['asset'] == a),
                       'events': [e['label'] for e in events if e['asset'] == a][:5]})
    assets.sort(key=lambda a: (a['met'] is not False, -a['instances'], a['asset']))
    actions: dict[str, dict] = {}
    for i in found:
        if i['chosenSkill']:
            x = actions.setdefault(i['chosenSkill'], {'id': i['chosenSkill'], 'name': i['chosenSkillName'] or i['chosenSkill'],
                                                      'count': 0, 'effect': (skills.get(i['chosenSkill']) or {}).get('effect')})
            x['count'] += 1
    if measure_id in trial:
        _trial_view({measure_id: result}, original, trial)
    return {
        'window': w.view(), 'measure': {k: v for k, v in result.items() if k != 'events'},
        'drivers': sorted(({'id': k, 'name': d['name'], 'kind': d['kind'], 'path': d['path'], 'depth': d['depth'],
                            'sign': d['sign'], 'strength': d['strength'], 'condition': d['condition'],
                            'effect': d['sign'] * good, 'paths': [{'effect': sg * good, 'path': t} for sg, t in sorted(d['signs'].items())]}
                           for k, d in drivers.items()), key=lambda d: (d['depth'], d['name'])),
        'objectives': [{'id': o['id'], 'name': o['name'], 'supports': [s for s in o['supports'] if s.get('id')]} for o in objectives],
        'patterns': [{'code': c, 'name': p['name']} for c, p in sorted(patterns.items())],
        'skills': sorted(skills.values(), key=lambda s: (s['effect'], s['name'])),
        'instances': found[:30], 'instanceTotal': len(found), 'instancesRead': len(insts),
        'assets': assets, 'actions': sorted(actions.values(), key=lambda a: -a['count']),
    }


# ============================================================== 실제 원천 (process 서비스)
class PgSources:
    """시계열 · 업무 DB는 읽기 전용 트랜잭션, 그래프는 읽기 세션. 요청 하나 동안 연결을 재사용한다."""

    def __init__(self, ts_dsn: str, biz_dsn: str, driver_factory: Callable):
        self.dsn = {'ts': ts_dsn, 'biz': biz_dsn}
        self.driver_factory = driver_factory
        self.driver = None
        self.conns: dict = {}

    def _conn(self, kind):
        import psycopg
        from psycopg.rows import dict_row
        if kind not in self.conns:
            try:
                c = psycopg.connect(self.dsn[kind], connect_timeout=5, row_factory=dict_row, autocommit=False)
                c.read_only = True
            except Exception as exc:  # noqa: BLE001 — 연결 실패도 기억해 같은 요청의 다음 질의가 다시 기다리지 않게 한다
                c = SourceError(f'{SYSTEM[kind]}에 연결하지 못했습니다: {str(exc).splitlines()[0][:160]}')
            self.conns[kind] = c
        if isinstance(self.conns[kind], SourceError):
            raise self.conns[kind]
        return self.conns[kind]

    def _sql(self, kind, name, sql, params):
        import psycopg
        c = self._conn(kind)
        try:
            with c.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '8s'")
                cur.execute(sql, params)
                rows = cur.fetchall()
            c.commit()
            return rows
        except psycopg.errors.UndefinedTable as exc:
            c.rollback()
            raise SourceError(f'{SYSTEM[kind]}에 원천 표가 없습니다 ({name}): {str(exc).splitlines()[0][:160]}') from exc
        except psycopg.errors.UndefinedColumn as exc:
            c.rollback()
            raise SourceError(f'{SYSTEM[kind]} 원천 표에 필요한 열이 없습니다 ({name}): {str(exc).splitlines()[0][:160]}') from exc
        except psycopg.Error as exc:
            c.rollback()
            raise SourceError(f'{SYSTEM[kind]} 조회 실패 ({name}): {str(exc).splitlines()[0][:160]}') from exc

    def ts(self, name, sql, params):
        return self._sql('ts', name, sql, params)

    def biz(self, name, sql, params):
        return self._sql('biz', name, sql, params)

    def graph(self, name, cypher, params):
        try:
            if self.driver is None:
                self.driver = self.driver_factory()
            with self.driver.session() as s:
                return s.execute_read(lambda tx: [r.data() for r in tx.run(cypher, **params)])
        except Exception as exc:  # noqa: BLE001
            text = str(exc).splitlines()[0][:160] if str(exc) else type(exc).__name__
            raise SourceError(f'지식 그래프 조회 실패 ({name}): {text}') from exc

    def close(self):
        self.conns = {k: c for k, c in self.conns.items() if not isinstance(c, SourceError)}
        if self.driver is not None:
            try:
                self.driver.close()
            except Exception:  # noqa: BLE001
                pass
            self.driver = None
        for c in self.conns.values():
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        self.conns.clear()


def register(app, *, ts_dsn, biz_dsn, driver_factory, time_scale, tenant):
    """GET /api/kpi · /api/kpi/definitions · /api/kpi/trace — 모두 읽기 전용."""
    import asyncio
    from fastapi import HTTPException

    async def run(fn):
        def work():
            src = PgSources(ts_dsn, biz_dsn, driver_factory)
            try:
                return fn(src)
            finally:
                src.close()
        try:
            return await asyncio.get_running_loop().run_in_executor(None, work)
        except SourceError as exc:
            raise HTTPException(503, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, f'성과 지표 {exc.args[0]} 를 지식 그래프에서 찾을 수 없습니다') from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get('/api/kpi')
    async def kpi_report(period: str = '24h', start: str | None = None, end: str | None = None):
        return await run(lambda s: report(s, period, start=start, end=end, time_scale=time_scale, tenant=tenant))

    @app.get('/api/kpi/definitions')
    async def kpi_definitions():
        return await run(definitions)

    @app.get('/api/kpi/trace')
    async def kpi_trace(measure: str, period: str = '24h', start: str | None = None, end: str | None = None):
        return await run(lambda s: trace(s, measure, period, start=start, end=end, time_scale=time_scale, tenant=tenant))

    # B5 목표값 바꿔 보기: 같은 계산에 시험 목표만 넣는다(쓰기 없음 — 그래프 · DB 는 읽기 전용 연결)
    @app.post('/api/kpi/try')
    async def kpi_try(body: dict):
        b = body or {}
        return await run(lambda s: report(s, b.get('period') or '24h', start=b.get('start'), end=b.get('end'), time_scale=time_scale,
                                          tenant=tenant, targets=b.get('targets') or {}))

    @app.post('/api/kpi/try/trace')
    async def kpi_try_trace(body: dict):
        b = body or {}
        if not b.get('measure'):
            raise HTTPException(400, '원인을 찾을 지표(measure)를 지정하세요')
        return await run(lambda s: trace(s, b['measure'], b.get('period') or '24h', start=b.get('start'), end=b.get('end'),
                                         time_scale=time_scale, tenant=tenant, targets=b.get('targets') or {}))
