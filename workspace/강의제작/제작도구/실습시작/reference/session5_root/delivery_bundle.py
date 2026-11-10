def delivery(candidates, unresolved, safety_refs):
    if unresolved:
        refs = list(dict.fromkeys(r for x in unresolved for r in x.get('evidence_refs',[])))
        return [{'recipient':'설비보전팀','action':'미확인 목록을 한 묶음으로 모아 운전원에게 적용 운전 조건을, 조회 담당자에게 해당 조건의 원문·관측을 보완받은 뒤 점검 제안을 재검토',
                 'preconditions':['이 단계에서는 물리 점검 착수를 제안하지 않음','근거 보완 뒤 안전·승인 조건을 다시 확인'],'evidence_refs':refs}], '요청 전체의 근거가 모일 때까지 한 묶음의 점검 제안은 보류한다.'
    checks=[]
    for candidate in candidates:
        if candidate['status']=='충족' and safety_refs:
            checks.append({'recipient':'설비보전팀','action':candidate['name']+' 관련 현장 상태를 점검 계획에 올리고 운전 정지 가능 시점을 담당자와 확인',
                           'preconditions':['설비 정지·LOCAL·동력 잠금을 현장에서 확인한 뒤 물리 점검','설비보전팀장의 기존 승인 절차'],
                           'evidence_refs':list(dict.fromkeys(candidate['evidence_refs']+safety_refs))})
    return checks or [{'recipient':'설비보전팀','action':'대조한 범위를 묶어 전달하고 추가 증상을 확인','preconditions':['설비 정상 확정이 아님'],'evidence_refs':[]}], '이번 요청의 근거가 모두 갖춰져 점검 제안을 한 묶음으로 전달한다.'
