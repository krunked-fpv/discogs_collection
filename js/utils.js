// KRUNKED // VINYL VAULT v6.0 — Core Utilities, Valuation, Zero-Stock Asset Resolvers & Wax Parser

export const DEFAULT_FLATTENING_STATUS = 'Need to be done';

export const VERIFIED_PRICE_FALLBACKS = Object.freeze({
  22031968: 59.99,
  12988109: 35.0,
  27611781: 45.0,
  27717681: 25.0,
  38854575: 45.0,
  26047519: 55.0,
  27079776: 55.0,
  9346527: 39.98,
  27927123: 29.0,
});

export function safeGetStorage(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function safeSetStorage(key, val) {
  try {
    localStorage.setItem(key, val);
  } catch {
    // Ignore quota/sandbox storage restrictions
  }
}

export function safeRemoveStorage(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    // Ignore storage restrictions
  }
}

export function escapeHtml(val) {
  return String(val ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function safeExternalUrl(url, fallback = '#') {
  const s = String(url || '').trim();
  return /^https?:\/\//i.test(s) ? s : fallback;
}

export function safeImageSrc(url) {
  const s = String(url || '').trim();
  if (!s) return '';
  if (/^(?:assets\/pressings\/|procedural:\/\/)/i.test(s)) return '';
  return /^(?:https?:\/\/|assets\/|\.\/assets\/|blob:|data:image\/png)/i.test(s) ? s : '';
}

export function safeCssColor(val, fallback = '#18181b') {
  const s = String(val || '').trim();
  return /^#[0-9a-fA-F]{3,8}$/.test(s) ? s : fallback;
}

export function safeJsonForScript(obj, indent = 2) {
  return JSON.stringify(obj, null, indent)
    .replace(/<\//g, '<\\/')
    .replace(/<!--/g, '\\u003c!--')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}

/**
 * Single authoritative USD valuation helper shared across Stage, Crate Cards, 3D Bin, Arena & Analytics.
 */
export function getNumericUsdValue(rec) {
  if (!rec) return 35.0;
  const raw = Number(rec.estimated_value_usd);
  if (Number.isFinite(raw) && raw > 0) return raw;
  const rid = Number(rec.release_id);
  if (rid && Object.prototype.hasOwnProperty.call(VERIFIED_PRICE_FALLBACKS, rid)) {
    return VERIFIED_PRICE_FALLBACKS[rid];
  }
  return 35.0;
}

export function formatUsdValue(rec) {
  return `$${getNumericUsdValue(rec).toFixed(2)}`;
}

export function cleanArtistName(artistStr) {
  return String(artistStr || '').replace(/\s*\(\d+\)\s*$/g, '').trim();
}

export function cleanSearchTitle(titleStr) {
  const s = String(titleStr || '')
    .replace(/∆/g, 'A')
    .replace(/\bln\b/g, 'In')
    .replace(/\[([^\]]{1,2})\]/g, '$1')
    .replace(/\s*\((?:remake|reissue|repress|deluxe[^)]*|anniversary[^)]*|instrumentals?|live[^)]*|edition[^)]*|tour collection)\)/gi, '')
    .replace(/\s*:\s*(?:reloaded|definitive)\b/gi, '')
    .replace(/\bRepented\.?$/i, '')
    .replace(/[•●|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return s || String(titleStr || '').replace(/[\[\]]/g, '').trim();
}

export function normalizeAlbumGroupKey(artist, title) {
  const a = cleanArtistName(artist).toLowerCase().replace(/[^a-z0-9]+/g, '');
  const t = cleanSearchTitle(title)
    .toLowerCase()
    .replace(/\bthe\b|\ba\b|\ban\b/g, '')
    .replace(/[^a-z0-9]+/g, '');
  return `${a}::${t}`;
}

export function formatMillisToDuration(ms) {
  if (!ms || Number.isNaN(ms) || ms <= 0) return '';
  const totalSec = Math.round(ms / 1000);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

export function parseDurationToSeconds(durStr) {
  if (!durStr) return 215;
  const parts = String(durStr).trim().split(':').map(Number);
  if (parts.length === 2 && !Number.isNaN(parts[0]) && !Number.isNaN(parts[1])) {
    return parts[0] * 60 + parts[1];
  }
  return 215;
}

export function formatDurationHms(ms) {
  const totalSec = Math.max(0, Math.ceil(ms / 1000));
  const hrs = Math.floor(totalSec / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

/**
 * Resolves cover art URLs prioritizing local same-origin assets/releases/<rid>/cover.jpg.
 */
export function getCoverUrls(rec) {
  if (!rec || rec._synthetic) return { primary: '', fallback: '' };
  const ridNum = Number(rec.release_id || 0);
  const rid = ridNum > 0 ? String(ridNum) : '';
  const imgs = rec.images || {};
  const classified = Array.isArray(imgs.classified_images) ? imgs.classified_images : [];
  const localFromList = classified[0] ? safeImageSrc(classified[0].local_uri) : '';
  const localC = safeImageSrc(imgs.local_cover_image_url) || localFromList || (rid ? `assets/releases/${rid}/cover.jpg` : '');
  const remoteC = safeImageSrc(imgs.cover_image_url) || (classified[0] ? safeImageSrc(classified[0].uri) : '');
  const primary = localC || remoteC;
  const fallback = remoteC && remoteC !== primary ? remoteC : '';
  return { primary, fallback };
}

export function getRealCoverUrl(rec) {
  const { primary, fallback } = getCoverUrls(rec);
  return primary || fallback || '';
}

export function getCenterLabelArtUrl(rec) {
  const { primary, fallback } = getCoverUrls(rec);
  const imgs = (rec && rec.images) || {};
  return primary || safeImageSrc(imgs.center_label_image_url) || fallback || '';
}

/**
 * Resolves verified pressing photo URLs, honoring user overrides and rejecting stock vinyl placeholders.
 */
export function getPressingPhotoUrls(rec, userOverrides = {}) {
  if (!rec) return { primary: '', fallback: '' };
  const rid = String(rec.release_id);
  const imgs = rec.images || {};
  const classified = Array.isArray(imgs.classified_images) ? imgs.classified_images : [];

  if (userOverrides && userOverrides[rid]) {
    const ovEntry = userOverrides[rid];
    const ovUrl = typeof ovEntry === 'object' ? (ovEntry.uri || ovEntry.local_uri || '') : String(ovEntry);
    const matched = classified.find(
      (im) =>
        im.uri === ovUrl ||
        im.local_uri === ovUrl ||
        (typeof ovEntry === 'object' && im.index === ovEntry.pressing_image_index)
    );
    const safeMatchedLocal = matched ? safeImageSrc(matched.local_uri) : '';
    const safeMatchedRemote = matched ? safeImageSrc(matched.uri) : '';
    const safeOv = safeImageSrc(ovUrl);
    if (safeMatchedLocal) {
      return { primary: safeMatchedLocal, fallback: safeMatchedRemote || safeOv };
    }
    if (safeOv) {
      return { primary: safeOv, fallback: safeImageSrc(imgs.remote_pressing_image_url || imgs.pressing_image_url) || safeOv };
    }
  }

  const localP = safeImageSrc(imgs.local_pressing_image_url);
  const pressP = imgs.has_pressing_photo ? safeImageSrc(imgs.pressing_image_url) : '';
  const remoteP = safeImageSrc(imgs.remote_pressing_image_url) || (pressP.startsWith('http') ? pressP : '');

  const primary = localP || pressP;
  const fallback = remoteP || (pressP !== primary ? pressP : '');
  return { primary, fallback };
}

export function getVerifiedPressingPhotoUrl(rec, userOverrides = {}) {
  const { primary, fallback } = getPressingPhotoUrls(rec, userOverrides);
  return primary || fallback || '';
}

export function getGalleryImages(rec) {
  if (!rec || !rec.images) return [];
  const rid = String(rec.release_id);
  const rawList = Array.isArray(rec.images.classified_images) ? rec.images.classified_images : [];
  if (rawList.length) {
    return rawList.map((im, idx) => {
      const i = typeof im.index === 'number' ? im.index : idx;
      const localUri = safeImageSrc(im.local_uri) || `assets/releases/${rid}/img_${i}.jpg`;
      const remoteUri = safeImageSrc(im.uri || im.uri150 || '');
      const primarySrc = localUri || remoteUri;
      const fallbackSrc = remoteUri && remoteUri !== primarySrc ? remoteUri : '';
      return {
        ...im,
        index: i,
        local_uri: localUri,
        remote_uri: remoteUri,
        primary_src: primarySrc,
        fallback_src: fallbackSrc,
      };
    });
  }
  const { primary, fallback } = getCoverUrls(rec);
  if (!primary && !fallback) return [];
  return [
    {
      index: 0,
      role: 'front_cover',
      local_uri: primary,
      remote_uri: fallback,
      primary_src: primary,
      fallback_src: fallback,
      width: 600,
      height: 600,
    },
  ];
}

export function buildImgOnErrorAttr(fallbackUrl, primaryUrl = '') {
  const fb = safeImageSrc(fallbackUrl);
  if (!fb || (primaryUrl && fb === safeImageSrc(primaryUrl))) return '';
  return `onerror="this.onerror=null;if(this.dataset.fb){this.src=this.dataset.fb;}" data-fb="${escapeHtml(fb)}"`;
}

/**
 * Mirrors detect_pressing_image.py `parse_wax_variant()` deterministically in browser JS.
 */
export function parseWaxVariantJS(formatStr, notesStr = '', releaseId = 0) {
  const extractRelevantNotes = (comments) => {
    if (!comments) return '';
    const lines = String(comments).split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    const thisLines = lines.filter((ln) => /\(\s*this\s*\)/i.test(ln));
    return thisLines.length ? thisLines.join(' ') : String(comments);
  };

  const filteredComments = extractRelevantNotes(notesStr);
  const fmtLower = String(formatStr || '').toLowerCase();
  const combined = `${formatStr || ''} ${filteredComments}`.trim();
  const lower = combined.toLowerCase();

  const colorMap = {
    pur: ['#8b2cf5', 'Purple', true],
    purple: ['#8b2cf5', 'Purple', true],
    purplish: ['#8b2cf5', 'Purple', true],
    vio: ['#6d28d9', 'Violet', true],
    violet: ['#6d28d9', 'Violet', true],
    pin: ['#ec4899', 'Hot Pink', false],
    pink: ['#ec4899', 'Hot Pink', false],
    mag: ['#d946ef', 'Magenta', true],
    magenta: ['#d946ef', 'Magenta', true],
    ora: ['#f97316', 'Translucent Orange', true],
    orange: ['#f97316', 'Translucent Orange', true],
    pea: ['#fb923c', 'Peach Opaque', false],
    peach: ['#fb923c', 'Peach Opaque', false],
    yel: ['#eab308', 'Yellow', true],
    yellow: ['#eab308', 'Yellow', true],
    can: ['#facc15', 'Canary Yellow', false],
    canary: ['#facc15', 'Canary Yellow', false],
    gold: ['#d97706', 'Metallic Gold', false],
    amber: ['#d97706', 'Amber Translucent', true],
    gre: ['#10b981', 'Emerald Green', true],
    green: ['#10b981', 'Emerald Green', true],
    olive: ['#65a30d', 'Olive Green', false],
    aci: ['#84cc16', 'Acid Green', true],
    acid: ['#84cc16', 'Acid Green', true],
    neo: ['#ccff00', 'Neon Highlighter', true],
    neon: ['#ccff00', 'Neon Highlighter', true],
    blu: ['#2563eb', 'Cobalt Blue', true],
    blue: ['#2563eb', 'Cobalt Blue', true],
    ele: ['#06b6d4', 'Electric Blue', true],
    electric: ['#06b6d4', 'Electric Blue', true],
    cyan: ['#06b6d4', 'Cyan', true],
    teal: ['#0d9488', 'Teal', true],
    turquoise: ['#06b6d4', 'Turquoise', true],
    aqua: ['#06b6d4', 'Aqua', true],
    lig: ['#38bdf8', 'Light Sky Blue', true],
    cle: ['#cbd5e1', 'Crystal Clear', true],
    clear: ['#cbd5e1', 'Crystal Clear', true],
    ult: ['#e2e8f0', 'Ultra Clear', true],
    mil: ['#f1f5f9', 'Milky Clear', true],
    milk: ['#f1f5f9', 'Milky Clear', true],
    milky: ['#f1f5f9', 'Milky Clear', true],
    gho: ['#94a3b8', 'Ghostly Clear', true],
    ghost: ['#94a3b8', 'Ghostly Clear', true],
    ghostly: ['#94a3b8', 'Ghostly Smoke', true],
    smoke: ['#64748b', 'Translucent Smoke', true],
    smoky: ['#64748b', 'Translucent Smoke', true],
    smokey: ['#64748b', 'Translucent Smoke', true],
    cok: ['#5eead4', 'Coke Bottle Clear', true],
    coke: ['#5eead4', 'Coke Bottle Clear', true],
    whi: ['#f8fafc', 'Opaque White', false],
    white: ['#f8fafc', 'Opaque White', false],
    bone: ['#fef3c7', 'Bone White', false],
    cream: ['#fef3c7', 'Cream White', false],
    tan: ['#d6d3d1', 'Tan Translucent', true],
    gra: ['#64748b', 'Graphite Grey', false],
    grey: ['#64748b', 'Graphite Grey', false],
    gray: ['#64748b', 'Graphite Grey', false],
    sil: ['#94a3b8', 'Metallic Silver', false],
    silver: ['#94a3b8', 'Metallic Silver', false],
    dus: ['#a8a29e', 'Dusty Smoke', true],
    dust: ['#a8a29e', 'Dusty Smoke', true],
    dusk: ['#a8a29e', 'Dusk Ripple', true],
    hou: ['#3b82f6', 'House Blue/Cyan Swirl', true],
    gal: ['#4f46e5', 'Galaxy Nebula', true],
    galaxy: ['#4f46e5', 'Galaxy Nebula', true],
    blood: ['#dc2626', 'Blood Pool Red', true],
    oxblood: ['#9f1239', 'Oxblood Red', true],
    red: ['#dc2626', 'Crimson Red', true],
    crimson: ['#dc2626', 'Crimson Red', true],
    ruby: ['#e11d48', 'Ruby Red', true],
    burgundy: ['#9f1239', 'Burgundy Red', true],
    maroon: ['#881337', 'Maroon Red', false],
    bla: ['#18181b', '180g Audiophile Black', false],
    black: ['#18181b', '180g Audiophile Black', false],
  };

  const matched = [];
  const seenHex = new Set();
  const pushMatch = (hex, name, trans) => {
    if (!seenHex.has(hex)) {
      matched.push([hex, name, trans]);
      seenHex.add(hex);
    }
  };

  if (lower.includes('blood pool')) {
    pushMatch('#dc2626', 'Blood Pool Red', true);
    pushMatch('#f8fafc', 'Ghostly White', true);
  } else if (lower.includes('ghostly black')) {
    pushMatch('#18181b', 'Ghostly Black', true);
    pushMatch('#94a3b8', 'Ghostly Smoke', true);
  }

  const tokens = fmtLower.split(/[,()+/:\s\[\]-]+/).filter(Boolean);
  for (const tok of tokens) {
    if (colorMap[tok]) {
      const [hex, name, trans] = colorMap[tok];
      pushMatch(hex, name, trans);
    }
  }

  const colorWords = [
    [/\bblood\s+pool\b/, '#dc2626', 'Blood Pool Red', true],
    [/\bmilky\s+in\s+clear\b/, '#f1f5f9', 'Milky in Clear', true],
    [/\b(?:red(?:dish)?|blood)\b/, '#dc2626', 'Crimson Red', true],
    [/\bruby\b/, '#e11d48', 'Ruby Red', true],
    [/\b(?:burgundy|maroon|oxblood)\b/, '#9f1239', 'Burgundy Red', true],
    [/\bpurp(?:le|lish)\b/, '#8b2cf5', 'Purple', true],
    [/\bviolet\b/, '#6d28d9', 'Violet', true],
    [/\byellow(?:ish)?\b/, '#facc15', 'Yellow', true],
    [/\bpink(?:ish)?\b/, '#ec4899', 'Hot Pink', false],
    [/\bmagenta\b/, '#d946ef', 'Magenta', true],
    [/\b(?:cyan|turquoise|aqua)\b/, '#06b6d4', 'Cyan', true],
    [/\bblu(?:e|ish)\b/, '#2563eb', 'Electric Blue', true],
    [/\bgreen(?:ish)?\b/, '#10b981', 'Emerald Green', true],
    [/\bolive\b/, '#65a30d', 'Olive Green', false],
    [/\borange\b/, '#f97316', 'Translucent Orange', true],
    [/\bghost(?:ly)?\b/, '#94a3b8', 'Ghostly Smoke', true],
    [/\bsmok(?:e|y|ey)\b/, '#64748b', 'Translucent Smoke', true],
    [/\bmilky\b/, '#f1f5f9', 'Milky Clear', true],
    [/\bclear\b/, '#cbd5e1', 'Crystal Clear', true],
    [/\bwhite\b/, '#f8fafc', 'Opaque White', false],
    [/\b(?:bone|cream)\b/, '#fef3c7', 'Bone White', false],
    [/\b(?:gold|amber)\b/, '#eab308', 'Metallic Gold', false],
    [/\bsilver\b/, '#94a3b8', 'Silver', false],
    [/\bblack\b/, '#18181b', '180g Audiophile Black', false],
  ];

  for (const [rx, hex, label, trans] of colorWords) {
    if (rx.test(fmtLower)) pushMatch(hex, label, trans);
  }
  if (matched.length < 2 && filteredComments) {
    const notesLow = filteredComments.toLowerCase();
    for (const [rx, hex, label, trans] of colorWords) {
      if (rx.test(notesLow)) pushMatch(hex, label, trans);
    }
  }
  if (!matched.length) pushMatch('#18181b', '180g Audiophile Black', false);

  const [c1, primaryName, isTrans] = matched[0];
  let c2;
  if (matched.length >= 2) c2 = matched[1][0];
  else if (c1 === '#18181b') c2 = '#3f3f46';
  else if (['#cbd5e1', '#e2e8f0', '#f1f5f9', '#f8fafc', '#94a3b8'].includes(c1)) c2 = '#38bdf8';
  else c2 = '#18181b';

  const c3 = matched.length >= 3
    ? matched[2][0]
    : (!['#dc2626', '#e11d48', '#ec4899'].includes(c1) ? '#f43f5e' : '#facc15');

  const etched = /\betch/.test(lower);
  const patRx = /splatter|starburst|blood pool|in clear|color-in-color|ripple|\b(gal|galaxy|nebula|dus|dust|dusk|gho|ghost|ghostly|smoke|smoky|smokey|cloudy|glitter|starlight|swirl|marb|marble|hou|aci|acid|split|smash|twister|flip|neo|neon|fun dip)\b/;
  const patSrc = patRx.test(fmtLower) ? fmtLower : lower;

  let pattern = 'solid_color';
  if (/splatter|starburst|blood pool/.test(patSrc)) pattern = 'splatter';
  else if (/in clear|color-in-color|milky in clear|bone in|pink in|black in|red in|ripple/.test(patSrc)) pattern = 'color_in_color';
  else if (/\b(gal|galaxy|nebula|dus|dust|dusk|gho|ghost|ghostly|smoke|smoky|smokey|cloudy|glitter|starlight)\b/.test(patSrc)) pattern = 'galaxy';
  else if (/\b(swirl|marb|marble|hou|aci|acid)\b/.test(patSrc)) pattern = 'marble';
  else if (/\b(split|smash|twister|flip|neo|neon|fun dip)\b/.test(patSrc)) pattern = 'split';
  else if (isTrans || /\b(cle|ult|mil|cok|clear|translucent)\b/.test(patSrc)) pattern = 'translucent';
  else if (c1 === '#18181b') pattern = 'black';

  const is2lp = lower.includes('2xlp') || lower.includes('2x12') || lower.includes('2xvinyl') || lower.includes('+ lp') || lower.includes('+ vinyl');
  const isLtd = lower.includes('ltd') || lower.includes('limited');
  const isRepress = /\b(rp|re|reissue|repress)\b/.test(lower);

  const parts = [is2lp ? '2xLP' : '12" LP'];
  if (matched.length > 1 && matched[1][1] !== primaryName && matched[1][0] !== '#18181b') {
    parts.push(`${primaryName} + ${matched[1][1]}`);
  } else {
    parts.push(primaryName);
  }
  if (pattern === 'splatter') parts.push('Splatter');
  else if (pattern === 'galaxy') parts.push('Galaxy');
  else if (pattern === 'color_in_color') parts.push('Color-in-Color');
  else if (pattern === 'marble') parts.push('Marble Swirl');
  else if (pattern === 'split') parts.push('Split Swirl');
  if (etched) parts.push('Etched Side');
  if (isLtd) parts.push('Ltd Ed');

  return {
    pattern,
    primary_color: c1,
    secondary_color: c2,
    accent_color: c3,
    color_name: primaryName,
    translucent: Boolean(isTrans),
    etched,
    is_double_lp: is2lp,
    is_limited: isLtd,
    is_repress: isRepress,
    variant_badge: parts.join(' • '),
    deterministic_seed: Math.abs(Number(releaseId || 12345) * 2654435761) % 100000000,
  };
}

let svgCounter = 0;

/**
 * Lightweight DOM/SVG vinyl disc renderer for 159+ Crate Cards, Flattening rows & Bin previews.
 * Strictly renders verified local/Discogs pressing photos OR deterministic procedural wax_spec.
 */
export function renderCrateWaxDiscHTML(rec, sizePx = 140, allowVerifiedPressingPhoto = true, userOverrides = {}) {
  const wax = (rec && rec.wax_spec) || {};
  const c1 = safeCssColor(wax.primary_color, '#18181b');
  const c2 = safeCssColor(wax.secondary_color, '#3f3f46');
  const c3 = safeCssColor(wax.accent_color, '#06b6d4');
  const pattern = wax.pattern || 'black';
  const seed = Math.abs(Number(wax.deterministic_seed || (rec && rec.release_id) || 12345));

  if (allowVerifiedPressingPhoto) {
    const { primary, fallback } = getPressingPhotoUrls(rec, userOverrides);
    const activeUrl = safeImageSrc(primary) || safeImageSrc(fallback);
    if (activeUrl) {
      const onErrAttr = (fallback && fallback !== activeUrl) ? buildImgOnErrorAttr(fallback) : '';
      return `
        <div class="relative w-full h-full rounded-full overflow-hidden shadow-2xl border border-white/25 bg-slate-950 select-none">
          <img src="${escapeHtml(activeUrl)}" ${onErrAttr} loading="lazy" decoding="async" referrerpolicy="no-referrer" alt="${escapeHtml(rec.artist)} - ${escapeHtml(rec.title)} pressing" class="w-full h-full object-cover rounded-full" />
          <div class="absolute inset-0 rounded-full ring-1 ring-inset ring-white/20 pointer-events-none" style="background: radial-gradient(circle, transparent 60%, rgba(0,0,0,0.28) 95%, rgba(255,255,255,0.18) 100%);"></div>
          <div class="absolute inset-[47.5%] rounded-full bg-[#05060a]/95 border border-white/35 pointer-events-none"></div>
        </div>
      `;
    }
  }

  svgCounter += 1;
  const uid = `wax-${String((rec && rec.release_id) || 0).replace(/[^a-zA-Z0-9_-]/g, '')}-${sizePx}-${svgCounter}`;
  const centerArt = getCoverUrls(rec);
  const centerArtUrl = safeImageSrc(centerArt.primary) || safeImageSrc(centerArt.fallback);

  let raysSvg = '';
  for (let i = 0; i < 24; i++) {
    const angle = (seed + i * 47) % 360;
    const len = 28 + ((seed + i * 13) % 18);
    const col = i % 3 === 0 ? c3 : c2;
    const width = i % 4 === 0 ? 2.1 : 1.2;
    raysSvg += `<line x1="50" y1="50" x2="${50 + len * Math.cos((angle * Math.PI) / 180)}" y2="${50 + len * Math.sin((angle * Math.PI) / 180)}" stroke="${col}" stroke-width="${width}" stroke-linecap="round" opacity="0.82" />`;
  }

  let patternLayer = '';
  if (pattern === 'splatter') {
    patternLayer = `<g>${raysSvg}</g>`;
  } else if (pattern === 'color_in_color') {
    patternLayer = `<circle cx="50" cy="50" r="33" fill="${c2}" opacity="0.74" />${raysSvg}`;
  } else if (pattern === 'split') {
    patternLayer = `<path d="M50,2 A48,48 0 0,1 50,98 Z" fill="${c2}" opacity="0.9" />`;
  } else if (pattern === 'galaxy' || pattern === 'marble') {
    patternLayer = `
      <ellipse cx="44" cy="46" rx="40" ry="26" transform="rotate(${seed % 180} 50 50)" fill="${c2}" opacity="0.65" />
      <ellipse cx="56" cy="54" rx="34" ry="20" transform="rotate(${(seed * 3) % 180} 50 50)" fill="${c3}" opacity="0.45" />
    `;
  }

  const etchedRing = wax.etched
    ? `<circle cx="50" cy="50" r="34" fill="none" stroke="rgba(226,232,240,0.45)" stroke-width="0.9" stroke-dasharray="2.4 1.6" />`
    : '';

  const initials = escapeHtml(
    ((rec && rec.artist) || 'LP')
      .split(/\s+/)
      .map((w) => w[0] || '')
      .join('')
      .slice(0, 3)
      .toUpperCase()
  );

  return `
    <div class="relative w-full h-full rounded-full overflow-hidden select-none">
      <svg viewBox="0 0 100 100" class="w-full h-full rounded-full shadow-inner">
        <defs>
          <radialGradient id="${uid}-grad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="${c2}" />
            <stop offset="55%" stop-color="${c1}" />
            <stop offset="94%" stop-color="${c1}" />
            <stop offset="100%" stop-color="#050508" />
          </radialGradient>
          <clipPath id="${uid}-clip">
            <circle cx="50" cy="50" r="48" />
          </clipPath>
        </defs>
        <g clip-path="url(#${uid}-clip)">
          <circle cx="50" cy="50" r="48" fill="url(#${uid}-grad)" />
          ${patternLayer}
          ${etchedRing}
          <circle cx="50" cy="50" r="44" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="0.35" />
          <circle cx="50" cy="50" r="39" fill="none" stroke="rgba(0,0,0,0.38)" stroke-width="0.45" />
          <circle cx="50" cy="50" r="34" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="0.35" />
          <circle cx="50" cy="50" r="28" fill="none" stroke="rgba(0,0,0,0.38)" stroke-width="0.45" />
          <circle cx="50" cy="50" r="23" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="0.35" />
          <circle cx="50" cy="50" r="16.8" fill="#11131c" stroke="${c3}" stroke-width="0.7" />
          <text x="50" y="45" text-anchor="middle" fill="#e2e8f0" font-size="4.2" font-weight="800" font-family="Inter, sans-serif">${initials}</text>
          <text x="50" y="57.5" text-anchor="middle" fill="#94a3b8" font-size="3.1" font-family="JetBrains Mono, monospace">${escapeHtml((rec && rec.year) || '')}</text>
          <circle cx="50" cy="50" r="2.2" fill="#05060a" stroke="#cbd5e1" stroke-width="0.4" />
        </g>
        <circle cx="50" cy="50" r="48" fill="none" stroke="rgba(255,255,255,0.22)" stroke-width="0.8" />
      </svg>
      ${
        centerArtUrl
          ? `
        <div class="absolute inset-[33.5%] rounded-full overflow-hidden border border-white/30 shadow-inner pointer-events-none">
          <img src="${escapeHtml(centerArtUrl)}" ${buildImgOnErrorAttr(centerArt.fallback, centerArtUrl)} loading="lazy" decoding="async" referrerpolicy="no-referrer" alt="" class="w-full h-full object-cover" />
          <div class="absolute inset-[42%] rounded-full bg-[#07080c] border border-slate-300/70"></div>
        </div>
      `
          : ''
      }
    </div>
  `;
}

export function renderJacketSleeveHTML(rec, extraClass = '') {
  const { primary, fallback } = getCoverUrls(rec);
  const coverUrl = safeImageSrc(primary) || safeImageSrc(fallback);
  if (coverUrl) {
    const onErrAttr = fallback && fallback !== coverUrl ? buildImgOnErrorAttr(fallback) : '';
    return `
      <div class="relative w-full h-full rounded-xl overflow-hidden border border-white/20 bg-slate-950 shadow-xl select-none ${extraClass}">
        <img src="${escapeHtml(coverUrl)}" ${onErrAttr} loading="lazy" decoding="async" referrerpolicy="no-referrer" alt="${escapeHtml(rec.artist)} - ${escapeHtml(rec.title)}" class="w-full h-full object-cover" />
      </div>
    `;
  }
  const wax = (rec && rec.wax_spec) || {};
  const c1 = safeCssColor(wax.primary_color, '#6d28d9');
  const c2 = safeCssColor(wax.secondary_color, '#06b6d4');
  const c3 = safeCssColor(wax.accent_color, '#f43f5e');
  return `
    <div class="relative w-full h-full rounded-xl overflow-hidden border border-white/15 p-3 flex flex-col justify-between select-none ${extraClass}"
         style="background: linear-gradient(135deg, #0f121d 0%, ${c1}44 55%, ${c2}55 100%);">
      <div class="relative z-10 flex items-center justify-between gap-1">
        <span class="px-1.5 py-0.5 rounded text-[9px] font-mono-tech uppercase bg-black/60 text-slate-300 border border-white/10 truncate max-w-[70%]">${escapeHtml(rec.label || '')}</span>
        <span class="text-[9px] font-mono-tech text-slate-400">${escapeHtml(rec.year || '')}</span>
      </div>
      <div class="relative z-10 my-auto py-2">
        <div class="w-8 h-0.5 mb-1.5" style="background:${c3}"></div>
        <div class="text-xs font-black uppercase tracking-tight text-white leading-snug line-clamp-2">${escapeHtml(rec.artist || '')}</div>
        <div class="text-[11px] font-semibold text-slate-200 leading-tight mt-0.5 line-clamp-2">${escapeHtml(rec.title || '')}</div>
      </div>
      <div class="relative z-10 flex items-center justify-between text-[9px] font-mono-tech text-slate-300 border-t border-white/10 pt-1.5">
        <span class="truncate max-w-[65%]">${escapeHtml(rec.catno && rec.catno !== 'none' ? rec.catno : 'LP')}</span>
        <span class="text-cyan-300">#${escapeHtml(rec.release_id)}</span>
      </div>
    </div>
  `;
}

// =========================================================================
// Toast, Clipboard & 60fps Particle Engine
// =========================================================================
let toastTimer = null;

export function showToast(msg) {
  const el = document.getElementById('toast-banner');
  if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 3600);
}

export function copyTextToClipboard(text, successMsg) {
  if (!text) return;
  const fallbackCopy = () => {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      showToast(ok ? successMsg : 'Copy blocked by browser — select and copy manually.');
    } catch {
      showToast('Copy unavailable in this browser.');
    }
  };
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    navigator.clipboard.writeText(text).then(() => showToast(successMsg)).catch(fallbackCopy);
  } else {
    fallbackCopy();
  }
}

const fxParticles = [];
let fxAnimRunning = false;

export function initParticleCanvas() {
  const fxCanvas = document.getElementById('fx-particles-canvas');
  if (!fxCanvas) return;
  const resize = () => {
    fxCanvas.width = window.innerWidth;
    fxCanvas.height = window.innerHeight;
  };
  window.addEventListener('resize', resize);
  resize();
}

function tickParticles() {
  const fxCanvas = document.getElementById('fx-particles-canvas');
  const fxCtx = fxCanvas ? fxCanvas.getContext('2d') : null;
  if (!fxCtx || !fxCanvas) {
    fxAnimRunning = false;
    return;
  }
  fxCtx.clearRect(0, 0, fxCanvas.width, fxCanvas.height);
  for (let i = fxParticles.length - 1; i >= 0; i--) {
    const p = fxParticles[i];
    p.x += p.vx;
    p.y += p.vy;
    p.vy += 0.24;
    p.rotation += p.vRot;
    p.alpha -= p.decay;
    if (p.alpha <= 0) {
      fxParticles.splice(i, 1);
    } else {
      fxCtx.save();
      fxCtx.globalAlpha = p.alpha;
      fxCtx.translate(p.x, p.y);
      fxCtx.rotate(p.rotation);
      fxCtx.fillStyle = p.color;
      fxCtx.shadowColor = p.color;
      fxCtx.shadowBlur = 9;
      fxCtx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.68);
      fxCtx.restore();
    }
  }
  if (fxParticles.length > 0) {
    requestAnimationFrame(tickParticles);
  } else {
    fxAnimRunning = false;
    fxCtx.clearRect(0, 0, fxCanvas.width, fxCanvas.height);
  }
}

