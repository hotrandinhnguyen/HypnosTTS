import { useRef, useState } from 'react'
import {
  Atom,
  BadgeDollarSign,
  BarChart3,
  Binary,
  Brain,
  BrainCircuit,
  BriefcaseBusiness,
  ChevronLeft,
  ChevronRight,
  Cloud,
  Cog,
  Database,
  Globe2,
  Link2,
  Play,
  RadioTower,
  Search,
  ShieldCheck,
  Smartphone,
  Square,
  TrendingUp,
  Video,
  type LucideIcon,
} from 'lucide-react'
import { Button } from './ui/button'

interface LearnPageProps {
  isActive: boolean
  onStart: (topic: string) => void
  onStop: () => void
  onStartVideo: (topic: string, nImages: number, durationMinutes: number, videoMode: string) => void
  isVideoGenerating: boolean
}

interface Domain {
  label: string
  icon: LucideIcon
  topics: string[]
}

const DOMAINS: Domain[] = [
  {
    label: 'AI & ML',
    icon: BrainCircuit,
    topics: ['Machine Learning', 'Deep Learning', 'Neural Networks', 'Transformer', 'RAG', 'Reinforcement Learning', 'Computer Vision', 'NLP'],
  },
  {
    label: 'DevOps',
    icon: Cog,
    topics: ['Docker', 'Kubernetes', 'CI/CD Pipeline', 'Terraform', 'Ansible', 'Helm', 'GitOps', 'Jenkins'],
  },
  {
    label: 'Web Dev',
    icon: Globe2,
    topics: ['React Hooks', 'TypeScript', 'REST API', 'GraphQL', 'WebSockets', 'Next.js', 'Vite', 'Micro Frontends'],
  },
  {
    label: 'Database',
    icon: Database,
    topics: ['PostgreSQL', 'Redis', 'MongoDB', 'SQL Indexing', 'ACID', 'Database Sharding', 'ClickHouse', 'Elasticsearch'],
  },
  {
    label: 'Bảo mật',
    icon: ShieldCheck,
    topics: ['JWT', 'OAuth 2.0', 'HTTPS & TLS', 'SQL Injection', 'Zero Trust', 'CORS', 'CSP', 'XSS'],
  },
  {
    label: 'Cloud',
    icon: Cloud,
    topics: ['AWS Lambda', 'Microservices', 'Load Balancing', 'CDN', 'API Gateway', 'Event-Driven Architecture', 'CQRS', 'Service Mesh'],
  },
  {
    label: 'Kinh tế',
    icon: BadgeDollarSign,
    topics: ['Lãi suất', 'Lạm phát', 'GDP', 'Cổ phiếu', 'Trái phiếu', 'Forex', 'Phân tích kỹ thuật', 'Quỹ ETF', 'Đòn bẩy tài chính', 'Dòng tiền'],
  },
  {
    label: 'Đầu tư',
    icon: TrendingUp,
    topics: ['Giá trị nội tại', 'P/E Ratio', 'Phân tích cơ bản', 'Quản lý rủi ro', 'Danh mục đầu tư', 'Market Cap', 'Short Selling', 'Options'],
  },
  {
    label: 'Data Science',
    icon: BarChart3,
    topics: ['Pandas', 'NumPy', 'Data Visualization', 'Thống kê', 'A/B Testing', 'Feature Engineering', 'Data Pipeline', 'Power BI'],
  },
  {
    label: 'Mobile',
    icon: Smartphone,
    topics: ['React Native', 'Flutter', 'SwiftUI', 'Jetpack Compose', 'PWA', 'App Store Optimization', 'Push Notification', 'Deep Link'],
  },
  {
    label: 'Blockchain',
    icon: Link2,
    topics: ['Smart Contract', 'DeFi', 'NFT', 'Ethereum', 'Consensus Mechanism', 'Layer 2', 'DAO', 'Tokenomics'],
  },
  {
    label: 'Mạng & hệ thống',
    icon: RadioTower,
    topics: ['TCP/IP', 'DNS', 'HTTP/2 & HTTP/3', 'WebRTC', 'VPN', 'OSI Model', 'BGP', 'Firewall'],
  },
  {
    label: 'Thuật toán',
    icon: Binary,
    topics: ['Big O Notation', 'Dynamic Programming', 'Graph Theory', 'Linear Algebra', 'Xác suất thống kê', 'Đệ quy', 'Binary Search', 'Sorting Algorithms'],
  },
  {
    label: 'Kinh doanh',
    icon: BriefcaseBusiness,
    topics: ['OKR', 'Agile & Scrum', 'Product Management', 'Design Thinking', 'Lean Startup', 'Business Model Canvas', 'Go-to-Market', 'KPI'],
  },
  {
    label: 'Tâm lý học',
    icon: Brain,
    topics: ['Cognitive Bias', 'Tư duy phản biện', 'Dunning-Kruger', 'Tâm lý hành vi', 'Flow State', 'Growth Mindset', 'Hiệu ứng mỏ neo', 'Tâm lý đám đông'],
  },
  {
    label: 'Khoa học',
    icon: Atom,
    topics: ['Cơ học lượng tử', 'Thuyết tương đối', 'CRISPR', 'Biến đổi khí hậu', 'Vũ trụ học', 'Hố đen', 'Năng lượng tái tạo', 'AGI'],
  },
]

