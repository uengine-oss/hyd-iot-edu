# 강의 스킬

이 저장소의 교재와 실습 자료를 만들 때 쓰는 스킬이다. 스킬 원본은 이 폴더 한 곳에 둔다. 경로는 저장소 루트 기준이다.

HYD 과정의 일은 HYD 전용 스킬 둘이 먼저다. 일반 스킬(`lecture-*`)은 형식 · 도구 · 일반 절차를 맡고, HYD 스킬과 부딪치면 HYD 스킬과 `production/standards/제작기준.md`를 따른다.

| 스킬 | 언제 쓰는가 | 주요 파일 |
|---|---|---|
| `hyd-course-deck` | HYD 이론 교재 PPTX 덱을 만들거나 고치거나 점검하거나 다시 조립하거나 배포 묶음을 만들 때 | `SKILL.md`, `scripts/재조립.py`, `scripts/장수.py`, `scripts/배포묶음.py` |
| `hyd-lab-guide` | HYD 실습 가이드(핸즈온 가이드)를 쓰거나 고칠 때 | `SKILL.md`, `scripts/실습목록.py` |
| `lecture-plan` | 학교 지시 · 리서치를 요구와 수용 기준으로 정리하고, 강의계획 · 커리큘럼을 짜고, 검토 의견과 바뀐 사실을 자료 전체에 반영할 때 | `SKILL.md`, `scripts/check_contract.py`, `templates/requirements.json` |
| `lecture-deck` | 덱 MD(화면 원고)를 쓰고 `deck2pptx.py`로 PPTX를 만들 때. 덱 MD의 형식, 유형, 아이콘, 렌더 | `SKILL.md`, `references/덱MD-PPTX형식.md`, `references/문체.md`, `scripts/deck2pptx.py`, `scripts/find_icon.py` |
| `lecture-lab` | 실습 코드, 학생 실습 가이드(HTML · MD · PDF), 환경 세팅 문서를 만들고 실제로 돌려 검증할 때 | `SKILL.md`, `references/`, `가이드그림.py`, `assets/가이드기준/md2pdf.py` |
| `lecture-verify` | 자료의 정확성 · 누락 · 흐름 · 실습 가능성과 완료 상태를 검토할 때(검토만이면 고치지 않는다) | `SKILL.md`, `문서검사.py` |
| `lecture-deliver` | 학생 배포본 · 검토용 묶음 ZIP을 만들고 구성과 민감 정보를 검증할 때. 업로드는 명시 요청이 있을 때만 | `SKILL.md`, `검토자료.py` |
| `lecture-common` | 스킬이 아니다. 위 스킬이 함께 쓰는 공통 기준과 도구 | `공통기준.md`, `rules/`, `프로젝트탐지.py`, `workflow_doctor.py` |

## 서로의 관계

```
lecture-common(공통 기준 · 공용 도구)
      │
lecture-plan ──► lecture-deck ──► lecture-lab ──► lecture-verify ──► lecture-deliver
 요구 · 계획        덱 · PPTX        실습 · 가이드      검토 · 완료 판정     묶음 · 업로드

hyd-course-deck  = HYD 교재 덱의 절차. 형식과 도구는 lecture-deck, 규칙은 production/standards/제작기준.md, 경위는 production/handoff/
hyd-lab-guide    = HYD 실습 가이드의 원칙. 일반 절차는 lecture-lab, 형식은 production/labs/_old/실습가이드/틀/, 착수는 production/handoff/06_실습가이드_착수.md
```

- 보통 순서는 계획 → 덱 · 실습 → 검증 → 요청이 있을 때 배포다. 한 스킬의 일만 요청받았으면 그 스킬만 쓴다.
- 규칙을 스킬 문서에 복사하지 않는다. HYD 교재의 규칙을 바꿀 때는 `production/standards/제작기준.md`를 고친다.
- 스킬은 훅이나 슬래시 명령에 기대지 않는다. 공통 기준은 `lecture-common/공통기준.md`에 있다.

## 스킬을 고치거나 더할 때

`lecture-common/rules/스킬-공식규격.md`와 `lecture-common/rules/skill-admission.md`를 따르고, 더했으면 `lecture-common/workflow-skills.json`과 위 표에 올린다. 구조 검사는 저장소 루트에서 돌린다(머리말 · 이름 · 깨진 링크만 본다. 내용이 맞는지는 판정하지 않는다).

```bash
uv run --no-project --with pyyaml python .claude/skills/lecture-common/workflow_doctor.py .
```
