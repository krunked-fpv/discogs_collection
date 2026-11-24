// KRUNKED // VINYL VAULT v6.0 — Pitch-Coupled Web Audio Engine, iTunes 30s Needle-Drop & Arena DJ Crossfader

import {
  STORAGE_KEYS,
  emit,
  getActiveRecord,
  store,
} from './store.js';
import {
  cleanArtistName,
  cleanSearchTitle,
  escapeHtml,
  formatMillisToDuration,
  getCoverUrls,
  parseDurationToSeconds,
  safeExternalUrl,
  safeGetStorage,
  safeRemoveStorage,
  safeSetStorage,
  showToast,
} from './utils.js';

const CURATED_TRACKLISTS = {
  26047147: {
    year: 2005,
    totalMinutes: 48,
    description: 'Kezia is the debut full-length concept album by Canadian progressive metal band Protest The Hero.',
    tracks: [
      { position: 'A1', title: 'No Stars Over Bethlehem', duration: '3:49', plays: '494K plays' },
      { position: 'A2', title: 'Heretics & Killers', duration: '3:10', plays: '1.2M plays' },
      { position: 'A3', title: 'Divinity Within', duration: '4:33', plays: '535K plays' },
      { position: 'B1', title: 'Bury the Hatchet', duration: '3:25', plays: '298K plays' },
      { position: 'B2', title: 'Nautical', duration: '2:58', plays: '347K plays' },
      { position: 'B3', title: 'Blindfolds Aside', duration: '6:00', plays: '3.4M plays' },
      { position: 'C1', title: 'She Who Mars the Skin of Gods', duration: '3:52', plays: '289K plays' },
      { position: 'C2', title: 'Turn Soonest to the Sea', duration: '6:22', plays: '769K plays' },
      { position: 'D1', title: 'The Divine Suicide of K.', duration: '5:11', plays: '274K plays' },
      { position: 'D2', title: 'A Plateful of Our Dead', duration: '4:30', plays: '187K plays' },
    ],
  },
  17743813: {
    year: 2021,
    totalMinutes: 58,
    description: 'For Those That Wish To Exist is the ninth studio album by British metalcore band Architects.',
    tracks: [
      { position: 'A1', title: 'Do You Dream of Armageddon?', duration: '1:38', plays: '8.4M plays' },
      { position: 'A2', title: 'Black Lungs', duration: '3:51', plays: '42M plays' },
      { position: 'A3', title: 'Giving Blood', duration: '3:32', plays: '14M plays' },
      { position: 'A4', title: 'Discourse Is Dead', duration: '3:46', plays: '19M plays' },
      { position: 'B1', title: 'Dead Butterflies', duration: '4:02', plays: '28M plays' },
      { position: 'B2', title: 'An Ordinary Extinction', duration: '4:07', plays: '11M plays' },
      { position: 'B3', title: 'Impermanence', duration: '4:02', plays: '21M plays' },
      { position: 'B4', title: 'Flight Without Feathers', duration: '3:48', plays: '6.2M plays' },
      { position: 'C1', title: 'Little Wonder', duration: '3:47', plays: '9.1M plays' },
      { position: 'C2', title: 'Animals', duration: '4:04', plays: '118M plays' },
      { position: 'C3', title: 'Libertine', duration: '4:01', plays: '8.7M plays' },
      { position: 'D1', title: 'Goliath', duration: '4:17', plays: '12M plays' },
      { position: 'D2', title: 'Demi God', duration: '4:26', plays: '6.5M plays' },
      { position: 'D3', title: 'Meteor', duration: '4:01', plays: '18M plays' },
      { position: 'D4', title: 'Dying Is Absolutely Safe', duration: '4:59', plays: '9.4M plays' },
    ],
  },
  17583742: {
    year: 2021,
    totalMinutes: 34,
    description: "Embryonic Anomaly (Remake) is the full 2021 studio re-recording of Rings Of Saturn's debut album.",
    tracks: [
      { position: 'A1', title: 'Seized and Devoured', duration: '4:04', plays: '1.9M plays' },
      { position: 'A2', title: 'Invasion', duration: '4:07', plays: '610K plays' },
      { position: 'A3', title: 'Abducted', duration: '4:07', plays: '540K plays' },
      { position: 'A4', title: 'Final Abhorrent Dream', duration: '5:02', plays: '410K plays' },
      { position: 'B1', title: 'Corpses Thrown Across the Sky', duration: '4:05', plays: '720K plays' },
      { position: 'B2', title: 'Embryonic Anomaly', duration: '3:25', plays: '480K plays' },
      { position: 'B3', title: 'No Pity for a Coward', duration: '3:20', plays: '390K plays' },
      { position: 'B4', title: 'Annihilating the Pure', duration: '4:54', plays: '460K plays' },
      { position: 'B5', title: 'Grinding of Internal Organs / End of Humanity', duration: '5:26', plays: '350K plays' },
    ],
  },
};

function getYtmReleaseMap() {
  return window.__VAULT_YTM_RELEASE_MAP__ || {};
}
function getYtmStemMap() {
  return window.__VAULT_YTM_ALBUM_STEM_MAP__ || {};
}

function normalizeTrackKey(str) {
  const s = String(str || '')
    .toLowerCase()
    .replace(/∆/g, 'a')
    .replace(/flouride/g, 'fluoride')
    .replace(/st4f1sh/g, 'st4rf1sh')
    .replace(/\[([^\]]{1,2})\]/g, '$1')
    .replace(/\([^)]*\)|\[[^\]]*\]/g, ' ');
  const words = s.match(/[a-z0-9]+/g) || [];
  return words.map((w) => (w.length > 3 && w.endsWith('s') ? w.slice(0, -1) : w)).join('');
}

function computeAlbumFuzzyStemKey(artist, title) {
  const a = cleanArtistName(artist || '').toLowerCase();
  const t = String(title || '').toLowerCase().replace(/∆/g, 'a').replace(/\bln\b/g, 'in').replace(/\[([^\]]{1,2})\]/g, '$1');
  const aWords = (a.match(/[a-z0-9]+/g) || []).map((w) => (w.length > 3 && w.endsWith('s') ? w.slice(0, -1) : w));
  const tWords = (t.match(/[a-z0-9]+/g) || []).map((w) => (w.length > 3 && w.endsWith('s') ? w.slice(0, -1) : w));
  return `${aWords.join('')}::${tWords.join('')}`;
}

// =========================================================================
// Web Audio Context, Turntable Acoustics & Crackle Generator
// =========================================================================
let audioCtx = null;
let crackleNodes = null;
let mainPreviewSource = null;
let mainAnalyser = null;
let mainGainNode = null;
let untaintedAudioMode = false;
let freqDataBuf = null;
const spectrumBars = new Float32Array(64);
let spectrumHasEnergy = false;
let lastScratchSoundMs = 0;

