"""A7 손익 · What-if · 규칙 바꿔 보기 (순수 계산, 시험 실행만).

조치 판단(cards.evaluate)이 쓴 입력 묶음과 업무 DB(ent) 값을 받아 네 가지를 계산한다. 원본(그래프 · 업무 DB · 순위 정책)은
읽기만 하고, 시험값은 이 모듈 안의 사본에만 적용한다 — 쓰기 경로가 없다.

  ① 카드별 손익(원)   항목마다 값 · 식 · 출처(업무 DB 필드 · 문서 · 가정). 출처를 댈 수 없는 항목은 값을 만들지 않고 '미확인'으로 둔다.
  ② 값 바꿔 보기      시험값(납기 · 위약금 · 부품값 · 환율 …)으로 판단 순위(정책 점수)와 손익 순위를 다시 계산하고,
                       카드마다 "이 값이 얼마를 넘으면 1순위가 바뀐다"는 경계값을 찾아 그 값에서 실제로 다시 계산해 확인한다.
  ③ 몇 주 What-if     조치 → 설비 값(부하 · 팬) → 지표(가동률 · 생산량 · 비용 · 이익)를 영향 계수로 잇고 주별로 계산한다.
                       계수마다 출처 종류(데이터 · 문서 · 가정)가 붙는다. 같은 입력은 같은 결과다(난수 · 현재 시각 없음).
  ④ 규칙 바꿔 보기    순위 정책 항목 하나의 가중치, 감점 규칙 하나의 감점을 시험값으로 바꿔 순위를 다시 계산한다.
  ⑤ 관점 중요도(B5)   BSC 관점(재무 · 고객 · 내부 · 학습 — 이름과 지표 소속은 지식 그래프에서 읽음)마다 중요도 배수를 주면 카드 점수의
                       성과 지표 득실이 그 비중으로 다시 계산된다. 1순위가 뒤집히는 비중은 ②의 경계값 찾기를 그대로 쓴다.

돈 단위: 업무 DB는 만원, 화면은 원(× 10,000).
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import secrets
import threading
from datetime import datetime, timezone
from urllib.parse import quote

from hydcommon import ranking
from . import cards

WON = 10_000                       # 업무 DB 금액 단위 만원 → 원
FAN_NORMAL, FAN_MAX = 60.0, 100.0  # 설비 모델 정상 운전점 팬 60 %, 팬 최대 100 % (ot/plant-sim thermal.py 설명)
QUALITY_TS1 = 55.0                 # 고온 로트 품질 위험 기준 (매뉴얼 HM-7.5 "TS1 55 ℃ 미만", 순위 정책 quality 항목과 같은 선)
FX_TO_PART = 1.0                   # 환율 1 % → 수입 부품값 1 % (가정: 부품 전량 수입. 부호는 온톨로지 ext:fx -INFLUENCES(+1)-> msr:part-price)
WEEK_HOURS = 120.0                 # 주 운전 시간 (가정: 주 5일 × 24 h 연속 운전)
# 순위 정책 항목 이름 (포털 ui.js score.* 와 같은 말). 정책에 새 항목이 생기면 그 키를 그대로 보인다.
COMPONENT_LABELS = {'bsc': '성과 지표', 'forecast': '예측', 'warn': '경고', 'penalty': '감점', 'precedent': '과거 선택', 'delivery': '납기', 'quality': '품질'}

DOC_LOAD = {'kind': '문서', 'where': '설비 모델의 설계 부하 90 % (정상 운전점)', 'ref': 'ot/plant-sim/plantsim/thermal.py · cards.LOAD_DESIGN'}
DOC_FAN = {'kind': '문서', 'where': '설비 모델의 정상 팬 60 %, 팬 최대 100 % — 업무 DB 팬 최대 추가 전력은 60 → 100 % 증가분',
           'ref': 'thermal.py 정상 운전점 · EMS fan_boost_kw'}
DOC_TS1 = {'kind': '문서', 'where': '매뉴얼 유온 55 ℃ 기준 (순위 정책 품질 항목과 같은 선)', 'ref': 'HM-7.5 · ranking-default.json quality'}
ASSUME_FX = {'kind': '가정', 'where': '환율 1 % → 수입 부품값 1 % (부품 전량 수입 가정). 방향은 지식 지도의 환율 → 부품 단가 (+, 강함)',
             'ref': 'ext:fx -INFLUENCES(+1, high)-> msr:part-price'}
ASSUME_RISK = {'kind': '가정', 'where': '원인이 남아 있는 동안 고장 확률 = 운전 시간 ÷ MTBF, 근본 조치 카드(작업지시 포함)는 첫 주에 원인을 없앤다',
               'ref': 'Skill relation REMEDIED_BY · WO_CREATE'}
ASSUME_WEEK = {'kind': '가정', 'where': '주 운전 시간 120 h (주 5일 × 24 h 연속 운전)'}
ASSUME_RESTORE = {'kind': '가정', 'where': '근본 조치 뒤에는 정상 부하 90 % · 팬 60 %로 돌아간다. 완화 카드의 설정은 기간 내내 유지된다'}
ASSUME_REPAIR = {'kind': '가정', 'where': '고장이 나면 이 원인의 근본 조치 표준 작업 시간만큼 멈춘다 (CMMS 표준 작업)'}

# ---------------------------------------------------------------- 업무 DB 값 (읽기 전용 GET)
ENT_READS = (('mes', '/mes/orders?asset={asset}'), ('erp', '/erp/contract?asset={asset}'), ('cmms', '/cmms/history?asset={asset}'),
             ('qms', '/qms/lots?asset={asset}'), ('ems', '/ems/demand'), ('tasks', '/cmms/tasks?asset={asset}'))
ENT_FIELDS = {'mes': ('due_in_h', 'remaining_qty', 'rate_per_h', 'hour_value'), 'erp': ('penalty_per_h', 'failure_cost'),
              'cmms': ('mtbf_h',), 'qms': ('auto_qty', 'auto_claim', 'auto_defect_p'), 'ems': ('fan_boost_kw', 'energy_rate')}
FIELD_LABELS = {'mes.due_in_h': '납기까지 남은 시간', 'mes.remaining_qty': '오더 잔량', 'mes.rate_per_h': '시간당 생산 수량',
                'mes.hour_value': '시간당 생산 가치', 'erp.penalty_per_h': '납기 지연 위약금', 'erp.failure_cost': '계획 외 고장 1회 비용',
                'cmms.mtbf_h': '평균 고장 간격(MTBF)', 'qms.auto_qty': '고온 구간 OEM 로트 수량', 'qms.auto_claim': '고온 로트 클레임 금액',
                'qms.auto_defect_p': '고온 로트 불량 확률', 'ems.fan_boost_kw': '팬 최대 추가 전력', 'ems.energy_rate': '전력 단가'}
UNITS = {'mes.due_in_h': 'h', 'mes.remaining_qty': 'ea', 'mes.rate_per_h': 'ea/h', 'mes.hour_value': '만원/h', 'erp.penalty_per_h': '만원/h',
         'erp.failure_cost': '만원', 'cmms.mtbf_h': 'h', 'qms.auto_qty': 'ea', 'qms.auto_claim': '만원', 'qms.auto_defect_p': '확률',
         'ems.fan_boost_kw': 'kW', 'ems.energy_rate': '만원/kWh'}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _finite(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def load_money_facts(fetch, asset: str) -> dict:
    """fetch(endpoint, asset) -> enterprise JSON (agentsvc.tools.mcp_ent.fetch). Only GET reads; a failed read is a readable error."""
    raw = {}
    for key, path in ENT_READS:
        try:
            raw[key] = (path.replace('{asset}', asset), fetch(path, asset))
        except Exception as e:  # noqa: BLE001
            raise ValueError(f'업무 DB를 읽지 못했습니다 ({path.replace("{asset}", asset)}): {str(e)[:160]}') from e
    values = {}
    for system, fields in ENT_FIELDS.items():
        path, resp = raw[system]
        facts = resp.get('facts') or {}
        for f in fields:
            key = f'{system}.{f}'
            values[key] = {'value': _finite(facts.get(f)), 'system': resp.get('system') or system.upper(), 'path': path, 'field': f,
                           'label': FIELD_LABELS[key], 'unit': UNITS[key], 'as_of': resp.get('as_of')}
    tasks = {}
    tpath, tresp = raw['tasks']
    for r in tresp.get('records') or []:
        if isinstance(r, dict) and r.get('sop'):
            tasks[r['sop']] = {'sop': r['sop'], 'name': r.get('name') or r['sop'], 'stop_h': _finite(r.get('stop_h')),
                               'labor_cost': _finite(r.get('labor_cost')), 'part_no': r.get('part_no'), 'part_qty': _finite(r.get('part_qty')) or 0,
                               'table': r.get('source') or 'task_standards', 'path': tpath}
    parts = {}
    for part in sorted({t['part_no'] for t in tasks.values() if t.get('part_no')}):
        path = f'/scm/suppliers?part={quote(part)}'
        try:
            resp = fetch(path, asset)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f'업무 DB를 읽지 못했습니다 ({path}): {str(e)[:160]}') from e
        quotes = {s['id']: _finite(s.get('price')) for s in resp.get('records') or []
                  if isinstance(s, dict) and s.get('id') and (s.get('part_no') or s.get('part')) == part}
        parts[part] = {'std_price': _finite((resp.get('facts') or {}).get('std_price')) or None, 'quotes': quotes, 'path': path}
    return {'asset': asset, 'read_at': _now(), 'values': values, 'tasks': tasks, 'parts': parts}


# ---------------------------------------------------------------- 시험값으로 바꿀 수 있는 값
# id -> 라벨, 단위, 업무 DB 출처(money) 또는 고정 기준(base), 판단 사실 변수(fact), 쓰는 곳(kinds), 범위
VARIABLES = {
    'due_h': {'label': '납기까지 남은 시간', 'unit': 'h', 'money': 'mes.due_in_h', 'fact': 'order_due_h', 'kinds': ('decision', 'money', 'weeks')},
    'penalty_per_h': {'label': '납기 지연 위약금', 'unit': '만원/h', 'money': 'erp.penalty_per_h', 'fact': 'order_penalty_per_h', 'kinds': ('decision', 'money', 'weeks')},
    'claim': {'label': '고온 로트 클레임 금액', 'unit': '만원', 'money': 'qms.auto_claim', 'fact': 'hot_lot_claim', 'kinds': ('decision', 'money', 'weeks')},
    'hour_value': {'label': '시간당 생산 가치', 'unit': '만원/h', 'money': 'mes.hour_value', 'kinds': ('money', 'weeks')},
    'failure_cost': {'label': '계획 외 고장 비용', 'unit': '만원', 'money': 'erp.failure_cost', 'kinds': ('money', 'weeks')},
    'mtbf_h': {'label': '평균 고장 간격(MTBF)', 'unit': 'h', 'money': 'cmms.mtbf_h', 'kinds': ('money', 'weeks')},
    'part_price_pct': {'label': '부품값 변동', 'unit': '%', 'base': 0.0, 'lo': -90.0, 'hi': 400.0, 'kinds': ('money', 'weeks'),
                       'where': '업무 DB 부품 단가(SCM)에 곱하는 시험 변동률. 기준 0 % = 업무 DB 단가 그대로'},
    'fx_pct': {'label': '환율 변동', 'unit': '%', 'base': 0.0, 'lo': -50.0, 'hi': 400.0, 'kinds': ('money', 'weeks'),
               'where': '기준 0 % = 업무 DB 단가 그대로. 환율 1 % → 부품값 1 % (가정)'},
    'energy_rate': {'label': '전력 단가', 'unit': '만원/kWh', 'money': 'ems.energy_rate', 'kinds': ('money', 'weeks')},
    'week_hours': {'label': '주 운전 시간', 'unit': 'h', 'base': WEEK_HOURS, 'lo': 0.0, 'hi': 168.0, 'kinds': ('weeks',), 'where': ASSUME_WEEK['where']},
    'load_pct': {'label': '조치 부하 설정', 'unit': '%', 'lo': 60.0, 'hi': 100.0, 'kinds': ('weeks',),
                 'where': '고른 카드의 부하 명령(LOAD_SET, 없으면 설계 부하 90 %)을 바꿔 본다 — 조치 → 설비 값'},
}


def _base(mf: dict, vid: str):
    spec = VARIABLES[vid]
    if 'money' in spec:
        v = mf['values'].get(spec['money']) or {}
        return v.get('value'), dict(kind='데이터', where=f"업무 DB {v.get('system')} · {v.get('label')}", ref=f"{v.get('field')} · {v.get('path')}")
    return spec.get('base'), dict(kind='가정' if vid in ('week_hours', 'fx_pct', 'part_price_pct') else '문서', where=spec.get('where', ''))


def variable_list(mf: dict, trial: dict | None = None) -> list[dict]:
    out = []
    for vid, spec in VARIABLES.items():
        if vid == 'load_pct':
            continue                                   # 카드마다 다르다 (weeks에서 카드의 값으로)
        base, src = _base(mf, vid)
        t = (trial or {}).get(vid)
        out.append({'id': vid, 'label': spec['label'], 'unit': spec['unit'], 'base': base, 'value': base if t is None else t,
                    'trial': t is not None, 'kinds': list(spec['kinds']), 'source': src, 'fact': spec.get('fact')})
    return out


def check_trial(values: dict | None) -> dict:
    out = {}
    for vid, v in (values or {}).items():
        if vid not in VARIABLES:
            raise ValueError(f"바꿀 수 없는 값입니다: {vid} (가능: {', '.join(VARIABLES)})")
        x = _finite(v)
        if x is None:
            raise ValueError(f"{VARIABLES[vid]['label']} 시험값은 숫자여야 합니다")
        lo, hi = VARIABLES[vid].get('lo', 0.0), VARIABLES[vid].get('hi')
        if x < lo or (hi is not None and x > hi):
            raise ValueError(f"{VARIABLES[vid]['label']} 시험값 {x:g}는 허용 범위({lo:g} ~ {'' if hi is None else f'{hi:g}'}) 밖입니다")
        out[vid] = x
    return out


# ---------------------------------------------------------------- 카드에서 읽는 것 (온톨로지 스킬 명령)
def card_shape(o: dict) -> dict:
    cmds = {a.get('code'): a.get('value') for a in o.get('actions') or [] if a.get('code') and a.get('kind', 'command') == 'command'}
    wos = [str(a.get('value')) for a in o.get('actions') or [] if a.get('code') == 'WO_CREATE' and a.get('value')]
    pr = next((a.get('value') for a in o.get('actions') or [] if a.get('code') == 'PR_CREATE'), None)
    load = _finite(cmds.get('LOAD_SET'))
    fan = _finite(cmds.get('FAN_SET'))
    ts1 = next((f.get('value') for f in o.get('forecast') or [] if f.get('variable') == 'sv:ts1'), None)
    return {'load': cards.LOAD_DESIGN if load is None else load, 'load_cmd': load is not None, 'fan_delta': 0.0 if fan is None else fan - FAN_NORMAL,
            'stop_cmd': 'STOP' in cmds, 'wos': wos, 'pr': pr, 'ts1': _finite(ts1),
            'remedy': bool(wos) or o.get('relation') == 'REMEDIED_BY'}


def _src_field(mf, key, trial_vid=None, trial=None):
    v = mf['values'][key]
    if trial_vid and trial and trial_vid in trial:
        return {'kind': '시험값', 'where': f"{v['label']} {trial[trial_vid]:g} {v['unit']} (업무 DB 값 {v['value']:g})",
                'ref': f"{v['system']} {v['field']} · {v['path']}"}
    shown = '없음' if v['value'] is None else f"{v['value']:g} {v['unit']}"
    return {'kind': '데이터', 'where': f"업무 DB {v['system']} · {v['label']} {shown}", 'ref': f"{v['system']} {v['field']} = {v['value']} · {v['path']}"}


class _Inputs:
    """업무 DB 값 + 시험값. get(key)는 (값, 출처) — 값이 없으면 None."""

    def __init__(self, mf: dict, trial: dict):
        self.mf, self.trial = mf, trial
        self.rev = {spec['money']: vid for vid, spec in VARIABLES.items() if 'money' in spec}

    def get(self, key):
        vid = self.rev.get(key)
        if vid in self.trial:
            return self.trial[vid], _src_field(self.mf, key, vid, self.trial)
        v = self.mf['values'].get(key) or {}
        return v.get('value'), _src_field(self.mf, key)

    def pct(self, vid):
        return self.trial.get(vid, VARIABLES[vid]['base'])


def _item(key, label, value, formula, sources, note=None):
    return {'key': key, 'label': label, 'value_won': None if value is None else int(round(-value * WON)),
            'formula': formula, 'sources': sources, **({'note': note} if note else {})}


def _missing(key, label, why, sources=()):
    return {'key': key, 'label': label, 'value_won': None, 'missing': why, 'formula': None, 'sources': list(sources)}


def _tasks_of(shape, mf):
    found, missing = [], []
    for sop in shape['wos']:
        t = mf['tasks'].get(sop)
        (found if t and t.get('stop_h') is not None and t.get('labor_cost') is not None else missing).append(t or {'sop': sop})
    return found, missing


def _task_src(t):
    return {'kind': '데이터', 'where': f"업무 DB CMMS 표준 작업 '{t['name']}' 정지 {t['stop_h']:g} h · 작업비 {t['labor_cost']:g}만원",
            'ref': f"{t['table']} {t['sop']} · {t['path']}"}


def card_money(o: dict, mf: dict, trial: dict | None = None, hours: float | None = None) -> dict:
    """한 카드의 예상 손익(원) — 비용은 음수. hours: 계산 기간(기본 = 납기까지 남은 시간)."""
    trial = trial or {}
    ins, s = _Inputs(mf, trial), card_shape(o)
    items = []
    due, due_src = ins.get('mes.due_in_h')
    H = hours if hours is not None else (None if due is None else max(0.0, due))
    hv, hv_src = ins.get('mes.hour_value')
    rate, rate_src = ins.get('mes.rate_per_h')
    tasks, tmiss = _tasks_of(s, mf)
    stop_h = sum(t['stop_h'] for t in tasks)
    stop_src = [_task_src(t) for t in tasks]
    load_src = {'kind': '문서', 'where': f"카드의 부하 명령 {s['load']:g} %", 'ref': '온톨로지 Skill -CONSISTS_OF-> LOAD_SET'} if s['load_cmd'] else \
        {'kind': '문서', 'where': '부하 명령 없음 → 설계 부하 90 % 유지'}
    r = s['load'] / cards.LOAD_DESIGN
    stop_unknown = bool(tmiss) or (s['stop_cmd'] and not tasks)
    why_stop = ('업무 DB CMMS 표준 작업에 이 카드 작업지시(' + ', '.join(t['sop'] for t in tmiss) + ')의 정지 시간 · 작업비가 없음') if tmiss else \
        '정지 명령의 정지 시간을 업무 DB에서 찾을 수 없음 (CMMS 표준 작업 없음)'
    # 1. 생산 감소
    if H is None or hv is None:
        items.append(_missing('production', '생산 감소', '납기 · 시간당 생산 가치 값이 업무 DB에 없음', [due_src, hv_src]))
    elif stop_unknown:
        items.append(_missing('production', '생산 감소', why_stop, [hv_src]))
    else:
        lost_h = H * (1 - r) + stop_h
        items.append(_item('production', '생산 감소', hv * lost_h,
                           f"시간당 생산 가치 {hv:g}만원 × (기간 {H:g} h × (1 − 부하 {s['load']:g}/90) + 작업 정지 {stop_h:g} h)",
                           [hv_src, due_src, load_src, DOC_LOAD] + stop_src))
    # 2. 납기 지연 위약금
    rem, rem_src = ins.get('mes.remaining_qty')
    pen, pen_src = ins.get('erp.penalty_per_h')
    if None in (due, rem, rate, pen) or rate * r <= 0:
        items.append(_missing('delay', '납기 지연 위약금', '오더 잔량 · 생산 속도 · 위약금 · 납기 중 업무 DB에 없는 값이 있음', [rem_src, rate_src, pen_src, due_src]))
    elif stop_unknown:
        items.append(_missing('delay', '납기 지연 위약금', why_stop, [pen_src]))
    else:
        finish = stop_h + rem / (rate * r)
        late = max(0.0, finish - max(0.0, due))
        items.append(_item('delay', '납기 지연 위약금', pen * late,
                           f"위약금 {pen:g}만원/h × 지연 {late:.2f} h (정지 {stop_h:g} h + 잔량 {rem:g} ÷ ({rate:g} × {s['load']:g}/90) ea/h = {finish:.2f} h, 납기 {max(0.0, due):g} h)",
                           [pen_src, rem_src, rate_src, due_src, load_src, DOC_LOAD] + stop_src))
    # 3. 품질 클레임 위험
    qty, qty_src = ins.get('qms.auto_qty')
    claim, claim_src = ins.get('qms.auto_claim')
    p, p_src = ins.get('qms.auto_defect_p')
    if s['ts1'] is None:
        items.append(_item('quality', '품질 클레임 위험', 0.0, '유온 예측이 없는 카드 — 고온 로트 위험을 더하지 않음 (순위 정책과 같은 처리)', [DOC_TS1]))
    elif None in (qty, claim, p):
        items.append(_missing('quality', '품질 클레임 위험', 'QMS 고온 로트 수량 · 클레임 · 불량 확률 중 없는 값이 있음', [qty_src, claim_src, p_src]))
    else:
        hot = qty > 0 and s['ts1'] >= QUALITY_TS1
        items.append(_item('quality', '품질 클레임 위험', p * claim if hot else 0.0,
                           (f"불량 확률 {p:g} × 클레임 {claim:g}만원 (예측 유온 {s['ts1']:g} ℃ ≥ 55 ℃, 출하 대기 로트 {qty:g} ea)" if hot else
                            f"예측 유온 {s['ts1']:g} ℃ < 55 ℃ 또는 출하 대기 로트 {qty:g} ea → 0"),
                           [p_src, claim_src, qty_src, DOC_TS1, {'kind': '문서', 'where': f"카드의 예측 유온 {s['ts1']:g} ℃ (설비 모델 예측)"}]))
    # 4. 고장 위험 (원인이 남는 카드만)
    fc, fc_src = ins.get('erp.failure_cost')
    mtbf, mtbf_src = ins.get('cmms.mtbf_h')
    if s['remedy']:
        items.append(_item('failure', '고장 위험', 0.0, '근본 조치 카드 — 원인을 없애므로 고장 위험을 더하지 않음', [ASSUME_RISK]))
    elif None in (fc, mtbf, H) or mtbf <= 0:
        items.append(_missing('failure', '고장 위험', 'ERP 고장 비용 · CMMS MTBF · 납기 중 없는 값이 있음', [fc_src, mtbf_src]))
    else:
        prob = min(1.0, H / mtbf)
        items.append(_item('failure', '고장 위험', fc * prob, f"고장 비용 {fc:g}만원 × 기간 {H:g} h ÷ MTBF {mtbf:g} h", [fc_src, mtbf_src, due_src, ASSUME_RISK]))
    # 5. 정비 작업비 · 6. 부품비
    if tmiss:
        items.append(_missing('work', '정비 작업비', why_stop))
    else:
        items.append(_item('work', '정비 작업비', sum(t['labor_cost'] for t in tasks),
                           ' + '.join(f"{t['name']} {t['labor_cost']:g}만원" for t in tasks) or '작업지시 없음 → 0', stop_src or [{'kind': '문서', 'where': '카드에 작업지시 없음'}]))
    part_total, part_src, part_formula, part_missing = 0.0, [], [], []
    k = (1 + ins.pct('part_price_pct') / 100) * (1 + ins.pct('fx_pct') * FX_TO_PART / 100)
    for t in tasks:
        if not t.get('part_no') or not t.get('part_qty'):
            continue
        part = mf['parts'].get(t['part_no']) or {}
        quote_price = (part.get('quotes') or {}).get(s['pr']) if s['pr'] else None
        price = quote_price if quote_price is not None else part.get('std_price')
        if price is None:
            part_missing.append(t['part_no'])
            continue
        part_total += price * t['part_qty'] * k
        how = '구매요청 공급사 견적' if quote_price is not None else '표준단가'
        part_src.append({'kind': '데이터', 'where': f"업무 DB SCM · {t['name']} 부품 {how} {price:g}만원 × {t['part_qty']:g}개",
                         'ref': f"{t['part_no']} · {part.get('path')}"})
        part_formula.append(f"{t['name']} 부품 {price:g}만원 × {t['part_qty']:g}")
    if part_missing:
        items.append(_missing('parts', '부품비', '업무 DB SCM에 단가가 없는 부품이 있음 (' + ', '.join(part_missing) + ')'))
    else:
        pct_note = ''
        if ins.pct('part_price_pct') or ins.pct('fx_pct'):
            pct_note = f" × (1 {ins.pct('part_price_pct'):+g} %) × (1 {ins.pct('fx_pct'):+g} % × {FX_TO_PART:g})"
            part_src += [{'kind': '시험값', 'where': f"부품값 {ins.pct('part_price_pct'):+g} % · 환율 {ins.pct('fx_pct'):+g} %"}, ASSUME_FX]
        items.append(_item('parts', '부품비', part_total, (' + '.join(part_formula) or '필요 부품 없음 → 0') + pct_note,
                           part_src or [{'kind': '데이터', 'where': '업무 DB CMMS 표준 작업에 필요 부품 없음'} if tasks else {'kind': '문서', 'where': '카드에 작업지시 없음'}]))
    # 7. 에너지비 (팬 전력)
    kw, kw_src = ins.get('ems.fan_boost_kw')
    er, er_src = ins.get('ems.energy_rate')
    if not s['fan_delta']:
        items.append(_item('energy', '에너지비(팬)', 0.0, '팬 명령 없음 → 0', [DOC_FAN]))
    elif None in (kw, er, H):
        items.append(_missing('energy', '에너지비(팬)', 'EMS 팬 전력 · 전력 단가 중 없는 값이 있음', [kw_src, er_src]))
    else:
        items.append(_item('energy', '에너지비(팬)', s['fan_delta'] * kw / (FAN_MAX - FAN_NORMAL) * H * er,
                           f"팬 {s['fan_delta']:+g} %p × {kw:g} kW ÷ 40 %p × {H:g} h × {er:g}만원/kWh", [kw_src, er_src, due_src, DOC_FAN]))
    missing = [i['label'] for i in items if i['value_won'] is None]
    total = None if missing else sum(i['value_won'] for i in items)
    return {'items': items, 'total_won': total, 'complete': not missing, 'missing': missing,
            'hours': H, 'basis': '납기까지 남은 시간 동안의 예상 손익 (비용은 음수, 단위 원)'}


# ---------------------------------------------------------------- ④ 규칙 바꿔 보기 (정책 사본)
def policy_view(dmn: list[dict]) -> dict:
    rank = next((r for r in dmn if r.get('decision') == 'dec:rank-actions' and r.get('rankingPolicy')), None)
    pol = ranking.validate(rank['rankingPolicy']) if rank else None
    return {'rule': rank and rank['rule'],
            'components': [{'key': k, 'label': COMPONENT_LABELS.get(k, k), 'expr': v} for k, v in (pol or {}).get('components', {}).items()],
            'penalties': [{'rule': r['rule'], 'annotation': r.get('annotation'), 'penalty': r.get('penalty'), 'applies': r.get('applies') or []}
                          for r in dmn if r.get('decision') == 'dec:compliance' and r.get('effect') == 'PENALTY']}


def check_policy(dmn: list[dict], policy: dict | None, perspectives: dict | None = None) -> dict:
    """perspectives: perspective_view(bundle) — 관점 중요도 시험값(B5)을 검사할 때 필요하다."""
    policy = policy or {}
    if set(policy) - {'weights', 'penalties', 'perspectives'}:
        raise ValueError('규칙 시험값은 weights(순위 항목 가중치) · penalties(감점 규칙 감점) · perspectives(관점 중요도)만 받습니다')
    view = policy_view(dmn)
    comps = {c['key'] for c in view['components']}
    pens = {p['rule'] for p in view['penalties']}
    out = {'weights': {}, 'penalties': {}}
    if policy.get('perspectives'):
        pv = perspectives or {}
        if not pv.get('available'):
            raise ValueError('관점 중요도를 바꿀 수 없습니다: ' + (pv.get('reason') or '지식 그래프의 BSC 관점을 읽지 못했습니다'))
        known = {x['id']: x['name'] for x in pv['perspectives']}
        out['perspectives'] = {}
        for k, w in policy['perspectives'].items():
            x = _finite(w)
            if k not in known:
                raise ValueError(f'지식 그래프에 없는 관점입니다: {k}')
            if x is None or not 0 <= x <= 10:
                raise ValueError(f"관점 '{known[k]}' 중요도는 0 ~ 10배 사이 숫자여야 합니다")
            out['perspectives'][k] = x
    for k, w in (policy.get('weights') or {}).items():
        x = _finite(w)
        if k not in comps:
            raise ValueError(f'순위 정책에 없는 항목입니다: {k}')
        if x is None or not -10 <= x <= 10:
            raise ValueError(f'{k} 가중치는 -10 ~ 10 사이 숫자여야 합니다')
        out['weights'][k] = x
    for k, v in (policy.get('penalties') or {}).items():
        x = _finite(v)
        if k not in pens:
            raise ValueError(f'감점 규칙이 아닙니다: {k}')
        if x is None or not 0 <= x <= 1000:
            raise ValueError(f'{k} 감점은 0 ~ 1000 사이 숫자여야 합니다')
        out['penalties'][k] = x
    return out


def apply_policy(dmn: list[dict], policy: dict) -> list[dict]:
    """정책 사본: 원본 dmn은 건드리지 않는다. 가중치 k는 그 항목 식을 k × (식)으로 감싼다(같은 안전 식 검사를 다시 통과해야 한다)."""
    if not policy.get('weights') and not policy.get('penalties'):
        return dmn
    out = copy.deepcopy(dmn)
    for r in out:
        if r.get('decision') == 'dec:rank-actions' and r.get('rankingPolicy') and policy.get('weights'):
            pol = ranking.validate(r['rankingPolicy'])
            for k, w in policy['weights'].items():
                pol['components'][k] = f"{w!r} * ({pol['components'][k]})"
            r['rankingPolicy'] = ranking.validate(pol)
        if r.get('decision') == 'dec:compliance' and r.get('rule') in policy.get('penalties', {}):
            r['penalty'] = policy['penalties'][r['rule']]
    return out


# ---------------------------------------------------------------- ⑤ 관점 중요도 (B5, 시험 실행만)
def load_perspectives(rows: list[dict]) -> dict:
    """t3_perspectives 행 → {perspectives: [{id, name, order}], measures: {지표 id: 관점 id}}. 이름 · 소속은 그래프 그대로."""
    out = {'perspectives': [], 'measures': {}}
    for r in rows or []:
        if not r.get('id'):
            continue
        out['perspectives'].append({'id': r['id'], 'name': r.get('name') or r['id'], 'order': r.get('ord')})
        for m in r.get('measures') or []:
            out['measures'][m] = r['id']
    if not out['perspectives']:
        return {'error': '지식 그래프에 BSC 관점(Perspective)이 없습니다 — 온톨로지 적재를 확인하세요'}
    return out


def perspective_view(bundle: dict) -> dict:
    """화면용: 관점마다 이름과 이 판단의 카드 득실에 실제로 나오는 지표(없으면 바꿔도 순위가 그대로)."""
    p = bundle.get('perspectives') or {}
    if p.get('error') or not p.get('perspectives'):
        return {'available': False, 'reason': p.get('error') or '지식 그래프에서 BSC 관점을 읽지 않았습니다', 'perspectives': []}
    used: dict[str, dict] = {}
    for t in bundle.get('tradeoffs') or []:
        pid = p['measures'].get(t.get('measure'))
        if pid:
            used.setdefault(pid, {})[t['measure']] = t.get('name') or t['measure']
    return {'available': True, 'perspectives': [{'id': x['id'], 'name': x['name'], 'order': x.get('order'),
                                                 'measures': sorted(used.get(x['id'], {}).values()), 'inUse': x['id'] in used}
                                                for x in p['perspectives']]}


def measure_weights(bundle: dict, policy: dict | None) -> dict[str, float] | None:
    w = (policy or {}).get('perspectives') or {}
    if not w:
        return None
    m2p = (bundle.get('perspectives') or {}).get('measures') or {}
    return {mid: float(w[pid]) for mid, pid in m2p.items() if pid in w}


def bsc_by_perspective(o: dict, bundle: dict) -> list[dict]:
    """카드 하나의 성과 지표 득실을 관점별로(시험 비중이 적용된 무게). 조건이 확인되지 않은 득실은 따로 센다."""
    m2p = (bundle.get('perspectives') or {}).get('measures') or {}
    names = {x['id']: x['name'] for x in (bundle.get('perspectives') or {}).get('perspectives') or []}
    acc: dict[str, dict] = {}
    for kind in ('gains', 'losses'):
        for t in o.get(kind) or []:
            pid = m2p.get(t.get('measure'))
            x = acc.setdefault(pid or '-', {'perspective': pid, 'name': names.get(pid, '관점 없음'), 'gain': 0.0, 'loss': 0.0, 'measures': []})
            x['gain' if kind == 'gains' else 'loss'] += 0 if t.get('conditional') else t['weight']
            x['measures'].append(f"{t.get('name')} {'↑' if t.get('dir') == 1 else '↓'}")
    return [dict(v, gain=round(v['gain'], 4), loss=round(v['loss'], 4)) for v in acc.values()]


# ---------------------------------------------------------------- ② 다시 계산 · 경계값
def _fingerprint(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def rerank(bundle: dict, trial: dict | None = None, policy: dict | None = None) -> dict:
    """판단 순위(정책 점수)를 시험값으로 다시 계산 — cards.evaluate를 사본 사실 · 사본 정책으로 그대로 부른다."""
    facts = dict(bundle['facts'])
    for vid, x in (trial or {}).items():
        fact = VARIABLES[vid].get('fact')
        if fact:
            facts[fact] = x
    dmn = apply_policy(bundle['dmn'], policy or {})
    return cards.evaluate(dmn, bundle['skills'], facts, bundle['forecasts'], bundle['tradeoffs'], bundle['precedents'],
                          bundle['suppliers'], bundle.get('forecast_contexts'), measure_weights=measure_weights(bundle, policy))


def money_order(options: list[dict], money: dict[str, dict]) -> list[str]:
    """손익 순위: 규정상 가능한 카드 중 손익 합계가 계산된 것, 큰(덜 잃는) 순. 동점이면 판단 순위."""
    ok = [o for o in options if o['feasible'] and money[o['id']]['complete']]
    return [o['id'] for o in sorted(ok, key=lambda o: (-money[o['id']]['total_won'], o['rank']))]


def evaluate(bundle: dict, mf: dict, trial: dict | None = None, policy: dict | None = None) -> dict:
    res = rerank(bundle, trial, policy)
    money = {o['id']: card_money(o, mf, trial) for o in res['options']}
    order = money_order(res['options'], money)
    cards_out = []
    for o in res['options']:
        cards_out.append({'id': o['id'], 'name': o.get('name'), 'sopId': o.get('sopId'), 'kind': o.get('kind'), 'relation': o.get('relation'),
                          'feasible': o['feasible'], 'excluded': [v.get('annotation') for v in o.get('violations') or []],
                          'decisionRank': o['rank'] if o['feasible'] else None, 'score': o['score'], 'scoreParts': o['scoreParts'],
                          'production': o.get('production'), 'moneyRank': order.index(o['id']) + 1 if o['id'] in order else None,
                          'money': money[o['id']], 'paths': [p.get('nodes') for p in o.get('tradeoffEvaluation') or [] if p.get('nodes')],
                          'bscByPerspective': bsc_by_perspective(o, bundle)})
    return {'cards': cards_out, 'top': {'decision': res['recommended'], 'money': order[0] if order else None},
            'explanation': res['explanation']}


def _top(bundle, mf, kind, trial, policy):
    if kind == 'decision':
        return rerank(bundle, trial, policy)['recommended']
    # 판단 사실에 닿는 시험값(납기 · 위약금 · 클레임)은 카드 가능 여부도 바꿀 수 있어 다시 판단한다
    touches_facts = any(VARIABLES[v].get('fact') for v in trial or {})
    res_opts = rerank(bundle, trial, policy)['options'] if touches_facts else _feasible_cache(bundle, policy)
    money = {o['id']: card_money(o, mf, trial) for o in res_opts}
    order = money_order(res_opts, money)
    return order[0] if order else None


def _feasible_cache(bundle, policy):
    # 손익 순위는 판단 사실과 무관한 시험값(부품값 · 시간당 가치 …)만 바뀔 때 카드 목록 · 가능 여부가 같다.
    key = _fingerprint(policy or {})
    cache = bundle.setdefault('_opts', {})
    if key not in cache:
        cache[key] = rerank(bundle, None, policy)['options']
    return cache[key]


def _range(vid, base):
    spec = VARIABLES[vid]
    lo = spec.get('lo', 0.0)
    hi = spec.get('hi') if spec.get('hi') is not None else max(10 * abs(base or 0), 1.0)
    if base is not None:
        lo, hi = min(lo, base), max(hi, base)
    return lo, hi


def _merge_policy(policy, weights=None, penalties=None, perspectives=None):
    p = {'weights': dict((policy or {}).get('weights') or {}), 'penalties': dict((policy or {}).get('penalties') or {})}
    p['weights'].update(weights or {})
    p['penalties'].update(penalties or {})
    persp = dict((policy or {}).get('perspectives') or {})
    persp.update(perspectives or {})
    if persp:
        p['perspectives'] = persp
    return p


def boundary_axes(bundle: dict, mf: dict, policy: dict | None = None, variables: list[str] | None = None) -> list[dict]:
    """경계값을 찾을 축: 시험값(②) + 순위 정책 항목 가중치 · 감점 규칙 감점(④). apply(x) -> (trial, policy)."""
    axes = []
    for vid in variables or [v for v in VARIABLES if v not in ('week_hours', 'load_pct')]:
        if vid not in VARIABLES:
            continue
        base, _ = _base(mf, vid)
        if base is None:
            continue
        kinds = [k for k in ('decision', 'money') if k in VARIABLES[vid]['kinds']
                 and (k != 'decision' or VARIABLES[vid].get('fact') in bundle['facts'])]
        lo, hi = _range(vid, base)
        axes.append({'id': vid, 'label': VARIABLES[vid]['label'], 'unit': VARIABLES[vid]['unit'], 'base': base, 'lo': lo, 'hi': hi,
                     'kinds': kinds, 'apply': (lambda x, v=vid: ({v: x}, policy))})
    if variables is None:
        view = policy_view(bundle['dmn'])
        for c in view['components']:
            w0 = ((policy or {}).get('weights') or {}).get(c['key'], 1.0)
            axes.append({'id': 'w:' + c['key'], 'label': f"순위 항목 '{c['label']}' 가중치", 'unit': '배', 'base': w0, 'lo': min(-2.0, w0), 'hi': max(5.0, w0),
                         'kinds': ['decision'], 'apply': (lambda x, k=c['key']: (None, _merge_policy(policy, weights={k: x})))})
        for r in view['penalties']:
            p0 = ((policy or {}).get('penalties') or {}).get(r['rule'], _finite(r['penalty']) or 0.0)
            axes.append({'id': 'p:' + r['rule'], 'label': f"감점 규칙 '{r['annotation'] or r['rule']}' 감점", 'unit': '점', 'base': p0, 'lo': 0.0, 'hi': max(200.0, p0),
                         'kinds': ['decision'], 'apply': (lambda x, k=r['rule']: (None, _merge_policy(policy, penalties={k: x})))})
        for pp in perspective_view(bundle)['perspectives']:     # B5: 관점 중요도 — 이 판단의 득실에 나오는 관점만
            if not pp['inUse']:
                continue
            v0 = ((policy or {}).get('perspectives') or {}).get(pp['id'], 1.0)
            axes.append({'id': 'v:' + pp['id'], 'label': f"관점 '{pp['name']}' 중요도", 'unit': '배', 'base': v0, 'lo': 0.0, 'hi': max(5.0, v0),
                         'kinds': ['decision'], 'apply': (lambda x, k=pp['id']: (None, _merge_policy(policy, perspectives={k: x})))})
    return axes


def find_boundaries(bundle: dict, mf: dict, variables: list[str] | None = None, policy: dict | None = None, steps: int = 40) -> list[dict]:
    """값 하나씩: 기준값에서 가장 가까운 '1순위가 바뀌는 값'을 카드마다 찾고, 그 값으로 다시 계산해 바뀐 1순위를 확인한다."""
    base_eval = evaluate(bundle, mf, None, policy)
    names = {c['id']: c['name'] for c in base_eval['cards']}
    out = []
    for ax in boundary_axes(bundle, mf, policy, variables):
        base, lo, hi = ax['base'], ax['lo'], ax['hi']
        for kind in ax['kinds']:
            t0 = base_eval['top'][kind]
            if t0 is None:
                continue
            f = lambda x, a=ax, k=kind: _top(bundle, mf, k, *a['apply'](x))  # noqa: E731
            grid = sorted({lo + (hi - lo) * i / steps for i in range(steps + 1)} | {base})
            tops = {x: f(x) for x in grid}
            for cid in names:
                want = (lambda t, t0=t0: t != t0) if cid == t0 else (lambda t, c=cid: t == c)
                hit = _nearest(grid, tops, base, want, f)
                if hit is None:
                    continue
                x, new_top = hit
                trial, pol = ax['apply'](x)
                out.append({'variable': ax['id'], 'label': ax['label'], 'unit': ax['unit'], 'kind': kind,
                            'card': cid, 'cardName': names[cid], 'base': base, 'value': x, 'direction': '이상' if x > base else '이하',
                            'topBefore': t0, 'topBeforeName': names.get(t0), 'topAfter': new_top, 'topAfterName': names.get(new_top),
                            'trial': trial or {}, 'policy': pol or {}, 'verified': True})
    return out


def _nearest(grid, tops, base, want, f):
    """기준값 양쪽으로 격자를 훑어 처음 조건이 맞는 칸을 찾고, 그 칸과 바로 앞 칸 사이를 이분해 경계를 좁힌다. 가장 가까운 쪽을 고른다."""
    best = None
    i0 = grid.index(base)
    for step in (1, -1):
        prev = grid[i0]
        j = i0 + step
        while 0 <= j < len(grid):
            x = grid[j]
            if want(tops[x]):
                a, b = prev, x                      # a: 조건 아님, b: 조건 맞음
                for _ in range(40):
                    if abs(b - a) <= max(1e-6, abs(b) * 1e-7):
                        break
                    m = (a + b) / 2
                    if want(f(m)):
                        b = m
                    else:
                        a = m
                v = _round_toward(b, a, grid[-1] - grid[0])
                t = f(v)
                if not want(t):
                    v, t = b, f(b)
                if want(t) and (best is None or abs(v - base) < abs(best[0] - base)):
                    best = (v, t)
                break
            prev = x
            j += step
    return best


def _round_toward(b, a, span):
    """범위의 1/2000 안쪽 자리로 반올림하되 조건이 맞는 쪽(b)으로 올리거나 내린다 (확인은 부른 쪽이 다시 계산해서 한다)."""
    nd = max(0, min(6, -math.floor(math.log10(max(span, 1e-9) / 2000))))
    s = 10 ** nd
    return round(math.ceil(b * s - 1e-9) / s if b > a else math.floor(b * s + 1e-9) / s, nd)


# ---------------------------------------------------------------- ③ 몇 주 What-if
def weeks(bundle: dict, mf: dict, card_id: str, weeks_n: int = 4, change: dict | None = None, policy: dict | None = None) -> dict:
    if not 1 <= int(weeks_n) <= 12:
        raise ValueError('기간은 1 ~ 12주입니다')
    opts = {o['id']: o for o in _feasible_cache(bundle, policy)}
    if card_id not in opts:
        raise ValueError(f'이 판단에 없는 카드입니다: {card_id}')
    o = opts[card_id]
    change = change or {}
    if len(change) > 1:
        raise ValueError('몇 주 What-if는 값 하나만 바꿉니다')
    load_base = card_shape(o)['load']
    trial = check_trial(change)
    base = _week_series(bundle, mf, o, int(weeks_n), {})
    changed = _week_series(bundle, mf, o, int(weeks_n), trial) if trial else None
    out = {'card': card_id, 'cardName': o.get('name'), 'weeks': int(weeks_n), 'coefficients': base['coefficients'], 'paths': base['paths'],
           'base': base['rows'], 'changed': changed and changed['rows'], 'missing': base['missing'],
           'change': None}
    if trial:
        vid, x = next(iter(trial.items()))
        b = load_base if vid == 'load_pct' else _base(mf, vid)[0]
        out['change'] = {'variable': vid, 'label': VARIABLES[vid]['label'], 'unit': VARIABLES[vid]['unit'], 'base': b, 'value': x}
        out['delta'] = [{k: (None if r1[k] is None or r0[k] is None else round(r1[k] - r0[k], 4)) for k in r0 if k != 'week'} | {'week': r0['week']}
                        for r0, r1 in zip(base['rows'], changed['rows'])]
    return out


def _coef(cid, label, value, unit, src):
    return {'id': cid, 'label': label, 'value': value, 'unit': unit, 'kind': src['kind'], 'source': src['where'], 'ref': src.get('ref')}


def _repair_hours(bundle, mf, o):
    """고장 시 정지 시간: 같은 원인을 근본 조치하는 후보 카드의 CMMS 표준 작업 정지 시간 (없으면 None)."""
    cause, fm = bundle['facts'].get('cause'), bundle['facts'].get('failure_mode')
    for sk in sorted(bundle['skills'].values(), key=lambda k: k.get('sopId') or ''):
        if sk.get('relation') != 'REMEDIED_BY' or (sk.get('addresses') and cause not in sk['addresses']) \
                or (sk.get('failureModeId') and fm and sk['failureModeId'] != fm):
            continue
        for sop in card_shape(sk)['wos']:
            t = mf['tasks'].get(sop)
            if t and t.get('stop_h') is not None:
                return t['stop_h'], t
    return None, None


def _week_series(bundle, mf, o, n, trial):
    ins, s = _Inputs(mf, trial), card_shape(o)
    W = trial.get('week_hours', WEEK_HOURS)
    L = trial.get('load_pct', s['load'])
    rate, rate_src = ins.get('mes.rate_per_h')
    hv, hv_src = ins.get('mes.hour_value')
    mtbf, mtbf_src = ins.get('cmms.mtbf_h')
    fc, fc_src = ins.get('erp.failure_cost')
    kw, kw_src = ins.get('ems.fan_boost_kw')
    er, er_src = ins.get('ems.energy_rate')
    one = card_money(dict(o, actions=[a for a in o.get('actions') or [] if a.get('code') != 'LOAD_SET'] +
                          ([{'code': 'LOAD_SET', 'kind': 'command', 'value': L}] if 'load_pct' in trial or s['load_cmd'] else [])), mf, trial)
    by = {i['key']: i for i in one['items']}
    tasks, _ = _tasks_of(s, mf)
    stop_h = sum(t['stop_h'] for t in tasks)
    repair_h, repair_task = _repair_hours(bundle, mf, o)
    load_src = {'kind': '시험값', 'where': f'부하 {L:g} % (카드 값 {s["load"]:g} %)'} if 'load_pct' in trial else \
        {'kind': '문서', 'where': f"카드의 부하 명령 {L:g} %" if s['load_cmd'] else '부하 명령 없음 → 설계 부하 90 %'}
    week_src = {'kind': '시험값', 'where': f'주 운전 시간 {W:g} h'} if 'week_hours' in trial else ASSUME_WEEK
    coefficients = [
        _coef('load', '조치 부하 (조치 → 설비 값)', L, '%', load_src),
        _coef('fan', '조치 팬 변화 (조치 → 설비 값)', s['fan_delta'], '%p', {'kind': '문서', 'where': '카드의 팬 명령 − 정상 팬 60 %', 'ref': '온톨로지 Skill FAN_SET · thermal.py'}),
        _coef('throughput', '부하 1 %당 생산 수량 (설비 값 → 생산량)', None if rate is None else round(rate / cards.LOAD_DESIGN, 4), 'ea/h per %', rate_src | {'where': rate_src['where'] + ' ÷ 설계 부하 90 %'}),
        _coef('value', '수량 1개당 생산 가치 (생산량 → 매출)', None if None in (hv, rate) or not rate else round(hv / rate, 6), '만원/ea', hv_src | {'where': hv_src['where'] + ' ÷ ' + rate_src['where']}),
        _coef('stop', '작업 정지 시간 (첫 주, 조치 → 가동률)', stop_h, 'h', _task_src(tasks[0]) if tasks else {'kind': '문서', 'where': '카드에 작업지시 없음'}),
        _coef('mtbf', 'MTBF (원인 → 고장 확률)', mtbf, 'h', mtbf_src),
        _coef('risk', '원인 유지 시 주별 고장 확률', None if not mtbf else round(min(1.0, W / mtbf), 6), '확률/주', ASSUME_RISK),
        _coef('failure_cost', '고장 1회 비용 (고장 → 비용)', fc, '만원', fc_src),
        _coef('repair', '고장 시 정지 시간 (고장 → 가동률)', repair_h if repair_task else 0.0, 'h', _task_src(repair_task) if repair_task else
              {'kind': '가정', 'where': '이 원인을 근본 조치하는 표준 작업이 없어 고장 정지 시간을 0으로 둔다 (고장 정지를 가동률에 넣지 않음)'}),
        _coef('repair_rule', '고장 시 정지 규칙', None, '', ASSUME_REPAIR),
        _coef('restore', '근본 조치 뒤 복귀', None, '', ASSUME_RESTORE),
        _coef('fan_kw', '팬 1 %p당 전력 (설비 값 → 전력)', None if kw is None else round(kw / (FAN_MAX - FAN_NORMAL), 6), 'kW/%p', kw_src),
        _coef('energy_rate', '전력 단가 (전력 → 비용)', er, '만원/kWh', er_src),
        _coef('week_hours', '주 운전 시간', W, 'h', week_src),
    ]
    missing = [c['label'] for c in coefficients if c['value'] is None and c['id'] not in ('repair_rule', 'restore')]
    rows, cum = [], 0.0
    for w in range(1, n + 1):
        active = (not s['remedy']) or w == 1
        Lw = L if active else cards.LOAD_DESIGN
        fan = s['fan_delta'] if active else 0.0
        p = 0.0 if s['remedy'] or not mtbf else min(1.0, W / mtbf)
        down = (stop_h if w == 1 else 0.0) + p * (repair_h or 0.0)
        run = max(0.0, W - down)
        avail = None if W <= 0 else round(run / W * 100, 2)
        output = None if rate is None else rate * Lw / cards.LOAD_DESIGN * run
        revenue = None if None in (output, hv, rate) or not rate else output * hv / rate
        energy = 0.0 if not fan else (None if None in (kw, er) else fan * kw / (FAN_MAX - FAN_NORMAL) * run * er)
        once = 0.0
        if w == 1:
            vals = [by[k]['value_won'] for k in ('work', 'parts', 'quality', 'delay')]
            once = None if None in vals else -sum(vals) / WON
        risk = None if fc is None else p * fc
        cost = None if None in (energy, once, risk) else energy + once + risk
        profit = None if None in (revenue, cost) else revenue - cost
        cum = None if profit is None or cum is None else cum + profit
        rows.append({'week': w, 'availability': avail, 'output': None if output is None else round(output, 1),
                     'revenue_won': None if revenue is None else int(round(revenue * WON)), 'cost_won': None if cost is None else int(round(cost * WON)),
                     'profit_won': None if profit is None else int(round(profit * WON)), 'cum_profit_won': None if cum is None else int(round(cum * WON)),
                     'load': Lw, 'failure_p': round(p, 6)})
    return {'rows': rows, 'coefficients': coefficients, 'missing': missing,
            'paths': [p.get('nodes') for p in o.get('tradeoffEvaluation') or [] if p.get('nodes')]}


# ---------------------------------------------------------------- 세션 (시험 실행 기준 묶음, 메모리에만)
class Sessions:
    def __init__(self, cap: int = 30):
        self._lock, self._items, self.cap = threading.Lock(), {}, cap

    def put(self, data: dict) -> str:
        sid = 'WI-' + secrets.token_hex(4)
        with self._lock:
            self._items[sid] = data
            while len(self._items) > self.cap:
                self._items.pop(next(iter(self._items)))
        return sid

    def get(self, sid: str) -> dict | None:
        return self._items.get(sid)


def original_fingerprint(bundle: dict, mf: dict) -> str:
    return _fingerprint({k: v for k, v in bundle.items() if not k.startswith('_')} | {'money_facts': mf})


def summary(ev: dict, base_top: dict | None = None) -> str:
    names = {c['id']: c['name'] for c in ev['cards']}
    d, m = ev['top']['decision'], ev['top']['money']
    parts = [f"판단 1순위 '{names.get(d, '없음')}'" if d else '판단 1순위 없음 (모두 규정상 제외)',
             f"손익 1순위 '{names.get(m)}'" if m else '손익 1순위 없음 (손익을 끝까지 계산한 카드가 없음)']
    if base_top:
        for kind, label in (('decision', '판단'), ('money', '손익')):
            if base_top.get(kind) != ev['top'][kind]:
                parts.append(f"{label} 1순위가 '{names.get(base_top.get(kind), '없음')}'에서 바뀌었습니다")
    if d and m and d != m:
        parts.append('정책 점수와 돈 기준이 다른 카드를 고릅니다 — 가치의 상충')
    return ' · '.join(parts) + '.'
