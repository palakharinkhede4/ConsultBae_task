/**
 * ConsultBae Audio Collection App - Frontend Logic
 * Implements Web Audio API recording, real-time waveform visualization,
 * metadata extraction rendering, and candidate database views.
 */

let audioMode = 'record'; // 'record' or 'upload'
let mediaRecorder = null;
let audioChunks = [];
let recordedBlob = null;
let recordingInterval = null;
let recordingStartTime = 0;
let audioContext = null;
let analyserNode = null;
let canvasCtx = null;
let animationFrameId = null;
let allCandidates = [];

document.addEventListener('DOMContentLoaded', () => {
  setupCanvas();
  loadStats();
  loadSubmissions();
  loadCandidates();
});

// Tab Navigation
function switchTab(tabId) {
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.view-panel').forEach(v => v.classList.remove('active'));

  const tabBtn = document.getElementById(`tab-btn-${tabId}`);
  const viewPanel = document.getElementById(`view-${tabId}`);
  
  if (tabBtn) tabBtn.classList.add('active');
  if (viewPanel) viewPanel.classList.add('active');

  if (tabId === 'submissions') loadSubmissions();
  if (tabId === 'database') loadCandidates();
}

function setAudioMode(mode) {
  audioMode = mode;
  document.getElementById('btn-mode-record').classList.toggle('active', mode === 'record');
  document.getElementById('btn-mode-upload').classList.toggle('active', mode === 'upload');

  document.getElementById('recorder-panel').style.display = mode === 'record' ? 'block' : 'none';
  document.getElementById('upload-panel').style.display = mode === 'upload' ? 'block' : 'none';
}

function quickFill(name, phone) {
  document.getElementById('candidate-name').value = name;
  document.getElementById('candidate-phone').value = phone;
}

// Canvas & Visualizer
function setupCanvas() {
  const canvas = document.getElementById('waveform-canvas');
  if (!canvas) return;
  canvasCtx = canvas.getContext('2d');
  drawEmptyWaveform();
}

function drawEmptyWaveform() {
  const canvas = document.getElementById('waveform-canvas');
  if (!canvas || !canvasCtx) return;
  canvasCtx.fillStyle = '#080c16';
  canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
  canvasCtx.strokeStyle = 'rgba(99, 102, 241, 0.3)';
  canvasCtx.lineWidth = 2;
  canvasCtx.beginPath();
  canvasCtx.moveTo(0, canvas.height / 2);
  canvasCtx.lineTo(canvas.width, canvas.height / 2);
  canvasCtx.stroke();
}

// MediaRecorder Audio Recording
async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // Web Audio Visualizer setup
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    analyserNode = audioContext.createAnalyser();
    analyserNode.fftSize = 256;
    source.connect(analyserNode);

    visualizeWaveform();

    // Media Recorder setup
    audioChunks = [];
    let options = { mimeType: 'audio/webm' };
    if (!MediaRecorder.isTypeSupported('audio/webm')) {
      options = { mimeType: 'audio/ogg' };
    }
    
    try {
      mediaRecorder = new MediaRecorder(stream, options);
    } catch (e) {
      mediaRecorder = new MediaRecorder(stream);
    }

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      recordedBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/wav' });
      const audioUrl = URL.createObjectURL(recordedBlob);
      const preview = document.getElementById('audio-preview');
      preview.src = audioUrl;
      document.getElementById('preview-container').style.display = 'block';
      document.getElementById('btn-reset-record').disabled = false;
    };

    mediaRecorder.start();
    recordingStartTime = Date.now();
    updateTimer();
    recordingInterval = setInterval(updateTimer, 1000);

    document.getElementById('btn-start-record').disabled = true;
    document.getElementById('btn-stop-record').disabled = false;
    document.getElementById('btn-reset-record').disabled = true;

  } catch (err) {
    console.error('Microphone access denied or error:', err);
    alert('Microphone access error. You can also use "Upload Audio File" mode directly.');
  }
}

function updateTimer() {
  const elapsedSec = Math.floor((Date.now() - recordingStartTime) / 1000);
  const mins = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
  const secs = String(elapsedSec % 60).padStart(2, '0');
  document.getElementById('record-timer').innerText = `${mins}:${secs}`;
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(track => track.stop());
  }
  clearInterval(recordingInterval);
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  drawEmptyWaveform();

  document.getElementById('btn-start-record').disabled = false;
  document.getElementById('btn-stop-record').disabled = true;
}

