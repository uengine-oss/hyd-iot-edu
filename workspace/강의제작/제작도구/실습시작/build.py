"""시작본 → 오프라인 → 조건표 → 2회차 공통 → ARROWS → 3회차(조건별 손익·판정·문서) → 시작 도구 순서로 같은 판본 생성."""
from pathlib import Path
import ast
import subprocess,sys
here=Path(__file__).resolve().parent


def preflight():
    # 자식 생성기를 import/실행하지 않고 현재 CLI 계약부터 확인한다.
    draft_only = []
    for name in ('build_offline.py', 'build_guide_bundle.py'):
        tree = ast.parse((here/name).read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'add_argument'
                    and any(isinstance(arg, ast.Constant) and arg.value == '--draft' for arg in node.args)
                    and any(k.arg == 'required' and isinstance(k.value, ast.Constant)
                            and k.value.value is True for k in node.keywords)):
                draft_only.append(name)
                break
    if draft_only:
        raise SystemExit(
            '일괄 생성 중단: ' + ', '.join(draft_only) + '는 --draft 검수 출력만 지원합니다. '
            '04·06 가이드와 사진의 최종 확인 및 정본 적용 경로가 아직 필요합니다. '
            '각 도구에 --draft 작업/<작업>/오프라인1_제공물검수를 지정해 따로 실행하세요. '
            '자식 생성기를 실행하지 않았으며 정본을 변경하지 않았습니다.'
        )


preflight()
for script in ['build_labs.py','build_offline.py','build_conditions.py','build_common.py','pack_arrows.py','build_session3_whatif.py','build_session3_judgement.py','build_session3_documents.py']:
    subprocess.run([sys.executable,str(here/script)],check=True)
subprocess.run([sys.executable,str(here/'build_launcher.py'),*sys.argv[1:]],check=True)
subprocess.run([sys.executable,str(here/'build_guide_bundle.py')],check=True)
