"""통합02의 지정 프로젝트 하나만 생성한다. 다른 과정·회차·강사 참조를 재생성하지 않는다.

python build_session2_projects.py ontology --dest 작업/검사/...
python build_session2_projects.py ontology --apply [--completed]
"""
from pathlib import Path
import argparse
from contextlib import nullcontext
import json
import shutil
import subprocess
import sys
import tempfile

import build_labs as B
import data_session2 as D
import lab_frame as F
from lab_package import ROOT, pack, entry, register, student_files, write_zip
from project_layout import write_metadata, errors, DB_RULE
import session2_project as P
import session2_project_guides as G
import session2_graph_project as GP

DEST = ROOT / 'workspace/강의제작/산출물/통합반/실습/02회차/랩'
# 실전반 두 랩은 같은 생성 길에 공장 규모 자료와 끝의 구매팀 응용만 얹는다(코딩랩 K-10 — session2_factory*.py). 통합반 산출물은 과정 인자의 기본값으로 예전과 같은 바이트가 나온다.
COURSES = {'통합반': dict(dest=DEST, prefix='integrated', versions=None),
           '실전반': dict(dest=ROOT / 'workspace/강의제작/산출물/실전반/실습/02회차/랩', prefix='practical', versions={'ontology-lab': 'v32-practical', 'graph-lab': 'v32-practical'})}
