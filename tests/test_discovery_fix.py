"""Regression tests for browser connection forms whose blank fields mean auto."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine

class AutoDiscoveryTests(unittest.TestCase):
    def test_blank_controller_field_uses_config_controller(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps({'external-controller': '127.0.0.1:9090'}), encoding='utf-8')
            form = {key: '' for key in ('config_path', 'binary_path', 'core_dir', 'controller', 'unix_socket', 'interface')}
            form.update(config_path=str(config), binary_path=sys.executable)
            resolved = engine.discover(form)
            self.assertEqual(resolved['controller'], 'http://127.0.0.1:9090')

    def test_catalog_auto_discovers_before_reading_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps({'proxies': [{'name': '日本 fixture', 'type': 'http', 'server': '127.0.0.1', 'port': 8888}]}), encoding='utf-8')
            resolved = {'config_path': str(config), 'binary_path': sys.executable, 'core_dir': directory, 'controller': '', 'unix_socket': '', 'interface': ''}
            with patch.object(engine, 'discover', return_value=resolved) as discovery:
                try:
                    catalog = engine.catalog({key: '' for key in resolved})
                except (RuntimeError, ValueError, OSError, KeyError):
                    catalog = None
                self.assertIsNotNone(catalog, 'Blank browser settings must trigger discovery before config access')
                self.assertEqual([n['name'] for n in catalog['nodes']], ['日本 fixture'])
                discovery.assert_called_once()

if __name__ == '__main__':
    unittest.main()
