"""Scraper cho truyenfull.today và fallback generic."""
import re
import logging
from urllib.parse import urlparse, urljoin

import cloudscraper
from bs4 import BeautifulSoup

log = logging.getLogger("scraper")

_HTML_PARSER = "html.parser"
_BASE_URL    = "https://truyenfull.today"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

_SITE_SELECTORS: dict[str, dict] = {
    "truyenfull.today": {
        "content": "#chapter-c",
        "title":   "h3.chapter-title a, .chapter-title a, h3.chapter-title",
        "story":   "h3.truyen-title a, a.truyen-title",
        "prev":    'a[title*="chương trước"], a[title*="Chương trước"], #prev_chap',
        "next":    'a[title*="chương sau"], a[title*="Chương sau"],  #next_chap',
    },
}

_AD_PATTERNS = re.compile(
    r"(nguồn\s*:?\s*truyenfull|vui lòng đọc tại|https?://\S+|"
    r"truyenfull\.today|hãy ủng hộ|đọc tiếp tại|follow\s+us)",
    re.IGNORECASE,
)

_SENT_SPLIT  = re.compile(r'(?<=[.!?…])\s+(?=[^\s])')
_CHAP_NUM_RE = re.compile(r"chuong-(\d+)")


def _domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def _make_scraper():
    s = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows"})
    s.headers.update(_HEADERS)
    return s


def _fetch_soup(url: str, timeout: int = 20) -> BeautifulSoup:
    resp = _make_scraper().get(url, timeout=timeout)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, _HTML_PARSER)


def _sel_text(soup: BeautifulSoup, css: str) -> str:
    el = soup.select_one(css) if css else None
    return el.get_text(strip=True) if el else ""


def _parse_nav_link(soup: BeautifulSoup, css: str, base: str) -> str | None:
    if not css:
        return None
    el = soup.select_one(css)
    if not el:
        return None
    href = el.get("href", "")
    if not href:
        return None
    return href if href.startswith("http") else urljoin(base, href)


def _parse_max_pagination(soup: BeautifulSoup) -> int:
    total = 1
    for el in soup.select(".pagination li a[href]"):
        try:
            pg = int(el.get_text(strip=True))
            if pg > total:
                total = pg
        except ValueError:
            pass
    return total


def scrape_chapter(url: str) -> dict:
    """Trả về dict: title, story_title, sentences, prev_url, next_url."""
    log.info("Scraping %s", url)
    parsed = urlparse(url)
    base   = f"{parsed.scheme}://{parsed.netloc}"
    soup   = _fetch_soup(url, timeout=20)
    sel    = _SITE_SELECTORS.get(_domain(url), {})

    title       = _sel_text(soup, sel.get("title", "")) or _guess_title(soup)
    story_title = _sel_text(soup, sel.get("story", ""))

    content_el = soup.select_one(sel.get("content", "")) if sel.get("content") else None
    if content_el is None:
        content_el = _find_main_content(soup)
    if content_el is None:
        raise ValueError("Không tìm thấy nội dung chương — thử URL khác.")

    sentences = _extract_sentences(content_el.get_text(separator="\n"))
    if not sentences:
        raise ValueError("Nội dung chương trống sau khi làm sạch.")

    prev_url = _parse_nav_link(soup, sel.get("prev", ""), base)
    next_url = _parse_nav_link(soup, sel.get("next", ""), base)

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
        if len(line) < 4 or _AD_PATTERNS.search(line):
            continue
        for part in _SENT_SPLIT.split(line):
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


def search_stories(query: str, base: str = _BASE_URL) -> list[dict]:
    """Tìm kiếm truyện, trả về [{title, slug, latest_chapter, cover}]."""
    url  = f"{base}/tim-kiem/?tukhoa={query.replace(' ', '+')}"
    log.info("Searching: %s", url)
    soup = _fetch_soup(url, timeout=15)
    items   = soup.select("div.list-truyen .row, .list-truyen div[itemscope]")
    results = [r for item in items if (r := _parse_story_item(item, base))]
    log.info("Found %d results for %r", len(results), query)
    return results


def build_chapter_url(slug: str, chapter: int, base: str = _BASE_URL) -> str:
    return f"{base}/{slug}/chuong-{chapter}/"


def _parse_chapter_links(soup: BeautifulSoup, slug: str, base: str) -> list[dict]:
    chapters: list[dict] = []
    seen: set[int] = set()
    for a in soup.select("ul.list-chapter li a, .list-chapter a"):
        href  = a.get("href", "")
        m     = _CHAP_NUM_RE.search(href)
        num   = int(m.group(1)) if m else 0
        if num and num not in seen:
            seen.add(num)
            chapters.append({
                "num":   num,
                "title": a.get_text(strip=True),
                "url":   href if href.startswith("http") else f"{base}/{slug}/chuong-{num}/",
            })
    chapters.sort(key=lambda c: c["num"])
    return chapters


def get_chapter_list(slug: str, page: int = 1, base: str = _BASE_URL) -> dict:
    """Trả về {chapters: [{num, title, url}], total_pages, current_page}."""
    url  = f"{base}/{slug}/" if page == 1 else f"{base}/{slug}/trang-{page}/"
    log.info("Fetching chapter list page %d: %s", page, url)
    soup = _fetch_soup(url, timeout=15)

    chapters    = _parse_chapter_links(soup, slug, base)
    total_pages = _parse_max_pagination(soup)

    log.info("Chapter list: %d chapters, %d total pages", len(chapters), total_pages)
    return {"chapters": chapters, "total_pages": total_pages, "current_page": page}


def _find_main_content(soup: BeautifulSoup):
    """Heuristic: div/article có nhiều text nhất."""
    best, best_len = None, 0
    for el in soup.find_all(["div", "article"]):
        length = len(el.get_text())
        if length > best_len:
            best_len = length
            best = el
    return best
