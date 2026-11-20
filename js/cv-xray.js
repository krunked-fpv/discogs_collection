// KRUNKED // VINYL VAULT v6.0 — Deterministic Polar CV X-Ray Overlay & parse_wax_variant Live Sandbox

import {
  getActiveRecord,
  store,
  subscribe,
} from './store.js';
import {
  buildImgOnErrorAttr,
  escapeHtml,
  getGalleryImages,
  parseWaxVariantJS,
  renderCrateWaxDiscHTML,
  safeImageSrc,
} from './utils.js';

/**
 * Draws deterministic polar concentric rings & 4 diagonal corner masks from `detect_pressing_image.py`
 * directly onto an overlay <canvas> matching the loaded release image.
 */
export function drawPolarCvOverlay(canvas, imgEl, cvMetrics = null) {
  if (!canvas || !imgEl) return;
  const w = canvas.clientWidth || imgEl.clientWidth || 420;
  const h = canvas.clientHeight || imgEl.clientHeight || 420;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2;
  const half = Math.min(w, h) / 2;
  const rDisc = Number(cvMetrics?.detected_disc_radius || 0.96);
  const isPass = cvMetrics ? Boolean(cvMetrics.is_pressing) : false;

  // 1. 4-Quadrant Diagonal Corner Masks (|sin(2θ)| > 0.55 avoids 0/90/180/270 square borders)
  ctx.save();
  for (let q = 0; q < 4; q++) {
    const startAngle = q * (Math.PI / 2) + 0.36;
    const endAngle = (q + 1) * (Math.PI / 2) - 0.36;
    ctx.beginPath();
    ctx.arc(cx, cy, half * Math.min(1.32, rDisc + 0.22), startAngle, endAngle);
    ctx.arc(cx, cy, half * (rDisc + 0.035), endAngle, startAngle, true);
    ctx.closePath();
    ctx.fillStyle = 'rgba(245, 158, 11, 0.14)';
    ctx.fill();
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.55)';
    ctx.stroke();
  }
  ctx.restore();

  // 2. Outer 12" Disc Rim + ±0.024 Radial Gradient Scan Band
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, half * rDisc, 0, Math.PI * 2);
  ctx.lineWidth = Math.max(2, half * 0.048);
  ctx.strokeStyle = isPass ? 'rgba(16, 185, 129, 0.26)' : 'rgba(244, 63, 94, 0.26)';
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(cx, cy, half * rDisc, 0, Math.PI * 2);
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = isPass ? '#10b981' : '#f43f5e';
  ctx.stroke();
  ctx.restore();

  // 3. 4" Center-Label Boundary Step (r ≈ 0.333) + 8-Octant Rays
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, half * 0.333, 0, Math.PI * 2);
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#d946ef';
  ctx.stroke();

  for (let oct = 0; oct < 8; oct++) {
    const ang = (oct * Math.PI) / 4;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(ang) * half * 0.34, cy + Math.sin(ang) * half * 0.34);
    ctx.lineTo(cx + Math.cos(ang) * half * (rDisc - 0.04), cy + Math.sin(ang) * half * (rDisc - 0.04));
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(34, 211, 238, 0.38)';
    ctx.stroke();
  }
  ctx.restore();

  // 4. Center Spindle Hole Target (r ≈ 0.045)
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, half * 0.045, 0, Math.PI * 2);
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#22d3ee';
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(cx - 12, cy);
  ctx.lineTo(cx + 12, cy);
  ctx.moveTo(cx, cy - 12);
  ctx.lineTo(cx, cy + 12);
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = '#22d3ee';
  ctx.stroke();
  ctx.restore();

  // 5. Ring Telemetry Callouts
  ctx.save();
  ctx.font = 'bold 10px "JetBrains Mono", monospace';
  ctx.fillStyle = '#22d3ee';
  ctx.fillText('SPINDLE r=0.045', cx + 12, cy - 6);
  ctx.fillStyle = '#f0abfc';
  ctx.fillText('4" LABEL r=0.333', cx + half * 0.24, cy - half * 0.25);
  ctx.fillStyle = isPass ? '#34d399' : '#fb7185';
  ctx.fillText(`12" RIM r=${rDisc.toFixed(2)}`, 10, 18);
  ctx.fillStyle = '#fcd34d';
  ctx.fillText('DIAG CORNER MASKS', 10, h - 10);
  ctx.restore();
}

export function formatCvMetricsHtml(imgMeta) {
  const m = imgMeta?.cv_metrics;
  if (!m) {
    return `<div class="text-[11px] font-mono-tech text-slate-400">Role: <strong class="text-slate-200">${escapeHtml(imgMeta?.role || 'front_cover')}</strong> • Polar rings overlaid at standard 12" geometry (r=0.045 / 0.333 / 0.96).</div>`;
  }
  const pass = Boolean(m.is_pressing);
  return `
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono-tech">
      <div class="p-2 rounded-lg bg-slate-950 border ${pass ? 'border-emerald-500/40' : 'border-rose-500/40'}">
        <span class="text-slate-400 block text-[9px]">VERDICT</span>
        <span class="font-bold ${pass ? 'text-emerald-300' : 'text-rose-300'}">${pass ? '✓ PRESSING' : '✕ REJECTED'} (${Number(m.score || 0).toFixed(3)})</span>
      </div>
      <div class="p-2 rounded-lg bg-slate-950 border border-white/10">
        <span class="text-slate-400 block text-[9px]">RIM / QUADS</span>
        <span class="text-cyan-300 font-bold">r=${Number(m.detected_disc_radius || 0.96).toFixed(2)} • ${m.active_diagonal_quadrants ?? 0}/4 Q</span>
      </div>
      <div class="p-2 rounded-lg bg-slate-950 border border-white/10">
        <span class="text-slate-400 block text-[9px]">SPINDLE / LABEL</span>
        <span class="text-fuchsia-300 font-bold">sp=${Number(m.spindle_contrast || 0).toFixed(2)} • Δ=${Number(m.label_wax_dist || 0).toFixed(2)}</span>
      </div>
      <div class="p-2 rounded-lg bg-slate-950 border border-white/10">
        <span class="text-slate-400 block text-[9px]">REASON</span>
        <span class="text-amber-300 truncate block" title="${escapeHtml(m.reason || '')}">${escapeHtml(m.reason || 'deterministic')}</span>
      </div>
    </div>
  `;
}

