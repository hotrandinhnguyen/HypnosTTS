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
  visible,
  chapterTitle,
  prevUrl,
  nextUrl,
  onPrev,
  onNext,
  onJump,
  autoPlay,
  onAutoPlayChange,
  autoPlayCountdown,
  onCancelAutoPlay,
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
    <div className="chapter-nav-shell">
      <div className="chapter-nav-main">
        <Button variant="ghost" size="sm" disabled={!prevUrl} onClick={onPrev}>
          <ChevronLeft size={13} />
          Trước
        </Button>

        <span className="chapter-title-display">{chapterTitle}</span>

        <Button variant="ghost" size="sm" disabled={!nextUrl} onClick={onNext}>
          Sau
          <ChevronRight size={13} />
        </Button>
      </div>

      <div className="chapter-nav-tools">
        {info ? (
          <div className="jump-control">
            <span className="section-label">Đến chương</span>
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

        <div className="switch-row">
          <label htmlFor="autoplay-toggle">Tự động chuyển chương</label>
          <button
            id="autoplay-toggle"
            type="button"
            role="switch"
            aria-checked={autoPlay}
            onClick={() => onAutoPlayChange(!autoPlay)}
            className={`toggle-switch ${autoPlay ? 'active' : ''}`}
          >
            <span />
          </button>
        </div>
      </div>

      {autoPlayCountdown > 0 && (
        <div className="autoplay-banner">
          <span>
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
