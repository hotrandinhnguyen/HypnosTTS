(() => {
  // ── DOM refs ──────────────────────────────────────────────────
  const topicInput       = document.getElementById('topic-input');
  const startBtn         = document.getElementById('start-btn');
  const stopBtn          = document.getElementById('stop-btn');
  const storySearchInput = document.getElementById('story-search-input');
  const storySearchBtn   = document.getElementById('story-search-btn');
  const storyResults     = document.getElementById('story-results');
  const chapterPicker    = document.getElementById('chapter-picker');
  const selectedStoryEl  = document.getElementById('selected-story-name');
  const chapterNumInput  = document.getElementById('chapter-num-input');
  const storyStartBtn    = document.getElementById('story-start-btn');
  const storyStopBtn     = document.getElementById('story-stop-btn');
  const chapterNav       = document.getElementById('chapter-nav');
  const prevChapBtn      = document.getElementById('prev-chapter-btn');
  const nextChapBtn      = document.getElementById('next-chapter-btn');
  const chapterTitle     = document.getElementById('chapter-title-display');
  const statusBar     = document.getElementById('status-bar');
  const statusText    = document.getElementById('status-text');
  const caption       = document.getElementById('caption');
  const controls      = document.getElementById('controls');
  const pauseBtn      = document.getElementById('pause-btn');
  const pauseLabel    = document.getElementById('pause-label');
  const pauseIcon     = document.getElementById('pause-icon');
  const progressCont  = document.getElementById('progress-container');
  const progressFill  = document.getElementById('progress-fill');
  const progressLabel = document.getElementById('progress-label');
  const downloadBtn   = document.getElementById('download-btn');
  const volumeSlider  = document.getElementById('volume-slider');
  const historyList   = document.getElementById('history-list');
  const sidebarLabel  = document.getElementById('sidebar-history-label');

  // ── Voice state ───────────────────────────────────────────────
  let selectedInstruct = '';

  function selectVoice(btn) {
    document.querySelectorAll('.voice-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedInstruct = btn.dataset.instruct;
  }

  async function loadVoices() {
    const res = await fetch('/api/voices');
    const voices = await res.json();
    const picker = document.getElementById('voice-picker');
    picker.innerHTML = '';
    voices.forEach((v, i) => {
      const btn = document.createElement('button');
      btn.className = 'voice-btn' + (i === 0 ? ' active' : '');
      btn.textContent = v.label;
      btn.dataset.instruct = v.instruct;
      btn.addEventListener('click', () => selectVoice(btn));
      picker.appendChild(btn);
    });
    if (voices.length > 0) selectedInstruct = voices[0].instruct;
  }

  // ── Tab switching ─────────────────────────────────────────────
  let activeTab = 'learn';

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activeTab = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
      document.getElementById(`tab-${activeTab}`).classList.remove('hidden');
      sidebarLabel.textContent = activeTab === 'story' ? 'Truyện đã đọc' : 'Lịch sử';
      loadHistory();
      resetPlayer();
    });
  });

  // ── Audio state ───────────────────────────────────────────────
  let audioCtx       = null;
  let gainNode       = null;
  let pendingSpans   = [];
  let isPaused       = false;
  let totalSentences = 0;
  let playedCount    = 0;
  let nextStartTime  = 0;
  let playbackSpeed  = 1;
  let sessionBuffers = [];
  let currentTopic   = '';
  let activeWs       = null;

  // Story nav state
  let prevUrl = null;
  let nextUrl = null;

  // ── Audio helpers ─────────────────────────────────────────────

  function ensureAudioCtx() {
    if (!audioCtx) {
      audioCtx = new AudioContext();
      gainNode  = audioCtx.createGain();
      gainNode.gain.value = Number.parseFloat(volumeSlider.value);
      gainNode.connect(audioCtx.destination);
    }
    if (audioCtx.state === 'suspended') audioCtx.resume();
  }

  async function decodeWav(ab) { return audioCtx.decodeAudioData(ab); }

  function scheduleBuffer(audioBuffer, spanEl) {
    const src = audioCtx.createBufferSource();
    src.buffer = audioBuffer;
    src.playbackRate.value = playbackSpeed;
    src.connect(gainNode);

    const startAt = Math.max(audioCtx.currentTime, nextStartTime);
    src.start(startAt);
    nextStartTime = startAt + audioBuffer.duration / playbackSpeed;

    const delay = Math.max(0, (startAt - audioCtx.currentTime) * 1000);
    setTimeout(() => {
      document.querySelectorAll('.sentence.active').forEach(el => el.classList.replace('active', 'done'));
      spanEl.classList.add('active');
      spanEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, delay);

    src.onended = () => {
      spanEl.classList.replace('active', 'done');
      playedCount++;
      updateProgress();
    };
  }

  function updateProgress() {
    progressLabel.textContent = `${playedCount} / ${totalSentences}`;
    const pct = totalSentences > 0 ? (playedCount / totalSentences) * 100 : 0;
    progressFill.style.width = pct + '%';
  }

  // ── WS message handlers ───────────────────────────────────────

  function handleTextFrame(msg) {
    if (msg.type === 'status') {
      setStatus(msg.data);
    } else if (msg.type === 'chapter_info') {
      prevUrl = msg.prev || null;
      nextUrl = msg.next || null;
      chapterTitle.textContent = msg.story ? `${msg.story} · ${msg.title}` : msg.title;
      prevChapBtn.disabled = !prevUrl;
      nextChapBtn.disabled = !nextUrl;
      chapterNav.classList.remove('hidden');
      if (msg.cached) hideStatus();
    } else if (msg.type === 'text') {
      totalSentences++;
      updateProgress();
      const placeholder = caption.querySelector('.caption-placeholder');
      if (placeholder) placeholder.remove();
      const span = document.createElement('span');
      span.className = 'sentence';
      span.textContent = ' ' + msg.data;
      caption.appendChild(span);
      pendingSpans.push(span);
      progressCont.classList.remove('hidden');
    } else if (msg.type === 'done') {
      hideStatus();
      controls.classList.remove('hidden');
      downloadBtn.classList.remove('hidden');
      setCardDot('done');
      resetButtons();
      loadHistory();
    } else if (msg.type === 'error') {
      setStatus('Lỗi: ' + msg.data);
      resetButtons();
    }
  }

  async function handleAudioFrame(data) {
    const span   = pendingSpans.shift();
    const cloned = data.slice(0);
    try {
      const audioBuffer = await decodeWav(cloned);
      sessionBuffers.push(audioBuffer);
      if (span) scheduleBuffer(audioBuffer, span);
      controls.classList.remove('hidden');
      setCardDot('playing');
    } catch (err) {
      console.error('[Audio] decode error:', err);
    }
  }

  // ── Generic session starter ───────────────────────────────────

  function resetPlayer() {
    caption.innerHTML = '<span class="caption-placeholder">Nội dung sẽ xuất hiện ở đây...</span>';
    pendingSpans   = [];
    sessionBuffers = [];
    totalSentences = 0;
    playedCount    = 0;
    nextStartTime  = 0;
    isPaused       = false;
    updateProgress();
    controls.classList.add('hidden');
    progressCont.classList.add('hidden');
    downloadBtn.classList.add('hidden');
    chapterNav.classList.add('hidden');
    hideStatus();
    setCardDot('idle');
  }

  function openWs(wsPath, payload) {
    ensureAudioCtx();
    resetPlayer();

    const ws = new WebSocket(`ws://${location.host}${wsPath}`);
    ws.binaryType = 'arraybuffer';
    activeWs = ws;

    ws.onopen = () => ws.send(JSON.stringify(payload));
    ws.onmessage = async (evt) => {
      if (typeof evt.data === 'string') handleTextFrame(JSON.parse(evt.data));
      else await handleAudioFrame(evt.data);
    };
    ws.onerror = () => { setStatus('Kết nối thất bại.'); resetButtons(); };
    ws.onclose = () => { resetButtons(); };
    return ws;
  }

  // ── Learn session ─────────────────────────────────────────────

  function startLearnSession() {
    const topic = topicInput.value.trim();
    if (!topic) return;
    currentTopic = topic;
    setStatus('Đang kết nối...');
    startBtn.disabled = true;
    startBtn.classList.add('hidden');
    stopBtn.classList.remove('hidden');
    openWs('/ws/lesson', { topic, instruct: selectedInstruct });
  }

  startBtn.addEventListener('click', startLearnSession);
  topicInput.addEventListener('keydown', e => { if (e.key === 'Enter') startLearnSession(); });

  // ── Story search + select ─────────────────────────────────────

  let selectedSlug = null;

  async function doSearch() {
    const q = storySearchInput.value.trim();
    if (!q) return;
    storySearchBtn.disabled = true;
    storySearchBtn.textContent = 'Đang tìm...';
    try {
      const res = await fetch(`/api/story/search?q=${encodeURIComponent(q)}`);
      const results = await res.json();
      renderStoryResults(results);
    } catch (e) {
      console.error('[Search]', e);
    }
    storySearchBtn.disabled = false;
    storySearchBtn.innerHTML = `
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
      </svg> Tìm`;
  }

  function selectStoryCard(card, r) {
    document.querySelectorAll('.story-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    selectedSlug = r.slug;
    selectedStoryEl.textContent = r.title;
    chapterNumInput.value = 1;
    chapterPicker.classList.remove('hidden');
    chapterNumInput.focus();
  }

  function renderStoryResults(results) {
    storyResults.innerHTML = '';
    chapterPicker.classList.add('hidden');
    if (!results.length) {
      storyResults.innerHTML = '<div class="no-results">Không tìm thấy truyện nào.</div>';
      storyResults.classList.remove('hidden');
      return;
    }
    results.forEach(r => {
      const card = document.createElement('div');
      card.className = 'story-card';
      card.innerHTML = `
        ${r.cover ? `<img class="story-cover" src="${r.cover}" alt="" loading="lazy" />` : '<div class="story-cover-placeholder"></div>'}
        <div class="story-info">
          <div class="story-title">${r.title}</div>
          ${r.latest_chapter ? `<div class="story-latest">${r.latest_chapter}</div>` : ''}
        </div>`;
      card.addEventListener('click', () => selectStoryCard(card, r));
      storyResults.appendChild(card);
    });
    storyResults.classList.remove('hidden');
  }

  storySearchBtn.addEventListener('click', doSearch);
  storySearchInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

  // ── Story session ─────────────────────────────────────────────

  function startStorySession(url) {
    if (!url) return;
    currentTopic = url;
    setStatus('Đang tải chương...');
    storySearchBtn.disabled = true;
    storySearchBtn.classList.add('hidden');
    storyStartBtn.disabled = true;
    storyStartBtn.classList.add('hidden');
    storyStopBtn.classList.remove('hidden');
    storyResults.classList.add('hidden');
    openWs('/ws/story', { url, instruct: selectedInstruct });
  }

  storyStartBtn.addEventListener('click', () => {
    if (!selectedSlug) return;
    const chapter = Number.parseInt(chapterNumInput.value, 10) || 1;
    startStorySession(`https://truyenfull.today/${selectedSlug}/chuong-${chapter}/`);
  });
  chapterNumInput.addEventListener('keydown', e => { if (e.key === 'Enter') storyStartBtn.click(); });
  prevChapBtn.addEventListener('click', () => { if (prevUrl) startStorySession(prevUrl); });
  nextChapBtn.addEventListener('click', () => { if (nextUrl) startStorySession(nextUrl); });

  // ── Stop ──────────────────────────────────────────────────────

  function stopActive() {
    if (activeWs) { activeWs.close(); activeWs = null; }
    // Đóng AudioContext để dừng hết audio đã buffer sẵn
    if (audioCtx) { audioCtx.close(); audioCtx = null; gainNode = null; }
    hideStatus();
    resetPlayer();
    resetButtons();
  }
  stopBtn.addEventListener('click', stopActive);
  storyStopBtn.addEventListener('click', stopActive);

  // ── Reset buttons ─────────────────────────────────────────────

  function resetButtons() {
    startBtn.disabled = false;
    startBtn.classList.remove('hidden');
    stopBtn.classList.add('hidden');
    storySearchBtn.disabled = false;
    storySearchBtn.classList.remove('hidden');
    storyStartBtn.disabled = false;
    storyStartBtn.classList.remove('hidden');
    storyStopBtn.classList.add('hidden');
    activeWs = null;
    setCardDot('idle');
  }

  function setCardDot(state) {
    const dot = document.querySelector('.card-dot');
    if (!dot) return;
    if (state === 'playing') dot.style.background = 'var(--cyan)';
    else if (state === 'done') dot.style.background = '#4ade80';
    else dot.style.background = 'var(--violet)';
  }

  // ── Pause / Resume ────────────────────────────────────────────

  pauseBtn.addEventListener('click', () => {
    if (!audioCtx) return;
    if (isPaused) {
      audioCtx.resume();
      isPaused = false;
      pauseLabel.textContent = 'Tạm dừng';
      pauseIcon.innerHTML = '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>';
    } else {
      audioCtx.suspend();
      isPaused = true;
      pauseLabel.textContent = 'Tiếp tục';
      pauseIcon.innerHTML = '<path d="M5 3l14 9-14 9V3z"/>';
    }
  });

  // ── Speed ─────────────────────────────────────────────────────

  document.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      playbackSpeed = Number.parseFloat(btn.dataset.speed);
      document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  // ── Volume ────────────────────────────────────────────────────

  volumeSlider.addEventListener('input', () => {
    if (gainNode) gainNode.gain.value = Number.parseFloat(volumeSlider.value);
  });

  // ── Download ──────────────────────────────────────────────────

  downloadBtn.addEventListener('click', async () => {
    if (!sessionBuffers.length) return;
    downloadBtn.disabled = true;
    downloadBtn.textContent = 'Đang xuất...';
    try {
      const sr = sessionBuffers[0].sampleRate;
      const total = sessionBuffers.reduce((s, b) => s + b.length, 0);
      const off = new OfflineAudioContext(1, total, sr);
      let offset = 0;
      for (const buf of sessionBuffers) {
        const src = off.createBufferSource();
        src.buffer = buf; src.connect(off.destination);
        src.start(offset / sr); offset += buf.length;
      }
      const rendered = await off.startRendering();
      const wav = _toWav(rendered);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([wav], { type: 'audio/wav' }));
      a.download = currentTopic.replace(/[^a-z0-9]/gi, '_').slice(0, 40) + '.wav';
      a.click();
    } catch (e) { console.error(e); }
    downloadBtn.disabled = false;
    downloadBtn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Tải xuống';
  });

  function _toWav(buffer) {
    const data = buffer.getChannelData(0);
    const samples = new Int16Array(data.length);
    for (let i = 0; i < data.length; i++) {
      const s = Math.max(-1, Math.min(1, data[i]));
      samples[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    const ab = new ArrayBuffer(44 + samples.byteLength);
    const v  = new DataView(ab);
    const ws = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.codePointAt(i)); };
    ws(0, 'RIFF'); v.setUint32(4, ab.byteLength - 8, true);
    ws(8, 'WAVE'); ws(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, buffer.sampleRate, true); v.setUint32(28, buffer.sampleRate * 2, true);
    v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    ws(36, 'data'); v.setUint32(40, samples.byteLength, true);
    new Int16Array(ab, 44).set(samples);
    return ab;
  }

  // ── History ───────────────────────────────────────────────────

  async function loadHistory() {
    if (activeTab === 'story') {
      const rows = await (await fetch('/api/story/history')).json();
      historyList.innerHTML = '';
      rows.forEach(row => {
        const li = document.createElement('li');
        const d  = new Date(row.created_at);
        const ds = `${d.getDate()}/${d.getMonth()+1} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
        li.innerHTML = `<span>${row.chapter_title || row.story_title}</span><span class="history-date">${row.story_title} · ${ds}</span>`;
        li.title = row.url;
        li.addEventListener('click', () => startStorySession(row.url));
        historyList.appendChild(li);
      });
    } else {
      const rows = await (await fetch('/api/history')).json();
      historyList.innerHTML = '';
      rows.forEach(row => {
        const li = document.createElement('li');
        const d  = new Date(row.created_at);
        const ds = `${d.getDate()}/${d.getMonth()+1} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
        li.innerHTML = `<span>${row.topic}</span><span class="history-date">${ds}</span>`;
        li.title = row.topic;
        li.addEventListener('click', () => replayLearnSession(row.id, li));
        historyList.appendChild(li);
      });
    }
  }

  async function replayLearnSession(sessionId, liEl) {
    ensureAudioCtx();
    resetPlayer();
    document.querySelectorAll('#history-list li').forEach(l => l.classList.remove('active'));
    liEl.classList.add('active');
    const lessons = await (await fetch(`/api/session/${sessionId}`)).json();
    for (const lesson of lessons) {
      totalSentences++;
      const span = document.createElement('span');
      span.className = 'sentence';
      span.textContent = ' ' + lesson.text;
      caption.querySelector('.caption-placeholder')?.remove();
      caption.appendChild(span);
      const raw = atob(lesson.audio);
      const ab  = new ArrayBuffer(raw.length);
      const view = new Uint8Array(ab);
      for (let i = 0; i < raw.length; i++) view[i] = raw.codePointAt(i) & 0xff;
      const buf = await decodeWav(ab);
      sessionBuffers.push(buf);
      scheduleBuffer(buf, span);
    }
    updateProgress();
    progressCont.classList.remove('hidden');
    controls.classList.remove('hidden');
    downloadBtn.classList.remove('hidden');
  }

  // ── Status helpers ────────────────────────────────────────────

  function setStatus(msg) { statusText.textContent = msg; statusBar.classList.remove('hidden'); }
  function hideStatus() { statusBar.classList.add('hidden'); }

  // ── Init ──────────────────────────────────────────────────────

  loadVoices();
  loadHistory();
})();
