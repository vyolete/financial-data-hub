// Process and transport regressions. The functional smoke still runs real Chrome.
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const check = fileURLToPath(new URL("./browser_check.mjs", import.meta.url));

async function runBrowserCheck(t, childSource) {
  const dir = await mkdtemp(join(tmpdir(), "fdh-chrome-test-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const browser = join(dir, "chrome");
  if (childSource !== undefined) {
    await writeFile(browser, `#!/usr/bin/env node\n${childSource}\n`, { mode: 0o700 });
  }
  return new Promise((resolve, reject) => {
    execFile(process.execPath, [check], {
      env: { ...process.env, CHROME_BIN: browser },
      timeout: 14_000,
    }, (error, stdout, stderr) => {
      if (error?.killed) reject(error);
      else resolve({ code: error?.code ?? 0, stdout, stderr });
    });
  });
}

test("a missing executable fails immediately with its launch error", async t => {
  const { code, stderr } = await runBrowserCheck(t);
  assert.equal(code, 1);
  assert.match(stderr, /Chrome launch failed \(ENOENT\)/);
});

test("a premature exit reports status and only recognized stderr fragments", async t => {
  const { code, stderr } = await runBrowserCheck(t, `
    process.stderr.write("No usable sandbox: token=fictitious-private-value\\n");
    process.exitCode = 42;
  `);
  assert.equal(code, 1);
  assert.match(stderr, /Chrome premature exit \{"code":42,"signal":null\}|Chrome exited prematurely \(code=42/);
  assert.match(stderr, /Chrome startup stderr: No usable sandbox/);
  assert.doesNotMatch(stderr, /fictitious-private-value/);
});

test("closing the CDP output while the process lives fails immediately", async t => {
  const { code, stderr } = await runBrowserCheck(t, `
    require("node:fs").closeSync(4);
    setInterval(() => {}, 1000);
  `);
  assert.equal(code, 1);
  assert.match(stderr, /Chrome CDP output closed/);
});

test("CDP must respond to Browser.getVersion before the eight-second target deadline", async t => {
  const { code, stdout, stderr } = await runBrowserCheck(t, `
    const { createReadStream, writeSync } = require("node:fs");
    let input = "";
    const stream = createReadStream(null, { fd: 3, encoding: "utf8" });
    stream.on("data", data => {
      input += data;
      let end;
      while ((end = input.indexOf("\\0")) >= 0) {
        const request = JSON.parse(input.slice(0, end));
        input = input.slice(end + 1);
        if (request.id === 1 && request.method === "Browser.getVersion") {
          const result = { product: "Chrome/fixture", protocolVersion: "1.3" };
          writeSync(4, JSON.stringify({ id: request.id, result }) + "\\0");
        } else if (request.id !== 2 || request.method !== "Target.createTarget") {
          process.exit(99);
        }
      }
    });
  `);
  assert.equal(code, 1);
  assert.match(stdout, /Chrome CDP ready.*Chrome\/fixture/);
  assert.match(stderr, /Timed out: Target.createTarget after 8000 ms/);
});