export function LearnPage({ isActive, onStart, onStop, onStartVideo, isVideoGenerating }: Readonly<LearnPageProps>) {
  const [topic, setTopic] = useState('')
  const [activeDomain, setActiveDomain] = useState(0)
  const [durationMinutes, setDurationMinutes] = useState(0)
  const tabsRef = useRef<HTMLDivElement>(null)

  function handleStart() {
    const t = topic.trim()
    if (t) onStart(t)
  }

  function handleStartVideo() {
    const t = topic.trim()
    if (t) onStartVideo(t, 0, durationMinutes, 'i2v')
  }

  function scrollTabs(dir: 'left' | 'right') {
    if (!tabsRef.current) return
    tabsRef.current.scrollBy({ left: dir === 'left' ? -180 : 180, behavior: 'smooth' })
  }

  const domain = DOMAINS[activeDomain]
  const DomainIcon = domain.icon
  const canSubmit = !!topic.trim() && !isVideoGenerating

  return (
    <div className="learn-workspace">
      <div className="composer-panel">
        <div className="topic-command-row">
          <div className="input-wrapper">
            <Search size={16} className="input-icon" />
            <input
              className="glass-input"
              placeholder="Nhập chủ đề hoặc chọn một gợi ý bên dưới..."
              value={topic}
              onChange={e => setTopic(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !isActive && !isVideoGenerating) handleStart() }}
              autoComplete="off"
              disabled={isActive || isVideoGenerating}
            />
          </div>

          {isActive ? (
            <Button variant="destructive" onClick={onStop} className="primary-action-btn">
              <Square size={13} fill="currentColor" />
              Dừng
            </Button>
          ) : (
            <Button onClick={handleStart} disabled={!canSubmit} className="primary-action-btn">
              <Play size={13} fill="currentColor" />
              Bắt đầu
            </Button>
          )}
        </div>

        {!isActive && (
          <div className="video-command-row">
            <div className="video-command-copy">
              <Video size={14} />
              <span>Tạo video minh họa</span>
            </div>

            <label className="control-field">
              <span>Thời lượng</span>
              <select
                value={durationMinutes}
                onChange={e => setDurationMinutes(Number(e.target.value))}
                disabled={isVideoGenerating}
              >
                <option value={0}>Auto</option>
                <option value={1}>1 phút</option>
                <option value={2}>2 phút</option>
                <option value={3}>3 phút</option>
                <option value={5}>5 phút</option>
                <option value={10}>10 phút</option>
                <option value={15}>15 phút</option>
                <option value={20}>20 phút</option>
              </select>
            </label>

            <Button
              variant="outline"
              onClick={handleStartVideo}
              disabled={!canSubmit}
              title="Tạo video MP4 kèm ảnh minh họa"
            >
              <Video size={13} />
              {isVideoGenerating ? 'Đang tạo...' : 'Tạo video'}
            </Button>
          </div>
        )}
      </div>

      {!isActive && (
        <div className="learn-suggestions">
          <div className="learn-tab-bar">
            <button
              type="button"
              className="learn-tab-arrow"
              onClick={() => scrollTabs('left')}
              aria-label="Cuộn sang trái"
            >
              <ChevronLeft size={14} />
            </button>

            <div className="learn-tabs" ref={tabsRef}>
              {DOMAINS.map((d, i) => {
                const Icon = d.icon
                return (
                  <button
                    key={d.label}
                    type="button"
                    className={`learn-domain-tab ${activeDomain === i ? 'active' : ''}`}
                    onClick={() => setActiveDomain(i)}
                  >
                    <Icon size={13} />
                    <span>{d.label}</span>
                  </button>
                )
              })}
            </div>

            <button
              type="button"
              className="learn-tab-arrow"
              onClick={() => scrollTabs('right')}
              aria-label="Cuộn sang phải"
            >
              <ChevronRight size={14} />
            </button>
          </div>

          <div className="topic-panel-heading">
            <DomainIcon size={15} />
            <span>{domain.label}</span>
          </div>

          <div className="learn-chips-row">
            {domain.topics.map(t => (
              <button
                key={t}
                type="button"
                className={`topic-chip ${topic === t ? 'active' : ''}`}
                onClick={() => setTopic(t)}
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
