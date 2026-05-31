import React, { useState } from 'react'
import { Download, Pause, Play, Volume2 } from 'lucide-react'
import { Button } from './ui/button'
import { Card, CardHeader, CardTitle } from './ui/card'
import { Separator } from './ui/separator'
import { Slider } from './ui/slider'
import { toWav } from '@/hooks/useAudio'
import type { AudioEngine } from '@/hooks/useAudio'

interface PlayerCardProps {
  audio: AudioEngine
  captionRef: React.RefObject<HTMLDivElement>
  controlsVisible: boolean
  progressVisible: boolean
  downloadVisible: boolean
  totalSentences: number
  playedCount: number
  cardDotState: 'idle' | 'playing' | 'done'
  currentTopic: string
}

const SPEEDS = [0.75, 1, 1.25, 1.5]

export function PlayerCard({
  audio,
  captionRef,
  controlsVisible,
  progressVisible,
  downloadVisible,
  totalSentences,
  playedCount,
  cardDotState,
  currentTopic,
}: PlayerCardProps) {
  const [isPaused, setIsPaused] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [volume, setVolume] = useState(1)
  const [downloading, setDownloading] = useState(false)

  const dotColor =
    cardDotState === 'playing'
      ? 'var(--info)'
      : cardDotState === 'done'
      ? 'var(--success)'
      : 'var(--accent)'

  const pct = totalSentences > 0 ? (playedCount / totalSentences) * 100 : 0

  function handlePause() {
    if (isPaused) {
      audio.resume()
      setIsPaused(false)
    } else {
      audio.pause()
      setIsPaused(true)
    }
  }

  function handleSpeed(s: number) {
    setSpeed(s)
    audio.setSpeed(s)
  }

  function handleVolume(val: number[]) {
    const v = val[0]
    setVolume(v)
    audio.setVolume(v)
  }

  async function handleDownload() {
    const buffers = audio.getSessionBuffers()
    if (!buffers.length) return
    setDownloading(true)
    try {
      const sr = buffers[0].sampleRate
      const total = buffers.reduce((s, b) => s + b.length, 0)
      const off = new OfflineAudioContext(1, total, sr)
      let offset = 0
      for (const buf of buffers) {
        const src = off.createBufferSource()
        src.buffer = buf
        src.connect(off.destination)
        src.start(offset / sr)
        offset += buf.length
      }
      const rendered = await off.startRendering()
      const wav = toWav(rendered)
      const a = document.createElement('a')
      a.href = URL.createObjectURL(new Blob([wav], { type: 'audio/wav' }))
      a.download = currentTopic.replace(/[^a-z0-9]/gi, '_').slice(0, 40) + '.wav'
      a.click()
    } catch (e) {
      console.error(e)
    }
    setDownloading(false)
  }

  return (
    <Card className="player-card">
      <div className="card-top-glow" />

      <CardHeader>
        <div className="flex items-center gap-2">
          <div
            className="card-dot"
            style={{
              background: dotColor,
              boxShadow: `0 0 0 4px color-mix(in srgb, ${dotColor} 18%, transparent)`,
            }}
          />
          <CardTitle>Nội dung</CardTitle>
        </div>
        {downloadVisible && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownload}
            disabled={downloading}
          >
            <Download size={13} />
            {downloading ? 'Đang xuất...' : 'Tải xuống'}
          </Button>
        )}
      </CardHeader>

      <div
        ref={captionRef}
        className="caption"
      >
        <span className="caption-placeholder">Nội dung sẽ xuất hiện ở đây...</span>
      </div>

      {progressVisible && (
        <div className="player-telemetry">
          <div className="waveform-strip" aria-hidden="true">
            {Array.from({ length: 28 }).map((_, index) => (
              <span key={index} style={{ animationDelay: `${index * -0.055}s` }} />
            ))}
          </div>
          <div className="progress-container">
            <div className="progress-track">
              <div
                className="progress-fill"
                style={{ width: `${pct}%` }}
              >
                <div className="progress-shimmer" />
              </div>
            </div>
            <span className="progress-label">
              {playedCount} / {totalSentences}
            </span>
          </div>
        </div>
      )}

      {controlsVisible && (
        <>
          <Separator />
          <div className="controls">
            <Button variant="secondary" size="sm" onClick={handlePause}>
              {isPaused ? <Play size={13} fill="currentColor" /> : <Pause size={13} fill="currentColor" />}
              {isPaused ? 'Tiếp tục' : 'Tạm dừng'}
            </Button>

            <Separator orientation="vertical" className="h-7" />

            <div className="ctrl-group">
              <span className="ctrl-label">Tốc độ</span>
              <div className="speed-buttons">
                {SPEEDS.map(s => (
                  <button
                    key={s}
                    onClick={() => handleSpeed(s)}
                    className={`speed-pill ${speed === s ? 'active' : ''}`}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            </div>

            <Separator orientation="vertical" className="h-7" />

            <div className="ctrl-group">
              <span className="ctrl-label">Âm lượng</span>
              <div className="volume-row">
                <Volume2 size={13} />
                <Slider
                  min={0}
                  max={1}
                  step={0.05}
                  value={[volume]}
                  onValueChange={handleVolume}
                  className="w-20"
                />
              </div>
            </div>
          </div>
        </>
      )}
    </Card>
  )
}
