# 仅创建项目生成目录的联接；无需更改 Windows 开发者模式。
$projectRoot = Split-Path $PSScriptRoot -Parent
$metadataPath = Join-Path $projectRoot 'desktop\.flutter-plugins-dependencies'
$metadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
$linkRoot = Join-Path $projectRoot 'desktop\windows\flutter\ephemeral\.plugin_symlinks'
New-Item -ItemType Directory -Path $linkRoot -Force | Out-Null
foreach ($plugin in $metadata.plugins.windows) {
    $pluginLink = Join-Path $linkRoot $plugin.name
    if (-not (Test-Path -LiteralPath $pluginLink)) {
        New-Item -ItemType Junction -Path $pluginLink -Target $plugin.path | Out-Null
    }
}
