/**
 * YancoHub — Built-in Emulator Engine
 * Wraps EmulatorJS with cinematic transitions, per-system boot sequences,
 * a YancoVerse-themed pause menu, and CatByte integration.
 */

// ── System → EmulatorJS core mapping ───────────────────────────────────────

const BUILTIN_SYSTEMS = {
    // Tier 1 — fully self-contained, no user BIOS needed
    nes:          { core: 'nes',       name: 'NES',              tier: 1, color: '#c62828', icon: '🎮' },
    snes:         { core: 'snes',      name: 'Super Nintendo',   tier: 1, color: '#6a1b9a', icon: '🎮' },
    gb:           { core: 'gb',        name: 'Game Boy',         tier: 1, color: '#2e7d32', icon: '🟢' },
    gbc:          { core: 'gbc',       name: 'Game Boy Color',   tier: 1, color: '#1565c0', icon: '🔵' },
    gba:          { core: 'gba',       name: 'Game Boy Advance', tier: 1, color: '#4527a0', icon: '🟣', bios: '/api/bios/gba' },
    megadrive:    { core: 'segaMD',    name: 'Sega Genesis',     tier: 1, color: '#1565c0', icon: '🔷' },
    mastersystem: { core: 'segaMS',    name: 'Master System',    tier: 1, color: '#1565c0', icon: '🔷' },
    gamegear:     { core: 'segaGG',    name: 'Game Gear',        tier: 1, color: '#1565c0', icon: '🔷' },
    atari2600:    { core: 'atari2600', name: 'Atari 2600',       tier: 1, color: '#bf360c', icon: '🕹️' },
    ngp:          { core: 'ngp',       name: 'Neo Geo Pocket',   tier: 1, color: '#00838f', icon: '🎮' },
    psx:          { core: 'psx',       name: 'PlayStation',       tier: 1, color: '#37474f', icon: '🎮', bios: '/api/bios/psx' },

    // Tier 2 — built-in but user provides BIOS
    neogeo:       { core: 'arcade',    name: 'Neo Geo',          tier: 2, color: '#b71c1c', icon: '🕹️', biosRequired: true },
    fbneo:        { core: 'arcade',    name: 'Arcade',           tier: 2, color: '#b71c1c', icon: '🕹️' },
    cps1:         { core: 'arcade',    name: 'CPS-1',            tier: 2, color: '#880e4f', icon: '🕹️' },
    cps2:         { core: 'arcade',    name: 'CPS-2',            tier: 2, color: '#880e4f', icon: '🕹️' },
    cps3:         { core: 'arcade',    name: 'CPS-3',            tier: 2, color: '#880e4f', icon: '🕹️' },
    nds:          { core: 'nds',       name: 'Nintendo DS',      tier: 2, color: '#78909c', icon: '📱', biosRequired: true },
    mame:         { core: 'mame2003',  name: 'MAME',             tier: 2, color: '#4e342e', icon: '🕹️' },

    // Tier 3 — built-in, beta quality
    n64:          { core: 'n64',       name: 'Nintendo 64',      tier: 3, color: '#1b5e20', icon: '🎮' },
};

// Systems that need external emulators (not built-in)
const EXTERNAL_SYSTEMS = new Set(['ps2', 'ps3', 'psp', 'gamecube', 'wii', 'dreamcast', 'saturn']);

const EJS_CDN = 'https://cdn.emulatorjs.org/stable/data/';

// ── Emulator State ─────────────────────────────────────────────────────────

let emuActive = false;
let emuGameId = null;
let emuPaused = false;
let emuInstance = null;

// ── Public API ─────────────────────────────────────────────────────────────

function isBuiltinSystem(system) {
    return system in BUILTIN_SYSTEMS;
}

function getSystemInfo(system) {
    return BUILTIN_SYSTEMS[system] || null;
}

async function launchBuiltinEmulator(game) {
    if (emuActive) return;

    const sys = BUILTIN_SYSTEMS[game.system];
    if (!sys) return;

    emuActive = true;
    emuGameId = game.id;
    emuPaused = false;

    // Notify backend
    fetch(`/api/launch/${game.id}`, { method: 'POST' });

    // Show boot sequence
    await showBootSequence(game, sys);

    // Load emulator
    await loadEmulatorJS(game, sys);
}

function exitEmulator() {
    if (!emuActive) return;

    // Clean up EmulatorJS
    const container = document.getElementById('emuContainer');
    const gameDiv = document.getElementById('emuGame');

    // Remove all EJS scripts and styles
    document.querySelectorAll('script[src*="emulatorjs"], script[src*="loader"]').forEach(s => s.remove());

    // Clear the game div
    gameDiv.innerHTML = '';

    // Reset EJS globals
    if (window.EJS_emulator) {
        try { window.EJS_emulator.callEvent('exit'); } catch {}
    }
    window.EJS_player = undefined;
    window.EJS_core = undefined;
    window.EJS_gameUrl = undefined;
    window.EJS_emulator = undefined;

    // Hide container with transition
    container.classList.add('emu-exit');
    setTimeout(() => {
        container.classList.add('hidden');
        container.classList.remove('emu-exit');
        document.getElementById('emuPauseMenu').classList.add('hidden');
        document.getElementById('emuBootScreen').classList.add('hidden');
    }, 500);

    // Notify backend
    if (emuGameId) {
        // Session end will be handled by the active game monitor
    }

    emuActive = false;
    emuGameId = null;
    emuInstance = null;
}

// ── Boot Sequence ──────────────────────────────────────────────────────────

