"""End-to-end proof using a real Mihomo binary and local HTTP/proxy fixtures.

No public-site ranking is invented. All timings are actual curl requests through
Mihomo and controlled forward proxies. Supply the binary with --mihomo.
"""
from __future__ import annotations
import argparse
import contextlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import select
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler, Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

class TargetHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        if self.path == '/slow':
            time.sleep(5)
        status = 204 if self.path == '/second' else 200
        body = b'' if status == 204 else b'{"fixture":"actual-local-http-server"}'
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.wfile.write(body)

class ForwardHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_CONNECT(self):
        # Mihomo's HTTP outbound tunnels TCP, even when curl's target is HTTP.
        if self.server.fail:
            self.send_error(502, 'Intentional fixture CONNECT failure')
            return
        if self.path != f'127.0.0.1:{self.server.target_port}':
            self.send_error(400, 'Fixture only tunnels its local target')
            return
        with socket.create_connection(('127.0.0.1', self.server.target_port), timeout=8) as upstream:
            self.send_response(200)
            self.end_headers()
            self.wfile.flush()
            self.close_connection = True
            delayed = False
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                ready, _, _ = select.select([self.connection, upstream], [], [], .1)
                for source in ready:
                    try:
                        data = source.recv(65536)
                        if not data:
                            return
                        if source is self.connection and not delayed:
                            request_path = data.split(b' ', 2)[1].decode('ascii', errors='replace') if data.startswith(b'GET ') else ''
                            time.sleep(self.server.delays.get(request_path, 0))
                            delayed = True
                        (upstream if source is self.connection else self.connection).sendall(data)
                    except OSError:
                        return
    def do_GET(self):
        parsed = urlsplit(self.path)
        if self.server.fail:
            self.send_error(502, 'Intentional fixture failure')
            return
        if parsed.hostname != '127.0.0.1' or parsed.port != self.server.target_port:
            self.send_error(400, 'Fixture only forwards its local target')
            return
        time.sleep(self.server.delays.get(parsed.path, 0))
        upstream = http.client.HTTPConnection('127.0.0.1', parsed.port, timeout=8)
        try:
            upstream.request('GET', parsed.path or '/')
            response = upstream.getresponse()
            body = response.read()
            self.send_response(response.status)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Type', response.getheader('Content-Type', 'application/octet-stream'))
            self.end_headers()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(body)
        finally:
            upstream.close()

class FixtureHTTP(ThreadingHTTPServer):
    daemon_threads = True

