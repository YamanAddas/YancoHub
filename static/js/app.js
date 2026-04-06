/**
 * YancoHub — Frontend Application
 * 3D hexagonal crystal carousel, adapted from YancoDeck.
 */

// ── Constants ──────────────────────────────────────────────────────────────

const VISIBLE_HALF = 4; // cards visible on each side of center

// ── State ──────────────────────────────────────────────────────────────────

const state = {
    games: [],
    filteredGames: [],
    selectedIndex: 0,
    currentTab: 'all',
    collections: {},
    favorites: new Set(),
    hiddenSystems: new Set(),
    playtimes: {},
    stores: {},
    chatHistory: [],
    scanning: false,
    catbyteOnline: false,
    activeMood: null,
};

// ── DOM ────────────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);
const $$ = (sel) => document.querySelectorAll(sel);
const qs = (sel) => document.querySelector(sel);

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

    bindEvents();
}

async function waitForBackend() {
    for (let i = 0; i < 30; i++) {
        try {
            const r = await fetch('/health');
            if (r.ok) return;
        } catch {}
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
        const r = await fetch('/api/games');
        const data = await r.json();
        if (data.status === 'scanning') {
            state.games = [];
            state.scanning = true;
            return;
        }
        state.games = Array.isArray(data) ? data : (data.games || []);
        state.scanning = false;
    } catch { state.games = []; state.scanning = false; }
}

async function loadStores() {
    try {
        const r = await fetch('/api/stores');
        state.stores = await r.json();
        renderStoreIndicators();
    } catch {}
}

async function loadFavorites() {
    try {
        const r = await fetch('/api/favorites');
        state.favorites = new Set(await r.json());
    } catch {}
}

async function loadCollections() {
    try {
        const r = await fetch('/api/collections');
        state.collections = await r.json();
    } catch {}
}

async function loadHiddenSystems() {
    try {
        const r = await fetch('/api/hidden-systems');
        state.hiddenSystems = new Set(await r.json());
    } catch {}
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
        const r = await fetch('/api/artwork/progress');
        const p = await r.json();
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
        const r = await fetch('/api/playtime');
        state.playtimes = await r.json();
    } catch {}
}

async function checkCatbyteStatus() {
    let d = null;
    try {
        const r = await fetch('/api/catbyte/status');
        d = await r.json();
        state.catbyteOnline = d.status === 'online';
    } catch {
        state.catbyteOnline = false;
    }
    const on = state.catbyteOnline;
    $('catbyteStatusDot').classList.toggle('online', on);
    $('catbyteStatus').textContent = on ? (d && d.model ? `Online (${d.model.toUpperCase()})` : 'Online') : 'Offline';
    $('catbyteStatus').classList.toggle('online', on);
    $('btnCatbyte').classList.toggle('dimmed', !on);
    $('btnCatbyte').title = on ? 'CatByte AI (F10)' : 'CatByte offline — check Settings (F10)';
}

// ── Filtering & Carousel ───────────────────────────────────────────────────

