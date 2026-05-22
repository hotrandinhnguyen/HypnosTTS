import {
  useState,
  useEffect,
  useRef,
  useCallback,
} from 'react'
import { Play, Square, Search } from 'lucide-react'

import { useAudio } from './hooks/useAudio'
import { Button } from './components/ui/button'
import { NavSidebar } from './components/NavSidebar'
import type { Page } from './components/NavSidebar'
import type { HistoryItem } from './components/Sidebar'
import { VoicePicker } from './components/VoicePicker'
import type { Voice } from './components/VoicePicker'
import { StatusBar } from './components/StatusBar'
import { PlayerCard } from './components/PlayerCard'
import { ChapterNav } from './components/ChapterNav'
import { StorySearch } from './components/StorySearch'

type CardDotState = 'idle' | 'playing' | 'done'

const PAGE_META: Record<Page, { title: string; titleAccent: string; subtitle: string }> = {
  learn: {
    title: 'Học',
    titleAccent: 'Tập',
    subtitle: 'AI tổng hợp bài học · TTS giọng nhất quán',
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

  // ── Learn tab ─────────────────────────────────────────────────
  const [topic, setTopic] = useState('')
  const [learnActive, setLearnActive] = useState(false)

  // ── Story tab ─────────────────────────────────────────────────
  const [storyActive, setStoryActive] = useState(false)

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
      if (activePage === 'story') {
        const rows: HistoryItem[] = await (await fetch('/api/story/history')).json()
        setHistoryItems(rows)
      } else {
        const rows: HistoryItem[] = await (await fetch('/api/history')).json()
        setHistoryItems(rows)
      }
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
      setStatusVisible(false)
      setControlsVisible(true)
      setDownloadVisible(true)
      setCardDotState('done')
      resetButtons()
      loadHistory()
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

  // ── Open WebSocket ────────────────────────────────────────────
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
    ws.onclose = () => {
      resetButtons()
    }
    return ws
  }

  // ── Reset buttons ─────────────────────────────────────────────
  function resetButtons() {
    setLearnActive(false)
    setStoryActive(false)
    wsRef.current = null
  }

  // ── Stop ──────────────────────────────────────────────────────
  function stopActive() {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    audio.stop()
    resetPlayer()
    resetButtons()
  }

  // ── Learn session ─────────────────────────────────────────────
  function startLearnSession() {
    const t = topic.trim()
    if (!t) return
    setCurrentTopic(t)
    setStatusMsg('Đang kết nối...')
    setStatusVisible(true)
    setLearnActive(true)
    openWs('/ws/lesson', { topic: t, instruct: selectedVoice?.instruct || '' })
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
  function goToPrev() {
    if (prevUrlRef.current) startStorySession(prevUrlRef.current)
  }
  function goToNext() {
    if (nextUrlRef.current) startStorySession(nextUrlRef.current)
  }

  const meta = PAGE_META[activePage]

  return (
    <>
      {/* Orbs */}
      <div className="orb orb-1" />
      <div className="orb orb-2" />
      <div className="orb orb-3" />
      <div className="orb orb-4" />

      {/* Layout */}
      <div className="app-layout">
        <NavSidebar
          activePage={activePage}
          onNavigate={handleNavigate}
          historyItems={historyItems}
          activeHistoryId={activeHistoryId}
          onHistorySelect={handleHistorySelect}
        />

        {/* Main content — key triggers .page-enter animation on page switch */}
        <div className="main-content">
          <div key={activePage} className="page-enter" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>

            {/* Page header */}
            <header className="page-header">
              <div className="page-title-group">
                <h1 className="page-title">
                  {meta.title}
                  <span className="page-title-accent"> {meta.titleAccent}</span>
                </h1>
                <p className="page-subtitle">{meta.subtitle}</p>
              </div>
            </header>

            {/* Page body */}
            <div className="page-body">

              {/* Voice picker */}
              <VoicePicker
                voices={voices}
                selectedKey={selectedVoice?.key ?? ''}
                onSelect={setSelectedVoice}
              />

              {/* Learn page */}
              {activePage === 'learn' && (
                <div className="flex gap-2.5 items-center">
                  <div className="flex-1 relative flex items-center">
                    <Search size={16} className="absolute left-4 text-[#64748b] pointer-events-none" />
                    <input
                      className="glass-input"
                      placeholder="Nhập chủ đề muốn học (VD: Deep Learning, Docker, React hooks...)"
                      value={topic}
                      onChange={e => setTopic(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && !learnActive) startLearnSession() }}
                      autoComplete="off"
                    />
                  </div>
                  {learnActive ? (
                    <Button variant="destructive" onClick={stopActive}>
                      <Square size={13} fill="currentColor" />
                      Dừng
                    </Button>
                  ) : (
                    <Button onClick={startLearnSession}>
                      <Play size={13} fill="currentColor" />
                      Bắt đầu
                    </Button>
                  )}
                </div>
              )}

              {/* Story page */}
              {activePage === 'story' && (
                <>
                  <StorySearch
                    isActive={storyActive}
                    onStartSession={startStorySession}
                    onStop={stopActive}
                  />
                  <ChapterNav
                    visible={chapterNavVisible}
                    chapterTitle={chapterTitle}
                    prevUrl={prevUrlRef.current}
                    nextUrl={nextUrlRef.current}
                    onPrev={goToPrev}
                    onNext={goToNext}
                  />
                </>
              )}

              {/* Status bar */}
              <StatusBar message={statusMsg} visible={statusVisible} />

              {/* Player card */}
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

            </div>
          </div>
        </div>
      </div>
    </>
  )
}
