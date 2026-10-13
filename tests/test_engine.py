"""Real local-network fixtures; never synthesize benchmark successes."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class EngineTests(unittest.TestCase):
    def test_site_validation_rejects_unsafe_targets(self):
        self.assertIsNotNone(importlib.util.find_spec('engine'), 'engine module is required')
        import engine
        for url in ['file:///etc/passwd', 'https://u:p@example.org/', 'https://example.org/\n', 'https://']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                engine.validate_site({'url': url})
        site = engine.validate_site({'name': '自定义', 'url': 'http://localhost:8090/a', 'statuses': [200, '204']})
        self.assertEqual(site['statuses'], [200, 204])
        self.assertRegex(site['id'], r'^[a-zA-Z0-9_-]+$')
        self.assertEqual(site['validator'], 'none')
        for bad in [{'statuses': [999]}, {'validator': 'execute'}, {'id': '../secret'}]:
            with self.assertRaises(ValueError):
                engine.validate_site({'url': 'https://example.org/', **bad})

class OptionTests(unittest.TestCase):
    def test_option_defaults_and_resource_limits(self):
        import engine
        self.assertTrue(hasattr(engine, 'validate_options'), 'option validation required')
        opts = engine.validate_options({})
        self.assertEqual(opts['regions'], ['jp', 'sg'])
        self.assertEqual(opts['rounds'], 3)
        self.assertEqual(opts['workers'], 4)
        self.assertEqual([s['name'] for s in engine.DEFAULT_SITES], ['ChatGPT', 'GitHub', 'Google', 'YouTube', 'Wikipedia'])
        for field, value in [('regions', ['mars']), ('limit', 201), ('workers', 0), ('rounds', 99), ('timeout', -1), ('limit', True), ('node_names', 'abc')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                engine.validate_options({field: value})

class FilterTests(unittest.TestCase):
    def test_region_and_recursive_filters_are_precise(self):
        import engine
        self.assertTrue(hasattr(engine, 'filter_nodes'))
        names = ['JP fast', 'Singapore clean', 'HK excluded', 'randomjpword', '🇰🇷 Seoul', '台北 01', 'Tokyo slow']
        nodes = [{'name': n, 'region': engine._region(n), 'provider': 'p', 'type': 'ss'} for n in names]
        self.assertEqual([n['region'] for n in nodes], ['jp', 'sg', 'hk', 'other', 'kr', 'tw', 'jp'])
        cat = {'nodes': nodes + [nodes[0]], 'groups': [{'name': 'root', 'all': ['nested', 'root']}, {'name': 'nested', 'all': names[:3]}], 'providers': ['p']}
        out = engine.filter_nodes(cat, {'group': 'root', 'provider': 'p', 'include': 'FAST,clean', 'exclude': 'excluded'})
        self.assertEqual([n['name'] for n in out], names[:2])
        self.assertEqual(len(engine.filter_nodes(cat, {'regions': [], 'limit': 1})), 1)
        with self.assertRaises(ValueError):
            engine.filter_nodes(cat, {'group': 'missing'})
        with self.assertRaises(ValueError):
            engine.filter_nodes({'nodes': [{'name': f'JP {i}', 'region': 'jp'} for i in range(201)], 'groups': []}, {})

import json
import tempfile
import threading
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager

@contextmanager
def controller_fixture():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            calls.append((self.path, self.headers.get('Authorization')))
            payload = {'/version': {'version': 'fixture'}, '/proxies': {'proxies': {'root': {'all': ['[P] JP cached', 'SG inline'], 'now': 'SG inline'}, '[P] JP cached': {'type': 'Http'}, 'SG inline': {'type': 'Http'}}}, '/providers/proxies': {'providers': {'p': {'proxies': [{'name': '[P] JP cached'}]}, 'inline': {'proxies': [{'name': 'SG inline'}]}}}}.get(self.path, {})
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', calls
    finally:
        server.shutdown(); server.server_close(); thread.join()

class CatalogTests(unittest.TestCase):
    def test_explicit_discovery_and_cached_provider_catalog_are_read_only(self):
        import engine
        self.assertTrue(hasattr(engine, 'discover'))
        with tempfile.TemporaryDirectory() as tmp, controller_fixture() as (url, calls):
            base = Path(tmp)
            (base / 'cache').mkdir()
            (base / 'cache/p.yaml').write_text('proxies:\n- {name: JP cached, type: http, server: localhost, port: 8080, password: NEVER_LEAK}\n', encoding='utf-8')
            cfg = {'secret': 'CONTROLLER_SECRET', 'external-controller': url, 'proxy-providers': {'p': {'type': 'http', 'url': 'https://never.download/', 'path': 'cache/p.yaml', 'override': {'additional-prefix': '[P] '}}, 'inline': {'type': 'inline', 'payload': [{'name': 'SG inline', 'type': 'http', 'server': 'localhost', 'port': 8081}]}, 'missing': {'type': 'file', 'path': 'missing.yaml'}}, 'proxy-groups': [{'name': 'root', 'type': 'select', 'use': ['p', 'inline']}]}
            path = base / 'main.json'; path.write_text(json.dumps(cfg), encoding='utf-8')
            before = path.read_bytes()
            connection = engine.discover({'config_path': str(path), 'binary_path': sys.executable, 'core_dir': str(base), 'interface': ''})
            self.assertEqual(connection['core_dir'], str(base.resolve()))
            cat = engine.catalog(connection)
            self.assertEqual([n['name'] for n in cat['nodes']], ['[P] JP cached', 'SG inline'])
            self.assertEqual(cat['groups'][0]['all'], ['[P] JP cached', 'SG inline'])
            self.assertTrue(any('missing' in w and '缓存' in w for w in cat['warnings']))
            public = json.dumps(cat)
            self.assertNotIn('NEVER_LEAK', public); self.assertNotIn('CONTROLLER_SECRET', public)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual({p for p, auth in calls}, {'/version', '/proxies', '/providers/proxies'})
            self.assertTrue(all(auth == 'Bearer CONTROLLER_SECRET' for p, auth in calls))
            with self.assertRaises(ValueError):
                engine.discover({'config_path': str(path), 'binary_path': sys.executable, 'controller': 'http://evil.example:9090'})

class IsolationTests(unittest.TestCase):
    def test_minimal_config_closes_dialer_dependencies_without_main_routes(self):
        import engine
        self.assertTrue(hasattr(engine, '_isolated_config'))
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); (base / 'cert.pem').write_text('fixture certificate')
            nodes = {'JP target': ({'name': 'JP target', 'type': 'http', 'server': 'localhost', 'port': 1, 'dialer-proxy': 'SG hop', 'certificate': 'cert.pem', 'interface-name': 'utun3'}, ''), 'SG hop': ({'name': 'SG hop', 'type': 'socks5', 'server': 'localhost', 'port': 2}, ''), 'unrelated': ({'name': 'unrelated', 'type': 'http'}, '')}
            conf = engine._isolated_config({'core_dir': tmp, 'interface': 'en0'}, [{'name': 'JP target'}], nodes, {'rules': ['GEOIP,CN,DIRECT'], 'tun': {'enable': True}}, {'JP target': 10001})
            self.assertEqual({p['name'] for p in conf['proxies']}, {'JP target', 'SG hop'})
            self.assertEqual(conf['listeners'][0]['proxy'], 'JP target')
            self.assertEqual(conf['listeners'][0]['listen'], '127.0.0.1')
            self.assertTrue(all(listener.get('udp') is False for listener in conf['listeners']), 'HTTP/TCP 探针必须显式关闭每个监听器的 UDP')
            self.assertEqual(conf['rules'], ['MATCH,REJECT'])
            self.assertFalse(conf['tun']['enable'])
            self.assertNotIn('proxy-providers', conf); self.assertNotIn('external-controller', conf)
            self.assertTrue(all(p['interface-name'] == 'en0' for p in conf['proxies']))
            self.assertEqual(conf['proxies'][-1]['certificate'], str((base / 'cert.pem').resolve()))
            nodes['SG hop'][0]['dialer-proxy'] = 'JP target'
            with self.assertRaises(ValueError): engine._isolated_config({'core_dir': tmp, 'interface': 'en0'}, [{'name': 'JP target'}], nodes, {}, {'JP target': 10001})

import time
import urllib.request
from urllib.parse import urlsplit

@contextmanager
def network_fixture():
    seen = []
    class Origin(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            if self.path == '/slow': time.sleep(2)
            body = b'h=chatgpt.com\nip=127.0.0.1\n' if self.path == '/trace' else b'<html>real fixture response</html>'
            status = 403 if self.path == '/blocked' else 200
            try:
                self.send_response(status); self.send_header('Content-Length', str(len(body))); self.end_headers()
                self.wfile.write(body)
            except OSError: pass
    origin = ThreadingHTTPServer(('127.0.0.1', 0), Origin)
    class Forward(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_CONNECT(self):
            import socket, select
            seen.append(self.path)
            if self.path != f'127.0.0.1:{origin.server_port}':
                self.send_error(403); return
            with socket.create_connection(('127.0.0.1', origin.server_port), timeout=4) as upstream:
                self.send_response(200); self.end_headers(); self.wfile.flush()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([self.connection, upstream], [], [], .1)
                    for source in ready:
                        try:
                            data = source.recv(65536)
                            if not data: return
                            (upstream if source is self.connection else self.connection).sendall(data)
                        except OSError: return
        def do_GET(self):
            seen.append(self.path)
            if self.path.startswith('/'):
                self.send_error(400); return
            target = urlsplit(self.path)
            if target.hostname != '127.0.0.1' or target.port != origin.server_port:
                self.send_error(403); return
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(self.path, timeout=4) as response:
                    body = response.read(); status = response.status
            except urllib.error.HTTPError as response:
                with response:
                    body = response.read(); status = response.code
            try:
                self.send_response(status); self.send_header('Content-Length', str(len(body))); self.end_headers()
                self.wfile.write(body)
            except OSError: pass
    forward = ThreadingHTTPServer(('127.0.0.1', 0), Forward)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (origin, forward)]
    for thread in threads: thread.start()
    try: yield f'http://127.0.0.1:{origin.server_port}', forward.server_port, seen
    finally:
        for server in (forward, origin): server.shutdown(); server.server_close()
        for thread in threads: thread.join()

class CurlTests(unittest.TestCase):
    def test_real_curl_requires_status_and_chatgpt_trace_not_captive_html(self):
        import engine
        self.assertTrue(hasattr(engine, '_sample'))
        with network_fixture() as (url, port, seen), tempfile.TemporaryDirectory() as tmp:
            for suffix, expected, validator in [('/trace', True, 'chatgpt-trace'), ('/html', False, 'chatgpt-trace'), ('/blocked', False, 'none')]:
                sample = engine._sample(port, engine.validate_site({'url': url + suffix, 'validator': validator}), 3, threading.Event(), Path(tmp))
                self.assertEqual(sample['ok'], expected, sample)
                self.assertIsInstance(sample['total_ms'], float)
                self.assertGreater(sample['ttfb_ms'], 0)
            self.assertEqual(len(seen), 3, 'curl must really use the explicit forward proxy')

import os

class BenchmarkTests(unittest.TestCase):
    def test_real_mihomo_report_keeps_failed_rows_and_recommends_only_complete_success(self):
        import engine
        self.assertTrue(hasattr(engine, 'benchmark'))
        binary = os.environ.get('MIHOMO_TEST_BINARY')
        if not binary: self.skipTest('Set MIHOMO_TEST_BINARY to run real-core integration')
        with network_fixture() as (url, port, seen), tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'main.json'
            original = {'proxies': [{'name': 'JP real', 'type': 'http', 'server': '127.0.0.1', 'port': port, 'password': 'NO_REPORT_SECRET'}, {'name': 'SG refused', 'type': 'http', 'server': '127.0.0.1', 'port': 1}]}
            path.write_text(json.dumps(original)); before = path.read_bytes()
            connection = engine.discover({'config_path': str(path), 'binary_path': binary, 'core_dir': tmp, 'interface': ''})
            events = []
            report = engine.benchmark(connection, [{'id': 'trace', 'url': url + '/trace', 'validator': 'chatgpt-trace'}, {'id': 'blocked', 'url': url + '/blocked'}], {'rounds': 2, 'workers': 2, 'timeout': 2}, lambda kind, **data: events.append((kind, data)), threading.Event())
            self.assertEqual(len(report['rows']), 4)
            good = [r for r in report['rows'] if r['name'] == 'JP real' and r['site_id'] == 'trace'][0]
            self.assertEqual(good['successes'], 2, good)
            self.assertEqual(good['success_rate'], 1)
            self.assertGreater(good['median_ms'], 0)
            self.assertEqual([r['name'] for r in report['recommendations']], ['JP real'])
            self.assertTrue(all(len(r['samples']) == 2 for r in report['rows']))
            self.assertEqual(events[0], ('start', {'total': 4}))
            self.assertEqual([d['completed'] for k, d in events if k == 'row'], [1, 2, 3, 4])
            self.assertNotIn('NO_REPORT_SECRET', json.dumps(report)); self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(seen), 4)
            self.assertIn('不是', report['note'])

class CancellationTests(unittest.TestCase):
    def test_cancelled_job_does_not_discover_config_or_start_children(self):
        import engine
        stop = threading.Event(); stop.set()
        with self.assertRaisesRegex(RuntimeError, '取消'):
            engine.benchmark({'config_path': 'does-not-exist'}, [{'url': 'http://localhost/'}], {}, lambda *a, **k: None, stop)

class ProviderNormalizationTests(unittest.TestCase):
    def test_provider_renames_and_filters_match_mihomo_semantics(self):
        import engine
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'main.json'
            path.write_text(json.dumps({'proxy-providers': {'p': {'type': 'inline', 'payload': [{'name': 'JP-2x', 'type': 'http', 'server': 'localhost', 'port': 1}, {'name': 'SG-3x', 'type': 'http', 'server': 'localhost', 'port': 1}, {'name': 'JP expired', 'type': 'http', 'server': 'localhost', 'port': 1}], 'filter': '^JP', 'exclude-filter': 'expired', 'override': {'proxy-name': [{'pattern': '-(\\d+)x', 'target': ' fast $1'}], 'additional-prefix': '[p] '}}}}))
            cat = engine.catalog({'config_path': str(path), 'core_dir': tmp, 'interface': '', 'controller': ''})
            self.assertEqual([n['name'] for n in cat['nodes']], ['[p] JP fast 2'])

class ControllerSecurityTests(unittest.TestCase):
    def test_controller_redirect_cannot_forward_secret_to_other_origin(self):
        import engine
        with controller_fixture() as (target, calls):
            class Redirect(BaseHTTPRequestHandler):
                def log_message(self, *args): pass
                def do_GET(self):
                    self.send_response(302); self.send_header('Location', target + '/version'); self.end_headers()
            server = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                with self.assertRaises(RuntimeError):
                    engine._api({'controller': f'http://127.0.0.1:{server.server_port}'}, {'secret': 'PRIVATE'}, '/version')
                self.assertEqual(calls, [])
            finally: server.shutdown(); server.server_close(); thread.join()

class MacDiscoveryTests(unittest.TestCase):
    def test_running_mac_process_paths_with_spaces_override_guessed_paths(self):
        import engine
        from unittest.mock import patch
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            binary = base / 'Clash Verge.app/Contents/MacOS/verge-mihomo'; binary.parent.mkdir(parents=True); binary.write_text('fixture executable')
            core_dir = base / 'Application Support/main core'; core_dir.mkdir(parents=True)
            config = core_dir / 'clash-verge.yaml'; config.write_text('external-controller: 0.0.0.0:9090\n')
            listing = f'{binary} -d {core_dir} -f {config}'
            def run(args, **kwargs): return SimpleNamespace(stdout=listing if args[0] == '/bin/ps' else 'PrimaryInterface : en0')
            with patch.object(engine.sys, 'platform', 'darwin'), patch.object(engine.subprocess, 'run', run), patch.object(engine.os, 'getuid', lambda: 501, create=True):
                connection = engine.discover({})
            self.assertEqual(connection['binary_path'], str(binary.resolve()))
            self.assertEqual(connection['core_dir'], str(core_dir.resolve()))
            self.assertEqual(connection['controller'], 'http://127.0.0.1:9090')
            self.assertEqual(connection['interface'], 'en0')

class ProviderCacheTests(unittest.TestCase):
    def test_http_provider_default_md5_cache_path_uses_actual_core_directory(self):
        import engine, hashlib
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); (base / 'proxies').mkdir()
            url = 'https://not-downloaded.invalid/subscription?token=SECRET'
            cache = base / 'proxies' / hashlib.md5(url.encode()).hexdigest()
            cache.write_text('proxies:\n- {name: JP cached default, type: http, server: localhost, port: 1}\n')
            config = base / 'config.json'; config.write_text(json.dumps({'proxy-providers': {'automatic': {'type': 'http', 'url': url}}}))
            cat = engine.catalog({'config_path': str(config), 'core_dir': tmp, 'controller': '', 'interface': ''})
            self.assertEqual([n['name'] for n in cat['nodes']], ['JP cached default'])
            self.assertNotIn('SECRET', json.dumps(cat))

class ProviderPrecedenceTests(unittest.TestCase):
    def inventory(self, base, settings, cached, runtime_names):
        import engine
        from unittest.mock import patch
        path = base / 'main.json'
        path.write_text(json.dumps({'proxy-providers': {'p': settings}}), encoding='utf-8')
        if cached is not None:
            (base / 'cached.yaml').write_text(json.dumps({'proxies': cached}), encoding='utf-8')
        responses = {'/version': {}, '/proxies': {}, '/providers/proxies': {
            'providers': {'p': {'proxies': [{'name': name} for name in runtime_names]}}}}
        connection = {'config_path': str(path), 'core_dir': str(base), 'controller': '', 'interface': ''}
        before = path.read_bytes()
        with patch.object(engine, '_api', side_effect=lambda conn, cfg, endpoint: responses[endpoint]) as api:
            result = engine._inventory(connection)
        self.assertEqual([call.args[2] for call in api.call_args_list], list(responses))
        self.assertEqual(path.read_bytes(), before)
        return result

    def test_file_and_http_use_cache_with_filters_and_overrides_before_fallback(self):
        import engine
        fallback = {'name': 'SG fallback only', 'type': 'http', 'server': 'localhost', 'port': 1}
        cached = [dict(fallback, name='JP live cache', port=2), dict(fallback, name='SG filtered')]
        for provider_type in ('file', 'http'):
            with self.subTest(provider_type=provider_type), tempfile.TemporaryDirectory() as tmp:
                settings = {'type': provider_type, 'path': 'cached.yaml', 'payload': [fallback],
                            'url': 'https://never-downloaded.invalid/', 'filter': '^JP',
                            'override': {'additional-prefix': '[p] ', 'udp': False}}
                cat, proxies, cfg = self.inventory(Path(tmp), settings, cached, ['[p] JP live cache'])
                self.assertEqual([n['name'] for n in cat['nodes']], ['[p] JP live cache'])
                selected = engine.filter_nodes(cat, {'provider': 'p'})
                conf = engine._isolated_config({'core_dir': tmp}, selected, proxies, cfg,
                                               {'[p] JP live cache': 10001})
                self.assertEqual(conf['proxies'][0]['port'], 2)
                self.assertIs(conf['proxies'][0]['udp'], False)

    def test_inline_uses_payload_even_when_cache_exists(self):
        proxy = {'name': 'SG inline', 'type': 'http', 'server': 'localhost', 'port': 1}
        with tempfile.TemporaryDirectory() as tmp:
            cat, proxies, _ = self.inventory(Path(tmp), {'type': 'inline', 'path': 'cached.yaml',
                                                         'payload': [proxy]},
                                              [dict(proxy, name='JP unused cache', port=2)], ['SG inline'])
            self.assertEqual(list(proxies), ['SG inline'])
            self.assertEqual([n['name'] for n in cat['nodes']], ['SG inline'])

    def test_cache_runtime_mismatch_and_empty_membership_skip_uncertain_nodes(self):
        proxy = {'name': 'JP stale cache', 'type': 'http', 'server': 'localhost', 'port': 1}
        for runtime_names in (['SG runtime only'], []):
            with self.subTest(runtime_names=runtime_names), tempfile.TemporaryDirectory() as tmp:
                cat, proxies, _ = self.inventory(Path(tmp), {'type': 'file', 'path': 'cached.yaml'},
                                                  [proxy], runtime_names)
                self.assertEqual(cat['nodes'], [])
                self.assertEqual(proxies, {})
                self.assertTrue(any('p' in w and '跳过' in w and 'core_dir' in w
                                    for w in cat['warnings']), cat['warnings'])

    def test_missing_cache_fallback_requires_runtime_membership(self):
        import engine
        from unittest.mock import patch
        proxy = {'name': 'SG fallback only', 'type': 'http', 'server': 'localhost', 'port': 1}
        for provider_type in ('file', 'http'):
            for names in (['SG fallback only'], ['JP runtime only'], []):
                with self.subTest(provider_type=provider_type, names=names), tempfile.TemporaryDirectory() as tmp:
                    cat, proxies, _ = self.inventory(Path(tmp), {'type': provider_type, 'path': 'cached.yaml',
                                                                 'payload': [proxy]}, None, names)
                    expected = ['SG fallback only'] if names == ['SG fallback only'] else []
                    self.assertEqual(list(proxies), expected)
                    self.assertEqual([n['name'] for n in cat['nodes']], expected)
                    with patch.object(engine, '_api', side_effect=RuntimeError('fixture offline')):
                        offline = engine.catalog({'config_path': str(Path(tmp) / 'main.json'), 'core_dir': tmp})
                    self.assertEqual(offline['nodes'], [])
                    self.assertTrue(any('p' in w and '跳过' in w and '控制器' in w
                                        for w in offline['warnings']), offline['warnings'])

    def test_offline_catalog_keeps_cached_nodes_before_fallback(self):
        import engine
        from unittest.mock import patch
        proxy = {'name': 'SG fallback only', 'type': 'http', 'server': 'localhost', 'port': 1}
        with tempfile.TemporaryDirectory() as tmp:
            self.inventory(Path(tmp), {'type': 'file', 'path': 'cached.yaml', 'payload': [proxy]},
                           [dict(proxy, name='JP live cache', port=2)], ['JP live cache'])
            with patch.object(engine, '_api', side_effect=RuntimeError('fixture offline')):
                cat = engine.catalog({'config_path': str(Path(tmp) / 'main.json'), 'core_dir': tmp})
            self.assertEqual([n['name'] for n in cat['nodes']], ['JP live cache'])

    def test_real_mihomo_settled_file_provider_uses_live_cache_in_probe(self):
        import engine, socket, subprocess
        binary = os.environ.get('MIHOMO_TEST_BINARY')
        if not binary:
            self.skipTest('Set MIHOMO_TEST_BINARY to run real-core integration')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with socket.socket() as stream:
                stream.bind(('127.0.0.1', 0))
                port = stream.getsockname()[1]
            fallback = {'name': 'SG fallback only', 'type': 'http', 'server': '127.0.0.1', 'port': 1}
            (base / 'cached.yaml').write_text(json.dumps({'proxies': [dict(fallback, name='JP live cache', port=2)]}), encoding='utf-8')
            cfg = {'external-controller': f'127.0.0.1:{port}', 'log-level': 'error',
                   'proxy-providers': {'p': {'type': 'file', 'path': 'cached.yaml', 'payload': [fallback],
                                             'health-check': {'enable': False}}},
                   'proxy-groups': [{'name': 'Root', 'type': 'select', 'use': ['p']}], 'rules': ['MATCH,REJECT']}
            path = base / 'main.json'
            path.write_text(json.dumps(cfg), encoding='utf-8')
            before = {p.name: p.read_bytes() for p in (path, base / 'cached.yaml')}
            connection = {'config_path': str(path), 'core_dir': tmp, 'binary_path': binary,
                          'controller': f'http://127.0.0.1:{port}', 'interface': ''}
            with (base / 'core.log').open('w', encoding='utf-8') as log:
                core = subprocess.Popen([binary, '-d', tmp, '-f', str(path)], stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 10
                    while True:
                        try:
                            members = engine._api(connection, cfg, '/providers/proxies')['providers']['p']['proxies']
                            if [p['name'] for p in members] == ['JP live cache']:
                                break
                        except (OSError, KeyError):
                            pass
                        self.assertIsNone(core.poll(), '真实核心必须保持运行')
                        self.assertLess(time.monotonic(), deadline, '等待 provider 缓存初始化超时')
                        time.sleep(.05)
                    selection = engine._api(connection, cfg, '/proxies')['proxies']['Root']['now']
                    cat, proxies, original = engine._inventory(connection)
                    self.assertEqual([n['name'] for n in cat['nodes']], ['JP live cache'])
                    conf = engine._isolated_config(connection, cat['nodes'], proxies, original, {'JP live cache': 10001})
                    self.assertEqual(conf['proxies'][0]['port'], 2)
                    self.assertEqual(engine.catalog(connection)['nodes'], cat['nodes'])
                    self.assertEqual(engine._api(connection, cfg, '/proxies')['proxies']['Root']['now'], selection)
                    self.assertEqual({p.name: p.read_bytes() for p in (path, base / 'cached.yaml')}, before)
                finally:
                    engine._terminate(core)

class InlineKeyTests(unittest.TestCase):
    def test_wireguard_base64_private_key_is_not_treated_as_file(self):
        import engine
        key = 'A' * 43 + '='
        proxies = {'JP wireguard': ({'name': 'JP wireguard', 'type': 'wireguard', 'private-key': key, 'server': 'localhost', 'port': 1}, '')}
        conf = engine._isolated_config({'core_dir': '.', 'interface': 'en0'}, [{'name': 'JP wireguard'}], proxies, {}, {'JP wireguard': 12345})
        self.assertEqual(conf['proxies'][0]['private-key'], key)

class LiveCancellationTests(unittest.TestCase):
    def test_active_curl_cancellation_terminates_child_and_closes_pipes(self):
        import engine
        from unittest.mock import patch
        with network_fixture() as (url, port, seen), tempfile.TemporaryDirectory() as tmp:
            stop = threading.Event(); children = []; real = engine.subprocess.Popen
            def popen(*args, **kwargs):
                child = real(*args, **kwargs); children.append(child); return child
            timer = threading.Timer(.25, stop.set); timer.start()
            started = time.monotonic()
            try:
                with patch.object(engine.subprocess, 'Popen', popen):
                    sample = engine._sample(port, engine.validate_site({'url': url + '/slow'}), 10, stop, Path(tmp))
            finally: timer.cancel(); timer.join()
            self.assertFalse(sample['ok']); self.assertIn('取消', sample['reason'])
            self.assertLess(time.monotonic() - started, 1.5)
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll())
            self.assertTrue(children[0].stdout.closed)
            self.assertTrue(children[0].stderr.closed)
            self.assertEqual(list(Path(tmp).iterdir()), [])

class MetadataTests(unittest.TestCase):
    def test_subscription_metadata_and_builtin_outbounds_are_not_candidates(self):
        import engine
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps({'proxies': [{'name': n, 'type': t, 'server': 'localhost', 'port': 1} for n, t in [('剩余流量: 20 GB', 'http'), ('套餐到期: 2027-01-01', 'http'), ('Traffic remaining 20GB', 'http'), ('JP bypass', 'direct'), ('SG real', 'http')]]}))
            cat = engine.catalog({'config_path': str(path), 'core_dir': tmp, 'interface': '', 'controller': ''})
            self.assertEqual([n['name'] for n in engine.filter_nodes(cat, {'regions': []})], ['SG real'])

class LiveCoreCancellationTests(unittest.TestCase):
    def test_real_core_cancel_stops_all_processes_and_removes_private_temp_config(self):
        import engine
        from unittest.mock import patch
        binary = os.environ.get('MIHOMO_TEST_BINARY')
        if not binary: self.skipTest('Set MIHOMO_TEST_BINARY to run real-core integration')
        with network_fixture() as (url, port, seen), tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'main.json'; path.write_text(json.dumps({'proxies': [{'name': 'JP real', 'type': 'http', 'server': '127.0.0.1', 'port': port}]}))
            conn = engine.discover({'config_path': str(path), 'binary_path': binary, 'core_dir': tmp, 'interface': ''})
            stop = threading.Event(); children = []; timers = []; real = engine.subprocess.Popen
            def popen(args, **kwargs):
                child = real(args, **kwargs); children.append((args, child))
                if '--write-out' in args:
                    timer = threading.Timer(.25, stop.set); timers.append(timer); timer.start()
                return child
            try:
                with patch.object(engine.subprocess, 'Popen', popen):
                    report = engine.benchmark(conn, [{'url': url + '/slow'}], {'rounds': 3, 'timeout': 10}, lambda *a, **k: None, stop)
            finally:
                for timer in timers: timer.cancel(); timer.join()
            self.assertEqual(report['recommendations'], [])
            self.assertTrue(any('取消' in w for w in report['warnings']))
            self.assertTrue(all(child.poll() is not None for args, child in children))
            self.assertTrue(any('--write-out' in args for args, child in children))
            core_args = [args for args, child in children if '-f' in args]
            self.assertTrue(core_args)
            self.assertTrue(all(not Path(args[args.index('-f') + 1]).exists() for args in core_args))

class BindRaceTests(unittest.TestCase):
    def test_real_core_retries_instead_of_accepting_foreign_listener(self):
        import engine, socket
        from unittest.mock import patch
        binary = os.environ.get('MIHOMO_TEST_BINARY')
        if not binary: self.skipTest('Set MIHOMO_TEST_BINARY to run real-core integration')
        with tempfile.TemporaryDirectory() as tmp, socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0)); occupied.listen(); port = occupied.getsockname()[1]
            real = engine._reserve_ports; reservations = []
            def reserve(names):
                result = {names[0]: port} if not reservations else real(names)
                reservations.append(result); return result
            conn = {'binary_path': binary, 'core_dir': tmp, 'interface': ''}
            proxies = {'JP node': ({'name': 'JP node', 'type': 'http', 'server': '127.0.0.1', 'port': 1}, '')}
            with patch.object(engine, '_reserve_ports', reserve):
                core, log, ports = engine._launch_core(conn, [{'name': 'JP node'}], proxies, {}, Path(tmp), threading.Event(), lambda *a, **k: None)
            try:
                self.assertNotEqual(ports['JP node'], port, 'A foreign process must never be mistaken for our isolated listener')
                self.assertEqual(len(reservations), 2)
            finally: engine._terminate(core); log.close()

class MalformedOptionTests(unittest.TestCase):
    def test_unhashable_region_value_returns_user_facing_validation_error(self):
        import engine
        for regions in [[{}], [[]]]:
            with self.subTest(regions=regions), self.assertRaises(ValueError):
                engine.validate_options({'regions': regions})

class SelfDiscoveryTests(unittest.TestCase):
    def test_mac_discovery_does_not_mistake_active_probe_for_main_core(self):
        import engine
        from unittest.mock import patch
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); binary = base / 'verge-mihomo'; binary.write_text('fixture')
            probe = base / 'clash-site-probe-active'; probe.mkdir(); (probe / 'config.json').write_text('{}')
            main = base / 'main'; main.mkdir(); (main / 'config.yaml').write_text('{}')
            listing = f'{binary} -d {probe} -f {probe / "config.json"}\n{binary} -d {main} -f {main / "config.yaml"}'
            def run(args, **kwargs): return SimpleNamespace(stdout=listing if args[0] == '/bin/ps' else 'PrimaryInterface : en0')
            with patch.object(engine.sys, 'platform', 'darwin'), patch.object(engine.subprocess, 'run', run), patch.object(engine.os, 'getuid', lambda: 501, create=True):
                connection = engine.discover({})
            self.assertEqual(connection['config_path'], str((main / 'config.yaml').resolve()))

if __name__ == '__main__':
    unittest.main()
