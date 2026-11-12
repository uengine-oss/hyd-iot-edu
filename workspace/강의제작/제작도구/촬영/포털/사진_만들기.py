"""1회차 06 학생 가이드 사진을 게시본 영상의 프레임에서 뽑는다. 사진의 시각 · 자르기 · 표시 좌표 · 설명은 이 파일 한 곳이다.

PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/강의제작/제작도구/촬영/포털/사진_만들기.py --work 작업/<작업>/06원본
    → 사진/06-*.png, 전체과정_학생가이드_사진근거.json. 바뀐 사진은 verified가 풀린다.
--확인 <이름 …>: 눈으로 본 사진을 verified로 적는다(이름 없이 --확인 전부면 모두).
시각은 큐 id로 적는다. 자막(SRT)의 n번째 말이 큐 파일의 n번째 큐이므로, 영상 판본이 바뀌어도 VIDEO · SRT만 바꾸면 시각이 따라온다
(말 수가 큐 수와 다르면 멈춘다). 화면 배치가 바뀐 판이면 좌표는 프레임을 보고 다시 잰다.
네모 그리기 · 선 자리 검사 · 자르기 가장자리 검사는 환경세팅 prepare_student_photos.py의 사진_만들기 하나를 같이 쓴다(가이드 P-8).
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess

import imageio_ffmpeg
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
VIDEO = '작업/촬영/포털/06-최종/06-최종.mp4'   # 다시 찍은 06(2026-11-12)의 합본. 학생에게 낸 판과 같은 바이트여야 한다
SRT = '작업/촬영/포털/06-최종/06-최종.srt'
CUES = HERE/'전체과정관찰_다시찍기_큐.json'
MANIFEST = HERE/'전체과정_학생가이드_사진근거.json'
EX = '강사 화면의 예입니다. '
_spec = importlib.util.spec_from_file_location('prepare_student_photos', HERE.parent/'환경세팅'/'prepare_student_photos.py')
_photos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_photos)

# 자르기가 None이면 화면 전체다(가이드 P-8 — 누르거나 고르거나 새 화면에서 위치를 찾는 사진). 읽기만 하는 칸은 그 칸만 잘라 원래 크기로 싣는다
# (2026-11-11 사용자 「전체화면으로 해야할부분과 아닌부분을 잘판단해봐」 · 「너무 부분만 작게 자르지 말고 어느 영역인지는 알게」).
# 같은 화면에서 이어지는 조작은 한 사진에 네모 여럿으로 묶는다(사용자 「가이드문서가 너무 길어질려나」).
# 네모는 대상 [x0, y0, x1, y1](좁은 곳은 다섯째 pad · 여섯째 굵기)이고, 선 자리에 글자가 걸리면 만들기가 멈춘다.
# 커서는 설명하는 줄을 따라 움직이므로, 읽는 칸은 화면을 굴린 직후(커서가 빈 곳에 남은 때)의 프레임을 고른다.
# 이름, (큐 id, 'start'|'end', 더할 초), 자르기, 빨간 표시들, 설명, 글자 아닌 칸(누르는 순간 대상 밖으로 삐져나온 커서)
PHOTOS = [
    ('연결그림', ('o0101', 'start', 3), None, [[770, 198, 1127, 333]], '홈 위쪽의 열린 사건 칸과 흐름 그림'),
    ('문서개정', ('o0209', 'start', 1), None, [[15, 918, 360, 966], [436, 290, 844, 370], [1380, 296, 1830, 360]], '고른 파일과 등록할 문서의 문서 개정'),
    ('미리보기', ('o0303', 'start', 0.5), None, [[440, 556, 984, 652]], '미리보기 뒤의 절 · 절차 수와 검사 칸'),
    ('원문펼치기', ('o0403', 'start', 0.5), None, [[660, 742, 870, 778], [448, 810, 572, 842]], '추출 원문 전체 보기와 1쪽 전체'),
    ('판정기준', ('o0406', 'start', 2), [440, 200, 1830, 530], [[450, 296, 1300, 432], [450, 456, 1800, 514]], 'HM-8.3 냉각 성능 판정 기준'),
    ('원인', ('o0410', 'start', 2), [440, 110, 1840, 430], [[455, 212, 1800, 362]], 'HM-8.4 원인 셋과 팬 진동 기준'),
    ('즉시완화', ('o0415', 'start', 2), [440, 400, 1840, 680], [[455, 460, 1800, 548]], 'HM-8.5 즉시 완화 조치 — 원격 조치는 REMOTE_AUTO일 때만'),
    ('회복금지', ('o0421', 'end', -0.5), [440, 100, 1840, 680], [[452, 482, 1790, 632]], 'HM-8.8 금지와 제한'),
    ('추출요청', ('o0502', 'start', 0.3), None, [[445, 680, 830, 740]], '추출 제안 준비와 추출 진행 · 결과 확인'),
    ('추출경고', ('o0506', 'start', 1), None, [[445, 306, 665, 360], [465, 376, 1815, 594]], EX+'추출 경고 원문 3개'),
    ('조치방법', ('o0603', 'start', 4), None, [[1070, 262, 1434, 316], [1450, 262, 1814, 316]], EX+'등록할 조치 방법의 관계와 종류'),
    ('원문인용', ('o0608', 'end', -0.5), None, [[1070, 416, 1814, 478], [1076, 656, 1804, 964]], EX+'팬 최대 운전 — 즉시 완화 · 설비 제어와 원문 인용'),
    ('원인원문', ('o0705', 'start', 3), [420, 90, 1860, 1010], [[456, 546, 1804, 804]], EX+'쿨러 핀 오염의 원문 인용'),
    ('확인증거', ('o0708', 'start', 3), [420, 90, 1860, 1010], [[440, 512, 1824, 814]], EX+'확인 증거의 시간과 미만 · 이상'),
    ('규칙', ('o0711', 'start', 2), [420, 560, 1860, 1010], [[446, 686, 1824, 994]], EX+'규칙의 첫 두 줄'),
    ('적재결과', ('o0804', 'start', 2), None, [[440, 740, 1824, 866]], '검토 체크와 적재 완료의 수'),
    ('지도검색', ('o0903', 'end', -0.3), None, [[1540, 192, 1814, 240]], '검색 칸의 쿨러 — 쿨러가 든 항목이 노랗게 표시된다'),
    ('지도관계', ('o0906', 'start', 1), None, [[1146, 396, 1514, 724], [1146, 746, 1514, 982]], '쿨러 냉각 성능 상실의 나가는 관계 · 들어오는 관계'),
    ('설비시작', ('o1005', 'start', 1), None, [[746, 232, 844, 306], [452, 312, 648, 384], [452, 482, 844, 518]], 'HYD-01의 원격 자동 · 유온 · 냉각 효율'),
    ('열화주입', ('o1006', 'end', -0.5), None, [[452, 932, 634, 984]], '쿨러 열화 주입 버튼'),
    ('경보발생', ('o1015', 'end', 0.5), [400, 82, 900, 1000], [[452, 400, 844, 432], [452, 736, 844, 768], [676, 776, 844, 838]], '떨어진 냉각 효율 · 쿨러 성능 비율과 경보 발생'),
    ('새처리건', ('o1104', 'start', 3), None, [[15, 196, 360, 240], [424, 726, 874, 874]], '새로 생긴 냉각 긴급 대응 HYD-01'),
    ('진행상황', ('o1107', 'start', 2), None, [[956, 360, 1814, 884]], '끝난 원인 진단과 멈춰 있는 운전원 승인'),
    ('승인요청', ('o1205', 'start', 2), None, [[446, 302, 934, 344], [466, 426, 1804, 824]], EX+'승인 요청의 첫 번째 조치와 예상 · 좋아지는 것 · 감수할 것'),
    ('다른안', ('o1209', 'start', 2), None, [[476, 686, 1804, 1002]], EX+'다른 안 3개는 왜 졌나와 이 안으로 바꾸기'),
    ('운전원', ('o1215', 'start', 0.5), None, [[15, 144, 360, 192], [416, 232, 1854, 312], [420, 426, 1854, 504]], '나 칸의 최운전 · 운전원과 내 작업의 운전원 승인'),
    ('승인', ('o1217', 'end', -0.5), None, [[446, 356, 584, 394], [1736, 736, 1824, 788]], '담당자 최운전과 진해진 승인 버튼'),
    ('처리과정', ('o1303', 'start', 1), None, [[956, 96, 1804, 364]], '운전원 승인 · 냉각 명령 · 재관측'),
    ('끝', ('o1306', 'start', 1), None, [[956, 172, 1814, 228]], '처리 건 위의 끝'),
    ('기록탭', ('o1402', 'start', 0.5), None, [[1082, 546, 1200, 602], [956, 626, 1804, 824]], '처리 기록 탭과 단계 순서'),
    ('추천길', ('o1413', 'start', 1), None, [[1086, 76, 1804, 254], [1086, 306, 1804, 602], [1086, 786, 1804, 894]], EX+'지식 경로 · 원인마다 맞춰 본 증거 · 추천안에 이른 길'),
    ('재관측', ('o1420', 'start', 3), None, [[1026, 212, 1814, 374], [1026, 736, 1814, 904]], EX+'냉각 명령의 응답과 재관측'),
    ('정비결과보고', ('o1424', 'start', 1), None, [[1026, 212, 1814, 494], [1026, 716, 1814, 914]], EX+'작업지시 등록과 결과 보고: 정상'),
    ('결과', ('o1502', 'start', 1), None, [[976, 446, 1524, 584]], EX+'결과 탭의 유온 · 경보 해제'),
]


def cue_times():
    """큐 id → (말 시작초, 말 끝초). SRT의 n번째 말이 큐 파일의 n번째 큐다."""
    import re
    blocks = [x for x in re.split(r'\n\s*\n', (ROOT/SRT).read_text('utf8').strip()) if x.strip()]
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
    if not args.work:
        parser.error('--work가 필요합니다')
    work = args.work.resolve()
    if not work.is_relative_to((ROOT/'작업').resolve()):
        parser.error('원본 프레임은 저장소 작업 폴더에 둡니다.')
    work.mkdir(parents=True, exist_ok=True)
    video_sha = sha(ROOT/VIDEO)
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
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-threads', '1', '-ss', str(seconds), '-i', str(ROOT/VIDEO), '-frames:v', '1', str(frame)], check=True)
        with Image.open(frame) as image:
            crop = crop or [0, 0, image.width, image.height]
        target = out/(key+'.png')
        _photos.사진_만들기(frame, crop, rects, key, ignore=ignore).save(target)
        digest = sha(target)
        photos[key] = {'required_scene': caption, 'check': caption, 'path': target.relative_to(ROOT).as_posix(),
                       'verified': bool(old.get(key, {}).get('verified')) and old[key].get('sha256') == digest,
                       'source_type': 'video', 'source': VIDEO, 'source_sha256': video_sha, 'seconds': seconds, 'cue': list(at), 'crop': crop,
                       'rectangles': rects, 'ignore': ignore, 'redactions': [], 'caption': caption, 'sha256': digest, 'raw_frame_sha256': sha(frame)}
    stale = {p.name for p in out.glob('06-*.png')} - {k+'.png' for k in photos}
    if stale:
        raise SystemExit(f'근거에 없는 옛 사진을 지우세요: {sorted(stale)}')
    MANIFEST.write_text(json.dumps({'photos': photos}, ensure_ascii=False, indent=2)+'\n', 'utf8')
    print(len(photos), '사진. 눈으로 본 뒤 --확인.')


if __name__ == '__main__':
    main()
