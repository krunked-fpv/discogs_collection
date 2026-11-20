    const DEFAULT_FLATTENING_STATUS = 'Need to be done';
/* __VAULT_YTM_MAPS_JS__ */
    window.__VAULT_YTM_RELEASE_MAP__ = typeof VERIFIED_YTM_RELEASE_MAP !== 'undefined' ? VERIFIED_YTM_RELEASE_MAP : {};
    window.__VAULT_YTM_ALBUM_STEM_MAP__ = typeof VERIFIED_YTM_ALBUM_STEM_MAP !== 'undefined' ? VERIFIED_YTM_ALBUM_STEM_MAP : {};
    window.__VAULT_DEFAULT_FLATTENING_STATUS__ = DEFAULT_FLATTENING_STATUS;
    function initApp() {
      window.__VAULT_DOM_READY__ = true;
      if (typeof window.__KRUNKED_BOOT_ESM__ === 'function') {
        window.__KRUNKED_BOOT_ESM__();
      }
    }
    window.addEventListener('DOMContentLoaded', initApp);
