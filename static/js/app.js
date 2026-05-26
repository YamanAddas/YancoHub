/**
 * YancoHub — Frontend Application
 * 3D hexagonal crystal carousel, starfield, cinematic UI.
 */

// ── Constants ──────────────────────────────────────────────────────────────

const VISIBLE_HALF = 4; // cards visible on each side of center

// ── State ──────────────────────────────────────────────────────────────────

const state = {
    games: [],
    filteredGames: [],
    selectedIndex: 0,
    currentTab: 'all',
    sortBy: 'az',
    collections: {},
    favorites: new Set(),
    hiddenSystems: new Set(),
    playtimes: {},
    stores: {},
    chatHistory: [],
    chatSessionId: null,
    chatSessions: [],
    chatSidebarOpen: false,
    catbyteModels: [],
    catbyteCurrentModel: '',
    scanning: false,
    catbyteOnline: false,
    activeMood: null,
    gamingMode: false,
    gamingFocusIndex: 0,
    settings: {},
    settingsSchema: {},
};

// ── DOM ────────────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);
const $$ = (sel) => document.querySelectorAll(sel);
const qs = (sel) => document.querySelector(sel);

/**
 * Fetch JSON with HTTP status validation.
 * Throws on non-OK responses so callers' catch blocks handle it.
 */
async function fetchJSON(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`HTTP ${r.status} from ${url}`);
    return r.json();
}

// ── Unified Settings ─────────────────────────────────────────────────────────

/** Load all settings once; caches values + schema, applies visual settings. */
async function loadSettings() {
    try {
        const data = await fetchJSON('/api/settings');
        state.settings = data.values || {};
        state.settingsSchema = {};
        if (Array.isArray(data.schema)) {
            for (const entry of data.schema) state.settingsSchema[entry.key] = entry;
        }
        applyVisualSettings();
    } catch (e) {
        console.warn('loadSettings failed:', e);
    }
    return state.settings;
}

/** Apply settings that affect the visual appearance (live preview targets). */
function applyVisualSettings() {
    document.documentElement.dataset.density = state.settings.card_density || 'comfortable';
    if (state.settings.theme_accent) applyTheme(state.settings.theme_accent);
}

/** Set the accent-family CSS vars from a hex color. accent-dim/glow follow
 *  automatically because they're defined as rgba(var(--accent-rgb), X). */
function applyTheme(hex) {
    if (typeof hex !== 'string') return;
    let m = hex.replace('#', '').trim();
    if (m.length === 3) m = m.split('').map(c => c + c).join('');
    if (m.length !== 6 || /[^0-9a-f]/i.test(m)) return;
    const r = parseInt(m.slice(0, 2), 16);
    const g = parseInt(m.slice(2, 4), 16);
    const b = parseInt(m.slice(4, 6), 16);
    const mix = (v, t = 0.30) => Math.round(v + (255 - v) * t);
    const toHex = (v) => v.toString(16).padStart(2, '0');
    const bright = `#${toHex(mix(r))}${toHex(mix(g))}${toHex(mix(b))}`;
    const root = document.documentElement;
    root.style.setProperty('--accent', '#' + m);
    root.style.setProperty('--accent-rgb', `${r}, ${g}, ${b}`);
    root.style.setProperty('--accent-bright', bright);
}

/** Wire the accent-color swatches + native color picker. */
function bindThemeSwatches() {
    const root = document.querySelector('.theme-swatches[data-setting="theme_accent"]');
    if (!root) return;
    const current = (state.settings.theme_accent || '#00e5c1').toLowerCase();
    const swatches = root.querySelectorAll('.theme-swatch[data-value]');
    const customSwatch = root.querySelector('.theme-swatch-custom');
    const isPreset = [...swatches].some(s => s.dataset.value.toLowerCase() === current);
    swatches.forEach(s => s.classList.toggle('active', s.dataset.value.toLowerCase() === current));
    if (customSwatch) customSwatch.classList.toggle('active', !isPreset);

    swatches.forEach((s) => {
        s.onclick = async () => {
            const value = s.dataset.value;
            swatches.forEach(b => b.classList.toggle('active', b === s));
            if (customSwatch) customSwatch.classList.remove('active');
            try { await patchSetting('theme_accent', value, { showUndo: true }); }
            catch (e) { console.warn('patchSetting theme_accent failed:', e); }
        };
    });

    const picker = document.getElementById('themeAccentPicker');
    if (picker) {
        picker.value = current.length === 7 ? current : '#00e5c1';
        // Live-preview only while dragging the picker (no PATCH each frame)
        picker.oninput = (e) => applyTheme(e.target.value);
        picker.onchange = async (e) => {
            swatches.forEach(b => b.classList.remove('active'));
            if (customSwatch) customSwatch.classList.add('active');
            try { await patchSetting('theme_accent', e.target.value, { showUndo: true }); }
            catch (err) { console.warn('patchSetting theme_accent failed:', err); }
        };
    }
}

/**
 * Partial-update one setting via PATCH /api/settings.
 * Returns {values, errors, meta}; updates state.settings with the new values.
 *
 * opts.showUndo — if true and the value actually changed, raises a 5s
 *                 "{Label} updated · Undo" toast that PATCHes back on click.
 */
async function patchSetting(key, value, opts = {}) {
    const prev = state.settings[key];
    const data = await fetchJSON('/api/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value }),
    });
    if (data.values) state.settings = data.values;
    const hadError = !!(data.errors && data.errors[key]);
    if (!hadError) {
        // Reapply visual settings (cheap and keeps preview in sync with server truth)
        applyVisualSettings();
        if (opts.showUndo && prev !== state.settings[key]) {
            const label = (state.settingsSchema[key] && state.settingsSchema[key].label) || key;
            showUndoToast(label, key, prev);
        }
    }
    return data;
}

/** Toast with an inline "Undo" action that reverts the setting. */
function showUndoToast(label, key, prevValue) {
    const safe = label.replace(/[&<>"']/g, (c) =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const toast = showToast(`<strong>${safe}</strong> updated`, 'success', 5000);
    if (!toast) return;
    const body = toast.querySelector('.toast-body');
    if (!body) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'toast-action';
    btn.textContent = 'Undo';
    btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        btn.disabled = true;
        try { await patchSetting(key, prevValue, { showUndo: false }); }
        catch (err) { console.warn('undo failed:', err); }
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 260);
    });
    body.appendChild(btn);
}

// Optional post-change hooks for settings with client-side effects.
const SETTING_HOOKS = {
    show_uninstalled: () => { setTimeout(async () => { await loadGames(); applyFilter(); }, 3000); },
};

/** Wire every [data-setting] toggle-switch to the unified API. */
function bindSettingToggles() {
    document.querySelectorAll('.toggle-switch[data-setting]').forEach((el) => {
        const key = el.dataset.setting;
        el.setAttribute('aria-checked', state.settings[key] ? 'true' : 'false');
        el.onclick = async () => {
            const prev = el.getAttribute('aria-checked') === 'true';
            const next = !prev;
            el.setAttribute('aria-checked', next ? 'true' : 'false');  // optimistic
            try {
                const d = await patchSetting(key, next, { showUndo: true });
                if (d.errors && d.errors[key]) {
                    el.setAttribute('aria-checked', prev ? 'true' : 'false');  // revert
                    showToast(d.errors[key], 'error');
                    return;
                }
                el.setAttribute('aria-checked', state.settings[key] ? 'true' : 'false');
                if (SETTING_HOOKS[key]) SETTING_HOOKS[key]();
            } catch (e) {
                el.setAttribute('aria-checked', prev ? 'true' : 'false');  // revert
                console.warn(`patchSetting ${key} failed:`, e);
            }
        };
    });
}

/** Wire every [data-setting] segmented-enum control to the unified API. */
function bindSettingEnums() {
    document.querySelectorAll('.settings-segmented[data-setting]').forEach((group) => {
        const key = group.dataset.setting;
        const setActive = (val) => group.querySelectorAll('.settings-seg').forEach((b) =>
            b.classList.toggle('active', b.dataset.value === val));
        setActive(state.settings[key]);
        group.querySelectorAll('.settings-seg').forEach((btn) => {
            btn.onclick = async () => {
                if (btn.classList.contains('active')) return;
                const value = btn.dataset.value;
                setActive(value);
                // Live preview is applied inside patchSetting (applyVisualSettings)
                try {
                    const d = await patchSetting(key, value, { showUndo: true });
                    if (d.errors && d.errors[key]) {
                        showToast(d.errors[key], 'error');
                        setActive(state.settings[key]);
                    }
                } catch (e) {
                    console.warn(`patchSetting ${key} failed:`, e);
                    setActive(state.settings[key]);
                }
            };
        });
    });
}

// ── Settings backup / import / reset ─────────────────────────────────────────

/** Download all current settings as a portable JSON file. */
function exportSettings() {
    const payload = {
        yancohub_settings: '1.0',
        exported_at: new Date().toISOString(),
        values: { ...state.settings },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    a.href = url;
    a.download = `yancohub-settings-${stamp}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    showToast(`Exported <strong>${Object.keys(payload.values).length}</strong> settings`, 'success');
}

/** Read a JSON file and PATCH its values via the unified API. */
async function importSettings(file) {
    if (!file) return;
    let parsed;
    try {
        parsed = JSON.parse(await file.text());
    } catch {
        showToast('Could not parse JSON file', 'error');
        return;
    }
    // Accept either the wrapped export format or a plain {key: value} map.
    const values = (parsed && typeof parsed === 'object' && parsed.values && typeof parsed.values === 'object')
        ? parsed.values
        : (parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null);
    if (!values) {
        showToast('Settings file is not in the expected format', 'error');
        return;
    }
    const total = Object.keys(values).length;
    if (!total) { showToast('No settings to import', 'info'); return; }
    try {
        const d = await fetchJSON('/api/settings', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(values),
        });
        if (d.values) state.settings = d.values;
        applyVisualSettings();
        bindSettingToggles();
        bindSettingEnums();
        const failed = Object.keys(d.errors || {}).length;
        const applied = total - failed;
        if (failed) {
            showToast(`Imported ${applied} setting${applied === 1 ? '' : 's'} · ${failed} skipped`, 'info');
        } else {
            showToast(`Imported <strong>${applied}</strong> setting${applied === 1 ? '' : 's'}`, 'success');
        }
    } catch {
        showToast('Failed to apply imported settings', 'error');
    }
}

let _resetArmed = false;
let _resetArmTimer = null;

/** Two-step reset: first click arms; second click within 3.5s actually resets. */
async function resetSettings() {
    const btn = $('btnResetSettings');
    if (!btn) return;
    if (!_resetArmed) {
        _resetArmed = true;
        btn.dataset.origText = btn.textContent;
        btn.textContent = 'Click again to confirm';
        btn.classList.add('btn-danger-armed');
        _resetArmTimer = setTimeout(() => {
            _resetArmed = false;
            btn.textContent = btn.dataset.origText || 'Reset to defaults';
            btn.classList.remove('btn-danger-armed');
        }, 3500);
        return;
    }
    clearTimeout(_resetArmTimer);
    _resetArmed = false;
    btn.classList.remove('btn-danger-armed');
    btn.textContent = btn.dataset.origText || 'Reset to defaults';

    // Build defaults from the cached schema (skips hidden keys; includes
    // registry-backed keys, which PATCH applies via set_startup_enabled).
    const defaults = {};
    Object.values(state.settingsSchema).forEach((entry) => {
        if (entry && entry.key && entry.default !== undefined) {
            defaults[entry.key] = entry.default;
        }
    });
    try {
        const d = await fetchJSON('/api/settings', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(defaults),
        });
        if (d.values) state.settings = d.values;
        applyVisualSettings();
        bindSettingToggles();
        bindSettingEnums();
        showToast(`Reset <strong>${Object.keys(defaults).length}</strong> settings to defaults`, 'success');
    } catch {
        showToast('Failed to reset settings', 'error');
    }
}

// ── Global Toast Notifications ────────────────────────────────────────────

const TOAST_ICONS = {
    success: '\u2714',  // ✔
    error:   '\u2716',  // ✖
    info:    '\u24D8',  // ⓘ
};

/**
 * Show a toast notification.
 * @param {string} message - Main text (supports HTML)
 * @param {'success'|'error'|'info'} type - Toast variant
 * @param {number} duration - Auto-dismiss ms (0 = sticky)
 * @returns {HTMLElement} The toast element (for manual dismiss)
 */
function showToast(message, type = 'info', duration = 3500) {
    const stack = $('toastStack');
    if (!stack) return null;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${TOAST_ICONS[type] || TOAST_ICONS.info}</span>
        <div class="toast-body">${message}</div>
        <button class="toast-dismiss" aria-label="Dismiss">\u2715</button>
    `;

    const dismiss = () => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 260);
    };

    toast.querySelector('.toast-dismiss').addEventListener('click', dismiss);

    stack.appendChild(toast);

    // Cap at 5 visible toasts
    while (stack.children.length > 5) {
        stack.firstElementChild.remove();
    }

    if (duration > 0) {
        setTimeout(dismiss, duration);
    }

    return toast;
}

// ── Connection Error Helpers (called by pywebview health watchdog) ────────

function showConnectionError() {
    const el = $('connectionError');
    if (el) el.classList.remove('hidden');
}

function hideConnectionError() {
    const el = $('connectionError');
    if (el) el.classList.add('hidden');
}

function showFatalError(msg) {
    const el = $('fatalError');
    if (el) {
        if (msg) {
            const txt = document.getElementById('fatalErrorMessage');
            if (txt) txt.textContent = msg;
        }
        el.classList.remove('hidden');
    }
}

// ── Per-system fallback color gradients ────────────────────────────────────

const SYS_COLORS = {
    snes:         ['#3b1f7e', '#1a0d3d'],
    nes:          ['#8b1a1a', '#3d0d0d'],
    megadrive:    ['#1a3a6b', '#0a1a35'],
    mastersystem: ['#1a3a6b', '#0a1a35'],
    gamegear:     ['#1a3a6b', '#0a1a35'],
    gba:          ['#2d1b5e', '#140d2e'],
    gb:           ['#2a4a2a', '#0d1f0d'],
    gbc:          ['#3a3a1a', '#1a1a0d'],
    n64:          ['#1a4a1a', '#0a250a'],
    psx:          ['#2a2a3a', '#0d0d1a'],
    ps2:          ['#1a2a4a', '#0a1525'],
    ps3:          ['#1a1a2a', '#0a0a15'],
    psp:          ['#2a2a3a', '#15151f'],
    dreamcast:    ['#3a2a1a', '#1f150d'],
    saturn:       ['#3a3a3a', '#1a1a1a'],
    gamecube:     ['#2a1a4a', '#150d25'],
    wii:          ['#2a3a4a', '#151f25'],
    nds:          ['#3a2a3a', '#1f151f'],
    atari2600:    ['#4a2a1a', '#251510'],
    neogeo:       ['#4a1a1a', '#250d0d'],
    fbneo:        ['#4a1a1a', '#250d0d'],
    cps1:         ['#3a1a2a', '#1f0d15'],
    cps2:         ['#3a1a2a', '#1f0d15'],
    cps3:         ['#3a1a2a', '#1f0d15'],
    mame:         ['#2a2a1a', '#15150d'],
    ngp:          ['#1a3a3a', '#0d1f1f'],
    steam:        ['#1a2a3a', '#0a1520'],
    epic:         ['#2d1b69', '#1a1a2e'],
    gog:          ['#4a1942', '#1a1a2e'],
    xbox:         ['#107c10', '#0e3d0e'],
    ea:           ['#4a1a1a', '#1a1a2e'],
    ubisoft:      ['#1a2a4a', '#1a1a2e'],
    battlenet:    ['#1a3a4a', '#1a1a2e'],
    local:        ['#2a2a2a', '#1a1a1a'],
};

const SOURCE_ICONS = {
    steam: '🎮', epic: '🏔️', gog: '🌌', xbox: '🎯',
    ea: '⚡', ubisoft: '🔷', battlenet: '🌀', local: '📁', retro: '👾',
};

// ── Initialization ─────────────────────────────────────────────────────────

async function init() {
    initStarfield();
    initParticles();
    updateSplash(10, 'Connecting...');

    await waitForBackend();
    updateSplash(30, 'Loading stores...');

    await loadStores();
    updateSplash(50, 'Scanning libraries...');

    await loadGames();
    updateSplash(70, 'Loading user data...');

    await Promise.all([loadFavorites(), loadCollections(), loadHiddenSystems(), loadPlaytimes()]);
    updateSplash(90, 'Preparing interface...');

    checkCatbyteStatus();
    setInterval(checkCatbyteStatus, 60000);
    buildRetroTabs();
    autoShowConsolePanel();
    applyFilter();

    if (state.scanning) {
        updateSplash(95, 'Scanning your libraries...');
        // Poll until scan completes, then refresh
        const pollScan = setInterval(async () => {
            await loadGames();
            if (!state.scanning) {
                clearInterval(pollScan);
                buildRetroTabs();
                autoShowConsolePanel();
                applyFilter();
            }
        }, 2000);
    }

    updateSplash(100, 'Ready!');

    setTimeout(() => {
        $('splash').classList.add('fade-out');
        $('app').classList.remove('hidden');
        setTimeout(() => $('splash').style.display = 'none', 800);
        // Start polling for artwork batch progress after splash
        startArtworkProgressPoll();
    }, 400);

    // Auto-enter Game Mode if setting is enabled
    try {
        const s = await loadSettings();
        if (s.start_in_game_mode && state.games.length > 0) {
            setTimeout(() => enterGamingMode(), 800);
        }
    } catch (e) { console.warn('Game mode setting check failed:', e); }

    bindEvents();

    // Check for updates 3s after load
    setTimeout(async () => {
        try {
            const ud = await fetchJSON('/api/update-available');
            if (ud.available) {
                const banner = $('updateBanner');
                const ver = $('updateBannerVersion');
                const link = $('updateBannerLink');
                if (banner && ver) {
                    ver.textContent = 'v' + ud.latest_version;
                    if (link && ud.url) link.href = ud.url;
                    banner.classList.remove('hidden');
                }
            }
        } catch { /* silent */ }
    }, 3000);

    // Dismiss update banner
    const dismissBtn = $('updateBannerDismiss');
    if (dismissBtn) {
        dismissBtn.onclick = () => {
            const banner = $('updateBanner');
            if (banner) banner.classList.add('hidden');
        };
    }

    // First-run onboarding check
    try {
        const onbStatus = await fetchJSON('/api/onboarding/status');
        if (!onbStatus.complete) {
            const onb = $('onboardingOverlay');
            if (onb) {
                onb.classList.remove('hidden');
                initOnboarding();
            }
        }
    } catch { /* silent */ }
}

async function waitForBackend() {
    for (let i = 0; i < 30; i++) {
        try {
            const r = await fetch('/health');
            if (r.ok) return;
        } catch (e) { console.warn('Waiting for backend:', e.message); }
        await new Promise(r => setTimeout(r, 500));
    }
}

function updateSplash(pct, text) {
    $('splashProgress').style.width = pct + '%';
    $('splashStatus').textContent = text;
}

// ── Data Loading ───────────────────────────────────────────────────────────

async function loadGames() {
    try {
        const data = await fetchJSON('/api/games');
        if (data.status === 'scanning') {
            state.games = [];
            state.scanning = true;
            return;
        }
        state.games = Array.isArray(data) ? data : (data.games || []);
        state.scanning = false;
    } catch (e) { console.warn('loadGames failed:', e); state.games = []; state.scanning = false; }
}

async function loadStores() {
    try {
        state.stores = await fetchJSON('/api/stores');
    } catch (e) { console.warn('loadStores failed:', e); }
}

async function loadFavorites() {
    try {
        state.favorites = new Set(await fetchJSON('/api/favorites'));
    } catch (e) { console.warn('loadFavorites failed:', e); }
}

async function loadCollections() {
    try {
        state.collections = await fetchJSON('/api/collections');
    } catch (e) { console.warn('loadCollections failed:', e); }
}

async function loadHiddenSystems() {
    try {
        state.hiddenSystems = new Set(await fetchJSON('/api/hidden-systems'));
    } catch (e) { console.warn('loadHiddenSystems failed:', e); }
}

// ── Artwork Progress Polling ──────────────────────────────────────────────

let _artworkPollTimer = null;

function startArtworkProgressPoll() {
    if (_artworkPollTimer) return;
    _artworkPollTimer = setInterval(pollArtworkProgress, 1500);
    // First check immediately
    pollArtworkProgress();
}

async function pollArtworkProgress() {
    try {
        const p = await fetchJSON('/api/artwork/progress');
        const pill = $('artworkProgressPill');
        const stack = $('toastStack');

        if (p.active && p.total > 0) {
            $('artworkProgressCount').textContent = p.fetched;
            $('artworkProgressTotal').textContent = p.total;
            pill.classList.remove('hidden');
            if (stack) stack.classList.add('has-pill');
        } else {
            if (!pill.classList.contains('hidden') && p.done) {
                // Was visible, now done — show completion toast
                pill.classList.add('hidden');
                if (stack) stack.classList.remove('has-pill');
                if (p.fetched > 0) {
                    showToast(`Artwork sync complete \u2014 <strong>${p.fetched}</strong> new images`, 'success');
                }
            }
            if (p.done || !p.active) {
                pill.classList.add('hidden');
                if (stack) stack.classList.remove('has-pill');
                clearInterval(_artworkPollTimer);
                _artworkPollTimer = null;
            }
        }
    } catch {
        clearInterval(_artworkPollTimer);
        _artworkPollTimer = null;
    }
}

async function loadPlaytimes() {
    try {
        state.playtimes = await fetchJSON('/api/playtime');
    } catch (e) { console.warn('loadPlaytimes failed:', e); }
}

async function checkCatbyteStatus() {
    let d = null;
    try {
        d = await fetchJSON('/api/catbyte/status');
        state.catbyteOnline = d.status === 'online';
    } catch (e) {
        console.warn('CatByte status check failed:', e);
        state.catbyteOnline = false;
    }
    const on = state.catbyteOnline;
    $('catbyteStatusDot').classList.toggle('online', on);
    $('catbyteStatus').textContent = on ? 'Online' : 'Offline';
    $('catbyteStatus').classList.toggle('online', on);
    if (on && d && d.model) {
        state.catbyteCurrentModel = d.model;
        updateModelPill();
    }
    $('btnCatbyte').classList.toggle('dimmed', !on);
    $('btnCatbyte').title = on ? 'CatByte AI (Ctrl+B)' : 'CatByte offline — check Settings (Ctrl+B)';
}

// ── Filtering & Carousel ───────────────────────────────────────────────────

// ── Sort Options ─────────────────────────────────────────────────────────

const SORT_OPTIONS = {
    az:       { label: 'A \u2192 Z',       icon: '<i class="ph ph-sort-ascending"></i>' },
    za:       { label: 'Z \u2192 A',       icon: '<i class="ph ph-sort-descending"></i>' },
    recent:   { label: 'Recent',            icon: '<i class="ph ph-clock-counter-clockwise"></i>' },
    playtime: { label: 'Most Played',       icon: '<i class="ph ph-timer"></i>' },
    rating:   { label: 'Top Rated',         icon: '<i class="ph ph-star"></i>' },
    year:     { label: 'Release Year',      icon: '<i class="ph ph-calendar"></i>' },
    random:   { label: 'Random',            icon: '<i class="ph ph-shuffle"></i>' },
};

function applySortOrder(games) {
    const sort = state.sortBy;
    switch (sort) {
        case 'az':
            games.sort((a, b) => {
                const af = state.favorites.has(a.id) ? 0 : 1;
                const bf = state.favorites.has(b.id) ? 0 : 1;
                if (af !== bf) return af - bf;
                return a.name.localeCompare(b.name);
            });
            break;
        case 'za':
            games.sort((a, b) => {
                const af = state.favorites.has(a.id) ? 0 : 1;
                const bf = state.favorites.has(b.id) ? 0 : 1;
                if (af !== bf) return af - bf;
                return b.name.localeCompare(a.name);
            });
            break;
        case 'recent':
            games.sort((a, b) => (b.last_played || 0) - (a.last_played || 0));
            break;
        case 'playtime':
            games.sort((a, b) => totalPlaytime(b) - totalPlaytime(a));
            break;
        case 'rating':
            games.sort((a, b) => (b.community_rating || 0) - (a.community_rating || 0));
            break;
        case 'year':
            games.sort((a, b) => (b.release_year || 0) - (a.release_year || 0));
            break;
        case 'random':
            for (let i = games.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [games[i], games[j]] = [games[j], games[i]];
            }
            break;
    }
    return games;
}

