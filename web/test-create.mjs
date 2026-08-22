#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { newTemplateFields } from "./src/template-create.js";

const created = newTemplateFields("probe-new", "新規", "試験", "# hi");
assert.equal(created.id, "probe-new");
assert.equal(created.title, "新規");
assert.throws(() => newTemplateFields("bad id", "x", "", ""));

const root = dirname(fileURLToPath(import.meta.url));
const main = readFileSync(join(root, "src/main.ts"), "utf8");
assert.match(main, /id="create-template"/);
assert.match(main, /id="new-id"/);
assert.match(main, /id="create"/);
assert.match(main, /newTemplateFields/);
const dist = join(root, "dist/assets");
const js = readdirSync(dist)
  .filter((n) => n.endsWith(".js"))
  .map((n) => readFileSync(join(dist, n), "utf8"))
  .join("\n");
assert.match(js, /create-template/);
assert.match(js, /new-id/);

console.log("template create UI ok", created.id);
