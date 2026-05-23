"""Assemble slideshow video: Ken Burns + crossfade + word-sync subtitles + optional music."""
import asyncio
import io
import logging
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

log = logging.getLogger("video_assembler")

FPS       = 25
TRANS_DUR = 0.5   # crossfade duration in seconds

# Ken Burns presets — cycled across images for variety
_KB_PRESETS = [
    "z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    "z='if(lte(zoom,1),1.3,max(1,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    "z='min(zoom+0.001,1.3)':x='iw-iw/zoom':y='ih/2-(ih/zoom/2)'",
    "z='min(zoom+0.001,1.3)':x='0':y='ih/2-(ih/zoom/2)'",
    "z='min(zoom+0.001,1.25)':x='iw/2-(iw/zoom/2)':y='ih-ih/zoom'",
]


# ── WAV helpers ───────────────────────────────────────────────────────────────

def wav_duration(wav_bytes: bytes) -> float:
    with io.BytesIO(wav_bytes) as f:
        with wave.open(f) as w:
            return w.getnframes() / w.getframerate()


def concat_wavs(wav_list: list[bytes]) -> bytes:
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
        if end <= start:
            end = start + 2.0
        result.append((start, end))
    return result


# ── Subtitle helpers ──────────────────────────────────────────────────────────