function resetRecording() {
  recordedBlob = null;
  audioChunks = [];
  document.getElementById('record-timer').innerText = '00:00';
  document.getElementById('preview-container').style.display = 'none';
  document.getElementById('btn-reset-record').disabled = true;
  document.getElementById('btn-start-record').disabled = false;
  document.getElementById('btn-stop-record').disabled = true;
  drawEmptyWaveform();
}

function visualizeWaveform() {
  const canvas = document.getElementById('waveform-canvas');
  if (!canvas || !analyserNode || !canvasCtx) return;

  const bufferLength = analyserNode.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    animationFrameId = requestAnimationFrame(draw);
    analyserNode.getByteTimeDomainData(dataArray);

    canvasCtx.fillStyle = '#080c16';
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

    canvasCtx.lineWidth = 2.5;
    canvasCtx.strokeStyle = '#06b6d4';
    canvasCtx.beginPath();

    const sliceWidth = (canvas.width * 1.0) / bufferLength;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0;
      const y = (v * canvas.height) / 2;

      if (i === 0) {
        canvasCtx.moveTo(x, y);
      } else {
        canvasCtx.lineTo(x, y);
      }
      x += sliceWidth;
    }

    canvasCtx.lineTo(canvas.width, canvas.height / 2);
    canvasCtx.stroke();
  }

  draw();
}

// File Upload Handler
function handleFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  document.getElementById('selected-filename').innerText = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  document.getElementById('selected-file-badge').style.display = 'flex';
}

function removeSelectedFile() {
  document.getElementById('file-input').value = '';
  document.getElementById('selected-file-badge').style.display = 'none';
}

// Form Submission & Audio Ingestion
async function handleAudioSubmit(event) {
  event.preventDefault();

  const name = document.getElementById('candidate-name').value.trim();
  const phone = document.getElementById('candidate-phone').value.trim();
  const submitBtn = document.getElementById('btn-submit');

  const formData = new FormData();
  formData.append('name', name);
  formData.append('phone', phone);

  if (audioMode === 'record') {
    if (!recordedBlob) {
      alert('Please record an audio snippet first or switch to "Upload Audio File".');
      return;
    }
    formData.append('audio_file', recordedBlob, 'recording.webm');
  } else {
    const fileInput = document.getElementById('file-input');
    if (!fileInput.files || fileInput.files.length === 0) {
      alert('Please select an audio file to upload.');
      return;
    }
    formData.append('audio_file', fileInput.files[0]);
  }

  submitBtn.disabled = true;
  submitBtn.innerText = '⏳ Processing & Extracting Metrics...';

  try {
    const res = await fetch('/api/submit-audio', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      alert(`Error: ${data.detail || 'Failed to submit audio'}`);
      return;
    }

    // Display Extracted Metrics
    displayResult(data);
    loadStats();
    loadSubmissions();

  } catch (err) {
    console.error('Submission error:', err);
    alert('An error occurred during submission.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerText = '🚀 Submit Recording & Extract Metrics';
  }
}

function displayResult(data) {
  document.getElementById('empty-state').style.display = 'none';
  const resultBox = document.getElementById('metrics-result');
  resultBox.style.display = 'block';

  document.getElementById('result-candidate-info').innerText = 
    `Candidate: ${data.candidate.name} (${data.candidate.phone}) ${data.candidate.matched_existing_profile ? '• [Matched Profile in DB]' : '• [New Candidate]'}`;

  const metrics = data.audio_metrics;
  document.getElementById('metric-duration').innerText = `${metrics.duration_sec} s`;
  document.getElementById('metric-samplerate').innerText = `${metrics.sample_rate_khz} kHz`;
  document.getElementById('metric-bitrate').innerText = `${metrics.bitrate_kbps} kbps`;
  document.getElementById('metric-loudness').innerText = `${metrics.loudness_db} dB`;
  document.getElementById('metric-quality').innerText = metrics.quality_score;

  const player = document.getElementById('result-audio-player');
  player.src = data.audio_url;
}

// Data Fetchers
async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('stat-candidates').innerText = data.total_candidates;
    document.getElementById('stat-verified').innerText = data.verified_workers;
    document.getElementById('stat-submissions').innerText = data.audio_submissions;
  } catch (e) {
    console.error(e);
  }
}

