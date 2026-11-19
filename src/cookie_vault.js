(function () {
  "use strict";
  if (window.__KRUNKED_COOKIE_VAULT__) return;

  var COOKIE_PREFIX = "kv1_";
  var PULSE_COOKIE = "krunked_family_pulse";
  var MAX_AGE_SEC = 34560000; // 400 days (RFC 6265 browser cap)
  var CHUNK_SIZE = 3200;      // Safe margin under 4096-byte per-cookie limit
  var MAX_CHUNKS_PER_KEY = 4; // Up to ~12.8 KB compacted JSON per state key

  // Match state keys across Violet's Homework, Ozias's Lab, Discogs Vault & future apps
  var TRACKED_KEY_PATTERNS = [
    /violet/i,
    /quest/i,
    /ozias/i,
    /pokemath/i,
    /krunked/i,
    /discogs/i,
    /vault/i,
    /flatten/i,
    /override/i,
    /thumbmode/i,
    /uvblacklight/i,
    /spinmode/i,
    /arena/i,
    /sync/i,
    /state/i,
    /progress/i
  ];

  // Never mirror massive read-only Discogs API release caches into cookies
  var IGNORED_KEY_PATTERNS = [
    /releases_cache/i,
    /full_collection_cache/i,
    /^debug/i
  ];

  function shouldTrackKey(key) {
    if (!key || typeof key !== "string") return false;
    for (var i = 0; i < IGNORED_KEY_PATTERNS.length; i++) {
      if (IGNORED_KEY_PATTERNS[i].test(key)) return false;
    }
    for (var j = 0; j < TRACKED_KEY_PATTERNS.length; j++) {
      if (TRACKED_KEY_PATTERNS[j].test(key)) return true;
    }
    return false;
  }

  function getAppScopePath() {
    try {
      var p = window.location.pathname || "/";
      if (p.endsWith(".html")) {
        p = p.substring(0, p.lastIndexOf("/") + 1);
      }
      return p || "/";
    } catch (e) {
      return "/";
    }
  }

  function sanitizeSlug(key) {
    return String(key).replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 40);
  }

  function readAllCookies() {
    var map = {};
    try {
      var raw = document.cookie || "";
      if (!raw) return map;
      var parts = raw.split(";");
      for (var i = 0; i < parts.length; i++) {
        var seg = parts[i].trim();
        if (!seg) continue;
        var eq = seg.indexOf("=");
        if (eq < 0) continue;
        var k = seg.substring(0, eq).trim();
        var v = seg.substring(eq + 1).trim();
        map[k] = v;
      }
    } catch (e) {}
    return map;
  }

  function writeRawCookie(name, value, path, maxAge) {
    try {
      if (window.location.protocol === "file:") return false;
      var p = path || getAppScopePath();
      var age = typeof maxAge === "number" ? maxAge : MAX_AGE_SEC;
      var secureFlag = window.location.protocol === "https:" ? "; Secure" : "";
      document.cookie =
        name + "=" + value +
        "; Max-Age=" + age +
        "; Path=" + p +
        "; SameSite=Lax" +
        secureFlag;
      return true;
    } catch (e) {
      return false;
    }
  }

  function deleteCookieChunks(slug) {
    var all = readAllCookies();
    var prefix = COOKIE_PREFIX + slug + "__";
    var appPath = getAppScopePath();
    for (var k in all) {
      if (Object.prototype.hasOwnProperty.call(all, k) && k.indexOf(prefix) === 0) {
        writeRawCookie(k, "", appPath, 0);
        writeRawCookie(k, "", "/", 0);
      }
    }
  }

  function clearAllAppShadowCookies() {
    var all = readAllCookies();
    var appPath = getAppScopePath();
    for (var k in all) {
      if (Object.prototype.hasOwnProperty.call(all, k) && k.indexOf(COOKIE_PREFIX) === 0) {
        writeRawCookie(k, "", appPath, 0);
        writeRawCookie(k, "", "/", 0);
      }
    }
  }

  // Strip oversized base64 canvas images or huge record arrays so cookies stay lean
  function compactValueForCookie(key, rawValue) {
    if (typeof rawValue !== "string") return "";
    if (rawValue.length <= 2800) return rawValue;

    try {
      var parsed = JSON.parse(rawValue);
      if (!parsed || typeof parsed !== "object") {
        return rawValue.length <= CHUNK_SIZE * MAX_CHUNKS_PER_KEY ? rawValue : "";
      }

      // Skip full Discogs 157-LP collection array if accidentally written to localStorage
      if (Array.isArray(parsed.records) && parsed.records.length > 25) {
        return "";
      }

      var clone = Array.isArray(parsed) ? parsed.slice() : Object.assign({}, parsed);
      var heavyKeys = [
        "drawingDataUrl",
        "canvasDataUrl",
        "scratchpadDataUrl",
        "scratchpadImage",
        "comicDataUrl",
        "audioBlob",
        "rawReleases",
        "releases",
        "need_to_be_done_entries",
        "done_entries"
      ];
      for (var i = 0; i < heavyKeys.length; i++) {
        if (heavyKeys[i] in clone) {
          delete clone[heavyKeys[i]];
        }
      }

      // Recursively strip any nested data:image/ base64 strings
      var strippedJson = JSON.stringify(clone, function (k, v) {
        if (typeof v === "string" && v.indexOf("data:image/") === 0) {
          return undefined;
        }
        if (typeof v === "string" && v.length > 2000) {
          return v.slice(0, 2000);
        }
        return v;
      });

      return strippedJson;
    } catch (e) {
      return rawValue.length <= CHUNK_SIZE * MAX_CHUNKS_PER_KEY ? rawValue : "";
    }
  }

  function mirrorKeyToCookie(key, rawValue) {
    try {
      if (!shouldTrackKey(key)) return false;
      var compacted = compactValueForCookie(key, String(rawValue));
      if (!compacted) return false;

      var envelope = JSON.stringify({
        k: key,
        t: Date.now(),
        d: compacted
      });
      var encoded = encodeURIComponent(envelope);
      var totalLen = encoded.length;
      var numChunks = Math.ceil(totalLen / CHUNK_SIZE);

      if (numChunks > MAX_CHUNKS_PER_KEY) {
        return false; // Safely skip if still larger than ~12.8 KB encoded
      }

      var slug = sanitizeSlug(key);
      deleteCookieChunks(slug);

      var appPath = getAppScopePath();
      for (var c = 0; c < numChunks; c++) {
        var slice = encoded.slice(c * CHUNK_SIZE, (c + 1) * CHUNK_SIZE);
        writeRawCookie(COOKIE_PREFIX + slug + "__" + c, slice, appPath, MAX_AGE_SEC);
      }
      writeRawCookie(
        COOKIE_PREFIX + slug + "__meta",
        encodeURIComponent(JSON.stringify({ k: key, n: numChunks, t: Date.now() })),
        appPath,
        MAX_AGE_SEC
      );

      updateFamilyPulseCookie(key, compacted);
      return true;
    } catch (e) {
      return false;
    }
  }

  function readFamilyPulseCookie() {
    try {
      var cookies = readAllCookies();
      if (!cookies[PULSE_COOKIE]) return {};
      return JSON.parse(decodeURIComponent(cookies[PULSE_COOKIE])) || {};
    } catch (e) {
      return {};
    }
  }

  // Tiny cross-repo summary cookie (Path=/) shared across krunked-fpv.github.io
  function updateFamilyPulseCookie(key, compactedStr) {
    try {
      var pulse = readFamilyPulseCookie();
      var obj = null;
      try {
        obj = JSON.parse(compactedStr);
      } catch (e) {}

      if (obj && typeof obj === "object") {
        // Detect Violet's Homework Game state
        if ("coins" in obj && ("stars" in obj || "signoffs" in obj || "readyCheck" in obj)) {
          var starCount = Array.isArray(obj.stars)
            ? obj.stars.filter(Boolean).length
            : typeof obj.stars === "object" && obj.stars
            ? Object.keys(obj.stars).filter(function (k) { return !!obj.stars[k]; }).length
            : Number(obj.stars) || 0;
          pulse.violet = {
            coins: Number(obj.coins) || 0,
            stars: starCount,
            streak: Number(obj.streak) || 0,
            ts: Date.now()
          };
        }
        // Detect Ozias's PokéMath League state
        else if ("xp" in obj && ("pokedex" in obj || "badges" in obj || "gradeLevel" in obj)) {
          var badgeCount = Array.isArray(obj.badges)
            ? obj.badges.filter(Boolean).length
            : typeof obj.badges === "object" && obj.badges
            ? Object.keys(obj.badges).filter(function (k) { return !!obj.badges[k]; }).length
            : 0;
          var caughtCount = Array.isArray(obj.pokedex)
            ? obj.pokedex.length
            : typeof obj.pokedex === "object" && obj.pokedex
            ? Object.keys(obj.pokedex).filter(function (k) { return !!obj.pokedex[k]; }).length
            : 0;
          pulse.ozias = {
            grade: obj.gradeLevel || "Lv.30",
            xp: Number(obj.xp) || 0,
            coins: Number(obj.coins || obj.pokeCoins) || 0,
            badges: badgeCount,
            caught: caughtCount,
            ts: Date.now()
          };
        }
        // Detect Discogs Vinyl Vault flattening queue or overrides
        else if (
          "todo" in obj ||
          "done" in obj ||
          "Need to be done" in obj ||
          "need_to_be_done_release_ids" in obj ||
          "done_release_ids" in obj
        ) {
          var todoArr = obj.need_to_be_done_release_ids || obj.todo || obj["Need to be done"] || [];
          var doneArr = obj.done_release_ids || obj.done || obj["Done"] || [];
          pulse.discogs = pulse.discogs || {};
          pulse.discogs.flattenTodo = Array.isArray(todoArr) ? todoArr.length : 0;
          pulse.discogs.flattenDone = Array.isArray(doneArr) ? doneArr.length : 0;
          pulse.discogs.ts = Date.now();
        }
      }

      var encodedPulse = encodeURIComponent(JSON.stringify(pulse));
      if (encodedPulse.length <= 1800) {
        writeRawCookie(PULSE_COOKIE, encodedPulse, "/", MAX_AGE_SEC);
      }
    } catch (e) {}
  }

  // Reconstruct any missing localStorage keys from Shadow Cookies BEFORE app boots
  function healLocalStorageFromCookies() {
    var healedKeys = [];
    try {
      var cookies = readAllCookies();
      for (var ck in cookies) {
        if (!Object.prototype.hasOwnProperty.call(cookies, ck)) continue;
        if (ck.indexOf(COOKIE_PREFIX) !== 0 || !ck.endsWith("__meta")) continue;

        var slug = ck.slice(COOKIE_PREFIX.length, ck.length - "__meta".length);
        var meta = null;
        try {
          meta = JSON.parse(decodeURIComponent(cookies[ck]));
        } catch (e) {
          continue;
        }
        if (!meta || !meta.k || !meta.n) continue;

        var chunks = [];
        var complete = true;
        for (var c = 0; c < meta.n; c++) {
          var part = cookies[COOKIE_PREFIX + slug + "__" + c];
          if (typeof part !== "string") {
            complete = false;
            break;
          }
          chunks.push(part);
        }
        if (!complete) continue;

        var envelope = null;
        try {
          envelope = JSON.parse(decodeURIComponent(chunks.join("")));
        } catch (e) {
          continue;
        }
        if (!envelope || !envelope.k || typeof envelope.d !== "string") continue;

        var targetKey = envelope.k;
        var existingVal = null;
        try {
          existingVal = window.localStorage.getItem(targetKey);
        } catch (e) {}

        // Restore if localStorage was wiped/evicted
        if (existingVal === null || existingVal === undefined || existingVal === "") {
          try {
            Storage.prototype.setItem.call(window.localStorage, targetKey, envelope.d);
            healedKeys.push(targetKey);
          } catch (e) {}
        }
      }
    } catch (e) {}
    return healedKeys;
  }

  // Backup existing localStorage keys into cookies immediately on script load
  function syncExistingLocalStorageToCookies() {
    var count = 0;
    try {
      for (var i = 0; i < window.localStorage.length; i++) {
        var k = window.localStorage.key(i);
        if (shouldTrackKey(k)) {
          var v = window.localStorage.getItem(k);
          if (v && mirrorKeyToCookie(k, v)) {
            count++;
          }
        }
      }
    } catch (e) {}
    return count;
  }

  // Monkey-patch Storage.prototype.setItem, removeItem, and clear so every save/reset is mirrored
  function installStorageInterceptor() {
    try {
      var origSetItem = Storage.prototype.setItem;
      var origRemoveItem = Storage.prototype.removeItem;
      var origClear = Storage.prototype.clear;

      Storage.prototype.setItem = function (key, value) {
        origSetItem.apply(this, arguments);
        if (this === window.localStorage) {
          mirrorKeyToCookie(String(key), String(value));
        }
      };

      Storage.prototype.removeItem = function (key) {
        origRemoveItem.apply(this, arguments);
        if (this === window.localStorage && shouldTrackKey(String(key))) {
          deleteCookieChunks(sanitizeSlug(String(key)));
        }
      };

      Storage.prototype.clear = function () {
        origClear.apply(this, arguments);
        if (this === window.localStorage) {
          clearAllAppShadowCookies();
        }
      };
    } catch (e) {}
  }

  var healedOnBoot = healLocalStorageFromCookies();
  installStorageInterceptor();
  var mirroredOnBoot = syncExistingLocalStorageToCookies();

  // Add subtle tooltip/indicator to existing Sync badge once DOM loads
  window.addEventListener("DOMContentLoaded", function () {
    try {
      var badgeCandidates = [
        document.getElementById("syncStatusPill"),
        document.getElementById("topSyncBtn"),
        document.getElementById("btn-open-sync-modal"),
        document.getElementById("btn-live-sync-modal")
      ];
      for (var i = 0; i < badgeCandidates.length; i++) {
        var el = badgeCandidates[i];
        if (el && !el.getAttribute("data-cookie-vault")) {
          el.setAttribute("data-cookie-vault", "active");
          var prevTitle = el.getAttribute("title") || "";
          el.setAttribute(
            "title",
            (prevTitle ? prevTitle + " • " : "") +
              "Shadow-Cookie Auto-Healer Active (400-Day Backup)"
          );
        }
      }
    } catch (e) {}
  });

  window.__KRUNKED_COOKIE_VAULT__ = {
    version: "1.0.0",
    healedOnBoot: healedOnBoot,
    mirroredOnBoot: mirroredOnBoot,
    healNow: healLocalStorageFromCookies,
    syncFromLocalStorage: syncExistingLocalStorageToCookies,
    getFamilyPulse: readFamilyPulseCookie,
    clearCookies: clearAllAppShadowCookies,
    status: function () {
      return {
        protocol: window.location.protocol,
        cookiesEnabled: navigator.cookieEnabled && window.location.protocol !== "file:",
        healedKeysOnBoot: healedOnBoot,
        mirroredKeysCount: syncExistingLocalStorageToCookies(),
        familyPulse: readFamilyPulseCookie()
      };
    }
  };
})();
