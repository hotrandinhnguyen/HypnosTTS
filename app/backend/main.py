import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.backend.config import TTS_INSTRUCT, VOICE_PRESETS
from app.backend.db import (
    init_db,
    create_session, save_lesson, get_history, get_session_audio, get_session_text,
    get_cached_chapter, save_chapter, save_sentence, get_story_history,
    save_video, get_video, get_video_history,
)
from app.backend.pipeline import run
from app.backend.story_pipeline import run_story
from app.backend.video_pipeline import run_video
from app.backend.discuss_pipeline import run_discuss

log = logging.getLogger("main")
FRONTEND_DIR = Path(__file__).parents[1] / "frontend" / "dist"

app = FastAPI()

_bg_tasks: set = set()


@app.on_event("startup")
async def startup():
    await init_db()
    task = asyncio.create_task(_warmup_tts())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def _warmup_tts():
    from app.backend.pipeline import _executor
    import app.backend.tts_engine as tts_engine

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            _executor,
            lambda: tts_engine._build_voice_prompt(TTS_INSTRUCT),
        )
        log.info("TTS warmup done — VoiceClonePrompt sẵn sàng")
    except Exception as e:
        log.warning("TTS warmup failed: %s", e)


async def _wait_disconnect(ws: WebSocket) -> None:
    """Chờ cho đến khi client đóng kết nối."""
    try:
        await ws.receive_text()
    except Exception:
        pass


