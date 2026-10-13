import 'dart:async';

import 'package:flutter/foundation.dart';

import 'engine_bridge.dart';

typedef Json = Map<String, dynamic>;

/// 界面状态；筛选、统计、持久化与取消继续交给已验证的引擎。
class ProbeController extends ChangeNotifier {
  final EngineApi engine;
  ProbeController(this.engine);
  List<Json> sites = [];
  List<Json> regions = [];
  Json options = {};
  Json connection = {};
  Json? catalog;
  Json? report;
  List<Json> liveRows = [];
  Set<String> selectedSites = {'chatgpt'};
  String activeSite = 'chatgpt';
  String sortKey = 'median_ms';
  bool ascending = true;
  bool ready = false;
  bool busy = false;
  bool running = false;
  bool stopping = false;
  bool cancelled = false;
  bool _disposed = false;
  String error = '';
  List<String> warnings = [];
  String progressText = '';
  int completed = 0;
  int total = 0;
  int _lastSequence = 0;
  Timer? _pollTimer;

  List<Json> _objects(dynamic value) =>
      (value as List? ?? []).map((e) => Json.from(e as Map)).toList();

  Future<void> initialize() async {
    try {
      final data = await engine.call('bootstrap');
      if (_disposed) return;
      sites = _objects(data['sites']);
      regions = _objects(data['regions']);
      options = Json.from(data['options'] as Map);
      connection = Json.from(data['connection'] as Map);
      report = data['last_report'] is Map
          ? Json.from(data['last_report'])
          : null;
      warnings = List<String>.from(data['warnings'] as List? ?? []);
      if (!sites.any((s) => s['id'] == 'chatgpt')) {
        selectedSites = {sites.first['id'].toString()};
      }
      final previousRows = _objects(report?['rows']);
      activeSite = previousRows.isEmpty
          ? selectedSites.first
          : previousRows.first['site_id'].toString();
      ready = true;
      notifyListeners();
      await refreshCatalog();
    } catch (failure) {
      error = message(failure);
      if (!_disposed) notifyListeners();
    }
  }

  static String message(Object failure) => failure.toString().replaceFirst(
    RegExp(r'^(Bad state: |Exception: )'),
    '',
  );

  Json settings({
    List<Json>? newSites,
    Json? newOptions,
    Json? newConnection,
  }) => {
    'sites': newSites ?? sites,
    'options': newOptions ?? options,
    'connection': newConnection ?? connection,
  };

  Future<bool> save({
    List<Json>? newSites,
    Json? newOptions,
    Json? newConnection,
  }) async {
    try {
      final saved = await engine.call(
        'settings',
        settings(
          newSites: newSites,
          newOptions: newOptions,
          newConnection: newConnection,
        ),
      );
      sites = _objects(saved['sites']);
      options = Json.from(saved['options'] as Map);
      connection = Json.from(saved['connection'] as Map);
      selectedSites = selectedSites
          .where((id) => sites.any((s) => s['id'] == id))
          .toSet();
      if (selectedSites.isEmpty && sites.isNotEmpty) {
        selectedSites.add(sites.first['id'].toString());
      }
      if (!_disposed) notifyListeners();
      return true;
    } catch (failure) {
      error = message(failure);
      if (!_disposed) notifyListeners();
      return false;
    }
  }

  Future<void> refreshCatalog() async {
    if (_disposed || running || busy) return;
    busy = true;
    error = '';
    notifyListeners();
    try {
      catalog = await engine.call('catalog', {'connection': connection});
      connection = Json.from(catalog!['connection'] as Map);
      warnings = List<String>.from(catalog!['warnings'] as List? ?? []);
    } catch (failure) {
      error = message(failure);
    } finally {
      busy = false;
      if (!_disposed) notifyListeners();
    }
  }

  Future<Json?> preview({Json? draftOptions}) async {
    try {
      return await engine.call('preview', {
        'connection': connection,
        'options': draftOptions ?? options,
      });
    } catch (failure) {
      error = message(failure);
      if (!_disposed) notifyListeners();
      return null;
    }
  }

