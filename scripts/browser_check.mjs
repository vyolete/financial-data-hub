// Real Chrome against a running portal and API backed by the synthetic PostgreSQL catalog.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const origin = process.env.FDH_BROWSER_URL ?? `http://127.0.0.1:${process.env.FDH_WEB_PORT ?? 8080}`;
const chrome = process.env.CHROME_BIN ?? (process.platform === "darwin"
  ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : "google-chrome");
const profile = await mkdtemp(join(tmpdir(), "fdh-chrome-"));
const processArgs = [
  "--headless", "--disable-background-networking", "--no-first-run",
  "--remote-debugging-pipe", `--user-data-dir=${profile}`,
];
if (process.env.FDH_CHROME_NO_SANDBOX === "1") processArgs.push("--no-sandbox");
const browser = spawn(chrome, processArgs, { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
const input = browser.stdio[3];
const output = browser.stdio[4];
const pending = new Map();
let buffer = "";
let nextId = 0;
let targetSession;
let pausedDataset;

function rejectPending(error) {
  for (const { reject } of pending.values()) reject(error);
  pending.clear();
}

browser.on("error", rejectPending);
browser.on("exit", () => rejectPending(new Error("Chrome closed unexpectedly")));
input.on("error", rejectPending);
output.setEncoding("utf8");
output.on("data", chunk => {
  buffer += chunk;
  let separator;
  while ((separator = buffer.indexOf("\0")) >= 0) {
    const message = JSON.parse(buffer.slice(0, separator));
    buffer = buffer.slice(separator + 1);
    if (message.method === "Fetch.requestPaused") pausedDataset = message.params.requestId;
    const request = pending.get(message.id);
    if (!request) continue;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  }
});

async function command(method, params = {}, sessionId = targetSession) {
  const id = ++nextId;
  let timer;
  try {
    return await new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(new Error(`Timed out: ${method}`)), 8000);
      pending.set(id, { resolve, reject });
      input.write(JSON.stringify({ id, method, params, sessionId }) + "\0");
    });
  } finally {
    clearTimeout(timer);
    pending.delete(id);
  }
}

async function evaluate(expression) {
  const { result, exceptionDetails } = await command("Runtime.evaluate", {
    expression, returnByValue: true,
  });
  if (exceptionDetails) throw new Error(result.description ?? "Browser assertion failed");
  return result.value;
}

async function waitFor(selector, expected) {
  const expression = `Array.from(document.querySelectorAll(${JSON.stringify(selector)}), item => item.textContent.trim())`;
  for (let attempt = 0; attempt < 60; ++attempt) {
    const values = await evaluate(expression).catch(() => []);
    if (expected(values)) return values;
    await delay(150);
  }
  throw new Error(`Portal state timed out: ${selector}`);
}

const titles = "main article h2";
const has = text => values => values.some(value => value.includes(text));
const matches = expected => values => JSON.stringify(values) === JSON.stringify(expected);

async function api(path) {
  const response = await fetch(origin + path, { signal: AbortSignal.timeout(8000) });
  assert.equal(response.status, 200, path);
  return response.json();
}

try {
  const { targetId } = await command("Target.createTarget", { url: "about:blank" });
  ({ sessionId: targetSession } = await command("Target.attachToTarget", { targetId, flatten: true }));
  const initial = await api("/api/v1/datasets");
  assert.ok(initial.total > 20 && initial.items.every(item => item.title.startsWith("SINTÉTICO")));
  await command("Fetch.enable", { patterns: [{ urlPattern: "*/api/v1/datasets?*" }] });
  await command("Page.navigate", { url: origin });
  await waitFor("main [role=status]", has("Cargando"));
  for (let attempt = 0; !pausedDataset && attempt < 60; ++attempt) await delay(150);
  assert.ok(pausedDataset, "Chrome intercepted the real dataset request");
  await command("Fetch.continueRequest", { requestId: pausedDataset });
  await command("Fetch.disable");
  await waitFor(titles, matches(initial.items.map(item => item.title)));

  await evaluate('document.querySelector("[name=q]").value = "ejecucion"; document.querySelector("main form").requestSubmit()');
  const filtered = await api("/api/v1/datasets?q=ejecucion");
  assert.equal(filtered.total, 1);
  await waitFor(titles, matches(filtered.items.map(item => item.title)));
  await evaluate('document.querySelector("main article h2 a").click()');
  await waitFor("main h1", has(filtered.items[0].title));
  await waitFor("main", has("Revisión pendiente"));
  await waitFor("main", has("Citar como fuente sintética."));
  await waitFor("main", has("Condición sintética de acceso"));
  await evaluate('Array.from(document.querySelectorAll("main button")).find(b => b.textContent.includes("historial completo")).click()');
  const provenance = await api(`/api/v1/datasets/${filtered.items[0].id}/provenance`);
  await waitFor("main nav", has(`${provenance.total} resultados`));

  for (const query of ["Restringido", "Oculto", "denegada"]) {
    assert.equal((await api(`/api/v1/datasets?q=${query}`)).total, 0);
  }
  await command("Page.navigate", { url: origin + "/datasets/00000000-0000-0000-0000-000000000000" });
  await waitFor("main [role=status]", has("Recurso no encontrado."));
  await command("Page.navigate", { url: origin + "/runs" });
  const runs = await api("/api/v1/runs");
  await waitFor("main article .run-status", matches(runs.items.map(run => ({
    running: "En curso", succeeded: "Exitosa", partial: "Parcial", failed: "Fallida",
  })[run.status])));
  await waitFor("main article", has("Truncada"));
  const failed = runs.items.find(run => run.status === "failed");
  assert.equal(failed.persistence_ms, 0);
  await command("Page.navigate", { url: origin + "/runs/" + failed.id });
  await waitFor("main", has("synthetic timeout"));
  assert.equal(await evaluate(`Array.from(document.querySelectorAll("dt")).find(d => d.textContent === "Persistencia (ms)").nextElementSibling.textContent`), "0");

  await command("Page.navigate", { url: origin + "/datasets" });
  await waitFor(titles, matches(initial.items.map(item => item.title)));
  await evaluate('document.querySelector("[name=q]").value = "inexistente-browser"; document.querySelector("main form").requestSubmit()');
  await waitFor("main [role=status]", has("Sin resultados."));

  await command("Network.enable");
  await command("Network.setBlockedURLs", { urls: ["*/api/v1/datasets*"] });
  await command("Page.navigate", { url: origin });
  await waitFor("main [role=alert]", has("No se pudo cargar"));
  console.log("ok   Chrome: API parity, search, provenance, hidden metadata, run metrics, loading, empty, missing and failed states");
} finally {
  if (browser.pid && browser.exitCode === null && browser.signalCode === null) {
    await new Promise(resolve => {
      browser.once("exit", resolve);
      browser.kill();
    });
  }
  await rm(profile, { recursive: true, force: true, maxRetries: 3 });
}
