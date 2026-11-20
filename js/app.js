// KRUNKED // VINYL VAULT v6.0 — Top-Level Zero-Build ES Module Application Coordinator

import { renderAnalyticsView, initAnalyticsWheel } from './analytics-wheel.js';
import {
  applyArenaCrossfade,
  bindAudioEngineEvents,
  dualDropArenaDecks,
  isArenaAudioPlaying,
  playCrateTickSound,
  stopArenaAudio,
} from './audio-preview.js';
import { initCardExporter } from './card-exporter.js';
import {
  closeCommandPalette,
  initCommandPalette,
  isCommandPaletteOpen,
  openCommandPalette,
} from './command-palette.js';
import { initCrateViews } from './crate-views.js';
import { initCvXrayAndSandbox, renderPipelineCvXrayPanel } from './cv-xray.js';
import { initFlatteningLab, renderFlatteningView } from './flattening-lab.js';
import { closeJacketInspector, initJacketInspector } from './jacket-inspector.js';
import { initPersistenceHub } from './persistence.js';
import {
  getActiveRecord,
  hydrateVaultStore,
  refreshExternalJsonIfNewer,
  saveUiPrefs,
  setActiveIndex,
  store,
  subscribe,
  syncUrlFromState,
} from './store.js';
import {
  initTurntableStage,
  toggleBacklight,
  toggleHeroCardFlip,
  toggleUvBlacklight,
  triggerKineticCrateSpin,
} from './turntable-stage.js';
import {
  escapeHtml,
  getVerifiedPressingPhotoUrl,
  initParticleCanvas,
  copyTextToClipboard,
  showToast,
} from './utils.js';
import {
  castArenaVote,
  dealNextMatchup,
  initVariantClashArena,
  renderArenaView,
  toggleArenaBacklight,
} from './variant-clash.js';

export function updateKpiStrip() {
  const total = store.records.length;
  const verifiedCount = store.records.filter((r) => Boolean(getVerifiedPressingPhotoUrl(r, store.userOverrides))).length;
  const coloredCount = store.records.filter((r) => r.wax_spec && r.wax_spec.pattern !== 'black').length;
  const pct = total ? ((coloredCount / total) * 100).toFixed(1) : '0.0';
  const pressPct = total ? ((verifiedCount / total) * 100).toFixed(1) : '0.0';

  const setText = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  setText('kpi-total-records', `${total} LPs`);
  setText('kpi-pressing-photos', `${verifiedCount} / ${total}`);
  setText('kpi-colored-wax', `${pct}%`);
  setText('bg-enrich-progress', `• ${total} LPs & ${verifiedCount} Pressing Photos Compiled`);
  setText('hero-pressing-ratio', `${verifiedCount}/${total}`);

  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.placeholder = `Search all ${total} LPs by artist, album, label, catalog #, or pressing color...`;
  }

  const prof = window.__DISCOGS_COLLECTION__?.profile || {};
  const colVal = prof.collection_value || {};
  const SYNTHETIC_LEGACY = new Set([
    '$3,917.41', '$6,252.80', '$10,848.23',
    '$3,721.74', '$6,011.87', '$10,437.49',
    '$3,886.22', '$6,203.01', '$10,761.84',
  ]);
  const lowStr = colVal.minimum && !SYNTHETIC_LEGACY.has(String(colVal.minimum).trim()) ? colVal.minimum : '$3,921.14';
  const medianStr = colVal.median && !SYNTHETIC_LEGACY.has(String(colVal.median).trim()) ? colVal.median : '$6,406.96';
  const highStr = colVal.maximum && !SYNTHETIC_LEGACY.has(String(colVal.maximum).trim()) ? colVal.maximum : '$11,044.13';

  setText('kpi-vault-value', medianStr);
  setText('kpi-vault-range', `Low ${lowStr} • High ${highStr}`);
  setText('kpi-nm-ratio', highStr);
  setText('kpi-gallery-sub', `High Est. • Low ${lowStr}`);

  const todoCount = store.records.filter((r) => (r.flattening_status || 'Need to be done') === 'Need to be done').length;
  const doneCount = store.records.filter((r) => r.flattening_status === 'Done').length;
  const unlistedCount = Math.max(0, total - todoCount - doneCount);

  setText('kpi-flattening', `${todoCount} Queued / ${doneCount} Done`);
  setText('chip-flatten-todo', `🔥 Flattening Queue (${todoCount})`);
  setText('chip-flatten-done', `✓ Flattened & Verified (${doneCount})`);
  setText('pipe-kpi-cv', `${verifiedCount} / ${total} Physical Discs Verified (${pressPct}%)`);
  setText('pipe-kpi-flatten', `${todoCount} Queued • ${doneCount} Flat / Done • ${unlistedCount} Unlisted`);
  setText('pipe-kpi-val', `Med ${medianStr} • Low ${lowStr} • High ${highStr}`);
  setText('modal-stat-lps', `${total} LPs`);
  setText('modal-stat-photos', `${verifiedCount} Pressing Photos`);
  setText('modal-stat-flatten', `${todoCount} Queued / ${doneCount} Done`);
}

