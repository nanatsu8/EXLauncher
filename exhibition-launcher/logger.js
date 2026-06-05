const { app } = require('electron');
const path = require('path');
const log = require('electron-log');

// 保存先をユーザーデータ配下の logs ディレクトリにする
log.transports.file.resolvePathFn = () => {
    const logDir = path.join(app.getPath('userData'), 'logs');
    return path.join(logDir, 'launcher.log');
};

// ログレベルのデフォルト
log.transports.file.level = 'silly';
log.transports.console.level = false; // console は既存の console 出力を使う

// ファイルサイズによるローテーション（electron-log は maxSize をサポート）
log.transports.file.maxSize = 5 * 1024 * 1024; // 5MB

// 時刻フォーマット
log.format = '{y}-{m}-{d} {h}:{i}:{s}.{ms} [{level}] {text}';

module.exports = log;
