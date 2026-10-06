const moduleStatus = document.querySelector('#module-status');
moduleStatus.textContent = 'ES Module: OK';
moduleStatus.className = 'ok';

const fetchStatus = document.querySelector('#fetch-status');
try {
    const response = await fetch('/data/message.json');
    const data = await response.json();
    fetchStatus.textContent = `fetch: ${data.message}`;
    fetchStatus.className = 'ok';
} catch (error) {
    fetchStatus.textContent = `fetch: 失敗 (${error.message})`;
}

document.querySelector('#interaction-button').addEventListener('click', () => {
    const status = document.querySelector('#interaction-status');
    status.textContent = 'ボタン操作: OK';
    status.className = 'ok';
});
