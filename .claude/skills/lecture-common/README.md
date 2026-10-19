# lecture-common — 강의 스킬의 공용 문서와 도구

스킬이 아니다(`SKILL.md`가 없다). 다른 강의 스킬이 함께 쓰는 기준 문서와 도구를 둔다.

| 파일 | 무엇 |
|---|---|
| `공통기준.md` | 강의 스킬이 함께 전제하는 기준(범위와 판정, 이해 · 구현 기준, 보존과 공개, 사용자 표시). 스킬 문서가 「공통 기준 N절」로 가리킨다 |
| `rules/스킬-공식규격.md`, `rules/skill-admission.md`, `rules/routing-cases.json` | 스킬 문서의 규격, 스킬 추가와 시험 절차, 요청별 담당 스킬의 경계 사례 |
| `workflow-skills.json` | 이 저장소가 지원하는 스킬 이름 목록(`workflow_doctor.py`가 읽는다) |
| `프로젝트탐지.py` | 강의 프로젝트의 루트 · 문서 · 가이드 · 그림 폴더를 찾는다. `lecture-lab/가이드그림.py`, `lecture-verify/문서검사.py`, `lecture-deliver/검토자료.py`가 불러 쓴다 |
| `workflow_doctor.py` | 스킬 폴더의 구조 검사(머리말, 이름, 깨진 링크). 의미와 자동 선택은 판정하지 않는다 |
| `inspect_host_probe.py` | 기록해 둔 호스트 시험 결과를 다시 검사한다(스킬 선택 시험을 기록했을 때만 쓴다) |
| `owned_process.py` | 시험이 띄운 프로세스를 그 핸들로만 정리한다(Windows 전용) |
| `세션시작.py` | 작업 공간에서 세션 시작 훅으로 쓰던 안내문 출력기. 이 저장소의 설정에는 걸려 있지 않다. 스킬은 이 훅 없이 동작한다 |

저장소 루트에서 실행한다.

```bash
uv run --no-project --with pyyaml python .claude/skills/lecture-common/workflow_doctor.py .
python3 .claude/skills/lecture-common/프로젝트탐지.py 제작용/기존제작/decks
```
