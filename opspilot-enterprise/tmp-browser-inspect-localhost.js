const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  page.on('console', (msg) => console.log('console:', msg.type(), msg.text()));
  page.on('pageerror', (err) => console.log('pageerror:', err.message));
  await page.goto('http://localhost:3000/chat', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(8000);
  console.log('url=', page.url());
  console.log('textareaCount=', await page.locator('textarea').count());
  console.log('buttonTexts=', await page.locator('button').evaluateAll((nodes) => nodes.map((n) => n.textContent?.trim()).filter(Boolean).slice(0, 20)));
  console.log('bodySnippet=', (await page.locator('body').innerText()).slice(0, 2000));
  await browser.close();
})();