async function showBootSequence(game, sys) {
    const container = document.getElementById('emuContainer');
    const boot = document.getElementById('emuBootScreen');
    const bootSystem = document.getElementById('emuBootSystem');
    const bootTitle = document.getElementById('emuBootTitle');
    const bootIcon = document.getElementById('emuBootIcon');
    const bootProgress = document.getElementById('emuBootProgress');
    const bootRing = document.getElementById('emuBootRing');

    // Set system-specific colors
    container.style.setProperty('--emu-accent', sys.color);
    bootRing.style.borderTopColor = sys.color;
    bootProgress.style.background = `linear-gradient(90deg, ${sys.color}, ${sys.color}88)`;

    bootIcon.textContent = sys.icon;
    bootSystem.textContent = sys.name;
    bootTitle.textContent = game.name;

    // Show
    container.classList.remove('hidden');
    boot.classList.remove('hidden');

    // Animate boot sequence
    bootProgress.style.width = '0%';
    await sleep(100);

    // Phase 1: System name appears
    boot.classList.add('boot-phase-1');
    bootProgress.style.width = '30%';
    await sleep(600);

    // Phase 2: Game title appears
    boot.classList.add('boot-phase-2');
    bootProgress.style.width = '60%';
    await sleep(600);

    // Phase 3: Loading ring
    boot.classList.add('boot-phase-3');
    bootProgress.style.width = '90%';
    await sleep(400);

    // Phase 4: Complete
    bootProgress.style.width = '100%';
    await sleep(300);

    // Fade out boot screen
    boot.classList.add('boot-done');
    await sleep(500);
    boot.classList.remove('boot-phase-1', 'boot-phase-2', 'boot-phase-3', 'boot-done');
    boot.classList.add('hidden');
}

// ── EmulatorJS Loader ──────────────────────────────────────────────────────

async function loadEmulatorJS(game, sys) {
    const gameDiv = document.getElementById('emuGame');
    gameDiv.innerHTML = '';

    // Configure EmulatorJS globals
    window.EJS_player = '#emuGame';
    window.EJS_core = sys.core;
    window.EJS_gameUrl = `/api/rom/${game.id}`;
    window.EJS_pathtodata = EJS_CDN;
    window.EJS_color = '#00e5c1';
    window.EJS_backgroundColor = '#060b14';
    window.EJS_darkMode = true;
    window.EJS_startOnLoaded = true;
    window.EJS_fullscreenOnLoaded = false;
    window.EJS_oldCores = false;
    window.EJS_softLoad = false;

    // BIOS
    if (sys.bios && !sys.biosRequired) {
        window.EJS_biosUrl = sys.bios;
    }

    // Disable default EJS UI elements we're replacing
    window.EJS_Buttons = {
        playPause: false,
        restart: false,
        mute: false,
        settings: false,
        fullscreen: false,
        saveState: false,
        loadState: false,
        screenRecord: false,
        gamepad: false,
        cheat: false,
        volume: false,
        saveSavFiles: false,
        loadSavFiles: false,
        quickSave: false,
        quickLoad: false,
        screenshot: false,
        cacheManager: false,
    };

    // Callbacks
    window.EJS_onGameStart = () => {
        document.getElementById('emuGame').classList.add('emu-game-active');
    };

    // Load EmulatorJS
    const script = document.createElement('script');
    script.src = EJS_CDN + 'loader.js';
    script.async = true;
    document.body.appendChild(script);

    // Show game container
    document.getElementById('emuGameWrapper').classList.remove('hidden');
}

// ── Pause Menu ─────────────────────────────────────────────────────────────

function togglePauseMenu() {
    if (!emuActive) return;

    const menu = document.getElementById('emuPauseMenu');
    emuPaused = !emuPaused;
    menu.classList.toggle('hidden', !emuPaused);

    // Pause/resume the emulator
    if (window.EJS_emulator) {
        try {
            if (emuPaused) window.EJS_emulator.pause();
            else window.EJS_emulator.play();
        } catch {}
    }
}

async function emuSaveState() {
    if (!window.EJS_emulator) return;
    try {
        window.EJS_emulator.quickSave();
        showEmuToast('State saved');
    } catch (e) {
        showEmuToast('Save failed');
    }
}

async function emuLoadState() {
    if (!window.EJS_emulator) return;
    try {
        window.EJS_emulator.quickLoad();
        showEmuToast('State loaded');
        togglePauseMenu();
    } catch (e) {
        showEmuToast('Load failed');
    }
}

function emuRestart() {
    if (!window.EJS_emulator) return;
    try {
        window.EJS_emulator.restart();
        togglePauseMenu();
        showEmuToast('Restarted');
    } catch {}
}

function emuScreenshot() {
    if (!window.EJS_emulator) return;
    try {
        window.EJS_emulator.screenshot();
        showEmuToast('Screenshot saved');
    } catch {}
}

function showEmuToast(msg) {
    const toast = document.getElementById('emuToast');
    toast.textContent = msg;
    toast.classList.remove('hidden');
    toast.classList.add('emu-toast-show');
    setTimeout(() => {
        toast.classList.remove('emu-toast-show');
        setTimeout(() => toast.classList.add('hidden'), 300);
    }, 1500);
}

// ── Keyboard Handler ───────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
    if (!emuActive) return;

    if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        if (emuPaused) {
            // If pause menu is open, check if they want to exit
            togglePauseMenu();
        } else {
            togglePauseMenu();
        }
    }

    if (e.key === 'F5' && emuActive) {
        e.preventDefault();
        emuSaveState();
    }
    if (e.key === 'F8' && emuActive) {
        e.preventDefault();
        emuLoadState();
    }
}, true);

// ── Utility ────────────────────────────────────────────────────────────────

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}