function ensureAudioCtx() {
  if (!audioCtx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) audioCtx = new AC();
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

export function playCrateTickSound(pitchFactor = 1.0) {
  if (!store.analogSfx) return;
  try {
    const ctx = ensureAudioCtx();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(240 * pitchFactor, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(58, ctx.currentTime + 0.036);
    gain.gain.setValueAtTime(0.14, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.038);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.04);
  } catch {
    // Ignore autoplay restriction before gesture
  }
}

export function playNeedleDropSound() {
  if (!store.analogSfx) return;
  try {
    const ctx = ensureAudioCtx();
    if (!ctx) return;
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(98, now);
    osc.frequency.exponentialRampToValueAtTime(25, now + 0.19);
    gain.gain.setValueAtTime(0.28, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.21);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.22);

    // Subtle micro-crackle stylus kiss
    const len = Math.floor(ctx.sampleRate * 0.09);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < len; i++) {
      ch[i] = (Math.random() * 2 - 1) * Math.exp(-i / (len * 0.25)) * 0.25;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass';
    bp.frequency.value = 1800;
    const g2 = ctx.createGain();
    g2.gain.value = 0.22;
    src.connect(bp);
    bp.connect(g2);
    g2.connect(ctx.destination);
    src.start(now + 0.02);
  } catch {
    // Ignore audio context restrictions
  }
}

export function playRouletteWinChord(isArenaChampion = false) {
  if (!store.analogSfx) return;
  try {
    const ctx = ensureAudioCtx();
    if (!ctx) return;
    const freqs = isArenaChampion
      ? [261.63, 329.63, 392.0, 523.25, 659.25]
      : [293.66, 369.99, 440.0, 587.33];
    freqs.forEach((f, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = idx % 2 === 0 ? 'triangle' : 'sine';
      const startT = ctx.currentTime + idx * 0.045;
      osc.frequency.setValueAtTime(f, startT);
      gain.gain.setValueAtTime(0.09, startT);
      gain.gain.exponentialRampToValueAtTime(0.0008, startT + 0.45);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(startT);
      osc.stop(startT + 0.46);
    });
  } catch {
    // Ignore
  }
}

export function playUvToggleSound(turningOn) {
  if (!store.analogSfx) return;
  try {
    const ctx = ensureAudioCtx();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sawtooth';
    const now = ctx.currentTime;
    osc.frequency.setValueAtTime(turningOn ? 115 : 320, now);
    osc.frequency.exponentialRampToValueAtTime(turningOn ? 440 : 88, now + 0.16);
    gain.gain.setValueAtTime(0.075, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.19);
  } catch {
    // Ignore
  }
}

export function playTimerChime() {
  try {
    const ctx = ensureAudioCtx();
    if (!ctx) return;
    [523.25, 659.25, 783.99, 1046.5].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.18);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.18 + 0.45);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime + i * 0.18);
      osc.stop(ctx.currentTime + i * 0.18 + 0.46);
    });
  } catch {
    // Ignore
  }
}

export function playScratchChirp(speedMag = 1) {
  if (!store.analogSfx) return;
  const nowMs = performance.now();
  if (nowMs - lastScratchSoundMs < 75) return;
  lastScratchSoundMs = nowMs;
  try {
    const ctx = ensureAudioCtx();
    if (!ctx) return;
    const len = Math.floor(ctx.sampleRate * 0.055);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (len * 0.45));
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass';
    bp.frequency.value = Math.min(3400, 650 + speedMag * 720);
    bp.Q.value = 3.2;
    const g = ctx.createGain();
    g.gain.value = 0.12;
    src.connect(bp);
    bp.connect(g);
    g.connect(ctx.destination);
    src.start();
  } catch {
    // Ignore
  }
}

export function toggleVinylCrackle(forceState) {
  const next = typeof forceState === 'boolean' ? forceState : !store.crackleOn;
  if (!next) {
    if (crackleNodes) {
      try {
        crackleNodes.src.stop();
        crackleNodes.rumble.stop();
      } catch {
        // Ignore already stopped
      }
      crackleNodes = null;
    }
    store.crackleOn = false;
    return;
  }

  const ctx = ensureAudioCtx();
  if (!ctx) {
    showToast('Web Audio API unavailable in this browser.');
    return;
  }
  const bufferSize = ctx.sampleRate * 3;
  const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
  const output = noiseBuffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) {
    output[i] = Math.random() < 0.0038 ? Math.random() * 0.36 - 0.18 : Math.random() * 0.014 - 0.007;
  }
  const src = ctx.createBufferSource();
  src.buffer = noiseBuffer;
  src.loop = true;

  const bp = ctx.createBiquadFilter();
  bp.type = 'bandpass';
  bp.frequency.value = 1850;
  bp.Q.value = 0.9;

  const gain = ctx.createGain();
  gain.gain.value = 0.17;
  src.connect(bp);
  bp.connect(gain);
  gain.connect(ctx.destination);
  src.start();

  // Subtle 38Hz platter rumble
  const rumble = ctx.createOscillator();
  rumble.type = 'sine';
  rumble.frequency.value = 38;
  const rumbleGain = ctx.createGain();
  rumbleGain.gain.value = 0.014;
  rumble.connect(rumbleGain);
  rumbleGain.connect(ctx.destination);
  rumble.start();

  crackleNodes = { src, gain, rumble, rumbleGain };
  store.crackleOn = true;
}

// =========================================================================
// Pitch-Coupled Playback Rate + Radial Platter Spectrum Analyser
// =========================================================================
function ensureMainAudioPipeline() {
  const audioEl = document.getElementById('vault-preview-audio');
  if (!audioEl || untaintedAudioMode || mainPreviewSource) return;
  try {
    const ctx = ensureAudioCtx();
    if (!ctx) return;
    audioEl.crossOrigin = 'anonymous';
    mainPreviewSource = ctx.createMediaElementSource(audioEl);
    mainGainNode = ctx.createGain();
    mainGainNode.gain.value = 1.0;
    mainAnalyser = ctx.createAnalyser();
    mainAnalyser.fftSize = 64;
    mainAnalyser.smoothingTimeConstant = 0.72;
    freqDataBuf = new Uint8Array(mainAnalyser.frequencyBinCount);
    mainPreviewSource.connect(mainGainNode);
    mainGainNode.connect(mainAnalyser);
    mainAnalyser.connect(ctx.destination);
  } catch {
    // Fallback gracefully without Web Audio media source
  }
}

