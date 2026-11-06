#!/usr/bin/env bash
cd /home/user/hyd-iot-edu
O=/home/user/hyd-iot-edu/작업/검사/toy4
K=/root/.claude/uploads/476059fc-242d-55b3-911f-45e453197017/001cc594-gnu-class-key.txt
C=/tmp/claude-0/-home-user-hyd-iot-edu/476059fc-242d-55b3-911f-45e453197017/scratchpad/codex/node_modules/.bin/codex
run() { python3 workspace/강의제작/제작도구/실습시작/reference/ai_toy_test.py "$1" --tool $2 --scenario $3 --out $O/$4 --env-file $K $5 --codex-bin $C > $O/$4.runner.log 2>&1; echo "exit=$?" >> $O/$4.runner.log; }
P=$PWD/workspace/강의제작/산출물
E2=$P/통합반/실습/04회차/랩/04일차_실습2_문서지식추출.zip; E4=$P/실전반/실습/03회차/랩/03일차_실습4_지식추출.zip
G3=$P/통합반/실습/04회차/랩/04일차_실습3_그래프반영과검증.zip; G5=$P/실전반/실습/03회차/랩/03일차_실습5_그래프반영.zip
# 1차: 추출 랩 키 있는 꼴 8
for t in codex claude; do for sc in two_turn one_turn; do run $E2 $t $sc d4k2_int42_${t}_${sc} "--lab-env $K" & run $E4 $t $sc d4k2_pra34_${t}_${sc} "--lab-env $K" & done; done; wait
# 2차: 그래프 랩 8 + 추출 랩 키 없는 루나 2
for t in codex claude; do for sc in two_turn one_turn; do run $G3 $t $sc d4v2_int43_${t}_${sc} "" & run $G5 $t $sc d4v2_pra35_${t}_${sc} "" & done; done
for sc in two_turn one_turn; do run $E2 codex $sc d4v2_int42_codex_${sc} "" & done; wait
echo ALLDONE > $O/ALLDONE_v2
