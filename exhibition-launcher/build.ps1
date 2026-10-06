Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot
npm run build
if ($LASTEXITCODE -ne 0) {
    throw "Electronランチャーのビルドに失敗しました。終了コード: $LASTEXITCODE"
}

$sourceDir = (Resolve-Path '.\dist\win-unpacked').Path
$targetDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'launcher-win'

if (Get-Process -Name 'KSWL-Exhibition-Launcher' -ErrorAction SilentlyContinue) {
    throw 'ランチャーが実行中です。終了してからもう一度 build.ps1 を実行してください。'
}

if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

Write-Host '配布用ランチャー本体を更新します...'
Get-ChildItem -LiteralPath $sourceDir -File |
    Copy-Item -Destination $targetDir -Force

$localesDir = Join-Path $targetDir 'locales'
New-Item -ItemType Directory -Path $localesDir -Force | Out-Null
Copy-Item -Path (Join-Path $sourceDir 'locales\*') -Destination $localesDir -Recurse -Force

$targetResourcesDir = Join-Path $targetDir 'resources'
New-Item -ItemType Directory -Path $targetResourcesDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceDir 'resources\app.asar') `
    -Destination (Join-Path $targetResourcesDir 'app.asar') -Force

foreach ($name in @('assets', 'renderer', 'templates')) {
    $destination = Join-Path $targetResourcesDir $name
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Copy-Item -Path (Join-Path $sourceDir "resources\$name\*") `
        -Destination $destination -Recurse -Force
}

Write-Host "更新完了: $targetDir"
Write-Host 'resources\works、resources\works_backup、resources\config.json5 は保持されています。'
