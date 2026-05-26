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
import re
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
    ('assets', 'assets'),
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

    # DPI manifest for crisp rendering on high-DPI displays
    manifest_path = PROJECT_DIR / 'assets' / 'YancoHub.manifest'
    if manifest_path.exists():
        cmd.extend(['--manifest', str(manifest_path)])

    # Embed Windows version metadata (company / product / version / copyright)
    # so File Properties → Details has real values and SmartScreen heuristics
    # treat the binary as a real app. Sync the numeric tuples to constants.VERSION.
    version_file = PROJECT_DIR / 'assets' / 'version_info.py'
    if version_file.exists():
        sys.path.insert(0, str(PROJECT_DIR))
        from constants import VERSION
        try:
            parts = [int(p) for p in VERSION.split('.')[:4]]
        except ValueError:
            parts = [1, 0, 0, 0]
        while len(parts) < 4:
            parts.append(0)
        tup = ', '.join(str(p) for p in parts)
        text = version_file.read_text(encoding='utf-8')
        text = re.sub(r'filevers=\([^)]*\)', f'filevers=({tup})', text)
        text = re.sub(r'prodvers=\([^)]*\)', f'prodvers=({tup})', text)
        text = re.sub(r"'FileVersion',\s*'[^']+'", f"'FileVersion',      '{'.'.join(str(p) for p in parts)}'", text)
        text = re.sub(r"'ProductVersion',\s*'[^']+'", f"'ProductVersion',   '{VERSION}'", text)
        version_file.write_text(text, encoding='utf-8')
        cmd.extend(['--version-file', str(version_file)])

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
        # Add portable marker so the app runs in portable mode
        zf.writestr(f'{APP_NAME}/portable.txt',
                     'Portable mode — data stored in app directory\n')

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"[BUILD] Portable zip created: {zip_path} ({size_mb:.1f} MB)")
    return zip_path


def build_installer():
    """Build installer using Inno Setup (preferred) or NSIS (fallback)."""
    # Try Inno Setup first (modern look)
    iscc = shutil.which('ISCC')
    if not iscc:
        # Check common install locations
        for iscc_candidate in [
            Path('C:/Program Files (x86)/Inno Setup 6/ISCC.exe'),
            Path.home() / 'AppData/Local/Programs/Inno Setup 6/ISCC.exe',
        ]:
            if iscc_candidate.exists():
                iscc = str(iscc_candidate)
                break

    if iscc:
        return _build_inno_installer(iscc)

    # Fallback to NSIS
    makensis = shutil.which('makensis')
    if not makensis:
        makensis_path = Path('C:/Program Files (x86)/NSIS/makensis.exe')
        if makensis_path.exists():
            makensis = str(makensis_path)

    if makensis:
        return _build_nsis_installer(makensis)

    print("[BUILD] No installer tool found — skipping installer build")
    print("  Install Inno Setup: winget install JRSoftware.InnoSetup")
    return None


def _build_inno_installer(iscc: str):
    """Build installer with Inno Setup."""
    iss_script = PROJECT_DIR / 'installer.iss'
    if not iss_script.exists():
        print("[BUILD] installer.iss not found — skipping")
        return None

    # Sync version from constants.py into installer.iss
    sys.path.insert(0, str(PROJECT_DIR))
    from constants import VERSION
    iss_text = iss_script.read_text(encoding='utf-8')
    iss_text_patched = re.sub(
        r'AppVersion=.*',
        f'AppVersion={VERSION}',
        iss_text,
    )
    iss_text_patched = re.sub(
        r'OutputBaseFilename=.*',
        f'OutputBaseFilename={APP_NAME}-{VERSION}-setup',
        iss_text_patched,
    )
    if iss_text_patched != iss_text:
        iss_script.write_text(iss_text_patched, encoding='utf-8')
        print(f"  [OK] Synced installer.iss version to {VERSION}")

    print("[BUILD] Building Inno Setup installer...")
    subprocess.check_call([iscc, '/Q', str(iss_script)])

    installer_path = DIST_DIR / f'{APP_NAME}-{VERSION}-setup.exe'
    if installer_path.exists():
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        print(f"[BUILD] Installer created: {installer_path} ({size_mb:.1f} MB)")
        return installer_path

    print("[BUILD] Installer may have been created with a different name in dist/")
    return None