function setPitchPreservationOff(audioEl) {
  if (!audioEl) return;
  try {
    audioEl.preservesPitch = false;
    audioEl.mozPreservesPitch = false;
    audioEl.webkitPreservesPitch = false;
  } catch {
    // Ignore unsupported property
  }
}

/**
 * Couples HTML5 <audio> playbackRate & synthesized crackle directly to live platter angular velocity.
 * `ratio` is `currentOmega / nominalOmega33` (1.0 at 33.3 RPM, 1.35 at 45 RPM, 0 on stop, <0 on backspin).
 */
export function setPlatterVelocityRatio(ratio) {
  const absR = Math.abs(ratio);
  if (crackleNodes && audioCtx) {
    try {
      const clampedR = Math.max(0.05, Math.min(2.2, absR));
      crackleNodes.src.playbackRate.setTargetAtTime(clampedR, audioCtx.currentTime, 0.04);
      crackleNodes.gain.gain.setTargetAtTime(absR < 0.06 ? 0.005 : Math.min(0.24, 0.08 + absR * 0.1), audioCtx.currentTime, 0.05);
      crackleNodes.rumbleGain.gain.setTargetAtTime(absR < 0.06 ? 0.0 : 0.015 * Math.min(1.4, absR), audioCtx.currentTime, 0.05);
    } catch {
      // Ignore
    }
  }

  const audioEl = document.getElementById('vault-preview-audio');
  if (!audioEl || !store.isPreviewPlaying) return;
  setPitchPreservationOff(audioEl);

  let targetRate = store.quartzPitchLock ? 1.0 : absR;
  if (ratio < -0.15) {
    playScratchChirp(absR);
    targetRate = 0.35;
  }

  if (absR < 0.08) {
    if (!audioEl.paused) {
      audioEl.volume = 0.05;
      audioEl.playbackRate = 0.25;
    }
  } else {
    const safeRate = Math.max(0.25, Math.min(2.25, targetRate));
    if (Math.abs(audioEl.playbackRate - safeRate) > 0.015) {
      audioEl.playbackRate = safeRate;
    }
    const targetVol = store.isAudioMuted ? 0 : Math.min(1, 0.3 + absR * 0.7);
    audioEl.volume = targetVol;
  }
}

export function getVuLevels() {
  if (store.isPreviewPlaying && mainAnalyser && freqDataBuf && !untaintedAudioMode) {
    mainAnalyser.getByteFrequencyData(freqDataBuf);
    let sum = 0;
    for (let i = 0; i < freqDataBuf.length; i++) sum += freqDataBuf[i];
    const energy = Math.min(1, (sum / (freqDataBuf.length * 255)) * 1.45);
    if (energy > 0.01) {
      spectrumHasEnergy = true;
      const binLen = freqDataBuf.length;
      for (let i = 0; i < 64; i++) {
        const binVal = (freqDataBuf[i % binLen] || 0) / 255;
        spectrumBars[i] = spectrumBars[i] * 0.55 + binVal * 0.45;
      }
      return { energy, bars: spectrumBars, active: true };
    }
  }
  if (store.isPreviewPlaying) {
    spectrumHasEnergy = true;
    const audioEl = document.getElementById('vault-preview-audio');
    const rate = audioEl ? Math.max(0.35, audioEl.playbackRate || 1) : 1;
    const t = performance.now() * 0.007 * rate;
    const energy = 0.44 + 0.28 * Math.abs(Math.sin(t * 1.7) * Math.cos(t * 0.8));
    for (let i = 0; i < 64; i++) {
      const target = 0.22 + 0.68 * Math.abs(Math.sin(t * 1.15 + i * 0.37) * Math.cos(t * 0.65 - i * 0.19));
      spectrumBars[i] = spectrumBars[i] * 0.5 + target * 0.5;
    }
    return { energy, bars: spectrumBars, active: true };
  }
  if (store.crackleOn && store.isSpinning) {
    spectrumHasEnergy = true;
    const t = performance.now() * 0.01;
    for (let i = 0; i < 64; i++) {
      const target = 0.05 + 0.11 * Math.abs(Math.sin(t * 1.9 + i * 0.91));
      spectrumBars[i] = spectrumBars[i] * 0.65 + target * 0.35;
    }
    return { energy: 0.1, bars: spectrumBars, active: true };
  }
  if (!spectrumHasEnergy) {
    return { energy: 0, bars: spectrumBars, active: false };
  }
  let stillActive = false;
  for (let i = 0; i < 64; i++) {
    if (spectrumBars[i] < 0.004) {
      spectrumBars[i] = 0;
    } else {
      spectrumBars[i] *= 0.82;
      stillActive = true;
    }
  }
  spectrumHasEnergy = stillActive;
  return { energy: 0, bars: spectrumBars, active: stillActive };
}

// =========================================================================
// Album Tracklist & Platform Link Resolution (Zero-Key iTunes + OLAK5uy_ / Spotify)
// =========================================================================
const previewUrlMemCache = {};
let linkMapCache = null;
function loadLinkMapCache() {
  if (linkMapCache) return linkMapCache;
  try {
    const raw = safeGetStorage(STORAGE_KEYS.LINK_CACHE);
    linkMapCache = raw ? JSON.parse(raw) || {} : {};
  } catch {
    linkMapCache = {};
  }
  return linkMapCache;
}

export function resolveAlbumStreamingData(rec) {
  if (!rec) return { year: 'LP', totalMinutes: 40, ytPlaylistId: '', description: '', tracks: [] };
  const rid = Number(rec.release_id);
  if (store.streamCache[rid]) return store.streamCache[rid];

  const curated = CURATED_TRACKLISTS[rid] || null;
  const ytmMap = getYtmReleaseMap();
  const ytmVerified = ytmMap[rid] || ytmMap[String(rid)] || {};
  const ytmDurMap = ytmVerified.trackDurations || {};
  const bakedTracks = Array.isArray(rec.tracklist) && rec.tracklist.length ? rec.tracklist : null;
  const ytPlaylistId = ytmVerified.ytPlaylistId || rec.ytPlaylistId || '';

  let baseTracks = [];
  if (bakedTracks && bakedTracks.length) {
    const curTracks = curated ? curated.tracks : [];
    baseTracks = bakedTracks.map((t, idx) => {
      const ct = curTracks[idx] || {};
      return {
        position: t.position || ct.position || String(idx + 1),
        title: t.title || ct.title || `Track ${idx + 1}`,
        duration: ytmDurMap[String(idx)] || t.duration || ct.duration || '3:45',
        plays: ct.plays || '',
        previewUrl: '',
      };
    });
  } else if (curated && Array.isArray(curated.tracks)) {
    baseTracks = curated.tracks.map((t, idx) => ({
      ...t,
      duration: ytmDurMap[String(idx)] || t.duration || '3:45',
      previewUrl: '',
    }));
  } else {
    baseTracks = [{ position: 'A1', title: rec.title, duration: '3:45', plays: '', previewUrl: '' }];
  }

  const totalSecs = baseTracks.reduce((acc, t) => acc + parseDurationToSeconds(t.duration), 0);
  const compiled = {
    year: (curated && curated.year) || rec.year || 'LP',
    totalMinutes: Math.max(1, Math.round(totalSecs / 60)),
    ytPlaylistId,
    description:
      (curated && curated.description) ||
      `${rec.title} by ${rec.artist} • ${rec.label} (${rec.catno !== 'none' ? rec.catno : 'LP'})`,
    tracks: baseTracks,
  };
  store.streamCache[rid] = compiled;
  return compiled;
}

