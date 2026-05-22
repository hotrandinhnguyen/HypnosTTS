import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from './ui/button'

interface ChapterNavProps {
  visible: boolean
  chapterTitle: string
  prevUrl: string | null
  nextUrl: string | null
  onPrev: () => void
  onNext: () => void
  onJump: (url: string) => void
}

const _SLUG_RE = /^(https?:\/\/[^/]+)\/([^/]+)\/chuong-\d+/

function extractSlugAndChapter(url: string | null): { slug: string; base: string } | null {
  if (!url) return null
  const m = _SLUG_RE.exec(url)
  if (!m) return null
  return { base: m[1], slug: m[2] }
}

export function ChapterNav({
  visible, chapterTitle, prevUrl, nextUrl, onPrev, onNext, onJump,
}: Readonly<ChapterNavProps>) {
  const [jumpVal, setJumpVal] = useState('')

  if (!visible) return null

  const info = extractSlugAndChapter(prevUrl ?? nextUrl)

  function handleJump() {
    const n = Number.parseInt(jumpVal, 10)
    if (!n || !info) return
    onJump(`${info.base}/${info.slug}/chuong-${n}/`)
    setJumpVal('')
  }

  return (
    <div className="flex flex-col gap-1.5">
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

      {/* Jump to chapter */}
      {info && (
        <div className="flex items-center justify-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#2d3a52]">Đến chương</span>
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
      )}
    </div>
  )
}