function applyFilter() {
    const tab = state.currentTab;
    let games = [...state.games];
    const now = Date.now() / 1000;

    // ── Filter by tab ──
    switch (tab) {
        case 'all': break;
        case 'favorites':
            games = games.filter(g => state.favorites.has(g.id));
            break;
        case 'recent':
            games = games.filter(g => g.last_played);
            break;
        case 'retro':
            games = games.filter(g => g.source === 'retro');
            break;
        // Smart collections
        case 'smart_unplayed':
            games = games.filter(g => !g.last_played && totalPlaytime(g) === 0);
            break;
        case 'smart_continue':
            games = games.filter(g => g.last_played && (now - g.last_played) < 30 * 86400 && totalPlaytime(g) > 0);
            break;
        case 'smart_backlog':
            games = games.filter(g => totalPlaytime(g) > 0 && totalPlaytime(g) < 0.5);
            break;
        case 'smart_completed':
            games = games.filter(g => {
                const pt = totalPlaytime(g);
                return g.source === 'retro' ? pt >= 5 : pt >= 10;
            });
            break;
        case 'smart_aside':
            // Started but set aside: > 30 min played, last touched >60 days ago,
            // and not in the "completed" bucket.
            games = games.filter(g => {
                if (!g.last_played) return false;
                const pt = totalPlaytime(g);
                if (pt < 0.5) return false;
                if ((now - g.last_played) < 60 * 86400) return false;
                const completedThreshold = g.source === 'retro' ? 5 : 10;
                return pt < completedThreshold;
            });
            break;
        case 'smart_gems':
            // Hidden gems: highly rated but barely played by *you*.
            games = games.filter(g => {
                const r = _normalizedRating(g);
                return r !== null && r >= 75 && totalPlaytime(g) < 1;
            });
            break;
        default:
            // Genre tab: "genre_Action"
            if (tab.startsWith('genre_')) {
                const genre = tab.slice(6);
                games = games.filter(g => g.genre && g.genre.split(/;\s*/).some(
                    t => t.toLowerCase() === genre.toLowerCase()
                ));
            }
            // Retro system tab: "retro_snes"
            else if (tab.startsWith('retro_')) {
                const sys = tab.slice(6);
                games = games.filter(g => g.source === 'retro' && g.system === sys);
            }
            // Store tab
            else {
                games = games.filter(g => g.source === tab);
            }
            break;
    }

    // ── Sort ──
    games = applySortOrder(games);

    state.filteredGames = games;
    state.selectedIndex = 0;

    if (state.scanning) {
        $('carousel').innerHTML = '';
        $('emptyState').classList.add('hidden');
        $('scanningState').classList.remove('hidden');
        $('carouselContainer').classList.add('hidden');
        $('gameInfo').style.visibility = 'hidden';
        $('detailPanel').classList.remove('visible');
        $('heroBackdrop').classList.remove('active');
        $('gameCount').textContent = '';
        return;
    }

    $('scanningState').classList.add('hidden');

    if (games.length === 0) {
        $('carousel').innerHTML = '';
        $('emptyState').classList.remove('hidden');
        $('carouselContainer').classList.add('hidden');
        $('gameInfo').style.visibility = 'hidden';
        $('detailPanel').classList.remove('visible');
        $('heroBackdrop').classList.remove('active');
        $('gameCount').textContent = '';
    } else {
        $('emptyState').classList.add('hidden');
        $('carouselContainer').classList.remove('hidden');
        $('gameInfo').style.visibility = 'visible';
        renderCarousel();
        updateGameInfo();
        updateGameCount();
    }
}

// ── Dynamic Retro System Tabs ─────────────────────────────────────────────

const RETRO_SYSTEM_NAMES = {
    snes: 'SNES', nes: 'NES', gba: 'GBA', gb: 'GB', gbc: 'GBC',
    n64: 'N64', nds: 'NDS', megadrive: 'Genesis', mastersystem: 'Master Sys',
    gamegear: 'Game Gear', atari2600: 'Atari 2600', psx: 'PS1', ps2: 'PS2',
    ps3: 'PS3', psp: 'PSP', dreamcast: 'Dreamcast', saturn: 'Saturn',
    gamecube: 'GameCube', wii: 'Wii', neogeo: 'Neo Geo', fbneo: 'FBNeo',
    cps1: 'CPS-1', cps2: 'CPS-2', cps3: 'CPS-3', mame: 'MAME', ngp: 'NGP',
};

const RETRO_SYSTEM_ICONS = {
    snes: '\uD83C\uDFAE', nes: '\uD83D\uDD79\uFE0F', gba: '\uD83D\uDCF1',
    gb: '\uD83D\uDCDF', gbc: '\uD83C\uDF08', n64: '\uD83D\uDD79\uFE0F',
    nds: '\u270F\uFE0F', megadrive: '\uD83D\uDC99', mastersystem: '\uD83D\uDD35',
    gamegear: '\uD83D\uDD0D', atari2600: '\uD83D\uDD78\uFE0F', psx: '\uD83D\uDCBF',
    ps2: '\uD83D\uDCBF', ps3: '\uD83C\uDFAE', psp: '\uD83C\uDFAE',
    dreamcast: '\uD83C\uDF00', saturn: '\uD83E\uDE90', gamecube: '\uD83D\uDFEA',
    wii: '\u2B1C', neogeo: '\uD83C\uDFB0', fbneo: '\uD83D\uDD25',
    cps1: '\uD83E\uDD4A', cps2: '\uD83E\uDD4A', cps3: '\uD83E\uDD4A',
    mame: '\uD83D\uDC7E', ngp: '\uD83D\uDCDF',
};

// ── Brand metadata for hex panel tabs ────────────────────────────────────

const BRAND_ICON = {
    all:       '<i class="ph-bold ph-squares-four"></i>',
    favorites: '<i class="ph-fill ph-star"></i>',
    recent:    '<i class="ph ph-clock-counter-clockwise"></i>',
    steam:     '<i class="ph-bold ph-steam-logo"></i>',
    epic:      '<i class="ph-bold ph-mountain"></i>',
    gog:       '<i class="ph-bold ph-planet"></i>',
    xbox:      '<i class="ph-bold ph-x-circle"></i>',
    ea:        '<i class="ph-bold ph-lightning"></i>',
    ubisoft:   '<i class="ph-bold ph-spiral"></i>',
    battlenet: '<i class="ph-bold ph-globe-hemisphere-west"></i>',
    local:     '<i class="ph ph-folder-open"></i>',
    retro:     '<i class="ph-fill ph-game-controller"></i>',
};

const TAB_META = {
    all:       { name: 'All Games',   colors: ['#0a2a3a', '#060b14'] },
    favorites: { name: 'Favorites',   colors: ['#4a3a0a', '#2a1f05'] },
    recent:    { name: 'Recent',      colors: ['#0a2a4a', '#051525'] },
    steam:     { name: 'Steam',       colors: ['#1b2838', '#0a1520'] },
    epic:      { name: 'Epic Games',  colors: ['#2d1b69', '#1a1a2e'] },
    gog:       { name: 'GOG',         colors: ['#4a1942', '#1a0a1a'] },
    xbox:      { name: 'Xbox',        colors: ['#107c10', '#0e3d0e'] },
    ea:        { name: 'EA',          colors: ['#4a1a1a', '#1a0a0a'] },
    ubisoft:   { name: 'Ubisoft',     colors: ['#1a2a4a', '#0a1525'] },
    battlenet: { name: 'Battle.net',  colors: ['#1a3a4a', '#0a1f25'] },
    local:     { name: 'Local',       colors: ['#2a2a2a', '#1a1a1a'] },
    retro:     { name: 'All Retro',   colors: ['#2a1a3a', '#150d1f'] },
};

// Ordered list of store sources to show in the panel
const STORE_SOURCES = ['steam', 'epic', 'gog', 'xbox', 'ea', 'ubisoft', 'battlenet', 'local'];

// Smart collection metadata
const SMART_META = {
    smart_unplayed:  { name: 'Unplayed',          colors: ['#1a2a1a', '#0a150a'], icon: '\u2728' },
    smart_continue:  { name: 'Continue Playing',   colors: ['#2a1a3a', '#150d1f'], icon: '\u25B6' },
    smart_backlog:   { name: 'Backlog',            colors: ['#3a2a1a', '#1f150d'], icon: '\uD83D\uDCDA' },
    smart_completed: { name: 'Completed',          colors: ['#0a3a2a', '#051f15'], icon: '\u2714' },
    smart_aside:     { name: 'Set Aside',          colors: ['#3a1a1a', '#1f0d0d'], icon: '\u23F8' },
    smart_gems:      { name: 'Hidden Gems',        colors: ['#3a3a0d', '#1f1f05'], icon: '\u2728' },
};

const SMART_ICON = {
    smart_unplayed:  '<i class="ph ph-sparkle"></i>',
    smart_continue:  '<i class="ph-fill ph-play"></i>',
    smart_backlog:   '<i class="ph ph-books"></i>',
    smart_completed: '<i class="ph ph-check-circle"></i>',
    smart_aside:     '<i class="ph ph-pause-circle"></i>',
    smart_gems:      '<i class="ph-fill ph-diamond"></i>',
};

// Genre color palette (rotating)
const GENRE_COLORS = [
    ['#3a1a2a', '#1f0d15'], ['#1a2a3a', '#0d1520'], ['#2a3a1a', '#151f0d'],
    ['#3a2a1a', '#1f150d'], ['#1a3a2a', '#0d1f15'], ['#2a1a3a', '#150d1f'],
    ['#3a1a1a', '#1f0d0d'], ['#1a1a3a', '#0d0d1f'], ['#2a2a1a', '#15150d'],
];

function buildRetroTabs() {
    document.querySelectorAll('.tab-retro-system').forEach(t => t.remove());
    buildConsolePanel();
}

function buildConsolePanel() {
    const scroll = $('consolePanelScroll');
    if (!scroll) return;
    scroll.innerHTML = '';

    // Build sort bar
    buildSortBar();

    // ── Count games per source, system, genre, smart ──
    const sourceCounts = {};
    const systemCounts = {};
    const genreCounts = {};
    const now = Date.now() / 1000;
    let smartUnplayed = 0, smartContinue = 0, smartBacklog = 0, smartCompleted = 0;
    let smartAside = 0, smartGems = 0;

    for (const g of state.games) {
        const src = g.source || 'local';
        sourceCounts[src] = (sourceCounts[src] || 0) + 1;
        if (src === 'retro' && g.system && !state.hiddenSystems.has(g.system)) {
            systemCounts[g.system] = (systemCounts[g.system] || 0) + 1;
        }
        // Genres
        if (g.genre) {
            for (const genre of g.genre.split(/;\s*/)) {
                const trimmed = genre.trim();
                if (trimmed) genreCounts[trimmed] = (genreCounts[trimmed] || 0) + 1;
            }
        }
        // Smart collections
        const pt = totalPlaytime(g);
        const completedThreshold = src === 'retro' ? 5 : 10;
        if (!g.last_played && pt === 0) smartUnplayed++;
        if (g.last_played && (now - g.last_played) < 30 * 86400 && pt > 0) smartContinue++;
        if (pt > 0 && pt < 0.5) smartBacklog++;
        if (pt >= completedThreshold) smartCompleted++;
        if (g.last_played && pt >= 0.5 && pt < completedThreshold && (now - g.last_played) >= 60 * 86400) smartAside++;
        const r = _normalizedRating(g);
        if (r !== null && r >= 75 && pt < 1) smartGems++;
    }

    const totalGames = state.games.length;
    const totalFavorites = state.favorites ? state.favorites.size : 0;
    const totalRecent = state.games.filter(g => g.last_played).length;
    const totalRetro = sourceCounts['retro'] || 0;

    // ── Utility section ──
    _addHexTab(scroll, 'all', totalGames);
    if (totalFavorites > 0) _addHexTab(scroll, 'favorites', totalFavorites);
    if (totalRecent > 0) _addHexTab(scroll, 'recent', totalRecent);

    // ── Smart Collections ──
    const smartCounts = {
        smart_unplayed: smartUnplayed,
        smart_continue: smartContinue,
        smart_aside: smartAside,
        smart_gems: smartGems,
        smart_backlog: smartBacklog,
        smart_completed: smartCompleted,
    };
    const hasAnySmart = Object.values(smartCounts).some(c => c > 0);
    if (hasAnySmart) {
        _addHexDivider(scroll, 'Smart');
        for (const [key, count] of Object.entries(smartCounts)) {
            if (count === 0) continue;
            _addSmartHexTab(scroll, key, count);
        }
    }

    // ── Stores ──
    const hasStores = STORE_SOURCES.some(s => (sourceCounts[s] || 0) > 0);
    if (hasStores) {
        _addHexDivider(scroll, 'Stores');
        for (const src of STORE_SOURCES) {
            const count = sourceCounts[src] || 0;
            if (count === 0) continue;
            _addHexTab(scroll, src, count);
        }
    }

    // ── Genres ──
    const genreKeys = Object.keys(genreCounts).sort((a, b) => genreCounts[b] - genreCounts[a]);
    if (genreKeys.length > 0) {
        _addHexDivider(scroll, 'Genres');
        genreKeys.forEach((genre, i) => {
            _addGenreHexTab(scroll, genre, genreCounts[genre], i);
        });
    }

    // ── Retro ──
    const retroSystems = Object.keys(systemCounts).sort((a, b) => systemCounts[b] - systemCounts[a]);
    if (totalRetro > 0) {
        _addHexDivider(scroll, 'Retro');
        _addHexTab(scroll, 'retro', totalRetro);
        for (const sys of retroSystems) {
            _addRetroHexTab(scroll, sys, systemCounts[sys]);
        }
    }

    // Mark active tab
    const activeHex = scroll.querySelector(`.console-hex-wrap[data-tab="${state.currentTab}"]`);
    if (activeHex) activeHex.classList.add('active');
}

function _addHexTab(container, tab, count) {
    const meta = TAB_META[tab];
    if (!meta) return;
    const svg = BRAND_ICON[tab] || '';
    const colors = meta.colors;

    const wrap = document.createElement('div');
    wrap.className = 'console-hex-wrap';
    wrap.dataset.tab = tab;
    wrap.title = `${meta.name} \u2014 ${count} game${count !== 1 ? 's' : ''}`;

    wrap.innerHTML = `
        <div class="console-hex-border"></div>
        <div class="console-hex">
            <div class="console-hex-art" style="background: linear-gradient(135deg, ${colors[0]}, ${colors[1]});"></div>
            <div class="console-hex-overlay"></div>
            <div class="console-hex-brand-icon">${svg}</div>
            <div class="console-hex-glass"></div>
            <div class="console-hex-label">
                <span class="console-hex-name">${meta.name}</span>
                <span class="console-hex-count">${count} game${count !== 1 ? 's' : ''}</span>
            </div>
        </div>
    `;
    container.appendChild(wrap);
}

function _addRetroHexTab(container, sys, count) {
    const icon = RETRO_SYSTEM_ICONS[sys] || '\uD83C\uDFAE';
    const name = RETRO_SYSTEM_NAMES[sys] || sys;
    const colors = SYS_COLORS[sys] || ['#1a2a3a', '#0a1520'];

    const wrap = document.createElement('div');
    wrap.className = 'console-hex-wrap';
    wrap.dataset.tab = `retro_${sys}`;
    wrap.title = `${name} \u2014 ${count} game${count !== 1 ? 's' : ''}`;

    wrap.innerHTML = `
        <div class="console-hex-border"></div>
        <div class="console-hex">
            <div class="console-hex-art" style="background: linear-gradient(135deg, ${colors[0]}, ${colors[1]});"></div>
            <div class="console-hex-overlay"></div>
            <span class="console-hex-fallback-icon">${icon}</span>
            <div class="console-hex-glass"></div>
            <div class="console-hex-label">
                <span class="console-hex-name">${name}</span>
                <span class="console-hex-count">${count} game${count !== 1 ? 's' : ''}</span>
            </div>
        </div>
    `;
    container.appendChild(wrap);

    // Load platform artwork from LaunchBox
    _loadPlatformArt(wrap, sys);
}

function _addSmartHexTab(container, key, count) {
    const meta = SMART_META[key];
    if (!meta) return;
    const svg = SMART_ICON[key] || '';

    const wrap = document.createElement('div');
    wrap.className = 'console-hex-wrap';
    wrap.dataset.tab = key;
    wrap.title = `${meta.name} \u2014 ${count} game${count !== 1 ? 's' : ''}`;

    wrap.innerHTML = `
        <div class="console-hex-border"></div>
        <div class="console-hex">
            <div class="console-hex-art" style="background: linear-gradient(135deg, ${meta.colors[0]}, ${meta.colors[1]});"></div>
            <div class="console-hex-overlay"></div>
            <div class="console-hex-brand-icon">${svg}</div>
            <div class="console-hex-glass"></div>
            <div class="console-hex-label">
                <span class="console-hex-name">${meta.name}</span>
                <span class="console-hex-count">${count} game${count !== 1 ? 's' : ''}</span>
            </div>
        </div>
    `;
    container.appendChild(wrap);
}

function _addGenreHexTab(container, genre, count, index) {
    const colors = GENRE_COLORS[index % GENRE_COLORS.length];

    const wrap = document.createElement('div');
    wrap.className = 'console-hex-wrap';
    wrap.dataset.tab = `genre_${genre}`;
    wrap.title = `${genre} \u2014 ${count} game${count !== 1 ? 's' : ''}`;

    wrap.innerHTML = `
        <div class="console-hex-border"></div>
        <div class="console-hex">
            <div class="console-hex-art" style="background: linear-gradient(135deg, ${colors[0]}, ${colors[1]});"></div>
            <div class="console-hex-overlay"></div>
            <div class="console-hex-brand-icon"><i class="ph ph-tag"></i></div>
            <div class="console-hex-glass"></div>
            <div class="console-hex-label">
                <span class="console-hex-name">${genre}</span>
                <span class="console-hex-count">${count} game${count !== 1 ? 's' : ''}</span>
            </div>
        </div>
    `;
    container.appendChild(wrap);
}

function _addHexDivider(container, label) {
    const div = document.createElement('div');
    div.className = 'console-hex-divider';
    div.innerHTML = `<span>${label}</span>`;
    container.appendChild(div);
}

function buildSortBar() {
    const bar = $('sortBar');
    if (!bar) return;
    bar.innerHTML = '';
    for (const [key, opt] of Object.entries(SORT_OPTIONS)) {
        const btn = document.createElement('button');
        btn.className = `sort-btn${state.sortBy === key ? ' active' : ''}`;
        btn.dataset.sort = key;
        btn.title = opt.label;
        btn.innerHTML = opt.icon;
        bar.appendChild(btn);
    }
}

function setSort(sortKey) {
    if (!SORT_OPTIONS[sortKey]) return;
    state.sortBy = sortKey;
    buildSortBar();
    applyFilter();
}

function _loadPlatformArt(wrap, sys) {
    const artEl = wrap.querySelector('.console-hex-art');
    if (!artEl) return;

    const img = new Image();
    img.onload = () => {
        artEl.style.background = 'none';
        artEl.style.backgroundImage = `url(${img.src})`;
        artEl.style.backgroundSize = 'contain';
        artEl.style.backgroundPosition = 'center';
        artEl.style.backgroundRepeat = 'no-repeat';
    };
    img.onerror = () => {};
    img.src = `/api/platform-artwork/${encodeURIComponent(sys)}`;
}

function toggleConsolePanel() {
    const panel = $('consolePanel');
    const toggle = $('consolePanelToggle');
    const app = $('app');
    const isHidden = panel.classList.contains('hidden');

    if (isHidden) {
        panel.classList.remove('hidden');
        toggle.classList.add('active');
        app.classList.add('console-panel-open');
    } else {
        panel.classList.add('hidden');
        toggle.classList.remove('active');
        app.classList.remove('console-panel-open');
    }
}

function selectConsoleHex(tab) {
    // Deactivate all hex tabs, activate selected
    $$('.console-hex-wrap').forEach(h => h.classList.remove('active'));
    const wrap = document.querySelector(`.console-hex-wrap[data-tab="${tab}"]`);
    if (wrap) wrap.classList.add('active');

    state.currentTab = tab;
    applyFilter();
}

function autoShowConsolePanel() {
    const panel = $('consolePanel');
    const toggle = $('consolePanelToggle');
    if (!panel || !toggle) return;

    if (state.games.length > 0 && panel.classList.contains('hidden')) {
        // Auto-open on wide screens
        if (window.innerWidth > 1200) {
            panel.classList.remove('hidden');
            toggle.classList.add('active');
            $('app').classList.add('console-panel-open');
        }
    }
}

// ── Gaming Mode ──────────────────────────────────────────────────────────

function enterGamingMode() {
    state.gamingMode = true;
    state.gamingFocusIndex = 0;
    const overlay = $('gamingMode');
    overlay.classList.remove('hidden');

    // Use native pywebview fullscreen (falls back to browser API)
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.toggle_fullscreen();
    } else {
        try { document.documentElement.requestFullscreen().catch(() => {}); } catch (e) { console.warn('Fullscreen enter failed:', e); }
    }

    renderGamingGrid();
    updateGamingInfo();
    updateGamingCategory();
    initGamingCardTilt();

    // Animate entrance — stagger only the first ~20 visible cards
    overlay.classList.add('gaming-entering');
    const cards = overlay.querySelectorAll('.gaming-card');
    const animCount = Math.min(cards.length, 20);
    for (let i = 0; i < animCount; i++) {
        cards[i].style.animationDelay = `${60 + i * 25}ms`;
        cards[i].classList.add('gaming-card-enter');
    }
    setTimeout(() => {
        overlay.classList.remove('gaming-entering');
        for (let i = 0; i < animCount; i++) {
            cards[i].classList.remove('gaming-card-enter');
            cards[i].style.animationDelay = '';
        }
    }, 700);
}

function exitGamingMode() {
    state.gamingMode = false;
    const overlay = $('gamingMode');
    overlay.classList.add('gaming-exiting');
    setTimeout(() => {
        overlay.classList.add('hidden');
        overlay.classList.remove('gaming-exiting');
    }, 300);

    // Exit native fullscreen
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.toggle_fullscreen();
    } else {
        try { if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); } catch (e) { console.warn('Fullscreen exit failed:', e); }
    }
}

function renderGamingGrid() {
    const grid = $('gamingGrid');
    if (!grid) return;
    grid.innerHTML = '';

    const games = state.filteredGames;
    const frag = document.createDocumentFragment();

    games.forEach((game, i) => {
        const card = document.createElement('div');
        card.className = `gaming-card${i === state.gamingFocusIndex ? ' focused' : ''}`;
        card.dataset.index = i;
        card.tabIndex = 0;

        const colors = SYS_COLORS[game.system || game.source] || ['#1a2a3a', '#0a1520'];
        card.innerHTML = `
            <div class="gaming-card-hex" style="background: linear-gradient(135deg, ${colors[0]}, ${colors[1]});">
                <div class="gaming-card-art"></div>
                <div class="gaming-card-overlay"></div>
                <div class="gaming-card-name">${game.name}</div>
            </div>
        `;
        frag.appendChild(card);
    });

    // Single DOM insert — no reflow per card
    grid.appendChild(frag);

    // Lazy-load artwork after DOM is settled
    requestAnimationFrame(() => {
        const cards = grid.children;
        for (let i = 0; i < games.length; i++) {
            const game = games[i];
            if (game.source === 'retro' || (game.artwork && game.artwork.cover)) {
                const artEl = cards[i]?.querySelector('.gaming-card-art');
                if (!artEl) continue;
                const url = `/api/artwork/${encodeURIComponent(game.id)}/cover`;
                const img = new Image();
                img.onload = () => { artEl.style.backgroundImage = `url(${url})`; };
                img.src = url;
            }
        }
    });
}

function updateGamingInfo() {
    const game = state.filteredGames[state.gamingFocusIndex];
    const title = $('gamingInfoTitle');
    const meta = $('gamingInfoMeta');
    const desc = $('gamingInfoDesc');
    const hero = $('gamingHero');
    const cover = $('gamingSpotlightCover');
    if (!game) {
        title.textContent = '';
        meta.textContent = '';
        if (desc) desc.textContent = '';
        hero.style.backgroundImage = '';
        hero.classList.remove('active');
        if (cover) cover.style.backgroundImage = '';
        return;
    }
    title.textContent = game.name;
    const parts = [];
    if (game.source) parts.push(game.source.charAt(0).toUpperCase() + game.source.slice(1));
    if (game.genre) parts.push(game.genre.split(';')[0].trim());
    if (game.developer) parts.push(game.developer.split(';')[0].trim());
    if (game.release_year) parts.push(game.release_year);
    const pt = totalPlaytime(game);
    if (pt > 0) parts.push(`${pt < 1 ? Math.round(pt * 60) + 'm' : Math.round(pt) + 'h'} played`);
    meta.textContent = parts.join('  \u00B7  ');

    // Description
    if (desc) desc.textContent = game.description || '';

    // Spotlight cover art
    if (cover) {
        cover.style.backgroundImage = `url(/api/artwork/${encodeURIComponent(game.id)}/cover)`;
    }

    // Hero backdrop
    hero.style.backgroundImage = `url(/api/artwork/${encodeURIComponent(game.id)}/hero)`;
    hero.classList.add('active');

    // Dynamic ambient color from artwork
    applyGameAmbientColor(game.id);
}

function updateGamingCategory() {
    const el = $('gamingCategory');
    const sortEl = $('gamingSort');
    if (!el) return;
    const hexName = document.querySelector('.console-hex-wrap.active .console-hex-name');
    el.textContent = hexName ? hexName.textContent : 'All Games';
    if (sortEl) sortEl.textContent = SORT_OPTIONS[state.sortBy] ? SORT_OPTIONS[state.sortBy].label : '';
}

function gamingNavigate(dir) {
    const total = state.filteredGames.length;
    if (total === 0) return;

    const grid = $('gamingGrid');
    // Read actual column count from computed grid
    const gridStyle = getComputedStyle(grid);
    const cols = Math.max(1, gridStyle.gridTemplateColumns.split(' ').length);
    let idx = state.gamingFocusIndex;

    switch (dir) {
        case 'left':  idx = Math.max(0, idx - 1); break;
        case 'right': idx = Math.min(total - 1, idx + 1); break;
        case 'up':    idx = Math.max(0, idx - cols); break;
        case 'down':  idx = Math.min(total - 1, idx + cols); break;
    }

    if (idx !== state.gamingFocusIndex) {
        state.gamingFocusIndex = idx;
        $$('.gaming-card').forEach((c, i) => c.classList.toggle('focused', i === idx));
        const focused = grid.children[idx];
        if (focused) focused.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        updateGamingInfo();
    }
}

function gamingLaunch() {
    const game = state.filteredGames[state.gamingFocusIndex];
    if (!game) return;

    // ── Launch Ceremony ──
    const overlay = $('gamingMode');
    const ceremony = document.createElement('div');
    ceremony.className = 'launch-ceremony';
    ceremony.innerHTML = `
        <div class="launch-ceremony-bg"></div>
        <div class="launch-ceremony-art"></div>
        <div class="launch-ceremony-title">${escapeHtml(game.name)}</div>
        <div class="launch-ceremony-flash"></div>
    `;

    // Set art
    const artEl = ceremony.querySelector('.launch-ceremony-art');
    artEl.style.backgroundImage = `url(/api/artwork/${encodeURIComponent(game.id)}/hero)`;
    const bgEl = ceremony.querySelector('.launch-ceremony-bg');
    bgEl.style.backgroundImage = `url(/api/artwork/${encodeURIComponent(game.id)}/hero)`;

    overlay.appendChild(ceremony);

    // Phase 1: cards fade, art swells (0-400ms)
    requestAnimationFrame(() => ceremony.classList.add('phase-1'));

    // Phase 2: title appears, hold (400-900ms)
    setTimeout(() => ceremony.classList.add('phase-2'), 400);

    // Phase 3: flash and fade to black (900-1200ms)
    setTimeout(() => ceremony.classList.add('phase-3'), 900);

    // Actually launch and clean up
    setTimeout(() => {
        fetch(`/api/launch/${encodeURIComponent(game.id)}`, { method: 'POST' })
            .then(r => { if (!r.ok) return r.json().then(d => showToast(d.error || 'Launch failed', 'error')); })
            .catch(e => showToast('Failed to launch game', 'error'));
        setTimeout(() => {
            ceremony.classList.add('phase-done');
            setTimeout(() => ceremony.remove(), 500);
        }, 800);
    }, 1100);
}

