import React, { useRef, useState, useCallback } from 'react'
import { Pause, Play, Volume2, Download } from 'lucide-react'
import { Button } from './ui/button'
import { Slider } from './ui/slider'
import { Card, CardHeader, CardTitle } from './ui/card'
import { Separator } from './ui/separator'
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
      ? '#22d3ee'
      : cardDotState === 'done'
      ? '#4ade80'
      : '#8b5cf6'

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
    <Card className="flex-1 min-h-0 flex flex-col overflow-hidden">
      {/* Gradient top edge */}
      <div className="absolute top-0 left-[10%] right-[10%] h-px bg-gradient-to-r from-transparent via-violet-500 to-cyan-400 to-transparent opacity-60 pointer-events-none" />

      <CardHeader>
        <div className="flex items-center gap-2">
          <div
            className="card-dot"
            style={{
              background: dotColor,
              boxShadow: `0 0 8px ${dotColor}55`,
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

      {/* Caption */}
      <div
        ref={captionRef}
        className="flex-1 px-7 py-6 overflow-y-auto text-base leading-[2] text-slate-200 scroll-smooth"
      >
        <span className="text-[#2d3a52] italic">Nội dung sẽ xuất hiện ở đây...</span>
      </div>

      {/* Progress */}
      {progressVisible && (
        <div className="flex items-center gap-3.5 px-5 pb-3.5 flex-shrink-0">
          <div className="flex-1 h-[5px] bg-white/[.06] rounded-[3px] overflow-hidden shadow-[inset_0_1px_3px_rgba(0,0,0,.4)] relative">
            <div
              className="h-full bg-gradient-to-r from-violet-500 to-cyan-400 rounded-[3px] transition-all duration-500 ease-[cubic-bezier(.4,0,.2,1)] relative overflow-hidden"
              style={{ width: `${pct}%` }}
            >
              <div className="progress-shimmer" />
            </div>
          </div>
          <span className="text-[11px] font-semibold text-[#64748b] whitespace-nowrap min-w-[56px] text-right font-mono">
            {playedCount} / {totalSentences}
          </span>
        </div>
      )}

      {/* Controls */}
      {controlsVisible && (
        <>
          <Separator />
          <div className="flex items-center gap-3.5 px-5 py-3 flex-wrap flex-shrink-0">
            {/* Pause/Resume */}
            <Button variant="secondary" size="sm" onClick={handlePause}>
              {isPaused ? <Play size={13} fill="currentColor" /> : <Pause size={13} fill="currentColor" />}
              {isPaused ? 'Tiếp tục' : 'Tạm dừng'}
            </Button>

            <Separator orientation="vertical" className="h-7" />

            {/* Speed */}
            <div className="flex items-center gap-2.5">
              <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#2d3a52] whitespace-nowrap">
                Tốc độ
              </span>
              <div className="flex gap-1">
                {SPEEDS.map(s => (
                  <button
                    key={s}
                    onClick={() => handleSpeed(s)}
                    className={`speed-pill ${speed === s ? 'active' : ''}`}
                  >
                    {s}×
                  </button>
                ))}
              </div>
            </div>

            <Separator orientation="vertical" className="h-7" />

            {/* Volume */}
            <div className="flex items-center gap-2.5">
              <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#2d3a52] whitespace-nowrap">
                Âm lượng
              </span>
              <div className="flex items-center gap-2 text-[#64748b]">
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
