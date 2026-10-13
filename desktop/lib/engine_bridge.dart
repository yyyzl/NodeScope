import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// 私有子进程通信，不开放端口，不将凭据放入命令行。
abstract class EngineApi {
  Future<Map<String, dynamic>> call(
    String command, [
    Map<String, dynamic> payload = const {},
  ]);
  Future<void> close();
}

class EngineBridge implements EngineApi {
  final Process _process;
  final Map<int, Completer<Map<String, dynamic>>> _pending = {};
  late final StreamSubscription<String> _output;
  int _sequence = 0;
  bool _closed = false;

  EngineBridge._(this._process) {
    _output = _process.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen(_onMessage, onError: (_) => _failPending());
    // 内核错误可能带出配置数据，stderr 不转发给 UI 或日志。
    _process.stderr.drain<void>();
    _process.exitCode.then((_) => _failPending());
  }

  static Future<EngineBridge> launch(
    String dataDirectory, {
    String? developmentPython,
    String? developmentScript,
  }) async {
    final executable = File(Platform.resolvedExecutable);
    final bundled = Platform.isWindows
        ? '${executable.parent.path}/engine/probe-engine/probe-engine.exe'
        : '${executable.parent.parent.path}/Resources/engine/probe-engine/probe-engine';
    final binary = developmentPython ?? bundled;
    if (!await File(binary).exists()) {
      throw StateError('缺少随应用打包的测速引擎，请使用完整发布目录。');
    }
    final arguments = [?developmentScript, '--data-dir', dataDirectory];
    final bridge = EngineBridge._(await Process.start(binary, arguments));
    try {
      await bridge.call('bootstrap');
      return bridge;
    } catch (_) {
      await bridge.close();
      rethrow;
    }
  }

  void _onMessage(String line) {
    try {
      final message = jsonDecode(line) as Map<String, dynamic>;
      final completer = _pending.remove(message['id']);
      if (completer == null || completer.isCompleted) return;
      if (message['error'] != null) {
        completer.completeError(StateError(message['error'].toString()));
      } else {
        completer.complete(Map<String, dynamic>.from(message['result'] as Map));
      }
    } catch (_) {
      _failPending();
    }
  }

  void _failPending() {
    for (final completer in _pending.values) {
      if (!completer.isCompleted) {
        completer.completeError(StateError('本地测速引擎已退出，请重新打开应用。'));
      }
    }
    _pending.clear();
  }

  @override
  Future<Map<String, dynamic>> call(
    String command, [
    Map<String, dynamic> payload = const {},
  ]) async {
    if (_closed) throw StateError('测速引擎已关闭。');
    final id = ++_sequence;
    final completer = Completer<Map<String, dynamic>>();
    _pending[id] = completer;
    _process.stdin.writeln(
      jsonEncode({'id': id, 'command': command, 'payload': payload}),
    );
    try {
      return await completer.future.timeout(const Duration(seconds: 40));
    } on TimeoutException {
      throw StateError('本地引擎响应超时，请检查客户端是否正常运行。');
    } finally {
      _pending.remove(id);
    }
  }

  @override
  Future<void> close() async {
    if (_closed) return;
    _closed = true;
    _process.stdin.writeln(
      jsonEncode({'id': ++_sequence, 'command': 'shutdown'}),
    );
    await _process.stdin.close();
    try {
      await _process.exitCode.timeout(const Duration(seconds: 10));
    } on TimeoutException {
      _process.kill();
      await _process.exitCode;
    } finally {
      _failPending();
      await _output.cancel();
    }
  }
}
