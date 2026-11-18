"""1회차 실습3(06 전체과정관찰) 학생 가이드 사진을 확정 영상의 프레임에서 뽑는다. 사진의 시각 · 자르기 · 표시 좌표 · 설명은 이 파일 한 곳이다.
언제: 06 확정 영상이 바뀌어 가이드 사진을 다시 뽑을 때(그다음 build_전체과정_학생가이드.py --apply).

PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/강의제작/제작도구/촬영/포털/사진_만들기.py --work 작업/<작업>/06원본 --video <확정 06 영상.mp4>
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
# 이름, (큐 id, 'start'|'end', 더할 초), 자르기, 빨간 표시들, 설명, 글자 아닌 칸(선 자리에 걸린 그림의 점선 등)
PHOTOS = [
    ('홈', ('v0601', 'start', 5), None,
     [[18, 1016, 240, 1048], [426, 174, 1056, 206], [1278, 270, 1424, 304], [1548, 890, 1684, 990]],
     '서비스 16/16 · 맨 위 한 줄 · 사람이 승인한 조치 · 4 결과 보기',
     [[1262, 278, 1279, 292], [1388, 298, 1440, 316]]),
    ('문서등록링크', ('v0609', 'start', 7), None, [[640, 1000, 744, 1032]], '1 지식 넣기 아래 문서 등록 →'),
    ('제공문서', ('v0610', 'start', 7), None, [[426, 330, 1022, 368], [496, 498, 1222, 562]], '단계 줄과 제공 문서의 쿨러 팬 정비 매뉴얼'),
    ('추출시작', ('v0612', 'start', 7.6), None, [[428, 418, 804, 486], [1690, 580, 1860, 630]], '이미 적재된 문서와 AI 추출 시작'),
    ('추출결과', ('v0613', 'start', 8), None, [[428, 420, 1188, 524]], 'AI가 찾은 조치 방법 · 지식 후보 · 매뉴얼 절의 수'),
    ('조치목록', ('v0615', 'start', 2), None, [[578, 114, 688, 144], [496, 184, 858, 246]], '첫 조치와 그 조치가 쓰이는 고장, 지식 후보 칸'),
    ('지식후보', ('v0616', 'start', 1.2), None, [[496, 184, 784, 244], [494, 272, 816, 516]], '고장 유형과 증상, 원인 셋'),
    ('원문대조', ('v0621', 'end', -1.4), None, [[494, 506, 866, 568], [960, 397, 1861, 566], [960, 626, 1112, 658]],
     '고른 팬 진동 줄 · 그 줄의 원문 인용 · 적재에서 제외'),
    ('적재', ('v0622', 'start', 11.3), None, [[428, 836, 840, 870], [1690, 892, 1862, 944]], '검토 체크와 검토한 내용 적재'),
    ('적재완료', ('v0624', 'end', 1), None, [[428, 342, 644, 376], [1486, 742, 1660, 776]], '지식 지도에 적재했습니다와 지식 지도에서 보기 →'),
    ('지식지도', ('v0627', 'end', 0.9), None, [[714, 194, 1003, 246], [664, 954, 1626, 984]], '쿨러 성능 저하를 고른 이상 패턴 경로',
     [[966, 218, 1000, 264]]),
    ('결함시뮬레이션', ('v0632', 'start', 4.4), None,
     [[48, 241, 339, 287], [457, 272, 718, 396], [462, 412, 657, 455], [428, 686, 1152, 716]],
     '결함 시뮬레이션 메뉴 · HYD-01의 상태와 값 · 쿨러 열화 주입 · 명령 관문 안내'),
    ('유온오름', ('v0635', 'start', 8), None, [[459, 244, 704, 272], [486, 908, 1320, 996]], '오르는 유온과 경보 조건 55 °C'),
    ('경보발생', ('v0656', 'start', 10.4), None, [[550, 274, 640, 308], [20, 484, 364, 522], [706, 668, 866, 700]],
     '경보 발생 · 처리 건 옆의 1 · 처리 건에서 보기 →'),
    ('승인요청', ('v0638', 'start', 1.1), None, [[436, 286, 848, 368], [958, 428, 1280, 494], [958, 572, 1486, 662]],
     EX+'내 차례의 처리 건 · 승인 카드의 제목 · AI 판단과 판단 근거 보기', [[410, 306, 446, 354]]),
    ('판단근거', ('v0640', 'start', 2.6), None,
     [[872, 244, 1430, 282], [906, 378, 1688, 496], [874, 646, 1886, 719], [874, 984, 1886, 1072], [1859, 41, 1884, 66]],
     EX+'결론 · 근거 · 후보 비교의 1번과 4번 · 판을 닫는 ×'),
    ('승인', ('v0643', 'start', 2.6), None, [[961, 821, 1063, 870], [1646, 832, 1832, 860]], '승인 단추와 운전원 역할로 기록됩니다'),
    ('냉각명령', ('v0645', 'end', 0.6), None, [[1014, 850, 1832, 944], [1012, 984, 1534, 1044], [18, 1016, 240, 1048]],
     '냉각 명령의 응답 · 효과 확인 · 20배속'),
    ('진행완료', ('v0649', 'end', 0.5), None, [[1012, 392, 1830, 488], [1012, 524, 1832, 588], [1012, 624, 1832, 720]],
     EX+'효과 확인의 회복 판정 · 정비 요청 등록 · 결과 보고: 정상'),
    ('결과', ('v0651', 'start', 7.5), None, [[958, 426, 1556, 514], [958, 578, 1146, 608]], EX+'처리 건 맨 위의 결과와 경보 해제'),
    ('세기록', ('v0652', 'start', 10.2), None, [[1012, 354, 1832, 416], [1012, 454, 1832, 518], [1014, 558, 1832, 648]],
     EX+'원인 진단 · 운전원 승인 · 냉각 명령이 따로 남은 줄'),
    ('가지않은단계', ('v0653', 'start', 3.9), None, [[1000, 742, 1846, 912]], '펼친 가지 않은 단계의 이름'),
    ('홈결과', ('v0657', 'end', 0.7), None, [[426, 174, 1056, 206], [1548, 890, 1684, 990]], '맨 위 한 줄과 4 결과 보기의 처리 완료'),
]


def cue_times():
    """큐 id → (말 시작초, 말 끝초). SRT의 n번째 말이 큐 파일의 n번째 큐다."""
    blocks = [x for x in re.split(r'\n\s*\n', SRT.read_text('utf8').strip()) if x.strip()]
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
    times = cue_times()
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
