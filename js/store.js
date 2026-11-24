// KRUNKED // VINYL VAULT v6.0 — Central Store, URL Deep-Linking & KRUNKED_COOKIE_VAULT_V1 Persistence

import {
  DEFAULT_FLATTENING_STATUS,
  getNumericUsdValue,
  getVerifiedPressingPhotoUrl,
  safeGetStorage,
  safeRemoveStorage,
  safeSetStorage,
  showToast,
} from './utils.js';

export const STORAGE_KEYS = Object.freeze({
  OVERRIDES: 'krunked_pressing_overrides_v2_2',
  FLATTEN_QUEUE: 'krunked_flattening_state_v4',
  FLATTEN_NOTES: 'krunked_flattening_notes_v6',
  FLATTEN_TIMER: 'krunked_flattening_timer_v4',
  UI_PREFS: 'krunked_ui_prefs_v6',
  ARENA_ELO: 'krunked_arena_elo_v6',
  ARENA_BRACKET: 'krunked_arena_bracket_v6',
  SYNC_STAMP: '__discogs_py_sync_stamp__',
  // Intentionally NOT matching cookie_vault.js TRACKED_KEY_PATTERNS:
  GH_PAT: 'local_gh_pat_auth',
  DC_PAT: 'local_dc_pat_auth',
  PREVIEW_CACHE: 'itunes_prev_cache_v6',
  LINK_CACHE: 'album_link_map_v6',
});

export const store = {
  records: [],
  filteredRecords: [],
  activeIndex: 0,
  thumbMode: 'split', // Strictly defaults to 'split' (Sleeve + Disc) on boot
  stageMode: 'auto', // 'auto' | 'sleeve'
  activeTab: 'showcase', // 'showcase' | 'arena' | 'analytics' | 'pipeline' | 'flattening'
  filter: 'all',
  filterArtist: '',
  filterLabel: '',
  filterYear: 0,
  filterColorHex: '',
  sortBy: 'added_desc',
  searchQuery: '',
  doneSearchQuery: '',
  benchSearchQuery: '',
  // Turntable & Optical Hardware State
  motorOn: true,
  isSpinning: true,
  rpm: 33,
  quartzPitchLock: false,
  backlightOn: false,
  backlightIntensity: 0.78,
  uvBlacklight: true,
  etchedPreviewOverride: false,
  analogSfx: true,
  crackleOn: false,
  spinMode: 'all', // 'all' | 'showroom' | 'eyecandy' | 'splatter' | 'translucent' | 'double_lp' | 'etched' | 'todo'
  showroomCountdown: 15,
  showroomTickInterval: null,
  isSpinningRoulette: false,
  isCardFlipped: false,
  stageCollapsed: false,
  // Audio / Tracklist State
  autoAdvanceTracks: true,
  streamCache: {},
  activeStreamRid: null,
  activeTrackIndex: -1,
  isPreviewPlaying: false,
  isAudioMuted: false,
  // Persistence & Overrides
  userOverrides: {},
  localOverrideEdits: {},
  releaseGalleryCache: {},
  flatteningNotes: {},
  unsavedPinCount: 0,
  unsavedFlattenCount: 0,
  // Arena State
  eloMap: {}, // { [rid]: { elo, w, l, s } }
  arenaMode: 'elo', // 'elo' | 'artist' | 'bracket' | 'blind'
  arenaEloSubmode: 'king', // 'king' | 'random'
  arenaArtistFilter: '',
  arenaTwinKey: '',
  arenaPoolMode: 'all',
  arenaBracketPreset: 'open',
  arenaBracketSize: 8,
  arenaBracketState: null,
  arenaDeckA: null,
  arenaDeckB: null,
  arenaCrossfade: 0, // -1 (Deck A) .. +1 (Deck B)
  arenaBlindRevealed: false,
  arenaWinnerFlash: '', // '' | 'A' | 'B'
  // Hydration flag
  _initialized: false,
};

const listeners = new Set();

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function emit(topic, detail = null) {
  for (const fn of listeners) {
    try {
      fn(topic, detail, store);
    } catch (err) {
      console.error('[VaultStore listener error]', topic, err);
    }
  }
}

