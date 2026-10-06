const fs = require('fs');
const fsp = fs.promises;
const http = require('http');
const path = require('path');

const MIME_TYPES = new Map([
    ['.avif', 'image/avif'],
    ['.css', 'text/css; charset=utf-8'],
    ['.gif', 'image/gif'],
    ['.htm', 'text/html; charset=utf-8'],
    ['.html', 'text/html; charset=utf-8'],
    ['.ico', 'image/x-icon'],
    ['.jpeg', 'image/jpeg'],
    ['.jpg', 'image/jpeg'],
    ['.js', 'text/javascript; charset=utf-8'],
    ['.json', 'application/json; charset=utf-8'],
    ['.mjs', 'text/javascript; charset=utf-8'],
    ['.mp3', 'audio/mpeg'],
    ['.mp4', 'video/mp4'],
    ['.ogg', 'audio/ogg'],
    ['.pdf', 'application/pdf'],
    ['.png', 'image/png'],
    ['.svg', 'image/svg+xml'],
    ['.txt', 'text/plain; charset=utf-8'],
    ['.wasm', 'application/wasm'],
    ['.wav', 'audio/wav'],
    ['.webm', 'video/webm'],
    ['.webp', 'image/webp'],
    ['.woff', 'font/woff'],
    ['.woff2', 'font/woff2'],
    ['.xml', 'application/xml; charset=utf-8']
]);

function isPathInside(rootPath, candidatePath) {
    const relative = path.relative(rootPath, candidatePath);
    return relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative));
}

async function resolveExistingPathInside(rootPath, relativePath, options = {}) {
    if (typeof relativePath !== 'string' || !relativePath.trim()) {
        throw Object.assign(new Error('作品ファイルの相対パスが指定されていません。'), { code: 'INVALID_WORK_PATH' });
    }

    const normalizedInput = relativePath.trim();
    if (path.isAbsolute(normalizedInput) || /^[a-z][a-z0-9+.-]*:/i.test(normalizedInput)) {
        throw Object.assign(new Error('絶対パスやURLは作品ファイルに指定できません。'), { code: 'INVALID_WORK_PATH' });
    }

    const realRoot = await fsp.realpath(rootPath);
    const candidate = path.resolve(realRoot, normalizedInput);
    if (!isPathInside(realRoot, candidate)) {
        throw Object.assign(new Error('作品フォルダ外のパスは指定できません。'), { code: 'WORK_PATH_OUTSIDE_ROOT' });
    }

    const realCandidate = await fsp.realpath(candidate);
    if (!isPathInside(realRoot, realCandidate)) {
        throw Object.assign(new Error('作品フォルダ外を指すリンクは使用できません。'), { code: 'WORK_PATH_OUTSIDE_ROOT' });
    }

    const stat = await fsp.stat(realCandidate);
    if (options.fileOnly && !stat.isFile()) {
        throw Object.assign(new Error('指定された作品ファイルは通常ファイルではありません。'), { code: 'INVALID_WORK_FILE' });
    }
    if (options.directoryOnly && !stat.isDirectory()) {
        throw Object.assign(new Error('指定された作品フォルダはディレクトリではありません。'), { code: 'INVALID_WORK_DIRECTORY' });
    }

    return realCandidate;
}

async function resolveHtmlEntry(workDir, htmlPath) {
    const extension = path.extname(String(htmlPath || '')).toLowerCase();
    if (!['.html', '.htm'].includes(extension)) {
        throw Object.assign(new Error('HTML作品の入口は .html または .htm ファイルである必要があります。'), {
            code: 'INVALID_HTML_ENTRY'
        });
    }

    return resolveExistingPathInside(workDir, htmlPath, { fileOnly: true });
}

function getMimeType(filePath) {
    return MIME_TYPES.get(path.extname(filePath).toLowerCase()) || 'application/octet-stream';
}

function parseRange(rangeHeader, fileSize) {
    if (!rangeHeader || !rangeHeader.startsWith('bytes=')) {
        return null;
    }

    const match = /^bytes=(\d*)-(\d*)$/.exec(rangeHeader.trim());
    if (!match) {
        return { invalid: true };
    }

    let start;
    let end;
    if (!match[1] && match[2]) {
        const suffixLength = Number(match[2]);
        if (!Number.isSafeInteger(suffixLength) || suffixLength <= 0) {
            return { invalid: true };
        }
        start = Math.max(fileSize - suffixLength, 0);
        end = fileSize - 1;
    } else {
        start = Number(match[1]);
        end = match[2] ? Number(match[2]) : fileSize - 1;
    }

    if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end < start || start >= fileSize) {
        return { invalid: true };
    }

    return { start, end: Math.min(end, fileSize - 1) };
}

