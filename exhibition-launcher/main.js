const { app, BrowserWindow, ipcMain } = require('electron');
const { randomUUID } = require('crypto');
const path = require('path');
const fs = require('fs').promises;
const { execFile } = require('child_process');
const JSON5 = require('json5');
const log = require('electron-log');
const {
    createStaticWorkServer,
    resolveExistingPathInside,
    resolveHtmlEntry
} = require('./local-html-server');

const defaultLoggingConfig = {
    level: 'silly',
    maxSizeMB: 5,
    fileName: 'launcher.log'
};

// ロガー初期化
function applyLoggingConfig(loggingConfig = {}) {
    const mergedLoggingConfig = {
        ...defaultLoggingConfig,
        ...loggingConfig
    };

    log.transports.file.resolvePathFn = () => {
        const logDir = path.join(app.getPath('userData'), 'logs');
        return path.join(logDir, mergedLoggingConfig.fileName);
    };
    log.transports.file.level = mergedLoggingConfig.level;
    log.transports.console.level = false;
    log.transports.file.maxSize = mergedLoggingConfig.maxSizeMB * 1024 * 1024;
    log.format = '{y}-{m}-{d} {h}:{i}:{s}.{ms} [{level}] {text}';
}

applyLoggingConfig();
const logger = log;

// console をラップしてファイルにも書き出す（既存のコンソール出力は維持）
const _console = {
    log: console.log,
    info: console.info,
    warn: console.warn,
    error: console.error,
    debug: console.debug
};

console.log = (...args) => { logger.info(...args); _console.log(...args); };
console.info = (...args) => { logger.info(...args); _console.info(...args); };
console.error = (...args) => { logger.error(...args); _console.error(...args); };
console.warn = (...args) => { logger.warn(...args); _console.warn(...args); };
console.debug = (...args) => { logger.debug(...args); _console.debug(...args); };

process.on('uncaughtException', (err) => {
    logger.error('uncaughtException', err && err.stack ? err.stack : err);
    _console.error(err);
});

process.on('unhandledRejection', (reason) => {
    logger.error('unhandledRejection', reason);
    _console.error(reason);
});

function getErrorCode(error, fallbackCode = 'UNKNOWN_ERROR') {
    if (!error) {
        return fallbackCode;
    }

    if (typeof error.code === 'string' && error.code) {
        return error.code;
    }

    return fallbackCode;
}

function getRecoveryHint(errorCode, options = {}) {
    if (options.recoveryHint) {
        return options.recoveryHint;
    }

    if (errorCode === 'ENOENT') {
        return '作品フォルダや設定ファイルの配置を確認してから再実行してください。';
    }

    if (errorCode === 'EACCES' || errorCode === 'EPERM') {
        return 'アプリを終了してからもう一度実行してください。';
    }

    return '詳細はログを確認してください。';
}

function createErrorResponse(operation, error, options = {}) {
    const errorCode = options.errorCode || getErrorCode(error);
    const userMessage = options.userMessage || '処理に失敗しました。';
    const recoveryHint = getRecoveryHint(errorCode, options);
    const debugMessage = error && error.stack ? error.stack : (error && error.message ? error.message : String(error));

    logger.error(`${operation} error`, {
        errorCode,
        userMessage,
        recoveryHint,
        debugMessage,
        context: options.context || {}
    });

    return {
        success: false,
        error: userMessage,
        errorCode,
        userMessage,
        recoveryHint,
        debugMessage,
        operation,
        context: options.context || {}
    };
}

let mainWindow;
let appConfig;
const activeLocalHtmlWorks = new Map();

// リソースディレクトリのパスを取得する関数
function getResourcePath(relativePath) {
    if (app.isPackaged) {
        // ビルド後：extraResourcesディレクトリから読み込み
        return path.join(process.resourcesPath, relativePath);
    } else {
        // 開発時：プロジェクトディレクトリから読み込み
        return path.join(__dirname, relativePath);
    }
}

function getWorksDirectoryPath() {
    const worksPath = appConfig?.worksDirectory || 'works';
    return path.isAbsolute(worksPath) ? worksPath : getResourcePath(worksPath);
}

async function resolveWorkDirectory(workId) {
    return resolveExistingPathInside(getWorksDirectoryPath(), workId, { directoryOnly: true });
}

function shouldOpenLocalHtml(config) {
    return config?.type === 'html'
        && (config.displayMode === 'local-html' || (!config.displayMode && Boolean(config.htmlPath)));
}

function shouldMaximizeWorkWindow(config) {
    return typeof config?.startMaximized !== 'undefined'
        ? config.startMaximized === true
        : appConfig?.startMaximized === true;
}

