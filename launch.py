"""
YancoHub — Main Entry Point
Starts Flask backend, waits for health check, then opens the window.
"""

import sys
import time
import subprocess
import requests
from pathlib import Path

from constants import FLASK_PORT

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


def wait_for_flask(timeout=15):
    """Wait for Flask to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f'http://127.0.0.1:{FLASK_PORT}/health', timeout=2)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def cleanup():
    """Kill all child processes."""
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def main():
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
    cleanup()
    print("[YancoHub] Goodbye!")


if __name__ == '__main__':
    main()