export function getActiveRecord() {
  const list = store.filteredRecords.length ? store.filteredRecords : store.records;
  if (!list.length) return null;
  if (store.activeIndex < 0 || store.activeIndex >= list.length) {
    store.activeIndex = 0;
  }
  return list[store.activeIndex] || null;
}

export function setActiveIndex(idx) {
  const list = store.filteredRecords.length ? store.filteredRecords : store.records;
  if (!list.length) return;
  store.activeIndex = ((idx % list.length) + list.length) % list.length;
  syncUrlFromState();
  emit('activeRecordChanged', getActiveRecord());
}

export function setActiveRecordById(releaseId) {
  const rid = Number(releaseId);
  let idx = store.filteredRecords.findIndex((r) => Number(r.release_id) === rid);
  if (idx === -1) {
    clearAllCrateFilters(false);
    idx = store.filteredRecords.findIndex((r) => Number(r.release_id) === rid);
  }
  if (idx !== -1) {
    store.activeIndex = idx;
    syncUrlFromState();
    emit('activeRecordChanged', getActiveRecord());
  }
}

export function clearAllCrateFilters(shouldEmit = true) {
  store.filter = 'all';
  store.filterArtist = '';
  store.filterLabel = '';
  store.filterYear = 0;
  store.filterColorHex = '';
  store.searchQuery = '';
  const sEl = document.getElementById('search-input');
  if (sEl) sEl.value = '';
  const clearEl = document.getElementById('btn-clear-search');
  if (clearEl) clearEl.classList.add('hidden');
  applyFiltersAndSort(shouldEmit);
}

// =========================================================================
// Compact Persistence Helpers (Safe under KRUNKED_COOKIE_VAULT_V1 4KB Cap)
// =========================================================================
export function saveUiPrefs() {
  const persistedSpin = store.spinMode === 'showroom' ? 'all' : (store.spinMode || 'all');
  const prefs = {
    uv: store.uvBlacklight ? 1 : 0,
    back: store.backlightOn ? 1 : 0,
    backInt: Number(store.backlightIntensity.toFixed(2)),
    sfx: store.analogSfx ? 1 : 0,
    rpm: store.rpm,
    thumb: store.thumbMode || 'split',
    spin: persistedSpin,
  };
  safeSetStorage(STORAGE_KEYS.UI_PREFS, JSON.stringify(prefs));
}

export function loadUiPrefs() {
  const raw = safeGetStorage(STORAGE_KEYS.UI_PREFS);
  if (!raw) return;
  try {
    const p = JSON.parse(raw);
    if (!p || typeof p !== 'object') return;
    if (typeof p.uv === 'number') store.uvBlacklight = p.uv === 1;
    if (typeof p.back === 'number') store.backlightOn = p.back === 1;
    if (typeof p.backInt === 'number') store.backlightIntensity = Math.min(1, Math.max(0.1, p.backInt));
    if (typeof p.sfx === 'number') store.analogSfx = p.sfx === 1;
    if (p.rpm === 33 || p.rpm === 45) store.rpm = p.rpm;
    if (typeof p.thumb === 'string' && ['split', 'pressing', 'sleeve', 'bin3d'].includes(p.thumb)) {
      store.thumbMode = p.thumb;
    }
    if (
      typeof p.spin === 'string' &&
      ['all', 'eyecandy', 'splatter', 'translucent', 'double_lp', 'etched', 'todo'].includes(p.spin)
    ) {
      store.spinMode = p.spin;
    }
  } catch {
    // Ignore malformed prefs
  }
}

export function getEloStats(releaseId) {
  const rid = String(releaseId);
  return store.eloMap[rid] || { elo: 1500, w: 0, l: 0, s: 0 };
}