# 그래프 랩 v33-lab(2026-11-18): 장난감 시험 two_turn에서 AI가 「다 해 줘」에 기능 파일 둘을 한 번에 고치고 update.cypher에 불용 설비 처리(정할 지점)를 학생 선택 없이 써 넣어, 랩별 경계 두 줄을 더함(GRAPH_RULE). 설계 랩은 v32-lab 그대로다.
# v34-lab(2026-11-18): 학생 역 리허설(판정/리허설_i2v32_ontology.md · 리허설_i2v33_graph.md)의 막힐 자리 — 기대 답 틀의 칸 뜻(기준 단위 · 질문 3 항목), 가이드 문장 여덟 곳, 칸 수가 다른 CSV 줄을 파일:줄로 짚고 멈춤.
VERSIONS = {'ontology-lab': 'v64-lab', 'graph-lab': 'v64-lab'}
# v64-lab(통합반 두 랩) · v32-practical(실전반 두 랩) — 2026-11-28, 받기 시험 v63 · v31(작업 폴더 판정/받기시험_v63_v31.md 9절 나4 ~ 나6 · 가14 ~ 가16)에서 나온 것을 한 판에(판정/랩고침_실행기록_v64_v32.md):
#   설계 랩 — 질문 대조 화면(query)도 근거 칸의 파일:줄을 원자료에 대어 꼴 카드처럼 먼저 짚는다(가이드는 기대 답 화면을 앞 단계에서만 실행하게 해, 뒤 단계에서 더한 줄이 끝까지 검사받지 않았다 — session2_steps ask),
#   속성 화면(표를 적기 전 · 뒤)은 모델에 담지 않기로 행 처리 표에 적은 줄을 세지 않아 넣기 전 검증과 같은 줄을 본다(session2_model_tool.kept), 관계 화면의 「가장 많은 곳」은 같은 수인 곳을 모두 댄다(links_view),
#   카드의 문장은 「 · 」에서 배지로 갈리지 않는다(result_view — 줄 (이름, 글, '글')), 실전 질문 5의 근거 검사는 공급사 이름을 원자료와 같은 잣대(괄호 앞 이름)로 견준다(session2_factory_lab purchase_evidence).
#   그래프 랩 — 되돌리기 화면(reset)이 개수만 보지 않고 넣기 화면과 같은 잣대(관계의 시작과 끝 · 노드의 값 · 날짜 속성의 자료형)로 본다(session2_graph_project reset — 틀린 적재 쿼리로 되돌려도 「모델 파일대로 돌아왔습니다」였다),
#   날짜 속성을 글자와 견준 조건 카드는 결론 줄 바로 아래(대조 표보다 먼저)에 둔다(session2_steps ask_question). AGENTS.md · 빈 틀 · 자료는 앞 판과 같은 바이트다.
# 실전반 설계 v32-practical — 2026-11-28, 학생 역 리허설 v31(47분)의 두 자리: 가이드 07이 HYD-07 지시계 두 줄이 유온계 · 압력계임을 밝히고, 11은 다르게 적은 곳의 개수를 13단계 공급 화면이 센 수와 다시 맞춰 보게 한다.
# v63-lab(통합반 두 랩) · v31-practical(실전반 두 랩) — 2026-11-28, 실전 설계 v30 학생 역 리허설(65.9분 · Codex 기다림 50.7분) · 받기 시험(v62 · v30 가10 ~ 가13)에서 나온 것을 한 판에(작업 폴더 판정/랩고침_실행기록_v63_v31.md):
#   누가 세어도 같은 개수는 제공 화면이 센다 — 설계 랩의 속성 · 관계 화면은 표를 적기 전에 실행하면 클래스마다 쓸 수 있는 칸의 빈 줄 수, 클래스 짝마다 지금 자료의 이어짐과 하나도 없는 대상을 보이고
#   (session2_model_tool.columns_view · links_view, session2_steps properties_before · relations_before), 실전 설계의 공급 화면은 공급사 · 견적을 적기 전에 견적표를 읽은 값 · 겹친 줄 · 칸마다 빈 줄을 보인다(session2_factory_lab supply_before).
#   실전 설계 가이드 05 · 13은 그 화면을 먼저 실행하고 Codex에게는 선택지 · 뜻 · 추천을 묻게 한다(공장 규모 자료에서 Codex가 개수를 세느라 한 번에 8.8분 · 7.1분을 기다렸다). 통합반 가이드는 그대로다.
#   기대 답 화면이 근거 칸의 파일:줄을 원자료에 대어, 그 줄에 물은 대상이나 답의 값이 없으면 짚는다(session2_steps evidence_off, 실전 질문 5는 session2_factory_lab purchase_evidence — 리허설에서 Codex가 낸 근거 줄 번호가 여러 곳 틀렸는데 잡는 화면이 없었다).
#   「 / 」로 이은 답(한 공급사의 견적 여럿)은 묶음끼리 견주고 칩도 묶음끼리 놓는다(session2_steps same · result_view.aligned), 꼴 카드의 조사를 받침에 맞게, 목록에 없는 공급사 이름의 안내,
#   그래프 랩 내보내기는 속성이 적히는 차례까지 고정하고(lab_cypher.exported), 질문 화면은 날짜 속성을 따옴표 글자와 견준 쿼리를 짚는다(lab_cypher.text_against_date).
#   실전 설계 13(견적의 출처도 속성으로) · 14(다른 표기 기대 답은 공급사마다 · 고친 뒤 다시 확인 묶음).
# v62-lab(통합반 두 랩) · v30-practical(실전반 두 랩) — 2026-11-27, 학생 역 리허설(실전 설계 v29 · 실전 그래프 v28) · 받기 시험(v61 · v29) · v61 Codex 재확인에서 나온 것을 한 판에(작업 폴더 판정/랩고침_실행기록_v62_v30.md):
#   화면이 사실과 다르게 말하던 곳 — 넣기 화면이 관계를 이름별 개수로만 견줘 화살표를 거꾸로 넣어도 「맞음」(lab_cypher.relation_gap — 시작 · 끝 노드까지 견줘 거꾸로 들어간 관계를 짚는다, 실전 공급 관계 화면도),
#   「TS1=65」처럼 짝지은 값이 같음인데 다른 값처럼 그려짐(result_view.aligned), 스키마는 날짜인데 랩 DB에는 글자로 들어가 날짜와 견주는 쿼리가 조용히 다 거름(제공 적재 쿼리가 날짜로 넣고, lab_cypher.date_gap이 랩 DB의 자료형을 물어 넣기 · 수정본 반영 화면이 짚는다),
#   실전 그래프 모델 파일의 출처가 폴더에 없는 옛 파일 이름(build_graph가 새 구조 이름으로), 실전 그래프 첫 화면 · 개수 화면이 공급 관계를 뺀 수와 그 까닭을 말함, 넣은 뒤 그림은 나가는 관계가 있는 노드에서.
#   설계 랩 — 기대 답 화면이 줄마다 꼴(무엇을 어느 칸에)을 원자료에 대어 파일:줄로 짚고 질문 대조도 같은 카드를 먼저 보인다(session2_steps expected_form, 실전반 질문 5는 session2_factory_lab), 속성 빈 틀 머리의 예에 「구성 요소의 구성요소」.
#   가이드 — 설계 05(정할 것 넷을 한 번에) · 07 힌트(갈리는 센서를 한 번에 모아서), 그래프 04(질문 ① · ②를 물을 설비를 내가 고름) · 07(날짜인 속성은 날짜로 · 관계 방향 카드) · 12(수정본에 적힌 칸만 · 파일 하나마다 「이어서 해 줘」),
#   실전 설계 11(기준일) · 12(공급사 이름 꼴) · 13(결정 뒤 표 셋을 함께 — 부탁 5 → 2, AGENTS.md 한 문장) · 실전 그래프 13 · 14.
# v61-lab(그래프 랩) — 2026-11-27, 수정 쿼리가 멈추는 박아 넣기를 넓힘: 수정본 칸의 값에 더해 모델에 있는 대상의 식별자(설비 코드와 태그를 이어 붙인 HYD-01:VS1 같은)를 쿼리에 적어도 파일:줄로 멈춘다(lab_cypher.change_plan — 일부러 넣어 보니 앞 판은 이 꼴을 통과시켰다).
# v61-lab(설계 랩) — 2026-11-27, 가이드 07의 규칙 코드 앞 물음을 「갈리는 센서 셋을 한 번에 모아서 물어봐 줘」로(학생 역 리허설 v59에서 「하나씩」을 받은 Codex가 다섯 번을 오갔다 — 06-2 대본 윤문 3차의 지적).
# v60-lab(두 랩) — 2026-11-27, v59 학생 역 리허설 두 건과 실전반 공장 규모 자료에서 나온 구멍(작업 폴더 판정/랩고침_v60_대기.md):
#   설계 랩 — 넣기 전 검증이 관계가 하나도 이어지지 않은 인스턴스를 경고 카드로 보인다(판단은 사람이 원자료로). 속성 빈 틀 머리를 「id 줄만 적지 않고 질문이 묻는 칸은 속성으로 담는다」로,
#   질문 1 대조는 센서가 없는 구성 요소도 「없음」 줄로 낸다.
#   그래프 랩 — 수정 쿼리가 수정본 줄의 값을 쿼리에 적으면 파일:줄로 멈춘다(lab_cypher.change_plan — 리허설에서 'HYD-02'를 박아도 「맞음」이었음), 넣기 전 실험 둘째 카드는 name으로,
#   가이드 03 · 04 · 12의 힌트와 정답 글(근거 줄 열어 보기 · 질문 ②는 사내 품번 · 결정이 보이는 설비로 물은 질문 ① 줄 · 값은 row의 칸으로).
# v59-lab(두 랩) — 2026-11-27, v58 독립 검토 두 건(작업 폴더 판정/검토_랩_설계_v58.json · 검토_랩_그래프_v58.json)의 지적 고침(실행 기록 판정/랩고침_실행기록_v59.md):
#   설계 랩 — 스키마 표 세 장도 학생이 고른다(가이드 04 · 05단계, AGENTS.md 랩별 경계가 표 이름으로 짚음). 관계는 그은 방향 그대로든 거꾸로든 따라가 찾고(1회차 「찾을 때는 거꾸로 따라가도 된다」),
#   방향은 관계 표의 「읽는_말」로 원자료 한 쌍을 문장으로 읽어 본다. 칸 이름을 이론대로 「시작 · 종료」, 「적어도_하나」는 어느 쪽인지(시작마다 · 종료마다) 적는다.
#   카디널리티는 이어질 수 있는 개수라 지금 자료보다 넓게 적어도 어긋남이 아니다(참조 답 「쓴다」 = N:M). UTF-8이 아닌 표 · 한글이 깨진 표는 파일:줄로 짚고 멈춘다. 완성본은 둘째 바퀴(질문 4)까지.
#   그래프 랩 — 제공 모델을 설계 랩 참조 갈래의 출력으로 바꿈(design_model — 두 랩의 모델 꼴 · 식별자가 같다). 수정본 반영은 넣은 직후와 견주고 둘째 실행은 되돌리는 트랜잭션에서, 스키마에 없는 속성 ·
#   목록에 겹친 값은 멈춤(스키마에 더할 속성은 빈 틀 schema_additions.csv), `python run.py reset` · `changes`, 질문 대조는 「열+열」 짝, 볼_열이 결과에 없으면 그 줄만 견주지 못함,
#   학생 몫 적재 쿼리 셋은 설비 노드(원자료 표의 줄) · 설비-구성 요소 관계 · 구성 요소-부품 관계, 제공 쿼리는 코드가 모델에서 만들어 output/에 남긴다. 결정은 수정본 반영 바로 앞 단계로.
# v58-lab(두 랩) — 2026-11-27, 사용자 「랩이 이 수업의 메인 … 장난감이면 안 되고 … 난이도를 내리지 말고 쉽게 이끈다」 · 확정 구성안(작업 폴더 판정/구성안_랩고침.md, 근거 판정/랩검토_설계.md · 랩검토_그래프.md):
#   설계 랩 — 스키마를 학생이 만든다: 제공 코드에 박혀 있던 클래스의 의미 · 속성 · 자료형 · 필수를 빈 틀 classes.csv · properties.csv로 꺼내고 relations.csv에 「끝이 적어도 하나」를 더했다(design.csv는 없앰).
#   제공 코드(session2_model_tool)는 그 표대로 원자료를 옮기고, 원자료 행을 표에 대어 본다(필수인데 빈 행 · 자료형에 맞지 않는 값 · 적어도 하나인데 관계가 없는 인스턴스 — 걸릴 수 있는 검증).
#   질문은 관계를 정한 방향대로만 따라가고(반대로 저장하면 찾지 못함), 답에 필요한 원자료 칸을 담은 속성이 없으면 「답할 수 없음」이다. 내가 더하는 질문 4(클래스의 속성으로 거르기 · 견주기)로 둘째 바퀴를 돈다.
#   구조 검사(check.py)는 날짜 자료형과 「끝이 적어도 하나」를 본다(checker의 통합반 덧댐). 가이드는 열 단계(04 스키마 표 세 장 · 09 새 질문).
#   그래프 랩 — 아래 build_graph와 session2_graph_project의 v58 주석.
# v54-lab(설계) · v57-lab(그래프) — 2026-11-25, 사용자 「너무 유치하고 그럼.. 세련되고 트렌디하게」 → 「가독성을 위주로 … css를 신경써 레이아웃이랑 / 필요한것만 보여준다던지」 → 견본을 보고 「이 모양으로 전부」:
#   결과 화면을 읽기 쉬움 위주로 다시 — 화면마다 결론 한 줄 → 주인공 그림이나 표 하나 → 볼 곳, 그림과 겹치는 표 · 원문은 화면 끝 「자세히 보기」 하나에 모으고 설명은 한 줄로.
#   큰 글자(본문 18px · 결론 38px · 표 17px · 노드 식별자 18px 고정폭)와 진한 대비, 흰 카드 + 얇은 선, 상태는 작은 점 + 글, 클래스 색은 노드 왼쪽 띠와 범례에만(result_view.py). 대조 표는 기대 · 실제 조각을 같은 차례로 놓는다.
#   아래 v53 · v56의 내용 고침(따라간 길 · 힌트 · 오류 좌표)을 그대로 담는다. v53 · v56은 정본에 올린 적이 없는 판이다.
# v53-lab(설계) · v56-lab(그래프) — 2026-11-25, 그래프 랩 v55 학생 역 리허설(판정/리허설_그래프_v55.md)의 지적: ① 질문 화면의 「쿼리가 따라간 길」이 결과 값으로 길을 짐작해 쿼리가 지나지 않은 관계까지 칠했다 —
#   쿼리의 MATCH 패턴에 경로 이름을 붙여 랩 DB에서 다시 맞춘 노드 · 관계만 그린다(lab_cypher.path_query · walked, result_figures.walk_figure). 읽지 못하는 쿼리는 그림 없이 까닭을 말한다.
#   ② 질문 ③ 문장을 「다른 표기(예전 품번 · 제조사 품번 · 표기 변형)」로 ③ 08 힌트에 볼_열 ④ 결정 기록 검사가 파일:줄과 지점 이름으로 짚음(lab_frame.CHOSEN_CHECK — 설계 랩 check.py도 같은 원본)
#   ⑤ 적재 표 「바뀐 것」 · 유일 제약 카드에 한국어 뜻을 먼저. 설계 랩은 공용 원본(check.py · results.py)이 바뀌어 같은 바이트로 맞추려고 다시 만들었다(화면 · 가이드는 v52와 같다).
# v52-lab(설계) · v55-lab(그래프) — 2026-11-25, 사용자 「html이 진짜 이쁘고 좀 가독성좋고 재밌어야해 … 눈으로 보여주기 용을 htmㅣ이 담당 … 파트가없다고하더라도 쥐어짜내셈 neo4j를 그댈 보여줘도되기도하는데」:
#   결과 화면을 밝은 바탕 · 맨 위 결론 한 줄 · 명령마다 그림 하나(표는 그 아래 근거)로 다시 만듦(코딩랩 K-3). 그리는 코드는 result_view.py(학생 app/ui/render.py), 그림 블록과 자료 → 그림 도우미는 result_figures.py(학생 app/utils/results.py 끝),
#   명령마다 무엇을 그릴지는 session2_steps의 COMMON · DESIGN_INTEGRATED · GRAPH와 session2_graph_project.EXTRA_ACTIONS. 클래스마다 색 하나(두 랩 같은 색), 그래프 랩은 그 폴더 랩 DB의 Neo4j Browser를 여는 단추.
#   같은 판에서 독립 검토(판정/검토_랩_v51_v54.md) 「나」 셋: 새 랩 DB 안내가 유일 제약부터(가이드 13 · db.py 두 줄), 멈춤 글의 학생 PC 절대 경로(run.py의 local), 06 힌트 「한 번 더 실행해도 오류가 나지 않게」.
#   AGENTS.md · 빈 틀 · 자료 · 결정 지점은 앞 판과 같은 바이트.
# v51-lab(설계) · v54-lab(그래프) — 2026-11-25, 사용자 「결함 근본을 수정하셈」: ① 출력 글자표 — 제공 run.py · check.py가 출력을 UTF-8로 쓰고(lab_frame.UTF8_OUT), 구조 검사는 UTF-8 모드로 띄운다.
#   한국어 Windows에서 Codex가 `python run.py`를 대신 돌리면 파이썬이 cp949로 써서 한글이 모두 깨지고 「—」에서 UnicodeEncodeError로 멈췄다(실측: 코딩랩.md 「함정」).
#   ② 그래프 랩에 유일 제약 걸음(가이드 06단계 · 빈 틀 constraints.cypher · `python run.py constraints`) — 이론 48 · 57 · 58장 「식별자에 유일 제약을 걸고 넣을 때는 MERGE」의 앞 절반이 랩에 없었다.
#   두 고침의 원본은 두 반 공용 자리(lab_frame · session2_project.RUN · session2_steps.COMMON · GRAPH · lab_cypher · session2_answers.CONSTRAINT_*)에 있다. AGENTS.md는 두 랩 모두 앞 판과 같다.
# v53-lab(2026-11-23, 그래프 랩만): 06 「뭐부터 해야 할까?」의 ON CREATE SET 줄을 다른 힌트와 같은 물음 · 권유 꼴로(가이드 P-5 — 힌트에 까닭 문장 · 「~하지 않게」 꼴을 쓰지 않음). 랩 폴더는 v51과 같다.
# v52-lab(2026-11-23, 그래프 랩만): 가이드 정답 부탁 · 힌트를 완성본에 맞춤 — 06 넣기는 「SET」 대신 값을 처음 만들 때만 넣는 ON CREATE SET(맨 SET이면 수정본 반영 뒤 load · repeat이 이름 · 상태를 옛 값으로 되돌려 질문 3이 「다름」), 질문 2에서 교체 부품이 없는 구성 요소(구동 모터)는 「없음」으로 남김(04 기대 답 · 08 쿼리, 완성본 query.cypher의 OPTIONAL MATCH · expected.csv). 랩 폴더는 v51과 같다.
# v51-lab(2026-11-20, 그래프 랩만 — workspace 84561f36, lab_package --version으로 묶음): 기준 지도(data/reference_map.json)의 쿨러 → 센서 관계 화면 이름을 포털 main ca7fdee8의 「감시 센서」로. 이 생성기는 main의 enterprise.js를 읽어 같은 바이트를 낸다.
# v50-lab(2026-11-20, 사용자 「적대적 검토를 통해서 1번 더 봐봐」): 적대 검토 둘(판정/검토_가이드_ontology_v49.json · 검토_가이드_graph_v49.json)의 지적 고침 — 설계 06 예가 원자료와 거꾸로였던 것, 식별자 · 카디널리티 풀이를 이론 정의로, MATCH를 이론 53 · 55장대로, 그래프 11 기준 지도 비교를 화면에 보이는 줄로, 없는 품번의 답 꼴을 04에서, 10 개수를 종류마다, 결정 표 네 칸, 결정 단계 정답 보기에 갈래 묻기 부탁, 승인 · 백틱 줄을 차례 목록 밖으로, 겹친 말 · 이름 섞임 정리.
# v49-lab(2026-11-20, 사용자 「목표 상황 말고 뭔가 이유라든지 지금 뭘 해야 되는지를 짧게 핵심만 … 두 줄 정도까지는 괜찮을 것 같은데」): 목표 칸을 「무엇을 하는지 + 왜 하는지」 두 문장까지로, 상황 칸에 있던 같은 까닭은 목표로 옮김.
# v48-lab(2026-11-20, 사용자 「말을 좀 더 쉽게 표현해보고 … 말을 좀 유먼을 해서 좀 다듬어줄 수 없나요??」): 목표 · 상황 · 뭐부터 · 확인의 모든 줄을 사람이 말하듯 쉬운 문장으로 윤문(칸과 차례는 그대로).
# v47-lab(2026-11-20, 사용자 「지금도 어려운데 그그냥 각 파일별로 어떠파일인지 설명 … 지금 목표강 ㅣ렇고 이런상황이다 뭐부터해야할까 라면서..」): 폴더 열기 단계에서 폴더 · 파일마다 무엇인지 한 줄씩(AGENTS.md는 「AI가 지킬 공통 규칙」 — 코딩랩 K-6), 단계마다 처음 나오는 파일은 상황 칸에서 한 마디로, 힌트 칸을 「뭐부터 해야 할까?」 차례 목록으로.
# v46-lab(2026-11-20, 사용자 「쉽게 가야한다.. 알지? 가이드 좀 어려운것가틍ㄴ데」): 힌트에서 코드 수준 이름(볼_열 · SET · $rows · $ 자리 · 돌려줄 열 · other_codes · note · 판단 함수)을 빼고 쉬운 말과 이론 이름(식별자 · 관계 방향 · 카디널리티 · MERGE · MATCH)만 — 코드 이름은 정답 보기에만.
# v45-lab(2026-11-20, 사용자 「계정이없으면.. 이런말이 왜있음..? 가정은 하지마」 · 「가이드에서 복사하라는말 x 알아서 가이드에서 제공할거임」): 계정이 없는 경우의 안내와 「복사해 붙여 넣는다」를 뺌.
# v44-lab(2026-11-20, 사용자 「지금 현재 목표 이렇고 상황 이렇고 힌트 이렇게 이런 거 이런 걸 해야 되겠다 … 그냥 하나의 문맥으로 탕 떄려넣지말고」 · 「결과 화면에 띄워」): 가이드 단계를 목표 · 상황 · 힌트 칸(session2_project_guides.plan)으로, 그래프 랩 비교 기능이 내 그래프 아래에 기준 지도 표를 띄움(제공 입력 data/reference_map.json — build_labs.portal_reference, 가이드의 기준 지도 표는 뺌).
# v43-lab(2026-11-20, 사용자 「(손으로 치면 오타가 납니다). 이런ㄱ말 codex가 가ㅣ드 정답까지 읽는다 는 등 다 x 넣지마」): 괄호 속 까닭(오타 · 바깥 폴더 · Docker · 재부팅)을 뺌.
# v42-lab(2026-11-20, 사용자 「작업지시 같은 말을 빼라고 그냥 딱 행위 설명만 있어야 있어라고 왜 자꾸 막 이상 쓸데없는 말을 다 더워 군더더기 다 빼고」): 단계는 할 행동 한두 문장 → 힌트(물음 하나와 단어 목록) → 명령 → 확인 한 줄만. 「지금 · 할 일 · 요령」 꼬리표, 요령의 까닭 문장(TIP_* — 까닭은 영상과 현장이 푼다), 힌트 속 작업 지시 문구를 뺌.
# v41-lab(2026-11-20, 사용자 「가이드는 이정표처ㅓㅁ 지금 이런 상황이고 이러 ㅇ리렇다 어떻게햐앟ㄹ가?」 · 「지금 이런이런거가지 알았다 그러면 ~~ 일떄에 어떻게행할까 -- OO -- OO … 정답을 단어형태로 알려주는건 좋은데 프롬포트 자체를 주면안됨」): 단계를 「지금(앞 단계까지 안 것과 상황) → 힌트(그러면 무엇을 물어보고 알아야 할까 + 단어 · 짧은 구 목록) → 요령 → 명령 → 확인」으로, 파악 단계에도 정답 보기(완성 부탁 글은 정답 보기에만).
# v40-lab(2026-11-20, 사용자 「코덱스 채팅에 붙여놓는 그 자체를 그냥 통으로 제공하는 이유가 뭐야 … 글이 너무 많다니까」 · 「현장에서 설명 및 영상에서 설명하는데 왜 가이드에도 설명을 풀로하나요 핵시만 있으면됨 여떻게해야하나 왜? (핵심만)」): 단계를 「왜 / 할 일 / 확인」으로, 본문의 Codex 붙여 넣기 블록을 빼고 부탁은 학생이 짠다(완성 부탁 글은 정답 보기에만 — 가이드 P-3 · P-4 · P-5).
# v39-lab(2026-11-20): v38 적대 검토 두 건(fable · 추론 중간 — 판정/검토_통합2_ontology_v38.json · graph_v38.json) 고침: 받기 문단에 안쪽 폴더를 열라고, 역량 질문은 Codex에 붙여 넣는 글 블록(F.block ask_ai)으로, 그래프 랩 정할 지점을 한 단계로 떼고 결정 요청 틀(decide_request), 볼_열 · 확인 문장 되살림, 명령마다 하는 일 한 구절과 Codex가 채운 파일을 열어 보는 자리, 같은 화면 · 물음 되풀이 뺌, 자기 모델 복사는 접힌 안내의 터미널 명령(학생 입력은 터미널과 Codex뿐).
# v38-lab(2026-11-20, 사용자 「가이드에 글이 너무 많은데..? 가이드의 원칙 모름?」): 가이드 P-5대로 단계 글을 핵심 설명 한두 줄 · Codex에게 부탁할 것 · 명령 블록 · 확인할 결과 화면으로 줄이고, 결과가 학생마다 같지 않아도 된다는 것을 첫 단계에 밝힘. 랩 폴더 · AGENTS.md는 v37과 같다.
# v37-lab(2026-11-20): v36 독립 검토 두 건(작업 폴더 판정/검토_통합2_ontology_v36.json · 검토_통합2_graph_v36.json) 고침 — Codex의 첫 파일 쓰기 단계로 승인 창 안내를 옮김,
#   역량 질문을 Codex에게 붙여 넣게 하고 정답 토글에 질문 문장을, 요령 「묻게 하기」를 첫 결정 자리로(TIP_ASK 문장도 「짐작」 되풀이를 피해 고침), Codex가 채운 design.csv · quantity_rules.py를 열어 역할 짚기,
#   그래프 10단계는 compare 명령을 먼저(Codex는 포털 표를 못 봄), 09단계 질문 3 기대 답도 Codex에게, 손으로 쓰는 것처럼 읽히는 문장 · 토글 속 단계 번호 · `$` 자리 풀이 · 새 대화 여는 법.
# v36-lab(2026-11-20, 사용자 「냉정하게 그냥 헌법, 입력데이터 및 입력 문서 … , 로직 끝아님?」 · 「학생은 오로직 입력은 터미널에서 실행 및 띄워보기, 그리고 바이브코딩 codex 챗엣만」):
#   랩 폴더에는 규칙(AGENTS.md) · 입력(data/) · 로직(app/) · 실행 파일만 둔다 — README.md · requirements.md · review.md · data/model/provenance.md를 뺐다(코드가 읽지 않는 사본 · 서류).
#   가이드는 학생 손으로 파일을 쓰게 하지 않고 Codex에게 적게 하며, 요령 셋(TIP_ASK · TIP_PROOF · TIP_FRESH)을 처음 쓰는 단계에 싣는다. AGENTS.md와 판단 칸은 v35와 같다(장난감 시험 다시 돌리지 않음 — 코딩랩 길 6).
# v35: 랩별 경계에 「권장안대로는 결정이 아니다」(장난감 시험 v34 two_turn)
# v32-lab — 2026-11-18: 독립 검토 두 건(판정/검토_통합2_ontology_v31.json · 검토_통합2_graph_v31.json) 고침 — 가이드 끝의 내 말로 되짚기, 기대 답을 결정 직후 · 구현 앞에, 역량 질문을 현장 값(설비 코드 · 품번)으로 묻기(식별자 틀과 무관), 같은 모델의 구성 요소 이름 맞추기는 제공 코드로(name_rules.py 뺌), 그래프 랩의 쿼리 짚어 보기와 장부의 이름. 앞 판 v31-lab: 설비 3대는 눈으로 다 읽혀 실습 랩 규모(코딩랩 K-3)보다 작아, 공장 규모에서 2라인 한일유압 설비 5대 · 모델 셋(현장 지시계 포함)을 골라 다시 만듦 — 정할 지점은 그대로, 이론 개편의 이름을 받고 요령의 까닭은 lab_frame TIP_*. 앞 판 v30-lab: 독립 검토(판정/검토_지침과_통합2회차.json) 고침 — 작업 2026-11-17_코딩랩-원리중심-학생결정자
WORK = ROOT / '작업/검사/session2-projects'