def _build_nsis_installer(makensis: str):
    """Build installer with NSIS (fallback)."""
    nsis_script = PROJECT_DIR / 'installer.nsi'
    if not nsis_script.exists():
        print("[BUILD] installer.nsi not found — skipping")
        return None

    sys.path.insert(0, str(PROJECT_DIR))
    from constants import VERSION
    nsi_text = nsis_script.read_text(encoding='utf-8')
    nsi_text_patched = re.sub(
        r'!define APP_VERSION ".*?"',
        f'!define APP_VERSION "{VERSION}"',
        nsi_text,
    )
    if nsi_text_patched != nsi_text:
        nsis_script.write_text(nsi_text_patched, encoding='utf-8')
        print(f"  [OK] Synced installer.nsi version to {VERSION}")

    print("[BUILD] Building NSIS installer (fallback)...")
    subprocess.check_call([makensis, str(nsis_script)])

    installer_path = DIST_DIR / f'{APP_NAME}-{VERSION}-setup.exe'
    if installer_path.exists():
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        print(f"[BUILD] Installer created: {installer_path} ({size_mb:.1f} MB)")
        return installer_path

    return None


def _resolve_signtool() -> str | None:
    """Find signtool.exe via PATH or common Windows SDK locations."""
    found = shutil.which('signtool') or shutil.which('signtool.exe')
    if found:
        return found
    sdk_root = Path('C:/Program Files (x86)/Windows Kits/10/bin')
    if sdk_root.is_dir():
        # Pick the newest x64 SDK build
        candidates = sorted(sdk_root.glob('*/x64/signtool.exe'),
                            key=lambda p: p.parent.parent.name, reverse=True)
        if candidates:
            return str(candidates[0])
    fallback = Path('C:/Program Files (x86)/Windows Kits/10/App Certification Kit/signtool.exe')
    return str(fallback) if fallback.exists() else None


def sign_executable(path: Path) -> bool:
    """Code-sign an executable with signtool when a cert is configured.

    Configuration (any one of these is enough):
      • YANCOHUB_SIGN_CERT = <path to .pfx>   + YANCOHUB_SIGN_PASS = <password>
      • YANCOHUB_SIGN_CERT = "store"           (use the best cert in CurrentUser\\My)
      • YANCOHUB_SIGN_CERT = <SHA1 thumbprint> (pick a specific cert from the store)

    Skips silently when no cert is configured so unsigned builds still succeed.
    Uses a sha256 file digest + RFC 3161 timestamp so the signature stays valid
    after the cert expires.
    """
    import os
    if not path.exists():
        return False
    signtool = _resolve_signtool()
    if not signtool:
        return False
    cert = os.environ.get('YANCOHUB_SIGN_CERT', '').strip()
    if not cert:
        return False

    cmd = [
        signtool, 'sign',
        '/tr', 'http://timestamp.digicert.com',
        '/td', 'sha256',
        '/fd', 'sha256',
    ]
    if cert.lower() == 'store':
        cmd += ['/a']
    elif Path(cert).is_file():
        cmd += ['/f', cert]
        pw = os.environ.get('YANCOHUB_SIGN_PASS', '')
        if pw:
            cmd += ['/p', pw]
    else:
        # Treat as a thumbprint in the user's certificate store
        cmd += ['/sha1', cert.replace(' ', '')]

    cmd.append(str(path))
    try:
        subprocess.check_call(cmd)
        print(f"  [OK] Signed: {path.name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] Signing failed for {path.name}: {e}")
        return False


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

    # Sign the main exe
    sign_executable(DIST_DIR / APP_NAME / f'{APP_NAME}.exe')

    if build_all or args.portable:
        build_portable_zip()

    if build_all or args.installer:
        installer_path = build_installer()
        if installer_path:
            sign_executable(installer_path)

    print("\n[BUILD] Done!")
    print(f"  App directory: dist/{APP_NAME}/")
    print(f"  Run directly:  dist/{APP_NAME}/{APP_NAME}.exe")


if __name__ == '__main__':
    main()