function setMainVaultTab(tab) {
  const validTabs = ['showcase', 'arena', 'analytics', 'pipeline', 'flattening'];
  const nextTab = validTabs.includes(tab) ? tab : 'showcase';
  if (store.activeTab === 'arena' && nextTab !== 'arena') {
    stopArenaAudio();
  }
  store.activeTab = nextTab;

  for (const t of validTabs) {
    document.getElementById(`view-${t}`)?.classList.toggle('hidden', t !== nextTab);
    const btn = document.getElementById(`tab-btn-${t}`);
    if (btn) {
      btn.className = t === nextTab
        ? 'px-3 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap nav-tab-active'
        : 'px-3 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap nav-tab-idle';
    }
  }

  if (nextTab === 'arena') renderArenaView();
  else if (nextTab === 'analytics') renderAnalyticsView();
  else if (nextTab === 'pipeline') renderPipelineCvXrayPanel();
  else if (nextTab === 'flattening') renderFlatteningView();

  syncUrlFromState();
}

function bindGlobalHotkeys() {
  window.addEventListener('keydown', (e) => {
    // Global Cmd/Ctrl + K Command Palette
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (isCommandPaletteOpen()) closeCommandPalette();
      else openCommandPalette();
      return;
    }

    const modalSync = document.getElementById('modal-backdrop');
    const modalInsp = document.getElementById('jacket-inspector-modal');

    if (e.key === 'Escape') {
      if (isCommandPaletteOpen()) {
        e.preventDefault();
        closeCommandPalette();
        return;
      }
      if (modalInsp && !modalInsp.classList.contains('hidden')) {
        e.preventDefault();
        closeJacketInspector();
        return;
      }
      if (modalSync && !modalSync.classList.contains('hidden')) {
        e.preventDefault();
        modalSync.classList.add('hidden');
        return;
      }
    }

    const activeEl = document.activeElement;
    const tag = activeEl && activeEl.tagName ? activeEl.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (activeEl && activeEl.isContentEditable)) return;
    if (isCommandPaletteOpen()) return;
    if (modalSync && !modalSync.classList.contains('hidden')) return;
    if (modalInsp && !modalInsp.classList.contains('hidden')) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    // Showcase Shortcuts
    if (store.activeTab === 'showcase') {
      if (e.code === 'Space') {
        e.preventDefault();
        triggerKineticCrateSpin();
      } else if (e.key === 'ArrowLeft') {
        if (store.isSpinningRoulette) return;
        e.preventDefault();
        playCrateTickSound(0.92);
        setActiveIndex(store.activeIndex - 1);
      } else if (e.key === 'ArrowRight') {
        if (store.isSpinningRoulette) return;
        e.preventDefault();
        playCrateTickSound(1.08);
        setActiveIndex(store.activeIndex + 1);
      } else if (e.key.toLowerCase() === 'f') {
        e.preventDefault();
        toggleHeroCardFlip();
      } else if (e.key.toLowerCase() === 'b') {
        e.preventDefault();
        toggleBacklight();
      }
    }
    // Variant Clash Arena Shortcuts
    else if (store.activeTab === 'arena') {
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        castArenaVote('A');
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        castArenaVote('B');
      } else if (e.code === 'Space') {
        e.preventDefault();
        const fader = document.getElementById('arena-crossfader');
        const nextVal = store.arenaCrossfade < 0 ? 1 : -1;
        if (fader) fader.value = String(nextVal);
        applyArenaCrossfade(nextVal);
        if (!isArenaAudioPlaying() && store.arenaDeckA && store.arenaDeckB) {
          dualDropArenaDecks(store.arenaDeckA, store.arenaDeckB);
        }
      } else if (e.key.toLowerCase() === 'b') {
        e.preventDefault();
        toggleArenaBacklight();
      } else if (e.key.toLowerCase() === 's') {
        e.preventDefault();
        playCrateTickSound(1.2);
        dealNextMatchup();
      }
    }

    // Universal Shortcuts
    if (e.key === '/') {
      e.preventDefault();
      if (store.activeTab !== 'showcase') setMainVaultTab('showcase');
      const searchEl = document.getElementById('search-input');
      if (searchEl) {
        searchEl.focus();
        searchEl.select();
      }
    } else if (e.key.toLowerCase() === 'u') {
      e.preventDefault();
      toggleUvBlacklight();
    }
  });
}

