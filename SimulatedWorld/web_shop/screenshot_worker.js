/**
 * Playwright 截图脚本 — 由 capture_screenshots.py 调用
 * 用法: node screenshot_worker.js <urls_json> <output_dir>
 * urls_json: [{"name": "t1_main", "path": "http://..."}, ...]
 */
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const urls = JSON.parse(process.argv[2]);
  const outDir = process.argv[3];

  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });

  for (const { name, path } of urls) {
    const page = await browser.newPage();
    await page.setViewportSize({ width: 900, height: 700 });
    try {
      await page.goto(path, { waitUntil: 'networkidle', timeout: 10000 });
      await page.waitForTimeout(500);
      const outPath = outDir + '/' + name + '.png';
      await page.screenshot({ path: outPath, fullPage: false });
      const sizeKb = (fs.statSync(outPath).size / 1024).toFixed(1);
      console.log('OK: ' + name + ' (' + sizeKb + ' KB)');
    } catch (e) {
      console.error('FAIL: ' + name + ' - ' + e.message);
    }
    await page.close();
  }
  await browser.close();
})();