// テンプレート用のformat関数
function format(template, values, escapeForAttributes = false) {
    return template.replace(/\{(\w+)\}/g, (_, key) => {
        let value = values[key] ?? `{${key}}`;
        // データ属性用の場合のみHTMLエスケープ
        if (escapeForAttributes && typeof value === 'string') {
            value = value.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }
        return value;
    });
}

// アプリケーション設定を読み込む関数
async function loadAppConfig() {
    try {
        const configPath = getResourcePath('config.json5');
        const configData = await fs.readFile(configPath, 'utf8');
        appConfig = JSON5.parse(configData);
        console.log('アプリケーション設定を読み込みました:', appConfig);
    } catch (error) {
        console.error('設定ファイル読み込みエラー:', error);
        // デフォルト設定を使用
        appConfig = {
            appName: "Launcher",
            appTitle: "作品展示ランチャー",
            appDescription: "ボタンをクリックして閲覧できます。\nマウスホイールやスクロールバーで上下にスクロールできます。",
            icon: "assets/kswl-logo.png",
            // 起動時ウィンドウを最大化するかどうかのデフォルト設定
            startMaximized: true,
            workDisplayHandling: {
                mode: "overwrite"
            },
            logging: defaultLoggingConfig
        };
    }

    applyLoggingConfig(appConfig.logging);
}

async function createWindow() {
    // 設定が読み込まれていない場合は読み込む
    if (!appConfig) {
        await loadAppConfig();
    }

    mainWindow = new BrowserWindow({
        width: 900,
        height: 700,
        show: false, // 最初は非表示
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
            webSecurity: false // ローカルファイルアクセスのため
        },
        icon: path.join(__dirname, appConfig.icon)
    });
    const baseDir = app.isPackaged
        ? process.resourcesPath
        : __dirname;

    mainWindow.loadFile(
        path.join(baseDir, 'renderer', 'index.html')
    );
    // mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

    // 設定によって起動時に最大化してから表示
    if (appConfig && appConfig.startMaximized === true) {
        mainWindow.maximize();
    }
    mainWindow.show();

    // 開発時にDevToolsを開く（必要に応じて）
    // mainWindow.webContents.openDevTools();
}

app.whenReady().then(async () => {
    await loadAppConfig();
    await createWindow();
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    for (const activeWork of activeLocalHtmlWorks.values()) {
        activeWork.closeServer();
    }
    activeLocalHtmlWorks.clear();
});

app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        await createWindow();
    }
});

// アプリケーション設定を取得
ipcMain.handle('get-app-config', async () => {
    if (!appConfig) {
        await loadAppConfig();
    }
    return appConfig;
});

// 作品一覧を取得
ipcMain.handle('get-works', async () => {
    try {
        // 設定からworksディレクトリのパスを取得
        const worksPath = appConfig?.worksDirectory || 'works';
        const worksDir = path.isAbsolute(worksPath) ? worksPath : getResourcePath(worksPath);
        const folders = await fs.readdir(worksDir);
        const works = [];

        for (const folder of folders) {
            const folderPath = path.join(worksDir, folder);
            const stat = await fs.stat(folderPath);

            if (stat.isDirectory()) {
                const configPath = path.join(folderPath, 'config.json5');
                try {
                    const configData = await fs.readFile(configPath, 'utf8');
                    const config = JSON5.parse(configData);

                    works.push({
                        ...config,
                        workId: folder
                    });
                } catch (error) {
                    console.error(`設定ファイル読み込みエラー (${folder}):`, error);
                }
            }
        }

        // visible: false の作品を除外
        const visibleWorks = works.filter(work => work.visible !== false);

        // priority順でソート
        visibleWorks.sort((a, b) => a.priority - b.priority);
        return { success: true, data: visibleWorks };
    } catch (error) {
        console.error('作品一覧取得エラー:', error);
        return createErrorResponse('作品一覧取得', error, {
            userMessage: '作品一覧を読み込めませんでした。',
            recoveryHint: 'works フォルダと config.json5 の内容を確認してから再起動してください。',
            context: { worksDirectory: appConfig?.worksDirectory || 'works' }
        });
    }
});