// ── Dynamic Color Extraction ─────────────────────────────────────────────

const _colorCache = {};

function extractDominantColor(gameId, callback) {
    if (_colorCache[gameId]) { callback(_colorCache[gameId]); return; }

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
        const canvas = document.createElement('canvas');
        const size = 32; // downsample for speed
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, size, size);

        try {
            const data = ctx.getImageData(0, 0, size, size).data;
            let rSum = 0, gSum = 0, bSum = 0, count = 0;
            // Sample from center region and skip very dark/very light pixels
            for (let i = 0; i < data.length; i += 16) { // sample every 4th pixel
                const r = data[i], g = data[i+1], b = data[i+2];
                const brightness = (r + g + b) / 3;
                if (brightness > 30 && brightness < 220) {
                    rSum += r; gSum += g; bSum += b; count++;
                }
            }
            if (count > 0) {
                const color = {
                    r: Math.round(rSum / count),
                    g: Math.round(gSum / count),
                    b: Math.round(bSum / count),
                };
                // Find the most saturated channel to make the accent pop
                const max = Math.max(color.r, color.g, color.b);
                const boost = max > 0 ? Math.min(255 / max, 1.8) : 1;
                color.r = Math.min(255, Math.round(color.r * boost));
                color.g = Math.min(255, Math.round(color.g * boost));
                color.b = Math.min(255, Math.round(color.b * boost));
                _colorCache[gameId] = color;
                callback(color);
                return;
            }
        } catch (e) { console.warn('Color extraction failed:', e); }
        callback(null);
    };
    img.onerror = () => callback(null);
    img.src = `/api/artwork/${encodeURIComponent(gameId)}/cover`;
}

function applyGameAmbientColor(gameId) {
    extractDominantColor(gameId, (color) => {
        const overlay = $('gamingMode');
        if (!color) {
            overlay.style.setProperty('--game-r', '0');
            overlay.style.setProperty('--game-g', '229');
            overlay.style.setProperty('--game-b', '193');
            return;
        }
        overlay.style.setProperty('--game-r', color.r);
        overlay.style.setProperty('--game-g', color.g);
        overlay.style.setProperty('--game-b', color.b);
    });
}

// ── Holographic Card Tilt ────────────────────────────────────────────────

function initGamingCardTilt() {
    const grid = $('gamingGrid');
    if (!grid) return;

    // Remove old listeners if re-initializing
    if (grid._tiltCleanup) grid._tiltCleanup();

    let rafPending = false;
    let lastCard = null;
    let lastX = 0, lastY = 0;

    const onMove = (e) => {
        if (rafPending) return;
        const card = e.target.closest('.gaming-card');
        if (!card) return;
        lastCard = card;
        lastX = e.clientX;
        lastY = e.clientY;
        rafPending = true;
        requestAnimationFrame(() => {
            rafPending = false;
            if (!lastCard) return;
            const rect = lastCard.getBoundingClientRect();
            const x = (lastX - rect.left) / rect.width;
            const y = (lastY - rect.top) / rect.height;
            const rotY = (x - 0.5) * 14;
            const rotX = (0.5 - y) * 10;

            lastCard.style.transform = lastCard.classList.contains('focused')
                ? `scale(1.1) perspective(600px) rotateX(${rotX}deg) rotateY(${rotY}deg)`
                : `perspective(600px) rotateX(${rotX}deg) rotateY(${rotY}deg)`;

            const hex = lastCard.querySelector('.gaming-card-hex');
            if (hex) {
                hex.style.setProperty('--spec-x', `${x * 100}%`);
                hex.style.setProperty('--spec-y', `${y * 100}%`);
            }
        });
    };

    const onOut = (e) => {
        const card = e.target.closest('.gaming-card');
        if (card && !card.contains(e.relatedTarget)) {
            card.style.transform = card.classList.contains('focused') ? 'scale(1.1)' : '';
        }
    };

    const onLeave = () => {
        lastCard = null;
        grid.querySelectorAll('.gaming-card[style*="perspective"]').forEach(c => {
            c.style.transform = c.classList.contains('focused') ? 'scale(1.1)' : '';
        });
    };

    grid.addEventListener('mousemove', onMove);
    grid.addEventListener('mouseout', onOut);
    grid.addEventListener('mouseleave', onLeave);

    grid._tiltCleanup = () => {
        grid.removeEventListener('mousemove', onMove);
        grid.removeEventListener('mouseout', onOut);
        grid.removeEventListener('mouseleave', onLeave);
    };
}

// ── Mood Helpers ──────────────────────────────────────────────────────────

const MOOD_META = {
    quick:      { icon: '\u26A1',              label: 'Quick Session' },
    deep:       { icon: '\uD83C\uDF0A',        label: 'Deep Dive' },
    nostalgia:  { icon: '\uD83D\uDD79\uFE0F',  label: 'Nostalgia Trip' },
    new:        { icon: '\u2728',              label: 'Something New' },
    unfinished: { icon: '\uD83D\uDCCC',        label: 'Unfinished Business' },
    comfort:    { icon: '\u2615',              label: 'Comfort Pick' },
    surprise:   { icon: '\uD83C\uDFB0',        label: 'Surprise Me' },
    chill:      { icon: '\uD83C\uDF19',        label: 'Chill Vibes' },
};

function totalPlaytime(g) {
    return (g.playtime_hours || 0) + (g.playtime_from_api || 0);
}

/** Normalize a game's rating to a 0–100 scale, or null if unrated.
 *  Steam scores are already 0–100 (positive %), Wikipedia/IGDB sometimes 0–10.  */
function _normalizedRating(g) {
    const r = g.community_rating;
    if (r === null || r === undefined || r === '') return null;
    const n = typeof r === 'string' ? parseFloat(r) : r;
    if (!isFinite(n) || n <= 0) return null;
    return n <= 10 ? n * 10 : n;
}

function hasGenre(g, keywords) {
    if (!g.genre) return false;
    const lower = g.genre.toLowerCase();
    return keywords.some(k => lower.includes(k.toLowerCase()));
}

// ── Mood Filter ───────────────────────────────────────────────────────────

function applyMoodFilter(mood) {
    state.activeMood = mood;
    $('moodCatbyteBubble').classList.add('hidden');

    // Surprise Me has its own flow
    if (mood === 'surprise') {
        applySurpriseMood();
        return;
    }

    const now = Date.now() / 1000;
    const sixMonthsAgo = now - (180 * 24 * 60 * 60);
    const threeMonthsAgo = now - (90 * 24 * 60 * 60);
    const sixtyDaysAgo = now - (60 * 24 * 60 * 60);
    const fourteenDaysAgo = now - (14 * 24 * 60 * 60);
    let games = [...state.games];

    switch (mood) {
        case 'quick':
            games = games.filter(g =>
                g.source === 'retro' ||
                totalPlaytime(g) < 2 ||
                hasGenre(g, ['arcade', 'puzzle', 'racing', 'platformer'])
            );
            games.sort(() => Math.random() - 0.5);
            break;

        case 'deep':
            games = games.filter(g => {
                const hours = totalPlaytime(g);
                return hours >= 2 && hours < 100 &&
                       g.last_played && g.last_played > sixtyDaysAgo &&
                       g.source !== 'retro';
            });
            games.sort((a, b) => (b.last_played || 0) - (a.last_played || 0));
            break;

        case 'nostalgia':
            games = games.filter(g =>
                g.source === 'retro' ||
                (g.last_played && g.last_played < sixMonthsAgo) ||
                (state.favorites.has(g.id) && g.last_played && g.last_played < threeMonthsAgo) ||
                (g.release_year && g.release_year < 2010)
            );
            games.sort(() => Math.random() - 0.5);
            break;

        case 'new':
            games = games.filter(g => totalPlaytime(g) === 0 && !g.last_played);
            games.sort((a, b) => {
                const ra = a.community_rating || 0;
                const rb = b.community_rating || 0;
                if (rb !== ra) return rb - ra;
                return Math.random() - 0.5;
            });
            break;

        case 'unfinished':
            games = games.filter(g => {
                const hours = totalPlaytime(g);
                return hours >= 1 && hours <= 30 &&
                       g.last_played && g.last_played < fourteenDaysAgo;
            });
            games.sort((a, b) => totalPlaytime(b) - totalPlaytime(a));
            break;

        case 'comfort':
            games = games.filter(g =>
                state.favorites.has(g.id) ||
                (totalPlaytime(g) > 10 && (g.session_count || 0) > 5)
            );
            games.sort((a, b) => totalPlaytime(b) - totalPlaytime(a));
            break;

        case 'chill':
            games = games.filter(g => {
                if (hasGenre(g, ['horror', 'competitive', 'battle royale'])) return false;
                return hasGenre(g, ['rpg', 'adventure', 'simulation', 'sandbox', 'visual novel', 'walking simulator']) ||
                       (g.source === 'retro' && ['gb', 'gbc', 'gba', 'snes'].includes(g.system)) ||
                       totalPlaytime(g) < 5;
            });
            games.sort(() => Math.random() - 0.5);
            break;
    }

    state.filteredGames = games;
    state.selectedIndex = 0;

    // Show mood label
    const meta = MOOD_META[mood];
    $('moodLabelIcon').textContent = meta.icon;
    $('moodLabelText').textContent = meta.label + ' \u2014 ' + games.length + ' game' + (games.length !== 1 ? 's' : '');
    $('moodLabel').classList.remove('hidden');

    // Update carousel
    if (games.length === 0) {
        $('carousel').innerHTML = '';
        $('carouselContainer').classList.add('hidden');
        $('gameInfo').style.visibility = 'hidden';
        $('detailPanel').classList.remove('visible');
        $('gameCount').textContent = '';
    } else {
        $('carouselContainer').classList.remove('hidden');
        $('gameInfo').style.visibility = 'visible';
        renderCarousel();
        updateGameInfo();
    }

    // Async CatByte recommendation (non-blocking)
    if (games.length > 0) fetchCatbyteMoodRec(mood, games);
}

// ── Surprise Me ───────────────────────────────────────────────────────────

function applySurpriseMood() {
    const games = state.games.filter(g => g.installed !== false);
    if (games.length === 0) {
        $('moodLabelIcon').textContent = MOOD_META.surprise.icon;
        $('moodLabelText').textContent = 'No games to pick from!';
        $('moodLabel').classList.remove('hidden');
        return;
    }

    const now = Date.now() / 1000;
    const thirtyDaysAgo = now - (30 * 24 * 60 * 60);

    // Build weighted pool
    const pool = games.map(g => {
        const hours = totalPlaytime(g);
        let weight;
        if (hours === 0 && !g.last_played) weight = 3;
        else if (hours < 2) weight = 2;
        else if (g.last_played && g.last_played < thirtyDaysAgo) weight = 1;
        else weight = 0.5;
        return { game: g, weight };
    });

    const totalWeight = pool.reduce((s, p) => s + p.weight, 0);
    let pick = Math.random() * totalWeight;
    let chosen = pool[0].game;
    for (const p of pool) {
        pick -= p.weight;
        if (pick <= 0) { chosen = p.game; break; }
    }

    showSurpriseReveal(chosen, () => {
        // After animation: show full library scrolled to chosen game
        state.filteredGames = [...state.games];
        const idx = state.filteredGames.findIndex(g => g.id === chosen.id);
        state.selectedIndex = idx >= 0 ? idx : 0;

        $('moodLabelIcon').textContent = MOOD_META.surprise.icon;
        $('moodLabelText').textContent = 'Surprise Me \u2014 ' + chosen.name;
        $('moodLabel').classList.remove('hidden');

        $('carouselContainer').classList.remove('hidden');
        $('gameInfo').style.visibility = 'visible';
        renderCarousel();
        updateGameInfo();

        fetchCatbyteMoodRec('surprise', [chosen]);
    });
}

function showSurpriseReveal(game, callback) {
    const overlay = $('surpriseReveal');
    const cardArt = $('surpriseCardArt');
    const card = $('surpriseCard');
    const title = $('surpriseTitle');
    const subtitle = $('surpriseSubtitle');
    if (!overlay || !card) { if (callback) callback(); return; }

    // Reset state
    overlay.classList.remove('hidden', 'surprise-reveal--active', 'surprise-reveal--exit');
    card.classList.remove('surprise-card--visible');
    title.textContent = '';
    subtitle.textContent = '';
    cardArt.src = '';

    // Build subtitle from available metadata
    const parts = [];
    if (game.source) parts.push((SOURCE_ICONS[game.source] || '') + ' ' + game.source);
    if (game.genre) parts.push(game.genre.split(/[;,]/)[0].trim());
    if (game.release_year) parts.push(String(game.release_year));
    subtitle.textContent = parts.join('  \u00B7  ');

    // Phase 1: glow burst
    requestAnimationFrame(() => {
        overlay.classList.add('surprise-reveal--active');
    });

    // Phase 2: card reveal
    setTimeout(() => {
        const artType = (game.artwork && game.artwork.cover) ? 'cover' : 'header';
        cardArt.src = `/api/artwork/${game.id}/${artType}`;
        cardArt.onerror = () => { cardArt.style.display = 'none'; };
        card.classList.add('surprise-card--visible');
        title.textContent = game.name;
    }, 600);

    // Phase 3: exit
    setTimeout(() => {
        overlay.classList.add('surprise-reveal--exit');
    }, 2200);

    // Cleanup and callback
    setTimeout(() => {
        overlay.classList.add('hidden');
        overlay.classList.remove('surprise-reveal--active', 'surprise-reveal--exit');
        card.classList.remove('surprise-card--visible');
        cardArt.src = '';
        cardArt.style.display = '';
        callback();
    }, 2700);
}

// ── CatByte Mood Recommendation (async, non-blocking) ────────────────────

async function fetchCatbyteMoodRec(mood, games) {
    if (!state.catbyteOnline) return;

    const bubble = $('moodCatbyteBubble');
    const textEl = $('moodCatbyteText');
    bubble.classList.add('hidden');

    const sampleNames = games.slice(0, 15).map(g => g.name).join(', ');
    const prompt = `The user picked the "${MOOD_META[mood].label}" mood in their game launcher. ` +
        `Here are some matching games: ${sampleNames}. ` +
        `Give a fun one-liner recommendation or comment (1 sentence max, stay in character as CatByte).`;

    try {
        const d = await fetchJSON('/api/catbyte/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: prompt, history: [] }),
        });
        // Only show if mood hasn't changed while we were waiting
        if (d.response && d.status !== 'offline' && state.activeMood === mood) {
            textEl.textContent = d.response;
            bubble.classList.remove('hidden');
        }
    } catch {
        // Silent fail — non-blocking mood comment
    }
}

function clearMoodFilter() {
    state.activeMood = null;
    $('moodLabel').classList.add('hidden');
    $('moodCatbyteBubble').classList.add('hidden');
    applyFilter();
}

// ── 3D Carousel ────────────────────────────────────────────────────────────

function renderCarousel() {
    $('carousel').innerHTML = '';
    const total = state.filteredGames.length;
    if (total === 0) return;

    const start = Math.max(0, state.selectedIndex - VISIBLE_HALF);
    const end = Math.min(total - 1, state.selectedIndex + VISIBLE_HALF);

    for (let i = start; i <= end; i++) {
        const offset = i - state.selectedIndex;
        const card = createCarouselCard(state.filteredGames[i], i, offset);
        applyCardTransform(card, offset);
        $('carousel').appendChild(card);
    }
}

function updateCarousel() {
    const total = state.filteredGames.length;
    if (total === 0) { $('carousel').innerHTML = ''; return; }

    const start = Math.max(0, state.selectedIndex - VISIBLE_HALF);
    const end = Math.min(total - 1, state.selectedIndex + VISIBLE_HALF);
    const desired = new Set();
    for (let i = start; i <= end; i++) desired.add(i);

    // Remove cards no longer visible — animate out
    const existing = $('carousel').querySelectorAll('.carousel-card');
    const existingMap = new Map();
    existing.forEach(card => {
        const idx = parseInt(card.dataset.index);
        if (desired.has(idx)) {
            existingMap.set(idx, card);
        } else {
            card.style.opacity = '0';
            card.style.transform += ' scale(0.5)';
            card.style.pointerEvents = 'none';
            setTimeout(() => card.remove(), 550);
        }
    });

    // Add or update cards
    for (let i = start; i <= end; i++) {
        const offset = i - state.selectedIndex;
        let card = existingMap.get(i);

        if (!card) {
            card = createCarouselCard(state.filteredGames[i], i, offset);
            card.classList.add('card-entering');
            $('carousel').appendChild(card);
            card.offsetHeight; // force reflow
            setTimeout(() => card.classList.remove('card-entering'), 400);
        }

        card.className = 'carousel-card';
        if (offset === 0) card.classList.add('center');
        else card.classList.add('side-' + Math.min(Math.abs(offset), 3));
        card.dataset.offset = offset;
        applyCardTransform(card, offset);
    }
}

function applyFallbackGradient(el, game) {
    const colors = SYS_COLORS[game.system] || SYS_COLORS[game.source] || ['#0c1628', '#060b14'];
    el.style.background = `radial-gradient(ellipse 70% 50% at 50% 35%, ${colors[0]}88 0%, transparent 60%), linear-gradient(160deg, ${colors[0]} 0%, ${colors[1]} 100%)`;
}

function createCarouselCard(game, index, offset) {
    const card = document.createElement('div');
    card.className = 'carousel-card';
    card.dataset.index = index;
    card.dataset.offset = offset;

    if (offset === 0) card.classList.add('center');
    else card.classList.add('side-' + Math.min(Math.abs(offset), 3));

    // Outer glow shell
    const glow = document.createElement('div');
    glow.className = 'carousel-card-glow';
    card.appendChild(glow);

    // Hex border (crystal edge with bevel)
    const border = document.createElement('div');
    border.className = 'carousel-card-border';
    card.appendChild(border);

    // Hex body (crystal glass fill)
    const hex = document.createElement('div');
    hex.className = 'carousel-card-hex';
    card.appendChild(hex);

    // Glass highlight (top bevel light)
    const glass = document.createElement('div');
    glass.className = 'carousel-card-glass';
    card.appendChild(glass);

    // Inner depth shadow (recessed feel)
    const depth = document.createElement('div');
    depth.className = 'carousel-card-depth';
    card.appendChild(depth);

    // Surface reflection sweep
    const reflect = document.createElement('div');
    reflect.className = 'carousel-card-reflect';
    card.appendChild(reflect);

    // Inner rectangular art area
    const inner = document.createElement('div');
    inner.className = 'carousel-card-inner';

    // Always attempt artwork for retro games (LaunchBox lookup is on-demand),
    // and for any game with pre-populated artwork URLs
    const hasArtwork = (game.artwork && (game.artwork.cover || game.artwork.header));
    const isRetro = game.source === 'retro';
    if (hasArtwork || isRetro) {
        const artType = (game.artwork && game.artwork.cover) ? 'cover' : 'cover';
        const art = document.createElement('div');
        art.className = 'carousel-card-art skeleton';

        // Skeleton icon while loading
        const skelIcon = document.createElement('div');
        skelIcon.className = 'skeleton-icon';
        skelIcon.textContent = SOURCE_ICONS[game.source] || '\uD83C\uDFAE';
        art.appendChild(skelIcon);

        const loadArt = () => {
            const img = new Image();
            img.src = `/api/artwork/${game.id}/${artType}`;
            img.onload = () => {
                art.style.backgroundImage = `url('${img.src}')`;
                art.classList.remove('skeleton');
                art.classList.add('materialize');
                art.innerHTML = '';  // remove skeleton icon + retry
                setTimeout(() => art.classList.remove('materialize'), 500);
            };
            img.onerror = () => {
                art.classList.remove('skeleton');
                art.innerHTML = '';
                applyFallbackGradient(art, game);
                // Add retry icon
                const retry = document.createElement('button');
                retry.className = 'art-retry';
                retry.title = 'Retry artwork';
                retry.textContent = '\u21BB';  // ↻
                retry.addEventListener('click', (e) => {
                    e.stopPropagation();
                    art.style.backgroundImage = '';
                    art.style.background = '';
                    art.className = 'carousel-card-art skeleton';
                    art.innerHTML = '';
                    const si = document.createElement('div');
                    si.className = 'skeleton-icon';
                    si.textContent = SOURCE_ICONS[game.source] || '\uD83C\uDFAE';
                    art.appendChild(si);
                    loadArt();
                });
                art.style.position = 'relative';
                art.appendChild(retry);
            };
        };
        loadArt();
        inner.appendChild(art);
    } else {
        const fb = document.createElement('div');
        fb.className = 'carousel-card-fallback';
        applyFallbackGradient(fb, game);

        const icon = document.createElement('div');
        icon.className = 'fallback-icon';
        icon.textContent = SOURCE_ICONS[game.source] || '🎮';
        fb.appendChild(icon);

        const sysLabel = document.createElement('div');
        sysLabel.className = 'fallback-system';
        sysLabel.textContent = game.system_name || game.system || game.source;
        fb.appendChild(sysLabel);

        const gameLabel = document.createElement('div');
        gameLabel.className = 'fallback-name';
        gameLabel.textContent = game.name;
        fb.appendChild(gameLabel);

        inner.appendChild(fb);
    }
    card.appendChild(inner);

    // Uninstalled badge
    if (game.installed === false) {
        card.classList.add('uninstalled');
        const ubadge = document.createElement('div');
        ubadge.className = 'uninstalled-badge';
        ubadge.textContent = 'not installed';
        card.appendChild(ubadge);
    }

    // Favorite star badge
    if (state.favorites.has(game.id)) {
        const star = document.createElement('div');
        star.className = 'carousel-card-fav';
        star.textContent = '\u2B50';
        card.appendChild(star);
    }

    // Play time badge (from local tracking or API)
    const pt = state.playtimes[game.id];
    const apiHours = game.playtime_from_api || 0;
    const displayHours = (pt && pt.total_hours > 0) ? pt.total_hours : apiHours;
    if (displayHours > 0) {
        const badge = document.createElement('div');
        badge.className = 'carousel-card-playtime';
        badge.textContent = displayHours < 1
            ? `${Math.round(displayHours * 60)}m`
            : `${displayHours}h`;
        card.appendChild(badge);
    }

    // Click: center card → launch, side card → select
    card.addEventListener('click', () => {
        const off = parseInt(card.dataset.offset);
        if (off === 0) launchSelected();
        else {
            state.selectedIndex = index;
            updateCarousel();
            updateGameInfo();
        }
    });

    return card;
}

function applyCardTransform(card, offset) {
    const absOff = Math.abs(offset);
    const sign = offset > 0 ? 1 : -1;

    if (offset === 0) {
        card.style.transform = 'translateX(0) translateZ(60px) rotateY(0deg) scale(1)';
        card.style.zIndex = 10;
        card.style.opacity = 1;
    } else {
        const tx = sign * (140 + (absOff - 1) * 115);
        const ry = sign * -35;
        const tz = -80 - (absOff - 1) * 55;
        const sc = Math.max(0.45, 0.75 - (absOff - 1) * 0.12);
        const op = Math.max(0.3, 1.0 - absOff * 0.2);

        card.style.transform = `translateX(${tx}px) translateZ(${tz}px) rotateY(${ry}deg) scale(${sc})`;
        card.style.zIndex = 10 - absOff;
        card.style.opacity = op;
    }
}

// ── Game Info (above carousel) ─────────────────────────────────────────────

function updateGameInfo() {
    const game = state.filteredGames[state.selectedIndex];
    if (!game) {
        $('gameInfoTitle').textContent = '';
        $('gameInfoMeta').innerHTML = '';
        updateHeroBackdrop(null);
        updateDetailPanel(null);
        return;
    }

    $('gameInfoTitle').textContent = game.name;

    const badges = [];
    badges.push(`<span class="meta-badge source">${game.system_name || game.source}</span>`);

    if (game.developer) {
        badges.push(`<span class="meta-badge">${escapeHtml(game.developer.split(';')[0].trim())}</span>`);
    }
    if (game.release_year) {
        badges.push(`<span class="meta-badge">${game.release_year}</span>`);
    }
    if (game.genre) {
        badges.push(`<span class="meta-badge">${escapeHtml(game.genre.split(';')[0].trim())}</span>`);
    }
    if (game.community_rating) {
        // Normalize to a 5-star scale: Steam scores are 0–100, Wikipedia 0–10.
        const n = _normalizedRating(game);  // 0–100 or null
        if (n !== null) {
            const filled = Math.max(0, Math.min(5, Math.round(n / 20)));
            const stars = '★'.repeat(filled) + '☆'.repeat(5 - filled);
            badges.push(`<span class="meta-badge fav">${stars}</span>`);
        }
    }
    if (game.installed === false) {
        badges.push(`<span class="meta-badge not-installed">Not Installed</span>`);
    }

    const pt = state.playtimes[game.id];
    const apiHours = game.playtime_from_api || 0;
    const displayHours = (pt && pt.total_hours > 0) ? pt.total_hours : apiHours;
    if (displayHours > 0) {
        badges.push(`<span class="meta-badge playtime">${displayHours}h played</span>`);
    }
    if (state.favorites.has(game.id)) {
        badges.push(`<span class="meta-badge fav">★ Favorite</span>`);
    }

    $('gameInfoMeta').innerHTML = badges.join('');

    updateHeroBackdrop(game);
    updateDetailPanel(game);
}

// ── Hero Backdrop ─────────────────────────────────────────────────────────

let _heroGameId = null;

