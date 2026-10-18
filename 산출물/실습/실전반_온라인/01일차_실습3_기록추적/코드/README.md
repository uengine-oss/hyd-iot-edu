# 기록 추적기

포털에 저장된 실행 기록의 참조를 검사하는 작은 도구입니다. 서버·모델 키·추가 패키지 없이 Python 3으로 실행합니다. 제공된 코드는 온라인 수업용 실행본입니다. 직접 구현을 연습하려면 먼저 검사 함수를 읽고, 한 조건씩 고친 뒤 검사를 반복하세요.

이 폴더를 VS Code로 열고 터미널의 현재 폴더가 이곳인지 확인합니다.

```powershell
python trace_records.py
python trace_records.py recorded/case_a_redacted.json --output result/redacted_result.json
python -m unittest -v
```

첫 실행은 작업지시→판단 하나만 확인하며, 나머지 연결은 미확인입니다. 전체 연결의 미확인은 프로그램 오류가 아닙니다. 두 번째 실행은 참조를 가린 교육용 자료라서 첫 연결도 미확인입니다. 테스트 네 개는 누락·다른 사건의 식별자·빈 문자열을 잘못 통과시키지 않는지 확인합니다.

`result/trace_result.json`과 `result/redacted_result.json`을 비교하세요. 원본에 없는 참조를 보충해 테스트를 통과시키지 마세요. 작업지시는 배정됨 상태이며 정비 완료로 바꾸어 설명할 수 없습니다.

이 도구는 참조를 대조할 뿐, 경보부터 명령 ACK까지 전체 실행을 재생하거나 설비를 제어하지 않습니다.
