"""Tests for settings_schema.py — the settings single-source-of-truth."""

import settings_schema as ss


class TestDefaults:
    def test_build_defaults_excludes_registry_keys(self):
        defaults = ss.build_default_settings()
        # userdata-backed keys present
        assert defaults['show_uninstalled'] is True
        assert defaults['direct_launch'] is True
        assert defaults['start_in_game_mode'] is False
        assert defaults['gamepad_mapping'] == {}
        assert defaults['retroarch_path'] == ''
        # registry-backed key excluded from userdata defaults
        assert 'launch_on_startup' not in defaults

    def test_every_default_matches_its_type(self):
        for key, spec in ss.SETTINGS.items():
            ok, cleaned = ss.validate(key, spec['default']) if not spec.get('hidden') else (True, None)
            # hidden keys (onboarding_complete) validate as unknown by design
            if spec.get('hidden'):
                continue
            assert ok, f"default for {key} failed validation"


class TestValidate:
    def test_bool_coercion(self):
        assert ss.validate('show_uninstalled', 1) == (True, True)
        assert ss.validate('show_uninstalled', 0) == (True, False)
        assert ss.validate('direct_launch', False) == (True, False)

    def test_unknown_key_rejected(self):
        ok, msg = ss.validate('does_not_exist', True)
        assert ok is False

    def test_hidden_key_rejected(self):
        ok, msg = ss.validate('onboarding_complete', True)
        assert ok is False

    def test_path_dir_must_exist(self, tmp_path):
        ok, val = ss.validate('launchbox_path', str(tmp_path))
        assert ok and val == str(tmp_path)
        ok, msg = ss.validate('launchbox_path', str(tmp_path / 'nope'))
        assert ok is False

    def test_path_empty_is_allowed(self):
        assert ss.validate('launchbox_path', '') == (True, '')
        assert ss.validate('retroarch_path', '   ') == (True, '')

    def test_path_file_accepts_existing(self, tmp_path):
        f = tmp_path / 'retroarch.exe'
        f.write_text('x')
        ok, val = ss.validate('retroarch_path', str(f))
        assert ok and val == str(f)

    def test_path_non_string_rejected(self):
        ok, msg = ss.validate('retroarch_path', 123)
        assert ok is False

    def test_int_map_cleans_values(self):
        ok, cleaned = ss.validate('gamepad_mapping',
                                  {'a': 2, 'neg': -1, 'b': 'x', 'bool': True})
        assert ok
        assert cleaned == {'a': 2}  # negative, string, and bool dropped

    def test_int_map_rejects_non_dict(self):
        ok, msg = ss.validate('gamepad_mapping', 'bad')
        assert ok is False

    def test_enum_accepts_choice(self):
        assert ss.validate('card_density', 'compact') == (True, 'compact')
        assert ss.validate('card_density', 'spacious') == (True, 'spacious')

    def test_enum_rejects_invalid(self):
        ok, msg = ss.validate('card_density', 'huge')
        assert ok is False
        assert 'compact' in msg  # error lists valid choices

    def test_color_accepts_six_digit_hex(self):
        assert ss.validate('theme_accent', '#00e5c1') == (True, '#00e5c1')
        assert ss.validate('theme_accent', '#FF7E5F') == (True, '#ff7e5f')

    def test_color_expands_three_digit_hex(self):
        assert ss.validate('theme_accent', '#0fc') == (True, '#00ffcc')

    def test_color_accepts_without_hash(self):
        assert ss.validate('theme_accent', '00e5c1') == (True, '#00e5c1')

    def test_color_rejects_invalid(self):
        for bad in ['', 'not-a-color', '#zzzzzz', '#00e5c', 12345]:
            ok, _ = ss.validate('theme_accent', bad)
            if bad == '':
                assert ok is True  # empty allowed (clears)
            else:
                assert ok is False, f'should reject {bad!r}'


class TestPublicSchema:
    def test_excludes_hidden(self):
        keys = {entry['key'] for entry in ss.public_schema()}
        assert 'onboarding_complete' not in keys
        assert 'show_uninstalled' in keys

    def test_entries_have_ui_metadata(self):
        for entry in ss.public_schema():
            assert entry['label']
            assert entry['tab']
            assert 'default' in entry
            # internal fields not leaked
            assert 'side_effect' not in entry
            assert 'backend' not in entry

    def test_enum_entry_exposes_choices(self):
        density = next(e for e in ss.public_schema() if e['key'] == 'card_density')
        assert density['choices'] == ['compact', 'comfortable', 'spacious']