function updateHeroBackdrop(game) {
    const el = $('heroBackdrop');
    if (!game) {
        el.classList.remove('active');
        _heroGameId = null;
        return;
    }

    // Don't reload if same game
    if (_heroGameId === game.id) return;
    _heroGameId = game.id;

    // Fade out current backdrop before loading new one
    el.classList.remove('active');

    // Try hero art first, then header, then cover
    const artTypes = ['hero', 'header', 'cover'];
    const artwork = game.artwork || {};
    let artType = null;
    for (const t of artTypes) {
        if (artwork[t]) { artType = t; break; }
    }
    // Retro games: always try cover even if artwork dict is empty (LaunchBox on-demand)
    if (!artType && game.source === 'retro') artType = 'cover';

    const applyBackdrop = (bgValue) => {
        // Small delay for fade-out to complete before swapping
        setTimeout(() => {
            if (_heroGameId !== game.id) return;
            el.style.backgroundImage = bgValue;
            el.classList.add('active');
        }, 250);
    };

    if (!artType) {
        const colors = SYS_COLORS[game.system] || SYS_COLORS[game.source] || ['#0c1628', '#060b14'];
        applyBackdrop(`linear-gradient(135deg, ${colors[0]}, ${colors[1]})`);
        return;
    }

    // Preload then cross-fade
    const img = new Image();
    img.src = `/api/artwork/${game.id}/${artType}`;
    img.onload = () => {
        if (_heroGameId !== game.id) return;
        applyBackdrop(`url('${img.src}')`);
    };
    img.onerror = () => {
        if (_heroGameId !== game.id) return;
        const colors = SYS_COLORS[game.system] || SYS_COLORS[game.source] || ['#0c1628', '#060b14'];
        applyBackdrop(`linear-gradient(135deg, ${colors[0]}, ${colors[1]})`);
    };
}

// ── Detail Panel ──────────────────────────────────────────────────────────

// ── Keyboard / controller cheat sheet ────────────────────────────────────────

function openShortcuts()  { $('shortcutsOverlay').classList.remove('hidden'); }
function closeShortcuts() { $('shortcutsOverlay').classList.add('hidden'); }
function toggleShortcuts() {
    const ov = $('shortcutsOverlay');
    if (!ov) return;
    ov.classList.toggle('hidden');
}

// ── Per-game notes (free-text, autosaved) ────────────────────────────────────

let _notesCurrentGameId = null;
let _notesSaveTimer = null;
let _notesLastSaved = '';

function _autoSizeNote() {
    const ta = $('detailNotes');
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
}

function _flashNoteStatus(text, cls = 'is-saved', ms = 1400) {
    const el = $('detailNotesStatus');
    if (!el) return;
    el.textContent = text;
    el.classList.remove('is-saved', 'is-saving');
    if (cls) el.classList.add(cls);
    if (ms > 0) {
        clearTimeout(el._fadeT);
        el._fadeT = setTimeout(() => {
            el.classList.remove('is-saving', 'is-saved');
        }, ms);
    }
}

async function loadGameNote(gameId) {
    _notesCurrentGameId = gameId;
    const ta = $('detailNotes');
    if (!ta) return;
    // Flush any pending save from the previous game before swapping.
    if (_notesSaveTimer) { clearTimeout(_notesSaveTimer); _notesSaveTimer = null; }
    try {
        const d = await fetchJSON(`/api/notes/${encodeURIComponent(gameId)}`);
        // Guard against race: the user may have already navigated again.
        if (_notesCurrentGameId !== gameId) return;
        ta.value = d.note || '';
        _notesLastSaved = ta.value;
        _autoSizeNote();
        _flashNoteStatus('', null, 0);
    } catch (e) {
        console.warn('loadGameNote failed:', e);
    }
}

async function _saveCurrentNote() {
    const ta = $('detailNotes');
    if (!ta || !_notesCurrentGameId) return;
    const text = ta.value;
    if (text === _notesLastSaved) return;
    const targetGid = _notesCurrentGameId;  // capture for race protection
    _flashNoteStatus('Saving…', 'is-saving', 0);
    try {
        const d = await fetchJSON(`/api/notes/${encodeURIComponent(targetGid)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note: text }),
        });
        if (_notesCurrentGameId === targetGid) {
            _notesLastSaved = d.note || '';
            _flashNoteStatus('Saved');
        }
    } catch (e) {
        console.warn('saveNote failed:', e);
        _flashNoteStatus('Save failed', 'is-saving', 2000);
    }
}

function bindNoteHandlers() {
    const ta = $('detailNotes');
    if (!ta) return;
    ta.addEventListener('input', () => {
        _autoSizeNote();
        if (_notesSaveTimer) clearTimeout(_notesSaveTimer);
        _notesSaveTimer = setTimeout(() => {
            _notesSaveTimer = null;
            _saveCurrentNote();
        }, 800);
    });
    ta.addEventListener('blur', () => {
        if (_notesSaveTimer) { clearTimeout(_notesSaveTimer); _notesSaveTimer = null; }
        _saveCurrentNote();
    });
    ta.addEventListener('keydown', (e) => {
        // Esc commits + blurs (escape from the textarea).
        if (e.key === 'Escape') { e.preventDefault(); ta.blur(); }
    });
}

function updateDetailPanel(game) {
    const panel = $('detailPanel');
    if (!game) {
        panel.classList.remove('visible');
        return;
    }

    // Description
    $('detailDesc').textContent = game.description || '';

    // Personal note (debounced auto-save while typing)
    loadGameNote(game.id);

    // Favorite button state
    const isFav = state.favorites.has(game.id);
    $('detailFavIcon').textContent = isFav ? '★' : '☆';
    const favBtn = $('detailFavorite');
    favBtn.classList.toggle('fav-active', isFav);

    // Direct launch button — only show for store games that have a direct exe
    const dlBtn = $('detailDirectLaunch');
    if (dlBtn) {
        const hasDirectExe = game.direct_exe && game.source !== 'retro' && game.source !== 'local';
        dlBtn.classList.toggle('hidden', !hasDirectExe);
        if (hasDirectExe) updateDirectLaunchButton(game.id);
    }

    // Close any open dropdown
    $('collectionDropdown').classList.add('hidden');

    // Show the panel with slide-up animation
    panel.classList.add('visible');
}

async function updateDirectLaunchButton(gameId) {
    const btn = $('detailDirectLaunch');
    const label = $('detailDirectLabel');
    if (!btn || !label) return;
    try {
        const d = await fetchJSON(`/api/settings/direct-launch/${gameId}`);
        if (d.override === true) {
            label.textContent = 'Direct: ON';
            btn.classList.add('dl-force-on');
            btn.classList.remove('dl-force-off');
        } else if (d.override === false) {
            label.textContent = 'Direct: OFF';
            btn.classList.remove('dl-force-on');
            btn.classList.add('dl-force-off');
        } else {
            label.textContent = d.effective ? 'Direct' : 'Via Store';
            btn.classList.remove('dl-force-on', 'dl-force-off');
        }
    } catch (e) { console.warn('updateDirectLaunchButton failed:', e); }
}

async function cycleDirectLaunch() {
    const game = state.filteredGames[state.selectedIndex];
    if (!game) return;
    try {
        // Get current state
        const d = await fetchJSON(`/api/settings/direct-launch/${game.id}`);
        // Cycle: null → true → false → null
        let next;
        if (d.override === null || d.override === undefined) next = true;
        else if (d.override === true) next = false;
        else next = null;
        try {
            await fetch(`/api/settings/direct-launch/${game.id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value: next }),
            });
        } catch (e2) { console.warn('Set direct launch failed:', e2); }
        updateDirectLaunchButton(game.id);
    } catch (e) { console.warn('cycleDirectLaunch failed:', e); }
}

function updateGameCount() {
    const count = state.filteredGames.length;
    const hexEl = document.querySelector('.console-hex-wrap.active .console-hex-name');
    const tabName = hexEl ? hexEl.textContent : (TAB_META[state.currentTab] ? TAB_META[state.currentTab].name : state.currentTab);
    $('gameCount').textContent = `${tabName} \u2014 ${count} game${count !== 1 ? 's' : ''}`;
}

// ── Navigation ─────────────────────────────────────────────────────────────

function navigateCarousel(direction) {
    const total = state.filteredGames.length;
    if (total === 0) return;

    state.selectedIndex = Math.max(0, Math.min(total - 1, state.selectedIndex + direction));
    updateCarousel();
    updateGameInfo();
}

function launchSelected() {
    const game = state.filteredGames[state.selectedIndex];
    if (game) launchGame(game.id);
}

// ── Store Indicators (removed from top bar — info lives in Settings) ──────

// ── Onboarding ────────────────────────────────────────────────────────────

function initOnboarding() {
    const overlay = $('onboardingOverlay');
    if (!overlay) return;

    const storeNames = {
        steam: 'Steam', epic: 'Epic Games', gog: 'GOG Galaxy', xbox: 'Xbox',
        ea: 'EA Desktop', ubisoft: 'Ubisoft', battlenet: 'Battle.net',
    };

    function closeOnboarding() {
        overlay.classList.add('hidden');
        fetch('/api/onboarding/complete', { method: 'POST' });
    }

    function showStep(n) {
        for (let i = 1; i <= 3; i++) {
            const s = $('onbStep' + i);
            if (s) s.classList.toggle('hidden', i !== n);
        }
    }

    // Step 1 → 2
    const getStarted = $('onbGetStarted');
    if (getStarted) getStarted.onclick = () => {
        showStep(2);
        // Populate detected stores
        const container = $('onbStores');
        if (container && state.stores) {
            container.innerHTML = Object.entries(storeNames)
                .map(([k, v]) => {
                    const detected = state.stores[k];
                    return `<div class="onboarding-store-badge ${detected ? 'detected' : ''}">
                        <span class="store-dot"></span>${v}
                    </div>`;
                }).join('');
        }
    };

    // Step 2 → 3
    const cont2 = $('onbContinue2');
    if (cont2) cont2.onclick = () => {
        showStep(3);
        // Trigger rescan and watch for completion
        fetch('/api/rescan', { method: 'POST' });
        const pollId = setInterval(async () => {
            try {
                const r = await fetchJSON('/api/games');
                const count = r.length || 0;
                const countEl = $('onbGameCount');
                if (countEl) countEl.textContent = `Found ${count} game${count !== 1 ? 's' : ''} so far...`;
                if (count > 0) {
                    clearInterval(pollId);
                    if (countEl) countEl.textContent = `Found ${count} game${count !== 1 ? 's' : ''}!`;
                    const spinner = overlay.querySelector('.onboarding-spinner');
                    if (spinner) spinner.style.display = 'none';
                    const finish = $('onbFinish');
                    if (finish) finish.classList.remove('hidden');
                }
            } catch { /* keep polling */ }
        }, 1500);
        // Auto-complete after 15s even if no games found
        setTimeout(() => {
            clearInterval(pollId);
            const finish = $('onbFinish');
            if (finish) finish.classList.remove('hidden');
            const spinner = overlay.querySelector('.onboarding-spinner');
            if (spinner) spinner.style.display = 'none';
        }, 15000);
    };

    // Add folder buttons
    const addRom = $('onbAddRomFolder');
    if (addRom) addRom.onclick = async () => {
        if (window.pywebview && window.pywebview.api) {
            const path = await window.pywebview.api.browse_folder('Select ROM Folder');
            if (path) {
                await fetch('/api/rom-dirs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path }),
                });
                showToast('ROM folder added');
            }
        }
    };

    const addLocal = $('onbAddLocalFolder');
    if (addLocal) addLocal.onclick = async () => {
        if (window.pywebview && window.pywebview.api) {
            const path = await window.pywebview.api.browse_folder('Select Games Folder');
            if (path) {
                await fetch('/api/local-dirs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path }),
                });
                showToast('Games folder added');
            }
        }
    };

    // Finish
    const finish = $('onbFinish');
    if (finish) finish.onclick = closeOnboarding;

    // Skip buttons
    const skip1 = $('onbSkip1');
    if (skip1) skip1.onclick = closeOnboarding;
    const skip2 = $('onbSkip2');
    if (skip2) skip2.onclick = closeOnboarding;
}

// ── Events ─────────────────────────────────────────────────────────────────

function bindEvents() {
    // Console panel toggle + hex clicks (primary navigation)
    $('consolePanelToggle').addEventListener('click', toggleConsolePanel);
    $('consolePanelScroll').addEventListener('click', (e) => {
        const hex = e.target.closest('.console-hex-wrap');
        if (!hex) return;
        selectConsoleHex(hex.dataset.tab);
    });

    // Sort bar clicks
    $('sortBar').addEventListener('click', (e) => {
        const btn = e.target.closest('.sort-btn');
        if (!btn) return;
        setSort(btn.dataset.sort);
    });

    // Gaming mode
    $('btnGamingMode').addEventListener('click', enterGamingMode);
    $('gamingLaunchBtn').addEventListener('click', gamingLaunch);
    $('gamingGrid').addEventListener('click', (e) => {
        const card = e.target.closest('.gaming-card');
        if (!card) return;
        const idx = parseInt(card.dataset.index, 10);
        if (idx === state.gamingFocusIndex) {
            gamingLaunch();
        } else {
            state.gamingFocusIndex = idx;
            $$('.gaming-card').forEach((c, i) => c.classList.toggle('focused', i === idx));
            updateGamingInfo();
        }
    });

    // Gaming mode clock
    function updateGamingClock() {
        const el = $('gamingClock');
        if (el) {
            const d = new Date();
            el.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
    }
    updateGamingClock();
    setInterval(updateGamingClock, 30000);

    // Show gamepad hints when gamepad is connected
    function updateGamingHintVisibility() {
        const hints = $('gamingHints');
        if (!hints) return;
        hints.classList.toggle('gp-connected', _gp.connected);
    }
    window.addEventListener('gamepadconnected', updateGamingHintVisibility);
    window.addEventListener('gamepaddisconnected', updateGamingHintVisibility);

    // Gaming mode keyboard
    document.addEventListener('keydown', (e) => {
        if (!state.gamingMode) return;
        switch (e.key) {
            case 'Escape': exitGamingMode(); e.preventDefault(); break;
            case 'ArrowLeft':  gamingNavigate('left');  e.preventDefault(); break;
            case 'ArrowRight': gamingNavigate('right'); e.preventDefault(); break;
            case 'ArrowUp':    gamingNavigate('up');    e.preventDefault(); break;
            case 'ArrowDown':  gamingNavigate('down');  e.preventDefault(); break;
            case 'Enter':      gamingLaunch();          e.preventDefault(); break;
            case 'Tab': {
                e.preventDefault();
                const hexes = Array.from(document.querySelectorAll('.console-hex-wrap'));
                const activeIdx = hexes.findIndex(h => h.classList.contains('active'));
                const next = e.shiftKey
                    ? (activeIdx - 1 + hexes.length) % hexes.length
                    : (activeIdx + 1) % hexes.length;
                selectConsoleHex(hexes[next].dataset.tab);
                renderGamingGrid();
                updateGamingInfo();
                updateGamingCategory();
                break;
            }
        }
    });

    // F11 shortcut for gaming mode
    document.addEventListener('keydown', (e) => {
        if (e.key === 'F11' && !state.gamingMode) {
            e.preventDefault();
            enterGamingMode();
        }
    });

    // Exit gaming mode when browser fullscreen exits (only if not using pywebview native)
    document.addEventListener('fullscreenchange', () => {
        if (!document.fullscreenElement && state.gamingMode && !(window.pywebview && window.pywebview.api)) {
            exitGamingMode();
        }
    });

    // Search
    $('btnSearch').addEventListener('click', openSearch);
    $('closeSearch').addEventListener('click', closeSearch);
    $('searchInput').addEventListener('input', debounce(doSearch, 200));

    // CatByte
    $('btnCatbyte').addEventListener('click', toggleCatbyte);
    $('closeCatbyte').addEventListener('click', () => $('catbytePanel').classList.add('hidden'));
    $('catbyteSend').addEventListener('click', sendCatbyteMessage);
    $('catbyteScreenshot').addEventListener('click', sendScreenshot);
    $('catbyteInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendCatbyteMessage(); }
    });
    $('btnNewChat').addEventListener('click', createNewChat);
    $('btnToggleSessions').addEventListener('click', toggleChatSidebar);
    $('closeSidebar').addEventListener('click', closeChatSidebar);
    $('catbyteSidebarBackdrop').addEventListener('click', closeChatSidebar);
    $('catbyteModelPill').addEventListener('click', toggleModelDropdown);
    // Close model dropdown on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.catbyte-model-pill')) {
            $('catbyteModelDropdown').classList.add('hidden');
        }
    });
    // Esc to close sidebar
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && state.chatSidebarOpen) closeChatSidebar();
    });
    setupChatInput();
    $('dismissCatbyteInfo').addEventListener('click', () => $('catbyteInfoOverlay').classList.add('hidden'));
    $('btnOpenCatbyteSettings').addEventListener('click', () => {
        $('catbyteInfoOverlay').classList.add('hidden');
        openSettings();
        switchSettingsTab('catbyte');
    });

    // Detail panel actions
    $('detailLaunch').addEventListener('click', launchSelected);
    $('detailDirectLaunch').addEventListener('click', cycleDirectLaunch);
    $('detailFavorite').addEventListener('click', () => {
        const game = state.filteredGames[state.selectedIndex];
        if (game) toggleFavorite(game.id);
    });
    $('detailCollection').addEventListener('click', toggleCollectionDropdown);
    $('newCollectionBtn').addEventListener('click', createCollectionFromDetail);
    $('newCollectionInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') createCollectionFromDetail(); });

    // Close collection dropdown on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.detail-collection-wrap')) {
            $('collectionDropdown').classList.add('hidden');
        }
    });

    // Settings
    $('btnSettings').addEventListener('click', openSettings);
    $('closeSettings').addEventListener('click', () => $('settingsOverlay').classList.add('hidden'));
    $('settingsTabs').addEventListener('click', (e) => {
        const tab = e.target.closest('.settings-tab');
        if (tab) switchSettingsTab(tab.dataset.stab);
    });

    // Year in Review (full-screen)
    $('btnOpenYearOverlay').addEventListener('click', openYearOverlay);
    $('closeYearOverlay').addEventListener('click', closeYearOverlay);

    // Per-game note textarea
    bindNoteHandlers();

    // Keyboard / controller cheat sheet
    $('closeShortcuts').addEventListener('click', closeShortcuts);
    $('shortcutsOverlay').addEventListener('click', (e) => {
        if (e.target.id === 'shortcutsOverlay') closeShortcuts();
    });

    // Tonight's Pick (CatByte curator)
    $('btnTonightsPick').addEventListener('click', openTonightsPick);
    $('closeTonightsPick').addEventListener('click', closeTonightsPick);
    $('btnRerollTonightsPick').addEventListener('click', () => {
        _renderTonightsPickLoading();
        _fetchTonightsPick();
    });
    $('tonightsPickOverlay').addEventListener('click', (e) => {
        if (e.target.id === 'tonightsPickOverlay') closeTonightsPick();
    });

    // Settings backup / import / reset
    $('btnExportSettings').addEventListener('click', exportSettings);
    $('btnImportSettings').addEventListener('click', () => $('importSettingsFile').click());
    $('importSettingsFile').addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        importSettings(file);
        e.target.value = '';  // allow re-importing the same file
    });
    $('btnResetSettings').addEventListener('click', resetSettings);

    // Settings command palette
    $('settingsSearchTrigger').addEventListener('click', openSettingsPalette);
    $('settingsSearchOverlay').addEventListener('click', (e) => {
        if (e.target.id === 'settingsSearchOverlay') closeSettingsPalette();
    });
    $('settingsSearchInput').addEventListener('input', (e) => {
        renderSettingsSearchResults(e.target.value);
    });
    $('settingsSearchInput').addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            _searchActiveIdx = Math.min(_searchResults.length - 1, _searchActiveIdx + 1);
            updatePaletteActiveRow();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            _searchActiveIdx = Math.max(0, _searchActiveIdx - 1);
            updatePaletteActiveRow();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            selectSettingsSearchResult();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            closeSettingsPalette();
        }
    });
    $('addRomDir').addEventListener('click', addRomDir);
    $('addLocalDir').addEventListener('click', addLocalDir);
    $('addBiosDir').addEventListener('click', addBiosDir);
    $('btnRescan').addEventListener('click', rescanLibrary);
    $('btnConnectSteam').addEventListener('click', connectSteam);
    // Settings toggles are wired generically via bindSettingToggles() (data-setting attrs)

    // Browse buttons — native folder dialogs via pywebview bridge
    $('browseRomDir').addEventListener('click', () => browseFolder('romDirInput'));
    $('browseLocalDir').addEventListener('click', () => browseFolder('localDirInput'));
    $('browseBiosDir').addEventListener('click', () => browseFolder('biosDirInput'));
    $('browseRetroarch').addEventListener('click', () => browseFolder('retroarchPathInput'));
    $('browseLaunchbox').addEventListener('click', () => browseFolder('launchboxPathInput'));
    $('saveLaunchboxPath').addEventListener('click', saveLaunchboxPath);
    $('saveRetroarch').addEventListener('click', saveRetroarchPath);
    $('testRetroarch').addEventListener('click', testRetroarch);
    $('testLaunchbox').addEventListener('click', testLaunchbox);
    $('emuAutoSetup').addEventListener('click', startEmuSetup);

    // Save original placeholders for browse fallback
    ['romDirInput', 'localDirInput', 'biosDirInput'].forEach(id => {
        const el = $(id);
        if (el) el.dataset.originalPlaceholder = el.placeholder;
    });

    // Input validation on type
    $('romDirInput').addEventListener('input', () => validateDirInput('romDirInput'));
    $('localDirInput').addEventListener('input', () => validateDirInput('localDirInput'));

    // CatByte test connection
    bindCatbyteTest();

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd+K — open the settings command palette from anywhere.
        // Handled before the input-focus guard so it works even from text fields.
        if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            openSettingsSearch();
            return;
        }
        // Ctrl+Shift+Y — open Your YancoHub Year
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && !e.altKey && e.key.toLowerCase() === 'y') {
            e.preventDefault();
            openYearOverlay();
            return;
        }
        // "?" (Shift+/) — show the keyboard / controller cheat sheet.
        // Skipped when typing into a text input so "?" remains a literal character there.
        if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) {
            const t = e.target;
            const inField = t && (['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName) || t.isContentEditable);
            if (!inField) {
                e.preventDefault();
                toggleShortcuts();
                return;
            }
        }

        // Don't navigate if a text input is focused
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) ||
            e.target.isContentEditable) return;

        if (e.key === 'ArrowLeft')  { e.preventDefault(); navigateCarousel(-1); }
        if (e.key === 'ArrowRight') { e.preventDefault(); navigateCarousel(1); }
        if (e.key === 'Enter')      { e.preventDefault(); launchSelected(); }

        if (e.ctrlKey && e.key === 'f') { e.preventDefault(); openSearch(); }
        if (e.ctrlKey && e.key === 'b') { e.preventDefault(); toggleCatbyte(); }
        if (e.ctrlKey && e.key === ',') { e.preventDefault(); openSettings(); }
        if (e.ctrlKey && e.shiftKey && e.key === 'S') { e.preventDefault(); sendScreenshot(); }

        if (e.key === 'Escape') {
            // Palette closes before its parent settings overlay
            if (!$('settingsSearchOverlay').classList.contains('hidden')) { closeSettingsPalette(); return; }
            if (!$('shortcutsOverlay').classList.contains('hidden')) { closeShortcuts(); return; }
            if (!$('yearOverlay').classList.contains('hidden')) { closeYearOverlay(); return; }
            if (!$('tonightsPickOverlay').classList.contains('hidden')) { closeTonightsPick(); return; }
            if (!$('moodOverlay').classList.contains('hidden')) { $('moodOverlay').classList.add('hidden'); return; }
            if (!$('catbyteInfoOverlay').classList.contains('hidden')) $('catbyteInfoOverlay').classList.add('hidden');
            else if (!$('searchOverlay').classList.contains('hidden')) closeSearch();
            else if (!$('settingsOverlay').classList.contains('hidden')) $('settingsOverlay').classList.add('hidden');
            else if (!$('catbytePanel').classList.contains('hidden')) $('catbytePanel').classList.add('hidden');
        }

        // F for favorite toggle (only when no overlay/panel is open)
        if (e.key === 'f' && !e.ctrlKey && !e.altKey &&
            $('searchOverlay').classList.contains('hidden') &&
            $('settingsOverlay').classList.contains('hidden') &&
            $('catbytePanel').classList.contains('hidden')) {
            const game = state.filteredGames[state.selectedIndex];
            if (game) toggleFavorite(game.id);
        }
    });

    // Mouse wheel on carousel for navigation
    $('carouselContainer').addEventListener('wheel', (e) => {
        e.preventDefault();
        if (e.deltaY > 0 || e.deltaX > 0) navigateCarousel(1);
        else navigateCarousel(-1);
    }, { passive: false });

    // Mood picker
    $('btnMoodPicker').addEventListener('click', () => $('moodOverlay').classList.remove('hidden'));
    $('closeMood').addEventListener('click', () => $('moodOverlay').classList.add('hidden'));
    $('moodLabelClear').addEventListener('click', clearMoodFilter);
    $$('.mood-card').forEach(card => {
        card.addEventListener('click', () => {
            $('moodOverlay').classList.add('hidden');
            applyMoodFilter(card.dataset.mood);
        });
    });

    // Close overlays on backdrop click
    $('searchOverlay').addEventListener('click', (e) => { if (e.target === $('searchOverlay')) closeSearch(); });
    $('settingsOverlay').addEventListener('click', (e) => { if (e.target === $('settingsOverlay')) $('settingsOverlay').classList.add('hidden'); });
    $('moodOverlay').addEventListener('click', (e) => { if (e.target === $('moodOverlay')) $('moodOverlay').classList.add('hidden'); });
}

// ── Game Launch ────────────────────────────────────────────────────────────

async function launchGame(gameId) {
    const game = state.games.find(g => g.id === gameId);
    if (!game) return;

    // Check if this is a retro game with a built-in emulator
    if (game.source === 'retro' && game.system && typeof isBuiltinSystem === 'function' && isBuiltinSystem(game.system)) {
        // Set the pause menu game name
        const pauseGame = document.getElementById('emuPauseGame');
        if (pauseGame) pauseGame.textContent = game.name;

        // Launch in built-in emulator
        launchBuiltinEmulator(game);
        return;
    }

    // External launch (Steam, Epic, native emulators, etc.)
    $('launchText').textContent = `Launching ${game.name}...`;
    $('launchOverlay').classList.remove('hidden');

    try {
        const r = await fetch(`/api/launch/${gameId}`, { method: 'POST' });
        const d = await r.json();
        if (!r.ok) $('launchText').textContent = `Failed: ${d.error || 'Unknown error'}`;
        setTimeout(() => $('launchOverlay').classList.add('hidden'), 3000);
    } catch {
        $('launchText').textContent = 'Launch failed!';
        setTimeout(() => $('launchOverlay').classList.add('hidden'), 3000);
    }
}

