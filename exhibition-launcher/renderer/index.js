// DOM要素の取得
const loadingElement = document.getElementById('loading');
const worksContainer = document.getElementById('works-container');
const errorMessage = document.getElementById('error-message');

// レンダラ側の最低限のログ転送（エラーと警告）
if (window.electronAPI && typeof window.electronAPI.log === 'function') {
    const _err = console.error;
    console.error = (...args) => {
        try { window.electronAPI.log('error', ...args); } catch (e) { /* ignore */ }
        _err(...args);
    };
    const _warn = console.warn;
    console.warn = (...args) => {
        try { window.electronAPI.log('warn', ...args); } catch (e) { /* ignore */ }
        _warn(...args);
    };
}

function formatErrorMessage(result, fallbackMessage) {
    if (typeof result === 'string') {
        return result;
    }

    const message = result?.userMessage || result?.error || result?.message || fallbackMessage;
    const lines = [message];

    if (result?.recoveryHint) {
        lines.push(`対処: ${result.recoveryHint}`);
    }

    if (result?.errorCode) {
        lines.push(`エラーコード: ${result.errorCode}`);
    }

    return lines.join('\n');
}

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await initializeApp();
        await loadWorks();
    } catch (error) {
        console.error('初期化エラー:', error);
        showError();
    }
});

// アプリの初期化
async function initializeApp() {
    try {
        const appConfig = await window.electronAPI.getAppConfig();

        // ページタイトルを設定
        if (appConfig.appTitle) {
            document.getElementById('page-title').textContent = appConfig.appTitle;
            document.getElementById('app-title').textContent = appConfig.appTitle;
        }

        // アプリ説明文を設定
        if (appConfig.appDescription) {
            document.getElementById('app-description').textContent = appConfig.appDescription;
        }
    } catch (error) {
        console.error('アプリ初期化エラー:', error);
    }
}

// 作品一覧を読み込み・表示
async function loadWorks() {
    try {
        loadingElement.style.display = 'block';
        worksContainer.style.display = 'none';
        errorMessage.style.display = 'none';

        const worksResult = await window.electronAPI.getWorks();

        if (worksResult && worksResult.success === false) {
            console.warn(formatErrorMessage(worksResult, '作品一覧を読み込めませんでした。'));
            showError(worksResult);
            return;
        }

        const works = Array.isArray(worksResult)
            ? worksResult
            : Array.isArray(worksResult?.data)
                ? worksResult.data
                : [];

        if (works.length === 0) {
            showError('作品が見つかりませんでした。');
            return;
        }

        displayWorks(works);

        loadingElement.style.display = 'none';
        worksContainer.style.display = 'grid';

    } catch (error) {
        console.error('作品読み込みエラー:', error);
        showError(error);
    }
}

// 作品カードを表示
async function displayWorks(works) {
    worksContainer.innerHTML = '';

    for (const work of works) {
        const workCard = await createWorkCard(work);
        worksContainer.appendChild(workCard);
    }
}

// 作品カードを作成
async function createWorkCard(work) {
    const card = document.createElement('div');
    card.className = 'work-card';

    // サムネイル画像を安全に読み込み(No Imageプレースホルダー付き)
    let thumbnailSrc = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzUwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDM1MCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIzNTAiIGhlaWdodD0iMjAwIiBmaWxsPSIjZjhmOWZhIi8+Cjx0ZXh0IHg9IjE3NSIgeT0iMTAwIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjN2Y4YzhkIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiPk5vIEltYWdlPC90ZXh0Pgo8L3N2Zz4=';

    try {
        const imageResult = await window.electronAPI.getImageBase64(work.thumbnailPath);
        if (imageResult.success) {
            thumbnailSrc = imageResult.data;
        } else {
            console.warn(formatErrorMessage(imageResult, 'サムネイル画像を読み込めませんでした。'));
        }
    } catch (error) {
        console.error('サムネイル読み込みエラー:', error);
    }

    // テンプレートからHTMLを生成
    try {
        const cardHtml = await window.electronAPI.generateWorkCardHtml(work, thumbnailSrc);
        card.innerHTML = cardHtml;
    } catch (error) {
        console.error('カードHTML生成エラー:', error);
        // フォールバック用の基本的なカード
        card.innerHTML = `
            <div class="thumbnail-frame">
                <img src="${thumbnailSrc}" alt="${work.title}" class="work-thumbnail">
                <div class="frame-title">${work.title}</div>
            </div>
            <div class="work-info">
                <p class="work-description">${work.description.replace(/\\n/g, '<br>')}</p>
                <div class="work-meta">
                    <span class="work-author">${work.author}</span>
                </div>
                <button class="launch-button ${work.type}-type" onclick="launchWork('${work.workId}', '${work.type}', '${work.type === 'exe' ? work.executablePath : work.htmlPath}')">
                    ${work.type === 'exe' ? 'ゲームを起動' : '作品を表示'}
                </button>
            </div>
        `;
    }

    return card;
}

// 作品を起動（データ属性から値を取得）
async function launchWork(button) {
    const workId = button.dataset.workId;
    const type = button.dataset.type;
    const path = button.dataset.path;
    const originalText = button.textContent;

    try {
        // ボタンを無効化
        button.disabled = true;
        button.textContent = type === 'exe' ? '起動中...' : '表示中...';

        let result;
        if (type === 'exe') {
            result = await window.electronAPI.launchExe(workId, path);
        } else if (type === 'html') {
            result = await window.electronAPI.showHtmlWork(workId, path);
        }

        if (!result.success) {
            alert(formatErrorMessage(result, '作品の起動に失敗しました。'));
        }

    } catch (error) {
        console.error('起動エラー:', error);
        alert(formatErrorMessage(error, '作品の起動に失敗しました。'));
    } finally {
        // ボタンを元に戻す
        setTimeout(() => {
            button.disabled = false;
            button.textContent = originalText;
        }, 200);
    }
}

// エラー表示
function showError(message = '作品の読み込みに失敗しました。') {
    loadingElement.style.display = 'none';
    worksContainer.style.display = 'none';
    errorMessage.style.display = 'block';
    errorMessage.querySelector('p').textContent = formatErrorMessage(message, '作品の読み込みに失敗しました。');
}

// グローバル関数として定義（HTMLから呼び出すため）
window.launchWork = launchWork;