def write(path, text):
    F.write(path, text)


STRICT_OLD = """        if None in row and list(row)[-2:-1] == ['근거']:      # 맨 끝 「근거」 칸 글에 쉼표가 든 경우 — 남은 칸을 근거에 이어 붙인다
            row['근거'] = ','.join([row['근거'] or '', *row.pop(None)])
        if None in row:
            raise Stop(f'{rel(path)}:{line}: 칸 수가 열 이름보다 많습니다(쉼표가 든 값은 큰따옴표로 감쌉니다).')
"""
STRICT_NEW = """        if None in row:      # 넘친 칸을 끝 칸에 이어 붙이지 않는다 — 앞 칸에 쉼표가 든 줄은 값이 한 칸씩 밀린 채 조용히 지나간다
            raise Stop(f'{rel(path)}:{line}: 칸 수가 열 이름({len(reader.fieldnames)}칸)보다 많습니다 — 값 안에 쉼표가 있으면 그 값을 큰따옴표로 감싸거나 쉼표를 「 · 」로 바꿉니다.')
        if None in row.values():
            raise Stop(f'{rel(path)}:{line}: 칸 수가 열 이름({len(reader.fieldnames)}칸)보다 적습니다 — 빈 칸도 쉼표로 자리를 둡니다.')
"""


