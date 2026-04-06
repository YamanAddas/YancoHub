"""Tests for constants.py — validates integrity of shared constant definitions."""

from constants import (
    VERSION, FLASK_PORT,
    LIBRETRO_SYSTEMS, VALID_ART_TYPES, BUILTIN_SYSTEMS,
    STEAM_CDN, LIBRETRO_THUMB,
)


class TestVersion:
    def test_version_format(self):
        """VERSION follows semver (major.minor.patch)."""
        parts = VERSION.split('.')
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()

    def test_version_is_string(self):
        assert isinstance(VERSION, str)


class TestPorts:
    def test_flask_port_is_int(self):
        assert isinstance(FLASK_PORT, int)
        assert 1024 < FLASK_PORT < 65536


class TestLibretroSystems:
    def test_is_dict(self):
        assert isinstance(LIBRETRO_SYSTEMS, dict)

    def test_not_empty(self):
        assert len(LIBRETRO_SYSTEMS) > 20

    def test_keys_are_lowercase(self):
        for key in LIBRETRO_SYSTEMS:
            assert key == key.lower(), f"Key '{key}' should be lowercase"

    def test_values_are_nonempty_strings(self):
        for key, value in LIBRETRO_SYSTEMS.items():
            assert isinstance(value, str) and len(value) > 0, f"Bad value for '{key}'"

    def test_common_systems_present(self):
        expected = ['nes', 'snes', 'gba', 'n64', 'megadrive', 'psx']
        for sys_id in expected:
            assert sys_id in LIBRETRO_SYSTEMS, f"Missing system: {sys_id}"


class TestValidArtTypes:
    def test_is_set(self):
        assert isinstance(VALID_ART_TYPES, set)

    def test_expected_types(self):
        assert VALID_ART_TYPES == {'cover', 'header', 'hero', 'logo', 'screenshot'}


class TestBuiltinSystems:
    def test_is_set(self):
        assert isinstance(BUILTIN_SYSTEMS, set)

    def test_builtin_are_subset_of_libretro(self):
        """All built-in systems should be in LIBRETRO_SYSTEMS."""
        missing = BUILTIN_SYSTEMS - set(LIBRETRO_SYSTEMS.keys())
        assert not missing, f"Built-in systems not in LIBRETRO_SYSTEMS: {missing}"

    def test_common_builtins(self):
        for sys_id in ['nes', 'snes', 'gba', 'n64']:
            assert sys_id in BUILTIN_SYSTEMS


class TestCDNUrls:
    def test_steam_cdn_is_https(self):
        assert STEAM_CDN.startswith('https://')

    def test_libretro_thumb_is_https(self):
        assert LIBRETRO_THUMB.startswith('https://')
