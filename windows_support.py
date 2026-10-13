"""Windows 客户端发现与只读 named pipe HTTP；不修改 Clash 配置。"""
from __future__ import annotations
import ctypes
import http.client
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time


def hidden_process():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


_job_handle = None


def enable_child_cleanup():
    """临时 Job 仅包含本应用引擎和后续子进程，异常退出时由 Windows 回收。"""
    global _job_handle
    if os.name != 'nt' or _job_handle is not None:
        return
    from ctypes import wintypes
    class BasicLimits(ctypes.Structure):
        _fields_ = [('ProcessTime', ctypes.c_longlong), ('JobTime', ctypes.c_longlong),
                    ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSet', ctypes.c_size_t),
                    ('MaximumWorkingSet', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD),
                    ('SchedulingClass', wintypes.DWORD)]
    class IOCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ('ReadOperations', 'WriteOperations', 'OtherOperations',
                     'ReadBytes', 'WriteBytes', 'OtherBytes')]
    class ExtendedLimits(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IOCounters),
                    ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    api.CreateJobObjectW.restype = wintypes.HANDLE
    api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    api.GetCurrentProcess.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    job = api.CreateJobObjectW(None, None)
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x2000
    if job and api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        if api.AssignProcessToJobObject(job, api.GetCurrentProcess()):
            _job_handle = job
            return
    if job:
        api.CloseHandle(job)


def _powershell(script):
    executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    result = subprocess.run([str(executable), '-NoProfile', '-NonInteractive', '-Command',
                             '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; ' + script],
                            capture_output=True, encoding='utf-8-sig', timeout=8, **hidden_process())
    return json.loads(result.stdout or '[]')


def discover_windows():
    hints = {}
    try:
        processes = _powershell("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(verge-mihomo|mihomo|clash-verge)(-alpha)?\\.exe$' } | Select-Object Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress")
        if isinstance(processes, dict):
            processes = [processes]
        for proc in processes:
            command = proc.get('CommandLine') or ''
            if 'clash-site-probe-' in command:
                continue
            if 'mihomo' in proc.get('Name', '') and proc.get('ExecutablePath'):
                hints['binary_path'] = proc['ExecutablePath']
                for key, value in re.findall(r'(?:^|\s)-([df])\s+("[^"]+"|\S+)', command):
                    hints['core_dir' if key == 'd' else 'config_path'] = value.strip('"')
            elif proc.get('Name') == 'clash-verge.exe' and proc.get('ExecutablePath'):
                candidate = Path(proc['ExecutablePath']).parent / 'verge-mihomo.exe'
                if candidate.is_file():
                    hints.setdefault('binary_path', str(candidate))
        if hints.get('core_dir') and not hints.get('config_path'):
            folder = Path(hints['core_dir'])
            hints['config_path'] = str(next((p for p in [folder / 'clash-verge.yaml', folder / 'config.yaml'] if p.is_file()), folder / 'config.yaml'))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    # 服务进程可能不可读；此文件是 Verge 生成的生效配置，连接状态另由 API 验证。
    folder = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming')) / 'io.github.clash-verge-rev.clash-verge-rev'
    if (folder / 'clash-verge.yaml').is_file():
        hints.setdefault('config_path', str(folder / 'clash-verge.yaml'))
        hints.setdefault('core_dir', str(folder))
    return hints


def physical_interface():
    try:
        result = _powershell("$adapters = @(Get-NetAdapter -Physical | Where-Object Status -eq Up); $routes = @(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric); $choice = $null; foreach ($route in $routes) { $choice = $adapters | Where-Object InterfaceIndex -eq $route.InterfaceIndex | Select-Object -First 1; if ($choice) { break } }; if ($choice) { $choice.Name | ConvertTo-Json -Compress } else { 'null' }")
        return result if isinstance(result, str) else ''
    except (OSError, ValueError, subprocess.SubprocessError):
        return ''


def resolve_pipe(configured):
    """Verge 服务模式与 sidecar 共用用户后缀，仅尝试已存在的对应管道。"""
    if not configured or os.name != 'nt':
        return configured
    candidates = [configured]
    for prefix in ('verge-mihomo-sidecar-release-', 'verge-mihomo-sidecar-alpha-'):
        if prefix in configured:
            candidates.append(configured.replace(prefix, 'verge-mihomo-production-'))
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.WaitNamedPipeW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong]
    for candidate in candidates:
        if api.WaitNamedPipeW(candidate, 100) or ctypes.get_last_error() in (121, 231):
            return candidate
    return configured


class _PipeReader(io.RawIOBase):
    def __init__(self, api, handle):
        self.api, self.handle = api, handle
        self.deadline = time.monotonic() + 4

    def readable(self):
        return True

    def readinto(self, buffer):
        available = ctypes.c_ulong()
        while time.monotonic() < self.deadline:
            if not self.api.PeekNamedPipe(self.handle, None, 0, None, ctypes.byref(available), None):
                if ctypes.get_last_error() in (109, 232):
                    return 0
                raise OSError('本机控制管道读取失败')
            if available.value:
                size = min(len(buffer), available.value)
                chunk = ctypes.create_string_buffer(size)
                count = ctypes.c_ulong()
                if not self.api.ReadFile(self.handle, chunk, size, ctypes.byref(count), None):
                    raise OSError('本机控制管道读取失败')
                buffer[:count.value] = chunk.raw[:count.value]
                return count.value
            time.sleep(.01)
        raise TimeoutError('本机控制管道响应超时')


def pipe_api(pipe, endpoint, secret=''):
    if os.name != 'nt' or not pipe.startswith('\\\\.\\pipe\\') or any(ord(c) < 32 for c in pipe):
        raise ValueError('只允许本机 Windows named pipe')
    if endpoint not in ('/version', '/proxies', '/providers/proxies'):
        raise ValueError('仅允许读取内核版本和节点清单')
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    api.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    api.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
    api.WriteFile.argtypes = api.ReadFile.argtypes
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.WaitNamedPipeW(pipe, 1000)
    handle = api.CreateFileW(pipe, 0xC0000000, 0, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), '无法连接 Clash 本机控制管道；请确认客户端正在运行')
    try:
        if '\r' in secret or '\n' in secret:
            raise ValueError('控制器认证值无效')
        auth = ('Authorization: Bearer ' + secret + '\r\n') if secret else ''
        request = (f'GET {endpoint} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n{auth}\r\n').encode()
        count = ctypes.c_ulong()
        if not api.WriteFile(handle, request, len(request), ctypes.byref(count), None) or count.value != len(request):
            raise OSError('本机控制管道请求失败')
        reader = io.BufferedReader(_PipeReader(api, handle))
        class PipeSocket:
            def makefile(self, *args):
                return reader
        response = http.client.HTTPResponse(PipeSocket())
        try:
            response.begin()
            if response.status != 200:
                raise RuntimeError('本机控制管道返回错误；请确认配置与内核匹配')
            body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise RuntimeError('控制器响应过大')
            return json.loads(body)
        finally:
            response.close()
            reader.close()
    finally:
        api.CloseHandle(handle)
