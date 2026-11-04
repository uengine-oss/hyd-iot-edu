#!/usr/bin/env bash
# 굽기가 끝난 편부터 강조 전편을 돌린다 — 실전반 쪽 tools/video 파이썬이 2개 미만일 때만 시작(VM 전체 3편 상한, 통합 1편 몫은 남긴다).
#   bash 강조줄.sh <편 키 …>
cd /home/user/hyd-iot-edu; D=작업/2026-11-04_5-6회차-렌더-음성/영상/실전반
mine() { python3 - <<'PY'
import os
n=0
for p in os.listdir('/proc'):
    if not p.isdigit(): continue
    try: a=open(f'/proc/{p}/cmdline','rb').read().decode('utf-8','ignore').split('\0')
    except Exception: continue
    if a and a[0]=='python3' and len(a)>2 and 'tools/video/' in a[1] and '영상출력/실전반_' in a[2]: n+=1
print(n)
PY
}
# 첫 인자 = 기다릴 PID 목록(쉼표) — 그 굽기 줄들이 다 끝난 뒤에 시작한다(줄이 다음 편으로 넘어가며 순간 3편이 되지 않게)
for w in ${1//,/ }; do while kill -0 $w 2>/dev/null; do sleep 15; done; done; shift
for k in "$@"; do
  until grep -q "실전반_$k 끝" $D/로그/진행.txt && [ "$(mine)" -lt 2 ]; do sleep 20; done
  bash $D/강조.sh $k
done
