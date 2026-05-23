import { useCurrentFrame, useVideoConfig, Img, Audio, AbsoluteFill } from 'remotion';
import { TransitionSeries, linearTiming } from '@remotion/transitions';
import { fade } from '@remotion/transitions/fade';

const TRANS_FRAMES = 13; // 0.5s at 25fps

// 5 Ken Burns presets — cycled per image
const KB_PRESETS = [
  (p) => `scale(${(1 + p * 0.06).toFixed(4)})`,                              // zoom-in center
  (p) => `scale(${(1.06 - p * 0.06).toFixed(4)})`,                          // zoom-out
  (p) => `scale(1.05) translateX(${(-p * 3).toFixed(2)}%)`,                  // pan right
  (p) => `scale(1.05) translateX(${(p * 3).toFixed(2)}%)`,                   // pan left
  (p) => `scale(1.05) translateY(${(-p * 3).toFixed(2)}%)`,                  // pan up
];

const ImageSlide = ({ src, idx, durationInFrames }) => {
  const frame = useCurrentFrame();
  const progress = durationInFrames > 0
    ? Math.max(0, Math.min(1, frame / durationInFrames))
    : 0;

  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      {/* Ken Burns + color grade */}
      <AbsoluteFill style={{
        transform: KB_PRESETS[idx % KB_PRESETS.length](progress),
        transformOrigin: 'center center',
        filter: 'contrast(1.08) saturate(1.12)',
      }}>
        <Img src={src} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      </AbsoluteFill>

      {/* Vignette overlay */}
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.45) 100%)',
        pointerEvents: 'none',
      }} />
    </AbsoluteFill>
  );
};

export const VideoComposition = ({ images, timings, sentences, sentenceTimings, audioSrc }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Word-synced subtitle with fade-in
  let subtitle = '';
  let subOpacity = 1;
  for (let i = 0; i < sentenceTimings.length; i++) {
    const [s, e] = sentenceTimings[i];
    if (currentTime >= s && currentTime < e) {
      const words      = sentences[i].split(' ');
      const dur        = e - s;
      const wordIdx    = Math.floor(((currentTime - s) / dur) * words.length);
      const groupStart = Math.floor(wordIdx / 4) * 4;
      // Fade-in: measure frames since this word group started
      const groupStartTime  = s + dur * (groupStart / words.length);
      const framesSinceGroup = (currentTime - groupStartTime) * fps;
      subOpacity = Math.min(1, framesSinceGroup / 6);
      subtitle   = words.slice(groupStart, groupStart + 4).join(' ');
      break;
    }
  }

  return (
    <AbsoluteFill style={{ background: '#000' }}>
      {/* Images: Ken Burns + crossfade transitions */}
      <TransitionSeries>
        {images.flatMap((src, i) => {
          const [start, end] = timings[i] ?? [0, 1];
          const durFrames = Math.max(Math.round((end - start) * fps), 2);
          const items = [];
          if (i > 0) {
            items.push(
              <TransitionSeries.Transition
                key={`t${i}`}
                timing={linearTiming({ durationInFrames: TRANS_FRAMES })}
                presentation={fade()}
              />
            );
          }
          items.push(
            <TransitionSeries.Sequence key={`s${i}`} durationInFrames={durFrames}>
              <ImageSlide src={src} idx={i} durationInFrames={durFrames} />
            </TransitionSeries.Sequence>
          );
          return items;
        })}
      </TransitionSeries>

      {/* Audio */}
      {audioSrc && <Audio src={audioSrc} />}

      {/* Subtitle with fade-in */}
      {subtitle && (
        <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 44 }}>
          <div style={{
            opacity: subOpacity,
            background: 'rgba(0,0,0,0.65)',
            color: '#FFEF80',
            fontSize: 30,
            fontFamily: 'Arial, sans-serif',
            fontWeight: 'bold',
            padding: '8px 24px',
            borderRadius: 8,
            maxWidth: '82%',
            textAlign: 'center',
            lineHeight: 1.4,
          }}>
            {subtitle}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
