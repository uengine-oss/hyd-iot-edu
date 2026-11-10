"""수집된 실제 근거로 후보별 증거 대조를 구현합니다. 모델을 다시 호출하지 않습니다."""
def assess(request, ledger):
    """request는 요청 한 행, ledger는 실제 도구 반환 목록입니다.
    각 반환: id(T식별자), tool, model_arguments, arguments, status(ok/error), result 또는 error.
    반환 dict:
      candidates: cause_id/name/status(충족·해당 없음·보류)/reason/evidence_refs 목록.
      unresolved: needed(더 필요한 근거)/evidence_refs 목록. cause_id는 해당할 때만.
      safety_refs: 실제로 받은 작업 전제 원문 T식별자 목록.
      safety: field_confirmed(실제 현장 확인 여부)/meaning(문서 전제와 현장 상태의 구분).
    없던 반환·숫자·관계를 만들지 않고 값 없음, 0, 조건 불충족을 구분합니다.
    """
    raise NotImplementedError("assess.py: 원문 적용 조건과 관측을 대조해 후보·미확인을 반환합니다.")
