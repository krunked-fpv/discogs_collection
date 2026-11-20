// KRUNKED // VINYL VAULT v6.0 — Thermal Flattening Lab Mission Control & Per-Record Warp Notes

import { playTimerChime } from './audio-preview.js';
import {
  STORAGE_KEYS,
  buildFlatteningQueueObject,
  setActiveRecordById,
  setFlatteningNote,
  setRecordFlatteningStatus,
  store,
  subscribe,
  syncInlineFlatteningFormState,
} from './store.js';
import {
  DEFAULT_FLATTENING_STATUS,
  escapeHtml,
  formatDurationHms,
  formatUsdValue,
  renderCrateWaxDiscHTML,
  safeExternalUrl,
  safeGetStorage,
  safeRemoveStorage,
  safeSetStorage,
  showToast,
} from './utils.js';

const HOLD_DURATION_MS = 150 * 60 * 1000; // 2.5 hours
const RING_CIRCUMFERENCE = 2 * Math.PI * 42;

let timerInterval = null;

function notifyHoldComplete(recordLabel) {
  if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
    try {
      new Notification('KRUNKED // 2.5h Thermal Hold Complete', {
        body: recordLabel
          ? `${recordLabel} finished 130°F hold — turn plate off & cool completely before unbagging.`
          : 'Turn plate off and let vinyl pouch cool completely before unbagging!',
      });
    } catch {
      // Ignore notification restrictions
    }
  }
}

export function updateThermalTimerUI() {
  const readoutEl = document.getElementById('timer-readout');
  const badgeEl = document.getElementById('timer-phase-badge');
  const ringEl = document.getElementById('thermal-progress-circle');
  const finishBtn = document.getElementById('btn-timer-finish-lp');
  if (!readoutEl || !badgeEl) return;

  const rawState = safeGetStorage(STORAGE_KEYS.FLATTEN_TIMER);
  if (!rawState) {
    readoutEl.textContent = '02:30:00';
    badgeEl.textContent = 'Plate Idle • Ready';
    badgeEl.className = 'px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-slate-800 text-slate-300 border border-white/10';
    if (ringEl) ringEl.style.strokeDashoffset = String(RING_CIRCUMFERENCE);
    finishBtn?.classList.add('hidden');
    return;
  }

  let tState = null;
  try {
    tState = JSON.parse(rawState);
  } catch {
    return;
  }
  if (!tState) return;

  if (tState.mode === 'ramp') {
    const elapsedMs = Date.now() - (tState.startedAt || Date.now());
    readoutEl.textContent = formatDurationHms(elapsedMs);
    badgeEl.textContent = '🔥 Stage 1: Ramping to 130°F';
    badgeEl.className = 'px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse';
    if (ringEl) {
      const rampPct = Math.min(1, elapsedMs / (20 * 60 * 1000));
      ringEl.style.strokeDashoffset = String(RING_CIRCUMFERENCE * (1 - rampPct));
    }
    finishBtn?.classList.toggle('hidden', !tState.recordId);
  } else if (tState.mode === 'hold') {
    const remainingMs = (tState.endsAt || 0) - Date.now();
    finishBtn?.classList.toggle('hidden', !tState.recordId);
    if (remainingMs <= 0) {
      readoutEl.textContent = '00:00:00';
      badgeEl.textContent = '✓ 2.5h Hold Complete — Cool Before Unbagging!';
      badgeEl.className = 'px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-emerald-500/25 text-emerald-300 border border-emerald-400/50';
      if (ringEl) ringEl.style.strokeDashoffset = '0';
      if (!tState.notified) {
        tState.notified = true;
        safeSetStorage(STORAGE_KEYS.FLATTEN_TIMER, JSON.stringify(tState));
        playTimerChime();
        const rec = store.records.find((r) => String(r.release_id) === String(tState.recordId));
        notifyHoldComplete(rec ? `${rec.artist} — ${rec.title}` : '');
        showToast('🔥 2.5-Hour Thermal Hold Complete! Turn plate off & cool completely.');
      }
    } else {
      readoutEl.textContent = formatDurationHms(remainingMs);
      badgeEl.textContent = '⏱ Stage 2: Isothermal Hold (130°F • 2.5h)';
      badgeEl.className = 'px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 animate-pulse';
      if (ringEl) {
        const doneFrac = Math.min(1, Math.max(0, 1 - remainingMs / HOLD_DURATION_MS));
        ringEl.style.strokeDashoffset = String(RING_CIRCUMFERENCE * (1 - doneFrac));
      }
    }
  }
}

