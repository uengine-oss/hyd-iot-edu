"""Read-only, host-optional SessionStart reminder. No lecture scan or execution."""
import json
from pathlib import Path
import sys

def reminder(cwd):
    root = Path(__file__).resolve().parents[3]
    current = Path(cwd).resolve()
    if not current.is_relative_to(root):
        return ''
    return (f'작업 루트: {root}\n현재 위치: {current}\n'
            '.claude/skills/lecture-common/공통기준.md와 요청에 해당하는 SKILL.md를 읽는다. '
            'HYD 교재 덱은 hyd-course-deck, HYD 실습 가이드는 hyd-lab-guide가 먼저다. '
            '요구 정리·커리큘럼·의견 반영은 lecture-plan, 덱·대본은 lecture-deck, '
            '실습·가이드는 lecture-lab, 검토만은 lecture-verify, ZIP·업로드는 lecture-deliver다. '
            '이어서 할 때는 대상 강의의 인계와 실제 파일을 먼저 대조한다. '
            '강의별 계약·원문을 보존하고 실제 산출물과 대조한다. '
            '요약 후에는 완료 증거를 보존하고 변동 상태·미완료 부분을 확인한다. '
            '도구 이름이나 훅 실행에 의존하지 않는다.')

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    payload = {}
    if not sys.stdin.isatty():
        raw = sys.stdin.buffer.read().decode('utf-8-sig')
        if raw.strip():
            payload = json.loads(raw)
    text = reminder(payload.get('cwd', str(Path.cwd())))
    if text:
        if '--훅' in sys.argv:
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart',
                                                     'additionalContext': text}}, ensure_ascii=False))
        else:
            print(text)

if __name__ == '__main__':
    main()
