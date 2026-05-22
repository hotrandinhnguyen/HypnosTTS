import json
import aiosqlite
from app.backend.config import DB_PATH


async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                topic      TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS lessons (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER REFERENCES sessions(id),
                sequence   INTEGER NOT NULL,
                text       TEXT NOT NULL,
                audio      BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS research_cache (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                concept    TEXT UNIQUE NOT NULL,
                data       TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS story_chapters (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT UNIQUE NOT NULL,
                story_title TEXT NOT NULL,
                chapter_title TEXT NOT NULL,
                prev_url    TEXT,
                next_url    TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS story_sentences (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id INTEGER REFERENCES story_chapters(id),
                sequence   INTEGER NOT NULL,
                text       TEXT NOT NULL,
                audio      BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS video_sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER REFERENCES sessions(id),
                topic      TEXT NOT NULL,
                video      BLOB NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()


# ── Learning session ──────────────────────────────────────────────

async def create_session(topic: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO sessions (topic) VALUES (?)", (topic,))
        await db.commit()
        return cur.lastrowid


async def save_lesson(session_id: int, sequence: int, text: str, audio: bytes):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO lessons (session_id, sequence, text, audio) VALUES (?,?,?,?)",
            (session_id, sequence, text, audio),
        )
        await db.commit()


async def get_history() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, topic, created_at FROM sessions ORDER BY created_at DESC LIMIT 30"
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_session_audio(session_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT sequence, text, audio FROM lessons WHERE session_id=? ORDER BY sequence",
            (session_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


# ── Research cache ────────────────────────────────────────────────

async def get_cached_research(concept: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT data FROM research_cache WHERE concept=?", (concept.lower().strip(),)
        )
        row = await cur.fetchone()
        return json.loads(row["data"]) if row else None


async def save_research_cache(concept: str, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO research_cache (concept, data) VALUES (?,?)
               ON CONFLICT(concept) DO UPDATE SET data=excluded.data, created_at=CURRENT_TIMESTAMP""",
            (concept.lower().strip(), json.dumps(data)),
        )
        await db.commit()


# ── Story chapter ─────────────────────────────────────────────────

async def get_cached_chapter(url: str) -> dict | None:
    """Trả về chapter đã cache (kèm audio) nếu có, None nếu chưa."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, story_title, chapter_title, prev_url, next_url FROM story_chapters WHERE url=?",
            (url,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        chapter_id = row["id"]
        cur2 = await db.execute(
            "SELECT sequence, text, audio FROM story_sentences WHERE chapter_id=? ORDER BY sequence",
            (chapter_id,),
        )
        sentences = [dict(r) for r in await cur2.fetchall()]
        return {**dict(row), "sentences": sentences}


async def save_chapter(
    url: str,
    story_title: str,
    chapter_title: str,
    prev_url: str | None,
    next_url: str | None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO story_chapters (url, story_title, chapter_title, prev_url, next_url)
               VALUES (?,?,?,?,?)
               ON CONFLICT(url) DO UPDATE SET
                 story_title=excluded.story_title,
                 chapter_title=excluded.chapter_title,
                 prev_url=excluded.prev_url,
                 next_url=excluded.next_url""",
            (url, story_title, chapter_title, prev_url, next_url),
        )
        await db.commit()
        if cur.lastrowid:
            return cur.lastrowid
        cur2 = await db.execute("SELECT id FROM story_chapters WHERE url=?", (url,))
        row = await cur2.fetchone()
        return row[0]


async def save_sentence(chapter_id: int, sequence: int, text: str, audio: bytes):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO story_sentences (chapter_id, sequence, text, audio) VALUES (?,?,?,?)",
            (chapter_id, sequence, text, audio),
        )
        await db.commit()


async def get_session_text(session_id: int) -> str:
    """Concatenate all lesson texts for a session (used as discuss context)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT text FROM lessons WHERE session_id=? ORDER BY sequence",
            (session_id,),
        )
        rows = await cur.fetchall()
        return " ".join(row[0] for row in rows)


async def save_video(session_id: int | None, topic: str, video_bytes: bytes) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO video_sessions (session_id, topic, video) VALUES (?,?,?)",
            (session_id, topic, video_bytes),
        )
        await db.commit()
        return cur.lastrowid


async def get_video(video_id: int) -> bytes | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT video FROM video_sessions WHERE id=?", (video_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def get_video_history() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, topic, created_at FROM video_sessions ORDER BY created_at DESC LIMIT 30"
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_story_history() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT id, story_title, chapter_title, url, prev_url, next_url, created_at
               FROM story_chapters ORDER BY created_at DESC LIMIT 30"""
        )
        return [dict(r) for r in await cur.fetchall()]