export function saveCompactEloMap() {
  const entries = Object.entries(store.eloMap)
    .filter(([, v]) => v && (v.w > 0 || v.l > 0))
    .sort((a, b) => (b[1].w + b[1].l) - (a[1].w + a[1].l));
  let packed = '';
  for (const [rid, v] of entries) {
    const seg = `${rid}:${Math.round(v.elo)},${v.w},${v.l},${v.s}`;
    const candidate = packed ? `${packed}|${seg}` : seg;
    if (candidate.length > 4800) break;
    packed = candidate;
  }
  if (packed) {
    safeSetStorage(STORAGE_KEYS.ARENA_ELO, packed);
  } else {
    safeRemoveStorage(STORAGE_KEYS.ARENA_ELO);
  }
}

export function loadCompactEloMap() {
  const raw = safeGetStorage(STORAGE_KEYS.ARENA_ELO);
  if (!raw) return;
  const out = {};
  for (const seg of raw.split('|')) {
    const [rid, nums] = seg.split(':');
    if (!rid || !nums) continue;
    const [elo, w, l, s] = nums.split(',').map(Number);
    if (Number.isFinite(elo)) {
      out[rid] = {
        elo: Math.round(elo),
        w: Number.isFinite(w) ? w : 0,
        l: Number.isFinite(l) ? l : 0,
        s: Number.isFinite(s) ? s : 0,
      };
    }
  }
  store.eloMap = out;
}

export function recordEloMatchResult(winnerId, loserId) {
  const wKey = String(winnerId);
  const lKey = String(loserId);
  const wPrev = { ...getEloStats(wKey) };
  const lPrev = { ...getEloStats(lKey) };
  const expectedW = 1 / (1 + Math.pow(10, (lPrev.elo - wPrev.elo) / 400));
  const expectedL = 1 - expectedW;
  const k = 32;
  const deltaW = Math.max(1, Math.round(k * (1 - expectedW)));
  const deltaL = Math.max(1, Math.round(k * expectedL));

  store.eloMap[wKey] = {
    elo: wPrev.elo + deltaW,
    w: wPrev.w + 1,
    l: wPrev.l,
    s: wPrev.s + 1,
  };
  store.eloMap[lKey] = {
    elo: Math.max(900, lPrev.elo - deltaL),
    w: lPrev.w,
    l: lPrev.l + 1,
    s: 0,
  };
  saveCompactEloMap();
  emit('eloUpdated', { winnerId: wKey, loserId: lKey, deltaW, deltaL });
  return { deltaW, deltaL, winnerStats: store.eloMap[wKey], loserStats: store.eloMap[lKey] };
}

export function loadFlatteningNotes() {
  const raw = safeGetStorage(STORAGE_KEYS.FLATTEN_NOTES);
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') store.flatteningNotes = parsed;
  } catch {
    store.flatteningNotes = {};
  }
}

export function setFlatteningNote(releaseId, noteText) {
  const rid = String(releaseId);
  const clean = String(noteText || '').trim().slice(0, 140);
  if (clean) store.flatteningNotes[rid] = clean;
  else delete store.flatteningNotes[rid];
  // Trim oldest if approaching cookie limit
  const keys = Object.keys(store.flatteningNotes);
  while (JSON.stringify(store.flatteningNotes).length > 4200 && keys.length > 0) {
    delete store.flatteningNotes[keys.shift()];
  }
  if (Object.keys(store.flatteningNotes).length) {
    safeSetStorage(STORAGE_KEYS.FLATTEN_NOTES, JSON.stringify(store.flatteningNotes));
  } else {
    safeRemoveStorage(STORAGE_KEYS.FLATTEN_NOTES);
  }
}

// =========================================================================
// Flattening Queue & Overrides Reconciliation (Matches Python Contract)
// =========================================================================
export function normalizeDefaultFlatteningStatuses() {
  for (const rec of store.records) {
    if (!rec.flattening_status) {
      rec.flattening_status = DEFAULT_FLATTENING_STATUS;
    }
  }
}

