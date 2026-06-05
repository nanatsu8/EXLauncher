const { contextBridge, ipcRenderer } = require('electron');

// メインプロセスとの通信用APIを公開
contextBridge.exposeInMainWorld('electronAPI', {
    // アプリケーション設定を取得
    getAppConfig: () => ipcRenderer.invoke('get-app-config'),

    // 作品一覧を取得
    getWorks: () => ipcRenderer.invoke('get-works'),

    // exe実行
    launchExe: (workId, executablePath) => ipcRenderer.invoke('launch-exe', workId, executablePath),

    // HTML作品を表示
    showHtmlWork: (workId, htmlPath) => ipcRenderer.invoke('show-html-work', workId, htmlPath),

    // 画像をBase64で取得
    getImageBase64: (imagePath) => ipcRenderer.invoke('get-image-base64', imagePath),

    // 作品カードHTMLを生成
    generateWorkCardHtml: (work, thumbnailSrc) => ipcRenderer.invoke('generate-work-card-html', work, thumbnailSrc),

    // レンダラーログ送信（最小限）
    log: (level, ...args) => ipcRenderer.invoke('renderer-log', level, args),

    // 作品一覧に戻る
    backToLauncher: () => ipcRenderer.invoke('back-to-launcher')
});