#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { bindTranscriptSeek } from "./src/seek.js";

function stub(t) {
  const listeners = [];
  return {
    dataset: { t: String(t) },
    addEventListener(_type, fn) {
      listeners.push(fn);
    },
    click() {
      for (const fn of listeners) fn();
    },
  };
}

const a = stub(42);
const b = stub(125);
const root = { querySelectorAll: () => [a, b] };
const player = { currentTime: 0 };
bindTranscriptSeek(root, player);
a.click();
assert.equal(player.currentTime, 42);
b.click();
assert.equal(player.currentTime, 125);
const ignored = stub(7);
bindTranscriptSeek({ querySelectorAll: () => [ignored] }, null);
ignored.click();
assert.equal(player.currentTime, 125);

const dist = join(dirname(fileURLToPath(import.meta.url)), "dist/assets");
const js = readdirSync(dist)
  .filter((n) => n.endsWith(".js"))
  .map((n) => readFileSync(join(dist, n), "utf8"))
  .join("\n");
assert.match(js, /currentTime/);
assert.match(js, /data-t/);
assert.match(js, /querySelectorAll\("\[data-t\]"\)|querySelectorAll\('\[data-t\]'\)/);

console.log("transcript seek click->currentTime ok", player.currentTime);
