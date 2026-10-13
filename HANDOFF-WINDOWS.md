# Windows 应用接手文档 — 节点探针 / ClashSiteProbe

## 0. 最重要的方向纠正

**用户真正要的是 Windows 应用，不是 Mac 应用。**

原始材料是 Mac 脚本，只是实现思路的参考。上一轮把来源平台误当成目标平台，交付了“Python 本地网页工具 + Mac 启动脚本”，与用户预期不符。不要继续完善 Mac 启动器，也不要把已有 `ClashSiteProbe-mac.zip` 当作最终交付。

用户要求本交接文档，由用户自己的 Codex 接手后续开发。本轮只交接，未实施 Windows 桌面化。

## 1. 开发在哪里

**完整、最新的项目源码：**

```text
C:\Users\10455\ClashSiteProbe
```

**本交接文档的固定位置：**

```text
C:\Users\10455\ClashSiteProbe\HANDOFF-WINDOWS.md
```

其他已有材料：

| 路径（相对项目根目录） | 用途 |
| --- | --- |
| `engine.py` | 节点读取、筛选、临时 Mihomo 内核、curl 请求、排名和取消 |
| `server.py` | Python 本地 HTTP 服务、设置、异步任务、报告导出 |
| `static/index.html` | 中文网页界面；不是 Windows 桌面窗口 |
| `requirements.txt` | 当前运行依赖，PyYAML；Python 标准库处理服务与任务 |
| `tests/test_engine.py` | 引擎测试，包括真实内核和 provider 回归 |
| `tests/test_server.py` | 本地服务与会话/CSRF/导出测试 |
| `tests/test_discovery_fix.py` | 空连接字段与自动发现回归 |
| `tests/integration_real.py` | 真实 Mihomo + 本地 HTTP/CONNECT 代理的整服务集成 |
| `static/tests.js` | Chromium UI 自动化测试，含测试专用夹具 |
| `README.md` | 当前使用说明，仍以 Mac 为目标；迁移时需改写 |
| `VALIDATION.md` | 上一版测试命令、结果、证据位置和验证边界 |
| `preview.png` | 现有界面的真实截图，空结果状态，没有虚构排名 |
| `启动.command` | Mac 启动器，Windows 交付中不适用 |
| `ClashSiteProbe-mac.zip` | 已验证的旧方向发布包，仅供参考，不是 Windows 应用 |
| `.venv\Scripts\python.exe` | 现有 Windows 开发虚拟环境，可直接复用做测试 |

Git 状态已实际检查：项目已初始化 Git，分支 `main`，**还没有任何提交或远程发布**。存在 staged 新文件、后续 unstaged 修改，以及未跟踪的 ZIP/验证文档。以磁盘上的当前文件为准；不要只读取暂存区，也不要执行 `reset --hard` 或清理未跟踪文件。

临时证据与测试内核位于：

```text
C:\Users\10455\AppData\Local\hermes\cache\scratch\clashsiteprobe
```

该目录可能被清理，不是源码主目录，也不是正式应用数据目录。旧发布包未包含虚拟环境、真实节点配置、用户凭据或本地测速报告。

## 2. 用户需求与验收方向

已经明确：

1. **目标平台：Windows。** 交付应是面向 Windows 用户的小应用，不是要求用户安装 Python、运行 Mac 脚本的方案。
2. **多站点**：不仅 ChatGPT，支持添加其他网站；可保存配置并针对不同网站分别测速、推荐。
3. **区域可自选**：默认日本、新加坡；至少支持香港、韩国、台湾等附近区域。
4. **范围可限定**：可指定节点范围，而不是只能测全部节点。
5. 编程实现和修复优先交给 **实际 Codex CLI**，不要用普通子代理冒充 Codex CLI。沟通使用中文，给用户实际文件和验证结果，不要长时间扩大开发范围。

需要下一位 Codex 尽早确认、而不是擅自假定：

- 用户 Windows 上实际使用的 Clash 客户端、版本及内核类型。原材料来自 Clash Verge Rev，不等于用户现在一定使用同一客户端。
- Windows 应用的窗口形态：原生界面或桌面 WebView。**可以提出复用当前网页界面的方案，但不能把“一个 EXE 打开外部浏览器”直接宣称符合用户预期。**
- 是否需要便携 EXE 或安装包、是否需要托盘。这些没有被用户明确要求；不要先扩展成大型桌面项目。

建议以“Windows 上双击启动、可见应用窗口、无需手动配置开发环境”为第一版验收目标。具体技术栈由下一位 Codex结合现有代码和用户确认决定；尚未选定桌面框架，也没有 `.exe` 或安装器。

## 3. 已完成、可复用的部分

当前不是空项目。可以保留引擎与测试，不必重写核心逻辑：

