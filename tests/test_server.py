"""Local HTTP boundary tests; fixture engine never represents real benchmark data."""
import http.client
import importlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

class FixtureEngine:
    REGIONS = [{'id': 'jp', 'name': '日本'}, {'id': 'sg', 'name': '新加坡'}]
    DEFAULT_OPTIONS = {'regions': ['jp', 'sg'], 'rounds': 3, 'workers': 4, 'timeout': 8}
    DEFAULT_SITES = [{'id': 'chatgpt', 'name': 'ChatGPT', 'url': 'https://chatgpt.com/cdn-cgi/trace', 'statuses': [200], 'validator': 'chatgpt-trace'}]

    @staticmethod
    def validate_site(site):
        if not isinstance(site, dict) or not site.get('url', '').startswith('https://'):
            raise ValueError('网站地址无效')
        return dict(site)

    @staticmethod
    def catalog(connection):
        return {'connection': connection, 'nodes': [{'name': '日本 fixture', 'region': 'jp', 'provider': 'local', 'type': 'http'}], 'groups': [], 'providers': ['local'], 'warnings': []}

    @staticmethod
    def filter_nodes(catalog, options):
        return [node for node in catalog['nodes'] if node['region'] in options['regions']]

    @staticmethod
    def benchmark(connection, sites, options, emit, stop):
        emit('start', total=1)
        if not stop.wait(timeout=5):
            raise RuntimeError('测试应主动停止任务')
        raise RuntimeError('已停止（测试控制信号）')

    @staticmethod
    def validate_options(options):
        return dict(FixtureEngine.DEFAULT_OPTIONS, **options)

class ServerTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('server')
        except ModuleNotFoundError:
            self.module = None
        self.assertIsNotNone(self.module, 'The runnable local web server has not been implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.httpd = self.module.make_server(port=0, data_dir=Path(self.temp.name), engine_module=FixtureEngine)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = ''

    def tearDown(self):
        if hasattr(self, 'httpd'):
            self.httpd.shutdown()
            self.httpd.server_close()
            self.thread.join(timeout=2)
            self.temp.cleanup()

    def request(self, path, method='GET', body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=3)
        merged = dict(headers or {})
        if self.cookie:
            merged['Cookie'] = self.cookie
        if body is not None:
            merged['Content-Type'] = 'application/json'
            body = json.dumps(body).encode()
        connection.request(method, path, body=body, headers=merged)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def login(self):
        status, headers, _ = self.request('/?launch=' + self.httpd.app.session)
        self.assertEqual(status, 303)
        self.cookie = headers['Set-Cookie'].split(';')[0]
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])

    def test_bootstrap_requires_launch_session_and_defaults_to_jp_sg(self):
        self.assertEqual(self.request('/api/bootstrap')[0], 403)
        self.login()
        status, headers, body = self.request('/api/bootstrap')
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data['options']['regions'], ['jp', 'sg'])
        self.assertTrue(data['csrf'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertIsNone(data['last_report'])

    def test_settings_require_csrf_and_persist(self):
        self.login()
        csrf = json.loads(self.request('/api/bootstrap')[2])['csrf']
        payload = {'sites': FixtureEngine.DEFAULT_SITES, 'options': {'regions': ['sg'], 'rounds': 4}, 'connection': {'config_path': '/tmp/example.yaml'}}
        self.assertEqual(self.request('/api/settings', 'POST', payload)[0], 403)
        status, _, body = self.request('/api/settings', 'POST', payload, {'X-CSRF-Token': csrf})
        self.assertEqual(status, 200, body)
        restored = self.module.App(Path(self.temp.name), FixtureEngine)
        self.assertEqual(restored.settings['options']['regions'], ['sg'])
        self.assertEqual(restored.settings['connection']['config_path'], '/tmp/example.yaml')
        self.assertNotIn('csrf', json.loads((Path(self.temp.name) / 'settings.json').read_text()))

    def test_job_rejects_overlap_and_stops_without_fabricated_report(self):
        self.login()
        csrf = json.loads(self.request('/api/bootstrap')[2])['csrf']
        headers = {'X-CSRF-Token': csrf}
        payload = {'site_ids': ['chatgpt'], 'options': FixtureEngine.DEFAULT_OPTIONS, 'connection': {}}
        status, _, body = self.request('/api/start', 'POST', payload, headers)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.request('/api/start', 'POST', payload, headers)[0], 409)
        self.assertEqual(self.request('/api/stop', 'POST', {}, headers)[0], 200)
        self.httpd.app.worker.join(timeout=3)
        status, _, body = self.request('/api/job')
        self.assertEqual(status, 200)
        job = json.loads(body)
        self.assertFalse(job['running'])
        self.assertIn('已停止', job['error'])
        self.assertIsNone(job['report'])
        self.assertIsNone(self.httpd.app.last_report)

    def test_preview_returns_only_filtered_catalog_without_starting_job(self):
        self.login()
        csrf = json.loads(self.request('/api/bootstrap')[2])['csrf']
        status, _, body = self.request('/api/preview', 'POST', {'options': {'regions': ['sg']}, 'connection': {}}, {'X-CSRF-Token': csrf})
        self.assertEqual(status, 200, body)
        preview = json.loads(body)
        self.assertEqual(preview['total'], 0)
        self.assertEqual(preview['nodes'], [])
        self.assertEqual(len(preview['catalog']['nodes']), 1)
        self.assertFalse(self.httpd.app.job['running'])

    def test_export_is_session_gated_and_csv_disarms_spreadsheet_formula(self):
        self.assertEqual(self.request('/api/export.csv')[0], 403)
        self.login()
        self.assertEqual(self.request('/api/export.json')[0], 404)
        fixture = {'rows': [{'name': '=1+1', 'region': 'jp', 'site_name': '@fixture', 'url': 'https://example.test/', 'success_rate': 0, 'median_ms': None, 'samples': []}], 'recommendations': []}
        self.httpd.app.last_report = fixture
        status, headers, body = self.request('/api/export.csv')
        self.assertEqual(status, 200)
        text = body.decode('utf-8-sig')
        self.assertIn("'=1+1", text)
        self.assertIn("'@fixture", text)
        self.assertIn('attachment', headers['Content-Disposition'])
        self.httpd.app.write_json(Path(self.temp.name) / 'latest.json', fixture)
        self.assertEqual(self.module.App(Path(self.temp.name), FixtureEngine).last_report, fixture)

    def test_command_line_has_runnable_entrypoint(self):
        result = subprocess.run([sys.executable, str(ROOT / 'server.py'), '--help'], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--no-browser', result.stdout)
        self.assertIn('--data-dir', result.stdout)

    def test_foreign_origin_and_dns_rebinding_host_are_rejected(self):
        self.login()
        csrf = json.loads(self.request('/api/bootstrap')[2])['csrf']
        self.assertEqual(self.request('/api/bootstrap', headers={'Host': 'attacker.example'})[0], 403)
        headers = {'X-CSRF-Token': csrf, 'Origin': 'https://attacker.example'}
        self.assertEqual(self.request('/api/settings', 'POST', {}, headers)[0], 403)
        status, _, body = self.request('/api/settings', 'POST', {'connection': {'secret': 'not-accepted'}}, {'X-CSRF-Token': csrf})
        self.assertEqual(status, 400)
        self.assertNotIn('not-accepted', body.decode())

    def test_non_ascii_security_tokens_return_denial_without_crashing_handler(self):
        try:
            status = self.request('/?launch=%C3%A9')[0]
        except http.client.RemoteDisconnected:
            status = None
        self.assertEqual(status, 403, 'Invalid launch tokens must be denied, not crash the request handler')
        self.login()
        try:
            status = self.request('/api/settings', 'POST', {}, {'X-CSRF-Token': '\u00e9'})[0]
        except http.client.RemoteDisconnected:
            status = None
        self.assertEqual(status, 403)

if __name__ == '__main__':
    unittest.main()
