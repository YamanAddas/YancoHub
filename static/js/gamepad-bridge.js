/**
 * YancoHub — Gamepad Bridge Polyfill
 *
 * WebView2 does NOT support the W3C Gamepad API (navigator.getGamepads()
 * returns null and connection events never fire).  This script receives
 * gamepad state pushed from Python via pywebview's evaluate_js() and
 * exposes it through the standard Gamepad API surface so that both the
 * YancoHub UI code (app.js) and EmulatorJS work transparently.
 *
 * Data flow:
 *   DualSense / Xbox → Windows API (ctypes) → Python thread
 *     → evaluate_js('_gpBridgeUpdate(…)') → this polyfill
 *     → navigator.getGamepads() / gamepadconnected event
 *     → app.js + EmulatorJS
 */

// ── Internal state ────────────────────────────────────────────────────────

let _bridgePad = null;   // synthetic Gamepad object, or null


// ── Functions called from Python (gamepad.py) ─────────────────────────────

/** Called when a controller is first detected (idempotent — safe to call
 *  repeatedly from the Python heartbeat without duplicating events). */
function _gpBridgeConnect(state) {
    if (_bridgePad && _bridgePad.connected) {
        // Already connected — treat as a state update
        _gpBridgeUpdate(state);
        return;
    }
    _bridgePad = _makePad(state);
    _fireEvent('gamepadconnected', _bridgePad);
}

/** Called every frame when the controller state changes. */
function _gpBridgeUpdate(state) {
    if (!_bridgePad) {
        // Missed the connect — create now
        _gpBridgeConnect(state);
        return;
    }
    _bridgePad.timestamp = performance.now();
    const b = state.buttons;
    for (let i = 0; i < b.length; i++) {
        _bridgePad.buttons[i].pressed = b[i].pressed;
        _bridgePad.buttons[i].value   = b[i].value;
    }
    for (let i = 0; i < state.axes.length; i++) {
        _bridgePad.axes[i] = state.axes[i];
    }
}

/** Called when the controller is disconnected. */
function _gpBridgeDisconnect() {
    if (!_bridgePad) return;
    const old = _bridgePad;
    old.connected = false;
    _bridgePad = null;
    _fireEvent('gamepaddisconnected', old);
}


// ── Polyfill navigator.getGamepads() ──────────────────────────────────────

const _origGetGamepads = (navigator.getGamepads)
    ? navigator.getGamepads.bind(navigator)
    : () => [null, null, null, null];

Object.defineProperty(navigator, 'getGamepads', {
    value: function () {
        const result = [null, null, null, null];
        // Preserve any native gamepads (future-proofing)
        try {
            const orig = _origGetGamepads();
            for (let i = 0; i < orig.length && i < 4; i++) {
                if (orig[i]) result[i] = orig[i];
            }
        } catch (_) { /* WebView2 may throw */ }
        // Inject bridge gamepad
        if (_bridgePad) {
            result[_bridgePad.index] = _bridgePad;
        }
        return result;
    },
    writable: true,
    configurable: true,
});


// ── Helpers ───────────────────────────────────────────────────────────────

function _makePad(state) {
    return {
        id:        state.id,
        index:     state.index,
        mapping:   state.mapping,
        connected: true,
        timestamp: performance.now(),
        buttons:   state.buttons.map(b => ({
            pressed: b.pressed,
            value:   b.value,
            touched: false,
        })),
        axes: state.axes.slice(),
    };
}

function _fireEvent(type, gamepad) {
    let ev;
    try {
        ev = new GamepadEvent(type, { gamepad });
    } catch (_) {
        // GamepadEvent constructor may not exist in WebView2
        ev = new Event(type);
        ev.gamepad = gamepad;
    }
    window.dispatchEvent(ev);
}

// Signal readiness to Python
window._gpBridgeReady = true;