READ_OLD = """    data = Path(path).read_bytes()
    try:
        return data.decode('utf-8-sig'), 'UTF-8'
    except UnicodeDecodeError:
        return data.decode('cp949'), 'CP949'
"""
READ_NEW = """    data = Path(path).read_bytes()
    try:
        return data.decode('utf-8-sig'), 'UTF-8'
    except UnicodeDecodeError:      # 다른 글자표로 조용히 바꿔 읽지 않는다 — 그 줄을 짚고 멈춘다
        for n, line in enumerate(data.split(b'\\n'), 1):
            try:
                line.decode('utf-8')
            except UnicodeDecodeError:
                raise Stop(f'{rel(path)}:{n}: UTF-8로 저장되지 않은 글자가 있습니다 — Codex에게 「이 파일을 UTF-8로 다시 저장해 줘」라고 부탁합니다(한글이 다른 글자표로 저장됐습니다).')
        raise
"""


def result_sources(strict=False):
    """제공 결과 화면 코드(그리는 코드의 원본은 result_view.py, 그림 블록은 result_figures.py — 두 반 · 뒤 회차 새 구조 랩의 공용 자리).
    strict = 통합반 2회차 두 랩: 칸 수가 열 이름과 다른 CSV 줄을 파일:줄로 짚고 멈춘다(리허설 v32 — 코딩랩 「함정」의 틀 꼴 멈춤). 실전반 · 3회차 생성기는 기본값을 쓴다."""
    utilities, ui = P.result_sources()
    if strict:
        if utilities.count(STRICT_OLD) != 1:
            raise ValueError('결과 화면 코드의 CSV 읽기 꼴이 바뀌었습니다 — 칸 수 멈춤을 넣을 자리를 다시 봅니다.')
        utilities = utilities.replace(STRICT_OLD, STRICT_NEW)
        if utilities.count(READ_OLD) != 1:
            raise ValueError('결과 화면 코드의 파일 읽기 꼴이 바뀌었습니다 — UTF-8 멈춤을 넣을 자리를 다시 봅니다.')
        utilities = utilities.replace(READ_OLD, READ_NEW)
        said = '"""(글, 글자 방식). UTF-8(BOM 포함)로 읽고, 안 되면 CP949로 읽는다 — 어느 쪽으로 읽었는지 함께 돌려준다."""'
        if utilities.count(said) != 1:
            raise ValueError('결과 화면 코드의 read_text 설명이 바뀌었습니다.')
        utilities = utilities.replace(said, '"""(글, 글자 방식). UTF-8(BOM 포함)로만 읽는다 — 다른 글자표로 저장된 파일은 그 줄을 짚고 멈춘다."""')
    return utilities, ui


