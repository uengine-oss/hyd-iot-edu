"""Source-declared PM applicability and cadence, separate from alert generations."""
from copy import deepcopy
import json
import math


def consistent_packages(procedures):
    """A package BOM is per asset, including when its scheduling scope is a bundle.

    The execution planner sums it once for each selected asset. Compare the
    same package across proposed policies; do not guess missing source amounts.
    """
    seen = {}
    for procedure in procedures:
        fields = procedure.get('link') or procedure
        contract = fields.get('maintenance_policy') or {}
        for package in contract.get('packages') or []:
            key = (package['sop'], package['interval_h'])
            signature = sorted(((part.get('part_no') or part['name'], part.get('qty'))
                                for part in package['parts']), key=lambda part: part[0])
            if key in seen and seen[key][1] != signature:
                raise ValueError(f"{procedure['id']} / {seen[key][0]}: 같은 정비 패키지 {key[0]}의 부품 수량이 다릅니다. "
                                 'packages.parts.qty는 설비 한 대당 수량입니다. 묶음 총수량을 넣으면 실행 시 다시 합산됩니다. '
                                 '원문 패키지 표를 대조하고 미상 수량은 추정하지 마세요')
            seen[key] = (procedure['id'], signature)


class ScopeError(ValueError):
    def __init__(self,message,diagnostics):
        super().__init__(message)
        self.diagnostics=diagnostics


def policy(value):
    if isinstance(value,str):
        value=json.loads(value)
    if not isinstance(value,dict) or value.get('version') != 1 or value.get('scope') not in ('single','bundle'):
        raise ValueError('원문 PM 적용 정책과 단독/두 대 묶음 범위를 명시하세요')
    if value.get('stock_effect') not in ('reserve','issue','preserve'):
        raise ValueError('원문 부품 효과를 예약·출고·기존 할당 보존으로 명시하세요')
    if type(value.get('interval_h')) not in (int,float) or value['interval_h'] <= 0 or not math.isfinite(value['interval_h']):
        raise ValueError('원문 정비 간격을 명시하세요')
    if type(value.get('tolerance_pct')) not in (int,float) or not 0 <= value['tolerance_pct'] < 100:
        raise ValueError('원문 허용 오차를 명시하세요')
    assets=value.get('model_assets')
    if not isinstance(assets,list) or not assets or len(set(assets)) != len(assets) or any(not isinstance(a,str) or not a for a in assets):
        raise ValueError('동일 모델 원문 적용 설비 목록을 명시하세요')
    for key in ('anchor','model_anchor'):
        if not isinstance(value.get(key),dict) or not value[key].get('quote'):
            raise ValueError('정비 주기와 동일 모델 적용 범위의 원문 인용이 필요합니다')
    packages=value.get('packages')
    if not isinstance(packages,list) or len(packages)!=3:
        raise ValueError('원문 2천/4천/8천 시간 패키지 세 개를 모두 명시하세요')
    periods=[]
    for package in packages:
        if not isinstance(package,dict) or type(package.get('interval_h')) not in (int,float) or not package.get('sop') or not package.get('name'):
            raise ValueError('패키지 간격·원문 SOP·이름이 필요합니다')
        periods.append(package['interval_h'])
        parts=package.get('parts')
        if not isinstance(parts,list) or not parts or len({p.get('part_no') or ('source',p.get('name')) for p in parts if isinstance(p,dict)}) != len(parts):
            raise ValueError('패키지의 모든 원문 부품 범위가 필요합니다')
        for part in parts:
            if not isinstance(part,dict):
                raise ValueError('원문 부품 요구는 객체여야 합니다')
            if part.get('part_no') is None:
                if not isinstance(part.get('name'),str) or not part['name'] or not part.get('mapping_reason'):
                    raise ValueError('부품 번호 미상은 원문 이름과 연결 미상 사유를 명시하세요')
            elif not isinstance(part['part_no'],str) or not part['part_no']:
                raise ValueError('원문 부품과 실제 부품 번호의 명시 연결이 필요합니다')
            if part.get('qty') is not None and (type(part['qty']) not in (int,float) or not math.isfinite(part['qty']) or part['qty']<=0):
                raise ValueError('부품 수량은 원문에서 확인된 양수 또는 미상 null입니다')
    if sorted(periods) != [value['interval_h'],value['interval_h']*2,value['interval_h']*4]:
        raise ValueError('패키지 주기와 기본 정비 간격이 일치하지 않습니다')
    ordered=sorted(packages,key=lambda p:p['interval_h'])
    required_names={'펌프 축 씰 키트','리턴 필터 엘리먼트'}
    if not required_names <= {p.get('name') for p in ordered[0]['parts']}:
        raise ValueError('원문 기본 패키지의 씰 키트와 리턴 필터 범위를 모두 보존하세요')
    previous={(p.get('part_no'),p.get('name'),p.get('qty')) for p in ordered[0]['parts']}
    for package in ordered[1:]:
        current={(p.get('part_no'),p.get('name'),p.get('qty')) for p in package['parts']}
        if not previous <= current:
            raise ValueError('큰 원문 패키지는 작은 패키지의 모든 부품 범위를 포함해야 합니다')
        previous=current
    if not any(p.get('name')=='작동유' for p in ordered[-1]['parts']):
        raise ValueError('8천 시간 원문 패키지의 작동유를 미상 수량이라도 보존하세요')
    return deepcopy(value)


