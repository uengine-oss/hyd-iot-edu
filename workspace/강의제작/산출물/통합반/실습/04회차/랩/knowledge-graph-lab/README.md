# 검토한 문서 지식을 그래프 DB에 반영하고 관계 확인하기

검토해 승인한 문서 지식을 랩 DB의 설비 모델과 조치 기준에 기존 ID로 잇습니다. 가이드의 다섯 질문으로 조회한 답을 원문과 견주고 하나의 온톨로지 구축 결과로 저장합니다.

```text
data/           실습 자료
app/features/   AI와 구현할 핵심 기능
app/ui/         결과 화면 — 제공
app/utils/      공통 처리 — 제공
output/         실행 후 생기는 결과
AGENTS.md       AI가 지킬 공통 규칙
```

실행: `python run.py`
