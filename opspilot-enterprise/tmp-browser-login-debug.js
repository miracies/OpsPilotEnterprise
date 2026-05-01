const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  page.on('response', async (res) => {
    const url = res.url();
    if (url.includes('/api/v1/auth/')) {
      console.log('response:', res.status(), url);
      try { console.log('body:', await res.text()); } catch {}
    }
  });
  await page.goto('http://localhost:3000/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('#username').fill('admin');
  await page.locator('#password').fill('admin123');
  await page.getByRole('button', { name: /登录/ }).click();
  await page.waitForTimeout(8000);
  console.log('url=', page.url());
  console.log('body=', (await page.locator('body').innerText()).slice(0, 2000));
  await browser.close();
})();
