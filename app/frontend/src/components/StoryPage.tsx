import { StorySearch } from './StorySearch'
import { ChapterNav } from './ChapterNav'

interface StoryPageProps {
  isActive: boolean
  onStartSession: (url: string) => void
  onStop: () => void
  chapterNavVisible: boolean
  chapterTitle: string
  prevUrl: string | null
  nextUrl: string | null
  onPrev: () => void
  onNext: () => void
  onJump: (url: string) => void
  autoPlay: boolean
  onAutoPlayChange: (v: boolean) => void
  autoPlayCountdown: number
  onCancelAutoPlay: () => void
}

export function StoryPage({
  isActive, onStartSession, onStop,
  chapterNavVisible, chapterTitle, prevUrl, nextUrl,
  onPrev, onNext, onJump,
  autoPlay, onAutoPlayChange, autoPlayCountdown, onCancelAutoPlay,
}: Readonly<StoryPageProps>) {
  return (
    <>
      <StorySearch
        isActive={isActive}
        onStartSession={onStartSession}
        onStop={onStop}
      />
      <ChapterNav
        visible={chapterNavVisible}
        chapterTitle={chapterTitle}
        prevUrl={prevUrl}
        nextUrl={nextUrl}
        onPrev={onPrev}
        onNext={onNext}
        onJump={onJump}
        autoPlay={autoPlay}
        onAutoPlayChange={onAutoPlayChange}
        autoPlayCountdown={autoPlayCountdown}
        onCancelAutoPlay={onCancelAutoPlay}
      />
    </>
  )
}