export function getVerifiedOlakPlaylistId(rec, streamData) {
  if (!rec) return '';
  const rid = Number(rec.release_id);
  const lCache = loadLinkMapCache();
  const cached = lCache[rid] || lCache[String(rid)] || {};
  if (cached.olakId && String(cached.olakId).startsWith('OLAK5uy_')) return String(cached.olakId);

  const ytmMap = getYtmReleaseMap();
  const stemMap = getYtmStemMap();
  const ytmVerified = ytmMap[rid] || ytmMap[String(rid)] || {};
  const stemKey = computeAlbumFuzzyStemKey(rec.artist, rec.title);
  const stemOlak = stemMap[stemKey] || '';

  for (const c of [ytmVerified.ytPlaylistId, rec.ytPlaylistId, streamData && streamData.ytPlaylistId, stemOlak]) {
    if (typeof c === 'string' && c.startsWith('OLAK5uy_')) return c;
  }
  return '';
}

export function getVerifiedSpotifyAlbumId(rec) {
  if (!rec) return '';
  const rid = Number(rec.release_id);
  const lCache = loadLinkMapCache();
  const cached = lCache[rid] || lCache[String(rid)] || {};
  if (cached.spotifyAlbumId && /^[A-Za-z0-9]{15,30}$/.test(String(cached.spotifyAlbumId))) {
    return String(cached.spotifyAlbumId);
  }
  const ytmMap = getYtmReleaseMap();
  const ytmVerified = ytmMap[rid] || ytmMap[String(rid)] || {};
  for (const c of [rec.spotifyAlbumId, ytmVerified.spotifyAlbumId]) {
    if (typeof c === 'string' && /^[A-Za-z0-9]{15,30}$/.test(c)) return c;
  }
  return '';
}

export function getYouTubeMusicDeepLink(rec, streamData = null) {
  const olakId = getVerifiedOlakPlaylistId(rec, streamData);
  if (olakId) return `https://music.youtube.com/playlist?list=${encodeURIComponent(olakId)}`;
  const q = `${cleanArtistName(rec ? rec.artist : '')} ${cleanSearchTitle(rec ? rec.title : '')}`.trim();
  return `https://music.youtube.com/search?q=${encodeURIComponent(q)}`;
}

export function getSpotifyAlbumDeepLink(rec) {
  if (!rec) return 'https://open.spotify.com';
  const spId = getVerifiedSpotifyAlbumId(rec);
  if (spId) return `https://open.spotify.com/album/${encodeURIComponent(spId)}`;
  const q = `${cleanArtistName(rec.artist || '')} ${cleanSearchTitle(rec.title || '')}`.trim();
  return `https://open.spotify.com/search/${encodeURIComponent(q)}/albums`;
}

function fetchJsonpUrl(url, callbackParam = 'callback', timeoutMs = 3400) {
  return new Promise((resolve, reject) => {
    const cbName = `__vaultJsonp_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
    const script = document.createElement('script');
    let settled = false;
    const cleanup = () => {
      delete window[cbName];
      if (script.parentNode) script.parentNode.removeChild(script);
    };
    const tid = setTimeout(() => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(new Error('JSONP timeout'));
    }, timeoutMs);

    window[cbName] = (data) => {
      if (settled) return;
      settled = true;
      clearTimeout(tid);
      cleanup();
      resolve(data);
    };
    script.onerror = () => {
      if (settled) return;
      settled = true;
      clearTimeout(tid);
      cleanup();
      reject(new Error('JSONP error'));
    };
    const sep = url.includes('?') ? '&' : '?';
    script.src = `${url}${sep}${callbackParam}=${cbName}`;
    document.head.appendChild(script);
  });
}

function scorePreviewCandidate(itemArtist, itemTrack, itemAlbum, targetArtKey, targetTrkKey, targetAlbKey) {
  const aKey = normalizeTrackKey(itemArtist || '');
  const tKey = normalizeTrackKey(itemTrack || '');
  const cKey = normalizeTrackKey(itemAlbum || '');
  let score = 0;
  if (aKey && targetArtKey) {
    if (aKey === targetArtKey) score += 50;
    else if (aKey.includes(targetArtKey) || targetArtKey.includes(aKey)) score += 30;
    else return -1;
  }
  if (tKey && targetTrkKey) {
    if (tKey === targetTrkKey) score += 60;
    else if (tKey.startsWith(targetTrkKey) || targetTrkKey.startsWith(tKey)) score += 45;
    else if (tKey.includes(targetTrkKey) || targetTrkKey.includes(tKey)) score += 30;
  }
  if (cKey && targetAlbKey && (cKey.includes(targetAlbKey) || targetAlbKey.includes(cKey))) {
    score += 20;
  }
  return score;
}

function getPreviewCacheKey(rec, trackTitle) {
  const cleanArt = cleanArtistName((rec && rec.artist) || '');
  const cleanTrk = cleanSearchTitle(trackTitle || (rec && rec.title) || '');
  return `p30_${normalizeTrackKey(cleanArt)}_${normalizeTrackKey(cleanTrk)}`;
}

let persistedPreviewMap = null;
function getPersistedPreviewMap() {
  if (persistedPreviewMap) return persistedPreviewMap;
  try {
    const raw = safeGetStorage(STORAGE_KEYS.PREVIEW_CACHE);
    persistedPreviewMap = raw ? JSON.parse(raw) || {} : {};
  } catch {
    persistedPreviewMap = {};
  }
  return persistedPreviewMap;
}

function savePreviewUrlToCache(cacheKey, url) {
  if (!url || /dzcdn\.net/i.test(url)) return;
  previewUrlMemCache[cacheKey] = url;
  const map = getPersistedPreviewMap();
  map[cacheKey] = url;
  const keys = Object.keys(map);
  if (keys.length > 180) {
    delete map[keys[0]];
  }
  safeSetStorage(STORAGE_KEYS.PREVIEW_CACHE, JSON.stringify(map));
}

export async function resolve30sTrackPreviewUrl(rec, trackTitle) {
  if (!rec) return null;
  const cleanArt = cleanArtistName(rec.artist || '');
  const cleanTrk = cleanSearchTitle(trackTitle || rec.title || '');
  const cleanAlb = cleanSearchTitle(rec.title || '');
  const artKey = normalizeTrackKey(cleanArt);
  const trkKey = normalizeTrackKey(cleanTrk);
  const albKey = normalizeTrackKey(cleanAlb);
  const cacheKey = getPreviewCacheKey(rec, trackTitle);

  if (previewUrlMemCache[cacheKey]) return previewUrlMemCache[cacheKey];
  const savedMap = getPersistedPreviewMap();
  if (savedMap[cacheKey]) {
    previewUrlMemCache[cacheKey] = savedMap[cacheKey];
    return savedMap[cacheKey];
  }

  const pickBest = (results) => {
    if (!Array.isArray(results) || !results.length) return null;
    let bestUrl = null;
    let bestScore = -1;
    for (const item of results) {
      if (!item || !item.previewUrl) continue;
      const sc = scorePreviewCandidate(item.artistName, item.trackName, item.collectionName, artKey, trkKey, albKey);
      const itemAKey = normalizeTrackKey(item.artistName || '');
      const itemTKey = normalizeTrackKey(item.trackName || '');
      if (itemAKey === artKey && itemTKey) {
        savePreviewUrlToCache(`p30_${artKey}_${itemTKey}`, item.previewUrl);
      }
      if (sc > bestScore) {
        bestScore = sc;
        bestUrl = item.previewUrl;
      }
    }
    return bestUrl;
  };

  const queries = [
    `${cleanArt} ${cleanTrk} ${cleanAlb}`.trim(),
    `${cleanArt} ${cleanTrk}`.trim(),
    `${cleanArt} ${cleanAlb}`.trim(),
  ];

  for (const q of queries) {
    const baseUrl = `https://itunes.apple.com/search?term=${encodeURIComponent(q)}&media=music&entity=song&limit=25`;
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), 3200);
    try {
      const resp = await fetch(baseUrl, { signal: ctrl.signal });
      if (resp.ok) {
        const data = await resp.json();
        const best = pickBest(data && data.results);
        if (best) {
          savePreviewUrlToCache(cacheKey, best);
          return best;
        }
      }
    } catch {
      try {
        const data = await fetchJsonpUrl(baseUrl, 'callback', 3200);
        const best = pickBest(data && data.results);
        if (best) {
          savePreviewUrlToCache(cacheKey, best);
          return best;
        }
      } catch {
        // Continue to next query
      }
    } finally {
      clearTimeout(tid);
    }
  }
  return null;
}

