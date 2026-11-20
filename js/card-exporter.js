// KRUNKED // VINYL VAULT v6.0 — High-Res "Now Spinning" & Tournament Champion Trophy Card PNG Studio

import { subscribe } from './store.js';
import {
  formatUsdValue,
  getCoverUrls,
  getPressingPhotoUrls,
  safeCssColor,
  safeImageSrc,
  showToast,
} from './utils.js';

function loadCanvasImage(candidates) {
  const urls = candidates.map((u) => safeImageSrc(u)).filter(Boolean);
  return new Promise((resolve) => {
    let idx = 0;
    const tryNext = () => {
      if (idx >= urls.length) {
        resolve(null);
        return;
      }
      const url = urls[idx++];
      const img = new Image();
      if (/^https?:\/\//i.test(url)) img.crossOrigin = 'anonymous';
      img.referrerPolicy = 'no-referrer';
      img.onload = () => resolve(img);
      img.onerror = () => tryNext();
      img.src = url;
    };
    tryNext();
  });
}

function drawRoundedRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawProceduralDiscOnCanvas(ctx, cx, cy, radius, wax, coverImg) {
  const c1 = safeCssColor(wax.primary_color, '#18181b');
  const c2 = safeCssColor(wax.secondary_color, '#3f3f46');
  const c3 = safeCssColor(wax.accent_color, '#06b6d4');

  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.clip();

  const g = ctx.createRadialGradient(cx, cy, radius * 0.1, cx, cy, radius);
  g.addColorStop(0, c2);
  g.addColorStop(0.65, c1);
  g.addColorStop(1, '#05060b');
  ctx.fillStyle = g;
  ctx.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);

  if (wax.pattern === 'splatter' || wax.pattern === 'color_in_color') {
    const seed = Number(wax.deterministic_seed || 12345);
    for (let i = 0; i < 32; i++) {
      const a = ((seed + i * 47) % 360) * (Math.PI / 180);
      const len = radius * (0.45 + ((seed + i * 19) % 48) / 100);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(a) * len, cy + Math.sin(a) * len);
      ctx.lineWidth = i % 3 === 0 ? 7 : 3.5;
      ctx.lineCap = 'round';
      ctx.strokeStyle = i % 3 === 0 ? c3 : c2;
      ctx.globalAlpha = 0.8;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  } else if (wax.pattern === 'split') {
    ctx.beginPath();
    ctx.arc(cx, cy, radius, -Math.PI / 2, Math.PI / 2);
    ctx.fillStyle = c2;
    ctx.fill();
  }

  // Microgrooves
  for (let r = radius * 0.38; r < radius * 0.96; r += 8) {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // Center label
  const lblR = radius * 0.333;
  ctx.beginPath();
  ctx.arc(cx, cy, lblR, 0, Math.PI * 2);
  ctx.save();
  ctx.clip();
  if (coverImg) {
    ctx.drawImage(coverImg, cx - lblR, cy - lblR, lblR * 2, lblR * 2);
  } else {
    ctx.fillStyle = '#111524';
    ctx.fillRect(cx - lblR, cy - lblR, lblR * 2, lblR * 2);
  }
  ctx.restore();
  ctx.strokeStyle = c3;
  ctx.lineWidth = 3;
  ctx.stroke();

  // Spindle hole
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.042, 0, Math.PI * 2);
  ctx.fillStyle = '#05060b';
  ctx.fill();
  ctx.strokeStyle = '#cbd5e1';
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();
}

function wrapLines(ctx, text, maxWidth) {
  const words = String(text || '').split(/\s+/);
  const lines = [];
  let line = '';
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = w;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines.slice(0, 2);
}

