"""Unit tests for background plugin discovery in desktop mode."""

import os
import unittest
from unittest.mock import MagicMock, patch

from moor_cli.main import _dashboard_prepare_runtime
from moor_cli.plugins import start_background_plugin_discovery


class TestBackgroundPluginDiscovery(unittest.TestCase):
    def test_start_background_plugin_discovery_spawns_thread(self):
        with patch("moor_cli.plugins.get_plugin_manager") as mock_mgr_getter:
            mock_mgr = MagicMock()
            mock_mgr._discovered = False
            mock_mgr_getter.return_value = mock_mgr

            start_background_plugin_discovery()

            # Ensure get_plugin_manager was accessed to start discovery
            self.assertTrue(mock_mgr_getter.called)

    def test_dashboard_prepare_runtime_uses_background_discovery_in_desktop_mode(self):
        with (
            patch.dict(os.environ, {"MOOR_DESKTOP": "1"}, clear=False),
            patch("moor_cli.plugins.start_background_plugin_discovery") as mock_bg_discover,
            patch("moor_cli.plugins.discover_plugins") as mock_sync_discover,
            patch("moor_cli.main._resolve_dashboard_web_dist"),
        ):
            args = MagicMock()
            _dashboard_prepare_runtime(args, headless_backend=True)

            mock_bg_discover.assert_called_once()
            mock_sync_discover.assert_not_called()

    def test_dashboard_prepare_runtime_uses_sync_discovery_in_cli_mode(self):
        with (
            patch.dict(os.environ, {"MOOR_DESKTOP": "0"}, clear=False),
            patch("moor_cli.plugins.start_background_plugin_discovery") as mock_bg_discover,
            patch("moor_cli.plugins.discover_plugins") as mock_sync_discover,
            patch("moor_cli.main._resolve_dashboard_web_dist"),
        ):
            args = MagicMock()
            _dashboard_prepare_runtime(args, headless_backend=False)

            mock_sync_discover.assert_called_once()
            mock_bg_discover.assert_not_called()


if __name__ == "__main__":
    unittest.main()
