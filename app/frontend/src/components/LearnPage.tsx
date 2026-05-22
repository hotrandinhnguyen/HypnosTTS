import { useState } from 'react'
import { Search, Play, Square, Sparkles } from 'lucide-react'
import { Button } from './ui/button'

interface LearnPageProps {
  isActive: boolean
  onStart: (topic: string) => void
  onStop: () => void
}

interface Domain {
  label: string
  icon: string
  topics: string[]
}

const DOMAINS: Domain[] = [
  {
    label: 'AI & Machine Learning',
    icon: '🤖',
    topics: ['Machine Learning', 'Deep Learning', 'Neural Networks', 'Transformer', 'RAG', 'Reinforcement Learning', 'Computer Vision', 'NLP'],
  },
  {
    label: 'DevOps',
    icon: '⚙️',
    topics: ['Docker', 'Kubernetes', 'CI/CD Pipeline', 'Terraform', 'Ansible', 'Helm', 'GitOps', 'Jenkins'],
  },
  {
    label: 'Web Development',
    icon: '🌐',
    topics: ['React Hooks', 'TypeScript', 'REST API', 'GraphQL', 'WebSockets', 'Next.js', 'Vite', 'Micro Frontends'],
  },
  {
    label: 'Cơ sở dữ liệu',
    icon: '🗄️',
    topics: ['PostgreSQL', 'Redis', 'MongoDB', 'SQL Indexing', 'ACID', 'Database Sharding', 'ClickHouse', 'Elasticsearch'],
  },
  {
    label: 'Bảo mật',
    icon: '🔒',
    topics: ['JWT', 'OAuth 2.0', 'HTTPS & TLS', 'SQL Injection', 'Zero Trust', 'CORS', 'CSP', 'XSS'],
  },
  {
    label: 'Cloud & Kiến trúc',
    icon: '☁️',
    topics: ['AWS Lambda', 'Microservices', 'Load Balancing', 'CDN', 'API Gateway', 'Event-Driven Architecture', 'CQRS', 'Service Mesh'],
  },
]

export function LearnPage({ isActive, onStart, onStop }: Readonly<LearnPageProps>) {
  const [topic, setTopic] = useState('')

  function handleStart() {
    const t = topic.trim()
    if (t) onStart(t)
  }

  function handleChipClick(t: string) {
    setTopic(t)
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Search row */}
      <div className="flex gap-2.5 items-center">
        <div className="flex-1 relative flex items-center">
          <Search size={16} className="absolute left-4 text-[#64748b] pointer-events-none" />
          <input
            className="glass-input"
            placeholder="Nhập chủ đề hoặc chọn gợi ý bên dưới..."
            value={topic}
            onChange={e => setTopic(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !isActive) handleStart() }}
            autoComplete="off"
            disabled={isActive}
          />
        </div>
        {isActive ? (
          <Button variant="destructive" onClick={onStop}>
            <Square size={13} fill="currentColor" />
            Dừng
          </Button>
        ) : (
          <Button onClick={handleStart} disabled={!topic.trim()}>
            <Play size={13} fill="currentColor" />
            Bắt đầu
          </Button>
        )}
      </div>

      {/* Topic suggestions — hidden while session is active */}
      {!isActive && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Sparkles size={12} className="text-violet-400" />
            <span className="learn-section-label">Gợi ý theo lĩnh vực</span>
          </div>

          {DOMAINS.map(domain => (
            <div key={domain.label} className="learn-domain-row">
              <div className="learn-domain-label">
                <span>{domain.icon}</span>
                <span>{domain.label}</span>
              </div>
              <div className="learn-chips-row">
                {domain.topics.map(t => (
                  <button
                    key={t}
                    type="button"
                    className={`topic-chip ${topic === t ? 'active' : ''}`}
                    onClick={() => handleChipClick(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
