"""강사용: 수업 단계 선언(it/process/procsvc/course_phase.json)에 서명한다 — PBL을 열거나 다시 수업 단계로 닫는다.

학생 PC는 이 파일을 git pull(또는 새 ZIP)로 받아 시작.bat 때 읽는다(procsvc/course_policy.py). 서명이 맞지 않으면 process가 뜨지 않으므로
학생은 자기 PC에서 단계를 바꿀 수 없다. 비밀 키는 강사가 정한 자리(저장소 밖)에만 둔다 — 이 도구는 비밀 키를 화면에 내거나 저장소에 쓰지 않는다.

  # (처음 한 번, 따로 키를 쓸 때) 키 쌍 만들기 — 비밀 키는 지정한 파일에, 화면에는 공개 키만. 공개 키는 course_policy.PHASE_KEYS 에 넣는다
  .venv314/Scripts/python.exe workspace/개발/scripts/course_phase_sign.py keygen D:/안전한자리/hyd-course-phase.key
  # PBL 열기(기한 필수, 시간대 포함, 지금보다 뒤) — 저장소의 선언 파일을 바꾼다. 커밋 · push 하면 학생이 받는다
  .venv314/Scripts/python.exe workspace/개발/scripts/course_phase_sign.py pbl D:/안전한자리/hyd-course-phase.key --expires 2026-12-31T23:59:59+09:00 --note "1기 PBL"
  # 다시 수업 단계로
  .venv314/Scripts/python.exe workspace/개발/scripts/course_phase_sign.py course D:/안전한자리/hyd-course-phase.key

판정은 학생 PC와 같은 함수 하나(course_policy.load_phase)로 한다: 서명한 선언을 옆 임시 파일에 쓰고 그 함수로 읽어, 공개 키가
PHASE_KEYS 에 없거나(어떤 꼴로 적혔든 — 키는 바이트로 비교된다) PBL 기한이 이미 지났으면 선언 파일을 바꾸지 않고 멈춘다.
비밀 키 파일 형식: Ed25519 비밀 키 32바이트를 base64url로 쓴 한 줄(keygen 이 만드는 모양) 또는 PEM(PKCS#8).
"""
import argparse
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'common'), str(ROOT / 'it' / 'process')]

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from procsvc import course_policy  # noqa: E402


class SignError(RuntimeError):
    """선언을 쓰지 않은 까닭(강사가 읽는 문장)."""


def b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def load_private(path):
    data = Path(path).read_bytes()
    if data.lstrip().startswith(b'-----BEGIN'):
        key = serialization.load_pem_private_key(data, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise SignError(f'{path}: Ed25519 비밀 키가 아닙니다')
        return key
    return Ed25519PrivateKey.from_private_bytes(course_policy.decode64(data.decode().strip()))


def keygen(path):
    path = Path(path)
    if path.exists():
        raise SignError(f'{path}: 이미 있습니다 — 덮어쓰지 않습니다')
    if ROOT in path.resolve().parents:
        raise SignError(f'{path}: 저장소 안에는 비밀 키를 두지 않습니다 — 저장소 밖 자리를 고르세요')
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    path.write_text(b64(raw) + '\n', encoding='utf8')
    return b64(private.public_key().public_bytes_raw())


def write_phase(private, phase, out, *, note='', expires=None, keys=None, now=None):
    """서명한 선언을 out 에 쓴다. 학생 PC와 같은 load_phase 로 확인되지 않으면 out 을 바꾸지 않고 SignError."""
    payload = {'contract': course_policy.PHASE_CONTRACT, 'phase': phase, 'note': note,
               'issued_at': (now or datetime.now().astimezone()).isoformat(timespec='seconds')}
    if phase == 'pbl':
        until = datetime.fromisoformat(str(expires))
        if until.tzinfo is None:
            raise SignError('--expires 에 시간대를 넣으세요(예 +09:00)')
        payload['expires'] = until.isoformat()
    out = Path(out)
    trial = out.with_name(out.name + '.서명확인')
    trial.write_text(json.dumps(course_policy.sign_phase(payload, private), ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    try:
        try:
            got = course_policy.load_phase(trial, **({} if keys is None else {'keys': keys}), **({} if now is None else {'now': now}))
        except course_policy.PhaseError as exc:
            public = b64(private.public_key().public_bytes_raw())
            raise SignError(f'학생 PC가 이 선언을 믿지 않습니다({exc}) — 이 비밀 키의 공개 키 {public} 가 course_policy.PHASE_KEYS 에 있는지 '
                            '확인하세요. 선언 파일은 그대로 두었습니다') from exc
        if got.name != phase:
            raise SignError(f'PBL 기한 {payload.get("expires")}이 이미 지나 학생 PC는 수업 단계로 읽습니다 — 지금보다 뒤의 기한을 넣으세요. '
                            '선언 파일은 그대로 두었습니다')
        os.replace(trial, out)
    finally:
        trial.unlink(missing_ok=True)
    return got


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    k = sub.add_parser('keygen'); k.add_argument('key_file')
    for name in ('pbl', 'course'):
        p = sub.add_parser(name); p.add_argument('key_file')
        p.add_argument('--note', default='')
        p.add_argument('--out', default=str(course_policy.PHASE_FILE))
        if name == 'pbl':
            p.add_argument('--expires', required=True, help='PBL 기한(시간대 포함 ISO, 지금보다 뒤, 예 2026-12-31T23:59:59+09:00)')
    args = parser.parse_args()
    try:
        if args.cmd == 'keygen':
            public = keygen(args.key_file)
            print('비밀 키를 저장했습니다:', args.key_file)
            print('공개 키(이것만 course_policy.PHASE_KEYS 에 넣습니다):', public)
            return
        phase = write_phase(load_private(args.key_file), args.cmd, args.out, note=args.note, expires=getattr(args, 'expires', None))
    except SignError as exc:
        sys.exit(f'[멈춤] {exc}')
    print(f'{args.out}: {phase.label} 단계 선언을 썼습니다' + (f' (기한 {phase.expires})' if phase.expires else '')
          + ' — 커밋 · push 하면 학생 PC가 다음 시작 때 읽습니다')


if __name__ == '__main__':
    main()
