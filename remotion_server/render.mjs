import { bundle } from '@remotion/bundler';
import { renderMedia, selectComposition } from '@remotion/renderer';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const args = JSON.parse(process.argv[2]);

const { durationInFrames, fps = 15, width = 1024, height = 1024, outputPath, ...props } = args;

console.log('[Remotion] Bundling...');
const bundled = await bundle({ entryPoint: path.resolve(__dirname, './src/Root.jsx') });

console.log('[Remotion] Selecting composition...');
const comp = await selectComposition({
  serveUrl: bundled,
  id: 'Video',
  inputProps: props,
});

console.log('[Remotion] Rendering', durationInFrames, 'frames...');
await renderMedia({
  composition: {
    ...comp,
    durationInFrames,
    fps,
    width,
    height,
  },
  serveUrl: bundled,
  codec: 'h264',
  outputLocation: outputPath,
  inputProps: props,
  concurrency: 8,
  hardwareAcceleration: 'if-possible',
  onProgress: ({ progress }) => {
    process.stdout.write(`\r[Remotion] ${Math.round(progress * 100)}%`);
  },
});

console.log('\nDONE:' + outputPath);