function applyFilter() {
    const tab = state.currentTab;
    let games = [...state.games];

    switch (tab) {
        case 'all': break;
        case 'favorites':
            games = games.filter(g => state.favorites.has(g.id));
            break;
        case 'recent':
            games = games.filter(g => g.last_played);
            games.sort((a, b) => (b.last_played || 0) - (a.last_played || 0));
            break;
        case 'retro':
            games = games.filter(g => g.source === 'retro');
            break;
        default:
            // Check if it's a retro system tab (e.g. "retro_snes")
            if (tab.startsWith('retro_')) {
                const sys = tab.slice(6);
                games = games.filter(g => g.source === 'retro' && g.system === sys);
            } else {
                games = games.filter(g => g.source === tab);
            }
            break;
    }

    if (tab !== 'recent') {
        games.sort((a, b) => {
            const af = state.favorites.has(a.id) ? 0 : 1;
            const bf = state.favorites.has(b.id) ? 0 : 1;
            if (af !== bf) return af - bf;
            return a.name.localeCompare(b.name);
        });
    }

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

const BRAND_SVG = {
    all: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>`,
    favorites: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.56 5.82 22 7 14.14l-5-4.87 6.91-1.01z"/></svg>`,
    recent: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/></svg>`,
    steam: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 0 0-9.95 11.08l5.34 2.2a2.85 2.85 0 0 1 1.6-.49h.12l2.39-3.46v-.05a3.8 3.8 0 1 1 3.8 3.8h-.09l-3.4 2.43a2.86 2.86 0 0 1-5.67.42L1.7 16.24A10 10 0 1 0 12 2zm-4.53 15.8a2.15 2.15 0 0 0 2.27-1.08l-1.18-.49a1.58 1.58 0 0 1-2.06.78 1.59 1.59 0 0 1-.83-2.08l-1.1-.45a2.86 2.86 0 0 0 2.9 3.32zm9.16-6.18a2.54 2.54 0 1 0-2.54-2.54 2.54 2.54 0 0 0 2.54 2.54z"/></svg>`,
    epic: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.537 0C2.165 0 1.66.506 1.66 1.879V18.12c0 1.374.504 1.88 1.877 1.88h3.965v-1.21H4.283c-.69 0-.943-.252-.943-.942V2.15c0-.69.254-.94.943-.94h11.434c.69 0 .943.25.943.94v15.7c0 .69-.253.943-.943.943h-2.5l-1.51 1.21h4.764c1.373 0 1.877-.506 1.877-1.88V1.88C18.348.506 17.844 0 16.47 0H3.537zM6.1 6.4v7.2h5.2v-1.2H7.4v-1.8h3.2V9.4H7.4V7.6h3.9V6.4H6.1z"/></svg>`,
    gog: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 17.5c-4.14 0-7.5-3.36-7.5-7.5S7.86 4.5 12 4.5s7.5 3.36 7.5 7.5-3.36 7.5-7.5 7.5zm0-12a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zm0 6.75a2.25 2.25 0 1 1 0-4.5 2.25 2.25 0 0 1 0 4.5z"/></svg>`,
    xbox: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6.19 5.18c-.75.75-1.33 1.6-1.75 2.52 1.06-.36 2.44.14 4.16 1.68 1.37 1.23 2.55 2.78 3.4 4.1.85-1.32 2.03-2.87 3.4-4.1 1.72-1.54 3.1-2.04 4.16-1.68-.42-.92-1-1.77-1.75-2.52-1.28.23-2.79 1.1-4.4 2.74-.47.47-.91.97-1.3 1.46l-.11.14-.11-.14c-.39-.49-.83-.99-1.3-1.46-1.61-1.64-3.12-2.51-4.4-2.74zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 1.5c1.83 0 3.51.59 4.89 1.58-1.53-.13-3.2.78-4.89 2.49-1.69-1.71-3.36-2.62-4.89-2.49A8.46 8.46 0 0 1 12 3.5zM3.5 12c0-1.33.32-2.59.88-3.71.01 1.56 1.2 3.32 3.07 5 1.36 1.22 2.82 2.32 3.87 3.07-.3.27-.83.68-1.2.89C7.48 18.98 3.5 16.11 3.5 12zm8.5 8.5c-.56 0-1.1-.06-1.63-.16.59-.33 1.2-.76 1.63-1.17.43.41 1.04.84 1.63 1.17-.53.1-1.07.16-1.63.16zm5.38-3.25c-.37-.21-.9-.62-1.2-.89 1.05-.75 2.51-1.85 3.87-3.07 1.87-1.68 3.06-3.44 3.07-5 .56 1.12.88 2.38.88 3.71 0 4.11-3.98 6.98-6.62 5.25z"/></svg>`,
    ea: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 5v14h18V5H3zm16.5 12.5h-15V6.5h15v11zM6 9h5.5v1.5h-4V12h3.5v1.5H7.5V15h4v1.5H6V9zm7 0h2.2l1.8 4 1.8-4H21v7.5h-1.5v-5l-1.7 3.5h-1.1L15 11v5.5h-2V9z"/></svg>`,
    ubisoft: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18.25c-1.41 0-2.73-.36-3.88-1 .49.13 1.01.2 1.54.2 3.39 0 6.14-2.75 6.14-6.14 0-2.27-1.23-4.25-3.07-5.31.33-.06.67-.1 1.01-.1 3.59 0 6.51 2.91 6.51 6.51 0 3.21-2.32 5.88-5.38 6.42-.28.04-.57.06-.87.08-.65.22-1.3.34-2 .34zm-3.43-2.3A5.14 5.14 0 0 1 6.8 13.5c0-2.85 2.3-5.16 5.16-5.16.77 0 1.5.17 2.16.47a5.15 5.15 0 0 1 2.99 4.69c0 1.98-1.12 3.7-2.76 4.55a4.37 4.37 0 0 0 .56-2.14c0-2.43-1.97-4.4-4.4-4.4a4.41 4.41 0 0 0-4.4 4.4c0 .74.19 1.43.52 2.04zm1.87.3a3.19 3.19 0 0 1-1.4-2.64 3.2 3.2 0 0 1 3.2-3.2 3.2 3.2 0 0 1 3.2 3.2c0 .98-.44 1.85-1.13 2.43a3.62 3.62 0 0 0 1.34-2.82c0-2-1.63-3.63-3.63-3.63A3.64 3.64 0 0 0 8.4 15.2c0 1.19.58 2.24 1.47 2.9-.15-.05-.3-.12-.43-.2z"/></svg>`,
    battlenet: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.73 14.24c-.44.7-1.26 1.05-2.12.87-.48-.1-.91-.36-1.27-.7l-.18.3c.55.67.8 1.54.6 2.4-.12.5-.4.93-.78 1.25A8.46 8.46 0 0 1 12 20.5a8.46 8.46 0 0 1-1.97-.23c.12-.35.15-.73.06-1.12a2.15 2.15 0 0 0-1.32-1.5l.05-.33c-.87.07-1.72-.35-2.17-1.12-.25-.44-.33-.93-.26-1.41l-.28-.16c-.35.77-.99 1.36-1.79 1.59a8.46 8.46 0 0 1-.82-3.22c.37.04.75-.02 1.1-.2a2.15 2.15 0 0 0 1.06-1.73h.34c.32.86 1.1 1.47 2.04 1.54.52.04 1.02-.1 1.43-.37l.28.16c-.2.86-.02 1.77.55 2.45.32.38.74.64 1.2.78v.35c-.87.28-1.72.12-2.38-.36a8.46 8.46 0 0 0 2.86 1c.3-.25.55-.56.71-.93a2.15 2.15 0 0 0-.27-2.02l.23-.26c.72.57 1.66.72 2.52.36.48-.2.87-.55 1.13-.98l.3.12c.04.91-.37 1.79-1.1 2.35a8.46 8.46 0 0 0 1.89-2.47c-.37.02-.75-.07-1.08-.28a2.15 2.15 0 0 0-.8-1.82l-.1-.34z"/></svg>`,
    local: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`,
    retro: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 2h-11A5.5 5.5 0 0 0 1 7.5v9A5.5 5.5 0 0 0 6.5 22h11a5.5 5.5 0 0 0 5.5-5.5v-9A5.5 5.5 0 0 0 17.5 2zM9 13H7v2a1 1 0 0 1-2 0v-2H3a1 1 0 0 1 0-2h2V9a1 1 0 0 1 2 0v2h2a1 1 0 0 1 0 2zm5 2a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm4-2a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"/></svg>`,
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

function buildRetroTabs() {
    // Legacy cleanup
    document.querySelectorAll('.tab-retro-system').forEach(t => t.remove());

    // Build the full hex panel with all tabs
    buildConsolePanel();
}

function buildConsolePanel() {
    const scroll = $('consolePanelScroll');
    if (!scroll) return;
    scroll.innerHTML = '';

    // ── Count games per source & retro system ──
    const sourceCounts = {};
    const systemCounts = {};
    for (const g of state.games) {
        const src = g.source || 'local';
        sourceCounts[src] = (sourceCounts[src] || 0) + 1;
        if (src === 'retro' && g.system && !state.hiddenSystems.has(g.system)) {
            systemCounts[g.system] = (systemCounts[g.system] || 0) + 1;
        }
    }
    const totalGames = state.games.length;
    const totalFavorites = state.favorites ? state.favorites.size : 0;
    const totalRecent = state.games.filter(g => g.last_played).length;
    const totalRetro = sourceCounts['retro'] || 0;

    // ── Utility section: All, Favorites, Recent ──
    _addHexTab(scroll, 'all', totalGames);
    if (totalFavorites > 0) _addHexTab(scroll, 'favorites', totalFavorites);
    if (totalRecent > 0) _addHexTab(scroll, 'recent', totalRecent);

    // ── Divider ──
    _addHexDivider(scroll, 'Stores');

    // ── Store tabs (only those with games) ──
    for (const src of STORE_SOURCES) {
        const count = sourceCounts[src] || 0;
        if (count === 0) continue;
        _addHexTab(scroll, src, count);
    }

    // ── Retro section ──
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
    const svg = BRAND_SVG[tab] || '';
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

function _addHexDivider(container, label) {
    const div = document.createElement('div');
    div.className = 'console-hex-divider';
    div.innerHTML = `<span>${label}</span>`;
    container.appendChild(div);
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
        toggle.classList.add('panel-open');
        app.classList.add('console-panel-open');
    } else {
        panel.classList.add('hidden');
        toggle.classList.remove('panel-open');
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
            toggle.classList.add('panel-open');
            $('app').classList.add('console-panel-open');
        }
    }
    toggle.style.display = state.games.length > 0 ? '' : 'none';
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
        const r = await fetch('/api/catbyte/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: prompt, history: [] }),
        });
        const d = await r.json();
        // Only show if mood hasn't changed while we were waiting
        if (d.response && d.status !== 'offline' && state.activeMood === mood) {
            textEl.textContent = d.response;
            bubble.classList.remove('hidden');
        }
    } catch {
        // Silent fail — non-blocking
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
        const stars = '★'.repeat(Math.round(game.community_rating)) + '☆'.repeat(5 - Math.round(game.community_rating));
        badges.push(`<span class="meta-badge fav">${stars}</span>`);
    }
    if (game.installed === false) {
        badges.push(`<span class="meta-badge" style="background:rgba(255,255,255,0.05);color:var(--text-dim)">Not Installed</span>`);
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

function updateDetailPanel(game) {
    const panel = $('detailPanel');
    if (!game) {
        panel.classList.remove('visible');
        return;
    }

    // Description
    $('detailDesc').textContent = game.description || '';

    // Favorite button state
    const isFav = state.favorites.has(game.id);
    $('detailFavIcon').textContent = isFav ? '★' : '☆';
    const favBtn = $('detailFavorite');
    favBtn.classList.toggle('fav-active', isFav);

    // Close any open dropdown
    $('collectionDropdown').classList.add('hidden');

    // Show the panel with slide-up animation
    panel.classList.add('visible');
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

// ── Store Indicators ───────────────────────────────────────────────────────

function renderStoreIndicators() {
    const names = {
        steam: 'Steam', epic: 'Epic', gog: 'GOG', xbox: 'Xbox',
        ea: 'EA', ubisoft: 'Ubisoft', battlenet: 'Battle.net', retroarch: 'RetroArch'
    };
    $('storeIndicators').innerHTML = Object.entries(state.stores)
        .map(([k, v]) => `<div class="store-dot ${v ? 'active' : ''}" data-label="${names[k] || k}" title="${names[k]}: ${v ? 'Detected' : 'Not found'}"></div>`)
        .join('');
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

    // Search
    $('btnSearch').addEventListener('click', openSearch);
    $('closeSearch').addEventListener('click', closeSearch);
    $('searchInput').addEventListener('input', debounce(doSearch, 200));

    // CatByte
    $('btnCatbyte').addEventListener('click', toggleCatbyte);
    $('closeCatbyte').addEventListener('click', () => $('catbytePanel').classList.add('hidden'));
    $('catbyteSend').addEventListener('click', sendCatbyteMessage);
    $('catbyteScreenshot').addEventListener('click', sendScreenshot);
    $('catbyteInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendCatbyteMessage(); });
    $('dismissCatbyteInfo').addEventListener('click', () => $('catbyteInfoOverlay').classList.add('hidden'));
    $('btnOpenCatbyteSettings').addEventListener('click', () => {
        $('catbyteInfoOverlay').classList.add('hidden');
        openSettings();
        switchSettingsTab('catbyte');
    });

    // Detail panel actions
    $('detailLaunch').addEventListener('click', launchSelected);
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
    $('addRomDir').addEventListener('click', addRomDir);
    $('addLocalDir').addEventListener('click', addLocalDir);
    $('addBiosDir').addEventListener('click', addBiosDir);
    $('btnRescan').addEventListener('click', rescanLibrary);
    $('btnConnectSteam').addEventListener('click', connectSteam);
    $('btnToggleUninstalled').addEventListener('click', toggleShowUninstalled);

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
        // Don't navigate if a text input is focused
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) ||
            e.target.isContentEditable) return;

        if (e.key === 'ArrowLeft')  { e.preventDefault(); navigateCarousel(-1); }
        if (e.key === 'ArrowRight') { e.preventDefault(); navigateCarousel(1); }
        if (e.key === 'Enter')      { e.preventDefault(); launchSelected(); }

        if (e.ctrlKey && e.key === 'f') { e.preventDefault(); openSearch(); }
        if (e.key === 'F10') { e.preventDefault(); toggleCatbyte(); }
        if (e.ctrlKey && e.key === 'b') { e.preventDefault(); toggleCatbyte(); }
        if (e.ctrlKey && e.key === ',') { e.preventDefault(); openSettings(); }
        if (e.ctrlKey && e.shiftKey && e.key === 'S') { e.preventDefault(); sendScreenshot(); }

        if (e.key === 'Escape') {
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
        const r = await fetch('/api/favorites/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_id: gameId }),
        });
        const d = await r.json();
        if (d.is_favorite) state.favorites.add(gameId);
        else state.favorites.delete(gameId);
        // Refresh carousel to update star badge
        renderCarousel();
        updateGameInfo();
    } catch {}
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
            if (inCol) {
                await fetch(`/api/collections/${encodeURIComponent(name)}/games/${encodeURIComponent(game.id)}`, { method: 'DELETE' });
            } else {
                await fetch(`/api/collections/${encodeURIComponent(name)}/games`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ game_id: game.id }),
                });
            }
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
    } catch {}
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
        const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
        const results = await r.json();

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
    } catch {}
}

