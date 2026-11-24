// KRUNKED // VINYL VAULT v6.0 — Cmd/Ctrl + K Fuzzy Command & Crate Search Palette

import { playCrateTickSound } from './audio-preview.js';
import { setThumbMode } from './crate-views.js';
import { emit, getActiveRecord, setActiveRecordById, store } from './store.js';
import { toggleBacklight, toggleUvBlacklight, triggerKineticCrateSpin } from './turntable-stage.js';
import { escapeHtml, formatUsdValue, safeCssColor } from './utils.js';

let paletteOpen = false;
let selectedIdx = 0;
let currentResults = [];

function getCommands() {
  return [
    { kind: 'cmd', icon: '🎰', title: 'Spin the Crate (Kinetic Roulette)', sub: 'Spacebar • Random pressing in active pool', run: () => { window.__setMainVaultTab?.('showcase'); triggerKineticCrateSpin(); } },
    { kind: 'cmd', icon: '☀️', title: 'Toggle Hold Up to the Light (Backlight)', sub: 'Shortcut: B • Translucent wax transmission', run: () => toggleBacklight() },
    { kind: 'cmd', icon: '🟣', title: 'Toggle UV 395nm Blacklight', sub: 'Shortcut: U • Fluorescence reactive glow', run: () => toggleUvBlacklight() },
    { kind: 'cmd', icon: '⚔️', title: 'Open Variant Clash Arena', sub: 'Twin-Deck DJ Crossfader, Elo & 32-Seed Brackets', run: () => window.__setMainVaultTab?.('arena') },
    { kind: 'cmd', icon: '🗂️', title: 'Switch to 3D Record Store Bin Flipper', sub: 'Flip front-to-back through upright sleeves', run: () => { window.__setMainVaultTab?.('showcase'); setThumbMode('bin3d'); } },
    { kind: 'cmd', icon: '🌌', title: 'Open Vault Constellation & Wax Wheel', sub: 'Color spectrum, artists, labels & valuation', run: () => window.__setMainVaultTab?.('analytics') },
    { kind: 'cmd', icon: '🔥', title: 'Open Thermal Flattening Lab', sub: '130°F multi-stage timer & arrival queue', run: () => window.__setMainVaultTab?.('flattening') },
    { kind: 'cmd', icon: '📸', title: 'Export "Now Spinning" PNG Studio Card', sub: 'High-res audiophile card of active record', run: () => { const r = getActiveRecord(); if (r) emit('exportNowSpinningCard', r); } },
  ];
}

function scoreMatch(rec, queryTokens) {
  const hay = `${rec.artist || ''} ${rec.title || ''} ${rec.label || ''} ${rec.catno || ''} ${rec.year || ''} ${rec.format_string || ''} ${rec.wax_spec?.variant_badge || ''} ${rec.release_id || ''}`.toLowerCase();
  let score = 0;
  for (const tok of queryTokens) {
    if (!hay.includes(tok)) return -1;
    if ((rec.artist || '').toLowerCase().includes(tok)) score += 35;
    if ((rec.title || '').toLowerCase().includes(tok)) score += 30;
    if ((rec.wax_spec?.color_name || '').toLowerCase().includes(tok)) score += 20;
    score += 10;
  }
  return score;
}

