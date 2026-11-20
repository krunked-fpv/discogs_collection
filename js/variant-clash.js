// KRUNKED // VINYL VAULT v6.0 — Twin-Deck Variant Clash Arena, DJ Crossfader, 4 Battle Modes & S/A/B/C Tier Matrix

import {
  applyArenaCrossfade,
  auditionArenaDeck,
  dualDropArenaDecks,
  isArenaAudioPlaying,
  playCrateTickSound,
  playNeedleDropSound,
  playRouletteWinChord,
  stopArenaAudio,
} from './audio-preview.js';
import {
  STORAGE_KEYS,
  emit,
  getEloStats,
  recordEloMatchResult,
  setActiveRecordById,
  store,
  subscribe,
} from './store.js';
import {
  escapeHtml,
  formatUsdValue,
  getNumericUsdValue,
  getVerifiedPressingPhotoUrl,
  normalizeAlbumGroupKey,
  renderJacketSleeveHTML,
  safeCssColor,
  safeGetStorage,
  safeSetStorage,
  showToast,
  spawnParticles,
} from './utils.js';
import { WebGLWaxDiscRenderer } from './wax-shaders.js';

let deckARenderer = null;
let deckBRenderer = null;
let arenaRafId = null;
let arenaLastTime = performance.now();
let angleA = 0;
let angleB = 0;
let omegaA = 3.49;
let omegaB = 3.49;
let targetOmegaA = 3.49;
let targetOmegaB = 3.49;
let winnerGlowA = 0;
let winnerGlowB = 0;
let voteCooldown = false;
let arenaBacklightOn = false;

const BRACKET_PRESETS = [
  { id: 'open', label: '🌐 Full Vault Open' },
  { id: 'splatter', label: '🎨 Splatter Wars' },
  { id: 'galaxy_marble', label: '🌌 Galaxy, Marble & Swirl' },
  { id: 'clear_cic', label: '💎 Crystal Clear & Color-in-Color' },
  { id: 'label_wars', label: '🏷️ Label Wars (Sumerian vs SharpTone vs UNFD...)' },
  { id: 'era_clash', label: '⏳ 2000s/10s Classics vs 2020s Heavyweights' },
  { id: 'deluxe_etched', label: '✨ Etched & 2xLP Deluxe Heavyweights' },
  { id: 'high_roller', label: '💰 $50+ High-Roller Grails' },
];

function getRecordById(rid) {
  const num = Number(rid);
  return store.records.find((r) => Number(r.release_id) === num) || null;
}

function shuffleCopy(arr) {
  const copy = arr.slice();
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

// =========================================================================
// Dynamic Vault Scanners: Artist Stacks (3+) & Twin-Variant Same-Album Duels
// =========================================================================
export function getArtistStacks(minCount = 3) {
  const counts = new Map();
  for (const r of store.records) {
    const art = String(r.artist || '').trim();
    if (!art) continue;
    counts.set(art, (counts.get(art) || 0) + 1);
  }
  return Array.from(counts.entries())
    .filter(([, c]) => c >= minCount)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([artist, count]) => ({ artist, count }));
}

export function getTwinVariantGroups() {
  const groups = new Map();
  for (const r of store.records) {
    const key = normalizeAlbumGroupKey(r.artist, r.title);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }
  return Array.from(groups.entries())
    .filter(([, list]) => list.length >= 2)
    .map(([key, list]) => ({
      key,
      label: `${list[0].artist} — ${list[0].title.trim()} (${list.length} variants)`,
      records: list,
    }))
    .sort((a, b) => b.records.length - a.records.length || a.label.localeCompare(b.label));
}

function getPoolForPreset(presetId) {
  const all = store.records.slice();
  if (presetId === 'splatter') {
    return all.filter((r) => r.wax_spec?.pattern === 'splatter');
  }
  if (presetId === 'galaxy_marble') {
    return all.filter((r) => ['galaxy', 'marble', 'split'].includes(r.wax_spec?.pattern || ''));
  }
  if (presetId === 'clear_cic') {
    return all.filter((r) => r.wax_spec?.pattern === 'color_in_color' || r.wax_spec?.translucent);
  }
  if (presetId === 'label_wars') {
    const topLabels = new Set([
      'Sumerian Records', 'SharpTone', '3 Dot Recordings', 'UNFD',
      'Fearless Records', 'Century Media', 'Equal Vision Records', 'Pure Noise Records',
    ]);
    return all.filter((r) => topLabels.has(r.label));
  }
  if (presetId === 'era_clash') {
    return all.filter((r) => Number(r.year || 0) > 0);
  }
  if (presetId === 'deluxe_etched') {
    return all.filter((r) => r.wax_spec?.etched || r.wax_spec?.is_double_lp);
  }
  if (presetId === 'high_roller') {
    return all.filter((r) => getNumericUsdValue(r) >= 50);
  }
  return all;
}