// ── CatByte ────────────────────────────────────────────────────────────────

function toggleCatbyte() {
    $('catbytePanel').classList.toggle('hidden');
    if (!$('catbytePanel').classList.contains('hidden')) {
        $('catbyteInput').focus();
        checkCatbyteStatus();
    }
}

async function sendCatbyteMessage() {
    const msg = $('catbyteInput').value.trim();
    if (!msg) return;

    appendChat('user', msg);
    $('catbyteInput').value = '';
    state.chatHistory.push({ role: 'user', content: msg });

    const game = state.filteredGames[state.selectedIndex];

    try {
        const r = await fetch('/api/catbyte/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: msg,
                history: state.chatHistory.slice(-10),
                game_context: game?.name || '',
            }),
        });
        const d = await r.json();
        appendChat('bot', d.response);
        state.chatHistory.push({ role: 'assistant', content: d.response });
    } catch {
        appendChat('bot', '\uD83D\uDE3F Connection error — check your AI backend in Settings.');
    }
}

function appendChat(role, text) {
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.innerHTML = `<div class="chat-bubble">${escapeHtml(text)}</div>`;
    $('catbyteMessages').appendChild(div);
    $('catbyteMessages').scrollTop = $('catbyteMessages').scrollHeight;
}

async function sendScreenshot() {
    if (!state.catbyteOnline) return;

    try {
        const canvas = document.createElement('canvas');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        const ctx = canvas.getContext('2d');

        // Draw the starfield canvas first
        const starfield = document.getElementById('starfield');
        if (starfield) ctx.drawImage(starfield, 0, 0);

        // For game screenshots during emulator play, grab the emulator canvas
        const emuCanvas = document.querySelector('#emuGame canvas');
        if (emuCanvas) {
            ctx.drawImage(emuCanvas, 0, 0, canvas.width, canvas.height);
        }

        // Convert to base64 JPEG (smaller than PNG)
        const base64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];

        // Show a prompt for the user's question
        const question = prompt('What do you want to ask CatByte about this screenshot?');
        if (!question) return;

        // Show in chat — open panel if hidden
        if ($('catbytePanel').classList.contains('hidden')) {
            $('catbytePanel').classList.remove('hidden');
        }

        appendChat('user', '\uD83D\uDCF8 ' + question);
        state.chatHistory.push({ role: 'user', content: '[Screenshot] ' + question });

        // Send to vision endpoint
        const game = state.filteredGames[state.selectedIndex];
        const r = await fetch('/api/catbyte/chat-vision', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: question,
                image: base64,
                history: state.chatHistory.slice(-6),
                game_context: game?.name || '',
            }),
        });
        const d = await r.json();
        appendChat('bot', d.response);
        state.chatHistory.push({ role: 'assistant', content: d.response });
    } catch (err) {
        console.error('Screenshot capture failed:', err);
        appendChat('bot', '\uD83D\uDE3F Screenshot capture failed. Try again!');
    }
}

