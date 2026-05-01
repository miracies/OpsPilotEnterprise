const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:3000/chat', { waitUntil: 'networkidle', timeout: 60000 });
  console.log(await page.title());
  await browser.close();
})();
