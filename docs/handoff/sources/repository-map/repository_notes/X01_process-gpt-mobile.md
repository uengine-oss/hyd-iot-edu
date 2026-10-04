### X01 · process-gpt-mobile
- Git: https://github.com/uengine-oss/process-gpt-mobile
- Clone: `https://github.com/uengine-oss/process-gpt-mobile.git`
- 구분: 선택 구성 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 운영 웹 포털을 여는 모바일 앱 껍데기. 푸시·네이티브 이동·오프라인 안내를 담당한다.
- 연결: 주 화면은 Vue 포털이며 mobile-live/shell/은 앱 에셋이다. 웹 배포와 앱 재배포를 구분한다.
- 확인 경로: `capacitor.config.json · android/ · ios/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-mobile/blob/main/README.md)

## 연결 목록

- X01 process-gpt-mobile → C02 process-gpt-vue3 / 화면 사용 / 웹 포털 + mobile-live/shell 앱 에셋 / [근거](https://github.com/uengine-oss/process-gpt-mobile/blob/main/README.md)
