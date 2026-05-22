import React, { useState } from 'react'
import { Search, Play, Square } from 'lucide-react'
import { Button } from './ui/button'

export interface StoryResult {
  title: string
  slug: string
  latest_chapter?: string
  cover?: string
}

interface StorySearchProps {
  isActive: boolean
  onStartSession: (url: string) => void
  onStop: () => void
}

export function StorySearch({ isActive, onStartSession, onStop }: StorySearchProps) {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState<StoryResult[]>([])
  const [showResults, setShowResults] = useState(false)
  const [selectedStory, setSelectedStory] = useState<StoryResult | null>(null)
  const [chapterNum, setChapterNum] = useState(1)

  async function doSearch() {
    const q = query.trim()
    if (!q) return
    setSearching(true)
    setSelectedStory(null)
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

  function handleStart() {
    if (!selectedStory) return
    const url = `https://truyenfull.today/${selectedStory.slug}/chuong-${chapterNum}/`
    onStartSession(url)
  }

  return (
    <div className="flex flex-col gap-2.5">
      {/* Search row */}
      <div className="flex gap-2.5 items-center">
        <div className="flex-1 relative flex items-center">
          <Search size={16} className="absolute left-4 text-[#64748b] pointer-events-none" />
          <input
            className="glass-input"
            placeholder="Tìm tên truyện (VD: Vạn Cổ Chí Tôn, Đấu Phá Thương Khung...)"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') doSearch() }}
            autoComplete="off"
          />
        </div>
        {!isActive ? (
          <Button
            onClick={doSearch}
            disabled={searching}
          >
            <Search size={13} />
            {searching ? 'Đang tìm...' : 'Tìm'}
          </Button>
        ) : (
          <Button variant="destructive" onClick={onStop}>
            <Square size={13} fill="currentColor" />
            Dừng
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
              <div
                key={r.slug}
                className={`story-card ${selectedStory?.slug === r.slug ? 'selected' : ''}`}
                onClick={() => setSelectedStory(r)}
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
              </div>
            ))
          )}
        </div>
      )}

      {/* Chapter picker */}
      {selectedStory && !isActive && (
        <div className="pt-2.5 pb-0.5">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="flex-1 min-w-0 text-[13px] font-semibold text-[#a78bfa] whitespace-nowrap overflow-hidden text-ellipsis">
              {selectedStory.title}
            </span>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#2d3a52]">Chương</span>
              <input
                type="number"
                min={1}
                value={chapterNum}
                onChange={e => setChapterNum(parseInt(e.target.value, 10) || 1)}
                onKeyDown={e => { if (e.key === 'Enter') handleStart() }}
                className="chapter-num-input"
              />
            </div>
            <Button onClick={handleStart}>
              <Play size={13} fill="currentColor" />
              Đọc
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
