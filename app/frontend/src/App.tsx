import {
  useState,
  useEffect,
  useRef,
  useCallback,
} from 'react'

import { useAudio } from './hooks/useAudio'
import { NavSidebar } from './components/NavSidebar'
import type { Page } from './components/NavSidebar'
import type { HistoryItem } from './components/Sidebar'
import { VoicePicker } from './components/VoicePicker'
import type { Voice } from './components/VoicePicker'
import { StatusBar } from './components/StatusBar'
import { PlayerCard } from './components/PlayerCard'
import { LearnPage } from './components/LearnPage'
import { StoryPage } from './components/StoryPage'
import { DiscussPanel } from './components/DiscussPanel'

type CardDotState = 'idle' | 'playing' | 'done'

const PAGE_META: Record<Page, { title: string; titleAccent: string; subtitle: string }> = {
  learn: {
    title: 'Học',
    titleAccent: 'Tập',
    subtitle: 'AI nghiên cứu · tổng hợp analogy · TTS giọng nhất quán',
  },
  story: {
    title: 'Đọc',
    titleAccent: 'Truyện',
    subtitle: 'Crawl & phát thanh truyện từ truyenfull.today',
  },
}

export default function App() {
  // ── Voices ────────────────────────────────────────────────────
  const [voices, setVoices] = useState<Voice[]>([])
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null)

  // ── Page ──────────────────────────────────────────────────────
  const [activePage, setActivePage] = useState<Page>('learn')

  // ── Session state ─────────────────────────────────────────────
  const [learnActive, setLearnActive]           = useState(false)
  const [storyActive, setStoryActive]           = useState(false)
  const [videoActive, setVideoActive]           = useState(false)
  const [videoId, setVideoId]                   = useState<number | null>(null)
  const [discussSessionId, setDiscussSessionId] = useState<number | null>(null)
  const videoWsRef = useRef<WebSocket | null>(null)

  // ── Auto-play ─────────────────────────────────────────────────
  const [autoPlay, setAutoPlay] = useState(false)
  const [autoPlayCountdown, setAutoPlayCountdown] = useState(0)
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Chapter nav ───────────────────────────────────────────────
  const [chapterNavVisible, setChapterNavVisible] = useState(false)
  const [chapterTitle, setChapterTitle] = useState('')
  const prevUrlRef = useRef<string | null>(null)
  const nextUrlRef = useRef<string | null>(null)

  // ── Status ────────────────────────────────────────────────────
  const [statusMsg, setStatusMsg] = useState('')
  const [statusVisible, setStatusVisible] = useState(false)

  // ── Player state ──────────────────────────────────────────────
  const captionRef = useRef<HTMLDivElement>(null)
  const [controlsVisible, setControlsVisible] = useState(false)
  const [progressVisible, setProgressVisible] = useState(false)
  const [downloadVisible, setDownloadVisible] = useState(false)
  const [totalSentences, setTotalSentences] = useState(0)
  const [playedCount, setPlayedCount] = useState(0)
  const [cardDotState, setCardDotState] = useState<CardDotState>('idle')
  const [currentTopic, setCurrentTopic] = useState('')

  // ── Audio engine ──────────────────────────────────────────────
  const audio = useAudio()
  const volumeRef = useRef(1)

  // ── WebSocket ─────────────────────────────────────────────────
  const wsRef = useRef<WebSocket | null>(null)

  // ── Pending spans queue ───────────────────────────────────────
  const pendingSpansRef = useRef<HTMLElement[]>([])

  // ── History ───────────────────────────────────────────────────
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([])
  const [activeHistoryId, setActiveHistoryId] = useState<number | string | undefined>(undefined)

  // ── Init ──────────────────────────────────────────────────────
  useEffect(() => {
    fetch('/api/voices')
      .then(r => r.json())
      .then((data: Voice[]) => {
        setVoices(data)
        if (data.length > 0) setSelectedVoice(data[0])
      })
      .catch(console.error)
  }, [])

  useEffect(() => {
    loadHistory()
  }, [activePage])

  async function loadHistory() {
    try {
      const url = activePage === 'story' ? '/api/story/history' : '/api/history'
      const rows: HistoryItem[] = await (await fetch(url)).json()
      setHistoryItems(rows)
    } catch (e) {
      console.error('[History]', e)
    }
  }

  // ── Caption helpers ───────────────────────────────────────────
  function clearCaption() {
    if (!captionRef.current) return
    captionRef.current.innerHTML =
      '<span class="text-[#2d3a52] italic">Nội dung sẽ xuất hiện ở đây...</span>'
  }

  function appendSentenceSpan(text: string): HTMLElement {
    const el = captionRef.current!
    const placeholder = el.querySelector('span.italic')
    if (placeholder) placeholder.remove()
    const span = document.createElement('span')
    span.className = 'sentence'
    span.textContent = ' ' + text
    el.appendChild(span)
    return span
  }

  // ── Reset player ──────────────────────────────────────────────
  const resetPlayer = useCallback(() => {
    clearCaption()
    pendingSpansRef.current = []
    audio.clearSessionBuffers()
    setTotalSentences(0)
    setPlayedCount(0)
    setControlsVisible(false)
    setProgressVisible(false)
    setDownloadVisible(false)
    setChapterNavVisible(false)
    setStatusVisible(false)
    setCardDotState('idle')
    prevUrlRef.current = null
    nextUrlRef.current = null
  }, [audio])

  // ── Handle text WS frame ──────────────────────────────────────
  function handleTextFrame(msg: Record<string, unknown>) {
    if (msg.type === 'status') {
      setStatusMsg(String(msg.data))
      setStatusVisible(true)
    } else if (msg.type === 'chapter_info') {
      prevUrlRef.current = (msg.prev as string) || null
      nextUrlRef.current = (msg.next as string) || null
      const story = msg.story as string | undefined
      const title = msg.title as string
      setChapterTitle(story ? `${story} · ${title}` : title)
      setChapterNavVisible(true)
      if (msg.cached) setStatusVisible(false)
    } else if (msg.type === 'text') {
      setTotalSentences(prev => prev + 1)
      setProgressVisible(true)
      const span = appendSentenceSpan(String(msg.data))
      pendingSpansRef.current.push(span)
    } else if (msg.type === 'done') {
      setControlsVisible(true)
      setDownloadVisible(true)
      setCardDotState('done')
      if (msg.session_id) setDiscussSessionId(Number(msg.session_id))
      resetButtons()
      loadHistory()
      if (autoPlay && nextUrlRef.current) {
        const next = nextUrlRef.current
        let secs = 3
        setAutoPlayCountdown(secs)
        setStatusMsg(`Tự động chuyển chương sau ${secs}s...`)
        setStatusVisible(true)
        countdownRef.current = setInterval(() => {
          secs -= 1
          if (secs <= 0) {
            clearInterval(countdownRef.current!)
            countdownRef.current = null
            setAutoPlayCountdown(0)
            setStatusVisible(false)
            startStorySession(next)
          } else {
            setAutoPlayCountdown(secs)
            setStatusMsg(`Tự động chuyển chương sau ${secs}s...`)
          }
        }, 1000)
      } else {
        setStatusVisible(false)
      }
    } else if (msg.type === 'error') {
      setStatusMsg('Lỗi: ' + String(msg.data))
      setStatusVisible(true)
      resetButtons()
    }
  }

  // ── Handle binary WS frame ────────────────────────────────────
  async function handleAudioFrame(data: ArrayBuffer) {
    const span = pendingSpansRef.current.shift()
    const cloned = data.slice(0)
    try {
      const audioBuffer = await audio.decodeWav(cloned)
      audio.addSessionBuffer(audioBuffer)
      if (span) {
        audio.scheduleBuffer(audioBuffer, span)
        const obs = new MutationObserver(() => {
          if (span.classList.contains('done')) {
            setPlayedCount(prev => prev + 1)
            obs.disconnect()
          }
        })
        obs.observe(span, { attributes: true, attributeFilter: ['class'] })
      }
      setControlsVisible(true)
      setCardDotState('playing')
    } catch (err) {
      console.error('[Audio] decode error:', err)
    }
  }

  // ── Open WebSocket (lesson / story) ───────────────────────────
  function openWs(wsPath: string, payload: object) {
    audio.ensureCtx(volumeRef.current)
    resetPlayer()

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${location.host}${wsPath}`)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => ws.send(JSON.stringify(payload))
    ws.onmessage = async (evt) => {
      if (typeof evt.data === 'string') {
        handleTextFrame(JSON.parse(evt.data))
      } else {
        await handleAudioFrame(evt.data as ArrayBuffer)
      }
    }
    ws.onerror = () => {
      setStatusMsg('Kết nối thất bại.')
      setStatusVisible(true)
      resetButtons()
    }
    ws.onclose = () => { resetButtons() }
    return ws
  }

  // ── Reset buttons ─────────────────────────────────────────────
  function resetButtons() {
    setLearnActive(false)
    setStoryActive(false)
    wsRef.current = null
  }

  // ── Cancel auto-play countdown ────────────────────────────────
  function cancelAutoPlay() {
    if (countdownRef.current) {
      clearInterval(countdownRef.current)
      countdownRef.current = null
    }
    setAutoPlayCountdown(0)
    setStatusVisible(false)
  }

  // ── Stop ──────────────────────────────────────────────────────
  function stopActive() {
    cancelAutoPlay()
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (videoWsRef.current) {
      videoWsRef.current.close()
      videoWsRef.current = null
    }
    setVideoActive(false)
    audio.stop()
    resetPlayer()
    resetButtons()
  }

  // ── Learn session ─────────────────────────────────────────────
  function startLearnSession(topic: string) {
    setDiscussSessionId(null)
    setVideoId(null)
    setCurrentTopic(topic)
    setStatusMsg('Đang kết nối...')
    setStatusVisible(true)
    setLearnActive(true)
    openWs('/ws/lesson', { topic, instruct: selectedVoice?.instruct || '' })
  }

  // ── Video session ─────────────────────────────────────────────
  function startVideoSession(topic: string, nImages: number = 0, durationMinutes: number = 0) {
    setVideoId(null)
    setVideoActive(true)
    setStatusMsg('Đang kết nối...')
    setStatusVisible(true)

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${location.host}/ws/video`)
    videoWsRef.current = ws

    ws.onopen = () => ws.send(JSON.stringify({ topic, instruct: selectedVoice?.instruct || '', n_images: nImages, duration_minutes: durationMinutes }))
    ws.onmessage = (evt) => {
      if (typeof evt.data !== 'string') return
      const msg = JSON.parse(evt.data)
      if (msg.type === 'status') {
        setStatusMsg(msg.data)
        setStatusVisible(true)
      } else if (msg.type === 'video_done') {
        setVideoId(Number(msg.video_id))
        setVideoActive(false)
        setStatusVisible(false)
        loadHistory()
      } else if (msg.type === 'error') {
        setStatusMsg('Lỗi video: ' + msg.data)
        setStatusVisible(true)
        setVideoActive(false)
      }
    }
    ws.onerror = () => {
      setStatusMsg('Kết nối video thất bại.')
      setStatusVisible(true)
      setVideoActive(false)
    }
    ws.onclose = () => {
      setVideoActive(false)
      videoWsRef.current = null
    }
  }

  // ── Story session ─────────────────────────────────────────────
  function startStorySession(url: string) {
    if (!url) return
    setCurrentTopic(url)
    setStatusMsg('Đang tải chương...')
    setStatusVisible(true)
    setStoryActive(true)
    openWs('/ws/story', { url, instruct: selectedVoice?.instruct || '' })
  }

  // ── Replay learn session ──────────────────────────────────────
  async function replayLearnSession(item: HistoryItem) {
    if (!item.id) return
    setActiveHistoryId(item.id)
    setDiscussSessionId(item.id)
    setVideoId(null)
    audio.ensureCtx(volumeRef.current)
    resetPlayer()
    try {
      const lessons: { sequence: number; text: string; audio: string }[] = await (
        await fetch(`/api/session/${item.id}`)
      ).json()
      for (const lesson of lessons) {
        setTotalSentences(prev => prev + 1)
        const span = appendSentenceSpan(lesson.text)
        const raw = atob(lesson.audio)
        const ab = new ArrayBuffer(raw.length)
        const view = new Uint8Array(ab)
        for (let i = 0; i < raw.length; i++) view[i] = raw.codePointAt(i)! & 0xff
        const buf = await audio.decodeWav(ab)
        audio.addSessionBuffer(buf)
        const obs = new MutationObserver(() => {
          if (span.classList.contains('done')) {
            setPlayedCount(prev => prev + 1)
            obs.disconnect()
          }
        })
        obs.observe(span, { attributes: true, attributeFilter: ['class'] })
        audio.scheduleBuffer(buf, span)
      }
      setProgressVisible(true)
      setControlsVisible(true)
      setDownloadVisible(true)
      setCardDotState('done')
    } catch (e) {
      console.error('[Replay]', e)
    }
  }

  // ── History select ────────────────────────────────────────────
  function handleHistorySelect(item: HistoryItem) {
    if (activePage === 'story' && item.url) {
      startStorySession(item.url)
    } else if (activePage === 'learn' && item.id) {
      replayLearnSession(item)
    }
  }

  // ── Page navigate ─────────────────────────────────────────────
  function handleNavigate(page: Page) {
    if (page === activePage) return
    stopActive()
    setActivePage(page)
  }

  // ── Chapter nav ───────────────────────────────────────────────
  function goToPrev() { if (prevUrlRef.current) startStorySession(prevUrlRef.current) }
  function goToNext() { if (nextUrlRef.current) startStorySession(nextUrlRef.current) }

  const meta = PAGE_META[activePage]
  const anyActive = learnActive || storyActive || videoActive

  return (
    <>
      <div className="orb orb-1" />
      <div className="orb orb-2" />
      <div className="orb orb-3" />
      <div className="orb orb-4" />

      <div className="app-layout">
        <NavSidebar
          activePage={activePage}
          onNavigate={handleNavigate}
          historyItems={historyItems}
          activeHistoryId={activeHistoryId}
          onHistorySelect={handleHistorySelect}
        />

        <div className="main-content">
          <div key={activePage} className="page-enter" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>

            {/* Page header */}
            <header className="page-header">
              <div className="page-title-group">
                <h1 className="page-title">
                  {meta.title}
                  <span className={`page-title-accent ${activePage === 'story' ? 'story-accent' : ''}`}>
                    {' '}{meta.titleAccent}
                  </span>
                </h1>
                <p className="page-subtitle">{meta.subtitle}</p>
              </div>
            </header>

            {/* Page body */}
            <div className="page-body">

              <VoicePicker
                voices={voices}
                selectedKey={selectedVoice?.key ?? ''}
                onSelect={setSelectedVoice}
              />

              {/* ── Learn page ─────────────────────────────── */}
              {activePage === 'learn' && (
                <LearnPage
                  isActive={learnActive}
                  onStart={startLearnSession}
                  onStop={stopActive}
                  onStartVideo={startVideoSession}
                  isVideoGenerating={videoActive}
                />
              )}

              {/* ── Story page ─────────────────────────────── */}
              {activePage === 'story' && (
                <StoryPage
                  isActive={storyActive}
                  onStartSession={startStorySession}
                  onStop={stopActive}
                  chapterNavVisible={chapterNavVisible}
                  chapterTitle={chapterTitle}
                  prevUrl={prevUrlRef.current}
                  nextUrl={nextUrlRef.current}
                  onPrev={goToPrev}
                  onNext={goToNext}
                  onJump={startStorySession}
                  autoPlay={autoPlay}
                  onAutoPlayChange={setAutoPlay}
                  autoPlayCountdown={autoPlayCountdown}
                  onCancelAutoPlay={cancelAutoPlay}
                />
              )}

              <StatusBar message={statusMsg} visible={statusVisible} />

              {/* ── Video ready banner ─────────────────────── */}
              {videoId && !anyActive && (
                <a
                  href={`/api/video/${videoId}`}
                  download={`hypnos_${videoId}.mp4`}
                  className="video-ready-banner"
                >
                  <span>🎬 Video sẵn sàng!</span>
                  <span className="video-ready-btn">Tải xuống MP4 →</span>
                </a>
              )}

              <PlayerCard
                audio={audio}
                captionRef={captionRef}
                controlsVisible={controlsVisible}
                progressVisible={progressVisible}
                downloadVisible={downloadVisible}
                totalSentences={totalSentences}
                playedCount={playedCount}
                cardDotState={cardDotState}
                currentTopic={currentTopic}
              />

              {/* ── Discuss panel ──────────────────────────── */}
              {activePage === 'learn' && (
                <DiscussPanel
                  sessionId={discussSessionId}
                  instruct={selectedVoice?.instruct || ''}
                  visible={!!discussSessionId && !learnActive}
                />
              )}

            </div>
          </div>
        </div>
      </div>
    </>
  )
}
