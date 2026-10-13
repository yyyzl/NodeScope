import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:clash_site_probe/engine_bridge.dart';
import 'package:clash_site_probe/probe_controller.dart';
import 'package:clash_site_probe/probe_page.dart';
import 'package:clash_site_probe/ui_style.dart';

class FakeEngine implements EngineApi {
  bool failSave = false;
  bool stopped = false;
  List<String> commands = [];
  final settings = <String, dynamic>{
    'sites': [
      {
        'id': 'chatgpt',
        'name': 'ChatGPT',
        'url': 'https://chatgpt.com/cdn-cgi/trace',
        'statuses': [200],
        'validator': 'chatgpt-trace',
      },
      {
        'id': 'github',
        'name': 'GitHub',
        'url': 'https://github.com/',
        'statuses': [200],
        'validator': 'none',
      },
    ],
    'regions': [
      {'id': 'jp', 'name': '日本'},
      {'id': 'sg', 'name': '新加坡'},
    ],
    'options': {
      'regions': ['jp', 'sg'],
      'group': '',
      'provider': '',
      'include': '',
      'exclude': '',
      'limit': 0,
      'rounds': 3,
      'workers': 4,
      'timeout': 8,
      'node_names': [],
    },
    'connection': {
      'binary_path': '',
      'config_path': '',
      'core_dir': '',
      'controller': '',
      'named_pipe': '',
      'unix_socket': '',
      'interface': '',
    },
    'last_report': null,
    'warnings': <String>[],
  };
  @override
  Future<Json> call(String command, [Json payload = const {}]) async {
    commands.add(command);
    switch (command) {
      case 'bootstrap':
        return settings;
      case 'catalog':
        return {
          'connection': settings['connection'],
          'nodes': [],
          'groups': [],
          'providers': [],
          'warnings': [],
          'version': 'test',
        };
      case 'settings':
        if (failSave) throw StateError('保存失败');
        return payload;
      case 'start':
        stopped = false;
        return {'id': 'test', 'running': true};
      case 'stop':
        stopped = true;
        return {'stopping': true};
      case 'job':
        return {
          'running': !stopped,
          'events': [],
          'progress': {'completed': 0, 'total': 2},
          'report': null,
          'error': stopped ? '已取消' : null,
        };
      case 'preview':
        return {'nodes': [], 'count': 0, 'warnings': []};
    }
    throw StateError(command);
  }

  @override
  Future<void> close() async {}
}

void main() {
  test('启动后优先展示上次报告的网站', () async {
    final engine = FakeEngine();
    engine.settings['last_report'] = {
      'rows': [
        {
          'site_id': 'github',
          'name': '保存节点',
          'eligible': true,
          'median_ms': 10,
        },
      ],
      'recommendations': [],
    };
    final controller = ProbeController(engine);
    await controller.initialize();
    expect(controller.activeSite, 'github');
    expect(controller.rows.length, 1);
    controller.dispose();
  });
  test('快速连续点击不会启动重复任务', () async {
    final engine = FakeEngine();
    final controller = ProbeController(engine);
    await controller.initialize();
    await Future.wait([controller.start(), controller.start()]);
    expect(engine.commands.where((command) => command == 'start').length, 1);
    controller.dispose();
  });
  test('设置保存失败保留当前网站配置', () async {
    final engine = FakeEngine();
    final controller = ProbeController(engine);
    await controller.initialize();
    engine.failSave = true;
    final ok = await controller.save(newSites: []);
    expect(ok, false);
    expect(controller.sites.length, 2);
    expect(controller.error, '保存失败');
    controller.dispose();
  });
  test('取消保留上次完整报告', () async {
    final controller = ProbeController(FakeEngine());
    await controller.initialize();
    final previous = <String, dynamic>{
      'rows': [],
      'recommendations': [],
      'created_at': '2026-10-14T02:00:00Z',
    };
    controller.report = previous;
    await controller.start();
    await controller.stop();
    await controller.poll();
    expect(controller.running, false);
    expect(controller.cancelled, true);
    expect(identical(controller.report, previous), true);
    controller.dispose();
  });
  test('空网站选择不能启动测速', () async {
    final engine = FakeEngine();
    final controller = ProbeController(engine);
    await controller.initialize();
    controller.selectedSites.clear();
    await controller.start();
    expect(engine.commands.contains('start'), false);
    expect(controller.error, contains('至少选择'));
    controller.dispose();
  });
  test('排序不会改变引擎推荐且失败节点仍在末尾', () {
    final controller = ProbeController(FakeEngine());
    controller.report = {
      'rows': [
        {'name': '稳', 'site_id': 'chatgpt', 'eligible': true, 'median_ms': 90},
        {'name': '波动', 'site_id': 'chatgpt', 'eligible': true, 'median_ms': 80},
        {
          'name': '失败',
          'site_id': 'chatgpt',
          'eligible': false,
          'median_ms': 10,
        },
      ],
      'recommendations': [
        {'site_id': 'chatgpt', 'name': '稳'},
      ],
    };
    expect(controller.recommendation!['name'], '稳');
    controller.toggleSort('median_ms');
    expect(controller.rows.last['name'], '失败');
    expect(controller.recommendation!['name'], '稳');
    controller.dispose();
  });
  for (final size in [const Size(1280, 860), const Size(880, 640)]) {
    testWidgets('主界面在 $size 自然排版且没有虚构结果', (tester) async {
      await tester.binding.setSurfaceSize(size);
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final controller = ProbeController(FakeEngine());
      await controller.initialize();
      await tester.pumpWidget(
        MaterialApp(
          theme: probeTheme(),
          home: ProbePage(controller: controller),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('节点探针'), findsOneWidget);
      expect(find.text('开始测速'), findsOneWidget);
      expect(find.text('首字节从快到慢'), findsNothing);
      expect(find.textContaining('下方还有结果'), findsNothing);
      expect(find.text('本次推荐'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.tap(find.text('高级筛选'));
      await tester.pumpAndSettle();
      expect(find.text('名称包含'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      controller.dispose();
    });
  }
}