- 内置 ChatGPT、GitHub、Google、YouTube、Wikipedia 测试配置，支持新增普通 HTTP/HTTPS 网址和预期状态码。
- 日本/新加坡默认选中；香港、韩国、台湾、美国、其他地区可选。
- 策略组递归展开、provider 来源、名称包含/排除、手动节点、最多节点数等组合筛选。
- 读取主配置中的节点及既有 provider 缓存，不主动下载订阅。
- 独立临时 Mihomo，每个候选节点有固定 loopback listener；不切换主核心的当前节点。
- curl 实际请求；每站分别汇总成功率、TTFB 中位数和波动，保留失败行。
- 只从全部轮次成功的节点中推荐；不是对所有站点使用一个“最快节点”。
- 保存设置、完整报告和 JSON/CSV；取消不覆盖上一次完整报告。
- 本地 HTTP 服务有随机会话、CSRF、Host/Origin 校验；界面不插入未经转义的节点/网站 HTML。

详细现有行为见 `README.md` 和代码，不在这里复制整份设计说明。

**指标边界：** 地区来自节点名，不是 IP 地理定位。ChatGPT 默认检查 trace 端点，不测模型生成速度，不验证账号业务，也不读取 Codex/browser 登录凭据。控制器 secret 如存在，会从本地 Clash 配置读取用于本机 API，不应出现在 argv、日志或报告中。

## 4. Windows 迁移的实际缺口

不要把“在 Windows 跑过测试”理解为“Windows 应用已完成”。目前缺少：

### A. Windows 客户端发现与连接

`engine.discover()` 的进程扫描、候选路径、Unix socket 和物理网卡自动检测主要为 Mac 编写。Windows 只验证过**显式提供配置/内核/控制器路径**的测试场景，没有完成对用户安装客户端的自动发现。

下一步需：

- 从实际 Windows 客户端/服务的进程、配置或受支持接口发现二进制、实际生效配置和核心工作目录；不要猜路径后声称发现成功。
- 保留手动路径/文件选择作为可靠后备。
- 确认当前客户端控制接口是本机 TCP、named pipe 或其他方式，再实现相应适配。当前引擎支持本机 HTTP 与 Mac Unix socket，**没有 named pipe 适配**。
- provider 相对缓存路径以主核心实际工作目录（`-d`）为基准，不是应用目录。
- Windows 网络接口和主客户端 TUN 共存还需真实环境验证；未绑定物理接口时会警告，不保证请求完全不受其他 VPN/系统路由影响。

### B. 桌面窗口与生命周期

当前 `server.py` 启动后会打开外部浏览器，退出依赖终端。要改成符合用户预期的 Windows 应用启动/关闭流程。

若继续使用本地 Web UI，应保留 loopback/session 安全边界；主窗口关闭或任务取消必须清理临时内核与 curl，不影响用户主 Clash 进程。不要为了隐藏终端而丢失错误反馈。

### C. 发布与资源路径

- 目前没有 Windows EXE/安装包，也没有 Windows 启动器。
- 当前依赖外部 Python、PyYAML、curl、Mihomo。需要决定哪些随应用打包、哪些从用户客户端复用；检测缺失和版本能力，不能依赖开发机 PATH。
- 打包后 HTML、资源目录、可写数据目录与内核文件路径需明确；不要继续把开发时 `__file__` 路径当成所有打包场景都有效。
- 当前 Windows 默认数据目录是 `~/.clash-site-probe/`（见 `server.default_data_dir()`）；可以讨论迁移到用户级 AppData，但这不是已实现行为。
- 临时配置含节点凭据。Windows 应核实目录 ACL、清理和异常退出，不把 POSIX chmod 等同于 Windows 权限保护。
- 修改 README 和发布说明，去掉 Mac 为主要启动方式。最终交付名也不应继续带 `-mac`。

## 5. 不要退回去的修复

这些不是待办，当前磁盘源码中已经修复并验证：

1. **HTTP/TCP 探针 listener 显式 `udp: False`。** 原来只预留 TCP 端口，却由 mixed listener 启用 UDP；Windows 保留 UDP 范围造成间歇性启动失败。不能删掉这个字段或放宽内核就绪检查来“修复”失败。
2. **provider 按类型选择数据。** inline 用 payload；file/http 优先已有活动缓存。缺失缓存的 fallback 须运行时成员确认；无法匹配的节点跳过并告警，不能只警告后仍测速错误定义。
3. **浏览器空连接字段意味着自动发现。** 空字段不得覆盖配置里的控制器地址；catalog 先发现再读取 inventory。
4. **清单浏览与测速前置条件分开。** `catalog` 使用 `require_runtime=False`；真正 benchmark 仍检查运行条件。
5. **验证所有 listener 的归属和就绪。** 连接到端口不等于该端口属于新内核，保留 bounded bind-race 重试。
6. **取消主动结束子进程。** 不只设置线程标志；保留前一次完整报告。