// ── Settings ───────────────────────────────────────────────────────────────

async function connectSteam() {
    const apiKey = $('steamApiKey').value.trim();
    const steamId = $('steamIdInput').value.trim();
    const status = $('steamConnectStatus');

    if (!apiKey || !steamId) {
        status.style.color = 'var(--danger)';
        status.textContent = 'Both API key and Steam ID are required';
        return;
    }

    status.style.color = 'var(--accent)';
    status.textContent = 'Connecting...';

    try {
        const r = await fetch('/api/accounts/steam/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey, steam_id: steamId }),
        });
        const d = await r.json();

        if (r.ok) {
            status.style.color = 'var(--success)';
            status.textContent = `Connected as ${d.persona_name}! Library loading...`;
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
            const r = await fetch('/api/validate-path', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path }),
            });
            const d = await r.json();
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

async function toggleShowUninstalled() {
    try {
        const r = await fetch('/api/settings/show-uninstalled', { method: 'POST' });
        const d = await r.json();
        $('btnToggleUninstalled').textContent = d.show_uninstalled
            ? 'Hide Uninstalled Games'
            : 'Show Uninstalled Games';
        setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
    } catch {}
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
        const [accountsResp, epicManifestResp] = await Promise.all([
            fetch('/api/accounts'),
            fetch('/api/epic/manifest-count'),
        ]);
        const accounts = await accountsResp.json();
        const epicManifest = await epicManifestResp.json();

        let accountsHtml = '';

        // Steam
        const steam = accounts.steam || {};
        if (steam.connected) {
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🎮</div>
                    <div class="account-info">
                        <div class="account-name">Steam</div>
                        <div class="account-detail">${escapeHtml(steam.persona_name || 'Connected')}</div>
                    </div>
                    <div class="account-status connected"></div>
                    <button class="account-btn disconnect" id="btnDisconnectSteam">Disconnect</button>
                </div>`;
        } else {
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🎮</div>
                    <div class="account-info">
                        <div class="account-name">Steam</div>
                        <div class="account-detail">Not connected</div>
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
        const btnShowSteam = document.getElementById('btnShowSteamConnect');
        if (btnShowSteam) {
            btnShowSteam.addEventListener('click', () => {
                $('steamConnectSection').classList.remove('hidden');
            });
        }
        const btnDisconnect = document.getElementById('btnDisconnectSteam');
        if (btnDisconnect) {
            btnDisconnect.addEventListener('click', async () => {
                await fetch('/api/accounts/steam/disconnect', { method: 'POST' });
                $('steamConnectSection').classList.add('hidden');
                renderSettings();
                setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
            });
        }
        const btnGalaxy = document.getElementById('btnToggleGalaxy');
        if (btnGalaxy) {
            btnGalaxy.addEventListener('click', async () => {
                await fetch('/api/accounts/gog-galaxy/toggle', { method: 'POST' });
                renderSettings();
                setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
            });
        }
        const btnEpicAuth = document.getElementById('btnEpicAuth');
        if (btnEpicAuth) {
            btnEpicAuth.addEventListener('click', async () => {
                btnEpicAuth.textContent = 'Connecting...';
                btnEpicAuth.disabled = true;
                const r = await fetch('/api/accounts/epic/auth', { method: 'POST' });
                const d = await r.json();
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
    } catch {}

    // ── Show/Hide Uninstalled toggle ──
    try {
        const uResp = await fetch('/api/settings/show-uninstalled');
        const uData = await uResp.json();
        $('btnToggleUninstalled').textContent = uData.show_uninstalled
            ? 'Hide Uninstalled Games'
            : 'Show Uninstalled Games';
    } catch {
        $('btnToggleUninstalled').textContent = 'Toggle Show Uninstalled Games';
    }

    // ── Detected Stores ──
    const storeNames = {
        steam: 'Steam', epic: 'Epic Games', gog: 'GOG Galaxy', xbox: 'Xbox/Game Pass',
        ea: 'EA Desktop', ubisoft: 'Ubisoft Connect', battlenet: 'Battle.net', retroarch: 'RetroArch'
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
        const r = await fetch('/api/rom-dirs');
        romDirs = await r.json();
        $('settingsRomDirs').innerHTML = romDirs.map(d => `
            <div class="dir-entry">
                <span class="dir-icon">\uD83D\uDCC2</span>
                <span>${escapeHtml(d)}</span>
                <button class="dir-remove" data-dir="${escapeAttr(d)}" data-type="rom">&times;</button>
            </div>
        `).join('') || '<div style="color:var(--text-dim);font-size:12px;padding:4px 0">No ROM directories configured</div>';
    } catch {}

    // Local dirs
    try {
        const r = await fetch('/api/local-dirs');
        localDirs = await r.json();
        $('settingsLocalDirs').innerHTML = localDirs.map(d => `
            <div class="dir-entry">
                <span class="dir-icon">\uD83C\uDFAE</span>
                <span>${escapeHtml(d)}</span>
                <button class="dir-remove" data-dir="${escapeAttr(d)}" data-type="local">&times;</button>
            </div>
        `).join('') || '<div style="color:var(--text-dim);font-size:12px;padding:4px 0">No local game directories configured</div>';
    } catch {}

    renderDirectoriesSummary(romDirs, localDirs);

    // Bind remove buttons
    $$('.dir-remove').forEach(btn => {
        btn.addEventListener('click', async () => {
            const dirPath = btn.dataset.dir;
            const typeLabel = { rom: 'ROM', local: 'local game', bios: 'BIOS' }[btn.dataset.type] || '';
            if (!confirm(`Remove ${typeLabel} directory?\n${dirPath}`)) return;
            const typeMap = { rom: '/api/rom-dirs', local: '/api/local-dirs', bios: '/api/bios/dirs' };
            const endpoint = typeMap[btn.dataset.type] || '/api/local-dirs';
            await fetch(endpoint, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: dirPath }),
            });
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
        const [bdResp, bsResp] = await Promise.all([
            fetch('/api/bios/dirs'),
            fetch('/api/bios/status'),
        ]);
        const biosDirs = await bdResp.json();
        const biosStatus = await bsResp.json();
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
                await fetch('/api/bios/dirs', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: btn.dataset.dir }),
                });
                showToast('BIOS directory removed', 'info');
                renderEmulationTab();
            });
        });
    } catch {}

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
            const r = await fetch('/api/hidden-systems/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ system: btn.dataset.system }),
            });
            const d = await r.json();
            if (d.is_hidden) state.hiddenSystems.add(btn.dataset.system);
            else state.hiddenSystems.delete(btn.dataset.system);
            btn.classList.toggle('hidden-sys', d.is_hidden);
            btn.classList.toggle('active', !d.is_hidden);
        });
    });

    // RetroArch path
    try {
        const raResp = await fetch('/api/settings/retroarch-path');
        const raData = await raResp.json();
        if (raData.retroarch_path) $('retroarchPathInput').value = raData.retroarch_path;
    } catch {}

    // LaunchBox path
    let lbPath = '';
    try {
        const lbResp = await fetch('/api/settings/launchbox-path');
        const lbData = await lbResp.json();
        lbPath = lbData.launchbox_path || '';
        $('launchboxPathInput').value = lbPath;
        $('launchboxStatus').textContent = lbPath
            ? 'Artwork will be loaded directly from LaunchBox — no files copied.'
            : '';
    } catch {}

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
        const r = await fetch('/api/settings/launchbox-path', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        const d = await r.json();
        if (d.error) {
            $('launchboxStatus').textContent = d.error;
            $('launchboxStatus').style.color = 'var(--danger, #ff4444)';
            showToast(d.error, 'error');
        } else {
            const msg = path
                ? `Saved. ${d.matched_count != null ? d.matched_count + ' games matched.' : 'Artwork will load from LaunchBox.'}`
                : 'Cleared.';
            $('launchboxStatus').textContent = msg;
            $('launchboxStatus').style.color = 'var(--accent)';
            showToast(path ? `LaunchBox linked \u2014 <strong>${d.matched_count ?? '?'}</strong> games indexed` : 'LaunchBox path cleared', 'success');
        }
    } catch {
        $('launchboxStatus').textContent = 'Failed to save.';
        $('launchboxStatus').style.color = 'var(--danger, #ff4444)';
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
        const r = await fetch('/api/settings/retroarch-path', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        const d = await r.json();
        if (d.error) {
            $('retroarchStatus').textContent = d.error;
            $('retroarchStatus').style.color = 'var(--danger, #ff4444)';
            showToast(d.error, 'error');
        } else {
            const msg = path ? 'RetroArch path saved.' : 'Cleared.';
            $('retroarchStatus').textContent = msg;
            $('retroarchStatus').style.color = 'var(--accent)';
            showToast(path ? 'RetroArch path saved' : 'RetroArch path cleared', 'success');
        }
    } catch {
        $('retroarchStatus').textContent = 'Failed to save.';
        $('retroarchStatus').style.color = 'var(--danger, #ff4444)';
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
        const r = await fetch('/api/test/retroarch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        const d = await r.json();
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
        const r = await fetch('/api/test/launchbox', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        const d = await r.json();
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
        const resp = await fetch('/api/emulators/status');
        const data = await resp.json();

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
        const resp = await fetch('/api/emulators/setup', { method: 'POST' });
        const data = await resp.json();
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
        const resp = await fetch('/api/emulators/progress');
        const p = await resp.json();
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
    } catch {}
}

// ── CatByte Settings Tab ──────────────────────────────────────────────────

async function renderCatbyteTab() {
    try {
        const [configResp, presetsResp] = await Promise.all([
            fetch('/api/catbyte/config'),
            fetch('/api/catbyte/presets'),
        ]);
        const config = await configResp.json();
        const presets = await presetsResp.json();

        // Backend selector cards
        const backendOrder = ['openclaw', 'ollama', 'lmstudio', 'openai', 'custom'];
        let backendHtml = '';
        for (const key of backendOrder) {
            const p = presets[key];
            if (!p) continue;
            const selected = config.backend === key;
            const badgeClass = p.local ? 'local' : 'cloud';
            const badgeText = p.local ? 'Local' : 'Cloud';
            backendHtml += `
                <div class="backend-card ${selected ? 'selected' : ''}" data-backend="${key}">
                    <div class="backend-card-header">
                        <span class="backend-card-radio"></span>
                        <span class="backend-card-name">${escapeHtml(p.name)}</span>
                        <span class="backend-card-badge ${badgeClass}">${badgeText}</span>
                    </div>
                    <div class="backend-card-desc">${escapeHtml(p.description)}</div>
                </div>`;
        }
        $('catbyteBackendSelector').innerHTML = backendHtml;

        // Bind backend card clicks
        $$('.backend-card').forEach(card => {
            card.addEventListener('click', async () => {
                const backend = card.dataset.backend;
                await fetch('/api/catbyte/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ backend }),
                });
                renderCatbyteTab();
            });
        });

        // Custom fields (URL, API key, model) based on selected backend
        const preset = presets[config.backend] || {};
        let fieldsHtml = '';

        if (config.backend === 'custom' || config.backend === 'openai') {
            if (config.backend === 'custom') {
                fieldsHtml += `
                    <div class="settings-field">
                        <label class="settings-label">Base URL</label>
                        <input type="text" class="settings-input" id="catbyteBaseUrl"
                               value="${escapeAttr(config.base_url || '')}"
                               placeholder="http://localhost:8080">
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

        // Model field for backends that support multiple models
        if (['openclaw', 'ollama', 'lmstudio', 'openai', 'custom'].includes(config.backend)) {
            fieldsHtml += `
                <div class="settings-field">
                    <label class="settings-label">Model</label>
                    <div class="settings-input-row">
                        <input type="text" class="settings-input" id="catbyteModel"
                               value="${escapeAttr(config.model || '')}"
                               placeholder="${escapeAttr(preset.default_model || 'default')}">
                        <button class="btn-small" id="btnRefreshModels" title="Refresh available models">&#8635;</button>
                    </div>
                    <div id="catbyteModelList" class="catbyte-model-list"></div>
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
                await fetch('/api/catbyte/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updates),
                });
                btnSave.textContent = 'Saved!';
                setTimeout(() => { btnSave.textContent = 'Save'; }, 1500);
            });
        }

        // Bind refresh models button
        const btnRefresh = document.getElementById('btnRefreshModels');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', async () => {
                btnRefresh.textContent = '...';
                btnRefresh.disabled = true;
                try {
                    const r = await fetch('/api/catbyte/models');
                    const models = await r.json();
                    const listEl = $('catbyteModelList');
                    if (listEl && models.length > 0) {
                        listEl.innerHTML = models.slice(0, 15).map(m =>
                            `<span class="about-tech-tag" style="cursor:pointer;margin-top:4px" data-model="${escapeAttr(m)}">${escapeHtml(m)}</span>`
                        ).join(' ');
                        listEl.querySelectorAll('[data-model]').forEach(tag => {
                            tag.addEventListener('click', () => {
                                const modelInput = document.getElementById('catbyteModel');
                                if (modelInput) modelInput.value = tag.dataset.model;
                            });
                        });
                    } else if (listEl) {
                        listEl.innerHTML = '<span style="font-size:11px;color:var(--text-dim)">No models found \u2014 is the backend running?</span>';
                    }
                } catch {}
                btnRefresh.textContent = '\u21BB';
                btnRefresh.disabled = false;
            });
        }

        // Toggle switches
        const catPunsToggle = $('toggleCatPuns');
        const gameAwareToggle = $('toggleGameAwareness');
        if (catPunsToggle) {
            catPunsToggle.setAttribute('aria-checked', config.cat_puns ? 'true' : 'false');
            catPunsToggle.onclick = async () => {
                const newVal = catPunsToggle.getAttribute('aria-checked') !== 'true';
                catPunsToggle.setAttribute('aria-checked', newVal);
                await fetch('/api/catbyte/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cat_puns: newVal }),
                });
            };
        }
        if (gameAwareToggle) {
            gameAwareToggle.setAttribute('aria-checked', config.game_awareness ? 'true' : 'false');
            gameAwareToggle.onclick = async () => {
                const newVal = gameAwareToggle.getAttribute('aria-checked') !== 'true';
                gameAwareToggle.setAttribute('aria-checked', newVal);
                await fetch('/api/catbyte/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ game_awareness: newVal }),
                });
            };
        }

        // Setup hint
        $('catbyteSetupHint').innerHTML = escapeHtml(preset.setup_hint || '').replace(
            /`([^`]+)`/g, '<code>$1</code>'
        );

        // Check connection status
        const statusResp = await fetch('/api/catbyte/status');
        const status = await statusResp.json();
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
            const r = await fetch('/api/catbyte/test', { method: 'POST' });
            const d = await r.json();
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

    await fetch('/api/rom-dirs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });

    // Scan preview
    try {
        const scanResp = await fetch('/api/scan-rom-dir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        const scanData = await scanResp.json();
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
    } catch {
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

    await fetch('/api/local-dirs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });
    input.value = '';
    $('localDirValidation').textContent = '';
    addBtn.textContent = 'Add';
    addBtn.disabled = false;
    showToast('Local game directory added', 'success');
    renderSettings();
    await fetch('/api/rescan', { method: 'POST' });
    setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
}

async function addBiosDir() {
    const input = $('biosDirInput');
    const path = input.value.trim();
    if (!path) return;

    const addBtn = $('addBiosDir');
    addBtn.textContent = 'Adding...';
    addBtn.disabled = true;

    await fetch('/api/bios/dirs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });
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
    await fetch('/api/rescan', { method: 'POST' });
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

const _gp = {
    connected: false,
    index: null,
    // Repeat timers: held buttons fire repeatedly after initial delay
    navRepeat: null,
    navDelay: 220,          // ms between repeated nav inputs
    navInitialDelay: 400,   // ms before repeat kicks in
    // Track button-down state to detect fresh presses
    prev: {},
    // Axis dead zone
    deadZone: 0.5,
    // Which direction is being held (-1, 0, 1)
    heldDir: 0,
    holdStart: 0,
    holdFired: false,
};

window.addEventListener('gamepadconnected', (e) => {
    _gp.connected = true;
    _gp.index = e.gamepad.index;
    $('gamepadIndicator').classList.remove('hidden');
});

window.addEventListener('gamepaddisconnected', (e) => {
    if (_gp.index === e.gamepad.index) {
        _gp.connected = false;
        _gp.index = null;
        _gp.prev = {};
        _gp.heldDir = 0;
        $('gamepadIndicator').classList.add('hidden');
    }
});

function pollGamepad() {
    if (!_gp.connected) { requestAnimationFrame(pollGamepad); return; }

    const gp = navigator.getGamepads()[_gp.index];
    if (!gp) { requestAnimationFrame(pollGamepad); return; }

    const pressed = (i) => gp.buttons[i] && gp.buttons[i].pressed;
    const justPressed = (i) => {
        const now = pressed(i);
        const was = _gp.prev[i] || false;
        _gp.prev[i] = now;
        return now && !was;
    };

    // Read all button states first (so justPressed is consumed once)
    const btnA      = justPressed(0);   // A / Cross
    const btnB      = justPressed(1);   // B / Circle
    const btnY      = justPressed(3);   // Y / Triangle
    const btnLB     = justPressed(4);   // Left bumper
    const btnRB     = justPressed(5);   // Right bumper
    const btnSelect = justPressed(8);   // Select / Back / Share
    const btnStart  = justPressed(9);   // Start / Menu
    const dpadLeft  = justPressed(14);  // D-pad left
    const dpadRight = justPressed(15);  // D-pad right

    // Left stick axis (axis 0 = horizontal)
    const axisX = gp.axes[0] || 0;

    // ── Determine navigation direction ──
    // Combine D-pad discrete presses and stick axis for left/right
    let navDir = 0;
    if (dpadLeft)  navDir = -1;
    if (dpadRight) navDir = 1;

    // Stick-based navigation with repeat
    const stickDir = Math.abs(axisX) > _gp.deadZone ? Math.sign(axisX) : 0;
    const now = performance.now();

    if (stickDir !== 0) {
        if (_gp.heldDir !== stickDir) {
            // Direction changed — fire immediately
            _gp.heldDir = stickDir;
            _gp.holdStart = now;
            _gp.holdFired = false;
            navDir = stickDir;
        } else if (!_gp.holdFired && now - _gp.holdStart > _gp.navInitialDelay) {
            // Initial delay passed — start repeating
            _gp.holdFired = true;
            _gp.holdStart = now;
            navDir = stickDir;
        } else if (_gp.holdFired && now - _gp.holdStart > _gp.navDelay) {
            // Repeat fire
            _gp.holdStart = now;
            navDir = stickDir;
        }
    } else {
        _gp.heldDir = 0;
    }

    // ── Check which overlay is open ──
    const settingsOpen = !$('settingsOverlay').classList.contains('hidden');
    const searchOpen   = !$('searchOverlay').classList.contains('hidden');
    const catbyteOpen  = !$('catbytePanel').classList.contains('hidden');
    const catbyteInfoOpen = !$('catbyteInfoOverlay').classList.contains('hidden');
    const anyOverlay   = settingsOpen || searchOpen || catbyteOpen || catbyteInfoOpen;

    // ── B: Back / Close ──
    if (btnB) {
        if (catbyteInfoOpen) $('catbyteInfoOverlay').classList.add('hidden');
        else if (searchOpen)   closeSearch();
        else if (settingsOpen) $('settingsOverlay').classList.add('hidden');
        else if (catbyteOpen)  $('catbytePanel').classList.add('hidden');
    }

    // ── Start: Toggle settings ──
    if (btnStart) {
        if (settingsOpen) $('settingsOverlay').classList.add('hidden');
        else if (!anyOverlay) openSettings();
    }

    // ── Select: Toggle search ──
    if (btnSelect) {
        if (searchOpen) closeSearch();
        else if (!anyOverlay) openSearch();
    }

    // ── Bumpers: Tab switching ──
    if (btnLB || btnRB) {
        if (settingsOpen) {
            // Switch settings tabs
            const tabs = Array.from(document.querySelectorAll('.settings-tab'));
            const activeIdx = tabs.findIndex(t => t.classList.contains('active'));
            const next = btnRB
                ? (activeIdx + 1) % tabs.length
                : (activeIdx - 1 + tabs.length) % tabs.length;
            switchSettingsTab(tabs[next].dataset.stab);
        } else if (!anyOverlay) {
            // Switch hex panel tabs via gamepad bumpers
            const hexes = Array.from(document.querySelectorAll('.console-hex-wrap'));
            const activeIdx = hexes.findIndex(h => h.classList.contains('active'));
            const next = btnRB
                ? (activeIdx + 1) % hexes.length
                : (activeIdx - 1 + hexes.length) % hexes.length;
            selectConsoleHex(hexes[next].dataset.tab);
        }
    }

    // ── Navigation (only when no text-input overlay is focused) ──
    if (navDir !== 0 && !searchOpen) {
        navigateCarousel(navDir);
    }

    // ── A: Launch / Confirm ──
    if (btnA && !anyOverlay) {
        launchSelected();
    }

    // ── Y: Favorite toggle ──
    if (btnY && !anyOverlay) {
        const game = state.filteredGames[state.selectedIndex];
        if (game) toggleFavorite(game.id);
    }

    requestAnimationFrame(pollGamepad);
}

// Start the gamepad poll loop
requestAnimationFrame(pollGamepad);

// ── Start ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
