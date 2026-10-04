### C05 · process-gpt-infra-docker
- Git: https://github.com/uengine-oss/process-gpt-infra-docker
- Clone: `https://github.com/uengine-oss/process-gpt-infra-docker.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 로컬 배포 정의. 애플리케이션과 Supabase·Neo4j·LiteLLM·nginx를 묶는다.
- 연결: 자체 서비스 서브모듈과 DB 초기화·라우팅 파일을 보유한다. 문서상 경로와 실제 등록은 대조해야 한다.
- 확인 경로: `docker-compose.yml · .gitmodules · nginx/ · volumes/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/README.md) · [.gitmodules](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/.gitmodules) · [docker-compose.yml](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml)

## 연결 목록

- C05 process-gpt-infra-docker → T06 process-gpt-glossary / 배포 / ProcessGPT용 용어집 이미지·포트 구성 / [근거](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml)