// exe実行
ipcMain.handle('launch-exe', async (_event, workId) => {
    try {
        const workDir = await resolveWorkDirectory(workId);
        const configData = await fs.readFile(path.join(workDir, 'config.json5'), 'utf8');
        const config = JSON5.parse(configData);
        if (config.type !== 'exe') {
            throw Object.assign(new Error('EXE作品ではない設定が指定されました。'), { code: 'INVALID_WORK_TYPE' });
        }
        const fullExePath = await resolveExistingPathInside(workDir, config.executablePath, { fileOnly: true });

        return new Promise((resolve) => {
            execFile(fullExePath, { cwd: path.dirname(fullExePath) }, (error) => {
                if (error) {
                    console.error('exe実行エラー:', error);
                    resolve(createErrorResponse('exe実行', error, {
                        userMessage: '作品を起動できませんでした。',
                        recoveryHint: '実行ファイルの場所と権限を確認してから再実行してください。',
                        context: { workId, fullExePath }
                    }));
                } else {
                    resolve({ success: true });
                }
            });
        });
    } catch (error) {
        console.error('exe起動エラー:', error);
        return createErrorResponse('exe起動', error, {
            userMessage: '作品を起動できませんでした。',
            recoveryHint: '実行ファイルの場所と権限を確認してから再実行してください。',
            context: { workId }
        });
    }
});

async function openGeneratedWorkDisplay(config, workDir, workId) {
    const displayHtmlPath = path.join(workDir, 'work_display.html');
    const rootHandlingMode = appConfig?.workDisplayHandlingMode || 'overwrite';
    const workHandlingMode = config?.workDisplayHandlingMode || rootHandlingMode;
    let shouldCreateFile = true;

    console.log(`work_display.html 処理モード: ${workHandlingMode} (${workId})`);
    if (workHandlingMode === 'reuse') {
        try {
            await fs.access(displayHtmlPath);
            console.log(`work_display.html が既に存在します (${workId}): 再利用します`);
            shouldCreateFile = false;
        } catch (_error) {
            console.log(`work_display.html が存在しません (${workId}): 新規作成します`);
        }
    }

    if (shouldCreateFile) {
        const htmlContent = await generateWorkHtml(config, workDir);
        await fs.writeFile(displayHtmlPath, htmlContent, 'utf8');
    }

    const workWindow = new BrowserWindow({
        width: 950,
        height: 710,
        parent: mainWindow,
        modal: false,
        show: false,
        webPreferences: {
            preload: path.join(__dirname, 'work-display-preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
            webSecurity: false
        },
        icon: path.join(__dirname, appConfig.icon)
    });

    workWindow.setTitle(config.title || '作品表示');
    await workWindow.loadFile(displayHtmlPath);
    if (shouldMaximizeWorkWindow(config)) {
        workWindow.maximize();
    }
    workWindow.show();
    workWindow.on('closed', () => {
        console.log(`作品ウィンドウが閉じられました: ${config.title}`);
    });
}

function configureLocalHtmlWindowSecurity(workWindow, allowedOrigin) {
    const workSession = workWindow.webContents.session;
    workSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
    workSession.setPermissionCheckHandler(() => false);
    workSession.on('will-download', (event) => event.preventDefault());
    workSession.webRequest.onBeforeRequest({ urls: ['<all_urls>'] }, (details, callback) => {
        let allowed = false;
        try {
            const requestUrl = new URL(details.url);
            allowed = requestUrl.origin === allowedOrigin
                || requestUrl.protocol === 'data:'
                || requestUrl.protocol === 'blob:';
        } catch (_error) {
            allowed = false;
        }
        callback({ cancel: !allowed });
    });

    const preventExternalNavigation = (event, targetUrl) => {
        try {
            if (new URL(targetUrl).origin !== allowedOrigin) {
                event.preventDefault();
            }
        } catch (_error) {
            event.preventDefault();
        }
    };
    workWindow.webContents.on('will-navigate', preventExternalNavigation);
    workWindow.webContents.on('will-redirect', preventExternalNavigation);
    workWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
}

async function openLocalHtmlWork(config, workDir, workId) {
    const current = activeLocalHtmlWorks.get(workId);
    if (current && !current.window.isDestroyed()) {
        if (current.window.isMinimized()) {
            current.window.restore();
        }
        current.window.show();
        current.window.focus();
        return;
    }

    const htmlEntry = await resolveHtmlEntry(workDir, config.htmlPath);
    const siteRoot = path.dirname(htmlEntry);
    const staticServer = await createStaticWorkServer(siteRoot);
    const partition = `local-html-${randomUUID()}`;
    let workWindow;
    try {
        workWindow = new BrowserWindow({
            width: 950,
            height: 710,
            parent: mainWindow,
            modal: false,
            show: false,
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                sandbox: true,
                webSecurity: true,
                partition,
                backgroundThrottling: false
            },
            icon: path.join(__dirname, appConfig.icon)
        });
    } catch (error) {
        staticServer.close();
        throw error;
    }

    let cleanedUp = false;
    const cleanup = () => {
        if (cleanedUp) {
            return;
        }
        cleanedUp = true;
        activeLocalHtmlWorks.delete(workId);
        staticServer.close();
    };

    activeLocalHtmlWorks.set(workId, { window: workWindow, closeServer: cleanup });
    configureLocalHtmlWindowSecurity(workWindow, staticServer.origin);
    workWindow.setTitle(config.title || 'HTML作品');
    workWindow.on('closed', () => {
        cleanup();
        console.log(`HTML作品ウィンドウが閉じられました: ${config.title}`);
    });

    const entryUrl = `${staticServer.origin}/${encodeURIComponent(path.basename(htmlEntry))}`;
    try {
        await workWindow.loadURL(entryUrl);
    } catch (error) {
        cleanup();
        if (!workWindow.isDestroyed()) {
            workWindow.destroy();
        }
        throw error;
    }

    if (shouldMaximizeWorkWindow(config)) {
        workWindow.maximize();
    }
    workWindow.show();
}

