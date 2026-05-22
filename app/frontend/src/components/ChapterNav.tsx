import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from './ui/button'

interface ChapterNavProps {
  visible: boolean
  chapterTitle: string
  prevUrl: string | null
  nextUrl: string | null
  onPrev: () => void
  onNext: () => void
}

export function ChapterNav({
  visible,
  chapterTitle,
  prevUrl,
  nextUrl,
  onPrev,
  onNext,
}: ChapterNavProps) {
  if (!visible) return null

  return (
    <div className="flex items-center justify-between gap-3 py-2 px-1">
      <Button
        variant="ghost"
        size="sm"
        disabled={!prevUrl}
        onClick={onPrev}
      >
        <ChevronLeft size={13} />
        Chương trước
      </Button>
      <span className="flex-1 text-center text-[13px] font-semibold text-[#64748b] whitespace-nowrap overflow-hidden text-ellipsis">
        {chapterTitle}
      </span>
      <Button
        variant="ghost"
        size="sm"
        disabled={!nextUrl}
        onClick={onNext}
      >
        Chương sau
        <ChevronRight size={13} />
      </Button>
    </div>
  )
}
