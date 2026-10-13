# Codex向け保守・引継ぎガイド

このファイルはリポジトリ全体に適用する。プロジェクトフォルダを別のWindows PCへコピーし、引継ぎ先で保守する運用を前提とする。
「現状」はコード・設定で確認できる実装、「変更時の指示」は保守で守る方針を示す。実装が変わった場合は関連する記述も更新する。

## 作業の基本方針

- 依頼に関係するソース・設定・テストを読んでから変更する。確認できない環境や仕様を推測で補わない。
- フォルダ内に `.github/copilot-instructions.md` があれば、その確認方針も読む。削除・移動、設定・依存関係、IPC、セキュリティ、テンプレート構造、コード実行等の確認対象を尊重する。ユーザーが明示した作業範囲・許可を優先し、既に許可された同じ操作を再確認しない。
- 同ファイルの関数長・ネスト等の条件は確認対象であり、既存コード全体で成立しているコーディング規約や一律の禁止事項とは扱わない。
- ソースの修正と、作品データの更新・配布先への反映を区別する。開発依頼だけを理由に本番更新やDriveへのコピーを実行しない。
- 作業結果には変更内容、実施した検証、未実施の検証と理由を記載する。過去のテスト成功記録を今回の結果として報告しない。

## 現在の運用（ユーザー確認済み）

- 提出されたCSV・作品・サムネイルをGoogle Drive for desktopのローカルミラーから読み込む運用は継続する。各展示PCで `build_works_from_csv` によりステージングを生成し、`apply_update` で本番へ反映する。
- 生成済みの `works` をDriveへコピーする運用と、Driveマスターからステージングへコピーする運用は行わない。`copy_works_to_drive.py` と `copy_drive_master_to_staging.py` は実装として残るが、通常手順として実行・案内しない。再利用は運用変更が明示された場合に扱う。
- 保守引継ぎのためのプロジェクトフォルダ全体のコピーは、上記の作品配布用コピーとは別の作業として扱う。

## 構成と編集先

現状はElectron製ランチャーとPython製の作品生成・配布ツールで構成される。JavaScriptはCommonJS、画面はHTML/CSSと直接のDOM操作を使用する。Python側は `Config`・`WorkData` のdataclass、`CSVDataClient`、`LauncherStructureGenerator` で設定・入力・生成を分けている。依存関係は各パッケージ定義を参照する。

| 対象 | 主な編集・確認先 |
| --- | --- |
| 設定読込、作品一覧、EXE起動、ウィンドウ、IPC、ログ | `exhibition-launcher/main.js` |
| 一覧画面のIPC公開 | `exhibition-launcher/preload.js` |
| 生成した作品紹介画面のIPC公開 | `exhibition-launcher/work-display-preload.js` |
| ローカルHTML配信、パス検証、MIME、Range | `exhibition-launcher/local-html-server.js` |
| 一覧画面の表示・操作・デザイン | `exhibition-launcher/renderer/` |
| 作品カード・作品紹介・メディア表示 | `exhibition-launcher/templates/` |
| CSV読込、作品分類、コピー、作品設定・マニフェスト生成 | `exhibition-automation/build_works_from_csv.py` |
| ステージング検証、本番反映、バックアップ・復旧 | `exhibition-automation/apply_update.py` |
| 手動編集後のマニフェスト更新 | `exhibition-automation/update_manifest.py` |
| 現在の運用では使用しない作品配布用コピー機能 | `exhibition-automation/copy_works_to_drive.py`、`copy_drive_master_to_staging.py` |
| 実行場所・設定パスの解決、CLIエラー表示 | `exhibition-automation/path_utils.py`、`cli_error.py` |
| 自動テスト・手動確認用作品 | `exhibition-launcher/test/`・`test-fixtures/`・`scripts/`、`exhibition-automation/tests/` |
| 依存関係・ビルド・配布 | `exhibition-launcher/package.json`・`package-lock.json`、`exhibition-automation/requirements.txt`、各 `build.ps1` |

