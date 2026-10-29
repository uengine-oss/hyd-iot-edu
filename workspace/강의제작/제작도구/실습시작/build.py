"""시작본 → 오프라인 → 조건표 → 2회차 공통 → ARROWS → 3회차(조건별 손익·판정·문서) → 시작 도구 순서로 같은 판본 생성."""
from pathlib import Path
import subprocess,sys
here=Path(__file__).resolve().parent
for script in ['build_labs.py','build_offline.py','build_conditions.py','build_common.py','pack_arrows.py','build_session3_whatif.py','build_session3_judgement.py','build_session3_documents.py']:
    subprocess.run([sys.executable,str(here/script)],check=True)
subprocess.run([sys.executable,str(here/'build_launcher.py'),*sys.argv[1:]],check=True)
subprocess.run([sys.executable,str(here/'build_guide_bundle.py')],check=True)