// HTML作品表示（ローカルサイトまたは生成した作品紹介画面）
ipcMain.handle('show-html-work', async (_event, workId) => {
    try {
        const workDir = await resolveWorkDirectory(workId);
        const configPath = path.join(workDir, 'config.json5');
        const configData = await fs.readFile(configPath, 'utf8');
        const config = JSON5.parse(configData);

        if (config.type !== 'html') {
            throw Object.assign(new Error('HTML作品ではない設定が指定されました。'), { code: 'INVALID_WORK_TYPE' });
        }

        if (shouldOpenLocalHtml(config)) {
            await openLocalHtmlWork(config, workDir, workId);
        } else {
            await openGeneratedWorkDisplay(config, workDir, workId);
        }

        return { success: true };
    } catch (error) {
        console.error('HTML表示エラー:', error);
        return createErrorResponse('HTML表示', error, {
            userMessage: '作品画面を開けませんでした。',
            recoveryHint: 'config.json5、htmlPath、作品ファイルの配置を確認してから再実行してください。',
            context: { workId }
        });
    }
});

// HTMLテンプレートを生成する関数
async function generateWorkHtml(config, workDir) {
    try {
        // メインテンプレートを読み込み
        const templatePath = getResourcePath(path.join('templates', 'work-template.html'));
        const template = await fs.readFile(templatePath, 'utf8');

        // ImagePathsから画像コンテンツを生成
        const imageContent = await generateImageContent(config.ImagePaths || []);

        // MoviePathsから動画コンテンツを生成
        const movieContent = await generateMovieContent(config.MoviePaths || []);

        // PdfPathsからPDFコンテンツを生成
        const pdfContent = await generatePdfContent(config.PdfPaths || []);

        // テンプレートに値を埋め込み
        return format(template, {
            title: config.title,
            description: config.description.replace(/\\n/g, '\n'),
            author: config.author,
            genre: config.genre || '',
            credit: config.credit ? config.credit.replace(/\\n/g, '\n') : '',
            imageContent: imageContent,
            movieContent: movieContent,
            pdfContent: pdfContent
        });
    } catch (error) {
        console.error('HTMLテンプレート生成エラー:', error);
        throw error;
    }
}

// PDFコンテンツを生成する関数
async function generatePdfContent(pdfPaths) {
    if (!pdfPaths || pdfPaths.length === 0) {
        return '';
    }

    try {
        const templatePath = getResourcePath(path.join('templates', 'pdf-item-template.html'));
        const template = await fs.readFile(templatePath, 'utf8');

        return pdfPaths.map(pdfPath => {
            return format(template, { pdfPath: pdfPath });
        }).join('');
    } catch (error) {
        console.error('PDFコンテンツ生成エラー:', error);
        return '';
    }
}

// 動画コンテンツを生成する関数
async function generateMovieContent(moviePaths) {
    if (!moviePaths || moviePaths.length === 0) {
        return '';
    }

    try {
        const templatePath = getResourcePath(path.join('templates', 'movie-item-template.html'));
        const template = await fs.readFile(templatePath, 'utf8');

        return moviePaths.map(moviePath => {
            return format(template, { moviePath: moviePath });
        }).join('');
    } catch (error) {
        console.error('動画コンテンツ生成エラー:', error);
        return '';
    }
}

