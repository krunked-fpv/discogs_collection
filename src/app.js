    const state = {
      records: [],
      filteredRecords: [],
      activeIndex: 0,
      thumbMode: 'split', // 'pressing' | 'split' | 'sleeve'
      stageMode: 'auto',  // 'auto' | 'sleeve'
      activeTab: 'showcase', // 'showcase' | 'arena' | 'pipeline' | 'flattening'
      filter: 'all',
      sortBy: 'added_desc',
      searchQuery: '',
      doneSearchQuery: '',
      benchSearchQuery: '',
      isSpinning: true,
      rpm: 33,
      audioPlaying: false,
      audioCtx: null,
      analogSfx: true,
      uvBlacklight: true,
      spinMode: 'all', // 'all' | 'showroom' | 'eyecandy'
      showroomCountdown: 15,
      showroomTickInterval: null,
      isSpinningRoulette: false,
      arenaPoolMode: 'all', // 'all' | 'eyecandy' | 'flat'
      arenaBracket: [],
      arenaWinners: [],
      arenaStage: 0, // 0: Semi 1, 1: Semi 2, 2: Final, 3: Champion Crowned
      arenaChampion: null,
      userOverrides: {},       // release_id -> pinned pressing image URL
      releaseGalleryCache: {}, // release_id -> array of Discogs image objects
      unsavedPinCount: 0,
      unsavedFlattenCount: 0,
      timerInterval: null,
      isCardFlipped: false,
      preferredService: 'ytm',
      showVideoStage: true,
      autoAdvanceTracks: true,
      activePlaybackEngine: 'yt',
      ytApiReady: false,
      ytApiLoading: false,
      ytPlayer: null,
      ytPlayerReady: false,
      ytCurrentVideoId: '',
      ytCurrentPlaylistId: '',
      ytIsFullAlbumStream: false,
      ytIsPlaylistMode: false,
      ytFallbackCanvasMode: false,
      ytProgressTimer: null,
      ytPendingAction: null,
      failedYtIds: new Set(),
      streamCache: {},
      previewUrlCache: {},
      activeStreamRid: null,
      cuedStreamRid: null,
      activeTrackIndex: -1,
      isPreviewPlaying: false,
    };

    function safeGetStorage(key) {
      try { return localStorage.getItem(key); } catch (e) { return null; }
    }
    function safeSetStorage(key, val) {
      try { localStorage.setItem(key, val); } catch (e) {}
    }
    function safeRemoveStorage(key) {
      try { localStorage.removeItem(key); } catch (e) {}
    }

    function showToast(msg) {
      const el = document.getElementById('toast-banner');
      if (!el) return;
      el.textContent = msg;
      el.classList.remove('hidden');
      clearTimeout(window.__toastTimer);
      window.__toastTimer = setTimeout(() => el.classList.add('hidden'), 3600);
    }

    // =========================================================================
    // v5.0 WEB AUDIO ANALOG SFX SYNTHESIZER & 60FPS PARTICLE BURST ENGINE
    // =========================================================================
    let sfxCtx = null;

    function ensureSfxCtx() {
      if (!sfxCtx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (AC) sfxCtx = new AC();
      }
      if (sfxCtx && sfxCtx.state === 'suspended') {
        sfxCtx.resume().catch(() => {});
      }
      return sfxCtx;
    }

    // Velocity-sensitive mechanical crate sleeve flip tick
    function playCrateTickSound(pitchFactor = 1.0) {
      if (!state.analogSfx) return;
      try {
        const ctx = ensureSfxCtx();
        if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(240 * pitchFactor, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(58, ctx.currentTime + 0.036);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.038);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.04);
      } catch (e) {}
    }

    // Warm analog stylus needle drop thump + micro-crackle kiss
    function playNeedleDropSound() {
      if (!state.analogSfx) return;
      try {
        const ctx = ensureSfxCtx();
        if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(98, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(26, ctx.currentTime + 0.19);
        gain.gain.setValueAtTime(0.28, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.21);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.22);
      } catch (e) {}
    }

    // Triumphant warm synth chord on Roulette Lock-In or Arena Crown
    function playRouletteWinChord(isArenaChampion = false) {
      if (!state.analogSfx) return;
      try {
        const ctx = ensureSfxCtx();
        if (!ctx) return;
        const freqs = isArenaChampion
          ? [261.63, 329.63, 392.00, 523.25, 659.25]
          : [293.66, 369.99, 440.00, 587.33];
        freqs.forEach((f, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = idx % 2 === 0 ? 'triangle' : 'sine';
          const startT = ctx.currentTime + idx * 0.045;
          osc.frequency.setValueAtTime(f, startT);
          gain.gain.setValueAtTime(0.09, startT);
          gain.gain.exponentialRampToValueAtTime(0.0008, startT + 0.45);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(startT);
          osc.stop(startT + 0.46);
        });
      } catch (e) {}
    }

    // UV Blacklight Tube Ignition / Power-Down SFX
    function playUvToggleSound(turningOn) {
      if (!state.analogSfx) return;
      try {
        const ctx = ensureSfxCtx();
        if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sawtooth';
        const now = ctx.currentTime;
        osc.frequency.setValueAtTime(turningOn ? 110 : 320, now);
        osc.frequency.exponentialRampToValueAtTime(turningOn ? 440 : 85, now + 0.16);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.19);
      } catch (e) {}
    }

    // 60FPS Particle Confetti Burst Canvas Engine
    const fxCanvas = document.getElementById('fx-particles-canvas');
    const fxCtx = fxCanvas ? fxCanvas.getContext('2d') : null;
    let fxParticles = [];
    let fxAnimRunning = false;

    function resizeFxCanvas() {
      if (!fxCanvas) return;
      fxCanvas.width = window.innerWidth;
      fxCanvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeFxCanvas);
    resizeFxCanvas();

    function tickParticles() {
      if (!fxCtx || !fxCanvas) return;
      fxCtx.clearRect(0, 0, fxCanvas.width, fxCanvas.height);
      for (let i = fxParticles.length - 1; i >= 0; i--) {
        const p = fxParticles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.22;
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
          fxCtx.shadowBlur = 8;
          fxCtx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.7);
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

    function spawnParticles(c1, c2, c3, count = 64) {
      if (!fxCanvas || !fxCtx) return;
      const platterEl = document.getElementById('turntable-plinth-box');
      let cx = window.innerWidth * 0.35;
      let cy = window.innerHeight * 0.45;
      if (platterEl && state.activeTab === 'showcase') {
        const rect = platterEl.getBoundingClientRect();
        if (rect.width > 0) {
          cx = rect.left + rect.width / 2;
          cy = rect.top + rect.height / 2;
        }
      } else {
        cx = window.innerWidth / 2;
        cy = window.innerHeight * 0.38;
      }
      const palette = [c1 || '#d946ef', c2 || '#06b6d4', c3 || '#facc15', '#38bdf8', '#ffffff'];
      for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = 3.2 + Math.random() * 9.5;
        fxParticles.push({
          x: cx,
          y: cy,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed - 2.4,
          size: 4 + Math.random() * 6,
          color: palette[i % palette.length],
          alpha: 1,
          decay: 0.015 + Math.random() * 0.014,
          rotation: Math.random() * Math.PI * 2,
          vRot: (Math.random() - 0.5) * 0.25,
        });
      }
      if (!fxAnimRunning) {
        fxAnimRunning = true;
        requestAnimationFrame(tickParticles);
      }
    }

    // Deterministic Discogs Format & Variant Parser (matches detect_pressing_image.py)
    function parseWaxVariantJS(formatStr, notesStr, releaseId = 0) {
      const combined = `${formatStr || ''} ${notesStr || ''}`.toLowerCase();
      const colorMap = [
        ['pur', '#8b2cf5', 'Purple', true],
        ['purple', '#8b2cf5', 'Purple', true],
        ['vio', '#6d28d9', 'Violet', true],
        ['violet', '#6d28d9', 'Violet', true],
        ['pin', '#ec4899', 'Hot Pink', false],
        ['pink', '#ec4899', 'Hot Pink', false],
        ['mag', '#d946ef', 'Magenta', true],
        ['magenta', '#d946ef', 'Magenta', true],
        ['ora', '#f97316', 'Translucent Orange', true],
        ['orange', '#f97316', 'Translucent Orange', true],
        ['pea', '#fb923c', 'Peach', false],
        ['peach', '#fb923c', 'Peach', false],
        ['yel', '#eab308', 'Yellow', true],
        ['yellow', '#eab308', 'Yellow', true],
        ['can', '#facc15', 'Canary Yellow', false],
        ['gold', '#d97706', 'Metallic Gold', false],
        ['gre', '#10b981', 'Emerald Green', true],
        ['green', '#10b981', 'Emerald Green', true],
        ['aci', '#84cc16', 'Acid Green', true],
        ['neo', '#ccff00', 'Neon Highlighter', true],
        ['blu', '#2563eb', 'Cobalt Blue', true],
        ['blue', '#2563eb', 'Cobalt Blue', true],
        ['ele', '#06b6d4', 'Electric Blue', true],
        ['electric', '#06b6d4', 'Electric Blue', true],
        ['cyan', '#06b6d4', 'Cyan', true],
        ['lig', '#38bdf8', 'Light Sky Blue', true],
        ['cle', '#cbd5e1', 'Crystal Clear', true],
        ['clear', '#cbd5e1', 'Crystal Clear', true],
        ['ult', '#e2e8f0', 'Ultra Clear', true],
        ['mil', '#f1f5f9', 'Milky Clear', true],
        ['gho', '#94a3b8', 'Ghostly Clear', true],
        ['cok', '#5eead4', 'Coke Bottle Clear', true],
        ['whi', '#f8fafc', 'Opaque White', false],
        ['white', '#f8fafc', 'Opaque White', false],
        ['bone', '#fef3c7', 'Bone White', false],
        ['gra', '#64748b', 'Graphite Grey', false],
        ['grey', '#64748b', 'Graphite Grey', false],
        ['sil', '#94a3b8', 'Metallic Silver', false],
        ['dus', '#a8a29e', 'Dusty Smoke', true],
        ['hou', '#3b82f6', 'Blue/Cyan Swirl', true],
        ['gal', '#4f46e5', 'Galaxy Nebula', true],
        ['ruby', '#e11d48', 'Ruby Red', true],
        ['red', '#dc2626', 'Crimson Red', true],
        ['bla', '#18181b', '180g Black Wax', false],
        ['black', '#18181b', '180g Black Wax', false],
      ];

      const tokens = (formatStr || '').toLowerCase().split(/[,()+/:\s\[\]-]+/).filter(Boolean);
      const matched = [];
      for (const tok of tokens) {
        const found = colorMap.find(c => c[0] === tok);
        if (found && !matched.some(m => m[1] === found[1])) {
          matched.push(found);
        }
      }
      for (const entry of colorMap) {
        if (matched.some(m => m[1] === entry[1])) continue;
        const rx = entry[0].length <= 3
          ? new RegExp(`\\b${entry[0]}\\b`)
          : new RegExp(`\\b${entry[0]}`);
        if (rx.test(combined)) {
          matched.push(entry);
        }
      }
      if (!matched.length) matched.push(['bla', '#18181b', '180g Black Wax', false]);

      let pattern = 'solid_color';
      if (combined.includes('splatter') || combined.includes('starburst')) pattern = 'splatter';
      else if (combined.includes('in clear') || combined.includes('color-in-color') || combined.includes('bone in')) pattern = 'color_in_color';
      else if (combined.includes('gal') || combined.includes('smoke') || combined.includes('gho') || combined.includes('dus') || combined.includes('glitter')) pattern = 'galaxy';
      else if (combined.includes('swirl') || combined.includes('marb') || combined.includes('hou')) pattern = 'marble';
      else if (combined.includes('split') || combined.includes('smash') || combined.includes('twister') || combined.includes('neo')) pattern = 'split';
      else if (matched[0][1] === '#18181b') pattern = 'black';
      else if (matched[0][3]) pattern = 'translucent';

      const c1 = matched[0][1];
      const c2 = matched[1] ? matched[1][1] : (c1 === '#18181b' ? '#3f3f46' : '#18181b');
      const c3 = matched[2] ? matched[2][1] : '#38bdf8';
      const etched = combined.includes('etch');
      const is2lp = combined.includes('2xlp') || combined.includes('2x12') || combined.includes('2xvinyl') || combined.includes('2 x vinyl');
      const isLtd = combined.includes('ltd') || combined.includes('limited');

      const parts = [is2lp ? '2xLP' : '12" LP', matched[0][2]];
      if (pattern === 'splatter') parts.push('Splatter');
      else if (pattern === 'galaxy') parts.push('Galaxy');
      else if (pattern === 'color_in_color') parts.push('Color-in-Color');
      else if (pattern === 'marble') parts.push('Marble Swirl');
      else if (pattern === 'split') parts.push('Split Wax');
      if (etched) parts.push('Etched');
      if (isLtd) parts.push('Ltd Ed');

      return {
        pattern,
        primary_color: c1,
        secondary_color: c2,
        accent_color: c3,
        color_name: matched[0][2],
        translucent: Boolean(matched[0][3]),
        etched,
        is_double_lp: is2lp,
        is_limited: isLtd,
        variant_badge: parts.join(' • '),
        deterministic_seed: Math.abs(Number(releaseId || 12345) * 2654435761) % 1000000,
      };
    }

    // Helper: Get primary and fallback pressing photo URLs for a record
    function getPressingPhotoUrls(rec) {
      if (!rec) return { primary: '', fallback: '' };
      const rid = String(rec.release_id);
      const imgs = rec.images || {};
      const classified = Array.isArray(imgs.classified_images) ? imgs.classified_images : [];

      if (state.userOverrides[rid]) {
        const ovEntry = state.userOverrides[rid];
        const ovUrl = typeof ovEntry === 'object' ? (ovEntry.uri || ovEntry.local_uri || '') : String(ovEntry);
        const matchedImg = classified.find(im => im.uri === ovUrl || im.local_uri === ovUrl || (typeof ovEntry === 'object' && im.index === ovEntry.pressing_image_index));
        if (matchedImg && matchedImg.local_uri) {
          return { primary: matchedImg.local_uri, fallback: matchedImg.uri || ovUrl };
        }
        return { primary: ovUrl, fallback: imgs.pressing_image_url || ovUrl };
      }

      const localP = imgs.local_pressing_image_url || '';
      const remoteP = (imgs.has_pressing_photo && imgs.pressing_image_url && !imgs.pressing_image_url.startsWith('assets/pressings/'))
        ? imgs.pressing_image_url
        : '';

      if (localP && remoteP) return { primary: localP, fallback: remoteP };
      if (localP) return { primary: localP, fallback: '' };
      if (remoteP) return { primary: remoteP, fallback: '' };
      return { primary: '', fallback: '' };
    }

    function getVerifiedPressingPhotoUrl(rec) {
      const { primary, fallback } = getPressingPhotoUrls(rec);
      return primary || fallback || '';
    }

    // Helper: Get real Discogs front cover URL (preferring local cached cover.jpg with remote fallback)
    function getCoverUrls(rec) {
      if (!rec || !rec.images) return { primary: '', fallback: '' };
      const localC = rec.images.local_cover_image_url || '';
      const remoteC = rec.images.cover_image_url || '';
      if (localC && remoteC) return { primary: localC, fallback: remoteC };
      return { primary: localC || remoteC, fallback: remoteC };
    }

    function getRealCoverUrl(rec) {
      const { primary, fallback } = getCoverUrls(rec);
      return primary || fallback || '';
    }

    function getCenterLabelArtUrl(rec) {
      if (!rec || !rec.images) return '';
      return rec.images.local_cover_image_url || rec.images.center_label_image_url || rec.images.cover_image_url || '';
    }

    // Build and sync the portable inline HTML form (#flattening-inline-form) + window.__DISCOGS_COLLECTION__
    function buildFlatteningQueueObject(customTimestamp) {
      const ts = customTimestamp || new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
      const protoEl = document.getElementById('flatten-hidden-protocol');
      const protocol = (protoEl && protoEl.value)
        ? protoEl.value
        : 'Bag on 6 until 130°F then drop to 4 — 2.5 hours once at 130°F on the plate';

      const todoRecs = state.records
        .filter(r => r.flattening_status === 'Need to be done')
        .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));
      const doneRecs = state.records
        .filter(r => r.flattening_status === 'Done')
        .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));

      const todoIds = todoRecs.map(r => Number(r.release_id)).filter(Boolean).sort((a, b) => a - b);
      const doneIds = doneRecs.map(r => Number(r.release_id)).filter(Boolean).sort((a, b) => a - b);

      const unlistedEl = document.getElementById('flatten-hidden-unlisted-ids');
      const prevUnlisted = (unlistedEl && unlistedEl.value)
        ? unlistedEl.value.split(',').map(x => Number(x.trim())).filter(Boolean)
        : [];
      const unlistedIds = Array.from(new Set(prevUnlisted)).filter(id => !todoIds.includes(id) && !doneIds.includes(id)).sort((a, b) => a - b);

      return {
        schema_version: '5.0.0',
        storage_mode: 'portable_inline_html+json',
        updated_at_utc: ts,
        protocol,
        need_to_be_done_release_ids: todoIds,
        done_release_ids: doneIds,
        unlisted_release_ids: unlistedIds,
        need_to_be_done_entries: todoRecs.map(r => ({
          artist: r.artist,
          album: r.title,
          release_ids: [Number(r.release_id)],
        })),
        done_entries: doneRecs.map(r => ({
          artist: r.artist,
          album: r.title,
          release_ids: [Number(r.release_id)],
        })),
      };
    }

    function syncInlineFlatteningFormState(markEdited = false) {
      const fqObj = buildFlatteningQueueObject();
      const todoCsv = fqObj.need_to_be_done_release_ids.join(',');
      const doneCsv = fqObj.done_release_ids.join(',');
      const unlistedCsv = (fqObj.unlisted_release_ids || []).join(',');

      const setHiddenVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) {
          el.value = val;
          el.setAttribute('value', val);
        }
      };

      setHiddenVal('flatten-hidden-updated-at', fqObj.updated_at_utc);
      setHiddenVal('flatten-hidden-todo-ids', todoCsv);
      setHiddenVal('flatten-hidden-done-ids', doneCsv);
      setHiddenVal('flatten-hidden-unlisted-ids', unlistedCsv);

      const jsonArea = document.getElementById('flatten-hidden-json');
      if (jsonArea) {
        jsonArea.textContent = JSON.stringify(fqObj);
      }

      if (window.__DISCOGS_COLLECTION__) {
        window.__DISCOGS_COLLECTION__.flattening_queue = fqObj;
        if (window.__DISCOGS_COLLECTION__.profile) {
          window.__DISCOGS_COLLECTION__.profile.flattening_need_to_be_done = fqObj.need_to_be_done_release_ids.length;
          window.__DISCOGS_COLLECTION__.profile.flattening_done = fqObj.done_release_ids.length;
        }
      }

      if (markEdited) {
        state.unsavedFlattenCount++;
        safeSetStorage('krunked_flattening_state_v4', JSON.stringify(fqObj));
      }
      updateSessionEditIndicators();
      return fqObj;
    }

    function applyFlatteningQueueObjectToRecords(fqObj) {
      if (!fqObj || typeof fqObj !== 'object') return;
      const todoSet = new Set((fqObj.need_to_be_done_release_ids || []).map(Number));
      const doneSet = new Set((fqObj.done_release_ids || []).map(Number));
      const unlistedSet = new Set((fqObj.unlisted_release_ids || []).map(Number));

      if (!todoSet.size && !doneSet.size && !unlistedSet.size) return;

      for (const rec of state.records) {
        const rid = Number(rec.release_id);
        if (unlistedSet.has(rid)) {
          rec.flattening_status = 'Not Listed';
        } else if (todoSet.has(rid)) {
          rec.flattening_status = 'Need to be done';
        } else if (doneSet.has(rid)) {
          rec.flattening_status = 'Done';
        } else {
          rec.flattening_status = 'Not Listed';
        }
      }
    }

    function setRecordFlatteningStatus(releaseId, newStatus) {
      const rid = Number(releaseId);
      const rec = state.records.find(r => Number(r.release_id) === rid);
      if (!rec) return;

      rec.flattening_status = newStatus;

      // Track explicit unlisted removals so Python sync knows the user removed it
      const unlistedEl = document.getElementById('flatten-hidden-unlisted-ids');
      if (unlistedEl) {
        const cur = unlistedEl.value ? unlistedEl.value.split(',').map(x => Number(x.trim())).filter(Boolean) : [];
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
      updateKpiStrip();
      renderFlatteningView();
      renderHeroStage();
      renderCrateGrid();

      const labelMap = {
        'Need to be done': '🔥 Added to Flattening Queue',
        'Done': '✓ Marked Flattened & Verified',
        'Not Listed': 'Removed from Flattening Queue',
      };
      showToast(`${rec.artist} — "${rec.title}": ${labelMap[newStatus] || newStatus}`);
    }

    function updateSessionEditIndicators() {
      const totalEdits = state.unsavedPinCount + state.unsavedFlattenCount;
      const syncBtnLabel = document.getElementById('sync-btn-label');
      const syncBtnDot = document.getElementById('sync-btn-dot');
      if (syncBtnLabel) {
        syncBtnLabel.textContent = totalEdits > 0 ? `Sync & Export LP's (${totalEdits})` : `Sync & Export LP's`;
      }
      if (syncBtnDot) {
        syncBtnDot.className = totalEdits > 0
          ? 'w-2 h-2 rounded-full bg-amber-400 animate-ping'
          : 'w-2 h-2 rounded-full bg-emerald-400';
      }

      const inlineBadge = document.getElementById('flatten-inline-status');
      if (inlineBadge) {
        if (state.unsavedFlattenCount > 0) {
          inlineBadge.textContent = `● ${state.unsavedFlattenCount} Queue Edit${state.unsavedFlattenCount === 1 ? '' : 's'} — Click "Save Updated index.html" to Persist`;
          inlineBadge.className = 'px-2.5 py-1 rounded-lg text-[11px] font-mono-tech bg-amber-500/20 text-amber-300 border border-amber-500/30';
        } else {
          inlineBadge.textContent = '✓ Inline HTML Form Synced';
          inlineBadge.className = 'px-2.5 py-1 rounded-lg text-[11px] font-mono-tech bg-emerald-500/15 text-emerald-300 border border-emerald-500/30';
        }
      }

      const modalEdits = document.getElementById('modal-stat-edits');
      const modalEditsSub = document.getElementById('modal-stat-edits-sub');
      if (modalEdits && modalEditsSub) {
        if (totalEdits > 0) {
          modalEdits.textContent = `${totalEdits} Pending Edit${totalEdits === 1 ? '' : 's'}`;
          modalEdits.className = 'text-sm sm:text-base font-extrabold text-amber-300 mt-0.5';
          modalEditsSub.textContent = `${state.unsavedPinCount} Pin(s) • ${state.unsavedFlattenCount} Queue`;
        } else {
          modalEdits.textContent = '0 Unsaved';
          modalEdits.className = 'text-sm sm:text-base font-extrabold text-emerald-400 mt-0.5';
          modalEditsSub.textContent = 'In Sync with HTML';
        }
      }
    }

    // Generate a complete, self-contained index.html file with all current overrides, flattening state, and KPIs baked in
    function downloadSelfContainedIndexHtml() {
      const fqObj = syncInlineFlatteningFormState(false);
      const nowStamp = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
      fqObj.updated_at_utc = nowStamp;

      if (window.__DISCOGS_COLLECTION__) {
        window.__DISCOGS_COLLECTION__.synced_at_utc = nowStamp;
        window.__DISCOGS_COLLECTION__.schema_version = '5.0.0';
        window.__DISCOGS_COLLECTION__.records = state.records;
        window.__DISCOGS_COLLECTION__.flattening_queue = fqObj;
        if (window.__DISCOGS_COLLECTION__.profile) {
          window.__DISCOGS_COLLECTION__.profile.num_collection = state.records.length;
          window.__DISCOGS_COLLECTION__.profile.pressing_photos_detected = state.records.filter(r => Boolean(getVerifiedPressingPhotoUrl(r))).length;
          window.__DISCOGS_COLLECTION__.profile.flattening_need_to_be_done = fqObj.need_to_be_done_release_ids.length;
          window.__DISCOGS_COLLECTION__.profile.flattening_done = fqObj.done_release_ids.length;
        }
      }

      // Sync hidden inputs and reset unsaved edit indicators BEFORE cloning DOM
      const setHiddenVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) {
          el.value = val;
          el.setAttribute('value', val);
        }
      };
      setHiddenVal('flatten-hidden-updated-at', nowStamp);
      setHiddenVal('flatten-hidden-todo-ids', fqObj.need_to_be_done_release_ids.join(','));
      setHiddenVal('flatten-hidden-done-ids', fqObj.done_release_ids.join(','));
      setHiddenVal('flatten-hidden-unlisted-ids', (fqObj.unlisted_release_ids || []).join(','));
      const jsonArea = document.getElementById('flatten-hidden-json');
      if (jsonArea) jsonArea.textContent = JSON.stringify(fqObj);

      // Keep localStorage stamp aligned and clear unsaved badges prior to DOM snapshot
      safeSetStorage('__discogs_py_sync_stamp__', nowStamp);
      state.unsavedPinCount = 0;
      state.unsavedFlattenCount = 0;
      updateSessionEditIndicators();
      updateKpiStrip();

      // Clone and sanitize DOM so exported index.html never bakes extension bloat, Tailwind CDN CSS,
      // transient modal/toast state, non-default active tab visibility, or ephemeral pre-rendered list cards
      const docClone = document.documentElement.cloneNode(true);

      // 1. Strip Dark Reader / extension <style>/<meta> tags and Tailwind CDN runtime <style>
      docClone.querySelectorAll('style, meta').forEach(node => {
        const tag = node.tagName.toLowerCase();
        if (tag === 'meta' && /darkreader/i.test(node.getAttribute('name') || '')) {
          node.remove();
          return;
        }
        if (tag === 'style') {
          const cls = node.getAttribute('class') || '';
          const txt = node.textContent || '';
          if (/darkreader/i.test(cls) || txt.indexOf('tailwindcss v3') !== -1) {
            node.remove();
          }
        }
      });

      // 2. Strip LastPass / Dark Reader attributes and --darkreader-* inline styles across all nodes
      const sanitizeNodeAttrs = (el) => {
        if (!el || !el.attributes) return;
        const toRemove = [];
        for (let i = 0; i < el.attributes.length; i++) {
          const name = el.attributes[i].name;
          if (/^data-(lastpass|darkreader)/i.test(name)) {
            toRemove.push(name);
          }
        }
        toRemove.forEach(n => el.removeAttribute(n));
        if (el.hasAttribute('style')) {
          const cleaned = el.getAttribute('style')
            .split(';')
            .map(s => s.trim())
            .filter(s => s && !/^--darkreader-/i.test(s))
            .join('; ');
          if (cleaned) el.setAttribute('style', cleaned + ';');
          else el.removeAttribute('style');
        }
      };
      sanitizeNodeAttrs(docClone);
      docClone.querySelectorAll('*').forEach(sanitizeNodeAttrs);

      // 3. Remove runtime-appended Shadow-Cookie tooltip marker so it attaches cleanly on next boot
      const syncBtnClone = docClone.querySelector('#btn-live-sync-modal');
      if (syncBtnClone && syncBtnClone.getAttribute('data-cookie-vault')) {
        syncBtnClone.removeAttribute('data-cookie-vault');
        const t = (syncBtnClone.getAttribute('title') || '').replace(/\s*•?\s*Shadow-Cookie Auto-Healer Active \(400-Day Backup\)\s*$/, '');
        if (t) syncBtnClone.setAttribute('title', t);
      }

      // 4. Clear ephemeral runtime-populated containers, particle canvas dimensions, search inputs, modal & toast
      const fxCanvasClone = docClone.querySelector('#fx-particles-canvas');
      if (fxCanvasClone) {
        fxCanvasClone.removeAttribute('width');
        fxCanvasClone.removeAttribute('height');
      }
      ['collection-grid', 'arena-card-left', 'arena-card-right', 'flatten-todo-list', 'flatten-done-list', 'flatten-bench-list'].forEach(id => {
        const el = docClone.querySelector('#' + id);
        if (el) el.innerHTML = '';
      });
      ['search-input', 'flatten-done-search', 'flatten-bench-search'].forEach(id => {
        const el = docClone.querySelector('#' + id);
        if (el) el.removeAttribute('value');
      });
      const modalClone = docClone.querySelector('#modal-backdrop');
      if (modalClone) modalClone.classList.add('hidden');
      const toastClone = docClone.querySelector('#toast-banner');
      if (toastClone) {
        toastClone.classList.add('hidden');
        toastClone.textContent = '';
      }

      // 5. Normalize exported default view to Showcase so exported HTML always boots cleanly
      const viewIds = ['view-showcase', 'view-arena', 'view-pipeline', 'view-flattening'];
      viewIds.forEach(vid => {
        const v = docClone.querySelector('#' + vid);
        if (v) v.classList.toggle('hidden', vid !== 'view-showcase');
      });
      const tabIds = ['tab-btn-showcase', 'tab-btn-arena', 'tab-btn-pipeline', 'tab-btn-flattening'];
      tabIds.forEach(tid => {
        const b = docClone.querySelector('#' + tid);
        if (!b) return;
        b.className = (tid === 'tab-btn-showcase')
          ? 'px-3 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap bg-gradient-to-r from-fuchsia-600 to-cyan-600 text-white shadow-md'
          : 'px-3 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap text-slate-300 hover:text-white hover:bg-white/5';
      });

      let rawDoc = '<!DOCTYPE html>\n' + docClone.outerHTML;
      // v5.0: Clean HTML5 <audio> 30s preview deck (no YouTube iframe bridge)

      const overridesJs = JSON.stringify(state.userOverrides, null, 2);
      const collectionJs = JSON.stringify(window.__DISCOGS_COLLECTION__, null, 2);
      const replacementBlock = [
        '/* __DISCOGS_COLLECTION_DATA_' + 'START__ */',
        `    window.__DISCOGS_OVERRIDES__ = ${overridesJs};`,
        `    window.__DISCOGS_COLLECTION__ = ${collectionJs};`,
        '    try {',
        `      var __pySyncStamp = ${JSON.stringify(nowStamp)};`,
        "      if (typeof localStorage !== 'undefined' && localStorage.getItem('__discogs_py_sync_stamp__') !== __pySyncStamp) {",
        '        Object.keys(localStorage).forEach(function(k) {',
        "          if (k.toLowerCase().indexOf('token') === -1 && k.indexOf('flattening_timer') === -1) {",
        '            localStorage.removeItem(k);',
        '          }',
        '        });',
        "        localStorage.setItem('__discogs_py_sync_stamp__', __pySyncStamp);",
        '      }',
        '    } catch (e) {}',
        '    /* __DISCOGS_COLLECTION_DATA_' + 'END__ */',
      ].join('\n');

      rawDoc = rawDoc.replace(
        new RegExp('\\/\\*\\s*__DISCOGS_COLLECTION_DATA_' + 'START__\\s*\\*\\/[\\s\\S]*?\\/\\*\\s*__DISCOGS_COLLECTION_DATA_' + 'END__\\s*\\*\\/'),
        () => replacementBlock
      );

      const blob = new Blob([rawDoc], { type: 'text/html;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'index.html';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Downloaded self-contained index.html with inline flattening state & pins baked in!');
    }

    // Render Vinyl Disc:
    // Defaults the 'wax ring' to the release's actual pressing photo whenever available,
    // falling back to the deterministic SVG wax shader ONLY when no pressing photo exists on Discogs.
    function renderDeterministicWaxSVG(rec, sizePx = 240, allowVerifiedPressingPhoto = true) {
      const wax = rec.wax_spec || {};
      const c1 = wax.primary_color || '#18181b';
      const c2 = wax.secondary_color || '#3f3f46';
      const c3 = wax.accent_color || '#06b6d4';
      const pattern = wax.pattern || 'black';
      const seed = Math.abs(Number(wax.deterministic_seed || rec.release_id || 12345));

      if (allowVerifiedPressingPhoto) {
        const { primary, fallback } = getPressingPhotoUrls(rec);
        const activeUrl = primary || fallback;
        if (activeUrl) {
          const onErrAttr = (fallback && fallback !== activeUrl)
            ? `onerror="if(this.dataset.fb && this.src!==this.dataset.fb){this.src=this.dataset.fb;}" data-fb="${fallback}"`
            : '';
          return `
            <div class="relative w-full h-full rounded-full overflow-hidden shadow-2xl border-2 border-white/25 bg-slate-950 select-none">
              <img src="${activeUrl}" ${onErrAttr} referrerpolicy="no-referrer" alt="${rec.artist} - ${rec.title} pressing" class="w-full h-full object-cover rounded-full" />
              <div class="absolute inset-0 rounded-full ring-1 ring-inset ring-white/20 pointer-events-none" style="background: radial-gradient(circle, transparent 62%, rgba(0,0,0,0.22) 96%, rgba(255,255,255,0.16) 100%);"></div>
              <div class="absolute inset-[47.8%] rounded-full bg-[#05060a]/90 border border-white/35 pointer-events-none"></div>
            </div>
          `;
        }
      }

      const centerArtUrl = getCenterLabelArtUrl(rec);
      const uid = 'wax-' + rec.release_id + '-' + sizePx + '-' + Math.floor(Math.random() * 10000);

      let raysSvg = '';
      for (let i = 0; i < 28; i++) {
        const angle = ((seed + i * 47) % 360);
        const len = 28 + ((seed + i * 13) % 18);
        const col = (i % 3 === 0) ? c3 : c2;
        const width = (i % 4 === 0) ? 2.2 : 1.25;
        raysSvg += `<line x1="50" y1="50" x2="${50 + len * Math.cos(angle * Math.PI / 180)}" y2="${50 + len * Math.sin(angle * Math.PI / 180)}" stroke="${col}" stroke-width="${width}" stroke-linecap="round" opacity="0.82" />`;
      }

      let patternLayer = '';
      if (pattern === 'splatter') {
        patternLayer = `<g>${raysSvg}</g>`;
      } else if (pattern === 'color_in_color') {
        patternLayer = `<circle cx="50" cy="50" r="34" fill="${c2}" opacity="0.72" />${raysSvg}`;
      } else if (pattern === 'split') {
        patternLayer = `<path d="M50,2 A48,48 0 0,1 50,98 Z" fill="${c2}" opacity="0.88" />`;
      } else if (pattern === 'galaxy' || pattern === 'marble') {
        patternLayer = `
          <ellipse cx="44" cy="46" rx="40" ry="26" transform="rotate(${seed % 180} 50 50)" fill="${c2}" opacity="0.65" />
          <ellipse cx="56" cy="54" rx="34" ry="20" transform="rotate(${(seed * 3) % 180} 50 50)" fill="${c3}" opacity="0.45" />
        `;
      }

      const initials = (rec.artist || 'LP').split(/\s+/).map(w => w[0] || '').join('').slice(0, 3).toUpperCase();

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
              <!-- Concentric Microgrooves -->
              <circle cx="50" cy="50" r="44" fill="none" stroke="rgba(255,255,255,0.13)" stroke-width="0.35" />
              <circle cx="50" cy="50" r="39" fill="none" stroke="rgba(0,0,0,0.35)" stroke-width="0.45" />
              <circle cx="50" cy="50" r="34" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="0.35" />
              <circle cx="50" cy="50" r="28" fill="none" stroke="rgba(0,0,0,0.35)" stroke-width="0.45" />
              <circle cx="50" cy="50" r="23" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="0.35" />
              <!-- Center Label Ring -->
              <circle cx="50" cy="50" r="16.8" fill="#11131c" stroke="${c3}" stroke-width="0.7" />
              <text x="50" y="45" text-anchor="middle" fill="#e2e8f0" font-size="4.2" font-weight="800" font-family="Inter, sans-serif">${initials}</text>
              <text x="50" y="57.5" text-anchor="middle" fill="#94a3b8" font-size="3.1" font-family="JetBrains Mono, monospace">${rec.year || ''}</text>
              <circle cx="50" cy="50" r="2.2" fill="#05060a" stroke="#cbd5e1" stroke-width="0.4" />
            </g>
            <circle cx="50" cy="50" r="48" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="0.8" />
          </svg>
          ${centerArtUrl ? `
            <div class="absolute inset-[33.5%] rounded-full overflow-hidden border border-white/30 shadow-inner pointer-events-none">
              <img src="${centerArtUrl}" referrerpolicy="no-referrer" alt="" class="w-full h-full object-cover" />
              <div class="absolute inset-[42%] rounded-full bg-[#07080c] border border-slate-300/70"></div>
            </div>
          ` : ''}
        </div>
      `;
    }

    // Render Real Discogs Album Jacket Cover
    function renderJacketSleeveHTML(rec) {
      const { primary, fallback } = getCoverUrls(rec);
      const coverUrl = primary || fallback;
      if (coverUrl) {
        const onErrAttr = (fallback && fallback !== coverUrl)
          ? `onerror="if(this.dataset.fb && this.src!==this.dataset.fb){this.src=this.dataset.fb;}" data-fb="${fallback}"`
          : '';
        return `
          <div class="relative w-full h-full rounded-xl overflow-hidden border border-white/20 bg-slate-950 shadow-xl select-none">
            <img src="${coverUrl}" ${onErrAttr} referrerpolicy="no-referrer" alt="${rec.artist} - ${rec.title}" class="w-full h-full object-cover" />
          </div>
        `;
      }
      const wax = rec.wax_spec || {};
      const c1 = wax.primary_color || '#6d28d9';
      const c2 = wax.secondary_color || '#06b6d4';
      const c3 = wax.accent_color || '#f43f5e';
      return `
        <div class="relative w-full h-full rounded-xl overflow-hidden border border-white/15 p-3 flex flex-col justify-between select-none"
             style="background: linear-gradient(135deg, #0f121d 0%, ${c1}44 55%, ${c2}55 100%);">
          <div class="relative z-10 flex items-center justify-between gap-1">
            <span class="px-1.5 py-0.5 rounded text-[9px] font-mono-tech uppercase bg-black/60 text-slate-300 border border-white/10 truncate max-w-[70%]">${rec.label}</span>
            <span class="text-[9px] font-mono-tech text-slate-400">${rec.year || ''}</span>
          </div>
          <div class="relative z-10 my-auto py-2">
            <div class="w-8 h-0.5 mb-1.5" style="background:${c3}"></div>
            <div class="text-xs font-black uppercase tracking-tight text-white leading-snug line-clamp-2">${rec.artist}</div>
            <div class="text-[11px] font-semibold text-slate-200 leading-tight mt-0.5 line-clamp-2">${rec.title}</div>
          </div>
          <div class="relative z-10 flex items-center justify-between text-[9px] font-mono-tech text-slate-300 border-t border-white/10 pt-1.5">
            <span class="truncate max-w-[65%]">${rec.catno !== 'none' ? rec.catno : 'LP'}</span>
            <span class="text-cyan-300">#${rec.release_id}</span>
          </div>
        </div>
      `;
    }


    // Helper: Get the Stylus-Safe Smart Spin Pool based on state.spinMode
    function getSmartSpinPool() {
      const base = state.records.length ? state.records : [];
      // Always lock out warped ("Need to be done") records from Roulette so the AT-VMN95ML stylus is protected!
      const safePool = base.filter(r => r.flattening_status !== 'Need to be done');
      const working = safePool.length ? safePool : base;

      if (state.spinMode === 'eyecandy') {
        const eyeCandy = working.filter(r => {
          const pat = (r.wax_spec && r.wax_spec.pattern) || '';
          return ['splatter', 'galaxy', 'marble', 'split', 'color_in_color'].includes(pat);
        });
        return eyeCandy.length ? eyeCandy : working;
      }
      return working;
    }

    function updateSmartSpinModeBadges() {
      const base = state.records.length ? state.records : [];
      const safePool = base.filter(r => r.flattening_status !== 'Need to be done');
      const eyeCandyPool = safePool.filter(r => {
        const pat = (r.wax_spec && r.wax_spec.pattern) || '';
        return ['splatter', 'galaxy', 'marble', 'split', 'color_in_color'].includes(pat);
      });

      const badgeAll = document.getElementById('spin-badge-all');
      if (badgeAll) badgeAll.textContent = `ALL SAFE (${safePool.length})`;
      const badgeEye = document.getElementById('spin-badge-eyecandy');
      if (badgeEye) badgeEye.textContent = `FLEX WAX (${eyeCandyPool.length})`;
      const badgeShow = document.getElementById('spin-badge-showroom');
      if (badgeShow) {
        badgeShow.textContent = state.showroomTickInterval ? `AUTO ${state.showroomCountdown}s` : 'AUTO 15s';
      }

      const modePill = document.getElementById('active-spin-mode-pill');
      if (modePill) {
        if (state.spinMode === 'showroom') {
          modePill.textContent = `📺 Showroom Kiosk Active • Auto-Cycle (${state.showroomCountdown}s)`;
          modePill.className = 'text-[10px] font-mono-tech uppercase px-2.5 py-0.5 rounded-full bg-purple-500/25 text-purple-200 border border-purple-400/50 font-bold animate-pulse';
        } else if (state.spinMode === 'eyecandy') {
          modePill.textContent = `🌈 Eye-Candy Variants • ${eyeCandyPool.length} Flex Wax LPs`;
          modePill.className = 'text-[10px] font-mono-tech uppercase px-2.5 py-0.5 rounded-full bg-fuchsia-500/20 text-fuchsia-300 border border-fuchsia-400/35 font-bold';
        } else {
          modePill.textContent = `🎲 Full Vault Roulette • ${safePool.length} Stylus-Safe LPs`;
          modePill.className = 'text-[10px] font-mono-tech uppercase px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/35 font-bold';
        }
      }
    }

    // Populate Left or Right Crate Wing Card (Matches Mockup image_b09c49.jpg)
    function populateCrateWingCard(prefix, rec) {
      if (!rec) return;
      const wax = rec.wax_spec || {};
      const c1 = wax.primary_color || '#8b2cf5';
      const c2 = wax.secondary_color || '#06b6d4';

      const orbEl = document.getElementById(`${prefix}-orb`);
      if (orbEl) {
        orbEl.style.background = `radial-gradient(circle, ${c2}, ${c1})`;
      }

      const pillEl = document.getElementById(`${prefix}-pill`);
      if (pillEl) {
        if (rec.flattening_status === 'Done') {
          pillEl.textContent = 'Flat ✓';
          pillEl.className = 'px-1.5 py-0.5 rounded bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-[9px] font-mono-tech font-bold';
        } else if (rec.flattening_status === 'Need to be done') {
          pillEl.textContent = 'Warped ⚠️';
          pillEl.className = 'px-1.5 py-0.5 rounded bg-rose-500/30 text-rose-200 border border-rose-500/40 text-[9px] font-mono-tech font-bold';
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

      const legacyDisc = document.getElementById(`${prefix}-disc`);
      if (legacyDisc) legacyDisc.innerHTML = renderDeterministicWaxSVG(rec, 180, true);
      const legacyLbl = document.getElementById(`${prefix}-label`);
      if (legacyLbl) legacyLbl.textContent = `${rec.artist} — ${rec.title}`;
    }

    // Render Hero Turntable Stage, Wing Cards, Ambient Glow & Release Gallery Strip
    function renderHeroStage() {
      const list = state.filteredRecords.length ? state.filteredRecords : state.records;
      if (!list.length) return;
      if (state.activeIndex >= list.length) state.activeIndex = 0;
      if (state.activeIndex < 0) state.activeIndex = list.length - 1;

      const rec = list[state.activeIndex];
      const prevRec = list[(state.activeIndex - 1 + list.length) % list.length];
      const nextRec = list[(state.activeIndex + 1) % list.length];

      // Update Command Deck Ambient Stage Backdrop Glow to match active record's wax palette
      const wax = rec.wax_spec || {};
      const c1 = wax.primary_color || '#8b2cf5';
      const c2 = wax.secondary_color || '#06b6d4';
      const c3 = wax.accent_color || '#f43f5e';
      document.documentElement.style.setProperty('--glow-primary', c1 + '44');
      document.documentElement.style.setProperty('--glow-secondary', c2 + '40');
      document.documentElement.style.setProperty('--glow-accent', c3 + '33');

      document.getElementById('carousel-counter').textContent = `${state.activeIndex + 1} / ${list.length}`;

      const platterEl = document.getElementById('active-platter-disc');
      const spinClass = state.isSpinningRoulette
        ? 'spin-roulette-fast'
        : `${state.rpm === 45 ? 'spin-45' : 'spin-33'} ${state.isSpinning ? '' : 'spin-paused'}`;
      platterEl.className = `uv-reactive relative w-[272px] h-[272px] sm:w-[318px] sm:h-[318px] rounded-full shadow-2xl cursor-pointer overflow-hidden ${spinClass}`;

      if (state.stageMode === 'sleeve') {
        platterEl.innerHTML = renderJacketSleeveHTML(rec);
      } else {
        platterEl.innerHTML = renderDeterministicWaxSVG(rec, 320, true);
      }

      // Populate Left & Right Crate Wing Cards
      populateCrateWingCard('stage-prev', prevRec);
      populateCrateWingCard('stage-next', nextRec);

      document.getElementById('hero-variant-badge').textContent = wax.variant_badge || '12" LP';
      const verifiedUrl = getVerifiedPressingPhotoUrl(rec);
      const pillEl = document.getElementById('hero-detection-pill');
      if (verifiedUrl) {
        pillEl.textContent = '✓ Real Pressing Photo Active';
        pillEl.className = 'px-2.5 py-0.5 rounded-full text-[11px] font-mono-tech font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30';
      } else {
        pillEl.textContent = 'Sleeve-Only on Discogs • Wax Ring';
        pillEl.className = 'px-2.5 py-0.5 rounded-full text-[11px] font-mono-tech font-bold bg-slate-800 text-slate-300 border border-white/10';
      }

      document.getElementById('hero-title').textContent = rec.title;
      document.getElementById('hero-artist').textContent = `${rec.artist} (${rec.year || 'LP'})`;
      document.getElementById('hero-price').textContent = `$${Number(rec.estimated_value_usd || 35).toFixed(2)}`;
      document.getElementById('hero-label-cat').textContent = `${rec.label} • ${rec.catno}`;
      document.getElementById('hero-format').textContent = rec.format_string;

      const mShort = (rec.media_condition || 'NM').split('(')[0].trim();
      const sShort = (rec.sleeve_condition || 'NM').split('(')[0].trim();
      document.getElementById('hero-grading').textContent = `Media: ${mShort} / Sleeve: ${sShort}`;

      const flatStatus = rec.flattening_status || 'Not Listed';
      const flatBadge = flatStatus === 'Need to be done'
        ? ` • 🔥 Queue`
        : (flatStatus === 'Done' ? ` • ✓ Flattened` : '');
      document.getElementById('hero-flattening').textContent = `#${rec.release_id}${flatBadge}`;

      const cycleBtn = document.getElementById('btn-hero-flatten-cycle');
      if (cycleBtn) {
        if (flatStatus === 'Not Listed') {
          cycleBtn.textContent = '+ 🔥 Queue';
          cycleBtn.className = 'shrink-0 px-2 py-0.5 rounded bg-amber-500/15 hover:bg-amber-500/25 text-[10px] font-mono-tech font-bold text-amber-300 border border-amber-500/30 transition';
        } else if (flatStatus === 'Need to be done') {
          cycleBtn.textContent = '✓ Mark Done';
          cycleBtn.className = 'shrink-0 px-2 py-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-[10px] font-mono-tech font-bold text-emerald-300 border border-emerald-500/30 transition';
        } else {
          cycleBtn.textContent = '↺ Unlist';
          cycleBtn.className = 'shrink-0 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-[10px] font-mono-tech font-bold text-slate-300 border border-white/10 transition';
        }
      }

      document.getElementById('hero-discogs-link').href = rec.discogs_url || `https://www.discogs.com/release/${rec.release_id}`;

      const syncLogEl = document.getElementById('sync-log-output');
      if (syncLogEl) {
        syncLogEl.textContent = `# Daily Incremental Delta Sync (Fast-Paths Unchanged LPs):\ncd C:\\DiscogsCollection\\discogs_collection\npython scripts/sync_discogs.py\n\n# Force Resync Active Turntable Record (#${rec.release_id} — ${rec.artist}):\npython scripts/sync_discogs.py --resync ${rec.release_id}`;
      }

      updateSmartSpinModeBadges();

      // During rapid kinetic roulette ticks, skip heavy gallery/tracklist DOM rebuilds until lock-in
      if (!state.isSpinningRoulette) {
        renderHeroGalleryStrip(rec);
        renderStreamingDeck(rec);
        updateStreamingQuickLinks(rec);
      }
    }

    // Trigger Kinetic "SPIN THE CRATE" Roulette Animation on the Unified Stage
    function triggerKineticCrateSpin() {
      if (state.isSpinningRoulette) return;
      const pool = getSmartSpinPool();
      if (!pool.length) return;

      // Ensure all records in filteredRecords can show the winner, or reset filter if current filter excludes pool
      const list = state.filteredRecords.length ? state.filteredRecords : state.records;
      const candidateSet = new Set(pool.map(r => Number(r.release_id)));
      let validIndices = [];
      list.forEach((r, idx) => {
        if (candidateSet.has(Number(r.release_id))) validIndices.push(idx);
      });
      if (!validIndices.length) {
        // Reset crate grid filter to 'all' so any Smart Spin Mode record can lock onto the stage
        state.filter = 'all';
        state.searchQuery = '';
        const sIn = document.getElementById('search-input');
        if (sIn) sIn.value = '';
        applyFiltersAndSort();
        state.filteredRecords.forEach((r, idx) => {
          if (candidateSet.has(Number(r.release_id))) validIndices.push(idx);
        });
      }
      if (!validIndices.length) {
        validIndices = list.map((_, i) => i);
      }

      state.isSpinningRoulette = true;
      const totalSteps = 22 + Math.floor(Math.random() * 8);
      let step = 0;

      // Lift tonearm during crate spin
      const armEl = document.getElementById('turntable-tonearm');
      if (armEl) {
        armEl.className = 'tonearm-pivot tonearm-parked absolute top-3.5 right-3.5 w-32 h-64 sm:w-[140px] sm:h-[280px] pointer-events-none z-30';
      }

      const prevWing = document.getElementById('stage-prev-card');
      const nextWing = document.getElementById('stage-next-card');
      const velReadout = document.getElementById('reel-velocity-readout');

      function stepRoulette() {
        step++;
        const progress = step / totalSteps;
        // Pick next index in validIndices
        const pickIdx = validIndices[Math.floor(Math.random() * validIndices.length)];
        state.activeIndex = pickIdx;

        // Pitch scales down as reel decelerates
        const pitch = 1.45 - progress * 0.65;
        playCrateTickSound(pitch);

        const rpmSim = Math.max(4.2, (1 - progress) * 96).toFixed(1);
        if (velReadout) {
          velReadout.textContent = `Velocity: ${rpmSim} RPM • Spinning Crate...`;
          velReadout.className = 'text-[11px] font-mono-tech font-bold text-fuchsia-300 animate-pulse';
        }

        if (prevWing && nextWing) {
          prevWing.classList.toggle('wing-tick-left', step % 2 === 0);
          nextWing.classList.toggle('wing-tick-right', step % 2 === 1);
        }

        renderHeroStage();

        if (step < totalSteps) {
          // Exponential ease-out delay from 38ms up to 240ms
          const nextDelay = Math.round(38 + Math.pow(progress, 2.35) * 210);
          setTimeout(stepRoulette, nextDelay);
        } else {
          // Winner Locked In!
          state.isSpinningRoulette = false;
          if (prevWing) prevWing.classList.remove('wing-tick-left');
          if (nextWing) nextWing.classList.remove('wing-tick-right');

          if (armEl && state.isSpinning) {
            armEl.className = 'tonearm-pivot tonearm-engaged absolute top-3.5 right-3.5 w-32 h-64 sm:w-[140px] sm:h-[280px] pointer-events-none z-30';
          }

          const activeList = state.filteredRecords.length ? state.filteredRecords : state.records;
          const winner = activeList[state.activeIndex];

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

          renderHeroStage();
          renderCrateGrid();
        }
      }

      stepRoulette();
    }

    // Set Smart Spin Mode ('all' | 'showroom' | 'eyecandy')
    function setSmartSpinMode(mode, autoTriggerSpin = true) {
      // Clear any active Showroom Kiosk timer first
      if (state.showroomTickInterval) {
        clearInterval(state.showroomTickInterval);
        state.showroomTickInterval = null;
      }

      state.spinMode = mode;

      document.querySelectorAll('.spin-mode-btn').forEach(btn => {
        const m = btn.getAttribute('data-spin-mode');
        const isAct = m === mode;
        if (isAct) {
          btn.className = 'spin-mode-btn text-left p-2.5 rounded-2xl border-2 transition-all bg-cyan-500/15 border-cyan-400 text-white shadow-[0_0_20px_rgba(6,182,212,0.25)]';
        } else {
          btn.className = 'spin-mode-btn text-left p-2.5 rounded-2xl border transition-all bg-slate-950/80 border-white/15 text-slate-300 hover:border-cyan-400/50 hover:text-white';
        }
      });

      if (mode === 'showroom') {
        state.showroomCountdown = 15;
        // Automatically enable UV Blacklight for Showroom Kiosk mode if not already on
        if (!state.uvBlacklight) {
          toggleUvBlacklight(true);
        }
        state.showroomTickInterval = setInterval(() => {
          if (!state.isSpinningRoulette) {
            state.showroomCountdown--;
            if (state.showroomCountdown <= 0) {
              state.showroomCountdown = 15;
              triggerKineticCrateSpin();
            }
            updateSmartSpinModeBadges();
          }
        }, 1000);
        showToast('📺 Showroom Kiosk Active: Auto-spinning a new pressing every 15s with UV Blacklight!');
      }

      updateSmartSpinModeBadges();
      if (autoTriggerSpin) {
        triggerKineticCrateSpin();
      }
    }

    // Toggle UV Blacklight Mode
    function toggleUvBlacklight(forceState) {
      state.uvBlacklight = typeof forceState === 'boolean' ? forceState : !state.uvBlacklight;
      document.body.classList.toggle('uv-blacklight', state.uvBlacklight);
      const uvBtn = document.getElementById('btn-uv-toggle');
      if (uvBtn) {
        uvBtn.textContent = state.uvBlacklight ? '🟣 UV Blacklight: ON' : '🟣 UV Blacklight: Off';
        uvBtn.className = state.uvBlacklight
          ? 'px-2.5 py-1.5 rounded-xl text-xs font-black border-2 border-fuchsia-400 bg-fuchsia-500/30 text-white shadow-[0_0_20px_rgba(217,70,239,0.5)] transition-all'
          : 'px-2.5 py-1.5 rounded-xl text-xs font-bold border border-purple-400/40 bg-purple-500/15 text-purple-200 hover:bg-purple-500/25 transition-all';
      }
      playUvToggleSound(state.uvBlacklight);
      showToast(state.uvBlacklight ? '🟣 UV Blacklight ON — Neon reactive wax shader active!' : '🟣 UV Blacklight Off — Standard studio lighting restored.');
    }

    // =========================================================================
    // v5.0 VARIANT CLASH ARENA (4-LP HEAD-TO-HEAD KNOCKOUT BRACKET)
    // =========================================================================
    function getArenaCandidatePool() {
      const base = state.records.length ? state.records : [];
      const safe = base.filter(r => r.flattening_status !== 'Need to be done');
      const working = safe.length >= 4 ? safe : base;

      if (state.arenaPoolMode === 'eyecandy') {
        const ec = working.filter(r => ['splatter', 'galaxy', 'marble', 'split', 'color_in_color'].includes((r.wax_spec && r.wax_spec.pattern) || ''));
        if (ec.length >= 4) return ec;
      } else if (state.arenaPoolMode === 'flat') {
        const fl = working.filter(r => r.flattening_status === 'Done');
        if (fl.length >= 4) return fl;
      }
      return working;
    }

    function initArenaBracket() {
      const pool = getArenaCandidatePool();
      if (pool.length < 4) return;
      const shuffled = pool.slice().sort(() => Math.random() - 0.5);
      state.arenaBracket = shuffled.slice(0, 4);
      state.arenaWinners = [];
      state.arenaStage = 0;
      state.arenaChampion = null;
      renderArenaView();
    }

    function renderArenaContenderCard(rec, side) {
      if (!rec) return '';
      const wax = rec.wax_spec || {};
      const verifiedPhoto = Boolean(getVerifiedPressingPhotoUrl(rec));
      const flatLabel = rec.flattening_status === 'Done'
        ? '✓ 130°F Flat Certified'
        : '🛡️ Stylus Safe';
      const flatClass = rec.flattening_status === 'Done'
        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
        : 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30';

      return `
        <div>
          <div class="flex flex-wrap items-center justify-between gap-2 text-xs mb-3">
            <div class="flex flex-wrap items-center gap-1.5">
              <span class="px-2.5 py-0.5 rounded-full font-mono-tech font-bold bg-purple-500/20 text-purple-200 border border-purple-400/35">
                ${wax.variant_badge || '12" LP'}
              </span>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-mono-tech font-bold border ${flatClass}">
                ${flatLabel}
              </span>
            </div>
            <span class="font-mono-tech font-black text-emerald-400">$${Number(rec.estimated_value_usd || 35).toFixed(2)}</span>
          </div>

          <!-- Dual Visual Showcase: Real Jacket Cover + Spinning Pressing Disc -->
          <div class="relative h-44 rounded-2xl bg-gradient-to-b from-slate-900/90 to-[#070910] border border-white/10 flex items-center justify-center px-4 overflow-hidden my-3">
            <div class="relative w-32 h-32 z-10 shadow-2xl -ml-6 transition-transform duration-300 group-hover:-translate-x-2 holo-sleeve rounded-xl overflow-hidden">
              ${renderJacketSleeveHTML(rec)}
            </div>
            <div class="uv-reactive relative w-32 h-32 -ml-8 z-20 rounded-full shadow-2xl spin-33 transition-transform duration-300 group-hover:translate-x-2">
              ${renderDeterministicWaxSVG(rec, 128, true)}
            </div>
            <span class="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full text-[10px] font-mono-tech font-bold ${verifiedPhoto ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-900/90 text-cyan-300 border border-white/10'} z-30">
              ${verifiedPhoto ? '📸 Real Pressing Photo' : '⚙ Wax Shader'}
            </span>
            <span class="absolute bottom-2 right-2.5 text-[10px] font-mono-tech text-slate-400">#${rec.release_id}</span>
          </div>

          <div class="mt-2">
            <p class="text-xs font-extrabold uppercase tracking-wider text-cyan-400 truncate">${rec.artist} • ${rec.year || 'LP'}</p>
            <h3 class="text-lg sm:text-xl font-black text-white leading-snug mt-0.5 line-clamp-1">${rec.title}</h3>
            <p class="text-[11px] font-mono-tech text-slate-400 mt-1 truncate">${rec.label} (${rec.catno}) • ${rec.format_string}</p>
          </div>
        </div>

        <div class="mt-4 pt-3 border-t border-white/10 flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
          <button
            type="button"
            data-arena-audition="${rec.release_id}"
            class="px-3 py-2.5 rounded-xl font-mono-tech font-bold text-xs bg-slate-900 hover:bg-slate-800 text-cyan-300 border border-cyan-500/30 transition flex items-center justify-center gap-1.5 shrink-0"
            title="Audition a 30-second studio track preview before voting"
          >
            <span>🎧 Audition 30s</span>
          </button>
          <button
            type="button"
            data-arena-vote="${side}"
            class="flex-1 py-2.5 px-4 rounded-xl font-black text-xs uppercase tracking-wider text-center bg-gradient-to-r ${side === 'left' ? 'from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950' : 'from-fuchsia-600 to-purple-600 hover:from-fuchsia-500 hover:to-purple-500 text-white'} shadow-lg group-hover:scale-[1.01] transition-transform"
          >
            ${state.arenaStage === 3 ? '💿 Load Champion on Turntable Stage' : `⚡ Crown ${rec.artist} as Winner`}
          </button>
        </div>
      `;
    }

    function renderArenaView() {
      const badgeEl = document.getElementById('arena-round-badge');
      const leftEl = document.getElementById('arena-card-left');
      const rightEl = document.getElementById('arena-card-right');
      const summaryEl = document.getElementById('arena-bracket-summary');
      if (!badgeEl || !leftEl || !rightEl || !summaryEl) return;

      if (!state.arenaBracket || state.arenaBracket.length < 4) {
        initArenaBracket();
        return;
      }

      let leftRec = null;
      let rightRec = null;

      if (state.arenaStage === 0) {
        badgeEl.textContent = 'Semifinal 1 of 2';
        badgeEl.className = 'px-3.5 py-1.5 rounded-xl font-mono-tech text-xs font-extrabold bg-cyan-500/20 text-cyan-300 border border-cyan-400/40';
        leftRec = state.arenaBracket[0];
        rightRec = state.arenaBracket[1];
      } else if (state.arenaStage === 1) {
        badgeEl.textContent = 'Semifinal 2 of 2';
        badgeEl.className = 'px-3.5 py-1.5 rounded-xl font-mono-tech text-xs font-extrabold bg-purple-500/20 text-purple-300 border border-purple-400/40';
        leftRec = state.arenaBracket[2];
        rightRec = state.arenaBracket[3];
      } else if (state.arenaStage === 2) {
        badgeEl.textContent = '🏆 Championship Final';
        badgeEl.className = 'px-3.5 py-1.5 rounded-xl font-mono-tech text-xs font-extrabold bg-amber-500/25 text-amber-200 border border-amber-400/50 animate-pulse';
        leftRec = state.arenaWinners[0];
        rightRec = state.arenaWinners[1];
      } else {
        badgeEl.textContent = '👑 Champion Crowned!';
        badgeEl.className = 'px-3.5 py-1.5 rounded-xl font-mono-tech text-xs font-extrabold bg-emerald-500/25 text-emerald-200 border border-emerald-400/50';
        leftRec = state.arenaChampion;
        rightRec = state.arenaChampion;
      }

      if (leftRec && rightRec) {
        leftEl.innerHTML = renderArenaContenderCard(leftRec, 'left');
        rightEl.innerHTML = renderArenaContenderCard(rightRec, 'right');

        leftEl.onclick = (e) => {
          const audBtn = e.target.closest('[data-arena-audition]');
          if (audBtn) {
            e.stopPropagation();
            playAlbumTrackAtIndex(leftRec, 0);
            showToast(`🎧 Auditioning 30s preview: ${leftRec.artist} — "${leftRec.title}"`);
            return;
          }
          advanceArenaBracket(leftRec);
        };
        rightEl.onclick = (e) => {
          const audBtn = e.target.closest('[data-arena-audition]');
          if (audBtn) {
            e.stopPropagation();
            playAlbumTrackAtIndex(rightRec, 0);
            showToast(`🎧 Auditioning 30s preview: ${rightRec.artist} — "${rightRec.title}"`);
            return;
          }
          advanceArenaBracket(rightRec);
        };
      }

      summaryEl.innerHTML = `
        <div class="bg-slate-950/90 p-3.5 rounded-2xl border border-white/10">
          <p class="text-[10px] font-mono-tech font-bold uppercase text-cyan-400">Semifinal 1 Winner</p>
          <p class="font-extrabold text-white mt-1 truncate">${state.arenaWinners[0] ? state.arenaWinners[0].artist + ' — ' + state.arenaWinners[0].title : 'Battle in progress...'}</p>
        </div>
        <div class="bg-slate-950/90 p-3.5 rounded-2xl border border-white/10">
          <p class="text-[10px] font-mono-tech font-bold uppercase text-fuchsia-400">Semifinal 2 Winner</p>
          <p class="font-extrabold text-white mt-1 truncate">${state.arenaWinners[1] ? state.arenaWinners[1].artist + ' — ' + state.arenaWinners[1].title : 'Waiting for Semifinal 2...'}</p>
        </div>
        <div class="bg-slate-950/90 p-3.5 rounded-2xl border ${state.arenaChampion ? 'border-amber-400/60 bg-amber-500/10' : 'border-amber-500/30'} flex items-center justify-between gap-2">
          <div class="min-w-0">
            <p class="text-[10px] font-mono-tech font-bold uppercase text-amber-300">👑 Tonight's Turntable Champion</p>
            <p class="font-black text-amber-200 mt-1 truncate">${state.arenaChampion ? state.arenaChampion.artist + ' — ' + state.arenaChampion.title : 'Win 2 rounds to crown!'}</p>
          </div>
          ${state.arenaChampion ? `
            <button type="button" id="btn-arena-load-champ" class="shrink-0 px-3 py-1.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-black text-xs transition shadow-md">
              Spin Winner →
            </button>
          ` : ''}
        </div>
      `;

      const loadChampBtn = document.getElementById('btn-arena-load-champ');
      if (loadChampBtn && state.arenaChampion) {
        loadChampBtn.onclick = () => jumpToRecordOnTurntable(state.arenaChampion.release_id);
      }
    }

    function advanceArenaBracket(winnerRec) {
      if (!winnerRec) return;
      if (state.arenaStage === 0) {
        playCrateTickSound(1.3);
        state.arenaWinners[0] = winnerRec;
        state.arenaStage = 1;
        renderArenaView();
      } else if (state.arenaStage === 1) {
        playCrateTickSound(1.45);
        state.arenaWinners[1] = winnerRec;
        state.arenaStage = 2;
        renderArenaView();
      } else if (state.arenaStage === 2) {
        state.arenaChampion = winnerRec;
        state.arenaStage = 3;
        playNeedleDropSound();
        setTimeout(() => playRouletteWinChord(true), 80);
        const wax = winnerRec.wax_spec || {};
        spawnParticles(wax.primary_color, wax.secondary_color, wax.accent_color, 85);
        renderArenaView();
        showToast(`👑 Variant Clash Champion: ${winnerRec.artist} — "${winnerRec.title}"! Click again to load on Turntable.`);
      } else {
        jumpToRecordOnTurntable(winnerRec.release_id);
      }
    }

    function jumpToRecordOnTurntable(releaseId) {
      const rid = Number(releaseId);
      let idx = state.filteredRecords.findIndex(r => Number(r.release_id) === rid);
      if (idx === -1) {
        state.filter = 'all';
        state.searchQuery = '';
        const sIn = document.getElementById('search-input');
        if (sIn) sIn.value = '';
        applyFiltersAndSort();
        idx = state.filteredRecords.findIndex(r => Number(r.release_id) === rid);
      }
      if (idx !== -1) {
        state.activeIndex = idx;
      }
      if (typeof window.__setMainVaultTab === 'function') {
        window.__setMainVaultTab('showcase');
      }
      playNeedleDropSound();
      renderHeroStage();
      renderCrateGrid();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Curated album metadata & YouTube Music / YouTube stream map (100% Embedded YouTube Player — zero iTunes 30s previews)
    const CURATED_TRACKLISTS = {
      26047147: {
        year: 2005,
        totalMinutes: 48,
        fullAlbumYtVideoId: "8l_V2a5ZTqQ",
        description: "Kezia is the debut full-length concept album by Canadian progressive metal band Protest The Hero.",
        tracks: [
          { position: "A1", title: "No Stars Over Bethlehem", duration: "3:49", plays: "494K plays", ytVideoId: "0F30bLYWmmg" },
          { position: "A2", title: "Heretics & Killers", duration: "3:10", plays: "1.2M plays", ytVideoId: "AEn8HmgJxd4" },
          { position: "A3", title: "Divinity Within", duration: "4:33", plays: "535K plays" },
          { position: "B1", title: "Bury the Hatchet", duration: "3:25", plays: "298K plays" },
          { position: "B2", title: "Nautical", duration: "2:58", plays: "347K plays" },
          { position: "B3", title: "Blindfolds Aside", duration: "6:00", plays: "3.4M plays", ytVideoId: "8x3sLH4G0qA" },
          { position: "C1", title: "She Who Mars the Skin of Gods", duration: "3:52", plays: "289K plays" },
          { position: "C2", title: "Turn Soonest to the Sea", duration: "6:22", plays: "769K plays", ytVideoId: "ygUPP02XHwg" },
          { position: "D1", title: "The Divine Suicide of K.", duration: "5:11", plays: "274K plays", ytVideoId: "DLUD8jicLsk" },
          { position: "D2", title: "A Plateful of Our Dead", duration: "4:30", plays: "187K plays" }
        ]
      },
      17743813: {
        year: 2021,
        totalMinutes: 58,
        fullAlbumYtVideoId: "cDdvMnu5RoQ",
        description: "For Those That Wish To Exist is the ninth studio album by British metalcore band Architects.",
        tracks: [
          { position: "A1", title: "Do You Dream of Armageddon?", duration: "1:38", plays: "8.4M plays" },
          { position: "A2", title: "Black Lungs", duration: "3:51", plays: "42M plays", ytVideoId: "W69ow97hqbI" },
          { position: "A3", title: "Giving Blood", duration: "3:32", plays: "14M plays" },
          { position: "A4", title: "Discourse Is Dead", duration: "3:46", plays: "19M plays" },
          { position: "B1", title: "Dead Butterflies", duration: "4:02", plays: "28M plays", ytVideoId: "2ZmjG3wuUes" },
          { position: "B2", title: "An Ordinary Extinction", duration: "4:07", plays: "11M plays" },
          { position: "B3", title: "Impermanence", duration: "4:02", plays: "21M plays" },
          { position: "B4", title: "Flight Without Feathers", duration: "3:48", plays: "6.2M plays" },
          { position: "C1", title: "Little Wonder", duration: "3:47", plays: "9.1M plays" },
          { position: "C2", title: "Animals", duration: "4:04", plays: "118M plays", ytVideoId: "jdWhJcrrjQs" },
          { position: "C3", title: "Libertine", duration: "4:01", plays: "8.7M plays" },
          { position: "D1", title: "Goliath", duration: "4:17", plays: "12M plays" },
          { position: "D2", title: "Demi God", duration: "4:26", plays: "6.5M plays" },
          { position: "D3", title: "Meteor", duration: "4:01", plays: "18M plays", ytVideoId: "lm7ejB08cbQ" },
          { position: "D4", title: "Dying Is Absolutely Safe", duration: "4:59", plays: "9.4M plays" }
        ]
      },
      17583742: {
        year: 2021,
        totalMinutes: 34,
        fullAlbumYtVideoId: "kBSb6UVAetw",
        description: "Embryonic Anomaly (Remake) is the full 2021 studio re-recording of Rings Of Saturn's debut album.",
        tracks: [
          { position: "A1", title: "Seized and Devoured", duration: "4:04", plays: "1.9M plays" },
          { position: "A2", title: "Invasion", duration: "4:07", plays: "610K plays" },
          { position: "A3", title: "Abducted", duration: "4:07", plays: "540K plays", ytVideoId: "b6vhOPTdmeI" },
          { position: "A4", title: "Final Abhorrent Dream", duration: "5:02", plays: "410K plays" },
          { position: "B1", title: "Corpses Thrown Across the Sky", duration: "4:05", plays: "720K plays" },
          { position: "B2", title: "Embryonic Anomaly", duration: "3:25", plays: "480K plays" },
          { position: "B3", title: "No Pity for a Coward", duration: "3:20", plays: "390K plays" },
          { position: "B4", title: "Annihilating the Pure", duration: "4:54", plays: "460K plays" },
          { position: "B5", title: "Grinding of Internal Organs / End of Humanity", duration: "5:26", plays: "350K plays" }
        ]
      }
    };

    function cleanSearchTitle(titleStr) {
      let s = String(titleStr || '')
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

    function cleanArtistName(artistStr) {
      return String(artistStr || '')
        .replace(/\s*\(\d+\)\s*$/g, '')
        .trim();
    }

    function extractYoutubeIdFromUri(uri) {
      if (!uri) return '';
      const m = String(uri).match(/(?:v=|youtu\.be\/|embed\/)([A-Za-z0-9_-]{11})/);
      return m ? m[1] : '';
    }

    function formatMillisToDuration(ms) {
      if (!ms || isNaN(ms) || ms <= 0) return '';
      const totalSec = Math.round(ms / 1000);
      const mins = Math.floor(totalSec / 60);
      const secs = totalSec % 60;
      return `${mins}:${String(secs).padStart(2, '0')}`;
    }

    function parseDurationToSeconds(durStr) {
      if (!durStr) return 215;
      const parts = String(durStr).trim().split(':').map(Number);
      if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        return parts[0] * 60 + parts[1];
      }
      return 215;
    }

    function normalizeTrackKey(str) {
      const s = String(str || '')
        .toLowerCase()
        .replace(/∆/g, 'a')
        .replace(/flouride/g, 'fluoride')
        .replace(/st4f1sh/g, 'st4rf1sh')
        .replace(/\[([^\]]{1,2})\]/g, '$1')
        .replace(/\([^)]*\)|\[[^\]]*\]/g, ' ');
      const words = s.match(/[a-z0-9]+/g) || [];
      return words.map(w => (w.length > 3 && w.endsWith('s')) ? w.slice(0, -1) : w).join('');
    }

    function recomputeAlbumCumulativeOffsets(tracks) {
      let cum = 0;
      tracks.forEach(t => {
        t.albumYtStart = cum;
        cum += parseDurationToSeconds(t.duration);
      });
    }

    function isTrueFullAlbumVideoMeta(title, durationSec) {
      const low = String(title || '').toLowerCase();
      if (Number(durationSec || 0) >= 1100) return true;
      return (
        low.includes('full album') ||
        low.includes('full-album') ||
        low.includes('full length') ||
        low.includes('full ep') ||
        low.includes('complete album') ||
        low.includes('album stream') ||
        low.includes('album premiere') ||
        low.includes('(full)')
      );
    }

