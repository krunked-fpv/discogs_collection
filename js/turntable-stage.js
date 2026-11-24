// KRUNKED // VINYL VAULT v6.0 — WebGL2 Direct-Drive Turntable Stage, Tonearm Physics & Scroll-Collapse Mini-Bar

import {
  playAlbumTrackAtIndex,
  playCrateTickSound,
  playNeedleDropSound,
  playRouletteWinChord,
  playUvToggleSound,
  renderStreamingDeck,
  resolveAlbumStreamingData,
  setPlatterVelocityRatio,
  stopPreviewAudio,
  getVuLevels,
} from './audio-preview.js';
import {
  clearReleasePressingOverride,
  emit,
  getActiveRecord,
  pinReleasePressingOverride,
  saveUiPrefs,
  setActiveIndex,
  setRecordFlatteningStatus,
  store,
  subscribe,
  syncUrlFromState,
} from './store.js';
import {
  DEFAULT_FLATTENING_STATUS,
  buildImgOnErrorAttr,
  escapeHtml,
  formatUsdValue,
  getGalleryImages,
  getPressingPhotoUrls,
  getVerifiedPressingPhotoUrl,
  renderCrateWaxDiscHTML,
  renderJacketSleeveHTML,
  safeCssColor,
  safeImageSrc,
  showToast,
  spawnParticles,
} from './utils.js';
import { WebGLWaxDiscRenderer } from './wax-shaders.js';

const OMEGA_33 = (33.3333 / 60) * Math.PI * 2;
const OMEGA_45 = (45.0 / 60) * Math.PI * 2;

let heroRenderer = null;
let rafId = null;
let lastFrameTime = performance.now();

// Viewport visibility, scroll-collapse mini-bar & GPU rAF pause state
let isHeroInViewport = true;
let scrolledPastHero = false;
let currentHeaderHeight = 58;
let sentinelObserver = null;
let heroVisObserver = null;
let lastMiniBarThumbKey = '';
let spectrumClearedIdle = false;

// Real-time platter kinematics
let platterAngle = 0;
let strobeAngle = 0;
let currentOmega = OMEGA_33;
let isScrubbingPlatter = false;
let scrubMoved = false;
let scrubLastAngle = 0;
let scrubLastTime = 0;
let scrubOmega = 0;

// Tonearm kinematics
let tonearmAngleDeg = 18;
let isDraggingArm = false;

export function getHeroWebGLRenderer() {
  return heroRenderer;
}

export function getSmartSpinPool() {
  const base = store.records.length ? store.records : [];
  if (store.spinMode === 'eyecandy') {
    const res = base.filter((r) => ['splatter', 'galaxy', 'marble', 'split', 'color_in_color'].includes(r.wax_spec?.pattern || ''));
    return res.length ? res : base;
  }
  if (store.spinMode === 'splatter') {
    const res = base.filter((r) => ['splatter', 'color_in_color'].includes(r.wax_spec?.pattern || ''));
    return res.length ? res : base;
  }
  if (store.spinMode === 'translucent') {
    const res = base.filter((r) => Boolean(r.wax_spec?.translucent));
    return res.length ? res : base;
  }
  if (store.spinMode === 'double_lp') {
    const res = base.filter((r) => Boolean(r.wax_spec?.is_double_lp));
    return res.length ? res : base;
  }
  if (store.spinMode === 'etched') {
    const res = base.filter((r) => Boolean(r.wax_spec?.etched));
    return res.length ? res : base;
  }
  if (store.spinMode === 'todo') {
    const res = base.filter((r) => (r.flattening_status || DEFAULT_FLATTENING_STATUS) === 'Need to be done');
    return res.length ? res : base;
  }
  return base;
}

export function updateSmartSpinModeBadges() {
  const base = store.records.length ? store.records : [];
  const eyeCandyCount = base.filter((r) => ['splatter', 'galaxy', 'marble', 'split', 'color_in_color'].includes(r.wax_spec?.pattern || '')).length;

  const badgeAll = document.getElementById('spin-badge-all');
  if (badgeAll) badgeAll.textContent = `ALL LPS (${base.length})`;
  const badgeEye = document.getElementById('spin-badge-eyecandy');
  if (badgeEye) badgeEye.textContent = `FLEX WAX (${eyeCandyCount})`;
  const badgeShow = document.getElementById('spin-badge-showroom');
  if (badgeShow) badgeShow.textContent = store.showroomTickInterval ? `AUTO ${store.showroomCountdown}s` : 'AUTO 15s';

  const modePill = document.getElementById('active-spin-mode-pill');
  if (modePill) {
    if (store.spinMode === 'showroom') {
      modePill.textContent = `📺 Showroom Kiosk Active • Auto-Cycle (${store.showroomCountdown}s)`;
      modePill.className = 'hidden xl:inline-flex text-[10px] font-mono-tech uppercase px-2 py-0.5 rounded-full bg-purple-500/25 text-purple-200 border border-purple-400/50 font-bold animate-pulse';
    } else if (store.spinMode === 'eyecandy') {
      modePill.textContent = `🌈 Eye-Candy Variants • ${eyeCandyCount} Flex Wax LPs`;
      modePill.className = 'hidden xl:inline-flex text-[10px] font-mono-tech uppercase px-2 py-0.5 rounded-full bg-fuchsia-500/20 text-fuchsia-300 border border-fuchsia-400/35 font-bold';
    } else if (store.spinMode !== 'all') {
      const pool = getSmartSpinPool();
      const labelMap = {
        splatter: '🎨 Splatter Sommelier',
        translucent: '💎 Translucent Sommelier',
        double_lp: '💿 2xLP Sommelier',
        etched: '✨ Etched Sommelier',
        todo: '🔥 Flattening Queue Sommelier',
      };
      modePill.textContent = `${labelMap[store.spinMode] || store.spinMode} • ${pool.length} LPs`;
      modePill.className = 'hidden xl:inline-flex text-[10px] font-mono-tech uppercase px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-200 border border-amber-400/40 font-bold';
    } else {
      modePill.textContent = `🎲 Full Vault Roulette • ${base.length} LPs`;
      modePill.className = 'hidden xl:inline-flex text-[10px] font-mono-tech uppercase px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/35 font-bold';
    }
  }
}