async function toggleFavorite(gameId) {
    try {
        const d = await fetchJSON('/api/favorites/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_id: gameId }),
        });
        if (d.is_favorite) state.favorites.add(gameId);
        else state.favorites.delete(gameId);
        // Refresh carousel to update star badge
        renderCarousel();
        updateGameInfo();
    } catch (e) { console.warn('toggleFavorite failed:', e); }
}

// ── Collection Dropdown (detail panel) ────────────────────────────────────

async function toggleCollectionDropdown(e) {
    e.stopPropagation();
    const dd = $('collectionDropdown');
    if (!dd.classList.contains('hidden')) {
        dd.classList.add('hidden');
        return;
    }

    const game = state.filteredGames[state.selectedIndex];
    if (!game) return;

    // Build the list
    const collections = state.collections || {};
    const list = $('collectionList');
    list.innerHTML = '';

    for (const [name, games] of Object.entries(collections)) {
        const inCol = (games || []).includes(game.id);
        const item = document.createElement('div');
        item.className = 'detail-collection-item';
        item.innerHTML = `<span class="check">${inCol ? '\u2713' : ''}</span><span>${escapeHtml(name)}</span>`;
        item.addEventListener('click', async () => {
            try {
                if (inCol) {
                    await fetch(`/api/collections/${encodeURIComponent(name)}/games/${encodeURIComponent(game.id)}`, { method: 'DELETE' });
                } else {
                    await fetch(`/api/collections/${encodeURIComponent(name)}/games`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ game_id: game.id }),
                    });
                }
            } catch (e2) { console.warn('Toggle collection game failed:', e2); }
            await loadCollections();
            toggleCollectionDropdown(e);
        });
        list.appendChild(item);
    }

    $('newCollectionInput').value = '';
    dd.classList.remove('hidden');
}

async function createCollectionFromDetail() {
    const input = $('newCollectionInput');
    const name = input.value.trim();
    if (!name) return;

    const game = state.filteredGames[state.selectedIndex];
    try {
        await fetch('/api/collections', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        if (game) {
            await fetch(`/api/collections/${encodeURIComponent(name)}/games`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ game_id: game.id }),
            });
        }
        await loadCollections();
        input.value = '';
        $('collectionDropdown').classList.add('hidden');
    } catch (e) { console.warn('createCollectionFromDetail failed:', e); }
}

// ── Search ─────────────────────────────────────────────────────────────────

function openSearch() {
    $('searchOverlay').classList.remove('hidden');
    $('searchInput').value = '';
    $('searchResults').innerHTML = '';
    $('searchInput').focus();
}

function closeSearch() { $('searchOverlay').classList.add('hidden'); }

async function doSearch() {
    const q = $('searchInput').value.trim();
    if (!q) { $('searchResults').innerHTML = ''; return; }

    try {
        const results = await fetchJSON(`/api/search?q=${encodeURIComponent(q)}`);

        $('searchResults').innerHTML = results.map(g => `
            <div class="search-result" data-id="${escapeAttr(g.id)}">
                <span class="search-result-name">${escapeHtml(g.name)}</span>
                <span class="search-result-source">${g.system_name || g.source}</span>
            </div>
        `).join('');

        $('searchResults').querySelectorAll('.search-result').forEach(el => {
            el.addEventListener('click', () => {
                closeSearch();
                // Switch to all tab and find game
                selectConsoleHex('all');

                // Navigate to the game
                const idx = state.filteredGames.findIndex(g => g.id === el.dataset.id);
                if (idx >= 0) {
                    state.selectedIndex = idx;
                    updateCarousel();
                    updateGameInfo();
                }
            });
        });
    } catch (e) { console.warn('doSearch failed:', e); }
}

// ── CatByte ────────────────────────────────────────────────────────────────

// ── CatByte: Panel Toggle ─────────────────────────────────────────────────

async function toggleCatbyte() {
    // Use the overlay window instead of the in-app panel
    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_catbyte_overlay) {
        window.pywebview.api.toggle_catbyte_overlay();
    } else {
        // Fallback for browser dev mode: open in-app panel
        $('catbytePanel').classList.toggle('hidden');
        if (!$('catbytePanel').classList.contains('hidden')) {
            checkCatbyteStatus();
            loadChatModels();
            await loadChatSessions();
            if (!state.chatSessionId) {
                const sessions = state.chatSessions;
                if (sessions.length > 0) {
                    const data = await fetchJSON('/api/catbyte/sessions');
                    const activeId = data.active_session_id;
                    if (activeId && sessions.find(s => s.id === activeId)) {
                        await selectChatSession(activeId);
                    } else {
                        await selectChatSession(sessions[0].id);
                    }
                } else {
                    renderEmptyState();
                }
            }
            $('catbyteInput').focus();
        }
    }
}

// ── CatByte: Session Management ───────────────────────────────────────────

async function loadChatSessions() {
    try {
        const data = await fetchJSON('/api/catbyte/sessions');
        state.chatSessions = data.sessions || [];
    } catch (e) { console.warn('loadChatSessions failed:', e); state.chatSessions = []; }
    renderChatSidebar();
}

function renderChatSidebar() {
    const list = $('catbyteSessionList');
    if (!list) return;
    if (state.chatSessions.length === 0) {
        list.innerHTML = '<div style="padding:16px;text-align:center;font-size:11px;color:var(--text-dim)">No conversations yet</div>';
        return;
    }
    list.innerHTML = state.chatSessions.map(s => {
        const active = s.id === state.chatSessionId ? ' active' : '';
        const pinIcon = s.pinned ? '<i class="ph ph-push-pin session-pin"></i>' : '';
        const timeStr = formatTimeAgo(s.updated_at);
        const preview = escapeHtml((s.preview || 'New conversation').slice(0, 40));
        return `<div class="catbyte-session-item${active}" data-session-id="${escapeAttr(s.id)}">
            ${pinIcon}
            <div class="session-info">
                <div class="session-title">${escapeHtml(s.title)}</div>
                <div class="session-meta">${preview} &middot; ${timeStr}</div>
            </div>
            <div class="session-actions">
                <button class="session-action-btn" data-action="pin" title="${s.pinned ? 'Unpin' : 'Pin'}"><i class="ph ph-push-pin"></i></button>
                <button class="session-action-btn" data-action="delete" title="Delete"><i class="ph ph-trash"></i></button>
            </div>
        </div>`;
    }).join('');

    // Bind clicks
    list.querySelectorAll('.catbyte-session-item').forEach(el => {
        el.addEventListener('click', (e) => {
            // Don't select if action button clicked
            if (e.target.closest('.session-action-btn')) return;
            selectChatSession(el.dataset.sessionId);
            closeChatSidebar();
        });
    });
    list.querySelectorAll('.session-action-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const sid = btn.closest('.catbyte-session-item').dataset.sessionId;
            if (btn.dataset.action === 'delete') {
                await deleteChatSession(sid);
            } else if (btn.dataset.action === 'pin') {
                try {
                    await fetch(`/api/catbyte/sessions/${sid}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ pinned: true }),
                    });
                } catch (e) { console.warn('Pin session failed:', e); }
                await loadChatSessions();
            }
        });
    });
}

async function selectChatSession(sessionId) {
    try {
        const session = await fetchJSON(`/api/catbyte/sessions/${sessionId}`);
        if (session.error) return;

        state.chatSessionId = sessionId;
        state.chatHistory = (session.messages || []).map(m => ({ role: m.role, content: m.content }));

        // Update header title
        const titleEl = $('catbyteSessionTitle');
        if (titleEl) titleEl.textContent = session.title || 'CatByte';

        // Render messages
        const msgContainer = $('catbyteMessages');
        msgContainer.innerHTML = '';

        if (session.messages && session.messages.length > 0) {
            renderMessagesWithGrouping(session.messages);
        } else {
            renderEmptyState();
        }

        // Mark active on server
        fetch(`/api/catbyte/sessions/${sessionId}/active`, { method: 'POST' }).catch(e => console.warn('Set active session failed:', e));

        // Update sidebar active state
        renderChatSidebar();
    } catch (err) {
        console.error('Failed to load session:', err);
    }
}

function renderMessagesWithGrouping(messages) {
    const container = $('catbyteMessages');
    container.innerHTML = '';
    let lastRole = null;
    let lastDate = null;

    messages.forEach((m, i) => {
        const msgDate = formatDateLabel(m.ts);
        if (msgDate !== lastDate) {
            const sep = document.createElement('div');
            sep.className = 'chat-date-sep';
            sep.textContent = msgDate;
            container.appendChild(sep);
            lastDate = msgDate;
            lastRole = null; // Reset grouping after date separator
        }

        const isGroupCont = m.role === lastRole;
        const role = m.role === 'assistant' ? 'bot' : 'user';
        const div = document.createElement('div');
        div.className = `chat-msg ${role}${isGroupCont ? ' group-cont' : ''}`;
        // Staggered entrance animation for session load
        div.style.animationDelay = `${Math.min(i * 40, 400)}ms`;
        div.classList.add('animate');

        const bubbleContent = role === 'bot' ? renderMarkdown(m.content) : escapeHtml(m.content);
        const timeStr = formatMessageTime(m.ts);
        div.innerHTML = `<div class="chat-bubble">${bubbleContent}</div>
            <div class="chat-bubble-time">${timeStr}</div>`;
        container.appendChild(div);
        lastRole = m.role;
    });

    // Scroll to bottom
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

async function createNewChat() {
    const game = state.filteredGames[state.selectedIndex];
    try {
        const session = await fetchJSON('/api/catbyte/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_context: game?.name || '',
                model: state.catbyteCurrentModel,
            }),
        });
        state.chatSessionId = session.id;
        state.chatHistory = [];

        $('catbyteSessionTitle').textContent = session.title || 'New conversation';
        renderEmptyState();
        await loadChatSessions();
        closeChatSidebar();
        $('catbyteInput').focus();
    } catch (err) {
        console.error('Failed to create session:', err);
    }
}

async function deleteChatSession(sessionId) {
    try {
        const delResp = await fetch(`/api/catbyte/sessions/${sessionId}`, { method: 'DELETE' });
        if (!delResp.ok) console.warn('Delete session failed:', delResp.status);
        if (state.chatSessionId === sessionId) {
            state.chatSessionId = null;
            state.chatHistory = [];
            $('catbyteMessages').innerHTML = '';
        }
        await loadChatSessions();
        // If deleted the active session, load another or show empty
        if (!state.chatSessionId && state.chatSessions.length > 0) {
            await selectChatSession(state.chatSessions[0].id);
        } else if (!state.chatSessionId) {
            renderEmptyState();
        }
    } catch (err) {
        console.error('Failed to delete session:', err);
    }
}

// ── CatByte: Sidebar Toggle ──────────────────────────────────────���───────

function toggleChatSidebar() {
    state.chatSidebarOpen = !state.chatSidebarOpen;
    $('catbyteSidebar').classList.toggle('hidden', !state.chatSidebarOpen);
    $('catbyteSidebarBackdrop').classList.toggle('hidden', !state.chatSidebarOpen);
}

function closeChatSidebar() {
    state.chatSidebarOpen = false;
    $('catbyteSidebar').classList.add('hidden');
    $('catbyteSidebarBackdrop').classList.add('hidden');
}

// ── CatByte: Model Dropdown ──────────────────────────────────────────────

async function loadChatModels() {
    try {
        const [models, config] = await Promise.all([
            fetchJSON('/api/catbyte/models'),
            fetchJSON('/api/catbyte/config'),
        ]);
        state.catbyteModels = models;
        // Use configured model, or fall back to first available from backend
        state.catbyteCurrentModel = config.model || (state.catbyteModels[0] || '');
        updateModelPill();
    } catch (e) {
        console.warn('loadChatModels failed:', e);
        state.catbyteModels = [];
    }
}

function updateModelPill() {
    const nameEl = $('catbyteModelName');
    if (!nameEl) return;
    let display = state.catbyteCurrentModel || 'model';
    nameEl.textContent = display.length > 16 ? display.slice(0, 14) + '\u2026' : display;
    nameEl.title = state.catbyteCurrentModel;
}

async function toggleModelDropdown(e) {
    e.stopPropagation();
    const dd = $('catbyteModelDropdown');
    const wasHidden = dd.classList.contains('hidden');
    dd.classList.toggle('hidden');
    if (wasHidden) {
        dd.innerHTML = '<div class="catbyte-model-option" style="color:var(--text-dim);cursor:default">Loading...</div>';
        try {
            const [models, config] = await Promise.all([
                fetchJSON('/api/catbyte/models'),
                fetchJSON('/api/catbyte/config'),
            ]);
            state.catbyteModels = models;
        } catch (e) { console.warn('toggleModelDropdown load failed:', e); state.catbyteModels = []; }
        renderModelDropdown();
    }
}

function renderModelDropdown() {
    const dd = $('catbyteModelDropdown');
    if (state.catbyteModels.length === 0) {
        dd.innerHTML = '<div class="catbyte-model-option" style="color:var(--text-dim);cursor:default">No models found</div>';
        return;
    }

    dd.innerHTML = state.catbyteModels.slice(0, 20).map(m => {
        const active = m === state.catbyteCurrentModel ? ' active' : '';
        return `<div class="catbyte-model-option${active}" data-model="${escapeAttr(m)}">${escapeHtml(m)}</div>`;
    }).join('');

    dd.querySelectorAll('.catbyte-model-option[data-model]').forEach(opt => {
        opt.addEventListener('click', async (e) => {
            e.stopPropagation();
            const model = opt.dataset.model;
            if (!model) return;
            state.catbyteCurrentModel = model;
            updateModelPill();
            dd.classList.add('hidden');
            try {
                await fetch('/api/catbyte/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model }),
                });
            } catch (e) { console.warn('Set model failed:', e); }
        });
    });
}

// ── CatByte: Send Message ─────────────────────────────────────────────────

async function sendCatbyteMessage() {
    const input = $('catbyteInput');
    const msg = input.value.trim();
    if (!msg) return;

    // Auto-create session if needed
    if (!state.chatSessionId) {
        await createNewChat();
        // Clear empty state if present
        const empty = $('catbyteMessages').querySelector('.catbyte-empty');
        if (empty) empty.remove();
    }

    appendChat('user', msg, Date.now() / 1000);
    input.value = '';
    input.style.height = 'auto';
    state.chatHistory.push({ role: 'user', content: msg });

    showTypingIndicator();

    const game = state.filteredGames[state.selectedIndex];
    try {
        const d = await fetchJSON('/api/catbyte/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: msg,
                session_id: state.chatSessionId,
                game_context: game?.name || '',
            }),
        });
        hideTypingIndicator();
        appendChat('bot', d.response, Date.now() / 1000);
        state.chatHistory.push({ role: 'assistant', content: d.response });

        // Refresh sidebar for updated title/timestamp
        loadChatSessions();
    } catch {
        hideTypingIndicator();
        appendChat('bot', '\uD83D\uDE3F Connection error \u2014 check your AI backend in Settings.', Date.now() / 1000);
    }
}

function appendChat(role, text, ts) {
    const container = $('catbyteMessages');
    // Remove empty state if present
    const empty = container.querySelector('.catbyte-empty');
    if (empty) empty.remove();

    // Check for message grouping
    const lastMsg = container.querySelector('.chat-msg:last-of-type');
    const lastRole = lastMsg?.classList.contains('bot') ? 'bot' : (lastMsg?.classList.contains('user') ? 'user' : null);
    const currentRole = role === 'assistant' ? 'bot' : role;
    const isGroupCont = lastRole === currentRole;

    const div = document.createElement('div');
    div.className = `chat-msg ${currentRole}${isGroupCont ? ' group-cont' : ''} animate`;

    const bubbleContent = currentRole === 'bot' ? renderMarkdown(text) : escapeHtml(text);
    const timeStr = ts ? formatMessageTime(ts) : '';
    div.innerHTML = `<div class="chat-bubble">${bubbleContent}</div>
        <div class="chat-bubble-time">${timeStr}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// ── CatByte: Smart Features ───────────────────────────────────────────────

function showTypingIndicator() {
    const container = $('catbyteMessages');
    const existing = container.querySelector('.typing-wrapper');
    if (existing) return;
    const div = document.createElement('div');
    div.className = 'chat-msg bot animate typing-wrapper';
    div.innerHTML = '<div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>';
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
    const el = $('catbyteMessages').querySelector('.typing-wrapper');
    if (el) el.remove();
}

function renderEmptyState() {
    const container = $('catbyteMessages');
    container.innerHTML = `<div class="catbyte-empty">
        <div class="catbyte-empty-avatar">😺</div>
        <h3>Hey there, gamer!</h3>
        <p>I'm CatByte, your gaming companion.<br>Ask me anything about your games!</p>
        <div class="catbyte-quick-actions">
            <button class="catbyte-quick-btn" data-prompt="Give me tips for the game I'm playing">Game tips</button>
            <button class="catbyte-quick-btn" data-prompt="Help me optimize my PC for better gaming performance">Performance help</button>
            <button class="catbyte-quick-btn" data-prompt="Help me set up retro emulation">Retro setup</button>
        </div>
    </div>`;
    container.querySelectorAll('.catbyte-quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $('catbyteInput').value = btn.dataset.prompt;
            sendCatbyteMessage();
        });
    });
}

function renderMarkdown(text) {
    let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Code blocks (``` ... ```)
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g,
        '<pre class="chat-codeblock"><code class="lang-$1">$2</code></pre>');
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code class="chat-code">$1</code>');
    // Bold + italic
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Headers
    html = html.replace(/^### (.+)$/gm, '<h4 class="chat-heading">$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 class="chat-heading">$1</h3>');
    // Unordered lists
    html = html.replace(/^[*\-] (.+)$/gm, '<li>$1</li>');
    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, url) => {
        if (/^https?:|^mailto:/i.test(url)) {
            return `<a href="${url}" target="_blank" rel="noopener">${text}</a>`;
        }
        return text;
    });
    // Double newline → paragraph break
    html = html.replace(/\n\n/g, '<br><br>');
    // Single newline → line break (but not inside pre)
    html = html.replace(/\n/g, '<br>');

    return html;
}

// ── CatByte: Time Formatting ──────────────────────────────────────────────

function formatMessageTime(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const now = new Date();
    const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    if (d.toDateString() === now.toDateString()) return time;
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ', ' + time;
}

function formatDateLabel(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) return 'Today';
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function formatTimeAgo(ts) {
    if (!ts) return '';
    const now = Date.now() / 1000;
    const diff = now - ts;
    if (diff < 60) return 'now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 172800) return 'yesterday';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    return new Date(ts * 1000).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

// ── CatByte: Textarea Auto-expand ─────────────────────────────────────────

function setupChatInput() {
    const textarea = $('catbyteInput');
    if (!textarea) return;
    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    });
}

// ── CatByte: Screenshot ───────────────────────────────────────────────────

async function sendScreenshot() {
    if (!state.catbyteOnline) return;

    try {
        const canvas = document.createElement('canvas');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        const ctx = canvas.getContext('2d');

        const starfield = document.getElementById('starfield');
        if (starfield) ctx.drawImage(starfield, 0, 0);

        const emuCanvas = document.querySelector('#emuGame canvas');
        if (emuCanvas) {
            ctx.drawImage(emuCanvas, 0, 0, canvas.width, canvas.height);
        }

        const base64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];

        const question = prompt('What do you want to ask CatByte about this screenshot?');
        if (!question) return;

        if ($('catbytePanel').classList.contains('hidden')) {
            $('catbytePanel').classList.remove('hidden');
        }

        // Auto-create session if needed
        if (!state.chatSessionId) {
            await createNewChat();
        }

        appendChat('user', '\uD83D\uDCF8 ' + question, Date.now() / 1000);
        state.chatHistory.push({ role: 'user', content: '[Screenshot] ' + question });

        showTypingIndicator();

        const game = state.filteredGames[state.selectedIndex];
        const d = await fetchJSON('/api/catbyte/chat-vision', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: question,
                image: base64,
                session_id: state.chatSessionId,
                game_context: game?.name || '',
            }),
        });
        hideTypingIndicator();
        appendChat('bot', d.response, Date.now() / 1000);
        state.chatHistory.push({ role: 'assistant', content: d.response });
        loadChatSessions();
    } catch (err) {
        hideTypingIndicator();
        console.error('Screenshot capture failed:', err);
        appendChat('bot', '\uD83D\uDE3F Screenshot capture failed. Try again!', Date.now() / 1000);
    }
}

// ── Settings ───────────────────────────────────────────────────────────────

async function connectSteam() {
    const apiKey = $('steamApiKey').value.trim();
    const steamId = $('steamIdInput').value.trim();
    const status = $('steamConnectStatus');

    if (!steamId) {
        status.style.color = 'var(--danger)';
        status.textContent = 'Steam ID is required (API key is optional)';
        return;
    }

    status.style.color = 'var(--accent)';
    status.textContent = apiKey ? 'Connecting with full library...' : 'Connecting...';

    try {
        const body = { steam_id: steamId };
        if (apiKey) body.api_key = apiKey;
        const r = await fetch('/api/accounts/steam/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const d = await r.json();

        if (r.ok) {
            status.style.color = 'var(--success)';
            const msg = d.has_api_key
                ? `Connected as ${d.persona_name}! Full library loading...`
                : `Connected as ${d.persona_name}! Installed games ready.`;
            status.textContent = msg;
            $('steamConnectSection').classList.add('hidden');
            renderSettings();
            setTimeout(async () => { await loadGames(); applyFilter(); }, 5000);
        } else {
            status.style.color = 'var(--danger)';
            status.textContent = d.error || 'Connection failed';
        }
    } catch {
        status.style.color = 'var(--danger)';
        status.textContent = 'Network error';
    }
}

// ── Browse Folder (pywebview native dialog) ───────────────────────────────

async function browseFolder(inputId) {
    // pywebview.api is only available when running in pywebview desktop window
    if (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.browse_folder) {
        try {
            const currentVal = $(inputId)?.value || '';
            const path = await pywebview.api.browse_folder('Select Folder', currentVal);
            if (path && $(inputId)) {
                $(inputId).value = path;
                // Trigger validation
                validateDirInput(inputId);
            }
        } catch (e) {
            console.warn('Browse dialog failed:', e);
        }
    } else {
        // Fallback for browser dev mode — flash hint
        const input = $(inputId);
        if (input) {
            input.placeholder = 'Paste a folder path (browse available in desktop mode)';
            input.focus();
            setTimeout(() => {
                input.placeholder = input.dataset.originalPlaceholder || 'Path...';
            }, 3000);
        }
    }
}

async function browseFile(inputId, fileTypes) {
    if (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.browse_file) {
        try {
            const path = await pywebview.api.browse_file('Select File', '', fileTypes || []);
            if (path && $(inputId)) {
                $(inputId).value = path;
            }
        } catch (e) {
            console.warn('Browse dialog failed:', e);
        }
    }
}

// ── Directory Validation ──────────────────────────────────────────────────

let _validateTimer = null;

function validateDirInput(inputId) {
    const input = $(inputId);
    if (!input) return;
    const path = input.value.trim();
    const validationId = inputId.replace('Input', 'Validation').replace('Dir', 'Dir');

    const validationEl = $(validationId);
    if (!validationEl) return;

    if (!path) {
        validationEl.className = 'dir-validation';
        validationEl.textContent = '';
        return;
    }

    clearTimeout(_validateTimer);
    validationEl.className = 'dir-validation checking';
    validationEl.textContent = 'Checking...';

    _validateTimer = setTimeout(async () => {
        try {
            const d = await fetchJSON('/api/validate-path', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path }),
            });
            if (d.valid) {
                validationEl.className = 'dir-validation valid';
                validationEl.textContent = `\u2713 Valid \u2014 ${d.message}`;
            } else {
                validationEl.className = 'dir-validation invalid';
                validationEl.textContent = `\u2717 ${d.message}`;
            }
        } catch {
            validationEl.className = 'dir-validation invalid';
            validationEl.textContent = '\u2717 Could not validate';
        }
    }, 300);
}

async function openSettings() {
    $('settingsOverlay').classList.remove('hidden');
    // Default to first tab
    switchSettingsTab('accounts');
    await renderSettings();
}

function switchSettingsTab(tabId) {
    document.querySelectorAll('.settings-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.stab === tabId);
    });
    document.querySelectorAll('.settings-pane').forEach(p => {
        p.classList.toggle('active', p.id === 'settingsPane-' + tabId);
    });
}

async function renderSettings() {
    await Promise.all([
        renderAccountsTab(),
        renderDirectoriesTab(),
        renderEmulationTab(),
        renderCatbyteTab(),
    ]);
    // Re-index the palette after each render so newly created cards are searchable.
    buildSettingsIndex();
}

// ── Settings Command Palette ─────────────────────────────────────────────────

let _settingsIndex = [];
let _searchResults = [];
let _searchActiveIdx = 0;

/** Build a searchable index of every settings card + toggle row across all panes. */
function buildSettingsIndex() {
    const entries = [];
    document.querySelectorAll('.settings-pane').forEach((pane) => {
        const tabId = pane.id.replace('settingsPane-', '');
        pane.querySelectorAll('.settings-card').forEach((card) => {
            const h4 = card.querySelector('.settings-card-header h4');
            const cardHint = card.querySelector('.settings-card-hint');
            if (h4 && h4.textContent.trim()) {
                entries.push({
                    title: h4.textContent.trim(),
                    hint: cardHint ? cardHint.textContent.trim() : '',
                    tab: tabId,
                    element: card,
                });
            }
            card.querySelectorAll('.settings-toggle-row').forEach((row) => {
                const labelEl = row.querySelector('.settings-toggle-label > span:first-child');
                const rowHint = row.querySelector('.settings-toggle-hint');
                if (labelEl && labelEl.textContent.trim()) {
                    entries.push({
                        title: labelEl.textContent.trim(),
                        hint: rowHint ? rowHint.textContent.trim() : '',
                        tab: tabId,
                        element: row,
                    });
                }
            });
        });
    });
    _settingsIndex = entries;
    return entries;
}

