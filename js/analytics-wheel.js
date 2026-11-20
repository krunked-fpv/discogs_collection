// KRUNKED // VINYL VAULT v6.0 — Interactive Chromatic Wax Color Wheel & Vault Intelligence Constellation

import { playCrateTickSound } from './audio-preview.js';
import {
  applyFiltersAndSort,
  clearAllCrateFilters,
  setActiveRecordById,
  store,
  subscribe,
} from './store.js';
import {
  escapeHtml,
  formatUsdValue,
  getNumericUsdValue,
  safeCssColor,
  showToast,
} from './utils.js';

let wheelNodes = [];
let hoveredNode = null;

function hexToHsl(hex) {
  const clean = safeCssColor(hex, '#18181b').replace('#', '');
  const r = parseInt(clean.slice(0, 2), 16) / 255;
  const g = parseInt(clean.slice(2, 4), 16) / 255;
  const b = parseInt(clean.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0;
  let s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
  }
  return { h: h * 360, s, l };
}

function drawWaxColorWheel() {
  const canvas = document.getElementById('analytics-wax-wheel');
  if (!canvas || !store.records.length) return;
  const size = Math.min(canvas.parentElement?.clientWidth || 380, 400);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(size * dpr);
  canvas.height = Math.round(size * dpr);
  canvas.style.width = `${size}px`;
  canvas.style.height = `${size}px`;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, size, size);

  const cx = size / 2;
  const cy = size / 2;
  const maxR = size * 0.44;

  // Radial background grid rings
  [0.25, 0.5, 0.75, 1.0].forEach((f) => {
    ctx.beginPath();
    ctx.arc(cx, cy, maxR * f, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1;
    ctx.stroke();
  });

  // Hue spectrum ring outline
  for (let deg = 0; deg < 360; deg += 4) {
    const rad1 = (deg * Math.PI) / 180;
    const rad2 = ((deg + 5) * Math.PI) / 180;
    ctx.beginPath();
    ctx.arc(cx, cy, maxR + 8, rad1, rad2);
    ctx.strokeStyle = `hsla(${deg}, 88%, 60%, 0.55)`;
    ctx.lineWidth = 4;
    ctx.stroke();
  }

  wheelNodes = [];
  store.records.forEach((rec, i) => {
    const wax = rec.wax_spec || {};
    const c1 = safeCssColor(wax.primary_color, '#18181b');
    const c2 = safeCssColor(wax.secondary_color, c1);
    const { h, s } = hexToHsl(c1);
    const jitter = (((Number(rec.release_id || i) * 9301 + 49297) % 233280) / 233280 - 0.5) * 0.16;
    const angle = ((s < 0.08 ? (i * 137.5) % 360 : h) * Math.PI) / 180 + jitter;

    const patRadius =
      wax.pattern === 'black' ? 0.16 :
      wax.pattern === 'translucent' ? 0.34 :
      wax.pattern === 'solid_color' ? 0.52 :
      wax.pattern === 'galaxy' || wax.pattern === 'marble' ? 0.72 :
      0.88;
    const rDist = maxR * Math.max(0.1, Math.min(0.96, patRadius + jitter * 0.5));
    const x = cx + Math.cos(angle) * rDist;
    const y = cy + Math.sin(angle) * rDist;
    const dotR = wax.is_double_lp ? 6.2 : 4.8;

    const isHover = hoveredNode && hoveredNode.rec.release_id === rec.release_id;

    ctx.beginPath();
    ctx.arc(x, y, isHover ? dotR + 3 : dotR, 0, Math.PI * 2);
    ctx.fillStyle = c1;
    ctx.fill();
    ctx.lineWidth = isHover ? 2.5 : 1.3;
    ctx.strokeStyle = isHover ? '#ffffff' : c2;
    ctx.stroke();

    wheelNodes.push({ x, y, r: dotR + 4, rec });
  });

  // Center label
  ctx.font = 'bold 10px "JetBrains Mono", monospace';
  ctx.fillStyle = '#94a3b8';
  ctx.textAlign = 'center';
  ctx.fillText(`${store.records.length} LPs`, cx, cy + 4);
}

