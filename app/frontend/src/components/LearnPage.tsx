import { useState, useRef } from 'react'
import { Search, Play, Square, ChevronLeft, ChevronRight, Video } from 'lucide-react'
import { Button } from './ui/button'

interface LearnPageProps {
  isActive: boolean
  onStart: (topic: string) => void
  onStop: () => void
  onStartVideo: (topic: string) => void
  isVideoGenerating: boolean
}

interface Domain {
  label: string
  icon: string
  topics: string[]
}

const DOMAINS: Domain[] = [
  {
    label: 'AI & ML',
    icon: '🤖',
    topics: ['Machine Learning', 'Deep Learning', 'Neural Networks', 'Transformer', 'RAG', 'Reinforcement Learning', 'Computer Vision', 'NLP'],
  },
  {
    label: 'DevOps',
    icon: '⚙️',
    topics: ['Docker', 'Kubernetes', 'CI/CD Pipeline', 'Terraform', 'Ansible', 'Helm', 'GitOps', 'Jenkins'],
  },
  {
    label: 'Web Dev',
    icon: '🌐',
    topics: ['React Hooks', 'TypeScript', 'REST API', 'GraphQL', 'WebSockets', 'Next.js', 'Vite', 'Micro Frontends'],
  },
  {
    label: 'Database',
    icon: '🗄️',
    topics: ['PostgreSQL', 'Redis', 'MongoDB', 'SQL Indexing', 'ACID', 'Database Sharding', 'ClickHouse', 'Elasticsearch'],
  },
  {
    label: 'Bảo mật',
    icon: '🔒',
    topics: ['JWT', 'OAuth 2.0', 'HTTPS & TLS', 'SQL Injection', 'Zero Trust', 'CORS', 'CSP', 'XSS'],
  },
  {
    label: 'Cloud',
    icon: '☁️',
    topics: ['AWS Lambda', 'Microservices', 'Load Balancing', 'CDN', 'API Gateway', 'Event-Driven Architecture', 'CQRS', 'Service Mesh'],
  },
  {
    label: 'Kinh tế',
    icon: '💰',
    topics: ['Lãi suất', 'Lạm phát', 'GDP', 'Cổ phiếu', 'Trái phiếu', 'Forex', 'Phân tích kỹ thuật', 'Quỹ ETF', 'Đòn bẩy tài chính', 'Dòng tiền'],
  },
  {
    label: 'Đầu tư',
    icon: '📈',
    topics: ['Giá trị nội tại', 'P/E Ratio', 'Phân tích cơ bản', 'Quản lý rủi ro', 'Danh mục đầu tư', 'Market Cap', 'Short Selling', 'Options'],
  },
  {
    label: 'Data Science',
    icon: '📊',
    topics: ['Pandas', 'NumPy', 'Data Visualization', 'Thống kê', 'A/B Testing', 'Feature Engineering', 'Data Pipeline', 'Power BI'],
  },
  {
    label: 'Mobile',
    icon: '📱',
    topics: ['React Native', 'Flutter', 'SwiftUI', 'Jetpack Compose', 'PWA', 'App Store Optimization', 'Push Notification', 'Deep Link'],
  },
  {
    label: 'Blockchain',
    icon: '🔗',
    topics: ['Smart Contract', 'DeFi', 'NFT', 'Ethereum', 'Consensus Mechanism', 'Layer 2', 'DAO', 'Tokenomics'],
  },
  {
    label: 'Mạng & Hệ thống',
    icon: '📡',
    topics: ['TCP/IP', 'DNS', 'HTTP/2 & HTTP/3', 'WebRTC', 'VPN', 'OSI Model', 'BGP', 'Firewall'],
  },
  {
    label: 'Thuật toán',
    icon: '📐',
    topics: ['Big O Notation', 'Dynamic Programming', 'Graph Theory', 'Linear Algebra', 'Xác suất thống kê', 'Đệ quy', 'Binary Search', 'Sorting Algorithms'],
  },
  {
    label: 'Kinh doanh',
    icon: '🏢',
    topics: ['OKR', 'Agile & Scrum', 'Product Management', 'Design Thinking', 'Lean Startup', 'Business Model Canvas', 'Go-to-Market', 'KPI'],
  },
  {
    label: 'Tâm lý học',
    icon: '🧠',
    topics: ['Cognitive Bias', 'Tư duy phản biện', 'Dunning-Kruger', 'Tâm lý hành vi', 'Flow State', 'Growth Mindset', 'Hiệu ứng mỏ neo', 'Tâm lý đám đông'],
  },
  {
    label: 'Khoa học',
    icon: '🔭',
    topics: ['Cơ học lượng tử', 'Thuyết tương đối', 'CRISPR', 'Biến đổi khí hậu', 'Vũ trụ học', 'Hố đen', 'Năng lượng tái tạo', 'AGI'],
  },
]

