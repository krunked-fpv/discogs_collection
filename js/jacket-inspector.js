// KRUNKED // VINYL VAULT v6.0 — 3D Jacket, Back-Cover & Gatefold Inspector + Loupe + CV X-Ray Overlay

import { playCrateTickSound } from './audio-preview.js';
import { drawPolarCvOverlay, formatCvMetricsHtml } from './cv-xray.js';
import {
  clearReleasePressingOverride,
  getActiveRecord,
  pinReleasePressingOverride,
  store,
  subscribe,
} from './store.js';
import {
  buildImgOnErrorAttr,
  escapeHtml,
  formatUsdValue,
  getGalleryImages,
  getVerifiedPressingPhotoUrl,
  safeImageSrc,
} from './utils.js';

let inspRecord = null;
let inspMode = 'flip3d'; // 'flip3d' | 'gatefold' | 'gallery'
let inspSelectedIdx = 0;
let inspFlippedBack = false;
let inspXrayOn = false;
let inspZoom = 1.0;
let inspRotX = 0;
let inspRotY = 0;
let isDragging3D = false;
let dragStartX = 0;
let dragStartY = 0;

function renderInspectorBody() {
  const modal = document.getElementById('jacket-inspector-modal');
  const stageEl = document.getElementById('jacket-inspector-stage');
  const stripEl = document.getElementById('jacket-inspector-strip');
  const metricsEl = document.getElementById('jacket-inspector-metrics');
  if (!modal || !stageEl || !inspRecord) return;

  const gallery = getGalleryImages(inspRecord);
  if (inspSelectedIdx >= gallery.length) inspSelectedIdx = 0;
  const frontImg = gallery[0] || {};
  const backImg = gallery[inspSelectedIdx > 0 ? inspSelectedIdx : (gallery[1] ? 1 : 0)] || frontImg;
  const activeImg = gallery[inspSelectedIdx] || frontImg;
  const verifiedUrl = getVerifiedPressingPhotoUrl(inspRecord, store.userOverrides);

  document.getElementById('jacket-insp-title').textContent = `${inspRecord.artist} — ${inspRecord.title}`;
  document.getElementById('jacket-insp-sub').textContent =
    `#${inspRecord.release_id} • ${inspRecord.label} (${inspRecord.catno}) • ${formatUsdValue(inspRecord)} • ${gallery.length} Gallery Photo${gallery.length === 1 ? '' : 's'}`;

  // Mode pills
  document.querySelectorAll('[data-insp-mode]').forEach((btn) => {
    const act = btn.getAttribute('data-insp-mode') === inspMode;
    btn.className = act
      ? 'px-3 py-1.5 rounded-xl text-xs font-bold bg-cyan-500/25 text-cyan-200 border border-cyan-400/50 transition'
      : 'px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-900 text-slate-300 border border-white/10 hover:text-white transition';
  });

  const xrayBtn = document.getElementById('btn-insp-xray');
  if (xrayBtn) {
    xrayBtn.textContent = inspXrayOn ? '🔬 Polar CV X-Ray: ON' : '🔬 Polar CV X-Ray';
    xrayBtn.className = inspXrayOn
      ? 'px-3 py-1.5 rounded-xl text-xs font-mono-tech font-bold bg-emerald-500/25 text-emerald-200 border border-emerald-400/50 transition'
      : 'px-3 py-1.5 rounded-xl text-xs font-mono-tech font-bold bg-slate-900 text-slate-300 border border-white/10 hover:text-white transition';
  }

  if (inspMode === 'gatefold') {
    const leftIdx = Math.min(inspSelectedIdx, Math.max(0, gallery.length - 1));
    const rightIdx = gallery.length > 1 ? (leftIdx + 1) % gallery.length : leftIdx;
    const leftObj = gallery[leftIdx] || frontImg;
    const rightObj = gallery[rightIdx] || frontImg;

    stageEl.innerHTML = `
      <div class="gatefold-spread grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-w-2xl mx-auto p-3">
        <div class="gatefold-wing-left cv-xray-stage rounded-xl overflow-hidden border border-white/20 bg-slate-950 aspect-square shadow-2xl">
          <img id="insp-img-primary" src="${escapeHtml(safeImageSrc(leftObj.primary_src))}" ${buildImgOnErrorAttr(leftObj.fallback_src)} referrerpolicy="no-referrer" alt="Gatefold Left" class="w-full h-full object-contain bg-slate-950" />
          ${inspXrayOn ? '<canvas id="insp-xray-canvas"></canvas>' : ''}
          <span class="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-black/80 text-[10px] font-mono-tech text-cyan-300">Panel [${leftIdx}]</span>
        </div>
        <div class="gatefold-wing-right rounded-xl overflow-hidden border border-white/20 bg-slate-950 aspect-square shadow-2xl relative">
          <img src="${escapeHtml(safeImageSrc(rightObj.primary_src))}" ${buildImgOnErrorAttr(rightObj.fallback_src)} referrerpolicy="no-referrer" alt="Gatefold Right" class="w-full h-full object-contain bg-slate-950" />
          <span class="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/80 text-[10px] font-mono-tech text-fuchsia-300">Panel [${rightIdx}]</span>
        </div>
      </div>
    `;
  } else if (inspMode === 'gallery') {
    stageEl.innerHTML = `
      <div class="flex flex-col items-center justify-center p-2">
        <div id="insp-loupe-box" class="cv-xray-stage relative w-full max-w-[440px] aspect-square rounded-2xl overflow-hidden border border-white/20 bg-slate-950 shadow-2xl cursor-zoom-in">
          <img id="insp-img-primary" src="${escapeHtml(safeImageSrc(activeImg.primary_src))}" ${buildImgOnErrorAttr(activeImg.fallback_src)} referrerpolicy="no-referrer" alt="Gallery Image" class="w-full h-full object-contain transition-transform duration-150" style="transform: scale(${inspZoom});" />
          ${inspXrayOn ? '<canvas id="insp-xray-canvas"></canvas>' : ''}
          <span class="absolute top-2.5 left-2.5 px-2.5 py-0.5 rounded-full bg-black/80 text-[10px] font-mono-tech font-bold text-cyan-300 border border-white/15">
            Img [${inspSelectedIdx}] • ${inspZoom.toFixed(1)}x Loupe
          </span>
        </div>
      </div>
    `;
  } else {
    // 3D Flip Jacket (0° Front <-> 180° Back / Selected)
    const rotY = (inspFlippedBack ? 180 : 0) + inspRotY;
    stageEl.innerHTML = `
      <div class="jacket-3d-scene flex flex-col items-center justify-center py-2">
        <div id="jacket-3d-card" class="jacket-3d-card w-[290px] h-[290px] sm:w-[370px] sm:h-[370px] cursor-grab active:cursor-grabbing" style="transform: rotateX(${inspRotX}deg) rotateY(${rotY}deg);">
          <div class="jacket-3d-face absolute inset-0 rounded-2xl overflow-hidden border-2 border-white/20 bg-slate-950 shadow-2xl cv-xray-stage">
            <img id="insp-img-front" src="${escapeHtml(safeImageSrc(frontImg.primary_src))}" ${buildImgOnErrorAttr(frontImg.fallback_src)} referrerpolicy="no-referrer" alt="Front Cover" class="w-full h-full object-cover" />
            ${inspXrayOn && !inspFlippedBack ? '<canvas id="insp-xray-canvas"></canvas>' : ''}
            <span class="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-black/80 text-[10px] font-mono-tech text-cyan-300">Front Cover [0]</span>
          </div>
          <div class="jacket-3d-face jacket-3d-back absolute inset-0 rounded-2xl overflow-hidden border-2 border-fuchsia-400/40 bg-slate-950 shadow-2xl cv-xray-stage">
            <img id="insp-img-back" src="${escapeHtml(safeImageSrc(backImg.primary_src))}" ${buildImgOnErrorAttr(backImg.fallback_src)} referrerpolicy="no-referrer" alt="Back / Pressing" class="w-full h-full object-contain bg-slate-950" />
            ${inspXrayOn && inspFlippedBack ? '<canvas id="insp-xray-canvas"></canvas>' : ''}
            <span class="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-black/80 text-[10px] font-mono-tech text-fuchsia-300">Back / Img [${gallery[inspSelectedIdx > 0 ? inspSelectedIdx : (gallery[1] ? 1 : 0)]?.index ?? 0}]</span>
          </div>
        </div>
        <p class="text-[11px] font-mono-tech text-slate-400 mt-3">Drag sleeve in 3D or click <strong class="text-cyan-300">↻ Flip 180°</strong> to inspect back-cover tracklists &amp; wax</p>
      </div>
    `;
  }

  // Draw X-Ray canvas if enabled
  if (inspXrayOn) {
    const imgTarget =
      document.getElementById('insp-img-primary') ||
      (inspFlippedBack ? document.getElementById('insp-img-back') : document.getElementById('insp-img-front'));
    const cvCanvas = document.getElementById('insp-xray-canvas');
    const targetMeta = inspMode === 'flip3d' && !inspFlippedBack ? frontImg : (inspMode === 'flip3d' && inspFlippedBack ? backImg : activeImg);
    if (imgTarget && cvCanvas) {
      const paint = () => drawPolarCvOverlay(cvCanvas, imgTarget, targetMeta?.cv_metrics || null);
      imgTarget.onload = paint;
      if (imgTarget.complete) setTimeout(paint, 30);
    }
  }

  // Gallery thumbnail strip
  if (stripEl) {
    stripEl.innerHTML = gallery
      .map((im, i) => {
        const isSel = i === inspSelectedIdx;
        const isPinned = Boolean(
          verifiedUrl && (verifiedUrl === im.local_uri || verifiedUrl === im.remote_uri)
        );
        return `
          <button type="button" data-insp-thumb="${i}" class="shrink-0 relative rounded-xl overflow-hidden border-2 ${isSel ? 'border-cyan-400 ring-2 ring-cyan-400/30' : 'border-white/15 hover:border-cyan-400/50'} transition">
            <img src="${escapeHtml(safeImageSrc(im.primary_src))}" ${buildImgOnErrorAttr(im.fallback_src)} referrerpolicy="no-referrer" alt="Gallery [${i}]" class="w-16 h-16 object-cover bg-slate-900" />
            <span class="absolute bottom-0 inset-x-0 bg-black/85 text-[9px] font-mono-tech text-center py-0.5 ${isPinned ? 'text-emerald-300 font-bold' : 'text-slate-300'}">
              ${isPinned ? `✓ Pin [${i}]` : `Img [${i}]`}
            </span>
          </button>
        `;
      })
      .join('');
  }

  // Pin button label + CV telemetry readout
  const pinBtn = document.getElementById('btn-insp-pin-pressing');
  if (pinBtn) {
    pinBtn.textContent = `📌 Pin Img [${inspSelectedIdx}] as Verified Pressing`;
  }
  if (metricsEl) {
    metricsEl.innerHTML = formatCvMetricsHtml(activeImg);
  }
}

