// KRUNKED // VINYL VAULT v6.0 — Tactile Split Sleeve-Peek Crate, 3D Record Store Bin Flipper & Filters

import { playCrateTickSound } from './audio-preview.js';
import {
  applyFiltersAndSort,
  clearAllCrateFilters,
  emit,
  getActiveRecord,
  getEloStats,
  saveUiPrefs,
  setActiveIndex,
  setActiveRecordById,
  store,
  subscribe,
  syncUrlFromState,
} from './store.js';
import {
  DEFAULT_FLATTENING_STATUS,
  escapeHtml,
  formatUsdValue,
  getVerifiedPressingPhotoUrl,
  renderCrateWaxDiscHTML,
  renderJacketSleeveHTML,
  safeCssColor,
} from './utils.js';

let binActiveIdx = 0;
let binDragStartX = 0;
let binDragging = false;
let lastWheelTs = 0;

function renderActiveSubfilterBanner() {
  const banner = document.getElementById('crate-subfilter-banner');
  if (!banner) return;
  const activeTags = [];
  if (store.filterArtist) activeTags.push(`Artist: ${store.filterArtist}`);
  if (store.filterLabel) activeTags.push(`Label: ${store.filterLabel}`);
  if (store.filterYear) activeTags.push(`Year: ${store.filterYear}`);
  if (store.filterColorHex) activeTags.push(`Wax Color: ${store.filterColorHex}`);

  if (!activeTags.length) {
    banner.classList.add('hidden');
    banner.innerHTML = '';
    return;
  }
  banner.classList.remove('hidden');
  banner.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 rounded-2xl bg-cyan-500/15 border border-cyan-400/40 text-xs">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="font-mono-tech font-bold text-cyan-300 uppercase text-[10px]">Active Constellation Filter:</span>
        ${activeTags.map((t) => `<span class="px-2 py-0.5 rounded-full bg-slate-950 text-white font-semibold border border-white/15">${escapeHtml(t)}</span>`).join('')}
      </div>
      <button type="button" id="btn-clear-subfilters" class="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-cyan-300 font-mono-tech font-bold text-[11px] border border-cyan-500/30">✕ Clear Filter</button>
    </div>
  `;
}

export function renderCrateGrid() {
  const grid = document.getElementById('collection-grid');
  const binWrap = document.getElementById('crate-bin-3d-wrap');
  const statusLabel = document.getElementById('grid-status-label');
  if (!grid) return;

  renderActiveSubfilterBanner();

  const _vUser = (window.__DISCOGS_COLLECTION__ && window.__DISCOGS_COLLECTION__.username) || 'krunked';
  if (statusLabel) {
    statusLabel.textContent = `Showing ${store.filteredRecords.length} of ${store.records.length} releases in ${_vUser}'s collection`;
  }

  const isBinMode = store.thumbMode === 'bin3d';
  if (binWrap) binWrap.classList.toggle('hidden', !isBinMode);
  grid.classList.toggle('hidden', isBinMode);

  if (isBinMode) {
    render3DCrateBinFlipper();
    return;
  }

  if (!store.filteredRecords.length) {
    grid.innerHTML = `
      <div class="col-span-full bg-slate-900/60 border border-white/10 rounded-2xl p-8 text-center space-y-2">
        <div class="text-base font-bold text-white">No matching releases found</div>
        <p class="text-xs text-slate-400">Try clearing your search or selecting "All Releases".</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = store.filteredRecords
    .map((rec, idx) => {
      const isSelected = idx === store.activeIndex;
      const verifiedPressingUrl = getVerifiedPressingPhotoUrl(rec, store.userOverrides);
      const flatStatus = rec.flattening_status || DEFAULT_FLATTENING_STATUS;
      const flatPill = flatStatus === 'Need to be done'
        ? `<span class="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-amber-500/25 text-amber-200 border border-amber-400/40 z-30">🔥 Flatten Queue</span>`
        : (flatStatus === 'Done'
          ? `<span class="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-emerald-500/20 text-emerald-200 border border-emerald-400/30 z-30">✓ Flat / Done</span>`
          : '');

      const eloStats = getEloStats(rec.release_id);
      const eloPill = (eloStats.w > 0 || eloStats.l > 0)
        ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono-tech font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">ELO ${eloStats.elo}</span>`
        : '';

      const waxGlow = safeCssColor(rec.wax_spec?.primary_color, '#22d3ee');
      const nowSpinningBadge = `<span data-spinning-badge class="${isSelected ? 'flex' : 'hidden'} absolute bottom-2 left-2.5 px-2 py-0.5 rounded-full text-[9px] font-mono-tech font-bold bg-cyan-500/25 text-cyan-200 border border-cyan-400/50 backdrop-blur-sm z-30 items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-cyan-300 animate-pulse"></span>SPINNING</span>`;

      let visualHtml = '';
      if (store.thumbMode === 'pressing' && verifiedPressingUrl) {
        visualHtml = `
          <div class="relative w-full h-56 bg-gradient-to-b from-slate-900/90 to-[#090b12] flex items-center justify-center p-4 overflow-hidden">
            ${flatPill}
            ${nowSpinningBadge}
            <div class="uv-reactive w-44 h-44 rounded-full shadow-2xl hover-spin transition-transform duration-300 group-hover:scale-105">
              ${renderCrateWaxDiscHTML(rec, 176, true, store.userOverrides)}
            </div>
            <div class="absolute bottom-2.5 left-2.5 w-14 h-14 rounded-lg shadow-lg overflow-hidden border border-white/20 z-20 ${isSelected ? 'hidden' : ''}">
              ${renderJacketSleeveHTML(rec)}
            </div>
            <span class="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-slate-950/75 backdrop-blur-sm text-emerald-300 border border-emerald-500/30 z-30">
              📸 Pressing
            </span>
          </div>
        `;
      } else if (store.thumbMode === 'sleeve') {
        visualHtml = `
          <div class="relative w-full h-56 bg-gradient-to-b from-slate-900/90 to-[#090b12] p-4 flex items-center justify-center overflow-hidden">
            ${flatPill}
            ${nowSpinningBadge}
            <div class="w-44 h-44 shadow-2xl holo-sleeve rounded-xl overflow-hidden transition-transform duration-300 group-hover:scale-[1.03]">
              ${renderJacketSleeveHTML(rec)}
            </div>
            <div class="absolute bottom-2.5 right-2.5 uv-reactive w-16 h-16 rounded-full shadow-2xl hover-spin border border-white/20 z-20">
              ${renderCrateWaxDiscHTML(rec, 68, true, store.userOverrides)}
            </div>
          </div>
        `;
      } else {
        // Default: 'split' (Sleeve + Disc tactile sleeve-peek)
        visualHtml = `
          <div class="sleeve-peek-stage relative w-full h-56 px-4" style="--card-wax-glow: ${waxGlow}22;">
            ${flatPill}
            ${nowSpinningBadge}
            <div class="sleeve-peek-jacket holo-sleeve">
              ${renderJacketSleeveHTML(rec)}
            </div>
            <div class="sleeve-peek-disc uv-reactive">
              ${renderCrateWaxDiscHTML(rec, 150, true, store.userOverrides)}
            </div>
            <span class="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-slate-950/75 backdrop-blur-sm ${
              verifiedPressingUrl
                ? 'text-emerald-300 border border-emerald-500/30'
                : 'text-cyan-300 border border-white/10'
            } z-30">
              ${verifiedPressingUrl ? '📸 Pressing' : '⚙ Wax'}
            </span>
          </div>
        `;
      }

      const safeDiscogsHref = escapeHtml(
        /^https?:\/\//i.test(rec.discogs_url || '') ? rec.discogs_url : `https://www.discogs.com/release/${rec.release_id}`
      );
      const waxBadge = (rec.wax_spec && rec.wax_spec.variant_badge) || '12" LP';
      const priceStr = formatUsdValue(rec);

      return `
        <article
          data-card-index="${idx}"
          data-release-id="${escapeHtml(rec.release_id)}"
          class="card-record group rounded-2xl bg-[#111524]/95 border ${
            isSelected ? 'border-cyan-400 ring-2 ring-cyan-400/30' : 'border-white/10 hover:border-cyan-500/45'
          } overflow-hidden shadow-lg flex flex-col justify-between cursor-pointer"
        >
          <div>
            <div class="relative">
              ${visualHtml}
              <div class="card-quick-actions absolute bottom-2 right-2 z-30 flex items-center gap-1" data-stop-prop="true">
                <button type="button" data-card-view-stage="${idx}" class="px-2 py-1 rounded-lg bg-slate-950/90 hover:bg-fuchsia-500/25 text-[10px] font-mono-tech font-bold text-fuchsia-200 border border-white/15 hover:border-fuchsia-400/50 shadow" title="Load on full Turntable Stage">
                  💿 Stage ↑
                </button>
                <button type="button" data-card-inspect="${escapeHtml(rec.release_id)}" class="px-2 py-1 rounded-lg bg-slate-950/90 hover:bg-cyan-500/25 text-[10px] font-mono-tech font-bold text-cyan-200 border border-white/15 hover:border-cyan-400/50 shadow" title="Open 3D Jacket, Gatefold &amp; Gallery Inspector">
                  🔍 3D Jacket
                </button>
              </div>
            </div>
            <div class="p-3.5 space-y-2">
              <div class="flex items-center justify-between gap-1 flex-wrap">
                <span class="px-2 py-0.5 rounded-md text-[10px] font-mono-tech font-medium bg-white/5 text-purple-300 border border-white/10 truncate max-w-[70%]">
                  ${escapeHtml(waxBadge)}
                </span>
                <span class="text-xs font-mono-tech font-black text-emerald-400">${priceStr}</span>
              </div>
              <div>
                <h3 class="text-sm font-extrabold text-white group-hover:text-cyan-300 transition line-clamp-1">${escapeHtml(rec.title)}</h3>
                <p class="text-xs font-semibold text-slate-400 line-clamp-1">${escapeHtml(rec.artist)} • <span class="text-slate-500">${escapeHtml(rec.year || 'LP')}</span></p>
              </div>
              <div class="text-[11px] font-mono-tech text-slate-400 flex items-center justify-between pt-1 border-t border-white/5">
                <span class="truncate max-w-[68%]">${escapeHtml(rec.label || '')} (${escapeHtml(rec.catno || 'none')})</span>
                <span>${escapeHtml((rec.media_condition || 'NM').split('(')[0].trim())}</span>
              </div>
            </div>
          </div>
          <div class="px-3.5 pb-3 flex items-center justify-between gap-2">
            <div class="flex items-center gap-1.5">
              <span class="text-[10px] font-mono-tech text-slate-500">#${escapeHtml(rec.release_id)}</span>
              ${eloPill}
            </div>
            <a
              href="${safeDiscogsHref}"
              target="_blank"
              rel="noopener noreferrer"
              data-stop-prop="true"
              class="text-[11px] font-mono-tech font-semibold text-cyan-400 hover:text-cyan-300 underline"
            >
              Discogs ↗
            </a>
          </div>
        </article>
      `;
    })
    .join('');
}