补充：真实集成夹具的 HTTP 代理必须支持 CONNECT。Mihomo HTTP outbound 可以对 HTTP 目标使用 TCP tunnel；GET-only 测试代理会制造误导性的失败。

## 6. 验证基线与复跑方式

交接前最后一次实际执行：

- **35 项 Python 测试通过，无跳过**，包括真实 Mihomo provider、取消和端口竞争回归。
- **11 项 Chromium UI 测试此前通过**；最近 provider 修复未改 UI。本机也曾对真实服务验证默认地区、设置保存/readback、缺失配置错误和无虚构结果。
- 最终代码又通过一次整服务真实内核集成：6 个本地代理节点、2 个本地网站、36 次实际 HTTP 请求、12 行结果；各站推荐不同、保留失败、缓存 provider 加载、主选择不变、导出和取消通过。
- 旧 Mac ZIP 的完整性、源文件一致性和启动器权限已核验。这不代表 Windows 应用包已存在。

更完整的历史证据与命令见 `VALIDATION.md`，其中的 Mac/旧方向叙述不能当成 Windows 新版验收。

现有真实测试内核（仅测试使用，未放进发布包）：

```text
C:\Users\10455\AppData\Local\hermes\cache\scratch\clashsiteprobe\mihomo\mihomo-windows-amd64-compatible.exe
```

版本为测试时确认的 `v1.19.32`；官方 GitHub 资产摘要已核对。该路径可能随 scratch 清理消失；如需重新获取，核对官方来源、架构和摘要，不要假设它是当前最新版本。

PowerShell 中可复跑：

```powershell
$P = 'C:\Users\10455\ClashSiteProbe'
Set-Location $P
$env:MIHOMO_TEST_BINARY = 'C:\Users\10455\AppData\Local\hermes\cache\scratch\clashsiteprobe\mihomo\mihomo-windows-amd64-compatible.exe'
& "$P\.venv\Scripts\python.exe" -W error::ResourceWarning -m unittest discover -s tests -v
& "$P\.venv\Scripts\python.exe" tests/integration_real.py --mihomo $env:MIHOMO_TEST_BINARY --scratch 'C:\Users\10455\AppData\Local\hermes\cache\scratch\clashsiteprobe'
```

浏览器测试依赖的开发缓存：

```text
C:\Users\10455\AppData\Local\hermes\cache\scratch\csp-ui-test-deps\node_modules\playwright
```

UI 测试完整调用见 `static/tests.js` 和 `VALIDATION.md`。测试使用本地服务/夹具，**没有对用户真实机场、安装的 Clash 客户端和公网 ChatGPT 做最终验收**。

## 7. 下一位 Codex 的最短接手流程

1. 读本文件、`engine.discover()`、`server.main()`、README、VALIDATION，确认现有源码和用户 Windows 客户端；不要从 Mac ZIP 重新开始。
2. 在当前源码上复跑基线，保留结果；别把 skip 当成真实内核验收。
3. 和用户确认 Windows 应用窗口/发布形态，优先复用已完成引擎，控制第一版范围。
4. 先做一个可运行的 Windows 垂直切片：双击 → 应用窗口 → 连接实际客户端 → 按默认地区预览 → 单站真实测速 → 取消/退出干净。
5. 再保留多站点、自选附近区域、范围筛选、结果导出等现有功能，补自动化和真实客户端验收。
6. 验证 EXE/安装器在非开发环境运行，不要求用户预先安装 Python/Node；确认失败提示、TUN 场景、子进程清理和主核心不变。
7. 提供实际 Windows 文件与简短使用说明。明确仍未验证的条件，不用“已打包”代替“已运行”。

## 8. 授权与工具纪律

现有 UI 基于 ESTHER不二（esthersjw）的 esther-design-system 模板，页面和 README 保留 **CC BY-NC-SA 4.0** 署名及非商业/相同方式共享限制。不要直接把该界面重新标成 MIT 或用于未确认授权的商业发行；如要换授权，重新设计或取得许可。

Mihomo、curl 和桌面框架的捆绑授权需分别核对。不要上传用户节点配置/订阅/token；不要为了测速改主 Clash 配置、切换当前节点或关闭用户正在使用的内核。修改前读文件、复现问题、做最小修复并实测；用户已经因上一轮耗时和目标平台偏差不满，应避免不必要的扩展、重复研究与多代理往返。

建议有对应技能的环境加载 Codex CLI、测试驱动开发、系统性调试和代码审查技能；它们是工作方法参考，不应成为用户自己的 Codex 接手的前置依赖。