# 장난감 시험(2026-11-12) — AI가 결정 · 기대 답을 스스로 채우고, 기능 파일 여럿을 한꺼번에 짰다. 작업 경계만 둔다(형식은 강제하지 않음, 코딩랩 K-6).
DECISION_RULE = ('- `app/features/decisions.csv`의 고른_것 · 근거와 `app/features/expected.csv`의 기대 답에는 학생이 대화에서 정한 것만 적는다(학생이 보고 받아들인 근거 줄과 기대 답 후보도 된다). '
                 '학생이 정하지 않았으면 적지 않고, 정할 것을 선택지와 그 결과로 보여 묻는다.\n'
                 '- 한 번에 요청받은 기능 파일 하나만 고치고, 그 기능을 실행해 실제 결과를 보인 뒤 멈춘다. 랩 DB를 쓰는 기능은 랩 DB에서 실행한 결과로 확인한다.')   # 첫 줄을 두 과정 설계 랩의 경계(DESIGN_RULE)가 쓴다

# 장난감 시험(v34-lab two_turn, 2026-11-18): 「권장안대로 다 해 줘」에 AI가 decisions.csv 두 줄을 근거 칸에 학생 이유 없이 스스로 채우고 끝까지 실행했다.
# 코딩랩 K-3 「이유 없이 판단을 넘기는 부탁은 결정이 아니다」를 이 랩들의 파일 이름으로 적는다(통합반 두 랩만 — 실전반 바이트는 그대로).
NOT_DECIDED = ('- 「권장안대로」 · 「알아서」 · 「다 해 줘」처럼 갈래를 고르지 않거나 이유를 말하지 않은 부탁은 결정이 아니다. '
               '학생이 고를 갈래와 그렇게 고른 자기 이유를 말하기 전에는 `decisions.csv`의 그 줄을 쓰지 않고, 그 결정이 걸린 {files}도 만들거나 고치지 않는다. '
               '추천안을 냈더라도 학생이 그 추천을 받아들인다고 말하고 이유를 대야 결정이고, `decisions.csv`의 근거 칸에는 그 이유를 학생의 말로 적는다. '
               '그때까지는 무엇을 정해야 하는지와 선택지 · 각 선택의 결과를 쉬운 말로 다시 묻는다.')

# 한글 파일의 글자표(남은일 「코딩 랩 학생 역 리허설」 ② — Codex가 PowerShell로 읽고 쓰다 한글이 깨졌다). 제공 코드는 UTF-8이 아닌 파일을 파일:줄로 짚고 멈춘다.
UTF8_RULE = ('- 파일은 모두 UTF-8(BOM 없음)이다. 읽고 쓸 때 글자표를 UTF-8로 밝힌다 — PowerShell로 읽을 때는 `Get-Content -Encoding utf8 <파일>`, '
             '한글이 든 파일을 `>` · `Out-File` · `Set-Content`로 쓰지 않는다. 읽은 글의 한글이 깨져 보이면 그 내용으로 답하지 말고 UTF-8로 다시 읽는다.')

# 통합반 설계 랩의 랩별 경계 — 이 랩에는 랩 DB가 없고, 판단 함수 파일은 하나다. 표는 가이드가 한 요청에 둘셋을 맞추게 하므로 「요청받은 것만」으로 적는다(검토 지적, 코딩랩 K-6).
# 스키마 표 세 장도 학생이 고르기 전에는 쓰지 않는다(v58 검토 — 「표 다 채워 줘」에 식별자 · 필수 · 방향 · 카디널리티를 AI가 정했다).
DESIGN_RULE = (DECISION_RULE.split('\n')[0] + '\n'
               '- 스키마는 `app/features/`의 표 세 장(`classes.csv` · `properties.csv` · `relations.csv`)이고, 판단 함수 파일은 `quantity_rules.py` 하나다. 판단 함수는 요청받았을 때만 고치고, 그 기능을 실행해 실제 결과를 보인 뒤 멈춘다. '
               '표(스키마 표 세 장과 `row_rules.csv` · `expected.csv` · `decisions.csv`)는 요청받은 것만 고친다.\n'
               '- 스키마 표 세 장의 줄은 학생이 고른 뒤에 적는다. 표를 채워 달라는 부탁을 받으면 먼저 그 표에서 정할 것(`classes.csv`: 무엇을 클래스로 둘지 · 식별자를 무엇으로 지을지, '
               '`properties.csv`: 자료형 · 필수 여부 · 센서 값의 단위를 담는 법, `relations.csv`: 시작과 종료 · 카디널리티 · 적어도 하나)마다 선택지와 각 선택의 결과(그렇게 정하면 걸리는 원자료 줄과 개수), 추천을 보이고, '
               '학생이 고른 것과 이유를 말한 줄만 적는다(학생이 보고 받아들인다고 말한 줄도 된다). 근거 칸에는 학생이 말한 이유를 적는다. 「알아서 채워 줘」 · 「추천대로 다 해 줘」에는 표를 쓰지 않고 정할 것을 다시 묻는다.\n'
               '- 스키마 표에 줄을 처음 채울 때는 한 번에 한 장만 쓰고 멈춘다. 학생이 이미 정한 것에 맞춰 여러 표의 줄을 함께 고쳐 달라는 부탁은 그대로 한다.\n'
               '- `expected.csv`의 기대 답은 원자료에서 찾아 적고, 모델이나 결과 화면이 낸 답을 옮겨 적지 않는다. 결과가 기대 답과 다르면 기대 답을 고치기 전에 원인을 원자료 줄로 먼저 설명한다.\n'
               '- 모델은 `python run.py parts`가 `output/schema.json` · `output/graph.json`에 쓴다. 이 두 파일을 손으로 고치지 않는다.\n'
               + NOT_DECIDED.format(files='`quantity_rules.py`, `row_rules.csv`의 떼어 낸 펌프 줄, `classes.csv` · `properties.csv` · `relations.csv`의 실물 줄') + '\n' + UTF8_RULE)


# 리허설 07 막힘: Codex 샌드박스는 랩 DB(Docker)에 닿지 못해 AI가 실행을 시도하다 실패했다. 그래프 랩은 랩 DB 명령을 학생 터미널에 둔다.
GRAPH_DECISION_RULE = ('- `app/features/decisions.csv`의 고른_것 · 근거와 `app/features/expected.csv`의 기대 답에는 학생이 대화에서 정한 것만 적는다(학생이 보고 받아들인 근거 줄과 기대 답 후보도 된다). '
                       '학생이 정하지 않았으면 적지 않고, 정할 것을 선택지와 그 결과로 보여 묻는다.\n'
                       '- 한 번에 요청받은 기능 파일 하나만 고친 뒤 멈춘다. 랩 DB를 쓰는 명령(`python run.py` 기능)은 학생이 자기 터미널에서 실행하고, '
                       'AI는 학생이 붙여 준 터미널 출력과 결과 화면으로 확인한다. AI가 그 명령을 직접 실행하지 않는다.')   # 두 과정 그래프 랩의 경계(GRAPH_RULE)가 쓴다