// =========================================================================
// Tournament Bracket Builder (8 / 16 / 32 Seeds)
// =========================================================================
function buildNewBracket(presetId, requestedSize) {
  let pool = getPoolForPreset(presetId);
  if (pool.length < 4) pool = store.records.slice();

  let actualSize = Number(requestedSize || 8);
  while (actualSize > pool.length && actualSize > 4) {
    actualSize = Math.floor(actualSize / 2);
  }
  actualSize = Math.max(4, Math.min(32, actualSize));

  let seeded = [];
  if (presetId === 'era_clash') {
    const classics = shuffleCopy(pool.filter((r) => Number(r.year) < 2020));
    const modern = shuffleCopy(pool.filter((r) => Number(r.year) >= 2020));
    const half = Math.floor(actualSize / 2);
    const leftPick = classics.slice(0, half);
    const rightPick = modern.slice(0, half);
    // Pair Classics vs Modern in Round 1
    for (let i = 0; i < Math.min(leftPick.length, rightPick.length); i++) {
      seeded.push(leftPick[i], rightPick[i]);
    }
    const used = new Set(seeded.map((r) => r.release_id));
    for (const extra of shuffleCopy(pool)) {
      if (seeded.length >= actualSize) break;
      if (!used.has(extra.release_id)) {
        seeded.push(extra);
        used.add(extra.release_id);
      }
    }
  } else if (presetId === 'label_wars') {
    // Interleave different labels so Round 1 clashes pit rival labels head-to-head
    const byLabel = new Map();
    for (const r of shuffleCopy(pool)) {
      if (!byLabel.has(r.label)) byLabel.set(r.label, []);
      byLabel.get(r.label).push(r);
    }
    const queues = Array.from(byLabel.values());
    while (seeded.length < actualSize && queues.some((q) => q.length > 0)) {
      for (const q of queues) {
        if (q.length && seeded.length < actualSize) seeded.push(q.shift());
      }
    }
  } else {
    seeded = shuffleCopy(pool).slice(0, actualSize);
  }

  const seedIds = seeded.map((r) => Number(r.release_id));
  const roundsCount = Math.round(Math.log2(seedIds.length));
  const rounds = [];
  let matchesInRound = seedIds.length / 2;
  for (let r = 0; r < roundsCount; r++) {
    rounds.push(new Array(matchesInRound).fill(0));
    matchesInRound = Math.max(1, matchesInRound / 2);
  }

  const bracket = {
    preset: presetId,
    size: seedIds.length,
    seeds: seedIds,
    rounds,
    curRound: 0,
    curMatch: 0,
    champRid: 0,
  };
  store.arenaBracketState = bracket;
  saveCompactBracket();
  return bracket;
}

function saveCompactBracket() {
  const b = store.arenaBracketState;
  if (!b) return;
  const compact = {
    p: b.preset,
    sz: b.size,
    s: b.seeds,
    r: b.rounds,
    cr: b.curRound,
    cm: b.curMatch,
    c: b.champRid,
  };
  const json = JSON.stringify(compact);
  if (json.length < 2400) {
    safeSetStorage(STORAGE_KEYS.ARENA_BRACKET, json);
  }
}

function loadCompactBracket() {
  const raw = safeGetStorage(STORAGE_KEYS.ARENA_BRACKET);
  if (!raw) return null;
  try {
    const c = JSON.parse(raw);
    if (!c || !Array.isArray(c.s) || c.s.length < 4) return null;
    return {
      preset: c.p || 'open',
      size: c.sz || c.s.length,
      seeds: c.s,
      rounds: c.r || [],
      curRound: c.cr || 0,
      curMatch: c.cm || 0,
      champRid: c.c || 0,
    };
  } catch {
    return null;
  }
}

function getCurrentBracketMatchPair(b) {
  if (!b || b.champRid) return [null, null];
  const r = b.curRound;
  const m = b.curMatch;
  if (r === 0) {
    return [getRecordById(b.seeds[m * 2]), getRecordById(b.seeds[m * 2 + 1])];
  }
  const prevRound = b.rounds[r - 1] || [];
  return [getRecordById(prevRound[m * 2]), getRecordById(prevRound[m * 2 + 1])];
}

// =========================================================================
// Deal Contenders for All 4 Modes
// =========================================================================
function getActiveModePool() {
  if (store.arenaMode === 'artist') {
    if (store.arenaTwinKey) {
      const twin = getTwinVariantGroups().find((g) => g.key === store.arenaTwinKey);
      if (twin && twin.records.length >= 2) return twin.records;
    }
    if (store.arenaArtistFilter) {
      const sub = store.records.filter((r) => r.artist === store.arenaArtistFilter);
      if (sub.length >= 2) return sub;
    }
    const stacks = getArtistStacks(3);
    if (stacks.length) {
      store.arenaArtistFilter = stacks[0].artist;
      return store.records.filter((r) => r.artist === store.arenaArtistFilter);
    }
  }
  if (store.arenaPoolMode === 'eyecandy') {
    const ec = store.records.filter((r) => ['splatter', 'galaxy', 'marble', 'split', 'color_in_color'].includes(r.wax_spec?.pattern || ''));
    if (ec.length >= 2) return ec;
  }
  return store.records;
}

function pickRandomPair(pool, excludeIds = new Set()) {
  let candidates = pool.filter((r) => !excludeIds.has(Number(r.release_id)));
  if (candidates.length < 2) candidates = pool.slice();
  if (candidates.length < 2) return [pool[0] || null, pool[1] || pool[0] || null];
  const shuffled = shuffleCopy(candidates);
  return [shuffled[0], shuffled[1]];
}

export function dealNextMatchup(options = {}) {
  store.arenaBlindRevealed = false;
  store.arenaWinnerFlash = '';
  targetOmegaA = 3.49;
  targetOmegaB = 3.49;
  winnerGlowA = 0;
  winnerGlowB = 0;

  if (store.arenaMode === 'bracket') {
    if (!store.arenaBracketState || options.rebuildBracket) {
      buildNewBracket(store.arenaBracketPreset, store.arenaBracketSize);
    }
    const b = store.arenaBracketState;
    if (b.champRid) {
      const champ = getRecordById(b.champRid);
      store.arenaDeckA = champ;
      store.arenaDeckB = champ;
    } else {
      const [a, br] = getCurrentBracketMatchPair(b);
      store.arenaDeckA = a;
      store.arenaDeckB = br;
    }
    renderArenaView();
    return;
  }

  const pool = getActiveModePool();
  if (pool.length < 2) return;

  if (store.arenaMode === 'elo' && store.arenaEloSubmode === 'king' && options.keepWinnerSide && store.arenaDeckA) {
    const champA = store.arenaDeckA;
    const champElo = getEloStats(champA.release_id).elo;
    const others = pool.filter((r) => Number(r.release_id) !== Number(champA.release_id));
    // Pick challenger with closest Elo among a random sample of 6 for dynamic matchups
    const sample = shuffleCopy(others).slice(0, Math.min(6, others.length));
    sample.sort((x, y) => Math.abs(getEloStats(x.release_id).elo - champElo) - Math.abs(getEloStats(y.release_id).elo - champElo));
    store.arenaDeckA = champA;
    store.arenaDeckB = sample[0] || others[0];
  } else {
    const [a, b] = pickRandomPair(pool);
    store.arenaDeckA = a;
    store.arenaDeckB = b;
  }

  renderArenaView();
}