async def _run_with_cancel(process_coro, ws: WebSocket) -> None:
    """Chạy process_coro song song với watcher disconnect; cancel ngay khi client ngắt."""
    process_task = asyncio.create_task(process_coro)
    disconnect_task = asyncio.create_task(_wait_disconnect(ws))

    done, pending = await asyncio.wait(
        {process_task, disconnect_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
        t.cancel()
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass

    # Re-raise exception từ process_task nếu có
    if process_task in done and not process_task.cancelled():
        exc = process_task.exception()
        if exc:
            raise exc


# ── Lesson pipeline ────────────────────────────────────────────────

async def _process_lesson(ws: WebSocket, topic: str, instruct: str) -> None:
    session_id = await create_session(topic)
    seq = 0
    async for event in run(topic, instruct):
        if event["type"] == "status":
            log.info("STATUS: %s", event["data"])
            await ws.send_text(json.dumps({"type": "status", "data": event["data"]}))
        elif event["type"] == "text":
            text, audio = event["data"], event["audio"]
            await save_lesson(session_id, seq, text, audio)
            log.info("SEND #%d | %d bytes | %r", seq, len(audio), text[:60])
            seq += 1
            await ws.send_text(json.dumps({"type": "text", "data": text}))
            await ws.send_bytes(audio)
        elif event["type"] == "done":
            log.info("Session done | id=%d | total=%d", session_id, seq)
            await ws.send_text(json.dumps({"type": "done", "session_id": session_id}))


@app.websocket("/ws/lesson")
async def ws_lesson(ws: WebSocket):
    await ws.accept()
    log.info("WS connected from %s", ws.client)
    try:
        raw = await ws.receive_text()
        data = json.loads(raw)
        topic: str = data.get("topic", "").strip()
        instruct: str = data.get("instruct", TTS_INSTRUCT).strip() or TTS_INSTRUCT

        if not topic:
            await ws.send_text(json.dumps({"type": "error", "data": "Topic không được trống."}))
            return

        log.info("New session | topic=%r | instruct=%r", topic, instruct)
        await _run_with_cancel(_process_lesson(ws, topic, instruct), ws)

    except WebSocketDisconnect:
        log.info("WS disconnected from %s", ws.client)
    except Exception as e:
        log.exception("WS error: %s", e)
        try:
            await ws.send_text(json.dumps({"type": "error", "data": str(e)}))
        except Exception:
            pass


# ── Video pipeline ─────────────────────────────────────────────────

async def _process_video(ws: WebSocket, topic: str, instruct: str, n_images: int = 0, duration_minutes: int = 0, video_mode: str = "i2v") -> None:
    session_id = await create_session(topic)
    async for event in run_video(topic, instruct, n_images=n_images, duration_minutes=duration_minutes, video_mode=video_mode):
        if event["type"] == "status":
            log.info("VIDEO STATUS: %s", event["data"])
            await ws.send_text(json.dumps({"type": "status", "data": event["data"]}))
        elif event["type"] == "video_done":
            video_bytes: bytes = event["video"]
            video_id = await save_video(session_id, topic, video_bytes)
            log.info("VIDEO DONE | id=%d | %d bytes", video_id, len(video_bytes))
            await ws.send_text(json.dumps({"type": "video_done", "video_id": video_id}))
        elif event["type"] == "error":
            await ws.send_text(json.dumps({"type": "error", "data": event["data"]}))


@app.websocket("/ws/video")
async def ws_video(ws: WebSocket):
    await ws.accept()
    log.info("WS/video connected from %s", ws.client)
    try:
        raw = await ws.receive_text()
        data = json.loads(raw)
        topic: str = data.get("topic", "").strip()
        instruct: str = data.get("instruct", TTS_INSTRUCT).strip() or TTS_INSTRUCT
        n_images: int        = int(data.get("n_images", 0))
        duration_minutes: int = int(data.get("duration_minutes", 0))
        video_mode: str       = data.get("video_mode", "i2v")

        if not topic:
            await ws.send_text(json.dumps({"type": "error", "data": "Topic không được trống."}))
            return

        log.info("Video session | topic=%r | n_images=%d | duration=%dmin | mode=%s",
                 topic, n_images, duration_minutes, video_mode)
        await _run_with_cancel(
            _process_video(ws, topic, instruct, n_images=n_images, duration_minutes=duration_minutes, video_mode=video_mode), ws
        )

    except WebSocketDisconnect:
        log.info("WS/video disconnected")
    except Exception as e:
        log.exception("WS/video error: %s", e)
        try:
            await ws.send_text(json.dumps({"type": "error", "data": str(e)}))
        except Exception:
            pass


# ── Story pipeline ─────────────────────────────────────────────────

async def _process_story(ws: WebSocket, url: str, instruct: str) -> None:
    cached = await get_cached_chapter(url)
    if cached:
        log.info("Cache hit | url=%s | %d sentences", url, len(cached["sentences"]))
        await ws.send_text(json.dumps({
            "type":   "chapter_info",
            "title":  cached["chapter_title"],
            "story":  cached["story_title"],
            "prev":   cached["prev_url"],
            "next":   cached["next_url"],
            "cached": True,
        }))
        audio_map = {s["sequence"]: s["audio"] for s in cached["sentences"]}
        for s in cached["sentences"]:
            await ws.send_text(json.dumps({"type": "text", "data": s["text"]}))
            await ws.send_bytes(audio_map[s["sequence"]])
        await ws.send_text(json.dumps({"type": "done"}))
        return

    await ws.send_text(json.dumps({"type": "status", "data": "Đang tải chương..."}))
    from app.backend.scraper import scrape_chapter
    loop = asyncio.get_event_loop()
    try:
        chapter = await asyncio.wait_for(
            loop.run_in_executor(None, scrape_chapter, url),
            timeout=30,
        )
    except asyncio.TimeoutError:
        raise ValueError("Tải trang quá lâu — thử lại sau.")

    await ws.send_text(json.dumps({
        "type":   "chapter_info",
        "title":  chapter["title"],
        "story":  chapter["story_title"],
        "prev":   chapter["prev_url"],
        "next":   chapter["next_url"],
        "cached": False,
    }))
    await ws.send_text(json.dumps({"type": "status", "data": "Đang render giọng đọc..."}))

    chapter_id = await save_chapter(
        url, chapter["story_title"], chapter["title"],
        chapter["prev_url"], chapter["next_url"],
    )

    seq = 0
    async for event in run_story(chapter["sentences"], instruct):
        if event["type"] == "text":
            await save_sentence(chapter_id, seq, event["data"], event["audio"])
            log.info("STORY SEND #%d | %r", seq, event["data"][:60])
            seq += 1
            await ws.send_text(json.dumps({"type": "text", "data": event["data"]}))
            await ws.send_bytes(event["audio"])
        elif event["type"] == "done":
            await ws.send_text(json.dumps({"type": "done"}))


@app.websocket("/ws/story")
async def ws_story(ws: WebSocket):
    await ws.accept()
    log.info("WS/story connected from %s", ws.client)
    try:
        raw = await ws.receive_text()
        data = json.loads(raw)
        url: str = data.get("url", "").strip()
        instruct: str = data.get("instruct", TTS_INSTRUCT).strip() or TTS_INSTRUCT

        if not url:
            await ws.send_text(json.dumps({"type": "error", "data": "URL không được trống."}))
            return

        await _run_with_cancel(_process_story(ws, url, instruct), ws)

    except WebSocketDisconnect:
        log.info("WS/story disconnected")
    except Exception as e:
        log.exception("WS/story error: %s", e)
        try:
            await ws.send_text(json.dumps({"type": "error", "data": str(e)}))
        except Exception:
            pass


# ── Discuss pipeline ───────────────────────────────────────────────

@app.websocket("/ws/discuss")
async def ws_discuss(ws: WebSocket):
    await ws.accept()
    log.info("WS/discuss connected from %s", ws.client)
    try:
        raw = await ws.receive_text()
        data = json.loads(raw)
        session_id: int | None = data.get("session_id")
        question: str = data.get("question", "").strip()
        history: list   = data.get("history", [])
        instruct: str   = data.get("instruct", TTS_INSTRUCT).strip() or TTS_INSTRUCT

        if not question or not session_id:
            await ws.send_text(json.dumps({"type": "error", "data": "Thiếu câu hỏi hoặc session."}))
            return

        script = await get_session_text(int(session_id))
        if not script:
            await ws.send_text(json.dumps({"type": "error", "data": "Không tìm thấy nội dung bài giảng."}))
            return

        log.info("Discuss | session=%d | question=%r", session_id, question[:60])

        async for event in run_discuss(script, history, question, instruct):
            if event["type"] == "text":
                await ws.send_text(json.dumps({"type": "text", "data": event["data"]}))
                await ws.send_bytes(event["audio"])
            elif event["type"] in ("done", "error"):
                await ws.send_text(json.dumps(event))

    except WebSocketDisconnect:
        log.info("WS/discuss disconnected")
    except Exception as e:
        log.exception("WS/discuss error: %s", e)
        try:
            await ws.send_text(json.dumps({"type": "error", "data": str(e)}))
        except Exception:
            pass


# ── REST endpoints ─────────────────────────────────────────────────

@app.get("/api/story/history")
async def story_history():
    return JSONResponse(await get_story_history())


@app.get("/api/story/search")
async def story_search(q: str = ""):
    if not q.strip():
        return JSONResponse([])
    from app.backend.scraper import search_stories
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, search_stories, q.strip())
    return JSONResponse(results)


@app.get("/api/story/chapters")
async def story_chapters(slug: str = "", page: int = 1):
    if not slug.strip():
        return JSONResponse({"chapters": [], "total_pages": 0, "current_page": 1})
    from app.backend.scraper import get_chapter_list
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, get_chapter_list, slug.strip(), page),
            timeout=15,
        )
        return JSONResponse(result)
    except Exception as e:
        log.warning("Chapter list failed for %r: %s", slug, e)
        return JSONResponse({"chapters": [], "total_pages": 0, "current_page": page})