async function loadSubmissions() {
  const tbody = document.getElementById('submissions-table-body');
  try {
    const res = await fetch('/api/submissions');
    const data = await res.json();
    
    if (data.submissions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" class="text-center" style="padding: 2rem; color: var(--text-muted);">No audio submissions yet. Submit a recording in View 1 to populate this table.</td></tr>';
      return;
    }

    tbody.innerHTML = data.submissions.map(s => `
      <tr>
        <td>#${s.id}</td>
        <td><strong>${s.candidate_name}</strong></td>
        <td><code>${s.phone}</code></td>
        <td>
          <audio controls style="height: 32px; width: 180px;">
            <source src="${s.audio_url}" type="audio/wav">
            <source src="${s.audio_url}" type="audio/webm">
          </audio>
        </td>
        <td><span class="badge" style="background: rgba(255,255,255,0.05);">${s.duration_sec}s</span></td>
        <td><span class="badge" style="background: rgba(6, 182, 212, 0.15); color: #67e8f9;">${s.sample_rate_khz} kHz</span></td>
        <td><span class="badge" style="background: rgba(168, 85, 247, 0.15); color: #d8b4fe;">${s.bitrate_kbps} kbps</span></td>
        <td><span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #fde68a;">${s.loudness_db} dB</span></td>
        <td><span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #6ee7b7;">${s.quality_score}</span></td>
        <td style="font-size: 0.75rem; color: var(--text-muted);">${s.submitted_at}</td>
      </tr>
    `).join('');

  } catch (err) {
    console.error('Error loading submissions:', err);
    tbody.innerHTML = '<tr><td colspan="10" class="text-center" style="color: #f43f5e;">Failed to load submissions.</td></tr>';
  }
}

async function loadCandidates() {
  const tbody = document.getElementById('candidates-table-body');
  try {
    const res = await fetch('/api/candidates');
    const data = await res.json();
    allCandidates = data.candidates;
    renderCandidates(allCandidates);
  } catch (err) {
    console.error('Error loading candidates:', err);
    tbody.innerHTML = '<tr><td colspan="12" class="text-center" style="color: #f43f5e;">Failed to load candidates.</td></tr>';
  }
}

function renderCandidates(candidates) {
  const tbody = document.getElementById('candidates-table-body');
  if (candidates.length === 0) {
    tbody.innerHTML = '<tr><td colspan="12" class="text-center">No matching candidates found.</td></tr>';
    return;
  }

  tbody.innerHTML = candidates.map(c => `
    <tr>
      <td>${c.id}</td>
      <td><strong>${c.full_name}</strong></td>
      <td><code>${c.phone || '—'}</code></td>
      <td style="max-width: 180px; overflow: hidden; text-overflow: ellipsis;">${c.email || '—'}</td>
      <td>${c.city || '—'}</td>
      <td>${c.experience_years !== null ? c.experience_years + 'y' : '—'}</td>
      <td>${c.current_ctc_formatted || '—'}</td>
      <td>${c.verified === 1 ? '<span class="badge badge-verified">✓ Yes</span>' : (c.verified === 0 ? '<span class="badge badge-unverified">No</span>' : '—')}</td>
      <td>${c.projects_completed !== null ? c.projects_completed : '—'}</td>
      <td>${c.rate_formatted || '—'}</td>
      <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis; font-size: 0.75rem;">${c.skills || '—'}</td>
      <td>${(c.data_sources || '').split(',').map(s => `<span class="badge badge-source">${s.trim()}</span>`).join(' ')}</td>
    </tr>
  `).join('');
}

function filterCandidates() {
  const query = document.getElementById('search-candidate').value.toLowerCase();
  const filtered = allCandidates.filter(c => {
    return (
      (c.full_name && c.full_name.toLowerCase().includes(query)) ||
      (c.city && c.city.toLowerCase().includes(query)) ||
      (c.skills && c.skills.toLowerCase().includes(query)) ||
      (c.phone && c.phone.includes(query))
    );
  });
  renderCandidates(filtered);
}
