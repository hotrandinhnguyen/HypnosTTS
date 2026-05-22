import React from 'react'
import { Music, BookOpen, BookMarked, Clock } from 'lucide-react'
import { ScrollArea } from './ui/scroll-area'
import type { HistoryItem } from './Sidebar'

export type Page = 'learn' | 'story'

interface NavSidebarProps {
  activePage: Page
  onNavigate: (page: Page) => void
  historyItems: HistoryItem[]
  activeHistoryId?: number | string
  onHistorySelect: (item: HistoryItem) => void
}

function formatDate(isoStr: string): string {
  const d = new Date(isoStr)
  return `${d.getDate()}/${d.getMonth() + 1} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const NAV_ITEMS = [
  { page: 'learn' as Page, label: 'Học', icon: BookOpen },
  { page: 'story' as Page, label: 'Truyện', icon: BookMarked },
]

export function NavSidebar({
  activePage, onNavigate, historyItems, activeHistoryId, onHistorySelect,
}: NavSidebarProps) {
  return (
    <aside className="nav-sidebar">
      {/* Brand */}
      <div className="nav-brand">
        <div className="brand-icon-wrap">
          <Music size={16} />
        </div>
        <span className="brand-text">HypnosTTS</span>
      </div>

      {/* Nav items */}
      <nav className="nav-items">
        <div className="nav-section-label">Menu</div>
        {NAV_ITEMS.map(({ page, label, icon: Icon }) => (
          <button
            key={page}
            className={`nav-item ${activePage === page ? 'active' : ''}`}
            onClick={() => onNavigate(page)}
          >
            <span className="nav-item-indicator" />
            <Icon size={15} className="nav-item-icon" />
            <span className="nav-item-label">{label}</span>
          </button>
        ))}
      </nav>

      {/* Divider */}
      <div className="nav-divider" />

      {/* Recent history */}
      <div className="nav-history">
        <div className="nav-section-label">
          <Clock size={11} />
          Gần đây
        </div>
        <ScrollArea className="flex-1">
          <div className="flex flex-col gap-0.5 pr-1">
            {historyItems.length === 0 && (
              <div className="text-[11px] text-[#2d3a52] px-3 py-2 italic">Chưa có lịch sử</div>
            )}
            {historyItems.map((item, idx) => {
              const key = item.id ?? item.url ?? idx
              const isActive = activeHistoryId === key
              const label = item.topic || item.chapter_title || item.story_title || '—'
              return (
                <div
                  key={key}
                  className={`history-item ${isActive ? 'active' : ''}`}
                  onClick={() => onHistorySelect(item)}
                  title={label}
                >
                  <div className="truncate text-[12px]">{label}</div>
                  <div className="text-[10px] text-[#2d3a52] mt-0.5">
                    {formatDate(item.created_at)}
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </div>
    </aside>
  )
}
