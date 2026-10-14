"""生成一次性本地 HTTPS 夹具；私钥仅位于测试临时目录。"""
from pathlib import Path
import shutil
import subprocess


def certificate(folder):
    executable = shutil.which('openssl')
    if not executable:
        git = shutil.which('git')
        candidate = Path(git).parents[1] / 'usr/bin/openssl.exe' if git else None
        if candidate and candidate.is_file():
            executable = str(candidate)
    if not executable:
        raise RuntimeError('HTTPS 夹具需要系统或 Git 自带的 OpenSSL。')
    config, cert, key = (folder / name for name in ('openssl.cnf', 'cert.pem', 'key.pem'))
    config.write_text('\n'.join([
        '[req]', 'distinguished_name=dn', 'x509_extensions=ext', 'prompt=no', 'default_md=sha256',
        '[dn]', 'CN=localhost', '[ext]', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
        'basicConstraints=critical,CA:TRUE',
        'subjectKeyIdentifier=hash', 'authorityKeyIdentifier=keyid:always',
        'keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign',
        'extendedKeyUsage=serverAuth',
    ]), encoding='ascii')
    subprocess.run([executable, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                    '-config', str(config), '-keyout', str(key), '-out', str(cert)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=True)
    return cert, key
