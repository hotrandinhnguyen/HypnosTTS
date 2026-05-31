import { useEffect, useState } from 'react'
import { BookOpen, ChevronLeft, ChevronRight, Play, Search, Square } from 'lucide-react'
import { Button } from './ui/button'

export interface StoryResult {
  title: string
  slug: string
  latest_chapter?: string
  cover?: string
}

interface ChapterItem {
  num: number
  title: string
  url: string
}

interface StorySearchProps {
  isActive: boolean
  onStartSession: (url: string) => void
  onStop: () => void
}

const _DIGIT_RE = /\d+/
const _URL_RE = /truyenfull\.today\/[^/]+\/chuong-\d+/

function parseMaxChapter(latest: string | undefined): number | null {
  if (!latest) return null
  const m = _DIGIT_RE.exec(latest)
  return m ? Number.parseInt(m[0], 10) : null
}

export function StorySearch({ isActive, onStartSession, onStop }: Readonly<StorySearchProps>) {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState<StoryResult[]>([])
  const [showResults, setShowResults] = useState(false)
  const [selected, setSelected] = useState<StoryResult | null>(null)
  const [chapterNum, setChapterNum] = useState(1)

  const [chapters, setChapters] = useState<ChapterItem[]>([])
  const [chapPage, setChapPage] = useState(1)
  const [chapTotalPages, setChapTotalPages] = useState(1)
  const [loadingChaps, setLoadingChaps] = useState(false)
  const [showChapters, setShowChapters] = useState(false)

  useEffect(() => {
    if (!selected) {
      setChapters([])
      return
    }
    let cancelled = false
    setLoadingChaps(true)
    fetch(`/api/story/chapters?slug=${encodeURIComponent(selected.slug)}&page=${chapPage}`)
      .then(r => r.json())
      .then((data: { chapters: ChapterItem[]; total_pages: number }) => {
        if (cancelled) return
        setChapters(data.chapters)
        setChapTotalPages(data.total_pages || 1)
        setLoadingChaps(false)
      })
      .catch(() => {
        if (!cancelled) setLoadingChaps(false)
      })
    return () => { cancelled = true }
  }, [selected, chapPage])

  async function doSearch() {
    const q = query.trim()
    if (!q) return

    if (_URL_RE.test(q) || q.startsWith('http')) {
      onStartSession(q)
      return
    }

    setSearching(true)
    setSelected(null)
    setChapters([])
    setShowChapters(false)
    try {
      const res = await fetch(`/api/story/search?q=${encodeURIComponent(q)}`)
      const data: StoryResult[] = await res.json()
      setResults(data)
      setShowResults(true)
    } catch (e) {
      console.error('[Search]', e)
    }
    setSearching(false)
  }

  function handleSelectStory(r: StoryResult) {
    setSelected(r)
    setChapPage(1)
    setShowChapters(false)
    const max = parseMaxChapter(r.latest_chapter)
    if (max) setChapterNum(max)
  }

  function handleStartWithNum() {
    if (!selected) return
    const url = `https://truyenfull.today/${selected.slug}/chuong-${chapterNum}/`
    setShowResults(false)
    onStartSession(url)
  }

  function handleStartChapter(url: string) {
    setShowResults(false)
    onStartSession(url)
  }

  const maxChapter = parseMaxChapter(selected?.latest_chapter)
  let chapBtnLabel = 'Danh sách chương'
  if (loadingChaps) chapBtnLabel = 'Đang tải...'
  else if (showChapters) chapBtnLabel = 'Ẩn chương'

  return (
    <div className="story-workspace">
      <div className="command-row">
        <div className="input-wrapper">
          <Search size={16} className="input-icon" />
          <input
            className="glass-input"
            placeholder="Tên truyện hoặc dán link chương trực tiếp..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') doSearch() }}
            autoComplete="off"
          />
        </div>
        {isActive ? (
          <Button variant="destructive" onClick={onStop}>
            <Square size={13} fill="currentColor" />
            Dừng
          </Button>
        ) : (
          <Button onClick={doSearch} disabled={searching}>
            <Search size={13} />
            {searching ? 'Đang tìm...' : 'Tìm'}
          </Button>
        )}
      </div>

      {showResults && !isActive && (
        <div className="story-results">
          {results.length === 0 ? (
            <div className="no-results">Không tìm thấy truyện nào.</div>
          ) : (
            results.map(r => (
              <button
                key={r.slug}
                type="button"
                className={`story-card ${selected?.slug === r.slug ? 'selected' : ''}`}
                onClick={() => handleSelectStory(r)}
              >
                {r.cover ? (
                  <img
                    src={r.cover}
                    alt=""
                    loading="lazy"
                    className="story-cover"
                  />
                ) : (
                  <div className="story-cover-placeholder" />
                )}
                <div className="story-info">
                  <div className="story-title">{r.title}</div>
                  {r.latest_chapter && (
                    <div className="story-latest">{r.latest_chapter}</div>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      )}

      {selected && !isActive && (
        <div className="chapter-picker">
          <div className="chapter-read-row">
            <span className="selected-story-label">{selected.title}</span>

            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowChapters(v => !v)}
              disabled={loadingChaps}
            >
              <BookOpen size={12} />
              {chapBtnLabel}
            </Button>

            <div className="chapter-num-group">
              <span className="section-label">Chương</span>
              <input
                type="number"
                min={1}
                max={maxChapter ?? undefined}
                value={chapterNum}
                onChange={e => setChapterNum(Number.parseInt(e.target.value, 10) || 1)}
                onKeyDown={e => { if (e.key === 'Enter') handleStartWithNum() }}
                className="chapter-num-input"
              />
              {maxChapter && (
                <span className="chapter-max">/ {maxChapter}</span>
              )}
            </div>
            <Button onClick={handleStartWithNum}>
              <Play size={13} fill="currentColor" />
              Đọc
            </Button>
          </div>

          {showChapters && (
            <div className="chapter-list-panel">
              <div className="chapter-list">
                {chapters.length === 0 && !loadingChaps && (
                  <div className="chapter-empty">Không tải được danh sách chương.</div>
                )}
                {chapters.map(ch => (
                  <button
                    key={ch.num}
                    type="button"
                    className="chapter-item"
                    onClick={() => handleStartChapter(ch.url)}
                  >
                    <span>{ch.num}</span>
                    {ch.title}
                  </button>
                ))}
              </div>

              {chapTotalPages > 1 && (
                <div className="chapter-pagination">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={chapPage <= 1}
                    onClick={() => setChapPage(p => p - 1)}
                    aria-label="Trang trước"
                  >
                    <ChevronLeft size={12} />
                  </Button>
                  <span>Trang {chapPage} / {chapTotalPages}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={chapPage >= chapTotalPages}
                    onClick={() => setChapPage(p => p + 1)}
                    aria-label="Trang sau"
                  >
                    <ChevronRight size={12} />
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
