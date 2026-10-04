### A08 · process-gpt-deep-research
- Git: https://github.com/uengine-oss/process-gpt-deep-research
- Clone: `https://github.com/uengine-oss/process-gpt-deep-research.git`
- 구분: 직접 등록 / public / 브랜치 `master`
- 메인 경로: `services/deep-research`
- 역할: 웹·내부 자료를 결합해 리서치 보고서·차트·이미지·템플릿 문서를 생성한다.
- 연결: Tavily·선택적 Memento·Office MCP·Supabase 및 SDK 폴링에 연결한다.
- 확인 경로: `main.py · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-deep-research/blob/master/README.md)

## 연결 목록

- C01 process-gpt → A08 process-gpt-deep-research / 등록 / services/deep-research / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- A08 process-gpt-deep-research → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-deep-research/blob/master/README.md)
- A08 process-gpt-deep-research → T03 process-gpt-office-mcp / 설정 연결 / 문서 출력 시 선택 연동 / [근거](https://github.com/uengine-oss/process-gpt-deep-research/blob/master/README.md)
