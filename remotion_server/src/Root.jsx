import { Composition, registerRoot } from 'remotion';
import { VideoComposition } from './Composition.jsx';

const RemotionRoot = () => (
  <Composition
    id="Video"
    component={VideoComposition}
    durationInFrames={300}
    fps={15}
    width={1024}
    height={1024}
    defaultProps={{
      images: [],
      timings: [],
      sentences: [],
      sentenceTimings: [],
      audioSrc: '',
    }}
  />
);

registerRoot(RemotionRoot);
