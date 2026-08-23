#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { bindTranscriptSeek, followPlayback } from "./src/seek.js";

function stub(t) {
  const listeners = [];
  const flags = new Set();
  return {
    dataset: { t: String(t) },
    classList: {
      toggle(name, on) {
        if (on) flags.add(name);
        else flags.delete(name);
      },
      contains(name) {
        return flags.has(name);
      },
    },
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

const s0 = stub(0);
const s1 = stub(42);
const s2 = stub(125);
const j0 = stub(0);
j0.dataset.pt = "0";
j0.dataset.jump = "0";
const live = {
  currentTime: 0,
  handlers: {},
  addEventListener(type, fn) {
    (this.handlers[type] ||= []).push(fn);
  },
};
const followRoot = {
  querySelectorAll(sel) {
    if (sel === ".seg[data-t]") return [s0, s1, s2];
    if (sel === "[data-jump]") return [j0];
    return [];
  },
};
followPlayback(followRoot, live);
live.currentTime = 50;
for (const fn of live.handlers.timeupdate) fn();
assert.equal(s0.classList.contains("now"), false);
assert.equal(s1.classList.contains("now"), true);
assert.equal(s2.classList.contains("now"), false);

const dist = join(dirname(fileURLToPath(import.meta.url)), "dist/assets");
const js = readdirSync(dist)
  .filter((n) => n.endsWith(".js"))
  .map((n) => readFileSync(join(dist, n), "utf8"))
  .join("\n");
assert.match(js, /currentTime/);
assert.match(js, /data-t/);
assert.match(js, /querySelectorAll\("\[data-t\]"\)|querySelectorAll\('\[data-t\]'\)/);
assert.match(js, /followPlayback|\.seg\[data-t\]/);

console.log("transcript seek click->currentTime ok", player.currentTime);