// =========================================================================
// Side B Tracklist Deck Rendering & Playback Transport
// =========================================================================
let playbackReqId = 0;

export function updateStreamingQuickLinks(rec, streamData = null) {
  if (!rec) return;
  const artPill = document.getElementById('stream-artist-pill');
  if (artPill) artPill.textContent = rec.artist;
  const sData = streamData || resolveAlbumStreamingData(rec);
  const ytmLink = document.getElementById('stream-ytm-direct-link');
  if (ytmLink) ytmLink.href = getYouTubeMusicDeepLink(rec, sData);
  const spLink = document.getElementById('stream-spotify-direct-link');
  if (spLink) spLink.href = getSpotifyAlbumDeepLink(rec);
}

export function updateStreamTransportUI(rec) {
  const playIcon = document.getElementById('stream-play-icon');
  const coverHoverIcon = document.getElementById('stream-cover-hover-icon');
  const badgeEl = document.getElementById('stream-cover-playing-badge');
  const nowLabel = document.getElementById('stream-now-playing-label');
  const engineDot = document.getElementById('stream-engine-dot');

  const rid = rec ? Number(rec.release_id) : 0;
  const isThisActive = store.activeStreamRid === rid && store.isPreviewPlaying;

  if (playIcon) {
    playIcon.textContent = isThisActive ? '⏸' : '▶';
    playIcon.className = isThisActive ? '' : 'ml-0.5';
  }
  if (coverHoverIcon) coverHoverIcon.textContent = isThisActive ? '⏸' : '▶';
  if (badgeEl) badgeEl.classList.toggle('hidden', !isThisActive);
  if (engineDot) {
    engineDot.className = isThisActive
      ? 'w-2 h-2 rounded-full bg-emerald-400 animate-ping shrink-0'
      : 'w-2 h-2 rounded-full bg-rose-500 shrink-0';
  }

  const streamData = rec ? resolveAlbumStreamingData(rec) : null;
  const tracks = streamData && Array.isArray(streamData.tracks) ? streamData.tracks : [];
  if (store.activeStreamRid === rid && store.activeTrackIndex >= 0 && tracks[store.activeTrackIndex]) {
    const curTrack = tracks[store.activeTrackIndex];
    if (nowLabel) {
      nowLabel.textContent = `${store.isPreviewPlaying ? '▶ [30s Needle-Drop]' : '⏸ [Paused]'} ${store.activeTrackIndex + 1}/${tracks.length}: ${curTrack.title}`;
    }
  } else if (nowLabel) {
    nowLabel.textContent = 'Drop tonearm or click any track below for 30s preview';
  }
  updateStreamingQuickLinks(rec, streamData);
}

