# 코드 폴더

- `source/`: 원자료입니다. 읽기만 합니다. `ontology/`(설비 그래프), `cases/`(경보 사례 열한 건), `manuals/`(HM-8 · PM-02 · PR-07 원문).
- `input/`: 이번 실습은 비어 있습니다.
- `output/`: 직접 만든 코드와 결과를 저장합니다. `expected.md`·`review.md`는 제공 빈 틀입니다.
- `llm_client.py`와 `.env`: 모델 접속입니다. `.env`에는 수업에서 받은 값만 적고, 그 값을 다른 파일·채팅에 옮기지 않습니다.
- `입출력_계약.md`: 결과 형식. `check.py`: 결과의 구조 검사.

과제는 [../START.md](../START.md)에 있습니다.