export function buildFlatteningQueueObject(customTimestamp = '') {
  const ts = customTimestamp || new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const protoEl = document.getElementById('flatten-hidden-protocol');
  const protocol = (protoEl && protoEl.value)
    ? protoEl.value
    : 'Bag on 6 until 130°F then drop to 4 — 2.5 hours once at 130°F on the plate';

  const todoRecs = store.records
    .filter((r) => (r.flattening_status || DEFAULT_FLATTENING_STATUS) === 'Need to be done')
    .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));
  const doneRecs = store.records
    .filter((r) => r.flattening_status === 'Done')
    .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));
  const explicitUnlistedIds = store.records
    .filter((r) => r.flattening_status === 'Not Listed')
    .map((r) => Number(r.release_id))
    .filter(Boolean);

  const todoIds = todoRecs.map((r) => Number(r.release_id)).filter(Boolean).sort((a, b) => a - b);
  const doneIds = doneRecs.map((r) => Number(r.release_id)).filter(Boolean).sort((a, b) => a - b);

  const unlistedEl = document.getElementById('flatten-hidden-unlisted-ids');
  const prevUnlisted = (unlistedEl && unlistedEl.value)
    ? unlistedEl.value.split(',').map((x) => Number(x.trim())).filter(Boolean)
    : [];
  const unlistedIds = Array.from(new Set([...prevUnlisted, ...explicitUnlistedIds]))
    .filter((id) => !todoIds.includes(id) && !doneIds.includes(id))
    .sort((a, b) => a - b);

  return {
    schema_version: '5.0.0',
    storage_mode: 'portable_inline_html+json',
    updated_at_utc: ts,
    protocol,
    need_to_be_done_release_ids: todoIds,
    done_release_ids: doneIds,
    unlisted_release_ids: unlistedIds,
    need_to_be_done_entries: todoRecs.map((r) => ({
      artist: r.artist,
      album: r.title,
      release_ids: [Number(r.release_id)],
    })),
    done_entries: doneRecs.map((r) => ({
      artist: r.artist,
      album: r.title,
      release_ids: [Number(r.release_id)],
    })),
  };
}

export function syncInlineFlatteningFormState(markEdited = false) {
  const fqObj = buildFlatteningQueueObject();
  const setHiddenVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) {
      el.value = val;
      el.setAttribute('value', val);
    }
  };
  setHiddenVal('flatten-hidden-updated-at', fqObj.updated_at_utc);
  setHiddenVal('flatten-hidden-todo-ids', fqObj.need_to_be_done_release_ids.join(','));
  setHiddenVal('flatten-hidden-done-ids', fqObj.done_release_ids.join(','));
  setHiddenVal('flatten-hidden-unlisted-ids', (fqObj.unlisted_release_ids || []).join(','));

  const jsonArea = document.getElementById('flatten-hidden-json');
  if (jsonArea) jsonArea.textContent = JSON.stringify(fqObj);

  if (window.__DISCOGS_COLLECTION__) {
    window.__DISCOGS_COLLECTION__.flattening_queue = fqObj;
    if (window.__DISCOGS_COLLECTION__.profile) {
      window.__DISCOGS_COLLECTION__.profile.flattening_need_to_be_done = fqObj.need_to_be_done_release_ids.length;
      window.__DISCOGS_COLLECTION__.profile.flattening_done = fqObj.done_release_ids.length;
    }
  }

  if (markEdited) {
    store.unsavedFlattenCount += 1;
    // Store compact form without bloated entries arrays so kv1_* cookie stays < 2KB
    const compact = {
      updated_at_utc: fqObj.updated_at_utc,
      protocol: fqObj.protocol,
      need_to_be_done_release_ids: fqObj.need_to_be_done_release_ids,
      done_release_ids: fqObj.done_release_ids,
      unlisted_release_ids: fqObj.unlisted_release_ids,
    };
    safeSetStorage(STORAGE_KEYS.FLATTEN_QUEUE, JSON.stringify(compact));
  }
  emit('sessionEditsChanged');
  return fqObj;
}