export function paintStreamingTracklistUI(rec, streamData) {
  if (!rec) return;
  const rid = Number(rec.release_id);
  const tracks = streamData && Array.isArray(streamData.tracks) ? streamData.tracks : [];
  const mins = streamData && streamData.totalMinutes ? streamData.totalMinutes : 42;
  const yr = (streamData && streamData.year) || rec.year || 'LP';

  const metaEl = document.getElementById('stream-album-meta');
  if (metaEl) {
    metaEl.textContent = tracks.length > 0
      ? `${rec.artist} • ${yr} • ${tracks.length} song${tracks.length === 1 ? '' : 's'} • ${mins} mins`
      : `${rec.artist} • ${yr} • ${(rec.wax_spec && rec.wax_spec.variant_badge) || 'LP'}`;
  }

  const listEl = document.getElementById('stream-tracklist-list');
  if (!listEl) return;

  const isThisRecordActive = store.activeStreamRid === rid;
  const albumYtmUrl = escapeHtml(safeExternalUrl(getYouTubeMusicDeepLink(rec, streamData), 'https://music.youtube.com'));
  const albumSpotifyUrl = escapeHtml(safeExternalUrl(getSpotifyAlbumDeepLink(rec), 'https://open.spotify.com'));

  listEl.innerHTML = tracks
    .map((t, idx) => {
      const isCurrent = isThisRecordActive && store.activeTrackIndex === idx;
      const isPlayingNow = isCurrent && store.isPreviewPlaying;
      const sourceTag = isPlayingNow ? '▶ Playing 30s Preview' : '🎵 30s Preview';
      const subMeta = t.plays
        ? `${t.plays}${t.position ? ` • ${t.position}` : ''} • ${sourceTag}`
        : `${t.position ? `Side ${t.position} • ` : ''}${sourceTag}`;

      return `
        <div
          data-track-idx="${idx}"
          data-track-rid="${rid}"
          class="group flex items-center justify-between gap-2 py-1.5 px-2.5 rounded-lg cursor-pointer transition select-none ${
            isCurrent
              ? 'bg-rose-500/20 text-rose-100 border border-rose-500/40 shadow-sm'
              : 'hover:bg-white/[0.07] text-slate-200 border border-transparent'
          }"
        >
          <div class="flex items-center gap-2.5 min-w-0 flex-1">
            <div class="w-5 text-center text-[11px] font-mono-tech shrink-0 ${isCurrent ? 'text-rose-400 font-bold' : 'text-slate-400'}">
              ${
                isPlayingNow
                  ? `<span class="inline-flex items-end justify-center gap-0.5 h-3">
                       <span class="w-0.5 bg-rose-400 eq-bar-1"></span>
                       <span class="w-0.5 bg-cyan-400 eq-bar-2"></span>
                       <span class="w-0.5 bg-emerald-400 eq-bar-3"></span>
                     </span>`
                  : `<span class="group-hover:hidden">${idx + 1}</span><span class="hidden group-hover:inline text-rose-400 font-bold">▶</span>`
              }
            </div>
            <div class="min-w-0 flex-1">
              <div class="text-xs font-bold truncate ${isCurrent ? 'text-rose-200' : 'text-white group-hover:text-rose-200'}">
                ${escapeHtml(t.title)}
              </div>
              <div class="text-[10px] text-slate-400 truncate">${escapeHtml(subMeta)}</div>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <span class="opacity-0 group-hover:opacity-100 ${isCurrent ? '!opacity-100 bg-rose-600 text-white' : 'bg-rose-500/20 text-rose-300'} px-1.5 py-0.5 rounded text-[9px] font-mono-tech font-semibold transition">
              ${isPlayingNow ? '⏸ Pause' : '▶ 30s'}
            </span>
            <a href="${albumYtmUrl}" target="_blank" rel="noopener noreferrer" data-ytm-ext="1" data-ytm-role="ytm" class="opacity-0 group-hover:opacity-100 hover:bg-rose-500/25 text-slate-400 hover:text-rose-200 px-1 py-0.5 rounded text-[9px] font-mono-tech transition" title="Open Full Album on YouTube Music">YT↗</a>
            <a href="${albumSpotifyUrl}" target="_blank" rel="noopener noreferrer" data-ytm-ext="1" data-ytm-role="spotify" class="opacity-0 group-hover:opacity-100 hover:bg-emerald-500/25 text-slate-400 hover:text-emerald-200 px-1 py-0.5 rounded text-[9px] font-mono-tech transition" title="Open Full Album on Spotify">SP↗</a>
            <span class="text-[11px] font-mono-tech text-slate-400 w-9 text-right">${escapeHtml(t.duration || '3:45')}</span>
          </div>
        </div>
      `;
    })
    .join('');

  updateStreamTransportUI(rec);
}

export function renderStreamingDeck(rec) {
  if (!rec) return;
  const rid = Number(rec.release_id);
  const wax = rec.wax_spec || {};
  const c1 = wax.primary_color || '#e11d48';
  const c2 = wax.secondary_color || '#7c3aed';

  const glowEl = document.getElementById('stream-ambient-glow');
  if (glowEl) {
    glowEl.style.background = `radial-gradient(circle at 50% 12%, ${c1}77, ${c2}38 56%, transparent 88%)`;
  }

  const { primary: covPrimary, fallback: covFallback } = getCoverUrls(rec);
  const coverImg = document.getElementById('stream-cover-img');
  if (coverImg) {
    coverImg.src = covPrimary || covFallback || '';
    coverImg.onerror = function onCoverErr() {
      if (covFallback && this.src !== covFallback) this.src = covFallback;
    };
  }

  const artPill = document.getElementById('stream-artist-pill');
  if (artPill) artPill.textContent = rec.artist;
  const titleEl = document.getElementById('stream-album-title');
  if (titleEl) titleEl.textContent = rec.title;

  const streamData = resolveAlbumStreamingData(rec);
  paintStreamingTracklistUI(rec, streamData);

  if (store.activeStreamRid !== rid) {
    const timeReadout = document.getElementById('stream-time-readout');
    if (timeReadout) timeReadout.textContent = '0:00 / 0:30';
    const seekSlider = document.getElementById('stream-seek-slider');
    if (seekSlider) seekSlider.value = '0';
  }
}

export function stopPreviewAudio() {
  const audioEl = document.getElementById('vault-preview-audio');
  if (audioEl && !audioEl.paused) {
    try {
      audioEl.pause();
    } catch {
      // Ignore
    }
  }
  store.isPreviewPlaying = false;
  emit('audioPlaybackChanged', { playing: false });
}