function _paletteEscape(s) {
    return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function _paletteHighlight(text, q) {
    if (!q) return _paletteEscape(text);
    const lower = text.toLowerCase();
    const needle = q.toLowerCase();
    let out = '';
    let i = 0;
    while (i < text.length) {
        const idx = lower.indexOf(needle, i);
        if (idx < 0) { out += _paletteEscape(text.slice(i)); break; }
        out += _paletteEscape(text.slice(i, idx));
        out += '<mark>' + _paletteEscape(text.slice(idx, idx + needle.length)) + '</mark>';
        i = idx + needle.length;
    }
    return out;
}

function _scoreEntry(entry, q) {
    const t = entry.title.toLowerCase();
    const h = entry.hint.toLowerCase();
    if (t === q) return 100;
    if (t.startsWith(q)) return 80;
    const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (new RegExp('\\b' + escaped).test(t)) return 60;
    if (t.includes(q)) return 50;
    if (h.includes(q)) return 25;
    return 0;
}

function filterSettings(query) {
    const q = query.trim().toLowerCase();
    if (!q) return _settingsIndex.slice(0, 12);
    return _settingsIndex
        .map((e) => ({ e, s: _scoreEntry(e, q) }))
        .filter((x) => x.s > 0)
        .sort((a, b) => b.s - a.s)
        .slice(0, 12)
        .map((x) => x.e);
}

function renderSettingsSearchResults(query) {
    _searchResults = filterSettings(query);
    _searchActiveIdx = 0;
    const container = $('settingsSearchResults');
    if (!_searchResults.length) {
        container.innerHTML = `<div class="settings-search-empty">No settings match "${_paletteEscape(query)}"</div>`;
        return;
    }
    container.innerHTML = _searchResults.map((e, i) => `
        <div class="settings-search-result ${i === 0 ? 'active' : ''}" data-idx="${i}" role="option">
            <div class="settings-search-result-body">
                <div class="settings-search-result-title">${_paletteHighlight(e.title, query)}</div>
                ${e.hint ? `<div class="settings-search-result-hint">${_paletteHighlight(e.hint, query)}</div>` : ''}
            </div>
            <span class="settings-search-result-tab">${_paletteEscape(e.tab)}</span>
        </div>
    `).join('');
    container.querySelectorAll('.settings-search-result').forEach((row) => {
        row.addEventListener('click', () => {
            _searchActiveIdx = parseInt(row.dataset.idx, 10);
            selectSettingsSearchResult();
        });
        row.addEventListener('mouseenter', () => {
            _searchActiveIdx = parseInt(row.dataset.idx, 10);
            updatePaletteActiveRow();
        });
    });
}

function updatePaletteActiveRow() {
    document.querySelectorAll('#settingsSearchResults .settings-search-result').forEach((row, i) => {
        row.classList.toggle('active', i === _searchActiveIdx);
        if (i === _searchActiveIdx) row.scrollIntoView({ block: 'nearest' });
    });
}

function selectSettingsSearchResult() {
    const entry = _searchResults[_searchActiveIdx];
    if (!entry) return;
    closeSettingsPalette();
    if ($('settingsOverlay').classList.contains('hidden')) openSettings();
    switchSettingsTab(entry.tab);
    setTimeout(() => {
        entry.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        entry.element.classList.remove('setting-flash');
        void entry.element.offsetWidth;  // restart animation on repeat
        entry.element.classList.add('setting-flash');
        setTimeout(() => entry.element.classList.remove('setting-flash'), 1700);
    }, 60);
}

function openSettingsPalette() {
    if (!_settingsIndex.length) buildSettingsIndex();
    const overlay = $('settingsSearchOverlay');
    overlay.classList.remove('hidden');
    const input = $('settingsSearchInput');
    input.value = '';
    renderSettingsSearchResults('');
    setTimeout(() => input.focus(), 0);
}

function closeSettingsPalette() {
    $('settingsSearchOverlay').classList.add('hidden');
}

/** Open settings first (if closed), then open the palette. Used by Ctrl+K. */
async function openSettingsSearch() {
    if ($('settingsOverlay').classList.contains('hidden')) {
        await openSettings();
    }
    buildSettingsIndex();
    openSettingsPalette();
}

// ── Settings focus navigation (controller-first / keyboard) ─────────────────

/** Focusable interactive controls within the currently active settings pane. */
function _focusableInSettings() {
    const pane = document.querySelector('.settings-pane.active');
    if (!pane) return [];
    const sel = 'button:not([disabled]):not([tabindex="-1"]),'
              + ' input:not([disabled]):not([type="hidden"]),'
              + ' select:not([disabled]),'
              + ' textarea:not([disabled]),'
              + ' a[href],'
              + ' [tabindex]:not([tabindex="-1"])';
    return Array.from(pane.querySelectorAll(sel)).filter((el) => {
        if (el.offsetParent === null) return false;  // hidden via display:none
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
    });
}

/** Move focus to the next/prev focusable settings control. direction: -1 | 1.
 *  Adds a .gp-focus class so the focus ring shows for gamepad users (Chromium
 *  withholds :focus-visible from script-driven focus). */
function focusSettingControl(direction) {
    const list = _focusableInSettings();
    if (!list.length) return;
    const active = document.activeElement;
    const idx = list.indexOf(active);
    const nextIdx = idx < 0 ? 0 : (idx + direction + list.length) % list.length;
    const target = list[nextIdx];
    document.querySelectorAll('.gp-focus').forEach((el) => el.classList.remove('gp-focus'));
    target.classList.add('gp-focus');
    target.focus();
    if (target.scrollIntoView) target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

// Clear the gp-focus marker as soon as the user picks up a pointer.
document.addEventListener('mousedown', () => {
    document.querySelectorAll('.gp-focus').forEach((el) => el.classList.remove('gp-focus'));
}, { capture: true });

// ── Your YancoHub Year (offline-only year-in-review) ─────────────────────────

let _yearObserver = null;

async function openYearOverlay() {
    const overlay = $('yearOverlay');
    const scroll = $('yearScroll');
    overlay.classList.remove('hidden');
    scroll.scrollTop = 0;
    scroll.innerHTML = `
        <section class="year-section year-hero is-visible">
            <div class="year-hero-eyebrow">Your YancoHub</div>
            <div class="year-title"><span class="year-tint">Loading your year…</span></div>
        </section>`;
    try {
        const data = await fetchJSON('/api/year-summary');
        renderYearSummary(data);
    } catch (e) {
        scroll.innerHTML = `
            <section class="year-section year-hero is-visible">
                <div class="year-title">Couldn't load your year.</div>
                <div class="year-hero-sub">${escapeHtml(String(e))}</div>
            </section>`;
    }
}

function closeYearOverlay() {
    $('yearOverlay').classList.add('hidden');
    if (_yearObserver) { _yearObserver.disconnect(); _yearObserver = null; }
}

function renderYearSummary(data) {
    const scroll = $('yearScroll');
    const year = data.year;
    const games = data.games_touched || 0;
    const hours = data.hours_total || 0;
    const top = (data.top_games && data.top_games[0]) || null;
    const topGames = data.top_games || [];
    const months = data.by_month || [];
    const systems = data.by_system || [];
    const genres = data.by_genre || [];
    const allTime = data.all_time || { hours: 0, games: 0 };

    // Empty state
    if (!games) {
        scroll.innerHTML = `
            <section class="year-section year-hero is-visible">
                <div class="year-hero-eyebrow">Your YancoHub</div>
                <div class="year-title">
                    <span class="year-tint">${year}</span>
                </div>
                <p class="year-hero-sub">
                    No play sessions tracked in ${year} yet. Launch a game from YancoHub and we'll
                    start building your year automatically — entirely on this device.
                </p>
            </section>`;
        return;
    }

    const maxTopHours = Math.max(1, ...topGames.map(g => g.hours));
    const maxMonthHours = Math.max(1, ...months.map(m => m.hours));
    const topMonth = months.reduce((a, b) => (b.hours > (a?.hours || 0) ? b : a), null);

    const topGameSection = top ? `
        <section class="year-section year-topgame" style="background-image: url('${escapeAttr(top.artwork_url)}');">
            <div class="year-eyebrow">Your most-played</div>
            <div class="year-topgame-name">${escapeHtml(top.name)}</div>
            <div class="year-topgame-hours">${top.hours} hours · ${top.system}</div>
            <p class="year-caption">You kept coming back. That's what counts.</p>
        </section>` : '';

    const top5Rows = topGames.map((g, i) => {
        const pct = Math.max(6, Math.round((g.hours / maxTopHours) * 100));
        return `
            <div class="year-list-row">
                <span class="year-list-rank">#${i + 1}</span>
                <div class="year-list-cell">
                    <span class="year-list-name">${escapeHtml(g.name)}</span>
                    <div class="year-bar"><div class="year-bar-fill" style="--bar-pct: ${pct}%"></div></div>
                </div>
                <span class="year-list-hours">${g.hours}h</span>
            </div>`;
    }).join('');

    const monthBars = months.map(m => {
        const pct = m.hours > 0 ? Math.max(4, Math.round((m.hours / maxMonthHours) * 100)) : 0;
        const isTop = topMonth && m.month === topMonth.month && m.hours > 0;
        return `
            <div class="year-month${isTop ? ' is-top' : ''}" title="${escapeAttr(m.label)} — ${m.hours}h${m.top_game ? ' · ' + m.top_game : ''}">
                <div class="year-month-bar"><div class="year-month-fill" style="--bar-pct: ${pct}%"></div></div>
                <div class="year-month-label">${escapeHtml(m.label)}</div>
            </div>`;
    }).join('');

    const systemChips = systems.slice(0, 8).map(s =>
        `<span class="year-chip"><span class="year-chip-num">${s.count}</span> ${escapeHtml(s.system)} · ${s.hours}h</span>`
    ).join('');

    const genreChips = genres.map(g =>
        `<span class="year-chip">${escapeHtml(g.genre)} <span class="year-chip-num">${g.hours}h</span></span>`
    ).join('');

    const topMonthLine = topMonth && topMonth.hours > 0
        ? `Your peak was <strong>${escapeHtml(topMonth.label)}</strong>${topMonth.top_game ? ` with <strong>${escapeHtml(topMonth.top_game)}</strong>` : ''}.`
        : '';

    scroll.innerHTML = `
        <section class="year-section year-hero">
            <div class="year-hero-eyebrow">Your YancoHub</div>
            <div class="year-title">
                Your year in
                <span class="year-tint">${year}</span>
            </div>
            <p class="year-hero-sub">
                Pieced together from your local play history. Nothing left this device.
            </p>
            <div class="year-scroll-cue">Scroll to see ↓</div>
        </section>

        <section class="year-section">
            <div class="year-eyebrow">The shape of your year</div>
            <div class="year-row">
                <div class="year-stat">
                    <div class="year-bignum" data-countup="${games}">0</div>
                    <div class="year-bignum-unit">games</div>
                </div>
                <div class="year-stat">
                    <div class="year-bignum" data-countup="${hours}" data-decimals="1">0</div>
                    <div class="year-bignum-unit">hours</div>
                </div>
            </div>
            <p class="year-caption">
                Lifetime totals for the games you returned to in ${year} — your library kept ${games}
                title${games === 1 ? '' : 's'} alive this year.
            </p>
        </section>

        ${topGameSection}

        ${topGames.length ? `
        <section class="year-section">
            <div class="year-eyebrow">Top ${topGames.length}</div>
            <div class="year-title" style="font-size: clamp(1.6rem, 3.5vw, 2.4rem);">The games that defined ${year}</div>
            <div class="year-list">${top5Rows}</div>
        </section>` : ''}

        ${months.some(m => m.hours > 0) ? `
        <section class="year-section">
            <div class="year-eyebrow">Across the months</div>
            <div class="year-title" style="font-size: clamp(1.6rem, 3.5vw, 2.4rem);">When you played</div>
            <div class="year-months">${monthBars}</div>
            ${topMonthLine ? `<p class="year-caption">${topMonthLine}</p>` : ''}
        </section>` : ''}

        ${systems.length ? `
        <section class="year-section">
            <div class="year-eyebrow">By store</div>
            <div class="year-title" style="font-size: clamp(1.6rem, 3.5vw, 2.4rem);">Where your games live</div>
            <div class="year-chips">${systemChips}</div>
        </section>` : ''}

        ${genres.length ? `
        <section class="year-section">
            <div class="year-eyebrow">By mood</div>
            <div class="year-title" style="font-size: clamp(1.6rem, 3.5vw, 2.4rem);">Your favourite flavours</div>
            <div class="year-chips">${genreChips}</div>
        </section>` : ''}

        <section class="year-section year-hero">
            <div class="year-hero-eyebrow">All-time</div>
            <div class="year-title" style="font-size: clamp(2rem, 4vw, 3rem);">
                <span class="year-tint">${allTime.games}</span> games · <span class="year-tint">${allTime.hours}</span> hours
            </div>
            <p class="year-hero-sub">Since you first launched a game inside YancoHub. Quietly accumulating.</p>
            <div class="year-outro-actions">
                <button class="btn-small btn-accent" id="yearOutroClose">Back to library</button>
            </div>
        </section>`;

    // Wire outro close
    const outroClose = document.getElementById('yearOutroClose');
    if (outroClose) outroClose.addEventListener('click', closeYearOverlay);

    // Observe sections to trigger entrance animations + count-ups
    if (_yearObserver) _yearObserver.disconnect();
    _yearObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                entry.target.querySelectorAll('[data-countup]').forEach(_runCountUp);
                _yearObserver.unobserve(entry.target);
            }
        });
    }, { root: $('yearOverlay'), threshold: 0.2 });
    scroll.querySelectorAll('.year-section:not(.year-hero)').forEach(s => _yearObserver.observe(s));
    // The first hero is already visible, but count-ups inside it (none) would run anyway.
    scroll.querySelector('.year-hero')?.classList.add('is-visible');
}

/** Animate a [data-countup] element from 0 to its target over ~1.2s. */
function _runCountUp(el) {
    if (el.dataset.countupDone === '1') return;
    el.dataset.countupDone = '1';
    const target = parseFloat(el.dataset.countup) || 0;
    const decimals = parseInt(el.dataset.decimals || '0', 10);
    const duration = 1200;
    const start = performance.now();
    function frame(now) {
        const t = Math.min(1, (now - start) / duration);
        // ease-out cubic
        const eased = 1 - Math.pow(1 - t, 3);
        const value = target * eased;
        el.textContent = decimals
            ? value.toFixed(decimals)
            : Math.round(value).toLocaleString();
        if (t < 1) requestAnimationFrame(frame);
        else el.textContent = decimals ? target.toFixed(decimals) : Math.round(target).toLocaleString();
    }
    requestAnimationFrame(frame);
}

// ── Tonight's Pick (CatByte curator) ─────────────────────────────────────────

function _renderTonightsPickLoading() {
    $('tonightsPickSub').textContent = 'CatByte is choosing from your library…';
    $('tonightsPickBody').innerHTML = `
        <div class="tonights-pick-loading" style="grid-column: 1 / -1;">
            Curating your night
            <span class="tonights-pick-loading-dots"><span></span><span></span><span></span></span>
        </div>`;
}

function _renderTonightsPickMessage(text) {
    $('tonightsPickSub').textContent = '';
    $('tonightsPickBody').innerHTML = `
        <div class="tonights-pick-message" style="grid-column: 1 / -1;">${escapeHtml(text)}</div>`;
}

function _renderTonightsPickResults(picks) {
    const sub = picks.length === 1
        ? "CatByte's pick for tonight."
        : `${picks.length} games CatByte thinks you'll enjoy tonight.`;
    $('tonightsPickSub').textContent = sub;
    $('tonightsPickBody').innerHTML = picks.map((p, i) => `
        <div class="tp-card" data-game-id="${escapeAttr(p.game_id)}" data-idx="${i}" role="button" tabindex="0">
            <div class="tp-card-art" style="background-image: url('${escapeAttr(p.artwork_url)}')"></div>
            <div class="tp-card-body">
                <div class="tp-card-name">${escapeHtml(p.name)}</div>
                <div class="tp-card-reason">${escapeHtml(p.reason)}</div>
            </div>
        </div>
    `).join('');
    $('tonightsPickBody').querySelectorAll('.tp-card').forEach((card) => {
        const gid = card.dataset.gameId;
        const activate = () => {
            closeTonightsPick();
            if (typeof launchGame === 'function') launchGame(gid);
        };
        card.addEventListener('click', activate);
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); }
        });
    });
}

async function openTonightsPick() {
    const overlay = $('tonightsPickOverlay');
    overlay.classList.remove('hidden');
    _renderTonightsPickLoading();
    await _fetchTonightsPick();
}

function closeTonightsPick() {
    $('tonightsPickOverlay').classList.add('hidden');
}

async function _fetchTonightsPick() {
    try {
        const r = await fetch('/api/catbyte/tonights-pick', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ count: 3 }),
        });
        if (!r.ok) {
            _renderTonightsPickMessage(`Backend error (${r.status}). Try again in a moment.`);
            return;
        }
        const data = await r.json();
        if (!data.picks || data.picks.length === 0) {
            _renderTonightsPickMessage(data.message || 'CatByte had nothing to recommend right now.');
            return;
        }
        _renderTonightsPickResults(data.picks);
    } catch (e) {
        _renderTonightsPickMessage('Could not reach the backend. Is YancoHub still running?');
    }
}

// ── Settings Status Summaries ──────────────────────────────────────────────

function renderAccountsSummary(accounts) {
    const el = $('summaryAccounts');
    if (!el) return;
    const stores = ['steam', 'gog', 'epic'];
    const items = stores.map(s => {
        const connected = accounts[s]?.connected || accounts[s]?.enabled || false;
        const dot = connected ? 'ok' : 'off';
        const label = s.charAt(0).toUpperCase() + s.slice(1);
        return `<span class="summary-item"><span class="summary-dot ${dot}"></span>${label}</span>`;
    });
    const gameCount = state.games.length;
    items.push(`<span class="summary-sep">\u00B7</span><span class="summary-item"><span class="summary-value">${gameCount}</span> games total</span>`);
    el.innerHTML = items.join('');
}

function renderDirectoriesSummary(romDirs, localDirs) {
    const el = $('summaryDirectories');
    if (!el) return;
    const retroCount = state.games.filter(g => g.source === 'retro').length;
    const localCount = state.games.filter(g => g.source === 'local').length;
    const parts = [];
    parts.push(`<span class="summary-item"><span class="summary-value">${romDirs.length}</span> ROM dirs</span>`);
    parts.push(`<span class="summary-sep">\u00B7</span><span class="summary-item"><span class="summary-value">${retroCount}</span> ROMs</span>`);
    parts.push(`<span class="summary-sep">\u00B7</span><span class="summary-item"><span class="summary-value">${localDirs.length}</span> local dirs</span>`);
    if (localCount > 0) {
        parts.push(`<span class="summary-sep">\u00B7</span><span class="summary-item"><span class="summary-value">${localCount}</span> local games</span>`);
    }
    el.innerHTML = parts.join('');
}

function renderEmulationSummary(biosStatus, lbPath) {
    const el = $('summaryEmulation');
    if (!el) return;
    const ready = Object.values(biosStatus || {}).filter(s => s.ready).length;
    const total = Object.keys(biosStatus || {}).length;
    const allReady = ready === total;
    const parts = [];
    parts.push(`<span class="summary-item"><span class="summary-dot ${allReady ? 'ok' : 'warn'}"></span>BIOS: <span class="summary-value">${ready}</span>/${total} ready</span>`);
    if (lbPath) {
        const lbCount = state.games.filter(g => g.source === 'retro').length;
        parts.push(`<span class="summary-sep">\u00B7</span><span class="summary-item"><span class="summary-dot ok"></span>LaunchBox linked</span>`);
    } else {
        parts.push(`<span class="summary-sep">\u00B7</span><span class="summary-item"><span class="summary-dot off"></span>LaunchBox not set</span>`);
    }
    const hiddenCount = state.hiddenSystems.size;
    if (hiddenCount > 0) {
        parts.push(`<span class="summary-sep">\u00B7</span><span class="summary-item">${hiddenCount} systems hidden</span>`);
    }
    el.innerHTML = parts.join('');
}

function renderCatbyteSummary(config, status) {
    const el = $('summaryCatbyte');
    if (!el) return;
    const backendName = (config?.backend || 'none').charAt(0).toUpperCase() + (config?.backend || 'none').slice(1);
    const online = status?.status === 'online';
    const dot = online ? 'ok' : 'off';
    const parts = [];
    parts.push(`<span class="summary-item"><span class="summary-dot ${dot}"></span>${backendName}</span>`);
    if (config?.model) {
        parts.push(`<span class="summary-sep">\u00B7</span><span class="summary-item">${config.model}</span>`);
    }
    parts.push(`<span class="summary-sep">\u00B7</span><span class="summary-item">${online ? 'Online' : 'Offline'}</span>`);
    el.innerHTML = parts.join('');
}

// ── Accounts Tab ──────────────────────────────────────────────────────────

