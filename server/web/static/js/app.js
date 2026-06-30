/**
 * PRESCRIPTION Web Dashboard — app.js  v2
 *
 * State-driven 4-screen flow:
 *   Screen 1: Voice Capture  (record / upload)
 *   Screen 2: Pipeline       (upload → transcribe → parse → validate)
 *   Screen 3: Rx Editor      (editable table, sticky approve)
 *   Screen 4: Export         (PDF preview, download, print)
 */

/* ══════════════════════════════════════════════════════════════════
   STATE
   ══════════════════════════════════════════════════════════════════ */
const state = {
  sessionId:       null,
  specialty:       'general',
  mediaRecorder:   null,
  audioChunks:     [],
  audioBlob:       null,
  audioUrl:        null,
  isRecording:     false,
  timerInterval:   null,
  elapsedSeconds:  0,
  animationId:     null,
  analyser:        null,
  // Autocomplete
  acTargetInput:   null,
  acDebounceTimer: null,
  // Stage elapsed timers (per stage)
  stageTimers:     {},
  stageStartTimes: {},
  // Last failed stage for retry
  lastFailedStage: null,
  currentScreen:   1,
  // Parse / validate results kept for retry and back-to-edit
  lastParseData:   null,
  lastValidData:   null,
};

/* ══════════════════════════════════════════════════════════════════
   DOM REFS
   ══════════════════════════════════════════════════════════════════ */
const $ = (id) => document.getElementById(id);

const els = {
  screens:      document.querySelectorAll('.screen'),
  dots:         document.querySelectorAll('.dot'),
  sessionBadge: $('session-badge'),

  // Screen 1
  inpDoctorName:   $('inp-doctor-name'),
  selSpecialty:    $('sel-specialty'),
  btnRecord:       $('btn-record'),
  recordHint:      $('record-hint'),
  timerDisplay:    $('timer-display'),
  waveform:        $('waveform'),
  audioActions:    $('audio-actions'),
  audioPlayer:     $('audio-player'),
  btnRunPipeline:  $('btn-run-pipeline'),
  fileInput:       $('inp-file-upload'),
  uploadAlt:       $('upload-alt'),

  // Screen 2
  stages: {
    upload:     {
      card:    $('stage-upload'),
      detail:  $('detail-upload'),
      status:  $('status-upload'),
      elapsed: $('elapsed-upload'),
    },
    transcribe: {
      card:    $('stage-transcribe'),
      detail:  $('detail-transcribe'),
      status:  $('status-transcribe'),
      elapsed: $('elapsed-transcribe'),
    },
    parse: {
      card:    $('stage-parse'),
      detail:  $('detail-parse'),
      status:  $('status-parse'),
      elapsed: $('elapsed-parse'),
    },
    validate: {
      card:    $('stage-validate'),
      detail:  $('detail-validate'),
      status:  $('status-validate'),
      elapsed: $('elapsed-validate'),
    },
  },
  transcriptPanel: $('transcript-panel'),
  transcriptText:  $('transcript-text'),
  retryRow:        $('retry-row'),
  btnRetry:        $('btn-retry'),

  // Screen 3
  rxName:           $('rx-name'),
  rxAge:            $('rx-age'),
  rxGender:         $('rx-gender'),
  rxPid:            $('rx-pid'),
  rxDiagnosis:      $('rx-diagnosis'),
  rxComplaints:     $('rx-complaints'),
  rxInvestigations: $('rx-investigations'),
  rxNotes:          $('rx-notes'),
  medTbody:         $('med-tbody'),
  btnAddMed:        $('btn-add-med'),
  btnApprove:       $('btn-approve'),
  btnBackToRec:     $('btn-back-to-rec'),
  approveBarInfo:   $('approve-bar-info'),

  // Screen 4
  btnDownloadPdf:  $('btn-download-pdf'),
  pdfPreviewWrap:  $('pdf-preview-wrap'),
  pdfIframe:       $('pdf-iframe'),
  btnPrint:        $('btn-print'),
  btnBackToEdit:   $('btn-back-to-edit'),
  sumSid:          $('sum-sid'),
  sumPatient:      $('sum-patient'),
  sumMeds:         $('sum-meds'),
  sumElapsed:      $('sum-elapsed'),
  btnNewSession:   $('btn-new-session'),

  // Toast
  toast:     $('toast'),
  toastIcon: $('toast-icon'),
  toastMsg:  $('toast-msg'),

  // Autocomplete
  acDropdown: $('ac-dropdown'),
  acList:     $('ac-list'),
};

