# 강의 중계 이미지 — LiteLLM 판본을 다이제스트로 박아 같은 판을 다시 만든다(v1.106.6). 설정은 config.yaml 한 곳, 비밀값은 실행 환경에서 받는다.
FROM ghcr.io/berriai/litellm@sha256:37e2dafb088a7723beb998590682957386dfc83ffea1848486f8e0e5cfac0b06
COPY config.yaml /app/config.yaml
# 관리 화면과 API 문서 화면은 쓰지 않는다 — 열어 두면 인터넷에 마스터 키 로그인 창이 하나 더 생긴다
ENV DISABLE_ADMIN_UI=True NO_DOCS=True NO_REDOC=True
CMD ["--port", "4000", "--config", "/app/config.yaml"]
