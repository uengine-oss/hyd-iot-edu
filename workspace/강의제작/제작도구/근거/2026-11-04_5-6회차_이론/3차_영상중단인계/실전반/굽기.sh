#!/usr/bin/env bash
# 실전반 5 · 6회차 이론 영상 굽기 — 줄 하나에 편 여럿을 차례로(줄 둘 = 동시 2편). 음성 키 없이(캐시만, 새로 사면 멈춤)
#   bash 굽기.sh <편 키 …>   예: 05회차_01 05회차_06
cd /home/user/hyd-iot-edu
V=workspace/강의제작/제작도구/기존제작/tools/video; W=작업/2026-11-04_5-6회차-렌더-음성
L=workspace/강의제작/제작도구/근거/2026-11-04_5-6회차_이론/2차_되풀이순서렌더/음성/음성기록.json
G=$W/영상/실전반/로그
for k in "$@"; do
  n=${k%_*}; p=${k#*_}; f=$(ls workspace/강의제작/산출물/실전반/이론/$n/대본/${p}_*.md); key=실전반_$k
  out=$W/영상출력/$key/영상; mkdir -p $out
  echo "$(date +%T) $key 시작" >> $G/진행.txt
  env -u ElevenLabs_API_KEY -u ELEVENLABS_API_KEY PATH=/usr/local/lo268/bin:$PATH python3 $V/강의영상.py $out $f --breath --voice 1PdAOcPlPTz12RwMyFVp --audio-ledger $L \
    --pause-short 0.15 --pause-mid 0.45 --pause-long 0.8 --pause-question 0.5 --pause-para 0.4 --gap 1.2 > $G/$key.log 2>&1 || { echo "$(date +%T) $key 굽기 실패: $(tail -1 $G/$key.log)" >> $G/진행.txt; continue; }
  name=$(basename $(ls $out/*.mp4) .mp4); tt=$W/영상출력/$key/_작업/영상_자막_기록/${name}_시간표.md
  python3 $V/검사/말머리_잘림.py $out/$name.mp4 > $G/${key}_말머리.txt 2>&1
  python3 $V/검사/장넘김_싱크.py $out/$name.mp4 $tt > $G/${key}_장넘김.txt 2>&1
  echo "$(date +%T) $key 끝 $(tail -1 $G/$key.log) | 말머리 $(head -1 $G/${key}_말머리.txt) | 장넘김 $(tail -1 $G/${key}_장넘김.txt)" >> $G/진행.txt
done
