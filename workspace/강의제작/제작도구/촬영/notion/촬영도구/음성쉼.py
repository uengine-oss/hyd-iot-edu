"""큐 안 문장 사이 쉼 늘리기(다시 사지 않음). 사용: PYTHONUTF8=1 python 음성쉼.py [source-cues-v12.json]
ElevenLabs가 한 큐 안의 문장 사이를 너무 붙여 말한다(사용자 2026-11-13 「사람이 원래 말할 때 랩처럼 말하진 않잖아요」).
산 음성(config audio)의 큐마다 silencedetect(n=-38dB, d=0.18)로 안쪽 무음(시작 0.3초 뒤, 끝 무음 제외)을 찾아 0.5초보다 짧으면
그 무음 가운데에 고요를 더해 0.5초로 만든다(사용자가 들어 승인한 맛보기 `음성맛보기_2단계_자연쉼.mp3`과 같은 값).
원본은 두고 config audio_play 폴더에 같은 이름의 mp3 · json을 쓴다. json에는 새 duration_ms와, 큐 파일의 point(마지막 문장 시작의
글자 비율)를 새 길이로 옮긴 point를 쓴다: 옛 시각 = point × 옛 길이 → 그 앞에서 늘린 몫을 더하고, 그 근처(0.6초 안) 무음이 있으면 그 무음의 끝에 맞춘다.
녹화 제어(ctrl.mjs) · preflight12 · encode.py는 audio_play를 읽는다. 큐 글이 산 음성 글과 다르면 멈춘다."""
import json, re, subprocess, sys
from pathlib import Path
from common import HERE, AUDIO, PLAY_AUDIO, ffmpeg

sys.stdout.reconfigure(encoding='utf-8')
SR, MIN_GAP, LEAD, NOISE, MIN_D = 44100, 0.5, 0.3, '-38dB', 0.18
ff = ffmpeg()


def pcm(mp3):
    return subprocess.check_output([ff, '-v', 'error', '-i', str(mp3), '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'])


def silences(mp3, dur):
    log = subprocess.run([ff, '-hide_banner', '-nostats', '-i', str(mp3), '-af', f'silencedetect=n={NOISE}:d={MIN_D}', '-f', 'null', '-'],
                         capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
    st = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', log)]
    en = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', log)]
    out = []
    for i, s in enumerate(st):
        e = en[i] if i < len(en) else dur
        if s > LEAD and e < dur - 0.02:   # 안쪽 무음만(앞 0.3초 · 끝 무음 제외)
            out.append((s, e))
    return out


def main():
    cues = json.loads((HERE / (sys.argv[1] if len(sys.argv) > 1 else 'source-cues-v12.json')).read_text(encoding='utf-8'))['cues']
    PLAY_AUDIO.mkdir(exist_ok=True)
    total_add, stretched = 0.0, 0
    for c in cues:
        src, meta = AUDIO / f"{c['id']}.mp3", AUDIO / f"{c['id']}.json"
        if not src.exists() or not meta.exists():
            raise SystemExit(f"산 음성 없음: {src} (voice.py source-cues-v12.json 먼저)")
        m = json.loads(meta.read_text(encoding='utf-8'))
        if m['text'] != c['text']:
            raise SystemExit(f"{c['id']}: 큐 글과 산 음성 글이 다름 — {meta}")
        raw = pcm(src)
        dur = len(raw) / 2 / SR
        gaps = silences(src, dur)
        cuts, add_before = [], []
        for s, e in gaps:
            need = MIN_GAP - (e - s)
            if need > 0:
                cuts.append((round((s + e) / 2 * SR), round(need * SR)))
        # 고요를 끼운 PCM
        parts, last = [], 0
        for at, n in cuts:
            parts.append(raw[last * 2:at * 2]); parts.append(b'\x00\x00' * n); last = at
        parts.append(raw[last * 2:])
        new = b''.join(parts)
        added = sum(n for _, n in cuts) / SR
        # point 옮기기
        t_old = c['point'] * dur
        shift = lambda t: t + sum(n for at, n in cuts if at / SR <= t) / SR
        near = [(s, e) for s, e in gaps if abs(e - t_old) < 0.6 or (s <= t_old <= e)]
        if near and c['point'] > 0:   # 무음 끝(다음 문장 시작)은 그 무음 안에 끼운 고요 뒤다
            t_new = shift(min(near, key=lambda g: abs(g[1] - t_old))[1])
        else:
            t_new = shift(t_old)
        dst = PLAY_AUDIO / f"{c['id']}.mp3"
        subprocess.run([ff, '-v', 'error', '-y', '-f', 's16le', '-ac', '1', '-ar', str(SR), '-i', '-', '-c:a', 'libmp3lame', '-b:a', '128k', str(dst)],
                       input=new, check=True)
        dms = round(len(pcm(dst)) / 2 / SR * 1000)
        (PLAY_AUDIO / f"{c['id']}.json").write_text(json.dumps({'id': c['id'], 'text': c['text'], 'duration_ms': dms, 'source_ms': m['duration_ms'],
            'point': round(min(t_new * 1000 / dms, 1), 3), 'added_ms': round(added * 1000), 'gaps_widened': len(cuts)}, ensure_ascii=False), encoding='utf-8')
        total_add += added; stretched += bool(cuts)
    print(json.dumps({'cues': len(cues), 'stretched': stretched, 'added_s': round(total_add, 1), 'out': str(PLAY_AUDIO)}, ensure_ascii=False))


main()
