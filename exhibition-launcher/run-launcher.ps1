Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# PowerShell の標準出力を UTF-8 に合わせて、日本語の文字化けを防ぐ
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
chcp 65001 | Out-Null

Set-Location $PSScriptRoot
npm start