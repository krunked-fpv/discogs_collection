// KRUNKED // VINYL VAULT v6.0 — Session Indicators, Portable HTML Baker, JSON Exporters & Direct GitHub Commit

import {
  STORAGE_KEYS,
  buildFlatteningQueueObject,
  store,
  subscribe,
  syncInlineFlatteningFormState,
} from './store.js';
import {
  DEFAULT_FLATTENING_STATUS,
  getVerifiedPressingPhotoUrl,
  safeGetStorage,
  safeJsonForScript,
  safeRemoveStorage,
  safeSetStorage,
  showToast,
} from './utils.js';

export function updateSessionEditIndicators() {
  const totalEdits = store.unsavedPinCount + store.unsavedFlattenCount;
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
    if (store.unsavedFlattenCount > 0) {
      inlineBadge.textContent = `● ${store.unsavedFlattenCount} Queue Edit${store.unsavedFlattenCount === 1 ? '' : 's'} — Export or Commit`;
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
      modalEditsSub.textContent = `${store.unsavedPinCount} Pin(s) • ${store.unsavedFlattenCount} Queue`;
    } else {
      modalEdits.textContent = '0 Unsaved';
      modalEdits.className = 'text-sm sm:text-base font-extrabold text-emerald-400 mt-0.5';
      modalEditsSub.textContent = 'In Sync with HTML';
    }
  }
}

