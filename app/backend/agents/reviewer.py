import re
import logging

from app.backend.state import GraphState

log = logging.getLogger("reviewer")

_MARKDOWN_RE = re.compile(r"(?:^|\s)[*#]{1,3}|^\s*[-*]\s|\*\*", re.MULTILINE)
_NUMBERED_LIST_RE = re.compile(r"^\s*\d+\.\s", re.MULTILINE)
_LONG_SENTENCE_RE = re.compile(r"[^.!?\n]{160,}")

MIN_WORDS = 2000
MAX_LONG_SENTENCES = 3


def _word_count(text: str) -> int:
    return len(text.split())


def _check_length(script: str) -> str | None:
    wc = _word_count(script)
    if wc < MIN_WORDS:
        return f"Quá ngắn: {wc} từ (cần ít nhất {MIN_WORDS} từ). Mở rộng nội dung, đào sâu hơn."
    return None


def _check_markdown(script: str) -> str | None:
    if _MARKDOWN_RE.search(script):
        return "Có ký tự markdown (*, #, -, **). Xóa toàn bộ ký hiệu định dạng."
    return None


def _check_numbered_lists(script: str) -> str | None:
    if _NUMBERED_LIST_RE.search(script):
        return "Có danh sách đánh số (1. 2. 3.). Viết lại thành đoạn văn nói liên tục."
    return None


def _check_sentence_length(script: str) -> str | None:
    matches = _LONG_SENTENCE_RE.findall(script)
    if len(matches) > MAX_LONG_SENTENCES:
        return (
            f"Có {len(matches)} đoạn câu quá dài (>160 ký tự liên tiếp không có dấu ngắt). "
            "Chia nhỏ câu, mỗi câu dưới 35 từ."
        )
    return None


def _check_topic_mentioned(script: str, topic: str) -> str | None:
    topic_words = [w.lower() for w in topic.split() if len(w) > 3]
    script_lower = script.lower()
    if topic_words and not any(w in script_lower for w in topic_words):
        return f"Không đề cập đến chủ đề '{topic}'. Đảm bảo chủ đề được nhắc đến rõ ràng."
    return None


def _check_analogy_used(script: str, analogy: dict) -> str | None:
    if not analogy:
        return None
    analogy_keywords: list[str] = []
    for field in ("image", "scenario", "mapping"):
        text = analogy.get(field, "")
        words = [w.lower() for w in text.split() if len(w) > 4]
        analogy_keywords.extend(words[:5])

    if not analogy_keywords:
        return None

    script_lower = script.lower()
    if not any(kw in script_lower for kw in analogy_keywords):
        return "Chưa dùng phép ẩn dụ đã chuẩn bị. Lồng ghép ít nhất một trong 3 phép ẩn dụ vào phần giải thích cơ chế."
    return None


def reviewer_node(state: GraphState) -> dict:
    script = state.get("script", "")
    topic = state["topic"]
    analogy = state.get("analogy") or {}
    revision_count = state.get("revision_count", 0)

    log.info("[Reviewer] START revision=%d, script_len=%d", revision_count, len(script))

    checks = [
        _check_length(script),
        _check_markdown(script),
        _check_numbered_lists(script),
        _check_sentence_length(script),
        _check_topic_mentioned(script, topic),
        _check_analogy_used(script, analogy),
    ]

    issues = [c for c in checks if c is not None]
    passed = len(issues) == 0

    suggestion = ""
    if issues:
        suggestion = "Ưu tiên sửa: " + issues[0]

    review = {"passed": passed, "issues": issues, "suggestion": suggestion}
    new_revision_count = revision_count + (0 if passed else 1)

    if passed:
        log.info("[Reviewer] PASSED")
    else:
        log.info("[Reviewer] FAILED — %d issues, new revision_count=%d", len(issues), new_revision_count)

    return {"review": review, "revision_count": new_revision_count, "status": "reviewed"}