@app.get("/api/video/{video_id}")
async def download_video(video_id: int):
    mp4 = await get_video(video_id)
    if mp4 is None:
        return JSONResponse({"error": "Video không tồn tại."}, status_code=404)
    return Response(
        content=mp4,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="hypnos_{video_id}.mp4"'},
    )


@app.get("/api/video/history")
async def video_history():
    return JSONResponse(await get_video_history())


@app.get("/api/voices")
async def voices():
    return JSONResponse([
        {"key": k, "label": _voice_label(k), "instruct": v}
        for k, v in VOICE_PRESETS.items()
    ])


def _voice_label(key: str) -> str:
    labels = {
        "male_mid":     "Nam - Trung niên",
        "male_young":   "Nam - Trẻ",
        "male_deep":    "Nam - Trầm",
        "female_warm":  "Nữ - Ấm áp",
        "female_young": "Nữ - Trẻ",
        "elderly":      "Nam - Lớn tuổi",
    }
    return labels.get(key, key)


@app.get("/api/history")
async def history():
    return JSONResponse(await get_history())


@app.get("/api/session/{session_id}")
async def session_audio(session_id: int):
    import base64
    lessons = await get_session_audio(session_id)
    return JSONResponse([
        {"sequence": l["sequence"], "text": l["text"],
         "audio": base64.b64encode(l["audio"]).decode()}
        for l in lessons
    ])


@app.get("/api/test-tts")
async def test_tts():
    from concurrent.futures import ThreadPoolExecutor
    import app.backend.tts_engine as tts_engine
    loop = asyncio.get_event_loop()
    wav = await loop.run_in_executor(
        ThreadPoolExecutor(max_workers=1),
        lambda: tts_engine.synthesize("Xin chào, đây là bài kiểm tra.", instruct=TTS_INSTRUCT),
    )
    return Response(content=wav, media_type="audio/wav")


@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