def _srt_time(sec: float) -> str:
    h  = int(sec // 3600)
    m  = int((sec % 3600) // 60)
    s  = int(sec % 60)
    ms = int(round((sec % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(sentences: list[str], timings: list[tuple[float, float]]) -> str:
    """Word-grouped SRT: 4 words per entry so subtitles update in real-time with speech."""
    WORDS_PER_ENTRY = 4
    blocks: list[str] = []
    idx = 1
    for sentence, (start, end) in zip(sentences, timings):
        words = sentence.split()
        if not words:
            continue
        total_chars = sum(len(w) for w in words) or 1
        dur = end - start
        t = start
        i = 0
        while i < len(words):
            group = words[i:i + WORDS_PER_ENTRY]
            group_chars = sum(len(w) for w in group)
            group_end = t + dur * group_chars / total_chars
            if i + WORDS_PER_ENTRY >= len(words):
                group_end = end
            blocks.append(
                f"{idx}\n{_srt_time(t)} --> {_srt_time(group_end)}\n{' '.join(group)}\n"
            )
            idx += 1
            t = group_end
            i += WORDS_PER_ENTRY
    return "\n".join(blocks)


# ── ffmpeg filter_complex builder ─────────────────────────────────────────────

def _build_filter_complex(
    n: int,
    display_durations: list[float],
    srt_escaped: str,
    audio_idx: int,
    music_idx: int | None,
) -> tuple[str, str, str]:
    """Returns (filter_complex_str, video_map_label, audio_map_label)."""
    parts: list[str] = []

    # Ken Burns zoompan per image
    for i in range(n):
        preset = _KB_PRESETS[i % len(_KB_PRESETS)]
        frames = max(int((display_durations[i] + TRANS_DUR) * FPS), 2)
        parts.append(
            f"[{i}:v]scale=1024:1024:force_original_aspect_ratio=increase,"
            f"crop=1024:1024,setsar=1,"
            f"zoompan={preset}:d={frames}:fps={FPS}:s=1024x1024[vkb{i}]"
        )

    # Crossfade chain
    if n == 1:
        pre_sub = "vkb0"
    else:
        cumulative = 0.0
        cur = "vkb0"
        for i in range(1, n):
            cumulative += display_durations[i - 1] - TRANS_DUR
            nxt = f"vx{i}" if i < n - 1 else "vxf"
            parts.append(
                f"[{cur}][vkb{i}]xfade=transition=fade:"
                f"duration={TRANS_DUR}:offset={max(cumulative, 0):.3f}[{nxt}]"
            )
            cur = nxt
        pre_sub = "vxf"

    # Subtitle overlay
    sub_style = (
        "FontName=Arial,FontSize=24,Bold=-1,"
        "PrimaryColour=&H00FFEF80,"
        "OutlineColour=&H00000000,Outline=2,"
        "BackColour=&H80000000,BorderStyle=3,"
        "Shadow=0,MarginV=40,Alignment=2"
    )
    parts.append(
        f"[{pre_sub}]subtitles='{srt_escaped}':force_style='{sub_style}'[vout]"
    )

    # Audio
    if music_idx is not None:
        parts.append(
            f"[{audio_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:"
            f"channel_layouts=stereo[amain];"
            f"[{music_idx}:a]volume=0.12,aformat=sample_fmts=fltp:sample_rates=44100:"
            f"channel_layouts=stereo[amusic];"
            f"[amain][amusic]amix=inputs=2:duration=first[aout]"
        )
    else:
        parts.append(
            f"[{audio_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:"
            f"channel_layouts=stereo[aout]"
        )

    return ";".join(parts), "[vout]", "[aout]"


# ── Main assembly ─────────────────────────────────────────────────────────────

def _check_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH. Install ffmpeg and retry.")
    return ffmpeg


async def assemble_video_from_clips(
    clip_data: list[bytes],
    audio_bytes: bytes,
    srt_text: str,
    fps: int = 16,
    bg_music_path: str = "",
) -> bytes:
    """Concat I2V MP4 clips, mux TTS audio, burn subtitles."""
    ffmpeg = _check_ffmpeg()

    def _run() -> bytes:
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            n = len(clip_data)

            clip_paths: list[Path] = []
            for i, clip in enumerate(clip_data):
                p = tmp / f"clip_{i:04d}.mp4"
                p.write_bytes(clip)
                clip_paths.append(p)

            audio_path = tmp / "audio.wav"
            audio_path.write_bytes(audio_bytes)
            srt_path = tmp / "subs.srt"
            srt_path.write_text(srt_text, encoding="utf-8")
            out_path = tmp / "output.mp4"

            has_music = bool(bg_music_path and Path(bg_music_path).exists())
            audio_idx = n
            music_idx = n + 1 if has_music else None

            srt_escaped = srt_path.as_posix().replace(":", "\\:")
            sub_style = (
                "FontName=Arial,FontSize=22,Bold=-1,"
                "PrimaryColour=&H00FFEF80,"
                "OutlineColour=&H00000000,Outline=2,"
                "BackColour=&H80000000,BorderStyle=3,"
                "Shadow=0,MarginV=35,Alignment=2"
            )

            parts: list[str] = []
            for i in range(n):
                parts.append(
                    f"[{i}:v]scale=832:480:"
                    f"force_original_aspect_ratio=increase,crop=832:480,setsar=1[v{i}]"
                )
            concat_in = "".join(f"[v{i}]" for i in range(n))
            parts.append(f"{concat_in}concat=n={n}:v=1:a=0[vcat]")
            parts.append(f"[vcat]fps=25[vfps]")
            parts.append(f"[vfps]subtitles='{srt_escaped}':force_style='{sub_style}'[vout]")

            if music_idx is not None:
                parts.append(
                    f"[{audio_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:"
                    f"channel_layouts=stereo[amain];"
                    f"[{music_idx}:a]volume=0.12,aformat=sample_fmts=fltp:sample_rates=44100:"
                    f"channel_layouts=stereo[amusic];"
                    f"[amain][amusic]amix=inputs=2:duration=first[aout]"
                )
            else:
                parts.append(
                    f"[{audio_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:"
                    f"channel_layouts=stereo[aout]"
                )

            fc = ";".join(parts)
            cmd = [ffmpeg, "-y"]
            for cp in clip_paths:
                cmd += ["-i", str(cp)]
            cmd += ["-i", str(audio_path)]
            if has_music:
                cmd += ["-stream_loop", "-1", "-i", bg_music_path]
            cmd += ["-filter_complex", fc]
            cmd += ["-map", "[vout]", "-map", "[aout]"]
            cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "22"]
            cmd += ["-c:a", "aac", "-b:a", "192k"]
            cmd += ["-pix_fmt", "yuv420p", "-shortest", str(out_path)]

            log.info("[VideoAssembler/I2V] start — %d clips %.1fs audio", n, wav_duration(audio_bytes))
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace")[-3000:]
                raise RuntimeError(f"ffmpeg (clips) failed:\n{err}")
            log.info("[VideoAssembler/I2V] done — %d bytes", out_path.stat().st_size)
            return out_path.read_bytes()

    return await asyncio.get_event_loop().run_in_executor(None, _run)


async def assemble_video(
    image_data: list[bytes],
    image_timings: list[tuple[float, float]],
    audio_bytes: bytes,
    srt_text: str,
    bg_music_path: str = "",
) -> bytes:
    """
    Assemble MP4 with Ken Burns zoom/pan, crossfade transitions,
    word-synced subtitles, and optional background music.
    """
    ffmpeg = _check_ffmpeg()

    def _run() -> bytes:
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            n = len(image_data)
            display_durations = [max(e - s, 1.0) for s, e in image_timings]

            # Write images
            image_paths: list[Path] = []
            for i, png in enumerate(image_data):
                p = tmp / f"img_{i:04d}.png"
                p.write_bytes(png)
                image_paths.append(p)

            # Write audio + SRT
            audio_path = tmp / "audio.wav"
            audio_path.write_bytes(audio_bytes)
            srt_path = tmp / "subs.srt"
            srt_path.write_text(srt_text, encoding="utf-8")
            out_path = tmp / "output.mp4"

            has_music = bool(bg_music_path and Path(bg_music_path).exists())
            audio_idx = n
            music_idx = n + 1 if has_music else None

            # Escape SRT path for subtitle filter (handle Windows drive colon)
            srt_pos = srt_path.as_posix()
            srt_escaped = srt_pos.replace(":", "\\:")

            fc, v_map, a_map = _build_filter_complex(
                n=n,
                display_durations=display_durations,
                srt_escaped=srt_escaped,
                audio_idx=audio_idx,
                music_idx=music_idx,
            )

            # Build command — images first, then audio, then optional music
            cmd = [ffmpeg, "-y"]
            for img_path, dur in zip(image_paths, display_durations):
                cmd += ["-loop", "1", "-t", f"{dur + TRANS_DUR:.3f}", "-i", str(img_path)]
            cmd += ["-i", str(audio_path)]
            if has_music:
                cmd += ["-stream_loop", "-1", "-i", bg_music_path]

            cmd += ["-filter_complex", fc]
            cmd += ["-map", v_map, "-map", a_map]
            cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "22"]
            cmd += ["-c:a", "aac", "-b:a", "192k"]
            cmd += ["-pix_fmt", "yuv420p", "-shortest", str(out_path)]

            log.info(
                "[VideoAssembler] start — %d images %.1fs audio music=%s",
                n, wav_duration(audio_bytes), has_music,
            )

            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace")[-3000:]
                raise RuntimeError(f"ffmpeg failed:\n{err}")

            log.info("[VideoAssembler] done — %d bytes", out_path.stat().st_size)
            return out_path.read_bytes()

    return await asyncio.get_event_loop().run_in_executor(None, _run)