export function applyFlatteningQueueObjectToRecords(fqObj) {
  if (!fqObj || typeof fqObj !== 'object') return;
  const todoSet = new Set((fqObj.need_to_be_done_release_ids || []).map(Number));
  const doneSet = new Set((fqObj.done_release_ids || []).map(Number));
  const unlistedSet = new Set((fqObj.unlisted_release_ids || []).map(Number));

  if (!todoSet.size && !doneSet.size && !unlistedSet.size) {
    normalizeDefaultFlatteningStatuses();
    return;
  }

  for (const rec of store.records) {
    const rid = Number(rec.release_id);
    if (unlistedSet.has(rid)) rec.flattening_status = 'Not Listed';
    else if (todoSet.has(rid)) rec.flattening_status = 'Need to be done';
    else if (doneSet.has(rid)) rec.flattening_status = 'Done';
    else rec.flattening_status = DEFAULT_FLATTENING_STATUS;
  }
}

export function setRecordFlatteningStatus(releaseId, newStatus) {
  const rid = Number(releaseId);
  const rec = store.records.find((r) => Number(r.release_id) === rid);
  if (!rec) return;

  rec.flattening_status = newStatus;
  const unlistedEl = document.getElementById('flatten-hidden-unlisted-ids');
  if (unlistedEl) {
    const cur = unlistedEl.value ? unlistedEl.value.split(',').map((x) => Number(x.trim())).filter(Boolean) : [];
    if (newStatus === 'Not Listed') {
      if (!cur.includes(rid)) cur.push(rid);
    } else {
      const idx = cur.indexOf(rid);
      if (idx !== -1) cur.splice(idx, 1);
    }
    const nextVal = cur.join(',');
    unlistedEl.value = nextVal;
    unlistedEl.setAttribute('value', nextVal);
  }

  syncInlineFlatteningFormState(true);
  emit('flatteningChanged', rec);
  emit('recordsChanged');

  const labelMap = {
    'Need to be done': '🔥 Queued for Arrival Inspection / Flattening',
    Done: '✓ Verified Flat / Done',
    'Not Listed': 'Excluded from Flattening Queue (Not Listed)',
  };
  showToast(`${rec.artist} — "${rec.title}": ${labelMap[newStatus] || newStatus}`);
}

export function pinReleasePressingOverride(releaseId, url, indexNum) {
  const rid = String(releaseId);
  const pinObj = {
    pressing_image_index: Number(indexNum || 0),
    user_locked: true,
    uri: url,
  };
  store.userOverrides[rid] = pinObj;
  store.localOverrideEdits[rid] = pinObj;

  const rec = store.records.find((r) => String(r.release_id) === rid);
  if (rec && rec.images) {
    rec.images.pressing_image_url = url;
    rec.images.has_pressing_photo = true;
    rec.images.selected_index = Number(indexNum || 0);
    const matched = (rec.images.classified_images || []).find(
      (im) => im.index === Number(indexNum) || im.uri === url || im.local_uri === url
    );
    rec.images.local_pressing_image_url = matched && matched.local_uri ? matched.local_uri : url;
  }

  store.unsavedPinCount += 1;
  safeSetStorage(STORAGE_KEYS.OVERRIDES, JSON.stringify(store.localOverrideEdits));
  emit('sessionEditsChanged');
  emit('overridesChanged', rec);
  emit('recordsChanged');
  showToast(`Pinned image [${indexNum}] as verified pressing for #${rid}!`);
}

export function clearReleasePressingOverride(releaseId) {
  const rid = String(releaseId);
  delete store.userOverrides[rid];
  store.localOverrideEdits[rid] = null;
  const rec = store.records.find((r) => String(r.release_id) === rid);
  if (rec && rec.images) {
    rec.images.pressing_image_url = '';
    rec.images.local_pressing_image_url = '';
    rec.images.has_pressing_photo = false;
  }
  store.unsavedPinCount += 1;
  safeSetStorage(STORAGE_KEYS.OVERRIDES, JSON.stringify(store.localOverrideEdits));
  emit('sessionEditsChanged');
  emit('overridesChanged', rec);
  emit('recordsChanged');
  showToast(`Switched #${rid} to deterministic procedural wax shader.`);
}

