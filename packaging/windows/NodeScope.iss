; 只安装本应用到当前用户目录；测速设置和报告位于独立的数据目录。
#ifndef AppVersion
  #error 必须通过 scripts/build_installer.py 指定版本和程序目录
#endif

[Setup]
AppId={{998697B5-563B-49EA-A210-C680D490DB28}
AppName=NodeScope
AppVersion={#AppVersion}
AppVerName=NodeScope {#AppVersion}
AppPublisher=yyyzl
AppPublisherURL=https://github.com/yyyzl/NodeScope
AppSupportURL=https://github.com/yyyzl/NodeScope/issues
AppUpdatesURL=https://github.com/yyyzl/NodeScope/releases
VersionInfoVersion={#AppVersion}.{#AppBuild}
DefaultDirName={localappdata}\Programs\NodeScope
DefaultGroupName=NodeScope
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableDirPage=no
DisableWelcomePage=no
DisableProgramGroupPage=yes
WizardStyle=modern
SetupIconFile=..\..\desktop\windows\runner\resources\app_icon.ico
UninstallDisplayIcon={app}\NodeScope.exe
OutputDir={#OutputDir}
OutputBaseFilename=NodeScope-Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.DesktopShortcut=创建桌面快捷方式
chinesesimplified.LaunchNodeScope=启动 NodeScope · 节点探针
chinesesimplified.UninstallNodeScope=卸载 NodeScope
english.DesktopShortcut=Create a desktop shortcut
english.LaunchNodeScope=Launch NodeScope
english.UninstallNodeScope=Uninstall NodeScope

[Messages]
chinesesimplified.ConfirmUninstall=确定卸载 %1 吗？%n%n本机设置和测速报告会保留。
english.ConfirmUninstall=Uninstall %1?%n%nYour settings and test reports will be kept.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\NodeScope\NodeScope"; Filename: "{app}\NodeScope.exe"; WorkingDir: "{app}"
Name: "{userprograms}\NodeScope\{cm:UninstallNodeScope}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\NodeScope"; Filename: "{app}\NodeScope.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\NodeScope.exe"; Description: "{cm:LaunchNodeScope}"; Flags: nowait postinstall skipifsilent
