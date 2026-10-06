# 作品展示ランチャー

大学の部活動で制作した映像作品やゲームを展示するためのElectronアプリケーションです。

## 機能

- 作品ごとの設定ファイル（config.json5）に基づいた自動読み込み
- priority順での作品表示
- exe実行、HTML作品表示、PDF作品表示に対応
- 美しいUI/UX

## フォルダ構造

```
launcher_electron/
├── main.js              # メインプロセス
├── preload.js           # プリロードスクリプト
├── package.json         # npm設定
├── renderer/            # ランチャーUI
│   ├── index.html
│   ├── index.js
│   └── style.css
├── works/               # 作品フォルダ
│   ├── work1/          # ゲーム作品
│   │   ├── config.json5
│   │   ├── thumbnail.jpg
│   │   └── forced_scorolling_maze/
│   └── work2/          # 映像作品
│       ├── config.json5
│       ├── thumbnail.jpg
│       ├── index.html
│       └── work2.mp4
└── assets/            # ロゴ等の素材
```

## 設定ファイル（config.json5）の形式

**注意**: JSON5形式（コメント・末尾カンマ対応）を使用しています。

### ゲーム（exe）の場合
```json5
{
    "title": "Forced Scrolling Maze",
    "description": "強制スクロール型のパズルゲーム。\nプレイヤーは迷路を進みながらゴールを目指します。",
    "priority": 1,
    "type": "exe",
    "executablePath": "forced_scorolling_maze/Forced Scrolling Maze.exe",
    "thumbnail": "thumbnail.jpg",
    "author": "kk, mm",
    "genre": "アクションゲーム",
    "credit": "制作\nプログラム: kk\nデザイン: mm\n\nフォント\nM+ FONTS (c) M+ FONTS PROJECT\n\nサウンド\n魔王魂",
    "operation": "キーボード", // ゲームの場合のみ
    "estimatedPlayTime": "10分", // ゲームの場合のみ
}
```

### HTML作品の場合
```json5
{
    "title": "ローカルWeb作品",
    "description": "ローカルファイルだけで動作するWeb作品です。",
    "priority": 2,
    "type": "html",
    "displayMode": "local-html",
    "htmlPath": "work_file/site/index.html",
    "thumbnail": "thumbnail.jpg",
    "author": "aa",
    "genre": "Web",
    "credit": "",
    "visible": true,
}
```

HTML作品はカードの「サイトを開く」ボタンから専用ウィンドウで開きます。`127.0.0.1` の一時サーバーを使用しますが、外部には公開されません。作品から外部サイトや外部APIへの通信は許可されません。

### PDF作品の場合
```json5
{
    "title": "PDF作品 - Work3",
    "description": "PDF形式の作品です。",
    "priority": 3,
    "type": "html",
    "PdfPaths": ["work3.pdf"],
    "thumbnail": "thumbnail.jpg",
    "author": "cc",
    "genre": "資料作品",
    "credit": "",
}
```

### 設定可能なフィールド

#### 共通フィールド
- `title`: 作品タイトル（必須）
- `description`: 作品説明（改行は `\n` で指定可能）
- `priority`: 表示順序（数値、小さいほど上に表示）
- `type`: 作品タイプ（`"exe"` または `"html"`。PDF作品も `"html"` として表示）
- `thumbnail`: サムネイル画像のファイル名
- `author`: 制作者名
- `genre`: ジャンル
- `credit`: クレジット情報（改行は `\n` で指定可能）

#### ゲーム固有フィールド
- `executablePath`: 実行ファイルのパス
- `operation`: 操作方法
- `estimatedPlayTime`: 推定プレイ時間

#### HTML作品固有フィールド
- `displayMode`: ローカルWeb作品では `"local-html"`
- `htmlPath`: 作品フォルダを基準にした入口HTMLの相対パス
- `MoviePaths`: 表示する動画ファイルのパス配列
- `ImagePaths`: 表示する画像ファイルのパス配列
- `PdfPaths`: 表示するPDFファイルのパス配列

`htmlPath` がある作品はHTMLサイトを直接表示し、ない作品は動画・画像・PDF用の作品紹介画面を表示します。

## 起動方法

### 開発モード
```powershell
npm start
```

または
```powershell
.\run.ps1
```

### ビルド（配布用）
```powershell
npm run build
```

### テストと確認用HTML作品

```powershell
npm test
npm run fixture:install
npm start
```

確認後は仮作品を削除してください。仮作品を配置したままビルドすると配布物にも含まれます。

```powershell
npm run fixture:remove
```

## 新しい作品の追加方法

1. `works/` フォルダに新しいフォルダを作成
2. 作品ファイル（exe または HTML+関連ファイル）を配置
3. `config.json5` を作成し、必要な情報を記入
4. `thumbnail.jpg` サムネイル画像を配置
5. アプリを再起動

フォームの「ゲーム(.html)」「その他(.html)」では、次の形式だけを受け付けます。

- 外部素材を使わない単一の `.html`
- `index.html` とCSS、JavaScript、画像などをまとめた `.zip`
- ReactやViteなどの場合は、ソースではなくビルド済みの成果物

公開URL、ログイン、サーバー処理、データベース、外部APIを必要とする作品には対応しません。複数ページを含むZIPは入口を `index.html` にしてください。

## 技術仕様

- **Framework**: Electron
- **言語**: JavaScript, HTML, CSS
- **対応OS**: Windows
- **ファイル形式**:
  - ゲーム: .exe
  - 映像/Web作品: HTML + CSS + JS + 動画ファイル
  - PDF作品: .pdf

## トラブルシューティング

### ログファイルの場所
- ログは次の場所に保存されます。
- `C:\Users\{user_name}\AppData\Roaming\exhibition-launcher\logs\launcher.log`
- `{user_name}` は Windows のログインユーザー名に置き換えてください。

### 作品が表示されない場合
- `config.json5` の形式が正しいか確認
- ファイルパスが正しいか確認
- サムネイル画像が存在するか確認

### exe実行時のエラー
- 実行ファイルのパスが正しいか確認
- 必要なランタイムがインストールされているか確認
- セキュリティソフトによるブロックがないか確認

### HTML作品が表示されない場合
- `displayMode` が `local-html` になっているか確認
- `htmlPath` の入口HTMLが存在するか確認
- CSS、JavaScript、画像などがZIP内に含まれているか確認
- 外部URLや外部APIに依存していないか確認

### PDF作品が表示されない場合
- `PdfPaths` に指定したPDFファイルが作品フォルダ内に存在するか確認
- PDFファイル名やパスに誤りがないか確認

## ライセンス

このソフトウェアは部活動での使用を目的として制作されています。
