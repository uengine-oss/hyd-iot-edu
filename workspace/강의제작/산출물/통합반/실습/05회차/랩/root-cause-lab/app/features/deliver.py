"""내가 선택한 전달 방침으로 다음 역할의 확인 항목을 만듭니다."""
def deliver(request, assessment, choices):
    """request는 요청 한 행, assessment는 현재 후보 판정입니다.
    choices는 choices.csv에서 decision=deliver인 실제 입력 행 목록입니다.
    각 행은 choice(전달 요구), source(선택 근거), changed_action(달라질 행동), input_file/input_line을 가집니다.
    이 요구를 후보 상태와 미확인 근거에 적용하는 판단을 구현합니다. 요구의 출처를 AI가 만들지 않습니다.
    반환 dict:
      next_checks: recipient(받을 역할)/action(할 일)/preconditions(작업 전제 문자열 목록)/evidence_refs 목록.
      delivery_reason: 선택한 방침이 이 요청의 다음 행동을 어떻게 바꿨는지 설명.
      delivery_questions: 요구가 더 필요하면 recipient/question 목록. 이때 next_checks는 비웁니다.
    원인·관측의 판정을 이 함수에서 새로 만들지 않습니다. 실제 승인·작업 발행도 하지 않습니다.
    """
    raise NotImplementedError("deliver.py: 선택과 근거를 실제 점검 전달 순서에 반영합니다.")