// 画像コンテンツを生成する関数
async function generateImageContent(imagePaths) {
    if (!imagePaths || imagePaths.length === 0) {
        return '';
    }

    try {
        const galleryTemplatePath = getResourcePath(path.join('templates', 'image-gallery-template.html'));
        const itemTemplatePath = getResourcePath(path.join('templates', 'image-item-template.html'));

        const galleryTemplate = await fs.readFile(galleryTemplatePath, 'utf8');
        const itemTemplate = await fs.readFile(itemTemplatePath, 'utf8');

        const imageItems = imagePaths.map(imagePath => {
            return format(itemTemplate, { imagePath: imagePath });
        }).join('');

        return format(galleryTemplate, { imageItems: imageItems });
    } catch (error) {
        console.error('画像コンテンツ生成エラー:', error);
        return '';
    }
}

// 作品一覧に戻る（ポップアップウィンドウを閉じる）
ipcMain.handle('back-to-launcher', async (event) => {
    try {
        // 呼び出し元のウィンドウを取得
        const senderWindow = BrowserWindow.fromWebContents(event.sender);

        if (senderWindow && senderWindow !== mainWindow) {
            // ポップアップウィンドウの場合は閉じる
            senderWindow.close();
        } else {
            // メインウィンドウの場合は何もしない（既にランチャー画面）
            console.log('メインウィンドウからの呼び出し - 何もしません');
        }

        return { success: true };
    } catch (error) {
        console.error('ランチャー復帰エラー:', error);
        return createErrorResponse('ランチャー復帰', error, {
            userMessage: 'ランチャー画面に戻れませんでした。',
            recoveryHint: 'アプリを一度閉じてから再起動してください。'
        });
    }
});

// 作品設定に記載されたサムネイルをBase64で取得
ipcMain.handle('get-image-base64', async (_event, workId) => {
    try {
        const workDir = await resolveWorkDirectory(workId);
        const configData = await fs.readFile(path.join(workDir, 'config.json5'), 'utf8');
        const config = JSON5.parse(configData);
        const imagePath = await resolveExistingPathInside(workDir, config.thumbnail, { fileOnly: true });
        const imageData = await fs.readFile(imagePath);
        const base64 = imageData.toString('base64');
        const ext = path.extname(imagePath).toLowerCase();
        const mimeType = ext === '.png'
            ? 'image/png'
            : ext === '.jpg' || ext === '.jpeg'
                ? 'image/jpeg'
                : ext === '.gif'
                    ? 'image/gif'
                    : ext === '.svg'
                        ? 'image/svg+xml'
                        : 'image/png';
        return { success: true, data: `data:${mimeType};base64,${base64}` };
    } catch (error) {
        console.error('画像読み込みエラー:', error);
        return createErrorResponse('画像読み込み', error, {
            userMessage: 'サムネイル画像を読み込めませんでした。',
            recoveryHint: '画像ファイルの場所と権限を確認してから再実行してください。',
            context: { workId }
        });
    }
});

// 作品カードHTMLを生成
ipcMain.handle('generate-work-card-html', async (event, work, thumbnailSrc) => {
    try {
        const templatePath = getResourcePath(path.join('templates', 'work-card-template.html'));
        const template = await fs.readFile(templatePath, 'utf8');

        const tagsSection = work.tags ? work.tags.map(tag => `<span class="work-tag">${tag}</span>`).join('') : '';
        const localHtmlWork = shouldOpenLocalHtml(work);
        const buttonText = work.type === 'exe'
            ? 'ゲームを起動'
            : localHtmlWork
                ? 'サイトを開く'
                : '作品を表示';
        return format(template, {
            thumbnailSrc: thumbnailSrc,
            title: work.title,
            description: work.description.replace(/\\n/g, '<br>'),
            author: work.author,
            genre: work.genre || '',
            operation: work.operation || '',
            estimatedPlayTime: work.estimatedPlayTime || '',
            tagsSection: tagsSection,
            credit: work.credit ? work.credit.replace(/\\n/g, '<br>') : '',
            type: work.type,
            workId: work.workId,
            buttonText: buttonText
        }, true); // データ属性用にエスケープを有効化
    } catch (error) {
        console.error('作品カードHTML生成エラー:', error);
        return '';
    }
});

// レンダラープロセスからの最小限のログ受信（preload 経由）
ipcMain.handle('renderer-log', async (event, level, args) => {
    try {
        if (!logger) return { success: false };
        const method = typeof logger[level] === 'function' ? logger[level] : logger.info;
        if (Array.isArray(args)) {
            method.apply(logger, args);
        } else {
            method.call(logger, args);
        }
        return { success: true };
    } catch (error) {
        console.error('renderer-log エラー:', error);
        return createErrorResponse('renderer-log', error, {
            userMessage: 'ログを送信できませんでした。',
            recoveryHint: 'アプリを再起動してから再度操作してください。'
        });
    }
});
