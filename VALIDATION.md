# 交付验证记录

日期：2026-10-14。环境：Windows、本地 Python 虚拟环境、真实 Mihomo v1.19.32。此前 UI 验证使用 Chrome 无头浏览器；本次未修改 UI，未重跑浏览器测试。未在 Mac 实机测试，不提供公网 ChatGPT 或其他公网网站排名。

## 本次 provider 优先级修复与回归

仅修改 `engine._inventory` 的 provider 来源选择与运行时成员核对：

- `inline` 使用 payload；`file/http` 优先读取现有本地缓存，包括 HTTP provider 的默认 MD5 缓存路径，不下载订阅。
- 缓存缺失时，仅允许获得运行时成员确认的 fallback payload 节点；无法确认时跳过并提示检查控制器、`core_dir` 或在主客户端更新订阅。
- 本地节点经现有过滤、override 和重命名后，若无法与运行时成员核对则跳过并给出操作提示；已确认的空成员列表也不会纳入节点。
- 保留离线缓存清单、纯 inline 行为、缓存名称适配、override 和 provider 筛选，以及 `catalog` 自动发现的 `require_runtime=False` 语义。保留此前 `udp: False` 修复。

先增加 6 项回归，再修改实现：RED 为 `Ran 6 tests in 1.082s`、`FAILED (failures=12)`（包含子测试）；GREEN 为 `Ran 6 tests in 1.419s`、`OK`。真实核心回归先等待 `/providers/proxies` 确认 `JP live cache` 初始化完成，原实现仍错误选择 `SG fallback only`；修复后清单及临时探针配置均使用缓存 JP 节点及端口 2，夹具配置/缓存内容和核心选择不变。

回归还覆盖 file/http 缓存与 fallback 并存、过滤和 override、inline 忽略缓存、名称不匹配与空成员、缺失缓存的 fallback 确认，以及离线清单读取缓存。证据为 scratch 中的 `provider-regression-red.log` 与 `provider-regression-green.log`。

本次未增加功能或重设计，未提交或推送 Git，未读取用户凭据，未修改用户主核心配置或调用其变更接口。与原发布包比较，代码修改仅涉及 `engine.py`、`tests/test_engine.py`，另更新本验证记录。

## 此前 UDP 修复保留

已捕获的启动日志显示：6 个 mixed listener 的 UDP 绑定均出现 Windows 禁止访问端口错误。端口预留只涉及 TCP，测速也仅需要 HTTP/TCP。

- 先在原有隔离配置测试中断言每个 listener 的 `udp` 均显式为 `False`，执行 1 项测试，实际失败。
- 再仅为 `engine._isolated_config` 的 listener 增加 `udp: False`，同一项测试通过。
- 保留内核配置校验、监听器归属检查、端口冲突重试、失败行和取消检查；没有放宽测试。
- 未重设计界面或新增功能；未提交或推送 Git。仓库本地 `core.autocrlf` 已读取确认为 `false`；启动器源文件已确认为 LF。

回归证据位于下述 scratch 目录的 `udp-regression-red.log` 与 `udp-regression-green.log`。

## 执行命令与结果

在项目根目录执行以下 PowerShell 命令。临时测试文件和浏览器证据放在指定 scratch 目录；未安装额外依赖。

```powershell
$env:MIHOMO_TEST_BINARY = 'C:/Users/10455/AppData/Local/hermes/cache/scratch/clashsiteprobe/mihomo/mihomo-windows-amd64-compatible.exe'
$env:TEMP = 'C:/Users/10455/AppData/Local/hermes/cache/scratch/clashsiteprobe'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
.venv/Scripts/python.exe -W error::ResourceWarning -m unittest discover -s tests -v

.venv/Scripts/python.exe tests/integration_real.py --mihomo $env:MIHOMO_TEST_BINARY --scratch $env:TEMP
# 本次 provider 修复后完整执行一次；此前 UDP 修复后连续执行三次。

$env:CSP_PLAYWRIGHT_PATH = 'C:/Users/10455/AppData/Local/hermes/cache/scratch/csp-ui-test-deps/node_modules/playwright'
$env:CSP_SERVER_PYTHON = 'C:/Users/10455/ClashSiteProbe/.venv/Scripts/python.exe'
$env:CSP_UI_EVIDENCE = 'C:/Users/10455/AppData/Local/hermes/cache/scratch/clashsiteprobe/ui-evidence'
node static/tests.js

& 'F:/Git/bin/bash.exe' -n 启动.command
```