function populateCrateWingCard(prefix, rec) {
  if (!rec) return;
  const wax = rec.wax_spec || {};
  const c1 = safeCssColor(wax.primary_color, '#8b2cf5');
  const c2 = safeCssColor(wax.secondary_color, '#06b6d4');

  const orbEl = document.getElementById(`${prefix}-orb`);
  if (orbEl) orbEl.style.background = `radial-gradient(circle, ${c2}, ${c1})`;

  const pillEl = document.getElementById(`${prefix}-pill`);
  if (pillEl) {
    const wingFlat = rec.flattening_status || DEFAULT_FLATTENING_STATUS;
    if (wingFlat === 'Done') {
      pillEl.textContent = 'Flat ✓';
      pillEl.className = 'px-1.5 py-0.5 rounded bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-[9px] font-mono-tech font-bold';
    } else if (wingFlat === 'Need to be done') {
      pillEl.textContent = 'Queue 🔥';
      pillEl.className = 'px-1.5 py-0.5 rounded bg-amber-500/25 text-amber-200 border border-amber-500/40 text-[9px] font-mono-tech font-bold';
    } else {
      pillEl.textContent = String(rec.year || 'LP');
      pillEl.className = 'px-1.5 py-0.5 rounded bg-white/10 text-slate-300 text-[9px] font-mono-tech font-bold';
    }
  }

  const artEl = document.getElementById(`${prefix}-artist`);
  if (artEl) artEl.textContent = (rec.artist || 'ARTIST').toUpperCase();
  const titEl = document.getElementById(`${prefix}-title`);
  if (titEl) titEl.textContent = rec.title || 'Album';
  const bdgEl = document.getElementById(`${prefix}-badge`);
  if (bdgEl) bdgEl.textContent = wax.variant_badge || '12" LP';
}

export function renderHeroGalleryStrip(rec) {
  const stripEl = document.getElementById('hero-gallery-strip');
  const expEl = document.getElementById('hero-cv-explanation');
  if (!stripEl || !expEl || !rec) return;

  const rid = String(rec.release_id);
  const classified = getGalleryImages(rec);
  const { primary: activePrimary, fallback: activeFallback } = getPressingPhotoUrls(rec, store.userOverrides);
  const activePressingUrl = activePrimary || activeFallback;

  if (!classified.length) {
    stripEl.innerHTML = `<span class="text-[11px] text-slate-400">Click <strong>↻ Refresh Gallery</strong> to load Discogs release photos.</span>`;
    expEl.textContent = `Format parsed: ${(rec.wax_spec && rec.wax_spec.variant_badge) || '12" LP'}`;
    return;
  }

  const selIdx = rec.images && typeof rec.images.selected_index === 'number' ? rec.images.selected_index : -1;

  stripEl.innerHTML =
    classified
      .map((img, i) => {
        const thumbSrc = safeImageSrc(img.local_uri) || safeImageSrc(img.uri150) || safeImageSrc(img.remote_uri);
        const pinTarget = safeImageSrc(img.local_uri) || safeImageSrc(img.remote_uri);
        const isPinned = Boolean(
          activePressingUrl &&
            (activePressingUrl === img.remote_uri ||
              activePressingUrl === img.local_uri ||
              (!store.userOverrides[rid] && i === selIdx && rec.images && rec.images.has_pressing_photo))
        );
        const roleLabel = i === 0 ? 'Cover [0]' : (isPinned || img.role === 'pressing_disc' ? `Pressing [${i}]` : `Img [${i}]`);
        const fbSrc = safeImageSrc(img.uri150 || img.remote_uri);
        const onErrAttr = img.local_uri && fbSrc ? buildImgOnErrorAttr(fbSrc) : '';
        return `
          <button
            type="button"
            data-pin-image-url="${escapeHtml(pinTarget)}"
            data-pin-image-index="${i}"
            data-pin-release-id="${escapeHtml(rec.release_id)}"
            class="shrink-0 group relative rounded-lg overflow-hidden border-2 ${
              isPinned ? 'border-emerald-400 ring-2 ring-emerald-400/30' : 'border-white/15 hover:border-cyan-400'
            } transition"
            title="Click to pin image [${i}] as the vinyl pressing photo for ${escapeHtml(rec.title)}"
          >
            <img src="${escapeHtml(thumbSrc)}" ${onErrAttr} referrerpolicy="no-referrer" alt="${escapeHtml(roleLabel)}" class="w-12 h-12 sm:w-[52px] sm:h-[52px] object-cover bg-slate-900" />
            <span class="absolute bottom-0 inset-x-0 bg-black/80 text-[8px] font-mono-tech text-center py-0.5 ${
              isPinned ? 'text-emerald-300 font-bold' : 'text-slate-300'
            }">
              ${isPinned ? `✓ Photo [${i}]` : roleLabel}
            </span>
          </button>
        `;
      })
      .join('') +
    (activePressingUrl
      ? `<button type="button" data-clear-pin="${escapeHtml(rec.release_id)}" class="shrink-0 whitespace-nowrap px-2 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-[10px] font-mono-tech text-slate-300 border border-white/10" title="Switch to procedural WebGL wax shader">
          Shader
        </button>`
      : '');

  const badgeText = escapeHtml((rec.wax_spec && rec.wax_spec.variant_badge) || '12" LP');
  expEl.innerHTML = activePressingUrl
    ? `Defaulted wax ring to verified pressing photo for <strong>#${escapeHtml(rec.release_id)}</strong> (${classified.length} images in gallery — click to pin or open 3D Inspector).`
    : `No separate vinyl disc photo uploaded on Discogs for <strong>#${escapeHtml(rec.release_id)}</strong> (${classified.length} sleeve image${classified.length === 1 ? '' : 's'}) — rendering live WebGL2 <strong>${badgeText}</strong> wax physics.`;
}

function updateOpticsVisuals(rec) {
  if (!rec) return;
  const wax = rec.wax_spec || {};
  const halo = document.getElementById('platter-backlight-halo');
  if (halo) {
    if (store.backlightOn || store.uvBlacklight) {
      const c1 = safeCssColor(wax.primary_color, '#8b2cf5');
      const c2 = safeCssColor(wax.secondary_color, '#06b6d4');
      const alpha = store.backlightOn ? Math.max(0.35, store.backlightIntensity * (wax.translucent ? 0.95 : 0.42)) : 0.32;
      const bgCol = store.uvBlacklight ? `radial-gradient(circle, rgba(168,85,247,0.72), ${c1} 45%, ${c2} 72%, transparent 76%)` : `radial-gradient(circle, rgba(255,242,204,0.85), ${c1} 52%, transparent 76%)`;
      halo.style.background = bgCol;
      halo.style.opacity = String(alpha);
    } else {
      halo.style.opacity = '0';
    }
  }
  if (heroRenderer) {
    heroRenderer.setOptics({
      backlight: store.backlightOn ? store.backlightIntensity : 0.0,
      uvMode: store.uvBlacklight,
      etchedOverride: store.etchedPreviewOverride,
      blindMode: false,
    });
  }
}

