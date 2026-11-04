#!/usr/bin/env bash
# 줄 하나가 끝나기를 기다렸다가 남은 편을 굽는다(동시 2편 유지):  bash 이어굽기.sh <기다릴 PID> <편 키 …>
while kill -0 "$1" 2>/dev/null; do sleep 15; done
shift; exec bash "$(dirname "$0")/굽기.sh" "$@"
