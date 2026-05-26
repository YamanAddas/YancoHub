"""
YancoHub Settings Schema — single source of truth for user-facing key/value settings.

Each entry declares a setting's type, default, owning tab, label/hint (for the UI),
and how it is applied. This module is pure data + validation (no app imports), so it
can be unit-tested and imported by both userdata.py (to build defaults) and app.py
(to drive the unified GET/PATCH /api/settings endpoints).

Backends:
  - 'userdata' (default): value is persisted in userdata.json under 'settings'
  - 'registry': value lives in an external store (Windows registry); app.py reads/
    writes it via a handler and does NOT persist it in userdata

Side effects (applied by app.py after a successful PATCH) are named by 'side_effect';
the dispatch lives in app.py where scanner/artwork/startup are already imported.
"""

from pathlib import Path

# Supported value types: 'bool', 'enum', 'color', 'path_file', 'path_dir', 'int_map'
SETTINGS = {
    'show_uninstalled': {
        'type': 'bool',
        'default': True,
        'tab': 'accounts',
        'label': 'Show uninstalled games',
        'hint': "Display owned games from connected accounts even if they're not "
                'currently installed',
        'side_effect': 'rebuild_library',
    },
    'direct_launch': {
        'type': 'bool',
        'default': True,
        'tab': 'accounts',
        'label': 'Direct launch',
        'hint': 'Run games directly without opening the store client. Works best for '
                'GOG (DRM-free) and Epic. Some Steam games may still require Steam.',
    },
    'start_in_game_mode': {
        'type': 'bool',
        'default': False,
        'tab': 'display',
        'label': 'Start in Game Mode',
        'hint': 'Launch YancoHub directly into fullscreen Game Mode',
    },
    'card_density': {
        'type': 'enum',
        'choices': ['compact', 'comfortable', 'spacious'],
        'default': 'comfortable',
        'tab': 'display',
        'label': 'Card density',
        'hint': 'How large game cards appear in the carousel',
    },
    'theme_accent': {
        'type': 'color',
        'default': '#00e5c1',
        'tab': 'display',
        'label': 'Accent color',
        'hint': 'Recolors highlights, glows, and active states throughout the UI',
    },
    'show_now_playing': {
        'type': 'bool',
        'default': True,
        'tab': 'display',
        'label': 'Show Now Playing screen',
        'hint': 'Fade into a cinematic ambient screen when you launch a game',
    },
    'launch_on_startup': {
        'type': 'bool',
        'default': False,
        'tab': 'display',
        'label': 'Launch on Windows startup',
        'hint': 'Automatically start YancoHub when you sign in to Windows',
        'backend': 'registry',
    },
    'retroarch_path': {
        'type': 'path_file',
        'default': '',
        'tab': 'emulation',
        'label': 'RetroArch path',
        'hint': 'Path to retroarch.exe or the folder containing it',
        'side_effect': 'update_retroarch',
    },
    'launchbox_path': {
        'type': 'path_dir',
        'default': '',
        'tab': 'emulation',
        'label': 'LaunchBox path',
        'hint': 'Point to your LaunchBox install folder to use its artwork for covers '
                '— no files are copied',
        'side_effect': 'update_launchbox',
    },
    'gamepad_mapping': {
        'type': 'int_map',
        'default': {},
        'tab': 'controller',
        'label': 'Controller button mapping',
        'hint': 'Custom controller button assignments',
    },
    'onboarding_complete': {
        'type': 'bool',
        'default': False,
        'hidden': True,  # internal — not shown in the settings UI
    },
}


def build_default_settings() -> dict:
    """Defaults for every userdata-backed setting (registry-backed keys excluded)."""
    return {
        key: spec['default']
        for key, spec in SETTINGS.items()
        if spec.get('backend', 'userdata') == 'userdata'
    }


def validate(key: str, value):
    """Validate/coerce a value against its schema entry.

    Returns (True, cleaned_value) or (False, error_message).
    """
    spec = SETTINGS.get(key)
    if spec is None or spec.get('hidden'):
        return False, 'unknown setting'

    t = spec['type']

    if t == 'bool':
        return True, bool(value)

    if t == 'enum':
        choices = spec.get('choices', [])
        if value in choices:
            return True, value
        return False, f'must be one of: {", ".join(choices)}'

    if t == 'color':
        if not isinstance(value, str):
            return False, 'must be a hex color string'
        v = value.strip().lower()
        if not v:
            return True, ''
        if v.startswith('#'):
            v = v[1:]
        if len(v) == 3:
            v = ''.join(c * 2 for c in v)
        if len(v) != 6 or any(c not in '0123456789abcdef' for c in v):
            return False, 'must be a hex color like #00e5c1'
        return True, '#' + v

    if t in ('path_file', 'path_dir'):
        if not isinstance(value, str):
            return False, 'must be a string path'
        v = value.strip()
        if v:
            p = Path(v)
            if t == 'path_dir' and not p.is_dir():
                return False, 'Directory not found'
            if t == 'path_file' and not p.exists():
                return False, 'File not found'
        return True, v

    if t == 'int_map':
        if not isinstance(value, dict):
            return False, 'must be an object'
        clean = {}
        for k, val in value.items():
            # bool is a subclass of int — exclude it explicitly
            if isinstance(val, bool):
                continue
            if isinstance(val, int) and val >= 0:
                clean[str(k)] = val
        return True, clean

    return False, 'unsupported type'


def public_schema() -> list:
    """UI-facing metadata for visible settings (no internal side_effect/backend)."""
    out = []
    for key, spec in SETTINGS.items():
        if spec.get('hidden'):
            continue
        entry = {
            'key': key,
            'type': spec['type'],
            'tab': spec.get('tab'),
            'label': spec.get('label'),
            'hint': spec.get('hint'),
            'default': spec['default'],
        }
        if 'choices' in spec:
            entry['choices'] = list(spec['choices'])
        out.append(entry)
    return out