// =========================================================================
// Vote Execution with Platter Physics, Elo & Confetti
// =========================================================================
export function castArenaVote(side) {
  if (voteCooldown || !store.arenaDeckA || !store.arenaDeckB) return;
  if (store.arenaMode === 'bracket' && store.arenaBracketState?.champRid) {
    setActiveRecordById(store.arenaBracketState.champRid);
    if (typeof window.__setMainVaultTab === 'function') window.__setMainVaultTab('showcase');
    return;
  }

  voteCooldown = true;
  const winner = side === 'A' ? store.arenaDeckA : store.arenaDeckB;
  const loser = side === 'A' ? store.arenaDeckB : store.arenaDeckA;
  const isWinA = side === 'A';

  // Visual platter boost & loser brake
  targetOmegaA = isWinA ? 6.8 : 0;
  targetOmegaB = isWinA ? 0 : 6.8;
  winnerGlowA = isWinA ? 1.0 : 0;
  winnerGlowB = isWinA ? 0 : 1.0;
  store.arenaWinnerFlash = side;

  const eloRes = recordEloMatchResult(winner.release_id, loser.release_id);
  const wax = winner.wax_spec || {};

  // Blind Wax Roulette dramatic reveal
  if (store.arenaMode === 'blind') {
    store.arenaBlindRevealed = true;
  }

  const cardAEl = document.getElementById('arena-deck-card-a');
  const cardBEl = document.getElementById('arena-deck-card-b');
  if (cardAEl && cardBEl) {
    cardAEl.classList.toggle('is-winner', isWinA);
    cardAEl.classList.toggle('is-loser', !isWinA);
    cardBEl.classList.toggle('is-winner', !isWinA);
    cardBEl.classList.toggle('is-loser', isWinA);
  }

  // Float +ELO badge
  const popEl = document.getElementById(isWinA ? 'arena-elo-pop-a' : 'arena-elo-pop-b');
  if (popEl) {
    popEl.textContent = `+${eloRes.deltaW} ELO`;
    popEl.classList.remove('hidden', 'elo-delta-pop');
    void popEl.offsetWidth;
    popEl.classList.add('elo-delta-pop');
  }

  const originEl = document.getElementById(isWinA ? 'arena-webgl-deck-a' : 'arena-webgl-deck-b');
  spawnParticles(wax.primary_color, wax.secondary_color, wax.accent_color, 76, originEl);
  playNeedleDropSound();

  // Handle Tournament Bracket progression
  let isChampCrowned = false;
  if (store.arenaMode === 'bracket' && store.arenaBracketState) {
    const b = store.arenaBracketState;
    b.rounds[b.curRound][b.curMatch] = Number(winner.release_id);
    const matchesThisRound = b.rounds[b.curRound].length;
    if (b.curMatch + 1 < matchesThisRound) {
      b.curMatch += 1;
    } else if (b.curRound + 1 < b.rounds.length) {
      b.curRound += 1;
      b.curMatch = 0;
    } else {
      b.champRid = Number(winner.release_id);
      isChampCrowned = true;
    }
    saveCompactBracket();
  }

  playRouletteWinChord(isChampCrowned);

  if (store.arenaMode === 'blind') {
    renderArenaCardsMetadataOnly();
    showToast(`🔍 Blind Reveal: ${winner.artist} — "${winner.title}" wins (+${eloRes.deltaW} ELO)!`);
  } else if (isChampCrowned) {
    showToast(`👑 GRAIL CHAMPION CROWNED: ${winner.artist} — "${winner.title}"!`);
    spawnParticles('#fbbf24', wax.primary_color, wax.accent_color, 110);
  } else {
    showToast(`⚔️ ${winner.artist} — "${winner.title}" wins (+${eloRes.deltaW} ELO • ${eloRes.winnerStats.s} Streak)`);
  }

  const delayMs = store.arenaMode === 'blind' ? 1150 : 620;
  setTimeout(() => {
    voteCooldown = false;
    stopArenaAudio();
    if (store.arenaMode === 'elo' && store.arenaEloSubmode === 'king') {
      store.arenaDeckA = winner;
      dealNextMatchup({ keepWinnerSide: true });
    } else {
      dealNextMatchup();
    }
  }, delayMs);
}