export function LearnPage({ isActive, onStart, onStop, onStartVideo, isVideoGenerating }: Readonly<LearnPageProps>) {
  const [topic, setTopic]           = useState('')
  const [activeDomain, setActiveDomain] = useState(0)
  const tabsRef = useRef<HTMLDivElement>(null)

  function handleStart() {
    const t = topic.trim()
    if (t) onStart(t)
  }

  function handleStartVideo() {
    const t = topic.trim()
    if (t) onStartVideo(t)
  }

  function handleChipClick(t: string) {
    setTopic(t)
  }

  function scrollTabs(dir: 'left' | 'right') {
    if (!tabsRef.current) return
    tabsRef.current.scrollBy({ left: dir === 'left' ? -160 : 160, behavior: 'smooth' })
  }

  const domain = DOMAINS[activeDomain]

  return (
    <div className="flex flex-col gap-3">

      {/* Search row */}
      <div className="flex gap-2.5 items-center">
        <div className="flex-1 relative flex items-center">
          <Search size={16} className="absolute left-4 text-[#64748b] pointer-events-none" />
          <input
            className="glass-input"
            placeholder="Nhập chủ đề hoặc chọn gợi ý bên dưới..."
            value={topic}
            onChange={e => setTopic(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !isActive && !isVideoGenerating) handleStart() }}
            autoComplete="off"
            disabled={isActive || isVideoGenerating}
          />
        </div>
        {isActive ? (
          <Button variant="destructive" onClick={onStop}>
            <Square size={13} fill="currentColor" />
            Dừng
          </Button>
        ) : (
          <>
            <Button onClick={handleStart} disabled={!topic.trim() || isVideoGenerating}>
              <Play size={13} fill="currentColor" />
              Bắt đầu
            </Button>
            <Button
              variant="outline"
              onClick={handleStartVideo}
              disabled={!topic.trim() || isVideoGenerating}
              title="Tạo video MP4 kèm ảnh minh họa"
            >
              <Video size={13} />
              {isVideoGenerating ? 'Đang tạo...' : 'Tạo Video'}
            </Button>
          </>
        )}
      </div>

      {/* Domain tabs + chips — hidden while active */}
      {!isActive && (
        <div className="learn-suggestions">

          {/* Domain tab bar */}
          <div className="learn-tab-bar">
            <button
              type="button"
              className="learn-tab-arrow"
              onClick={() => scrollTabs('left')}
              aria-label="scroll left"
            >
              <ChevronLeft size={14} />
            </button>

            <div className="learn-tabs" ref={tabsRef}>
              {DOMAINS.map((d, i) => (
                <button
                  key={d.label}
                  type="button"
                  className={`learn-domain-tab ${activeDomain === i ? 'active' : ''}`}
                  onClick={() => setActiveDomain(i)}
                >
                  <span>{d.icon}</span>
                  <span>{d.label}</span>
                </button>
              ))}
            </div>

            <button
              type="button"
              className="learn-tab-arrow"
              onClick={() => scrollTabs('right')}
              aria-label="scroll right"
            >
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Chips for active domain */}
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
      )}
    </div>
  )
}
