const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const CASES_PATH = path.join(ROOT, "tests", "data", "intent_understanding_cases.json");
const OUT_DIR = path.join(ROOT, "tmp", "intent-eval");
const PAGE_REPORT_PATH = path.join(OUT_DIR, "page-report.json");

const WEB_BASE = "http://localhost:3000";
const BFF_BASE = "http://localhost:8000";
const COOKIE_NAME = "opspilot_token";

fs.mkdirSync(OUT_DIR, { recursive: true });

function loadCases() {
  return JSON.parse(fs.readFileSync(CASES_PATH, "utf8"))
    .filter((item) => item.current_phase === "read_only" && item.page_enabled)
    .slice(0, 10);
}

async function login(context, page) {
  const resp = await fetch(`${BFF_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username: "admin", password: "admin123" }),
  });
  const setCookie = resp.headers.get("set-cookie") || "";
  const match = setCookie.match(new RegExp(`${COOKIE_NAME}=([^;]+)`));
  if (!match) throw new Error("auth_cookie_not_found");
  await context.addCookies([
    {
      name: COOKIE_NAME,
      value: match[1],
      domain: "localhost",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  await page.goto(`${WEB_BASE}/chat`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForFunction(() => !!document.querySelector("textarea"), { timeout: 30000 });
}

async function fetchJson(page, url, options) {
  return await page.evaluate(async ({ url, options }) => {
    const res = await fetch(url, options);
    return await res.json();
  }, { url, options });
}

async function latestSessionId(page, beforeIds) {
  for (let i = 0; i < 20; i += 1) {
    const list = await fetchJson(page, `${BFF_BASE}/api/v1/chat/sessions`);
    const sessions = list?.data || [];
    const fresh = sessions.find((item) => !beforeIds.has(item.id));
    if (fresh) return fresh.id;
    await page.waitForTimeout(500);
  }
  return null;
}

async function waitFinalMessage(page, sessionId) {
  let last = null;
  for (let i = 0; i < 80; i += 1) {
    const payload = await fetchJson(page, `${BFF_BASE}/api/v1/chat/sessions/${sessionId}/messages`);
    const messages = payload?.data || [];
    const assistants = messages.filter((item) => item.role === "assistant");
    last = assistants[assistants.length - 1] || null;
    if (last && last.status && last.status !== "in_progress") return last;
    await page.waitForTimeout(1000);
  }
  return last;
}

async function runCase(browser, testCase) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1800 } });
  const page = await context.newPage();
  await login(context, page);

  const before = await fetchJson(page, `${BFF_BASE}/api/v1/chat/sessions`);
  const beforeIds = new Set((before?.data || []).map((item) => item.id));

  await page.locator("textarea").fill(testCase.input);
  await page.locator("textarea").press("Enter");

  const sessionId = await latestSessionId(page, beforeIds);
  if (!sessionId) {
    await context.close();
    return {
      case_id: testCase.case_id,
      status: "failed",
      root_causes: ["ui_render_gap"],
      reason: "session_not_created",
    };
  }

  const initial = await waitFinalMessage(page, sessionId);
  let bodyText = await page.locator("body").innerText();
  let clarifyClicked = false;

  if (testCase.page_followup_selection && bodyText.includes("候选目标对象")) {
    const button = page.getByRole("button", { name: testCase.page_followup_selection }).first();
    if (await button.count()) {
      await button.click();
      clarifyClicked = true;
      for (let i = 0; i < 60; i += 1) {
        await page.waitForTimeout(1000);
        bodyText = await page.locator("body").innerText();
        if ((testCase.page_followup_expect || []).every((token) => bodyText.includes(token))) {
          break;
        }
      }
    }
  }

  const checks = {
    timeline_visible: bodyText.includes("执行状态时间线"),
    expected_text:
      (testCase.expected_answer_shape || []).some((token) => bodyText.includes(token)) ||
      (!!testCase.expected_target_resolution && bodyText.includes(testCase.expected_target_resolution)),
    clarify_visible: testCase.expected_next_step !== "clarify" || bodyText.includes("候选目标对象") || bodyText.includes("多个可能的目标对象"),
    followup_visible: !testCase.page_followup_expect || testCase.page_followup_expect.every((token) => bodyText.includes(token)),
  };

  const passed = Object.values(checks).every(Boolean);
  const screenshotPath = path.join(OUT_DIR, `${testCase.case_id}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await context.close();

  return {
    case_id: testCase.case_id,
    input: testCase.input,
    session_id: sessionId,
    status: passed ? "passed" : "failed",
    checks,
    clarify_clicked: clarifyClicked,
    last_kind: initial?.kind,
    last_status: initial?.status,
    screenshot: screenshotPath,
    root_causes: passed ? [] : ["ui_render_gap"],
  };
}

async function main() {
  const cases = loadCases();
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const results = [];
  for (const testCase of cases) {
    results.push(await runCase(browser, testCase));
  }
  await browser.close();

  const summary = results.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});

  const report = {
    generated_at: new Date().toISOString(),
    summary,
    results,
  };
  fs.writeFileSync(PAGE_REPORT_PATH, JSON.stringify(report, null, 2), "utf8");
  console.log(JSON.stringify({ summary }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
