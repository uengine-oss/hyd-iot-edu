#!/usr/bin/env bash
# A113 — clone the reference repos that HYD's parts follow, at their latest HEAD, and build a CodeGraph index for each,
# so a reviewer can follow entry → data flow → storage → UI with codegraph instead of keyword grep.
#   bash scripts/refs_latest.sh            (writes .evidence/reaudit/references-latest/<repo>, git-ignored)
# A repo already cloned is fetched to the latest HEAD instead. heads.tsv records name / sha / date / subject.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=.evidence/reaudit/references-latest
mkdir -p "$OUT"
REPOS=(
  process-gpt process-gpt-vue3 process-gpt-completion process-gpt-agent-sdk process-gpt-infra-docker
  process-gpt-deepagents process-gpt-codex process-gpt-cli-agent cliagents
  process-gpt-memento process-gpt-bpmn-extractor process-gpt-mcp-validator process-gpt-strategy
  ontology-studio ontologic bpmn-process-generation-skill process-gpt-docs.github.io process-gpt-sample-app-wms
  process-gpt-agent-utils process-gpt-llm-factory process-gpt-analytic process-gpt-glossary
  robo-data-catalog neo4j-text2sql
)
fetch_one() {
  local name="$1" dir="$OUT/$1"
  if [ -d "$dir/.git" ]; then
    git -C "$dir" fetch -q --depth 1 origin HEAD && git -C "$dir" reset -q --hard FETCH_HEAD
  else
    git clone -q --depth 1 "https://github.com/uengine-oss/$name.git" "$dir"
  fi || { echo "CLONE-FAIL $name"; return 1; }
  echo "CLONED $name $(git -C "$dir" log -1 --format='%h %ad' --date=short)"
}
export -f fetch_one; export OUT
printf '%s\n' "${REPOS[@]}" | xargs -P 6 -I{} bash -c 'fetch_one "$@"' _ {}
: > "$OUT/heads.tsv"
for n in "${REPOS[@]}"; do
  [ -d "$OUT/$n/.git" ] && printf '%s\t%s\n' "$n" "$(git -C "$OUT/$n" log -1 --format='%H%x09%ad%x09%s' --date=short)" >> "$OUT/heads.tsv"
done
echo "== index"
for n in "${REPOS[@]}"; do
  d="$OUT/$n"; [ -d "$d" ] || continue
  if [ -d "$d/.codegraph" ]; then codegraph sync "$d" >/dev/null 2>&1 && echo "SYNCED $n" || echo "SYNC-FAIL $n"
  else codegraph init "$d" >/dev/null 2>&1 && echo "INDEXED $n" || echo "INDEX-FAIL $n"; fi
done
echo DONE
