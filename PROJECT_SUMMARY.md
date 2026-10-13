# 作品展示ランチャー — AI向けプロジェクト概要

## プロジェクトの目的

このリポジトリは、大学の部活動で制作されたゲーム、映像、画像、PDF、HTML作品を、展示会場のWindows PCで一覧表示・起動するためのシステムです。

システムは次の2要素で構成されています。

1. Electron製の作品展示ランチャー
2. Googleフォームの提出データとCSVをDriveミラーから読み込み、各展示PCで作品を生成・本番反映するPython自動化ツール

## 現在の運用

提出されたCSV・作品・サムネイルをGoogle Drive for desktopのローカルミラーから読み込む運用は継続します。各展示PCで `build_works_from_csv` によりステージングを生成し、`apply_update` で本番へ反映します。

生成済みの `works` をDriveへコピーする運用と、Driveマスターからステージングへコピーする運用は行いません。コピー用ツールの実装は残っていますが、現在の通常手順には含めません。保守引継ぎのためにプロジェクトフォルダ全体を別PCへコピーする作業は、作品配布用コピーとは別です。

## ディレクトリ構成

### `exhibition-launcher/`

Electron製ランチャーのソースコードです。

- `main.js`: Electronメインプロセス。設定・作品一覧の読み込み、EXE起動、作品表示ウィンドウとHTML生成を担当
- `preload.js`: Context Bridgeを使い、レンダラーへ限定的なIPC APIを公開
- `renderer/`: 作品一覧画面のHTML、JavaScript、CSS
- `templates/`: 作品カード、作品詳細、動画、画像、PDF用HTMLテンプレート
- `logger.js`: `electron-log` によるログ出力
- `config.json5`: アプリ名、作品ディレクトリ、最大化、ログなどの実行時設定
- `package.json`: npmスクリプトとElectron Builder設定
- `README.md`: ランチャーの利用・作品追加方法

作品は通常 `works/<作品ID>/config.json5` の単位で管理されます。ランチャーは `visible !== false` の作品だけを読み込み、`priority` の昇順で表示します。

### `exhibition-automation/`

作品データの生成・検証・反映を行うPythonツール群です。PyInstallerでWindows用EXEとして配布できます。

- `build_works_from_csv.py`: CSVとGoogle Driveのミラーファイルから `works_staging` を生成
- `apply_update.py`: ステージングの整合性を検証し、バックアップを作って本番 `works` に切り替え
- `update_manifest.py`: 手動編集後の `manifest.json` を再生成
- `copy_works_to_drive.py`: ローカルの `works` をDrive側へコピーする実装。現在の運用では使用しない
- `copy_drive_master_to_staging.py`: Drive上のマスターをステージングへコピーする実装。現在の運用では使用しない
- `path_utils.py`: `{user_name}` を含むWindowsパスの解決とDriveフォルダ名の表記ゆれ対応
- `cli_error.py`: CLI向けの共通エラー整形
- `config.json5`: CSV、Driveミラー、ステージング、本番、バックアップのパスと列マッピング
- `tests/`: パス正規化とPDF処理のpytestテスト
- `build.ps1`: 各PythonツールをPyInstallerでEXE化

### `launcher-win/`

Windows向けにビルド済みのランチャーです。`KSWL-Exhibition-Launcher.exe`、Electronランタイム、作品データ用の `resources/` が含まれます。

生成物・配布物として扱われ、Gitでは追跡されていないファイルが多くあります。

### `docs/`

展示担当者向けの運用資料です。

- `readme.md`: CSV準備から展示PCへの反映までを説明する詳細ガイド
- `readme.pdf`: `readme.md` から再出力するガイドのPDF版
- `SLIDES.md`、説明会資料: システム説明用資料。説明会PDFはPowerPoint版から再出力する
- `todo.md`: 検討事項・未完了事項

## 基本データフロー

```text
Googleフォームで作品を提出
    ↓
スプレッドシートを確認・補正
    ↓
CSVとしてGoogle Driveのミラー先へ保存
    ↓
build_works_from_csvを実行
    ↓
launcher-win/resources/works_stagingを生成
    ↓
ファイル一覧とSHA-256を記録したmanifest.jsonを生成
    ↓
apply_updateで整合性を検証
    ↓
既存worksをバックアップし、ステージングを本番へ切り替え
    ↓
Electronランチャーで作品を表示・起動
```