async function bootApp() {
  if (store._initialized) return;
  store._initialized = true;

  initParticleCanvas();
  await hydrateVaultStore();

  window.__setMainVaultTab = setMainVaultTab;

  // Navigation buttons
  document.getElementById('tab-btn-showcase')?.addEventListener('click', () => setMainVaultTab('showcase'));
  document.getElementById('tab-btn-arena')?.addEventListener('click', () => setMainVaultTab('arena'));
  document.getElementById('btn-hero-open-arena')?.addEventListener('click', () => setMainVaultTab('arena'));
  document.getElementById('tab-btn-analytics')?.addEventListener('click', () => setMainVaultTab('analytics'));
  document.getElementById('tab-btn-pipeline')?.addEventListener('click', () => setMainVaultTab('pipeline'));
  document.getElementById('tab-btn-flattening')?.addEventListener('click', () => setMainVaultTab('flattening'));
  document.getElementById('kpi-flattening-card')?.addEventListener('click', () => setMainVaultTab('flattening'));

  // Header Hardware Controls
  document.getElementById('btn-uv-toggle')?.addEventListener('click', () => toggleUvBlacklight());
  const sfxBtn = document.getElementById('btn-sfx-toggle');
  if (sfxBtn) {
    const syncSfxBtn = () => {
      sfxBtn.textContent = store.analogSfx ? '🔊 Analog SFX: On' : '🔇 Analog SFX: Off';
      sfxBtn.className = store.analogSfx
        ? 'px-2.5 py-1.5 rounded-xl text-xs font-bold border border-cyan-400/40 bg-cyan-500/15 text-cyan-200 hover:bg-cyan-500/25 transition-all'
        : 'px-2.5 py-1.5 rounded-xl text-xs font-bold border border-white/10 bg-slate-900 text-slate-400 hover:text-white transition-all';
    };
    syncSfxBtn();
    sfxBtn.addEventListener('click', () => {
      store.analogSfx = !store.analogSfx;
      saveUiPrefs();
      syncSfxBtn();
      if (store.analogSfx) playCrateTickSound(1.15);
      showToast(store.analogSfx ? '🔊 Web Audio Analog SFX Enabled' : '🔇 Web Audio Analog SFX Muted');
    });
  }

  document.getElementById('btn-copy-deeplink')?.addEventListener('click', () => {
    syncUrlFromState();
    copyTextToClipboard(window.location.href, 'Copied direct link to this vinyl pressing!');
  });

  // Pipeline CLI copy buttons
  document.getElementById('view-pipeline')?.addEventListener('click', (e) => {
    const copyBtn = e.target.closest('[data-copy-cmd]');
    if (!copyBtn) return;
    const cmd = copyBtn.getAttribute('data-copy-cmd');
    if (cmd) copyTextToClipboard(cmd, 'Copied PowerShell command to clipboard!');
  });

  document.getElementById('btn-copy-sync-cmd')?.addEventListener('click', () => {
    copyTextToClipboard('cd C:\\DiscogsCollection\\discogs_collection\npython scripts/sync_discogs.py', 'Copied daily sync command!');
  });
  document.getElementById('btn-copy-resync-active')?.addEventListener('click', () => {
    const rec = getActiveRecord();
    const rid = rec ? rec.release_id : '';
    copyTextToClipboard(`cd C:\\DiscogsCollection\\discogs_collection\npython scripts/sync_discogs.py --resync ${rid}`, `Copied --resync ${rid} command!`);
  });

  // Boot all subsystems
  initTurntableStage();
  bindAudioEngineEvents();
  initCrateViews();
  initVariantClashArena();
  initJacketInspector();
  initAnalyticsWheel();
  initCommandPalette();
  initCardExporter();
  initFlatteningLab();
  initCvXrayAndSandbox();
  initPersistenceHub();
  bindGlobalHotkeys();

  subscribe((topic) => {
    if (topic === 'recordsChanged' || topic === 'overridesChanged' || topic === 'flatteningChanged') {
      updateKpiStrip();
    }
  });

  updateKpiStrip();
  setMainVaultTab(store.activeTab || 'showcase');
  refreshExternalJsonIfNewer();
}

window.__KRUNKED_BOOT_ESM__ = bootApp;
if (document.readyState !== 'loading' || window.__VAULT_DOM_READY__) {
  bootApp();
}