export function renderHeroStage() {
  const list = store.filteredRecords.length ? store.filteredRecords : store.records;
  if (!list.length) return;
  const rec = getActiveRecord();
  if (!rec) return;

  const prevRec = list[(store.activeIndex - 1 + list.length) % list.length];
  const nextRec = list[(store.activeIndex + 1) % list.length];

  const wax = rec.wax_spec || {};
  const c1 = safeCssColor(wax.primary_color, '#8b2cf5');
  const c2 = safeCssColor(wax.secondary_color, '#06b6d4');
  const c3 = safeCssColor(wax.accent_color, '#f43f5e');
  document.documentElement.style.setProperty('--glow-primary', `${c1}44`);
  document.documentElement.style.setProperty('--glow-secondary', `${c2}40`);
  document.documentElement.style.setProperty('--glow-accent', `${c3}33`);

  const counterEl = document.getElementById('carousel-counter');
  if (counterEl) counterEl.textContent = `${store.activeIndex + 1} / ${list.length}`;

  if (heroRenderer) {
    heroRenderer.setRecord(rec, store.userOverrides, {
      forceSleeveArt: store.stageMode === 'sleeve',
      etchedOverride: store.etchedPreviewOverride,
    });
    updateOpticsVisuals(rec);
  }

  populateCrateWingCard('stage-prev', prevRec);
  populateCrateWingCard('stage-next', nextRec);

  const vBadge = document.getElementById('hero-variant-badge');
  if (vBadge) vBadge.textContent = wax.variant_badge || '12" LP';

  const verifiedUrl = getVerifiedPressingPhotoUrl(rec, store.userOverrides);
  const pillEl = document.getElementById('hero-detection-pill');
  if (pillEl) {
    if (verifiedUrl) {
      pillEl.textContent = '✓ Real Pressing Photo Active';
      pillEl.className = 'px-2.5 py-0.5 rounded-full text-[11px] font-mono-tech font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30';
    } else {
      pillEl.textContent = 'Sleeve-Only on Discogs • WebGL2 Wax';
      pillEl.className = 'px-2.5 py-0.5 rounded-full text-[11px] font-mono-tech font-bold bg-slate-800 text-slate-300 border border-white/10';
    }
  }

  const setText = (id, txt) => {
    const el = document.getElementById(id);
    if (el) el.textContent = txt;
  };
  setText('hero-title', rec.title);
  setText('hero-artist', `${rec.artist} (${rec.year || 'LP'})`);
  setText('hero-price', formatUsdValue(rec));
  setText('hero-label-cat', `${rec.label} • ${rec.catno}`);
  setText('hero-format', rec.format_string);

  const mShort = (rec.media_condition || 'NM').split('(')[0].trim();
  const sShort = (rec.sleeve_condition || 'NM').split('(')[0].trim();
  setText('hero-grading', `Media: ${mShort} / Sleeve: ${sShort}`);

  const flatStatus = rec.flattening_status || DEFAULT_FLATTENING_STATUS;
  const flatBadge = flatStatus === 'Need to be done' ? ' • 🔥 Queue' : (flatStatus === 'Done' ? ' • ✓ Flat / Done' : ' • Unlisted');
  setText('hero-flattening', `#${rec.release_id}${flatBadge}`);

  const cycleBtn = document.getElementById('btn-hero-flatten-cycle');
  if (cycleBtn) {
    if (flatStatus === 'Need to be done') {
      cycleBtn.textContent = '✓ Flat / Done';
      cycleBtn.className = 'shrink-0 px-2 py-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-[10px] font-mono-tech font-bold text-emerald-300 border border-emerald-500/30 transition';
    } else if (flatStatus === 'Done') {
      cycleBtn.textContent = '🔥 Re-Queue';
      cycleBtn.className = 'shrink-0 px-2 py-0.5 rounded bg-amber-500/15 hover:bg-amber-500/25 text-[10px] font-mono-tech font-bold text-amber-300 border border-amber-500/30 transition';
    } else {
      cycleBtn.textContent = '+ 🔥 Queue';
      cycleBtn.className = 'shrink-0 px-2 py-0.5 rounded bg-amber-500/15 hover:bg-amber-500/25 text-[10px] font-mono-tech font-bold text-amber-300 border border-amber-500/30 transition';
    }
  }

  const dcLink = document.getElementById('hero-discogs-link');
  if (dcLink) dcLink.href = rec.discogs_url || `https://www.discogs.com/release/${rec.release_id}`;

  const syncLogEl = document.getElementById('sync-log-output');
  if (syncLogEl) {
    syncLogEl.textContent = `# Daily Incremental Delta Sync (Fast-Paths Unchanged LPs):\ncd C:\\DiscogsCollection\\discogs_collection\npython scripts/sync_discogs.py\n\n# Force Resync Active Turntable Record (#${rec.release_id} — ${rec.artist}):\npython scripts/sync_discogs.py --resync ${rec.release_id}`;
  }

  updateSmartSpinModeBadges();
  renderMiniBar(rec, false);

  if (!store.isSpinningRoulette) {
    renderHeroGalleryStrip(rec);
    renderStreamingDeck(rec);
  }
}

// =========================================================================
// Sticky "Now Spinning" Mini-Bar & Manual Stage Collapse
// =========================================================================
function isMiniBarVisible() {
  return store.activeTab === 'showcase' && (store.stageCollapsed || scrolledPastHero);
}

export function renderMiniBar(rec, shouldPulse = false) {
  if (!rec) return;
  const bar = document.getElementById('now-spinning-minibar');
  if (!bar) return;

  const titleEl = document.getElementById('minibar-artist-title');
  if (titleEl) titleEl.textContent = `${rec.artist} — ${rec.title}`;

  const badgeEl = document.getElementById('minibar-variant-badge');
  if (badgeEl) badgeEl.textContent = rec.wax_spec?.variant_badge || '12" LP';

  const subEl = document.getElementById('minibar-meta-sub');
  if (subEl) {
    const yr = rec.year || 'LP';
    const lbl = rec.label || 'Vinyl';
    subEl.textContent = `${yr} • ${lbl} • ${formatUsdValue(rec)}`;
  }

  const pressUrl = getVerifiedPressingPhotoUrl(rec, store.userOverrides);
  const thumbKey = `${rec.release_id}:${pressUrl}`;
  if (lastMiniBarThumbKey !== thumbKey) {
    lastMiniBarThumbKey = thumbKey;
    const sleeveEl = document.getElementById('minibar-thumb-sleeve');
    if (sleeveEl) sleeveEl.innerHTML = renderJacketSleeveHTML(rec);
    const discEl = document.getElementById('minibar-thumb-disc');
    if (discEl) discEl.innerHTML = renderCrateWaxDiscHTML(rec, 40, true, store.userOverrides);
  }

  const discEl = document.getElementById('minibar-thumb-disc');
  if (discEl) {
    const spinActive = store.isSpinning && isMiniBarVisible();
    discEl.classList.toggle('spin-paused', !spinActive);
  }

  if (shouldPulse && isMiniBarVisible()) {
    bar.classList.remove('minibar-pulse');
    void bar.offsetWidth;
    bar.classList.add('minibar-pulse');
  }
}