export function downloadSelfContainedIndexHtml() {
  const fqObj = syncInlineFlatteningFormState(false);
  const nowStamp = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  fqObj.updated_at_utc = nowStamp;

  if (window.__DISCOGS_COLLECTION__) {
    window.__DISCOGS_COLLECTION__.synced_at_utc = nowStamp;
    window.__DISCOGS_COLLECTION__.schema_version = '5.0.0';
    window.__DISCOGS_COLLECTION__.records = store.records;
    window.__DISCOGS_COLLECTION__.flattening_queue = fqObj;
    if (window.__DISCOGS_COLLECTION__.profile) {
      window.__DISCOGS_COLLECTION__.profile.num_collection = store.records.length;
      window.__DISCOGS_COLLECTION__.profile.pressing_photos_detected = store.records.filter((r) =>
        Boolean(getVerifiedPressingPhotoUrl(r, store.userOverrides))
      ).length;
      window.__DISCOGS_COLLECTION__.profile.flattening_need_to_be_done = fqObj.need_to_be_done_release_ids.length;
      window.__DISCOGS_COLLECTION__.profile.flattening_done = fqObj.done_release_ids.length;
    }
  }

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

  store.unsavedPinCount = 0;
  store.unsavedFlattenCount = 0;
  updateSessionEditIndicators();

  const docClone = document.documentElement.cloneNode(true);

  docClone.querySelectorAll('style, meta').forEach((node) => {
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

  const sanitizeNodeAttrs = (el) => {
    if (!el || !el.attributes) return;
    const toRemove = [];
    for (let i = 0; i < el.attributes.length; i++) {
      const name = el.attributes[i].name;
      if (/^data-(lastpass|darkreader)/i.test(name)) toRemove.push(name);
    }
    toRemove.forEach((n) => el.removeAttribute(n));
    if (el.hasAttribute('style')) {
      const cleaned = el
        .getAttribute('style')
        .split(';')
        .map((s) => s.trim())
        .filter((s) => s && !/^--darkreader-/i.test(s))
        .join('; ');
      if (cleaned) el.setAttribute('style', `${cleaned};`);
      else el.removeAttribute('style');
    }
  };
  sanitizeNodeAttrs(docClone);
  docClone.querySelectorAll('*').forEach(sanitizeNodeAttrs);

  const syncBtnClone = docClone.querySelector('#btn-live-sync-modal');
  if (syncBtnClone && syncBtnClone.getAttribute('data-cookie-vault')) {
    syncBtnClone.removeAttribute('data-cookie-vault');
    const t = (syncBtnClone.getAttribute('title') || '').replace(
      /\s*•?\s*Shadow-Cookie Auto-Healer Active \(400-Day Backup\)\s*$/,
      ''
    );
    if (t) syncBtnClone.setAttribute('title', t);
  }

  const fxCanvasClone = docClone.querySelector('#fx-particles-canvas');
  if (fxCanvasClone) {
    fxCanvasClone.removeAttribute('width');
    fxCanvasClone.removeAttribute('height');
  }

  [
    'collection-grid',
    'bin-3d-trough',
    'flatten-todo-list',
    'flatten-done-list',
    'flatten-bench-list',
    'cmd-palette-results',
  ].forEach((id) => {
    const el = docClone.querySelector(`#${id}`);
    if (el) el.innerHTML = '';
  });
  ['search-input', 'flatten-done-search', 'flatten-bench-search', 'github-pat-input'].forEach((id) => {
    const el = docClone.querySelector(`#${id}`);
    if (el) el.removeAttribute('value');
  });

  ['modal-backdrop', 'jacket-inspector-modal', 'cmd-palette-modal'].forEach((id) => {
    docClone.querySelector(`#${id}`)?.classList.add('hidden');
  });
  const toastClone = docClone.querySelector('#toast-banner');
  if (toastClone) {
    toastClone.classList.add('hidden');
    toastClone.textContent = '';
  }

  ['view-showcase', 'view-arena', 'view-analytics', 'view-pipeline', 'view-flattening'].forEach((vid) => {
    const v = docClone.querySelector(`#${vid}`);
    if (v) v.classList.toggle('hidden', vid !== 'view-showcase');
  });

  let rawDoc = '<!DOCTYPE html>\n' + docClone.outerHTML;
  const overridesJs = safeJsonForScript(store.userOverrides, 2);
  const collectionJs = safeJsonForScript(window.__DISCOGS_COLLECTION__, 2);
  const syncStampJs = safeJsonForScript(nowStamp, null);
  const replacementBlock = [
    '/* __DISCOGS_COLLECTION_DATA_' + 'START__ */',
    `    window.__DISCOGS_OVERRIDES__ = ${overridesJs};`,
    `    window.__DISCOGS_COLLECTION__ = ${collectionJs};`,
    '    try {',
    `      var __pySyncStamp = ${syncStampJs};`,
    "      if (typeof localStorage !== 'undefined' && localStorage.getItem('__discogs_py_sync_stamp__') !== __pySyncStamp) {",
    "        var __vaultStaleKeys = ['krunked_discogs_collection_v2_1', 'krunked_pressing_overrides_v2_2'];",
    '        for (var __i = 0; __i < __vaultStaleKeys.length; __i++) {',
    '          localStorage.removeItem(__vaultStaleKeys[__i]);',
    '        }',
    "        var __savedFqRaw = localStorage.getItem('krunked_flattening_state_v4');",
    '        if (__savedFqRaw) {',
    '          var __shouldDropFq = true;',
    '          try {',
    '            var __savedFq = JSON.parse(__savedFqRaw);',
    '            if (__savedFq && __savedFq.updated_at_utc && __pySyncStamp && __savedFq.updated_at_utc > __pySyncStamp) {',
    '              __shouldDropFq = false;',
    '            }',
    '          } catch (e2) {}',
    '          if (__shouldDropFq) {',
    "            localStorage.removeItem('krunked_flattening_state_v4');",
    '          }',
    '        }',
    "        localStorage.setItem('__discogs_py_sync_stamp__', __pySyncStamp);",
    '      }',
    '    } catch (e) {}',
    '    /* __DISCOGS_COLLECTION_DATA_' + 'END__ */',
  ].join('\n');

  rawDoc = rawDoc.replace(
    new RegExp(
      '\\/\\*\\s*__DISCOGS_COLLECTION_DATA_' +
        'START__\\s*\\*\\/[\\s\\S]*?\\/\\*\\s*__DISCOGS_COLLECTION_DATA_' +
        'END__\\s*\\*\\/'
    ),
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

// =========================================================================
// Direct Browser-to-GitHub Contents API Commit (Optional User-Supplied PAT)
// =========================================================================
function utf8ToBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (let i = 0; i < bytes.length; i++) {
    bin += String.fromCharCode(bytes[i]);
  }
  return btoa(bin);
}

async function commitFileToGitHub({ repo, branch, path, contentJson, message, token }) {
  const apiUrl = `https://api.github.com/repos/${repo}/contents/${path}`;
  const headers = {
    Accept: 'application/vnd.github+json',
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  let existingSha = undefined;
  const getResp = await fetch(`${apiUrl}?ref=${encodeURIComponent(branch)}`, { headers });
  if (getResp.ok) {
    const meta = await getResp.json();
    existingSha = meta.sha;
  } else if (getResp.status !== 404) {
    const errText = await getResp.text();
    throw new Error(`GitHub GET ${path} failed (${getResp.status}): ${errText.slice(0, 120)}`);
  }

  const putResp = await fetch(apiUrl, {
    method: 'PUT',
    headers,
    body: JSON.stringify({
      message,
      content: utf8ToBase64(contentJson),
      branch,
      ...(existingSha ? { sha: existingSha } : {}),
    }),
  });
  if (!putResp.ok) {
    const errText = await putResp.text();
    throw new Error(`GitHub PUT ${path} failed (${putResp.status}): ${errText.slice(0, 140)}`);
  }
  return putResp.json();
}

export function initPersistenceHub() {
  const modal = document.getElementById('modal-backdrop');
  const ghPatInput = document.getElementById('github-pat-input');
  const ghRepoInput = document.getElementById('github-repo-input');
  const ghStatusEl = document.getElementById('github-commit-status');

  // Load optional runtime PAT strictly from non-cookie-tracked localStorage key
  if (ghPatInput) {
    ghPatInput.value = safeGetStorage(STORAGE_KEYS.GH_PAT) || '';
    ghPatInput.addEventListener('input', () => {
      const val = ghPatInput.value.trim();
      if (val) safeSetStorage(STORAGE_KEYS.GH_PAT, val);
      else safeRemoveStorage(STORAGE_KEYS.GH_PAT);
    });
  }

  document.getElementById('btn-clear-gh-pat')?.addEventListener('click', () => {
    safeRemoveStorage(STORAGE_KEYS.GH_PAT);
    if (ghPatInput) ghPatInput.value = '';
    if (ghStatusEl) ghStatusEl.textContent = 'Cleared GitHub PAT from localStorage.';
    showToast('Cleared GitHub PAT from localStorage.');
  });

  document.getElementById('btn-gh-commit-data')?.addEventListener('click', async () => {
    const token = (ghPatInput?.value || safeGetStorage(STORAGE_KEYS.GH_PAT) || '').trim();
    const repo = (ghRepoInput?.value || 'krunked-fpv/discogs_collection').trim();
    if (!token) {
      if (ghStatusEl) ghStatusEl.textContent = '⚠ Enter a GitHub Fine-Grained PAT with Contents: Read & Write permission.';
      return;
    }
    safeSetStorage(STORAGE_KEYS.GH_PAT, token);
    if (ghStatusEl) ghStatusEl.textContent = '⏳ Committing data/flattening_queue.json & data/overrides.json to GitHub...';

    try {
      const fqObj = buildFlatteningQueueObject();
      const sortedOverrides = {};
      Object.keys(store.userOverrides)
        .sort((a, b) => (/^\d+$/.test(a) && /^\d+$/.test(b) ? Number(a) - Number(b) : a.localeCompare(b)))
        .forEach((k) => {
          sortedOverrides[k] = store.userOverrides[k];
        });

      await commitFileToGitHub({
        repo,
        branch: 'main',
        path: 'data/flattening_queue.json',
        contentJson: JSON.stringify(fqObj, null, 2) + '\n',
        message: 'chore(vault): update flattening_queue.json from browser mission control',
        token,
      });
      await commitFileToGitHub({
        repo,
        branch: 'main',
        path: 'data/overrides.json',
        contentJson: JSON.stringify(sortedOverrides, null, 2) + '\n',
        message: 'chore(vault): update overrides.json pressing pins from browser',
        token,
      });

      store.unsavedPinCount = 0;
      store.unsavedFlattenCount = 0;
      updateSessionEditIndicators();
      if (ghStatusEl) ghStatusEl.textContent = '✓ Committed data/flattening_queue.json & data/overrides.json to main!';
      showToast('🚀 Committed flattening_queue.json & overrides.json directly to GitHub!');
    } catch (err) {
      if (ghStatusEl) ghStatusEl.textContent = `✕ ${err.message}`;
      showToast(`GitHub commit failed: ${err.message}`);
    }
  });

  document.getElementById('btn-live-sync-modal')?.addEventListener('click', () => {
    updateSessionEditIndicators();
    modal?.classList.remove('hidden');
  });
  document.getElementById('btn-close-modal')?.addEventListener('click', () => modal?.classList.add('hidden'));
  modal?.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.add('hidden');
  });

  document.getElementById('btn-bake-full-html')?.addEventListener('click', downloadSelfContainedIndexHtml);
  document.getElementById('btn-flatten-save-html')?.addEventListener('click', downloadSelfContainedIndexHtml);

  document.getElementById('btn-reset-browser-cache')?.addEventListener('click', () => {
    safeRemoveStorage(STORAGE_KEYS.OVERRIDES);
    safeRemoveStorage(STORAGE_KEYS.FLATTEN_QUEUE);
    store.localOverrideEdits = {};
    store.unsavedPinCount = 0;
    store.unsavedFlattenCount = 0;
    window.location.reload();
  });

  const downloadJson = (obj, filename) => {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Downloaded ${filename}`);
  };

  document.getElementById('btn-export-flattening')?.addEventListener('click', () => {
    downloadJson(buildFlatteningQueueObject(), 'flattening_queue.json');
  });
  document.getElementById('btn-export-overrides')?.addEventListener('click', () => {
    downloadJson(store.userOverrides, 'overrides.json');
  });
  document.getElementById('btn-export-json')?.addEventListener('click', () => {
    syncInlineFlatteningFormState(false);
    downloadJson(window.__DISCOGS_COLLECTION__, 'collection.json');
  });

  subscribe((topic) => {
    if (topic === 'sessionEditsChanged') {
      updateSessionEditIndicators();
    }
  });

  updateSessionEditIndicators();
}
