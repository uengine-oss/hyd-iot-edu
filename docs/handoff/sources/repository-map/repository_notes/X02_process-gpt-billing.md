### X02 · process-gpt-billing
- Git: https://github.com/uengine-oss/process-gpt-billing
- Clone: `https://github.com/uengine-oss/process-gpt-billing.git`
- 구분: 선택 구성 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 결제 생성·검증·웹훅·사용량 차감과 Supabase 저장을 담당하는 백엔드.
- 연결: Gateway의 /payments 경로와 연결한다. 결제 제공자 자격증명은 저장소 지도에 포함하지 않는다.
- 확인 경로: `app/main.py · app/api/routes/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-billing/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml](https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml)

## 연결 목록

- C04 process-gpt-gateway → X02 process-gpt-billing / 호출 / /payments 경로 / [근거](https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml)
