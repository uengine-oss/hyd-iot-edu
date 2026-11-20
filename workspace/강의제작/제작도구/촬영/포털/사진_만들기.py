"""1회차 실습3(06 전체과정관찰) 학생 가이드 사진을 확정 영상의 프레임에서 뽑는다. 사진의 시각 · 자르기 · 표시 좌표 · 설명은 이 파일 한 곳이다.
언제: 06 확정 영상이 바뀌어 가이드 사진을 다시 뽑을 때(그다음 build_전체과정_학생가이드.py --apply).

PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/강의제작/제작도구/촬영/포털/사진_만들기.py --work 작업/<작업>/06원본 --video <확정 06 영상.mp4> [--srt <그 영상의 자막>]
    → 사진/06-*.png, 전체과정_학생가이드_사진근거.json. 바뀐 사진은 verified가 풀린다.
--확인 <이름 …>: 눈으로 본 사진을 verified로 적는다(이름 없이 --확인 전부면 모두).
확정 영상은 Release 「영상」의 int-01-06-lab.mp4다. 받아 둔 자리를 --video로 주고, 근거에는 그 이름과 sha256을 적는다.
시각은 큐 id로 적는다. 자막(SRT)의 n번째 말이 큐 파일의 n번째 큐이므로, 영상 판본이 바뀌어도 SRT만 바꾸면 시각이 따라온다
(말 수가 큐 수와 다르면 멈춘다). 화면 배치가 바뀐 판이면 좌표는 프레임을 보고 다시 잰다.
네모 그리기 · 선 자리 검사 · 자르기 가장자리 검사는 환경세팅 prepare_student_photos.py의 사진_만들기 하나를 같이 쓴다(가이드 P-8).
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess

import imageio_ffmpeg
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOURCE = 'Release 영상 · int-01-06-lab.mp4'
SRT = ROOT/'workspace/강의제작/산출물/영상/_작업/영상_자막_기록/통합반_01회차_06_실습_전체과정관찰.srt'
CUES = HERE/'통합_01_06_전체과정관찰_큐.json'
MANIFEST = HERE/'전체과정_학생가이드_사진근거.json'
EX = '강사 화면의 예: '
_spec = importlib.util.spec_from_file_location('prepare_student_photos', HERE.parent/'환경세팅'/'prepare_student_photos.py')
_photos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_photos)

# 자르기가 None이면 화면 전체다(가이드 P-8 — 누르거나 고르거나 새 화면에서 위치를 찾는 사진). 읽기만 하는 칸은 그 칸만 잘라 원래 크기로 싣는다.
# 같은 화면에서 이어지는 조작은 한 사진에 네모 여럿으로 묶는다. 네모는 대상 [x0, y0, x1, y1]이고, 선 자리에 글자가 걸리면 만들기가 멈춘다.
# 커서는 말하는 대상을 따라 움직이므로, 커서와 마우스 올림 색이 글을 가리지 않는 순간(화면을 굴린 직후, 누르기 전 빈자리)을 고른다.
# 영상의 강조(밑줄 · 띠 · 테두리)는 다음 짚기까지 남아 가이드의 빨간 네모와 섞이므로, 큐와 큐 사이나 누른 직후처럼 강조가 없는 순간을 고르고 뽑은 프레임에서 강조가 없는지 눈으로 본다.
# 이름, (큐 id, 'start'|'end', 더할 초), 자르기, 빨간 표시들, 설명, 글자 아닌 칸(선 자리에 걸린 그림의 점선 등)
PHOTOS = [
    ('홈', ('v0601', 'end', 0.65), None, [[20, 1020, 239, 1044], [429, 177, 1053, 205], [1549, 892, 1680, 981]],
     '서비스 16/16 · 맨 위 한 줄 · 4 결과 보기'),
    ('문서등록링크', ('v0609', 'start', 7.1), None, [[641, 1003, 741, 1028]],
     '1 지식 넣기 아래 문서 등록 →'),
    ('제공문서', ('v0609', 'end', 1.0), None, [[428, 330, 1019, 367], [500, 500, 1218, 557]],
     '단계 줄과 제공 문서의 쿨러 팬 정비 매뉴얼'),
    ('추출시작', ('v0611', 'end', 1.17), None, [[429, 421, 799, 485], [1687, 578, 1862, 631]],
     '이미 적재된 문서와 AI 추출 시작'),
    ('조치목록', ('v0615', 'start', 0.68), None, [[579, 133, 684, 158], [494, 204, 855, 261]],
     '첫 조치와 그 조치가 쓰이는 고장, 지식 후보 칸'),
    ('지식후보', ('v0615', 'end', 1.0), None, [[494, 186, 778, 245], [494, 276, 813, 513]],
     '고장 유형과 증상, 원인 셋'),
    ('원문대조', ('v0619', 'end', 1.0), None, [[495, 510, 841, 578], [982, 417, 1825, 546], [994, 630, 1111, 656]],
     '고른 팬 진동 줄 · 그 줄의 원문 인용 · 적재에서 제외'),
    ('적재', ('v0622', 'start', 14.9), None, [[428, 838, 838, 870], [1689, 891, 1862, 944]],
     '검토 체크와 검토한 내용 적재', [[436, 856, 476, 900]]),
    ('적재완료', ('v0624', 'end', 1.16), None, [[427, 393, 643, 419], [1487, 685, 1658, 710]],
     '지식 지도에 적재했습니다와 지식 지도에서 보기 →'),
    ('지식지도', ('v0627', 'end', 1.0), None, [[712, 192, 1004, 247], [670, 953, 1623, 979]],
     '쿨러 성능 저하를 고른 이상 패턴 경로', [[966, 218, 1000, 264]]),
    ('결함시뮬레이션', ('v0630', 'end', 1.08), None, [[60, 250, 195, 276], [460, 274, 714, 392], [460, 410, 658, 457], [429, 688, 1151, 716]],
     '결함 시뮬레이션 메뉴 · HYD-01의 상태와 값 · 쿨러 열화 주입 · 명령 관문 안내'),
    ('유온오름', ('v0634', 'end', 0.655), None, [[460, 287, 702, 312], [488, 910, 1317, 994]],
     '오르는 유온과 경보 조건 55 °C'),
    ('경보발생', ('v0635', 'end', 3.82), None, [[560, 199, 631, 222], [708, 591, 862, 616]],
     '경보 발생과 카드 아래 처리 건에서 보기 →'),
    ('승인요청', ('v0656', 'end', 1.65), None, [[447, 246, 833, 355], [958, 428, 1280, 491], [958, 574, 1483, 651]],
     EX+'내가 할 일의 처리 건 · 승인 카드의 제목 · AI 판단과 판단 근거 보기'),
    ('판단근거', ('v0642', 'end', 1.15), None, [[905, 320, 1685, 475], [890, 601, 1817, 641], [901, 927, 1869, 1014], [1861, 43, 1882, 64]],
     EX+'근거 · 후보 비교의 1번과 4번 · 판을 닫는 ×'),
    ('승인', ('v0643', 'start', 1.67), None, [[959, 819, 1065, 872], [1647, 834, 1832, 857]],
     '승인 단추와 운전원 역할로 기록됩니다'),
    ('냉각명령', ('v0645', 'end', 1.0), [0, 492, 1920, 1054], [[1013, 852, 1832, 943], [1012, 984, 1832, 1045], [177, 1020, 239, 1043]],
     '냉각 명령의 응답 · 효과 확인 · 20배속'),
    ('진행완료', ('v0648', 'end', 7.71), None, [[1013, 563, 1832, 624], [1013, 665, 1832, 724], [1013, 767, 1832, 854]],
     EX+'효과 확인의 회복 판정 · 정비 요청 등록 · 결과 보고: 정상'),
    ('결과', ('v0650', 'start', 1.16), None, [[959, 426, 1227, 461], [958, 481, 1554, 513], [959, 579, 1144, 606]],
     EX+'처리 건 맨 위의 결과와 경보 해제'),
    ('세기록', ('v0652', 'end', 1.15), None, [[1012, 356, 1832, 416], [1012, 457, 1832, 520], [1013, 559, 1832, 650]],
     EX+'원인 진단 · 운전원 승인 · 냉각 명령이 따로 남은 줄', [[1480, 496, 1530, 545]]),
    ('홈결과', ('v0657', 'end', 1.43), None, [[429, 177, 1053, 205], [1549, 892, 1680, 981]],
     '맨 위 한 줄과 4 결과 보기의 처리 완료'),
]


def cue_times(srt=SRT):
    """큐 id → (말 시작초, 말 끝초). SRT의 n번째 말이 큐 파일의 n번째 큐다."""
    blocks = [x for x in re.split(r'\n\s*\n', Path(srt).read_text('utf8').strip()) if x.strip()]
    ids = [q['id'] for q in json.loads(CUES.read_text('utf8'))['cues']]
    if len(blocks) != len(ids):
        raise SystemExit(f'자막 말 {len(blocks)}개와 큐 {len(ids)}개가 다릅니다 — 이 영상의 큐 파일인지 보세요')
    def sec(t):
        h, m, s = t.replace(',', '.').split(':')
        return int(h)*3600 + int(m)*60 + float(s)
    out = {}
    for cid, blk in zip(ids, blocks):
        a, z = blk.splitlines()[1].split(' --> ')
        out[cid] = (sec(a), sec(z))
    return out


def at_seconds(times, at):
    """(큐 id, 'start'|'end', 더할 초) → 영상 초."""
    cid, where, delta = at
    return round(times[cid][0 if where == 'start' else 1] + delta, 2)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path)
    parser.add_argument('--video', type=Path, help='확정 06 영상(Release 영상 int-01-06-lab.mp4와 같은 바이트)')
    parser.add_argument('--srt', type=Path, default=SRT, help='그 영상의 자막(기본: 확정 영상의 자막 기록). Release에 올리기 전의 새 판은 그 판 옆의 자막.srt를 준다')
    parser.add_argument('--확인', nargs='*', dest='confirm')
    args = parser.parse_args()
    old = json.loads(MANIFEST.read_text('utf8'))['photos'] if MANIFEST.exists() else {}
    if args.confirm is not None:
        names = list(old) if args.confirm == ['전부'] else ['06-'+n for n in args.confirm]
        for n in names:
            if sha(ROOT/old[n]['path']) != old[n]['sha256']:
                raise SystemExit(f'{n}: 사진이 근거와 다릅니다 — 먼저 다시 만드세요')
            old[n]['verified'] = True
        MANIFEST.write_text(json.dumps({'photos': old}, ensure_ascii=False, indent=2)+'\n', 'utf8')
        print('확인 적음:', len(names))
        return
    if not args.work or not args.video:
        parser.error('--work와 --video가 필요합니다')
    work = args.work.resolve()
    if not work.is_relative_to((ROOT/'작업').resolve()):
        parser.error('원본 프레임은 저장소 작업 폴더에 둡니다.')
    work.mkdir(parents=True, exist_ok=True)
    video = args.video.resolve()
    video_sha = sha(video)
    out = HERE/'사진'
    out.mkdir(exist_ok=True)
    photos = {}
    times = cue_times(args.srt)
    for name, at, crop, rects, caption, *rest in PHOTOS:
        seconds = at_seconds(times, at)
        ignore = rest[0] if rest else []
        key = '06-'+name
        frame = work/f'{video_sha[:12]}-{seconds}.png'
        if not frame.exists():
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-threads', '1', '-ss', str(seconds), '-i', str(video), '-frames:v', '1', str(frame)], check=True)
        with Image.open(frame) as image:
            crop = crop or [0, 0, image.width, image.height]
        target = out/(key+'.png')
        _photos.사진_만들기(frame, crop, rects, key, ignore=ignore).save(target)
        digest = sha(target)
        photos[key] = {'required_scene': caption, 'check': caption, 'path': target.relative_to(ROOT).as_posix(),
                       'verified': bool(old.get(key, {}).get('verified')) and old[key].get('sha256') == digest,
                       'source_type': 'video', 'source': SOURCE, 'source_sha256': video_sha, 'seconds': seconds, 'cue': list(at), 'crop': crop,
                       'rectangles': rects, 'ignore': ignore, 'redactions': [], 'caption': caption, 'sha256': digest, 'raw_frame_sha256': sha(frame)}
    stale = {p.name for p in out.glob('06-*.png')} - {k+'.png' for k in photos}
    if stale:
        raise SystemExit(f'근거에 없는 옛 사진을 지우세요: {sorted(stale)}')
    MANIFEST.write_text(json.dumps({'photos': photos}, ensure_ascii=False, indent=2)+'\n', 'utf8')
    print(len(photos), '사진. 눈으로 본 뒤 --확인.')


if __name__ == '__main__':
    main()