export function openJacketInspector(rec, startWithXray = false) {
  inspRecord = rec || getActiveRecord();
  if (!inspRecord) return;
  const gallery = getGalleryImages(inspRecord);
  const selIdx = inspRecord.images && typeof inspRecord.images.selected_index === 'number' ? inspRecord.images.selected_index : 0;
  inspSelectedIdx = gallery[selIdx] ? selIdx : 0;
  inspFlippedBack = false;
  inspXrayOn = Boolean(startWithXray);
  inspMode = startWithXray ? 'gallery' : 'flip3d';
  inspZoom = 1.0;
  inspRotX = 0;
  inspRotY = 0;

  const modal = document.getElementById('jacket-inspector-modal');
  if (modal) {
    modal.classList.remove('hidden');
    renderInspectorBody();
  }
}

export function closeJacketInspector() {
  document.getElementById('jacket-inspector-modal')?.classList.add('hidden');
}

export function initJacketInspector() {
  const modal = document.getElementById('jacket-inspector-modal');
  if (!modal) return;

  window.addEventListener('vault:openInspector', (e) => {
    const det = e.detail || {};
    openJacketInspector(det.record, det.xRay);
  });

  subscribe((topic, detail) => {
    if (topic === 'openJacketInspector') {
      openJacketInspector(detail?.record, detail?.xRay);
    }
  });

  document.getElementById('btn-close-inspector')?.addEventListener('click', closeJacketInspector);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeJacketInspector();
  });

  modal.addEventListener('click', (e) => {
    const modeBtn = e.target.closest('[data-insp-mode]');
    if (modeBtn) {
      inspMode = modeBtn.getAttribute('data-insp-mode') || 'flip3d';
      inspZoom = 1.0;
      playCrateTickSound(1.08);
      renderInspectorBody();
      return;
    }
    const thumbBtn = e.target.closest('[data-insp-thumb]');
    if (thumbBtn) {
      inspSelectedIdx = Number(thumbBtn.getAttribute('data-insp-thumb') || 0);
      if (inspMode === 'flip3d') inspFlippedBack = inspSelectedIdx > 0;
      playCrateTickSound(1.1);
      renderInspectorBody();
    }
  });

  document.getElementById('btn-insp-flip')?.addEventListener('click', () => {
    inspMode = 'flip3d';
    inspFlippedBack = !inspFlippedBack;
    inspRotX = 0;
    inspRotY = 0;
    if (inspFlippedBack && inspSelectedIdx === 0 && getGalleryImages(inspRecord).length > 1) {
      inspSelectedIdx = 1;
    }
    playCrateTickSound(1.15);
    renderInspectorBody();
  });

  document.getElementById('btn-insp-xray')?.addEventListener('click', () => {
    inspXrayOn = !inspXrayOn;
    playCrateTickSound(1.2);
    renderInspectorBody();
  });

  document.getElementById('btn-insp-pin-pressing')?.addEventListener('click', () => {
    if (!inspRecord) return;
    const gallery = getGalleryImages(inspRecord);
    const imgObj = gallery[inspSelectedIdx];
    const url = imgObj ? (imgObj.local_uri || imgObj.remote_uri) : '';
    if (url) {
      pinReleasePressingOverride(inspRecord.release_id, url, inspSelectedIdx);
      renderInspectorBody();
    }
  });

  document.getElementById('btn-insp-clear-pin')?.addEventListener('click', () => {
    if (!inspRecord) return;
    clearReleasePressingOverride(inspRecord.release_id);
    renderInspectorBody();
  });

  // 3D drag rotation & Gallery Loupe pan/zoom
  const stageEl = document.getElementById('jacket-inspector-stage');
  stageEl?.addEventListener('pointerdown', (e) => {
    if (inspMode === 'gallery') {
      inspZoom = inspZoom > 1.2 ? 1.0 : 2.3;
      renderInspectorBody();
      return;
    }
    if (inspMode !== 'flip3d') return;
    isDragging3D = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    document.getElementById('jacket-3d-card')?.classList.add('is-dragging');
  });

  window.addEventListener('pointermove', (e) => {
    if (inspMode === 'gallery' && inspZoom > 1.05) {
      const box = document.getElementById('insp-loupe-box');
      const img = document.getElementById('insp-img-primary');
      if (box && img) {
        const rect = box.getBoundingClientRect();
        const px = ((e.clientX - rect.left) / Math.max(1, rect.width)) * 100;
        const py = ((e.clientY - rect.top) / Math.max(1, rect.height)) * 100;
        img.style.transformOrigin = `${Math.max(0, Math.min(100, px))}% ${Math.max(0, Math.min(100, py))}%`;
      }
    }
    if (!isDragging3D) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    inspRotY = Math.max(-55, Math.min(55, inspRotY + dx * 0.45));
    inspRotX = Math.max(-28, Math.min(28, inspRotX - dy * 0.35));
    const card = document.getElementById('jacket-3d-card');
    if (card) {
      const rotY = (inspFlippedBack ? 180 : 0) + inspRotY;
      card.style.transform = `rotateX(${inspRotX}deg) rotateY(${rotY}deg)`;
    }
  });

  window.addEventListener('pointerup', () => {
    if (!isDragging3D) return;
    isDragging3D = false;
    document.getElementById('jacket-3d-card')?.classList.remove('is-dragging');
  });
}
