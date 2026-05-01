const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  page.on('console', (msg) => console.log('console:', msg.type(), msg.text()));
  page.on('pageerror', (err) => console.log('pageerror:', err.message));
  await page.goto('http://localhost:3000/chat', { waitUntil: 'domcontentloaded', timeout: 60000 });
  console.log('startUrl=', page.url());
  if (page.url().includes('/login')) {
    await page.locator('input').nth(0).fill('admin');
    await page.locator('input').nth(1).fill('admin123');
    await page.getByRole('button', { name: '登录' }).click();
    await page.waitForTimeout(10000);
  }
  console.log('endUrl=', page.url());
  console.log('textareaCount=', await page.locator('textarea').count());
  console.log('body=', (await page.locator('body').innerText()).slice(0, 3000));
  await browser.close();
})();
