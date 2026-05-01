const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  page.on('console', (msg) => console.log('console:', msg.type(), msg.text()));
  page.on('pageerror', (err) => console.log('pageerror:', err.message));
  page.on('requestfailed', (req) => console.log('requestfailed:', req.url(), req.failure()?.errorText));
  await page.goto('http://127.0.0.1:3000/chat', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(12000);
  console.log('url=', page.url());
  console.log('bodySnippet=', (await page.locator('body').innerText()).slice(0, 2000));
  await browser.close();
})();
