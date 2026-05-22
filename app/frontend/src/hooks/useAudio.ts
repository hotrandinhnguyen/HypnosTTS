import { useRef, useCallback } from 'react'

export interface AudioEngine {
  ensureCtx: (volume: number) => void
  scheduleBuffer: (audioBuffer: AudioBuffer, spanEl: HTMLElement) => void
  decodeWav: (ab: ArrayBuffer) => Promise<AudioBuffer>
  pause: () => void
  resume: () => void
  setSpeed: (speed: number) => void
  setVolume: (vol: number) => void
  stop: () => void
  isPaused: () => boolean
  exportWav: (buffers: AudioBuffer[]) => ArrayBuffer
  addSessionBuffer: (buf: AudioBuffer) => void
  getSessionBuffers: () => AudioBuffer[]
  clearSessionBuffers: () => void
}

function toWav(buffer: AudioBuffer): ArrayBuffer {
  const data = buffer.getChannelData(0)
  const samples = new Int16Array(data.length)
  for (let i = 0; i < data.length; i++) {
    const s = Math.max(-1, Math.min(1, data[i]))
    samples[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  const ab = new ArrayBuffer(44 + samples.byteLength)
  const v = new DataView(ab)
  const ws = (o: number, s: string) => {
    for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.codePointAt(i)!)
  }
  ws(0, 'RIFF'); v.setUint32(4, ab.byteLength - 8, true)
  ws(8, 'WAVE'); ws(12, 'fmt ')
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
  v.setUint32(24, buffer.sampleRate, true); v.setUint32(28, buffer.sampleRate * 2, true)
  v.setUint16(32, 2, true); v.setUint16(34, 16, true)
  ws(36, 'data'); v.setUint32(40, samples.byteLength, true)
  new Int16Array(ab, 44).set(samples)
  return ab
}

export function useAudio(): AudioEngine {
  const audioCtxRef = useRef<AudioContext | null>(null)
  const gainNodeRef = useRef<GainNode | null>(null)
  const nextStartTimeRef = useRef<number>(0)
  const playbackSpeedRef = useRef<number>(1)
  const pausedRef = useRef<boolean>(false)
  const sessionBuffersRef = useRef<AudioBuffer[]>([])

  const ensureCtx = useCallback((volume: number) => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext()
      gainNodeRef.current = audioCtxRef.current.createGain()
      gainNodeRef.current.gain.value = volume
      gainNodeRef.current.connect(audioCtxRef.current.destination)
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume()
    }
  }, [])

  const decodeWav = useCallback(async (ab: ArrayBuffer): Promise<AudioBuffer> => {
    if (!audioCtxRef.current) throw new Error('AudioContext not initialized')
    return audioCtxRef.current.decodeAudioData(ab)
  }, [])

  const scheduleBuffer = useCallback((audioBuffer: AudioBuffer, spanEl: HTMLElement) => {
    const ctx = audioCtxRef.current
    const gain = gainNodeRef.current
    if (!ctx || !gain) return

    const src = ctx.createBufferSource()
    src.buffer = audioBuffer
    src.playbackRate.value = playbackSpeedRef.current
    src.connect(gain)

    const startAt = Math.max(ctx.currentTime, nextStartTimeRef.current)
    src.start(startAt)
    nextStartTimeRef.current = startAt + audioBuffer.duration / playbackSpeedRef.current

    const delay = Math.max(0, (startAt - ctx.currentTime) * 1000)
    setTimeout(() => {
      document.querySelectorAll<HTMLElement>('.sentence.active').forEach(el => {
        el.classList.replace('active', 'done')
      })
      spanEl.classList.add('active')
      spanEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, delay)

    src.onended = () => {
      spanEl.classList.replace('active', 'done')
    }
  }, [])

  const pause = useCallback(() => {
    if (audioCtxRef.current) {
      audioCtxRef.current.suspend()
      pausedRef.current = true
    }
  }, [])

  const resume = useCallback(() => {
    if (audioCtxRef.current) {
      audioCtxRef.current.resume()
      pausedRef.current = false
    }
  }, [])

  const setSpeed = useCallback((speed: number) => {
    playbackSpeedRef.current = speed
  }, [])

  const setVolume = useCallback((vol: number) => {
    if (gainNodeRef.current) {
      gainNodeRef.current.gain.value = vol
    }
  }, [])

  const stop = useCallback(() => {
    if (audioCtxRef.current) {
      audioCtxRef.current.close()
      audioCtxRef.current = null
      gainNodeRef.current = null
    }
    nextStartTimeRef.current = 0
    pausedRef.current = false
  }, [])

  const isPaused = useCallback(() => pausedRef.current, [])

  const exportWav = useCallback((buffers: AudioBuffer[]): ArrayBuffer => {
    // This is synchronous — caller handles OfflineAudioContext rendering
    if (buffers.length === 0) return new ArrayBuffer(0)
    return toWav(buffers[0]) // placeholder, real export done async in component
  }, [])

  const addSessionBuffer = useCallback((buf: AudioBuffer) => {
    sessionBuffersRef.current.push(buf)
  }, [])

  const getSessionBuffers = useCallback(() => sessionBuffersRef.current, [])

  const clearSessionBuffers = useCallback(() => {
    sessionBuffersRef.current = []
  }, [])

  return {
    ensureCtx,
    scheduleBuffer,
    decodeWav,
    pause,
    resume,
    setSpeed,
    setVolume,
    stop,
    isPaused,
    exportWav,
    addSessionBuffer,
    getSessionBuffers,
    clearSessionBuffers,
  }
}

export { toWav }
