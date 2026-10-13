"""桌面私有协议的关键语义与 Windows 适配回归。"""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import desktop_host
import engine
from server import App
import windows_support


class DesktopProtocolTests(unittest.TestCase):
    def test_export_filter_does_not_change_last_complete_report(self):
        with tempfile.TemporaryDirectory() as folder:
            app=App(folder)
            rows=[{'name':'JP good','eligible':True,'samples':[]},
                  {'name':'SG failed','eligible':False,'samples':[]}]
            app.last_report={'rows':rows,'recommendations':[]}
            value=desktop_host.dispatch(app,'export',
                {'format':'json','include_failures':False})
            report=json.loads(base64.b64decode(value['content']))
            self.assertEqual([r['name'] for r in report['rows']],['JP good'])
            self.assertEqual(len(app.last_report['rows']),2)
            csv=desktop_host.dispatch(app,'export',{'format':'csv','include_failures':False})
            self.assertNotIn('SG failed',base64.b64decode(csv['content']).decode('utf-8-sig'))

    def test_empty_connections_still_discover_windows_client(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json'
            path.write_text(json.dumps({'proxies':[]}),encoding='utf-8')
            with patch.object(engine.sys,'platform','win32'), \
                 patch.object(engine,'discover_windows',return_value={
                     'config_path':str(path),'binary_path':str(path)}) as discover, \
                 patch.object(engine,'physical_interface',return_value='以太网'):
                value=engine.discover({'config_path':'','binary_path':''})
                self.assertEqual(value['interface'],'以太网')
                discover.assert_called_once()

    def test_named_pipe_only_allows_read_only_endpoints(self):
        with self.assertRaises(ValueError):
            windows_support.pipe_api(r'\\.\pipe\mihomo','/configs')

    def test_no_report_export_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'尚无完整'):
                desktop_host.dispatch(App(folder),'export',{})


if __name__=='__main__':
    unittest.main()
