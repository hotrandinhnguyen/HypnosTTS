"""Assemble slideshow video from images + audio using ffmpeg."""
import asyncio
import io
import logging
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

log = logging.getLogger("video_assembler")


# ── WAV helpers ───────────────────────────────────────────────────────────────

def wav_duration(wav_bytes: bytes) -> float:
    with io.BytesIO(wav_bytes) as f:
        with wave.open(f) as w:
            return w.getnframes() / w.getframerate()


def concat_wavs(wav_list: list[bytes]) -> bytes:
    """Concatenate multiple WAV buffers into one WAV file."""
    out = io.BytesIO()
    with wave.open(out, "wb") as out_wav:
        params_set = False
        for wav_bytes in wav_list:
            with io.BytesIO(wav_bytes) as f:
                with wave.open(f) as w:
                    if not params_set:
                        out_wav.setparams(w.getparams())
                        params_set = True
                    out_wav.writeframes(w.readframes(w.getnframes()))
    return out.getvalue()


# ── Timing helpers ────────────────────────────────────────────────────────────

def compute_sentence_timings(tts_wavs: list[bytes]) -> list[tuple[float, float]]:
    """Return (start_sec, end_sec) for each sentence."""
    timings: list[tuple[float, float]] = []
    t = 0.0
    for wav in tts_wavs:
        dur = wav_duration(wav)
        timings.append((t, t + dur))
        t += dur
    return timings


def map_image_timings(
    image_prompts: list[dict],
    sentence_timings: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """For each image, compute (start_sec, end_sec) based on sentence_index ranges."""
    n = len(sentence_timings)
    result: list[tuple[float, float]] = []
    for i, p in enumerate(image_prompts):
        s_idx = min(p["sentence_index"], n - 1)
        if i + 1 < len(image_prompts):
            e_idx = min(image_prompts[i + 1]["sentence_index"], n - 1)
        else:
            e_idx = n - 1
        start = sentence_timings[s_idx][0]
        end   = sentence_timings[e_idx][1]
        # Ensure positive duration (at least 2 seconds)
        if end <= start:
            end = start + 2.0
        result.append((start, end))
    return result


# ── SRT subtitle helpers ──────────────────────────────────────────────────────

def _srt_time(sec: float) -> str:
    h  = int(sec // 3600)
    m  = int((sec % 3600) // 60)
    s  = int(sec % 60)
    ms = int(round((sec % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(sentences: list[str], timings: list[tuple[float, float]]) -> str:
    blocks: list[str] = []
    for i, (text, (start, end)) in enumerate(zip(sentences, timings), 1):
        blocks.append(f"{i}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
    return "\n".join(blocks)


# ── ffmpeg assembly ───────────────────────────────────────────────────────────

def _check_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg không tìm thấy trong PATH. Cài ffmpeg rồi thử lại.")
    return ffmpeg


def _write_concat_file(
    tmpdir: Path,
    image_paths: list[Path],
    image_timings: list[tuple[float, float]],
) -> Path:
    lines: list[str] = []
    for img_path, (start, end) in zip(image_paths, image_timings):
        dur = max(end - start, 0.1)
        lines.append(f"file '{img_path.as_posix()}'")
        lines.append(f"duration {dur:.3f}")

    # ffmpeg concat: repeat last frame to avoid black flash at end
    if image_paths:
        lines.append(f"file '{image_paths[-1].as_posix()}'")

    concat_path = tmpdir / "images.txt"
    concat_path.write_text("\n".join(lines), encoding="utf-8")
    return concat_path


async def assemble_video(
    image_data: list[bytes],
    image_timings: list[tuple[float, float]],
    audio_bytes: bytes,
    srt_text: str,
) -> bytes:
    """
    Assemble MP4 from PNG images + WAV audio + SRT subtitles.
    Returns MP4 bytes.
    """
    ffmpeg = _check_ffmpeg()

    def _run() -> bytes:
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)

            # Write images
            image_paths: list[Path] = []
            for i, png in enumerate(image_data):
                p = tmp / f"img_{i:04d}.png"
                p.write_bytes(png)
                image_paths.append(p)

            # Write concat list
            concat_path = _write_concat_file(tmp, image_paths, image_timings)

            # Write audio
            audio_path = tmp / "audio.wav"
            audio_path.write_bytes(audio_bytes)

            # Write SRT
            srt_path = tmp / "subs.srt"
            srt_path.write_text(srt_text, encoding="utf-8")

            # Output
            out_path = tmp / "output.mp4"

            # Build subtitle filter string
            srt_escaped = srt_path.as_posix().replace("\\", "/").replace(":", "\\:")
            sub_filter = (
                f"subtitles='{srt_escaped}'"
                ":force_style='FontName=Arial,FontSize=15,"
                "PrimaryColour=&H00FFEF80,"
                "OutlineColour=&H00000000,Outline=2,"
                "BackColour=&H70000000,BorderStyle=3,"
                "Shadow=0,MarginV=28,Alignment=2'"
            )

            cmd = [
                ffmpeg, "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_path),
                "-i", str(audio_path),
                "-vf", sub_filter,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(out_path),
            ]

            log.info("[VideoAssembler] running ffmpeg: %d images, audio=%.1fs",
                     len(image_data), wav_duration(audio_bytes))

            result = subprocess.run(
                cmd, capture_output=True, timeout=300,
            )
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace")[-2000:]
                raise RuntimeError(f"ffmpeg failed:\n{err}")

            log.info("[VideoAssembler] done — %d bytes", out_path.stat().st_size)
            return out_path.read_bytes()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)