変更時の指示:

- アプリ・ツールの修正はソースに行う。`launcher-win/` やビルド済みEXEの直接編集をソース修正の代わりにしない。
- 一覧画面と作品紹介画面ではHTML・CSSの編集先が異なる。テンプレートの置換キーと呼出側も確認する。
- 既存のCommonJS、命名、周辺の書式に合わせる。JavaScriptの関数・変数は主にcamelCase、Pythonはsnake_case、クラスはPascalCase。引用符や型注釈の書き方には混在があるため、無関係な一括整形をしない。

## コピー後の環境確認とデータ保護

現状:

- `.gitignore` は設定、素材、作品、配布物、`docs/`、`.github/` 等を除外している。Gitの追跡一覧だけでは引継ぎ対象を判断できない。
- `path_utils.py` はスクリプト／EXEの配置先が `C:/Users/<ユーザー名>/...` であることを要求する。`{user_name}` は実行ファイルの配置パスから抽出し、相対設定パスも実行ファイルの基準ディレクトリから解決する。任意のドライブ・配置先に対応しているとは扱わない。
- Google APIを呼び出す実装はなく、CSVとGoogle Drive for desktopのローカルミラーを読む。
- Electronは開発時にソース側、パッケージ時に `process.resourcesPath` 側の資源を読む。配布版の設定・作品は `launcher-win/resources/` にある。

変更時の指示:

1. コピー先の配置場所、Windows環境、Node.js/npm、Python、Driveミラーと各設定パスを確認する。コピー元のユーザー名やDriveパスを新しい固定値としてコードへ埋め込まない。
2. コピー済みの `node_modules/` や `.venv/` がそのまま使えるとは仮定しない。特に `.venv/pyvenv.cfg` はコピー元Pythonのパスを保持する。依存関係の定義を確認し、必要な環境再構築を判断する。
3. `exhibition-launcher/config.json5`、`exhibition-automation/config.json5`、配布版の `resources/config.json5` を区別する。CSV入力、Drive参照、ステージング、本番、バックアップの設定と実在する配置を確認する。
4. 設定、`assets/`、作品、`works_staging/`、`works_backup/`、運用資料、既存配布物を引継ぎデータとして扱う。Git管理外であることを削除理由にしない。生成物と一括して消さない。
5. 必要な管理外ファイルが欠けていれば明示する。作品や設定を仮の内容で置き換えて引継ぎ完了としない。

## 作品設定とIPCの互換性

現状:

- 作品単位は `works/<作品ID>/config.json5`。作品IDはフォルダ名で、生成側は番号と作品名から作る。
- `type` は `exe` または `html`。PDF・動画・画像の紹介画面も `html`。ローカルHTMLは `displayMode: "local-html"` と `htmlPath` を使い、表示判定には既存設定との互換処理もある。
- 主な共通キーは `title`、`description`、`priority`、`thumbnail`、`author`、`genre`、`credit`、`visible`。EXEは `executablePath`、メディアは `MoviePaths`・`ImagePaths`・`PdfPaths` を使う。
- ランチャーは `visible !== false` の作品を表示し、`priority` の昇順に並べる。生成側は表示指定と必要ファイルの準備状態からbooleanの `visible` を生成する。
- 生成側はパスを `/` 区切りに正規化する。説明・クレジットの改行は生成・表示間で変換する。
- IPCは `contextBridge` 経由。多くの処理は `{ success, data }` またはエラー情報を返すが、アプリ設定はオブジェクト、カードHTMLは文字列で返る。

変更時の指示:

- 設定キーの大文字小文字、値の型、作品フォルダ基準のパス、既存設定との互換性を保つ。変更時はPythonの生成側とElectronの読込・表示側を合わせて確認する。
- CSVの列は `column_mapping` の数値と読込処理で確認する。列名のコメントや運用資料だけを根拠にしない。
- IPC変更は `main.js`、各preload、renderer／テンプレートの呼出側を確認する。戻り値が全APIで統一されているとは仮定しない。
- 増分生成に関わるスキーマ情報・入力比較・HTMLソースのfingerprintを確認する。具体的な版番号をこのガイドの恒久ルールにしない。

