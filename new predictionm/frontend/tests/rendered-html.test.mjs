import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the billing forecast interface", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Billing Forecast Lab<\/title>/i);
  assert.match(html, /Offline fallback ready/);
  assert.match(html, /Ask the prediction module/);
  assert.match(html, /No LLM, PostgreSQL, or internet connection is required/);
  assert.match(html, /Run prediction/);
  assert.doesNotMatch(html, /Your site is taking shape|codex-preview|react-loading-skeleton/i);
});

test("keeps the reusable prediction module and local artifacts available", async () => {
  const [page, packageJson, module] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../../future_billing_prediction.py", import.meta.url), "utf8"),
  ]);

  assert.match(page, /routePredictionQuery/);
  assert.match(page, /forecastOfflineAmount/);
  assert.match(page, /Offline compound-growth fallback/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.match(module, /class PredictionRouter/);
  assert.match(module, /class QueryExpander/);
  assert.match(module, /class PredictionEngine/);
  assert.match(module, /class ExplainablePredictor/);
  await access(new URL("../public/billing_xgb_model.json", import.meta.url));
  await access(new URL("../public/billing_model_manifest.json", import.meta.url));
});