// =========================================================================
// Rendering Twin-Deck Cards, Modes, Bracket Tree & Tier List
// =========================================================================
function renderDeckCardInfo(side, rec) {
  const isA = side === 'A';
  const cardEl = document.getElementById(isA ? 'arena-deck-card-a' : 'arena-deck-card-b');
  if (!cardEl || !rec) return;

  cardEl.classList.remove('is-winner', 'is-loser');
  const wax = rec.wax_spec || {};
  const stats = getEloStats(rec.release_id);
  const verifiedPhoto = Boolean(getVerifiedPressingPhotoUrl(rec, store.userOverrides));
  const isBlindHidden = store.arenaMode === 'blind' && !store.arenaBlindRevealed;
  const c1 = safeCssColor(wax.primary_color, '#06b6d4');

  const metaEl = document.getElementById(isA ? 'arena-meta-a' : 'arena-meta-b');
  if (metaEl) {
    metaEl.innerHTML = isBlindHidden
      ? `
        <div class="flex items-center justify-between gap-2 text-xs mb-2">
          <span class="px-2.5 py-0.5 rounded-full font-mono-tech font-bold bg-slate-800 text-cyan-300 border border-cyan-500/35">
            SPECIMEN ${side} • PURE WAX MODE
          </span>
          <span class="font-mono-tech font-bold text-slate-400">ELO ???</span>
        </div>
        <div class="mt-2">
          <p class="text-xs font-extrabold uppercase tracking-wider text-fuchsia-300">CLASSIFIED PRESSING</p>
          <h3 class="text-lg sm:text-xl font-black text-white mt-0.5">Vote purely on the spinning wax</h3>
          <p class="text-[11px] font-mono-tech text-slate-400 mt-1">Sleeve slides open &amp; reveals after your vote</p>
        </div>
      `
      : `
        <div class="flex flex-wrap items-center justify-between gap-2 text-xs mb-2">
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="px-2.5 py-0.5 rounded-full font-mono-tech font-bold bg-purple-500/20 text-purple-200 border border-purple-400/35">
              ${escapeHtml(wax.variant_badge || '12" LP')}
            </span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-mono-tech font-bold ${verifiedPhoto ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-800 text-cyan-300 border border-white/10'}">
              ${verifiedPhoto ? '📸 Real Photo' : '⚙ WebGL2 Wax'}
            </span>
          </div>
          <span class="font-mono-tech font-black text-emerald-400">${formatUsdValue(rec)}</span>
        </div>
        <div>
          <div class="flex items-center justify-between gap-2">
            <p class="text-xs font-extrabold uppercase tracking-wider text-cyan-400 truncate">${escapeHtml(rec.artist)} • ${escapeHtml(rec.year || 'LP')}</p>
            <span class="text-[10px] font-mono-tech font-bold px-2 py-0.5 rounded-md bg-slate-900 border border-white/10 text-amber-300 shrink-0">
              ELO ${stats.elo} ${stats.s >= 2 ? `• 🔥${stats.s}` : ''}
            </span>
          </div>
          <h3 class="text-lg sm:text-xl font-black text-white leading-snug mt-0.5 line-clamp-1">${escapeHtml(rec.title)}</h3>
          <p class="text-[11px] font-mono-tech text-slate-400 mt-0.5 truncate">${escapeHtml(rec.label || '')} (${escapeHtml(rec.catno || 'none')}) • W${stats.w}-L${stats.l}</p>
        </div>
      `;
  }

  const sleeveEl = document.getElementById(isA ? 'arena-sleeve-a' : 'arena-sleeve-b');
  if (sleeveEl) {
    sleeveEl.innerHTML = renderJacketSleeveHTML(rec);
  }
  const shroudEl = document.getElementById(isA ? 'arena-shroud-a' : 'arena-shroud-b');
  if (shroudEl) {
    shroudEl.classList.toggle('hidden', store.arenaMode !== 'blind');
    shroudEl.classList.toggle('is-revealed', store.arenaMode === 'blind' && store.arenaBlindRevealed);
  }

  const voteBtn = document.getElementById(isA ? 'btn-arena-vote-a' : 'btn-arena-vote-b');
  if (voteBtn) {
    if (store.arenaMode === 'bracket' && store.arenaBracketState?.champRid) {
      voteBtn.textContent = '💿 Spin Champion on Stage';
    } else if (isBlindHidden) {
      voteBtn.textContent = `⚡ Vote Wax ${side} (${isA ? '←' : '→'})`;
    } else {
      voteBtn.textContent = `⚡ Crown ${rec.artist} (${isA ? '←' : '→'})`;
    }
  }

  const stageShell = document.getElementById('arena-stage-shell');
  if (stageShell) {
    stageShell.style.setProperty(isA ? '--arena-color-a' : '--arena-color-b', `${c1}3b`);
  }
}

function renderArenaCardsMetadataOnly() {
  if (store.arenaDeckA) renderDeckCardInfo('A', store.arenaDeckA);
  if (store.arenaDeckB) renderDeckCardInfo('B', store.arenaDeckB);
}