## HTML作品と更新処理

現状:

- メイン画面と生成した作品紹介画面は `nodeIntegration: false`、`contextIsolation: true`、`webSecurity: false`。
- ローカルHTML作品はpreloadを持たず、sandbox・webSecurityを有効にし、作品ウィンドウごとのセッションで外部通信・外部遷移・別ウィンドウ・権限・ダウンロードを制限する。
- 静的サーバーは入口HTMLの親ディレクトリを配信ルートとし、`127.0.0.1` の一時ポートを使う。パス逸脱・リンク先を検証し、ウィンドウ終了・読込失敗・アプリ終了時に閉じる。
- `manifest.json` は自身を除くファイルについて、生成日時、ファイル数、相対パスとSHA-256を記録する。本番反映は検証後に旧作品を退避し、コピー後にも検証する。失敗時の復旧とファイル操作のリトライがある。`atomic_switch` は原子的なrenameではなくコピー・削除による切替。

変更時の指示:

- ウィンドウごとのセキュリティ設定を一律化しない。既存のIPC公開範囲、パス・ZIP検証、通信制限、サーバー終了処理を維持する。
- ZIP展開は既存の検証処理を使う。ローカルHTMLはサイト階層を保持し、メディア分類とは分ける。
- 紹介画面は `workDisplayHandlingMode` により既存 `work_display.html` を再利用することがある。テンプレート修正が表示へ反映されない場合は設定と生成ファイルを確認し、無断で削除しない。
- 本番・ステージング・バックアップ・コピー先の実パスを確認してから更新する。マニフェスト検証、バックアップ・復旧、リトライを理由なく省かない。
- 手動編集後のマニフェスト更新は対象ディレクトリを確認する。マニフェストの一致だけでUIやEXE起動の正常性を判断しない。

## エラーとログ

現状のIPCエラーは主に `main.js` の `createErrorResponse` で生成し、`success: false`、`errorCode`、`userMessage`、`recoveryHint`、`debugMessage` 等を返す。rendererは利用者向け説明・対処方法・コードを表示する。
Pythonは `cli_error.py` を使う処理と、`apply_update.py` 内の独自整形処理がある。全ツールで共通化済みとは扱わない。

- 変更時は該当処理の既存エラー形式に合わせ、呼出側・終了コード・フォールバックへの影響を確認する。利用者向け説明と開発者向け詳細を維持する。
- Electronの実際のログ初期化は `main.js`。`logger.js` だけを変更して反映したと判断しない。
- ログは `app.getPath('userData')/logs/` に出力し、ファイル名・レベル・最大サイズはアプリ設定で変更できる。未処理例外、メインのconsole、rendererの警告・エラーも記録する。
- Pythonは主に標準出力へ表示する。全ツール共通のファイルログがあるとは仮定しない。

## 検証・ビルド・配布

コマンドの定義元は `exhibition-launcher/package.json`、各 `build.ps1`、Pythonの引数定義。pytestの実行例は `PROJECT_SUMMARY.md` と `tests/` の構成に基づく。実行前に現在の定義を確認し、ユーザーから許可された作業範囲で使用する。