# 통합반 그래프 랩의 랩별 경계 — 위 둘에 장난감 시험(v32-lab two_turn)에서 뚫린 두 틈을 막는 줄을 더한다(코딩랩 K-6 · 길 6).
GRAPH_RULE = (GRAPH_DECISION_RULE + '\n'
              '- `app/features/update.cypher`에서 불용 설비와 수정본의 「삭제」 줄(목록에서 빠진 센서)을 어떻게 할지는 `decisions.csv`의 「불용 결정 설비」 · 「목록에서 빠진 센서」 줄을 학생이 정한 뒤에만 쓴다. '
              '정하기 전에는 수정본의 다른 줄만 반영하고 그 처리는 쓰지 않으며, 무엇을 정해야 하는지 선택지와 결과로 묻는다.\n'
              '- 「다 해 줘」처럼 여러 기능을 한꺼번에 부탁받아도 기능 파일 하나를 고친 뒤 멈추고, 다음 기능을 할지 묻는다.\n'
              '- `app/features/load.cypher`에는 그 파일 첫머리에 적힌 쿼리 셋만 쓴다. 나머지 종류 · 관계는 제공 코드가 넣는다(`output/load_provided.cypher`는 실행할 때마다 다시 쓰이는 기록이라 고치지 않는다).\n'
              '- `app/features/schema_additions.csv`에는 스키마에 없던 속성을 그래프에 남기기로 학생이 정했을 때, 학생과 정한 속성만 적는다. `data/model/`의 모델 파일은 고치지 않는다.\n'
              '- `expected.csv`의 기대 답은 원자료와 모델 파일에서 찾아 적고, 쿼리 결과를 옮겨 적지 않는다. 결과가 기대 답과 다르면 기대 답을 고치기 전에 원인을 먼저 설명한다.\n'
              + NOT_DECIDED.format(files='`update.cypher`의 불용 설비 처리와 「삭제」 줄 처리, `schema_additions.csv`') + '\n' + UTF8_RULE)


def run_source():
    """제공 run.py — 실행이 확인 필요로 끝나도 직전에 성공한 결과를 지우지 않고, 이번 실패를 위에 · 직전 성공을 그 아래에 밝혀 보인다(리허설 07 막힘)."""
    BS = chr(92)
    text = P.RUN
    old = "    target.write_text(page(actions.TITLE, title, blocks), encoding='utf-8', newline='" + BS + "n')" + chr(10) + \
          "    (output / 'result.json').write_text(json.dumps({'action': args.action, 'blocks': blocks}, ensure_ascii=False, indent=2) + '" + BS + "n', encoding='utf-8')" + chr(10)
    new = ("    failed = any(b['kind'] == 'error' for b in blocks)" + chr(10) +
           "    saved = output / 'result.json'" + chr(10) +
           "    last = json.loads(saved.read_text(encoding='utf-8')).get('last_success') if saved.exists() else None" + chr(10) +
           "    if not failed:" + chr(10) +
           "        last = {'action': args.action, 'title': title, 'blocks': blocks}" + chr(10) +
           "    shown = blocks + ([results.note('아래는 직전에 성공한 「' + last['title'] + '」 실행의 결과입니다. 이번 실행은 위의 확인 필요로 끝났습니다.')] + last['blocks'] if failed and last else [])" + chr(10) +
           "    target.write_text(page(actions.TITLE, title, shown), encoding='utf-8', newline='" + BS + "n')" + chr(10) +
           "    saved.write_text(json.dumps({'action': args.action, 'blocks': blocks, 'last_success': last}, ensure_ascii=False, indent=2) + '" + BS + "n', encoding='utf-8')" + chr(10))
    if text.count(old) != 1:
        raise ValueError('run.py 원본의 결과 쓰기 줄을 찾지 못했습니다.')
    return text.replace(old, new)


def source_data(folder, practical=False):
    work = (ROOT / '작업/검사/session2-projects').resolve()
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work, prefix='data-') as temp:
        raw = Path(temp).resolve()
        assert raw.is_relative_to(work) and raw != work
        D.write_sources(raw, practical)
        for path in raw.iterdir():
            write(folder / 'data' / P.NAMES[path.name], P.convert(path.read_text(encoding='utf-8-sig')))


CHECK_MORE = [
    ("'list':k=='list'}.get(spec)",
     "'list':k=='list','date':k=='string' and len(value)==10 and value[4]==value[7]=='-' and value.replace('-','').isdigit()}.get(spec)"),
    (B.CHECK_ANCHOR,      # 「적어도 하나」 — 스키마가 적은 쪽(from · to)의 인스턴스마다 이 관계가 하나는 있어야 한다
     "    for t,spec in relations.items():\n"
     "        least=spec.get('at_least_one') if isinstance(spec,dict) else None\n"
     "        for side in (least if isinstance(least,list) else []):\n"
     "            mine=spec.get(side);mine=mine if isinstance(mine,list) else [mine]\n"
     "            has={r.get('a' if side=='from' else 'b') for r in rels if r.get('type')==t}\n"
     "            lone=sorted(i for i,labs in labels_by_id.items() if any(x in mine for x in labs) and i not in has)\n"
     "            if lone:errors.append(f'{t} 적어도 하나 어긋남: 이 관계가 하나도 없는 {\"/\".join(map(str,mine))} {len(lone)}개 — '+', '.join(lone[:5])+(' …' if len(lone)>5 else ''))\n"
     + B.CHECK_ANCHOR),
    # 스키마에 없는 속성은 참고가 아니라 어긋남이다 — 스키마에 자리를 먼저 정한 뒤에 넣는다. 목록 속성에 같은 값이 두 번 든 것도 어긋남이다
    ("                if key in opt:check_value(f'{lab} {id}',key,v,opt[key])\n"
     "                else:warnings.append(f'{lab}에 정의되지 않은 속성 {key} ({id})')\n",
     "                if key in opt:check_value(f'{lab} {id}',key,v,opt[key])\n"
     "                else:errors.append(f'{lab} {id}: 스키마에 정의되지 않은 속성 {key}')\n"
     "            for key,v in props.items():\n"
     "                if isinstance(v,list) and len(set(map(str,v)))!=len(v):errors.append(f'{lab} {id}: 목록 속성 {key}에 같은 값이 두 번 — '+' · '.join(map(str,v)))\n"),
    ("            elif k!='id':warnings.append(f'{t}에 정의되지 않은 속성 {k}')\n",
     "            elif k!='id':errors.append(f'{t} {a}→{b}: 스키마에 정의되지 않은 속성 {k}')\n")]


LATER_POINT = '''_table = _root / 'app/features/classes.csv'
if not (_table.is_file() and any(x.startswith({kind!r}) for x in _table.read_text(encoding='utf-8-sig', errors='replace').splitlines())):
    _pre = [e for e in _pre if {mark!r} not in e]      # 아직 쓰지 않는 결정 지점의 빈 줄은 그 클래스를 클래스 표에 적은 뒤부터 본다
'''


def checker(folder, L, later=None):
    """later = (지점 이름, 클래스 이름) — 그 클래스를 클래스 표에 적기 전에는 그 지점 줄이 비어 있어도 걸지 않는다(실전반 설계 랩: 끝의 응용에서 정하는 결정)."""
    provided =[p.relative_to(folder).as_posix() for p in student_files(folder)
                if p.relative_to(folder).as_posix().startswith(('app/ui/', 'app/utils/')) or p.name == 'run.py']
    guard = F.provided_guard(folder, provided)
    chosen = P.convert(F.CHOSEN_CHECK)
    head = ('from pathlib import Path\nimport sys\n\n' + F.UTF8_OUT + guard + chosen +
            '_root = Path(__file__).resolve().parents[2]\n_pre = provided_errors(_root) + chosen_errors(_root)\n')
    if later:
        head += LATER_POINT.format(kind=later[1] + ',', mark=f'(지점 「{later[0]}」)')
    body = P.convert(B.CHECKER).replace('Path(__file__).resolve().parent', 'Path(__file__).resolve().parents[2]')
    body = body.replace("root/'app/features'", "root/'output'")
    body = body.replace('가이드 「결과 형식」의 모양으로 만든 뒤 다시 실행하세요.', 'python run.py parts로 모델을 생성한 뒤 다시 실행하세요.')
    body = body.replace('(가이드 결과 형식 참고)', '')
    body = body.replace('if errors:\n', 'errors = _pre + errors\nif errors:\n')
    for old, new in CHECK_MORE:      # 통합반 2회차 두 랩: 날짜 자료형과 「끝이 적어도 하나」(설계 랩의 스키마가 이 둘을 적는다)
        if body.count(old) != 1:
            raise ValueError('구조 검사기 원본이 바뀌었습니다 — 덧댈 자리를 다시 봅니다: ' + old[:40])
        body = body.replace(old, new)
    if L['kind'].startswith('graph'):
        body = body.replace('python run.py parts로 모델을 생성', 'python run.py export로 그래프를 저장')
    return head + body


