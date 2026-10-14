# NodeScope · 节点探针

NodeScope 是一款 Clash/Mihomo 节点测速工具，支持 Windows 和 macOS。
按目标网站、地区和节点范围，通过真实 HTTP 请求比较访问成功率、
首字节延迟与波动，帮助你选出访问各网站更快、更稳定的节点，并导出测速报告。

## 启动

Windows：双击 **NodeScope-Setup.exe**，按中文向导安装。默认安装到
当前用户的 LocalAppData/Programs/NodeScope，无需管理员权限。
安装后从开始菜单打开 NodeScope，也可在安装时选择创建桌面快捷方式。
可在 Windows“已安装的应用”中卸载；卸载保留本机设置和测速报告。
覆盖安装会更新已有程序。当前 EXE 尚无代码签名证书。

便携 ZIP 仍可使用：解压完整的 NodeScope-Windows-x64.zip，双击 NodeScope.exe，
保留旁边的 data、engine 和 DLL。两种发行方式均不需要安装 Python、Node 或 Flutter。

macOS：使用与 CPU 架构匹配的 macOS ZIP，解压后打开 NodeScope.app。
当前构建为 ad-hoc 签名，尚未做 Apple Developer 签名与公证。

点击“导入节点”，粘贴自己的 Clash/Mihomo 订阅 URL，或选择 YAML / JSON 配置文件。
导入后预览节点、选择网站与地区，再开始测速。安装包自带固定版本 Mihomo，
无需预先安装或打开代理客户端。应用不提供预置订阅。

配置引用其他 HTTP 节点来源时，界面先列出来源，勾选允许获取后再导入。
订阅目前直连获取；链接不可达时可导入已下载的配置文件。
本版本支持 YAML / JSON，暂不支持 URI / Base64 订阅。
“刷新节点”会重新获取当前订阅或读取当前文件；重新打开应用使用上次的本机快照。

已有 Clash Verge Rev 用户仍可在连接设置中自动发现客户端，读取生效配置与缓存。
自动发现失败时，手动选择内核、生效配置及其工作目录。

## 功能

- ChatGPT、GitHub、Google、YouTube、Wikipedia，以及自定义 HTTP/HTTPS 地址。
- 默认日本、新加坡；支持香港、韩国、台湾、美国和其他地区。
- 策略组、provider 来源、高级名称筛选、节点上限、手动选择。
- 留空名称筛选不限制节点，手动选择为空使用全部匹配节点。
- 成功率、首字节中位数、波动、逐轮明细；失败节点仍保留。
- 点击首字节表头排序；只有全部轮次成功的节点进入推荐。
- 取消不覆盖上次完整报告；导出 CSV / JSON。

界面沿用 prototypes/ui/index.html 的配色和组件。宽窗口下顶部入口固定，
左侧筛选与右侧结果各自滚动，测试参数和开始 / 停止按钮固定在左侧底部；
滚动长结果不会带走左侧设置。
窄窗口按上下顺序排列，并使用整体滚动。

## 引擎和安全边界

Flutter 通过私有 stdin/stdout 管道启动随包提供的 Python 引擎，
不会打开外部浏览器或新增本地 Web 服务。
订阅和文件在本机解析，只提取节点、节点来源、策略组及必要 TLS 设置，
主配置中的规则、TUN、控制器和脚本不带入测速内核。
节点快照和带令牌的来源设置只保存到用户私有数据目录，不写入测速报告。
远程订阅不能引用本机证书或本机文件；下载限制为总共 32 MiB、最多 20 个来源。
客户端模式仍只读取生效配置及缓存，不更新客户端订阅、不修改主配置、
不切换主节点、不关闭主客户端。Windows 支持只读 named pipe 控制接口。

地区来自节点名称，不是 IP 地理定位。ChatGPT 默认测试 trace 端点，
不测模型生成速度、不验证账号业务、不读取浏览器或 Codex 凭据。
Windows 使用系统 curl；macOS 使用本机 curl；订阅和文件模式使用自带 Mihomo v1.19.32。
客户端模式保留用户现有内核的行为。
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
    # Windows 另生成单文件安装器：
    python scripts/build_installer.py

Windows 未开启开发者模式时，可在 flutter pub get 更新依赖后运行
scripts/prepare_windows_links.ps1 创建项目内插件目录联接，
该脚本会再次执行 pub get 完成插件注册，再使用 --no-pub 编译；
使用 -Flutter 参数指定 SDK 路径。脚本不更改系统开发者模式。

scripts/download_test_core.py 下载固定官方内核并校验摘要，供测试与发行包共用。
tests/packaged_engine.py 在打包的引擎进程中验证真实 Mihomo、
两个本地网站、成功/失败行、各站独立推荐、URL / 文件独立测速、导出、取消与 EOF 清理。
这些服务是隔离测试夹具，不是公网节点测速成绩。

Windows 安装器使用 Inno Setup 6.7.3。build_installer.py 从官方固定版本下载
并核对 SHA-256，以便携模式放在项目 .tools/ 下，不修改系统 PATH 或安装全局编译器。
tests/windows_installer.py 在全新测试目录验证完整文件、开始菜单、覆盖安装、
已安装引擎真实请求、卸载和用户数据保留；如果检测到已有安装，会停止以避免覆盖。
安装包脚本位于 packaging/windows/NodeScope.iss，CI 同时上传 Setup.exe 和便携 ZIP。

Git 流程：独立功能分支先通过 Windows / macOS 构建和测试，然后创建 PR，
再次核对该提交的检查结果，最后合入 master。工作流见 .github/workflows/desktop.yml。
默认构建 Windows、Apple Silicon macOS 和 Intel macOS 三个平台。
推送 v* 标签或在 GitHub 发布该版本 Release 时，所有平台通过后自动附加安装器、
三个 ZIP 和 SHA256SUMS.txt 到 Release。
scripts/prepare_release.py 会拒绝缺少任一平台附件的发布。

## 授权

界面基于 ESTHER不二（esthersjw）的 esther-design-system，
其改编遵循 **CC BY-NC-SA 4.0**。第三方依赖和再分发说明见
THIRD_PARTY_NOTICES.md。未将该界面重新标为 MIT。
