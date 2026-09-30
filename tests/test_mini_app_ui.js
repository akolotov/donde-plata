// Run with: node tests/test_mini_app_ui.js
// Pure VM tests: no Telegram client, server, browser, or external requests.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
  path.join(__dirname, "../src/donde_plata/static/mini_app/app.js"), "utf8");

async function scenario(initData, response) {
  const status = { textContent: "Loading…" };
  const calls = [];
  let ready = 0;
  let expanded = 0;
  const context = {
    window: { Telegram: { WebApp: {
      initData, ready() { ready++; }, expand() { expanded++; },
    } } },
    document: { getElementById() { return status; } },
    async fetch(url, options) {
      calls.push({ url, options });
      return { ok: response.ok, async json() { return response.body; } };
    },
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  return { status, calls, ready, expanded };
}

async function main() {
  const outside = await scenario("", { ok: true, body: {} });
  assert.equal(outside.calls.length, 0);
  assert.match(outside.status.textContent, /Open this app/);
  assert.equal(outside.ready, 1);

  const success = await scenario("raw-signed-data", { ok: true, body: { user_id: 123 } });
  assert.equal(success.ready, 1);
  assert.equal(success.expanded, 1);
  assert.equal(success.calls[0].url, "./api/context");
  assert.equal(success.calls[0].options.headers.Authorization, "tma raw-signed-data");
  assert.match(success.status.textContent, /ready/);

  const expired = await scenario("expired", {
    ok: false, body: { error: "Authorization expired. Reopen the Mini App." },
  });
  assert.equal(expired.status.textContent, "Authorization expired. Reopen the Mini App.");
  console.log("Mini App UI checks passed (outside Telegram, authenticated launch, expired authorization).");
}

main().catch(error => { console.error(error); process.exitCode = 1; });
