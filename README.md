# NodeScope · 节点探针

一个 Flutter 原生桌面小应用，按目标网站、地区和节点范围比较 Clash/Mihomo
线路。支持 Windows 和 macOS，复用已有测速引擎，以每个网站的真实 HTTP
请求结果分别推荐节点。

## 启动

Windows：解压完整的 NodeScope-Windows-x64.zip，双击 NodeScope.exe。
请保留旁边的 data、engine 和 DLL，不需要安装 Python、Node 或 Flutter。

macOS：使用与 CPU 架构匹配的 macOS ZIP，解压后打开 NodeScope.app。
当前构建为 ad-hoc 签名，尚未做 Apple Developer 签名与公证。

先打开 Clash Verge Rev 并运行代理内核，再刷新节点、选择范围并开始测速。
自动发现失败时，在连接设置中选择内核、生效配置及其工作目录。
应用不包含订阅，不下载机场配置。

## 功能

- ChatGPT、GitHub、Google、YouTube、Wikipedia，以及自定义 HTTP/HTTPS 地址。
- 默认日本、新加坡；支持香港、韩国、台湾、美国和其他地区。
- 策略组、provider 来源、高级名称筛选、节点上限、手动选择。
- 留空名称筛选不限制节点，手动选择为空使用全部匹配节点。
- 成功率、首字节中位数、波动、逐轮明细；失败节点仍保留。
- 点击首字节表头排序；只有全部轮次成功的节点进入推荐。
- 取消不覆盖上次完整报告；导出 CSV / JSON。

界面以 prototypes/ui/index.html 的已确认原型为基准，左右栏自然展开，
只使用窗口整体滚动，避免固定高度把结果压成狭小区域。

## 引擎和安全边界

Flutter 通过私有 stdin/stdout 管道启动随包提供的 Python 引擎，
不会打开外部浏览器或新增本地 Web 服务。
引擎读取主客户端配置和已有缓存，启动独立临时 Mihomo，不修改主配置、
不切换主节点、不关闭主客户端。Windows 支持只读 named pipe 控制接口。

地区来自节点名称，不是 IP 地理定位。ChatGPT 默认测试 trace 端点，
不测模型生成速度、不验证账号业务、不读取浏览器或 Codex 凭据。
Windows 使用系统 curl；macOS 使用本机 curl；Mihomo 来自用户客户端。
普通退出、取消和窗口关闭会清理探针子进程。Windows Job Object 补充异常退出回收。
强制断电等中断可能留下用户私有数据目录中的临时文件。

数据目录：Windows 用户的 LocalAppData/NodeScope；
macOS 用户的 Library/Application Support/NodeScope。
设置和报告保存在本机。真实配置、节点凭据和用户测速报告禁止提交仓库。

## 开发和验证

源码位于 G:\project\ClashSiteProbe。Flutter 源码在 desktop/，
Python 引擎仍在项目根目录。当前使用 Flutter 3.47.7。

    python -m pip install -r requirements.txt pyinstaller
    cd desktop
    flutter pub get
    flutter analyze --no-pub
    flutter test --no-pub --timeout 60s
    cd ..
    python scripts/build_bundle.py

Windows 未开启开发者模式时，可在 flutter pub get 更新依赖后运行
scripts/prepare_windows_links.ps1 创建项目内插件目录联接，
该脚本会再次执行 pub get 完成插件注册，再使用 --no-pub 编译；
使用 -Flutter 参数指定 SDK 路径。脚本不更改系统开发者模式。

scripts/download_test_core.py 下载固定官方测试内核并校验摘要。
tests/packaged_engine.py 在打包的引擎进程中验证真实 Mihomo、
两个本地网站、成功/失败行、各站独立推荐、导出、取消与 EOF 清理。
这些服务是隔离测试夹具，不是公网节点测速成绩。

Git 流程：独立功能分支先通过 Windows / macOS 构建和测试，然后创建 PR，
再次核对该提交的检查结果，最后合入 master。工作流见 .github/workflows/desktop.yml。

## 授权

界面基于 ESTHER不二（esthersjw）的 esther-design-system，
其改编遵循 **CC BY-NC-SA 4.0**。第三方依赖和再分发说明见
THIRD_PARTY_NOTICES.md。未将该界面重新标为 MIT。
