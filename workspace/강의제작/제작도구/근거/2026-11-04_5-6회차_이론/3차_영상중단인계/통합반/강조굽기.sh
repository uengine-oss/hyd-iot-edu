#!/usr/bin/env bash
# 굽기가 다 끝나기를 기다렸다가(인자 1 = 굽기 줄의 PID) 편마다 검사 셋(말머리 잘림 · 장넘김 · 자막 대조)과 강조 전편을 차례로 한다(동시 1편).
cd /home/user/hyd-iot-edu
while kill -0 "$1" 2>/dev/null; do sleep 15; done; shift
export EMPH_FONT=/usr/share/fonts/malgun/MALGUNBD.TTF
W=작업/2026-11-04_5-6회차-렌더-음성; V=workspace/강의제작/제작도구/기존제작/tools/video; S=workspace/강의제작/산출물/통합반/이론; D=$W/영상/통합반; G=workspace/강의제작/제작도구/구성/통합반
for k in "$@"; do
  r=${k%_*}; p=${k#*_}; sc=$(ls $S/${r}회차/대본/${p}_*.md); o=$W/영상출력/통합반_${r}회차_${p}
  n=$(basename $(ls $o/영상/*.mp4) .mp4); t=$o/_작업/영상_자막_기록
  { echo "== $n"; python3 $V/검사/말머리_잘림.py $o/영상/$n.mp4; python3 $V/검사/장넘김_싱크.py $o/영상/$n.mp4 $t/${n}_시간표.md | tail -1
    python3 $D/도구/자막대조.py $sc $t/$n.srt; python3 $D/도구/강조검사.py $o/영상/$n.mp4 $G/${r}회차/강조_$n.json; } > $o/검사.txt 2>&1
  echo "$(date +%T) 검사 끝 $n" >> $D/굽기_진행.txt
  mkdir -p $o/강조 $o/확인
  python3 $V/강조표시.py $o/영상/$n.mp4 $G/${r}회차/강조_$n.json $o/강조/$n.mp4 --확인 $o/확인 > $o/강조.log 2>&1
  echo "$(date +%T) 강조 끝 $n 종료=$? $(tail -1 $o/강조.log)" >> $D/굽기_진행.txt
done
