# 作品展示ランチャー

大学の部活動で制作した映像作品やゲームを展示するためのElectronアプリケーションです。

## 機能

- 作品ごとの設定ファイル（config.json5）に基づいた自動読み込み
- priority順での作品表示
- exe実行とHTML作品表示の両方に対応
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
    "title": "映像作品 - Work2",
    "description": "部活動で制作した映像作品です。\n美しい映像と音楽をお楽しみください。",
    "priority": 2,
    "type": "html",
    "htmlPath": "index.html",
    "thumbnail": "thumbnail.jpg",
    "author": "aa, bb",
    "genre": "映像作品",
    "credit": "制作\n企画・演出: aa\n撮影・編集: bb\n\n音楽\nフリー音楽素材 MusMus\nhttps://musmus.main.jp/",
}
```

### 設定可能なフィールド

#### 共通フィールド
- `title`: 作品タイトル（必須）
- `description`: 作品説明（改行は `\n` で指定可能）
- `priority`: 表示順序（数値、小さいほど上に表示）
- `type`: 作品タイプ（`"exe"` または `"html"`）
- `thumbnail`: サムネイル画像のファイル名
- `author`: 制作者名
- `genre`: ジャンル
- `credit`: クレジット情報（改行は `\n` で指定可能）

#### ゲーム固有フィールド
- `executablePath`: 実行ファイルのパス
- `operation`: 操作方法
- `estimatedPlayTime`: 推定プレイ時間

#### HTML作品固有フィールド
- `htmlPath`: HTMLファイルのパス

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

## 新しい作品の追加方法

1. `works/` フォルダに新しいフォルダを作成
2. 作品ファイル（exe または HTML+関連ファイル）を配置
3. `config.json5` を作成し、必要な情報を記入
4. `thumbnail.jpg` サムネイル画像を配置
5. アプリを再起動

## 技術仕様

- **Framework**: Electron
- **言語**: JavaScript, HTML, CSS
- **対応OS**: Windows
- **ファイル形式**:
  - ゲーム: .exe
  - 映像/Web作品: HTML + CSS + JS + 動画ファイル

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
- index.htmlが存在するか確認
- 関連ファイル（動画、画像等）のパスが正しいか確認

## ライセンス

このソフトウェアは部活動での使用を目的として制作されています。