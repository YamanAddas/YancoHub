"""
YancoHub — Main Entry Point
Starts Flask backend, waits for health check, then opens the window.
"""

import os
import sys
import time
import subprocess
import signal
import requests
import threading

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
FLASK_PORT = 8745
OPENCLAW_PORT = 18789

processes = []


def start_flask():
    """Start the Flask backend."""
    proc = subprocess.Popen(
        [sys.executable, os.path.join(PROJECT_DIR, 'app.py')],
        cwd=PROJECT_DIR,
    )
    processes.append(proc)
    return proc


def start_openclaw():
    """Start OpenClaw gateway (optional, non-critical)."""
    try:
        openclaw_path = os.path.expanduser('~/.openclaw')
        if not os.path.exists(openclaw_path):
            print("[YancoHub] OpenClaw not found — CatByte will be offline")
            return None

        # Try to find openclaw executable
        import shutil
        openclaw_exe = shutil.which('openclaw')
        if not openclaw_exe:
            # Try common locations
            for p in [
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'openclaw', 'openclaw.exe'),
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'OpenClaw', 'openclaw.exe'),
            ]:
                if os.path.exists(p):
                    openclaw_exe = p
                    break

        if not openclaw_exe:
            print("[YancoHub] OpenClaw executable not found — CatByte will be offline")
            return None

        proc = subprocess.Popen(
            [openclaw_exe, 'serve', '--port', str(OPENCLAW_PORT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append(proc)
        print(f"[YancoHub] OpenClaw started on port {OPENCLAW_PORT}")
        return proc
    except Exception as e:
        print(f"[YancoHub] OpenClaw failed to start: {e}")
        return None


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

    # Start OpenClaw (non-blocking, non-critical)
    threading.Thread(target=start_openclaw, daemon=True).start()

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
