#!/bin/bash
# 처음부터 다시 찍기: 구간25(새 촬영 페이지를 만든다) → config.json의 page를 새 페이지로 바꿈 → 26~39 연속(chain.sh).
# 시작 전 기존 촬영 페이지는 휴지통에 있어야 한다(사이드바에 같은 이름이 하나 더 찍히지 않게).
#   ./full.sh <접두어>      예: ./full.sh r → take-r25, take-r26 … take-r39
set -u
cd "$(dirname "$0")"
p=$1
out=$(TMO=900 ./run.sh rec "take-${p}25" seg-25.mjs | tail -1); echo "$out"
echo "$out" | PYTHONUTF8=1 python -c "import json,sys;r=json.loads(sys.stdin.read());sys.exit(0 if not r['error'] and not r['banner_frames'] and not r['gaps_over_100'] else 1)" || { echo "STOPPED at 25"; exit 1; }
PYTHONUTF8=1 python - "$p" <<'EOF'
import json, re, sys
from common import WORK, HERE
url = (WORK / f'take-{sys.argv[1]}25' / 'new-page-url.txt').read_text(encoding='utf-8')
pid = re.findall(r'[0-9a-f]{32}', url)[-1]
cfg = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
if pid == cfg['protect']:
    raise SystemExit('new page id equals protected original')
cfg['page'] = pid
(HERE / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('config.page =', pid)
EOF
prev="take-${p}25"
for n in 26 27 28 29 30 31 32 33 34 35 36 37 38 39; do
  out=$(TMO=900 ./run.sh rec "take-${p}$n" "seg-$n.mjs" "$prev" | tail -1); echo "$out"
  ok=$(echo "$out" | PYTHONUTF8=1 python -c "import json,sys;r=json.loads(sys.stdin.read());print('ok' if not r['error'] and not r['banner_frames'] and not r['gaps_over_100'] and r['click_offset_max_px'] in (None,0,0.0) and (r.get('pointer') or {}).get('applied',0)==0 else 'stop')" 2>/dev/null || echo stop)
  [ "$ok" = ok ] || { echo "STOPPED at $n"; exit 1; }
  prev="take-${p}$n"
done
echo "FULL DONE"
