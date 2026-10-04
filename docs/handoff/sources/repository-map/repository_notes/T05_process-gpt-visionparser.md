### T05 · process-gpt-visionparser
- Git: https://github.com/uengine-oss/process-gpt-visionparser
- Clone: `https://github.com/uengine-oss/process-gpt-visionparser.git`
- 구분: 연결 확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: PDF·이미지 OCR과 스키마 기반 구조화 정보 추출 파이프라인.
- 연결: Agent SDK/A2A·Supabase로 작업 관리·진행 이벤트를 연결한다. Kubernetes 배포 정의도 확인된다.
- 확인 경로: `README.md · pyproject.toml`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-visionparser/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/process-gpt-visionparser.yaml](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/process-gpt-visionparser.yaml)

## 연결 목록

- C06 process-gpt-k8s → T05 process-gpt-visionparser / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