  Future<void> start() async {
    if (_disposed || running || busy) return;
    if (selectedSites.isEmpty) {
      error = '请至少选择一个测试网站。';
      notifyListeners();
      return;
    }
    busy = true;
    notifyListeners();
    try {
      if (!await save()) return;
      await engine.call('start', {
        'connection': connection,
        'options': options,
        'site_ids': selectedSites.toList(),
      });
      running = true;
      stopping = false;
      cancelled = false;
      error = '';
      liveRows = [];
      completed = 0;
      total = 0;
      _lastSequence = 0;
      progressText = '正在准备独立测速内核…';
      activeSite = selectedSites.first;
      if (!_disposed) {
        notifyListeners();
        _schedulePoll();
      }
    } catch (failure) {
      error = message(failure);
      if (!_disposed) notifyListeners();
    } finally {
      busy = false;
      if (!_disposed) notifyListeners();
    }
  }

  void _schedulePoll() {
    _pollTimer?.cancel();
    _pollTimer = Timer(const Duration(milliseconds: 250), poll);
  }

  Future<void> poll() async {
    if (_disposed || !running) return;
    try {
      final job = await engine.call('job');
      if (_disposed) return;
      final progress = Json.from(job['progress'] as Map);
      completed = (progress['completed'] as num).toInt();
      total = (progress['total'] as num).toInt();
      for (final event in _objects(job['events'])) {
        final sequence = (event['seq'] as num).toInt();
        if (sequence <= _lastSequence) continue;
        _lastSequence = sequence;
        if (event['event'] == 'row') {
          liveRows.add(Json.from(event['row'] as Map));
        } else if (event['text'] != null) {
          progressText = event['text'].toString();
        }
      }
      if (job['running'] == false) {
        running = false;
        cancelled = stopping;
        stopping = false;
        if (job['report'] is Map) {
          report = Json.from(job['report'] as Map);
          warnings = List<String>.from(report!['warnings'] as List? ?? []);
        } else if (!cancelled) {
          error = job['error']?.toString() ?? '测速未生成完整报告。';
        }
      }
      notifyListeners();
      if (running) _schedulePoll();
    } catch (failure) {
      running = false;
      stopping = false;
      error = message(failure);
      if (!_disposed) notifyListeners();
    }
  }

  Future<void> stop() async {
    if (!running || stopping) return;
    stopping = true;
    progressText = '正在停止请求并清理独立内核…';
    notifyListeners();
    try {
      await engine.call('stop');
    } catch (failure) {
      error = message(failure);
      if (!_disposed) notifyListeners();
    }
  }

  List<Json> get resultSites {
    final source = running ? liveRows : _objects(report?['rows']);
    final known = <String, Json>{};
    for (final row in source) {
      known[row['site_id'].toString()] = {
        'id': row['site_id'],
        'name': row['site_name'],
      };
    }
    if (running || known.isEmpty) {
      for (final site in sites.where((s) => selectedSites.contains(s['id']))) {
        known[site['id'].toString()] = site;
      }
    }
    return known.values.toList();
  }

  List<Json> get rows {
    final source = running ? liveRows : _objects(report?['rows']);
    final result = source.where((r) => r['site_id'] == activeSite).toList();
    result.sort((a, b) {
      final eligible = (a['eligible'] == true ? 0 : 1).compareTo(
        b['eligible'] == true ? 0 : 1,
      );
      if (eligible != 0) return eligible;
      final order = sortKey == 'name'
          ? a['name'].toString().compareTo(b['name'].toString())
          : ((a[sortKey] as num?) ?? double.infinity).compareTo(
              (b[sortKey] as num?) ?? double.infinity,
            );
      return ascending ? order : -order;
    });
    return result;
  }

  Json? get recommendation {
    if (running) return null;
    return _objects(report?['recommendations'])
        .where((r) => r['site_id'] == activeSite)
        .firstOrNull;
  }

  void toggleSort(String key) {
    ascending = sortKey == key ? !ascending : true;
    sortKey = key;
    notifyListeners();
  }

  void setOption(String key, dynamic value) {
    options = {...options, key: value};
    notifyListeners();
  }

  void toggleRegion(String id) {
    final selected = List<String>.from(options['regions'] as List);
    selected.contains(id) ? selected.remove(id) : selected.add(id);
    setOption('regions', selected);
  }

  void toggleSite(String id) {
    selectedSites.contains(id)
        ? selectedSites.remove(id)
        : selectedSites.add(id);
    notifyListeners();
  }

  void selectResultSite(String id) {
    activeSite = id;
    notifyListeners();
  }

  String regionName(String id) =>
      regions.where((r) => r['id'] == id).firstOrNull?['name']?.toString() ??
      id;

  @override
  void dispose() {
    _disposed = true;
    _pollTimer?.cancel();
    super.dispose();
  }
}
