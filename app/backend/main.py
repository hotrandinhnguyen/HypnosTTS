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
    create_session, save_lesson, get_history, get_session_audio,
    get_cached_chapter, save_chapter, save_sentence, get_story_history,
)
from app.backend.pipeline import run
from app.backend.story_pipeline import run_story

log = logging.getLogger("main")
FRONTEND_DIR = Path(__file__).parents[1] / "frontend"

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


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
