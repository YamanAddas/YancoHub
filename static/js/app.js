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
};

// ── DOM ────────────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id) || document.querySelector(id);
const $$ = (sel) => document.querySelectorAll(sel);

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
    applyFilter();

    if (state.scanning) {
        updateSplash(95, 'Scanning your libraries...');
        // Poll until scan completes, then refresh
        const pollScan = setInterval(async () => {
            await loadGames();
            if (!state.scanning) {
                clearInterval(pollScan);
                applyFilter();
            }
        }, 2000);
    }

    updateSplash(100, 'Ready!');

    setTimeout(() => {
        $('splash').classList.add('fade-out');
        $('app').classList.remove('hidden');
        setTimeout(() => $('splash').style.display = 'none', 800);
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

async function loadPlaytimes() {
    try {
        const r = await fetch('/api/playtime');
        state.playtimes = await r.json();
    } catch {}
}

async function checkCatbyteStatus() {
    try {
        const r = await fetch('/api/catbyte/status');
        const d = await r.json();
        state.catbyteOnline = d.status === 'online';
    } catch {
        state.catbyteOnline = false;
    }
    const on = state.catbyteOnline;
    $('catbyteStatusDot').classList.toggle('online', on);
    $('catbyteStatus').textContent = on ? 'Online' : 'Offline';
    $('catbyteStatus').classList.toggle('online', on);
    $('btnCatbyte').classList.toggle('dimmed', !on);
    $('btnCatbyte').title = on ? 'CatByte AI (Ctrl+B)' : 'CatByte requires OpenClaw';
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
            games = games.filter(g => g.source === tab);
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

    if (game.artwork && (game.artwork.cover || game.artwork.header)) {
        const artType = game.artwork.cover ? 'cover' : 'header';
        const art = document.createElement('div');
        art.className = 'carousel-card-art shimmer';

        const img = new Image();
        img.src = `/api/artwork/${game.id}/${artType}`;
        img.onload = () => {
            art.style.backgroundImage = `url('${img.src}')`;
            art.classList.remove('shimmer');
        };
        img.onerror = () => {
            art.classList.remove('shimmer');
            applyFallbackGradient(art, game);
        };
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
    const tabEl = document.querySelector('.tab.active');
    const tabName = tabEl ? tabEl.textContent : state.currentTab;
    $('gameCount').textContent = `${tabName} — ${count} game${count !== 1 ? 's' : ''}`;
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
    // Tabs
    $('tabBar').addEventListener('click', (e) => {
        const tab = e.target.closest('.tab');
        if (!tab) return;
        $$('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.currentTab = tab.dataset.tab;
        applyFilter();
    });

    // Search
    $('btnSearch').addEventListener('click', openSearch);
    $('closeSearch').addEventListener('click', closeSearch);
    $('searchInput').addEventListener('input', debounce(doSearch, 200));

    // CatByte
    $('btnCatbyte').addEventListener('click', toggleCatbyte);
    $('closeCatbyte').addEventListener('click', () => $('catbytePanel').classList.add('hidden'));
    $('catbyteSend').addEventListener('click', sendCatbyteMessage);
    $('catbyteInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendCatbyteMessage(); });
    $('dismissCatbyteInfo').addEventListener('click', () => $('catbyteInfoOverlay').classList.add('hidden'));

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

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        // Don't navigate if an input is focused
        if (e.target.tagName === 'INPUT') return;

        if (e.key === 'ArrowLeft')  { e.preventDefault(); navigateCarousel(-1); }
        if (e.key === 'ArrowRight') { e.preventDefault(); navigateCarousel(1); }
        if (e.key === 'Enter')      { e.preventDefault(); launchSelected(); }

        if (e.ctrlKey && e.key === 'f') { e.preventDefault(); openSearch(); }
        if (e.ctrlKey && e.key === 'b') { e.preventDefault(); toggleCatbyte(); }
        if (e.ctrlKey && e.key === ',') { e.preventDefault(); openSettings(); }

        if (e.key === 'Escape') {
            if (!$('catbyteInfoOverlay').classList.contains('hidden')) $('catbyteInfoOverlay').classList.add('hidden');
            else if (!$('searchOverlay').classList.contains('hidden')) closeSearch();
            else if (!$('settingsOverlay').classList.contains('hidden')) $('settingsOverlay').classList.add('hidden');
            else if (!$('catbytePanel').classList.contains('hidden')) $('catbytePanel').classList.add('hidden');
        }

        // F for favorite toggle
        if (e.key === 'f' && !e.ctrlKey) {
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

    // Close overlays on backdrop click
    $('searchOverlay').addEventListener('click', (e) => { if (e.target === $('searchOverlay')) closeSearch(); });
    $('settingsOverlay').addEventListener('click', (e) => { if (e.target === $('settingsOverlay')) $('settingsOverlay').classList.add('hidden'); });
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
            <div class="search-result" data-id="${g.id}">
                <span class="search-result-name">${escapeHtml(g.name)}</span>
                <span class="search-result-source">${g.system_name || g.source}</span>
            </div>
        `).join('');

        $('searchResults').querySelectorAll('.search-result').forEach(el => {
            el.addEventListener('click', () => {
                closeSearch();
                // Switch to all tab and find game
                state.currentTab = 'all';
                $$('.tab').forEach(t => t.classList.remove('active'));
                $$('.tab')[0].classList.add('active');
                applyFilter();
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
    if (!state.catbyteOnline) {
        $('catbyteInfoOverlay').classList.remove('hidden');
        return;
    }
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
        appendChat('bot', 'Connection error... is OpenClaw running?');
    }
}

function appendChat(role, text) {
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.innerHTML = `<div class="chat-bubble">${escapeHtml(text)}</div>`;
    $('catbyteMessages').appendChild(div);
    $('catbyteMessages').scrollTop = $('catbyteMessages').scrollHeight;
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
    // ── Accounts ──
    try {
        const r = await fetch('/api/accounts');
        const accounts = await r.json();

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
                            : 'Available — click to enable'}</div>
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

        // Epic
        const epic = accounts.epic || {};
        if (epic.authenticated) {
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🏔️</div>
                    <div class="account-info">
                        <div class="account-name">Epic Games</div>
                        <div class="account-detail">Connected via legendary</div>
                    </div>
                    <div class="account-status connected"></div>
                </div>`;
        } else if (epic.legendary_installed) {
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🏔️</div>
                    <div class="account-info">
                        <div class="account-name">Epic Games</div>
                        <div class="account-detail">Not logged in</div>
                    </div>
                    <div class="account-status disconnected"></div>
                    <button class="account-btn" id="btnEpicAuth">Login</button>
                </div>`;
        } else {
            accountsHtml += `
                <div class="account-card">
                    <div class="account-icon">🏔️</div>
                    <div class="account-info">
                        <div class="account-name">Epic Games</div>
                        <div class="account-detail">Install legendary: pip install legendary-gl</div>
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
                btnEpicAuth.textContent = 'Opening browser...';
                btnEpicAuth.disabled = true;
                const r = await fetch('/api/accounts/epic/auth', { method: 'POST' });
                const d = await r.json();
                if (d.status === 'ok') {
                    renderSettings();
                    setTimeout(async () => { await loadGames(); applyFilter(); }, 5000);
                } else {
                    btnEpicAuth.textContent = d.message || 'Failed';
                    setTimeout(() => { btnEpicAuth.textContent = 'Login'; btnEpicAuth.disabled = false; }, 3000);
                }
            });
        }

        // Hide steam connect form if already connected
        if (steam.connected) {
            $('steamConnectSection').classList.add('hidden');
        }
    } catch {}

    // ── Show/Hide Uninstalled toggle ──
    try {
        const r = await fetch('/api/stores');  // reuse to check settings
        const settings = await (await fetch('/api/games')).json();  // check current state
        // Just read the setting from a game's installed state
    } catch {}
    // We'll fetch settings state via a dedicated check
    $('btnToggleUninstalled').textContent = 'Toggle Show Uninstalled Games';

    // ── Detected Stores ──
    const storeNames = {
        steam: 'Steam', epic: 'Epic Games', gog: 'GOG Galaxy', xbox: 'Xbox/Game Pass',
        ea: 'EA Desktop', ubisoft: 'Ubisoft Connect', battlenet: 'Battle.net', retroarch: 'RetroArch'
    };
    $('settingsStores').innerHTML = Object.entries(state.stores)
        .map(([k, v]) => `<div class="store-badge"><span class="store-status ${v ? 'detected' : 'missing'}"></span>${storeNames[k] || k}</div>`)
        .join('');

    // ROM dirs
    try {
        const r = await fetch('/api/rom-dirs');
        const dirs = await r.json();
        $('settingsRomDirs').innerHTML = dirs.map(d => `
            <div class="dir-entry"><span>${escapeHtml(d)}</span><button class="dir-remove" data-dir="${escapeAttr(d)}" data-type="rom">&times;</button></div>
        `).join('') || '<div style="color:var(--text-dim);font-size:12px;padding:4px 0">No ROM directories configured</div>';
    } catch {}

    // Local dirs
    try {
        const r = await fetch('/api/local-dirs');
        const dirs = await r.json();
        $('settingsLocalDirs').innerHTML = dirs.map(d => `
            <div class="dir-entry"><span>${escapeHtml(d)}</span><button class="dir-remove" data-dir="${escapeAttr(d)}" data-type="local">&times;</button></div>
        `).join('') || '<div style="color:var(--text-dim);font-size:12px;padding:4px 0">No local game directories configured</div>';
    } catch {}

    // BIOS dirs + status
    try {
        const bd = await fetch('/api/bios/dirs');
        const biosDirs = await bd.json();
        $('settingsBiosDirs').innerHTML = biosDirs.map(d => `
            <div class="dir-entry"><span>${escapeHtml(d)}</span><button class="dir-remove" data-dir="${escapeAttr(d)}" data-type="bios">&times;</button></div>
        `).join('') || '<div style="color:var(--text-dim);font-size:12px;padding:4px 0">No BIOS directories configured</div>';

        const bs = await fetch('/api/bios/status');
        const biosStatus = await bs.json();
        let biosHtml = '<div style="display:flex;flex-wrap:wrap;gap:6px">';
        for (const [sysId, info] of Object.entries(biosStatus)) {
            const color = info.ready ? 'var(--success)' : 'var(--text-dim)';
            const icon = info.ready ? '●' : '○';
            biosHtml += `<span style="font-size:11px;color:${color}" title="${info.files.map(f => f.name + (f.found ? ' ✓' : ' ✗')).join(', ')}">${icon} ${info.system_name}</span>`;
        }
        biosHtml += '</div>';
        $('settingsBiosStatus').innerHTML = biosHtml;
    } catch {}

    // Systems
    const systems = {
        snes: 'SNES', nes: 'NES', gba: 'GBA', gb: 'GB', gbc: 'GBC',
        n64: 'N64', nds: 'NDS', megadrive: 'Genesis', mastersystem: 'Master System',
        gamegear: 'Game Gear', atari2600: 'Atari 2600', psx: 'PS1', ps2: 'PS2',
        ps3: 'PS3', psp: 'PSP', dreamcast: 'Dreamcast', saturn: 'Saturn',
        gamecube: 'GameCube', wii: 'Wii', neogeo: 'Neo Geo', fbneo: 'FBNeo',
        cps1: 'CPS-1', cps2: 'CPS-2', cps3: 'CPS-3', mame: 'MAME', ngp: 'NGP'
    };
    $('settingsVisibleSystems').innerHTML = Object.entries(systems)
        .map(([id, name]) => {
            const hidden = state.hiddenSystems.has(id);
            return `<button class="system-toggle ${hidden ? 'hidden-sys' : 'active'}" data-system="${id}">${name}</button>`;
        }).join('');

    // Bind remove buttons
    $$('.dir-remove').forEach(btn => {
        btn.addEventListener('click', async () => {
            const typeMap = { rom: '/api/rom-dirs', local: '/api/local-dirs', bios: '/api/bios/dirs' };
            const endpoint = typeMap[btn.dataset.type] || '/api/local-dirs';
            await fetch(endpoint, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: btn.dataset.dir }),
            });
            renderSettings();
        });
    });

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
}

async function addRomDir() {
    const input = $('romDirInput');
    const path = input.value.trim();
    if (!path) return;
    await fetch('/api/rom-dirs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });
    input.value = '';
    renderSettings();
    setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
}

async function addLocalDir() {
    const input = $('localDirInput');
    const path = input.value.trim();
    if (!path) return;
    await fetch('/api/local-dirs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });
    input.value = '';
    renderSettings();
    await fetch('/api/rescan', { method: 'POST' });
    setTimeout(async () => { await loadGames(); applyFilter(); }, 3000);
}

async function addBiosDir() {
    const input = $('biosDirInput');
    const path = input.value.trim();
    if (!path) return;
    await fetch('/api/bios/dirs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });
    input.value = '';
    renderSettings();
}

async function rescanLibrary() {
    const btn = $('btnRescan');
    btn.textContent = 'Scanning...';
    btn.disabled = true;
    await fetch('/api/rescan', { method: 'POST' });
    setTimeout(async () => {
        await loadGames();
        await loadStores();
        applyFilter();
        btn.textContent = 'Rescan All Libraries';
        btn.disabled = false;
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

function formatSize(bytes) {
    if (!bytes) return '';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + u[i];
}

// ── Start ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