export function syncMiniBarVisibility() {
  const bar = document.getElementById('now-spinning-minibar');
  if (!bar) return;
  const show = isMiniBarVisible();
  bar.classList.toggle('is-visible', show);
  bar.setAttribute('aria-hidden', show ? 'false' : 'true');

  const discEl = document.getElementById('minibar-thumb-disc');
  if (discEl) {
    discEl.classList.toggle('spin-paused', !(store.isSpinning && show));
  }
}

export function setStageCollapsed(collapsed) {
  store.stageCollapsed = Boolean(collapsed);
  const heroEl = document.getElementById('hero-turntable-stage');
  const spacerEl = document.getElementById('minibar-collapsed-spacer');
  if (heroEl) heroEl.classList.toggle('hidden', store.stageCollapsed);
  if (spacerEl) spacerEl.classList.toggle('hidden', !store.stageCollapsed);
  if (!store.stageCollapsed && window.scrollY < 320) {
    isHeroInViewport = true;
    scrolledPastHero = false;
  }
  syncMiniBarVisibility();
  syncStageLoopState();
}

export function expandHeroStage() {
  if (store.stageCollapsed) {
    setStageCollapsed(false);
  }
  if (store.activeTab !== 'showcase' && typeof window.__setMainVaultTab === 'function') {
    window.__setMainVaultTab('showcase');
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
  syncStageLoopState();
}

function setupScrollCollapseObservers() {
  const headerEl = document.getElementById('vault-header');
  const sentinelEl = document.getElementById('hero-stage-sentinel');
  const heroEl = document.getElementById('hero-turntable-stage');

  const evaluateSentinelBounds = (offset) => {
    const targetEl = sentinelEl || heroEl;
    if (!targetEl || store.stageCollapsed) return;
    const rect = targetEl.getBoundingClientRect();
    const nextPast = rect.bottom <= offset + 2;
    if (nextPast !== scrolledPastHero) {
      scrolledPastHero = nextPast;
      syncMiniBarVisibility();
    }
  };

  const rebuildSentinelObserver = (headerH) => {
    if (typeof IntersectionObserver === 'undefined') return;
    if (sentinelObserver) sentinelObserver.disconnect();
    const offset = Math.max(40, Math.round(headerH));
    // Observe BOTH the hero stage (immune to instant fast-scroll teleports on tall mobile layouts)
    // and the bottom sentinel (exact pixel boundary under sticky header)
    sentinelObserver = new IntersectionObserver(
      () => {
        evaluateSentinelBounds(offset);
      },
      {
        root: null,
        rootMargin: `-${offset}px 0px 0px 0px`,
        threshold: 0,
      }
    );
    if (heroEl) sentinelObserver.observe(heroEl);
    if (sentinelEl) sentinelObserver.observe(sentinelEl);
    evaluateSentinelBounds(offset);
  };

  if (headerEl) {
    const syncHeaderMetrics = () => {
      const h = Math.max(48, Math.round(headerEl.getBoundingClientRect().height || 58));
      if (h !== currentHeaderHeight || !sentinelObserver) {
        currentHeaderHeight = h;
        document.documentElement.style.setProperty('--vault-header-h', `${h}px`);
        rebuildSentinelObserver(h);
      }
    };
    syncHeaderMetrics();
    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(syncHeaderMetrics);
      ro.observe(headerEl);
    } else {
      window.addEventListener('resize', syncHeaderMetrics, { passive: true });
    }
  } else {
    rebuildSentinelObserver(currentHeaderHeight);
  }

  // Pause heavy WebGL2 platter rendering whenever hero stage is completely scrolled out of view
  if (heroEl && typeof IntersectionObserver !== 'undefined') {
    if (heroVisObserver) heroVisObserver.disconnect();
    heroVisObserver = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry) return;
        const nextVis = entry.isIntersecting;
        if (nextVis !== isHeroInViewport) {
          isHeroInViewport = nextVis;
          syncStageLoopState();
        }
      },
      {
        root: null,
        rootMargin: '80px 0px 80px 0px',
        threshold: 0,
      }
    );
    heroVisObserver.observe(heroEl);
  }
}

// =========================================================================
// Toggles: UV Blacklight, Hold Up to the Light, Motor, Card Flip
// =========================================================================
export function toggleUvBlacklight(forceState) {
  store.uvBlacklight = typeof forceState === 'boolean' ? forceState : !store.uvBlacklight;
  document.body.classList.toggle('uv-blacklight', store.uvBlacklight);
  const uvBtn = document.getElementById('btn-uv-toggle');
  if (uvBtn) {
    uvBtn.textContent = store.uvBlacklight ? '🟣 UV Blacklight: ON' : '🟣 UV Blacklight: Off';
    uvBtn.className = store.uvBlacklight
      ? 'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-black border border-fuchsia-400/60 bg-fuchsia-500/20 text-white transition-all'
      : 'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-bold border border-white/10 bg-slate-950/75 text-slate-400 hover:text-white transition-all';
  }
  updateOpticsVisuals(getActiveRecord());
  saveUiPrefs();
  playUvToggleSound(store.uvBlacklight);
  emit('opticsChanged');
  showToast(store.uvBlacklight ? '🟣 UV 395nm Blacklight ON — Fluorescence reactive!' : '🟣 UV Blacklight Off — Studio daylight restored.');
}

export function toggleBacklight(forceState) {
  store.backlightOn = typeof forceState === 'boolean' ? forceState : !store.backlightOn;
  updateOpticsVisuals(getActiveRecord());
  saveUiPrefs();
  playCrateTickSound(store.backlightOn ? 1.25 : 0.88);
  emit('opticsChanged');
  const rec = getActiveRecord();
  if (store.backlightOn && rec) {
    const trans = rec.wax_spec?.translucent;
    showToast(trans
      ? `☀️ Optical Backlight ON — Light transmits through ${rec.wax_spec.color_name || 'translucent'} wax!`
      : `☀️ Optical Backlight ON — Opaque ${rec.wax_spec?.color_name || '180g'} wax blocks internal spill.`);
  }
}

export function togglePlatterMotor(forceState) {
  const next = typeof forceState === 'boolean' ? forceState : !store.isSpinning;
  store.isSpinning = next;
  store.motorOn = next;
  setTonearmTargetDeg(next ? 18 : -8);
  syncMiniBarVisibility();
  if (next) playNeedleDropSound();
  else playCrateTickSound(0.75);
}

export function setTonearmTargetDeg(deg) {
  tonearmAngleDeg = deg;
  const arm = document.getElementById('turntable-tonearm');
  if (arm && !isDraggingArm) {
    arm.style.transform = `rotate(${deg.toFixed(2)}deg)`;
  }
}

