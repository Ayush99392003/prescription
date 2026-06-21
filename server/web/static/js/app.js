/**
 * PRESCRIPTION Web Dashboard — app.js
 * Handles tab nav, MediaRecorder audio capture, API calls,
 * pipeline sequencing, and prescription display.
 */

/* ── State ─────────────────────────────────────────────────────── */
const state = {
  sessionId: null,
  mediaRecorder: null,
  audioChunks: [],
  audioBlob: null,
  audioUrl: null,
  isRecording: false,
  timerInterval: null,
  elapsedSeconds: 0,
  animationFrameId: null,
  analyser: null,
};

/* ── DOM refs ───────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);

const els = {
  tabBtns:       document.querySelectorAll('.tab-btn'),
  tabPanels:     document.querySelectorAll('.tab-panel'),
  sessionBadge:  $('session-badge'),
  btnRecord:     $('btn-record'),
  recordHint:    $('record-hint'),
  timerDisplay:  $('timer-display'),
  waveform:      $('waveform'),
  audioActions:  $('audio-actions'),
  audioPlayer:   $('audio-player'),
  btnRunPipeline:$('btn-run-pipeline'),
  // pipeline stages
  stages: {
    upload:    { card: $('stage-upload'),    detail: $('detail-upload'),    status: $('status-upload') },
    transcribe:{ card: $('stage-transcribe'),detail: $('detail-transcribe'),status: $('status-transcribe') },
    parse:     { card: $('stage-parse'),     detail: $('detail-parse'),     status: $('status-parse') },
    validate:  { card: $('stage-validate'),  detail: $('detail-validate'),  status: $('status-validate') },
    export:    { card: $('stage-export'),    detail: $('detail-export'),     status: $('status-export') },
  },
  transcriptPanel: $('transcript-panel'),
  transcriptText:  $('transcript-text'),
  // prescription
  rxEmpty:    $('rx-empty-state'),
  rxContent:  $('rx-content'),
  rxName:     $('rx-name'),
  rxAge:      $('rx-age'),
  rxGender:   $('rx-gender'),
  rxPid:      $('rx-pid'),
  rxDiagnosis:$('rx-diagnosis'),
  medTbody:   $('med-tbody'),
  medCountBadge: $('med-count-badge'),
  rxNotes:    $('rx-notes'),
  notesCard:  $('notes-card'),
  // export
  btnExportPdf:  $('btn-export-pdf'),
  btnDownloadPdf:$('btn-download-pdf'),
  exportStatus:  $('export-status'),
  sumSid:        $('sum-sid'),
  sumStatus:     $('sum-status'),
  sumMeds:       $('sum-meds'),
  sumElapsed:    $('sum-elapsed'),
  toast:         $('toast'),
};

/* ── Tab navigation ────────────────────────────────────────────── */
function activateTab(tabName) {
  els.tabBtns.forEach((btn) => {
    const active = btn.dataset.tab === tabName;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active);
  });
  els.tabPanels.forEach((panel) => {
    const active = panel.id === `panel-${tabName}`;
    panel.classList.toggle('active', active);
    panel.hidden = !active;
  });
}

els.tabBtns.forEach((btn) =>
  btn.addEventListener('click', () => activateTab(btn.dataset.tab))
);

/* ── Toast ──────────────────────────────────────────────────────── */
let toastTimeout;
function showToast(message, type = 'info') {
  clearTimeout(toastTimeout);
  els.toast.textContent = message;
  els.toast.className = `toast show ${type}`;
  toastTimeout = setTimeout(() => {
    els.toast.classList.remove('show');
  }, 3800);
}

/* ── API helpers ────────────────────────────────────────────────── */
const API = '/api/session';

