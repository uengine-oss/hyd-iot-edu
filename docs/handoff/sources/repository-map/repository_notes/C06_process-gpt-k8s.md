### C06 · process-gpt-k8s
- Git: https://github.com/uengine-oss/process-gpt-k8s
- Clone: `https://github.com/uengine-oss/process-gpt-k8s.git`
- 구분: 연결 확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: Kubernetes Deployment·Service·런너 템플릿 등 배포 구성을 모은다.
- 연결: 메인 하위 목록에 없는 선택 실행체도 나타난다. 배포 파일 존재와 현재 운영 중임은 다르다.
- 확인 경로: `deployments/ · services/`
- 근거: [deployments/process-gpt-deepagents.yaml](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/process-gpt-deepagents.yaml) · [deployments/process-gpt-codex.yaml](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/process-gpt-codex.yaml) · [deployments/agent-runner-templates.yaml](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/agent-runner-templates.yaml)

## 연결 목록

- C06 process-gpt-k8s → A01 process-gpt-deepagents / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
- C06 process-gpt-k8s → A04 process-gpt-codex / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
- C06 process-gpt-k8s → A05 process-gpt-cli-agent / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
- C06 process-gpt-k8s → T05 process-gpt-visionparser / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
- C06 process-gpt-k8s → X03 process-gpt-crewai-action / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
- C06 process-gpt-k8s → X04 process-gpt-crewai-deep-research / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
- C06 process-gpt-k8s → X05 process-gpt-langchain-react / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
- C06 process-gpt-k8s → X06 process-gpt-browser-use / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
- C06 process-gpt-k8s → C08 process-gpt-session-router / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