def launch_http(handler):
    server = FixtureHTTP(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

def free_port():
    with socket.socket() as stream:
        stream.bind(('127.0.0.1', 0))
        return stream.getsockname()[1]

def exercise(binary, keep_dir=None):
    import engine
    import server as web
    if keep_dir:
        original_launch = engine._launch_core
        def diagnostic_launch(*args):
            try:
                return original_launch(*args)
            except Exception:
                source = Path(args[4]) / 'core.log'
                if source.exists():
                    (Path(keep_dir) / 'isolated-fixture-debug.log').write_bytes(source.read_bytes())
                raise
        engine._launch_core = diagnostic_launch
    fixtures = []
    proc = None
    httpd = None
    result = {}
    scratch = Path(keep_dir) if keep_dir else None
    temp = tempfile.TemporaryDirectory(prefix='node-probe-real-', dir=str(scratch) if scratch else None)
    base = Path(temp.name)
    opener = build_opener(ProxyHandler({}))
    try:
        target = launch_http(TargetHandler)
        fixtures.append(target)
        specs = [('日本 A', {'/ok': .025, '/second': .18}, False),
                 ('新加坡 B', {'/ok': .18, '/second': .025}, False),
                 ('香港失败', {}, True),
                 ('韩国 D', {'/ok': .12, '/second': .12}, False),
                 ('台湾 E', {'/ok': .10, '/second': .10}, False),
                 ('新加坡 cache', {'/ok': .08, '/second': .08}, False)]
        proxies = []
        for name, delays, fail in specs:
            proxy = launch_http(ForwardHandler)
            proxy.target_port = target.server_port
            proxy.delays = delays
            proxy.fail = fail
            fixtures.append(proxy)
            proxies.append({'name': name, 'type': 'http', 'server': '127.0.0.1', 'port': proxy.server_port})
        provider = base / 'provider.json'
        provider.write_text(json.dumps({'proxies': [proxies[-1]]}, ensure_ascii=False), encoding='utf-8')
        api_port = free_port()
        marker = 'integration-fixture-not-a-user-secret'
        config = {'mixed-port': free_port(), 'external-controller': f'127.0.0.1:{api_port}',
                  'secret': marker, 'allow-lan': False, 'mode': 'rule', 'log-level': 'error',
                  'proxies': proxies[:-1],
                  'proxy-providers': {'fixture-provider': {'type': 'file', 'path': 'provider.json', 'health-check': {'enable': False}}},
                  'proxy-groups': [{'name': 'Root', 'type': 'select', 'proxies': ['Asia']},
                                   {'name': 'Asia', 'type': 'select', 'proxies': [p['name'] for p in proxies[:-1]], 'use': ['fixture-provider']}],
                  'rules': ['MATCH,DIRECT']}
        config_path = base / 'main.json'
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        log = (base / 'main.log').open('w', encoding='utf-8')
        proc = subprocess.Popen([str(binary), '-d', str(base), '-f', str(config_path)], stdout=log, stderr=log)
        def main_api(path):
            request = Request(f'http://127.0.0.1:{api_port}' + path, headers={'Authorization': 'Bearer ' + marker})
            return json.load(opener.open(request, timeout=3))
        deadline = time.monotonic() + 15
        while True:
            try:
                version = main_api('/version')
                break
            except OSError:
                if proc.poll() is not None or time.monotonic() >= deadline:
                    log.flush()
                    raise AssertionError('Real Mihomo startup failed: ' + (base / 'main.log').read_text(encoding='utf-8', errors='replace'))
                time.sleep(.1)
        before = main_api('/proxies')['proxies']['Root']['now']
        connection = {'config_path': str(config_path), 'binary_path': str(binary), 'core_dir': str(base),
                      'controller': f'http://127.0.0.1:{api_port}', 'unix_socket': '', 'interface': ''}
        httpd = web.make_server(port=0, data_dir=base / 'app-data', engine_module=engine)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        cookie = ''
        def api(path, method='GET', value=None, csrf=None):
            client = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=20)
            headers = {'Cookie': cookie} if cookie else {}
            body = None
            if value is not None:
                headers['Content-Type'] = 'application/json'
                body = json.dumps(value).encode()
            if csrf:
                headers['X-CSRF-Token'] = csrf
            client.request(method, path, body, headers)
            response = client.getresponse()
            raw = response.read()
            code, response_headers = response.status, dict(response.getheaders())
            client.close()
            return code, response_headers, raw
        code, headers, _ = api('/?launch=' + httpd.app.session)
        assert code == 303
        cookie = headers['Set-Cookie'].split(';')[0]
        bootstrap = json.loads(api('/api/bootstrap')[2])
        assert bootstrap['options']['regions'] == ['jp', 'sg']
        csrf = bootstrap['csrf']
        sites = [{'id': 'fixture-ok', 'name': '本地 HTTP 200 夹具', 'url': f'http://127.0.0.1:{target.server_port}/ok', 'statuses': [200], 'validator': 'none'},
                 {'id': 'fixture-204', 'name': '本地 HTTP 204 夹具', 'url': f'http://127.0.0.1:{target.server_port}/second', 'statuses': [204], 'validator': 'none'}]
        defaults = dict(engine.DEFAULT_OPTIONS, group='Root', timeout=2)
        code, _, raw = api('/api/settings', 'POST', {'sites': sites, 'options': defaults, 'connection': connection}, csrf)
        assert code == 200, raw
        code, _, raw = api('/api/preview', 'POST', {'connection': connection, 'options': defaults}, csrf)
        assert code == 200, raw
        preview = json.loads(raw)
        assert {n['name'] for n in preview['nodes']} == {'日本 A', '新加坡 B', '新加坡 cache'}, preview
        options = dict(defaults, regions=['jp', 'sg', 'hk', 'kr', 'tw'])
        code, _, raw = api('/api/start', 'POST', {'connection': connection, 'options': options, 'site_ids': [s['id'] for s in sites]}, csrf)
        assert code == 200, raw
        deadline = time.monotonic() + 45
        while True:
            job = json.loads(api('/api/job')[2])
            if not job['running']:
                break
            assert time.monotonic() < deadline, 'Benchmark did not finish within bounded deadline'
            time.sleep(.1)
        assert not job['error'], job
        report = job['report']
        assert len(report['rows']) == len(specs) * len(sites), report
        recommendation = {r['site_id']: r['name'] for r in report['recommendations']}
        assert recommendation == {'fixture-ok': '日本 A', 'fixture-204': '新加坡 B'}, {'recommendation': recommendation, 'rows': [{'name': r['name'], 'site': r['site_id'], 'samples': r['samples']} for r in report['rows']]}
        failed = [r for r in report['rows'] if r['name'] == '香港失败']
        assert len(failed) == len(sites) and all(not r['eligible'] and r['success_rate'] == 0 for r in failed), failed
        after = main_api('/proxies')['proxies']['Root']['now']
        assert before == after
        assert marker not in json.dumps(report) and not any(k in json.dumps(report) for k in ('"password"', '"secret"'))
        export_code, _, export_raw = api('/api/export.json')
        assert export_code == 200 and json.loads(export_raw)['rows'] == report['rows']
        assert api('/api/export.csv')[0] == 200
        result = {'mihomo_version': version, 'real_http_requests': sum(r['total'] for r in report['rows']),
                  'nodes': len(specs), 'sites': len(sites), 'rows': len(report['rows']),
                  'recommendations': recommendation, 'main_selection_unchanged': before == after,
                  'provider_cache_loaded': any(r['name'] == '新加坡 cache' for r in report['rows']),
                  'jp_sg_default_preview': preview['total'], 'exports_verified': True,
                  'measurements': [{'name': r['name'], 'site_id': r['site_id'], 'success_rate': r['success_rate'], 'median_ms': r['median_ms']} for r in report['rows']]}
        # Exercise cancellation on a real slow network request, not a fake engine.
        slow = dict(sites[0], id='fixture-slow', name='本地慢请求取消夹具', url=f'http://127.0.0.1:{target.server_port}/slow')
        slow_options = dict(defaults, node_names=['日本 A'], timeout=10, workers=1)
        assert api('/api/settings', 'POST', {'sites': [slow], 'options': slow_options, 'connection': connection}, csrf)[0] == 200
        assert api('/api/start', 'POST', {'connection': connection, 'options': slow_options, 'site_ids': [slow['id']]}, csrf)[0] == 200
        time.sleep(.5)
        stopped_at = time.monotonic()
        assert api('/api/stop', 'POST', {}, csrf)[0] == 200
        httpd.app.worker.join(timeout=6)
        assert not httpd.app.worker.is_alive(), 'Cancel did not terminate the real probe in time'
        cancelled = json.loads(api('/api/job')[2])
        assert not cancelled['running'] and cancelled['report'] is None
        assert httpd.app.last_report == report
        result['cancel_ms'] = round((time.monotonic() - stopped_at) * 1000)
        result['cancel_kept_last_report'] = True
        if scratch:
            (scratch / 'integration-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    finally:
        if httpd:
            httpd.app.stop.set()
            if httpd.app.worker:
                httpd.app.worker.join(timeout=15)
            httpd.shutdown()
            httpd.server_close()
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            log.close()
        for fixture in fixtures:
            fixture.shutdown()
            fixture.server_close()
        temp.cleanup()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mihomo', type=Path, required=True)
    parser.add_argument('--scratch', type=Path)
    args = parser.parse_args()
    exercise(args.mihomo.resolve(), args.scratch)
