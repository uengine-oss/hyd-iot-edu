#!/usr/bin/env bash
# 통합반 5 · 6회차 이론 영상 굽기(한 번에 한 편 — 통합 작업자 상한 1). 인자: 편 키(05_01 …). 저장소 루트에서 돈다.
cd /home/user/hyd-iot-edu
export PATH=/usr/local/lo268/bin:$PATH
W=작업/2026-11-04_5-6회차-렌더-음성; V=workspace/강의제작/제작도구/기존제작/tools/video; S=workspace/강의제작/산출물/통합반/이론
L=workspace/강의제작/제작도구/근거/2026-11-04_5-6회차_이론/2차_되풀이순서렌더/음성/음성기록.json
for k in "$@"; do
  r=${k%_*}; p=${k#*_}; sc=$(ls $S/${r}회차/대본/${p}_*.md); n=통합반_${r}회차_${p}; o=$W/영상출력/$n
  mkdir -p $o/영상; echo "$(date +%T) 시작 $n" >> $W/영상/통합반/굽기_진행.txt
  env -u ELEVENLABS_API_KEY -u ElevenLabs_API_KEY python3 $V/강의영상.py $o/영상 $sc --breath --voice 1PdAOcPlPTz12RwMyFVp --audio-ledger $L \
    --pause-short 0.15 --pause-mid 0.45 --pause-long 0.8 --pause-question 0.5 --pause-para 0.4 --gap 1.2 > $o/굽기.log 2>&1
  echo "$(date +%T) 끝 $n 종료=$? $(tail -1 $o/굽기.log)" >> $W/영상/통합반/굽기_진행.txt
done
