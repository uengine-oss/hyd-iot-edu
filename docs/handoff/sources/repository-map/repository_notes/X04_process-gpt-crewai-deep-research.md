### X04 · process-gpt-crewai-deep-research
- Git: https://github.com/uengine-oss/process-gpt-crewai-deep-research
- Clone: `https://github.com/uengine-oss/process-gpt-crewai-deep-research.git`
- 구분: 선택 구성 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: CrewAI 병렬 보고서·다중 형식 생성 구성. README에 실험·데모 목적이 명시된다.
- 연결: 작업 폴링·MCP·Supabase 이벤트와 연결. 배포 파일 존재만으로 현재 기본 실행체라고 보지 않는다.
- 확인 경로: `main.py · src/parallel/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-crewai-deep-research/blob/main/README.md)

## 연결 목록

- C06 process-gpt-k8s → X04 process-gpt-crewai-deep-research / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