async function apiPost(path, body = null, isFormData = false) {
  const opts = { method: 'POST' };
  if (body && !isFormData) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  } else if (isFormData) {
    opts.body = body; // FormData — browser sets Content-Type with boundary
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function apiGet(path) {
  const res = await fetch(path);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Session ────────────────────────────────────────────────────── */
async function startSession() {
  const data = await apiPost(`${API}/start`);
  state.sessionId = data.session_id;
  els.sessionBadge.textContent = state.sessionId;
  els.sumSid.textContent = state.sessionId;
  return data.session_id;
}

/* ── Pipeline stage helpers ─────────────────────────────────────── */
function setStage(name, status, detail = '') {
  const s = els.stages[name];
  if (!s) return;
  // Reset classes
  s.card.className = `stage-card ${status}`;
  s.status.className = `stage-status ${status}`;
  s.status.textContent = status === 'done' ? '✓' : status === 'error' ? '✕' : '●';
  if (detail) s.detail.textContent = detail;
}

function resetStages() {
  Object.keys(els.stages).forEach((name) => setStage(name, 'idle', 'Waiting...'));
}

/* ── Waveform visualiser ────────────────────────────────────────── */
function startVisualiser(stream) {
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  state.analyser = ctx.createAnalyser();
  state.analyser.fftSize = 256;
  src.connect(state.analyser);
  const canvas = els.waveform;
  const canvasCtx = canvas.getContext('2d');
  const bufLen = state.analyser.frequencyBinCount;
  const dataArr = new Uint8Array(bufLen);

  function draw() {
    state.animationFrameId = requestAnimationFrame(draw);
    state.analyser.getByteTimeDomainData(dataArr);
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = '#22d3ee';
    canvasCtx.beginPath();
    const sliceW = canvas.width / bufLen;
    let x = 0;
    for (let i = 0; i < bufLen; i++) {
      const v = dataArr[i] / 128.0;
      const y = (v * canvas.height) / 2;
      if (i === 0) canvasCtx.moveTo(x, y);
      else canvasCtx.lineTo(x, y);
      x += sliceW;
    }
    canvasCtx.lineTo(canvas.width, canvas.height / 2);
    canvasCtx.stroke();
  }
  draw();
}

function stopVisualiser() {
  if (state.animationFrameId) {
    cancelAnimationFrame(state.animationFrameId);
    state.animationFrameId = null;
  }
  const canvas = els.waveform;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}

/* ── Recording ──────────────────────────────────────────────────── */
function formatTime(secs) {
  const m = String(Math.floor(secs / 60)).padStart(2, '0');
  const s = String(secs % 60).padStart(2, '0');
  return `${m}:${s}`;
}

async function startRecording() {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    showToast('Microphone access denied.', 'error');
    return;
  }

  state.audioChunks = [];
  state.isRecording = true;
  els.btnRecord.classList.add('recording');
  els.recordHint.textContent = 'Recording… click to stop';
  els.audioActions.style.display = 'none';

  startVisualiser(stream);

  // Timer
  state.elapsedSeconds = 0;
  els.timerDisplay.textContent = '00:00';
  state.timerInterval = setInterval(() => {
    state.elapsedSeconds++;
    els.timerDisplay.textContent = formatTime(state.elapsedSeconds);
    if (state.elapsedSeconds >= 60) stopRecording(); // enforce max
  }, 1000);

  state.mediaRecorder = new MediaRecorder(stream);
  state.mediaRecorder.addEventListener('dataavailable', (e) => {
    if (e.data.size > 0) state.audioChunks.push(e.data);
  });
  state.mediaRecorder.addEventListener('stop', () => {
    stream.getTracks().forEach((t) => t.stop());
    state.audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
    state.audioUrl = URL.createObjectURL(state.audioBlob);
    els.audioPlayer.src = state.audioUrl;
    els.audioActions.style.display = 'flex';
    els.btnRunPipeline.disabled = false;
  });
  state.mediaRecorder.start();
}

function stopRecording() {
  if (!state.isRecording) return;
  state.isRecording = false;
  clearInterval(state.timerInterval);
  stopVisualiser();
  els.btnRecord.classList.remove('recording');
  els.recordHint.textContent = 'Click to record again';
  state.mediaRecorder?.stop();
}

els.btnRecord.addEventListener('click', () => {
  if (state.isRecording) stopRecording();
  else startRecording();
});

/* ── Full pipeline run ──────────────────────────────────────────── */
async function runPipeline() {
  if (!state.audioBlob) { showToast('No audio recorded.', 'error'); return; }

  els.btnRunPipeline.disabled = true;
  activateTab('pipeline');
  resetStages();

  try {
    // ── Start / reuse session ──────────────────────────────────
    if (!state.sessionId) await startSession();

    // ── Stage 1: Upload + Transcribe ──────────────────────────
    setStage('upload', 'running', 'Uploading audio…');
    setStage('transcribe', 'running', 'Transcribing…');

    const form = new FormData();
    form.append('file', state.audioBlob, 'recording.webm');
    const transcribeData = await apiPost(
      `${API}/${state.sessionId}/upload`, form, true
    );
    setStage('upload', 'done', 'Audio saved');
    setStage('transcribe', 'done', 'Transcript ready');

    els.transcriptText.textContent = transcribeData.transcript;
    els.transcriptPanel.style.display = 'block';

    // ── Stage 2: LLM Parse ────────────────────────────────────
    setStage('parse', 'running', 'Calling LLM…');
    const parseData = await apiPost(`${API}/${state.sessionId}/parse`);
    setStage('parse', 'done', `${parseData.medications.length} medication(s) found`);

    // ── Stage 3: Validate ─────────────────────────────────────
    setStage('validate', 'running', 'Matching database…');
    const validateData = await apiPost(`${API}/${state.sessionId}/validate`);
    setStage('validate', 'done', `${validateData.medications.length} validated`);

    // ── Stage 4: Export PDF ───────────────────────────────────
    setStage('export', 'running', 'Generating PDF…');
    const exportData = await apiPost(`${API}/${state.sessionId}/export`);
    setStage('export', 'done', 'PDF ready');

    // ── Populate Prescription tab ─────────────────────────────
    renderPrescription(parseData, validateData.medications);

    // ── Populate Export tab ───────────────────────────────────
    setupExport(exportData.pdf_url, validateData.medications.length);

    showToast('Pipeline complete! Review your prescription.', 'success');
    setTimeout(() => activateTab('prescription'), 600);

  } catch (err) {
    // Find which stage was running and mark it error
    Object.keys(els.stages).forEach((name) => {
      if (els.stages[name].card.classList.contains('running')) {
        setStage(name, 'error', err.message);
      }
    });
    showToast(`Error: ${err.message}`, 'error');
    els.btnRunPipeline.disabled = false;
  }
}

els.btnRunPipeline.addEventListener('click', runPipeline);

/* ── Prescription renderer ──────────────────────────────────────── */
function renderPrescription(parseData, validatedMeds) {
  const pat = parseData.patient;
  els.rxName.textContent     = pat.name || '—';
  els.rxAge.textContent      = pat.age || '—';
  els.rxGender.textContent   = pat.gender || '—';
  els.rxPid.textContent      = pat.id || '—';
  els.rxDiagnosis.textContent= parseData.diagnosis || '';

  // Medications
  els.medTbody.innerHTML = '';
  const meds = validatedMeds.length ? validatedMeds : parseData.medications;
  meds.forEach((med, i) => {
    const score = med.match_score ?? 0;
    const scoreClass = score >= 80 ? 'score-good' : score >= 60 ? 'score-ok' : 'score-bad';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><strong>${med.matched_name || med.name}</strong>
          ${med.matched_name && med.matched_name !== med.name
            ? `<br><span style="font-size:0.75rem;color:var(--color-text-muted)">${med.name}</span>`
            : ''}</td>
      <td><span class="score-badge ${scoreClass}">${score}</span></td>
      <td>${med.dosage || '—'}</td>
      <td>${med.frequency || '—'}</td>
      <td>${med.duration || '—'}</td>
      <td>${med.instructions || '—'}</td>
      <td>${med.price || '—'}</td>
      <td>${med.manufacturer || '—'}</td>
    `;
    els.medTbody.appendChild(tr);
  });

  els.medCountBadge.textContent = `${meds.length} medication${meds.length !== 1 ? 's' : ''}`;

  if (parseData.notes) {
    els.rxNotes.textContent = parseData.notes;
    els.notesCard.style.display = 'block';
  } else {
    els.notesCard.style.display = 'none';
  }

  els.rxEmpty.style.display   = 'none';
  els.rxContent.style.display = 'block';
}

/* ── Export tab setup ───────────────────────────────────────────── */
function setupExport(pdfUrl, medCount) {
  els.btnExportPdf.disabled = false;
  els.exportStatus.textContent = 'PDF is ready to download.';

  els.btnExportPdf.onclick = () => {
    els.btnDownloadPdf.href = pdfUrl;
    els.btnDownloadPdf.style.display = 'inline-flex';
    els.btnDownloadPdf.click();
    showToast('PDF downloaded!', 'success');
  };

  els.btnDownloadPdf.href = pdfUrl;
  els.btnDownloadPdf.download = `prescription_${state.sessionId}.pdf`;
  els.btnDownloadPdf.style.display = 'inline-flex';

  // Summary
  els.sumStatus.textContent  = '✓ Complete';
  els.sumStatus.style.color  = 'var(--color-green)';
  els.sumMeds.textContent    = `${medCount} medication${medCount !== 1 ? 's' : ''}`;
  els.sumElapsed.textContent = 'Done';

  // Fetch elapsed from API
  if (state.sessionId) {
    apiGet(`${API}/${state.sessionId}`)
      .then((s) => { els.sumElapsed.textContent = `${s.elapsed}s`; })
      .catch(() => {});
  }
}

/* ── Init ───────────────────────────────────────────────────────── */
(async () => {
  // Pre-create session on page load so the ID is visible immediately
  try {
    await startSession();
  } catch (_) {
    // Server may not be ready yet — session created on first run
  }
})();
