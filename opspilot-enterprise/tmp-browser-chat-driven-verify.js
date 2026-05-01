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

async function fetchJson(page, url, options) {
  return await page.evaluate(async ({ url, options }) => {
    const res = await fetch(url, options);
    return await res.json();
  }, { url, options });
}

async function sendViaUiAndCollect(browser, name, message) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1800 } });
  const page = await context.newPage();
  await login(page);

  let createdSessionId = null;
  page.on('response', async (res) => {
    const url = res.url();
    if (url.endsWith('/api/v1/chat/sessions') && res.request().method() === 'POST') {
      try {
        const body = await res.json();
        createdSessionId = body?.data?.id ?? createdSessionId;
      } catch {}
    }
  });

  await page.locator('textarea').fill(message);
  await page.getByRole('button', { name: '发送' }).click();

  for (let i = 0; i < 20 && !createdSessionId; i += 1) {
    await page.waitForTimeout(500);
  }
  if (!createdSessionId) throw new Error(`No session created for case: ${name}`);

  let finalMessages = null;
  for (let i = 0; i < 45; i += 1) {
    const payload = await fetchJson(page, `http://localhost:8000/api/v1/chat/sessions/${createdSessionId}/messages`);
    const messages = payload?.data ?? [];
    const assistants = messages.filter((item) => item.role === 'assistant');
    const last = assistants[assistants.length - 1];
    if (last && last.status && last.status !== 'in_progress') {
      finalMessages = messages;
      break;
    }
    await page.waitForTimeout(1000);
  }

  const screenshotPath = path.join(outDir, `${name}-ui.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  const bodyText = await page.locator('body').innerText();
  fs.writeFileSync(path.join(outDir, `${name}-ui.txt`), bodyText, 'utf8');
  await context.close();

  return {
    sessionId: createdSessionId,
    messages: finalMessages,
    screenshotPath,
  };
}

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const fqdn = await sendViaUiAndCollect(browser, 'host-fqdn', '分析主机 esx06.vstecs.lab 健康情况');
  const shortName = await sendViaUiAndCollect(browser, 'host-shortname', '分析 esx06 健康情况');
  await browser.close();

  function summarize(run) {
    const assistants = (run.messages || []).filter((item) => item.role === 'assistant');
    const last = assistants[assistants.length - 1] || {};
    return {
      sessionId: run.sessionId,
      screenshotPath: run.screenshotPath,
      status: last.status,
      kind: last.kind,
      agent_name: last.agent_name,
      content: last.content,
      clarify_question: last.clarify_card?.question,
      candidate_targets: last.clarify_card?.candidate_targets,
      intent: last.intent_recovery?.chosen_intent?.intent_code,
      decision: last.intent_recovery?.decision,
      target_object_raw: last.intent_recovery?.chosen_intent?.target_object_raw,
      target_object_resolved: last.intent_recovery?.chosen_intent?.target_object_resolved,
      analysis_steps: last.analysis_steps,
    };
  }

  console.log(JSON.stringify({
    fqdn: summarize(fqdn),
    short_name: summarize(shortName),
  }, null, 2));
})();