/* __VAULT_YTM_MAPS_JS__ */

    // ============================================================================
    // v5.0 CLEAN 30-SECOND HTML5 AUDIO PREVIEW PLAYER + YT MUSIC & SPOTIFY LINKS
    // - Zero YouTube IFrame / Error 153 boxes (100% native HTML5 <audio> 30s clips)
    // - Zero autoplay on page load (plays ONLY when user clicks Play or a track row)
    // - Direct Album Links to YouTube Music (playlist?list=...) & Spotify
    // ============================================================================
    state.userRequestedPlay = false;
    state.activePlaybackEngine = 'html5';
    state.previewUrlCache = {};

    function ensureYouTubeIframeApiLoaded() {
      return Promise.resolve(false);
    }
    function stopYtProgressPoller() {}
    function startYtProgressPoller() {}

    function resolveAlbumStreamingData(rec) {
      const rid = Number(rec.release_id);
      if (state.streamCache[rid]) {
        return state.streamCache[rid];
      }

      const curated = CURATED_TRACKLISTS[rid] || null;
      const ytmVerified = VERIFIED_YTM_RELEASE_MAP[rid] || VERIFIED_YTM_RELEASE_MAP[String(rid)] || {};
      const ytmDurMap = ytmVerified.trackDurations || {};
      const bakedTracks = Array.isArray(rec.tracklist) && rec.tracklist.length ? rec.tracklist : null;
      const ytPlaylistId = ytmVerified.ytPlaylistId || rec.ytPlaylistId || '';

      let baseTracks = [];
      if (bakedTracks && bakedTracks.length) {
        const curTracks = curated ? curated.tracks : [];
        baseTracks = bakedTracks.map((t, idx) => {
          const ct = curTracks[idx] || {};
          const trDur = ytmDurMap[String(idx)] || t.duration || ct.duration || '3:45';
          return {
            position: t.position || ct.position || String(idx + 1),
            title: t.title || ct.title || `Track ${idx + 1}`,
            duration: trDur,
            plays: ct.plays || '',
          };
        });
      } else if (curated && Array.isArray(curated.tracks)) {
        baseTracks = curated.tracks.map((t, idx) => ({
          ...t,
          duration: ytmDurMap[String(idx)] || t.duration || '3:45',
        }));
      } else {
        baseTracks = [{
          position: 'A1',
          title: rec.title,
          duration: '3:45',
          plays: '',
        }];
      }

      const totalSecs = baseTracks.reduce((acc, t) => acc + parseDurationToSeconds(t.duration), 0);
      const totalMinutes = Math.max(1, Math.round(totalSecs / 60));

      const compiled = {
        year: (curated && curated.year) || rec.year || 'LP',
        totalMinutes,
        ytPlaylistId,
        description: (curated && curated.description) ||
          `${rec.title} by ${rec.artist} • ${rec.label} (${rec.catno !== 'none' ? rec.catno : 'LP'})`,
        tracks: baseTracks,
      };
      state.streamCache[rid] = compiled;
      return compiled;
    }

    // ============================================================================
    // EXACT ALBUM DEEP-LINK RESOLVER (YouTube Music OLAK5uy_... & Spotify /album/...)
    // - Strictly uses OLAK5uy_... for YouTube Music (NEVER PL... user playlists)
    // - Strictly resolves https://open.spotify.com/album/<id> for Spotify
    // - Multi-pass Fuzzy & Wildcard Album Matcher (handles "The Question Live" <->
    //   "The Question (Live)", Roman/Arabic Vols, [Id]/[M]other brackets, etc.)
    // ============================================================================
    safeRemoveStorage('krunked_exact_album_links_v48');
    state.exactAlbumLinksCache = (function () {
      try {
        const raw = safeGetStorage('krunked_exact_album_links_v49');
        return raw ? (JSON.parse(raw) || {}) : {};
      } catch (e) {
        return {};
      }
    })();
    state.pendingAlbumLinkPromises = {};

    function saveExactAlbumLinksCache() {
      try {
        safeSetStorage('krunked_exact_album_links_v49', JSON.stringify(state.exactAlbumLinksCache));
      } catch (e) {}
    }

    function normalizeFuzzyAlbumTokens(str, keepModifiers = true) {
      let s = String(str || '')
        .toLowerCase()
        .replace(/∆/g, 'a')
        .replace(/[•●|]/g, ' ')
        .replace(/\s*\(\d+\)\s*$/g, '')
        .replace(/\bln\b/g, 'in')
        .replace(/\[([^\]]{1,2})\]/g, '$1')
        .replace(/\bvols?\.?\s+i\b/g, 'vol 1')
        .replace(/\bvols?\.?\s+ii\b/g, 'vol 2')
        .replace(/\bvols?\.?\s+iii\b/g, 'vol 3')
        .replace(/\bvols?\.?\s+iv\b/g, 'vol 4')
        .replace(/\bii\b/g, '2')
        .replace(/\biii\b/g, '3')
        .replace(/\biv\b/g, '4');
      if (!keepModifiers) {
        s = s.replace(/\b(?:deluxe|reissue|repress|remastered|remaster|remake|live|edition|version|anniversary|definitive|reloaded|repented|tour|collection|special|expanded|encore|bonus|explicit|album|ep)\b/g, ' ');
      }
      const words = s.match(/[a-z0-9]+/g) || [];
      const stop = new Set(['the', 'a', 'an', 'of', 'and', 'in', 'to', 'for', 'on', 'at', 'by', 'with']);
      const stemmed = words.map(w => (w.length > 3 && w.endsWith('s')) ? w.slice(0, -1) : w);
      const filtered = stemmed.filter(w => !stop.has(w));
      return filtered.length ? filtered : stemmed;
    }

    function computeAlbumFuzzyStemKey(artist, title) {
      const a = cleanArtistName(artist || '').toLowerCase();
      const t = String(title || '').toLowerCase().replace(/∆/g, 'a').replace(/\bln\b/g, 'in').replace(/\[([^\]]{1,2})\]/g, '$1');
      const aWords = (a.match(/[a-z0-9]+/g) || []).map(w => (w.length > 3 && w.endsWith('s')) ? w.slice(0, -1) : w);
      const tWords = (t.match(/[a-z0-9]+/g) || []).map(w => (w.length > 3 && w.endsWith('s')) ? w.slice(0, -1) : w);
      return `${aWords.join('')}::${tWords.join('')}`;
    }

    function buildAlbumSearchQueryVariants(rec) {
      const cleanArt = cleanArtistName(rec ? rec.artist : '');
      const rawTit = String((rec && rec.title) || '').trim();
      const fixedTit = rawTit
        .replace(/∆/g, 'A')
        .replace(/\bln\b/g, 'In')
        .replace(/\[([^\]]{1,2})\]/g, '$1')
        .replace(/[•●|]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

      const queries = [];
      const addQ = (q) => {
        const c = String(q || '').replace(/\s+/g, ' ').trim();
        if (c && !queries.includes(c)) queries.push(c);
      };

      // 1. Literal cleaned query
      addQ(`${cleanArt} ${fixedTit}`);

      // 2. Parenthetical / un-parenthetical variant (e.g., "The Question Live" -> "The Question (Live)" & "The Question")
      const mSuf = fixedTit.match(/^(.*?)\s*[:\-]?\s+\b(Live|Remake|Deluxe(?:\s+Edition)?|Definitive|Reloaded|Repented)\.?$/i);
      if (mSuf) {
        addQ(`${cleanArt} ${mSuf[1].trim()} (${mSuf[2].trim()})`);
        addQ(`${cleanArt} ${mSuf[1].trim()}`);
      }

      // 3. Cleaned base title
      const cleanAlb = cleanSearchTitle(rawTit);
      if (cleanAlb && cleanAlb !== fixedTit) {
        addQ(`${cleanArt} ${cleanAlb}`);
      }

      // 4. Wildcard core-tokens query (roman-to-arabic & stripped symbols)
      const coreWords = normalizeFuzzyAlbumTokens(fixedTit, false);
      if (coreWords.length) {
        addQ(`${cleanArt} ${coreWords.join(' ')}`);
      }

      // 5. Track-assisted fallback query
      if (rec && Array.isArray(rec.tracklist) && rec.tracklist[0] && rec.tracklist[0].title) {
        addQ(`${cleanArt} ${cleanAlb || fixedTit} ${cleanSearchTitle(rec.tracklist[0].title)}`);
      }

      return queries;
    }

    function scoreAlbumCandidateFuzzy(targetArtist, targetTitle, candArtist, candTitle, trackCount = 0) {
      const tArtToks = normalizeFuzzyAlbumTokens(targetArtist, true);
      const cArtToks = normalizeFuzzyAlbumTokens(candArtist, true);
      const tArtStr = tArtToks.join('');
      const cArtStr = cArtToks.join('');
      let artScore = 0;
      if (tArtStr && cArtStr) {
        if (tArtStr === cArtStr) artScore = 45;
        else if (tArtStr.includes(cArtStr) || cArtStr.includes(tArtStr)) artScore = 35;
        else {
          const cSet = new Set(cArtToks);
          const overlap = tArtToks.filter(w => cSet.has(w)).length / Math.max(1, tArtToks.length);
          if (overlap >= 0.5) artScore = 28 * overlap;
          else return -1;
        }
      }

      const tLow = String(targetTitle || '').toLowerCase();
      const cLow = String(candTitle || '').toLowerCase();
      if (cLow.includes('instrumental') && !tLow.includes('instrumental')) return -1;
      if ((cLow.includes('karaoke') || cLow.includes('8-bit')) && !tLow.includes('karaoke')) return -1;

      const tFull = normalizeFuzzyAlbumTokens(targetTitle, true);
      let cFull = normalizeFuzzyAlbumTokens(candTitle, true);
      const tCore = normalizeFuzzyAlbumTokens(targetTitle, false);
      let cCore = normalizeFuzzyAlbumTokens(candTitle, false);

      if (tArtToks.length && cCore.length > tArtToks.length && cCore.slice(0, tArtToks.length).join('') === tArtStr) {
        cCore = cCore.slice(tArtToks.length);
      }
      if (tArtToks.length && cFull.length > tArtToks.length && cFull.slice(0, tArtToks.length).join('') === tArtStr) {
        cFull = cFull.slice(tArtToks.length);
      }

      const tFullStr = tFull.join('');
      const cFullStr = cFull.join('');
      const tCoreStr = tCore.join('');
      const cCoreStr = cCore.join('');

      let titScore = 0;
      if (tFullStr && tFullStr === cFullStr) {
        titScore = 90;
      } else if (tCoreStr && tCoreStr === cCoreStr) {
        titScore = 78;
      } else if (tCoreStr && cCoreStr && (tCoreStr.startsWith(cCoreStr) || cCoreStr.startsWith(tCoreStr))) {
        titScore = 62;
      } else if (tCore.length && cCore.length) {
        const cSet = new Set(cCore);
        const common = tCore.filter(w => cSet.has(w)).length;
        const recall = common / Math.max(1, tCore.length);
        const precision = common / Math.max(1, cCore.length);
        if (recall >= 0.6 && precision >= 0.4) {
          titScore = 55 * ((recall + precision) / 2);
        } else if (tCoreStr && cCoreStr && (tCoreStr.includes(cCoreStr) || cCoreStr.includes(tCoreStr))) {
          titScore = 45;
        } else {
          return -1;
        }
      } else {
        return -1;
      }

      for (const mod of ['live', 'remake', 'definitive', 'reloaded', 'repented', 'deluxe', 'tour']) {
        if (tLow.includes(mod) && cLow.includes(mod)) titScore += 12;
        else if (cLow.includes(mod) && !tLow.includes(mod) && mod === 'live') titScore -= 18;
      }
      if (Number(trackCount || 0) >= 4) titScore += 10;
      return artScore + titScore;
    }

    function getVerifiedOlakPlaylistId(rec, streamData) {
      if (!rec) return '';
      const rid = Number(rec.release_id);
      const cached = state.exactAlbumLinksCache[rid] || state.exactAlbumLinksCache[String(rid)] || {};
      if (cached.olakId && String(cached.olakId).startsWith('OLAK5uy_')) {
        return String(cached.olakId);
      }
      const ytmVerified = (rid && (VERIFIED_YTM_RELEASE_MAP[rid] || VERIFIED_YTM_RELEASE_MAP[String(rid)])) || {};
      const stemKey = computeAlbumFuzzyStemKey(rec.artist, rec.title);
      const stemOlak = (typeof VERIFIED_YTM_ALBUM_STEM_MAP === 'object' && VERIFIED_YTM_ALBUM_STEM_MAP)
        ? VERIFIED_YTM_ALBUM_STEM_MAP[stemKey]
        : '';
      const candidates = [
        ytmVerified.ytPlaylistId,
        rec.ytPlaylistId,
        streamData && streamData.ytPlaylistId,
        stemOlak,
      ];
      for (const c of candidates) {
        if (typeof c === 'string' && c.startsWith('OLAK5uy_')) {
          return c;
        }
      }
      return '';
    }

    function getVerifiedSpotifyAlbumId(rec) {
      if (!rec) return '';
      const rid = Number(rec.release_id);
      const cached = state.exactAlbumLinksCache[rid] || state.exactAlbumLinksCache[String(rid)] || {};
      if (cached.spotifyAlbumId && /^[A-Za-z0-9]{15,30}$/.test(String(cached.spotifyAlbumId))) {
        return String(cached.spotifyAlbumId);
      }
      const ytmVerified = (rid && (VERIFIED_YTM_RELEASE_MAP[rid] || VERIFIED_YTM_RELEASE_MAP[String(rid)])) || {};
      const candidates = [rec.spotifyAlbumId, ytmVerified.spotifyAlbumId];
      for (const c of candidates) {
        if (typeof c === 'string' && /^[A-Za-z0-9]{15,30}$/.test(c)) {
          return c;
        }
      }
      return '';
    }

    // Direct https://music.youtube.com/playlist?list=OLAK5uy_... Album URL (NEVER uses PL... playlists!)
    function getYouTubeMusicDeepLink(rec, track, streamData) {
      const olakId = getVerifiedOlakPlaylistId(rec, streamData);
      if (olakId) {
        return `https://music.youtube.com/playlist?list=${encodeURIComponent(olakId)}`;
      }
      const q = `${cleanArtistName(rec ? rec.artist : '')} ${cleanSearchTitle(rec ? rec.title : '')}`.trim();
      return `https://music.youtube.com/search?q=${encodeURIComponent(q)}`;
    }

    // Direct https://open.spotify.com/album/<id> Album URL
    function getSpotifyAlbumDeepLink(rec) {
      if (!rec) return 'https://open.spotify.com';
      const spId = getVerifiedSpotifyAlbumId(rec);
      if (spId) {
        return `https://open.spotify.com/album/${encodeURIComponent(spId)}`;
      }
      const q = `${cleanArtistName(rec.artist || '')} ${cleanSearchTitle(rec.title || '')}`.trim();
      return `https://open.spotify.com/search/${encodeURIComponent(q)}/albums`;
    }

    function applyResolvedAlbumLinksToDom(rec) {
      if (!rec) return;
      const list = state.filteredRecords.length ? state.filteredRecords : state.records;
      const activeRec = list[state.activeIndex];
      if (!activeRec || Number(activeRec.release_id) !== Number(rec.release_id)) return;

      const sData = state.streamCache[Number(rec.release_id)] || resolveAlbumStreamingData(rec);
      const ytmUrl = getYouTubeMusicDeepLink(rec, null, sData);
      const spUrl = getSpotifyAlbumDeepLink(rec);

      const ytmLink = document.getElementById('stream-ytm-direct-link');
      if (ytmLink) ytmLink.href = ytmUrl;
      const spLink = document.getElementById('stream-spotify-direct-link');
      if (spLink) spLink.href = spUrl;

      const trackListEl = document.getElementById('stream-tracklist-list');
      if (trackListEl) {
        trackListEl.querySelectorAll('a[data-ytm-role="ytm"]').forEach(a => { a.href = ytmUrl; });
        trackListEl.querySelectorAll('a[data-ytm-role="spotify"]').forEach(a => { a.href = spUrl; });
      }
    }

    async function fetchJsonWithCorsFallback(targetUrl, timeoutMs = 8500) {
      const urlsToTry = [
        targetUrl,
        `https://api.allorigins.win/raw?url=${encodeURIComponent(targetUrl)}`,
        `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(targetUrl)}`,
      ];
      for (const u of urlsToTry) {
        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), timeoutMs);
        try {
          const resp = await fetch(u, { signal: ctrl.signal });
          clearTimeout(tid);
          if (resp.ok) {
            return await resp.json();
          }
        } catch (err) {
          clearTimeout(tid);
        }
      }
      return null;
    }

    function extractOlakAndSpotifyFromSonglink(slData) {
      let olakId = '';
      let spotifyAlbumId = '';
      if (!slData || typeof slData !== 'object') return { olakId, spotifyAlbumId };

      const platforms = slData.linksByPlatform || {};
      const ytmUrl = (platforms.youtubeMusic && platforms.youtubeMusic.url) || (platforms.youtube && platforms.youtube.url) || '';
      const mOlak = String(ytmUrl).match(/(OLAK5uy_[A-Za-z0-9_-]+)/);
      if (mOlak && mOlak[1]) {
        olakId = mOlak[1];
      }
      if (!olakId && slData.entitiesByUniqueId) {
        for (const ent of Object.values(slData.entitiesByUniqueId)) {
          if (ent && ent.id && String(ent.id).startsWith('OLAK5uy_')) {
            olakId = String(ent.id);
            break;
          }
        }
      }

      const spUrl = (platforms.spotify && platforms.spotify.url) || '';
      const mSp = String(spUrl).match(/open\.spotify\.com\/(?:intl-[a-z-]+\/)?album\/([A-Za-z0-9]{15,30})/);
      if (mSp && mSp[1]) {
        spotifyAlbumId = mSp[1];
      }
      if (!spotifyAlbumId && slData.entitiesByUniqueId) {
        for (const [uid, ent] of Object.entries(slData.entitiesByUniqueId)) {
          if (uid.startsWith('SPOTIFY_ALBUM::') && ent && ent.id) {
            spotifyAlbumId = String(ent.id);
            break;
          }
        }
      }
      return { olakId, spotifyAlbumId };
    }

    // Resolve exact OLAK5uy_... YouTube Music Album ID & Spotify /album/<id> via Fuzzy/Wildcard iTunes Search + Odesli (api.song.link)
    async function resolveExactAlbumPlatformLinks(rec) {
      if (!rec) return { olakId: '', spotifyAlbumId: '' };
      const rid = Number(rec.release_id);
      const sData = state.streamCache[rid] || resolveAlbumStreamingData(rec);

      let olakId = getVerifiedOlakPlaylistId(rec, sData);
      let spotifyAlbumId = getVerifiedSpotifyAlbumId(rec);
      if (olakId && spotifyAlbumId) {
        return { olakId, spotifyAlbumId };
      }

      if (state.pendingAlbumLinkPromises[rid]) {
        return state.pendingAlbumLinkPromises[rid];
      }

      const promise = (async () => {
        const cleanArt = cleanArtistName(rec.artist || '');
        const queryVariants = buildAlbumSearchQueryVariants(rec);

        // 1. If we already have OLAK5uy_, ask Odesli directly for its matching Spotify Album ID!
        if (olakId && !spotifyAlbumId) {
          const ytmAlbumUrl = `https://music.youtube.com/playlist?list=${olakId}`;
          const slData = await fetchJsonWithCorsFallback(
            `https://api.song.link/v1-alpha.1/links?url=${encodeURIComponent(ytmAlbumUrl)}&userCountry=US`
          );
          const ext = extractOlakAndSpotifyFromSonglink(slData);
          if (ext.spotifyAlbumId) spotifyAlbumId = ext.spotifyAlbumId;
        }

        // 2. Query iTunes Search API across literal & wildcard variants (entity=album, then fallback entity=song)
        if (!olakId || !spotifyAlbumId) {
          let bestItem = null;
          let bestScore = -1;

          const evaluateResults = (results) => {
            if (!Array.isArray(results)) return;
            for (const item of results) {
              if (!item || (!item.collectionId && !item.collectionViewUrl)) continue;
              const sc = scoreAlbumCandidateFuzzy(
                cleanArt,
                rec.title || '',
                item.artistName || '',
                item.collectionName || '',
                item.trackCount || 0
              );
              if (sc > bestScore && sc >= 45) {
                bestScore = sc;
                bestItem = item;
              }
            }
          };

          for (const qVar of queryVariants.slice(0, 4)) {
            for (const entityType of ['album', 'song']) {
              const itunesUrl = `https://itunes.apple.com/search?term=${encodeURIComponent(qVar)}&media=music&entity=${entityType}&limit=15`;
              let itunesData = null;
              try {
                const ctrl = new AbortController();
                const tid = setTimeout(() => ctrl.abort(), 3000);
                const resp = await fetch(itunesUrl, { signal: ctrl.signal });
                clearTimeout(tid);
                if (resp.ok) itunesData = await resp.json();
              } catch (e) {
                try {
                  itunesData = await fetchJsonpUrl(itunesUrl, 'callback', 3200);
                } catch (e2) {}
              }
              if (itunesData && itunesData.results) {
                evaluateResults(itunesData.results);
              }
              if (bestItem && bestScore >= 95) break;
            }
            if (bestItem && bestScore >= 95) break;
          }

          if (bestItem) {
            const bestCollectionId = String(bestItem.collectionId || '');
            const bestCollectionUrl = String(bestItem.collectionViewUrl || '');
            const slEndpoint = bestCollectionId
              ? `https://api.song.link/v1-alpha.1/links?platform=itunes&type=album&id=${encodeURIComponent(bestCollectionId)}&userCountry=US`
              : `https://api.song.link/v1-alpha.1/links?url=${encodeURIComponent(bestCollectionUrl)}&userCountry=US`;
            const slData = await fetchJsonWithCorsFallback(slEndpoint);
            const ext = extractOlakAndSpotifyFromSonglink(slData);
            if (!olakId && ext.olakId) olakId = ext.olakId;
            if (!spotifyAlbumId && ext.spotifyAlbumId) spotifyAlbumId = ext.spotifyAlbumId;
          }

          // 3. Fallback: If OLAK5uy_ is still missing, query YouTube Playlist Search across wildcard variants for OLAK5uy_
          if (!olakId) {
            for (const qVar of queryVariants.slice(0, 3)) {
              const ytPlSearchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(qVar + ' album')}&sp=EgIQAw%3D%3D`;
              for (const proxyUrl of [
                `https://api.allorigins.win/raw?url=${encodeURIComponent(ytPlSearchUrl)}`,
                `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(ytPlSearchUrl)}`,
              ]) {
                try {
                  const ctrl = new AbortController();
                  const tid = setTimeout(() => ctrl.abort(), 4500);
                  const r = await fetch(proxyUrl, { signal: ctrl.signal });
                  clearTimeout(tid);
                  if (r.ok) {
                    const txt = await r.text();
                    const mOl = txt.match(/(OLAK5uy_[A-Za-z0-9_-]{10,})/);
                    if (mOl && mOl[1]) {
                      olakId = mOl[1];
                      break;
                    }
                  }
                } catch (e) {}
              }
              if (olakId) break;
            }
          }
        }

        // Persist any newly resolved OLAK5uy_ or spotifyAlbumId onto the record, VERIFIED_YTM_RELEASE_MAP, and localStorage
        if (olakId || spotifyAlbumId) {
          const prev = state.exactAlbumLinksCache[rid] || {};
          state.exactAlbumLinksCache[rid] = {
            olakId: olakId || prev.olakId || '',
            spotifyAlbumId: spotifyAlbumId || prev.spotifyAlbumId || '',
          };
          saveExactAlbumLinksCache();

          if (olakId) {
            rec.ytPlaylistId = olakId;
            if (state.streamCache[rid]) state.streamCache[rid].ytPlaylistId = olakId;
            if (!VERIFIED_YTM_RELEASE_MAP[rid]) VERIFIED_YTM_RELEASE_MAP[rid] = {};
            VERIFIED_YTM_RELEASE_MAP[rid].ytPlaylistId = olakId;
            const stemKey = computeAlbumFuzzyStemKey(rec.artist, rec.title);
            if (stemKey) VERIFIED_YTM_ALBUM_STEM_MAP[stemKey] = olakId;
          }
          if (spotifyAlbumId) {
            rec.spotifyAlbumId = spotifyAlbumId;
            if (!VERIFIED_YTM_RELEASE_MAP[rid]) VERIFIED_YTM_RELEASE_MAP[rid] = {};
            VERIFIED_YTM_RELEASE_MAP[rid].spotifyAlbumId = spotifyAlbumId;
          }
          applyResolvedAlbumLinksToDom(rec);
        }

        return { olakId, spotifyAlbumId };
      })().finally(() => {
        delete state.pendingAlbumLinkPromises[rid];
      });

      state.pendingAlbumLinkPromises[rid] = promise;
      return promise;
    }

    function updateStreamingQuickLinks(rec, track = null, streamData = null) {
      if (!rec) return;
      const artPill = document.getElementById('stream-artist-pill');
      if (artPill) artPill.textContent = rec.artist;
      const sData = streamData || state.streamCache[Number(rec.release_id)] || resolveAlbumStreamingData(rec);
      const ytmLink = document.getElementById('stream-ytm-direct-link');
      if (ytmLink) {
        ytmLink.href = getYouTubeMusicDeepLink(rec, track, sData);
      }
      const spLink = document.getElementById('stream-spotify-direct-link');
      if (spLink) {
        spLink.href = getSpotifyAlbumDeepLink(rec);
      }
      // Trigger background resolution so OLAK5uy_ and Spotify /album/<id> are ready before the user clicks
      resolveExactAlbumPlatformLinks(rec);
    }

    // JSONP helper for CORS-free / file:// fallback queries to iTunes & Deezer
    function fetchJsonpUrl(url, callbackParam = 'callback', timeoutMs = 3500) {
      return new Promise((resolve, reject) => {
        const cbName = `__vaultJsonp_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
        const script = document.createElement('script');
        let settled = false;
        const cleanup = () => {
          delete window[cbName];
          if (script.parentNode) script.parentNode.removeChild(script);
        };
        const tid = setTimeout(() => {
          if (settled) return;
          settled = true;
          cleanup();
          reject(new Error('JSONP timeout'));
        }, timeoutMs);

        window[cbName] = (data) => {
          if (settled) return;
          settled = true;
          clearTimeout(tid);
          cleanup();
          resolve(data);
        };
        script.onerror = () => {
          if (settled) return;
          settled = true;
          clearTimeout(tid);
          cleanup();
          reject(new Error('JSONP error'));
        };
        const sep = url.includes('?') ? '&' : '?';
        script.src = `${url}${sep}${callbackParam}=${cbName}`;
        document.head.appendChild(script);
      });
    }

    function scorePreviewCandidate(itemArtist, itemTrack, itemAlbum, targetArtKey, targetTrkKey, targetAlbKey) {
      const aKey = normalizeTrackKey(itemArtist || '');
      const tKey = normalizeTrackKey(itemTrack || '');
      const cKey = normalizeTrackKey(itemAlbum || '');
      let score = 0;
      if (aKey && targetArtKey) {
        if (aKey === targetArtKey) score += 50;
        else if (aKey.includes(targetArtKey) || targetArtKey.includes(aKey)) score += 30;
        else return -1;
      }
      if (tKey && targetTrkKey) {
        if (tKey === targetTrkKey) score += 60;
        else if (tKey.startsWith(targetTrkKey) || targetTrkKey.startsWith(tKey)) score += 45;
        else if (tKey.includes(targetTrkKey) || targetTrkKey.includes(tKey)) score += 30;
      }
      if (cKey && targetAlbKey && (cKey.includes(targetAlbKey) || targetAlbKey.includes(cKey))) {
        score += 20;
      }
      return score;
    }

    // Resolve a 30-second MP3/M4A preview URL from iTunes Search API (fetch + JSONP) or Deezer JSONP
    async function resolve30sTrackPreviewUrl(rec, trackTitle) {
      const cleanArt = cleanArtistName(rec.artist || '');
      const cleanTrk = cleanSearchTitle(trackTitle || rec.title || '');
      const cleanAlb = cleanSearchTitle(rec.title || '');
      const artKey = normalizeTrackKey(cleanArt);
      const trkKey = normalizeTrackKey(cleanTrk);
      const albKey = normalizeTrackKey(cleanAlb);
      const cacheKey = `prev30_v47_${artKey}_${trkKey}`;

      if (state.previewUrlCache[cacheKey]) {
        return state.previewUrlCache[cacheKey];
      }
      const saved = safeGetStorage(cacheKey);
      if (saved && saved.startsWith('http')) {
        state.previewUrlCache[cacheKey] = saved;
        return saved;
      }

      const pickBestFromItunesResults = (results) => {
        if (!Array.isArray(results) || !results.length) return null;
        let bestUrl = null;
        let bestScore = -1;
        for (const item of results) {
          if (!item || !item.previewUrl) continue;
          const sc = scorePreviewCandidate(item.artistName, item.trackName, item.collectionName, artKey, trkKey, albKey);
          const itemAKey = normalizeTrackKey(item.artistName || '');
          const itemTKey = normalizeTrackKey(item.trackName || '');
          if (itemAKey === artKey && itemTKey) {
            state.previewUrlCache[`prev30_v47_${artKey}_${itemTKey}`] = item.previewUrl;
          }
          if (sc > bestScore) {
            bestScore = sc;
            bestUrl = item.previewUrl;
          }
        }
        return bestUrl;
      };

      const queries = [
        `${cleanArt} ${cleanTrk} ${cleanAlb}`.trim(),
        `${cleanArt} ${cleanTrk}`.trim(),
      ];

      // 1. iTunes Search API via fetch (fast) with JSONP fallback (for file://)
      for (const q of queries) {
        const baseUrl = `https://itunes.apple.com/search?term=${encodeURIComponent(q)}&media=music&entity=song&limit=20`;
        try {
          const ctrl = new AbortController();
          const tid = setTimeout(() => ctrl.abort(), 2800);
          const resp = await fetch(baseUrl, { signal: ctrl.signal });
          clearTimeout(tid);
          if (resp.ok) {
            const data = await resp.json();
            const best = pickBestFromItunesResults(data && data.results);
            if (best) {
              state.previewUrlCache[cacheKey] = best;
              safeSetStorage(cacheKey, best);
              return best;
            }
          }
        } catch (e) {
          try {
            const data = await fetchJsonpUrl(baseUrl, 'callback', 3200);
            const best = pickBestFromItunesResults(data && data.results);
            if (best) {
              state.previewUrlCache[cacheKey] = best;
              safeSetStorage(cacheKey, best);
              return best;
            }
          } catch (e2) {}
        }
      }

      // 2. Deezer JSONP API fallback
      try {
        const dzUrl = `https://api.deezer.com/search?q=${encodeURIComponent(cleanArt + ' ' + cleanTrk)}&output=jsonp`;
        const dzData = await fetchJsonpUrl(dzUrl, 'callback', 3200);
        const dzList = (dzData && Array.isArray(dzData.data)) ? dzData.data : [];
        let bestDz = null;
        let bestDzScore = -1;
        for (const item of dzList) {
          if (!item || !item.preview) continue;
          const sc = scorePreviewCandidate(
            item.artist && item.artist.name,
            item.title,
            item.album && item.album.title,
            artKey,
            trkKey,
            albKey
          );
          if (sc > bestDzScore) {
            bestDzScore = sc;
            bestDz = item.preview;
          }
        }
        if (bestDz) {
          state.previewUrlCache[cacheKey] = bestDz;
          safeSetStorage(cacheKey, bestDz);
          return bestDz;
        }
      } catch (e) {}

      return null;
    }

    function syncStreamingStageModeUI(rec) {
      if (!rec) return;
      const rid = Number(rec.release_id);
      const streamData = state.streamCache[rid] || resolveAlbumStreamingData(rec);
      const tracks = (streamData && Array.isArray(streamData.tracks)) ? streamData.tracks : [];
      const activeIdx = (state.activeStreamRid === rid && state.activeTrackIndex >= 0) ? state.activeTrackIndex : 0;
      const curTrack = tracks[activeIdx] || tracks[0] || { title: rec.title, duration: '3:45' };

      const engineDot = document.getElementById('stream-engine-dot');
      const isPlayingThis = state.activeStreamRid === rid && state.isPreviewPlaying;

      if (engineDot) {
        engineDot.className = isPlayingThis
          ? 'w-2 h-2 rounded-full bg-emerald-400 animate-ping shrink-0'
          : 'w-2 h-2 rounded-full bg-rose-500 shrink-0';
      }

      updateStreamingQuickLinks(rec, curTrack, streamData);
    }

    // Render Side B (30-Second HTML5 Audio Preview Player + YT Music & Spotify Album Links)
    function renderStreamingDeck(rec) {
      if (!rec) return;
      const rid = Number(rec.release_id);
      const wax = rec.wax_spec || {};
      const c1 = wax.primary_color || '#e11d48';
      const c2 = wax.secondary_color || '#7c3aed';

      const glowEl = document.getElementById('stream-ambient-glow');
      if (glowEl) {
        glowEl.style.background = `radial-gradient(circle at 50% 12%, ${c1}77, ${c2}38 56%, transparent 88%)`;
      }

      const { primary: covPrimary, fallback: covFallback } = getCoverUrls(rec);
      const coverImg = document.getElementById('stream-cover-img');
      if (coverImg) {
        coverImg.src = covPrimary || covFallback || '';
        coverImg.onerror = function () {
          if (covFallback && this.src !== covFallback) this.src = covFallback;
        };
      }

      document.getElementById('stream-artist-pill').textContent = rec.artist;
      document.getElementById('stream-album-title').textContent = rec.title;

      const streamData = resolveAlbumStreamingData(rec);
      paintStreamingTracklistUI(rec, streamData, false);
      syncStreamingStageModeUI(rec);

      if (state.activeStreamRid !== rid) {
        const timeReadout = document.getElementById('stream-time-readout');
        if (timeReadout) timeReadout.textContent = '0:00 / 0:30';
        const seekSlider = document.getElementById('stream-seek-slider');
        if (seekSlider) seekSlider.value = '0';
      }
    }

    function paintStreamingTracklistUI(rec, streamData, isRefreshing = false) {
      const rid = Number(rec.release_id);
      const tracks = (streamData && Array.isArray(streamData.tracks)) ? streamData.tracks : [];
      const songCount = tracks.length;
      const mins = (streamData && streamData.totalMinutes) ? streamData.totalMinutes : 42;
      const yr = (streamData && streamData.year) || rec.year || 'LP';

      document.getElementById('stream-album-meta').textContent = songCount > 0
        ? `${rec.artist} • ${yr} • ${songCount} song${songCount === 1 ? '' : 's'} • ${mins} mins`
        : `${rec.artist} • ${yr} • ${rec.wax_spec ? rec.wax_spec.variant_badge : 'LP'}`;

      const listEl = document.getElementById('stream-tracklist-list');
      if (!listEl) return;

      const isThisRecordActive = state.activeStreamRid === rid;
      const albumYtmUrl = getYouTubeMusicDeepLink(rec, null, streamData);
      const albumSpotifyUrl = getSpotifyAlbumDeepLink(rec);

      listEl.innerHTML = tracks.map((t, idx) => {
        const isCurrent = isThisRecordActive && state.activeTrackIndex === idx;
        const isPlayingNow = isCurrent && state.isPreviewPlaying;
        const sourceTag = isPlayingNow ? '▶ Playing 30s Preview' : '🎵 30s Preview';
        const subMeta = t.plays
          ? `${t.plays}${t.position ? ' • ' + t.position : ''} • ${sourceTag}`
          : `${t.position ? 'Side ' + t.position + ' • ' : ''}${sourceTag}`;

        return `
          <div
            data-track-idx="${idx}"
            data-track-rid="${rid}"
            class="group flex items-center justify-between gap-2 py-1.5 px-2.5 rounded-lg cursor-pointer transition select-none ${isCurrent ? 'bg-rose-500/20 text-rose-100 border border-rose-500/40 shadow-sm' : 'hover:bg-white/[0.07] text-slate-200 border border-transparent'}"
          >
            <div class="flex items-center gap-2.5 min-w-0 flex-1">
              <div class="w-5 text-center text-[11px] font-mono-tech shrink-0 ${isCurrent ? 'text-rose-400 font-bold' : 'text-slate-400'}">
                ${isPlayingNow ? `
                  <span class="inline-flex items-end justify-center gap-0.5 h-3">
                    <span class="w-0.5 bg-rose-400 eq-bar-1"></span>
                    <span class="w-0.5 bg-cyan-400 eq-bar-2"></span>
                    <span class="w-0.5 bg-emerald-400 eq-bar-3"></span>
                  </span>
                ` : `
                  <span class="group-hover:hidden">${idx + 1}</span>
                  <span class="hidden group-hover:inline text-rose-400 font-bold">▶</span>
                `}
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-xs font-bold truncate ${isCurrent ? 'text-rose-200' : 'text-white group-hover:text-rose-200'}">
                  ${t.title}
                </div>
                <div class="text-[10px] text-slate-400 truncate">
                  ${subMeta}
                </div>
              </div>
            </div>

            <div class="flex items-center gap-1 shrink-0">
              <span
                class="opacity-0 group-hover:opacity-100 ${isCurrent ? '!opacity-100 bg-rose-600 text-white' : 'bg-rose-500/20 text-rose-300'} px-1.5 py-0.5 rounded text-[9px] font-mono-tech font-semibold transition"
              >
                ${isPlayingNow ? '⏸ Pause' : '▶ 30s'}
              </span>
              <a
                href="${albumYtmUrl}"
                target="_blank"
                rel="noopener noreferrer"
                data-ytm-ext="1"
                data-ytm-role="ytm"
                class="opacity-0 group-hover:opacity-100 hover:bg-rose-500/25 text-slate-400 hover:text-rose-200 px-1 py-0.5 rounded text-[9px] font-mono-tech transition"
                title="Open Full Album on YouTube Music (OLAK5uy)"
              >
                YT↗
              </a>
              <a
                href="${albumSpotifyUrl}"
                target="_blank"
                rel="noopener noreferrer"
                data-ytm-ext="1"
                data-ytm-role="spotify"
                class="opacity-0 group-hover:opacity-100 hover:bg-emerald-500/25 text-slate-400 hover:text-emerald-200 px-1 py-0.5 rounded text-[9px] font-mono-tech transition"
                title="Open Full Album on Spotify"
              >
                SP↗
              </a>
              <span class="text-[11px] font-mono-tech text-slate-400 w-9 text-right">${t.duration || '3:45'}</span>
            </div>
          </div>
        `;
      }).join('');

      updateStreamTransportUI(rec);
    }

    function updateStreamTransportUI(rec) {
      const playIcon = document.getElementById('stream-play-icon');
      const coverHoverIcon = document.getElementById('stream-cover-hover-icon');
      const badgeEl = document.getElementById('stream-cover-playing-badge');
      const nowLabel = document.getElementById('stream-now-playing-label');
      const rid = rec ? Number(rec.release_id) : 0;
      const isThisActive = state.activeStreamRid === rid && state.isPreviewPlaying;

      if (playIcon) {
        playIcon.textContent = isThisActive ? '⏸' : '▶';
        playIcon.className = isThisActive ? '' : 'ml-0.5';
      }
      if (coverHoverIcon) {
        coverHoverIcon.textContent = isThisActive ? '⏸' : '▶';
      }
      if (badgeEl) {
        badgeEl.classList.toggle('hidden', !isThisActive);
      }

      const streamData = state.streamCache[rid] || (rec ? resolveAlbumStreamingData(rec) : null);
      const tracks = (streamData && Array.isArray(streamData.tracks)) ? streamData.tracks : [];
      if (state.activeStreamRid === rid && state.activeTrackIndex >= 0 && tracks[state.activeTrackIndex]) {
        const curTrack = tracks[state.activeTrackIndex];
        if (nowLabel) {
          nowLabel.textContent = `${state.isPreviewPlaying ? '▶ [30s Preview]' : '⏸ [Paused]'} ${state.activeTrackIndex + 1}/${tracks.length}: ${curTrack.title}`;
        }
        updateStreamingQuickLinks(rec, curTrack, streamData);
      } else if (nowLabel) {
        nowLabel.textContent = 'Click ▶ or select any track below for 30s preview';
      }
      syncStreamingStageModeUI(rec);
    }

    function engageTurntableForTrack(trackTitle) {
      if (!state.isSpinning) {
        state.isSpinning = true;
        const spinBtn = document.getElementById('btn-toggle-spin');
        if (spinBtn) spinBtn.textContent = '⏸ Pause Platter';
        const arm = document.getElementById('turntable-tonearm');
        if (arm) arm.className = 'tonearm-pivot tonearm-engaged absolute top-3.5 right-3.5 w-32 h-64 sm:w-[140px] sm:h-[280px] pointer-events-none z-30';
        const platterEl = document.getElementById('active-platter-disc');
        if (platterEl) platterEl.classList.remove('spin-paused');
      }
      const rpmReadout = document.getElementById('platter-rpm-readout');
      if (rpmReadout && trackTitle) {
        rpmReadout.textContent = `♫ ${String(trackTitle).slice(0, 18).toUpperCase()}`;
      }
    }

    // Play 30-second track preview via native HTML5 <audio id="vault-preview-audio">
    async function playAlbumTrackAtIndex(rec, trackIdx) {
      if (!rec) return;
      state.userRequestedPlay = true;

      const rid = Number(rec.release_id);
      const streamData = resolveAlbumStreamingData(rec);
      const tracks = (streamData && Array.isArray(streamData.tracks) && streamData.tracks.length)
        ? streamData.tracks
        : [{ position: 'A1', title: rec.title, duration: '3:45' }];

      const safeIdx = ((trackIdx % tracks.length) + tracks.length) % tracks.length;
      const track = tracks[safeIdx];
      const reqId = (state.playbackReqId || 0) + 1;
      state.playbackReqId = reqId;
      state.activeStreamRid = rid;
      state.cuedStreamRid = rid;
      state.activeTrackIndex = safeIdx;
      state.lastTrackSwitchAt = Date.now();
      state.activePlaybackEngine = 'html5';

      const audioEl = document.getElementById('vault-preview-audio');
      if (audioEl && !audioEl.paused) {
        try { audioEl.pause(); } catch (e) {}
      }

      const seekSlider = document.getElementById('stream-seek-slider');
      if (seekSlider) seekSlider.value = '0';
      const timeReadout = document.getElementById('stream-time-readout');
      if (timeReadout) timeReadout.textContent = '0:00 / 0:30';

      const nowLabel = document.getElementById('stream-now-playing-label');
      if (nowLabel) {
        nowLabel.textContent = `⏳ Loading 30s preview: ${track.title}...`;
      }

      const previewUrl = await resolve30sTrackPreviewUrl(rec, track.title);
      if (state.playbackReqId !== reqId) return;

      if (!previewUrl || !audioEl) {
        state.isPreviewPlaying = false;
        paintStreamingTracklistUI(rec, streamData, false);
        if (nowLabel) {
          nowLabel.textContent = `⚠ No 30s clip for "${track.title}" — open YT Music ↗ or Spotify ↗ above`;
        }
        return;
      }

      try {
        audioEl.src = previewUrl;
        audioEl.currentTime = 0;
        audioEl.muted = Boolean(state.isAudioMuted);
        await audioEl.play();
        if (state.playbackReqId !== reqId) return;
        state.isPreviewPlaying = true;
        engageTurntableForTrack(track.title);
        syncStreamingStageModeUI(rec);
        paintStreamingTracklistUI(rec, streamData, false);
      } catch (err) {
        state.isPreviewPlaying = false;
        paintStreamingTracklistUI(rec, streamData, false);
        if (nowLabel) {
          nowLabel.textContent = `Click ▶ again to start "${track.title}" (or open YT Music / Spotify ↗)`;
        }
      }
    }

    function stopPreviewAudio() {
      const audioEl = document.getElementById('vault-preview-audio');
      if (audioEl && !audioEl.paused) {
        try { audioEl.pause(); } catch (e) {}
      }
      state.isPreviewPlaying = false;
      const rpmReadout = document.getElementById('platter-rpm-readout');
      if (rpmReadout) {
        rpmReadout.textContent = state.rpm === 45 ? '45.0 RPM • QUARTZ LOCK' : '33.3 RPM • QUARTZ LOCK';
      }
    }

    function toggleInPagePlayPause() {
      const list = state.filteredRecords.length ? state.filteredRecords : state.records;
      const rec = list[state.activeIndex];
      if (!rec) return;
      const rid = Number(rec.release_id);
      const audioEl = document.getElementById('vault-preview-audio');

      if (state.activeStreamRid === rid && state.isPreviewPlaying) {
        stopPreviewAudio();
        updateStreamTransportUI(rec);
        const streamData = state.streamCache[rid] || resolveAlbumStreamingData(rec);
        if (streamData) paintStreamingTracklistUI(rec, streamData, false);
        return;
      }

      if (state.activeStreamRid === rid && state.activeTrackIndex >= 0 && audioEl && audioEl.src && audioEl.paused && audioEl.currentTime > 0 && audioEl.currentTime < (audioEl.duration || 30) - 0.5) {
        state.userRequestedPlay = true;
        audioEl.play().then(() => {
          state.isPreviewPlaying = true;
          updateStreamTransportUI(rec);
          const streamData = state.streamCache[rid] || resolveAlbumStreamingData(rec);
          if (streamData) paintStreamingTracklistUI(rec, streamData, false);
        }).catch(() => {
          playAlbumTrackAtIndex(rec, state.activeTrackIndex);
        });
        return;
      }

      const nextIdx = (state.activeStreamRid === rid && state.activeTrackIndex >= 0) ? state.activeTrackIndex : 0;
      playAlbumTrackAtIndex(rec, nextIdx);
    }

    function toggleHeroCardFlip(forceState) {
      const stageEl = document.getElementById('hero-flip-stage');
      if (!stageEl) return;
      state.isCardFlipped = typeof forceState === 'boolean' ? forceState : !state.isCardFlipped;
      stageEl.classList.toggle('is-flipped', state.isCardFlipped);

      const topLabel = document.getElementById('top-flip-label');
      const topIcon = document.getElementById('top-flip-icon');
      const botText = document.getElementById('flip-btn-text');
      const botArrow = document.getElementById('flip-btn-arrow');

      if (state.isCardFlipped) {
        if (topLabel) topLabel.textContent = 'Flip to Pressing Specs';
        if (topIcon) topIcon.textContent = '↺';
        if (botText) botText.textContent = 'Pressing & Specs';
        if (botArrow) botArrow.textContent = '↺';
        const list = state.filteredRecords.length ? state.filteredRecords : state.records;
        const rec = list[state.activeIndex];
        if (rec) renderStreamingDeck(rec);
      } else {
        if (topLabel) topLabel.textContent = 'Flip to Album Player';
        if (topIcon) topIcon.textContent = '↻';
        if (botText) botText.textContent = 'Stream & Tracklist';
        if (botArrow) botArrow.textContent = '↻';
      }
    }

    // Render the clickable strip of all real Discogs images for the active release
    function renderHeroGalleryStrip(rec) {
      const stripEl = document.getElementById('hero-gallery-strip');
      const expEl = document.getElementById('hero-cv-explanation');
      const rid = String(rec.release_id);
      const classified = (rec.images && Array.isArray(rec.images.classified_images) && rec.images.classified_images.length)
        ? rec.images.classified_images
        : (state.releaseGalleryCache[rid] || []);

      const { primary: activePrimary, fallback: activeFallback } = getPressingPhotoUrls(rec);
      const activePressingUrl = activePrimary || activeFallback;

      if (!classified.length) {
        const coverUrl = getRealCoverUrl(rec);
        if (coverUrl) {
          stripEl.innerHTML = `
            <div class="flex items-center gap-2">
              <img src="${coverUrl}" referrerpolicy="no-referrer" alt="Cover" class="w-12 h-12 rounded-lg object-cover border border-cyan-400" />
              <span class="text-[11px] text-slate-400">Primary cover loaded. Click <strong>↻ Refresh Gallery</strong> to fetch secondary images from Discogs for #${rec.release_id}.</span>
            </div>
          `;
        } else {
          stripEl.innerHTML = `<span class="text-[11px] text-slate-400">Click <strong>↻ Refresh Gallery</strong> to load Discogs release photos.</span>`;
        }
        expEl.textContent = `Format parsed: ${rec.wax_spec.variant_badge}`;
        return;
      }

      const selIdx = (rec.images && typeof rec.images.selected_index === 'number') ? rec.images.selected_index : -1;

      stripEl.innerHTML = classified.map((img, i) => {
        const remoteUri = img.uri || img.uri150 || '';
        const thumbSrc = img.local_uri || img.uri150 || remoteUri;
        const pinTarget = img.local_uri || remoteUri || '';
        const isPinned = Boolean(
          activePressingUrl && (
            activePressingUrl === remoteUri ||
            activePressingUrl === img.local_uri ||
            (!state.userOverrides[rid] && i === selIdx && rec.images && rec.images.has_pressing_photo)
          )
        );
        const roleLabel = i === 0 ? 'Cover [0]' : (isPinned || img.role === 'pressing_disc' ? `Pressing [${i}]` : `Img [${i}]`);
        const onErrAttr = (img.local_uri && remoteUri)
          ? `onerror="if(this.dataset.fb && this.src!==this.dataset.fb){this.src=this.dataset.fb;}" data-fb="${img.uri150 || remoteUri}"`
          : '';
        return `
          <button
            type="button"
            data-pin-image-url="${pinTarget}"
            data-pin-image-index="${i}"
            data-pin-release-id="${rec.release_id}"
            class="shrink-0 group relative rounded-lg overflow-hidden border-2 ${isPinned ? 'border-emerald-400 ring-2 ring-emerald-400/30' : 'border-white/15 hover:border-cyan-400'} transition"
            title="Click to pin image [${i}] as the vinyl pressing photo for ${rec.title}"
          >
            <img src="${thumbSrc}" ${onErrAttr} referrerpolicy="no-referrer" alt="${roleLabel}" class="w-14 h-14 object-cover bg-slate-900" />
            <span class="absolute bottom-0 inset-x-0 bg-black/80 text-[9px] font-mono-tech text-center py-0.5 ${isPinned ? 'text-emerald-300 font-bold' : 'text-slate-300'}">
              ${isPinned ? `✓ Photo [${i}]` : roleLabel}
            </span>
          </button>
        `;
      }).join('') + (activePressingUrl ? `
        <button type="button" data-clear-pin="${rec.release_id}" class="shrink-0 px-2.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-[10px] font-mono-tech text-slate-300 border border-white/10" title="Switch to procedural SVG wax ring">
          Use Wax Shader
        </button>
      ` : '');

      expEl.innerHTML = activePressingUrl
        ? `Defaulted wax ring to verified pressing photo for <strong>#${rec.release_id}</strong> (${classified.length} images in release gallery — click any thumbnail above to change).`
        : `No separate vinyl disc photo uploaded on Discogs for <strong>#${rec.release_id}</strong> (${classified.length} sleeve image${classified.length === 1 ? '' : 's'}) — displaying <strong>${rec.wax_spec.variant_badge}</strong> wax ring.`;
    }

    // Filter & Sort Records
    function applyFiltersAndSort() {
      const q = state.searchQuery.trim().toLowerCase();
      let list = state.records.filter(rec => {
        if (q) {
          const hay = `${rec.artist} ${rec.title} ${rec.label} ${rec.catno} ${rec.format_string} ${rec.wax_spec.variant_badge} ${rec.comments} ${rec.flattening_status || ''}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        if (state.filter === 'pressing_photo') return Boolean(getVerifiedPressingPhotoUrl(rec));
        if (state.filter === 'flattening_todo') return rec.flattening_status === 'Need to be done';
        if (state.filter === 'flattening_done') return rec.flattening_status === 'Done';
        if (state.filter === 'splatter') return ['splatter', 'color_in_color'].includes(rec.wax_spec.pattern);
        if (state.filter === 'galaxy_marble') return ['galaxy', 'marble', 'split'].includes(rec.wax_spec.pattern);
        if (state.filter === 'translucent') return Boolean(rec.wax_spec.translucent);
        if (state.filter === 'double_lp') return Boolean(rec.wax_spec.is_double_lp);
        if (state.filter === 'black_wax') return rec.wax_spec.pattern === 'black';
        return true;
      });

      list.sort((a, b) => {
        if (state.sortBy === 'artist_asc') return a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title);
        if (state.sortBy === 'title_asc') return a.title.localeCompare(b.title);
        if (state.sortBy === 'value_desc') return (b.estimated_value_usd || 0) - (a.estimated_value_usd || 0);
        if (state.sortBy === 'year_desc') return (b.year || 0) - (a.year || 0);
        return (b.date_added || '').localeCompare(a.date_added || '') || a.artist.localeCompare(b.artist);
      });

      state.filteredRecords = list;
      if (state.activeIndex >= list.length) state.activeIndex = 0;
      updateKpiStrip();
      renderHeroStage();
      renderCrateGrid();
    }

    function updateKpiStrip() {
      const total = state.records.length;
      const verifiedCount = state.records.filter(r => Boolean(getVerifiedPressingPhotoUrl(r))).length;
      const coloredCount = state.records.filter(r => r.wax_spec && r.wax_spec.pattern !== 'black').length;
      const pct = total ? ((coloredCount / total) * 100).toFixed(1) : '0.0';
      const pressPct = total ? ((verifiedCount / total) * 100).toFixed(1) : '0.0';

      document.getElementById('kpi-total-records').textContent = `${total} LPs`;
      document.getElementById('kpi-pressing-photos').textContent = `${verifiedCount} / ${total}`;
      document.getElementById('kpi-colored-wax').textContent = `${pct}%`;

      const progEl = document.getElementById('bg-enrich-progress');
      if (progEl) progEl.textContent = `• ${total} LPs & ${verifiedCount} Pressing Photos Compiled`;

      const heroRatioEl = document.getElementById('hero-pressing-ratio');
      if (heroRatioEl) heroRatioEl.textContent = `${verifiedCount}/${total}`;

      const searchInput = document.getElementById('search-input');
      if (searchInput) {
        searchInput.placeholder = `Search all ${total} LPs by artist, album, label, catalog #, or pressing color...`;
      }

      // Display official Discogs Collection Value (Low / Med / High from /users/<user>/collection/value)
      // Automatically scrub legacy synthetic (0.52 / 0.83 / 1.44 * ask_sum) values ($3,917.41 / $6,252.80 / $10,848.23)
      const prof = (window.__DISCOGS_COLLECTION__ && window.__DISCOGS_COLLECTION__.profile) ? window.__DISCOGS_COLLECTION__.profile : {};
      const colVal = prof.collection_value || {};
      const SYNTHETIC_LEGACY_VALS = new Set(['$3,917.41', '$6,252.80', '$10,848.23', '$3,721.74', '$6,011.87', '$10,437.49', '$3,886.22', '$6,203.01', '$10,761.84']);
      if (colVal.median && SYNTHETIC_LEGACY_VALS.has(String(colVal.median).trim())) {
        colVal.minimum = '$3,952.62';
        colVal.median = '$6,423.73';
        colVal.maximum = '$11,091.69';
      }
      const lowStr = (colVal.minimum && !SYNTHETIC_LEGACY_VALS.has(String(colVal.minimum).trim())) ? colVal.minimum : '$3,952.62';
      const medianStr = (colVal.median && !SYNTHETIC_LEGACY_VALS.has(String(colVal.median).trim())) ? colVal.median : '$6,423.73';
      const highStr = (colVal.maximum && !SYNTHETIC_LEGACY_VALS.has(String(colVal.maximum).trim())) ? colVal.maximum : '$11,091.69';

      const vaultValEl = document.getElementById('kpi-vault-value');
      const vaultRangeEl = document.getElementById('kpi-vault-range');
      const sumEl = document.getElementById('kpi-nm-ratio');
      const sumSubEl = document.getElementById('kpi-gallery-sub');

      if (vaultValEl) vaultValEl.textContent = medianStr;
      if (vaultRangeEl) vaultRangeEl.textContent = `Low ${lowStr} • High ${highStr}`;
      if (sumEl) sumEl.textContent = highStr;
      if (sumSubEl) sumSubEl.textContent = `High Est. • Low ${lowStr}`;

      const todoCount = state.records.filter(r => r.flattening_status === 'Need to be done').length;
      const doneCount = state.records.filter(r => r.flattening_status === 'Done').length;
      const unlistedCount = Math.max(0, total - todoCount - doneCount);

      const flatKpiEl = document.getElementById('kpi-flattening');
      if (flatKpiEl) {
        flatKpiEl.textContent = `${todoCount} Queued / ${doneCount} Done`;
      }

      const chipTodo = document.getElementById('chip-flatten-todo');
      if (chipTodo) chipTodo.textContent = `🔥 Flattening Queue (${todoCount})`;
      const chipDone = document.getElementById('chip-flatten-done');
      if (chipDone) chipDone.textContent = `✓ Flattened & Verified (${doneCount})`;

      // Update Pipeline Tab dynamic telemetry cards
      const pipeCv = document.getElementById('pipe-kpi-cv');
      if (pipeCv) pipeCv.textContent = `${verifiedCount} / ${total} Physical Discs Verified (${pressPct}%)`;
      const pipeFlat = document.getElementById('pipe-kpi-flatten');
      if (pipeFlat) pipeFlat.textContent = `${todoCount} Queued • ${doneCount} Flattened • ${unlistedCount} Uninspected`;
      const pipeVal = document.getElementById('pipe-kpi-val');
      if (pipeVal) pipeVal.textContent = `Med ${medianStr} • Low ${lowStr} • High ${highStr}`;

      // Update Modal stats
      const mLps = document.getElementById('modal-stat-lps');
      if (mLps) mLps.textContent = `${total} LPs`;
      const mPhotos = document.getElementById('modal-stat-photos');
      if (mPhotos) mPhotos.textContent = `${verifiedCount} Pressing Photos`;
      const mFlat = document.getElementById('modal-stat-flatten');
      if (mFlat) mFlat.textContent = `${todoCount} Queued / ${doneCount} Done`;
    }

    // Render Crate Grid Cards
    function renderCrateGrid() {
      const grid = document.getElementById('collection-grid');
      const statusLabel = document.getElementById('grid-status-label');
      const _vUser = (window.__DISCOGS_COLLECTION__ && window.__DISCOGS_COLLECTION__.username) || 'krunked'; statusLabel.textContent = `Showing ${state.filteredRecords.length} of ${state.records.length} releases in ${_vUser}'s collection`;

      if (!state.filteredRecords.length) {
        grid.innerHTML = `
          <div class="col-span-full bg-slate-900/60 border border-white/10 rounded-2xl p-8 text-center space-y-2">
            <div class="text-base font-bold text-white">No matching releases found</div>
            <p class="text-xs text-slate-400">Try clearing your search or selecting "All Releases".</p>
          </div>
        `;
        return;
      }

      grid.innerHTML = state.filteredRecords.map((rec, idx) => {
        const isSelected = idx === state.activeIndex;
        const verifiedPressingUrl = getVerifiedPressingPhotoUrl(rec);
        const hasRealCover = Boolean(getRealCoverUrl(rec));
        const flatStatus = rec.flattening_status || 'Not Listed';
        const flatPill = flatStatus === 'Need to be done'
          ? `<span class="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-amber-500/25 text-amber-200 border border-amber-400/40 z-30">🔥 Flatten Queue</span>`
          : (flatStatus === 'Done'
            ? `<span class="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-emerald-500/20 text-emerald-200 border border-emerald-400/30 z-30">✓ Flattened</span>`
            : '');

        let visualHtml = '';

        if (state.thumbMode === 'pressing' && verifiedPressingUrl) {
          visualHtml = `
            <div class="relative w-full h-52 bg-gradient-to-b from-slate-900/90 to-[#090b12] flex items-center justify-center p-4 overflow-hidden">
              ${flatPill}
              <div class="uv-reactive w-40 h-40 rounded-full shadow-2xl hover-spin transition-transform duration-300 group-hover:scale-105">
                ${renderDeterministicWaxSVG(rec, 160, true)}
              </div>
              <div class="absolute bottom-2.5 left-2.5 w-14 h-14 rounded-lg shadow-lg overflow-hidden border border-white/20 z-20">
                ${renderJacketSleeveHTML(rec)}
              </div>
              <span class="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 z-30">
                📸 Pressing Photo
              </span>
            </div>
          `;
        } else if (state.thumbMode === 'sleeve') {
          visualHtml = `
            <div class="relative w-full h-52 bg-gradient-to-b from-slate-900/90 to-[#090b12] p-4 flex items-center justify-center overflow-hidden">
              ${flatPill}
              <div class="w-40 h-40 shadow-2xl">
                ${renderJacketSleeveHTML(rec)}
              </div>
              <div class="absolute bottom-2.5 right-2.5 uv-reactive w-16 h-16 rounded-full shadow-2xl hover-spin border border-white/20 z-20">
                ${renderDeterministicWaxSVG(rec, 68, true)}
              </div>
            </div>
          `;
        } else {
          visualHtml = `
            <div class="relative w-full h-52 bg-gradient-to-b from-slate-900/90 to-[#090b12] flex items-center justify-center px-4 overflow-hidden">
              ${flatPill}
              <div class="relative w-32 h-32 z-10 shadow-2xl -ml-8 transition-transform group-hover:-translate-x-1">
                ${renderJacketSleeveHTML(rec)}
              </div>
              <div class="relative uv-reactive w-32 h-32 -ml-10 z-20 rounded-full shadow-2xl hover-spin transition-transform group-hover:translate-x-3">
                ${renderDeterministicWaxSVG(rec, 130, true)}
              </div>
              <span class="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full text-[10px] font-mono-tech ${verifiedPressingUrl ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-900/90 text-cyan-300 border border-white/10'} z-30">
                ${verifiedPressingUrl ? '📸 Pressing Photo' : (hasRealCover ? '💿 Cover + Wax' : '⚙ Wax Spec')}
              </span>
            </div>
          `;
        }

        return `
          <article
            data-card-index="${idx}"
            class="card-record group rounded-2xl bg-[#121521]/95 border ${isSelected ? 'border-cyan-400 ring-2 ring-cyan-400/25' : 'border-white/10 hover:border-cyan-500/40'} overflow-hidden shadow-lg transition-all flex flex-col justify-between cursor-pointer"
          >
            <div>
              ${visualHtml}
              <div class="p-3.5 space-y-2">
                <div class="flex items-center justify-between gap-1 flex-wrap">
                  <span class="px-2 py-0.5 rounded-md text-[10px] font-mono-tech font-medium bg-white/5 text-purple-300 border border-white/10 truncate max-w-[74%]">
                    ${rec.wax_spec.variant_badge}
                  </span>
                  <span class="text-xs font-mono-tech font-bold text-emerald-400">$${Number(rec.estimated_value_usd || 35).toFixed(2)}</span>
                </div>
                <div>
                  <h3 class="text-sm font-extrabold text-white group-hover:text-cyan-300 transition line-clamp-1">${rec.title}</h3>
                  <p class="text-xs font-semibold text-slate-400 line-clamp-1">${rec.artist} • <span class="text-slate-500">${rec.year || 'LP'}</span></p>
                </div>
                <div class="text-[11px] font-mono-tech text-slate-400 flex items-center justify-between pt-1 border-t border-white/5">
                  <span class="truncate max-w-[68%]">${rec.label} (${rec.catno})</span>
                  <span>${(rec.media_condition || 'NM').split('(')[0].trim()}</span>
                </div>
              </div>
            </div>
            <div class="px-3.5 pb-3 flex items-center justify-between gap-2">
              <span class="text-[10px] font-mono-tech text-slate-500">#${rec.release_id}</span>
              <a
                href="${rec.discogs_url || ('https://www.discogs.com/release/' + rec.release_id)}"
                target="_blank"
                rel="noopener noreferrer"
                data-stop-prop="true"
                class="text-[11px] font-mono-tech font-semibold text-cyan-400 hover:text-cyan-300 underline"
              >
                Discogs ↗
              </a>
            </div>
          </article>
        `;
      }).join('');
    }

    // Fetch a single release's full details & image gallery from Discogs API
    async function fetchSingleReleaseGallery(rec) {
      const rid = String(rec.release_id);
      const headers = { 'Accept': 'application/vnd.discogs.v2.discogs+json' };
      const resp = await fetch(`https://api.discogs.com/releases/${rid}?curr_abbr=USD`, { headers });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const detail = await resp.json();
      const existingImgs = (rec.images && Array.isArray(rec.images.classified_images)) ? rec.images.classified_images : [];
      const imgs = (detail.images || []).map((im, i) => {
        const prev = existingImgs[i] || {};
        return {
          index: i,
          uri: im.uri || im.resource_url || '',
          uri150: im.uri150 || im.uri || '',
          local_uri: prev.local_uri || '',
          width: im.width || 600,
          height: im.height || 600,
          role: prev.role || (i === 0 ? 'front_cover' : 'secondary'),
        };
      });
      state.releaseGalleryCache[rid] = imgs;
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

    // Render Flattening Queue View + Owner Inspection Bench
    function renderFlatteningView() {
      const todo = state.records
        .filter(r => r.flattening_status === 'Need to be done')
        .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));
      const allDone = state.records
        .filter(r => r.flattening_status === 'Done')
        .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));
      const allUnlisted = state.records
        .filter(r => r.flattening_status !== 'Need to be done' && r.flattening_status !== 'Done')
        .sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title));

      document.getElementById('flatten-todo-count').textContent = `${todo.length} Records`;
      document.getElementById('flatten-done-count').textContent = `${allDone.length} Records`;
      const unlistedCountEl = document.getElementById('flatten-unlisted-count');
      if (unlistedCountEl) unlistedCountEl.textContent = `${allUnlisted.length} Uninspected`;

      // Populate thermal timer record dropdown
      const timerSelect = document.getElementById('timer-record-select');
      if (timerSelect) {
        const prevVal = timerSelect.value;
        timerSelect.innerHTML = `<option value="">Select LP in Pouch (${todo.length} Queued)...</option>` +
          todo.map(r => `<option value="${r.release_id}">${r.artist} — ${r.title}</option>`).join('');
        if (prevVal && todo.some(r => String(r.release_id) === String(prevVal))) {
          timerSelect.value = prevVal;
        }
      }

      const doneQ = state.doneSearchQuery.trim().toLowerCase();
      const filteredDone = doneQ
        ? allDone.filter(r => `${r.artist} ${r.title} ${r.wax_spec.variant_badge}`.toLowerCase().includes(doneQ))
        : allDone;

      const renderRow = (r, isTodo) => `
        <div class="flex items-center justify-between gap-3 p-2.5 rounded-xl bg-slate-900/90 border border-white/10 hover:border-cyan-500/30 transition">
          <div class="flex items-center gap-3 min-w-0 cursor-pointer" data-load-turntable="${r.release_id}" title="Click to load onto Turntable Stage">
            <div class="w-11 h-11 rounded-full shrink-0 overflow-hidden shadow">
              ${renderDeterministicWaxSVG(r, 44, true)}
            </div>
            <div class="min-w-0">
              <div class="text-xs font-bold text-white hover:text-cyan-300 truncate">${r.artist} — ${r.title}</div>
              <div class="text-[11px] font-mono-tech text-slate-400 truncate">${r.wax_spec.variant_badge} • <span class="text-emerald-400">$${Number(r.estimated_value_usd || 35).toFixed(2)}</span></div>
            </div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <button type="button" data-set-flatten="${r.release_id}" data-target-status="${isTodo ? 'Done' : 'Need to be done'}" class="px-2.5 py-1 rounded-lg text-[11px] font-mono-tech font-semibold ${isTodo ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30' : 'bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/25'}">
              ${isTodo ? '✓ Mark Done' : '🔥 Re-Queue'}
            </button>
            <button type="button" data-set-flatten="${r.release_id}" data-target-status="Not Listed" class="px-2 py-1 rounded-lg text-[11px] font-mono-tech bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 border border-white/10" title="Remove from Flattening Queue (set to Not Listed)">
              ✕
            </button>
            <a href="${r.discogs_url || ('https://www.discogs.com/release/' + r.release_id)}" target="_blank" rel="noopener noreferrer" class="text-xs font-mono-tech text-cyan-400 hover:underline px-1">↗</a>
          </div>
        </div>
      `;

      document.getElementById('flatten-todo-list').innerHTML = todo.map(r => renderRow(r, true)).join('') ||
        '<div class="p-4 rounded-xl bg-slate-900/50 border border-white/5 text-xs text-slate-400 text-center">Queue is clear! Use the Owner Inspection Bench below to add any warped LP.</div>';
      document.getElementById('flatten-done-list').innerHTML = filteredDone.map(r => renderRow(r, false)).join('') ||
        '<div class="p-4 rounded-xl bg-slate-900/50 border border-white/5 text-xs text-slate-400 text-center">No matching flattened records.</div>';

      // Render Owner Inspection Bench (unlisted records matching benchSearchQuery)
      const benchEl = document.getElementById('flatten-bench-list');
      if (benchEl) {
        const bq = state.benchSearchQuery.trim().toLowerCase();
        const benchPool = bq
          ? allUnlisted.filter(r => `${r.artist} ${r.title} ${r.label} ${r.catno} ${r.wax_spec.variant_badge} ${r.release_id}`.toLowerCase().includes(bq))
          : allUnlisted.slice(0, 18);

        benchEl.innerHTML = benchPool.map(r => `
          <div class="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-slate-900/80 border border-white/10 hover:border-cyan-500/30 transition">
            <div class="flex items-center gap-2.5 min-w-0 cursor-pointer" data-load-turntable="${r.release_id}" title="Click to inspect on Turntable Stage">
              <div class="w-9 h-9 rounded-full shrink-0 overflow-hidden shadow">
                ${renderDeterministicWaxSVG(r, 36, true)}
              </div>
              <div class="min-w-0">
                <div class="text-xs font-bold text-white truncate">${r.artist} — ${r.title}</div>
                <div class="text-[10px] font-mono-tech text-slate-400 truncate">#${r.release_id} • ${r.wax_spec.variant_badge}</div>
              </div>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <button type="button" data-set-flatten="${r.release_id}" data-target-status="Need to be done" class="px-2 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 text-[10px] font-mono-tech font-semibold" title="Add warped LP to Flattening Queue">
                + 🔥 Queue
              </button>
              <button type="button" data-set-flatten="${r.release_id}" data-target-status="Done" class="px-2 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono-tech font-semibold" title="Mark LP as Flattened &amp; Verified">
                + ✓ Done
              </button>
            </div>
          </div>
        `).join('') || '<div class="col-span-full text-xs text-slate-400 py-3 text-center">No matching uninspected records found.</div>';
      }
    }

    // 2.5-Hour (150-Minute) Thermal Plate Session Timer
    const HOLD_DURATION_MS = 150 * 60 * 1000; // 2.5 hours

    function formatDurationMs(ms) {
      const totalSec = Math.max(0, Math.ceil(ms / 1000));
      const hrs = Math.floor(totalSec / 3600);
      const mins = Math.floor((totalSec % 3600) / 60);
      const secs = totalSec % 60;
      return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    function playTimerChime() {
      try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return;
        const ctx = new AudioContextClass();
        [523.25, 659.25, 783.99, 1046.5].forEach((freq, i) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = 'sine';
          osc.frequency.value = freq;
          gain.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.18);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.18 + 0.45);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(ctx.currentTime + i * 0.18);
          osc.stop(ctx.currentTime + i * 0.18 + 0.46);
        });
      } catch (e) {}
    }

    function updateThermalTimerUI() {
      const readoutEl = document.getElementById('timer-readout');
      const badgeEl = document.getElementById('timer-phase-badge');
      if (!readoutEl || !badgeEl) return;

      const rawState = safeGetStorage('krunked_flattening_timer_v4');
      if (!rawState) {
        readoutEl.textContent = '02:30:00';
        badgeEl.textContent = 'Plate Idle • Ready';
        badgeEl.className = 'px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-slate-800 text-slate-300 border border-white/10';
        return;
      }

      let tState = null;
      try { tState = JSON.parse(rawState); } catch (e) {}
      if (!tState) return;

      if (tState.mode === 'ramp') {
        const elapsedMs = Date.now() - (tState.startedAt || Date.now());
        readoutEl.textContent = formatDurationMs(elapsedMs);
        badgeEl.textContent = '🔥 Stage 1: Ramping on 6 → 130°F';
        badgeEl.className = 'px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse';
      } else if (tState.mode === 'hold') {
        const remainingMs = (tState.endsAt || 0) - Date.now();
        if (remainingMs <= 0) {
          readoutEl.textContent = '00:00:00';
          badgeEl.textContent = '✓ 2.5h Hold Complete — Cool Before Unbagging!';
          badgeEl.className = 'px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-emerald-500/25 text-emerald-300 border border-emerald-400/50';
          if (!tState.notified) {
            tState.notified = true;
            safeSetStorage('krunked_flattening_timer_v4', JSON.stringify(tState));
            playTimerChime();
            showToast('🔥 2.5-Hour Thermal Hold Complete! Turn plate off and let pouch cool completely.');
          }
        } else {
          readoutEl.textContent = formatDurationMs(remainingMs);
          badgeEl.textContent = '⏱ Stage 2: Holding on 4 (130°F • 2.5h)';
          badgeEl.className = 'px-2 py-0.5 rounded-full text-[10px] font-mono-tech bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 animate-pulse';
        }
      }
    }

    function updateSandboxPreview() {
      const fmt = document.getElementById('sandbox-format-input').value;
      const notes = document.getElementById('sandbox-notes-input').value;
      const spec = parseWaxVariantJS(fmt, notes, 777);
      document.getElementById('sandbox-json-output').textContent = JSON.stringify(spec, null, 2);
      document.getElementById('sandbox-badge-preview').textContent = spec.variant_badge;
      document.getElementById('sandbox-disc-preview').innerHTML = renderDeterministicWaxSVG(
        { release_id: 99999, artist: 'KRUNKED', title: 'SANDBOX', year: 2026, catno: 'TEST-01', wax_spec: spec, images: {} },
        176,
        false
      );
    }

    function toggleVinylAudio() {
      const btn = document.getElementById('btn-toggle-audio');
      if (state.audioPlaying) {
        if (state.audioCtx) {
          state.audioCtx.close();
          state.audioCtx = null;
        }
        state.audioPlaying = false;
        btn.textContent = '🔇 Vinyl Audio: Off';
        btn.className = 'px-3 py-1.5 rounded-lg text-xs font-mono-tech font-semibold bg-slate-800 text-slate-300 border border-white/10 hover:text-white transition';
        return;
      }

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        showToast('Web Audio API unavailable in this browser.');
        return;
      }
      const ctx = new AudioContextClass();
      const bufferSize = ctx.sampleRate * 3;
      const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      const output = noiseBuffer.getChannelData(0);
      for (let i = 0; i < bufferSize; i++) {
        output[i] = (Math.random() < 0.004) ? (Math.random() * 0.35 - 0.175) : (Math.random() * 0.015 - 0.0075);
      }
      const whiteNoise = ctx.createBufferSource();
      whiteNoise.buffer = noiseBuffer;
      whiteNoise.loop = true;

      const filter = ctx.createBiquadFilter();
      filter.type = 'bandpass';
      filter.frequency.value = 1900;

      const gain = ctx.createGain();
      gain.gain.value = 0.18;

      whiteNoise.connect(filter);
      filter.connect(gain);
      gain.connect(ctx.destination);
      whiteNoise.start();

      state.audioCtx = ctx;
      state.audioPlaying = true;
      btn.textContent = '🔊 Vinyl Crackle: On';
      btn.className = 'px-3 py-1.5 rounded-lg text-xs font-mono-tech font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 transition';
    }

    async function loadExternalJsonIfNewer() {
      try {
        const [ovResp, colResp, fqResp] = await Promise.all([
          fetch('./data/overrides.json', { cache: 'no-store' }).catch(() => null),
          fetch('./data/collection.json', { cache: 'no-store' }).catch(() => null),
          fetch('./data/flattening_queue.json', { cache: 'no-store' }).catch(() => null),
        ]);
        let changed = false;
        if (ovResp && ovResp.ok) {
          const extOv = await ovResp.json();
          if (extOv && typeof extOv === 'object') {
            state.userOverrides = { ...extOv, ...state.userOverrides };
            changed = true;
          }
        }
        if (colResp && colResp.ok) {
          const extCol = await colResp.json();
          if (extCol && Array.isArray(extCol.records) && extCol.records.length >= state.records.length) {
            const extPressings = extCol.records.filter(r => r.images && r.images.has_pressing_photo).length;
            const curPressings = state.records.filter(r => r.images && r.images.has_pressing_photo).length;
            if (extCol.records.length > state.records.length || extPressings > curPressings) {
              extCol.records.forEach(r => {
                const olak = getVerifiedOlakPlaylistId(r, null);
                if (olak) r.ytPlaylistId = olak;
                const sp = getVerifiedSpotifyAlbumId(r);
                if (sp) r.spotifyAlbumId = sp;
              });
              if (extCol.profile && extCol.profile.collection_value) {
                const cv = extCol.profile.collection_value;
                if (['$6,252.80', '$6,011.87', '$6,203.01'].includes(String(cv.median || '').trim())) {
                  cv.minimum = '$3,952.62';
                  cv.median = '$6,423.73';
                  cv.maximum = '$11,091.69';
                }
              }
              window.__DISCOGS_COLLECTION__ = extCol;
              state.records = extCol.records;
              changed = true;
            }
          }
        }
        if (fqResp && fqResp.ok && !state.unsavedFlattenCount) {
          const extFq = await fqResp.json();
          const inlineTs = (document.getElementById('flatten-hidden-updated-at') || {}).value || '';
          if (extFq && extFq.updated_at_utc && (!inlineTs || extFq.updated_at_utc > inlineTs)) {
            applyFlatteningQueueObjectToRecords(extFq);
            syncInlineFlatteningFormState(false);
            changed = true;
          }
        }
        if (changed) {
          applyFiltersAndSort();
          renderFlatteningView();
        }
      } catch (e) {}
    }

    function initApp() {
      if (state._initialized) return;
      state._initialized = true;

      // Synchronous href synchronizer for YT Music & Spotify album links:
      // Ensures the <a target="_blank" rel="noopener noreferrer"> tag always carries the latest OLAK5uy_ or Spotify URL
      // and lets the browser's native link navigation open it directly (never opens a blank intermediate popup).
      const handleAlbumExternalClick = (e, platform, anchorEl = null) => {
        const list = state.filteredRecords.length ? state.filteredRecords : state.records;
        const rec = list[state.activeIndex];
        if (!rec) return;
        const sData = state.streamCache[Number(rec.release_id)] || resolveAlbumStreamingData(rec);
        const targetUrl = platform === 'spotify'
          ? getSpotifyAlbumDeepLink(rec)
          : getYouTubeMusicDeepLink(rec, null, sData);
        const el = anchorEl || (e.currentTarget && e.currentTarget.tagName === 'A' ? e.currentTarget : (e.target && e.target.closest ? e.target.closest('a') : null));
        if (el && targetUrl) {
          el.href = targetUrl;
          el.target = '_blank';
          el.rel = 'noopener noreferrer';
        }
      };

      const ytmDirectBtn = document.getElementById('stream-ytm-direct-link');
      if (ytmDirectBtn) {
        ytmDirectBtn.addEventListener('click', (e) => handleAlbumExternalClick(e, 'ytm'));
      }
      const spDirectBtn = document.getElementById('stream-spotify-direct-link');
      if (spDirectBtn) {
        spDirectBtn.addEventListener('click', (e) => handleAlbumExternalClick(e, 'spotify'));
      }
      const trkListEl = document.getElementById('stream-tracklist-list');
      if (trkListEl) {
        trkListEl.addEventListener('click', (e) => {
          const roleEl = e.target.closest('a[data-ytm-role]');
          if (!roleEl) return;
          const role = roleEl.getAttribute('data-ytm-role');
          if (role === 'ytm' || role === 'spotify') {
            handleAlbumExternalClick(e, role, roleEl);
          }
        }, true);
      }

      safeRemoveStorage('krunked_discogs_collection_v2_1');

      // 1. Initialize overrides from injected window.__DISCOGS_OVERRIDES__ + any user browser overrides
      const baseOverrides = (window.__DISCOGS_OVERRIDES__ && typeof window.__DISCOGS_OVERRIDES__ === 'object')
        ? window.__DISCOGS_OVERRIDES__
        : {};
      let localOverrides = {};
      const savedOverrides = safeGetStorage('krunked_pressing_overrides_v2_2');
      if (savedOverrides) {
        try { localOverrides = JSON.parse(savedOverrides) || {}; } catch (e) {}
      }
      state.userOverrides = { ...baseOverrides, ...localOverrides };

      let data = window.__DISCOGS_COLLECTION__;
      if (data && Array.isArray(data.records)) {
        state.records = data.records;
      }

      // 2. Reconcile Flattening Queue from inline HTML form (#flattening-inline-form) + localStorage
      const todoInput = document.getElementById('flatten-hidden-todo-ids');
      const doneInput = document.getElementById('flatten-hidden-done-ids');
      const unlistedInput = document.getElementById('flatten-hidden-unlisted-ids');
      const htmlTsInput = document.getElementById('flatten-hidden-updated-at');

      if (todoInput && doneInput && (todoInput.value || doneInput.value)) {
        applyFlatteningQueueObjectToRecords({
          need_to_be_done_release_ids: todoInput.value.split(',').map(x => Number(x.trim())).filter(Boolean),
          done_release_ids: doneInput.value.split(',').map(x => Number(x.trim())).filter(Boolean),
          unlisted_release_ids: (unlistedInput && unlistedInput.value)
            ? unlistedInput.value.split(',').map(x => Number(x.trim())).filter(Boolean)
            : [],
        });
      }

      const savedFlatten = safeGetStorage('krunked_flattening_state_v4');
      if (savedFlatten) {
        try {
          const parsedFq = JSON.parse(savedFlatten);
          const htmlTs = (htmlTsInput && htmlTsInput.value) ? htmlTsInput.value : '';
          if (parsedFq && (!htmlTs || (parsedFq.updated_at_utc && parsedFq.updated_at_utc > htmlTs))) {
            applyFlatteningQueueObjectToRecords(parsedFq);
            state.unsavedFlattenCount = 1;
          }
        } catch (e) {}
      }

      syncInlineFlatteningFormState(false);
      applyFiltersAndSort();
      renderFlatteningView();
      updateSandboxPreview();
      updateThermalTimerUI();
      state.timerInterval = setInterval(updateThermalTimerUI, 1000);

      loadExternalJsonIfNewer();

      // View Tabs (v5.0 Command Deck Navigation + Variant Clash Arena)
      const setTab = (tab) => {
        state.activeTab = tab;
        document.getElementById('view-showcase').classList.toggle('hidden', tab !== 'showcase');
        const arenaEl = document.getElementById('view-arena');
        if (arenaEl) arenaEl.classList.toggle('hidden', tab !== 'arena');
        document.getElementById('view-pipeline').classList.toggle('hidden', tab !== 'pipeline');
        document.getElementById('view-flattening').classList.toggle('hidden', tab !== 'flattening');

        const tabs = [
          ['showcase', 'tab-btn-showcase'],
          ['arena', 'tab-btn-arena'],
          ['pipeline', 'tab-btn-pipeline'],
          ['flattening', 'tab-btn-flattening'],
        ];
        for (const [tName, btnId] of tabs) {
          const b = document.getElementById(btnId);
          if (!b) continue;
          b.className = (tName === tab)
            ? 'px-3 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap bg-gradient-to-r from-fuchsia-600 to-cyan-600 text-white shadow-md'
            : 'px-3 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap text-slate-300 hover:text-white hover:bg-white/5';
        }
        if (tab === 'arena') {
          renderArenaView();
        }
      };
      window.__setMainVaultTab = setTab;
      setTab(state.activeTab || 'showcase');

      document.getElementById('tab-btn-showcase').addEventListener('click', () => setTab('showcase'));
      const tabArenaBtn = document.getElementById('tab-btn-arena');
      if (tabArenaBtn) tabArenaBtn.addEventListener('click', () => setTab('arena'));
      const heroArenaBtn = document.getElementById('btn-hero-open-arena');
      if (heroArenaBtn) heroArenaBtn.addEventListener('click', () => setTab('arena'));
      document.getElementById('tab-btn-pipeline').addEventListener('click', () => setTab('pipeline'));
      document.getElementById('tab-btn-flattening').addEventListener('click', () => setTab('flattening'));
      const flatCard = document.getElementById('kpi-flattening-card');
      if (flatCard) flatCard.addEventListener('click', () => setTab('flattening'));

      // Thumbnail Mode Buttons (defaulting natively to 'split' — Sleeve + Disc)
      const setThumbMode = (mode) => {
        state.thumbMode = mode;
        const modes = [
          ['pressing', 'mode-btn-pressing'],
          ['split', 'mode-btn-split'],
          ['sleeve', 'mode-btn-sleeve'],
        ];
        for (const [m, id] of modes) {
          const el = document.getElementById(id);
          if (!el) continue;
          el.className = (m === mode)
            ? 'px-2.5 py-1 rounded-lg font-medium bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
            : 'px-2.5 py-1 rounded-lg font-medium text-slate-400 hover:text-white';
        }
        document.getElementById('mobile-mode-select').value = mode;
        renderCrateGrid();
      };

      document.getElementById('mode-btn-pressing').addEventListener('click', () => setThumbMode('pressing'));
      document.getElementById('mode-btn-split').addEventListener('click', () => setThumbMode('split'));
      document.getElementById('mode-btn-sleeve').addEventListener('click', () => setThumbMode('sleeve'));
      document.getElementById('mobile-mode-select').addEventListener('change', (e) => setThumbMode(e.target.value));

      // Carousel & Kinetic Spin-the-Crate Transport (v5.0)
      document.getElementById('btn-carousel-prev').addEventListener('click', () => {
        playCrateTickSound(0.92);
        state.activeIndex--;
        renderHeroStage();
        renderCrateGrid();
      });
      document.getElementById('btn-carousel-next').addEventListener('click', () => {
        playCrateTickSound(1.08);
        state.activeIndex++;
        renderHeroStage();
        renderCrateGrid();
      });
      document.getElementById('stage-prev-card').addEventListener('click', () => {
        playCrateTickSound(0.92);
        state.activeIndex--;
        renderHeroStage();
        renderCrateGrid();
      });
      document.getElementById('stage-next-card').addEventListener('click', () => {
        playCrateTickSound(1.08);
        state.activeIndex++;
        renderHeroStage();
        renderCrateGrid();
      });
      document.getElementById('btn-carousel-random').addEventListener('click', () => {
        triggerKineticCrateSpin();
      });

      // Smart Spin Mode Cards (Full Vault Roulette | Showroom Kiosk | Eye-Candy Variants)
      document.querySelectorAll('.spin-mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const mode = btn.getAttribute('data-spin-mode') || 'all';
          if (mode === 'showroom' && state.spinMode === 'showroom' && state.showroomTickInterval) {
            setSmartSpinMode('all', false);
            showToast('📺 Showroom Kiosk Paused — Returned to Full Vault Roulette.');
            return;
          }
          setSmartSpinMode(mode, true);
        });
      });

      // UV Blacklight & Analog SFX Header Toggles
      const uvBtnEl = document.getElementById('btn-uv-toggle');
      if (uvBtnEl) {
        uvBtnEl.addEventListener('click', () => toggleUvBlacklight());
      }
      const sfxBtnEl = document.getElementById('btn-sfx-toggle');
      if (sfxBtnEl) {
        sfxBtnEl.addEventListener('click', () => {
          state.analogSfx = !state.analogSfx;
          sfxBtnEl.textContent = state.analogSfx ? '🔊 Analog SFX: On' : '🔇 Analog SFX: Off';
          sfxBtnEl.className = state.analogSfx
            ? 'px-2.5 py-1.5 rounded-xl text-xs font-bold border border-cyan-400/40 bg-cyan-500/15 text-cyan-200 hover:bg-cyan-500/25 transition-all'
            : 'px-2.5 py-1.5 rounded-xl text-xs font-bold border border-white/10 bg-slate-900 text-slate-400 hover:text-white transition-all';
          if (state.analogSfx) playCrateTickSound(1.15);
          showToast(state.analogSfx ? '🔊 Web Audio Analog SFX Enabled' : '🔇 Web Audio Analog SFX Muted');
        });
      }

      // Variant Clash Arena Controls
      const newBracketBtn = document.getElementById('btn-arena-new-bracket');
      if (newBracketBtn) {
        newBracketBtn.addEventListener('click', () => {
          playCrateTickSound(1.2);
          initArenaBracket();
          showToast('⚔️ Dealt a fresh 4-LP Variant Clash Bracket!');
        });
      }
      document.querySelectorAll('.arena-pool-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          state.arenaPoolMode = btn.getAttribute('data-arena-pool') || 'all';
          document.querySelectorAll('.arena-pool-btn').forEach(b => {
            const act = b.getAttribute('data-arena-pool') === state.arenaPoolMode;
            b.className = act
              ? 'arena-pool-btn px-2.5 py-1 rounded-lg font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
              : 'arena-pool-btn px-2.5 py-1 rounded-lg font-semibold text-slate-400 hover:text-white';
          });
          playCrateTickSound(1.1);
          initArenaBracket();
        });
      });

      // Initialize Arena Bracket on boot
      initArenaBracket();

      // Quick Flattening Status Cycle on Hero Turntable Stage
      document.getElementById('btn-hero-flatten-cycle').addEventListener('click', () => {
        const list = state.filteredRecords.length ? state.filteredRecords : state.records;
        const rec = list[state.activeIndex];
        if (!rec) return;
        const cur = rec.flattening_status || 'Not Listed';
        const nextStatus = cur === 'Not Listed' ? 'Need to be done' : (cur === 'Need to be done' ? 'Done' : 'Not Listed');
        setRecordFlatteningStatus(rec.release_id, nextStatus);
      });

      // Fetch full gallery button for active release
      document.getElementById('btn-fetch-this-release').addEventListener('click', async () => {
        const list = state.filteredRecords.length ? state.filteredRecords : state.records;
        const rec = list[state.activeIndex];
        if (!rec) return;
        showToast(`Refreshing Discogs image gallery for "${rec.title}"...`);
        try {
          const imgs = await fetchSingleReleaseGallery(rec);
          renderHeroStage();
          renderCrateGrid();
          showToast(`Loaded ${imgs.length} Discogs images for "${rec.title}". Click any image to pin it!`);
        } catch (err) {
          showToast(`Could not fetch gallery: ${err.message}`);
        }
      });

      // Pin / Unpin pressing image from release gallery strip
      document.getElementById('hero-gallery-strip').addEventListener('click', (e) => {
        const pinBtn = e.target.closest('[data-pin-image-url]');
        if (pinBtn) {
          const url = pinBtn.getAttribute('data-pin-image-url');
          const idxAttr = Number(pinBtn.getAttribute('data-pin-image-index') || 0);
          const rid = String(pinBtn.getAttribute('data-pin-release-id'));
          state.userOverrides[rid] = {
            pressing_image_index: idxAttr,
            user_locked: true,
            uri: url,
          };
          const rec = state.records.find(r => String(r.release_id) === rid);
          if (rec && rec.images) {
            rec.images.pressing_image_url = url;
            rec.images.has_pressing_photo = true;
            rec.images.selected_index = idxAttr;
            const matched = (rec.images.classified_images || []).find(im => im.index === idxAttr || im.uri === url || im.local_uri === url);
            if (matched) {
              rec.images.local_pressing_image_url = matched.local_uri || url;
            }
          }
          state.unsavedPinCount++;
          safeSetStorage('krunked_pressing_overrides_v2_2', JSON.stringify(state.userOverrides));
          updateSessionEditIndicators();
          updateKpiStrip();
          renderHeroStage();
          renderCrateGrid();
          showToast(`Pinned image [${idxAttr}] for release #${rid}! Click "Sync & Export LP's" to save inline.`);
          return;
        }
        const clearBtn = e.target.closest('[data-clear-pin]');
        if (clearBtn) {
          const rid = String(clearBtn.getAttribute('data-clear-pin'));
          delete state.userOverrides[rid];
          const rec = state.records.find(r => String(r.release_id) === rid);
          if (rec && rec.images) {
            rec.images.pressing_image_url = '';
            rec.images.local_pressing_image_url = '';
            rec.images.has_pressing_photo = false;
          }
          state.unsavedPinCount++;
          safeSetStorage('krunked_pressing_overrides_v2_2', JSON.stringify(state.userOverrides));
          updateSessionEditIndicators();
          updateKpiStrip();
          renderHeroStage();
          renderCrateGrid();
          showToast(`Switched release #${rid} to procedural Wax Ring.`);
        }
      });

      // Platter Spin / RPM / Stage Mode
      const toggleSpin = () => {
        state.isSpinning = !state.isSpinning;
        document.getElementById('btn-toggle-spin').textContent = state.isSpinning ? '⏸ Pause Platter' : '▶ Spin Platter';
        document.getElementById('turntable-tonearm').className = `tonearm-pivot ${state.isSpinning ? 'tonearm-engaged' : 'tonearm-parked'} absolute top-3.5 right-3.5 w-32 h-64 sm:w-[140px] sm:h-[280px] pointer-events-none z-30`;
        renderHeroStage();
      };
      document.getElementById('btn-toggle-spin').addEventListener('click', toggleSpin);
      document.getElementById('active-platter-disc').addEventListener('click', toggleSpin);

      document.getElementById('btn-toggle-rpm').addEventListener('click', () => {
        state.rpm = state.rpm === 33 ? 45 : 33;
        document.getElementById('btn-toggle-rpm').textContent = state.rpm === 45 ? 'Speed: 45 RPM' : 'Speed: 33⅓ RPM';
        document.getElementById('platter-rpm-readout').textContent = state.rpm === 45 ? '45.0 RPM • QUARTZ LOCK' : '33.3 RPM • QUARTZ LOCK';
        renderHeroStage();
      });

      document.getElementById('btn-toggle-audio').addEventListener('click', toggleVinylAudio);

      const setStageMode = (m) => {
        state.stageMode = m;
        const map = [
          ['auto', 'stage-view-auto'],
          ['sleeve', 'stage-view-sleeve'],
        ];
        for (const [k, id] of map) {
          document.getElementById(id).className = (k === m)
            ? 'px-2.5 py-1 rounded-md font-medium bg-purple-500/25 text-purple-200'
            : 'px-2.5 py-1 rounded-md font-medium text-slate-400 hover:text-white';
        }
        renderHeroStage();
      };
      document.getElementById('stage-view-auto').addEventListener('click', () => setStageMode('auto'));
      document.getElementById('stage-view-sleeve').addEventListener('click', () => setStageMode('sleeve'));

      // Search & Sort
      const searchInput = document.getElementById('search-input');
      const clearBtn = document.getElementById('btn-clear-search');
      searchInput.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        clearBtn.classList.toggle('hidden', !state.searchQuery);
        applyFiltersAndSort();
      });
      clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        state.searchQuery = '';
        clearBtn.classList.add('hidden');
        applyFiltersAndSort();
      });

      document.getElementById('sort-select').addEventListener('change', (e) => {
        state.sortBy = e.target.value;
        applyFiltersAndSort();
      });

      // Filter Chips Delegation
      document.getElementById('filter-chips-bar').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-filter]');
        if (!btn) return;
        state.filter = btn.getAttribute('data-filter');
        document.querySelectorAll('.filter-chip').forEach(chip => {
          const active = chip.getAttribute('data-filter') === state.filter;
          chip.className = active
            ? 'filter-chip shrink-0 px-3 py-1 rounded-full text-xs font-bold bg-gradient-to-r from-fuchsia-600 to-cyan-600 text-white shadow'
            : 'filter-chip shrink-0 px-3 py-1 rounded-full text-xs font-bold bg-slate-950/80 text-slate-300 hover:text-white border border-white/10';
        });
        applyFiltersAndSort();
      });

      // Card Click Delegation
      document.getElementById('collection-grid').addEventListener('click', (e) => {
        if (e.target.closest('[data-stop-prop]')) return;
        const card = e.target.closest('[data-card-index]');
        if (!card) return;
        state.activeIndex = Number(card.getAttribute('data-card-index') || 0);
        renderHeroStage();
        renderCrateGrid();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });

      // Pipeline Tab Copy Command Buttons
      document.getElementById('view-pipeline').addEventListener('click', (e) => {
        const copyBtn = e.target.closest('[data-copy-cmd]');
        if (!copyBtn) return;
        const cmd = copyBtn.getAttribute('data-copy-cmd');
        if (navigator.clipboard && cmd) {
          navigator.clipboard.writeText(cmd).then(() => showToast('Copied PowerShell command to clipboard!'));
        }
      });

      // Flattening Queue Tab Delegation (Status Toggle, Turntable Jump, Search, Timer)
      document.getElementById('view-flattening').addEventListener('click', (e) => {
        const setBtn = e.target.closest('[data-set-flatten]');
        if (setBtn) {
          const rid = Number(setBtn.getAttribute('data-set-flatten'));
          const targetStatus = setBtn.getAttribute('data-target-status') || 'Done';
          setRecordFlatteningStatus(rid, targetStatus);
          return;
        }
        const jumpEl = e.target.closest('[data-load-turntable]');
        if (jumpEl) {
          const rid = Number(jumpEl.getAttribute('data-load-turntable'));
          const idxInFiltered = state.filteredRecords.findIndex(r => Number(r.release_id) === rid);
          if (idxInFiltered !== -1) {
            state.activeIndex = idxInFiltered;
          } else {
            state.filter = 'all';
            state.searchQuery = '';
            document.getElementById('search-input').value = '';
            applyFiltersAndSort();
            const newIdx = state.filteredRecords.findIndex(r => Number(r.release_id) === rid);
            if (newIdx !== -1) state.activeIndex = newIdx;
          }
          setTab('showcase');
          renderHeroStage();
          renderCrateGrid();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      });

      document.getElementById('flatten-done-search').addEventListener('input', (e) => {
        state.doneSearchQuery = e.target.value;
        renderFlatteningView();
      });

      document.getElementById('flatten-bench-search').addEventListener('input', (e) => {
        state.benchSearchQuery = e.target.value;
        renderFlatteningView();
      });

      document.getElementById('btn-flatten-save-html').addEventListener('click', downloadSelfContainedIndexHtml);

      const exportFlatteningJson = () => {
        const fqObj = syncInlineFlatteningFormState(false);
        const blob = new Blob([JSON.stringify(fqObj, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'flattening_queue.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Downloaded flattening_queue.json (drop into data/flattening_queue.json)');
      };
      document.getElementById('btn-flatten-export-json').addEventListener('click', exportFlatteningJson);

      // Thermal Timer Controls
      document.getElementById('btn-timer-ramp').addEventListener('click', () => {
        safeSetStorage('krunked_flattening_timer_v4', JSON.stringify({
          mode: 'ramp',
          startedAt: Date.now(),
          recordId: document.getElementById('timer-record-select').value || '',
        }));
        updateThermalTimerUI();
        showToast('🔥 Stage 1 Ramp started (Bag on Setting 6 until 130°F).');
      });

      document.getElementById('btn-timer-start').addEventListener('click', () => {
        safeSetStorage('krunked_flattening_timer_v4', JSON.stringify({
          mode: 'hold',
          startedAt: Date.now(),
          endsAt: Date.now() + HOLD_DURATION_MS,
          notified: false,
          recordId: document.getElementById('timer-record-select').value || '',
        }));
        updateThermalTimerUI();
        showToast('⏱ Started 2.5-Hour (150:00) Hold Timer on Setting 4!');
      });

      document.getElementById('btn-timer-reset').addEventListener('click', () => {
        safeRemoveStorage('krunked_flattening_timer_v4');
        updateThermalTimerUI();
        showToast('Reset thermal plate timer.');
      });

      // Sandbox Inputs
      document.getElementById('sandbox-format-input').addEventListener('input', updateSandboxPreview);
      document.getElementById('sandbox-notes-input').addEventListener('input', updateSandboxPreview);
      document.getElementById('btn-sandbox-preset').addEventListener('click', () => {
        const presets = [
          ['LP, Album, Ltd, Cle', 'Sealed Clear w/ Yellow and Purple Splatter'],
          ['2xLP, Album, Ltd, Ruby With Black Splatter', '3 Dot Recordings Exclusive'],
          ['LP, Ltd, Mil', '2022 RED IN CLEAR VERSION, AUTOGRAPHED ON FRONT COVER'],
          ['LP, Ltd, Neo + LP, S/Sided, Etch, Ltd, Neo', 'Banquet Neon Highlighter Etched 2xLP'],
        ];
        const pick = presets[Math.floor(Math.random() * presets.length)];
        document.getElementById('sandbox-format-input').value = pick[0];
        document.getElementById('sandbox-notes-input').value = pick[1];
        updateSandboxPreview();
      });

      // Modal Open / Close / Exports
      const modal = document.getElementById('modal-backdrop');
      document.getElementById('btn-live-sync-modal').addEventListener('click', () => {
        updateSessionEditIndicators();
        modal.classList.remove('hidden');
      });
      // v5.0 3D Flip Deck & Embedded YouTube Music Audio Player Event Listeners
      ensureYouTubeIframeApiLoaded();

      const audioEl = document.getElementById('vault-preview-audio');
      if (audioEl) {
        audioEl.addEventListener('timeupdate', () => {
          if (state.activePlaybackEngine !== 'html5') return;
          const curSec = Number(audioEl.currentTime || 0);
          const totSec = Number(audioEl.duration || 0);
          if (totSec > 0) {
            const pct = Math.min(100, Math.round((curSec / totSec) * 100));
            const seekSlider = document.getElementById('stream-seek-slider');
            if (seekSlider) seekSlider.value = String(pct);
            const timeReadout = document.getElementById('stream-time-readout');
            if (timeReadout) {
              timeReadout.textContent = `${formatMillisToDuration(curSec * 1000) || '0:00'} / ${formatMillisToDuration(totSec * 1000) || '3:45'}`;
            }
          }
        });
        audioEl.addEventListener('ended', () => {
          if (state.activePlaybackEngine !== 'html5') return;
          const list = state.filteredRecords.length ? state.filteredRecords : state.records;
          const curRec = list[state.activeIndex];
          const curRid = curRec ? Number(curRec.release_id) : state.activeStreamRid;
          const sData = state.streamCache[curRid] || (curRec ? resolveAlbumStreamingData(curRec) : null);
          const trList = (sData && Array.isArray(sData.tracks)) ? sData.tracks : [];
          if (curRec && state.autoAdvanceTracks && state.activeTrackIndex + 1 < trList.length) {
            playAlbumTrackAtIndex(curRec, state.activeTrackIndex + 1);
          } else {
            stopPreviewAudio();
            if (curRec && sData) paintStreamingTracklistUI(curRec, sData, false);
          }
        });
      }

      document.getElementById('btn-flip-streaming').addEventListener('click', () => toggleHeroCardFlip());
      document.getElementById('btn-card-flip-top').addEventListener('click', () => toggleHeroCardFlip());

      window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal && !modal.classList.contains('hidden')) {
          e.preventDefault();
          modal.classList.add('hidden');
          return;
        }
        const activeEl = document.activeElement;
        const tag = (activeEl && activeEl.tagName) ? activeEl.tagName.toLowerCase() : '';
        if (tag === 'input' || tag === 'textarea' || tag === 'select' || (activeEl && activeEl.isContentEditable)) return;
        if (modal && !modal.classList.contains('hidden')) return;
        if (e.ctrlKey || e.metaKey || e.altKey) return;

        if (e.code === 'Space' && state.activeTab === 'showcase') {
          e.preventDefault();
          triggerKineticCrateSpin();
        } else if (e.key === 'ArrowLeft' && state.activeTab === 'showcase') {
          e.preventDefault();
          playCrateTickSound(0.92);
          state.activeIndex--;
          renderHeroStage();
          renderCrateGrid();
        } else if (e.key === 'ArrowRight' && state.activeTab === 'showcase') {
          e.preventDefault();
          playCrateTickSound(1.08);
          state.activeIndex++;
          renderHeroStage();
          renderCrateGrid();
        } else if (e.key === '/') {
          e.preventDefault();
          if (state.activeTab !== 'showcase') setTab('showcase');
          const searchEl = document.getElementById('search-input');
          if (searchEl) {
            searchEl.focus();
            searchEl.select();
          }
        } else if (e.key && e.key.toLowerCase() === 'f') {
          e.preventDefault();
          toggleHeroCardFlip();
        } else if (e.key && e.key.toLowerCase() === 'u') {
          e.preventDefault();
          toggleUvBlacklight();
        }
      });

      const backFaceEl = document.getElementById('hero-face-back');
      if (backFaceEl) {
        backFaceEl.addEventListener('click', (e) => {
          e.stopPropagation();
        });
      }

      document.getElementById('stream-artist-link').addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const list = state.filteredRecords.length ? state.filteredRecords : state.records;
        const rec = list[state.activeIndex];
        if (!rec) return;
        playAlbumTrackAtIndex(rec, 0);
      });

      document.getElementById('btn-stream-play').addEventListener('click', (e) => {
        e.stopPropagation();
        toggleInPagePlayPause();
      });
      const coverBtn = document.getElementById('stream-cover-btn');
      if (coverBtn) {
        coverBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          toggleInPagePlayPause();
        });
      }

      const restartBtn = document.getElementById('btn-stream-restart');
      if (restartBtn) {
        restartBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const list = state.filteredRecords.length ? state.filteredRecords : state.records;
          const rec = list[state.activeIndex];
          if (!rec) return;
          const curIdx = state.activeStreamRid === Number(rec.release_id) && state.activeTrackIndex >= 0 ? state.activeTrackIndex : 0;
          playAlbumTrackAtIndex(rec, curIdx);
        });
      }

      const muteBtn = document.getElementById('btn-stream-mute');
      if (muteBtn) {
        muteBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          state.isAudioMuted = !state.isAudioMuted;
          muteBtn.textContent = state.isAudioMuted ? '🔇' : '🔊';
          if (state.ytPlayer && state.ytPlayerReady) {
            try {
              if (state.isAudioMuted) state.ytPlayer.mute();
              else state.ytPlayer.unMute();
            } catch (err) {}
          }
          if (audioEl) {
            audioEl.muted = Boolean(state.isAudioMuted);
          }
          showToast(state.isAudioMuted ? 'Muted Album Player' : 'Unmuted Album Player');
        });
      }

      document.getElementById('btn-stream-prev').addEventListener('click', (e) => {
        e.stopPropagation();
        const list = state.filteredRecords.length ? state.filteredRecords : state.records;
        const rec = list[state.activeIndex];
        if (!rec) return;
        const curIdx = state.activeStreamRid === Number(rec.release_id) && state.activeTrackIndex >= 0 ? state.activeTrackIndex : 0;
        playAlbumTrackAtIndex(rec, Math.max(0, curIdx - 1));
      });

      document.getElementById('btn-stream-next').addEventListener('click', (e) => {
        e.stopPropagation();
        const list = state.filteredRecords.length ? state.filteredRecords : state.records;
        const rec = list[state.activeIndex];
        if (!rec) return;
        const curIdx = state.activeStreamRid === Number(rec.release_id) ? state.activeTrackIndex : -1;
        playAlbumTrackAtIndex(rec, curIdx + 1);
      });

      document.getElementById('btn-stream-popout').addEventListener('click', (e) => {
        e.stopPropagation();
        state.autoAdvanceTracks = !state.autoAdvanceTracks;
        const btn = document.getElementById('btn-stream-popout');
        if (btn) {
          btn.className = state.autoAdvanceTracks
            ? 'w-7 h-7 rounded-full bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 text-cyan-300 flex items-center justify-center text-[11px] transition'
            : 'w-7 h-7 rounded-full bg-white/5 hover:bg-white/15 border border-white/10 text-slate-400 flex items-center justify-center text-[11px] transition';
          btn.title = `Continuous Full-Album Auto-Advance (Currently: ${state.autoAdvanceTracks ? 'ON' : 'OFF'})`;
        }
        showToast(`Continuous Full-Album Auto-Advance: ${state.autoAdvanceTracks ? 'ON' : 'OFF'}`);
      });

      document.getElementById('stream-tracklist-list').addEventListener('click', (e) => {
        if (e.target.closest('[data-ytm-ext]')) {
          e.stopPropagation();
          return;
        }
        e.stopPropagation();
        const row = e.target.closest('[data-track-idx]');
        if (!row) return;
        const idx = Number(row.getAttribute('data-track-idx') || 0);
        const list = state.filteredRecords.length ? state.filteredRecords : state.records;
        const rec = list[state.activeIndex];
        if (!rec) return;
        if (state.activeStreamRid === Number(rec.release_id) && state.activeTrackIndex === idx && state.isPreviewPlaying) {
          stopPreviewAudio();
          updateStreamTransportUI(rec);
          const streamData = state.streamCache[Number(rec.release_id)] || resolveAlbumStreamingData(rec);
          if (streamData) paintStreamingTracklistUI(rec, streamData, false);
        } else {
          playAlbumTrackAtIndex(rec, idx);
        }
      });

      const seekSlider = document.getElementById('stream-seek-slider');
      if (seekSlider) {
        seekSlider.addEventListener('input', (e) => {
          const pct = Number(e.target.value || 0);
          state.lastTrackSwitchAt = Date.now();
          if (state.activePlaybackEngine === 'html5' && audioEl && audioEl.duration > 0) {
            audioEl.currentTime = (pct / 100) * audioEl.duration;
            return;
          }
          if (state.ytPlayer && state.ytPlayerReady) {
            try {
              const totalDur = Number(state.ytPlayer.getDuration() || 0);
              const list = state.filteredRecords.length ? state.filteredRecords : state.records;
              const rec = list[state.activeIndex];
              const rid = rec ? Number(rec.release_id) : state.activeStreamRid;
              const sData = state.streamCache[rid] || (rec ? resolveAlbumStreamingData(rec) : null);
              const trList = (sData && Array.isArray(sData.tracks)) ? sData.tracks : [];
              const curTr = trList[state.activeTrackIndex];

              if (state.ytIsFullAlbumStream && !state.ytIsPlaylistMode && curTr && totalDur >= 1080) {
                const trStart = Number(curTr.albumYtStart || 0);
                const trDur = parseDurationToSeconds(curTr.duration);
                state.ytPlayer.seekTo(trStart + (pct / 100) * trDur, true);
              } else if (totalDur > 0) {
                state.ytPlayer.seekTo((pct / 100) * totalDur, true);
              }
            } catch (err) {}
          }
        });
      }
      document.getElementById('btn-close-modal').addEventListener('click', () => modal.classList.add('hidden'));

      document.getElementById('btn-bake-full-html').addEventListener('click', downloadSelfContainedIndexHtml);
      document.getElementById('btn-export-flattening').addEventListener('click', exportFlatteningJson);

      document.getElementById('btn-reset-browser-cache').addEventListener('click', () => {
        safeRemoveStorage('krunked_pressing_overrides_v2_2');
        safeRemoveStorage('krunked_flattening_state_v4');
        state.unsavedPinCount = 0;
        state.unsavedFlattenCount = 0;
        window.location.reload();
      });

      document.getElementById('btn-export-json').addEventListener('click', () => {
        syncInlineFlatteningFormState(false);
        const blob = new Blob([JSON.stringify(window.__DISCOGS_COLLECTION__, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'collection.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Downloaded collection.json');
      });

      document.getElementById('btn-export-overrides').addEventListener('click', () => {
        const blob = new Blob([JSON.stringify(state.userOverrides, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'overrides.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Downloaded overrides.json');
      });

      document.getElementById('btn-copy-sync-cmd').addEventListener('click', () => {
        const cmd = 'cd C:\\DiscogsCollection\\discogs_collection\npython scripts/sync_discogs.py';
        if (navigator.clipboard) {
          navigator.clipboard.writeText(cmd).then(() => showToast('Copied daily sync command to clipboard!'));
        }
      });

      document.getElementById('btn-copy-resync-active').addEventListener('click', () => {
        const list = state.filteredRecords.length ? state.filteredRecords : state.records;
        const rec = list[state.activeIndex];
        const rid = rec ? rec.release_id : '';
        const cmd = `cd C:\\DiscogsCollection\\discogs_collection\npython scripts/sync_discogs.py --resync ${rid}`;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(cmd).then(() => showToast(`Copied --resync ${rid} command to clipboard!`));
        }
      });
    }

    window.addEventListener('DOMContentLoaded', initApp);
