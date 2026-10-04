### P03 · process-gpt-strategy
- Git: https://github.com/uengine-oss/process-gpt-strategy
- Clone: `https://github.com/uengine-oss/process-gpt-strategy.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/strategy`
- 역할: BSC 전략목표·KPI·실행과제·설문·성과 측정과 기업 운영 온톨로지를 관리한다.
- 연결: 실행 데이터에서 성과를 수집하며 AGE 그래프를 조회·동기화한다. DB_*와 GRAPH_DB_* 설정을 구분한다.
- 확인 경로: `app/main.py · docker-compose.age.yml · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-strategy/blob/main/README.md)

## 연결 목록

- C01 process-gpt → P03 process-gpt-strategy / 등록 / services/strategy / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → P03 process-gpt-strategy / 호출 / 전략·KPI·온톨로지 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
