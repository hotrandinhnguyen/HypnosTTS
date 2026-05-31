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
    <div className="voice-picker-shell">
      <span className="section-label">Giọng đọc</span>
      <div className="voice-picker">
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
