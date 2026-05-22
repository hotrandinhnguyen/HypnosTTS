import React from 'react'

interface StatusBarProps {
  message: string
  visible: boolean
}

export function StatusBar({ message, visible }: StatusBarProps) {
  if (!visible) return null

  return (
    <div className="flex items-center gap-3 px-[18px] py-3 rounded-xl border border-[rgba(139,92,246,.3)] bg-[rgba(12,18,38,0.75)] backdrop-blur-[20px] text-sm text-[#64748b] shadow-[0_4px_20px_rgba(0,0,0,.2),0_0_0_1px_rgba(139,92,246,.05)]">
      <div className="flex items-center gap-[3px] flex-shrink-0">
        <span className="status-wave-bar" />
        <span className="status-wave-bar" />
        <span className="status-wave-bar" />
        <span className="status-wave-bar" />
        <span className="status-wave-bar" />
      </div>
      <span>{message}</span>
    </div>
  )
}