/* ══════════════════════════════════════════════════════════════════
   LOCAL-STORAGE PERSISTENCE
   ══════════════════════════════════════════════════════════════════ */
const LS_DOCTOR = 'rx_doctor_name';
const LS_SPEC   = 'rx_specialty';

function savePrefs() {
  try {
    localStorage.setItem(LS_DOCTOR, els.inpDoctorName.value.trim());
    localStorage.setItem(LS_SPEC, els.selSpecialty.value);
  } catch { /* storage not available */ }
}

function loadPrefs() {
  try {
    const name = localStorage.getItem(LS_DOCTOR);
    const spec = localStorage.getItem(LS_SPEC);
    if (name) els.inpDoctorName.value = name;
    if (spec) els.selSpecialty.value = spec;
  } catch { /* ignore */ }
}

els.inpDoctorName.addEventListener('change', savePrefs);
els.selSpecialty.addEventListener('change', savePrefs);

/* ══════════════════════════════════════════════════════════════════
   SCREEN NAVIGATION
   ══════════════════════════════════════════════════════════════════ */
function showScreen(n) {
  state.currentScreen = n;
  document.body.classList.toggle('screen3-active', n === 3);

  els.screens.forEach((s, i) => {
    const active = i + 1 === n;
    s.classList.toggle('active', active);
    s.hidden = !active;
  });

  els.dots.forEach((d) => {
    const step = parseInt(d.dataset.step, 10);
    d.classList.toggle('active', step === n);
    d.classList.toggle('done', step < n);
  });

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ══════════════════════════════════════════════════════════════════
   TOAST
   ══════════════════════════════════════════════════════════════════ */
const TOAST_ICONS = { success: '✓', error: '✕', info: 'ℹ' };
let toastTimer;

function showToast(message, type = 'info') {
  clearTimeout(toastTimer);
  els.toastIcon.textContent = TOAST_ICONS[type] ?? 'ℹ';
  els.toastMsg.textContent  = message;
  els.toast.className = `toast show ${type}`;
  toastTimer = setTimeout(
    () => els.toast.classList.remove('show'),
    4000,
  );
}

/* ══════════════════════════════════════════════════════════════════
   API HELPERS
   ══════════════════════════════════════════════════════════════════ */
const SESSION_API = '/api/session';
const MED_API     = '/api/medicines';

async function apiPost(path, body = null, isForm = false) {
  const opts = { method: 'POST' };
  if (body && !isForm) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  } else if (isForm) {
    opts.body = body; // FormData — no Content-Type header
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({
      detail: res.statusText,
    }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function apiPatch(path, body) {
  const res = await fetch(path, {
    method:  'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({
      detail: res.statusText,
    }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function apiGet(path) {
  const res = await fetch(path);
  if (!res.ok) {
    const err = await res.json().catch(() => ({
      detail: res.statusText,
    }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ══════════════════════════════════════════════════════════════════
   SESSION
   ══════════════════════════════════════════════════════════════════ */
async function startSession() {
  const data = await apiPost(`${SESSION_API}/start`);
  state.sessionId = data.session_id;
  els.sessionBadge.textContent =
    state.sessionId.slice(0, 14) + '…';
  els.sessionBadge.classList.add('active');
  els.sumSid.textContent = state.sessionId;
  return data.session_id;
}

/* ══════════════════════════════════════════════════════════════════
   PIPELINE STAGE HELPERS
   ══════════════════════════════════════════════════════════════════ */
function formatSecs(s) {
  const m = String(Math.floor(s / 60)).padStart(2, '0');
  return `${m}:${String(s % 60).padStart(2, '0')}`;
}

function setStage(name, status, detail = '') {
  const s = els.stages[name];
  if (!s) return;

  // Card classes
  s.card.className = `stage-card ${status}`;

  // Status indicator
  s.status.className = `stage-status ${status}`;
  s.status.textContent =
    status === 'done'  ? '✓' :
    status === 'error' ? '✕' : '●';

  if (detail) s.detail.textContent = detail;

  // Elapsed timer management
  if (status === 'running') {
    state.stageStartTimes[name] = Date.now();
    state.stageTimers[name] = setInterval(() => {
      const sec = Math.floor(
        (Date.now() - state.stageStartTimes[name]) / 1000,
      );
      s.elapsed.textContent = formatSecs(sec);
    }, 1000);
  } else {
    clearInterval(state.stageTimers[name]);
    if (status !== 'idle') {
      const sec = state.stageStartTimes[name]
        ? Math.floor(
            (Date.now() - state.stageStartTimes[name]) / 1000,
          )
        : 0;
      s.elapsed.textContent = sec > 0
        ? `${sec}s` : '';
    } else {
      s.elapsed.textContent = '';
    }
  }
}

function resetStages() {
  Object.keys(els.stages).forEach((n) =>
    setStage(n, 'idle', 'Waiting…'),
  );
  els.retryRow.style.display = 'none';
}

/* ══════════════════════════════════════════════════════════════════
   WAVEFORM VISUALISER
   ══════════════════════════════════════════════════════════════════ */
function startVisualiser(stream) {
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  state.analyser = ctx.createAnalyser();
  state.analyser.fftSize = 256;
  src.connect(state.analyser);

  const canvas = els.waveform;
  const cCtx   = canvas.getContext('2d');
  const bufLen = state.analyser.frequencyBinCount;
  const data   = new Uint8Array(bufLen);

  function draw() {
    state.animationId = requestAnimationFrame(draw);
    state.analyser.getByteTimeDomainData(data);
    cCtx.clearRect(0, 0, canvas.width, canvas.height);
    cCtx.lineWidth   = 2;
    cCtx.strokeStyle = '#22d3ee';
    cCtx.shadowBlur  = 6;
    cCtx.shadowColor = 'rgba(34,211,238,0.5)';
    cCtx.beginPath();
    const sliceW = canvas.width / bufLen;
    let x = 0;
    for (let i = 0; i < bufLen; i++) {
      const v = data[i] / 128.0;
      const y = (v * canvas.height) / 2;
      if (i === 0) cCtx.moveTo(x, y);
      else cCtx.lineTo(x, y);
      x += sliceW;
    }
    cCtx.lineTo(canvas.width, canvas.height / 2);
    cCtx.stroke();
  }
  draw();
}

function stopVisualiser() {
  if (state.animationId) {
    cancelAnimationFrame(state.animationId);
    state.animationId = null;
  }
  const canvas = els.waveform;
  canvas.getContext('2d').clearRect(
    0, 0, canvas.width, canvas.height,
  );
}

/* ══════════════════════════════════════════════════════════════════
   RECORDING
   ══════════════════════════════════════════════════════════════════ */
async function startRecording() {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    showToast('Microphone access denied.', 'error');
    return;
  }
  state.audioChunks  = [];
  state.isRecording  = true;

  els.btnRecord.classList.add('recording');
  els.recordHint.textContent     = 'Recording… click or press Space to stop';
  els.audioActions.style.display = 'none';
  els.uploadAlt.style.display    = 'none';
  startVisualiser(stream);

  state.elapsedSeconds = 0;
  els.timerDisplay.textContent = '00:00';
  els.timerDisplay.classList.remove('timer-warning');

  state.timerInterval = setInterval(() => {
    state.elapsedSeconds++;
    els.timerDisplay.textContent =
      formatSecs(state.elapsedSeconds);

    // 50-second warning
    if (state.elapsedSeconds === 50) {
      els.timerDisplay.classList.add('timer-warning');
      showToast('Recording auto-stops in 10 seconds.', 'info');
    }
    if (state.elapsedSeconds >= 60) stopRecording();
  }, 1000);

  state.mediaRecorder = new MediaRecorder(stream);
  state.mediaRecorder.addEventListener('dataavailable', (e) => {
    if (e.data.size > 0) state.audioChunks.push(e.data);
  });
  state.mediaRecorder.addEventListener('stop', () => {
    stream.getTracks().forEach((t) => t.stop());
    state.audioBlob = new Blob(
      state.audioChunks, { type: 'audio/webm' },
    );
    _setAudioBlob(state.audioBlob);
  });
  state.mediaRecorder.start();
}

function stopRecording() {
  if (!state.isRecording) return;
  state.isRecording = false;
  clearInterval(state.timerInterval);
  stopVisualiser();
  els.btnRecord.classList.remove('recording');
  els.timerDisplay.classList.remove('timer-warning');
  els.recordHint.textContent = 'Click to record again';
  state.mediaRecorder?.stop();
}

function _setAudioBlob(blob) {
  state.audioBlob = blob;
  state.audioUrl  = URL.createObjectURL(blob);
  els.audioPlayer.src                = state.audioUrl;
  els.audioActions.style.display     = 'flex';
  els.uploadAlt.style.display        = 'flex';
  els.btnRunPipeline.disabled        = false;
}

// Record button
els.btnRecord.addEventListener('click', () => {
  if (state.isRecording) stopRecording();
  else startRecording();
});

// Space-bar shortcut (Screen 1 only)
document.addEventListener('keydown', (e) => {
  if (
    e.code === 'Space' &&
    state.currentScreen === 1 &&
    document.activeElement.tagName !== 'INPUT' &&
    document.activeElement.tagName !== 'TEXTAREA' &&
    document.activeElement.tagName !== 'SELECT'
  ) {
    e.preventDefault();
    if (state.isRecording) stopRecording();
    else startRecording();
  }
});

/* ══════════════════════════════════════════════════════════════════
   FILE UPLOAD FALLBACK
   ══════════════════════════════════════════════════════════════════ */
els.fileInput.addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  showToast(`File loaded: ${file.name}`, 'info');
  _setAudioBlob(file);
  els.recordHint.textContent = `📂 ${file.name}`;
  els.timerDisplay.textContent = '—';
  // Reset input so same file can be re-selected
  e.target.value = '';
});

/* ══════════════════════════════════════════════════════════════════
   FULL PIPELINE  (Screen 1 → 2 → 3)
   ══════════════════════════════════════════════════════════════════ */
els.btnRunPipeline.addEventListener('click', runPipeline);

async function runPipeline() {
  if (!state.audioBlob) {
    showToast('No audio recorded.', 'error');
    return;
  }

  // Persist specialty preference
  state.specialty = els.selSpecialty.value;
  savePrefs();

  els.btnRunPipeline.disabled = true;
  showScreen(2);
  resetStages();

  try {
    if (!state.sessionId) await startSession();
    await _runUploadTranscribe();
    await _runParse();
    await _runValidate();

    // Advance to editor with short delay
    setTimeout(() => showScreen(3), 500);

  } catch (err) {
    // Mark any still-running stage as errored
    Object.keys(els.stages).forEach((name) => {
      if (
        els.stages[name].card.classList.contains('running')
      ) {
        setStage(name, 'error', err.message);
        state.lastFailedStage = name;
      }
    });
    els.retryRow.style.display = 'flex';
    showToast(`Error: ${err.message}`, 'error');
    els.btnRunPipeline.disabled = false;
  }
}

async function _runUploadTranscribe() {
  setStage('upload',     'running', 'Uploading audio…');
  setStage('transcribe', 'running', 'Transcribing…');

  const form = new FormData();
  form.append('file', state.audioBlob, 'recording.webm');

  const txData = await apiPost(
    `${SESSION_API}/${state.sessionId}/upload`,
    form, true,
  );
  setStage('upload',     'done', 'Audio saved');
  setStage('transcribe', 'done', 'Transcript ready');

  els.transcriptText.textContent = txData.transcript;
  els.transcriptPanel.style.display = 'block';
}

async function _runParse() {
  setStage('parse', 'running', 'Calling AI model…');
  const parseData = await apiPost(
    `${SESSION_API}/${state.sessionId}/parse`,
  );
  setStage('parse', 'done',
    `${parseData.medications.length} medication(s) found`);
  state.lastParseData = parseData;
}

async function _runValidate() {
  setStage('validate', 'running', 'Matching medicines database…');
  const valData = await apiPost(
    `${SESSION_API}/${state.sessionId}/validate` +
    `?specialty=${state.specialty}`,
  );
  setStage('validate', 'done',
    `${valData.medications.length} validated`);
  state.lastValidData = valData;
  renderEditor(state.lastParseData, valData.medications);
}

/* Retry button */
els.btnRetry.addEventListener('click', async () => {
  els.retryRow.style.display = 'none';
  try {
    // Re-run from failed stage
    const f = state.lastFailedStage;
    if (f === 'upload' || f === 'transcribe') {
      await _runUploadTranscribe();
      await _runParse();
      await _runValidate();
    } else if (f === 'parse') {
      await _runParse();
      await _runValidate();
    } else if (f === 'validate') {
      await _runValidate();
    }
    setTimeout(() => showScreen(3), 500);
  } catch (err) {
    els.retryRow.style.display = 'flex';
    showToast(`Retry failed: ${err.message}`, 'error');
  }
});

/* Back to re-record */
els.btnBackToRec.addEventListener('click', () => {
  showScreen(1);
  els.btnRunPipeline.disabled = false;
});

/* ══════════════════════════════════════════════════════════════════
   RX EDITOR RENDERER  (Screen 3)
   ══════════════════════════════════════════════════════════════════ */
const FREQ_OPTIONS = [
  { value: 'OD',  label: 'OD — Once Daily' },
  { value: 'BD',  label: 'BD — Twice Daily' },
  { value: 'TDS', label: 'TDS — Three Times Daily' },
  { value: 'QID', label: 'QID — Four Times Daily' },
  { value: 'SOS', label: 'SOS — As Needed' },
  { value: 'HS',  label: 'HS — At Bedtime' },
  { value: 'PRN', label: 'PRN — When Required' },
  { value: 'CUSTOM', label: '✏ Custom…' },
];

function renderEditor(parseData, validatedMeds) {
  const pat = parseData.patient || {};
  els.rxName.value   = pat.name   || '';
  els.rxAge.value    = pat.age    || '';
  els.rxGender.value = pat.gender || '';
  els.rxPid.value    = pat.id     || '';
  els.rxDiagnosis.value = parseData.diagnosis || '';
  els.rxComplaints.value =
    (parseData.complaints || []).join('\n');
  els.rxInvestigations.value =
    (parseData.investigations || []).join('\n');
  els.rxNotes.value = parseData.notes || '';

  els.medTbody.innerHTML = '';
  const meds =
    validatedMeds?.length ? validatedMeds : parseData.medications;
  meds.forEach((med) => addMedRow(med));

  updateApproveBarInfo();
}

function scoreToTip(score) {
  if (score >= 90) return 'Exact match ✓';
  if (score >= 80) return 'High confidence match';
  if (score >= 65) return 'Good match — verify';
  if (score >= 50) return 'Low confidence — check manually';
  return 'No reliable match found';
}

function buildScoreBadge(score) {
  const cls =
    score >= 80 ? 'score-good' :
    score >= 60 ? 'score-ok'   : 'score-bad';
  return `<span class="score-badge ${cls}"
    data-tip="${scoreToTip(score)}">${score}</span>`;
}

function _buildFreqOptions(current) {
  const norm = (current || '').toUpperCase().trim();
  const known = FREQ_OPTIONS.some(
    (o) => o.value !== 'CUSTOM' && o.value === norm,
  );
  return FREQ_OPTIONS.map((o) => {
    const sel =
      o.value === 'CUSTOM'
        ? (!known && norm ? ' selected' : '')
        : o.value === norm ? ' selected' : '';
    return `<option value="${o.value}"${sel}>${o.label}</option>`;
  }).join('');
}

function addMedRow(med = {}) {
  const tr = document.createElement('tr');
  tr.className = 'med-row';
  const rowIndex =
    els.medTbody.querySelectorAll('tr').length + 1;
  const score     = med.match_score ?? 0;
  const freqVal   = med.frequency || '';
  const norm      = freqVal.toUpperCase().trim();
  const isCustom  =
    freqVal && !FREQ_OPTIONS.some(
      (o) => o.value !== 'CUSTOM' && o.value === norm,
    );

  tr.innerHTML = `
    <td class="td-drag" aria-label="drag handle">⠿</td>
    <td class="td-num">${rowIndex}</td>
    <td class="td-name">
      <div class="ac-wrap">
        <input
          class="rx-input med-name-input"
          type="text"
          value="${escHtml(med.matched_name || med.name || '')}"
          placeholder="Medicine name"
          autocomplete="off"
          aria-label="Medicine name"
        />
        <div class="ac-spinner" hidden></div>
      </div>
    </td>
    <td class="td-score">${buildScoreBadge(score)}</td>
    <td>
      <input class="rx-input med-field" type="text"
        value="${escHtml(med.dosage || '')}"
        placeholder="500mg"
        aria-label="Dosage" />
    </td>
    <td style="min-width:130px">
      <select class="rx-input med-field freq-select"
        aria-label="Frequency">
        ${_buildFreqOptions(freqVal)}
      </select>
      <input class="rx-input med-field freq-custom${
        isCustom ? ' visible' : ''
      }"
        type="text"
        value="${isCustom ? escHtml(freqVal) : ''}"
        placeholder="e.g. every 8 hrs"
        aria-label="Custom frequency" />
    </td>
    <td>
      <input class="rx-input med-field" type="text"
        value="${escHtml(med.duration || '')}"
        placeholder="5 days"
        aria-label="Duration" />
    </td>
    <td>
      <input class="rx-input med-field" type="text"
        value="${escHtml(med.instructions || '')}"
        placeholder="after meals"
        aria-label="Instructions" />
    </td>
    <td>
      <button class="del-btn" aria-label="Delete row"
        title="Remove medication">✕</button>
    </td>
  `;

  // Autocomplete on name input
  const nameInput = tr.querySelector('.med-name-input');
  const spinner   = tr.querySelector('.ac-spinner');
  nameInput.addEventListener('input',
    () => onMedInput(nameInput, spinner));
  nameInput.addEventListener('focus', () => {
    state.acTargetInput = nameInput;
  });

  // Frequency custom toggle
  const freqSel  = tr.querySelector('.freq-select');
  const freqCust = tr.querySelector('.freq-custom');
  freqSel.addEventListener('change', () => {
    const isC = freqSel.value === 'CUSTOM';
    freqCust.classList.toggle('visible', isC);
    if (isC) freqCust.focus();
  });

  // Delete row
  tr.querySelector('.del-btn').addEventListener('click', () => {
    tr.remove();
    renumberRows();
    updateApproveBarInfo();
  });

  els.medTbody.appendChild(tr);
  updateApproveBarInfo();
}

function renumberRows() {
  els.medTbody.querySelectorAll('tr').forEach((tr, i) => {
    tr.querySelector('.td-num').textContent = i + 1;
  });
}

function updateApproveBarInfo() {
  const count =
    els.medTbody.querySelectorAll('tr.med-row').length;
  els.approveBarInfo.innerHTML =
    `<strong>${count}</strong> medication${
      count !== 1 ? 's' : ''
    } — verify before approving`;
}

els.btnAddMed.addEventListener('click', () => {
  addMedRow();
  // Scroll to new row
  const lastRow = els.medTbody.lastElementChild;
  lastRow?.scrollIntoView({ behavior: 'smooth', block: 'center' });
});

/* ══════════════════════════════════════════════════════════════════
   MEDICINE AUTOCOMPLETE
   ══════════════════════════════════════════════════════════════════ */
function onMedInput(input, spinner) {
  clearTimeout(state.acDebounceTimer);
  const q = input.value.trim();
  if (q.length < 2) { hideDropdown(); return; }
  state.acDebounceTimer = setTimeout(
    () => fetchSuggestions(input, spinner, q),
    280,
  );
}

async function fetchSuggestions(input, spinner, q) {
  spinner.hidden = false;
  try {
    const url =
      `${MED_API}/search?q=${encodeURIComponent(q)}` +
      `&specialty=${state.specialty}&limit=8`;
    const data = await apiGet(url);
    spinner.hidden = true;
    showDropdown(input, data.results);
  } catch {
    spinner.hidden = true;
    hideDropdown();
  }
}

function showDropdown(input, results) {
  if (!results?.length) { hideDropdown(); return; }
  state.acTargetInput = input;

  const rect = input.getBoundingClientRect();
  const dd   = els.acDropdown;
  dd.style.top   = `${rect.bottom + window.scrollY + 4}px`;
  dd.style.left  = `${rect.left   + window.scrollX}px`;
  dd.style.width = `${Math.max(rect.width, 260)}px`;
  dd.hidden = false;

  els.acList.innerHTML = '';
  results.forEach((r) => {
    const li = document.createElement('li');
    li.className = 'ac-item';
    li.setAttribute('role', 'option');
    li.innerHTML = `
      <span class="ac-name">${escHtml(r.name)}</span>
      <span class="ac-meta">
        <span class="score-badge ${
          r.score >= 80 ? 'score-good' :
          r.score >= 60 ? 'score-ok'   : 'score-bad'
        }" data-tip="${scoreToTip(r.score)}">${r.score}</span>
        ${r.manufacturer
          ? `<span class="ac-mfr">${escHtml(r.manufacturer)}</span>`
          : ''}
      </span>
    `;
    li.addEventListener('mousedown', (e) => {
      e.preventDefault();
      selectSuggestion(r);
    });
    els.acList.appendChild(li);
  });
}

function selectSuggestion(result) {
  if (state.acTargetInput) {
    state.acTargetInput.value = result.name;
    // Update score badge
    const row = state.acTargetInput.closest('tr');
    if (row) {
      const scoreTd = row.querySelector('.td-score');
      if (scoreTd) scoreTd.innerHTML = buildScoreBadge(result.score);
    }
  }
  hideDropdown();
}

function hideDropdown() {
  els.acDropdown.hidden = true;
  els.acList.innerHTML  = '';
}

document.addEventListener('click', (e) => {
  if (
    !els.acDropdown.contains(e.target) &&
    e.target !== state.acTargetInput
  ) hideDropdown();
});

/* ══════════════════════════════════════════════════════════════════
   COLLECT EDITS
   ══════════════════════════════════════════════════════════════════ */
function collectEdits() {
  const meds = [];
  els.medTbody.querySelectorAll('tr.med-row').forEach((tr) => {
    const nameIn  = tr.querySelector('.med-name-input');
    const fields  = tr.querySelectorAll('.med-field');
    // fields[0]=dosage, fields[1]=freq-select,
    // fields[2]=freq-custom, fields[3]=duration, fields[4]=instruct
    const freqSel  = tr.querySelector('.freq-select');
    const freqCust = tr.querySelector('.freq-custom');

    let freqVal;
    if (freqSel.value === 'CUSTOM') {
      freqVal = freqCust.value.trim() || 'As directed';
    } else {
      freqVal = freqSel.value || 'OD';
    }

    meds.push({
      name:         nameIn?.value.trim()   || '',
      dosage:       fields[0]?.value.trim() || 'Not specified',
      frequency:    freqVal,
      duration:     fields[3]?.value.trim() || 'Not specified',
      instructions: fields[4]?.value.trim() || '',
    });
  });

  return {
    patient_name:   els.rxName.value.trim()         || null,
    patient_age:    els.rxAge.value.trim()           || null,
    patient_gender: els.rxGender.value               || null,
    patient_id:     els.rxPid.value.trim()           || null,
    complaints:     els.rxComplaints.value
      .split('\n').map((s) => s.trim()).filter(Boolean),
    diagnosis:      els.rxDiagnosis.value.trim()     || null,
    medications:    meds,
    investigations: els.rxInvestigations.value
      .split('\n').map((s) => s.trim()).filter(Boolean),
    notes:          els.rxNotes.value.trim()         || null,
  };
}

/* ══════════════════════════════════════════════════════════════════
   APPROVE & EXPORT  (Screen 3 → 4)
   ══════════════════════════════════════════════════════════════════ */
els.btnApprove.addEventListener('click', approveAndExport);

async function approveAndExport() {
  els.btnApprove.disabled    = true;
  els.btnApprove.textContent = '⏳ Generating…';

  try {
    const edits = collectEdits();

    // Persist edits
    await apiPatch(
      `${SESSION_API}/${state.sessionId}/update`,
      edits,
    );

    // Generate PDF
    const exportData = await apiPost(
      `${SESSION_API}/${state.sessionId}/export`,
    );

    // Elapsed
    let elapsed = '—';
    try {
      const s = await apiGet(
        `${SESSION_API}/${state.sessionId}`,
      );
      elapsed = `${Math.round(s.elapsed)}s`;
    } catch { /* non-fatal */ }

    // Populate Screen 4
    const pdfUrl = exportData.pdf_url;
    els.btnDownloadPdf.href     = pdfUrl;
    els.btnDownloadPdf.download =
      `prescription_${state.sessionId}.pdf`;

    // Inline PDF preview
    els.pdfIframe.src             = pdfUrl;
    els.pdfPreviewWrap.style.display = 'block';

    // Summary
    els.sumSid.textContent     = state.sessionId;
    els.sumPatient.textContent = els.rxName.value || 'Unknown';
    const mc = edits.medications.length;
    els.sumMeds.textContent    =
      `${mc} medication${mc !== 1 ? 's' : ''}`;
    els.sumElapsed.textContent = elapsed;

    showScreen(4);
    showToast('Prescription approved! ✓', 'success');

  } catch (err) {
    showToast(`Export failed: ${err.message}`, 'error');
    els.btnApprove.disabled    = false;
    els.btnApprove.textContent = '✅ Approve & Generate PDF';
  }
}

/* Back to edit from Screen 4 */
els.btnBackToEdit.addEventListener('click', () => showScreen(3));

/* Print */
els.btnPrint.addEventListener('click', () => {
  const iframe = els.pdfIframe;
  try {
    iframe.contentWindow.focus();
    iframe.contentWindow.print();
  } catch {
    // Fallback: open PDF in new tab for printing
    window.open(els.btnDownloadPdf.href, '_blank');
  }
});

/* ══════════════════════════════════════════════════════════════════
   NEW SESSION  (Screen 4 → 1)
   ══════════════════════════════════════════════════════════════════ */
els.btnNewSession.addEventListener('click', resetToStart);

function resetToStart() {
  state.sessionId       = null;
  state.audioBlob       = null;
  state.audioUrl        = null;
  state.audioChunks     = [];
  state.isRecording     = false;
  state.elapsedSeconds  = 0;
  state.lastParseData   = null;
  state.lastValidData   = null;
  state.lastFailedStage = null;

  els.audioActions.style.display      = 'none';
  els.uploadAlt.style.display         = 'flex';
  els.audioPlayer.src                 = '';
  els.timerDisplay.textContent        = '00:00';
  els.timerDisplay.classList.remove('timer-warning');
  els.recordHint.textContent          = 'Click to start recording';
  els.btnRecord.classList.remove('recording');
  els.btnRunPipeline.disabled         = true;
  els.sessionBadge.textContent        = 'No session';
  els.sessionBadge.classList.remove('active');

  resetStages();
  els.transcriptPanel.style.display   = 'none';
  els.transcriptText.textContent      = '';

  els.medTbody.innerHTML              = '';
  els.btnApprove.disabled             = false;
  els.btnApprove.textContent          = '✅ Approve & Generate PDF';

  els.pdfPreviewWrap.style.display    = 'none';
  els.pdfIframe.src                   = '';

  startSession().catch(() => {});
  showScreen(1);
}

/* ══════════════════════════════════════════════════════════════════
   UTILITY
   ══════════════════════════════════════════════════════════════════ */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ══════════════════════════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════════════════════════ */
(async () => {
  loadPrefs();
  try {
    await startSession();
  } catch {
    /* Server may not be ready yet — silent fail */
  }
})();
