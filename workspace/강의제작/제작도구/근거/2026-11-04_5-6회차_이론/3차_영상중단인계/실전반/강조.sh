#!/usr/bin/env bash
# 강조 전편: 강조 전 영상(영상출력/<키>/영상) + 강조 설정 → 영상출력/<키>/강조/, 확인 프레임 영상출력/<키>/확인/.   bash 강조.sh <편 키 …>
cd /home/user/hyd-iot-edu
V=workspace/강의제작/제작도구/기존제작/tools/video; W=작업/2026-11-04_5-6회차-렌더-음성; G=$W/영상/실전반/로그
export EMPH_FONT=/usr/share/fonts/malgun/MALGUNBD.TTF
for k in "$@"; do
  key=실전반_$k; n=${k%_*}; vid=$(ls $W/영상출력/$key/영상/*.mp4); name=$(basename $vid .mp4)
  cfg=workspace/강의제작/제작도구/구성/실전반/$n/강조_$name.json
  mkdir -p $W/영상출력/$key/강조
  echo "$(date +%T) $key 강조 시작" >> $G/진행.txt
  python3 $V/강조표시.py $vid $cfg $W/영상출력/$key/강조/$name.mp4 --확인 $W/영상출력/$key/확인 > $G/${key}_강조.log 2>&1 \
    && echo "$(date +%T) $key 강조 끝 $(tail -1 $G/${key}_강조.log)" >> $G/진행.txt \
    || echo "$(date +%T) $key 강조 실패: $(tail -1 $G/${key}_강조.log)" >> $G/진행.txt
done
