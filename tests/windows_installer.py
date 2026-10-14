"""验证实际安装包的文件、入口、覆盖安装、已安装引擎和卸载数据保护。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import winreg
from tls_fixture import certificate

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{998697B5-563B-49EA-A210-C680D490DB28}_is1'


def registration():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY)
    except FileNotFoundError:
        return None
    with key:
        return {name: winreg.QueryValueEx(key, name)[0]
                for name in ('DisplayName', 'InstallLocation', 'UninstallString')}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    assert os.name == 'nt', '安装器测试仅适用于 Windows'
    shortcut = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/NodeScope/NodeScope.lnk'
    # 不覆盖用户已经安装的程序；仅在独立的测试目录安装。
    assert registration() is None, '已存在 NodeScope 安装，请在干净环境运行安装器测试'
    assert not shortcut.parent.exists(), '开始菜单已有 NodeScope 入口，停止测试以免覆盖'
    folder = ROOT / 'work' / f'installer-smoke-{uuid.uuid4().hex}'
    installed = folder / '安装程序 验证'
    folder.mkdir(parents=True)
    installer = ROOT / 'dist/NodeScope-Setup.exe'
    data = Path(os.environ['LOCALAPPDATA']) / 'NodeScope'
    data.mkdir(parents=True, exist_ok=True)
    marker = data / f'installer-test-{uuid.uuid4().hex}.json'
    marker.write_text('{"keep_settings_and_reports":true}', encoding='utf-8')
    marker_hash = digest(marker)
    try:
        command = [str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                   '/NORESTART', '/TASKS=', f'/DIR={installed}']
        subprocess.run(command + [f'/LOG={folder / "install.log"}'],
                       check=True, timeout=60)
        entry = registration()
        assert entry and entry['DisplayName'].startswith('NodeScope')
        assert Path(entry['InstallLocation']).resolve() == installed.resolve()
        assert shortcut.is_file()
        # 对比全部资源，而不只检查 EXE 存在，防止遗漏引擎或运行库。
        payload = ROOT / 'dist/NodeScope-Windows-x64'
        for source in payload.rglob('*'):
            if source.is_file():
                target = installed / source.relative_to(payload)
                assert target.is_file() and digest(source) == digest(target), str(target)
        assert (installed / 'unins000.exe').is_file()
        subprocess.run(command + [f'/LOG={folder / "upgrade.log"}'],
                       check=True, timeout=60)
        assert digest(marker) == marker_hash
        cert, key = certificate(folder)
        environment = dict(os.environ,
                           NODESCOPE_ENGINE_BINARY=str(installed / 'engine/probe-engine/probe-engine.exe'),
                           NODESCOPE_TEST_CERT=str(cert), NODESCOPE_TEST_KEY=str(key),
                           PATH=str(Path(os.environ['SystemRoot']) / 'System32'))
        # 从含中文和空格的安装路径运行，且不依赖开发机 PATH。
        subprocess.run([sys.executable, str(ROOT / 'tests/packaged_engine.py')],
                       env=environment, cwd=folder, check=True, timeout=60)
        subprocess.run([str(installed / 'unins000.exe'), '/VERYSILENT',
                        '/SUPPRESSMSGBOXES', '/NORESTART',
                        f'/LOG={folder / "uninstall.log"}'],
                       check=True, timeout=60)
        assert registration() is None
        assert not shortcut.exists()
        assert not (installed / 'NodeScope.exe').exists()
        assert not (installed / 'engine/probe-engine/probe-engine.exe').exists()
        assert digest(marker) == marker_hash
        (folder / 'result.json').write_text(json.dumps({
            'install': True, 'complete_payload': True, 'start_menu': True,
            'reinstall': True, 'installed_engine': True, 'uninstall': True,
            'settings_and_reports_preserved': True,
            'installer_sha256': digest(installer),
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Windows 安装、开始菜单、覆盖安装、真实引擎、卸载及数据保留验证通过')
    finally:
        uninstaller = installed / 'unins000.exe'
        entry = registration()
        if (entry and Path(entry['InstallLocation']).resolve() == installed.resolve()
                and uninstaller.is_file()):
            subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                            '/NORESTART'], check=True, timeout=60)
        # 只清理本次测试创建的唯一标记，不触碰已有设置和报告。
        marker.unlink(missing_ok=True)


if __name__ == '__main__':
    run()
