const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
    createStaticWorkServer,
    parseRange,
    resolveHtmlEntry
} = require('../local-html-server');

async function makeSite(t) {
    const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'ex-launcher-html-'));
    t.after(() => fs.rm(tempDir, { recursive: true, force: true }));
    await fs.mkdir(path.join(tempDir, 'styles'));
    await fs.writeFile(path.join(tempDir, 'index.html'), '<h1>LOCAL HTML OK</h1>', 'utf8');
    await fs.writeFile(path.join(tempDir, 'styles', 'main.css'), 'body { color: green; }', 'utf8');
    await fs.writeFile(path.join(tempDir, 'media.bin'), Buffer.from('0123456789'));
    return tempDir;
}

test('resolveHtmlEntry accepts an HTML file inside the work directory', async (t) => {
    const siteDir = await makeSite(t);
    const workDir = path.dirname(siteDir);
    const relativeEntry = path.relative(workDir, path.join(siteDir, 'index.html'));

    const entry = await resolveHtmlEntry(workDir, relativeEntry);

    assert.equal(entry, await fs.realpath(path.join(siteDir, 'index.html')));
});

test('resolveHtmlEntry rejects paths outside the work directory', async (t) => {
    const siteDir = await makeSite(t);

    await assert.rejects(
        resolveHtmlEntry(siteDir, '../outside.html'),
        (error) => error.code === 'WORK_PATH_OUTSIDE_ROOT'
    );
});

test('static server serves nested files with MIME types and blocks traversal', async (t) => {
    const siteDir = await makeSite(t);
    const staticServer = await createStaticWorkServer(siteDir);
    t.after(() => staticServer.close());

    const htmlResponse = await fetch(`${staticServer.origin}/index.html`);
    assert.equal(htmlResponse.status, 200);
    assert.match(htmlResponse.headers.get('content-type'), /^text\/html/);
    assert.match(await htmlResponse.text(), /LOCAL HTML OK/);

    const cssResponse = await fetch(`${staticServer.origin}/styles/main.css`);
    assert.equal(cssResponse.status, 200);
    assert.match(cssResponse.headers.get('content-type'), /^text\/css/);

    const traversalResponse = await fetch(`${staticServer.origin}/%2e%2e/package.json`);
    assert.ok([403, 404].includes(traversalResponse.status));
});

test('static server supports byte ranges', async (t) => {
    const siteDir = await makeSite(t);
    const staticServer = await createStaticWorkServer(siteDir);
    t.after(() => staticServer.close());

    const response = await fetch(`${staticServer.origin}/media.bin`, {
        headers: { Range: 'bytes=2-5' }
    });

    assert.equal(response.status, 206);
    assert.equal(response.headers.get('content-range'), 'bytes 2-5/10');
    assert.equal(await response.text(), '2345');
});

test('parseRange rejects invalid ranges', () => {
    assert.deepEqual(parseRange('bytes=99-100', 10), { invalid: true });
    assert.deepEqual(parseRange('bytes=2-5', 10), { start: 2, end: 5 });
});

test('bundled smoke fixture is fully available from the local server', async (t) => {
    const fixtureSite = path.resolve(__dirname, '..', 'test-fixtures', 'local-html-work', 'site');
    const staticServer = await createStaticWorkServer(fixtureSite);
    t.after(() => staticServer.close());

    for (const resourcePath of [
        '/index.html',
        '/static/main.css',
        '/static/main.js',
        '/static/check.svg',
        '/data/message.json',
        '/pages/detail.html'
    ]) {
        const response = await fetch(`${staticServer.origin}${resourcePath}`);
        assert.equal(response.status, 200, resourcePath);
    }
});
