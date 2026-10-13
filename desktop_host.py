"""Flutter 子进程桥接：私有标准输入输出，不开放额外 HTTP 服务。"""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
from server import App


def dispatch(app, command, payload):
    if command == 'bootstrap':
        result = app.bootstrap()
        result.pop('csrf', None)
        return result
    if command in ('catalog', 'preview'):
        connection = app.normalize_connection(payload.get('connection', app.settings['connection']))
        catalog = app.engine.catalog(connection)
        if command == 'preview':
            nodes = app.engine.filter_nodes(catalog, payload.get('options', app.settings['options']))
            return {'nodes': nodes, 'count': len(nodes), 'warnings': catalog['warnings']}
        return catalog
    if command == 'settings':
        return app.save_settings(payload)
    if command == 'start':
        return app.start_job(payload)
    if command == 'job':
        return app.job_state()
    if command == 'stop':
        app.stop.set()
        return {'stopping': True}
    if command == 'export':
        if app.last_report is None:
            raise ValueError('尚无完整测速报告。')
        report = app.last_report
        if payload.get('include_failures', True) is False:
            report = dict(report, rows=[row for row in report['rows'] if row.get('eligible')])
        content = app.csv_report(report) if payload.get('format') == 'csv' else json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8')
        return {'content': base64.b64encode(content).decode('ascii')}
    raise ValueError('未知桌面操作')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir')
    args = parser.parse_args()
    default = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'Library/Application Support')) / 'ClashSiteProbe'
    data_dir = Path(args.data_dir) if args.data_dir else default
    data_dir.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        from windows_support import enable_child_cleanup
        enable_child_cleanup()
    # 继承当前用户 AppData 权限，不把带凭据的临时文件写到公共临时目录。
    (data_dir / 'temp').mkdir(exist_ok=True)
    tempfile.tempdir = str(data_dir / 'temp')
    app = App(data_dir)
    if sys.stdin is not None:
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    try:
        for line in sys.stdin:
            request_id = None
            try:
                if len(line) > 1024 * 1024:
                    raise ValueError('桌面请求过大')
                request = json.loads(line)
                request_id = request['id']
                if request['command'] == 'shutdown':
                    break
                result = dispatch(app, request['command'], request.get('payload') or {})
                response = {'id': request_id, 'result': result}
            except Exception as exc:
                message = str(exc) if isinstance(exc, (RuntimeError, ValueError)) else '本地引擎操作失败，请检查路径与客户端。'
                response = {'id': request_id, 'error': message}
            sys.stdout.write(json.dumps(response, ensure_ascii=False, allow_nan=False) + '\n')
            sys.stdout.flush()
    finally:
        app.stop.set()
        if app.worker:
            app.worker.join(timeout=8)


if __name__ == '__main__':
    main()