// =========================================================================
// Pipeline Tab: Polar CV X-Ray Inspector & parse_wax_variant Sandbox
// =========================================================================
let xrayImgIndex = 0;

export function renderPipelineCvXrayPanel() {
  const rec = getActiveRecord() || store.records[0];
  if (!rec) return;
  const gallery = getGalleryImages(rec);
  if (xrayImgIndex >= gallery.length) xrayImgIndex = 0;
  const imgObj = gallery[xrayImgIndex] || gallery[0];

  const titleEl = document.getElementById('cv-xray-active-label');
  if (titleEl) {
    titleEl.textContent = `#${rec.release_id} • ${rec.artist} — ${rec.title} (${gallery.length} gallery frames)`;
  }

  const thumbsEl = document.getElementById('cv-xray-thumbs');
  if (thumbsEl) {
    thumbsEl.innerHTML = gallery
      .map((im, i) => {
        const pass = im.cv_metrics?.is_pressing;
        const border = i === xrayImgIndex
          ? 'border-cyan-400 ring-2 ring-cyan-400/30'
          : (pass ? 'border-emerald-500/50' : 'border-white/15');
        return `
          <button type="button" data-xray-idx="${i}" class="shrink-0 relative rounded-lg overflow-hidden border-2 ${border} transition">
            <img src="${escapeHtml(safeImageSrc(im.primary_src))}" ${buildImgOnErrorAttr(im.fallback_src)} referrerpolicy="no-referrer" alt="Img ${i}" class="w-12 h-12 object-cover bg-slate-900" />
            <span class="absolute bottom-0 inset-x-0 bg-black/80 text-[8px] font-mono-tech text-center ${pass ? 'text-emerald-300' : 'text-slate-300'}">[${i}]</span>
          </button>
        `;
      })
      .join('');
  }

  const imgEl = document.getElementById('cv-xray-preview-img');
  const canvasEl = document.getElementById('cv-xray-overlay-canvas');
  const metricsEl = document.getElementById('cv-xray-metrics-bar');
  if (imgEl && imgObj) {
    const redraw = () => {
      if (canvasEl) drawPolarCvOverlay(canvasEl, imgEl, imgObj.cv_metrics || null);
    };
    imgEl.onload = redraw;
    imgEl.src = safeImageSrc(imgObj.primary_src);
    if (imgEl.complete) redraw();
  }
  if (metricsEl && imgObj) {
    metricsEl.innerHTML = formatCvMetricsHtml(imgObj);
  }
}

export function updateSandboxPreview() {
  const fmtEl = document.getElementById('sandbox-format-input');
  const notesEl = document.getElementById('sandbox-notes-input');
  const jsonOut = document.getElementById('sandbox-json-output');
  const discPrev = document.getElementById('sandbox-disc-preview');
  const badgePrev = document.getElementById('sandbox-badge-preview');
  if (!fmtEl || !notesEl || !jsonOut || !discPrev || !badgePrev) return;

  const spec = parseWaxVariantJS(fmtEl.value, notesEl.value, 777);
  jsonOut.textContent = JSON.stringify(spec, null, 2);
  badgePrev.textContent = spec.variant_badge;
  discPrev.innerHTML = renderCrateWaxDiscHTML(
    { release_id: 0, _synthetic: true, artist: 'KRUNKED', title: 'SANDBOX', year: 2026, catno: 'TEST-01', wax_spec: spec, images: {} },
    176,
    false
  );
}

export function initCvXrayAndSandbox() {
  document.getElementById('sandbox-format-input')?.addEventListener('input', updateSandboxPreview);
  document.getElementById('sandbox-notes-input')?.addEventListener('input', updateSandboxPreview);
  document.getElementById('btn-sandbox-preset')?.addEventListener('click', () => {
    const presets = [
      ['LP, Album, Ltd, Cle', 'Sealed Clear w/ Yellow and Purple Splatter'],
      ['2xLP, Album, Ltd, Ruby With Black Splatter', '3 Dot Recordings Exclusive'],
      ['LP, Ltd, Mil', '2022 RED IN CLEAR VERSION, AUTOGRAPHED ON FRONT COVER'],
      ['LP, Ltd, Neo + LP, S/Sided, Etch, Ltd, Neo', 'Banquet Neon Highlighter Etched 2xLP'],
    ];
    const pick = presets[Math.floor(Math.random() * presets.length)];
    const fmtEl = document.getElementById('sandbox-format-input');
    const notesEl = document.getElementById('sandbox-notes-input');
    if (fmtEl) fmtEl.value = pick[0];
    if (notesEl) notesEl.value = pick[1];
    updateSandboxPreview();
  });

  document.getElementById('cv-xray-thumbs')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-xray-idx]');
    if (!btn) return;
    xrayImgIndex = Number(btn.getAttribute('data-xray-idx') || 0);
    renderPipelineCvXrayPanel();
  });

  subscribe((topic) => {
    if (topic === 'activeRecordChanged' || topic === 'recordsChanged') {
      xrayImgIndex = 0;
      renderPipelineCvXrayPanel();
    }
  });

  updateSandboxPreview();
  renderPipelineCvXrayPanel();
}