function jumpToFilteredCrate({ filter = 'all', artist = '', label = '', year = 0, colorHex = '' } = {}) {
  clearAllCrateFilters(false);
  store.filter = filter;
  store.filterArtist = artist;
  store.filterLabel = label;
  store.filterYear = year;
  store.filterColorHex = colorHex;
  applyFiltersAndSort(true);
  if (typeof window.__setMainVaultTab === 'function') {
    window.__setMainVaultTab('showcase');
  }
  const grid = document.getElementById('collection-grid');
  grid?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export function renderAnalyticsView() {
  const recs = store.records;
  if (!recs.length) return;

  drawWaxColorWheel();

  // 1. Pattern Distribution
  const patCounts = new Map();
  const patLabels = {
    splatter: ['🎨 Splatter', 'splatter'],
    translucent: ['💎 Translucent / Clear', 'translucent'],
    galaxy: ['🌌 Galaxy Nebula', 'galaxy_marble'],
    solid_color: ['🟣 Solid Color', 'all'],
    black: ['⚫ 180g Black', 'black_wax'],
    marble: ['🌀 Marble Swirl', 'galaxy_marble'],
    color_in_color: ['🎯 Color-in-Color', 'splatter'],
    split: ['⚡ Split Wax', 'galaxy_marble'],
  };
  for (const r of recs) {
    const p = r.wax_spec?.pattern || 'black';
    patCounts.set(p, (patCounts.get(p) || 0) + 1);
  }
  const patEl = document.getElementById('analytics-pattern-bars');
  if (patEl) {
    const sortedPats = Array.from(patCounts.entries()).sort((a, b) => b[1] - a[1]);
    patEl.innerHTML = sortedPats
      .map(([pat, cnt]) => {
        const pct = ((cnt / recs.length) * 100).toFixed(1);
        const [lbl, filterKey] = patLabels[pat] || [pat, 'all'];
        return `
          <button type="button" data-ana-filter="${filterKey}" class="w-full text-left group">
            <div class="flex items-center justify-between text-xs mb-1">
              <span class="font-bold text-slate-200 group-hover:text-cyan-300 transition">${escapeHtml(lbl)}</span>
              <span class="font-mono-tech text-slate-400">${cnt} (${pct}%)</span>
            </div>
            <div class="h-2.5 rounded-full bg-slate-950 border border-white/10 overflow-hidden">
              <div class="h-full rounded-full bg-gradient-to-r from-fuchsia-500 to-cyan-400" style="width:${pct}%"></div>
            </div>
          </button>
        `;
      })
      .join('');
  }

  // 2. Top Artist Stacks
  const artCounts = new Map();
  for (const r of recs) artCounts.set(r.artist, (artCounts.get(r.artist) || 0) + 1);
  const topArtists = Array.from(artCounts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 14);
  const artEl = document.getElementById('analytics-artist-stacks');
  if (artEl) {
    artEl.innerHTML = topArtists
      .map(
        ([artist, cnt]) => `
        <button type="button" data-ana-artist="${escapeHtml(artist)}" class="px-3 py-1.5 rounded-xl bg-slate-950 hover:bg-cyan-500/20 border border-white/10 hover:border-cyan-400/50 text-xs flex items-center gap-2 transition">
          <span class="font-bold text-white">${escapeHtml(artist)}</span>
          <span class="px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono-tech font-bold text-[10px]">${cnt}</span>
        </button>
      `
      )
      .join('');
  }

  // 3. Label Constellation
  const lblCounts = new Map();
  for (const r of recs) if (r.label) lblCounts.set(r.label, (lblCounts.get(r.label) || 0) + 1);
  const topLabels = Array.from(lblCounts.entries()).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const lblEl = document.getElementById('analytics-label-leaderboard');
  if (lblEl) {
    lblEl.innerHTML = topLabels
      .map(
        ([label, cnt]) => `
        <button type="button" data-ana-label="${escapeHtml(label)}" class="px-3 py-1.5 rounded-xl bg-slate-950 hover:bg-fuchsia-500/20 border border-white/10 hover:border-fuchsia-400/50 text-xs flex items-center justify-between gap-2 transition">
          <span class="font-semibold text-slate-200 truncate">${escapeHtml(label)}</span>
          <span class="font-mono-tech font-bold text-fuchsia-300 text-[11px]">${cnt}</span>
        </button>
      `
      )
      .join('');
  }

  // 4. Release Year Timeline
  const yrCounts = new Map();
  for (const r of recs) {
    const y = Number(r.year || 0);
    if (y > 1990) yrCounts.set(y, (yrCounts.get(y) || 0) + 1);
  }
  const years = Array.from(yrCounts.entries()).sort((a, b) => a[0] - b[0]);
  const maxYrCnt = Math.max(1, ...years.map((x) => x[1]));
  const yrEl = document.getElementById('analytics-year-timeline');
  if (yrEl) {
    yrEl.innerHTML = years
      .map(([yr, cnt]) => {
        const hPct = Math.max(12, Math.round((cnt / maxYrCnt) * 100));
        return `
          <button type="button" data-ana-year="${yr}" class="flex-1 min-w-[22px] flex flex-col items-center gap-1 group" title="${yr}: ${cnt} pressings">
            <span class="text-[9px] font-mono-tech text-slate-400 group-hover:text-cyan-300">${cnt}</span>
            <div class="w-full h-24 bg-slate-950 rounded-t-md flex items-end overflow-hidden border border-white/5 group-hover:border-cyan-400/50">
              <div class="w-full bg-gradient-to-t from-cyan-600 to-fuchsia-400 rounded-t-sm" style="height:${hPct}%"></div>
            </div>
            <span class="text-[9px] font-mono-tech text-slate-400 -rotate-45 origin-top-left mt-1">${String(yr).slice(2)}</span>
          </button>
        `;
      })
      .join('');
  }

  // 5. Highest-Value Vault Grails
  const topValEl = document.getElementById('analytics-top-grails');
  if (topValEl) {
    const grails = recs.slice().sort((a, b) => getNumericUsdValue(b) - getNumericUsdValue(a)).slice(0, 8);
    topValEl.innerHTML = grails
      .map(
        (r, i) => `
        <button type="button" data-ana-spin="${r.release_id}" class="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-slate-950 hover:bg-slate-900 border border-white/10 hover:border-emerald-400/40 text-left transition">
          <div class="flex items-center gap-2.5 min-w-0">
            <span class="text-[11px] font-mono-tech font-bold text-slate-500">#${i + 1}</span>
            <span class="w-3 h-3 rounded-full shrink-0 border border-white/30" style="background:${safeCssColor(r.wax_spec?.primary_color)}"></span>
            <div class="min-w-0">
              <div class="text-xs font-bold text-white truncate">${escapeHtml(r.artist)} — ${escapeHtml(r.title)}</div>
              <div class="text-[10px] font-mono-tech text-slate-400 truncate">${escapeHtml(r.wax_spec?.variant_badge || 'LP')}</div>
            </div>
          </div>
          <span class="text-xs font-mono-tech font-black text-emerald-400 shrink-0">${formatUsdValue(r)}</span>
        </button>
      `
      )
      .join('');
  }
}

export function initAnalyticsWheel() {
  const canvas = document.getElementById('analytics-wax-wheel');
  const tipEl = document.getElementById('analytics-wheel-tooltip');

  canvas?.addEventListener('pointermove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    let found = null;
    let bestD = 999;
    for (const n of wheelNodes) {
      const d = Math.hypot(n.x - x, n.y - y);
      if (d <= n.r + 3 && d < bestD) {
        bestD = d;
        found = n;
      }
    }
    hoveredNode = found;
    drawWaxColorWheel();
    if (tipEl) {
      if (found) {
        const r = found.rec;
        tipEl.textContent = `${r.artist} — ${r.title} (${r.wax_spec?.color_name || 'Wax'}) • ${formatUsdValue(r)} • Click to Spin`;
      } else {
        tipEl.textContent = 'Hover any wax node to inspect; click a node to spin on Turntable Stage.';
      }
    }
  });

  canvas?.addEventListener('click', () => {
    if (!hoveredNode) return;
    playCrateTickSound(1.15);
    setActiveRecordById(hoveredNode.rec.release_id);
    if (typeof window.__setMainVaultTab === 'function') window.__setMainVaultTab('showcase');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  document.getElementById('view-analytics')?.addEventListener('click', (e) => {
    const fBtn = e.target.closest('[data-ana-filter]');
    if (fBtn) {
      playCrateTickSound(1.1);
      jumpToFilteredCrate({ filter: fBtn.getAttribute('data-ana-filter') || 'all' });
      showToast('Filtered Crate by Variant Pattern');
      return;
    }
    const aBtn = e.target.closest('[data-ana-artist]');
    if (aBtn) {
      const artist = aBtn.getAttribute('data-ana-artist') || '';
      playCrateTickSound(1.1);
      jumpToFilteredCrate({ artist });
      showToast(`Filtered Crate to ${artist}`);
      return;
    }
    const lBtn = e.target.closest('[data-ana-label]');
    if (lBtn) {
      const label = lBtn.getAttribute('data-ana-label') || '';
      playCrateTickSound(1.1);
      jumpToFilteredCrate({ label });
      showToast(`Filtered Crate to ${label}`);
      return;
    }
    const yBtn = e.target.closest('[data-ana-year]');
    if (yBtn) {
      const year = Number(yBtn.getAttribute('data-ana-year') || 0);
      playCrateTickSound(1.1);
      jumpToFilteredCrate({ year });
      showToast(`Filtered Crate to ${year} pressings`);
      return;
    }
    const sBtn = e.target.closest('[data-ana-spin]');
    if (sBtn) {
      setActiveRecordById(Number(sBtn.getAttribute('data-ana-spin')));
      if (typeof window.__setMainVaultTab === 'function') window.__setMainVaultTab('showcase');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });

  subscribe((topic) => {
    if (topic === 'recordsChanged' && store.activeTab === 'analytics') {
      renderAnalyticsView();
    }
  });

  renderAnalyticsView();
}