def service(row,contract):
    """No guessed historical phase; aligned actual counters or verified completion position."""
    interval=contract['interval_h'];since=row.get('pm_since_h');total=row.get('pm_total_h')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in (since,total)) or total<since:
        raise ValueError('실제 누적 운전시간과 마지막 정비 뒤 운전시간이 없거나 모순입니다')
    previous=total-since;recorded=row.get('service_position')
    if recorded is not None:
        if type(recorded) is not int or recorded<0:
            raise ValueError('검증된 정비 차례 이력이 올바르지 않습니다')
        position=recorded+1
    else:
        quotient=previous/interval
        if not math.isclose(quotient,round(quotient),abs_tol=1e-8):
            raise ValueError('조기·지연 정비의 실제 차례 이력이 없어 패키지 위상을 추정하지 않습니다')
        position=round(quotient)+1
    target=previous+interval
    package=max((p for p in contract['packages'] if position % round(p['interval_h']/interval)==0),key=lambda p:p['interval_h'])
    return dict(interval_h=interval,since_pm_h=since,total_h=total,last_service_total_h=previous,
                next_due_total_h=target,service_position=position,package_interval_h=package['interval_h'],
                package_sop=package['sop'],package_name=package['name']),package


def scope(contract,context,asset,window):
    rows=context.get('records');stock=context.get('parts')
    def fail(message):
        observed=[]
        for row in rows if isinstance(rows,list) else []:
            if not isinstance(row,dict) or row.get('asset') not in (asset,(next((r.get('bundle_peer') for r in rows if isinstance(r,dict) and r.get('asset')==asset),None))):
                continue
            info=None
            if row.get('pm_interval_h')==contract['interval_h']:
                try:info,_=service(row,contract)
                except ValueError:pass
            lower=contract['interval_h']*(1-contract['tolerance_pct']/100)
            hours=row.get('pm_since_h');prefix='following' if window and window.get('basis')=='hours_at_following_window' else 'night'
            observed.append(dict(asset=row.get('asset'),service=info,parts=[],
                applicability=dict(source_model_member=row.get('asset') in contract['model_assets'],
                    model_source_anchor=contract['model_anchor'],lower_hours=lower,observed_hours=hours,
                    lower_hours_met=hours>=lower if type(hours) in (int,float) else None,
                    actual_window_id=row.get(prefix+'_window_id'),common_start=row.get(prefix+'_window_at'),
                    common_window_verified=row.get(prefix+'_window_at')==window.get('starts_at') if window and window.get('starts_at') else None)))
        raise ScopeError(message,dict(scope=contract['scope'],assets=observed,ready=False,issues=[message]))
    if not isinstance(rows,list) or not isinstance(stock,list):
        fail('실제 CMMS 설비별 정비 상태와 전체 부품 가용 재고가 필요합니다')
    by_asset={r['asset']:r for r in rows if isinstance(r,dict) and isinstance(r.get('asset'),str)}
    if len(by_asset)!=len(rows) or asset not in by_asset or asset not in contract['model_assets']:
        fail('실제 설비와 원문 동일 모델 적용 범위가 일치하지 않습니다')
    selected=[asset];base=by_asset[asset];peer=base.get('bundle_peer')
    if contract['scope']=='bundle':
        eligible=[code for code,row in by_asset.items() if code!=asset and code in contract['model_assets']
                  and type(row.get('pm_since_h')) in (int,float)
                  and row['pm_since_h']>=contract['interval_h']*(1-contract['tolerance_pct']/100)
                  and window and row.get('night_window_at')==window.get('starts_at')]
        if len(eligible)!=1:
            fail('원문 동일 모델에서 하한과 공통 창을 충족하는 두 번째 설비가 없거나 복수여서 명시 선택이 필요합니다')
        peer=eligible[0]
        if peer==asset or peer not in by_asset or peer not in contract['model_assets']:
            fail('원문 동일 모델에 속하는 실제 두 번째 설비를 확인할 수 없습니다')
        selected.append(peer)
        if not window or not window.get('id') or window.get('basis')!='hours_at_next_window':
            fail('두 설비 묶음에는 실제 이번 공통 정비 창이 필요합니다')
    parts_by_no={r['part_no']:r for r in stock if isinstance(r,dict) and isinstance(r.get('part_no'),str)}
    if len(parts_by_no)!=len(stock):fail('전체 부품 재고의 식별자가 없거나 중복되었습니다')
    assets=[];totals={};issues=[]
    for code in selected:
        row=by_asset[code]
        if row.get('pm_interval_h')!=contract['interval_h'] or row.get('pm_tolerance_pct')!=contract['tolerance_pct']:
            fail('실제 설비 정비 기준과 원문 정책이 다릅니다')
        if type(row.get('pm_since_h')) not in (int,float) or row['pm_since_h']<contract['interval_h']*(1-contract['tolerance_pct']/100):
            fail('묶음 또는 단독 설비의 실제 운전시간이 원문 허용 하한 미만입니다')
        if window and window.get('id'):
            prefix='following' if window.get('basis')=='hours_at_following_window' else 'night'
            hours_key='hours_at_following_window' if prefix=='following' else 'hours_at_next_window'
            if code==asset and row.get(prefix+'_window_id')!=window['id']:
                fail('선택한 설비의 실제 목표 정비 창 ID가 다릅니다')
            if not window.get('starts_at') or row.get(prefix+'_window_at')!=window['starts_at']:
                fail('목표 정비 창의 실제 시작 시각이 없거나 다릅니다')
            if row.get(prefix+'_window_id')!=window['id'] and code!=asset:
                # IDs are asset-scoped; equality means shared actual start, not a reused foreign ID.
                if row.get(prefix+'_window_at')!=window.get('starts_at'):
                    fail('두 설비가 실제 같은 시작 시각의 정비 창에 속하지 않습니다')
            hours=row.get(hours_key)
        else:hours=row.get('pm_since_h')
        if type(hours) not in (int,float) or not math.isfinite(hours) or hours>contract['interval_h']*(1+contract['tolerance_pct']/100):
            fail('선택한 설비의 실제 목표 시점이 정비 허용 상한을 넘거나 미상입니다')
        service_info,package=service(row,contract);parts=[]
        for required in package['parts']:
            quantity=required.get('qty');part_no=required['part_no'];actual=parts_by_no.get(part_no)
            owned=(row.get('existing_pm_order') or {}).get('reserved_parts') or []
            allocated=next((a.get('qty') for a in owned if a.get('part_no')==part_no),None)
            verified=type(quantity) in (int,float) and actual is not None and type(actual.get('available')) in (int,float)
            if contract['stock_effect']=='preserve':verified=verified and type(allocated) in (int,float) and allocated>=quantity
            if contract['stock_effect']=='issue':
                verified=verified and type(actual.get('on_hand')) in (int,float) and type(actual.get('reserved')) in (int,float)
            name=required.get('name') or (actual or {}).get('name') or part_no
            if not verified:
                issues.append('원문 패키지 부품의 실제 수량·가용 재고를 확인할 수 없습니다: '+str(name))
            parts.append(dict(part_no=part_no,name=name,qty=quantity,available=actual.get('available') if actual else None,
                              owned_qty=allocated if contract['stock_effect']=='preserve' else None,
                              on_hand=actual.get('on_hand') if actual else None,reserved=actual.get('reserved') if actual else None,
                              stock_effect=contract['stock_effect'],verified=verified))
            if verified:totals[part_no]=totals.get(part_no,0)+quantity
        assets.append(dict(asset=code,service=service_info,parts=parts,
            window=dict(id=row.get(('following' if window and window.get('basis')=='hours_at_following_window' else 'night')+'_window_id'),
                        starts_at=window.get('starts_at') if window else None,immediate=bool(window and window.get('immediate'))),
            applicability=dict(source_model_member=True,model_source_anchor=contract['model_anchor'],
                lower_hours=contract['interval_h']*(1-contract['tolerance_pct']/100),observed_hours=row['pm_since_h'],lower_hours_met=True,
                target_hours=hours,limit_hours=contract['interval_h']*(1+contract['tolerance_pct']/100),within_limit=True,
                actual_window_id=row.get(('following' if window and window.get('basis')=='hours_at_following_window' else 'night')+'_window_id'),
                common_start=window.get('starts_at') if window else None,common_window_verified=True),
            expected_counter={k:row.get(k) for k in ('cycle','pm_since_h','pm_total_h','pm_planned_wo','service_position')}))
    for part_no,quantity in totals.items():
        if contract['stock_effect']=='reserve' and parts_by_no[part_no]['available']<quantity:
            issues.append('원문 패키지 전체 부품 가용 재고가 부족합니다: '+str(parts_by_no[part_no].get('name') or part_no))
        if contract['stock_effect']=='issue' and parts_by_no[part_no]['on_hand']-parts_by_no[part_no]['reserved']<quantity:
            issues.append('원문 패키지의 실제 출고 가능한 실물 재고가 부족합니다: '+str(parts_by_no[part_no].get('name') or part_no))
    observed_crews=[by_asset[code].get('pm_crew_available') for code in selected]
    required=4 if len(selected)==2 else None
    if any(type(crew) not in (int,float) or not math.isfinite(crew) or crew<0 for crew in observed_crews):
        fail('실제 목표 정비 창의 정비 인원을 확인할 수 없습니다')
    crew=min(observed_crews)
    result=dict(scope=contract['scope'],stock_effect=contract['stock_effect'],assets=assets,
                staffing=dict(required=required,available=crew,shortfall=max(required-crew,0) if required else None,
                              arrangement_required=crew<required if required else None,confirmed=False),
                parts_totals=[dict(part_no=k,qty=v,available=parts_by_no[k]['available']) for k,v in sorted(totals.items())],
                model_applicability=dict(assets=contract['model_assets'],source_anchor=contract['model_anchor']))
    if issues:raise ScopeError('; '.join(issues),dict(result,issues=issues,ready=False))
    return result
