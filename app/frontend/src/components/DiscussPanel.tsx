import { useState, useRef, useEffect } from 'react'
import { Button } from './ui/button'

interface Message {
  role: 'user' | 'ai'
  text: string
}

interface DiscussPanelProps {
  sessionId: number | null
  instruct: string
  visible: boolean
}

export function DiscussPanel({ sessionId, instruct, visible }: Readonly<DiscussPanelProps>) {
  const [messages, setMessages]   = useState<Message[]>([])
  const [input, setInput]         = useState('')
  const [responding, setResponding] = useState(false)

  const endRef        = useRef<HTMLDivElement>(null)
  const audioCtxRef   = useRef<AudioContext | null>(null)
  const nextTimeRef   = useRef(0)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, responding])

  function getCtx(): AudioContext {
    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
      audioCtxRef.current = new AudioContext()
      nextTimeRef.current = 0
    }
    return audioCtxRef.current
  }

  async function scheduleAudio(ab: ArrayBuffer) {
    const ctx = getCtx()
    const buf = await ctx.decodeAudioData(ab)
    const when = Math.max(ctx.currentTime + 0.02, nextTimeRef.current)
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(ctx.destination)
    src.start(when)
    nextTimeRef.current = when + buf.duration
  }

  async function sendQuestion() {
    if (!input.trim() || responding || !sessionId) return
    const question = input.trim()
    setInput('')
    setResponding(true)
    nextTimeRef.current = 0

    setMessages(prev => [...prev, { role: 'user', text: question }])

    const history = messages.map(m => ({ role: m.role === 'user' ? 'user' : 'ai', text: m.text }))
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${location.host}/ws/discuss`)
    ws.binaryType = 'arraybuffer'

    ws.onopen = () => ws.send(JSON.stringify({ session_id: sessionId, question, history, instruct }))

    ws.onmessage = async (evt) => {
      if (typeof evt.data === 'string') {
        const msg = JSON.parse(evt.data as string)
        if (msg.type === 'done') {
          setMessages(prev => [...prev, { role: 'ai', text: msg.full_text || '' }])
          setResponding(false)
        } else if (msg.type === 'error') {
          setResponding(false)
        }
      } else {
        await scheduleAudio((evt.data as ArrayBuffer).slice(0))
      }
    }

    ws.onerror  = () => setResponding(false)
    ws.onclose  = () => { if (responding) setResponding(false) }
  }

  if (!visible || !sessionId) return null

  return (
    <div className="discuss-panel">
      <div className="discuss-header">
        <span className="discuss-title">💬 Thảo luận</span>
        <span className="discuss-hint">Hỏi bất kỳ điều gì về bài giảng vừa nghe</span>
      </div>

      <div className="discuss-messages">
        {messages.length === 0 && !responding && (
          <div className="discuss-empty">Đặt câu hỏi về bài giảng vừa nghe...</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`discuss-msg discuss-msg--${m.role}`}>
            {m.text}
          </div>
        ))}
        {responding && (
          <div className="discuss-thinking">
            <span className="status-wave-bar" />
            <span className="status-wave-bar" />
            <span className="status-wave-bar" />
            <span>AI đang trả lời...</span>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="discuss-input-row">
        <input
          className="glass-input"
          style={{ paddingLeft: '16px' }}
          placeholder="Hỏi về bài giảng..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !responding) sendQuestion() }}
          disabled={responding}
          autoComplete="off"
        />
        <Button onClick={sendQuestion} disabled={!input.trim() || responding}>
          Hỏi
        </Button>
      </div>
    </div>
  )
}
