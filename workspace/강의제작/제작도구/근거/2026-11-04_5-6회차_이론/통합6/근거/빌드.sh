# 통합반 6회차 재편 한 바퀴: 덱 → 대본 → PPTX → 구성표 → 대본 표 → 검사(렌더 없음)
set -e
cd "$(dirname "$0")/../../../.."
W=작업/2026-11-04_5-6회차-이론/통합6
DECK=workspace/강의제작/제작도구/온라인/decks/integrated/day06/통합반_06일차.md
S=workspace/강의제작/산출물/통합반/이론/06회차
C=workspace/강의제작/제작도구/구성/통합반/06회차
python3 $W/근거/재편_덱.py
python3 $W/근거/재편_대본.py
python3 .claude/skills/hyd-course-deck/scripts/deck2pptx.py $DECK $S/통합반_06일차.pptx | tail -1
python3 workspace/강의제작/제작도구/구성/구성표.py $C/구성.json
python3 $W/근거/재편_대본.py $C/구성표.md
python3 workspace/강의제작/제작도구/구성/구성표.py $C/구성.json
python3 workspace/강의제작/제작도구/기존제작/tools/deck/대본시간.py $S/대본/*.md > $W/근거/시간_변경후.txt
python3 $W/근거/행시간.py $W/근거/시간_변경후.txt
python3 .claude/skills/hyd-course-deck/scripts/deck2pptx.py --check $DECK > $W/근거/check.out 2>&1; echo "rc=$?" >> $W/근거/check.out
rm -rf $W/dry; mkdir -p $W/dry; python3 workspace/강의제작/제작도구/기존제작/tools/video/강의영상.py $W/dry $S/대본/*.md --dry > $W/근거/dry.out 2>&1; echo "rc=$?" >> $W/근거/dry.out; cp $W/근거/dry.out $W/dry/
cat $W/근거/check.out $W/근거/dry.out
