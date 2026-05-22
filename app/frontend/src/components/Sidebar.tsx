import React from 'react'
import { Music } from 'lucide-react'
import { ScrollArea } from './ui/scroll-area'

export interface HistoryItem {
  id?: number
  topic?: string
  url?: string
  chapter_title?: string
  story_title?: string
  created_at: string
}

interface SidebarProps {
  label: string
  items: HistoryItem[]
  activeId?: number | string
  onSelect: (item: HistoryItem) => void
}

function formatDate(isoStr: string): string {
  const d = new Date(isoStr)
  return `${d.getDate()}/${d.getMonth() + 1} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function Sidebar({ label, items, activeId, onSelect }: SidebarProps) {
  return (
    <aside className="w-[220px] flex-shrink-0 bg-[rgba(6,9,20,.8)] border-r border-white/[.06] backdrop-blur-[20px] flex flex-col gap-[18px] py-5 px-3 overflow-hidden relative z-10">
      {/* Brand */}
      <div className="flex items-center gap-2.5 pb-3 border-b border-white/[.06] px-2">
        <div className="w-[34px] h-[34px] rounded-[10px] bg-gradient-to-br from-violet-500 to-cyan-400 flex items-center justify-center text-white flex-shrink-0 shadow-[0_0_20px_rgba(139,92,246,.35),0_4px_12px_rgba(0,0,0,.4)] transition-all duration-300 hover:rotate-[-10deg] hover:scale-110 hover:shadow-[0_0_30px_rgba(139,92,246,.35)]">
          <Music size={18} />
        </div>
        <span className="text-[15px] font-bold tracking-[-0.4px] bg-gradient-to-br from-[#a78bfa] to-[#22d3ee] bg-clip-text text-transparent">
          HypnosTTS
        </span>
      </div>

      {/* Label */}
      <div className="text-[10px] font-semibold uppercase tracking-[.12em] text-[#2d3a52] px-2">
        {label}
      </div>

      {/* History list */}
      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-0.5">
          {items.map((item, idx) => {
            const key = item.id ?? item.url ?? idx
            const isActive = activeId === key
            const primary = item.topic || item.chapter_title || item.story_title || '—'
            const secondary = item.url
              ? `${item.story_title} · ${formatDate(item.created_at)}`
              : formatDate(item.created_at)

            return (
              <div
                key={key}
                className={`history-item ${isActive ? 'active' : ''}`}
                onClick={() => onSelect(item)}
              >
                <div className="whitespace-nowrap overflow-hidden text-ellipsis">{primary}</div>
                <div className="block text-[10px] text-[#2d3a52] mt-0.5 whitespace-nowrap overflow-hidden text-ellipsis">
                  {secondary}
                </div>
              </div>
            )
          })}
        </div>
      </ScrollArea>
    </aside>
  )
}