export async function playAlbumTrackAtIndex(rec, trackIdx, options = {}) {
  if (!rec) return;
  stopArenaAudio();
  const rid = Number(rec.release_id);
  const streamData = resolveAlbumStreamingData(rec);
  const tracks = streamData.tracks && streamData.tracks.length
    ? streamData.tracks
    : [{ position: 'A1', title: rec.title, duration: '3:45' }];

  const safeIdx = ((trackIdx % tracks.length) + tracks.length) % tracks.length;
  const track = tracks[safeIdx];
  const reqId = ++playbackReqId;

  store.activeStreamRid = rid;
  store.activeTrackIndex = safeIdx;

  const audioEl = document.getElementById('vault-preview-audio');
  if (audioEl && !audioEl.paused) {
    try {
      audioEl.pause();
    } catch {
      // Ignore
    }
  }

  const seekSlider = document.getElementById('stream-seek-slider');
  if (seekSlider) seekSlider.value = '0';
  const timeReadout = document.getElementById('stream-time-readout');
  if (timeReadout) timeReadout.textContent = '0:00 / 0:30';

  const nowLabel = document.getElementById('stream-now-playing-label');
  if (nowLabel) nowLabel.textContent = `⏳ Loading 30s needle-drop: ${track.title}...`;

  if (!options.skipNeedleSound) playNeedleDropSound();

  const previewUrl = await resolve30sTrackPreviewUrl(rec, track.title);
  if (playbackReqId !== reqId) return;

  if (!previewUrl || !audioEl) {
    store.isPreviewPlaying = false;
    paintStreamingTracklistUI(rec, streamData);
    // Graceful vinyl crackle fallback when offline or unmatched
    if (!store.crackleOn) toggleVinylCrackle(true);
    if (nowLabel) {
      nowLabel.textContent = `🎧 Vinyl Groove Active (No iTunes clip for "${track.title}" — open YT Music / Spotify ↗)`;
    }
    emit('audioPlaybackChanged', { playing: false, track, trackIdx: safeIdx, totalTracks: tracks.length });
    return;
  }

  ensureMainAudioPipeline();

  const attemptPlay = async (useCors) => {
    if (useCors && !untaintedAudioMode) {
      audioEl.crossOrigin = 'anonymous';
    } else {
      audioEl.removeAttribute('crossorigin');
    }
    setPitchPreservationOff(audioEl);
    audioEl.src = previewUrl;
    audioEl.currentTime = 0;
    audioEl.muted = Boolean(store.isAudioMuted);
    const speedRatio = store.quartzPitchLock ? 1.0 : (store.rpm === 45 ? 1.35 : 1.0);
    audioEl.playbackRate = store.isSpinning ? speedRatio : 0.4;
    await audioEl.play();
  };

  try {
    await attemptPlay(!untaintedAudioMode);
  } catch (err) {
    if (!untaintedAudioMode && (!err || err.name !== 'NotAllowedError')) {
      untaintedAudioMode = true;
      mainPreviewSource = null;
      try {
        await attemptPlay(false);
      } catch {
        store.isPreviewPlaying = false;
        paintStreamingTracklistUI(rec, streamData);
        if (nowLabel) nowLabel.textContent = `Click ▶ again to start "${track.title}"`;
        return;
      }
    } else {
      store.isPreviewPlaying = false;
      paintStreamingTracklistUI(rec, streamData);
      if (nowLabel) nowLabel.textContent = `Click ▶ again to start "${track.title}"`;
      return;
    }
  }

  if (playbackReqId !== reqId) return;
  store.isPreviewPlaying = true;
  if (!store.isSpinning) {
    store.motorOn = true;
    store.isSpinning = true;
    emit('motorStartRequested');
  }
  paintStreamingTracklistUI(rec, streamData);
  emit('audioPlaybackChanged', { playing: true, track, trackIdx: safeIdx, totalTracks: tracks.length });
}

export function toggleInPagePlayPause() {
  const rec = getActiveRecord();
  if (!rec) return;
  const rid = Number(rec.release_id);
  const audioEl = document.getElementById('vault-preview-audio');

  if (store.activeStreamRid === rid && store.isPreviewPlaying) {
    stopPreviewAudio();
    const sData = resolveAlbumStreamingData(rec);
    paintStreamingTracklistUI(rec, sData);
    return;
  }

  if (
    store.activeStreamRid === rid &&
    store.activeTrackIndex >= 0 &&
    audioEl &&
    audioEl.src &&
    audioEl.paused &&
    audioEl.currentTime > 0 &&
    audioEl.currentTime < (audioEl.duration || 30) - 0.5
  ) {
    audioEl.play().then(() => {
      store.isPreviewPlaying = true;
      paintStreamingTracklistUI(rec, resolveAlbumStreamingData(rec));
      emit('audioPlaybackChanged', { playing: true });
    }).catch(() => {
      playAlbumTrackAtIndex(rec, store.activeTrackIndex);
    });
    return;
  }

  const nextIdx = store.activeStreamRid === rid && store.activeTrackIndex >= 0 ? store.activeTrackIndex : 0;
  playAlbumTrackAtIndex(rec, nextIdx);
}

// =========================================================================
// Twin-Deck Arena DJ Crossfader Engine (Deck A & Deck B)
// =========================================================================
let deckAAudio = null;
let deckBAudio = null;
let arenaPlaybackState = { aRid: 0, bRid: 0, playing: false };

function ensureArenaDecks() {
  if (!deckAAudio) {
    deckAAudio = new Audio();
    deckAAudio.preload = 'none';
    deckAAudio.loop = true;
  }
  if (!deckBAudio) {
    deckBAudio = new Audio();
    deckBAudio.preload = 'none';
    deckBAudio.loop = true;
  }
}

export function applyArenaCrossfade(val) {
  const x = Math.max(-1, Math.min(1, Number(val || 0)));
  store.arenaCrossfade = x;
  if (!deckAAudio || !deckBAudio) return;
  // Equal-power DJ crossfade curve
  const norm = (x + 1) * 0.5; // 0..1
  const gainA = Math.cos(norm * Math.PI * 0.5);
  const gainB = Math.sin(norm * Math.PI * 0.5);
  deckAAudio.volume = store.isAudioMuted ? 0 : Math.min(1, gainA * 1.05);
  deckBAudio.volume = store.isAudioMuted ? 0 : Math.min(1, gainB * 1.05);
}

export async function auditionArenaDeck(side, rec) {
  if (!rec) return;
  stopPreviewAudio();
  ensureArenaDecks();
  const track = (resolveAlbumStreamingData(rec).tracks || [])[0] || { title: rec.title };
  const url = await resolve30sTrackPreviewUrl(rec, track.title);
  if (!url) {
    showToast(`No 30s iTunes preview found for ${rec.artist} — "${rec.title}"`);
    return false;
  }
  const el = side === 'A' ? deckAAudio : deckBAudio;
  const rid = Number(rec.release_id);
  if (side === 'A') arenaPlaybackState.aRid = rid;
  else arenaPlaybackState.bRid = rid;

  el.src = url;
  el.currentTime = 0;
  applyArenaCrossfade(side === 'A' ? -1 : 1);
  try {
    await el.play();
    arenaPlaybackState.playing = true;
    playNeedleDropSound();
    emit('arenaAudioChanged', { side, rec, playing: true });
    return true;
  } catch {
    return false;
  }
}

