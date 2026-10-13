"""打包 Flutter 窗口与原 Python 引擎，发布目录无需安装 Python。"""
import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--flutter',default='flutter')
args=parser.parse_args()
target='windows' if os.name=='nt' else 'macos'
subprocess.run([args.flutter,'build',target,'--release','--no-pub'],
    cwd=ROOT/'desktop',check=True)
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--onedir',
    '--console','--name','probe-engine','--hidden-import','engine',
    '--hidden-import','windows_support','--distpath',str(ROOT/'work/frozen'),
    '--workpath',str(ROOT/'work/pyinstaller'),'desktop_host.py'],
    cwd=ROOT,check=True)
if os.name=='nt':
    output=ROOT/'dist/NodeScope-Windows-x64'
    shutil.copytree(ROOT/'desktop/build/windows/x64/runner/Release',
        output,dirs_exist_ok=True)
    vswhere=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
    installation=subprocess.check_output([str(vswhere),'-latest','-products','*',
        '-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
        '-property','installationPath'],text=True).strip()
    crt=list((Path(installation)/'VC/Redist/MSVC').glob('*/x64/Microsoft.VC143.CRT'))
    if not crt:
        raise RuntimeError('未找到可再分发的 Visual C++ Runtime')
    for library in sorted(crt)[-1].glob('*.dll'):
        shutil.copy2(library,output/library.name)
    engine=output/'engine/probe-engine'
else:
    output=ROOT/('dist/NodeScope-macOS-'+platform.machine())
    output.mkdir(parents=True,exist_ok=True)
    candidates=list((ROOT/'desktop/build/macos/Build/Products/Release').glob('*.app'))
    assert len(candidates)==1,'未找到唯一 macOS 应用'
    app=output/'NodeScope.app'
    shutil.copytree(candidates[0],app,symlinks=True,dirs_exist_ok=True)
    engine=app/'Contents/Resources/engine/probe-engine'
shutil.copytree(ROOT/'work/frozen/probe-engine',engine,dirs_exist_ok=True)
for name in ('README.md','THIRD_PARTY_NOTICES.md'):
    shutil.copy2(ROOT/name,output/name)
archive=output.with_suffix('.zip')
if os.name=='nt':
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for entry in sorted(output.rglob('*')):
            if entry.is_file():
                bundle.write(entry,output.name+'/'+entry.relative_to(output).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
else:
    subprocess.run(['codesign','--force','--deep','--sign','-',
        '--entitlements',str(ROOT/'desktop/macos/Runner/Release.entitlements'),
        '--timestamp=none',str(app)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',
        str(output),str(archive)],check=True)
print('已生成 '+str(archive))
