interface StatusBarProps {
  message: string
  visible: boolean
}

export function StatusBar({ message, visible }: StatusBarProps) {
  if (!visible) return null

  return (
    <div className="status-bar">
      <div className="status-waves">
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