export function toggleHeroCardFlip(forceState) {
  const stageEl = document.getElementById('hero-flip-stage');
  if (!stageEl) return;
  store.isCardFlipped = typeof forceState === 'boolean' ? forceState : !store.isCardFlipped;
  stageEl.classList.toggle('is-flipped', store.isCardFlipped);

  const topLabel = document.getElementById('top-flip-label');
  const topIcon = document.getElementById('top-flip-icon');
  const botText = document.getElementById('flip-btn-text');
  const botArrow = document.getElementById('flip-btn-arrow');

  if (store.isCardFlipped) {
    if (topLabel) topLabel.textContent = 'Flip to Pressing Specs';
    if (topIcon) topIcon.textContent = '↺';
    if (botText) botText.textContent = 'Pressing & Specs';
    if (botArrow) botArrow.textContent = '↺';
    const rec = getActiveRecord();
    if (rec) renderStreamingDeck(rec);
  } else {
    if (topLabel) topLabel.textContent = 'Flip to Album Player';
    if (topIcon) topIcon.textContent = '↻';
    if (botText) botText.textContent = 'Stream & Tracklist';
    if (botArrow) botArrow.textContent = '↻';
  }
}

// =========================================================================
// Kinetic "SPIN THE CRATE" Roulette
// =========================================================================
export function triggerKineticCrateSpin() {
  if (store.isSpinningRoulette) return;
  const pool = getSmartSpinPool();
  if (!pool.length) return;

  const list = store.filteredRecords.length ? store.filteredRecords : store.records;
  const candidateSet = new Set(pool.map((r) => Number(r.release_id)));
  let validIndices = [];
  list.forEach((r, idx) => {
    if (candidateSet.has(Number(r.release_id))) validIndices.push(idx);
  });
  if (!validIndices.length) {
    store.filter = 'all';
    store.searchQuery = '';
    const sIn = document.getElementById('search-input');
    if (sIn) sIn.value = '';
    emit('requestRefilter');
    const refreshed = store.filteredRecords.length ? store.filteredRecords : store.records;
    refreshed.forEach((r, idx) => {
      if (candidateSet.has(Number(r.release_id))) validIndices.push(idx);
    });
  }
  if (!validIndices.length) validIndices = list.map((_, i) => i);

  store.isSpinningRoulette = true;
  const totalSteps = 20 + Math.floor(Math.random() * 8);
  let step = 0;
  setTonearmTargetDeg(-8);

  const prevWing = document.getElementById('stage-prev-card');
  const nextWing = document.getElementById('stage-next-card');
  const velReadout = document.getElementById('reel-velocity-readout');

  const stepRoulette = () => {
    step += 1;
    const progress = step / totalSteps;
    let pickIdx = validIndices[Math.floor(Math.random() * validIndices.length)];
    if (validIndices.length > 1 && pickIdx === store.activeIndex) {
      const alt = validIndices.filter((i) => i !== store.activeIndex);
      pickIdx = alt[Math.floor(Math.random() * alt.length)];
    }
    store.activeIndex = pickIdx;
    currentOmega = OMEGA_45 * (2.6 - progress * 1.4);

    playCrateTickSound(1.45 - progress * 0.65);
    if (velReadout) {
      const rpmSim = Math.max(4.2, (1 - progress) * 96).toFixed(1);
      velReadout.textContent = `Velocity: ${rpmSim} RPM • Spinning Crate...`;
      velReadout.className = 'text-[11px] font-mono-tech font-bold text-fuchsia-300 animate-pulse';
    }
    if (prevWing && nextWing) {
      prevWing.classList.toggle('wing-tick-left', step % 2 === 0);
      nextWing.classList.toggle('wing-tick-right', step % 2 === 1);
    }
    renderHeroStage();

    if (step < totalSteps) {
      const nextDelay = Math.round(38 + Math.pow(progress, 2.3) * 200);
      setTimeout(stepRoulette, nextDelay);
    } else {
      store.isSpinningRoulette = false;
      if (prevWing) prevWing.classList.remove('wing-tick-left');
      if (nextWing) nextWing.classList.remove('wing-tick-right');
      if (store.isSpinning) setTonearmTargetDeg(18);

      const winner = getActiveRecord();
      playNeedleDropSound();
      setTimeout(() => playRouletteWinChord(false), 90);
      if (winner) {
        const wax = winner.wax_spec || {};
        spawnParticles(wax.primary_color, wax.secondary_color, wax.accent_color, 68);
        if (velReadout) {
          velReadout.textContent = `Locked: #${winner.release_id} • ${winner.artist}`;
          velReadout.className = 'text-[11px] font-mono-tech font-bold text-emerald-300';
        }
        showToast(`🎰 Spin Winner: ${winner.artist} — "${winner.title}" (${wax.variant_badge || 'LP'})`);
      }
      syncUrlFromState();
      renderHeroStage();
      emit('activeRecordChanged', winner);
    }
  };

  stepRoulette();
}

export function setSmartSpinMode(mode, autoTriggerSpin = true, persist = true) {
  if (store.showroomTickInterval) {
    clearInterval(store.showroomTickInterval);
    store.showroomTickInterval = null;
  }
  store.spinMode = mode;
  if (persist) saveUiPrefs();

  document.querySelectorAll('.spin-mode-btn').forEach((btn) => {
    const m = btn.getAttribute('data-spin-mode');
    const act = m === mode;
    btn.className = act
      ? 'spin-mode-btn inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl border transition-all bg-cyan-500/15 border-cyan-400 text-white text-[11px] font-bold shadow-[0_0_16px_rgba(6,182,212,0.2)]'
      : 'spin-mode-btn inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl border transition-all bg-slate-950/80 border-white/15 text-slate-300 hover:border-cyan-400/50 hover:text-white text-[11px] font-bold';
  });

  document.querySelectorAll('[data-sommelier-mode]').forEach((btn) => {
    const act = btn.getAttribute('data-sommelier-mode') === mode;
    btn.className = act
      ? 'px-2.5 py-1 rounded-full text-[11px] font-mono-tech font-bold bg-cyan-500/25 text-cyan-200 border border-cyan-400/50 transition'
      : 'px-2.5 py-1 rounded-full text-[11px] font-mono-tech font-semibold bg-slate-950/80 text-slate-400 border border-white/10 hover:text-white transition';
  });

  if (mode === 'showroom') {
    store.showroomCountdown = 15;
    if (!store.uvBlacklight) toggleUvBlacklight(true);
    store.showroomTickInterval = setInterval(() => {
      const modalOpen = Boolean(document.getElementById('modal-backdrop') && !document.getElementById('modal-backdrop').classList.contains('hidden'));
      if (!store.isSpinningRoulette && store.activeTab === 'showcase' && !modalOpen && !document.hidden) {
        store.showroomCountdown -= 1;
        if (store.showroomCountdown <= 0) {
          store.showroomCountdown = 15;
          triggerKineticCrateSpin();
        }
        updateSmartSpinModeBadges();
      }
    }, 1000);
    showToast('📺 Showroom Kiosk Active: Auto-spinning every 15s with UV Blacklight!');
  }

  updateSmartSpinModeBadges();
  if (autoTriggerSpin) triggerKineticCrateSpin();
}

