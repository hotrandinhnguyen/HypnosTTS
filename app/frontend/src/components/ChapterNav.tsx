import { useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { Button } from './ui/button'

interface ChapterNavProps {
  visible: boolean
  chapterTitle: string
  prevUrl: string | null
  nextUrl: string | null
  onPrev: () => void
  onNext: () => void
  onJump: (url: string) => void
  autoPlay: boolean
  onAutoPlayChange: (v: boolean) => void
  autoPlayCountdown: number
  onCancelAutoPlay: () => void
}

const _SLUG_RE = /^(https?:\/\/[^/]+)\/([^/]+)\/chuong-\d+/

function extractBase(url: string | null): { base: string; slug: string } | null {
  if (!url) return null
  const m = _SLUG_RE.exec(url)
  if (!m) return null
  return { base: m[1], slug: m[2] }
}

export function ChapterNav({
  visible, chapterTitle, prevUrl, nextUrl,
  onPrev, onNext, onJump,
  autoPlay, onAutoPlayChange, autoPlayCountdown, onCancelAutoPlay,
}: Readonly<ChapterNavProps>) {
  const [jumpVal, setJumpVal] = useState('')

  if (!visible) return null

  const info = extractBase(prevUrl ?? nextUrl)

  function handleJump() {
    const n = Number.parseInt(jumpVal, 10)
    if (!n || !info) return
    onJump(`${info.base}/${info.slug}/chuong-${n}/`)
    setJumpVal('')
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Prev / title / next */}
      <div className="flex items-center justify-between gap-3 py-1 px-1">
        <Button variant="ghost" size="sm" disabled={!prevUrl} onClick={onPrev}>
          <ChevronLeft size={13} />
          Trước
        </Button>

        <span className="flex-1 text-center text-[13px] font-semibold text-[#64748b] whitespace-nowrap overflow-hidden text-ellipsis">
          {chapterTitle}
        </span>

        <Button variant="ghost" size="sm" disabled={!nextUrl} onClick={onNext}>
          Sau
          <ChevronRight size={13} />
        </Button>
      </div>

      {/* Controls row: jump + auto-play toggle */}
      <div className="flex items-center justify-between gap-3 px-1">
        {/* Jump to chapter */}
        {info ? (
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#2d3a52]">
              Đến chương
            </span>
            <input
              type="number"
              min={1}
              value={jumpVal}
              placeholder="..."
              onChange={e => setJumpVal(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleJump() }}
              className="chapter-num-input"
            />
            <Button size="sm" variant="ghost" onClick={handleJump} disabled={!jumpVal}>
              Đi
            </Button>
          </div>
        ) : <div />}

        {/* Auto-play toggle */}
        <div className="flex items-center gap-2 cursor-pointer select-none">
          <label htmlFor="autoplay-toggle" className="text-[11px] text-[#64748b] cursor-pointer">
            Tự động chuyển chương
          </label>
          <button
            id="autoplay-toggle"
            type="button"
            role="switch"
            aria-checked={autoPlay}
            onClick={() => onAutoPlayChange(!autoPlay)}
            className={`relative w-9 h-5 rounded-full transition-colors duration-200 focus:outline-none ${
              autoPlay ? 'bg-violet-600' : 'bg-[rgba(255,255,255,.1)]'
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${
                autoPlay ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Auto-play countdown banner */}
      {autoPlayCountdown > 0 && (
        <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-[rgba(139,92,246,.12)] border border-[rgba(139,92,246,.2)]">
          <span className="text-[12px] text-[#a78bfa]">
            Tự động chuyển chương sau <strong>{autoPlayCountdown}s</strong>...
          </span>
          <Button size="sm" variant="ghost" onClick={onCancelAutoPlay} className="h-6 px-2 text-[11px]">
            <X size={11} />
            Hủy
          </Button>
        </div>
      )}
    </div>
  )
}