function renderArenaModeControls() {
  document.querySelectorAll('[data-arena-mode]').forEach((btn) => {
    const act = btn.getAttribute('data-arena-mode') === store.arenaMode;
    btn.className = act
      ? 'px-3 py-1.5 rounded-xl text-xs font-black bg-gradient-to-r from-fuchsia-600 to-cyan-600 text-white shadow-md transition whitespace-nowrap'
      : 'px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-950/90 text-slate-300 border border-white/10 hover:text-white transition whitespace-nowrap';
  });

  const subBar = document.getElementById('arena-submode-bar');
  if (!subBar) return;

  if (store.arenaMode === 'elo') {
    subBar.innerHTML = `
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-[11px] font-mono-tech uppercase text-slate-400 font-bold">Gauntlet Style:</span>
        <button type="button" data-elo-sub="king" class="px-3 py-1 rounded-lg text-xs font-bold ${store.arenaEloSubmode === 'king' ? 'bg-amber-500/25 text-amber-200 border border-amber-400/50' : 'bg-slate-900 text-slate-300 border border-white/10'}">👑 Winner Stays On</button>
        <button type="button" data-elo-sub="random" class="px-3 py-1 rounded-lg text-xs font-bold ${store.arenaEloSubmode === 'random' ? 'bg-cyan-500/25 text-cyan-200 border border-cyan-400/50' : 'bg-slate-900 text-slate-300 border border-white/10'}">⚡ Pure Random</button>
        <span class="text-[11px] text-slate-400 ml-auto hidden sm:inline">Hotkeys: <code class="text-cyan-300">←</code>/<code class="text-fuchsia-300">→</code> Vote • <code class="text-cyan-300">Space</code> Crossfade • <code class="text-amber-300">B</code> Backlight • <code class="text-slate-200">S</code> Reroll</span>
      </div>
    `;
  } else if (store.arenaMode === 'artist') {
    const stacks = getArtistStacks(3);
    const twins = getTwinVariantGroups();
    subBar.innerHTML = `
      <div class="flex flex-wrap items-center gap-2.5">
        <label class="text-[11px] font-mono-tech uppercase text-cyan-300 font-bold">Artist Stack (3+ LPs):</label>
        <select id="arena-artist-select" class="bg-slate-900 border border-white/15 rounded-xl px-3 py-1.5 text-xs font-semibold text-white outline-none focus:border-cyan-400">
          ${stacks.map((s) => `<option value="${escapeHtml(s.artist)}" ${!store.arenaTwinKey && store.arenaArtistFilter === s.artist ? 'selected' : ''}>${escapeHtml(s.artist)} (${s.count} LPs)</option>`).join('')}
        </select>
        <label class="text-[11px] font-mono-tech uppercase text-fuchsia-300 font-bold ml-1">Twin-Variant Shootout:</label>
        <select id="arena-twin-select" class="bg-slate-900 border border-white/15 rounded-xl px-3 py-1.5 text-xs font-semibold text-fuchsia-200 outline-none focus:border-fuchsia-400">
          <option value="">-- Select Same-Album Multi-Variant --</option>
          ${twins.map((g) => `<option value="${escapeHtml(g.key)}" ${store.arenaTwinKey === g.key ? 'selected' : ''}>${escapeHtml(g.label)}</option>`).join('')}
        </select>
      </div>
    `;
  } else if (store.arenaMode === 'bracket') {
    subBar.innerHTML = `
      <div class="flex flex-wrap items-center gap-2.5">
        <label class="text-[11px] font-mono-tech uppercase text-amber-300 font-bold">Bracket Theme:</label>
        <select id="arena-bracket-preset-select" class="bg-slate-900 border border-white/15 rounded-xl px-3 py-1.5 text-xs font-semibold text-white outline-none focus:border-amber-400">
          ${BRACKET_PRESETS.map((p) => `<option value="${p.id}" ${store.arenaBracketPreset === p.id ? 'selected' : ''}>${escapeHtml(p.label)}</option>`).join('')}
        </select>
        <div class="flex items-center gap-1 bg-slate-900 p-1 rounded-xl border border-white/10">
          ${[8, 16, 32].map((sz) => `<button type="button" data-bracket-size="${sz}" class="px-2.5 py-0.5 rounded-lg text-xs font-mono-tech font-bold ${store.arenaBracketSize === sz ? 'bg-amber-500/25 text-amber-200 border border-amber-400/50' : 'text-slate-400 hover:text-white'}">${sz}-Seed</button>`).join('')}
        </div>
        <button type="button" id="btn-bracket-restart" class="px-3 py-1.5 rounded-xl bg-fuchsia-600/25 hover:bg-fuchsia-600/40 text-fuchsia-200 border border-fuchsia-400/40 text-xs font-bold">🔄 New Seeded Bracket</button>
      </div>
    `;
  } else {
    subBar.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span class="text-fuchsia-200 font-bold">🕵️ Blind Wax Roulette: Sleeves &amp; metadata concealed until you vote — pure wax aesthetics + optical backlight!</span>
        <span class="font-mono-tech text-[11px] text-cyan-300">Vote locks in &amp; slides open sleeves</span>
      </div>
    `;
  }
}

function renderBracketTree() {
  const treeWrap = document.getElementById('arena-bracket-tree-wrap');
  if (!treeWrap) return;
  if (store.arenaMode !== 'bracket' || !store.arenaBracketState) {
    treeWrap.classList.add('hidden');
    return;
  }
  treeWrap.classList.remove('hidden');
  const b = store.arenaBracketState;
  const roundNames = (totalRounds, idx) => {
    const rem = totalRounds - idx;
    if (rem === 1) return '🏆 Championship Final';
    if (rem === 2) return 'Semifinals';
    if (rem === 3) return 'Quarterfinals';
    if (rem === 4) return 'Sweet 16';
    return 'Round of 32';
  };

  let colsHtml = '';
  for (let r = 0; r < b.rounds.length; r++) {
    const matchCount = b.rounds[r].length;
    const isFinalRound = r === b.rounds.length - 1;
    let nodesHtml = '';
    for (let m = 0; m < matchCount; m++) {
      const topId = r === 0 ? b.seeds[m * 2] : b.rounds[r - 1][m * 2];
      const botId = r === 0 ? b.seeds[m * 2 + 1] : b.rounds[r - 1][m * 2 + 1];
      const winId = b.rounds[r][m];
      const recTop = topId ? getRecordById(topId) : null;
      const recBot = botId ? getRecordById(botId) : null;
      const isActive = !b.champRid && b.curRound === r && b.curMatch === m;

      nodesHtml += `
        <div class="bracket-match-node ${isActive ? 'is-active-match' : ''} ${isFinalRound ? 'is-final-match' : ''} text-[11px]">
          <div class="px-2.5 py-1.5 flex items-center justify-between gap-2 border-b border-white/10 ${winId && winId === Number(topId) ? 'bg-emerald-500/20 text-emerald-200 font-bold' : 'text-slate-300'}">
            <span class="truncate">${recTop ? escapeHtml(`${recTop.artist} — ${recTop.title}`) : 'TBD'}</span>
            ${winId && winId === Number(topId) ? '<span class="text-emerald-400">✓</span>' : ''}
          </div>
          <div class="px-2.5 py-1.5 flex items-center justify-between gap-2 ${winId && winId === Number(botId) ? 'bg-emerald-500/20 text-emerald-200 font-bold' : 'text-slate-300'}">
            <span class="truncate">${recBot ? escapeHtml(`${recBot.artist} — ${recBot.title}`) : 'TBD'}</span>
            ${winId && winId === Number(botId) ? '<span class="text-emerald-400">✓</span>' : ''}
          </div>
        </div>
      `;
    }
    colsHtml += `
      <div class="bracket-round-col">
        <div class="text-[10px] font-mono-tech uppercase font-bold text-cyan-300 tracking-wider px-1">${roundNames(b.rounds.length, r)}</div>
        ${nodesHtml}
      </div>
    `;
  }

  const champ = b.champRid ? getRecordById(b.champRid) : null;
  const champBanner = champ
    ? `
      <div class="mt-4 p-4 rounded-2xl bg-gradient-to-r from-amber-500/20 via-fuchsia-500/15 to-cyan-500/20 border border-amber-400/50 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div class="text-[10px] font-mono-tech uppercase text-amber-300 font-bold">👑 ${b.size}-Seed Bracket Champion</div>
          <div class="text-base sm:text-lg font-black text-white">${escapeHtml(champ.artist)} — ${escapeHtml(champ.title)}</div>
          <div class="text-xs font-mono-tech text-cyan-300">${escapeHtml(champ.wax_spec?.variant_badge || '12" LP')} • ELO ${getEloStats(champ.release_id).elo}</div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button type="button" id="btn-champ-trophy-png" class="px-3.5 py-2 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-black text-xs transition shadow-lg">🏆 Download Trophy Card PNG</button>
          <button type="button" id="btn-champ-spin-stage" class="px-3.5 py-2 rounded-xl bg-cyan-500/25 hover:bg-cyan-500/35 text-cyan-200 border border-cyan-400/50 font-bold text-xs transition">💿 Spin on Main Stage</button>
        </div>
      </div>
    `
    : '';

  treeWrap.innerHTML = `
    <div class="flex items-center justify-between gap-2 mb-3">
      <div class="text-xs font-mono-tech font-bold uppercase text-amber-300">🏆 ${b.size}-Seed Tournament Bracket Tree (${escapeHtml(BRACKET_PRESETS.find((p) => p.id === b.preset)?.label || b.preset)})</div>
      <span class="text-[11px] font-mono-tech text-slate-400">${b.champRid ? 'Completed' : `${roundNames(b.rounds.length, b.curRound)} • Match ${b.curMatch + 1}/${b.rounds[b.curRound].length}`}</span>
    </div>
    <div class="bracket-tree-scroll custom-scrollbar">${colsHtml}</div>
    ${champBanner}
  `;
}

export function renderTierMatrixAndLeaderboard() {
  const tierEl = document.getElementById('arena-tier-matrix');
  const lbEl = document.getElementById('arena-elo-leaderboard');
  if (!tierEl || !lbEl) return;

  const battled = store.records
    .map((r) => ({ rec: r, stats: getEloStats(r.release_id) }))
    .filter((x) => x.stats.w > 0 || x.stats.l > 0)
    .sort((a, b) => b.stats.elo - a.stats.elo || b.stats.w - a.stats.w);

  const tiers = { S: [], A: [], B: [], C: [] };
  if (battled.length > 0) {
    for (const item of battled) {
      if (item.stats.elo >= 1532) tiers.S.push(item);
      else if (item.stats.elo >= 1505) tiers.A.push(item);
      else if (item.stats.elo >= 1480) tiers.B.push(item);
      else tiers.C.push(item);
    }
  }

  tierEl.innerHTML = ['S', 'A', 'B', 'C']
    .map((t) => {
      const items = tiers[t];
      return `
        <div class="flex items-stretch gap-2 rounded-xl bg-slate-950/90 border border-white/10 overflow-hidden">
          <div class="w-11 shrink-0 flex items-center justify-center font-black text-base tier-badge-${t}">${t}</div>
          <div class="flex-1 flex items-center gap-2 p-2 overflow-x-auto custom-scrollbar min-h-[54px]">
            ${
              items.length
                ? items
                    .slice(0, 14)
                    .map(
                      ({ rec, stats }) => `
                      <button type="button" data-arena-jump="${rec.release_id}" class="shrink-0 flex items-center gap-2 px-2 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-white/10 hover:border-cyan-400/50 transition text-left" title="${escapeHtml(rec.artist)} — ${escapeHtml(rec.title)} (ELO ${stats.elo})">
                        <span class="w-3 h-3 rounded-full shrink-0 border border-white/30" style="background:${safeCssColor(rec.wax_spec?.primary_color, '#8b2cf5')}"></span>
                        <span class="text-[11px] font-bold text-white truncate max-w-[130px]">${escapeHtml(rec.artist)}</span>
                        <span class="text-[10px] font-mono-tech text-amber-300">${stats.elo}</span>
                      </button>
                    `
                    )
                    .join('')
                : `<span class="text-[11px] text-slate-500 font-mono-tech">Battle pressings above to populate Tier ${t}</span>`
            }
          </div>
        </div>
      `;
    })
    .join('');

  lbEl.innerHTML = battled.length
    ? battled
        .slice(0, 20)
        .map((item, idx) => {
          const { rec, stats } = item;
          const total = stats.w + stats.l;
          const winPct = total ? Math.round((stats.w / total) * 100) : 0;
          return `
            <div data-arena-jump="${rec.release_id}" class="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-slate-950/85 hover:bg-slate-900 border border-white/10 hover:border-cyan-400/40 cursor-pointer transition">
              <div class="flex items-center gap-2.5 min-w-0">
                <span class="w-5 text-xs font-mono-tech font-black ${idx < 3 ? 'text-amber-300' : 'text-slate-400'}">#${idx + 1}</span>
                <span class="w-3.5 h-3.5 rounded-full shrink-0 border border-white/30" style="background:radial-gradient(circle, ${safeCssColor(rec.wax_spec?.secondary_color)}, ${safeCssColor(rec.wax_spec?.primary_color)})"></span>
                <div class="min-w-0">
                  <div class="text-xs font-bold text-white truncate">${escapeHtml(rec.artist)} — ${escapeHtml(rec.title)}</div>
                  <div class="text-[10px] font-mono-tech text-slate-400 truncate">${escapeHtml(rec.wax_spec?.variant_badge || 'LP')}</div>
                </div>
              </div>
              <div class="flex items-center gap-2 shrink-0 text-[11px] font-mono-tech">
                ${stats.s >= 2 ? `<span class="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">🔥${stats.s}</span>` : ''}
                <span class="text-slate-400">${stats.w}W-${stats.l}L (${winPct}%)</span>
                <span class="font-black text-amber-300 w-10 text-right">${stats.elo}</span>
              </div>
            </div>
          `;
        })
        .join('')
    : '<div class="text-xs text-slate-400 text-center py-6">No completed battles yet — cast your first vote above to start building live Vault Elo rankings!</div>';
}

export function renderArenaView() {
  renderArenaModeControls();

  const roundBadge = document.getElementById('arena-round-badge');
  if (roundBadge) {
    if (store.arenaMode === 'bracket' && store.arenaBracketState) {
      const b = store.arenaBracketState;
      roundBadge.textContent = b.champRid
        ? '👑 Champion Crowned!'
        : (b.curRound === b.rounds.length - 1 ? '🏆 Championship Final!' : `Round ${b.curRound + 1}/${b.rounds.length} • Match ${b.curMatch + 1}`);
      roundBadge.className = b.curRound === b.rounds.length - 1 && !b.champRid
        ? 'px-3.5 py-1.5 rounded-xl font-mono-tech text-xs font-extrabold bg-amber-500/25 text-amber-200 border border-amber-400/50 animate-pulse'
        : 'px-3.5 py-1.5 rounded-xl font-mono-tech text-xs font-extrabold bg-cyan-500/20 text-cyan-300 border border-cyan-400/40';
    } else if (store.arenaMode === 'blind') {
      roundBadge.textContent = '🕵️ Blind Wax Roulette';
      roundBadge.className = 'px-3.5 py-1.5 rounded-xl font-mono-tech text-xs font-extrabold bg-fuchsia-500/20 text-fuchsia-300 border border-fuchsia-400/40';
    } else if (store.arenaMode === 'artist') {
      roundBadge.textContent = store.arenaTwinKey ? '⚔️ Twin-Variant Shootout' : `🎸 ${store.arenaArtistFilter || 'Artist'} Clash`;
      roundBadge.className = 'px-3.5 py-1.5 rounded-xl font-mono-tech text-xs font-extrabold bg-purple-500/20 text-purple-200 border border-purple-400/40';
    } else {
      roundBadge.textContent = store.arenaEloSubmode === 'king' ? '👑 King of the Platter' : '⚡ Random Elo Gauntlet';
      roundBadge.className = 'px-3.5 py-1.5 rounded-xl font-mono-tech text-xs font-extrabold bg-cyan-500/20 text-cyan-300 border border-cyan-400/40';
    }
  }

  if (store.arenaDeckA && deckARenderer) {
    deckARenderer.setRecord(store.arenaDeckA, store.userOverrides);
    deckARenderer.setOptics({
      backlight: store.arenaMode === 'blind' ? 0.85 : (arenaBacklightOn ? 0.88 : 0),
      uvMode: store.uvBlacklight,
      blindMode: store.arenaMode === 'blind' && !store.arenaBlindRevealed,
      winnerGlow: winnerGlowA,
    });
  }
  if (store.arenaDeckB && deckBRenderer) {
    deckBRenderer.setRecord(store.arenaDeckB, store.userOverrides);
    deckBRenderer.setOptics({
      backlight: store.arenaMode === 'blind' ? 0.85 : (arenaBacklightOn ? 0.88 : 0),
      uvMode: store.uvBlacklight,
      blindMode: store.arenaMode === 'blind' && !store.arenaBlindRevealed,
      winnerGlow: winnerGlowB,
    });
  }

  renderArenaCardsMetadataOnly();
  renderBracketTree();
  renderTierMatrixAndLeaderboard();
}

function tickArenaFrame(now) {
  const dt = Math.min(0.05, Math.max(0.001, (now - arenaLastTime) / 1000));
  arenaLastTime = now;

  if (store.activeTab === 'arena') {
    omegaA += (targetOmegaA - omegaA) * Math.min(1, dt * 6.5);
    omegaB += (targetOmegaB - omegaB) * Math.min(1, dt * 6.5);
    angleA += omegaA * dt;
    angleB += omegaB * dt;

    if (deckARenderer) {
      deckARenderer.setAngles(angleA);
      deckARenderer.setOptics({ winnerGlow: winnerGlowA });
      deckARenderer.render();
    }
    if (deckBRenderer) {
      deckBRenderer.setAngles(angleB);
      deckBRenderer.setOptics({ winnerGlow: winnerGlowB });
      deckBRenderer.render();
    }
  }

  arenaRafId = requestAnimationFrame(tickArenaFrame);
}

export function toggleArenaBacklight() {
  arenaBacklightOn = !arenaBacklightOn;
  const btn = document.getElementById('btn-arena-backlight');
  if (btn) {
    btn.textContent = arenaBacklightOn ? '☀️ Backlight: ON' : '☀️ Hold Both to Light (B)';
    btn.className = arenaBacklightOn
      ? 'px-3 py-1.5 rounded-xl text-xs font-mono-tech font-bold bg-amber-400/25 text-amber-200 border border-amber-400/60 transition'
      : 'px-3 py-1.5 rounded-xl text-xs font-mono-tech font-bold bg-slate-900 text-slate-300 border border-white/10 hover:text-white transition';
  }
  renderArenaView();
}

export function initVariantClashArena() {
  const canvasA = document.getElementById('arena-webgl-deck-a');
  const canvasB = document.getElementById('arena-webgl-deck-b');
  if (canvasA) deckARenderer = new WebGLWaxDiscRenderer(canvasA);
  if (canvasB) deckBRenderer = new WebGLWaxDiscRenderer(canvasB);

  const savedBracket = loadCompactBracket();
  if (savedBracket) store.arenaBracketState = savedBracket;

  // Mode Tabs
  document.querySelectorAll('[data-arena-mode]').forEach((btn) => {
    btn.addEventListener('click', () => {
      store.arenaMode = btn.getAttribute('data-arena-mode') || 'elo';
      playCrateTickSound(1.15);
      dealNextMatchup({ rebuildBracket: store.arenaMode === 'bracket' && !store.arenaBracketState });
    });
  });

  // Sub-mode delegation
  document.getElementById('arena-submode-bar')?.addEventListener('click', (e) => {
    const eloBtn = e.target.closest('[data-elo-sub]');
    if (eloBtn) {
      store.arenaEloSubmode = eloBtn.getAttribute('data-elo-sub') || 'king';
      renderArenaView();
      return;
    }
    const szBtn = e.target.closest('[data-bracket-size]');
    if (szBtn) {
      store.arenaBracketSize = Number(szBtn.getAttribute('data-bracket-size') || 8);
      dealNextMatchup({ rebuildBracket: true });
      return;
    }
    if (e.target.closest('#btn-bracket-restart')) {
      playCrateTickSound(1.25);
      dealNextMatchup({ rebuildBracket: true });
    }
  });

  document.getElementById('arena-submode-bar')?.addEventListener('change', (e) => {
    if (e.target.id === 'arena-artist-select') {
      store.arenaTwinKey = '';
      store.arenaArtistFilter = e.target.value;
      dealNextMatchup();
    } else if (e.target.id === 'arena-twin-select') {
      store.arenaTwinKey = e.target.value;
      dealNextMatchup();
    } else if (e.target.id === 'arena-bracket-preset-select') {
      store.arenaBracketPreset = e.target.value;
      dealNextMatchup({ rebuildBracket: true });
    }
  });

  // Pool filter & Reroll
  document.getElementById('btn-arena-new-bracket')?.addEventListener('click', () => {
    playCrateTickSound(1.2);
    dealNextMatchup({ rebuildBracket: store.arenaMode === 'bracket' });
    showToast('⚔️ Dealt a fresh Variant Clash matchup!');
  });

  document.querySelectorAll('.arena-pool-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      store.arenaPoolMode = btn.getAttribute('data-arena-pool') || 'all';
      document.querySelectorAll('.arena-pool-btn').forEach((b) => {
        const act = b.getAttribute('data-arena-pool') === store.arenaPoolMode;
        b.className = act
          ? 'arena-pool-btn px-2.5 py-1 rounded-lg font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
          : 'arena-pool-btn px-2.5 py-1 rounded-lg font-semibold text-slate-400 hover:text-white';
      });
      dealNextMatchup();
    });
  });

  // Vote & Cue buttons
  document.getElementById('btn-arena-vote-a')?.addEventListener('click', () => castArenaVote('A'));
  document.getElementById('btn-arena-vote-b')?.addEventListener('click', () => castArenaVote('B'));
  document.getElementById('btn-arena-cue-a')?.addEventListener('click', () => auditionArenaDeck('A', store.arenaDeckA));
  document.getElementById('btn-arena-cue-b')?.addEventListener('click', () => auditionArenaDeck('B', store.arenaDeckB));
  document.getElementById('btn-arena-dual-drop')?.addEventListener('click', () => dualDropArenaDecks(store.arenaDeckA, store.arenaDeckB));
  document.getElementById('btn-arena-stop-audio')?.addEventListener('click', () => stopArenaAudio());
  document.getElementById('btn-arena-backlight')?.addEventListener('click', () => toggleArenaBacklight());

  document.getElementById('arena-crossfader')?.addEventListener('input', (e) => {
    applyArenaCrossfade(Number(e.target.value || 0));
    if (!isArenaAudioPlaying() && store.arenaDeckA && store.arenaDeckB) {
      dualDropArenaDecks(store.arenaDeckA, store.arenaDeckB);
    }
  });

  // Bracket Trophy & Tier Jump clicks
  document.getElementById('view-arena')?.addEventListener('click', (e) => {
    const jump = e.target.closest('[data-arena-jump]');
    if (jump) {
      const rid = Number(jump.getAttribute('data-arena-jump'));
      setActiveRecordById(rid);
      if (typeof window.__setMainVaultTab === 'function') window.__setMainVaultTab('showcase');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    if (e.target.closest('#btn-champ-spin-stage') && store.arenaBracketState?.champRid) {
      setActiveRecordById(store.arenaBracketState.champRid);
      if (typeof window.__setMainVaultTab === 'function') window.__setMainVaultTab('showcase');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    if (e.target.closest('#btn-champ-trophy-png') && store.arenaBracketState?.champRid) {
      const champ = getRecordById(store.arenaBracketState.champRid);
      if (champ) {
        emit('exportChampionTrophyCard', {
          record: champ,
          presetLabel: BRACKET_PRESETS.find((p) => p.id === store.arenaBracketState.preset)?.label || 'Vault Championship',
          seedSize: store.arenaBracketState.size,
          elo: getEloStats(champ.release_id).elo,
        });
      }
    }
  });

  // Mouse pointer light tracking on Arena decks
  canvasA?.addEventListener('pointermove', (e) => {
    const r = canvasA.getBoundingClientRect();
    deckARenderer?.setPointer(((e.clientX - r.left) / r.width) * 2 - 1, -(((e.clientY - r.top) / r.height) * 2 - 1));
  });
  canvasB?.addEventListener('pointermove', (e) => {
    const r = canvasB.getBoundingClientRect();
    deckBRenderer?.setPointer(((e.clientX - r.left) / r.width) * 2 - 1, -(((e.clientY - r.top) / r.height) * 2 - 1));
  });

  dealNextMatchup();
  if (!arenaRafId) {
    arenaLastTime = performance.now();
    arenaRafId = requestAnimationFrame(tickArenaFrame);
  }
}
