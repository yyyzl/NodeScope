# NodeScope Flutter 桌面界面

该模块提供 Windows / macOS 原生窗口，复用根目录 Python 引擎。
入口为 lib/main.dart；界面、状态和进程通信分别在 probe_page.dart、
probe_controller.dart 和 engine_bridge.dart。各类设置与详情位于 probe_dialogs.dart。

## 开发

安装 Flutter 3.47.7 后，在此目录执行 flutter pub get、flutter analyze
和 flutter test --timeout 60s。发布包从根目录执行 scripts/build_bundle.py。
Windows 再执行 scripts/build_installer.py，生成可直接安装的 NodeScope-Setup.exe。
开发运行可传 --engine-python 和 --engine-script 明确指定已有 Python 与
desktop_host.py；发布程序自动使用随包引擎。

    flutter run -d windows -- --engine-python <python路径> --engine-script <desktop_host.py路径>

--data-dir 可用于隔离测试配置；默认使用用户私有应用数据目录。
主程序界面不包含模拟节点、预置测速成绩或生产凭据。
布局基准是根目录 prototypes/ui/index.html。更改前先对照已确认原型。

设计权衡、限制与验证见 DESIGN.md，第三方与界面许可见根目录说明。
