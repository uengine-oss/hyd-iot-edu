"""이론 대본의 구획을 음성 캐시와 대조해 새로 뽑을 구획 · 글자 수를 낸다. 유료 호출이 없고 키도 쓰지 않는다.

    <py> workspace/강의제작/제작도구/기존제작/tools/video/음성견적.py <대본 파일 …> --voice <음성 ID> [--model ID] [--speed 값]

- 낭독 추출(slides_text) · 캐시 이름(cache_key) · 모델과 빠르기 기본값은 강의영상.py에서 불러 쓴다. 사본 로직이 없어 어긋나지 않는다.
- 음성 ID는 꼭 준다. 캐시 이름에 들어가고 강의영상.py에도 기본값이 없다(영상.md V맥-12).
- 글 · 음성 · 모델 · 빠르기가 같은 구획은 캐시(mp3 · json 둘 다)를 쓰므로 비용이 없다. 둘 중 하나만 있으면 강의영상.py처럼 새로 뽑는 구획으로 센다.
- 여러 파일에 같은 글이 있으면 한 번만 센다(두 과정이 같은 구획을 함께 쓸 때).
출력은 파일마다 구획 · 새 구획 · 새 글자와 새 구획의 장 번호, 끝에 합계다. 크레딧 단가는 영상.md V맥-12, 남은 크레딧은 음성키.py.
"""
import argparse
import sys

sys.dont_write_bytecode = True
import 강의영상 as tool  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("scripts", nargs="+")
ap.add_argument("--voice", required=True)
ap.add_argument("--model", default=tool.ap.get_default("model"))
ap.add_argument("--speed", type=float, default=tool.ap.get_default("speed"))
a = ap.parse_args()

seen = set()
tot_sec = tot_new = tot_ch = 0
for f in a.scripts:
    sec, new, ch, miss = 0, 0, 0, []
    for first, last, text in tool.slides_text(f):
        sec += 1
        h = tool.cache_key(text, a.voice, a.model, a.speed)
        if (tool.CACHE / f"{h}.mp3").exists() and (tool.CACHE / f"{h}.json").exists():
            continue
        if h in seen:
            continue
        seen.add(h)
        new += 1
        ch += len(text)
        miss.append(str(first) if first == last else f"{first}~{last}")
    print(f"{f}: 구획 {sec} · 새로 {new} · 글자 {ch}" + (f" · 장 {', '.join(miss)}" if miss else ""))
    tot_sec += sec
    tot_new += new
    tot_ch += ch
print(f"합계 구획 {tot_sec} · 새로 {tot_new} · 글자 {tot_ch} (음성 {a.voice} · 모델 {a.model} · 빠르기 {a.speed})")