export function spawnParticles(c1, c2, c3, count = 64, originEl = null) {
  const fxCanvas = document.getElementById('fx-particles-canvas');
  if (!fxCanvas) return;
  let cx = window.innerWidth * 0.5;
  let cy = window.innerHeight * 0.4;
  if (originEl) {
    const rect = originEl.getBoundingClientRect();
    if (rect.width > 0) {
      cx = rect.left + rect.width / 2;
      cy = rect.top + rect.height / 2;
    }
  } else {
    const plinth = document.getElementById('turntable-plinth-box');
    if (plinth) {
      const rect = plinth.getBoundingClientRect();
      if (rect.width > 0) {
        cx = rect.left + rect.width / 2;
        cy = rect.top + rect.height / 2;
      }
    }
  }
  const palette = [c1 || '#d946ef', c2 || '#06b6d4', c3 || '#facc15', '#38bdf8', '#ffffff'];
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = 3.2 + Math.random() * 10.5;
    fxParticles.push({
      x: cx,
      y: cy,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 2.6,
      size: 4 + Math.random() * 6,
      color: palette[i % palette.length],
      alpha: 1,
      decay: 0.015 + Math.random() * 0.014,
      rotation: Math.random() * Math.PI * 2,
      vRot: (Math.random() - 0.5) * 0.28,
    });
  }
  if (!fxAnimRunning) {
    fxAnimRunning = true;
    requestAnimationFrame(tickParticles);
  }
}
