"""Tests for updatecheck.py — version parsing, comparison, mocked HTTP."""

import json
from unittest.mock import patch, MagicMock

import pytest

from updatecheck import _parse_version, _is_newer, check_for_update


class TestParseVersion:
    def test_simple_version(self):
        assert _parse_version('1.2.3') == (1, 2, 3)

    def test_version_with_v_prefix(self):
        assert _parse_version('v1.0.0') == (1, 0, 0)

    def test_invalid_returns_zero(self):
        assert _parse_version('invalid') == (0, 0, 0)

    def test_empty_returns_zero(self):
        assert _parse_version('') == (0, 0, 0)

    def test_whitespace_stripped(self):
        assert _parse_version('  v2.5.1  ') == (2, 5, 1)


class TestIsNewer:
    def test_newer_major(self):
        assert _is_newer('2.0.0', '1.0.0') is True

    def test_newer_minor(self):
        assert _is_newer('1.1.0', '1.0.0') is True

    def test_newer_patch(self):
        assert _is_newer('1.0.1', '1.0.0') is True

    def test_same_version(self):
        assert _is_newer('1.0.0', '1.0.0') is False

    def test_older_version(self):
        assert _is_newer('0.9.0', '1.0.0') is False


class TestCheckForUpdate:
    def test_returns_info_when_newer(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'tag_name': 'v2.0.0',
            'html_url': 'https://github.com/test/releases/v2.0.0',
            'name': 'Release 2.0.0',
            'body': 'Bug fixes',
        }

        with patch('updatecheck.requests.get', return_value=mock_resp), \
             patch('updatecheck.VERSION', '1.0.0'):
            result = check_for_update()
            assert result is not None
            assert result['latest_version'] == '2.0.0'
            assert result['current_version'] == '1.0.0'
            assert 'url' in result

    def test_returns_none_when_same(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'tag_name': 'v1.0.0'}

        with patch('updatecheck.requests.get', return_value=mock_resp), \
             patch('updatecheck.VERSION', '1.0.0'):
            assert check_for_update() is None

    def test_returns_none_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch('updatecheck.requests.get', return_value=mock_resp):
            assert check_for_update() is None

    def test_returns_none_on_network_error(self):
        with patch('updatecheck.requests.get', side_effect=Exception('timeout')):
            assert check_for_update() is None

    def test_returns_none_when_no_tag(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'tag_name': ''}

        with patch('updatecheck.requests.get', return_value=mock_resp):
            assert check_for_update() is None