function sendText(response, statusCode, message, headers = {}) {
    const body = Buffer.from(message, 'utf8');
    response.writeHead(statusCode, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Length': body.length,
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
        ...headers
    });
    response.end(body);
}

async function createStaticWorkServer(siteRoot) {
    const realSiteRoot = await fsp.realpath(siteRoot);
    const rootStat = await fsp.stat(realSiteRoot);
    if (!rootStat.isDirectory()) {
        throw Object.assign(new Error('HTML作品のルートがディレクトリではありません。'), {
            code: 'INVALID_SITE_ROOT'
        });
    }

    const server = http.createServer(async (request, response) => {
        try {
            if (!['GET', 'HEAD'].includes(request.method)) {
                sendText(response, 405, 'Method Not Allowed', { Allow: 'GET, HEAD' });
                return;
            }

            let pathname;
            try {
                pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname);
            } catch (_error) {
                sendText(response, 400, 'Bad Request');
                return;
            }

            if (pathname.includes('\0')) {
                sendText(response, 400, 'Bad Request');
                return;
            }

            const relativeRequestPath = pathname.replace(/^\/+/, '').split('/').join(path.sep);
            let requestedPath = path.resolve(realSiteRoot, relativeRequestPath || '.');
            if (!isPathInside(realSiteRoot, requestedPath)) {
                sendText(response, 403, 'Forbidden');
                return;
            }

            let realRequestedPath;
            try {
                realRequestedPath = await fsp.realpath(requestedPath);
            } catch (error) {
                if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
                    sendText(response, 404, 'Not Found');
                    return;
                }
                throw error;
            }

            if (!isPathInside(realSiteRoot, realRequestedPath)) {
                sendText(response, 403, 'Forbidden');
                return;
            }

            let stat = await fsp.stat(realRequestedPath);
            if (stat.isDirectory()) {
                requestedPath = path.join(realRequestedPath, 'index.html');
                try {
                    realRequestedPath = await fsp.realpath(requestedPath);
                    stat = await fsp.stat(realRequestedPath);
                } catch (error) {
                    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
                        sendText(response, 404, 'Not Found');
                        return;
                    }
                    throw error;
                }
            }

            if (!stat.isFile() || !isPathInside(realSiteRoot, realRequestedPath)) {
                sendText(response, 404, 'Not Found');
                return;
            }

            const range = parseRange(request.headers.range, stat.size);
            if (range?.invalid) {
                sendText(response, 416, 'Range Not Satisfiable', {
                    'Content-Range': `bytes */${stat.size}`
                });
                return;
            }

            const headers = {
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-store',
                'Content-Type': getMimeType(realRequestedPath),
                'X-Content-Type-Options': 'nosniff'
            };
            let streamOptions;
            if (range) {
                headers['Content-Length'] = range.end - range.start + 1;
                headers['Content-Range'] = `bytes ${range.start}-${range.end}/${stat.size}`;
                response.writeHead(206, headers);
                streamOptions = { start: range.start, end: range.end };
            } else {
                headers['Content-Length'] = stat.size;
                response.writeHead(200, headers);
            }

            if (request.method === 'HEAD') {
                response.end();
                return;
            }

            const stream = fs.createReadStream(realRequestedPath, streamOptions);
            stream.on('error', () => {
                if (!response.headersSent) {
                    sendText(response, 500, 'Internal Server Error');
                } else {
                    response.destroy();
                }
            });
            stream.pipe(response);
        } catch (_error) {
            if (!response.headersSent) {
                sendText(response, 500, 'Internal Server Error');
            } else {
                response.destroy();
            }
        }
    });

    await new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(0, '127.0.0.1', () => {
            server.off('error', reject);
            resolve();
        });
    });

    const address = server.address();
    const origin = `http://127.0.0.1:${address.port}`;
    let closed = false;
    const close = () => {
        if (closed) {
            return;
        }
        closed = true;
        server.close();
        if (typeof server.closeAllConnections === 'function') {
            server.closeAllConnections();
        }
    };

    return { server, origin, close, siteRoot: realSiteRoot };
}

module.exports = {
    createStaticWorkServer,
    getMimeType,
    isPathInside,
    parseRange,
    resolveExistingPathInside,
    resolveHtmlEntry
};
