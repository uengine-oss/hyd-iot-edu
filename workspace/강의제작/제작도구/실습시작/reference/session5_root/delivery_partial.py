def delivery(candidates, unresolved, safety_refs):
    checks = []
    for candidate in candidates:
        if candidate['status'] == '충족' and safety_refs:
            checks.append({'recipient':'설비보전팀','action':candidate['name']+' 관련 현장 상태를 점검 계획에 올리고 운전 정지 가능 시점을 담당자와 확인',
                           'preconditions':['설비 정지·LOCAL·동력 잠금을 현장에서 확인한 뒤 물리 점검','설비보전팀장의 기존 승인 절차'],
                           'evidence_refs':list(dict.fromkeys(candidate['evidence_refs']+safety_refs))})
    for missing in sorted(unresolved, key=lambda item: bool(item.get('cause_id'))):
        condition = not missing.get('cause_id') and '운전 조건' in missing['needed']
        role = '운전원' if condition else '설비보전팀'
        action = ('요청 시각의 실제 운전 조건과 해당 기간의 기록을 먼저 확인해 보전팀에 알림: ' if condition else
                  '후보별로 적용 조건에 맞는 기존 원문·관측의 확보 가능 여부를 확인해 회신: ')
        checks.append({'recipient':role,'action':action+missing['needed'],
                       'preconditions':['조회·확인 요청이며 설비를 조작하지 않음','현재 조건을 바꾸어 근거를 만들지 않고 확인된 조건 안에서 재검토'],
                       'evidence_refs':missing.get('evidence_refs',[])})
    if not checks:
        checks.append({'recipient':'설비보전팀','action':'검토한 관측 범위를 전달하고 새 증상이 있으면 별도 요청으로 확인','preconditions':['관측 조건 미충족을 설비 정상 확정으로 쓰지 않음'],'evidence_refs':[]})
    return checks, '유효한 근거에 연결된 점검 제안은 먼저 전달하고, 부족한 근거는 담당 역할의 별도 확인 항목으로 분리한다.'