export function renderFlatteningView() {
  const todo = store.records
    .filter((r) => (r.flattening_status || DEFAULT_FLATTENING_STATUS) === 'Need to be done')
    .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));
  const allDone = store.records
    .filter((r) => r.flattening_status === 'Done')
    .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));
  const allUnlisted = store.records
    .filter((r) => r.flattening_status === 'Not Listed')
    .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));

  const todoCnt = document.getElementById('flatten-todo-count');
  if (todoCnt) todoCnt.textContent = `${todo.length} Records`;
  const doneCnt = document.getElementById('flatten-done-count');
  if (doneCnt) doneCnt.textContent = `${allDone.length} Records`;
  const unlCnt = document.getElementById('flatten-unlisted-count');
  if (unlCnt) unlCnt.textContent = `${allUnlisted.length} Unlisted`;

  const timerSelect = document.getElementById('timer-record-select');
  if (timerSelect) {
    const prevVal = timerSelect.value;
    timerSelect.innerHTML =
      `<option value="">Select LP in Pouch (${todo.length} Queued)...</option>` +
      todo.map((r) => `<option value="${escapeHtml(r.release_id)}">${escapeHtml(r.artist)} — ${escapeHtml(r.title)}</option>`).join('');
    if (prevVal && todo.some((r) => String(r.release_id) === String(prevVal))) {
      timerSelect.value = prevVal;
    }
  }

  const doneQ = store.doneSearchQuery.trim().toLowerCase();
  const filteredDone = doneQ
    ? allDone.filter((r) => `${r.artist || ''} ${r.title || ''} ${r.wax_spec?.variant_badge || ''} ${store.flatteningNotes[r.release_id] || ''}`.toLowerCase().includes(doneQ))
    : allDone;

  const renderRow = (r, isTodo) => {
    const safeHref = escapeHtml(safeExternalUrl(r.discogs_url, `https://www.discogs.com/release/${r.release_id}`));
    const badge = r.wax_spec?.variant_badge || '12" LP';
    const noteVal = store.flatteningNotes[String(r.release_id)] || '';
    return `
      <div class="p-2.5 rounded-xl bg-slate-900/90 border border-white/10 hover:border-cyan-500/30 transition space-y-2">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3 min-w-0 cursor-pointer" data-load-turntable="${escapeHtml(r.release_id)}" title="Click to load onto Turntable Stage">
            <div class="w-11 h-11 rounded-full shrink-0 overflow-hidden shadow">
              ${renderCrateWaxDiscHTML(r, 44, true, store.userOverrides)}
            </div>
            <div class="min-w-0">
              <div class="text-xs font-bold text-white hover:text-cyan-300 truncate">${escapeHtml(r.artist)} — ${escapeHtml(r.title)}</div>
              <div class="text-[11px] font-mono-tech text-slate-400 truncate">${escapeHtml(badge)} • <span class="text-emerald-400">${formatUsdValue(r)}</span></div>
            </div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <button type="button" data-set-flatten="${escapeHtml(r.release_id)}" data-target-status="${isTodo ? 'Done' : 'Need to be done'}" class="px-2.5 py-1 rounded-lg text-[11px] font-mono-tech font-semibold ${isTodo ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30' : 'bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/25'}">
              ${isTodo ? '✓ Flat / Done' : '🔥 Re-Queue'}
            </button>
            <button type="button" data-set-flatten="${escapeHtml(r.release_id)}" data-target-status="Not Listed" class="px-2 py-1 rounded-lg text-[11px] font-mono-tech bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 border border-white/10" title="Exclude from Flattening Queue">
              ✕
            </button>
            <a href="${safeHref}" target="_blank" rel="noopener noreferrer" class="text-xs font-mono-tech text-cyan-400 hover:underline px-1">↗</a>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <input type="text" data-warp-note="${escapeHtml(r.release_id)}" value="${escapeHtml(noteVal)}" placeholder="Warp / thermal inspection note (e.g. slight dish edge, 1 pass 130°F)..." class="w-full bg-slate-950/90 border border-white/10 focus:border-cyan-400/60 rounded-lg px-2.5 py-1 text-[11px] text-slate-200 placeholder-slate-500 outline-none" />
        </div>
      </div>
    `;
  };

  const todoEl = document.getElementById('flatten-todo-list');
  if (todoEl) {
    todoEl.innerHTML = todo.map((r) => renderRow(r, true)).join('') ||
      '<div class="p-4 rounded-xl bg-slate-900/50 border border-white/5 text-xs text-slate-400 text-center">Queue is clear! New Discogs additions automatically appear here for arrival inspection.</div>';
  }
  const doneEl = document.getElementById('flatten-done-list');
  if (doneEl) {
    doneEl.innerHTML = filteredDone.map((r) => renderRow(r, false)).join('') ||
      '<div class="p-4 rounded-xl bg-slate-900/50 border border-white/5 text-xs text-slate-400 text-center">No matching flat &amp; verified records.</div>';
  }

  const benchEl = document.getElementById('flatten-bench-list');
  if (benchEl) {
    const bq = store.benchSearchQuery.trim().toLowerCase();
    const benchPool = bq
      ? allUnlisted.filter((r) => `${r.artist || ''} ${r.title || ''} ${r.label || ''} ${r.catno || ''} ${r.wax_spec?.variant_badge || ''} ${r.release_id || ''}`.toLowerCase().includes(bq))
      : allUnlisted.slice(0, 18);

    benchEl.innerHTML =
      benchPool
        .map(
          (r) => `
        <div class="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-slate-900/80 border border-white/10 hover:border-cyan-500/30 transition">
          <div class="flex items-center gap-2.5 min-w-0 cursor-pointer" data-load-turntable="${escapeHtml(r.release_id)}">
            <div class="w-9 h-9 rounded-full shrink-0 overflow-hidden shadow">
              ${renderCrateWaxDiscHTML(r, 36, true, store.userOverrides)}
            </div>
            <div class="min-w-0">
              <div class="text-xs font-bold text-white truncate">${escapeHtml(r.artist)} — ${escapeHtml(r.title)}</div>
              <div class="text-[10px] font-mono-tech text-slate-400 truncate">#${escapeHtml(r.release_id)} • ${escapeHtml(r.wax_spec?.variant_badge || '12" LP')}</div>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <button type="button" data-set-flatten="${escapeHtml(r.release_id)}" data-target-status="Need to be done" class="px-2 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 text-[10px] font-mono-tech font-semibold">+ 🔥 Queue</button>
            <button type="button" data-set-flatten="${escapeHtml(r.release_id)}" data-target-status="Done" class="px-2 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono-tech font-semibold">+ ✓ Done</button>
          </div>
        </div>
      `
        )
        .join('') ||
      (allUnlisted.length === 0
        ? '<div class="col-span-full text-xs text-slate-400 py-3 text-center">0 unlisted records — all collection LPs are tracked above.</div>'
        : '<div class="col-span-full text-xs text-slate-400 py-3 text-center">No matching unlisted records found.</div>');
  }
}

