"""시작본 → 오프라인 → 조건표 → 시작 도구 순서로 같은 판본 생성."""
from pathlib import Path
import subprocess,sys
here=Path(__file__).resolve().parent
for script in ['build_labs.py','build_offline.py','build_conditions.py','pack_arrows.py']:
    subprocess.run([sys.executable,str(here/script)],check=True)
subprocess.run([sys.executable,str(here/'build_launcher.py'),*sys.argv[1:]],check=True)
