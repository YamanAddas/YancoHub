"""
YancoHub — Build Script
Creates both an installable and portable distribution using PyInstaller.

Usage:
    python build.py              # Build both installer-ready and portable
    python build.py --portable   # Portable zip only
    python build.py --installer  # Installer-ready dir only

Output:
    dist/YancoHub/               # Standalone app directory
    dist/YancoHub-portable.zip   # Portable zip (no install needed)
    dist/YancoHub-setup.exe      # NSIS installer (if makensis is on PATH)
"""

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DIST_DIR = PROJECT_DIR / 'dist'
BUILD_DIR = PROJECT_DIR / 'build'
APP_NAME = 'YancoHub'

# Files/dirs to include alongside the PyInstaller output
BUNDLE_EXTRAS = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('config', 'config'),
    ('bios/README.md', 'bios/README.md'),
    ('LICENSE', 'LICENSE'),
    ('README.md', 'README.md'),
]

# Directories to create in the output (empty, for user data)
EMPTY_DIRS = ['cache', 'logs', 'bios/user']


def check_pyinstaller():
    try:
        import PyInstaller
        return True
    except ImportError:
        print("[BUILD] PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
        return True


def run_pyinstaller():
    """Run PyInstaller to create the frozen app."""
    icon_path = PROJECT_DIR / 'assets' / 'icon.ico'
    icon_arg = f'--icon={icon_path}' if icon_path.exists() else ''

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', APP_NAME,
        '--noconfirm',
        '--clean',
        # Windowed mode (no console window) — Flask runs as subprocess
        '--windowed',
        # Hidden imports that PyInstaller may miss
        '--hidden-import', 'clr',
        '--hidden-import', 'webview',
        '--hidden-import', 'bottle',
        '--hidden-import', 'pythoncom',
        # Collect all of pywebview (it has platform-specific backends)
        '--collect-all', 'webview',
        # One-dir mode (faster startup, easier to update)
        '--distpath', str(DIST_DIR),
        '--workpath', str(BUILD_DIR),
    ]

    if icon_arg:
        cmd.append(icon_arg)

    # Entry point
    cmd.append(str(PROJECT_DIR / 'launch.py'))

    print(f"[BUILD] Running PyInstaller...")
    subprocess.check_call(cmd)


def copy_extras():
    """Copy non-Python files into the dist directory."""
    app_dir = DIST_DIR / APP_NAME
    print(f"[BUILD] Copying extra files to {app_dir}...")

    for src_rel, dst_rel in BUNDLE_EXTRAS:
        src = PROJECT_DIR / src_rel
        dst = app_dir / dst_rel
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        else:
            print(f"  [SKIP] {src_rel} (not found)")

    # Create empty directories for user data
    for d in EMPTY_DIRS:
        (app_dir / d).mkdir(parents=True, exist_ok=True)

    # Create default userdata.json if not present
    default_userdata = app_dir / 'userdata.json'
    if not default_userdata.exists():
        import json
        from userdata import DEFAULT_DATA
        with open(default_userdata, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_DATA, f, indent=2)
        print("  [OK] Created default userdata.json")


def build_portable_zip():
    """Create a portable zip from the dist directory."""
    app_dir = DIST_DIR / APP_NAME
    if not app_dir.exists():
        print("[BUILD] ERROR: dist/YancoHub not found — run PyInstaller first")
        return None

    # Read version from constants
    sys.path.insert(0, str(PROJECT_DIR))
    from constants import VERSION

    zip_name = f'{APP_NAME}-{VERSION}-portable.zip'
    zip_path = DIST_DIR / zip_name

    print(f"[BUILD] Creating portable zip: {zip_name}...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in app_dir.rglob('*'):
            if file.is_file():
                arcname = f'{APP_NAME}/{file.relative_to(app_dir)}'
                zf.write(file, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"[BUILD] Portable zip created: {zip_path} ({size_mb:.1f} MB)")
    return zip_path


def build_nsis_installer():
    """Build NSIS installer if makensis is available."""
    makensis = shutil.which('makensis')
    if not makensis:
        print("[BUILD] NSIS not found on PATH — skipping installer build")
        print("  Install NSIS from https://nsis.sourceforge.io/ to build .exe installer")
        return None

    nsis_script = PROJECT_DIR / 'installer.nsi'
    if not nsis_script.exists():
        print("[BUILD] installer.nsi not found — skipping installer build")
        return None

    print("[BUILD] Building NSIS installer...")
    subprocess.check_call([makensis, str(nsis_script)])

    sys.path.insert(0, str(PROJECT_DIR))
    from constants import VERSION
    installer_path = DIST_DIR / f'{APP_NAME}-{VERSION}-setup.exe'
    if installer_path.exists():
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        print(f"[BUILD] Installer created: {installer_path} ({size_mb:.1f} MB)")
        return installer_path

    print("[BUILD] Installer may have been created with a different name in dist/")
    return None


def main():
    parser = argparse.ArgumentParser(description=f'Build {APP_NAME} for distribution')
    parser.add_argument('--portable', action='store_true', help='Build portable zip only')
    parser.add_argument('--installer', action='store_true', help='Build installer only')
    args = parser.parse_args()

    build_all = not args.portable and not args.installer

    check_pyinstaller()

    # Always run PyInstaller first
    run_pyinstaller()
    copy_extras()

    if build_all or args.portable:
        build_portable_zip()

    if build_all or args.installer:
        build_nsis_installer()

    print("\n[BUILD] Done!")
    print(f"  App directory: dist/{APP_NAME}/")
    print(f"  Run directly:  dist/{APP_NAME}/{APP_NAME}.exe")


if __name__ == '__main__':
    main()
