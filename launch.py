"""
YancoHub — Main Entry Point
Starts Flask backend, waits for health check, then opens the window.
"""

import sys
import time
import logging
import subprocess
import threading
import requests
from pathlib import Path

from constants import FLASK_PORT, HTTP_TIMEOUT_PROBE, FLASK_STARTUP_TIMEOUT, PROCESS_CLEANUP_TIMEOUT

logger = logging.getLogger('yancohub.launch')

PROJECT_DIR = Path(__file__).parent

processes = []


def start_flask():
    """Start the Flask backend."""
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_DIR / 'app.py')],
        cwd=str(PROJECT_DIR),
    )
    processes.append(proc)
    return proc


def wait_for_flask(timeout=FLASK_STARTUP_TIMEOUT):
    """Wait for Flask to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f'http://127.0.0.1:{FLASK_PORT}/health', timeout=HTTP_TIMEOUT_PROBE)
            if resp.status_code == 200:
                return True
        except Exception as e:
            logger.debug(f"Waiting for Flask: {e}")
        time.sleep(0.5)
    return False


def cleanup():
    """Kill all child processes."""
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=PROCESS_CLEANUP_TIMEOUT)
        except Exception as e:
            logger.debug(f"Process terminate failed, killing: {e}")
            try:
                proc.kill()
            except Exception as e2:
                logger.debug(f"Process kill also failed: {e2}")


# ── Health Watchdog ──────────────────────────────────────────────────────────

_watchdog_stop = threading.Event()
_WATCHDOG_INTERVAL = 5       # seconds between health pings
_WATCHDOG_MAX_FAILURES = 3   # consecutive failures before restart
_WATCHDOG_MAX_RESTARTS = 5   # total restarts before giving up

_js_notify_lock = threading.Lock()


def _notify_frontend(js_code: str) -> None:
    """Try to send JS to the pywebview window (best-effort)."""
    try:
        import webview
        w = webview.active_window()
        if w:
            w.evaluate_js(js_code)
    except Exception:
        pass


def _health_watchdog():
    """Background thread that monitors Flask health and restarts if needed."""
    failures = 0
    restarts = 0
    was_down = False

    while not _watchdog_stop.is_set():
        _watchdog_stop.wait(_WATCHDOG_INTERVAL)
        if _watchdog_stop.is_set():
            break

        try:
            resp = requests.get(
                f'http://127.0.0.1:{FLASK_PORT}/health',
                timeout=HTTP_TIMEOUT_PROBE,
            )
            if resp.status_code == 200:
                if was_down:
                    logger.info("Flask recovered — connection restored")
                    _notify_frontend("if(typeof hideConnectionError==='function') hideConnectionError()")
                    was_down = False
                failures = 0
                continue
        except Exception:
            pass

        failures += 1
        logger.warning("Health check failed (%d/%d)", failures, _WATCHDOG_MAX_FAILURES)

        if failures >= _WATCHDOG_MAX_FAILURES:
            if restarts >= _WATCHDOG_MAX_RESTARTS:
                logger.error("Flask unrecoverable after %d restarts — giving up", restarts)
                _notify_frontend(
                    "if(typeof showFatalError==='function') "
                    "showFatalError('Backend crashed and could not recover. Please restart YancoHub.')"
                )
                break

            # Notify frontend
            was_down = True
            _notify_frontend("if(typeof showConnectionError==='function') showConnectionError()")

            # Restart Flask
            logger.info("Restarting Flask (attempt %d/%d)...", restarts + 1, _WATCHDOG_MAX_RESTARTS)
            flask_proc = start_flask()
            restarts += 1
            failures = 0

            # Wait for Flask to come back
            if wait_for_flask(timeout=FLASK_STARTUP_TIMEOUT):
                logger.info("Flask restarted successfully")
            else:
                logger.error("Flask failed to restart")


def start_watchdog() -> threading.Thread:
    """Start the health watchdog daemon thread."""
    t = threading.Thread(target=_health_watchdog, name='health-watchdog', daemon=True)
    t.start()
    return t


def stop_watchdog() -> None:
    """Signal the watchdog to stop."""
    _watchdog_stop.set()


def main():
    # DPI awareness must be set before any window creation
    from dpi import enable_dpi_awareness
    enable_dpi_awareness()

    # Parse protocol URL from argv (e.g. yancohub://launch/steam_12345)
    protocol_url = None
    for arg in sys.argv[1:]:
        if arg.startswith('yancohub://'):
            protocol_url = arg
            break

    # Single instance enforcement
    from singleinstance import acquire_instance_lock, show_already_running_message
    if not acquire_instance_lock():
        # If launched with a protocol URL, forward it to the running instance
        if protocol_url:
            try:
                requests.post(
                    f'http://127.0.0.1:{FLASK_PORT}/api/protocol-action',
                    json={'url': protocol_url},
                    timeout=HTTP_TIMEOUT_PROBE,
                )
            except Exception:
                pass
        else:
            show_already_running_message()
        sys.exit(0)

    # Migrate legacy data from app dir to %APPDATA% (one-time, skips in portable mode)
    from paths import migrate_legacy_data
    migrate_legacy_data()

    print("[YancoHub] Starting...")

    # Start Flask
    flask_proc = start_flask()
    print(f"[YancoHub] Flask starting on port {FLASK_PORT}...")

    # Wait for Flask
    if not wait_for_flask():
        print("[YancoHub] ERROR: Flask failed to start!")
        cleanup()
        sys.exit(1)

    print("[YancoHub] Flask ready!")

    # Start health watchdog
    start_watchdog()

    # Open window (blocks until closed)
    try:
        from window import main as window_main
        window_main()
    except Exception as e:
        print(f"[YancoHub] Window error: {e}")
        # Fallback: open in browser
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{FLASK_PORT}')
        print("[YancoHub] Opened in browser. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    # Cleanup
    print("[YancoHub] Shutting down...")
    stop_watchdog()
    cleanup()
    print("[YancoHub] Goodbye!")


if __name__ == '__main__':
    main()
