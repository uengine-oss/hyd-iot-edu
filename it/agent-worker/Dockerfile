# agent-worker: Claude Code(npm) + 워커. CLI 는 원본 키 없이 process 로컬 중계 관문이 그 점유에 묶어 준 실행 토큰으로만 모델을 부른다
# (worker/course_access.py). Neo4j 조회 MCP 는 hydcommon/neo4j_mcp.py(이 이미지의 파이썬)로 돈다.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git \
 && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && apt-get install -y --no-install-recommends nodejs \
 && node -e "const [a,b,c]=process.versions.node.split('.').map(Number); if(a!==24 || b<22 || (b===22 && c<1)) throw Error('Node.js 24.22.1 or newer 24.x LTS security release required')" \
 && npm install -g @anthropic-ai/claude-code@2.1.310 \
 && apt-get purge -y --auto-remove && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
# CLI 격리(worker/cli_sandbox.py)는 커널이 거는 Landlock 파일 규칙이 있어야 한다 — 없으면 이미지를 만들지 않는다(격리 없이 도는 폴백 없음).
RUN /usr/bin/setpriv --help | grep -q -- '--landlock-access'
COPY it/agent-worker/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
# procsvc 패키지 전체(워커가 procdb · task_deferral · agents_store · mcp_secrets · mcp_check · course_ledger · work_rules … 를 import 하고,
# procdb 는 그 저장소들을 끌어온다). 손으로 고른 파일 목록은 어긋나 컨테이너 워커가 켜지자마자 죽었다(2026-10-25: procdb → approval_store).
COPY it/process/procsvc /srv/procsvc
COPY it/neo4j/v2/schema_prompt.md /srv/ontology/schema_prompt.md
COPY it/agent-worker/worker /srv/worker
ENV PYTHONUNBUFFERED=1 WORKSPACE_ROOT=/workspace SCHEMA_PROMPT=/srv/ontology/schema_prompt.md HYD_CLI_SANDBOX=landlock
VOLUME ["/workspace"]
EXPOSE 8097
CMD ["python", "-m", "worker.main"]
