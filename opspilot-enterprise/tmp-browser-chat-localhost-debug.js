const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  page.on('console', (msg) => console.log('console:', msg.type(), msg.text()));
  page.on('pageerror', (err) => console.log('pageerror:', err.message));
  page.on('response', async (res) => {
    const url = res.url();
    if (url.includes('/api/') || url.includes('/login') || url.includes('/chat')) {
      console.log('response:', res.status(), url);
      if (url.includes('/api/')) {
        try { console.log('body:', await res.text()); } catch {}
      }
    }
  });
  page.on('requestfailed', (req) => console.log('requestfailed:', req.url(), req.failure()?.errorText));
  await page.goto('http://localhost:3000/chat', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(12000);
  console.log('url=', page.url());
  console.log('body=', await page.locator('body').innerText());
  await browser.close();
})();