export async function dualDropArenaDecks(recA, recB) {
  if (!recA || !recB) return;
  stopPreviewAudio();
  ensureArenaDecks();
  const trA = (resolveAlbumStreamingData(recA).tracks || [])[0] || { title: recA.title };
  const trB = (resolveAlbumStreamingData(recB).tracks || [])[0] || { title: recB.title };
  const [urlA, urlB] = await Promise.all([
    resolve30sTrackPreviewUrl(recA, trA.title),
    resolve30sTrackPreviewUrl(recB, trB.title),
  ]);
  if (urlA) {
    deckAAudio.src = urlA;
    deckAAudio.currentTime = 0;
    arenaPlaybackState.aRid = Number(recA.release_id);
  }
  if (urlB) {
    deckBAudio.src = urlB;
    deckBAudio.currentTime = 0;
    arenaPlaybackState.bRid = Number(recB.release_id);
  }
  applyArenaCrossfade(store.arenaCrossfade);
  const plays = [];
  if (urlA) plays.push(deckAAudio.play().catch(() => {}));
  if (urlB) plays.push(deckBAudio.play().catch(() => {}));
  await Promise.all(plays);
  arenaPlaybackState.playing = Boolean(urlA || urlB);
  playNeedleDropSound();
  emit('arenaAudioChanged', { side: 'BOTH', playing: arenaPlaybackState.playing });
}

export function stopArenaAudio() {
  if (deckAAudio && !deckAAudio.paused) deckAAudio.pause();
  if (deckBAudio && !deckBAudio.paused) deckBAudio.pause();
  arenaPlaybackState.playing = false;
  emit('arenaAudioChanged', { side: 'NONE', playing: false });
}

export function isArenaAudioPlaying() {
  return arenaPlaybackState.playing;
}

export function bindAudioEngineEvents() {
  const audioEl = document.getElementById('vault-preview-audio');
  if (audioEl) {
    audioEl.addEventListener('timeupdate', () => {
      const curSec = Number(audioEl.currentTime || 0);
      const totSec = Number(audioEl.duration || 0);
      if (totSec > 0) {
        const pct = Math.min(100, Math.round((curSec / totSec) * 100));
        const seekSlider = document.getElementById('stream-seek-slider');
        if (seekSlider) seekSlider.value = String(pct);
        const timeReadout = document.getElementById('stream-time-readout');
        if (timeReadout) {
          timeReadout.textContent = `${formatMillisToDuration(curSec * 1000) || '0:00'} / ${formatMillisToDuration(totSec * 1000) || '0:30'}`;
        }
      }
    });
    audioEl.addEventListener('ended', () => {
      const playingRec = store.records.find((r) => Number(r.release_id) === Number(store.activeStreamRid));
      const sData = playingRec ? resolveAlbumStreamingData(playingRec) : null;
      const trList = sData && Array.isArray(sData.tracks) ? sData.tracks : [];
      if (playingRec && store.activeTab !== 'arena' && store.autoAdvanceTracks && store.activeTrackIndex + 1 < trList.length) {
        playAlbumTrackAtIndex(playingRec, store.activeTrackIndex + 1, { skipNeedleSound: true });
      } else {
        stopPreviewAudio();
        const stageRec = getActiveRecord();
        if (stageRec && playingRec && Number(stageRec.release_id) === Number(playingRec.release_id) && sData) {
          paintStreamingTracklistUI(stageRec, sData);
        }
      }
    });
  }

  document.getElementById('stream-artist-link')?.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const rec = getActiveRecord();
    if (rec) playAlbumTrackAtIndex(rec, 0);
  });

  document.getElementById('btn-stream-play')?.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleInPagePlayPause();
  });
  document.getElementById('stream-cover-btn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleInPagePlayPause();
  });

  document.getElementById('btn-stream-restart')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const rec = getActiveRecord();
    if (!rec) return;
    const curIdx = store.activeStreamRid === Number(rec.release_id) && store.activeTrackIndex >= 0 ? store.activeTrackIndex : 0;
    playAlbumTrackAtIndex(rec, curIdx);
  });

  document.getElementById('btn-stream-mute')?.addEventListener('click', (e) => {
    e.stopPropagation();
    store.isAudioMuted = !store.isAudioMuted;
    const btn = document.getElementById('btn-stream-mute');
    if (btn) btn.textContent = store.isAudioMuted ? '🔇' : '🔊';
    if (audioEl) audioEl.muted = Boolean(store.isAudioMuted);
    applyArenaCrossfade(store.arenaCrossfade);
    showToast(store.isAudioMuted ? 'Muted Turntable Audio' : 'Unmuted Turntable Audio');
  });

  document.getElementById('btn-stream-prev')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const rec = getActiveRecord();
    if (!rec) return;
    const curIdx = store.activeStreamRid === Number(rec.release_id) && store.activeTrackIndex >= 0 ? store.activeTrackIndex : 0;
    playAlbumTrackAtIndex(rec, Math.max(0, curIdx - 1));
  });

  document.getElementById('btn-stream-next')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const rec = getActiveRecord();
    if (!rec) return;
    const curIdx = store.activeStreamRid === Number(rec.release_id) ? store.activeTrackIndex : -1;
    playAlbumTrackAtIndex(rec, curIdx + 1);
  });

  document.getElementById('btn-stream-popout')?.addEventListener('click', (e) => {
    e.stopPropagation();
    store.autoAdvanceTracks = !store.autoAdvanceTracks;
    const btn = document.getElementById('btn-stream-popout');
    if (btn) {
      btn.className = store.autoAdvanceTracks
        ? 'w-7 h-7 rounded-full bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 text-cyan-300 flex items-center justify-center text-[11px] transition'
        : 'w-7 h-7 rounded-full bg-white/5 hover:bg-white/15 border border-white/10 text-slate-400 flex items-center justify-center text-[11px] transition';
      btn.title = `Continuous Full-Album Auto-Advance (${store.autoAdvanceTracks ? 'ON' : 'OFF'})`;
    }
    showToast(`Continuous Auto-Advance: ${store.autoAdvanceTracks ? 'ON' : 'OFF'}`);
  });

  document.getElementById('stream-tracklist-list')?.addEventListener('click', (e) => {
    if (e.target.closest('[data-ytm-ext]')) {
      e.stopPropagation();
      return;
    }
    e.stopPropagation();
    const row = e.target.closest('[data-track-idx]');
    if (!row) return;
    const idx = Number(row.getAttribute('data-track-idx') || 0);
    const rec = getActiveRecord();
    if (!rec) return;
    if (store.activeStreamRid === Number(rec.release_id) && store.activeTrackIndex === idx && store.isPreviewPlaying) {
      stopPreviewAudio();
      paintStreamingTracklistUI(rec, resolveAlbumStreamingData(rec));
    } else {
      playAlbumTrackAtIndex(rec, idx);
    }
  });

  document.getElementById('stream-seek-slider')?.addEventListener('input', (e) => {
    const pct = Number(e.target.value || 0);
    if (audioEl && audioEl.duration > 0) {
      audioEl.currentTime = (pct / 100) * audioEl.duration;
    }
  });
}