async function generateVaultCardPng(rec, championMeta = null) {
  if (!rec) return;
  const W = 1200;
  const H = 1500;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const wax = rec.wax_spec || {};
  const c1 = safeCssColor(wax.primary_color, '#8b2cf5');
  const c2 = safeCssColor(wax.secondary_color, '#06b6d4');
  const c3 = safeCssColor(wax.accent_color, '#f43f5e');

  // Obsidian brushed card background + wax glow
  ctx.fillStyle = '#05060b';
  ctx.fillRect(0, 0, W, H);

  const g1 = ctx.createRadialGradient(280, 320, 40, 280, 320, 560);
  g1.addColorStop(0, `${c1}55`);
  g1.addColorStop(1, 'transparent');
  ctx.fillStyle = g1;
  ctx.fillRect(0, 0, W, H);

  const g2 = ctx.createRadialGradient(920, 620, 40, 920, 620, 560);
  g2.addColorStop(0, `${c2}44`);
  g2.addColorStop(1, 'transparent');
  ctx.fillStyle = g2;
  ctx.fillRect(0, 0, W, H);

  // Outer machined chassis border
  drawRoundedRect(ctx, 40, 40, W - 80, H - 80, 42);
  ctx.strokeStyle = championMeta ? 'rgba(251, 191, 36, 0.7)' : 'rgba(255, 255, 255, 0.14)';
  ctx.lineWidth = championMeta ? 4 : 2;
  ctx.stroke();

  // Top Header Tag
  ctx.font = 'bold 26px "JetBrains Mono", monospace';
  ctx.fillStyle = championMeta ? '#fbbf24' : '#22d3ee';
  ctx.fillText(
    championMeta
      ? `👑 TOURNAMENT CHAMPION • ${championMeta.seedSize}-SEED BRACKET`
      : '● NOW SPINNING // KRUNKED VINYL VAULT',
    92,
    118
  );

  if (championMeta) {
    ctx.font = 'bold 22px "JetBrains Mono", monospace';
    ctx.fillStyle = '#f0abfc';
    ctx.fillText(`${championMeta.presetLabel} • ELO ${championMeta.elo}`, 92, 156);
  }

  // Load real local cover & pressing photos
  const covUrls = getCoverUrls(rec);
  const pressUrls = getPressingPhotoUrls(rec, {});
  const [coverImg, pressImg] = await Promise.all([
    loadCanvasImage([covUrls.primary, covUrls.fallback]),
    loadCanvasImage([pressUrls.primary, pressUrls.fallback]),
  ]);

  // Disc peeking right (drawn first behind jacket)
  const discCx = 825;
  const discCy = 520;
  const discR = 250;
  if (pressImg) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(discCx, discCy, discR, 0, Math.PI * 2);
    ctx.clip();
    ctx.drawImage(pressImg, discCx - discR, discCy - discR, discR * 2, discR * 2);
    ctx.restore();
    ctx.beginPath();
    ctx.arc(discCx, discCy, discR, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.28)';
    ctx.lineWidth = 4;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(discCx, discCy, 14, 0, Math.PI * 2);
    ctx.fillStyle = '#05060b';
    ctx.fill();
  } else {
    drawProceduralDiscOnCanvas(ctx, discCx, discCy, discR, wax, coverImg);
  }

  // Jacket sleeve left
  const covX = 115;
  const covY = 230;
  const covSize = 560;
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.85)';
  ctx.shadowBlur = 45;
  ctx.shadowOffsetX = 18;
  drawRoundedRect(ctx, covX, covY, covSize, covSize, 26);
  ctx.fillStyle = '#0f172a';
  ctx.fill();
  ctx.clip();
  if (coverImg) {
    ctx.drawImage(coverImg, covX, covY, covSize, covSize);
  }
  ctx.restore();
  drawRoundedRect(ctx, covX, covY, covSize, covSize, 26);
  ctx.strokeStyle = 'rgba(255,255,255,0.22)';
  ctx.lineWidth = 3;
  ctx.stroke();

  // Variant Pill
  const badgeText = wax.variant_badge || '12" LP';
  ctx.font = 'bold 26px "JetBrains Mono", monospace';
  const badgeW = Math.min(W - 184, ctx.measureText(badgeText).width + 52);
  drawRoundedRect(ctx, 92, 870, badgeW, 56, 28);
  ctx.fillStyle = `${c1}38`;
  ctx.fill();
  ctx.strokeStyle = c3;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = '#f8fafc';
  ctx.fillText(badgeText, 118, 907);

  // Title & Artist
  ctx.font = '900 58px Inter, sans-serif';
  ctx.fillStyle = '#ffffff';
  const titleLines = wrapLines(ctx, rec.title || 'Album', W - 184);
  let textY = 1005;
  for (const ln of titleLines) {
    ctx.fillText(ln, 92, textY);
    textY += 68;
  }

  ctx.font = '800 38px Inter, sans-serif';
  ctx.fillStyle = '#22d3ee';
  ctx.fillText(`${rec.artist || 'Artist'} (${rec.year || 'LP'})`, 92, textY + 12);

  // Telemetry Grid Box
  drawRoundedRect(ctx, 92, 1170, W - 184, 195, 24);
  ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.font = 'bold 21px "JetBrains Mono", monospace';
  ctx.fillStyle = '#94a3b8';
  ctx.fillText('LABEL & CATALOG #', 130, 1218);
  ctx.fillText('GRADE & EST. VALUE', 640, 1218);

  ctx.font = 'bold 28px Inter, sans-serif';
  ctx.fillStyle = '#f8fafc';
  ctx.fillText(`${rec.label || 'Independent'} • ${rec.catno || 'LP'}`.slice(0, 32), 130, 1262);
  ctx.fillStyle = '#34d399';
  ctx.fillText(`${(rec.media_condition || 'NM').split('(')[0].trim()} • ${formatUsdValue(rec)}`, 640, 1262);

  ctx.font = '20px "JetBrains Mono", monospace';
  ctx.fillStyle = '#cbd5e1';
  ctx.fillText(`Discogs #${rec.release_id} • ${String(rec.format_string || '').slice(0, 66)}`, 130, 1324);

  // Footer
  ctx.font = 'bold 20px "JetBrains Mono", monospace';
  ctx.fillStyle = '#64748b';
  ctx.fillText('krunked-fpv/discogs_collection • AT-LP70XBT + AT-VMN95ML', 92, 1418);

  canvas.toBlob((blob) => {
    if (!blob) {
      showToast('Could not generate PNG card in this browser.');
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = championMeta
      ? `krunked-champion-${rec.release_id}.png`
      : `krunked-now-spinning-${rec.release_id}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(championMeta ? '🏆 Downloaded Tournament Champion Trophy Card PNG!' : '📸 Downloaded "Now Spinning" PNG Studio Card!');
  }, 'image/png');
}

export function initCardExporter() {
  subscribe((topic, detail) => {
    if (topic === 'exportNowSpinningCard' && detail) {
      generateVaultCardPng(detail, null);
    } else if (topic === 'exportChampionTrophyCard' && detail && detail.record) {
      generateVaultCardPng(detail.record, detail);
    }
  });
}
