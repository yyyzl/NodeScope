# NodeScope 桌面模块设计

## 设计目标

在 Windows / macOS 原生 Flutter 窗口中复用现有测速引擎，保持已确认的 HTML
界面、网站范围选择和真实结果。首版交付便携程序，暂不增加托盘、安装器和自动换节点。

## 架构

Flutter ProbePage → ProbeController → EngineBridge → desktop_host.py → server.App → engine.py。
通信为私有进程 stdin/stdout 的 JSON 行，请求携带递增 ID。引擎单独打包，前端无需
Python 开发环境。核心读取和测速仍由原实现完成，避免重写统计与 provider 逻辑。

## 关键决策

- 界面使用真实 Flutter 控件，承接 prototypes/ui 的布局、配色及状态。
- 主窗口使用整体滚动，配置与结果不设固定高度。排序通过表头触发。
- 模态窗口可滚动，以容纳完整路径、网站列表、节点清单和逐轮明细。
- 控制器只调用后端命令；成功结果、推荐和取消语义以引擎返回为准。
- 保存成功才替换网站和连接设置；保存失败保留草稿和上次配置。
- 关闭窗口先停止轮询，再关闭引擎 stdin、等待取消和清理，最后销毁窗口。
- Windows 后端使用 Job Object 管理本应用的子进程，不纳入用户主客户端。
- macOS 采用 App Store 之外的发行方式，允许读取用户选择的外部 Clash 配置及启动内核。

## 依赖

Flutter 3.47.7；window_manager、file_selector；Python、PyYAML、PyInstaller。
运行包复用用户 Mihomo 和系统 curl，捆绑 Python 与 Windows 可再分发运行库。

## 已知限制

macOS 构建需 GitHub macOS runner 或带 Xcode 的 Mac。当前只做 ad-hoc 签名，
尚无 Apple Developer 公证。地区按节点名识别，trace 验证不是模型生成速度。
正常退出与取消验证不代表断电时一定能移除私有目录中的临时文件。

## 验证

Flutter analyze、controller/widget 测试、已有 Python 回归、
打包后真实 Mihomo 本地 HTTP 集成，以及 Windows 实际窗口运行验证。
GitHub Actions 分别编译 Windows 与 macOS，分支检查通过后才提交和合并 PR。

## 变更历史

2026-10-14：从已确认 HTML 原型实施原生桌面窗口和进程桥接，保留现有引擎。