各展示PCが同じ提出データ・CSVをDriveミラーから読み込み、この生成・反映手順を実行します。生成済みの作品構造をDrive経由でほかのPCへ配布する手順は使用しません。

## 作品設定

作品ごとの `config.json5` では、主に次のフィールドを使用します。

- `title`: 作品名
- `description`: 説明
- `priority`: 表示順。小さい値ほど先に表示
- `type`: `exe` または `html`
- `thumbnail`: サムネイルへの相対パス
- `author`: 作者名
- `genre`: ジャンル
- `credit`: クレジット
- `visible`: ランチャーへの表示可否
- `executablePath`: EXE作品の実行ファイル
- `operation`: ゲームの操作方法
- `estimatedPlayTime`: 推定プレイ時間
- `MoviePaths`: 動画ファイルの配列
- `ImagePaths`: 画像ファイルの配列
- `PdfPaths`: PDFファイルの配列

## 対応ファイル

- ゲーム: `.exe`
- 動画: `.mp4`、`.mov`、`.avi`、`.mkv`
- 画像: `.jpg`、`.jpeg`、`.png`、`.gif`
- 文書: `.pdf`
- Web作品: `.html` と関連ファイル
- アーカイブ: 上記の作品を含む `.zip`

ZIPは自動的に展開され、作品タイプに応じてEXEやメディアファイルが探索・分類されます。

## ビルドと実行

### Electronランチャー

```powershell
cd exhibition-launcher
npm start
npm run build
```

主な技術要素はElectron 37、JavaScript、HTML、CSS、JSON5、`electron-log`、`electron-builder` です。

### Python自動化ツール

```powershell
cd exhibition-automation
python build_works_from_csv.py
python apply_update.py --check
python apply_update.py
python -m pytest tests -q
```

主な依存関係は `json5` とPyInstaller関連パッケージです。

## 整合性と更新方式

- `manifest.json` には対象ディレクトリ内のファイル数と各ファイルのSHA-256が保存されます。
- `apply_update.py` は本番切替前にマニフェストと実ファイルを照合します。
- 切替時は既存の本番データをバックアップします。
- Windowsの一時的なファイルロックを考慮し、削除やコピーにはリトライ処理があります。
- CSVビルドは設定により差分更新が可能です。
- 作品ファイルを手動編集した場合は `update_manifest.py` の再実行が必要です。

## 実装上の重要事項

- Windows専用の運用とパス構成を前提にしています。
- Google APIは使用せず、Google Drive for desktopのローカルミラーを読みます。
- 自動化ツールは通常 `C:/Users/{user_name}/...` 配下での実行を想定しています。
- Electronでは `nodeIntegration: false`、`contextIsolation: true` を使用しています。
- ローカル作品を表示する都合で、BrowserWindowの `webSecurity` は無効化されています。
- `work_display.html` は設定により既存ファイルを再利用するか、テンプレートから上書き生成します。
- ログは通常 `%APPDATA%/exhibition-launcher/logs/launcher.log` に保存されます。
- `launcher-win/`、ローカル設定、作品、ビルド成果物などにはGit管理外のファイルが含まれます。変更時は追跡対象か生成物かを確認してください。

## テスト状況

2026年8月16日の確認時点で、次のコマンドによるテストは6件すべて成功しています。

```powershell
python -m pytest exhibition-automation/tests -q
```

現在のテスト範囲は主に以下です。

- PDFファイルの分類と `PdfPaths` の生成
- 動画・画像の既存分類を壊さないこと
- Google Driveミラーフォルダの日本語・英語表記の正規化

Electron UI、EXE起動、ステージング切替全体の自動テストは確認できません。

## AIが変更するときの推奨確認順

1. `docs/readme.md` で実際の展示運用を確認する
2. `exhibition-automation/config.json5` でパスとCSV列マッピングを確認する
3. データ生成の変更は `build_works_from_csv.py` と対応テストを確認する
4. 表示や起動の変更は `main.js`、`preload.js`、`renderer/`、`templates/` を確認する
5. 生成物である `launcher-win/` を直接直すのではなく、原則としてソースを修正して再ビルドする
6. Python変更後はpytest、Electron変更後は開発起動とWindows向けビルドを確認する

## 関連ドキュメント

- `docs/readme.md`: 展示担当者向けの詳細運用ガイド
- `exhibition-launcher/README.md`: ランチャーの機能、設定、起動方法
- `docs/todo.md`: 残作業や検討事項