// =========================================================================
// Live Discogs Gallery Fetch (with Optional User Runtime PAT)
// =========================================================================
export async function fetchSingleReleaseGallery(rec) {
  const rid = String(rec.release_id);
  const headers = { Accept: 'application/vnd.discogs.v2.discogs+json' };
  const resp = await fetch(`https://api.discogs.com/releases/${rid}?curr_abbr=USD`, { headers });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const detail = await resp.json();
  const existingImgs = rec.images && Array.isArray(rec.images.classified_images) ? rec.images.classified_images : [];
  const imgs = (detail.images || []).map((im, i) => {
    const prev = existingImgs[i] || {};
    return {
      index: i,
      uri: im.uri || im.resource_url || '',
      uri150: im.uri150 || im.uri || '',
      local_uri: prev.local_uri || `assets/releases/${rid}/img_${i}.jpg`,
      width: im.width || 600,
      height: im.height || 600,
      role: prev.role || (i === 0 ? 'front_cover' : 'secondary'),
      cv_metrics: prev.cv_metrics || null,
    };
  });
  store.releaseGalleryCache[rid] = imgs;
  if (!rec.images) rec.images = {};
  rec.images.classified_images = imgs;
  if (imgs[0] && imgs[0].uri && !rec.images.cover_image_url) {
    rec.images.cover_image_url = imgs[0].uri;
  }
  if (typeof detail.lowest_price === 'number' && detail.lowest_price > 0) {
    rec.estimated_value_usd = Number(detail.lowest_price.toFixed(2));
  }
  return imgs;
}

// =========================================================================
// 60FPS Turntable Physics Loop, Platter Scrubbing & VU Needle Animation
// =========================================================================
let specCacheW = 0;
let specCacheH = 0;

function drawRadialSpectrumRing(bars, energy) {
  const canvas = document.getElementById('platter-spectrum-canvas');
  if (!canvas || !bars) return;
  const cw = canvas.clientWidth || 380;
  const ch = canvas.clientHeight || 380;
  if (cw <= 0 || ch <= 0) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const pw = Math.round(cw * dpr);
  const ph = Math.round(ch * dpr);
  if (specCacheW !== pw || specCacheH !== ph || canvas.width !== pw || canvas.height !== ph) {
    canvas.width = pw;
    canvas.height = ph;
    specCacheW = pw;
    specCacheH = ph;
  }
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, cw, ch);

  const cx = cw / 2;
  const cy = ch / 2;
  const half = Math.min(cw, ch) / 2;
  const rInner = half - 14.5;
  const rec = getActiveRecord();
  const wax = (rec && rec.wax_spec) || {};
  const colPrimary = safeCssColor(wax.accent_color || wax.primary_color, '#22d3ee');
  const colSecondary = safeCssColor(wax.secondary_color, '#d946ef');
  const count = bars.length || 64;
  const isIdle = energy < 0.02;

  ctx.lineCap = 'round';
  ctx.lineWidth = isIdle ? 1.5 : 2.1;

  for (let i = 0; i < count; i++) {
    const theta = (i / count) * Math.PI * 2 + platterAngle * 0.25;
    const amp = isIdle ? 0 : Math.min(1, Math.max(0, bars[i] || 0));
    const len = isIdle ? 2.2 : 2.5 + amp * 11.0;
    const x1 = cx + Math.cos(theta) * rInner;
    const y1 = cy + Math.sin(theta) * rInner;
    const x2 = cx + Math.cos(theta) * (rInner + len);
    const y2 = cy + Math.sin(theta) * (rInner + len);

    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    if (isIdle) {
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)';
    } else {
      ctx.globalAlpha = 0.45 + amp * 0.55;
      ctx.strokeStyle = i % 3 === 0 ? colSecondary : (i % 2 === 0 ? colPrimary : '#22d3ee');
    }
    ctx.stroke();
  }
  ctx.restore();
}

function updatePlatterAudioVisuals() {
  const { energy = 0, bars, active = false } = getVuLevels();
  if (heroRenderer) {
    heroRenderer.setOptics({ audioEnergy: energy });
  }
  if (!active) {
    if (!spectrumClearedIdle) {
      drawRadialSpectrumRing(bars, 0);
      spectrumClearedIdle = true;
    }
    return;
  }
  spectrumClearedIdle = false;
  drawRadialSpectrumRing(bars, energy);
}

function shouldRenderStageLoop() {
  return store.activeTab === 'showcase' && !store.stageCollapsed && isHeroInViewport && !document.hidden;
}

export function syncStageLoopState() {
  const heroEl = document.getElementById('hero-turntable-stage');
  if (shouldRenderStageLoop()) {
    if (heroEl) heroEl.dataset.renderState = 'active';
    if (!rafId) {
      lastFrameTime = performance.now();
      rafId = requestAnimationFrame(tickStageFrame);
    }
  } else {
    if (heroEl) heroEl.dataset.renderState = 'paused';
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }
}

function tickStageFrame(now) {
  if (!shouldRenderStageLoop()) {
    rafId = null;
    const heroEl = document.getElementById('hero-turntable-stage');
    if (heroEl) heroEl.dataset.renderState = 'paused';
    return;
  }

  const dt = Math.min(0.05, Math.max(0.001, (now - lastFrameTime) / 1000));
  lastFrameTime = now;

  const targetOmega = store.isSpinning && store.motorOn ? (store.rpm === 45 ? OMEGA_45 : OMEGA_33) : 0;
  if (isScrubbingPlatter) {
    currentOmega = scrubOmega;
    // Exponential decay of scrub velocity if user pauses hand on platter
    scrubOmega *= Math.exp(-dt * 12);
  } else if (targetOmega > 0) {
    // Direct-drive high torque ramp
    currentOmega += (targetOmega - currentOmega) * Math.min(1, dt * 8.5);
    platterAngle += currentOmega * dt;
  } else {
    // Authentic heavy aluminum platter coasting inertia
    currentOmega *= Math.exp(-dt * 0.85);
    if (Math.abs(currentOmega) < 0.02) currentOmega = 0;
    platterAngle += currentOmega * dt;
  }

  strobeAngle += (currentOmega - targetOmega) * dt * 0.35;
  setPlatterVelocityRatio(currentOmega / OMEGA_33);

  const rpmVal = (currentOmega / (Math.PI * 2)) * 60;
  const rpmReadout = document.getElementById('platter-rpm-readout');
  if (rpmReadout) {
    if (isScrubbingPlatter) {
      rpmReadout.textContent = `SCRUB ${rpmVal.toFixed(1)} RPM`;
    } else if (!store.isSpinning) {
      rpmReadout.textContent = rpmVal > 0.4 ? `COASTING ${rpmVal.toFixed(1)} RPM` : 'PLATTER PARKED • 0.0 RPM';
    } else if (store.isPreviewPlaying && store.activeTrackIndex >= 0) {
      const sData = resolveAlbumStreamingData(getActiveRecord());
      const tr = sData.tracks?.[store.activeTrackIndex];
      const ratioPct = ((currentOmega / (store.rpm === 45 ? OMEGA_45 : OMEGA_33) - 1) * 100).toFixed(1);
      rpmReadout.textContent = tr
        ? `♫ ${tr.title.slice(0, 15).toUpperCase()} • ${store.rpm === 45 ? '45' : '33.3'}`
        : `${store.rpm === 45 ? '45.0' : '33.3'} RPM (${ratioPct}%)`;
    } else {
      rpmReadout.textContent = store.rpm === 45 ? '45.0 RPM • QUARTZ LOCK' : '33.3 RPM • QUARTZ LOCK';
    }
  }

  const strobeLed = document.getElementById('platter-strobe-led');
  if (strobeLed) {
    strobeLed.className = store.isSpinning
      ? 'w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]'
      : 'w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_#f59e0b]';
  }

  updatePlatterAudioVisuals();
  if (heroRenderer) {
    heroRenderer.setAngles(platterAngle, strobeAngle);
    heroRenderer.render();
  }

  rafId = requestAnimationFrame(tickStageFrame);
}

