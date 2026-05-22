import React from 'react'

export interface Voice {
  key: string
  label: string
  instruct: string
}

interface VoicePickerProps {
  voices: Voice[]
  selectedKey: string
  onSelect: (voice: Voice) => void
}

export function VoicePicker({ voices, selectedKey, onSelect }: VoicePickerProps) {
  return (
    <div className="flex items-center gap-3.5 flex-wrap">
      <span className="text-[11px] font-semibold uppercase tracking-[.1em] text-[#2d3a52] whitespace-nowrap">
        Giọng đọc
      </span>
      <div className="flex flex-wrap gap-1.5">
        {voices.map(v => (
          <button
            key={v.key}
            onClick={() => onSelect(v)}
            className={`voice-pill ${v.key === selectedKey ? 'active' : ''}`}
          >
            {v.label}
          </button>
        ))}
      </div>
    </div>
  )
}