- 本次 Python：35/35 通过，无跳过；记录为 `Ran 35 tests in 16.185s`、`OK`，含新增真实核心 provider 回归及既有纯 inline、自动发现、UDP、取消和端口竞争检查。后台执行使用 `subprocess.run(timeout=60)` 限制最大时长，并启用 `-W error::ResourceWarning`。
- 本次整服务 `tests/integration_real.py`：退出码 0，真实核心版本 v1.19.32，结果见下表。
- 此前浏览器：11/11 通过，包括连接/预览/保存/开始/停止、网站管理、结果和失败行展示、桌面/手机布局，以及真实本地服务的会话、持久化与错误显示。UI 源文件与此前发布包逐字节一致，本次未重跑。
- 此前启动器：`bash -n` 退出码 0，仅证明 Bash 语法通过；本次源文件与此前发布包一致，并重新核对 ZIP 内 LF 与 Unix 0755。

## 真实内核集成

所有计时来自真实 curl → 独立 Mihomo → 本地转发代理 → 本地 HTTP 服务。每次均包含缓存 provider 节点；日本/新加坡默认预览为 3 个节点。

| 次数 | 退出码 | 节点 | 网站 | HTTP 请求 | 结果行 | 取消耗时 |
| --- | --- | --- | --- | --- | --- | --- |
| 此前 UDP 1 | 0 | 6 | 2 | 36 | 12 | 28 ms |
| 此前 UDP 2 | 0 | 6 | 2 | 36 | 12 | 11 ms |
| 此前 UDP 3 | 0 | 6 | 2 | 36 | 12 | 16 ms |
| 本次 provider 修复 | 0 | 6 | 2 | 36 | 12 | 21 ms |

上述各次均断言通过：

- `fixture-ok` 推荐“日本 A”，`fixture-204` 推荐“新加坡 B”，两站分别排名。
- 两个网站各保留一行“香港失败”，成功率均为 0。
- 主内核选择前后不变，缓存 provider 被加载，JSON/CSV 导出通过。
- 停止慢请求后任务结束，并保留上一份完整报告。

原始证据目录：`C:/Users/10455/AppData/Local/hermes/cache/scratch/clashsiteprobe`。本次为 `provider-unit-tests.log`、`provider-integration.log`、`provider-integration-result.json` 和上述 RED/GREEN 日志。此前的 `unit-tests.log`、`ui-tests.log`、三次集成日志/JSON 及 `ui-evidence/` 保留。这些本地证据不作为用户测速报告捆入发布包。

## 发布包检查

`ClashSiteProbe-mac.zip` 根目录为 `ClashSiteProbe/`，文件白名单如下：

```text
engine.py
server.py
README.md
VALIDATION.md
requirements.txt
preview.png
启动.command
static/index.html
static/tests.js
tests/integration_real.py
tests/test_discovery_fix.py
tests/test_engine.py
tests/test_server.py
```

本次按原白名单重建发布包，共 13 个文件，根目录为 `ClashSiteProbe/`。包内不含 `.git`、`.venv`、`__pycache__`、缓存、本地设置、测速报告、真实节点配置、凭据或 ZIP 自身。重新检查 `ZipFile.testzip()`、与原白名单相同的 manifest、逐文件内容比对、Python 源码语法、启动器 LF 换行及 Unix `external_attr` 的 `0755` 执行权限。现有 `preview.png` 为界面截图。检查记录保存于 scratch 的 `provider-zip-verification.json`。

## 验证边界

- Mac 双击启动、原生自动发现、物理网卡绑定和实际 Clash Verge Rev 共存行为仍需 Mac 实机验证；模拟 Mac 发现测试和 Windows 上的 Bash 语法检查不等于原生验收。
- 本地夹具证明当前代码通过真实 Mihomo 的网络路径和任务流程，不证明机场节点、公网网站或 ChatGPT 账号业务可用。
- 本次 provider 回归及整服务验证、此前 UDP 的三次集成通过覆盖了已复现问题；不能保证所有操作系统环境永远没有端口竞争。
