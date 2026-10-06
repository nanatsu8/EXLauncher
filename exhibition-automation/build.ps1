cd $PSScriptRoot

$pyinstaller = ".\.venv\Scripts\pyinstaller.exe"

if (!(Test-Path $pyinstaller)) {
	Write-Host "エラー: pyinstaller が見つかりません: $pyinstaller"
	exit 1
}

Write-Host "以前の build/dist を削除します..."
if (Test-Path ".\build") { Remove-Item -Recurse -Force ".\build" }
if (Test-Path ".\dist") { Remove-Item -Recurse -Force ".\dist" }

$targets = @(
	"build_works_from_csv.py",
	"copy_drive_master_to_staging.py",
	"apply_update.py",
	"copy_works_to_drive.py",
	"update_manifest.py"
)

foreach ($target in $targets) {
	Write-Host "ビルド中: $target"
	& $pyinstaller --clean --noconfirm --onefile $target
	if ($LASTEXITCODE -ne 0) {
		Write-Host "ビルド失敗: $target"
		exit $LASTEXITCODE
	}
}

Write-Host "実行用EXEをスクリプト直下へ反映します..."
foreach ($target in $targets) {
	$exeName = [System.IO.Path]::GetFileNameWithoutExtension($target) + ".exe"
	$builtExe = Join-Path ".\dist" $exeName
	$runtimeExe = Join-Path "." $exeName
	Copy-Item -LiteralPath $builtExe -Destination $runtimeExe -Force
}

Write-Host "すべてのビルドと実行用EXEの更新が完了しました。出力先: .\dist およびスクリプト直下"
