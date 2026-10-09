#!/bin/bash
# 시드 두 판(확정 TODO C1 · 결정 6) — seed.sh가 source 한다. 같은 규칙의 파이썬 구현은 scripts/ontology_v2.py edition_filter이고,
# tests/test_seed_editions.py가 두 구현의 출력이 같은지 대조한다.
#
#   SEED_EDITION=structure  수업용 구조판: 설비 구조 · 역할/조직/시스템 · BSC · 감시 패턴 · 회사 규정 · 순위 정책.
#                           고장 · 원인 · 증거 · 조치(SOP) · 매뉴얼 규칙 · 예측 · 선례는 넣지 않는다 — 학생이 문서를 적재해 만든다.
#   SEED_EDITION=full       회귀용 전체판: 지금까지의 시드 그대로(회귀 · 통합 시험이 기대는 시드 스킬 · 규칙 · 선례 포함).
#
# 표시 규칙: 시드 파일에서 "// @edition full" 또는 "// @edition structure" 줄 바로 뒤의 문장(다음 주석 아닌 줄부터 ';'로 끝나는 줄까지)은
# 그 판에서만 실행한다. 표시가 없는 문장은 두 판 모두에서 실행한다. 되읽기 검사 파일(seed_checks.cypher)에서는 표시 바로 뒤의 질의 한 줄에만 적용한다.

seed_edition_filter() {   # $1 = edition, $2 = file → 그 판의 cypher를 stdout으로
  local edition="$1" file="$2" pending="" active="" keep=1 line trimmed
  while IFS= read -r line || [ -n "$line" ]; do
    trimmed="${line#"${line%%[![:space:]]*}"}"
    if [ -z "$active" ]; then
      case "$trimmed" in
        "// @edition full"|"// @edition structure") pending="${trimmed#// @edition }"; continue;;
        //*|"") printf '%s\n' "$line"; continue;;
      esac
      if [ -n "$pending" ]; then
        active=1
        if [ "$pending" = "$edition" ]; then keep=1; else keep=0; fi
        pending=""
      else
        active=1; keep=1
      fi
    else
      case "$trimmed" in //*) [ "$keep" = 1 ] && printf '%s\n' "$line"; continue;; esac
    fi
    [ "$keep" = 1 ] && printf '%s\n' "$line"
    local stripped="${line%"${line##*[![:space:]]}"}"
    case "$stripped" in *';') active=""; keep=1;; esac
  done < "$file"
}

seed_edition_checks() {   # $1 = edition, $2 = seed_checks.cypher → 이 판에서 실행할 질의 줄들
  local edition="$1" file="$2" want="" line
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "// @edition full"|"// @edition structure") want="${line#// @edition }"; continue;;
      ''|//*) continue;;
    esac
    if [ -z "$want" ] || [ "$want" = "$edition" ]; then printf '%s\n' "$line"; fi
    want=""
  done < "$file"
}
