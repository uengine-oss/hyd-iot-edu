### X06 · process-gpt-browser-use
- Git: https://github.com/uengine-oss/process-gpt-browser-use
- Clone: `https://github.com/uengine-oss/process-gpt-browser-use.git`
- 구분: 선택 구성 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 브라우저 인스턴스와 Consumer ID 기반 라우팅·VNC·API 접근을 묶는 배포 프로젝트.
- 연결: browser-use/와 gateway/를 구분한다. T08의 일반 Pod 셸 MCP와 동일 구현이 아니다.
- 확인 경로: `browser-use/ · gateway/ · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-browser-use/blob/main/README.md)

## 연결 목록

- C06 process-gpt-k8s → X06 process-gpt-browser-use / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
