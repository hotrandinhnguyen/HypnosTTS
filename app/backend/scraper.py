"""Scraper cho truyenfull.today và fallback generic."""
import re
import logging
from urllib.parse import urlparse, urljoin

import cloudscraper
from bs4 import BeautifulSoup

log = logging.getLogger("scraper")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

# Selector cho từng trang — thêm vào đây nếu muốn hỗ trợ trang mới
_SITE_SELECTORS: dict[str, dict] = {
    "truyenfull.today": {
        "content": "#chapter-c",
        "title":   "h3.chapter-title a, .chapter-title a, h3.chapter-title",
        "story":   "h3.truyen-title a, a.truyen-title",
        "prev":    'a[title*="chương trước"], a[title*="Chương trước"], #prev_chap',
        "next":    'a[title*="chương sau"], a[title*="Chương sau"],  #next_chap',
    },
}

# Pattern quảng cáo / watermark thường thấy trong truyện Việt
_AD_PATTERNS = re.compile(
    r"(nguồn\s*:?\s*truyenfull|vui lòng đọc tại|https?://\S+|"
    r"truyenfull\.today|hãy ủng hộ|đọc tiếp tại|follow\s+us)",
    re.IGNORECASE,
)

# Tách câu: dừng ở . ? ! … nhưng không tách Mr./Dr./số thập phân
_SENT_SPLIT = re.compile(r'(?<=[.!?…])\s+(?=[^\s])')


def _domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def _make_scraper():
    s = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows"})
    s.headers.update(_HEADERS)
    return s


def scrape_chapter(url: str) -> dict:
    """Trả về dict: title, story_title, sentences, prev_url, next_url."""
    log.info("Scraping %s", url)
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    s = _make_scraper()
    resp = s.get(url, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    sel  = _SITE_SELECTORS.get(_domain(url), {})

    # ── Title ──────────────────────────────────────────────────
    title_el = soup.select_one(sel.get("title", "")) if sel.get("title") else None
    title = title_el.get_text(strip=True) if title_el else _guess_title(soup)

    story_el = soup.select_one(sel.get("story", "")) if sel.get("story") else None
    story_title = story_el.get_text(strip=True) if story_el else ""

    # ── Content ────────────────────────────────────────────────
    content_el = soup.select_one(sel.get("content", "")) if sel.get("content") else None
    if content_el is None:
        content_el = _find_main_content(soup)
    if content_el is None:
        raise ValueError("Không tìm thấy nội dung chương — thử URL khác.")

    raw = content_el.get_text(separator="\n")
    sentences = _extract_sentences(raw)
    if not sentences:
        raise ValueError("Nội dung chương trống sau khi làm sạch.")

    # ── Prev / Next ────────────────────────────────────────────
    def _nav(css: str) -> str | None:
        if not css:
            return None
        el = soup.select_one(css)
        if el and el.get("href"):
            href = el["href"]
            return href if href.startswith("http") else urljoin(base, href)
        return None

    prev_url = _nav(sel.get("prev", ""))
    next_url = _nav(sel.get("next", ""))

    log.info("Scraped %d sentences | prev=%s | next=%s", len(sentences), prev_url, next_url)
    return {
        "title":       title,
        "story_title": story_title,
        "sentences":   sentences,
        "prev_url":    prev_url,
        "next_url":    next_url,
        "url":         url,
    }


def _extract_sentences(raw: str) -> list[str]:
    sentences: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or len(line) < 4:
            continue
        # Bỏ dòng quảng cáo
        if _AD_PATTERNS.search(line):
            continue
        # Tách câu trong dòng
        parts = _SENT_SPLIT.split(line)
        for part in parts:
            part = part.strip()
            if len(part) >= 4:
                sentences.append(part)
    return sentences


def _guess_title(soup: BeautifulSoup) -> str:
    for tag in ("h1", "h2", "h3"):
        el = soup.find(tag)
        if el:
            return el.get_text(strip=True)
    return "Chương truyện"


def _parse_story_item(item, base: str) -> dict | None:
    title_el = item.select_one("h3.truyen-title a, .truyen-title a")
    if not title_el:
        return None
    cover_el = item.select_one("img")
    chap_el  = item.select_one("a.chapter-title, .text-info a")
    href     = title_el.get("href", "")
    slug     = href.rstrip("/").split("/")[-1]
    return {
        "title":          title_el.get_text(strip=True),
        "slug":           slug,
        "url":            href if href.startswith("http") else f"{base}/{slug}/",
        "latest_chapter": chap_el.get_text(strip=True) if chap_el else "",
        "cover":          cover_el.get("src", "") if cover_el else "",
    }


def search_stories(query: str, base: str = "https://truyenfull.today") -> list[dict]:
    """Tìm kiếm truyện trên truyenfull.today, trả về [{title, slug, latest_chapter, cover}]."""
    url = f"{base}/tim-kiem/?tukhoa={query.replace(' ', '+')}"
    log.info("Searching: %s", url)

    s = _make_scraper()
    resp = s.get(url, timeout=15)
    resp.raise_for_status()

    soup    = BeautifulSoup(resp.text, "html.parser")
    items   = soup.select("div.list-truyen .row, .list-truyen div[itemscope]")
    results = [r for item in items if (r := _parse_story_item(item, base))]
    log.info("Found %d results for %r", len(results), query)
    return results


def build_chapter_url(slug: str, chapter: int, base: str = "https://truyenfull.today") -> str:
    return f"{base}/{slug}/chuong-{chapter}/"


def _find_main_content(soup: BeautifulSoup):
    """Heuristic: div/article có nhiều text nhất."""
    best, best_len = None, 0
    for el in soup.find_all(["div", "article"]):
        length = len(el.get_text())
        if length > best_len:
            best_len = length
            best = el
    return best
