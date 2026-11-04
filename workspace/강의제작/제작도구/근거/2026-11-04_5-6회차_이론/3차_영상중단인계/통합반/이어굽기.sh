#!/usr/bin/env bash
# 앞 편이 끝나기를 기다렸다가(인자 1 = 그 PID) 남은 편을 차례로 굽는다(통합 작업자 상한 1편).
while kill -0 "$1" 2>/dev/null; do sleep 10; done
shift
bash /home/user/hyd-iot-edu/작업/2026-11-04_5-6회차-렌더-음성/영상/통합반/굽기.sh "$@"
