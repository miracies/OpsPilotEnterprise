const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  page.on('response', async (res) => {
    const url = res.url();
    if (url.includes('/api/') || url.includes('/chat') || url.includes('/_next/')) {
      console.log('response:', res.status(), url);
    }
  });
  page.on('requestfailed', (req) => console.log('requestfailed:', req.url(), req.failure()?.errorText));
  await page.goto('http://127.0.0.1:3000/chat', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(10000);
  console.log('body=', await page.locator('body').innerText());
  await browser.close();
})();
