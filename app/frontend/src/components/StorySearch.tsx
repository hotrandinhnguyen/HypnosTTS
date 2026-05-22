import { useState, useEffect } from 'react'
import { Search, Play, Square, BookOpen, ChevronLeft, ChevronRight } from 'lucide-react'
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

const _DIGIT_RE    = /\d+/
const _URL_RE      = /truyenfull\.today\/[^/]+\/chuong-\d+/

function parseMaxChapter(latest: string | undefined): number | null {
  if (!latest) return null
  const m = _DIGIT_RE.exec(latest)
  return m ? Number.parseInt(m[0], 10) : null
}

export function StorySearch({ isActive, onStartSession, onStop }: Readonly<StorySearchProps>) {
  const [query, setQuery]               = useState('')
  const [searching, setSearching]       = useState(false)
  const [results, setResults]           = useState<StoryResult[]>([])
  const [showResults, setShowResults]   = useState(false)
  const [selected, setSelected]         = useState<StoryResult | null>(null)
  const [chapterNum, setChapterNum]     = useState(1)

  // Chapter list
  const [chapters, setChapters]           = useState<ChapterItem[]>([])
  const [chapPage, setChapPage]           = useState(1)
  const [chapTotalPages, setChapTotalPages] = useState(1)
  const [loadingChaps, setLoadingChaps]   = useState(false)
  const [showChapters, setShowChapters]   = useState(false)

  // Fetch chapter list whenever selected story or page changes
  useEffect(() => {
    if (!selected) { setChapters([]); return }
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
      .catch(() => { if (!cancelled) setLoadingChaps(false) })
    return () => { cancelled = true }
  }, [selected, chapPage])

  async function doSearch() {
    const q = query.trim()
    if (!q) return

    // Direct URL → start immediately
    if (_URL_RE.test(q) || q.startsWith('http')) {
      onStartSession(q)
      return
    }

    setSearching(true)
    setSelected(null)
    setChapters([])
    setShowChapters(false)
    try {
      const res  = await fetch(`/api/story/search?q=${encodeURIComponent(q)}`)
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

  const maxChapter    = parseMaxChapter(selected?.latest_chapter)
  let chapBtnLabel    = 'Danh sách chương'
  if (loadingChaps)   chapBtnLabel = 'Đang tải...'
  else if (showChapters) chapBtnLabel = 'Ẩn chương'

  return (
    <div className="flex flex-col gap-2.5">
      {/* Search row */}
      <div className="flex gap-2.5 items-center">
        <div className="flex-1 relative flex items-center">
          <Search size={16} className="absolute left-4 text-[#64748b] pointer-events-none" />
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

      {/* Search results */}
      {showResults && !isActive && (
        <div className="flex flex-col gap-1.5 max-h-[240px] overflow-y-auto py-0.5">
          {results.length === 0 ? (
            <div className="py-4 text-center text-[#64748b] text-[13px] italic">
              Không tìm thấy truyện nào.
            </div>
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
                    className="w-10 h-[54px] object-cover rounded flex-shrink-0 border border-white/10"
                  />
                ) : (
                  <div className="w-10 h-[54px] flex-shrink-0 rounded bg-[rgba(139,92,246,.15)] border border-white/10" />
                )}
                <div className="flex flex-col gap-1 min-w-0">
                  <div className="text-[13px] font-semibold text-slate-200 whitespace-nowrap overflow-hidden text-ellipsis">
                    {r.title}
                  </div>
                  {r.latest_chapter && (
                    <div className="text-[11px] text-[#64748b]">{r.latest_chapter}</div>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      )}

      {/* Chapter picker */}
      {selected && !isActive && (
        <div className="flex flex-col gap-2 pt-1">
          {/* Story title + controls */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="flex-1 min-w-0 text-[13px] font-semibold text-[#a78bfa] whitespace-nowrap overflow-hidden text-ellipsis">
              {selected.title}
            </span>

            {/* Toggle chapter list */}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowChapters(v => !v)}
              disabled={loadingChaps}
            >
              <BookOpen size={12} />
              {chapBtnLabel}
            </Button>

            {/* Manual number input */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#2d3a52]">Chương</span>
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
                <span className="text-[10px] text-[#2d3a52]">/ {maxChapter}</span>
              )}
            </div>
            <Button onClick={handleStartWithNum}>
              <Play size={13} fill="currentColor" />
              Đọc
            </Button>
          </div>

          {/* Chapter list panel */}
          {showChapters && (
            <div className="flex flex-col gap-1">
              <div className="max-h-[200px] overflow-y-auto flex flex-col gap-0.5 pr-0.5">
                {chapters.length === 0 && !loadingChaps && (
                  <div className="text-[12px] text-[#64748b] italic py-2 px-2">
                    Không tải được danh sách chương.
                  </div>
                )}
                {chapters.map(ch => (
                  <button
                    key={ch.num}
                    type="button"
                    className="text-left px-3 py-1.5 rounded-lg text-[12px] text-[#94a3b8] hover:bg-[rgba(139,92,246,.1)] hover:text-[#c4b5fd] transition-colors truncate"
                    onClick={() => handleStartChapter(ch.url)}
                  >
                    <span className="font-mono text-[10px] text-[#4a5568] mr-2">{ch.num}</span>
                    {ch.title}
                  </button>
                ))}
              </div>

              {/* Pagination */}
              {chapTotalPages > 1 && (
                <div className="flex items-center justify-center gap-2 pt-1">
                  <Button
                    size="sm" variant="ghost"
                    disabled={chapPage <= 1}
                    onClick={() => setChapPage(p => p - 1)}
                  >
                    <ChevronLeft size={12} />
                  </Button>
                  <span className="text-[11px] text-[#64748b]">
                    Trang {chapPage} / {chapTotalPages}
                  </span>
                  <Button
                    size="sm" variant="ghost"
                    disabled={chapPage >= chapTotalPages}
                    onClick={() => setChapPage(p => p + 1)}
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
