import type { Page } from './NavSidebar'

interface StudioSceneProps {
  activePage: Page
  active: boolean
  progress: number
}

const BARS = [34, 58, 42, 76, 50, 68, 38, 82, 46, 62, 72, 44]

export function StudioScene({ activePage, active, progress }: StudioSceneProps) {
  return (
    <div className={`studio-scene studio-scene--${activePage} ${active ? 'is-active' : ''}`} aria-hidden="true">
      <div className="studio-horizon" />
      <div className="studio-ring ring-a" />
      <div className="studio-ring ring-b" />
      <div className="studio-stage">
        <div className="studio-deck">
          <div className="deck-screen">
            <div className="screen-scan" />
            <div className="signal-row">
              {BARS.map((height, index) => (
                <span
                  key={index}
                  style={{
                    height: `${active ? height : Math.max(18, height - 28)}%`,
                    animationDelay: `${index * -0.08}s`,
                  }}
                />
              ))}
            </div>
            <div className="screen-progress">
              <span style={{ width: `${Math.max(8, progress)}%` }} />
            </div>
          </div>
          <div className="deck-controls">
            <span />
            <span />
            <span />
          </div>
        </div>
        <div className="studio-core">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  )
}