// =========================================================================
// Initialize Stage Listeners & Interactions
// =========================================================================
export function initTurntableStage() {
  const canvas = document.getElementById('hero-webgl-canvas');
  if (canvas) {
    heroRenderer = new WebGLWaxDiscRenderer(canvas);
  }

  // Platter scrubbing / tapping
  if (canvas) {
    const getPointerAngle = (e) => {
      const rect = canvas.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      return Math.atan2(e.clientY - cy, e.clientX - cx);
    };

    canvas.addEventListener('pointerdown', (e) => {
      canvas.setPointerCapture(e.pointerId);
      isScrubbingPlatter = true;
      scrubMoved = false;
      scrubLastAngle = getPointerAngle(e);
      scrubLastTime = performance.now();
      scrubOmega = 0;
    });

    canvas.addEventListener('pointermove', (e) => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width > 0 && heroRenderer) {
        const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        const ny = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
        heroRenderer.setPointer(nx, ny);
      }
      if (!isScrubbingPlatter) return;
      const now = performance.now();
      const ang = getPointerAngle(e);
      let dA = ang - scrubLastAngle;
      while (dA > Math.PI) dA -= Math.PI * 2;
      while (dA < -Math.PI) dA += Math.PI * 2;
      if (Math.abs(dA) > 0.025) scrubMoved = true;
      const dt = Math.max(0.004, (now - scrubLastTime) / 1000);
      platterAngle += dA;
      scrubOmega = dA / dt;
      scrubLastAngle = ang;
      scrubLastTime = now;
    });

    const endScrub = (e) => {
      if (!isScrubbingPlatter) return;
      isScrubbingPlatter = false;
      try {
        canvas.releasePointerCapture(e.pointerId);
      } catch {
        // Ignore
      }
      if (!scrubMoved) {
        togglePlatterMotor();
      }
    };
    canvas.addEventListener('pointerup', endScrub);
    canvas.addEventListener('pointercancel', endScrub);
  }

  // Global cursor + mobile tilt anisotropic groove lighting
  window.addEventListener('pointermove', (e) => {
    if (!heroRenderer || store.activeTab !== 'showcase') return;
    const nx = (e.clientX / Math.max(1, window.innerWidth)) * 2 - 1;
    const ny = -((e.clientY / Math.max(1, window.innerHeight)) * 2 - 1);
    heroRenderer.setPointer(nx * 0.85, ny * 0.85);
  }, { passive: true });

  window.addEventListener('deviceorientation', (e) => {
    if (!heroRenderer || store.activeTab !== 'showcase') return;
    if (typeof e.gamma === 'number' && typeof e.beta === 'number') {
      heroRenderer.setPointer(Math.max(-1, Math.min(1, e.gamma / 35)), Math.max(-1, Math.min(1, (e.beta - 35) / 35)));
    }
  }, { passive: true });

  // Draggable S-Shaped Tonearm Cueing
  const armEl = document.getElementById('turntable-tonearm');
  const armHit = document.getElementById('tonearm-headshell-hit') || armEl;
  if (armEl && armHit) {
    const getArmAngleFromPointer = (e) => {
      const rect = armEl.getBoundingClientRect();
      const pivotX = rect.left + rect.width * 0.783;
      const pivotY = rect.top + rect.height * 0.175;
      const dx = e.clientX - pivotX;
      const dy = e.clientY - pivotY;
      // Straight down (+Y) is ~20 deg offset for S-arm geometry
      const rawDeg = (Math.atan2(-dx, dy) * 180) / Math.PI;
      return Math.max(-12, Math.min(34, rawDeg));
    };

    armHit.addEventListener('pointerdown', (e) => {
      e.stopPropagation();
      armHit.setPointerCapture(e.pointerId);
      isDraggingArm = true;
      armEl.classList.add('is-dragging');
    });

    armHit.addEventListener('pointermove', (e) => {
      if (!isDraggingArm) return;
      tonearmAngleDeg = getArmAngleFromPointer(e);
      armEl.style.transform = `rotate(${tonearmAngleDeg.toFixed(2)}deg)`;
    });

    const releaseArm = (e) => {
      if (!isDraggingArm) return;
      isDraggingArm = false;
      armEl.classList.remove('is-dragging');
      try {
        armHit.releasePointerCapture(e.pointerId);
      } catch {
        // Ignore
      }
      if (tonearmAngleDeg < 11) {
        setTonearmTargetDeg(-8);
        stopPreviewAudio();
        if (store.isSpinning) togglePlatterMotor(false);
        showToast('Tonearm parked on rest — platter coasting.');
      } else {
        const rec = getActiveRecord();
        if (rec) {
          const tracks = resolveAlbumStreamingData(rec).tracks || [];
          const frac = Math.max(0, Math.min(0.999, (tonearmAngleDeg - 13) / 18));
          const trIdx = Math.min(Math.max(0, tracks.length - 1), Math.floor(frac * Math.max(1, tracks.length)));
          if (!store.isSpinning) togglePlatterMotor(true);
          playAlbumTrackAtIndex(rec, trIdx);
          showToast(`🎯 Stylus cued onto Track ${trIdx + 1}: "${tracks[trIdx]?.title || rec.title}"`);
        }
      }
    };
    armHit.addEventListener('pointerup', releaseArm);
    armHit.addEventListener('pointercancel', releaseArm);
  }

  // Carousel, Wing Cards & Sticky Mini-Bar Controls
  const stepRecord = (delta, pulseMiniBar = false) => {
    if (store.isSpinningRoulette) return;
    playCrateTickSound(delta > 0 ? 1.08 : 0.92);
    setActiveIndex(store.activeIndex + delta);
    if (pulseMiniBar) renderMiniBar(getActiveRecord(), true);
  };
  document.getElementById('btn-carousel-prev')?.addEventListener('click', () => stepRecord(-1));
  document.getElementById('btn-carousel-next')?.addEventListener('click', () => stepRecord(1));
  document.getElementById('stage-prev-card')?.addEventListener('click', () => stepRecord(-1));
  document.getElementById('stage-next-card')?.addEventListener('click', () => stepRecord(1));
  document.getElementById('btn-carousel-random')?.addEventListener('click', () => triggerKineticCrateSpin());

  // Manual Stage Collapse & Mini-Bar Transport
  document.getElementById('btn-collapse-stage')?.addEventListener('click', () => {
    playCrateTickSound(0.95);
    setStageCollapsed(true);
  });
  document.getElementById('minibar-expand')?.addEventListener('click', () => {
    playCrateTickSound(1.1);
    expandHeroStage();
  });
  document.getElementById('minibar-expand-area')?.addEventListener('click', () => {
    playCrateTickSound(1.1);
    expandHeroStage();
  });
  document.getElementById('minibar-prev')?.addEventListener('click', () => stepRecord(-1, true));
  document.getElementById('minibar-next')?.addEventListener('click', () => stepRecord(1, true));
  document.getElementById('minibar-random')?.addEventListener('click', () => {
    if (isMiniBarVisible()) {
      const list = store.filteredRecords.length ? store.filteredRecords : store.records;
      const pool = getSmartSpinPool();
      const candidateSet = new Set(pool.map((r) => Number(r.release_id)));
      let validIndices = [];
      list.forEach((r, idx) => {
        if (candidateSet.has(Number(r.release_id))) validIndices.push(idx);
      });
      if (!validIndices.length) validIndices = list.map((_, i) => i);
      if (!validIndices.length) return;
      let pickIdx = validIndices[Math.floor(Math.random() * validIndices.length)];
      if (validIndices.length > 1 && pickIdx === store.activeIndex) {
        const alt = validIndices.filter((i) => i !== store.activeIndex);
        pickIdx = alt[Math.floor(Math.random() * alt.length)];
      }
      playCrateTickSound(1.22);
      setActiveIndex(pickIdx);
      const winner = getActiveRecord();
      renderMiniBar(winner, true);
      if (winner) {
        showToast(`🎲 Now Spinning: ${winner.artist} — "${winner.title}" (${winner.wax_spec?.variant_badge || 'LP'})`);
      }
    } else {
      triggerKineticCrateSpin();
    }
  });

  // Smart Spin Mode Pills
  document.querySelectorAll('.spin-mode-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-spin-mode') || 'all';
      if (mode === 'showroom' && store.spinMode === 'showroom' && store.showroomTickInterval) {
        setSmartSpinMode('all', false);
        showToast('📺 Showroom Kiosk Paused.');
        return;
      }
      setSmartSpinMode(mode, true);
    });
  });

  // Hero Flattening quick toggle
  document.getElementById('btn-hero-flatten-cycle')?.addEventListener('click', () => {
    const rec = getActiveRecord();
    if (!rec) return;
    const cur = rec.flattening_status || DEFAULT_FLATTENING_STATUS;
    setRecordFlatteningStatus(rec.release_id, cur === 'Need to be done' ? 'Done' : 'Need to be done');
  });

  // Gallery refresh & click-to-pin
  document.getElementById('btn-fetch-this-release')?.addEventListener('click', async () => {
    const rec = getActiveRecord();
    if (!rec) return;
    showToast(`Refreshing Discogs image gallery for "${rec.title}"...`);
    try {
      const imgs = await fetchSingleReleaseGallery(rec);
      renderHeroStage();
      emit('recordsChanged');
      showToast(`Loaded ${imgs.length} Discogs images for "${rec.title}"!`);
    } catch (err) {
      showToast(`Could not fetch gallery: ${err.message}`);
    }
  });

  document.getElementById('hero-gallery-strip')?.addEventListener('click', (e) => {
    const pinBtn = e.target.closest('[data-pin-image-url]');
    if (pinBtn) {
      pinReleasePressingOverride(
        pinBtn.getAttribute('data-pin-release-id'),
        pinBtn.getAttribute('data-pin-image-url'),
        Number(pinBtn.getAttribute('data-pin-image-index') || 0)
      );
      return;
    }
    const clearBtn = e.target.closest('[data-clear-pin]');
    if (clearBtn) {
      clearReleasePressingOverride(clearBtn.getAttribute('data-clear-pin'));
    }
  });

  // Card Flip listeners
  document.getElementById('btn-flip-streaming')?.addEventListener('click', () => toggleHeroCardFlip());
  document.getElementById('btn-card-flip-top')?.addEventListener('click', () => toggleHeroCardFlip());
  document.getElementById('hero-face-back')?.addEventListener('click', (e) => e.stopPropagation());

  // Sync UI state on store events
  subscribe((topic) => {
    if (topic === 'activeRecordChanged' || topic === 'recordsChanged' || topic === 'overridesChanged') {
      if (topic === 'overridesChanged') lastMiniBarThumbKey = '';
      renderHeroStage();
    }
    if (topic === 'crateCardSelected') {
      renderMiniBar(getActiveRecord(), true);
    }
    if (topic === 'expandStageRequested') {
      expandHeroStage();
    }
    if (topic === 'activeTabChanged') {
      syncMiniBarVisibility();
      syncStageLoopState();
    }
    if (topic === 'audioPlaybackChanged') {
      const rec = getActiveRecord();
      if (rec) renderStreamingDeck(rec);
    }
    if (topic === 'motorStartRequested') {
      if (!store.isSpinning) togglePlatterMotor(true);
    }
  });

  document.addEventListener('visibilitychange', () => {
    syncStageLoopState();
  });

  window.__expandHeroStage = expandHeroStage;

  // Apply persisted UV & Spin Mode UI states
  document.body.classList.toggle('uv-blacklight', store.uvBlacklight);
  const uvBtn = document.getElementById('btn-uv-toggle');
  if (uvBtn) {
    uvBtn.textContent = store.uvBlacklight ? '🟣 UV Blacklight: ON' : '🟣 UV Blacklight: Off';
    uvBtn.className = store.uvBlacklight
      ? 'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-black border border-fuchsia-400/60 bg-fuchsia-500/20 text-white transition-all'
      : 'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-bold border border-white/10 bg-slate-950/75 text-slate-400 hover:text-white transition-all';
  }
  if (store.spinMode && store.spinMode !== 'all') {
    setSmartSpinMode(store.spinMode, false, false);
  }

  setupScrollCollapseObservers();
  renderHeroStage();
  syncMiniBarVisibility();
  syncStageLoopState();
}