def build_ontology(folder, course='통합반'):
    D.require(course)
    practical = course == '실전반'
    if practical:
        import session2_factory as X
        import session2_factory_lab as XL
    L = XL.design_lab() if practical else B.design_integrated()
    source_data(folder, practical)
    write(folder / 'data/relationships.json', trunk_drawing())
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            write(folder / P.convert(name), P.convert(text))
    utilities, ui = result_sources(strict=True)
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/model.py', P.model_source(X.tool_source() if practical else None))
    actions = P.actions_source(L) + (P.convert(XL.SUPPLY_ACTIONS) if practical else '')
    commands = {'sources': ('원자료', 'sources'), 'expected': ('기대 답', 'expected'),
                'classes': ('클래스와 식별자', 'classes'), 'properties': ('속성과 자료형', 'properties'), 'relations': ('관계와 카디널리티', 'relations'),
                'names': ('구성 요소 이름과 실물', 'names'),
                'quantities': ('물리량과 센서', 'sensors'),
                'parts': ('부품과 모델', 'parts'), 'query': ('질문별 대조', 'ask'), 'check': ('넣기 전 검증', 'check'), **(XL.SUPPLY_COMMANDS if practical else {})}
    actions += '\nCOMMANDS = {\n' + ''.join(f'    {cmd!r}: ({label!r}, {fn}),\n' for cmd, (label, fn) in commands.items()) + '}\n'
    write(folder / 'app/utils/actions.py', actions)
    write(folder / 'run.py', run_source())
    write(folder / 'app/utils/check.py', checker(folder, L, (X.SUPPLY_POINT, '견적') if practical else None))
    purpose = XL.PURPOSE if practical else G.ONTOLOGY_PURPOSE
    write_metadata(folder, L['title'], purpose, extra_rules=XL.design_rule(DESIGN_RULE) if practical else DESIGN_RULE, readme_file=False)
    steps = XL.ontology_guide() if practical else G.ontology()
    F.write_guide(folder, G.render(L['title'], purpose, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps


def trunk_drawing():
    """출발 그림 — 1회차 관계 그림 실습의 끝 그림(session2_relationships.json)에서 설비 · 구성 요소 · 센서 줄기만 남긴다.
    증상 · 고장 유형 · 원인 · 조치 방법 · 매뉴얼 절은 이 랩이 다루지 않는 대상이라 랩 자료에 넣지 않는다(코딩랩 K-3 — 그 회차 원리와 상관없는 덩어리)."""
    whole = json.loads(Path(__file__).with_name('session2_relationships.json').read_text(encoding='utf-8-sig'))
    keep = {n['id'] for n in whole['nodes'] if set(n.get('labels', [])) & {'Asset', 'Component', 'Sensor'}}
    if len(keep) != 3:
        raise ValueError(f'출발 그림의 설비 · 구성 요소 · 센서 노드가 {len(keep)}개 — 줄기를 다시 봅니다.')
    whole['nodes'] = [n for n in whole['nodes'] if n['id'] in keep]
    whole['relationships'] = [r for r in whole['relationships'] if r['fromId'] in keep and r['toId'] in keep]
    return json.dumps(whole, ensure_ascii=False, indent=2) + '\n'


def design_model(branch, ids=None, course='통합반', supply=None):
    """설계 랩 강사 참조 그 갈래(둘째 바퀴까지 마친 판)를 설계 랩 제공 코드(session2_model_tool)로 돌려 얻은 (스키마, 인스턴스 데이터).
    그래프 랩의 제공 모델(data/model)이 이것이다 — 설계 랩의 output/과 꼴 · 식별자가 같아, 내 모델을 가져다 써도 같은 길로 돈다(코딩랩 K-9).
    course='실전반'이면 공장 규모 자료와 공장 규모 판 제공 코드(session2_factory)로 만들고, supply = 구매팀 응용의 셋째 결정 갈래(공급사 · 견적까지 담은 모델)."""
    import importlib.util
    import session2_answers as A
    D.require(course)
    if course == '실전반':
        import session2_factory as X
        import session2_factory_answers as FA
        with tempfile.TemporaryDirectory(dir=WORK, prefix='model-') as temp:
            root = Path(temp).resolve()
            assert root.is_relative_to(WORK.resolve()) and root != WORK.resolve()
            D.write_sources(root / '자료', True)
            files = FA.design(branch, supply, lap=True)
            files['결과/정한_것.csv'] = B.chosen_text(FA.chosen(branch, supply))
            for name, text in files.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text, encoding='utf-8', newline='\n')
            info, model = X.tool_module(root).build('부품', write=False)
            if info['어긋남']:
                raise ValueError(f'제공 모델을 만들 참조 갈래 {branch} · {supply}가 원자료와 어긋납니다: ' + str(info['어긋남'][:3]))
            return json.loads(json.dumps(model, ensure_ascii=False))
    with tempfile.TemporaryDirectory(dir=WORK, prefix='model-') as temp:
        root = Path(temp).resolve()
        assert root.is_relative_to(WORK.resolve()) and root != WORK.resolve()
        D.write_sources(root / '자료')
        files = A.integrated_design(branch, ids=ids, lap=True)
        files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen(branch))
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding='utf-8', newline='\n')
        spec = importlib.util.spec_from_file_location('design_tool_for_provided_model', Path(__file__).with_name('session2_model_tool.py'))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        tool.HERE, tool.DATA, tool.OUT = root, root / '자료', root / '결과'
        info, model = tool.build('부품', write=False)
        if info['어긋남'] or info['못_찾은_칸']:
            raise ValueError(f'제공 모델을 만들 참조 갈래 {branch}가 원자료와 어긋납니다: ' + str((info['어긋남'] or info['못_찾은_칸'])[:3]))
        return json.loads(json.dumps(model, ensure_ascii=False))