export function initFlatteningLab() {
  const viewEl = document.getElementById('view-flattening');

  viewEl?.addEventListener('click', (e) => {
    const setBtn = e.target.closest('[data-set-flatten]');
    if (setBtn) {
      setRecordFlatteningStatus(
        Number(setBtn.getAttribute('data-set-flatten')),
        setBtn.getAttribute('data-target-status') || 'Done'
      );
      return;
    }
    const jumpEl = e.target.closest('[data-load-turntable]');
    if (jumpEl) {
      setActiveRecordById(Number(jumpEl.getAttribute('data-load-turntable')));
      window.__setMainVaultTab?.('showcase');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });

  viewEl?.addEventListener('change', (e) => {
    if (e.target.matches('[data-warp-note]')) {
      setFlatteningNote(e.target.getAttribute('data-warp-note'), e.target.value);
      showToast('Saved thermal inspection note.');
    }
  });

  document.getElementById('flatten-protocol-select')?.addEventListener('change', (e) => {
    const protoEl = document.getElementById('flatten-hidden-protocol');
    if (protoEl) {
      protoEl.value = e.target.value;
      protoEl.setAttribute('value', e.target.value);
    }
    syncInlineFlatteningFormState(true);
    showToast(`Protocol set: ${e.target.value}`);
  });

  document.getElementById('flatten-done-search')?.addEventListener('input', (e) => {
    store.doneSearchQuery = e.target.value;
    renderFlatteningView();
  });
  document.getElementById('flatten-bench-search')?.addEventListener('input', (e) => {
    store.benchSearchQuery = e.target.value;
    renderFlatteningView();
  });

  document.getElementById('btn-timer-ramp')?.addEventListener('click', () => {
    safeSetStorage(
      STORAGE_KEYS.FLATTEN_TIMER,
      JSON.stringify({
        mode: 'ramp',
        startedAt: Date.now(),
        recordId: document.getElementById('timer-record-select')?.value || '',
      })
    );
    updateThermalTimerUI();
    showToast('🔥 Stage 1 Ramp started — heat until thermometer hits 130°F.');
  });

  document.getElementById('btn-timer-start')?.addEventListener('click', () => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {});
    }
    safeSetStorage(
      STORAGE_KEYS.FLATTEN_TIMER,
      JSON.stringify({
        mode: 'hold',
        startedAt: Date.now(),
        endsAt: Date.now() + HOLD_DURATION_MS,
        notified: false,
        recordId: document.getElementById('timer-record-select')?.value || '',
      })
    );
    updateThermalTimerUI();
    showToast('⏱ Started 2.5-Hour (150:00) Isothermal Hold Timer!');
  });

  document.getElementById('btn-timer-reset')?.addEventListener('click', () => {
    safeRemoveStorage(STORAGE_KEYS.FLATTEN_TIMER);
    updateThermalTimerUI();
    showToast('Reset thermal plate timer.');
  });

  document.getElementById('btn-timer-finish-lp')?.addEventListener('click', () => {
    const raw = safeGetStorage(STORAGE_KEYS.FLATTEN_TIMER);
    let rid = document.getElementById('timer-record-select')?.value || '';
    if (!rid && raw) {
      try {
        rid = JSON.parse(raw).recordId || '';
      } catch {
        rid = '';
      }
    }
    if (rid) {
      setRecordFlatteningStatus(Number(rid), 'Done');
    }
    safeRemoveStorage(STORAGE_KEYS.FLATTEN_TIMER);
    updateThermalTimerUI();
  });

  document.getElementById('btn-flatten-export-json')?.addEventListener('click', () => {
    const fqObj = buildFlatteningQueueObject();
    const blob = new Blob([JSON.stringify(fqObj, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'flattening_queue.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('Downloaded flattening_queue.json');
  });

  subscribe((topic) => {
    if (topic === 'flatteningChanged' || topic === 'recordsChanged') {
      renderFlatteningView();
    }
  });

  renderFlatteningView();
  updateThermalTimerUI();
  if (!timerInterval) {
    timerInterval = setInterval(updateThermalTimerUI, 1000);
  }
}
