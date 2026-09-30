"""Generate Korean narration audio for every scene (edge-tts online voice, Windows SAPI Heami offline fallback)
and write docs/video/narration.md.   Run: python video/narration.py
"""
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scenes import SCENES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "video" / "audio"
VOICE = os.getenv("TTS_VOICE", "ko-KR-SunHiNeural")


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def duration(path: Path) -> float:
    out = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr or ""
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


async def edge(text: str, path: Path) -> bool:
    try:
        import edge_tts
        await edge_tts.Communicate(text, VOICE, rate="+3%").save(str(path))
        return path.exists() and path.stat().st_size > 1000
    except Exception as e:  # noqa: BLE001
        print("edge-tts failed:", e)
        return False


def sapi(text: str, path: Path) -> bool:
    """Offline fallback: Windows System.Speech (Microsoft Heami Desktop, ko-KR)."""
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'ko-KR' } | Select-Object -First 1; "
          "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; $s.Rate = 0; "
          f"$s.SetOutputToWaveFile('{path}'); $s.Speak([IO.File]::ReadAllText('{path.with_suffix('.txt')}', [Text.Encoding]::UTF8)); $s.Dispose()")
    path.with_suffix(".txt").write_text(text, encoding="utf-8")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    return path.exists() and path.stat().st_size > 1000


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    for sc in SCENES:
        mp3 = OUT / f"{sc['id']}.mp3"
        wav = OUT / f"{sc['id']}.wav"
        path = None
        if mp3.exists() and mp3.stat().st_size > 1000:
            path = mp3
        elif await edge(sc["narration"], mp3):
            path = mp3
        elif sapi(sc["narration"], wav):
            path = wav
        if not path:
            raise SystemExit(f"no TTS available for scene {sc['id']}")
        d = duration(path)
        meta[sc["id"]] = {"file": str(path.relative_to(ROOT)), "duration": round(d, 2)}
        print(f"{sc['id']:<12} {d:6.1f}s  {path.name}")
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# 설명 영상 내레이션 대본 (hyd-iot-edu)", "", f"음성: {VOICE} (edge-tts) · 장면별 오디오는 `docs/video/audio/`", ""]
    for i, sc in enumerate(SCENES, 1):
        md += [f"## {i}. {sc['id']} — {sc['caption']}", "", sc["narration"], "", f"_길이 {meta[sc['id']]['duration']} s_", ""]
    (ROOT / "docs" / "video" / "narration.md").write_text("\n".join(md), encoding="utf-8")
    print("total narration:", round(sum(m["duration"] for m in meta.values()), 1), "s")


if __name__ == "__main__":
    asyncio.run(main())
