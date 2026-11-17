# 설계한 온톨로지를 그래프 DB에 구현하고 검증하기

설계 실습에서 다룬 클래스 · 식별자 · 관계를 Neo4j 실습에서 써 본 MERGE로 이 폴더 전용 그래프 DB(랩 DB)에 옮깁니다. 과정의 첫 단계인 온톨로지를 그래프 DB에서 실제로 묻고 고쳐 보며, 조회와 부분 수정 결과를 원자료와 대조합니다.

```text
data/           실습 자료
app/features/   AI와 구현할 핵심 기능
app/ui/         결과 화면 — 제공
app/utils/      공통 처리 — 제공
output/         실행 후 생기는 결과
AGENTS.md       AI가 지킬 공통 규칙
```

실행: `python run.py`