function renderPaletteResults(queryStr) {
  const listEl = document.getElementById('cmd-palette-results');
  if (!listEl) return;
  const q = String(queryStr || '').trim().toLowerCase();
  const tokens = q.split(/\s+/).filter(Boolean);

  const cmds = getCommands().filter((c) => !tokens.length || tokens.every((t) => `${c.title} ${c.sub}`.toLowerCase().includes(t)));
  let recHits = [];
  if (tokens.length) {
    recHits = store.records
      .map((r) => ({ rec: r, score: scoreMatch(r, tokens) }))
      .filter((x) => x.score >= 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 14)
      .map((x) => ({ kind: 'rec', rec: x.rec }));
  } else {
    recHits = store.records.slice(0, 8).map((r) => ({ kind: 'rec', rec: r }));
  }

  currentResults = [...recHits, ...cmds.slice(0, 6)];
  if (selectedIdx >= currentResults.length) selectedIdx = Math.max(0, currentResults.length - 1);

  if (!currentResults.length) {
    listEl.innerHTML = `<div class="p-6 text-center text-xs text-slate-400 font-mono-tech">No matching records or commands for "${escapeHtml(queryStr)}"</div>`;
    return;
  }

  listEl.innerHTML = currentResults
    .map((item, idx) => {
      const sel = idx === selectedIdx ? 'is-selected' : 'border-transparent hover:bg-white/5';
      if (item.kind === 'cmd') {
        return `
          <button type="button" data-cmd-idx="${idx}" class="cmd-palette-item w-full text-left flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl border ${sel} transition">
            <div class="flex items-center gap-3 min-w-0">
              <span class="text-base shrink-0">${item.icon}</span>
              <div class="min-w-0">
                <div class="text-xs font-bold text-white truncate">${escapeHtml(item.title)}</div>
                <div class="text-[10px] font-mono-tech text-slate-400 truncate">${escapeHtml(item.sub)}</div>
              </div>
            </div>
            <span class="text-[10px] font-mono-tech text-cyan-300 shrink-0">COMMAND</span>
          </button>
        `;
      }
      const r = item.rec;
      return `
        <button type="button" data-cmd-idx="${idx}" class="cmd-palette-item w-full text-left flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl border ${sel} transition">
          <div class="flex items-center gap-3 min-w-0">
            <span class="w-4 h-4 rounded-full shrink-0 border border-white/30" style="background:radial-gradient(circle, ${safeCssColor(r.wax_spec?.secondary_color)}, ${safeCssColor(r.wax_spec?.primary_color)})"></span>
            <div class="min-w-0">
              <div class="text-xs font-extrabold text-white truncate">${escapeHtml(r.artist)} — ${escapeHtml(r.title)}</div>
              <div class="text-[10px] font-mono-tech text-slate-400 truncate">${escapeHtml(r.wax_spec?.variant_badge || '12" LP')} • ${escapeHtml(r.label)} (${escapeHtml(r.year || 'LP')})</div>
            </div>
          </div>
          <span class="text-xs font-mono-tech font-bold text-emerald-400 shrink-0">${formatUsdValue(r)}</span>
        </button>
      `;
    })
    .join('');
}

function executePaletteItem(idx, openInspector = false) {
  const item = currentResults[idx];
  if (!item) return;
  closeCommandPalette();
  playCrateTickSound(1.2);
  if (item.kind === 'cmd') {
    item.run();
  } else if (item.kind === 'rec') {
    if (openInspector) {
      window.dispatchEvent(new CustomEvent('vault:openInspector', { detail: { record: item.rec, xRay: false } }));
    } else {
      setActiveRecordById(item.rec.release_id);
      window.__setMainVaultTab?.('showcase');
      if (typeof window.__expandHeroStage === 'function') window.__expandHeroStage();
      else window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }
}

export function openCommandPalette() {
  const modal = document.getElementById('cmd-palette-modal');
  const input = document.getElementById('cmd-palette-input');
  if (!modal || !input) return;
  paletteOpen = true;
  selectedIdx = 0;
  modal.classList.remove('hidden');
  input.value = '';
  renderPaletteResults('');
  setTimeout(() => input.focus(), 20);
}

export function closeCommandPalette() {
  paletteOpen = false;
  document.getElementById('cmd-palette-modal')?.classList.add('hidden');
}

export function isCommandPaletteOpen() {
  return paletteOpen;
}

export function initCommandPalette() {
  const modal = document.getElementById('cmd-palette-modal');
  const input = document.getElementById('cmd-palette-input');

  document.getElementById('btn-cmd-palette')?.addEventListener('click', openCommandPalette);
  modal?.addEventListener('click', (e) => {
    if (e.target === modal) closeCommandPalette();
  });

  input?.addEventListener('input', (e) => {
    selectedIdx = 0;
    renderPaletteResults(e.target.value);
  });

  input?.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIdx = Math.min(Math.max(0, currentResults.length - 1), selectedIdx + 1);
      renderPaletteResults(input.value);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIdx = Math.max(0, selectedIdx - 1);
      renderPaletteResults(input.value);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executePaletteItem(selectedIdx, e.shiftKey);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closeCommandPalette();
    }
  });

  document.getElementById('cmd-palette-results')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-cmd-idx]');
    if (!btn) return;
    executePaletteItem(Number(btn.getAttribute('data-cmd-idx') || 0), e.shiftKey);
  });
}
