const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const outDir = path.resolve('tmp-browser-artifacts');

async function login(page) {
  await page.goto('http://localhost:3000/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('#username').fill('admin');
  await page.locator('#password').fill('admin123');
  await page.getByRole('button', { name: /登录/ }).click();
  await page.waitForURL('http://localhost:3000/', { timeout: 60000 });
  await page.goto('http://localhost:3000/chat', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(() => !!document.querySelector('textarea'), { timeout: 30000 });
}

async function startFreshSession(page) {
  const newBtn = page.getByRole('button', { name: /新建/ });
  if (await newBtn.count()) {
    await newBtn.click();
    await page.waitForTimeout(1000);
  }
}

async function runCase(browser, name, message, waitFn) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1800 } });
  const page = await context.newPage();
  await login(page);
  await startFreshSession(page);
  await page.locator('textarea').fill(message);
  await page.getByRole('button', { name: '发送' }).click();
  await waitFn(page);
  await page.waitForTimeout(2500);
  const bodyText = await page.locator('body').innerText();
  const screenshotPath = path.join(outDir, `${name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  fs.writeFileSync(path.join(outDir, `${name}.txt`), bodyText, 'utf8');
  await context.close();
  return { name, screenshotPath, bodyText };
}

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const results = [];
  results.push(await runCase(browser, 'host-fqdn', '分析主机 esx06.vstecs.lab 健康情况', async (page) => {
    await page.waitForFunction(() => {
      const text = document.body.innerText;
      return text.includes('esx06.vstecs.lab') && !text.includes('请补充目标对象名称或 IP');
    }, { timeout: 45000 });
  }));
  results.push(await runCase(browser, 'host-shortname', '分析 esx06 健康情况', async (page) => {
    await page.waitForFunction(() => {
      const text = document.body.innerText;
      return text.includes('未在当前连接中找到目标对象') || text.includes('识别到多个可能的目标对象');
    }, { timeout: 45000 });
  }));
  await browser.close();
  console.log(JSON.stringify(results.map((item) => ({
    name: item.name,
    screenshotPath: item.screenshotPath,
    contains: {
      fqdn: item.bodyText.includes('esx06.vstecs.lab'),
      clarifyMulti: item.bodyText.includes('识别到多个可能的目标对象'),
      clarifyNotFound: item.bodyText.includes('未在当前连接中找到目标对象'),
      noMissingPrompt: !item.bodyText.includes('请补充目标对象名称或 IP'),
      intentCard: item.bodyText.includes('Intent Recovery'),
      clarifyCard: item.bodyText.includes('需要补充信息'),
      auditTimeline: item.bodyText.includes('Audit Timeline'),
      orchestratorV2: item.bodyText.includes('OrchestratorV2'),
    }
  })), null, 2));
})();