def build_graph(folder, course='통합반'):
    D.require(course)
    practical = course == '실전반'
    if practical:
        import session2_factory_answers as FA
        import session2_factory_graph as XG
    L = XG.graph_lab() if practical else B.graph_lab('통합반')
    source_data(folder, practical)
    schema, graph = design_model(B.GRAPH_LAB_INPUT['통합반'], course=course, supply=FA.PROVIDED_SUPPLY if practical else None)
    schema, graph = (json.loads(P.convert(json.dumps(x, ensure_ascii=False))) for x in (schema, graph))      # 출처 줄(자료/공급_조건.csv:2 꼴)을 이 폴더의 파일 이름으로 — 설계 랩이 output/에 쓰는 것과 같은 글
    for name, value in [('schema.json', schema), ('graph.json', graph)]:
        write(folder / 'data/model' / name, json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            if name == '결과/기대_답.csv':
                text = text.replace('값이 없으면(원자료에 없는 품번 · 빈 값) 「없음」',
                                    '쿼리 결과가 0행이면 「0줄」, 반환된 행의 빈 칸은 「없음」. 없는 품번을 설명하는 행을 반환하면 그 설명을 그대로 적음')
                if '쿼리 결과가 0행이면' not in text:
                    raise ValueError('그래프 랩 기대 답 틀의 값 꼴 문장이 바뀌었습니다.')
            write(folder / P.convert(name), P.convert(text).replace('python show_result.py가 실행', 'python run.py load가 실행'))
    with tempfile.TemporaryDirectory(dir=WORK, prefix='changes-') as temp:
        raw = Path(temp).resolve()
        assert raw.is_relative_to(WORK.resolve()) and raw != WORK.resolve()
        D.write_changes(raw)
        for path in raw.iterdir():
            name = 'notes.md' if path.name == 'README.md' else P.NAMES[path.name]
            text = P.convert(path.read_text(encoding='utf-8-sig')).replace('`../data/`', '`data/`')
            write(folder / 'data/changes' / D.CHANGE_DATE / name, text)
    utilities, ui = result_sources(strict=True)
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/db.py', GP.db_source(constraints_first=True))
    cypher, actions = GP.cypher_source(integrated=True), GP.actions_source(L)
    write(folder / 'app/utils/cypher.py', XG.cypher_source(cypher) if practical else cypher)
    write(folder / 'app/utils/actions.py', XG.actions_source(actions) if practical else actions)
    write(folder / 'run.py', run_source())
    write(folder / 'app/utils/check.py', checker(folder, L))
    purpose = XG.purpose() if practical else G.GRAPH_PURPOSE
    write_metadata(folder, L['title'], purpose, extra_rules=(XG.graph_rule(GRAPH_RULE) if practical else GRAPH_RULE) + '\n' + DB_RULE, readme_file=False)
    steps = XG.graph_guide(graph) if practical else G.graph()
    F.write_guide(folder, G.render(L['title'], purpose, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps


def validate(folder, L, steps, course='통합반'):
    issues = errors({p.relative_to(folder).as_posix(): p.read_bytes() for p in student_files(folder)}, folder.name)
    if issues:
        raise ValueError(issues)
    pack(folder)
    item = entry(COURSES[course]['prefix'] + '-02-' + folder.name.removesuffix('-lab'), course, '온라인 02회차', L['title'], (COURSES[course]['versions'] or VERSIONS)[folder.name], folder,
                 guide_steps=[s['name'] for s in steps])
    from verify_packages import check_zip, verify_lab
    assert not check_zip(folder.with_suffix('.zip'), folder)[0]
    verify_lab(item)
    return item


def replace_generated(source, target, dest=DEST):
    """검사가 끝난 이 생성기의 프로젝트 하나만 정본에 반영한다."""
    target = target.resolve()
    if target.parent != dest.resolve() or target.name != source.name or target.name not in ('ontology-lab', 'graph-lab'):
        raise ValueError('지정한 통합02 프로젝트 밖에는 반영하지 않습니다.')
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    for suffix in ('_guide.html', '.zip'):
        shutil.copyfile(source.parent / (source.name + suffix), target.parent / (target.name + suffix))


def completed_expected(branch):
    """설계 랩 완성본의 기대 답 — 그 갈래의 기대 답에서 구성 요소 이름을 빈 틀 머리대로 그 설비의 원자료에 적힌 이름으로 적고, 둘째 바퀴의 질문 4 한 줄을 더한다."""
    import csv, io
    import session2_answers as A
    (_, _, removed), = A.removed_rows()
    canon = B.CANON_NAME[D.REMOVED_PUMP[1]] + ' 실물'
    text = B.expect_design_text(branch)
    if text.count(',' + canon + ',') != 1:
        raise ValueError(f'기대 답에서 「{canon}」 줄을 하나로 찾지 못했습니다.')
    buf = io.StringIO()
    csv.writer(buf, lineterminator='\n').writerow(A.lap_question())
    return text.replace(',' + canon + ',', ',' + removed['구성요소'] + ' 실물,') + buf.getvalue()


def completed(starter, destination, work, course='통합반'):
    """학생용 완성본은 별도 묶음이며 시작 ZIP에 넣지 않는다. 유료 AI 호출 없음."""
    import session2_answers as A
    folder = work / 'completed' / starter.name
    shutil.copytree(starter, folder)
    if starter.name == 'ontology-lab' and course == '실전반':      # 완성본은 가이드의 끝 상태 — 둘째 바퀴와 구매팀 응용까지
        import session2_factory_answers as FA
        import session2_factory_lab as XL
        branch, supply = B.GRAPH_LAB_INPUT['통합반'], FA.PROVIDED_SUPPLY      # 완성본은 다음 랩(그래프)의 제공 모델과 같은 판단
        files = FA.design(branch, supply)
        files['결과/정한_것.csv'] = B.chosen_text(FA.chosen(branch, supply))
        files['결과/기대_답.csv'] = FA.expect_text(branch, supply)
        for name, text in files.items():
            write(folder / P.convert(name), P.convert(text))
        title, initial = '온톨로지 설계', 'python run.py supply\npython run.py query\npython run.py purchase'
        context, actions, rules = nullcontext(), ('supply', 'check', 'query', 'purchase'), XL.design_rule(DESIGN_RULE)
    elif starter.name == 'ontology-lab':
        branch = B.GRAPH_LAB_INPUT['통합반']    # 완성본은 다음 랩(그래프)의 제공 모델과 같은 판단
        files = A.integrated_design(branch, lap=True)      # 완성본은 가이드의 끝 상태 — 둘째 바퀴(질문 4)까지
        files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen(branch))
        files['결과/기대_답.csv'] = completed_expected(branch)
        for name, text in files.items():
            write(folder / P.convert(name), P.convert(text))
        title, initial = '온톨로지 설계', 'python run.py parts\npython run.py query'
        context, actions, rules = nullcontext(), ('parts', 'check', 'query'), DESIGN_RULE
    else:
        if course == '실전반':
            import session2_factory_graph as XG
            from reference.practical2_graph_trials import fill, finish, instance
        else:
            from reference.session2_graph_trials import fill, finish, instance
        fill(folder)
        finish(folder, '남김')     # 완성본은 수정본까지 반영한 상태라 기대 답과 질문 1 쿼리도 그 뒤의 것이다
        target = folder / 'app/features/expected.csv'   # 칸 뜻 머리는 학생 빈 틀과 같은 줄을 쓴다(v36 검토 — 강사 참조의 머리는 「0줄」 꼴을 모른다)
        head = (starter / 'app/features/expected.csv').read_text(encoding='utf-8').split('\n', 1)[0]
        target.write_text(head + '\n' + target.read_text(encoding='utf-8').split('\n', 1)[1], encoding='utf-8', newline='')
        title, initial = '그래프 구현과 검증', 'python run.py db\npython run.py constraints\npython run.py load\npython run.py update\npython run.py usage'
        context, actions, rules = instance(folder), ('constraints', 'probe', 'load', 'repeat', 'changes', 'update', 'repeat', 'sensors', 'parts', 'usage', 'export', 'check'), GRAPH_RULE + '\n' + DB_RULE
        if course == '실전반':      # 완성본은 가이드의 끝 상태 — 구매팀 응용(관계 넣기 · 질문 4)까지
            initial += '\npython run.py purchase'
            actions, rules = (*actions[:-2], 'supply', 'purchase', 'export', 'check'), XG.graph_rule(GRAPH_RULE) + '\n' + DB_RULE
    write_metadata(folder, title + ' · 완성본',
                   'AI 계정이 없거나 구현 중 막혔을 때 실행해 보는 묶음입니다. 판단마다 갈래 하나를 골라 적용했으며 선택과 근거는 app/features/decisions.csv에 있습니다.'
                   + (' Docker Desktop을 켠 뒤 실행합니다.' if starter.name == 'graph-lab' else ''), command=initial, extra_rules=rules, readme_file=False)   # 완성본을 Codex로 열어도 같은 랩별 경계
    logs = {}
    with context:
        for action in actions:
            run = subprocess.run([sys.executable, 'run.py', action, '--no-open'], cwd=folder,
                                 capture_output=True, text=True, encoding='utf-8')
            logs[action] = run.stdout + run.stderr
            if run.returncode:
                raise RuntimeError(logs[action])
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (starter.name + '-completed.zip')
    write_zip(archive, [(starter.name + '/' + p.relative_to(folder).as_posix(), p.read_bytes()) for p in student_files(folder)])
    write(work / 'completed-execution.json', json.dumps(logs, ensure_ascii=False, indent=2) + '\n')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lab', choices=['ontology', 'graph'])
    dest = parser.add_mutually_exclusive_group(required=True)
    dest.add_argument('--dest', type=Path, help='작업/ 아래 새 검증용 부모 폴더; 목록은 등록하지 않음')
    dest.add_argument('--apply', action='store_true', help='검증 사본을 만든 뒤 지정한 통합02 랩만 교체')
    parser.add_argument('--completed', action='store_true', help='별도 학생용 완성본도 실제 실행해 생성')
    parser.add_argument('--course', choices=list(COURSES), default='통합반', help='실전반 = 같은 랩에 공장 규모 자료와 끝의 구매팀 응용')
    args = parser.parse_args()
    build = (lambda folder: build_ontology(folder, args.course)) if args.lab == 'ontology' else (lambda folder: build_graph(folder, args.course))
    WORK.mkdir(parents=True, exist_ok=True)
    with D.for_course(args.course):
        generate(parser, args, build)


def generate(parser, args, build):
    if args.dest:
        parent = args.dest.resolve()
        if not parent.is_relative_to((ROOT / '작업').resolve()):
            parser.error('--dest는 저장소 작업/ 아래 새 폴더입니다.')
        folder = parent / (args.lab + '-lab')
        if folder.exists():
            parser.error('검증 폴더가 있습니다. 다른 --dest를 사용합니다.')
        L, steps = build(folder)
        validate(folder, L, steps, args.course)
        if args.completed:
            completed(folder, parent, parent, args.course)
    else:
        with tempfile.TemporaryDirectory(dir=WORK, prefix='publish-') as temp:
            work = Path(temp).resolve()
            assert work.is_relative_to(WORK.resolve()) and work != WORK.resolve()
            source = work / (args.lab + '-lab')
            dest = COURSES[args.course]['dest']
            L, steps = build(source)
            validate(source, L, steps, args.course)
            archive = completed(source, work, work, args.course) if args.completed else None
            folder = dest / source.name
            replace_generated(source, folder, dest)
            register([validate(folder, L, steps, args.course)])
            if archive:
                target = dest.parent / '완성본' / archive.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(archive, target)
                shutil.copyfile(work / 'completed-execution.json', WORK / (('practical-' if args.course == '실전반' else '') + args.lab + '-completed-execution.json'))
    print(folder)


if __name__ == '__main__':
    main()