async function renderAccountsTab() {
    try {
        const [accounts, epicManifest] = await Promise.all([
            fetchJSON('/api/accounts'),
            fetchJSON('/api/epic/manifest-count'),
        ]);

        let accountsHtml = '';

        // Steam
        const steam = accounts.steam || {};
        const detectedUsers = steam.detected_users || [];
        const detectedUser = detectedUsers[0]; // Most recent login

        if (steam.connected) {
            const apiNote = steam.has_api_key
                ? 'Full library (installed + owned)'
                : 'Installed games only';
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🎮</div>
                    <div class="account-info">
                        <div class="account-name">Steam</div>
                        <div class="account-detail">${escapeHtml(steam.persona_name || 'Connected')} &mdash; ${apiNote}</div>
                    </div>
                    <div class="account-status connected"></div>
                    <button class="account-btn${steam.has_api_key ? ' disconnect' : ''}" id="${steam.has_api_key ? 'btnDisconnectSteam' : 'btnShowSteamConnect'}">${steam.has_api_key ? 'Disconnect' : 'Add API Key'}</button>
                </div>`;
        } else if (detectedUser) {
            // Steam user detected locally — one-click connect
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🎮</div>
                    <div class="account-info">
                        <div class="account-name">Steam</div>
                        <div class="account-detail">Detected: ${escapeHtml(detectedUser.persona_name)} &mdash; click to connect</div>
                    </div>
                    <div class="account-status disconnected"></div>
                    <button class="account-btn" id="btnQuickConnectSteam">Connect</button>
                    <button class="account-btn" id="btnShowSteamConnect" style="margin-left:4px">Manual</button>
                </div>`;
        } else {
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🎮</div>
                    <div class="account-info">
                        <div class="account-name">Steam</div>
                        <div class="account-detail">Not detected</div>
                    </div>
                    <div class="account-status disconnected"></div>
                    <button class="account-btn" id="btnShowSteamConnect">Connect</button>
                </div>`;
        }

        // GOG Galaxy
        const galaxy = accounts.gog_galaxy || {};
        if (galaxy.available) {
            const platCount = (galaxy.connected_platforms || []).length;
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🌌</div>
                    <div class="account-info">
                        <div class="account-name">GOG Galaxy</div>
                        <div class="account-detail">${galaxy.enabled
                            ? `${platCount} platform${platCount !== 1 ? 's' : ''} connected`
                            : 'Available \u2014 click to enable'}</div>
                        ${galaxy.enabled && galaxy.connected_platforms?.length ? `
                            <div class="galaxy-platforms">
                                ${galaxy.connected_platforms.map(p =>
                                    `<span class="galaxy-platform-tag">${p}</span>`
                                ).join('')}
                            </div>` : ''}
                    </div>
                    <div class="account-status ${galaxy.enabled ? 'connected' : 'disconnected'}"></div>
                    <button class="account-btn" id="btnToggleGalaxy">${galaxy.enabled ? 'Disable' : 'Enable'}</button>
                </div>`;
        }

        // Epic — reads owned games from local catalog cache (like GOG Galaxy)
        const epic = accounts.epic || {};
        const epicInstalledCount = epicManifest.count || 0;
        const epicOwnedCount = epicManifest.owned_count || 0;
        const epicLauncher = epic.launcher_installed || epicManifest.launcher_installed;
        const epicCatalog = epic.catalog_available || epicManifest.catalog_available;
        const epicHasGames = epicOwnedCount > 0 || epicInstalledCount > 0;

        if (epicCatalog && epicHasGames) {
            // Epic catalog found with owned games — fully working (like Steam connected / GOG enabled)
            const detail = epicOwnedCount > 0
                ? `${epicOwnedCount} owned game${epicOwnedCount !== 1 ? 's' : ''}${epicInstalledCount > 0 ? ` \u2014 ${epicInstalledCount} installed` : ''}`
                : `${epicInstalledCount} installed game${epicInstalledCount !== 1 ? 's' : ''}`;
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🏔️</div>
                    <div class="account-info">
                        <div class="account-name">Epic Games</div>
                        <div class="account-detail">${detail}</div>
                    </div>
                    <div class="account-status connected"></div>
                </div>`;
        } else if (epicLauncher) {
            // Launcher installed but no catalog cache (not logged in yet or empty)
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🏔️</div>
                    <div class="account-info">
                        <div class="account-name">Epic Games</div>
                        <div class="account-detail">Launcher detected \u2014 log in to Epic to see your library</div>
                    </div>
                    <div class="account-status disconnected"></div>
                </div>`;
        } else {
            // No Epic detected at all
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🏔️</div>
                    <div class="account-info">
                        <div class="account-name">Epic Games</div>
                        <div class="account-detail">Not detected \u2014 install Epic Games Launcher to get started</div>
                    </div>
                    <div class="account-status disconnected"></div>
                </div>`;
        }

        $('settingsAccounts').innerHTML = accountsHtml || '<div style="color:var(--text-dim);font-size:12px">No accounts connected</div>';

        // Bind account buttons
        const btnQuickSteam = document.getElementById('btnQuickConnectSteam');
        if (btnQuickSteam && detectedUser) {
            btnQuickSteam.addEventListener('click', async () => {
                btnQuickSteam.textContent = 'Connecting...';
                btnQuickSteam.disabled = true;
                try {
                    const r = await fetch('/api/accounts/steam/connect', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ steam_id: detectedUser.steam_id }),
                    });
                    const d = await r.json();
                    if (r.ok) {
                        renderSettings();
                        setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
                    } else {
                        btnQuickSteam.textContent = d.error || 'Failed';
                        setTimeout(() => { btnQuickSteam.textContent = 'Connect'; btnQuickSteam.disabled = false; }, 3000);
                    }
                } catch {
                    btnQuickSteam.textContent = 'Failed';
                    setTimeout(() => { btnQuickSteam.textContent = 'Connect'; btnQuickSteam.disabled = false; }, 3000);
                }
            });
        }
        const btnShowSteam = document.getElementById('btnShowSteamConnect');
        if (btnShowSteam) {
            btnShowSteam.addEventListener('click', () => {
                $('steamConnectSection').classList.remove('hidden');
                // Auto-fill Steam ID if detected
                if (detectedUser && $('steamIdInput')) {
                    $('steamIdInput').value = steam.steam_id || detectedUser.steam_id || '';
                }
            });
        }
        const btnDisconnect = document.getElementById('btnDisconnectSteam');
        if (btnDisconnect) {
            btnDisconnect.addEventListener('click', async () => {
                try { await fetch('/api/accounts/steam/disconnect', { method: 'POST' }); }
                catch (e) { console.warn('Disconnect Steam failed:', e); }
                $('steamConnectSection').classList.add('hidden');
                renderSettings();
                setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
            });
        }
        const btnGalaxy = document.getElementById('btnToggleGalaxy');
        if (btnGalaxy) {
            btnGalaxy.addEventListener('click', async () => {
                try { await fetch('/api/accounts/gog-galaxy/toggle', { method: 'POST' }); }
                catch (e) { console.warn('Toggle GOG Galaxy failed:', e); }
                renderSettings();
                setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
            });
        }
        const btnEpicAuth = document.getElementById('btnEpicAuth');
        if (btnEpicAuth) {
            btnEpicAuth.addEventListener('click', async () => {
                btnEpicAuth.textContent = 'Connecting...';
                btnEpicAuth.disabled = true;
                const d = await fetchJSON('/api/accounts/epic/auth', { method: 'POST' });
                if (d.status === 'ok') {
                    renderSettings();
                    setTimeout(async () => { await loadGames(); applyFilter(); }, 5000);
                } else {
                    btnEpicAuth.textContent = d.message || 'Failed';
                    setTimeout(() => { btnEpicAuth.textContent = 'Import Full Library'; btnEpicAuth.disabled = false; }, 3000);
                }
            });
        }

        if (steam.connected) {
            $('steamConnectSection').classList.add('hidden');
        }

        renderAccountsSummary(accounts);
    } catch (e) { console.warn('renderAccountsTab failed:', e); }

    // ── Settings toggles + enums (unified schema-driven API) ──
    await loadSettings();
    bindSettingToggles();
    bindSettingEnums();
    bindThemeSwatches();

    // ── Detected Stores ──
    const storeNames = {
        steam: 'Steam', epic: 'Epic Games', gog: 'GOG Galaxy', xbox: 'Xbox/Game Pass',
        ea: 'EA Desktop', ubisoft: 'Ubisoft Connect', battlenet: 'Battle.net',
        amazon: 'Amazon Games', retroarch: 'RetroArch'
    };
    $('settingsStores').innerHTML = Object.entries(state.stores)
        .map(([k, v]) => `<div class="store-badge"><span class="store-status ${v ? 'detected' : 'missing'}"></span>${storeNames[k] || k}</div>`)
        .join('');
}

// ── Directories Tab ───────────────────────────────────────────────────────

async function renderDirectoriesTab() {
    let romDirs = [], localDirs = [];

    // ROM dirs
    try {
        romDirs = await fetchJSON('/api/rom-dirs');
        $('settingsRomDirs').innerHTML = romDirs.map(d => `
            <div class="dir-entry">
                <span class="dir-icon">\uD83D\uDCC2</span>
                <span>${escapeHtml(d)}</span>
                <button class="dir-remove" data-dir="${escapeAttr(d)}" data-type="rom">&times;</button>
            </div>
        `).join('') || '<div style="color:var(--text-dim);font-size:12px;padding:4px 0">No ROM directories configured</div>';
    } catch (e) { console.warn('loadRomDirs failed:', e); }

    // Local dirs
    try {
        localDirs = await fetchJSON('/api/local-dirs');
        $('settingsLocalDirs').innerHTML = localDirs.map(d => `
            <div class="dir-entry">
                <span class="dir-icon">\uD83C\uDFAE</span>
                <span>${escapeHtml(d)}</span>
                <button class="dir-remove" data-dir="${escapeAttr(d)}" data-type="local">&times;</button>
            </div>
        `).join('') || '<div style="color:var(--text-dim);font-size:12px;padding:4px 0">No local game directories configured</div>';
    } catch (e) { console.warn('loadLocalDirs failed:', e); }

    renderDirectoriesSummary(romDirs, localDirs);

    // Bind remove buttons
    $$('.dir-remove').forEach(btn => {
        btn.addEventListener('click', async () => {
            const dirPath = btn.dataset.dir;
            const typeLabel = { rom: 'ROM', local: 'local game', bios: 'BIOS' }[btn.dataset.type] || '';
            if (!confirm(`Remove ${typeLabel} directory?\n${dirPath}`)) return;
            const typeMap = { rom: '/api/rom-dirs', local: '/api/local-dirs', bios: '/api/bios/dirs' };
            const endpoint = typeMap[btn.dataset.type] || '/api/local-dirs';
            try {
                await fetch(endpoint, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: dirPath }),
                });
            } catch (e) { console.warn('Remove directory failed:', e); }
            showToast(`${typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1)} directory removed`, 'info');
            renderSettings();
        });
    });
}

// ── Emulation Tab ─────────────────────────────────────────────────────────

const SYSTEM_ICONS = {
    snes: '\uD83C\uDFAE', nes: '\uD83D\uDD79\uFE0F', gba: '\uD83D\uDCF1', gb: '\uD83D\uDCDF',
    gbc: '\uD83C\uDF08', n64: '\uD83D\uDD79\uFE0F', nds: '\u270F\uFE0F', megadrive: '\uD83D\uDC99',
    mastersystem: '\uD83D\uDD35', gamegear: '\uD83D\uDD0D', atari2600: '\uD83D\uDD78\uFE0F',
    psx: '\uD83D\uDCBF', ps2: '\uD83D\uDCBF', ps3: '\uD83C\uDFAE', psp: '\uD83C\uDFAE',
    dreamcast: '\uD83C\uDF00', saturn: '\uD83E\uDE90', gamecube: '\uD83D\uDFEA', wii: '\u2B1C',
    neogeo: '\uD83C\uDFB0', fbneo: '\uD83D\uDD25', cps1: '\uD83E\uDD4A', cps2: '\uD83E\uDD4A',
    cps3: '\uD83E\uDD4A', mame: '\uD83D\uDC7E', ngp: '\uD83D\uDCDF',
    atari5200: '\uD83D\uDD78\uFE0F', atari7800: '\uD83D\uDD78\uFE0F', atarilynx: '\uD83D\uDD78\uFE0F',
    atarist: '\uD83D\uDDA5\uFE0F', atarijaguar: '\uD83D\uDC06',
    colecovision: '\uD83C\uDFAE', c64: '\uD83D\uDDA5\uFE0F', amiga: '\uD83D\uDDA5\uFE0F',
    dos: '\uD83D\uDDA5\uFE0F', pcengine: '\uD83C\uDFAE', famicom: '\uD83D\uDD79\uFE0F',
    fds: '\uD83D\uDCBE', channelf: '\uD83D\uDCFA', arcade: '\uD83D\uDC7E',
    atomiswave: '\uD83C\uDFB0', daphne: '\uD83C\uDFAC', gameandwatch: '\u231A',
    odyssey2: '\uD83D\uDCFA', vectrex: '\uD83D\uDDA5\uFE0F', wonderswan: '\uD83C\uDFAE',
    wonderswanc: '\uD83C\uDF08', intellivision: '\uD83C\uDFAE', '3do': '\uD83D\uDCBF',
};

async function renderEmulationTab() {
    let _biosStatus = {};

    // BIOS dirs + status
    try {
        const [biosDirs, biosStatus] = await Promise.all([
            fetchJSON('/api/bios/dirs'),
            fetchJSON('/api/bios/status'),
        ]);
        _biosStatus = biosStatus;

        $('settingsBiosDirs').innerHTML = biosDirs.map(d => `
            <div class="dir-entry">
                <span class="dir-icon">\uD83D\uDCC1</span>
                <span>${escapeHtml(d)}</span>
                <button class="dir-remove" data-dir="${escapeAttr(d)}" data-type="bios">&times;</button>
            </div>
        `).join('') || '<div style="color:var(--text-dim);font-size:12px;padding:4px 0">No BIOS directories configured</div>';

        // BIOS cards grid
        let biosHtml = '';
        for (const [sysId, info] of Object.entries(biosStatus)) {
            const ready = info.ready;
            const fileDetails = (info.files || [])
                .map(f => `${f.name}: ${f.found ? 'Found' : 'Missing'}`)
                .join('\n');
            biosHtml += `
                <div class="bios-card ${ready ? 'ready' : ''}" title="${escapeAttr(fileDetails)}">
                    <span class="bios-card-dot ${ready ? 'ready' : 'missing'}"></span>
                    <div>
                        <div class="bios-card-name">${escapeHtml(info.system_name || sysId)}</div>
                        <div class="bios-card-files">${(info.files || []).filter(f => f.found).length}/${(info.files || []).length} files</div>
                    </div>
                </div>`;
        }
        $('settingsBiosStatus').innerHTML = biosHtml;

        // Re-bind BIOS dir remove buttons
        $('settingsBiosDirs').querySelectorAll('.dir-remove').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!confirm(`Remove BIOS directory?\n${btn.dataset.dir}`)) return;
                try {
                    await fetch('/api/bios/dirs', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: btn.dataset.dir }),
                    });
                } catch (e) { console.warn('Remove BIOS dir failed:', e); }
                showToast('BIOS directory removed', 'info');
                renderEmulationTab();
            });
        });
    } catch (e) { console.warn('renderEmulationTab BIOS section failed:', e); }

    // Systems with icons
    const systems = {
        snes: 'SNES', nes: 'NES', gba: 'GBA', gb: 'GB', gbc: 'GBC',
        n64: 'N64', nds: 'NDS', megadrive: 'Genesis', mastersystem: 'Master System',
        gamegear: 'Game Gear', atari2600: 'Atari 2600', psx: 'PS1', ps2: 'PS2',
        ps3: 'PS3', psp: 'PSP', dreamcast: 'Dreamcast', saturn: 'Saturn',
        gamecube: 'GameCube', wii: 'Wii', neogeo: 'Neo Geo', fbneo: 'FBNeo',
        cps1: 'CPS-1', cps2: 'CPS-2', cps3: 'CPS-3', mame: 'MAME', ngp: 'NGP',
        atari5200: 'Atari 5200', atari7800: 'Atari 7800', atarilynx: 'Lynx',
        atarist: 'Atari ST', atarijaguar: 'Jaguar', colecovision: 'ColecoVision',
        c64: 'C64', amiga: 'Amiga', dos: 'DOS', pcengine: 'PC Engine',
        famicom: 'Famicom', fds: 'FDS', channelf: 'Channel F', arcade: 'Arcade',
        atomiswave: 'Atomiswave', daphne: 'Daphne', gameandwatch: 'Game & Watch',
        odyssey2: 'Odyssey 2', vectrex: 'Vectrex', wonderswan: 'WonderSwan',
        wonderswanc: 'WS Color', intellivision: 'Intellivision', '3do': '3DO',
    };
    $('settingsVisibleSystems').innerHTML = Object.entries(systems)
        .map(([id, name]) => {
            const hidden = state.hiddenSystems.has(id);
            const icon = SYSTEM_ICONS[id] || '\uD83C\uDFAE';
            return `<button class="system-toggle ${hidden ? 'hidden-sys' : 'active'}" data-system="${id}">
                <span class="sys-icon">${icon}</span>
                <span class="sys-name">${name}</span>
            </button>`;
        }).join('');

    // Bind system toggles
    $$('.system-toggle').forEach(btn => {
        btn.addEventListener('click', async () => {
            const d = await fetchJSON('/api/hidden-systems/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ system: btn.dataset.system }),
            });
            if (d.is_hidden) state.hiddenSystems.add(btn.dataset.system);
            else state.hiddenSystems.delete(btn.dataset.system);
            btn.classList.toggle('hidden-sys', d.is_hidden);
            btn.classList.toggle('active', !d.is_hidden);
        });
    });

    // RetroArch + LaunchBox paths (from unified settings)
    const s = await loadSettings();
    if (s.retroarch_path) $('retroarchPathInput').value = s.retroarch_path;
    const lbPath = s.launchbox_path || '';
    $('launchboxPathInput').value = lbPath;
    $('launchboxStatus').textContent = lbPath
        ? 'Artwork will be loaded directly from LaunchBox — no files copied.'
        : '';

    renderEmulationSummary(_biosStatus, lbPath);

    // Emulator auto-setup
    renderEmuSetupStatus();
}

async function saveLaunchboxPath() {
    const input = $('launchboxPathInput');
    const path = input.value.trim();
    const btn = $('saveLaunchboxPath');
    btn.textContent = 'Saving...';
    btn.disabled = true;
    try {
        const d = await patchSetting('launchbox_path', path);
        const err = d.errors && d.errors.launchbox_path;
        if (err) {
            $('launchboxStatus').textContent = err;
            $('launchboxStatus').style.color = 'var(--danger)';
            showToast(err, 'error');
        } else {
            const matched = d.meta && d.meta.launchbox_path ? d.meta.launchbox_path.matched_count : null;
            const msg = path
                ? `Saved. ${matched != null ? matched + ' games matched.' : 'Artwork will load from LaunchBox.'}`
                : 'Cleared.';
            $('launchboxStatus').textContent = msg;
            $('launchboxStatus').style.color = 'var(--accent)';
            showToast(path ? `LaunchBox linked \u2014 <strong>${matched ?? '?'}</strong> games indexed` : 'LaunchBox path cleared', 'success');
        }
    } catch (e) {
        console.warn('saveLaunchboxPath failed:', e);
        $('launchboxStatus').textContent = 'Failed to save.';
        $('launchboxStatus').style.color = 'var(--danger)';
        showToast('Failed to save LaunchBox path', 'error');
    }
    btn.textContent = 'Save';
    btn.disabled = false;
}

async function saveRetroarchPath() {
    const input = $('retroarchPathInput');
    const path = input.value.trim();
    const btn = $('saveRetroarch');
    btn.textContent = 'Saving...';
    btn.disabled = true;
    try {
        const d = await patchSetting('retroarch_path', path);
        const err = d.errors && d.errors.retroarch_path;
        if (err) {
            $('retroarchStatus').textContent = err;
            $('retroarchStatus').style.color = 'var(--danger)';
            showToast(err, 'error');
        } else {
            const msg = path ? 'RetroArch path saved.' : 'Cleared.';
            $('retroarchStatus').textContent = msg;
            $('retroarchStatus').style.color = 'var(--accent)';
            showToast(path ? 'RetroArch path saved' : 'RetroArch path cleared', 'success');
        }
    } catch {
        $('retroarchStatus').textContent = 'Failed to save.';
        $('retroarchStatus').style.color = 'var(--danger)';
        showToast('Failed to save RetroArch path', 'error');
    }
    btn.textContent = 'Save';
    btn.disabled = false;
}

async function testRetroarch() {
    const path = $('retroarchPathInput').value.trim();
    const btn = $('testRetroarch');
    const status = $('retroarchStatus');
    if (!path) { showToast('Enter a RetroArch path first', 'info'); return; }
    btn.textContent = 'Testing...';
    btn.disabled = true;
    try {
        const d = await fetchJSON('/api/test/retroarch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        status.textContent = d.message;
        status.style.color = d.ok ? 'var(--accent)' : 'var(--danger)';
        showToast(d.ok ? `RetroArch OK \u2014 ${d.message}` : d.message, d.ok ? 'success' : 'error');
    } catch {
        status.textContent = 'Test failed';
        status.style.color = 'var(--danger)';
        showToast('RetroArch test failed', 'error');
    }
    btn.textContent = 'Test';
    btn.disabled = false;
}

async function testLaunchbox() {
    const path = $('launchboxPathInput').value.trim();
    const btn = $('testLaunchbox');
    const status = $('launchboxStatus');
    if (!path) { showToast('Enter a LaunchBox path first', 'info'); return; }
    btn.textContent = 'Testing...';
    btn.disabled = true;
    try {
        const d = await fetchJSON('/api/test/launchbox', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        status.textContent = d.message;
        status.style.color = d.ok ? 'var(--accent)' : 'var(--danger)';
        showToast(d.ok ? `LaunchBox OK \u2014 ${d.message}` : d.message, d.ok ? 'success' : 'error');
    } catch {
        status.textContent = 'Test failed';
        status.style.color = 'var(--danger)';
        showToast('LaunchBox test failed', 'error');
    }
    btn.textContent = 'Test';
    btn.disabled = false;
}

// ── Emulator Auto-Setup ──────────────────────────────────────────────────

async function renderEmuSetupStatus() {
    const container = $('emuSetupStatus');
    if (!container) return;
    try {
        const data = await fetchJSON('/api/emulators/status');

        const ra = data.retroarch;
        const cores = data.cores || {};
        const coreList = Object.entries(cores);
        const needed = data.needed_count || 0;
        const installed = data.installed_count || 0;

        if (needed === 0) {
            container.innerHTML = '<div class="emu-status-summary">No external emulator cores needed for your current library.</div>';
            $('emuAutoSetup').style.display = 'none';
            return;
        }

        let html = '<div class="emu-status-summary">';
        html += `RetroArch: <strong style="color:${ra.installed ? 'var(--accent)' : 'var(--danger)'}">`;
        html += ra.installed ? 'Installed' : 'Not installed';
        html += '</strong>';
        html += ` &nbsp;|&nbsp; Cores: <strong>${installed}/${needed}</strong>`;
        if (data.ready) html += ' &nbsp;<span style="color:var(--accent)">All ready</span>';
        html += '</div>';

        html += '<div class="emu-core-grid">';
        for (const [coreName, info] of coreList) {
            const ready = info.installed;
            html += `<div class="emu-core-card ${ready ? 'installed' : ''}">`;
            html += `<span class="emu-core-dot ${ready ? 'ready' : ''}"></span>`;
            html += `<span class="emu-core-name" title="${coreName}">${info.system_names.join(', ')}</span>`;
            html += '</div>';
        }
        html += '</div>';
        container.innerHTML = html;

        const btn = $('emuAutoSetup');
        if (data.ready) {
            btn.textContent = 'All Set';
            btn.disabled = true;
        } else {
            btn.textContent = 'Auto-Setup Emulators';
            btn.disabled = false;
        }
    } catch {
        container.innerHTML = '<div class="emu-status-summary" style="color:var(--text-dim)">Could not load emulator status.</div>';
    }
}

let _emuPollTimer = null;

async function startEmuSetup() {
    const btn = $('emuAutoSetup');
    btn.textContent = 'Starting...';
    btn.disabled = true;
    try {
        const data = await fetchJSON('/api/emulators/setup', { method: 'POST' });
        if (data.error) {
            showToast(data.error, 'error');
            btn.textContent = 'Auto-Setup Emulators';
            btn.disabled = false;
            return;
        }
        showToast('Emulator setup started \u2014 downloading RetroArch + cores...', 'info', 5000);
        $('emuSetupProgress').classList.remove('hidden');
        _emuPollTimer = setInterval(pollEmuProgress, 800);
    } catch {
        showToast('Failed to start emulator setup', 'error');
        btn.textContent = 'Auto-Setup Emulators';
        btn.disabled = false;
    }
}

async function pollEmuProgress() {
    try {
        const p = await fetchJSON('/api/emulators/progress');
        const bar = $('emuProgressBar');
        const text = $('emuProgressText');

        if (p.total > 0) {
            const pct = Math.round((p.downloaded / p.total) * 100);
            bar.style.width = pct + '%';
        }

        // Build status text
        let msg = '';
        if (p.phase === 'retroarch') {
            const mb = (p.bytes_downloaded / 1048576).toFixed(1);
            const totalMb = p.bytes_total > 0 ? (p.bytes_total / 1048576).toFixed(0) : '?';
            msg = `Downloading RetroArch... ${mb}MB / ${totalMb}MB`;
            if (p.current_item === 'Extracting RetroArch...') msg = 'Extracting RetroArch...';
        } else if (p.phase === 'cores') {
            msg = `Downloading core ${p.downloaded + 1}/${p.total}: ${p.current_item}`;
        } else if (p.phase === 'config') {
            msg = 'Writing configuration...';
        } else if (p.phase === 'done') {
            msg = 'Setup complete!';
        }
        text.textContent = msg;

        if (!p.active && p.done) {
            clearInterval(_emuPollTimer);
            _emuPollTimer = null;
            bar.style.width = '100%';

            if (p.error) {
                showToast('Setup finished with errors: ' + p.error, 'error', 8000);
            } else {
                showToast('Emulator setup complete \u2014 all cores ready!', 'success', 5000);
            }

            setTimeout(() => {
                $('emuSetupProgress').classList.add('hidden');
                renderEmuSetupStatus();
            }, 2000);
        }
    } catch (e) { console.warn('pollEmuProgress error:', e); }
}

// ── CatByte Settings Tab ──────────────────────────────────────────────────

async function renderCatbyteTab() {
    try {
        const [config, presets, detected] = await Promise.all([
            fetchJSON('/api/catbyte/config'),
            fetchJSON('/api/catbyte/presets'),
            fetchJSON('/api/catbyte/detect'),
        ]);

        // Backend selector cards — show detection status
        const backendOrder = ['ollama', 'openclaw', 'lmstudio', 'openai', 'custom'];
        let backendHtml = '';
        for (const key of backendOrder) {
            const p = presets[key];
            if (!p) continue;
            const selected = config.backend === key;
            const det = detected[key];
            const isRunning = det && det.reachable;
            const badgeClass = p.local ? 'local' : 'cloud';
            const badgeText = p.local ? 'Local' : 'Cloud';
            let statusHtml = '';
            if (p.local && det) {
                statusHtml = isRunning
                    ? `<span class="backend-card-status running">Running${det.models ? ` · ${det.models} model${det.models !== 1 ? 's' : ''}` : ''}</span>`
                    : `<span class="backend-card-status not-running">Not detected</span>`;
            }
            backendHtml += `
                <div class="backend-card ${selected ? 'selected' : ''}" data-backend="${key}">
                    <div class="backend-card-header">
                        <span class="backend-card-radio"></span>
                        <span class="backend-card-name">${escapeHtml(p.name)}</span>
                        <span class="backend-card-badge ${badgeClass}">${badgeText}</span>
                    </div>
                    <div class="backend-card-desc">${escapeHtml(p.description)}</div>
                    ${statusHtml}
                </div>`;
        }
        $('catbyteBackendSelector').innerHTML = backendHtml;

        // Bind backend card clicks
        $$('.backend-card').forEach(card => {
            card.addEventListener('click', async () => {
                const backend = card.dataset.backend;
                try {
                    await fetch('/api/catbyte/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ backend }),
                    });
                } catch (e) { console.warn('Set backend failed:', e); }
                renderCatbyteTab();
            });
        });

        // Custom fields (URL, API key, model) based on selected backend
        const preset = presets[config.backend] || {};
        let fieldsHtml = '';

        if (['custom', 'openai', 'openclaw'].includes(config.backend)) {
            if (config.backend === 'custom' || config.backend === 'openclaw') {
                fieldsHtml += `
                    <div class="settings-field">
                        <label class="settings-label">Base URL</label>
                        <input type="text" class="settings-input" id="catbyteBaseUrl"
                               value="${escapeAttr(config.base_url || '')}"
                               placeholder="${escapeAttr(preset.base_url || 'http://localhost:8080')}">
                    </div>`;
            }
            fieldsHtml += `
                <div class="settings-field">
                    <label class="settings-label">API Key</label>
                    <input type="password" class="settings-input" id="catbyteApiKey"
                           value="${config.has_api_key ? '••••••••' : ''}"
                           placeholder="${preset.api_key_required ? 'Required' : 'Optional'}">
                </div>`;
        }

        // Model dropdown for backends that support multiple models
        if (['ollama', 'openclaw', 'lmstudio', 'openai', 'custom'].includes(config.backend)) {
            fieldsHtml += `
                <div class="settings-field">
                    <label class="settings-label">Model</label>
                    <div class="settings-input-row">
                        <select class="settings-input" id="catbyteModel">
                            <option value="">Loading models...</option>
                        </select>
                        <button class="btn-small" id="btnRefreshModels" title="Refresh available models">&#8635;</button>
                    </div>
                </div>`;
        }

        // Save button for custom fields
        if (fieldsHtml) {
            fieldsHtml += `
                <button class="btn-small" id="btnSaveCatbyteConfig" style="margin-top:4px">Save</button>`;
        }

        $('catbyteCustomFields').innerHTML = fieldsHtml;

        // Bind save button
        const btnSave = document.getElementById('btnSaveCatbyteConfig');
        if (btnSave) {
            btnSave.addEventListener('click', async () => {
                const updates = {};
                const urlInput = document.getElementById('catbyteBaseUrl');
                const keyInput = document.getElementById('catbyteApiKey');
                const modelInput = document.getElementById('catbyteModel');
                if (urlInput) updates.base_url = urlInput.value.trim();
                if (keyInput && keyInput.value && !keyInput.value.startsWith('\u2022'))
                    updates.api_key = keyInput.value.trim();
                if (modelInput) updates.model = modelInput.value.trim();

                btnSave.textContent = 'Saving...';
                try {
                    await fetch('/api/catbyte/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(updates),
                    });
                    btnSave.textContent = 'Saved!';
                } catch (e) {
                    console.warn('Save catbyte config failed:', e);
                    btnSave.textContent = 'Error';
                }
                setTimeout(() => { btnSave.textContent = 'Save'; }, 1500);
            });
        }

        // Populate model dropdown
        const modelSelect = document.getElementById('catbyteModel');
        const btnRefresh = document.getElementById('btnRefreshModels');

        async function populateModelDropdown() {
            if (!modelSelect) return;
            if (btnRefresh) { btnRefresh.textContent = '...'; btnRefresh.disabled = true; }
            try {
                const models = await fetchJSON('/api/catbyte/models');
                const currentModel = config.model || preset.default_model || '';
                modelSelect.innerHTML = '';

                if (models.length > 0) {
                    for (const m of models) {
                        const opt = document.createElement('option');
                        opt.value = m;
                        opt.textContent = m;
                        if (m === currentModel) opt.selected = true;
                        modelSelect.appendChild(opt);
                    }
                    // If current model isn't in the list, add it at the top
                    if (currentModel && !models.includes(currentModel)) {
                        const opt = document.createElement('option');
                        opt.value = currentModel;
                        opt.textContent = currentModel + ' (custom)';
                        opt.selected = true;
                        modelSelect.prepend(opt);
                    }
                } else {
                    const opt = document.createElement('option');
                    opt.value = currentModel;
                    opt.textContent = currentModel || 'No models found';
                    opt.selected = true;
                    modelSelect.appendChild(opt);
                }
            } catch {
                modelSelect.innerHTML = `<option value="${escapeAttr(config.model || '')}">Failed to load models</option>`;
            }
            if (btnRefresh) { btnRefresh.textContent = '\u21BB'; btnRefresh.disabled = false; }
        }

        if (modelSelect) populateModelDropdown();
        if (btnRefresh) {
            btnRefresh.addEventListener('click', populateModelDropdown);
        }

        // Toggle switches
        const catPunsToggle = $('toggleCatPuns');
        const gameAwareToggle = $('toggleGameAwareness');
        if (catPunsToggle) {
            catPunsToggle.setAttribute('aria-checked', config.cat_puns ? 'true' : 'false');
            catPunsToggle.onclick = async () => {
                const newVal = catPunsToggle.getAttribute('aria-checked') !== 'true';
                catPunsToggle.setAttribute('aria-checked', newVal);
                try {
                    await fetch('/api/catbyte/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ cat_puns: newVal }),
                    });
                } catch (e) { console.warn('Toggle cat puns failed:', e); }
            };
        }
        if (gameAwareToggle) {
            gameAwareToggle.setAttribute('aria-checked', config.game_awareness ? 'true' : 'false');
            gameAwareToggle.onclick = async () => {
                const newVal = gameAwareToggle.getAttribute('aria-checked') !== 'true';
                gameAwareToggle.setAttribute('aria-checked', newVal);
                try {
                    await fetch('/api/catbyte/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ game_awareness: newVal }),
                    });
                } catch (e) { console.warn('Toggle game awareness failed:', e); }
            };
        }

        // Setup hint
        $('catbyteSetupHint').innerHTML = escapeHtml(preset.setup_hint || '').replace(
            /`([^`]+)`/g, '<code>$1</code>'
        );

        // Check connection status
        const status = await fetchJSON('/api/catbyte/status');
        const dot = $('catbyteConnDot');
        const text = $('catbyteConnText');
        if (status.status === 'online') {
            dot.className = 'catbyte-conn-dot online';
            text.textContent = `Connected \u2014 ${status.backend_name || status.backend} (${status.model || 'default'})`;
        } else {
            dot.className = 'catbyte-conn-dot';
            text.textContent = status.message || 'Offline';
        }

        renderCatbyteSummary(config, status);
    } catch (e) {
        console.error('CatByte settings error:', e);
    }
}

// Bind test connection button
function bindCatbyteTest() {
    const btn = $('btnTestCatbyte');
    if (!btn) return;
    btn.addEventListener('click', async () => {
        btn.textContent = 'Testing...';
        btn.disabled = true;
        try {
            const d = await fetchJSON('/api/catbyte/test', { method: 'POST' });
            const dot = $('catbyteConnDot');
            const text = $('catbyteConnText');
            if (d.success) {
                dot.className = 'catbyte-conn-dot online';
                text.textContent = d.message;
                // Also refresh the main CatByte status
                checkCatbyteStatus();
            } else {
                dot.className = 'catbyte-conn-dot error';
                text.textContent = d.message;
            }
        } catch {
            $('catbyteConnDot').className = 'catbyte-conn-dot error';
            $('catbyteConnText').textContent = 'Network error';
        }
        btn.textContent = 'Test Connection';
        btn.disabled = false;
    });
}

async function addRomDir() {
    const input = $('romDirInput');
    const path = input.value.trim();
    if (!path) return;

    const addBtn = $('addRomDir');
    addBtn.textContent = 'Adding...';
    addBtn.disabled = true;

    try {
        await fetch('/api/rom-dirs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
    } catch (e) { console.warn('Add ROM dir failed:', e); }

    // Scan preview
    try {
        const scanData = await fetchJSON('/api/scan-rom-dir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        const preview = $('romDirPreview');
        if (preview && scanData.total > 0) {
            let tagsHtml = Object.entries(scanData.systems)
                .sort((a, b) => b[1] - a[1])
                .map(([sys, count]) => `<span class="dir-preview-tag">${escapeHtml(sys)}: ${count}</span>`)
                .join('');
            preview.innerHTML = `
                <div class="dir-preview-title">Found ${scanData.total} ROM files</div>
                <div class="dir-preview-systems">${tagsHtml}</div>`;
            preview.classList.remove('hidden');
            setTimeout(() => preview.classList.add('hidden'), 8000);
            showToast(`ROM directory added \u2014 <strong>${scanData.total}</strong> files found`, 'success');
        } else {
            showToast('ROM directory added', 'success');
        }
    } catch (e) {
        console.warn('ROM dir scan preview failed:', e);
        showToast('ROM directory added', 'success');
    }

    input.value = '';
    $('romDirValidation').textContent = '';
    addBtn.textContent = 'Add';
    addBtn.disabled = false;
    renderSettings();
    setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
}

async function addLocalDir() {
    const input = $('localDirInput');
    const path = input.value.trim();
    if (!path) return;

    const addBtn = $('addLocalDir');
    addBtn.textContent = 'Adding...';
    addBtn.disabled = true;

    try {
        await fetch('/api/local-dirs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
    } catch (e) { console.warn('Add local dir failed:', e); }
    input.value = '';
    $('localDirValidation').textContent = '';
    addBtn.textContent = 'Add';
    addBtn.disabled = false;
    showToast('Local game directory added', 'success');
    renderSettings();
    fetch('/api/rescan', { method: 'POST' }).catch(e => console.warn('Rescan failed:', e));
    setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
}

async function addBiosDir() {
    const input = $('biosDirInput');
    const path = input.value.trim();
    if (!path) return;

    const addBtn = $('addBiosDir');
    addBtn.textContent = 'Adding...';
    addBtn.disabled = true;

    try {
        await fetch('/api/bios/dirs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
    } catch (e) { console.warn('Add BIOS dir failed:', e); }
    input.value = '';
    addBtn.textContent = 'Add';
    addBtn.disabled = false;
    showToast('BIOS directory added', 'success');
    renderEmulationTab();
}

async function rescanLibrary() {
    const btn = $('btnRescan');
    btn.textContent = 'Scanning...';
    btn.disabled = true;
    showToast('Rescanning all libraries\u2026', 'info', 4000);
    fetch('/api/rescan', { method: 'POST' }).catch(e => console.warn('Rescan failed:', e));
    // Start polling for artwork progress (batch fetch starts after rescan)
    setTimeout(() => startArtworkProgressPoll(), 3000);
    setTimeout(async () => {
        await loadGames();
        await loadStores();
        applyFilter();
        btn.textContent = 'Rescan All Libraries';
        btn.disabled = false;
        showToast(`Scan complete \u2014 <strong>${state.games.length}</strong> games found`, 'success');
    }, 5000);
}

// ── Starfield ──────────────────────────────────────────────────────────────

function initStarfield() {
    const canvas = $('starfield');
    const ctx = canvas.getContext('2d');

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const stars = [];
    for (let i = 0; i < 200; i++) {
        stars.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            size: Math.random() * 1.5 + 0.5,
            speed: Math.random() * 0.3 + 0.05,
            opacity: Math.random() * 0.6 + 0.2,
            twinkleSpeed: Math.random() * 0.02 + 0.005,
            twinklePhase: Math.random() * Math.PI * 2,
        });
    }

    const nebulae = [];
    for (let i = 0; i < 3; i++) {
        nebulae.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            radius: Math.random() * 200 + 100,
            hue: Math.random() * 40 + 160,
            opacity: Math.random() * 0.03 + 0.01,
        });
    }

    let frame = 0;
    function animate() {
        // Pause when gaming mode is fullscreen — no point rendering behind it
        if (state.gamingMode) { requestAnimationFrame(animate); return; }
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        frame++;

        for (const n of nebulae) {
            const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.radius);
            grad.addColorStop(0, `hsla(${n.hue}, 80%, 50%, ${n.opacity})`);
            grad.addColorStop(1, 'transparent');
            ctx.fillStyle = grad;
            ctx.fillRect(n.x - n.radius, n.y - n.radius, n.radius * 2, n.radius * 2);
        }

        for (const star of stars) {
            const twinkle = Math.sin(frame * star.twinkleSpeed + star.twinklePhase);
            const opacity = star.opacity + twinkle * 0.2;
            ctx.beginPath();
            ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(200, 220, 255, ${Math.max(0, opacity)})`;
            ctx.fill();
            star.y += star.speed;
            if (star.y > canvas.height) {
                star.y = -2;
                star.x = Math.random() * canvas.width;
            }
        }

        requestAnimationFrame(animate);
    }
    animate();
}

function initParticles() {
    const container = $('particles');
    for (let i = 0; i < 15; i++) {
        const p = document.createElement('div');
        p.className = 'particle';
        p.style.left = Math.random() * 100 + '%';
        p.style.top = Math.random() * 100 + '%';
        p.style.animationDelay = Math.random() * 8 + 's';
        p.style.animationDuration = (6 + Math.random() * 6) + 's';
        container.appendChild(p);
    }
}

// ── Utilities ──────────────────────────────────────────────────────────────

function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function escapeAttr(s) {
    return s.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function debounce(fn, ms) {
    let t;
    return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}


// ── Gamepad Support ─────────────────────────────────────────────────────────

// Default W3C Standard button mapping (action → button index)
const GP_DEFAULT_MAP = {
    a: 0, b: 1, x: 2, y: 3,
    lb: 4, rb: 5, select: 8, start: 9,
    dup: 12, ddown: 13, dleft: 14, dright: 15,
};

// Active mapping — starts as defaults, overridden by user prefs
let gpMap = Object.assign({}, GP_DEFAULT_MAP);

// Remap UI state
let _gpRemapListening = null;   // action key currently listening for, or null

const _gp = {
    connected: false,
    index: null,
    polling: false,         // whether the rAF poll loop is running
    // Repeat timers: held buttons fire repeatedly after initial delay
    navRepeat: null,
    navDelay: 220,          // ms between repeated nav inputs
    navInitialDelay: 400,   // ms before repeat kicks in
    // Track button-down state to detect fresh presses
    prev: {},
    // Axis dead zone — 0.2 works well for DualSense, Xbox, and most controllers
    deadZone: 0.2,
    // Horizontal held direction
    heldDir: 0,
    holdStart: 0,
    holdFired: false,
    // Vertical held direction
    heldDirY: 0,
    holdStartY: 0,
    holdFiredY: false,
};

window.addEventListener('gamepadconnected', (e) => {
    _gp.connected = true;
    _gp.index = e.gamepad.index;
    $('gamepadIndicator').classList.remove('hidden');
    // Start polling only when a gamepad is connected
    if (!_gp.polling) {
        _gp.polling = true;
        requestAnimationFrame(pollGamepad);
    }
});

window.addEventListener('gamepaddisconnected', (e) => {
    if (_gp.index === e.gamepad.index) {
        _gp.connected = false;
        _gp.index = null;
        _gp.prev = {};
        _gp.heldDir = 0;
        _gp.heldDirY = 0;
        _gp.polling = false;  // stop polling — will restart on next connect
        $('gamepadIndicator').classList.add('hidden');
        // Reset tester UI
        const disc = $('gpTesterDisconnected');
        const conn = $('gpTesterConnected');
        if (disc) disc.classList.remove('hidden');
        if (conn) conn.classList.add('hidden');
        const container = $('gpTesterButtons');
        if (container) container.innerHTML = '';
        // Reset status bar
        const dot = $('gpStatusDot');
        const txt = $('gpStatusText');
        if (dot) { dot.classList.remove('connected'); dot.classList.add('disconnected'); }
        if (txt) txt.textContent = 'No controller detected';
    }
});

/** Handle gamepad input when the built-in emulator is running.
 *  EmulatorJS owns game input — we only handle meta controls (pause, save, exit). */
function pollGamepadEmulator(gp) {
    const pressed = (i) => gp.buttons[i] && gp.buttons[i].pressed;
    const justPressed = (i) => {
        const now = pressed(i);
        const was = _gp.prev[i] || false;
        _gp.prev[i] = now;
        return now && !was;
    };

    const btnB      = justPressed(1);   // Circle — back/exit
    const btnStart  = justPressed(9);   // Options — pause menu
    const btnSelect = justPressed(8);   // Create — screenshot
    const btnLB     = justPressed(4);   // L1 — quick save
    const btnRB     = justPressed(5);   // R1 — quick load

    // Options / Start → toggle pause menu
    if (btnStart) togglePauseMenu();

    // When pause menu is open, handle menu actions
    if (typeof emuPaused !== 'undefined' && emuPaused) {
        if (btnB)      exitEmulator();       // Circle → exit emulator
        if (btnLB)     emuSaveState();       // L1 → save state
        if (btnRB)     emuLoadState();       // R1 → load state
        if (btnSelect) emuScreenshot();      // Create → screenshot
    }
}

function pollGamepad() {
    if (!_gp.connected) { _gp.polling = false; return; }

    const gp = navigator.getGamepads()[_gp.index];
    if (!gp) { requestAnimationFrame(pollGamepad); return; }

    // When the built-in emulator is active, let EmulatorJS own the gamepad.
    // Only handle emulator-specific controls (pause menu, save/load, exit).
    if (typeof emuActive !== 'undefined' && emuActive) {
        pollGamepadEmulator(gp);
        requestAnimationFrame(pollGamepad);
        return;
    }

    const pressed = (i) => gp.buttons[i] && gp.buttons[i].pressed;
    const justPressed = (i) => {
        const now = pressed(i);
        const was = _gp.prev[i] || false;
        _gp.prev[i] = now;
        return now && !was;
    };

    // Read all button states via user-remappable mapping
    const btnA      = justPressed(gpMap.a);
    const btnB      = justPressed(gpMap.b);
    const btnY      = justPressed(gpMap.y);
    const btnLB     = justPressed(gpMap.lb);
    const btnRB     = justPressed(gpMap.rb);
    const btnSelect = justPressed(gpMap.select);
    const btnStart  = justPressed(gpMap.start);
    const dpadUp    = justPressed(gpMap.dup);
    const dpadDown  = justPressed(gpMap.ddown);
    const dpadLeft  = justPressed(gpMap.dleft);
    const dpadRight = justPressed(gpMap.dright);

    // Left stick axes
    const axisX = gp.axes[0] || 0;
    const axisY = gp.axes[1] || 0;
    const now = performance.now();

    // ── Determine horizontal nav direction ──
    let navDirX = 0;
    if (dpadLeft)  navDirX = -1;
    if (dpadRight) navDirX = 1;

    const stickDirX = Math.abs(axisX) > _gp.deadZone ? Math.sign(axisX) : 0;
    if (stickDirX !== 0) {
        if (_gp.heldDir !== stickDirX) {
            _gp.heldDir = stickDirX; _gp.holdStart = now; _gp.holdFired = false;
            navDirX = stickDirX;
        } else if (!_gp.holdFired && now - _gp.holdStart > _gp.navInitialDelay) {
            _gp.holdFired = true; _gp.holdStart = now; navDirX = stickDirX;
        } else if (_gp.holdFired && now - _gp.holdStart > _gp.navDelay) {
            _gp.holdStart = now; navDirX = stickDirX;
        }
    } else { _gp.heldDir = 0; }

    // ── Determine vertical nav direction ──
    let navDirY = 0;
    if (dpadUp)   navDirY = -1;
    if (dpadDown) navDirY = 1;

    const stickDirY = Math.abs(axisY) > _gp.deadZone ? Math.sign(axisY) : 0;
    if (stickDirY !== 0) {
        if (_gp.heldDirY !== stickDirY) {
            _gp.heldDirY = stickDirY; _gp.holdStartY = now; _gp.holdFiredY = false;
            navDirY = stickDirY;
        } else if (!_gp.holdFiredY && now - _gp.holdStartY > _gp.navInitialDelay) {
            _gp.holdFiredY = true; _gp.holdStartY = now; navDirY = stickDirY;
        } else if (_gp.holdFiredY && now - _gp.holdStartY > _gp.navDelay) {
            _gp.holdStartY = now; navDirY = stickDirY;
        }
    } else { _gp.heldDirY = 0; }

    // ── Gaming Mode: dedicated gamepad handling ──
    if (state.gamingMode) {
        if (btnB)      exitGamingMode();
        if (navDirX < 0) gamingNavigate('left');
        if (navDirX > 0) gamingNavigate('right');
        if (navDirY < 0) gamingNavigate('up');
        if (navDirY > 0) gamingNavigate('down');
        if (btnA)      gamingLaunch();
        if (btnY) {
            const game = state.filteredGames[state.gamingFocusIndex];
            if (game) toggleFavorite(game.id);
        }
        // Bumpers: cycle categories in gaming mode
        if (btnLB || btnRB) {
            const hexes = Array.from(document.querySelectorAll('.console-hex-wrap'));
            const activeIdx = hexes.findIndex(h => h.classList.contains('active'));
            const next = btnRB
                ? (activeIdx + 1) % hexes.length
                : (activeIdx - 1 + hexes.length) % hexes.length;
            selectConsoleHex(hexes[next].dataset.tab);
            renderGamingGrid();
            updateGamingInfo();
            updateGamingCategory();
        }
        requestAnimationFrame(pollGamepad);
        return;
    }

    // ── Normal mode ──

    // Check which overlay is open
    const settingsOpen = !$('settingsOverlay').classList.contains('hidden');
    const searchOpen   = !$('searchOverlay').classList.contains('hidden');
    const catbyteOpen  = !$('catbytePanel').classList.contains('hidden');
    const catbyteInfoOpen = !$('catbyteInfoOverlay').classList.contains('hidden');
    const anyOverlay   = settingsOpen || searchOpen || catbyteOpen || catbyteInfoOpen;

    // B: Back / Close
    if (btnB) {
        if (catbyteInfoOpen) $('catbyteInfoOverlay').classList.add('hidden');
        else if (searchOpen)   closeSearch();
        else if (settingsOpen) $('settingsOverlay').classList.add('hidden');
        else if (catbyteOpen)  $('catbytePanel').classList.add('hidden');
    }

    // Start: Toggle settings (hold Start+Select to enter gaming mode)
    if (btnStart) {
        if (!anyOverlay) enterGamingMode();
        else if (settingsOpen) $('settingsOverlay').classList.add('hidden');
    }

    // Select: Toggle search
    if (btnSelect) {
        if (searchOpen) closeSearch();
        else if (!anyOverlay) openSearch();
    }

    // Bumpers: Tab switching
    if (btnLB || btnRB) {
        if (settingsOpen) {
            const tabs = Array.from(document.querySelectorAll('.settings-tab'));
            const activeIdx = tabs.findIndex(t => t.classList.contains('active'));
            const next = btnRB
                ? (activeIdx + 1) % tabs.length
                : (activeIdx - 1 + tabs.length) % tabs.length;
            switchSettingsTab(tabs[next].dataset.stab);
            // Move focus into the new pane for clear visual feedback
            focusSettingControl(1);
        } else if (!anyOverlay) {
            const hexes = Array.from(document.querySelectorAll('.console-hex-wrap'));
            const activeIdx = hexes.findIndex(h => h.classList.contains('active'));
            const next = btnRB
                ? (activeIdx + 1) % hexes.length
                : (activeIdx - 1 + hexes.length) % hexes.length;
            selectConsoleHex(hexes[next].dataset.tab);
        }
    }

    // ── Settings panel: gamepad focus navigation ──
    // Claims D-pad / stick / A while settings is open (and the palette isn't),
    // so input doesn't bleed through to the carousel below.
    const paletteOpen = !$('settingsSearchOverlay').classList.contains('hidden');
    if (settingsOpen && !paletteOpen) {
        if (navDirY !== 0) focusSettingControl(navDirY);
        if (navDirX !== 0) focusSettingControl(navDirX);
        if (btnA) {
            const el = document.activeElement;
            if (el && el !== document.body && typeof el.click === 'function') el.click();
        }
        requestAnimationFrame(pollGamepad);
        return;
    }

    // Navigation (only when no text-input overlay is focused)
    if (navDirX !== 0 && !searchOpen) {
        navigateCarousel(navDirX);
    }

    // A: Launch / Confirm
    if (btnA && !anyOverlay) {
        launchSelected();
    }

    // Y: Favorite toggle
    if (btnY && !anyOverlay) {
        const game = state.filteredGames[state.selectedIndex];
        if (game) toggleFavorite(game.id);
    }

    requestAnimationFrame(pollGamepad);
}

// Gamepad poll loop starts on-demand when a gamepad connects (see gamepadconnected handler)


// ── Gamepad Tester & Remap UI ──────────────────────────────────────────────

const GP_BTN_LABELS = [
    'A','B','X','Y','LB','RB','LT','RT',
    'Sel','Sta','LS','RS',
    'Up','Dn','Lt','Rt','Home',
];

/** Update the live gamepad tester in the Controller settings tab. */
function updateGpTester() {
    if (!_gp.connected) return;
    const pane = $('settingsPane-controller');
    if (!pane || !pane.classList.contains('active')) return;

    const gp = navigator.getGamepads()[_gp.index];
    if (!gp) return;

    // ── Buttons ──
    const container = $('gpTesterButtons');
    if (container && container.children.length === 0) {
        // Build button grid on first call
        for (let i = 0; i < gp.buttons.length; i++) {
            const el = document.createElement('div');
            el.className = 'gp-tester-btn';
            el.dataset.idx = i;
            el.textContent = i < GP_BTN_LABELS.length ? GP_BTN_LABELS[i] : i;
            container.appendChild(el);
        }
    }
    if (container) {
        for (const el of container.children) {
            const idx = parseInt(el.dataset.idx);
            const p = gp.buttons[idx] && gp.buttons[idx].pressed;
            el.classList.toggle('active', !!p);
        }
    }

    // ── Axes ──
    for (let i = 0; i < 4; i++) {
        const val = gp.axes[i] || 0;
        const fill = $('gpAxis' + i);
        const valEl = $('gpAxisVal' + i);
        if (fill) {
            const pct = Math.abs(val) * 50;
            if (val >= 0) {
                fill.style.left = '50%';
                fill.style.width = pct + '%';
            } else {
                fill.style.left = (50 - pct) + '%';
                fill.style.width = pct + '%';
            }
        }
        if (valEl) valEl.textContent = val.toFixed(2);
    }

    // ── Remap listening mode: detect pressed button ──
    if (_gpRemapListening) {
        for (let i = 0; i < gp.buttons.length; i++) {
            if (gp.buttons[i] && gp.buttons[i].pressed) {
                gpMap[_gpRemapListening] = i;
                const btn = document.querySelector(`.gp-remap-btn[data-action="${_gpRemapListening}"]`);
                if (btn) {
                    btn.classList.remove('listening');
                    btn.querySelector('.gp-remap-current').textContent = i;
                }
                _gpRemapListening = null;
                saveGpMapping();
                break;
            }
        }
    }

    // Show/hide connected state
    const disc = $('gpTesterDisconnected');
    const conn = $('gpTesterConnected');
    if (disc) disc.classList.add('hidden');
    if (conn) conn.classList.remove('hidden');
    const nameEl = $('gpTesterName');
    if (nameEl) nameEl.textContent = gp.id;

    // Update status bar
    const dot = $('gpStatusDot');
    const txt = $('gpStatusText');
    if (dot) { dot.classList.remove('disconnected'); dot.classList.add('connected'); }
    if (txt) {
        let label = gp.id;
        if (label.includes('HID'))    label += '  \u2022  Direct HID';
        else if (label.includes('XInput')) label += '  \u2022  XInput';
        else label += '  \u2022  WinMM';
        txt.textContent = label;
    }
}

/** Load user's custom gamepad mapping from backend. */
function loadGpMapping() {
    fetchJSON('/api/settings')
        .then(data => {
            const mapping = data.values && data.values.gamepad_mapping;
            if (mapping && Object.keys(mapping).length) {
                Object.assign(gpMap, mapping);
            }
            refreshGpRemapUI();
        })
        .catch(() => {});
}

/** Save current gamepad mapping to backend. */
function saveGpMapping() {
    patchSetting('gamepad_mapping', gpMap).catch(() => {});
}

/** Update the remap button labels to reflect current mapping. */
function refreshGpRemapUI() {
    document.querySelectorAll('.gp-remap-btn').forEach(btn => {
        const action = btn.dataset.action;
        if (action && gpMap[action] !== undefined) {
            btn.querySelector('.gp-remap-current').textContent = gpMap[action];
        }
    });
}

/** Initialize remap button click handlers. */
function initGpRemap() {
    document.querySelectorAll('.gp-remap-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Cancel any previous listening
            document.querySelectorAll('.gp-remap-btn.listening').forEach(b => b.classList.remove('listening'));
            const action = btn.dataset.action;
            _gpRemapListening = action;
            btn.classList.add('listening');
            btn.querySelector('.gp-remap-current').textContent = '...';
        });
    });

    const resetBtn = $('gpResetMapping');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            Object.assign(gpMap, GP_DEFAULT_MAP);
            refreshGpRemapUI();
            saveGpMapping();
        });
    }

    loadGpMapping();
}

// Hook tester updates into the existing poll loop
const _origPollGamepad = pollGamepad;

// Run tester at ~30fps when the controller tab is open
setInterval(updateGpTester, 33);


// ── Start ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    init();
    initGpRemap();
});
