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
# 이름, 영상 초, 자르기, 빨간 표시들, 설명, 글자 아닌 칸(누르는 순간 대상 밖으로 삐져나온 커서)
PHOTOS = [
    ('연결그림', 20, None, [[782, 198, 1127, 333], [1236, 475, 1502, 505, 5, 5]], '홈 위쪽의 열린 사건 칸', [[1222, 478, 1237, 498], [1336, 497, 1406, 518]]),
    ('매뉴얼등록', 94.0, None, [[15, 918, 250, 966], [504, 393, 751, 410], [445, 312, 833, 350], [913, 312, 1355, 358], [1380, 312, 1825, 358], [1703, 525, 1823, 572], [440, 598, 970, 692]], '미리보기 뒤 버튼 아래의 글자 수 · 절 · 절차 수', [[1752, 535, 1792, 592]]),
    ('원문펼치기', 117.1, None, [[668, 742, 880, 776], [457, 812, 556, 838]], '추출 원문 전체 보기와 1쪽 전체', [[480, 822, 520, 868]]),
    ('벨트원문', 139.5, [440, 140, 1580, 670], [[455, 484, 1000, 655]], 'HM-8.2와 벨트 교체 절차'),
    ('판정기준', 140.5, [440, 200, 1800, 525], [[450, 310, 1260, 420], [450, 462, 1790, 512]], 'HM-8.3 냉각 성능 판정 기준'),
    ('원인증거', 173.9, [440, 110, 1790, 430], [[455, 214, 1768, 266]], 'HM-8.4 핀 오염 — 최근 30초 냉각 효율 평균과 최근 2분 팬 진동 평균'),
    ('회복기준', 212.4, [440, 198, 1790, 318], [[452, 212, 1770, 300]], 'HM-8.6 회복 판정 — 조치 뒤 15분 유지'),
    ('금지제한', 256.2, [440, 160, 1790, 640], [[452, 180, 1145, 292], [452, 485, 1775, 630]], 'SOP-COOL-14 쿨러 핀 세척 절차와 HM-8.8 금지와 제한'),
    ('추출요청', 278, None, [[445, 680, 820, 738], [445, 790, 1830, 825]], '이 문서의 추출 작업 상태'),
    ('조치방법', 292, [420, 70, 1860, 703], [[1050, 305, 1230, 340]], EX+'오른쪽 등록할 조치 방법이 검토할 제안'),
    ('관계종류', 328.0, [1040, 130, 1860, 954], [[1078, 395, 1428, 440], [1455, 395, 1806, 440], [1080, 625, 1795, 772], [1101, 845, 1426, 935]], EX+'팬 최대 운전의 관계 · 종류와 원문 인용', [[1108, 448, 1142, 490]]),
    ('핀세척', 380.3, [1040, 150, 1860, 742], [[1455, 205, 1806, 255], [1078, 515, 1428, 564], [1455, 515, 1806, 564]], EX+'쿨러 핀 세척 — 근본 조치, 종류는 정비 요청'),
    ('원인후보', 483.6, [420, 130, 1300, 745], [[444, 147, 1290, 702]], EX+'원인 후보 셋과 원문 인용'),
    ('확인증거', 518.3, [420, 75, 1300, 735], [[450, 222, 1290, 362], [450, 567, 1290, 696]], EX+'팬 진동의 평균 시간과 비교 방향'),
    ('제한경고', 531.6, [420, 140, 1800, 817], [[455, 176, 1235, 198], [455, 351, 1745, 373], [455, 725, 1250, 748]], EX+'굵은 글씨의 조건 셋'),
    ('경고', 551.6, None, [[455, 310, 650, 338], [475, 469, 1810, 527]], EX+'두 번째 경고의 현장 점검 조건', [[485, 328, 516, 366]]),
    ('적재결과', 578.2, None, [[440, 750, 1410, 775], [1700, 790, 1830, 837], [440, 838, 1400, 865]], '적재 완료 아래의 절 · 조치 방법 · 단계 수와 연결된 고장'),
    ('지도검색', 593, None, [[15, 818, 250, 866], [415, 270, 725, 302]], '노랗게 표시된 쿨러 항목'),
    ('지도고장유형', 588.25, None, [[737, 653, 999, 698, 4, 3]], '고장 유형 아래의 쿨러 냉각 성능 상실', [[862, 688, 897, 718], [1000, 660, 1008, 705]]),
    ('지도관계', 611.7, [420, 480, 1860, 1030], [[444, 532, 690, 579], [1150, 570, 1495, 808]], '나가는 관계의 즉시 완화와 근본 조치', [[1388, 795, 1422, 842]]),
    ('운전원', 625.6, None, [[15, 145, 250, 190], [1659, 30, 1810, 60], [415, 237, 1850, 272]], '오른쪽 위에도 바뀐 이름 최운전', [[1785, 232, 1845, 322]]),
    ('설비시작', 640.8, None, [[15, 303, 250, 348], [755, 235, 880, 265], [440, 305, 680, 388], [445, 480, 870, 522]], 'HYD-01의 운전 모드 · 유온 · 냉각 효율'),
    ('열화주입전', 644, None, [[450, 732, 636, 789], [450, 857, 590, 904]], '원격 자동과 쿨러 열화 주입 버튼'),
    ('경보발생', 688.5, [400, 75, 895, 763], [[450, 298, 840, 322], [680, 335, 850, 400], [450, 634, 700, 658]], '떨어진 쿨러 성능 비율과 경보 발생'),
    ('새처리건', 698.8, None, [[15, 196, 250, 240], [425, 185, 880, 335]], '새로 생긴 냉각 긴급 대응 HYD-01'),
    ('진행상황', 705, [950, 140, 1800, 745], [[962, 155, 1112, 185], [966, 295, 1792, 700]], '끝난 단계와 진행 중인 운전원 승인', [[1030, 172, 1068, 218]]),
    ('작업요청', 722, None, [[15, 145, 250, 190], [420, 345, 549, 387], [425, 430, 1840, 525]], '운전원 승인 요청의 설비 · 기한'),
    ('승인근거', 725.5, [960, 235, 1800, 980], [[1000, 328, 1450, 930]], EX+'조치 카드 묶음의 추천안과 대안의 순위 · 이유'),
    ('승인카드', 727, [420, 70, 1860, 891], [[465, 115, 1800, 365], [905, 745, 1360, 808]], EX+'나갈 명령 · 근거와 역할'),
    ('승인선택', 729.7, None, [[905, 340, 1360, 390], [1640, 738, 1825, 785]], '역할 운전원과 승인 버튼'),
    ('단계자세히', 740.5, None, [[1000, 637, 1820, 672], [1130, 950, 1255, 982]], '운전원 승인 아래의 단계 자세히'),
    ('승인판단', 759.5, [970, 285, 1800, 688], [[995, 303, 1776, 672]], EX+'권고 · 고른 조치 · 승인자'),
    ('승인전달', 773.3, [970, 715, 1800, 1005], [[995, 738, 1785, 993]], EX+'다음 단계로 넘긴 값의 고른 조치'),
    ('원인입력', 789.2, [970, 320, 1860, 990], [[996, 348, 1800, 975]], EX+'원인 진단 단계의 받은 입력'),
    ('원인판단', 795, [970, 720, 1800, 900], [[992, 745, 1210, 885]], EX+'판단 · 출력의 원인'),
    ('처리과정', 802.9, [970, 300, 1800, 907], [[1000, 312, 1790, 340], [1090, 705, 1790, 900]], EX+'AI가 찾아 확인한 정보'),
    ('추천판단', 836.6, [970, 420, 1820, 1010], [[1395, 590, 1806, 1000]], EX+'판단 근거와 추천'),
    ('기록탭', 860.6, None, [[1080, 302, 1210, 339], [965, 500, 1706, 580]], '처리 기록 탭 위쪽의 처리 순서', [[1134, 328, 1172, 372]]),
    ('대안비교', 883.4, [1055, 672, 1820, 880], [[1090, 690, 1275, 726], [1087, 741, 1800, 865]], EX+'비교한 대안의 예측 평형 유온'),
    ('처리기록', 902.8, [1009, 110, 1820, 520], [[1086, 132, 1800, 303], [1086, 342, 1800, 505]], '냉각 명령의 실행 완료 응답과 재관측의 유온 변화 · 기준 안 시간 비율', [[1128, 222, 1162, 262]]),
    ('결과탭', 958, None, [[1205, 305, 1270, 338], [990, 490, 1440, 615], [990, 865, 1135, 895]], '결과 탭의 유온 · 경보 해제와 처리 기록 보기'),
    ('후속정비', 986, [1009, 95, 1830, 400], [[1084, 117, 1815, 387, 3, 3]], '작업지시 등록의 정비 오더'),
    ('처음경보', 1001.2, [1009, 95, 1850, 320], [[1035, 111, 1830, 306]], '센서 경보로 시작의 설비 · 시각 · 값'),
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