// =========================================================================
// 3D Record Store Bin Flipper
// =========================================================================
export function render3DCrateBinFlipper() {
  const trough = document.getElementById('bin-3d-trough');
  const infoEl = document.getElementById('bin-3d-active-info');
  const sliderEl = document.getElementById('bin-3d-scrubber');
  const azBar = document.getElementById('bin-3d-az-tabs');
  if (!trough) return;

  const list = store.filteredRecords;
  if (!list.length) {
    trough.innerHTML = '<div class="text-xs text-slate-400">No records match the current filter.</div>';
    if (infoEl) infoEl.innerHTML = '';
    return;
  }

  if (binActiveIdx >= list.length) binActiveIdx = list.length - 1;
  if (binActiveIdx < 0) binActiveIdx = 0;

  if (sliderEl) {
    sliderEl.max = String(Math.max(0, list.length - 1));
    sliderEl.value = String(binActiveIdx);
  }

  // Render A-Z jump tabs for artists in list
  if (azBar) {
    const letters = [];
    const seen = new Set();
    list.forEach((r, i) => {
      const ch = (r.artist || '#').trim().charAt(0).toUpperCase();
      const key = /[A-Z]/.test(ch) ? ch : '#';
      if (!seen.has(key)) {
        seen.add(key);
        letters.push({ key, idx: i });
      }
    });
    letters.sort((a, b) => a.key.localeCompare(b.key));
    const curCh = (list[binActiveIdx].artist || '#').trim().charAt(0).toUpperCase();
    azBar.innerHTML = letters
      .map(
        ({ key, idx }) => `
        <button type="button" data-bin-jump="${idx}" class="px-2 py-0.5 rounded-md text-[10px] font-mono-tech font-bold transition ${
          key === curCh ? 'bg-cyan-500 text-slate-950' : 'bg-slate-900 text-slate-400 hover:text-white border border-white/10'
        }">${escapeHtml(key)}</button>
      `
      )
      .join('');
  }

  // Render visible window of [-3 .. +8] sleeves in 3D space
  const start = Math.max(0, binActiveIdx - 2);
  const end = Math.min(list.length - 1, binActiveIdx + 8);
  let sleevesHtml = '';

  for (let i = end; i >= start; i--) {
    const rec = list[i];
    const rel = i - binActiveIdx; // <0 flipped forward past viewer, 0 active front, >0 stacked back
    let transform;
    let opacity = 1;
    let zIndex = 40 - Math.abs(rel);
    let filter = 'brightness(1)';

    if (rel < 0) {
      // Tipped forward into foreground trough
      transform = `translate3d(0, ${135 + Math.abs(rel) * 16}px, ${140 + Math.abs(rel) * 30}px) rotateX(-68deg) scale(0.95)`;
      opacity = Math.max(0, 0.55 - Math.abs(rel) * 0.25);
      zIndex = 60 + Math.abs(rel);
      filter = 'brightness(0.6)';
    } else if (rel === 0) {
      transform = `translate3d(0, 12px, 0px) rotateX(-6deg) scale(1.03)`;
      zIndex = 50;
    } else {
      const zStep = -rel * 44;
      const yStep = -rel * 16;
      const sc = Math.max(0.75, 1 - rel * 0.025);
      transform = `translate3d(0, ${yStep}px, ${zStep}px) rotateX(-12deg) scale(${sc})`;
      opacity = Math.max(0.22, 1 - rel * 0.09);
      filter = `brightness(${Math.max(0.45, 1 - rel * 0.08)})`;
    }

    sleevesHtml += `
      <div
        class="bin-3d-sleeve ${rel === 0 ? 'is-front' : ''}"
        data-bin-idx="${i}"
        style="transform: ${transform}; opacity: ${opacity}; z-index: ${zIndex}; filter: ${filter};"
      >
        ${
          rel === 0
            ? `<div class="bin-3d-wax-peek uv-reactive">${renderCrateWaxDiscHTML(rec, 180, true, store.userOverrides)}</div>`
            : ''
        }
        <div class="w-full h-full rounded-2xl overflow-hidden border-2 ${
          rel === 0 ? 'border-cyan-400 shadow-[0_20px_50px_rgba(6,182,212,0.35)]' : 'border-white/20 shadow-2xl'
        } bg-slate-950">
          ${renderJacketSleeveHTML(rec)}
        </div>
      </div>
    `;
  }
  trough.innerHTML = sleevesHtml;

  const active = list[binActiveIdx];
  if (infoEl && active) {
    infoEl.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="text-[11px] font-mono-tech text-cyan-300 font-bold uppercase">${binActiveIdx + 1} / ${list.length} • ${escapeHtml(active.wax_spec?.variant_badge || '12" LP')}</div>
          <h4 class="text-base sm:text-lg font-black text-white truncate">${escapeHtml(active.artist)} — ${escapeHtml(active.title)}</h4>
          <div class="text-xs font-mono-tech text-slate-400">${escapeHtml(active.label)} (${escapeHtml(active.catno || 'none')}) • <span class="text-emerald-400 font-bold">${formatUsdValue(active)}</span></div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <button type="button" data-bin-inspect="${active.release_id}" class="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-200 border border-white/15">🔍 3D Jacket</button>
          <button type="button" data-bin-spin="${active.release_id}" class="px-4 py-2 rounded-xl bg-gradient-to-r from-fuchsia-600 to-cyan-500 hover:from-fuchsia-500 hover:to-cyan-400 text-white text-xs font-black shadow-lg">💿 Pull to Platter</button>
        </div>
      </div>
    `;
  }
}

export function setThumbMode(mode, persist = true) {
  store.thumbMode = mode;
  const modes = [
    ['pressing', 'mode-btn-pressing'],
    ['split', 'mode-btn-split'],
    ['sleeve', 'mode-btn-sleeve'],
    ['bin3d', 'mode-btn-bin3d'],
  ];
  for (const [m, id] of modes) {
    const el = document.getElementById(id);
    if (!el) continue;
    const isAct = m === mode;
    el.setAttribute('aria-pressed', isAct ? 'true' : 'false');
    el.className = isAct
      ? 'px-2.5 py-1 rounded-lg font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 whitespace-nowrap'
      : 'px-2.5 py-1 rounded-lg font-semibold text-slate-400 hover:text-white whitespace-nowrap';
  }
  const mob = document.getElementById('mobile-mode-select');
  if (mob) mob.value = mode;
  if (mode === 'bin3d') binActiveIdx = store.activeIndex;
  if (persist) saveUiPrefs();
  syncUrlFromState();
  renderCrateGrid();
}

export function initCrateViews() {
  // Default strictly to 'split' (or restored pref / URL ?crate=...)
  setThumbMode(store.thumbMode || 'split', false);

  document.getElementById('mode-btn-pressing')?.addEventListener('click', () => setThumbMode('pressing'));
  document.getElementById('mode-btn-split')?.addEventListener('click', () => setThumbMode('split'));
  document.getElementById('mode-btn-sleeve')?.addEventListener('click', () => setThumbMode('sleeve'));
  document.getElementById('mode-btn-bin3d')?.addEventListener('click', () => setThumbMode('bin3d'));
  document.getElementById('mobile-mode-select')?.addEventListener('change', (e) => setThumbMode(e.target.value));

  const searchInput = document.getElementById('search-input');
  const clearBtn = document.getElementById('btn-clear-search');
  searchInput?.addEventListener('input', (e) => {
    store.searchQuery = e.target.value;
    clearBtn?.classList.toggle('hidden', !store.searchQuery);
    applyFiltersAndSort();
  });
  clearBtn?.addEventListener('click', () => {
    if (searchInput) searchInput.value = '';
    store.searchQuery = '';
    clearBtn.classList.add('hidden');
    applyFiltersAndSort();
  });

  document.getElementById('sort-select')?.addEventListener('change', (e) => {
    store.sortBy = e.target.value;
    applyFiltersAndSort();
  });

  document.getElementById('filter-chips-bar')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-filter]');
    if (!btn) return;
    store.filter = btn.getAttribute('data-filter') || 'all';
    document.querySelectorAll('.filter-chip').forEach((chip) => {
      const act = chip.getAttribute('data-filter') === store.filter;
      chip.className = act
        ? 'filter-chip shrink-0 px-3 py-1 rounded-full text-xs font-bold bg-gradient-to-r from-fuchsia-600 to-cyan-600 text-white shadow'
        : 'filter-chip shrink-0 px-3 py-1 rounded-full text-xs font-bold bg-slate-950/80 text-slate-300 hover:text-white border border-white/10';
    });
    applyFiltersAndSort();
  });

  document.getElementById('crate-subfilter-banner')?.addEventListener('click', (e) => {
    if (e.target.closest('#btn-clear-subfilters')) {
      clearAllCrateFilters(true);
    }
  });

  document.getElementById('collection-grid')?.addEventListener('click', (e) => {
    const viewStageBtn = e.target.closest('[data-card-view-stage]');
    if (viewStageBtn) {
      e.stopPropagation();
      setActiveIndex(Number(viewStageBtn.getAttribute('data-card-view-stage') || 0));
      playCrateTickSound(1.1);
      emit('expandStageRequested');
      return;
    }
    const inspectBtn = e.target.closest('[data-card-inspect]');
    if (inspectBtn) {
      e.stopPropagation();
      const rid = Number(inspectBtn.getAttribute('data-card-inspect'));
      const rec = store.records.find((r) => Number(r.release_id) === rid);
      if (rec) window.dispatchEvent(new CustomEvent('vault:openInspector', { detail: { record: rec, xRay: false } }));
      return;
    }
    if (e.target.closest('[data-stop-prop]')) return;
    const card = e.target.closest('[data-card-index]');
    if (!card) return;
    setActiveIndex(Number(card.getAttribute('data-card-index') || 0));
    playCrateTickSound(1.05);
    emit('crateCardSelected');
  });

  // 3D Crate Bin interactions
  const binViewport = document.getElementById('crate-bin-3d-viewport');
  const stepBin = (delta) => {
    if (!store.filteredRecords.length) return;
    const next = Math.max(0, Math.min(store.filteredRecords.length - 1, binActiveIdx + delta));
    if (next !== binActiveIdx) {
      binActiveIdx = next;
      playCrateTickSound(delta > 0 ? 1.12 : 0.9);
      render3DCrateBinFlipper();
    }
  };

  binViewport?.addEventListener('wheel', (e) => {
    if (store.thumbMode !== 'bin3d') return;
    e.preventDefault();
    const now = performance.now();
    if (now - lastWheelTs < 65) return;
    lastWheelTs = now;
    stepBin(e.deltaY > 0 ? 1 : -1);
  }, { passive: false });

  binViewport?.addEventListener('pointerdown', (e) => {
    if (e.target.closest('button')) return;
    binDragging = true;
    binDragStartX = e.clientY;
  });
  binViewport?.addEventListener('pointermove', (e) => {
    if (!binDragging) return;
    const dy = e.clientY - binDragStartX;
    if (Math.abs(dy) > 38) {
      stepBin(dy > 0 ? -1 : 1);
      binDragStartX = e.clientY;
    }
  });
  window.addEventListener('pointerup', () => {
    binDragging = false;
  });

  document.getElementById('crate-bin-3d-wrap')?.addEventListener('click', (e) => {
    const jump = e.target.closest('[data-bin-jump]');
    if (jump) {
      binActiveIdx = Number(jump.getAttribute('data-bin-jump') || 0);
      playCrateTickSound(1.05);
      render3DCrateBinFlipper();
      return;
    }
    const sleeve = e.target.closest('[data-bin-idx]');
    if (sleeve) {
      const idx = Number(sleeve.getAttribute('data-bin-idx') || 0);
      if (idx === binActiveIdx) {
        const rec = store.filteredRecords[idx];
        if (rec) setActiveRecordById(rec.release_id);
        emit('expandStageRequested');
      } else {
        binActiveIdx = idx;
        playCrateTickSound(1.0);
        render3DCrateBinFlipper();
      }
      return;
    }
    const spinBtn = e.target.closest('[data-bin-spin]');
    if (spinBtn) {
      setActiveRecordById(Number(spinBtn.getAttribute('data-bin-spin')));
      emit('expandStageRequested');
      return;
    }
    const inspBtn = e.target.closest('[data-bin-inspect]');
    if (inspBtn) {
      const rid = Number(inspBtn.getAttribute('data-bin-inspect'));
      const rec = store.records.find((r) => Number(r.release_id) === rid);
      if (rec) window.dispatchEvent(new CustomEvent('vault:openInspector', { detail: { record: rec, xRay: false } }));
    }
  });

  document.getElementById('bin-3d-prev')?.addEventListener('click', () => stepBin(-1));
  document.getElementById('bin-3d-next')?.addEventListener('click', () => stepBin(1));
  document.getElementById('bin-3d-scrubber')?.addEventListener('input', (e) => {
    binActiveIdx = Number(e.target.value || 0);
    render3DCrateBinFlipper();
  });

function syncSelectedCrateCard() {
  const grid = document.getElementById('collection-grid');
  if (!grid || store.thumbMode === 'bin3d') return;
  const activeIdx = String(store.activeIndex);
  grid.querySelectorAll('.card-record').forEach((card) => {
    const isSel = card.getAttribute('data-card-index') === activeIdx;
    card.classList.toggle('border-cyan-400', isSel);
    card.classList.toggle('ring-2', isSel);
    card.classList.toggle('ring-cyan-400/30', isSel);
    card.classList.toggle('border-white/10', !isSel);
    card.classList.toggle('hover:border-cyan-500/45', !isSel);
    const badge = card.querySelector('[data-spinning-badge]');
    if (badge) {
      badge.classList.toggle('flex', isSel);
      badge.classList.toggle('hidden', !isSel);
    }
  });
}

  subscribe((topic) => {
    if (topic === 'recordsChanged' || topic === 'eloUpdated') {
      renderCrateGrid();
    } else if (topic === 'activeRecordChanged') {
      if (store.thumbMode === 'bin3d') renderCrateGrid();
      else syncSelectedCrateCard();
    }
  });

  renderCrateGrid();
}
