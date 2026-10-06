const fs = require('fs');
const path = require('path');

const launcherDir = path.resolve(__dirname, '..');
const sourceDir = path.join(launcherDir, 'test-fixtures', 'local-html-work');
const worksDir = path.join(launcherDir, 'works');
const targetDir = path.join(worksDir, '999-local-html-smoke');

function assertSafeTarget() {
    const relative = path.relative(worksDir, targetDir);
    if (!relative || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
        throw new Error(`仮作品の配置先が不正です: ${targetDir}`);
    }
}

function removeFixture() {
    assertSafeTarget();
    fs.rmSync(targetDir, { recursive: true, force: true });
    console.log(`仮作品を削除しました: ${targetDir}`);
}

function installFixture() {
    assertSafeTarget();
    fs.mkdirSync(worksDir, { recursive: true });
    fs.rmSync(targetDir, { recursive: true, force: true });
    fs.cpSync(sourceDir, targetDir, { recursive: true });
    fs.renameSync(
        path.join(targetDir, 'config.template.json5'),
        path.join(targetDir, 'config.json5')
    );
    console.log(`仮作品を配置しました: ${targetDir}`);
}

const action = process.argv[2];
if (action === 'install') {
    installFixture();
} else if (action === 'remove') {
    removeFixture();
} else {
    console.error('使用方法: node scripts/local-html-fixture.js <install|remove>');
    process.exitCode = 1;
}
