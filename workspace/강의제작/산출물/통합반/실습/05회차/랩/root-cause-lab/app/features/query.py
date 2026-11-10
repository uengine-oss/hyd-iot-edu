"""모델이 필요한 도구를 고르도록 지침과 조회 범위를 구현합니다."""
def instructions(request):
    """request: requests.csv 한 행. 반환: 필요한 근거·조회 범위·미확인 처리에 관한 문자열."""
    raise NotImplementedError("query.py: 내 요구와 원문 근거에 맞는 조회 지침을 구현합니다.")


def prepare_query(name, arguments, request):
    """모델 도구 이름과 인수, 요청을 받아 실제 실행할 인수 dict를 반환합니다.
    도구 계약은 app/utils/evidence.py의 TOOL_CONTRACT입니다.
    원래 인수와 반환 인수는 수집 기록에 따로 남습니다.
    """
    raise NotImplementedError("query.py: 내가 고른 설비·기간·원문 범위 기준을 구현합니다.")