| 作業ディレクトリ | コマンド | 内容・書換対象 |
| --- | --- | --- |
| `exhibition-launcher/` | `npm test` | `node --test test/*.test.js`。一時ディレクトリとローカルサーバーを使用 |
| 同上 | `npm start` / `npm run dev` | Electron起動。生成する紹介画面は作品内へ書き込まれる場合がある |
| 同上 | `npm run fixture:install` / `npm run fixture:remove` | 開発用 `works/` に確認用作品を配置・削除。配布前に除去する |
| 同上 | `npm run build` / `npm run build:portable` | Windows向けビルド。既定はdir形式、出力先は `dist/` |
| 同上 | `.\build.ps1` | ビルドして `launcher-win/` の本体・表示資源を更新。既存の作品・バックアップ・配布版設定はコピー対象に含めない |
| `exhibition-automation/` | `python -m pytest tests -q` | pytest実行。使用するPythonと依存関係を確認する |
| 同上 | `.\build.ps1` | `.venv/Scripts/pyinstaller.exe` を使用。既存 `build/`・`dist/` を削除し、5ツールのEXEを `dist/` とスクリプト直下へ出力 |
| 同上 | `python apply_update.py --check` | ステージングの整合性検証のみ。本番反映はしない |

データを書き換える運用コマンド:

- `build_works_from_csv.py` は設定された出力先へ作品・設定・CSV・マニフェストを生成する。
- `apply_update.py` は引数なしで本番反映する。成功時にステージングを削除し、バックアップを更新する。
- `update_manifest.py --dir <対象>` は対象内のマニフェストを書き換える。未指定時は設定の `works_dir` を使う。
- 複数のCLIに終了時のEnter待ちがある。無人実行時の待ちを考慮する。

保守用の実装情報（現在の運用では使用しない）:

- `copy_drive_master_to_staging.py` は既存のステージングを削除して作り直す。
- `copy_works_to_drive.py` は **`--mirror` なしでも既存コピー先を削除してからコピーする**。名前から差分同期だけだと判断しない。
- `drive_master_dir` 等の関連設定と、ビルド対象に含まれるコピー用EXEが存在しても、現在の運用で使用する根拠にはしない。

検証範囲:

- Node.jsテストは静的配信、パス逸脱、MIME、Range、確認用作品を対象とする。PythonテストはDriveパス正規化、メディア分類、HTML配置、ZIP逸脱防止、設定・マニフェスト生成を対象とする。
- 変更に関係する既存テストを確認する。UI、EXE起動、本番切替全体の自動テストは確認できないため、その領域は必要な手動確認も記録する。
- 表示・起動の変更では、一覧・表示順・非表示、対象作品形式、関連ファイルの読込、ウィンドウを閉じた後の動作、エラー表示・ログを確認する。配布資源やパスに関わる変更は開発版と配布版の違いも確認する。
- ランチャーの配布更新は `exhibition-launcher/build.ps1` を参照する。Python修正はEXEを再ビルドするまで配布ツールに反映されない。実行中のランチャーや作品のファイルロックに注意する。

## 参照資料と未確認事項

- 概要: `PROJECT_SUMMARY.md`。利用・作品設定: `exhibition-launcher/README.md`。
- フォルダに存在する場合の運用資料: `docs/readme.md`、`docs/SLIDES.md`、`docs/図.md`、`docs/todo.md`。TODOは実装済み仕様として扱わない。
- 運用手順の変更は対応する配布資料にも反映する。`docs/readme.pdf` はガイドのPDF版、`docs/ランチャー説明会資料.pdf` はPowerPoint版の出力。Markdown・PowerPoint・PDF間に旧手順を残さない。
- 資料にはコードとの不一致がある。設定・コマンド・挙動は現在のコードを照合し、不一致を明示する。READMEの起動スクリプトは実在する `run-launcher.ps1` を確認する。
- Node.js・Pythonの正式な対応バージョンは定義を確認できない。コピー元の環境やロックファイルの現在の値だけで対応範囲を決めない。
- pytestはテストで使うが `requirements.txt` に含まれず、開発依存の導入手順は未定義。Lint・Formatter・型チェックの専用設定／コマンドも確認できない。架空のコマンドを書かない。
- DB／ORM、外部REST API、CIワークフローはリポジトリ内で確認できない。外部サービス・CIの有無は断定しない。
- 運用資料にあるフォーム送信時のGASはこのフォルダ内で確認できない。Drive同期・フォーム・シート側の処理を、フォルダコピーで引き継げると判断しない。
