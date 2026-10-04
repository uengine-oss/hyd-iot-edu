### T06 · process-gpt-glossary
- Git: https://github.com/uengine-oss/process-gpt-glossary
- Clone: `https://github.com/uengine-oss/process-gpt-glossary.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 용어집·용어·태그 등 메타데이터와 일괄 가져오기·추출 기능을 제공한다.
- 연결: 자체 backend/·frontend/와 Postgres 저장. ProcessGPT Compose에 연결된 용어집 구성만 다룬다.
- 확인 경로: `backend/main.py · frontend/ · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-glossary/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml)

## 연결 목록

- C05 process-gpt-infra-docker → T06 process-gpt-glossary / 배포 / ProcessGPT용 용어집 이미지·포트 구성 / [근거](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml)
