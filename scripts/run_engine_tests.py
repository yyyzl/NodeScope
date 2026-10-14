"""按测试文件执行完整回归，每个后台测试进程严格限制为 60 秒。"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = sorted((ROOT / 'tests').glob('test_*.py'))
    if not files:
        raise RuntimeError('没有找到引擎回归测试。')
    for path in files:
        subprocess.run([sys.executable, '-W', 'error::ResourceWarning', '-m', 'unittest',
                        'discover', '-s', 'tests', '-p', path.name, '-v'],
                       cwd=ROOT, timeout=60, check=True)


if __name__ == '__main__':
    main()