export function applyLocalOverrideEditsToRecords() {
  for (const [rid, editVal] of Object.entries(store.localOverrideEdits || {})) {
    const rec = store.records.find((r) => String(r.release_id) === String(rid));
    if (editVal === null) {
      delete store.userOverrides[rid];
      if (rec && rec.images) {
        rec.images.pressing_image_url = '';
        rec.images.local_pressing_image_url = '';
        rec.images.has_pressing_photo = false;
      }
    } else if (editVal) {
      store.userOverrides[rid] = editVal;
      const url = typeof editVal === 'object' ? (editVal.uri || editVal.local_uri || '') : String(editVal);
      if (rec && rec.images && url) {
        rec.images.pressing_image_url = url;
        rec.images.has_pressing_photo = true;
        if (typeof editVal === 'object' && typeof editVal.pressing_image_index === 'number') {
          rec.images.selected_index = editVal.pressing_image_index;
        }
        const matched = (rec.images.classified_images || []).find(
          (im) => (typeof editVal === 'object' && im.index === editVal.pressing_image_index) || im.uri === url || im.local_uri === url
        );
        rec.images.local_pressing_image_url = matched && matched.local_uri ? matched.local_uri : url;
      }
    }
  }
}

// =========================================================================
// Filtering & Sorting
// =========================================================================
export function applyFiltersAndSort(shouldEmit = true) {
  const prevActive = getActiveRecord();
  const prevRid = prevActive ? Number(prevActive.release_id) : 0;
  const q = store.searchQuery.trim().toLowerCase();

  const list = store.records.filter((rec) => {
    const wax = rec.wax_spec || {};
    if (store.filterArtist && rec.artist !== store.filterArtist) return false;
    if (store.filterLabel && rec.label !== store.filterLabel) return false;
    if (store.filterYear && Number(rec.year) !== Number(store.filterYear)) return false;
    if (store.filterColorHex && (wax.primary_color || '').toLowerCase() !== store.filterColorHex.toLowerCase()) {
      return false;
    }

    if (q) {
      const hay = `${rec.artist || ''} ${rec.title || ''} ${rec.label || ''} ${rec.catno || ''} ${rec.year || ''} ${rec.format_string || ''} ${wax.variant_badge || ''} ${rec.comments || ''} ${rec.flattening_status || ''} ${rec.release_id || ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }

    if (store.filter === 'pressing_photo') return Boolean(getVerifiedPressingPhotoUrl(rec, store.userOverrides));
    if (store.filter === 'flattening_todo') return (rec.flattening_status || DEFAULT_FLATTENING_STATUS) === 'Need to be done';
    if (store.filter === 'flattening_done') return rec.flattening_status === 'Done';
    if (store.filter === 'splatter') return ['splatter', 'color_in_color'].includes(wax.pattern);
    if (store.filter === 'galaxy_marble') return ['galaxy', 'marble', 'split'].includes(wax.pattern);
    if (store.filter === 'translucent') return Boolean(wax.translucent);
    if (store.filter === 'double_lp') return Boolean(wax.is_double_lp);
    if (store.filter === 'etched') return Boolean(wax.etched);
    if (store.filter === 'black_wax') return wax.pattern === 'black';
    return true;
  });

  list.sort((a, b) => {
    if (store.sortBy === 'artist_asc') return a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title);
    if (store.sortBy === 'title_asc') return a.title.localeCompare(b.title);
    if (store.sortBy === 'value_desc') return getNumericUsdValue(b) - getNumericUsdValue(a);
    if (store.sortBy === 'year_desc') return (b.year || 0) - (a.year || 0);
    if (store.sortBy === 'elo_desc') return getEloStats(b.release_id).elo - getEloStats(a.release_id).elo;
    return (b.date_added || '').localeCompare(a.date_added || '') || a.artist.localeCompare(b.artist);
  });

  store.filteredRecords = list;
  const keptIdx = prevRid ? list.findIndex((r) => Number(r.release_id) === prevRid) : -1;
  store.activeIndex = keptIdx >= 0 ? keptIdx : 0;

  if (shouldEmit) {
    emit('recordsChanged');
  }
}

// =========================================================================
// URL Deep-Link State
// =========================================================================
export function syncStateFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search);
    const view = params.get('view');
    if (view && ['showcase', 'arena', 'analytics', 'pipeline', 'flattening'].includes(view)) {
      store.activeTab = view;
    }
    const crate = params.get('crate');
    if (crate && ['split', 'pressing', 'sleeve', 'bin3d'].includes(crate)) {
      store.thumbMode = crate;
    }
    const arena = params.get('arena');
    if (arena && ['elo', 'artist', 'bracket', 'blind'].includes(arena)) {
      store.arenaMode = arena;
    }
    const ridParam = Number(params.get('release') || 0);
    if (ridParam > 0) {
      const idx = store.filteredRecords.findIndex((r) => Number(r.release_id) === ridParam);
      if (idx !== -1) store.activeIndex = idx;
    }
  } catch {
    // Ignore restricted URL environments
  }
}

export function syncUrlFromState() {
  try {
    if (window.location.protocol === 'file:') return;
    const rec = getActiveRecord();
    const params = new URLSearchParams(window.location.search);
    if (rec && rec.release_id) params.set('release', String(rec.release_id));
    params.set('view', store.activeTab);
    params.set('crate', store.thumbMode);
    if (store.activeTab === 'arena') params.set('arena', store.arenaMode);
    else params.delete('arena');
    const nextUrl = `${window.location.pathname}?${params.toString()}${window.location.hash || ''}`;
    window.history.replaceState(null, '', nextUrl);
  } catch {
    // Ignore history API blocks
  }
}

// =========================================================================
// Hydration: Embedded Payload + ./data/*.json Auto-Fetch & Reconcile
// =========================================================================
export async function hydrateVaultStore() {
  safeRemoveStorage('krunked_discogs_collection_v2_1');
  loadUiPrefs();
  loadCompactEloMap();
  loadFlatteningNotes();

  const baseOverrides =
    window.__DISCOGS_OVERRIDES__ && typeof window.__DISCOGS_OVERRIDES__ === 'object'
      ? window.__DISCOGS_OVERRIDES__
      : {};

  let localOverrides = {};
  const savedOverrides = safeGetStorage(STORAGE_KEYS.OVERRIDES);
  if (savedOverrides) {
    try {
      localOverrides = JSON.parse(savedOverrides) || {};
    } catch {
      localOverrides = {};
    }
  }

  const deltaEdits = {};
  let hadBloated = false;
  for (const [k, v] of Object.entries(localOverrides)) {
    if (v === null) deltaEdits[k] = null;
    else if (JSON.stringify(baseOverrides[k]) !== JSON.stringify(v)) deltaEdits[k] = v;
    else hadBloated = true;
  }
  store.localOverrideEdits = deltaEdits;
  store.unsavedPinCount = Object.keys(deltaEdits).length;
  if (hadBloated) {
    if (Object.keys(deltaEdits).length > 0) safeSetStorage(STORAGE_KEYS.OVERRIDES, JSON.stringify(deltaEdits));
    else safeRemoveStorage(STORAGE_KEYS.OVERRIDES);
  }
  store.userOverrides = { ...baseOverrides };

  let data = window.__DISCOGS_COLLECTION__;
  if (!data || !Array.isArray(data.records) || !data.records.length) {
    try {
      const resp = await fetch('./data/collection.json', { cache: 'no-store' });
      if (resp.ok) {
        data = await resp.json();
        window.__DISCOGS_COLLECTION__ = data;
      }
    } catch {
      // Offline / file:// without embedded payload
    }
  }

  if (data && Array.isArray(data.records)) {
    store.records = data.records;
  }

  applyLocalOverrideEditsToRecords();
  normalizeDefaultFlatteningStatuses();

  const todoInput = document.getElementById('flatten-hidden-todo-ids');
  const doneInput = document.getElementById('flatten-hidden-done-ids');
  const unlistedInput = document.getElementById('flatten-hidden-unlisted-ids');
  const htmlTsInput = document.getElementById('flatten-hidden-updated-at');

  if (todoInput && doneInput && (todoInput.value || doneInput.value || (unlistedInput && unlistedInput.value))) {
    applyFlatteningQueueObjectToRecords({
      need_to_be_done_release_ids: todoInput.value.split(',').map((x) => Number(x.trim())).filter(Boolean),
      done_release_ids: doneInput.value.split(',').map((x) => Number(x.trim())).filter(Boolean),
      unlisted_release_ids: unlistedInput && unlistedInput.value
        ? unlistedInput.value.split(',').map((x) => Number(x.trim())).filter(Boolean)
        : [],
    });
  }

  const savedFlatten = safeGetStorage(STORAGE_KEYS.FLATTEN_QUEUE);
  if (savedFlatten) {
    try {
      const parsedFq = JSON.parse(savedFlatten);
      const htmlTs = htmlTsInput && htmlTsInput.value ? htmlTsInput.value : '';
      if (parsedFq && (!htmlTs || (parsedFq.updated_at_utc && parsedFq.updated_at_utc > htmlTs))) {
        applyFlatteningQueueObjectToRecords(parsedFq);
        store.unsavedFlattenCount = 1;
      }
    } catch {
      // Ignore malformed stored queue
    }
  }

  syncInlineFlatteningFormState(false);
  applyFiltersAndSort(false);
  syncStateFromUrl();
}

export async function refreshExternalJsonIfNewer() {
  if (window.location.protocol === 'file:') return;
  try {
    const [ovResp, manifestResp, fqResp] = await Promise.all([
      fetch('./data/overrides.json', { cache: 'no-store' }).catch(() => null),
      fetch('./data/sync_manifest.json', { cache: 'no-store' }).catch(() => null),
      fetch('./data/flattening_queue.json', { cache: 'no-store' }).catch(() => null),
    ]);

    let changed = false;
    if (ovResp && ovResp.ok) {
      const extOv = await ovResp.json();
      if (extOv && typeof extOv === 'object') {
        for (const [k, v] of Object.entries(extOv)) {
          if (Object.prototype.hasOwnProperty.call(store.localOverrideEdits, k)) continue;
          if (JSON.stringify(store.userOverrides[k]) !== JSON.stringify(v)) {
            store.userOverrides[k] = v;
            changed = true;
          }
        }
      }
    }

    const curCol = window.__DISCOGS_COLLECTION__ || {};
    const curTotalUsd = Number(((curCol.profile || {}).collection_value || {}).total_estimated_usd || 0);
    let shouldFetchCol = !store.records.length;

    if (manifestResp && manifestResp.ok) {
      try {
        const man = await manifestResp.json();
        if (man && typeof man === 'object') {
          const newerTs = Boolean(curCol.synced_at_utc && man.synced_at_utc && man.synced_at_utc > curCol.synced_at_utc);
          const countDiff = Number(man.record_count || 0) !== store.records.length;
          const valDiff = Math.abs(Number(man.collection_value_total_usd || 0) - curTotalUsd) > 0.01;
          shouldFetchCol = shouldFetchCol || newerTs || countDiff || valDiff;
        }
      } catch {
        // Ignore invalid manifest
      }
    }

    if (shouldFetchCol) {
      const colResp = await fetch('./data/collection.json', { cache: 'no-store' }).catch(() => null);
      if (colResp && colResp.ok) {
        const extCol = await colResp.json();
        if (extCol && Array.isArray(extCol.records) && extCol.records.length > 0) {
          window.__DISCOGS_COLLECTION__ = extCol;
          store.records = extCol.records;
          store.streamCache = {};
          applyLocalOverrideEditsToRecords();
          normalizeDefaultFlatteningStatuses();
          changed = true;
        }
      }
    }

    if (fqResp && fqResp.ok && !store.unsavedFlattenCount) {
      const extFq = await fqResp.json();
      const inlineTs = (document.getElementById('flatten-hidden-updated-at') || {}).value || '';
      if (extFq && extFq.updated_at_utc && (!inlineTs || extFq.updated_at_utc > inlineTs)) {
        applyFlatteningQueueObjectToRecords(extFq);
        syncInlineFlatteningFormState(false);
        changed = true;
      }
    }

    if (changed) {
      applyFiltersAndSort(true);
      emit('flatteningChanged');
    }
  } catch {
    // Ignore transient network errors
  }
}
