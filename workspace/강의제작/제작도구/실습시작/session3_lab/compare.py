"""비교 산식 — 제공 코드(일반 로직). 고치지 않는다.

`data/metrics/metric_definitions.md`의 네 손실(비용 · 생산 · 품질 · 에너지)을 그 식 그대로 계산하고, 결정표가 낸 감점 금액을 더해 비교값을 낸다.
단위는 만 원이고 작을수록 좋다. 필요한 값이 비어 있으면 0으로 채우지 않고 그 후보의 비교값을 내지 않는다.
견준 후보 가운데 무엇을 1순위로 내줄지는 이 파일이 정하지 않는다(`app/features/compare_rule.py`).
"""
from pathlib import Path
import json

from app.utils.results import Stop, read_text
from app.utils.rules import read_rows

HERE = Path(__file__).resolve().parents[2]
METRICS = HERE / 'data/metrics'
DESIGN_LOAD, NORMAL_FAN = 90.0, 60.0
PARTS = ('비용', '생산', '품질', '에너지', '감점')


def load():
    """(업무 값 {이름: 값}, 표준 작업 {작업: 줄}, 후보 설정 {SOP ID: 줄})."""
    doc = json.loads(read_text(METRICS / 'business_values.json')[0])
    values = {v['이름']: v['값'] for v in doc['값']}
    jobs = {j['작업']: j for j in doc['표준_작업']}
    settings = {r['후보']: r for r in read_rows(METRICS / 'candidate_settings.csv')}
    return values, jobs, settings


def number(row, column):
    raw = (row.get(column) or '').strip()
    if raw == '':
        return None
    try:
        return float(raw)
    except ValueError:
        raise Stop(f'경보 {row.get("경보_ID")}의 {column} 칸 값 「{raw}」이 숫자가 아닙니다.') from None


def losses(sop, row, penalty, loaded=None):
    """후보 하나의 비교값. 돌려주는 값: ({비용, 생산, 품질, 에너지, 감점, 비교값}, None) 또는 (None, 값이 없는 칸 이름들)."""
    values, jobs, settings = loaded or load()
    if sop not in settings:
        return None, [f'candidate_settings.csv에 {sop} 줄']
    s = settings[sop]
    period, remain, hot = number(row, '납기까지_남은_시간_h'), number(row, '오더_잔량_ea'), number(row, '고온_로트_수량_ea')
    forecast = number(row, f'예측_유온_{sop}_C')
    missing = [name for name, v in (('납기까지_남은_시간_h', period), ('오더_잔량_ea', remain), ('고온_로트_수량_ea', hot), (f'예측_유온_{sop}_C', forecast)) if v is None]
    if missing:
        return None, missing
    load_pct = float(s['부하_설정_퍼센트']) if s['부하_설정_퍼센트'] else DESIGN_LOAD
    fan = float(s['팬_설정_퍼센트']) if s['팬_설정_퍼센트'] else NORMAL_FAN
    job = jobs.get(s['정비_요청']) if s['정비_요청'] else None
    if s['정비_요청'] and job is None:
        raise Stop(f'data/metrics/candidate_settings.csv:{s["_line"]}: 정비_요청 「{s["정비_요청"]}」이 business_values.json의 표준 작업에 없습니다.')
    stop_h = job['정지_시간_h'] if job else 0
    ratio = load_pct / DESIGN_LOAD
    risk = 0.0 if s['근본_조치'] == '예' else values['계획_외_고장_비용'] * min(period / values['평균_고장_간격'], 1.0)
    cost = (job['작업비_만원'] if job else 0) + risk
    reduced = values['시간당_생산_가치'] * (period * (1 - ratio) + stop_h)
    finish = stop_h + remain / (values['시간당_생산_수량'] * ratio)
    late = values['납기_지연_위약금'] * max(finish - period, 0.0)
    quality = values['고온_로트_불량_확률'] * values['고온_로트_클레임_금액'] if forecast >= 55.0 and hot > 0 else 0.0
    energy = (fan - NORMAL_FAN) * values['팬_최대_추가_전력'] / 40 * period * values['전력_단가']
    out = {'비용': round(cost, 2), '생산': round(reduced + late, 2), '품질': round(quality, 2), '에너지': round(energy, 2), '감점': round(penalty, 2)}
    out['비교값'] = round(sum(out[k] for k in PARTS), 2)
    return out, None


def ranked(compared):
    """{SOP ID: 비교값} → {SOP ID: 순위}. 비교값이 작을수록 앞이고, 같은 비교값은 같은 순위다."""
    order = sorted(set(compared.values()))
    return {sop: 1 + sum(1 for v in compared.values() if v < total) for sop, total in compared.items()} if order else {}
